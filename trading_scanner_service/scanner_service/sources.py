from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Iterable


class SourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


CRYPTO = {
    "BTC": "BTC_USDT",
    "ETH": "ETH_USDT",
    "BNB": "BNB_USDT",
    "SOL": "SOL_USDT",
    "XRP": "XRP_USDT",
    "DOGE": "DOGE_USDT",
    "ADA": "ADA_USDT",
    "AVAX": "AVAX_USDT",
    "LINK": "LINK_USDT",
    "DOT": "DOT_USDT",
    "LTC": "LTC_USDT",
    "BCH": "BCH_USDT",
    "SUI": "SUI_USDT",
    "HYPE": "HYPE_USDT",
    "PEPE": "PEPE_USDT",
    "ZEC": "ZEC_USDT",
    "TAO": "TAO_USDT",
    "WLD": "WLD_USDT",
    # US stocks are normalized through the existing *_USDT canonical keys,
    # then routed to Gate TradFi by GATE_TRADFI_NORMALIZED.
    "TSLA": "TSLA_USDT",
    "NVDA": "NVDA_USDT",
    "MSTR": "MSTR_USDT",
    "CRCL": "CRCL_USDT",
    # Semis stock perps on Gate USDT-M futures (verified live 2026-07-20).
    "MU": "MU_USDT",
    "MICRON": "MU_USDT",
    "SKHYNIX": "SKHYNIX_USDT",
    "HYNIX": "SKHYNIX_USDT",
    "SNDK": "SNDK_USDT",
    "SANDISK": "SNDK_USDT",
}

# Legacy canonical aliases retained for symbol normalization only. These names
# do not select a MEXC data source; MarketDataRouter is Gate-only.
MEXC_CFD = {
    "XAU": "XAU_USDT",
    "XAUUSD": "XAU_USDT",
    "GOLD": "XAU_USDT",
    "XAG": "SILVER_USDT",
    "XAGUSD": "SILVER_USDT",
    "SILVER": "SILVER_USDT",
    "NAS": "NAS100_USDT",
    "NAS100": "NAS100_USDT",
    "US100": "NAS100_USDT",
    "SPX": "SPX500_USDT",
    "US500": "SPX500_USDT",
    "SP500": "SPX500_USDT",
    "DJI": "US30_USDT",
    "US30": "US30_USDT",
    "XTI": "USOIL_USDT",
    "XTIUSD": "USOIL_USDT",
    "OIL": "USOIL_USDT",
}

GATE_TRADFI_CFD = {
    "XAU": "XAUUSD",
    "XAUUSD": "XAUUSD",
    "GOLD": "XAUUSD",
    "NAS": "NAS100",
    "NAS100": "NAS100",
    "US100": "NAS100",
    "SPX": "US500",
    "US500": "US500",
    "SP500": "US500",
    # US Dollar Index on Gate TradFi (desk alias DXY → venue USIDX).
    "DXY": "USIDX",
    "USIDX": "USIDX",
    "USDOLLAR": "USIDX",
    "USDX": "USIDX",
}

GATE_TRADFI_NORMALIZED = {
    "XAU_USDT": "XAUUSD",
    "NAS100_USDT": "NAS100",
    "SPX500_USDT": "US500",
    # Gate TradFi uses plain symbol names for these instruments.
    "SILVER_USDT": "XAGUSD",
    "US30_USDT": "US30",
    "USOIL_USDT": "XTIUSD",
    "TSLA_USDT": "TSLA",
    "NVDA_USDT": "NVDA",
    "MSTR_USDT": "MSTR",
    "CRCL_USDT": "CRCL",
    "USIDX": "DXY",
}

FX = {
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "USDCAD",
    "AUDUSD",
    "NZDUSD",
    "EURJPY",
    "GBPJPY",
    "EURGBP",
}

# MEXC parsing code remains for historical backtest utilities, but the live
# MarketDataRouter below uses Gate only and has no venue fallback.

MEXC_INTERVAL = {
    "M1": "Min1",
    "M5": "Min5",
    "M15": "Min15",
    "M30": "Min30",
    "H1": "Min60",
    "H4": "Hour4",
    "D1": "Day1",
    "W1": "Week1",
}

