import json
import tempfile
import unittest
from pathlib import Path

import scanner_service.papertrack as pt
from scanner_service.sources import Bar


def cand(**kw):
    base = {
        "symbol": "BTC", "tf": "M15", "direction": "SHORT", "state": "READY",
        "price": 99.0, "entry_ref": 105.25, "sl": 106.0, "dol": 95.0,
        "dol_runner": None, "rr": 10.0, "rr_now": 0.5, "late": True,
        "target_crowded": False, "swept_level": 105.0, "mss": True,
        "cisd": True, "reason": "test",
    }
    base.update(kw)
    return base


class PapertrackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        pt.DATA_DIR = Path(self.tmp.name)
        pt.SIGNALS_FILE = pt.DATA_DIR / "signals.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_record_dedupes_pending_and_skips_untrackable(self):
        n1 = pt.record_candidates([cand(), cand(state="ARMED"), cand(dol=None)], now=1000)
        self.assertEqual(n1, 1)
        n2 = pt.record_candidates([cand()], now=2000)
        self.assertEqual(n2, 0)  # same key still pending
        n3 = pt.record_candidates([cand(swept_level=110.0)], now=2000)
        self.assertEqual(n3, 1)  # different anchor = new signal

    def _resolve_with_bars(self, bars, now=100_000):
        class FakeRouter:
            def bars(self, symbol, tf, limit):
                return bars
        return pt.resolve(router=FakeRouter(), now=now)

    def test_short_fill_then_target_is_win(self):
        pt.record_candidates([cand()], now=1000)
        bars = [
            Bar(ts=2000, open=100, high=105.5, low=99, close=104),   # fill at 105.25
            Bar(ts=3000, open=104, high=104.5, low=94.5, close=95),  # DOL 95 touched
        ]
        self._resolve_with_bars(bars)
        row = pt._load()[0]
        self.assertEqual(row["outcome"], "win")
        self.assertEqual(row["result_r"], 10.0)

    def test_short_fill_then_stop_is_loss(self):
        pt.record_candidates([cand()], now=1000)
        bars = [
            Bar(ts=2000, open=100, high=105.4, low=99, close=104),
            Bar(ts=3000, open=104, high=106.2, low=103, close=105),  # SL 106 hit
        ]
        self._resolve_with_bars(bars)
        row = pt._load()[0]
        self.assertEqual(row["outcome"], "loss")
        self.assertEqual(row["result_r"], -1.0)

    def test_same_bar_stop_and_target_is_conservative_loss(self):
        pt.record_candidates([cand()], now=1000)
        bars = [
            Bar(ts=2000, open=100, high=105.4, low=99, close=104),
            Bar(ts=3000, open=104, high=106.5, low=94.0, close=100),  # both hit
        ]
        self._resolve_with_bars(bars)
        self.assertEqual(pt._load()[0]["outcome"], "loss")

    def test_ran_to_target_without_retest_is_no_fill(self):
        pt.record_candidates([cand()], now=1000)
        bars = [Bar(ts=2000, open=99, high=100, low=94.5, close=95)]  # DOL without fill
        self._resolve_with_bars(bars)
        self.assertEqual(pt._load()[0]["outcome"], "no_fill")

    def test_fill_window_expiry_is_no_fill(self):
        pt.record_candidates([cand()], now=1000)
        bars = [Bar(ts=1000 + pt.FILL_WINDOW_S + 60, open=99, high=100, low=98, close=99)]
        self._resolve_with_bars(bars, now=1000 + pt.FILL_WINDOW_S + 120)
        self.assertEqual(pt._load()[0]["outcome"], "no_fill")

    def test_stats_runs(self):
        pt.record_candidates([cand()], now=1000)
        out = pt.stats()
        self.assertIn("signals total=1", out)


    def test_mfe_and_scalp_on_giveback_loss(self):
        # the ETH 07-02 pattern: fill, run ~2.3R toward the far DOL, reverse to SL
        pt.record_candidates([cand()], now=1000)
        bars = [
            Bar(ts=2000, open=105.0, high=105.4, low=104.5, close=104.8),  # fill 105.25
            Bar(ts=3000, open=104.8, high=105.0, low=103.5, close=103.8),  # scalp 103.75 hit
            Bar(ts=4000, open=103.8, high=106.2, low=103.6, close=105.9),  # SL 106 hit
        ]
        self._resolve_with_bars(bars)
        row = pt._load()[0]
        self.assertEqual(row["outcome"], "loss")
        self.assertEqual(row["result_r"], -1.0)
        self.assertEqual(row["scalp_r"], 2.0)
        self.assertAlmostEqual(row["mfe_r"], 2.33, places=2)

    def test_scalp_resolves_on_dol_win(self):
        pt.record_candidates([cand()], now=1000)
        bars = [
            Bar(ts=2000, open=100, high=105.5, low=104.0, close=104.5),
            Bar(ts=3000, open=104.5, high=104.6, low=94.5, close=95.0),  # DOL 95 hit
        ]
        self._resolve_with_bars(bars)
        row = pt._load()[0]
        self.assertEqual(row["outcome"], "win")
        self.assertEqual(row["scalp_r"], 2.0)

    def test_scalp_target_capped_at_dol(self):
        # DOL only 1R away -> scalp exit is the DOL itself, not a phantom 2R
        pt.record_candidates([cand(dol=104.5, rr=1.0)], now=1000)
        bars = [
            Bar(ts=2000, open=105.0, high=105.4, low=104.8, close=105.0),
            Bar(ts=3000, open=105.0, high=105.1, low=104.4, close=104.6),
        ]
        self._resolve_with_bars(bars)
        row = pt._load()[0]
        self.assertEqual(row["outcome"], "win")
        self.assertEqual(row["scalp_r"], 1.0)

    def test_same_bar_scalp_and_stop_is_conservative_loss(self):
        pt.record_candidates([cand()], now=1000)
        bars = [
            Bar(ts=2000, open=105.0, high=105.4, low=104.5, close=104.8),
            Bar(ts=3000, open=104.8, high=106.5, low=103.0, close=105.0),  # SL and scalp same bar
        ]
        self._resolve_with_bars(bars)
        row = pt._load()[0]
        self.assertEqual(row["outcome"], "loss")
        self.assertEqual(row["scalp_r"], -1.0)


if __name__ == "__main__":
    unittest.main()
