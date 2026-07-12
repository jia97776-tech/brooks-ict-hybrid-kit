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
        self.assertEqual(run_payload["n_candidates"], 1)
        self.assertEqual(run_payload["candidates"][0]["tf"], "M15")

        status, body = app.handle("GET", "/scanner/status", "")
        self.assertEqual(status, 200)
        status_payload = json.loads(body)
        self.assertEqual(status_payload["status"], "done")
        self.assertEqual(status_payload["candidates"][0]["symbol"], "BTC")

    def test_mode_both_scans_intraday_and_swing(self):
        app = ScannerApp(router=FakeRouter(), symbols=["BTC"])

        status, body = app.handle("POST", "/scanner/run-once?mode=both", "")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["mode"], "both")
        self.assertEqual(payload["n_candidates"], 2)
        self.assertEqual({c["tf"] for c in payload["candidates"]}, {"M15", "H4"})

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


if __name__ == "__main__":
    unittest.main()
