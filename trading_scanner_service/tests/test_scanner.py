import unittest
from unittest import mock

from scanner_service.scanner import scan_symbol
from scanner_service.sources import Bar


def sweep_short_bars():
    """20 bars: deep swing low at 95 (idx2), swing high 105 (idx4), swing low
    100 (idx8), rally sweeps 105 with a wick to 105.5 (idx13) and closes back
    below, then closes break the 100 swing low (MSS) and the up-leg open
    (CISD). Untaken liquidity at 95 remains as DOL."""
    rows = [
        (100.0, 101.0, 99.0, 100.0),
        (100.0, 102.0, 99.5, 101.0),
        (101.0, 103.0, 95.0, 102.0),
        (102.0, 104.0, 101.0, 103.0),
        (103.0, 105.0, 102.0, 104.0),
        (104.0, 104.5, 102.5, 103.0),
        (103.0, 103.5, 101.5, 102.0),
        (102.0, 102.5, 100.5, 101.0),
        (101.0, 101.5, 100.0, 100.5),
        (100.5, 102.0, 100.2, 101.5),
        (101.5, 102.5, 101.0, 102.0),
        (102.0, 103.0, 101.5, 102.5),
        (102.5, 104.0, 102.0, 103.5),
        (103.5, 105.5, 103.0, 104.8),
        (104.8, 105.0, 103.5, 104.0),
        (104.0, 104.2, 102.5, 103.0),
        (103.0, 103.5, 101.0, 101.5),
        (101.5, 102.0, 99.5, 99.7),
        (99.7, 100.5, 99.0, 99.5),
        (99.5, 100.0, 98.8, 99.2),
    ]
    return [Bar(ts=i, open=o, high=h, low=l, close=c, volume=1) for i, (o, h, l, c) in enumerate(rows)]


def mirror(bars, pivot=200.0):
    return [
        Bar(ts=b.ts, open=pivot - b.open, high=pivot - b.low, low=pivot - b.high, close=pivot - b.close, volume=b.volume)
        for b in bars
    ]


def beyond_short_trigger_bars():
    """Move the live price below the already-confirmed short stop trigger."""
    bars = sweep_short_bars()
    last = bars[-1]
    bars[-1] = Bar(
        ts=last.ts,
        open=last.open,
        high=last.high,
        low=98.5,
        close=98.7,
        volume=last.volume,
    )
    return bars


class ScannerTest(unittest.TestCase):
    def test_ready_short_after_sweep_high_with_mss_and_cisd(self):
        candidate = scan_symbol("BTC", sweep_short_bars())

        self.assertEqual(candidate["direction"], "SHORT")
        self.assertEqual(candidate["state"], "READY")
        self.assertTrue(candidate["sweep"])
        self.assertTrue(candidate["mss"])
        self.assertTrue(candidate["cisd"])
        self.assertEqual(candidate["swept_level"], 105.0)
        self.assertEqual(candidate["mss_level"], 100.0)
        self.assertEqual(candidate["dol"], 95.0)
        self.assertGreater(candidate["sl"], 105.5)
        self.assertEqual(candidate["poi"], [105.0, 105.5])
        self.assertGreaterEqual(candidate["rr"], 1.0)
        self.assertFalse(candidate["target_crowded"])

    def test_ready_long_is_mirror_of_short(self):
        candidate = scan_symbol("ETH", mirror(sweep_short_bars()))

        self.assertEqual(candidate["direction"], "LONG")
        self.assertEqual(candidate["state"], "READY")
        self.assertTrue(candidate["sweep"])
        self.assertTrue(candidate["mss"])
        self.assertEqual(candidate["swept_level"], 95.0)
        self.assertEqual(candidate["mss_level"], 100.0)
        self.assertEqual(candidate["dol"], 105.0)
        self.assertLess(candidate["sl"], 94.5)
        self.assertGreaterEqual(candidate["rr"], 1.0)

    def test_trend_without_sweep_is_armed_wait(self):
        bars = []
        price = 100.0
        for i in range(24):
            o = price
            c = o + 0.5
            bars.append(Bar(ts=i, open=o, high=c + 0.2, low=o - 0.2, close=c, volume=1))
            price = c

        candidate = scan_symbol("EURUSD", bars)

        self.assertEqual(candidate["direction"], "WAIT")
        self.assertEqual(candidate["state"], "ARMED")
        self.assertFalse(candidate["sweep"])
        self.assertIn("no completed sweep", candidate["reason"])

    def test_not_enough_bars(self):
        bars = [Bar(ts=i, open=100, high=101, low=99, close=100, volume=1) for i in range(4)]

        candidate = scan_symbol("SOL", bars)

        self.assertEqual(candidate["direction"], "WAIT")
        self.assertEqual(candidate["state"], "ARMED")
        self.assertEqual(candidate["reason"], "not enough bars")


