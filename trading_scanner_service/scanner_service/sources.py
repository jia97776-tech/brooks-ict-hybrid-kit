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
    # US stock perps on Bitget usdt-futures (pilot 2026-07-11, scan-only).
    # 24/7 synthetic pricing off-RTH — desk rule: triggers only during US RTH.
    "TSLA": "TSLA_USDT",
    "NVDA": "NVDA_USDT",
    "MSTR": "MSTR_USDT",
    "CRCL": "CRCL_USDT",
}

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
}

GATE_TRADFI_NORMALIZED = {
    "XAU_USDT": "XAUUSD",
    "NAS100_USDT": "NAS100",
    "SPX500_USDT": "US500",
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

# Bitget USDT-M futures (switched from MEXC for crypto+metals 2026-07-10, user request).
# Coverage verified by probe: all 11 crypto + XAUUSDT/XAGUSDT are liquid; NDX100USDT
# exists but prints flat zero-volume M1 bars (unusable for sweep detection) and there
# is NO Bitget product for US500/US30/oil/FX — those stay on MEXC / Gate tradfi.
BITGET = {sym: f"{sym}USDT" for sym in (
    "BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
    "LTC", "BCH", "SUI", "HYPE", "PEPE", "ZEC", "TAO", "WLD",
    "TSLA", "NVDA", "MSTR", "CRCL")}
BITGET_NORMALIZED = {f"{sym}_USDT": f"{sym}USDT" for sym in BITGET}

# Bitget TradFi (MT5 CFD venue) public kline API, discovered 2026-07-10 via the
# web app's own XHR (getMoreKlineDataV2). Unauthenticated, 1000 bars/call,
# steps 1m..1w, last bar ~45s fresh. Covers FX + metals + US indexes + oil
# (WTI = USOUSD, Brent = UKOUSD). Undocumented endpoint — router falls back
# to Gate/MEXC on any failure.
BITGET_TRADFI = {
    "XAU_USDT": "XAUUSD",
    "SILVER_USDT": "XAGUSD",
    "NAS100_USDT": "NAS100",
    "SPX500_USDT": "US500",
    "US30_USDT": "US30",
    "USOIL_USDT": "USOUSD",  # WTI; Brent would be UKOUSD
}
BITGET_TRADFI.update({fx: fx for fx in (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD")})

BITGET_TRADFI_INTERVAL = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
    "W1": "1w",
}

BITGET_INTERVAL = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1H",
    "H4": "4H",
    "D1": "1D",
    "W1": "1W",
}

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
    raise SourceError(f"unknown symbol: {symbol}")


def normalize_gate_tradfi_symbol(symbol: str) -> str:
    compact = _compact(symbol)
    if compact in FX:
        return compact
    if compact in GATE_TRADFI_CFD:
        return GATE_TRADFI_CFD[compact]
    normalized = normalize_symbol(symbol)
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
    if normalized in BITGET_NORMALIZED:
        return "bitget_mix"
    if normalized in BITGET_TRADFI:
        return "bitget_tradfi"
    if normalized in FX or normalized in GATE_TRADFI_NORMALIZED:
        return "gate_tradfi"
    return "mexc_contract"


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


class BitgetMixClient:
    base_url = "https://api.bitget.com"

    def _bitget_symbol(self, symbol: str) -> str:
        normalized = normalize_symbol(symbol)
        try:
            return BITGET_NORMALIZED[normalized]
        except KeyError as exc:
            raise SourceError(f"symbol not on Bitget: {symbol}") from exc

    def price(self, symbol: str) -> float:
        bg = self._bitget_symbol(symbol)
        params = urllib.parse.urlencode({"symbol": bg, "productType": "usdt-futures"})
        payload = _json_get(f"{self.base_url}/api/v2/mix/market/ticker?{params}")
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, list) and data and "lastPr" in data[0]:
            return float(data[0]["lastPr"])
        raise SourceError(f"Bitget ticker missing price for {bg}: {payload}")

    def bars(self, symbol: str, tf: str, limit: int) -> list[Bar]:
        bg = self._bitget_symbol(symbol)
        normalized_tf = normalize_timeframe(tf)
        interval = BITGET_INTERVAL.get(normalized_tf)
        if not interval:
            raise SourceError(f"unsupported Bitget timeframe: {tf}")
        params = urllib.parse.urlencode(
            {"symbol": bg, "productType": "usdt-futures",
             "granularity": interval, "limit": min(int(limit), 1000)})
        payload = _json_get(f"{self.base_url}/api/v2/mix/market/candles?{params}")
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise SourceError(f"Bitget kline missing data for {bg}: {payload}")
        bars = [
            Bar(
                ts=int(int(row[0]) // 1000),  # Bitget returns ms; the stack runs on seconds
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]) if len(row) > 5 else 0.0,
            )
            for row in rows
        ]
        return sorted(bars, key=lambda bar: bar.ts)


