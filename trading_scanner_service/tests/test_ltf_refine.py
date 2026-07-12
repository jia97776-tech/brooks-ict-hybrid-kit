import tempfile
import unittest
from pathlib import Path

import scanner_service.papertrack as pt
from scanner_service.ltf_refine import refine_pending
from scanner_service.sources import Bar
from tests.test_papertrack import cand


def m5_bars_with_trigger():
    """Retest into the POI zone (swept=105), pullback swing low at 103.8
    confirms, then an M5 close below it triggers the LTF short entry."""
    rows = [
        (1300, 100.0, 102.0, 99.5, 101.5),
        (1600, 101.5, 104.0, 101.0, 103.5),
        (1900, 103.5, 105.2, 103.4, 104.6),   # zone entry: high >= 105
        (2200, 104.6, 105.0, 104.0, 104.5),
        (2500, 104.5, 105.3, 104.1, 104.8),
        (2800, 104.8, 105.1, 103.8, 104.2),   # swing low 103.8
        (3100, 104.2, 105.4, 104.0, 105.0),
        (3400, 105.0, 105.45, 104.3, 104.9),  # swing confirmed
        (3700, 104.9, 105.0, 103.5, 103.6),   # close 103.6 < 103.8 -> trigger
    ]
    return [Bar(ts=t, open=o, high=h, low=l, close=c) for t, o, h, l, c in rows]


class FakeRouter:
    def __init__(self, bars):
        self._bars = bars

    def bars(self, symbol, tf, limit):
        assert tf == "M5"
        return self._bars


class LtfRefineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        pt.DATA_DIR = Path(self.tmp.name)
        pt.SIGNALS_FILE = pt.DATA_DIR / "signals.jsonl"
        pt.record_candidates([cand()], now=1000)  # parent M15 SHORT signal

    def tearDown(self):
        self.tmp.cleanup()

    def test_trigger_emits_filled_model_b_row_once(self):
        out = refine_pending(router=FakeRouter(m5_bars_with_trigger()), now=4000)
        self.assertEqual(out["refined"], 1)

        rows = pt._load()
        self.assertEqual(len(rows), 2)
        parent, b = rows[0], rows[1]
        self.assertTrue(parent["ltf_refined"])
        self.assertEqual(b["model"], "ltf_refine")
        self.assertTrue(b["filled"])
        self.assertEqual(b["ts"], 3700)
        self.assertEqual(b["entry_ref"], 103.6)
        self.assertGreater(b["sl"], 105.45)       # beyond LTF extreme + buffer
        self.assertLess(b["sl"], parent["sl"])    # tighter than the M15 stop
        self.assertGreater(b["rr"], parent["rr"] / 4)  # sane equation
        self.assertEqual(b["dol"], parent["dol"])

        again = refine_pending(router=FakeRouter(m5_bars_with_trigger()), now=4300)
        self.assertEqual(again["refined"], 0)  # one B attempt per parent

    def test_no_zone_entry_keeps_parent_unmarked(self):
        bars = [Bar(ts=1300 + i * 300, open=100, high=103.0, low=99, close=101)
                for i in range(9)]  # never reaches 105
        out = refine_pending(router=FakeRouter(bars), now=4000)
        self.assertEqual(out["refined"], 0)
        parent = pt._load()[0]
        self.assertFalse(parent.get("ltf_refined", False))  # re-checked next run

    def test_model_b_resolves_like_any_row(self):
        refine_pending(router=FakeRouter(m5_bars_with_trigger()), now=4000)

        class ResolveRouter:
            def bars(self, symbol, tf, limit):
                # after the B entry at 103.6: DOL 95 touched before SL
                return [Bar(ts=5000, open=103, high=104, low=94.5, close=95.2)]

        pt.resolve(router=ResolveRouter(), now=6000)
        b = [r for r in pt._load() if r.get("model") == "ltf_refine"][0]
        self.assertEqual(b["outcome"], "win")
        self.assertEqual(b["result_r"], b["rr"])


if __name__ == "__main__":
    unittest.main()