def zigzag_bars(extrema):
    """Build a bar series that oscillates through the given (index, price, kind)
    extrema, each a strict local high/low under SWING_K=2 once interpolated."""
    n = extrema[-1][0] + 3
    idx_list = [e[0] for e in extrema]
    val_list = [e[1] for e in extrema]
    pre_val = val_list[0] + (5 if extrema[0][2] == "low" else -5)
    post_val = val_list[-1] + (5 if extrema[-1][2] == "low" else -5)
    full_idx = [0] + idx_list + [n - 1]
    full_val = [pre_val] + val_list + [post_val]
    prices = [0.0] * n
    j = 0
    for i in range(n):
        while full_idx[j + 1] < i:
            j += 1
        x0, x1 = full_idx[j], full_idx[j + 1]
        y0, y1 = full_val[j], full_val[j + 1]
        prices[i] = y0 if x1 == x0 else y0 + (i - x0) / (x1 - x0) * (y1 - y0)
    extrema_map = {e[0]: e for e in extrema}
    bars = []
    for i in range(n):
        p = prices[i]
        if i in extrema_map:
            _, val, kind = extrema_map[i]
            if kind == "high":
                bars.append(Bar(ts=i, open=p - 0.1, high=val, low=p - 0.2, close=p - 0.1, volume=1))
            else:
                bars.append(Bar(ts=i, open=p + 0.1, high=p + 0.2, low=val, close=p + 0.1, volume=1))
        else:
            bars.append(Bar(ts=i, open=p, high=p + 0.05, low=p - 0.05, close=p, volume=1))
    return bars


CONTRACTING_EXTREMA = [
    (2, 112.0, "high"), (6, 95.0, "low"), (10, 109.0, "high"), (14, 97.0, "low"),
    (18, 107.0, "high"), (22, 98.0, "low"), (26, 104.0, "high"), (30, 100.0, "low"),
]


class ContractingTest(unittest.TestCase):
    def test_symmetric_contraction_detected(self):
        from scanner_service.structure import contracting

        # highs falling 112->109->107->104, lows rising 95->97->98->100: a narrowing coil
        bars = zigzag_bars(CONTRACTING_EXTREMA)
        is_contracting, basis = contracting(bars)
        self.assertTrue(is_contracting)
        self.assertIn("rising", basis)
        self.assertIn("falling", basis)

    def test_trending_channel_is_not_contracting(self):
        from scanner_service.structure import contracting

        # both highs and lows rising: a normal up-channel, not a coil
        bars = zigzag_bars(
            [(2, 100.0, "high"), (6, 95.0, "low"), (10, 104.0, "high"), (14, 99.0, "low"),
             (18, 108.0, "high"), (22, 103.0, "low"), (26, 112.0, "high"), (30, 107.0, "low")]
        )
        is_contracting, basis = contracting(bars)
        self.assertFalse(is_contracting)

    def test_single_noisy_swing_does_not_break_detection(self):
        from scanner_service.structure import contracting

        # same coil as above, but the 3rd high ticks up slightly instead of down
        # (109 -> 110 -> 107 -> 104): first-vs-last across the window should
        # still catch the contraction; a strict step-by-step check would not.
        extrema = list(CONTRACTING_EXTREMA)
        extrema[4] = (18, 110.0, "high")
        bars = zigzag_bars(extrema)
        is_contracting, _ = contracting(bars)
        self.assertTrue(is_contracting)

    def test_not_enough_swings_is_not_contracting(self):
        from scanner_service.structure import contracting

        is_contracting, basis = contracting(sweep_short_bars())
        self.assertFalse(is_contracting)
        self.assertIn("not enough", basis)

    def test_scan_symbol_surfaces_contracting_flag(self):
        bars = zigzag_bars(CONTRACTING_EXTREMA)
        candidate = scan_symbol("WLD", bars)
        self.assertTrue(candidate["contracting"])
        self.assertIsNotNone(candidate["contracting_note"])
        self.assertIn("contraction", candidate["reason"])