class BitgetTradFiClient:
    base_url = "https://www.bitgettradfi.com"

    def _tradfi_symbol(self, symbol: str) -> str:
        normalized = normalize_symbol(symbol)
        try:
            return BITGET_TRADFI[normalized]
        except KeyError as exc:
            raise SourceError(f"symbol not on Bitget TradFi: {symbol}") from exc

    def price(self, symbol: str) -> float:
        bars = self.bars(symbol, "M1", 2)
        if not bars:
            raise SourceError(f"Bitget TradFi returned no price bars for {symbol}")
        return bars[-1].close

    def bars(self, symbol: str, tf: str, limit: int) -> list[Bar]:
        tradfi = self._tradfi_symbol(symbol)
        normalized_tf = normalize_timeframe(tf)
        interval = BITGET_TRADFI_INTERVAL.get(normalized_tf)
        if not interval:
            raise SourceError(f"unsupported Bitget TradFi timeframe: {tf}")
        params = urllib.parse.urlencode(
            {"symbolId": tradfi, "kLineStep": interval, "kLineType": 5,
             "endTime": int(time.time() * 1000)})
        payload = _json_get(f"{self.base_url}/v1/kline/getMoreKlineDataV2?{params}")
        if not isinstance(payload, dict) or payload.get("code") != "00000":
            raise SourceError(f"Bitget TradFi kline error for {tradfi}: {payload}")
        rows = payload.get("data")
        if not isinstance(rows, list) or not rows:
            raise SourceError(f"Bitget TradFi kline empty for {tradfi}")
        bars = [
            Bar(
                ts=int(int(row[0]) // 1000),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]) if len(row) > 5 else 0.0,
            )
            for row in rows
        ]
        bars.sort(key=lambda bar: bar.ts)
        return bars[-int(limit):]


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


class MarketDataRouter:
    def __init__(self, mexc=None, gate_tradfi=None, bitget=None, bitget_tradfi=None):
        self.mexc = mexc or MexcContractClient()
        self.gate_tradfi = gate_tradfi or GateTradFiClient()
        self.bitget = bitget or BitgetMixClient()
        self.bitget_tradfi = bitget_tradfi or BitgetTradFiClient()

    def _fallback_for(self, normalized: str):
        # pre-switch source: FX + NAS100/US500 lived on Gate, US30/metals on MEXC
        if normalized in FX or normalized in GATE_TRADFI_NORMALIZED:
            return self.gate_tradfi
        return self.mexc

    def price(self, symbol: str) -> float:
        normalized = normalize_symbol(symbol)
        route = classify_symbol(symbol)
        if route == "bitget_tradfi":
            try:
                return self.bitget_tradfi.price(normalized)
            except SourceError:
                return self._fallback_for(normalized).price(normalized)
        if route == "gate_tradfi":
            return self.gate_tradfi.price(normalized)
        if route == "bitget_mix":
            try:
                return self.bitget.price(normalized)
            except SourceError:
                return self.mexc.price(normalized)  # keep the desk alive if Bitget hiccups
        return self.mexc.price(normalized)

    def bars(self, symbol: str, tf: str, limit: int = 120) -> list[Bar]:
        normalized = normalize_symbol(symbol)
        route = classify_symbol(symbol)
        if route == "bitget_tradfi":
            try:
                return self.bitget_tradfi.bars(normalized, tf, limit)
            except SourceError:
                return self._fallback_for(normalized).bars(normalized, tf, limit)
        if route == "gate_tradfi":
            return self.gate_tradfi.bars(normalized, tf, limit)
        if route == "bitget_mix":
            try:
                return self.bitget.bars(normalized, tf, limit)
            except SourceError:
                return self.mexc.bars(normalized, tf, limit)
        return self.mexc.bars(normalized, tf, limit)


def bars_to_dicts(bars: Iterable[Bar]) -> list[dict]:
    return [bar.to_dict() for bar in bars]
