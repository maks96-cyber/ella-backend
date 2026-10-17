"""Ella backend v1.1.0 — этап 1: интеграция Gemini / Claude (модули 1-2)."""
import hmac
import os
import time
from collections import defaultdict, deque

import requests
from flask import Flask, jsonify, request

try:
    from flask_cors import CORS  # нужен для HUD-фронтенда в браузере
except ImportError:
    CORS = None

app = Flask(__name__)
if CORS:
    CORS(app)

VERSION = "1.1.0"

# ---------- Конфигурация (переменные окружения на Render) ----------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "claude")  # claude | gemini
ELLA_API_TOKEN = os.getenv("ELLA_API_TOKEN", "")  # если пусто — защита выключена
REQUEST_TIMEOUT = 60
MAX_HISTORY = 12  # сообщений на сессию (хранится в памяти процесса)

# ---------- Реестр модулей (1-18) ----------
# status: "active" — есть рабочий код; "planned" — только промпт-персона
MODULES = {
    1: ("Интеграция ИИ (Gemini)", "active"),
    2: ("Интеграция ИИ (Claude)", "active"),
    3: ("Саморазвитие и детское обучение", "planned"),
    4: ("Голосовой интерфейс и распознавание речи", "planned"),
    5: ("Духовные знания", "planned"),
    6: ("Инженерия и САПР (Компас-3D, SolidWorks)", "planned"),
    7: ("Крипто- и финансовый арбитраж", "planned"),
    8: ("Спутниковая связь GNSS и Direct-to-Cell", "planned"),
    9: ("Глубинная геология (4-5+ км)", "planned"),
    10: ("Роботизированное извлечение", "planned"),
    11: ("Кибербезопасность и защита HMAC-SHA256", "planned"),
    12: ("Конструирование роботов и шасси", "planned"),
    13: ("Квантовая физика, энергетика и биология", "planned"),
    14: ("Космическая геологоразведка (Psyche-16)", "planned"),
    15: ("Ионная логистика", "planned"),
    16: ("Сапфировый HUD: данные", "planned"),
    17: ("Сапфировый HUD: интерфейс", "planned"),
    18: ("Оркестрация и командный центр", "planned"),
}

BASE_PROMPT = (
    "Ты — Элла, голосовой ассистент и командный центр в стиле Джарвиса. "
    "Отвечай по-русски, кратко и по делу, как инженер-партнёр. "
    "Если не уверена или данных нет — прямо так и скажи."
)

# Доменные персоны для маршрутизации по ключевым словам
DOMAIN_PROMPTS = {
    6: ("Домен: инженерия и САПР. Помогай с чертежами, допусками, "
        "моделированием в Компас-3D и SolidWorks.",
        ("компас", "solidworks", "чертёж", "чертеж", "сапр", "допуск")),
    7: ("Домен: крипто и арбитраж. Давай аналитику, но не финансовые "
        "гарантии; указывай риски.",
        ("крипто", "арбитраж", "биткоин", "bitcoin", "курс", "биржа")),
    8: ("Домен: спутниковая связь, GNSS и Direct-to-Cell.",
        ("gnss", "gps", "спутник", "direct-to-cell")),
    9: ("Домен: глубинная геология и бурение на 4-5+ км.",
        ("геолог", "бурен", "скважин", "порода")),
    11: ("Домен: оборонительная кибербезопасность. Только защита, "
         "аудит и укрепление систем.",
         ("безопасн", "hmac", "уязвимост", "шифрован")),
    12: ("Домен: конструирование роботов, шасси и приводов.",
         ("робот", "шасси", "привод", "сервопривод")),
    13: ("Домен: квантовая физика, энергетика, биология.",
         ("квант", "планк", "энерги", "фотон")),
    14: ("Домен: космическая геологоразведка (астероид Psyche-16) "
         "и ионная логистика.",
         ("psyche", "астероид", "ионн", "орбит")),
}

_sessions = defaultdict(lambda: deque(maxlen=MAX_HISTORY))


# ---------- Вспомогательные функции ----------
def authorized() -> bool:
    if not ELLA_API_TOKEN:
        return True
    sent = request.headers.get("X-Ella-Token", "")
    return hmac.compare_digest(sent, ELLA_API_TOKEN)