class HtfGateTest(unittest.TestCase):
    def test_counter_htf_downgrades_ready(self):
        # M15 sweep-high short against a confirmed H4 LONG bias -> countertrend fade
        candidate = scan_symbol("ETH", sweep_short_bars(), htf=("LONG", "confirmed low-sweep reversal off 1556.75"))

        self.assertEqual(candidate["direction"], "SHORT")
        self.assertEqual(candidate["state"], "CONDITIONAL_READY")
        self.assertTrue(candidate["counter_htf"])
        self.assertEqual(candidate["htf_bias"], "LONG")
        self.assertIn("counter-HTF", candidate["reason"])

    def test_aligned_htf_keeps_ready(self):
        candidate = scan_symbol("ETH", sweep_short_bars(), htf=("SHORT", "confirmed high-sweep reversal"))

        self.assertEqual(candidate["state"], "READY")
        self.assertFalse(candidate["counter_htf"])
        self.assertEqual(candidate["htf_bias"], "SHORT")

    def test_neutral_htf_keeps_ready(self):
        candidate = scan_symbol("ETH", sweep_short_bars(), htf=("NEUTRAL", "no confirmed structure, mixed EMA"))

        self.assertEqual(candidate["state"], "READY")
        self.assertFalse(candidate["counter_htf"])

    def test_no_htf_data_changes_nothing(self):
        candidate = scan_symbol("ETH", sweep_short_bars(), htf=None)

        self.assertEqual(candidate["state"], "READY")
        self.assertIsNone(candidate["htf_bias"])
        self.assertFalse(candidate["counter_htf"])


class MgmtLevelTest(unittest.TestCase):
    def test_mgmt_is_two_r_when_dol_is_far(self):
        candidate = scan_symbol("ETH", sweep_short_bars())
        risk = candidate["sl"] - candidate["entry_ref"]
        self.assertAlmostEqual(candidate["mgmt"], candidate["entry_ref"] - 2 * risk, places=2)
        self.assertGreater(candidate["mgmt"], candidate["dol"])

    def test_mgmt_mirror_long(self):
        candidate = scan_symbol("ETH", mirror(sweep_short_bars()))
        risk = candidate["entry_ref"] - candidate["sl"]
        self.assertAlmostEqual(candidate["mgmt"], candidate["entry_ref"] + 2 * risk, places=2)
        self.assertLess(candidate["mgmt"], candidate["dol"])


class HtfBiasTest(unittest.TestCase):
    def test_confirmed_sweep_reversal_sets_bias(self):
        from scanner_service.structure import htf_bias

        bias, basis = htf_bias(sweep_short_bars())
        self.assertEqual(bias, "SHORT")
        self.assertIn("high-sweep reversal", basis)

        bias, basis = htf_bias(mirror(sweep_short_bars()))
        self.assertEqual(bias, "LONG")
        self.assertIn("low-sweep reversal", basis)

    def test_not_enough_bars_is_neutral(self):
        from scanner_service.structure import htf_bias

        bias, _ = htf_bias(sweep_short_bars()[:10])
        self.assertEqual(bias, "NEUTRAL")


def d1_bull_leg_bars():
    """25 D1 bars: 20 of flat base 98-102, then 5 strong bull closes stepping
    to a fresh 20-bar-high close, plus a small forming bar that must be
    ignored by the completed-bars read."""
    rows = []
    for i in range(20):
        base = 100.0 + (0.5 if i % 2 else -0.5)
        rows.append((base, base + 1.5, base - 1.5, base + (0.4 if i % 3 else -0.4)))
    level = 101.0
    for _ in range(5):
        rows.append((level, level + 3.2, level - 0.4, level + 3.0))
        level += 3.0
    rows.append((level, level + 0.3, level - 0.3, level - 0.1))  # forming bar
    return [Bar(ts=i, open=o, high=h, low=l, close=c, volume=1) for i, (o, h, l, c) in enumerate(rows)]


