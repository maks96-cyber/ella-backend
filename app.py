"""Ella backend v1.7.0 — модули 1-2 (ИИ), 4 (голос), 6 (САПР), 7, 9, 11, 13."""
import base64
import hmac
import json
import os
import time
from collections import defaultdict, deque

import requests
from flask import Flask, Response, g, jsonify, request, send_file

import arbitrage
import cad
import geology
import pwa
import quantum
import robotics
import security
import space
import tools

try:
    from flask_cors import CORS  # нужен для HUD-фронтенда в браузере
except ImportError:
    CORS = None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # фото в HUD сжимаются до ~0.3 МБ
if CORS:
    CORS(app)

VERSION = "1.7.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- Конфигурация (переменные окружения на Render) ----------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "claude")  # claude | gemini
REQUEST_TIMEOUT = 60
MAX_TOOL_ROUNDS = 4  # сколько раз подряд ИИ может вызывать инструменты
MAX_HISTORY = 12  # сообщений на сессию (хранится в памяти процесса)

# ---------- Реестр модулей (1-18) ----------
# status: "active" — есть рабочий код; "planned" — только промпт-персона
MODULES = {
    1: ("Интеграция ИИ (Gemini)", "active"),
    2: ("Интеграция ИИ (Claude)", "active"),
    3: ("Саморазвитие и детское обучение", "basic"),
    4: ("Голосовой интерфейс и распознавание речи", "beta"),
    5: ("Духовные знания", "basic"),
    6: ("Инженерия и САПР (Компас-3D, SolidWorks)", "beta"),
    7: ("Крипто- и финансовый арбитраж", "active"),
    8: ("Спутниковая связь GNSS и Direct-to-Cell", "active"),
    9: ("Глубинная геология (4-5+ км)", "active"),
    10: ("Роботизированное извлечение", "basic"),
    11: ("Кибербезопасность и защита HMAC-SHA256", "active"),
    12: ("Конструирование роботов и шасси", "active"),
    13: ("Квантовая физика, энергетика и биология", "active"),
    14: ("Космическая геологоразведка (Psyche-16)", "basic"),
    15: ("Ионная логистика", "active"),
    16: ("Сапфировый HUD: данные (/status)", "active"),
    17: ("Сапфировый HUD: интерфейс (/hud)", "active"),
    18: ("Оркестрация: маршрутизация и инструменты ИИ", "active"),
}

BASE_PROMPT = (
    "Ты — Элла, голосовой ассистент и командный центр в стиле Джарвиса. "
    "Отвечай по-русски, кратко и по делу, как инженер-партнёр. "
    "Если не уверена или данных нет — прямо так и скажи. "
    "Ответ читается вслух: пиши обычным текстом без markdown-разметки "
    "(без звёздочек, решёток и таблиц), формулы записывай словами или простым текстом. "
    "Для численных расчётов (геология, физика, энергетика, инженерия) и текущих котировок "
    "ВСЕГДА вызывай доступные инструменты, а не считай в уме; если инструмент вернул "
    "ошибку — объясни её и попроси недостающие данные. Называй числа с единицами измерения "
    "и упоминай допущения расчёта. "
    "Если к сообщению приложено фото: сначала кратко скажи, что на нём; чертежи, схемы, "
    "карты, разрезы и образцы породы разбирай по частям, читай размеры и подписи и "
    "отмечай, где не уверена. По лицам не определяй, кто это, и не ставь медицинских "
    "диагнозов по фото."
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
    14: ("Домен: космическая геологоразведка, астероиды (в т.ч. 16 Psyche). "
         "Различай подтверждённые научные данные и гипотезы, не выдумывай цифры.",
         ("psyche", "психе", "астероид", "геологоразведк")),
    15: ("Домен: ионная и электрореактивная тяга, межпланетная логистика, delta-v.",
         ("ионн", "дельта-v", "delta-v", "гоман", "тяга", "двигател")),
    10: ("Домен: роботизированное бурение и извлечение с глубины. Безопасность "
         "работ и решения по скважине остаются за лицензированными специалистами.",
         ("извлечен", "бурильн", "колонн", "добыч")),
    3: ("Домен: саморазвитие и обучение детей. Объясняй просто и по шагам, "
        "адаптируй под возраст, проверяй понимание вопросами, поддерживай интерес. "
        "Не ставь диагнозов и не заменяй педагога, врача или психолога.",
        ("ребёнок", "ребенок", "детей", "урок", "саморазвит", "выучить")),
    5: ("Домен: духовные знания (Коран, Сихах Ситта, пророческая медицина). "
        "Отвечай уважительно. НЕ выдумывай аяты и хадисы: называй суру и номер аята, "
        "сборник и номер хадиса только когда уверена, иначе прямо скажи, что нужно "
        "сверить по первоисточнику или у знающего учёного. Богословские вопросы "
        "и фетвы оставляй учёным. Пророческая медицина — традиционные рекомендации, "
        "они не заменяют врача.",
        ("коран", "хадис", "сихах", "сунн", "пророческ", "аят", "сура", "суре")),
}

