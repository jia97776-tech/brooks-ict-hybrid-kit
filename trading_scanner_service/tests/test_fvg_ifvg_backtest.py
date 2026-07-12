import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from backtest_fvg_ifvg_entries import (  # noqa: E402
    ORDER_NAMES,
    detect_cisd_event,
    detect_mss_event,
    first_event_per_symbol_day,
    find_directional_fvg,
    find_ifvg_flip,
    simulate_limit_order,
    simulate_market_entry,
    simulate_stop_order,
)
from scanner_service.sources import Bar  # noqa: E402


def bar(ts, o, h, l, c):
    return Bar(ts=ts, open=o, high=h, low=l, close=c)


def test_finds_latest_bearish_fvg_formed_by_short_displacement():
    bars = [
        bar(0, 105.0, 106.0, 104.0, 105.0),
        bar(300, 104.8, 105.0, 102.0, 102.5),
        bar(600, 101.5, 101.8, 99.0, 99.5),
    ]

    setup = find_directional_fvg(bars, "SHORT", 0, 2)

    assert setup is not None
    assert setup.kind == "fvg"
    assert setup.zone_low == 101.8
    assert setup.zone_high == 104.0
    assert setup.entry == 102.9


def test_finds_bullish_fvg_first_flipped_to_short_ifvg_on_trigger_close():
    bars = [
        bar(0, 99.0, 100.0, 98.5, 99.5),
        bar(300, 100.0, 102.0, 99.8, 101.5),
        bar(600, 103.0, 104.0, 103.0, 103.5),
        bar(900, 103.2, 103.8, 99.5, 99.8),
    ]

    setup = find_ifvg_flip(bars, "SHORT", 0, 3)

    assert setup is not None
    assert setup.kind == "ifvg"
    assert setup.zone_low == 100.0
    assert setup.zone_high == 103.0
    assert setup.entry == 101.5


def test_rejects_directional_fvg_invalidated_before_trigger_close():
    bars = [
        bar(0, 105.0, 106.0, 104.0, 105.0),
        bar(300, 104.8, 105.0, 102.0, 102.5),
        bar(600, 101.5, 101.8, 99.0, 99.5),
        bar(900, 100.0, 105.0, 99.5, 104.5),
    ]

    assert find_directional_fvg(bars, "SHORT", 0, 3) is None


def test_rejects_ifvg_flipped_then_invalidated_before_trigger_close():
    bars = [
        bar(0, 99.0, 100.0, 98.5, 99.5),
        bar(300, 100.0, 102.0, 99.8, 101.5),
        bar(600, 103.0, 104.0, 103.0, 103.5),
        bar(900, 103.2, 103.8, 99.5, 99.8),
        bar(1200, 100.0, 104.0, 99.8, 103.5),
    ]

    assert find_ifvg_flip(bars, "SHORT", 0, 4) is None


def test_detects_short_mss_only_after_swing_is_confirmed():
    bars = [
        bar(0, 104.0, 105.0, 103.5, 104.5),
        bar(300, 104.5, 105.5, 103.8, 105.0),
        bar(600, 105.0, 105.2, 102.0, 102.5),
        bar(900, 102.5, 104.0, 102.2, 103.5),
        bar(1200, 103.5, 103.8, 102.1, 102.6),
        bar(1500, 102.6, 103.0, 102.2, 102.8),
        bar(1800, 102.8, 103.0, 101.0, 101.5),
    ]

    event = detect_mss_event(bars, "SHORT", 0, len(bars) - 1)

    assert event is not None
    assert event.index == 6
    assert event.level == 102.0


def test_detects_short_cisd_close_through_bull_delivery_open():
    bars = [
        bar(0, 100.0, 101.0, 99.5, 100.5),
        bar(300, 100.5, 102.0, 100.2, 101.5),
        bar(600, 101.5, 103.0, 101.0, 102.5),
        bar(900, 102.5, 103.2, 101.8, 102.0),
        bar(1200, 102.0, 102.2, 99.8, 100.2),
        bar(1500, 100.2, 100.4, 99.0, 99.8),
    ]

    event = detect_cisd_event(bars, "SHORT", 0, len(bars) - 1)

    assert event is not None
    assert event.index == 5
    assert event.level == 100.0