class D1SpikeTest(unittest.TestCase):
    def test_bull_leg_detected_ignoring_forming_bar(self):
        from scanner_service.structure import d1_spike

        state, basis = d1_spike(d1_bull_leg_bars())
        self.assertEqual(state, "spike_up")
        self.assertIn("bull closes", basis)

    def test_bear_leg_is_mirror(self):
        from scanner_service.structure import d1_spike

        state, _ = d1_spike(mirror(d1_bull_leg_bars()))
        self.assertEqual(state, "spike_down")

    def test_flat_base_is_no_leg(self):
        from scanner_service.structure import d1_spike

        state, _ = d1_spike(d1_bull_leg_bars()[:20])
        self.assertIsNone(state)

    def test_not_enough_bars(self):
        from scanner_service.structure import d1_spike

        state, basis = d1_spike(d1_bull_leg_bars()[:10])
        self.assertIsNone(state)
        self.assertIn("not enough", basis)


class D1GateTest(unittest.TestCase):
    def test_counter_d1_downgrades_ready(self):
        # H4 sweep-high short fired against a fresh D1 bull leg -> pullback, not reversal
        candidate = scan_symbol("SOL", sweep_short_bars(), tf="H4",
                                d1=("spike_up", "LONG", "4/5 bull closes, net +11 >= 1.2xATR"))

        self.assertEqual(candidate["direction"], "SHORT")
        self.assertEqual(candidate["state"], "CONDITIONAL_READY")
        self.assertTrue(candidate["counter_d1"])
        self.assertEqual(candidate["d1_state"], "spike_up")
        self.assertEqual(candidate["d1_bias"], "LONG")
        self.assertIn("counter-D1", candidate["reason"])
        self.assertIn("pullback", candidate["reason"])

    def test_aligned_d1_keeps_ready(self):
        candidate = scan_symbol("SOL", sweep_short_bars(), tf="H4",
                                d1=("spike_down", "SHORT", "4/5 bear closes"))

        self.assertEqual(candidate["state"], "READY")
        self.assertFalse(candidate["counter_d1"])
        self.assertEqual(candidate["d1_state"], "spike_down")

    def test_no_d1_leg_changes_nothing(self):
        candidate = scan_symbol("SOL", sweep_short_bars(), tf="H4", d1=(None, "NEUTRAL", "no fresh D1 leg"))

        self.assertEqual(candidate["state"], "READY")
        self.assertFalse(candidate["counter_d1"])
        self.assertIsNone(candidate["d1_state"])
        self.assertEqual(candidate["d1_bias"], "NEUTRAL")

    def test_no_d1_data_changes_nothing(self):
        candidate = scan_symbol("SOL", sweep_short_bars(), tf="H4", d1=None)

        self.assertEqual(candidate["state"], "READY")
        self.assertIsNone(candidate["d1_state"])
        self.assertIsNone(candidate["d1_bias"])
        self.assertFalse(candidate["counter_d1"])


class StaleDataTest(unittest.TestCase):
    def test_frozen_feed_downgrades_ready(self):
        # bar ts are 0..19; a "now" three M15 intervals later = weekend-frozen feed
        bars = sweep_short_bars()
        candidate = scan_symbol("EURUSD", bars, tf="M15", now=bars[-1].ts + 3 * 900)

        self.assertTrue(candidate["stale_data"])
        self.assertEqual(candidate["state"], "CONDITIONAL_READY")
        self.assertIn("stale feed", candidate["reason"])
        self.assertIn("no live entries", candidate["reason"])

    def test_fresh_feed_untouched(self):
        bars = sweep_short_bars()
        candidate = scan_symbol("BTC", bars, tf="M15", now=bars[-1].ts + 100)

        self.assertFalse(candidate["stale_data"])
        self.assertEqual(candidate["state"], "READY")

    def test_no_now_skips_check(self):
        candidate = scan_symbol("EURUSD", sweep_short_bars())

        self.assertFalse(candidate["stale_data"])
        self.assertEqual(candidate["state"], "READY")

    def test_armed_path_also_flagged(self):
        rows = [(100 + i * 0.5, 101 + i * 0.5, 99.5 + i * 0.5, 100.8 + i * 0.5) for i in range(25)]
        bars = [Bar(ts=i, open=o, high=h, low=l, close=c, volume=1) for i, (o, h, l, c) in enumerate(rows)]
        candidate = scan_symbol("US500", bars, tf="H4", now=bars[-1].ts + 3 * 14400)

        self.assertEqual(candidate["state"], "ARMED")
        self.assertTrue(candidate["stale_data"])
        self.assertIn("stale feed", candidate["reason"])