GATE_INTERVAL = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
    "W1": "7d",
}

TIMEFRAME_ALIASES = {
    "1M": "M1",
    "M1": "M1",
    "5M": "M5",
    "M5": "M5",
    "15M": "M15",
    "M15": "M15",
    "1H": "H1",
    "H1": "H1",
    "4H": "H4",
    "H4": "H4",
    "1D": "D1",
    "D1": "D1",
    "1W": "W1",
    "W1": "W1",
}


def _compact(symbol: str) -> str:
    return symbol.upper().replace("-", "").replace("/", "").replace("_", "")


def normalize_symbol(symbol: str) -> str:
    compact = _compact(symbol)
    if compact in ("DXY", "USIDX", "USDOLLAR", "USDX"):
        return "DXY"
    if compact.endswith("USDT") and compact[:-4] in CRYPTO:
        return f"{compact[:-4]}_USDT"
    for normalized in MEXC_CFD.values():
        if compact == _compact(normalized):
            return normalized
    if compact in CRYPTO:
        return CRYPTO[compact]
    if compact in MEXC_CFD:
        return MEXC_CFD[compact]
    if compact in FX:
        return compact
    if compact in GATE_TRADFI_CFD:
        # Canonical internal names for Gate TradFi (e.g. DXY already handled).
        mapped = GATE_TRADFI_CFD[compact]
        if mapped == "USIDX":
            return "DXY"
        return mapped if mapped in ("XAUUSD", "NAS100", "US500") else compact
    raise SourceError(f"unknown symbol: {symbol}")


def normalize_gate_tradfi_symbol(symbol: str) -> str:
    compact = _compact(symbol)
    if compact in FX:
        return compact
    if compact in GATE_TRADFI_CFD:
        return GATE_TRADFI_CFD[compact]
    normalized = normalize_symbol(symbol)
    if normalized == "DXY":
        return "USIDX"
    if normalized in GATE_TRADFI_NORMALIZED:
        return GATE_TRADFI_NORMALIZED[normalized]
    return normalized


def normalize_timeframe(tf: str) -> str:
    compact = tf.upper().replace(" ", "")
    try:
        return TIMEFRAME_ALIASES[compact]
    except KeyError as exc:
        raise SourceError(f"unsupported timeframe: {tf}") from exc


def classify_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    # 2026-07-14 / restore 2026-07-20: Bitget and MEXC removed — Gate only
    # (single source of truth, no cross-venue fallback).
    # - Crypto + MU/SKHYNIX/SNDK stock perps → Gate USDT-M futures
    # - FX / metals / indexes / oil / TSLA·NVDA·MSTR·CRCL / DXY → Gate TradFi
    if normalized == "DXY" or normalized in FX or normalized in GATE_TRADFI_NORMALIZED:
        return "gate_tradfi"
    if normalized in CRYPTO.values():
        return "gate_crypto"
    return "unrouted"


def product_kind(symbol: str) -> str:
    """Desk-facing product type: 'contract' | 'cfd' | 'unrouted'."""
    route = classify_symbol(symbol)
    if route == "gate_crypto":
        return "contract"
    if route == "gate_tradfi":
        return "cfd"
    return "unrouted"


_RATE_LIMIT_CODES = {510}


def _json_get(url: str, timeout: float = 8.0, attempts: int = 4) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "codex-local-scanner/1.0"})
    last_exc = None
    last_payload = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code != 429 or attempt == attempts - 1:
                raise SourceError(f"request failed: {url}: {exc}") from exc
            time.sleep(0.5 * (attempt + 1))
            continue
        except Exception as exc:
            raise SourceError(f"request failed: {url}: {exc}") from exc

        # MEXC signals rate limiting as HTTP 200 + {"success": false, "code": 510, ...}
        # instead of a 429 — must be detected from the body, not the status code.
        if isinstance(payload, dict) and payload.get("success") is False and payload.get("code") in _RATE_LIMIT_CODES:
            last_payload = payload
            if attempt == attempts - 1:
                break
            time.sleep(0.5 * (attempt + 1))
            continue

        return payload

    raise SourceError(f"request failed: {url}: rate limited after retries: {last_payload or last_exc}")