_sessions = defaultdict(lambda: deque(maxlen=MAX_HISTORY))


# ---------- Вспомогательные функции ----------
@app.errorhandler(413)
def too_large(_e):
    return jsonify({"status": "error", "response": "Запрос слишком большой (максимум 6 МБ)"}), 413


OPEN_PATHS = ("/", "/health", "/hud", "/auth/login", "/manifest.webmanifest",
              "/sw.js", "/icon-192.png", "/icon-512.png")


@app.before_request
def guard():
    """Модуль 11: rate limit + проверка подписи для всех путей, кроме / и /health."""
    if request.method == "OPTIONS" or request.path in OPEN_PATHS:
        return None
    ip = security.client_ip(request)
    if security.rate_limited(ip):
        return jsonify({"status": "error", "response": "Слишком много запросов"}), 429
    ok, reason, g.auth = security.verify_request(request)
    if not ok:
        app.logger.warning("auth denied ip=%s path=%s reason=%s", ip, request.path, reason)
        return jsonify({"status": "error", "response": "Нет доступа"}), 401
    return None


@app.after_request
def secure(resp):
    return security.add_security_headers(resp)


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


IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 4 * 1024 * 1024
_MAGIC = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n", "image/webp": b"RIFF"}


def parse_image(raw):
    """Проверяет фото из запроса. Возвращает ({mime, data}, None) или (None, текст ошибки)."""
    if not isinstance(raw, dict):
        return None, "image: нужен объект {mime, data}"
    mime = str(raw.get("mime", "")).lower()
    data = raw.get("data")
    if mime not in IMAGE_MIMES:
        return None, "Поддерживаются фото JPEG, PNG и WEBP"
    if not isinstance(data, str) or not data:
        return None, "Фото пустое"
    try:
        blob = base64.b64decode(data, validate=True)
    except Exception:
        return None, "Фото повреждено (неверный base64)"
    if len(blob) > MAX_IMAGE_BYTES:
        return None, "Фото слишком большое (максимум 4 МБ)"
    if not blob.startswith(_MAGIC[mime]) or (mime == "image/webp" and blob[8:12] != b"WEBP"):
        return None, "Файл не похож на изображение"
    return {"mime": mime, "data": data}, None


def _api_error(name: str, r) -> AIError:
    if r.status_code == 429:
        return AIError(f"{name}: лимит запросов исчерпан (429). Подождите минуту "
                       f"или проверьте квоту у провайдера")
    return AIError(f"{name} API {r.status_code}: {r.text[:200]}")


def ask_claude(system: str, history: list, trace: list, image=None) -> str:
    if not ANTHROPIC_API_KEY:
        raise AIError("ANTHROPIC_API_KEY не задан")
    messages = list(history)
    if image:
        last = messages[-1]
        messages[-1] = {"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": image["mime"], "data": image["data"]}},
            {"type": "text", "text": last["content"]},
        ]}
    for _ in range(MAX_TOOL_ROUNDS + 1):
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
                "messages": messages,
                "tools": tools.CLAUDE_TOOLS,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            raise _api_error("Claude", r)
        blocks = r.json().get("content", [])
        uses = [b for b in blocks if b.get("type") == "tool_use"]
        if not uses:
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        messages.append({"role": "assistant", "content": blocks})
        results = []
        for b in uses:
            trace.append(b["name"])
            out = tools.run(b["name"], b.get("input"))
            results.append({"type": "tool_result", "tool_use_id": b["id"],
                            "content": json.dumps(out, ensure_ascii=False)})
        messages.append({"role": "user", "content": results})
    raise AIError("слишком много вызовов инструментов подряд")


