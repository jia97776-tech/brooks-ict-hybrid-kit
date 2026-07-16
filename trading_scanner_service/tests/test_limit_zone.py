"""limit_zone unit tests (scanner v2 §五)."""

from __future__ import annotations

import unittest

from scanner_service.limit_zone import build_limit_zone
from scanner_service.scanner import scan_symbol
from scanner_service.structure import detect_latest_sweep, find_swings, average_true_range, liquidity_targets
from tests.test_scanner import mirror, sweep_short_bars


class LimitZoneBuildTest(unittest.TestCase):
    def _short_inputs(self):
        bars = sweep_short_bars()
        swings = find_swings(bars)
        sweep = detect_latest_sweep(bars, swings)
        atr = average_true_range(bars)
        dol, _, _ = liquidity_targets(bars, swings, "SHORT")
        return bars, sweep, atr, dol

    def test_short_deep_limit_emitted(self):
        bars, sweep, atr, dol = self._short_inputs()
        self.assertIsNotNone(sweep)
        lz = build_limit_zone(
            direction="SHORT",
            bars=bars,
            sweep=sweep,
            atr=atr,
            dol=dol,
            tf="M15",
            htf_bias="SHORT",
            counter_htf=False,
        )
        self.assertIsNotNone(lz)
        assert lz is not None
        self.assertTrue(lz["requires_desk_review"])
        self.assertTrue(lz["never_auto_hang"])
        self.assertIn("sweep_extreme", lz["zone_source"])
        self.assertNotIn("M1", lz["zone_source"])
        self.assertNotIn("M5_FVG", lz["zone_source"])
        zlo, zhi = lz["zone"]
        self.assertLess(zlo, zhi)
        self.assertAlmostEqual(lz["refine"], (zlo + zhi) / 2, places=5)
        self.assertGreater(lz["sl"], lz["sl_anchor"])  # short stop above
        self.assertEqual(lz["sl_anchor"], sweep.extreme)
        self.assertIsNotNone(lz["sl_anchor_bar"])
        self.assertIn("M15 收盘 >", lz["invalidate"])
        # price must be below zone (deep)
        self.assertLess(bars[-1].close, zlo)

    def test_counter_htf_blocks(self):
        bars, sweep, atr, dol = self._short_inputs()
        lz = build_limit_zone(
            direction="SHORT",
            bars=bars,
            sweep=sweep,
            atr=atr,
            dol=dol,
            counter_htf=True,
            htf_bias="LONG",
        )
        self.assertIsNone(lz)

    def test_stale_or_news_blocks(self):
        bars, sweep, atr, dol = self._short_inputs()
        self.assertIsNone(
            build_limit_zone(
                direction="SHORT", bars=bars, sweep=sweep, atr=atr, dol=dol, stale_data=True
            )
        )
        self.assertIsNone(
            build_limit_zone(
                direction="SHORT", bars=bars, sweep=sweep, atr=atr, dol=dol, news_risk=True
            )
        )

    def test_price_still_in_zone_not_deep(self):
        """If last close is still inside/above short zone, no deep limit."""
        bars, sweep, atr, dol = self._short_inputs()
        # Force last bar close into the premium zone
        from scanner_service.sources import Bar

        b = bars[-1]
        bars = bars[:-1] + [
            Bar(ts=b.ts, open=105.2, high=105.6, low=105.0, close=105.3, volume=1)
        ]
        lz = build_limit_zone(
            direction="SHORT", bars=bars, sweep=sweep, atr=atr, dol=dol
        )
        self.assertIsNone(lz)

    def test_long_mirror(self):
        bars = mirror(sweep_short_bars())
        swings = find_swings(bars)
        sweep = detect_latest_sweep(bars, swings)
        atr = average_true_range(bars)
        dol, _, _ = liquidity_targets(bars, swings, "LONG")
        lz = build_limit_zone(
            direction="LONG",
            bars=bars,
            sweep=sweep,
            atr=atr,
            dol=dol,
            htf_bias="LONG",
        )
        self.assertIsNotNone(lz)
        assert lz is not None
        self.assertLess(lz["sl"], lz["sl_anchor"])
        self.assertIn("收盘 <", lz["invalidate"])


class LimitZoneScanWireTest(unittest.TestCase):
    def test_scan_symbol_attaches_limit_zone(self):
        c = scan_symbol("BTC", sweep_short_bars(), tf="M15", htf=("SHORT", "aligned"))
        self.assertEqual(c["direction"], "SHORT")
        self.assertFalse(c["counter_htf"])
        self.assertIsNotNone(c.get("limit_zone"))
        lz = c["limit_zone"]
        self.assertTrue(lz["requires_desk_review"])
        # limit_zone is arithmetic only — never makes pushable by itself on map TF
        # (pushable may still be false due to map_tf_not_entry)
        self.assertFalse(c.get("pushable") and lz and not c.get("confirm_bar"))

    def test_scan_counter_htf_null_limit_zone(self):
        c = scan_symbol(
            "ETH",
            sweep_short_bars(),
            tf="M15",
            htf=("LONG", "confirmed low-sweep reversal"),
        )
        self.assertTrue(c["counter_htf"])
        self.assertIsNone(c.get("limit_zone"))


if __name__ == "__main__":
    unittest.main()