def pick_module(text: str, explicit=None) -> int:
    if explicit in DOMAIN_PROMPTS:
        return explicit
    low = text.lower()
    for mod_id, (_, keywords) in DOMAIN_PROMPTS.items():
        if any(k in low for k in keywords):
            return mod_id
    return 0  # общий режим


def build_system_prompt(mod_id: int) -> str:
    if mod_id in DOMAIN_PROMPTS:
        return f"{BASE_PROMPT}\n{DOMAIN_PROMPTS[mod_id][0]}"
    return BASE_PROMPT


class AIError(Exception):
    pass


def ask_claude(system: str, history: list) -> str:
    if not ANTHROPIC_API_KEY:
        raise AIError("ANTHROPIC_API_KEY не задан")
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "system": system,
            "messages": history,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code != 200:
        raise AIError(f"Claude API {r.status_code}: {r.text[:200]}")
    blocks = r.json().get("content", [])
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def ask_gemini(system: str, history: list) -> str:
    if not GEMINI_API_KEY:
        raise AIError("GEMINI_API_KEY не задан")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in history
    ]
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": GEMINI_API_KEY,
                 "content-type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code != 200:
        raise AIError(f"Gemini API {r.status_code}: {r.text[:200]}")
    try:
        parts = r.json()["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise AIError("Gemini вернул пустой ответ")
    return "".join(p.get("text", "") for p in parts)


PROVIDERS = {"claude": ask_claude, "gemini": ask_gemini}


def ask_ai(text: str, provider: str, session_id: str, explicit_module=None):
    """Возвращает (ответ, провайдер, модуль). При сбое пробует второго провайдера."""
    mod_id = pick_module(text, explicit_module)
    system = build_system_prompt(mod_id)
    history = list(_sessions[session_id]) + [{"role": "user", "content": text}]

    order = [provider] + [p for p in PROVIDERS if p != provider]
    errors = []
    for name in order:
        try:
            answer = PROVIDERS[name](system, history)
        except (AIError, requests.RequestException) as e:
            errors.append(f"{name}: {e}")
            continue
        _sessions[session_id].append({"role": "user", "content": text})
        _sessions[session_id].append({"role": "assistant", "content": answer})
        return answer, name, mod_id
    raise AIError("; ".join(errors))


# ---------- Эндпоинты ----------
@app.route("/")
def home():
    return jsonify({"status": "online", "assistant": "Ella", "version": VERSION})


@app.route("/health")
def health():
    return jsonify({"ok": True, "ts": int(time.time())})


@app.route("/status")
def status():
    if not authorized():
        return jsonify({"status": "error", "response": "Нет доступа"}), 401
    return jsonify({
        "version": VERSION,
        "providers": {
            "claude": {"configured": bool(ANTHROPIC_API_KEY), "model": CLAUDE_MODEL},
            "gemini": {"configured": bool(GEMINI_API_KEY), "model": GEMINI_MODEL},
        },
        "modules": [
            {"id": i, "name": n, "status": s} for i, (n, s) in MODULES.items()
        ],
    })


@app.route("/command", methods=["POST"])
def handle_command():
    if not authorized():
        return jsonify({"status": "error", "response": "Нет доступа"}), 401

    data = request.get_json(silent=True) or {}
    command = str(data.get("command", "")).strip()
    if not command:
        return jsonify({"status": "error", "response": "Пустая команда"}), 400

    low = command.lower()
    # Локальные команды — без обращения к ИИ
    if "привет" in low:
        return jsonify({"status": "success",
                        "response": "Привет! Системы Элла активированы."})
    if "статус" in low:
        active = sum(1 for _, s in MODULES.values() if s == "active")
        return jsonify({
            "status": "success",
            "response": f"Активно модулей: {active} из {len(MODULES)}. "
                        f"Подробности — GET /status.",
        })

    provider = str(data.get("provider", DEFAULT_PROVIDER)).lower()
    if provider not in PROVIDERS:
        provider = DEFAULT_PROVIDER
    session_id = str(data.get("session_id", "default"))[:64]
    explicit = data.get("module")
    explicit = explicit if isinstance(explicit, int) else None

    try:
        answer, used, mod_id = ask_ai(command, provider, session_id, explicit)
    except AIError as e:
        return jsonify({"status": "error", "response": f"Сбой ИИ: {e}"}), 502

    return jsonify({
        "status": "success",
        "response": answer,
        "provider": used,
        "module": mod_id,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
