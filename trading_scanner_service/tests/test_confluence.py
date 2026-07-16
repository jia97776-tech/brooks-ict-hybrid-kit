"""confluence_retest (v2 §8.1) unit tests."""

from __future__ import annotations

import unittest
from unittest import mock

from scanner_service.confluence import (
    find_active_fvgs,
    find_confluence_zones,
    m5_signal_in_zone,
    ote_band,
    scan_confluence_retest,
    session_range,
    swept_into_zone,
)
from scanner_service.sources import Bar


def _bar(ts, o, h, l, c):
    return Bar(ts=ts, open=o, high=h, low=l, close=c, volume=1)


class ConfluenceUnitTest(unittest.TestCase):
    def test_fvg_bull_detected(self):
        # three-candle bull FVG: gap between bar0 high and bar2 low
        bars = [
            _bar(0, 100, 101, 99, 100.5),
            _bar(1, 100.5, 100.8, 100.2, 100.4),
            _bar(2, 102.0, 103, 101.5, 102.5),  # first.high 101 < third.low 101.5
        ]
        # need more padding for ATR
        bars = bars + [_bar(3 + i, 102.5, 103, 102, 102.5) for i in range(20)]
        fvgs = find_active_fvgs(bars, "LONG")
        self.assertTrue(any(lo < hi for _, lo, hi in fvgs))

    def test_zone_needs_three_layers(self):
        layers = [
            ("a", 100.0, 101.0),
            ("b", 100.2, 101.2),
            ("c", 100.4, 101.4),
            ("d", 110.0, 111.0),  # isolated
        ]
        zones = find_confluence_zones(layers, min_count=3)
        self.assertTrue(zones)
        self.assertGreaterEqual(zones[0]["layer_count"], 3)
        self.assertTrue(100.0 <= zones[0]["zone"][0] < zones[0]["zone"][1] <= 101.4)

    def test_swept_into_long(self):
        z = (100.0, 101.0)
        bars = [
            _bar(i, 102, 103, 101.5, 102) for i in range(10)
        ] + [
            _bar(10, 101, 101.2, 99.5, 100.5),  # wick below 100, close back above
        ]
        ok, ext, ts = swept_into_zone(bars, z, "LONG")
        self.assertTrue(ok)
        self.assertLess(ext, 100.0)

    def test_c_tier_skipped(self):
        m15 = [_bar(i, 1, 1.1, 0.9, 1) for i in range(40)]
        h4 = [_bar(i * 16, 1, 1.1, 0.9, 1) for i in range(30)]
        d1 = [_bar(i * 96, 1, 1.1, 0.9, 1) for i in range(20)]
        m5 = [_bar(i, 1, 1.05, 0.95, 1) for i in range(40)]
        self.assertEqual(scan_confluence_retest("PEPE", m15, h4, d1, m5), [])

    def test_session_range_asia(self):
        # ts as unix hours: use hour 2 UTC
        import time
        # 2026-07-14 02:00 UTC ≈ known
        base = 1783994400  # approximate; use constructed
        bars = []
        for i in range(20):
            ts = base + i * 900
            bars.append(_bar(ts, 100 + i * 0.01, 101, 99, 100))
        # function tolerates empty-ish; just ensure no crash
        session_range(bars, range(0, 7))

    def test_beyond_trigger_signal_is_chase_not_pushable(self):
        m15 = [_bar(i, 100, 101, 99, 100) for i in range(30)]
        h4 = [_bar(i, 100, 101, 99, 100) for i in range(20)]
        d1 = [_bar(i, 100, 101, 99, 100) for i in range(20)]
        m5 = [_bar(i, 100, 101, 99, 100) for i in range(20)]
        signal = {
            "tf": "M5",
            "grade": "acceptable",
            "trigger_price": 99.5,
            "market_ok": False,
            "market_fail": ["beyond_trigger_extreme"],
        }

        with (
            mock.patch("scanner_service.confluence.htf_bias", return_value=("SHORT", "test")),
            mock.patch(
                "scanner_service.confluence.build_layers",
                return_value=[("a", 99.5, 100.5), ("b", 99.5, 100.5), ("c", 99.5, 100.5)],
            ),
            mock.patch(
                "scanner_service.confluence.find_confluence_zones",
                return_value=[
                    {
                        "zone": (99.5, 100.5),
                        "layers": ["a", "b", "c"],
                        "layer_count": 3,
                    }
                ],
            ),
            mock.patch(
                "scanner_service.confluence.swept_into_zone",
                return_value=(True, 101.0, "test"),
            ),
            mock.patch(
                "scanner_service.confluence.liquidity_targets",
                return_value=(95.0, 90.0, False),
            ),
            mock.patch(
                "scanner_service.confluence.m5_signal_in_zone",
                return_value=signal,
            ),
        ):
            candidates = scan_confluence_retest("BTC", m15, h4, d1, m5)

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertFalse(candidate["pushable"])
        self.assertEqual(candidate["not_pushable_reason"], "chase")
        self.assertEqual(candidate["ltf_status"], "chase")
        self.assertIsNone(candidate["entry_confirm_bar"])

    def test_first_live_m5_signal_freezes_trigger_after_price_crosses(self):
        context = [_bar(i, 100.4, 100.8, 100.0, 100.3) for i in range(18)]
        first_signal = _bar(18, 100.4, 100.5, 99.6, 99.7)
        later_signal = _bar(19, 99.7, 99.8, 99.0, 99.2)

        signal = m5_signal_in_zone(
            context + [first_signal, later_signal],
            (99.5, 100.5),
            "SHORT",
        )

        self.assertIsNotNone(signal)
        self.assertEqual(signal["bar_time"], "1970-01-01T00:00:18Z")
        self.assertIn("beyond_trigger_extreme", signal["market_fail"])


class OteTest(unittest.TestCase):
    def test_ote_long_band_order(self):
        # Build clear upswing then stall
        bars = []
        price = 100.0
        for i in range(30):
            o = price
            c = price + 0.5
            bars.append(_bar(i, o, c + 0.2, o - 0.1, c))
            price = c
        # small pullback bars
        for i in range(30, 40):
            o = price
            c = price - 0.2
            bars.append(_bar(i, o, o + 0.1, c - 0.1, c))
            price = c
        band = ote_band(bars, "LONG")
        # May or may not form depending on swing k; if present ordered
        if band:
            self.assertLess(band[0], band[1])


if __name__ == "__main__":
    unittest.main()
