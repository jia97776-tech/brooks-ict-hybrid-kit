import json
import unittest

from scanner_service.server import ScannerApp
from scanner_service.sources import Bar
from tests.test_scanner import sweep_short_bars


class FakeRouter:
    def price(self, symbol):
        return 100.5

    def bars(self, symbol, tf, limit):
        return sweep_short_bars()


class ServerShapeTest(unittest.TestCase):
    def test_price_endpoint_shape(self):
        app = ScannerApp(router=FakeRouter())
        status, body = app.handle("GET", "/price/BTC", "")

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["symbol"], "BTC")
        self.assertEqual(payload["price"], 100.5)

    def test_bars_endpoint_shape(self):
        app = ScannerApp(router=FakeRouter())
        status, body = app.handle("GET", "/bars?symbol=BTC&tf=M15", "")

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["symbol"], "BTC")
        self.assertEqual(payload["tf"], "M15")
        self.assertEqual(len(payload["bars"]), 20)

    def test_multi_bars_endpoint_returns_requested_timeframes(self):
        app = ScannerApp(router=FakeRouter())
        status, body = app.handle("GET", "/multi-bars?symbol=BTC&tfs=1m,5m,15m,1h,4h,1d,1w&limit=1", "")

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["symbol"], "BTC")
        self.assertEqual(list(payload["timeframes"].keys()), ["M1", "M5", "M15", "H1", "H4", "D1", "W1"])
        self.assertEqual(len(payload["timeframes"]["M1"]), 20)

    def test_legacy_scanner_run_and_status(self):
        app = ScannerApp(router=FakeRouter(), symbols=["BTC"])

        status, body = app.handle("POST", "/scanner/run-once", "")
        self.assertEqual(status, 200)
        run_payload = json.loads(body)
        self.assertEqual(run_payload["status"], "done")
        self.assertEqual(run_payload["mode"], "intraday")
        # Map M15 + optional v2 extras (drilldown/confluence) share the same run
        self.assertGreaterEqual(run_payload["n_candidates"], 1)
        tfs = {c["tf"] for c in run_payload["candidates"]}
        types = {c.get("setup_type") for c in run_payload["candidates"]}
        self.assertIn("M15", tfs)
        self.assertIn("drilldown_chain", types)
        map_m15 = [c for c in run_payload["candidates"] if c.get("tf") == "M15" and not c.get("setup_type")]
        self.assertEqual(len(map_m15), 1)

        status, body = app.handle("GET", "/scanner/status", "")
        self.assertEqual(status, 200)
        status_payload = json.loads(body)
        self.assertEqual(status_payload["status"], "done")
        self.assertTrue(all(c["symbol"] == "BTC" for c in status_payload["candidates"]))

    def test_mode_both_scans_intraday_and_swing(self):
        app = ScannerApp(router=FakeRouter(), symbols=["BTC"])

        status, body = app.handle("POST", "/scanner/run-once?mode=both", "")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["mode"], "both")
        self.assertGreaterEqual(payload["n_candidates"], 2)
        tfs = {c["tf"] for c in payload["candidates"]}
        self.assertTrue({"M15", "H4"}.issubset(tfs))
        map_tfs = {
            c["tf"]
            for c in payload["candidates"]
            if not c.get("setup_type")
        }
        self.assertEqual(map_tfs, {"M15", "H4"})

    def test_unknown_mode_is_rejected(self):
        app = ScannerApp(router=FakeRouter(), symbols=["BTC"])

        status, body = app.handle("POST", "/scanner/run-once?mode=bogus", "")
        self.assertEqual(status, 400)

    def test_migrated_scan_aliases(self):
        app = ScannerApp(router=FakeRouter(), symbols=["BTC"])

        status, body = app.handle("POST", "/scan/run?mode=both", "")
        self.assertEqual(status, 200)
        job_id = json.loads(body)["job_id"]

        status, body = app.handle("GET", f"/scan/status/{job_id}", "")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["job_id"], job_id)

    def test_openapi_documents_live_routes(self):
        app = ScannerApp(router=FakeRouter(), symbols=["BTC"])

        status, body = app.handle("GET", "/openapi.json", "")

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["openapi"], "3.0.3")
        for route in (
            "/price/{symbol}",
            "/bars",
            "/signals",
            "/scanner/run-once",
            "/scanner/status",
        ):
            self.assertIn(route, payload["paths"])

        price_params = payload["paths"]["/price/{symbol}"]["get"]["parameters"]
        self.assertEqual(price_params[0]["name"], "symbol")
        self.assertEqual(price_params[0]["in"], "path")
        self.assertTrue(price_params[0]["required"])

        status_params = payload["paths"]["/scan/status/{job_id}"]["get"]["parameters"]
        self.assertEqual(status_params[0]["name"], "job_id")
        self.assertEqual(status_params[0]["in"], "path")
        self.assertTrue(status_params[0]["required"])

        signal_params = payload["paths"]["/signals"]["get"]["parameters"]
        limit_param = next(p for p in signal_params if p["name"] == "limit")
        self.assertEqual(limit_param["in"], "query")
        self.assertEqual(limit_param["schema"]["type"], "integer")
        self.assertEqual(limit_param["schema"]["default"], 100)
        self.assertEqual(limit_param["schema"]["minimum"], 1)
        self.assertEqual(limit_param["schema"]["maximum"], 1000)

    def test_signals_endpoint_returns_limited_rows(self):
        app = ScannerApp(router=FakeRouter(), symbols=["BTC"])

        status, body = app.handle("GET", "/signals?limit=2", "")

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("signals", payload)
        self.assertLessEqual(len(payload["signals"]), 2)
        self.assertEqual(payload["limit"], 2)

    def test_signals_endpoint_rejects_invalid_limit_without_trace(self):
        app = ScannerApp(router=FakeRouter(), symbols=["BTC"])

        status, body = app.handle("GET", "/signals?limit=bad", "")

        self.assertEqual(status, 400)
        payload = json.loads(body)
        self.assertIn("error", payload)
        self.assertNotIn("trace", payload)


if __name__ == "__main__":
    unittest.main()