if __name__ == "__main__":
    unittest.main()


class ConfirmBarTest(unittest.TestCase):
    """confirm_bar contract (2026-07-14): desk quotes scanner fields, never invents triggers."""

    def test_ready_short_has_confirm_bar_with_required_fields(self):
        c = scan_symbol("BTC", sweep_short_bars())
        self.assertEqual(c["state"], "READY")
        cb = c["confirm_bar"]
        self.assertIsNotNone(cb)
        for key in (
            "tf", "role", "map_tf", "entry_tf_hint", "event", "frozen_level",
            "frozen_source", "bar_time", "bar_age", "open", "high", "low", "close",
            "buffer", "buffer_calc", "trigger_price", "trigger_side", "market_ok",
            "market_fail", "expiry_bars", "bars_since_confirm", "cancel_level",
        ):
            self.assertIn(key, cb)
        self.assertIn(cb["event"], ("MSS", "CISD", "MSS+CISD"))
        self.assertIn(cb["frozen_source"], ("confirmed_swing", "delivery_open"))
        self.assertEqual(cb["trigger_side"], "sell_stop_below_low")
        self.assertEqual(cb["cancel_level"], cb["frozen_level"])
        self.assertEqual(cb["expiry_bars"], 6)
        # default scan tf is M15 → map layer, not executable entry
        self.assertEqual(cb["role"], "map_confirm")
        self.assertEqual(cb["entry_tf_hint"], "M5")
        self.assertFalse(c["pushable"])
        self.assertEqual(c["not_pushable_reason"], "map_tf_not_entry")
        # trigger = confirm low - buffer
        self.assertAlmostEqual(cb["trigger_price"], cb["low"] - cb["buffer"], places=5)
        # price has left confirm range on fixture → market_ok false
        self.assertFalse(cb["market_ok"])
        self.assertIn("price_outside_confirm_range", cb["market_fail"])

    def test_ready_long_confirm_bar_is_mirror(self):
        c = scan_symbol("ETH", mirror(sweep_short_bars()))
        self.assertEqual(c["direction"], "LONG")
        cb = c["confirm_bar"]
        self.assertIsNotNone(cb)
        self.assertEqual(cb["trigger_side"], "buy_stop_above_high")
        # both sides rounded by scanner; allow 2dp for large prices
        self.assertAlmostEqual(cb["trigger_price"], round(cb["high"] + cb["buffer"], 5), places=2)

    def test_no_confirm_means_null_confirm_bar(self):
        # Sweep high but no close through MSS/CISD yet: stop after sweep reclaim bars
        # without breaking the 100 swing low.
        rows = [
            (100.0, 101.0, 99.0, 100.0),
            (100.0, 102.0, 99.5, 101.0),
            (101.0, 103.0, 95.0, 102.0),
            (102.0, 104.0, 101.0, 103.0),
            (103.0, 105.0, 102.0, 104.0),
            (104.0, 104.5, 102.5, 103.0),
            (103.0, 103.5, 101.5, 102.0),
            (102.0, 102.5, 100.5, 101.0),
            (101.0, 101.5, 100.0, 100.5),
            (100.5, 102.0, 100.2, 101.5),
            (101.5, 102.5, 101.0, 102.0),
            (102.0, 103.0, 101.5, 102.5),
            (102.5, 104.0, 102.0, 103.5),
            (103.5, 105.5, 103.0, 104.8),  # sweep extreme
            (104.8, 105.0, 103.5, 104.0),
            (104.0, 104.2, 102.5, 103.0),
            (103.0, 103.5, 102.0, 102.5),
            (102.5, 103.0, 101.5, 102.0),
            (102.0, 102.5, 101.2, 101.8),
            (101.8, 102.2, 101.0, 101.5),
        ]
        bars = [Bar(ts=i, open=o, high=h, low=l, close=c, volume=1) for i, (o, h, l, c) in enumerate(rows)]
        cand = scan_symbol("BTC", bars)
        self.assertTrue(cand["sweep"])
        self.assertFalse(cand["mss"])
        self.assertFalse(cand["cisd"])
        self.assertIsNone(cand["confirm_bar"])
        self.assertIsNone(cand["rr_from_trigger"])

    def test_ttl_expiry_nulls_confirm_bar(self):
        base = sweep_short_bars()
        # Pad 6+ bars after last without reclaiming above frozen (stay below ~99)
        extra = []
        last = base[-1]
        for i in range(8):
            ts = last.ts + 1 + i
            extra.append(Bar(ts=ts, open=99.0, high=99.2, low=98.5, close=98.8, volume=1))
        bars = base + extra
        cand = scan_symbol("BTC", bars)
        # Still READY structurally (mss/cisd true historically) but confirm_bar TTL dead
        self.assertIsNone(cand["confirm_bar"])

    def test_reclaim_invalidates_confirm_bar(self):
        base = sweep_short_bars()
        # After confirm, close back above frozen (~100/100.5)
        extra = [
            Bar(ts=base[-1].ts + 1, open=99.5, high=101.5, low=99.4, close=101.2, volume=1),
        ]
        # Need still look like a sweep-high? reclaim may kill active sweep detection.
        bars = base + extra
        cand = scan_symbol("BTC", bars)
        # Either no active sweep or confirm_bar null after reclaim
        if cand["confirm_bar"] is not None:
            self.fail("confirm_bar must be null after close back through frozen")

    def test_m5_entry_tf_can_be_pushable_with_mss(self):
        c = scan_symbol("BTC", sweep_short_bars(), tf="M5")
        self.assertTrue(c["mss"])
        cb = c["confirm_bar"]
        self.assertIsNotNone(cb)
        self.assertEqual(cb["role"], "entry_confirm")
        self.assertTrue(c["pushable"])
        self.assertIsNone(c["not_pushable_reason"])

    def test_m5_entry_tf_beyond_trigger_is_chase_not_pushable(self):
        c = scan_symbol("BTC", beyond_short_trigger_bars(), tf="M5")
        cb = c["confirm_bar"]

        self.assertIsNotNone(cb)
        self.assertIn("beyond_trigger_extreme", cb["market_fail"])
        self.assertFalse(c["pushable"])
        self.assertEqual(c["not_pushable_reason"], "chase")
        self.assertEqual(c["ltf_status"], "chase")
        self.assertIsNone(c["entry_confirm_bar"])

    def test_m5_cisd_only_beyond_trigger_is_still_chase(self):
        with mock.patch(
            "scanner_service.scanner.mss_after_sweep",
            return_value=(None, False),
        ):
            c = scan_symbol("BTC", beyond_short_trigger_bars(), tf="M5")

        self.assertTrue(c["cisd"])
        self.assertFalse(c["mss"])
        self.assertIn("beyond_trigger_extreme", c["confirm_bar"]["market_fail"])
        self.assertFalse(c["pushable"])
        self.assertEqual(c["not_pushable_reason"], "chase")
        self.assertEqual(c["ltf_status"], "chase")
        self.assertIsNone(c["entry_confirm_bar"])

    def test_confirm_tf_role_map_vs_entry(self):
        from scanner_service.structure import confirm_tf_role

        role, map_tf, hint = confirm_tf_role("M5")
        self.assertEqual(role, "entry_confirm")
        self.assertEqual(map_tf, "M5")
        self.assertEqual(hint, "M5")
        role_m, map_tf, hint_m = confirm_tf_role("H4")
        self.assertEqual(role_m, "map_confirm")
        self.assertEqual(map_tf, "H4")
        self.assertEqual(hint_m, "M5")


