"""Модуль 11 — защита API: подпись HMAC-SHA256, защита от повторов, rate limit.

Схема подписи (клиент и сервер считают одинаково):
    message = METHOD \n PATH[?QUERY] \n TIMESTAMP \n NONCE \n SHA256(body)
    signature = HMAC_SHA256(secret, message), hex

Заголовки запроса: X-Ella-Timestamp, X-Ella-Nonce, X-Ella-Signature.
"""
import hashlib
import hmac
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

_lock = threading.Lock()
_nonces = {}  # nonce -> время истечения
_hits = defaultdict(deque)  # ip -> времена запросов


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


def verify_request(req):
    """Возвращает (ok, причина). Причину пишем в лог, клиенту не раскрываем."""
    if HMAC_SECRET:
        ts = req.headers.get("X-Ella-Timestamp", "")
        nonce = req.headers.get("X-Ella-Nonce", "")
        sig = req.headers.get("X-Ella-Signature", "")
        if not (ts and nonce and sig):
            return False, "missing signature headers"
        try:
            ts_int = int(ts)
        except ValueError:
            return False, "bad timestamp"
        now = int(time.time())
        if abs(now - ts_int) > MAX_SKEW:
            return False, "stale timestamp"
        if not 8 <= len(nonce) <= 64:
            return False, "bad nonce"

        expected = sign(HMAC_SECRET, req.method, _request_path(req), ts,
                        nonce, req.get_data())
        if not hmac.compare_digest(expected.encode(), sig.encode()):
            return False, "bad signature"

        # Проверка повтора — только после валидной подписи
        with _lock:
            for n in [n for n, exp in _nonces.items() if exp < now]:
                del _nonces[n]
            if nonce in _nonces:
                return False, "replayed nonce"
            _nonces[nonce] = now + MAX_SKEW * 2
        return True, "ok"

    if LEGACY_TOKEN:
        sent = req.headers.get("X-Ella-Token", "")
        if hmac.compare_digest(sent.encode(), LEGACY_TOKEN.encode()):
            return True, "ok"
        return False, "bad token"

    return True, "open"


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
