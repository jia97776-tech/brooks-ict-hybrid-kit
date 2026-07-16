"""improve_fill unit tests (scanner v2 §六)."""

from __future__ import annotations

import unittest

from scanner_service.improve_fill import attach_improve_fill, build_improve_fill
from scanner_service.scanner import scan_symbol
from scanner_service.sources import Bar
from tests.test_scanner import sweep_short_bars


def _confirm_ok_short(price: float = 100.0) -> dict:
    """Synthetic entry confirm with market_ok and room for a short FVG above price."""
    return {
        "tf": "M5",
        "role": "entry_confirm",
        "event": "MSS",
        "frozen_level": 101.0,
        "low": 99.0,
        "high": 102.0,
        "close": 100.0,
        "trigger_price": 98.5,  # low - buffer
        "market_ok": True,
        "market_fail": [],
    }


class ImproveFillBuildTest(unittest.TestCase):
    def test_market_ok_false_null(self):
        cb = _confirm_ok_short()
        cb["market_ok"] = False
        bars = sweep_short_bars()
        self.assertIsNone(build_improve_fill(cb, bars, "SHORT", zone_tf="M5"))

    def test_map_confirm_null(self):
        cb = _confirm_ok_short()
        cb["role"] = "map_confirm"
        cb["tf"] = "M15"
        bars = sweep_short_bars()
        self.assertIsNone(build_improve_fill(cb, bars, "SHORT", zone_tf="M15"))

    def test_fvg_inside_confirm_range(self):
        # Craft bars: bearish FVG fully inside confirm [99, 102]
        # bar i-2 low=101.5, bar i high=100.0 → gap 100.0–101.5
        rows = []
        for i in range(20):
            rows.append((100.0, 100.5, 99.5, 100.0))
        # create FVG bear: first.low > third.high
        rows[15] = (101.2, 101.8, 101.0, 101.5)  # first of 3
        rows[16] = (101.5, 101.6, 100.8, 101.0)
        rows[17] = (100.5, 100.6, 99.8, 100.0)  # third high 100.6 < first low 101.0
        # keep later bars not invalidating (close must not go above fhi=101.0)
        rows[18] = (100.0, 100.4, 99.5, 99.8)
        rows[19] = (99.8, 100.2, 99.4, 99.9)
        bars = [
            Bar(ts=i, open=o, high=h, low=l, close=c, volume=1)
            for i, (o, h, l, c) in enumerate(rows)
        ]
        cb = _confirm_ok_short()
        # price still in confirm range for market_ok narrative
        cb["close"] = 100.2
        imp = build_improve_fill(cb, bars, "SHORT", zone_tf="M5")
        self.assertIsNotNone(imp)
        assert imp is not None
        self.assertEqual(imp["zone_tf"], "M5")
        self.assertEqual(imp["zone_source"], "M5_FVG")
        self.assertEqual(imp["fallback"], "market_if_still_ok")
        self.assertEqual(imp["fallback_bars"], 3)
        self.assertFalse(imp["default_path"])
        self.assertTrue(imp["requires_user_opt_in"])
        # limit = 上沿, clipped into confirm range
        self.assertGreaterEqual(imp["limit_price"], cb["low"])
        self.assertLessEqual(imp["limit_price"], cb["high"])
        self.assertGreater(imp["limit_price"], cb["trigger_price"])

    def test_attach_sets_field(self):
        cb = _confirm_ok_short()
        cb["market_ok"] = False
        out = attach_improve_fill(cb, sweep_short_bars(), "SHORT", zone_tf="M5")
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("improve_fill", out)
        self.assertIsNone(out["improve_fill"])


class ImproveFillScanWireTest(unittest.TestCase):
    def test_m15_map_confirm_no_improve(self):
        c = scan_symbol("BTC", sweep_short_bars(), tf="M15")
        cb = c.get("confirm_bar")
        # READY short has confirm on M15 → map role → improve_fill null
        if cb is not None:
            self.assertEqual(cb.get("role"), "map_confirm")
            self.assertIsNone(cb.get("improve_fill"))

    def test_m5_entry_may_have_improve_field(self):
        """Entry TF always gets the field key when confirm exists; value may be null."""
        c = scan_symbol("BTC", sweep_short_bars(), tf="M5")
        cb = c.get("confirm_bar")
        if cb is not None:
            self.assertIn("improve_fill", cb)
            self.assertEqual(cb.get("role"), "entry_confirm")
            # If market_ok false, improve must be null
            if not cb.get("market_ok"):
                self.assertIsNone(cb.get("improve_fill"))


if __name__ == "__main__":
    unittest.main()
