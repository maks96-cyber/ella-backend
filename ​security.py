"""Модуль 11 — защита API: подпись HMAC-SHA256, защита от повторов, rate limit.

Схема подписи (клиент и сервер считают одинаково):
    message = METHOD \n PATH[?QUERY] \n TIMESTAMP \n NONCE \n SHA256(body)
    signature = HMAC_SHA256(secret, message), hex

Заголовки запроса: X-Ella-Timestamp, X-Ella-Nonce, X-Ella-Signature.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from collections import defaultdict, deque

log = logging.getLogger("ella.security")

HMAC_SECRET = os.getenv("ELLA_HMAC_SECRET", "").encode()
LEGACY_TOKEN = os.getenv("ELLA_API_TOKEN", "")  # запасной режим без подписи
MAX_SKEW = int(os.getenv("ELLA_MAX_SKEW", "60"))  # допуск по времени, сек
RATE_LIMIT = int(os.getenv("ELLA_RATE_LIMIT", "30"))  # запросов в минуту с IP
RATE_WINDOW = 60
LOGIN_PASSPHRASE = os.getenv("ELLA_LOGIN_PASSPHRASE", "")  # вход в HUD
SESSION_TTL = int(os.getenv("ELLA_SESSION_TTL", "3600"))  # жизнь токена, сек
LOGIN_ATTEMPTS = 5  # попыток входа в минуту с IP

_lock = threading.Lock()
_nonces = {}  # nonce -> время истечения
_hits = defaultdict(deque)  # ip -> времена запросов
_login_hits = defaultdict(deque)


def auth_mode() -> str:
    if HMAC_SECRET:
        return "hmac"
    if LEGACY_TOKEN:
        return "token"
    return "open"


def sign(secret: bytes, method: str, path: str, timestamp, nonce: str,
         body: bytes) -> str:
    body_hash = hashlib.sha256(body or b"").hexdigest()
    message = "\n".join(
        [method.upper(), path, str(timestamp), nonce, body_hash]
    ).encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _request_path(req) -> str:
    qs = req.query_string.decode("utf-8", "ignore")
    return req.path + (f"?{qs}" if qs else "")


# ---------- Сессионные токены для браузерного HUD ----------
def _session_key() -> bytes:
    return hmac.new(HMAC_SECRET, b"ella-session-v1", hashlib.sha256).digest()


def login_configured() -> bool:
    return bool(HMAC_SECRET and LOGIN_PASSPHRASE)


def check_login(passphrase: str) -> bool:
    return login_configured() and hmac.compare_digest(
        passphrase.encode(), LOGIN_PASSPHRASE.encode())


def issue_token():
    exp = int(time.time()) + SESSION_TTL
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=")
    sig = hmac.new(_session_key(), payload, hashlib.sha256).hexdigest()
    return f"{payload.decode()}.{sig}", exp


def _verify_token(token: str) -> bool:
    try:
        payload_b64, sig = token.split(".", 1)
        expected = hmac.new(_session_key(), payload_b64.encode(),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected.encode(), sig.encode()):
            return False
        pad = "=" * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        return int(data["exp"]) > time.time()
    except Exception:
        return False


def login_rate_limited(ip: str) -> bool:
    now = time.time()
    with _lock:
        q = _login_hits[ip]
        while q and now - q[0] > RATE_WINDOW:
            q.popleft()
        if len(q) >= LOGIN_ATTEMPTS:
            return True
        q.append(now)
        return False


def verify_request(req):
    """Возвращает (ok, причина, метод). Метод: hmac | bearer | token | open.
    Причину пишем в лог, клиенту не раскрываем."""
    auth = req.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        if HMAC_SECRET and _verify_token(auth[7:]):
            return True, "ok", "bearer"
        return False, "bad bearer", None

    if HMAC_SECRET:
        ts = req.headers.get("X-Ella-Timestamp", "")
        nonce = req.headers.get("X-Ella-Nonce", "")
        sig = req.headers.get("X-Ella-Signature", "")
        if not (ts and nonce and sig):
            return False, "missing signature headers", None
        try:
            ts_int = int(ts)
        except ValueError:
            return False, "bad timestamp", None
        now = int(time.time())
        if abs(now - ts_int) > MAX_SKEW:
            return False, "stale timestamp", None
        if not 8 <= len(nonce) <= 64:
            return False, "bad nonce", None

        expected = sign(HMAC_SECRET, req.method, _request_path(req), ts,
                        nonce, req.get_data())
        if not hmac.compare_digest(expected.encode(), sig.encode()):
            return False, "bad signature", None

        # Проверка повтора — только после валидной подписи
        with _lock:
            for n in [n for n, exp in _nonces.items() if exp < now]:
                del _nonces[n]
            if nonce in _nonces:
                return False, "replayed nonce", None
            _nonces[nonce] = now + MAX_SKEW * 2
        return True, "ok", "hmac"

    if LEGACY_TOKEN:
        sent = req.headers.get("X-Ella-Token", "")
        if hmac.compare_digest(sent.encode(), LEGACY_TOKEN.encode()):
            return True, "ok", "token"
        return False, "bad token", None

    return True, "open", "open"


def client_ip(req) -> str:
    # За прокси Render берём первый адрес из X-Forwarded-For (приблизительно)
    fwd = req.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() if fwd else req.remote_addr) or "unknown"


def rate_limited(ip: str) -> bool:
    now = time.time()
    with _lock:
        q = _hits[ip]
        while q and now - q[0] > RATE_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return True
        q.append(now)
        if len(_hits) > 5000:  # чистим пустые записи
            for k in [k for k, v in _hits.items() if not v]:
                del _hits[k]
        return False


def add_security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store"
    return resp
