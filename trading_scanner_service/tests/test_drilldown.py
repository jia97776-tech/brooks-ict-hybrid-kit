"""drilldown_chain + poi_scaled unit tests."""

from __future__ import annotations

import unittest
from unittest import mock

from scanner_service.drilldown import build_poi_scaled_contract, scan_drilldown_chain


class PoiScaledTest(unittest.TestCase):
    def test_contract_fields(self):
        c = build_poi_scaled_contract([100.0, 101.0], max_tranches=2)
        self.assertTrue(c["allowed"])
        self.assertEqual(c["max_tranches"], 2)
        self.assertEqual(c["risk_per_tranche_r"], 0.5)
        self.assertEqual(c["total_risk_r"], 1.0)
        self.assertTrue(c["must_declare_before_first"])
        self.assertTrue(c["requires_desk_review"])
        self.assertTrue(c["forbids_unplanned_add"])


class DrilldownSmokeTest(unittest.TestCase):
    def test_c_tier_empty(self):
        from scanner_service.sources import Bar

        bars = [
            Bar(ts=i, open=100, high=101, low=99, close=100, volume=1) for i in range(40)
        ]
        self.assertEqual(scan_drilldown_chain("PEPE", bars, bars, bars), [])

    def test_short_chain_fixture_progresses(self):
        """Reuse scanner short fixture on H4/M5/M1 with shared timestamps.

        Same OHLC on all TFs + equal wall times → H4→M5→M1 all confirm SHORT
        and chain completes. Do not pad: lookback=16 and H4_CHAIN_MAX_AGE=6
        would age/miss the sweep.
        """
        from tests.test_scanner import sweep_short_bars

        bars = sweep_short_bars()
        out = scan_drilldown_chain("BTC", bars, bars, bars)
        self.assertGreaterEqual(len(out), 1)
        c = out[0]
        self.assertEqual(c["setup_type"], "drilldown_chain")
        self.assertIn("chain", c)
        self.assertIn("poi_scaled", c)
        self.assertEqual(c["direction"], "SHORT")
        self.assertTrue(c["requires_desk_review"])
        self.assertEqual(c["chain"]["chain_status"], "chain_complete")
        self.assertTrue(c["chain"]["chain_complete"])
        self.assertTrue(c["chain"]["m1_cisd_ok_in_chain"])
        self.assertIsNotNone(c.get("confirm_bar"))
        self.assertTrue(c["pushable"])
        self.assertEqual(c["poi_scaled"]["total_risk_r"], 1.0)
        self.assertTrue(c["poi_scaled"]["must_declare_before_first"])

    def test_awaiting_m5_when_ltf_missing_confirm(self):
        """H4 short live but M5 has no same-direction event → awaiting_m5."""
        from scanner_service.sources import Bar
        from tests.test_scanner import sweep_short_bars

        h4 = sweep_short_bars()
        # Flat M5/M1: no sweep structure
        flat = [
            Bar(ts=i, open=100, high=100.2, low=99.8, close=100, volume=1)
            for i in range(40)
        ]
        out = scan_drilldown_chain("BTC", h4, flat, flat)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["chain"]["chain_status"], "awaiting_m5")
        self.assertFalse(out[0]["pushable"])
        self.assertIsNone(out[0].get("confirm_bar"))

    def test_h4_age_out_returns_empty(self):
        """H4 confirm older than H4_CHAIN_MAX_AGE → no candidate."""
        from scanner_service.sources import Bar
        from tests.test_scanner import sweep_short_bars

        base = sweep_short_bars()
        rows = [(b.open, b.high, b.low, b.close) for b in base]
        for _ in range(8):
            rows.append((99.0, 99.3, 98.7, 98.9))
        bars = [
            Bar(ts=i, open=o, high=h, low=l, close=c, volume=1)
            for i, (o, h, l, c) in enumerate(rows)
        ]
        out = scan_drilldown_chain("BTC", bars, bars, bars)
        self.assertEqual(out, [])

    def test_missing_forward_h4_dol_returns_empty(self):
        """A drilldown chain is invalid when H4 has no target in trade direction."""
        from tests.test_scanner import sweep_short_bars

        bars = sweep_short_bars()
        with mock.patch(
            "scanner_service.drilldown.liquidity_targets",
            return_value=(None, None, False),
        ):
            out = scan_drilldown_chain("BTC", bars, bars, bars)

        self.assertEqual(out, [])

    def test_complete_chain_beyond_m1_trigger_is_chase(self):
        from tests.test_scanner import beyond_short_trigger_bars, sweep_short_bars

        out = scan_drilldown_chain(
            "BTC",
            sweep_short_bars(),
            sweep_short_bars(),
            beyond_short_trigger_bars(),
        )

        self.assertEqual(len(out), 1)
        candidate = out[0]
        self.assertEqual(candidate["chain"]["chain_status"], "chain_complete")
        self.assertIn(
            "beyond_trigger_extreme",
            candidate["confirm_bar"]["market_fail"],
        )
        self.assertFalse(candidate["pushable"])
        self.assertEqual(candidate["not_pushable_reason"], "chase")
        self.assertEqual(candidate["ltf_status"], "chase")
        self.assertIsNone(candidate["entry_confirm_bar"])


if __name__ == "__main__":
    unittest.main()