def ask_gemini(system: str, history: list, trace: list, image=None) -> str:
    if not GEMINI_API_KEY:
        raise AIError("GEMINI_API_KEY не задан")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in history
    ]
    if image:
        contents[-1]["parts"].append(
            {"inlineData": {"mimeType": image["mime"], "data": image["data"]}})
    for _ in range(MAX_TOOL_ROUNDS + 1):
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY,
                     "content-type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": contents,
                "tools": tools.GEMINI_TOOLS,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            raise _api_error("Gemini", r)
        try:
            parts = r.json()["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError):
            raise AIError("Gemini вернул пустой ответ")
        calls = [p["functionCall"] for p in parts if "functionCall" in p]
        if not calls:
            return "".join(p.get("text", "") for p in parts)
        # Ответ модели возвращаем как есть (в нём могут быть служебные подписи)
        contents.append({"role": "model", "parts": parts})
        responses = []
        for c in calls:
            trace.append(c["name"])
            out = tools.run(c["name"], c.get("args") or {})
            responses.append({"functionResponse": {
                "name": c["name"], "response": {"result": out}}})
        contents.append({"role": "user", "parts": responses})
    raise AIError("слишком много вызовов инструментов подряд")


PROVIDERS = {"claude": ask_claude, "gemini": ask_gemini}


def ask_ai(text: str, provider: str, session_id: str, explicit_module=None, image=None):
    """Возвращает (ответ, провайдер, модуль, инструменты). При сбое пробует второго."""
    mod_id = pick_module(text, explicit_module)
    system = build_system_prompt(mod_id)
    history = list(_sessions[session_id]) + [{"role": "user", "content": text}]

    order = [provider] + [p for p in PROVIDERS if p != provider]
    errors = []
    for name in order:
        try:
            trace = []
            answer = PROVIDERS[name](system, history, trace, image)
        except (AIError, requests.RequestException) as e:
            errors.append(f"{name}: {e}")
            continue
        _sessions[session_id].append({"role": "user", "content": text + (
            " [к сообщению было приложено фото]" if image else "")})
        _sessions[session_id].append({"role": "assistant", "content": answer})
        return answer, name, mod_id, trace
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
    return jsonify({
        "version": VERSION,
        "auth_mode": security.auth_mode(),
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
    data = request.get_json(silent=True) or {}
    command = str(data.get("command", "")).strip()
    image = None
    if data.get("image") is not None:
        image, err = parse_image(data["image"])
        if err:
            return jsonify({"status": "error", "response": err}), 400
        if not command:
            command = "Опиши, что на фото, и разбери подробно."
    if not command:
        return jsonify({"status": "error", "response": "Пустая команда"}), 400

    low = command.lower()
    local = image is None  # с фото всегда идём к ИИ
    # Локальные команды — без обращения к ИИ
    if local and "привет" in low:
        return jsonify({"status": "success",
                        "response": "Привет! Системы Элла активированы."})
    if local and "статус" in low:
        count = lambda st: sum(1 for _, s in MODULES.values() if s == st)
        return jsonify({
            "status": "success",
            "response": f"Из {len(MODULES)} модулей: активных {count('active')}, "
                        f"базовых {count('basic')}, в бета-тесте {count('beta')}, "
                        f"в плане {count('planned')}. Подробности — GET /status.",
        })

    if local and any(w in low for w in ("арбитраж", "спред")):
        try:
            text = arbitrage.summarize(arbitrage.scan())
        except Exception as e:
            return jsonify({"status": "error",
                            "response": f"Сбой модуля 7: {e}"}), 502
        return jsonify({"status": "success", "response": text, "module": 7})

    provider = str(data.get("provider", DEFAULT_PROVIDER)).lower()
    if provider not in PROVIDERS:
        provider = DEFAULT_PROVIDER
    session_id = str(data.get("session_id", "default"))[:64]
    explicit = data.get("module")
    explicit = explicit if isinstance(explicit, int) else None

    try:
        answer, used, mod_id, used_tools = ask_ai(command, provider, session_id, explicit, image)
    except AIError as e:
        return jsonify({"status": "error", "response": f"Сбой ИИ: {e}"}), 502

    return jsonify({
        "status": "success",
        "response": answer,
        "provider": used,
        "module": mod_id,
        "tools": used_tools,
    })


@app.route("/arbitrage/scan")
def arbitrage_scan():
    """GET /arbitrage/scan?assets=BTC,ETH — публичные котировки и спреды."""
    assets = [a for a in request.args.get("assets", "").split(",") if a] or None
    try:
        return jsonify(arbitrage.scan(assets))
    except Exception as e:
        return jsonify({"status": "error", "response": f"Сбой модуля 7: {e}"}), 502


# ---------- Расчётные модули 9 и 13 ----------
CALC_DOMAINS = {
    "cad": (6, cad.CALCS),
    "geology": (9, geology.CALCS),
    "space": (8, space.CALCS),
    "robotics": (12, robotics.CALCS),
    "quantum": (13, quantum.CALCS),
}


@app.route("/calc/<domain>")
def calc_list(domain):
    """GET /calc/geology — список расчётов и их параметров."""
    entry = CALC_DOMAINS.get(domain)
    if not entry:
        return jsonify({"status": "error", "response": "Неизвестный раздел"}), 404
    mod_id, calcs = entry
    return jsonify({
        "module": mod_id,
        "calcs": {name: params for name, (_, params) in calcs.items()},
    })


@app.route("/calc/<domain>/<name>", methods=["POST"])
def calc_run(domain, name):
    """POST /calc/geology/thermal  {"depth_km": 5}"""
    entry = CALC_DOMAINS.get(domain)
    if not entry or name not in entry[1]:
        return jsonify({"status": "error", "response": "Неизвестный расчёт"}), 404
    mod_id, calcs = entry
    params = request.get_json(silent=True)
    if not isinstance(params, dict):
        return jsonify({"status": "error", "response": "Нужен JSON-объект"}), 400
    try:
        result = calcs[name][0](params)
    except ValueError as e:
        return jsonify({"status": "error", "response": str(e)}), 400
    return jsonify({"status": "success", "module": mod_id,
                    "calc": name, "result": result})


# ---------- Модуль 4: голосовой HUD и вход ----------
@app.route("/hud")
def hud():
    return send_file(os.path.join(BASE_DIR, "static", "hud.html"))


@app.route("/auth/login", methods=["POST"])
def auth_login():
    ip = security.client_ip(request)
    if security.login_rate_limited(ip):
        return jsonify({"status": "error", "response": "Слишком много попыток"}), 429
    if not security.login_configured():
        return jsonify({"status": "error", "response": "Вход не настроен на сервере"}), 503
    data = request.get_json(silent=True) or {}
    if not security.check_login(str(data.get("passphrase", ""))):
        app.logger.warning("login failed ip=%s", ip)
        return jsonify({"status": "error", "response": "Неверная кодовая фраза"}), 401
    token, exp = security.issue_token()
    return jsonify({"status": "success", "token": token, "expires_at": exp})


# ---------- Приложение (PWA): манифест, service worker, иконки ----------
@app.route("/manifest.webmanifest")
def pwa_manifest():
    resp = Response(json.dumps(pwa.MANIFEST, ensure_ascii=False),
                    mimetype="application/manifest+json")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/sw.js")
def pwa_sw():
    resp = Response(pwa.SERVICE_WORKER, mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/icon-<int:size>.png")
def pwa_icon(size):
    if size not in (192, 512):
        return jsonify({"status": "error", "response": "Нет такой иконки"}), 404
    resp = Response(pwa.icon_png(size), mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# ---------- Модуль 6: САПР ----------
def _bridge_only():
    """Очередь заданий для моста доступна только по HMAC-подписи (не по токену HUD)."""
    if g.get("auth") != "hmac":
        return jsonify({"status": "error",
                        "response": "Только для моста с HMAC-подписью"}), 403
    return None


@app.route("/cad")
def cad_info():
    return jsonify({
        "module": 6,
        "bridge_actions": list(cad.ACTIONS),
        "dxf": {k: doc for k, (_, doc) in cad.GENERATORS.items()},
        "calcs": {k: doc for k, (_, doc) in cad.CALCS.items()},
    })


@app.route("/cad/dxf/<kind>", methods=["POST"])
def cad_dxf(kind):
    """POST /cad/dxf/flange {...} — вернёт DXF-файл для Компаса/SolidWorks."""
    entry = cad.GENERATORS.get(kind)
    if not entry:
        return jsonify({"status": "error", "response": "Неизвестный чертёж"}), 404
    params = request.get_json(silent=True)
    if not isinstance(params, dict):
        return jsonify({"status": "error", "response": "Нужен JSON-объект"}), 400
    try:
        dxf = entry[0](params)
    except ValueError as e:
        return jsonify({"status": "error", "response": str(e)}), 400
    return Response(dxf, mimetype="application/dxf", headers={
        "Content-Disposition": f"attachment; filename={kind}.dxf"})


@app.route("/cad/jobs", methods=["GET", "POST"])
def cad_jobs():
    if request.method == "GET":
        return jsonify({"jobs": cad.list_jobs()})
    data = request.get_json(silent=True) or {}
    try:
        job = cad.create_job(str(data.get("action", "")), data.get("params"))
    except ValueError as e:
        return jsonify({"status": "error", "response": str(e)}), 400
    return jsonify({"status": "success", "job": job}), 201


@app.route("/cad/jobs/<job_id>")
def cad_job(job_id):
    job = cad.get_job(job_id)
    if not job:
        return jsonify({"status": "error", "response": "Задание не найдено"}), 404
    return jsonify({"job": job})


@app.route("/cad/bridge/next")
def cad_bridge_next():
    denied = _bridge_only()
    return denied if denied else jsonify({"job": cad.claim_next()})


@app.route("/cad/bridge/result/<job_id>", methods=["POST"])
def cad_bridge_result(job_id):
    denied = _bridge_only()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    try:
        job = cad.post_result(job_id, bool(data.get("ok")), data.get("result", {}))
    except ValueError as e:
        return jsonify({"status": "error", "response": str(e)}), 400
    return jsonify({"status": "success", "job": job})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
