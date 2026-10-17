"""Модуль 7 — мониторинг ценовых расхождений между биржами (только чтение).

Модуль НЕ торгует и не использует API-ключи бирж: берёт публичные котировки
(лучший bid/ask), считает спред «купить на A, продать на B» с учётом комиссий.
Это аналитика, а не финансовый совет и не гарантия прибыли.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests

TIMEOUT = 6
CACHE_TTL = 5  # сек, чтобы не упираться в лимиты бирж
ASSETS = ("BTC", "ETH", "SOL")
HEADERS = {"User-Agent": "ella-backend/1.2"}

# Taker-комиссия, % за одну сторону. Значения ПРИБЛИЗИТЕЛЬНЫЕ —
# задайте свои по вашему тарифу через переменные окружения.
FEES_PCT = {
    "binance": float(os.getenv("FEE_BINANCE_PCT", "0.10")),
    "kraken": float(os.getenv("FEE_KRAKEN_PCT", "0.40")),
    "coinbase": float(os.getenv("FEE_COINBASE_PCT", "0.60")),
}


def _get(url, **params):
    r = requests.get(url, params=params or None, headers=HEADERS,
                     timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _binance(asset):
    # data-api.binance.vision — публичные рыночные данные
    d = _get("https://data-api.binance.vision/api/v3/ticker/bookTicker",
             symbol=f"{asset}USDT")
    return float(d["bidPrice"]), float(d["askPrice"])


def _kraken(asset):
    pair = "XBTUSDT" if asset == "BTC" else f"{asset}USDT"
    d = _get("https://api.kraken.com/0/public/Ticker", pair=pair)
    if d.get("error"):
        raise ValueError(d["error"])
    t = next(iter(d["result"].values()))
    return float(t["b"][0]), float(t["a"][0])


def _coinbase(asset):
    d = _get(f"https://api.exchange.coinbase.com/products/{asset}-USDT/ticker")
    return float(d["bid"]), float(d["ask"])


EXCHANGES = {"binance": _binance, "kraken": _kraken, "coinbase": _coinbase}
_cache = {}


def _fetch_asset(asset):
    cached = _cache.get(asset)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    quotes, errors = {}, {}

    def job(name):
        try:
            bid, ask = EXCHANGES[name](asset)
            quotes[name] = {"bid": bid, "ask": ask}
        except Exception as e:  # биржа недоступна/гео-блок/нет пары
            errors[name] = str(e)[:120]

    with ThreadPoolExecutor(max_workers=len(EXCHANGES)) as pool:
        list(pool.map(job, EXCHANGES))

    result = (quotes, errors)
    _cache[asset] = (time.time(), result)
    return result


def _best_route(quotes):
    best = None
    for buy, bq in quotes.items():
        for sell, sq in quotes.items():
            if buy == sell:
                continue
            gross = (sq["bid"] - bq["ask"]) / bq["ask"] * 100
            net = gross - FEES_PCT[buy] - FEES_PCT[sell]
            if best is None or net > best["net_pct"]:
                best = {
                    "buy_on": buy, "sell_on": sell,
                    "buy_ask": bq["ask"], "sell_bid": sq["bid"],
                    "gross_pct": round(gross, 4), "net_pct": round(net, 4),
                }
    return best


def scan(assets=None):
    assets = [a.upper() for a in (assets or ASSETS) if a.upper() in ASSETS]
    out = []
    for asset in assets:
        quotes, errors = _fetch_asset(asset)
        out.append({
            "asset": asset,
            "quotes": quotes,
            "errors": errors,
            "best": _best_route(quotes) if len(quotes) >= 2 else None,
        })
    return {
        "ts": int(time.time()),
        "fees_pct_per_side": FEES_PCT,
        "assets": out,
        "note": ("Только лучшие bid/ask. Не учтены: комиссии за вывод и сеть, "
                 "время перевода, проскальзывание, глубина стакана, "
                 "ограничения аккаунта. Не финансовый совет."),
    }


def summarize(result) -> str:
    lines = []
    for a in result["assets"]:
        b = a["best"]
        if not b:
            lines.append(f"{a['asset']}: данных недостаточно "
                         f"(доступно бирж: {len(a['quotes'])}).")
            continue
        verdict = "после комиссий в плюсе" if b["net_pct"] > 0 else "после комиссий в минусе"
        lines.append(
            f"{a['asset']}: купить на {b['buy_on']} ({b['buy_ask']:.2f}), "
            f"продать на {b['sell_on']} ({b['sell_bid']:.2f}). "
            f"Спред {b['gross_pct']:+.3f}%, чистый {b['net_pct']:+.3f}% — {verdict}."
        )
    lines.append("Без учёта вывода, сети и проскальзывания. Не финансовый совет.")
    return "\n".join(lines)