class MexcContractClient:
    base_url = "https://contract.mexc.com"

    def price(self, symbol: str) -> float:
        normalized = normalize_symbol(symbol)
        params = urllib.parse.urlencode({"symbol": normalized})
        payload = _json_get(f"{self.base_url}/api/v1/contract/ticker?{params}")
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            for key in ("lastPrice", "last_price", "fairPrice", "indexPrice"):
                if key in data:
                    return float(data[key])
        raise SourceError(f"MEXC ticker missing price for {normalized}")

    def bars(self, symbol: str, tf: str, limit: int) -> list[Bar]:
        normalized = normalize_symbol(symbol)
        normalized_tf = normalize_timeframe(tf)
        interval = MEXC_INTERVAL.get(normalized_tf)
        if not interval:
            raise SourceError(f"unsupported MEXC timeframe: {tf}")
        params = urllib.parse.urlencode({"interval": interval, "limit": limit})
        payload = _json_get(f"{self.base_url}/api/v1/contract/kline/{normalized}?{params}")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise SourceError(f"MEXC kline missing data for {normalized}")

        times = data.get("time", [])
        opens = data.get("open", [])
        highs = data.get("high", [])
        lows = data.get("low", [])
        closes = data.get("close", [])
        vols = data.get("vol", data.get("volume", []))
        bars = []
        for idx, ts in enumerate(times):
            bars.append(
                Bar(
                    ts=int(ts),
                    open=float(opens[idx]),
                    high=float(highs[idx]),
                    low=float(lows[idx]),
                    close=float(closes[idx]),
                    volume=float(vols[idx]) if idx < len(vols) else 0.0,
                )
            )
        return bars


class GateCryptoClient:
    # Gate.io USDT-M futures — verified live for all 17 tracked crypto symbols
    # (2026-07-14). Stock perps (TSLA/NVDA/MSTR/CRCL) are NOT here; those have
    # no Gate futures contract and route through GateTradFiClient instead.
    base_url = "https://api.gateio.ws"

    def price(self, symbol: str) -> float:
        normalized = normalize_symbol(symbol)
        params = urllib.parse.urlencode({"contract": normalized})
        payload = _json_get(f"{self.base_url}/api/v4/futures/usdt/tickers?{params}")
        if isinstance(payload, list) and payload and "last" in payload[0]:
            return float(payload[0]["last"])
        raise SourceError(f"Gate futures ticker missing price for {normalized}")

    def bars(self, symbol: str, tf: str, limit: int) -> list[Bar]:
        normalized = normalize_symbol(symbol)
        normalized_tf = normalize_timeframe(tf)
        interval = GATE_INTERVAL.get(normalized_tf)
        if not interval:
            raise SourceError(f"unsupported Gate timeframe: {tf}")
        params = urllib.parse.urlencode(
            {"contract": normalized, "interval": interval, "limit": min(int(limit), 1000)})
        payload = _json_get(f"{self.base_url}/api/v4/futures/usdt/candlesticks?{params}")
        if not isinstance(payload, list):
            raise SourceError(f"Gate futures kline missing data for {normalized}: {payload}")
        bars = [
            Bar(
                ts=int(row["t"]),
                open=float(row["o"]),
                high=float(row["h"]),
                low=float(row["l"]),
                close=float(row["c"]),
                volume=float(row.get("v", 0.0)),
            )
            for row in payload
        ]
        return sorted(bars, key=lambda bar: bar.ts)