def test_market_entry_uses_next_bar_open():
    future = [bar(300, 101.0, 102.0, 97.0, 98.0)]

    result = simulate_market_entry(
        future_bars=future,
        direction="SHORT",
        sl=104.0,
        target=97.0,
        valid_bars=12,
    )

    assert result.filled
    assert result.entry == 101.0
    assert result.outcome == "tp"


def test_limit_order_cannot_fill_on_signal_bar():
    future = [
        bar(300, 99.0, 100.0, 98.0, 99.0),
        bar(600, 99.0, 103.0, 98.5, 102.0),
    ]

    result = simulate_limit_order(
        future_bars=future[1:],
        direction="SHORT",
        entry=102.0,
        sl=104.0,
        target=96.0,
        invalidation_close=104.0,
        valid_bars=12,
    )

    assert result.filled
    assert result.fill_ts == 600


def test_stop_order_fills_only_after_trigger_bar_and_uses_same_bar_loss_first():
    future = [bar(600, 99.0, 102.0, 95.0, 96.0)]

    result = simulate_stop_order(
        future_bars=future,
        direction="SHORT",
        entry=98.0,
        sl=101.0,
        target=95.0,
        valid_bars=12,
    )

    assert result.filled
    assert result.outcome == "sl"
    assert result.result_r == -1.0


def test_same_bar_fill_and_stop_counts_as_loss():
    future = [bar(300, 101.0, 105.0, 100.0, 104.5)]

    result = simulate_limit_order(
        future_bars=future,
        direction="SHORT",
        entry=102.0,
        sl=104.0,
        target=96.0,
        invalidation_close=104.0,
        valid_bars=12,
    )

    assert result.filled
    assert result.outcome == "sl"
    assert result.result_r == -1.0


def test_target_before_limit_fill_is_missed_alpha():
    future = [bar(300, 99.0, 101.0, 95.0, 96.0)]

    result = simulate_limit_order(
        future_bars=future,
        direction="SHORT",
        entry=102.0,
        sl=104.0,
        target=96.0,
        invalidation_close=104.0,
        valid_bars=12,
    )

    assert not result.filled
    assert result.outcome == "missed_alpha"
    assert result.result_r == 0.0


def test_filled_limit_soft_exits_on_array_close_through_before_hard_stop():
    future = [bar(300, 102.0, 103.5, 101.5, 103.2)]

    result = simulate_limit_order(
        future_bars=future,
        direction="SHORT",
        entry=102.0,
        sl=104.0,
        target=96.0,
        invalidation_close=103.0,
        valid_bars=12,
        soft_exit_after_fill=True,
    )

    assert result.filled
    assert result.outcome == "soft_exit"
    assert result.result_r == pytest.approx(-0.6)


def test_order_names_keep_hard_and_soft_array_variants_separate():
    assert ORDER_NAMES == (
        "next_open",
        "event_stop",
        "fvg_ce",
        "fvg_ce_soft",
        "ifvg_ce",
        "ifvg_ce_soft",
    )


def test_first_event_per_symbol_day_keeps_all_orders_for_earliest_event():
    rows = [
        {
            "symbol": "BTC",
            "event": "mss",
            "event_ts": 100,
            "order": "next_open",
        },
        {
            "symbol": "BTC",
            "event": "mss",
            "event_ts": 100,
            "order": "fvg_ce",
        },
        {
            "symbol": "BTC",
            "event": "mss",
            "event_ts": 200,
            "order": "next_open",
        },
        {
            "symbol": "BTC",
            "event": "cisd",
            "event_ts": 150,
            "order": "next_open",
        },
        {
            "symbol": "ETH",
            "event": "mss",
            "event_ts": 110,
            "order": "next_open",
        },
    ]

    selected = first_event_per_symbol_day(rows)

    assert [(row["symbol"], row["event"], row["event_ts"], row["order"]) for row in selected] == [
        ("BTC", "mss", 100, "next_open"),
        ("BTC", "mss", 100, "fvg_ce"),
        ("BTC", "cisd", 150, "next_open"),
        ("ETH", "mss", 110, "next_open"),
    ]