class LtfConfirmAttachTest(unittest.TestCase):
    def test_wants_ltf_filters(self):
        from scanner_service.scanner import wants_ltf_confirm

        base = {
            "symbol": "BTC", "tf": "M15", "direction": "SHORT", "sweep": True,
            "state": "READY", "mss": True, "cisd": True, "stale_data": False,
            "target_crowded": False,
        }
        self.assertTrue(wants_ltf_confirm(base))
        self.assertFalse(wants_ltf_confirm({**base, "symbol": "PEPE"}))
        self.assertFalse(wants_ltf_confirm({**base, "cisd": True, "mss": False}))
        self.assertFalse(wants_ltf_confirm({**base, "target_crowded": True}))
        self.assertFalse(wants_ltf_confirm({**base, "tf": "M5"}))
        self.assertFalse(wants_ltf_confirm({**base, "stale_data": True}))

    def test_apply_ltf_upgrades_map_parent_pushable(self):
        from scanner_service.scanner import apply_ltf_confirm_bar, scan_symbol

        parent = scan_symbol("BTC", sweep_short_bars(), tf="M15")
        self.assertFalse(parent["pushable"])
        self.assertEqual(parent["not_pushable_reason"], "map_tf_not_entry")
        # Same fixture as M5 = entry confirm with MSS
        upgraded = apply_ltf_confirm_bar(parent, sweep_short_bars(), ltf_tf="M5")
        self.assertIsNotNone(upgraded["ltf_confirm_bar"])
        self.assertEqual(upgraded["ltf_confirm_bar"]["role"], "entry_confirm")
        self.assertTrue(upgraded["pushable"])
        self.assertIsNotNone(upgraded["entry_confirm_bar"])
        self.assertEqual(upgraded["ltf_status"], "entry_pending")

    def test_apply_ltf_beyond_trigger_is_chase_not_pushable(self):
        from scanner_service.scanner import apply_ltf_confirm_bar, scan_symbol

        parent = scan_symbol("BTC", sweep_short_bars(), tf="M15")
        upgraded = apply_ltf_confirm_bar(
            parent,
            beyond_short_trigger_bars(),
            ltf_tf="M5",
        )

        self.assertIsNotNone(upgraded["ltf_confirm_bar"])
        self.assertIn(
            "beyond_trigger_extreme",
            upgraded["ltf_confirm_bar"]["market_fail"],
        )
        self.assertFalse(upgraded["pushable"])
        self.assertEqual(upgraded["not_pushable_reason"], "chase")
        self.assertEqual(upgraded["ltf_status"], "chase")
        self.assertIsNone(upgraded["entry_confirm_bar"])

    def test_apply_ltf_cisd_only_beyond_trigger_is_still_chase(self):
        from scanner_service.scanner import apply_ltf_confirm_bar, scan_symbol

        parent = scan_symbol("BTC", sweep_short_bars(), tf="M15")
        with mock.patch(
            "scanner_service.scanner.mss_after_sweep",
            return_value=(None, False),
        ):
            upgraded = apply_ltf_confirm_bar(
                parent,
                beyond_short_trigger_bars(),
                ltf_tf="M5",
            )

        self.assertTrue(upgraded["ltf_cisd"])
        self.assertFalse(upgraded["ltf_mss"])
        self.assertIn(
            "beyond_trigger_extreme",
            upgraded["ltf_confirm_bar"]["market_fail"],
        )
        self.assertFalse(upgraded["pushable"])
        self.assertEqual(upgraded["not_pushable_reason"], "chase")
        self.assertEqual(upgraded["ltf_status"], "chase")
        self.assertIsNone(upgraded["entry_confirm_bar"])

    def test_apply_ltf_direction_mismatch(self):
        from scanner_service.scanner import apply_ltf_confirm_bar, scan_symbol

        parent = scan_symbol("BTC", sweep_short_bars(), tf="M15")
        # Long-only mirror bars as LTF while parent short
        upgraded = apply_ltf_confirm_bar(parent, mirror(sweep_short_bars()), ltf_tf="M5")
        self.assertEqual(upgraded["ltf_status"], "direction_mismatch")
        self.assertFalse(upgraded["pushable"])
        self.assertIsNone(upgraded["ltf_confirm_bar"])