class GateTradFiClient:
    base_url = "https://api.gateio.ws"

    def price(self, symbol: str) -> float:
        bars = self.bars(symbol, "M1", 2)
        if not bars:
            raise SourceError(f"Gate TradFi returned no price bars for {symbol}")
        return bars[-1].close

    def bars(self, symbol: str, tf: str, limit: int) -> list[Bar]:
        normalized = normalize_gate_tradfi_symbol(symbol)
        normalized_tf = normalize_timeframe(tf)
        interval = GATE_INTERVAL.get(normalized_tf)
        if not interval:
            raise SourceError(f"unsupported Gate timeframe: {tf}")
        params = urllib.parse.urlencode({"kline_type": interval, "limit": limit})
        payload = _json_get(f"{self.base_url}/api/v4/tradfi/symbols/{normalized}/klines?{params}")
        raw = payload.get("data", {}).get("list") if isinstance(payload, dict) else None
        if not isinstance(raw, list):
            raise SourceError(f"Gate TradFi kline missing list for {normalized}")

        bars = []
        for row in raw:
            ts = row.get("t", row.get("time", int(time.time())))
            bars.append(
                Bar(
                    ts=int(float(ts)),
                    open=float(row["o"]),
                    high=float(row["h"]),
                    low=float(row["l"]),
                    close=float(row["c"]),
                    volume=float(row.get("v", 0.0)),
                )
            )
        return sorted(bars, key=lambda bar: bar.ts)


class GateSpotClient:
    # Gate.io spot — context-only ratio series (e.g. ETH_BTC), never a tradeable
    # candidate quote. Spot candlesticks are a POSITIONAL array (unlike futures'
    # dict): [t, quote_volume, close, high, low, open, base_volume, window_closed].
    base_url = "https://api.gateio.ws"

    def bars(self, pair: str, tf: str, limit: int) -> list[Bar]:
        normalized_tf = normalize_timeframe(tf)
        interval = GATE_INTERVAL.get(normalized_tf)
        if not interval:
            raise SourceError(f"unsupported Gate timeframe: {tf}")
        params = urllib.parse.urlencode(
            {"currency_pair": pair, "interval": interval, "limit": min(int(limit), 1000)})
        payload = _json_get(f"{self.base_url}/api/v4/spot/candlesticks?{params}")
        if not isinstance(payload, list):
            raise SourceError(f"Gate spot kline missing data for {pair}: {payload}")
        bars = []
        for row in payload:
            # positional: [t, quote_vol, close, high, low, open, base_vol, closed]
            bars.append(
                Bar(
                    ts=int(float(row[0])),
                    open=float(row[5]),
                    high=float(row[3]),
                    low=float(row[4]),
                    close=float(row[2]),
                    volume=float(row[6]) if len(row) > 6 else 0.0,
                )
            )
        return sorted(bars, key=lambda bar: bar.ts)


class MarketDataRouter:
    # 2026-07-14: Bitget AND MEXC removed — Gate only (TradFi + futures), no
    # fallback. If Gate is down, price()/bars() raise SourceError instead of
    # silently mixing in a different venue's quote (user's explicit choice:
    # one source of truth, no cross-venue spread surprises).
    def __init__(self, gate_tradfi=None, gate_crypto=None, gate_spot=None):
        self.gate_tradfi = gate_tradfi or GateTradFiClient()
        self.gate_crypto = gate_crypto or GateCryptoClient()
        self.gate_spot = gate_spot or GateSpotClient()

    def price(self, symbol: str) -> float:
        normalized = normalize_symbol(symbol)
        route = classify_symbol(symbol)
        if route == "gate_tradfi":
            return self.gate_tradfi.price(normalized)
        if route == "gate_crypto":
            return self.gate_crypto.price(normalized)
        raise SourceError(f"no data source configured for {symbol}")

    def bars(self, symbol: str, tf: str, limit: int = 120) -> list[Bar]:
        normalized = normalize_symbol(symbol)
        route = classify_symbol(symbol)
        if route == "gate_tradfi":
            return self.gate_tradfi.bars(normalized, tf, limit)
        if route == "gate_crypto":
            return self.gate_crypto.bars(normalized, tf, limit)
        raise SourceError(f"no data source configured for {symbol}")

    def spot_bars(self, pair: str, tf: str, limit: int = 120) -> list[Bar]:
        # Context-only spot ratio series (e.g. ETH_BTC). Deliberately off the
        # symbol router so it can never be mistaken for a tradeable quote.
        return self.gate_spot.bars(pair, tf, limit)


def bars_to_dicts(bars: Iterable[Bar]) -> list[dict]:
    return [bar.to_dict() for bar in bars]
