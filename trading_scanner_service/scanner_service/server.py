from __future__ import annotations

import json
import os
import threading
import time
import traceback
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scanner_service.newsguard import load_events, news_risk
from scanner_service.papertrack import recent_signals, record_candidates
from scanner_service.candidates_ledger import attach_protocol_fields, record_scan_candidates
from scanner_service.confluence import C_TIER, scan_confluence_retest
from scanner_service.drilldown import scan_drilldown_chain
from scanner_service.ltf_refine import ltf_tf
from scanner_service.scanner import apply_ltf_confirm_bar, scan_symbol, wants_ltf_confirm
from scanner_service.structure import d1_spike, eth_btc_regime, htf_bias, smt_divergence, smt_partner
from scanner_service.sources import MarketDataRouter, SourceError, bars_to_dicts, normalize_timeframe


DEFAULT_SYMBOLS = [
    "BTC", "ETH", "SOL", "DOGE", "XRP", "SUI", "HYPE", "PEPE", "ZEC", "TAO", "WLD",
    "XAUUSD", "XAGUSD", "XTIUSD",
    "NAS100", "US500", "US30",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    # US Dollar Index — Gate TradFi USIDX only (no Bitget product).
    "DXY",
    # US stock perps pilot (2026-07-11): scan-only, no a_watch push;
    # MSTR/CRCL cluster with BTC-beta for sample counting. Source: Bitget mix.
    "TSLA", "NVDA", "MSTR", "CRCL",
    # Semis pilot: Bitget USDT-M stock perps, scan-only.
    # MU = US RTH; SKHYNIX = KRX RTH (00:00-06:30 UTC); SNDK = SanDisk US RTH.
    "MU", "SKHYNIX", "SNDK",
]

# True crypto alts for the ETH/BTC breadth stamp — deliberately excludes BTC/ETH
# (ratio numerator/denominator) AND the stock perps (MU/SNDK/SKHYNIX/TSLA/... route
# gate_crypto but ETH/BTC strength is meaningless for equities). Extend when a new
# crypto coin joins the universe.
_ETH_BTC_ALTS = frozenset({"SOL", "DOGE", "XRP", "SUI", "HYPE", "PEPE", "ZEC", "TAO", "WLD"})

SCAN_MODES = {
    "intraday": [("M15", 240)],
    "swing": [("H4", 180)],
    "both": [("M15", 240), ("H4", 180)],
}


