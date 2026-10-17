"""PWA: Элла как приложение на телефоне.

Манифест, service worker и иконки создаются кодом — загружать картинки
на GitHub не нужно. Service worker кэширует только оболочку HUD
(страницу и иконки), но никогда не данные и не ответы API.
"""
import math
import struct
import zlib

MANIFEST = {
    "name": "Элла",
    "short_name": "Элла",
    "description": "Голосовой ассистент и командный центр",
    "start_url": "/hud",
    "scope": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#030a1a",
    "theme_color": "#030a1a",
    "lang": "ru",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
    ],
}

SERVICE_WORKER = """\
const CACHE = "ella-shell-v1";
const SHELL = ["/hud", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Сеть в приоритете (чтобы обновления приходили сразу), кэш — на случай офлайна.
// Кэшируем ТОЛЬКО оболочку; API и авторизация никогда не кэшируются.
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin ||
      !SHELL.includes(url.pathname)) return;
  e.respondWith(
    fetch(e.request)
      .then(r => { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request))
  );
});
"""

_icons = {}


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def icon_png(size: int) -> bytes:
    """Иконка в стиле реактора: сапфировый фон и светящиеся кольца."""
    if size in _icons:
        return _icons[size]
    cx = cy = (size - 1) / 2
    edge, center, glow = (3, 10, 26), (12, 38, 92), (74, 168, 255)
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # фильтр строки PNG
        for x in range(size):
            d = math.hypot((x - cx) / size, (y - cy) / size)
            t = max(0.0, 1 - d / 0.75)
            light = (math.exp(-((d - 0.30) / 0.022) ** 2)
                     + 0.7 * math.exp(-((d - 0.17) / 0.014) ** 2)
                     + 0.9 * math.exp(-(d / 0.05) ** 2)
                     + 0.18 * math.exp(-((d - 0.30) / 0.09) ** 2))
            for c in range(3):
                v = edge[c] + (center[c] - edge[c]) * t + glow[c] * light
                raw.append(min(255, int(v)))
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + _chunk(b"IEND", b""))
    _icons[size] = png
    return png
