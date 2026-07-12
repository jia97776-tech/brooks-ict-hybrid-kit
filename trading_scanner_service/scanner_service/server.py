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
from scanner_service.papertrack import record_candidates
from scanner_service.scanner import scan_symbol
from scanner_service.structure import d1_spike, htf_bias
from scanner_service.sources import MarketDataRouter, SourceError, bars_to_dicts, normalize_timeframe


DEFAULT_SYMBOLS = [
    "BTC", "ETH", "SOL", "DOGE", "XRP", "SUI", "HYPE", "PEPE", "ZEC", "TAO", "WLD",
    "XAUUSD", "XAGUSD", "XTIUSD",
    "NAS100", "US500", "US30",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    # US stock perps pilot (2026-07-11): scan-only, no a_watch push;
    # MSTR/CRCL cluster with BTC-beta for sample counting.
    "TSLA", "NVDA", "MSTR", "CRCL",
]

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
        self.last_status = {
            "job_id": job_id,
            "mode": mode,
            "status": "done" if not errors else "partial",
            "n_candidates": len(candidates),
            "candidates": candidates,
            "error": errors or None,
            "updated_at": int(time.time()),
        }
        return self.last_status

    @staticmethod
    def _one(query: dict, key: str, default: str) -> str:
        values = query.get(key)
        return values[0] if values else default

    @staticmethod
    def _json(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


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