class ScannerApp:
    def __init__(self, router=None, symbols=None):
        self.router = router or MarketDataRouter()
        self.symbols = list(symbols or DEFAULT_SYMBOLS)
        self.last_status = {
            "job_id": None,
            "mode": None,
            "status": "idle",
            "n_candidates": 0,
            "candidates": [],
            "error": None,
            "updated_at": None,
        }

    def handle(self, method: str, path: str, body: str = "") -> tuple[int, str]:
        parsed = urllib.parse.urlparse(path)
        query = urllib.parse.parse_qs(parsed.query)
        route = parsed.path
        try:
            if method == "GET" and route.startswith("/price/"):
                symbol = route.rsplit("/", 1)[-1]
                price = self.router.price(symbol)
                return 200, self._json({"symbol": symbol.upper(), "price": price, "source_ts": int(time.time())})

            if method == "GET" and route == "/bars":
                symbol = self._one(query, "symbol", "BTC")
                tf = normalize_timeframe(self._one(query, "tf", "M15"))
                limit = int(self._one(query, "limit", "120"))
                bars = self.router.bars(symbol, tf, limit)
                return 200, self._json({"symbol": symbol.upper(), "tf": tf, "bars": bars_to_dicts(bars)})

            if method == "GET" and route == "/multi-bars":
                symbol = self._one(query, "symbol", "BTC")
                raw_tfs = self._one(query, "tfs", "1m,5m,15m,1h,4h,1d,1w")
                limit = int(self._one(query, "limit", "120"))
                result = {}
                for raw_tf in [item.strip() for item in raw_tfs.split(",") if item.strip()]:
                    tf = normalize_timeframe(raw_tf)
                    result[tf] = bars_to_dicts(self.router.bars(symbol, tf, limit))
                return 200, self._json({"symbol": symbol.upper(), "timeframes": result})

            if method == "POST" and route in {"/scanner/run-once", "/scan/run"}:
                mode = self._one(query, "mode", "intraday").lower()
                if mode not in SCAN_MODES:
                    return 400, self._json({"error": f"unknown mode: {mode}", "modes": sorted(SCAN_MODES)})
                return 200, self._json(self.run_scan(mode))

            if method == "GET" and route == "/scanner/status":
                return 200, self._json(self.last_status)

            if method == "GET" and route.startswith("/scan/status/"):
                job_id = route.rsplit("/", 1)[-1]
                payload = dict(self.last_status)
                payload["job_id"] = job_id
                return 200, self._json(payload)

            if method == "GET" and route == "/symbols":
                return 200, self._json({"symbols": self.symbols})

            if method == "GET" and route == "/signals":
                try:
                    limit = int(self._one(query, "limit", "100"))
                except ValueError:
                    return 400, self._json({"error": "limit must be an integer"})
                limit = max(1, min(limit, 1000))
                signals = recent_signals(limit)
                return 200, self._json(
                    {
                        "signals": signals,
                        "count": len(signals),
                        "limit": limit,
                        "source": "papertrack",
                    }
                )

            if method == "GET" and route == "/openapi.json":
                return 200, self._json(self._openapi())

            if method == "GET" and route == "/healthz":
                return 200, self._json({"ok": True})

            return 404, self._json({"error": f"route not found: {method} {route}"})
        except Exception as exc:
            return 500, self._json({"error": str(exc), "trace": traceback.format_exc(limit=3)})

    def run_scan(self, mode: str = "intraday") -> dict:
        job_id = time.strftime("%Y%m%d-%H%M%S")
        plan = [(symbol, tf, limit) for symbol in self.symbols for tf, limit in SCAN_MODES[mode]]
        candidates = []
        errors = {}
        bias_cache: dict[str, tuple[str, str] | None] = {}
        bias_lock = threading.Lock()

        def bias_of(symbol):
            # H4 context for M15 signals; a bias failure must never break a scan
            with bias_lock:
                if symbol in bias_cache:
                    return bias_cache[symbol]
            try:
                value = htf_bias(self.router.bars(symbol, "H4", 60))
            except Exception:
                value = None
            with bias_lock:
                bias_cache[symbol] = value
            return value

        d1_cache: dict[str, tuple[str | None, str, str] | None] = {}
        d1_lock = threading.Lock()

        def d1_of(symbol):
            # D1 seniority layer for every candidate; a D1 fetch failure must
            # never break a scan
            with d1_lock:
                if symbol in d1_cache:
                    return d1_cache[symbol]
            try:
                bars = self.router.bars(symbol, "D1", 60)
                state, state_basis = d1_spike(bars)
                bias, bias_basis = htf_bias(bars)
                value = (state, bias, state_basis if state else bias_basis)
            except Exception:
                value = None
            with d1_lock:
                d1_cache[symbol] = value
            return value

        def scan_one(job):
            symbol, tf, limit = job
            bars = self.router.bars(symbol, tf, limit)
            htf = bias_of(symbol) if tf == "M15" else None
            return scan_symbol(symbol, bars, tf=tf, htf=htf, d1=d1_of(symbol), now=time.time())

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(scan_one, job): job for job in plan}
            for future in as_completed(futures):
                symbol, tf, _ = futures[future]
                try:
                    candidate = future.result()
                    if candidate["direction"] != "WAIT" or candidate["state"] in {"READY", "CONDITIONAL_READY"}:
                        candidates.append(candidate)
                except SourceError as exc:
                    errors[f"{symbol}:{tf}"] = str(exc)

        state_rank = {"READY": 0, "CONDITIONAL_READY": 1, "ARMED": 2}
        candidates.sort(key=lambda c: (state_rank.get(c["state"], 3), c["symbol"], c["tf"]))

        # SMT attach (desk evidence): DXY inverse / correlated partners.
        try:
            candidates = self._attach_smt(candidates, errors)
        except Exception as exc:
            errors["smt"] = str(exc)

        # LTF confirm attach (2026-07-14c): only eligible map parents get M1/M5
        # confirm_bar. Does not auto-promote to A/S — only fills pushable numbers.
        try:
            candidates = self._attach_ltf_confirms(candidates, errors)
        except Exception as exc:
            errors["ltf_confirm"] = str(exc)

        # Confluence retest setups (v2 §8.1) — label only, desk reviews.
        try:
            conf_extra = self._scan_confluence(errors)
            candidates.extend(conf_extra)
        except Exception as exc:
            errors["confluence_retest"] = str(exc)

        # Drilldown chain (v2 §8.2) + poi_scaled metadata on chain/confluence.
        try:
            chain_extra = self._scan_drilldown(errors)
            candidates.extend(chain_extra)
        except Exception as exc:
            errors["drilldown_chain"] = str(exc)

        candidates.sort(
            key=lambda c: (state_rank.get(c["state"], 3), c["symbol"], c.get("tf") or "")
        )

        try:
            events = load_events()
            for c in candidates:
                risk = news_risk(c["symbol"], events=events)
                c["news_risk"] = bool(risk)
                if risk:
                    c["news_event"] = f"{risk['currency']} {risk['title']} ({risk['minutes']:+d}m)"
        except Exception:
            pass  # the news guard must never break a scan
        try:
            record_candidates(candidates)
        except Exception:
            pass  # paper-tracking must never break a live scan
        try:
            # v2 §8.3 + 14i: protocol fields on candidates then full ledger
            attach_protocol_fields(candidates, model="scanner")
            record_scan_candidates(
                candidates, scan_id=job_id, now=int(time.time()), model="scanner"
            )
        except Exception as exc:
            errors["candidates_ledger"] = str(exc)

        # ETH/BTC breadth gauge (alt-vs-BTC strength), computed once per scan.
        # Context only (like SMT): surfaced in status + stamps alt candidates,
        # never gates pushable/READY. Fully guarded — cannot break a live scan.
        market_context = self._compute_market_context(errors)
        try:
            trend = market_context.get("h4_trend")
            for c in candidates:
                sym = (c.get("symbol") or "").upper()
                if sym not in _ETH_BTC_ALTS:
                    continue
                if c.get("direction") in ("LONG", "SHORT") and trend in ("LONG", "SHORT"):
                    # rising ETH/BTC (LONG) supports alt longs; falling supports shorts
                    c["eth_btc_align"] = c["direction"] == trend
                else:
                    c["eth_btc_align"] = None
        except Exception as exc:
            errors["eth_btc_align"] = str(exc)

        self.last_status = {
            "job_id": job_id,
            "mode": mode,
            "status": "done" if not errors else "partial",
            "n_candidates": len(candidates),
            "candidates": candidates,
            "market_context": market_context,
            "error": errors or None,
            "updated_at": int(time.time()),
        }
        return self.last_status

    def _compute_market_context(self, errors: dict) -> dict:
        """ETH/BTC breadth gauge, computed once per scan (context only, like SMT).

        Native Gate SPOT ETH_BTC — same venue as everything else (Gate-only),
        never a tradeable quote. Any failure is recorded and returns 'unknown';
        it must never break a live scan.
        """
        try:
            h4 = self.router.spot_bars("ETH_BTC", "H4", 120)
            d1 = self.router.spot_bars("ETH_BTC", "D1", 120)
            return eth_btc_regime(h4, d1)
        except Exception as exc:
            errors["market_context"] = str(exc)
            return {
                "ratio": None, "h4_trend": "NEUTRAL", "d1_trend": "NEUTRAL",
                "regime": "unknown", "note": f"unavailable: {exc}", "source": "gate_spot",
            }

    def _attach_smt(self, candidates: list, errors: dict) -> list:
        """Attach SMT confirm fields using DXY / correlated partners.

        Evidence only — never auto-promotes pushable or READY.
        """
        if not candidates:
            return candidates
        bar_cache: dict[tuple[str, str], list | None] = {}
        lock = threading.Lock()

        def bars_of(symbol: str, tf: str, limit: int = 80):
            key = (symbol.upper(), tf)
            with lock:
                if key in bar_cache:
                    return bar_cache[key]
            try:
                bars = self.router.bars(symbol, tf, limit)
            except Exception as exc:
                with lock:
                    errors[f"smt:{symbol}:{tf}"] = str(exc)
                    bar_cache[key] = None
                return None
            with lock:
                bar_cache[key] = bars
            return bars

        out = []
        for c in candidates:
            c = dict(c)
            direction = c.get("direction")
            if direction not in ("LONG", "SHORT"):
                c.setdefault("smt", False)
                c.setdefault("smt_partner", None)
                c.setdefault("smt_inverse", False)
                c.setdefault("smt_note", None)
                out.append(c)
                continue
            partner, inverse = smt_partner(c.get("symbol") or "")
            c["smt_partner"] = partner
            c["smt_inverse"] = inverse
            if not partner:
                c["smt"] = False
                c["smt_note"] = "no partner"
                out.append(c)
                continue
            tf = c.get("tf") or "M15"
            bars_a = bars_of(c["symbol"], tf)
            bars_b = bars_of(partner, tf)
            if not bars_a or not bars_b:
                c["smt"] = False
                c["smt_note"] = "partner bars missing"
                out.append(c)
                continue
            ok, note = smt_divergence(bars_a, bars_b, direction, inverse=inverse)
            c["smt"] = bool(ok)
            c["smt_note"] = note
            out.append(c)
        return out

    def _attach_ltf_confirms(self, candidates: list, errors: dict) -> list:
        """Fetch LTF bars for eligible parents and attach ltf_confirm_bar."""
        eligible = [c for c in candidates if wants_ltf_confirm(c)]
        if not eligible:
            return candidates

        # One LTF pull per symbol (indexes → M1, else M5); reuse across M15+H4 parents.
        symbols = sorted({c["symbol"] for c in eligible})
        ltf_cache: dict[str, tuple[str, list]] = {}
        ltf_lock = threading.Lock()

        def fetch_ltf(symbol: str):
            tf_name, _ = ltf_tf(symbol)
            try:
                bars = self.router.bars(symbol, tf_name, 120)
            except Exception as exc:
                with ltf_lock:
                    errors[f"{symbol}:LTF"] = str(exc)
                return symbol, tf_name, None
            return symbol, tf_name, bars

        with ThreadPoolExecutor(max_workers=6) as pool:
            for symbol, tf_name, bars in pool.map(fetch_ltf, symbols):
                if bars is not None:
                    ltf_cache[symbol] = (tf_name, bars)

        out = []
        for c in candidates:
            if not wants_ltf_confirm(c):
                out.append(c)
                continue
            packed = ltf_cache.get(c["symbol"])
            if not packed:
                c = dict(c)
                c["ltf_status"] = "fetch_failed"
                c["ltf_confirm_bar"] = None
                if c.get("not_pushable_reason") in (None, "map_tf_not_entry", "no_confirm_bar"):
                    c["pushable"] = False
                    c["not_pushable_reason"] = "no_ltf_confirm_bar"
                out.append(c)
                continue
            tf_name, bars = packed
            out.append(apply_ltf_confirm_bar(c, bars, ltf_tf=tf_name, now=time.time()))
        return out

    def _scan_confluence(self, errors: dict) -> list:
        """Build confluence_retest candidates for non-C symbols."""
        symbols = [s for s in self.symbols if s.upper() not in C_TIER]
        results: list = []

        def one(symbol: str):
            try:
                m15 = self.router.bars(symbol, "M15", 120)
                h4 = self.router.bars(symbol, "H4", 80)
                d1 = self.router.bars(symbol, "D1", 30)
                m5 = self.router.bars(symbol, "M5", 80)
                return scan_confluence_retest(symbol, m15, h4, d1, m5)
            except Exception as exc:
                return exc

        with ThreadPoolExecutor(max_workers=6) as pool:
            for symbol, res in zip(symbols, pool.map(one, symbols)):
                if isinstance(res, Exception):
                    errors[f"{symbol}:confluence"] = str(res)
                    continue
                results.extend(res)
        return results

    def _scan_drilldown(self, errors: dict) -> list:
        """Build drilldown_chain candidates (H4→M5→M1)."""
        symbols = [s for s in self.symbols if s.upper() not in C_TIER]
        results: list = []

        def one(symbol: str):
            try:
                h4 = self.router.bars(symbol, "H4", 80)
                m5 = self.router.bars(symbol, "M5", 120)
                m1 = self.router.bars(symbol, "M1", 120)
                return scan_drilldown_chain(symbol, h4, m5, m1)
            except Exception as exc:
                return exc

        with ThreadPoolExecutor(max_workers=6) as pool:
            for symbol, res in zip(symbols, pool.map(one, symbols)):
                if isinstance(res, Exception):
                    errors[f"{symbol}:drilldown"] = str(res)
                    continue
                results.extend(res)
        return results

    @staticmethod
    def _one(query: dict, key: str, default: str) -> str:
        values = query.get(key)
        return values[0] if values else default

    @staticmethod
    def _json(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _openapi() -> dict:
        json_response = {
            "200": {
                "description": "Successful response",
                "content": {"application/json": {"schema": {"type": "object"}}},
            }
        }
        symbol_path = {
            "name": "symbol",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
        job_id_path = {
            "name": "job_id",
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
        signal_limit = {
            "name": "limit",
            "in": "query",
            "required": False,
            "schema": {
                "type": "integer",
                "default": 100,
                "minimum": 1,
                "maximum": 1000,
            },
        }
        return {
            "openapi": "3.0.3",
            "info": {
                "title": "Local Trading Scanner Service",
                "version": "2026-07-14j",
            },
            "paths": {
                "/price/{symbol}": {
                    "get": {"parameters": [symbol_path], "responses": json_response}
                },
                "/bars": {"get": {"responses": json_response}},
                "/multi-bars": {"get": {"responses": json_response}},
                "/signals": {
                    "get": {"parameters": [signal_limit], "responses": json_response}
                },
                "/scanner/run-once": {"post": {"responses": json_response}},
                "/scanner/status": {"get": {"responses": json_response}},
                "/scan/run": {"post": {"responses": json_response}},
                "/scan/status/{job_id}": {
                    "get": {"parameters": [job_id_path], "responses": json_response}
                },
                "/symbols": {"get": {"responses": json_response}},
                "/healthz": {"get": {"responses": json_response}},
                "/openapi.json": {"get": {"responses": json_response}},
            },
        }


class RequestHandler(BaseHTTPRequestHandler):
    app = ScannerApp()

    def do_GET(self):
        self._send(*self.app.handle("GET", self.path))

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        self._send(*self.app.handle("POST", self.path, body))

    def log_message(self, fmt, *args):
        return

    def _send(self, status: int, body: str):
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def serve(host: str | None = None, port: int | None = None):
    host = host or os.environ.get("SCANNER_HOST", "127.0.0.1")
    port = port or int(os.environ.get("SCANNER_PORT", "8001"))
    server = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"scanner service listening on http://{host}:{port}", flush=True)
    server.serve_forever()
