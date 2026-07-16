"""Tests for PA_Agent-backfilled environment-quality vetoes (2026-07-11)."""
from scanner_service.sources import Bar
from scanner_service.structure import barbwire, climax_risk, micro_channel


def mk(o, h, l, c, ts=0):
    return Bar(ts=ts, open=o, high=h, low=l, close=c)


def bars_seq(specs):
    return [mk(o, h, l, c, ts=i * 60) for i, (o, h, l, c) in enumerate(specs)]


def trend_context(n=20, step=1.0, base=100.0):
    """Clean uptrend bars to give ATR context before a test window."""
    out = []
    p = base
    for i in range(n):
        out.append(mk(p, p + step, p - step * 0.2, p + step * 0.8, ts=i * 60))
        p += step * 0.8
    return out


def test_barbwire_detects_chop():
    ctx = trend_context()
    last = ctx[-1].close
    chop = []
    for i in range(12):  # tiny doji bars piled on each other
        o = last + (0.05 if i % 2 else -0.05)
        chop.append(mk(o, last + 0.4, last - 0.4, o + (0.02 if i % 2 else -0.02), ts=2000 + i * 60))
    hit, note = barbwire(ctx + chop)
    assert hit, note


def test_barbwire_clean_trend_not_flagged():
    hit, note = barbwire(trend_context(40))
    assert not hit, note


def test_climax_flags_fresh_strong_run():
    ctx = trend_context(20, step=1.0)
    p = ctx[-1].close
    run = []
    for i in range(5):  # 5 huge bull bars, ~1atr each
        run.append(mk(p, p + 1.6, p - 0.05, p + 1.5, ts=3000 + i * 60))
        p += 1.5
    hit, note = climax_risk(ctx + run, "LONG")
    assert hit, note


def test_climax_ignores_stale_or_weak_run():
    ctx = trend_context(20, step=1.0)
    p = ctx[-1].close
    weak = [mk(p + (0.1 if i % 2 else -0.1), p + 0.5, p - 0.5, p, ts=4000 + i * 60)
            for i in range(6)]
    hit, note = climax_risk(ctx + weak, "LONG")
    assert not hit, note


def test_micro_channel_bull_and_none():
    ctx = trend_context(10, step=1.0)
    p = ctx[-1].close
    mc = []
    for i in range(6):  # rising lows, closes never below prior low
        mc.append(mk(p, p + 0.6, p - 0.1, p + 0.5, ts=5000 + i * 60))
        p += 0.5
    side, note = micro_channel(ctx + mc)
    assert side == "LONG", note
    side2, _ = micro_channel(bars_seq([(100, 101, 99, 100.5), (100.5, 101.5, 99.5, 99.8),
                                       (99.8, 100.8, 98.8, 100.2), (100.2, 101, 99, 99.5),
                                       (99.5, 100.5, 98.5, 100.0)]))
    assert side2 is None


def test_signal_bar_strong_weak_ok():
    from scanner_service.structure import signal_bar_quality
    ctx = trend_context(20, step=1.0)
    p = ctx[-1].close
    strong = ctx + [mk(p, p + 1.2, p - 0.1, p + 1.1, ts=9000)]       # big bull body, top close
    grade, note = signal_bar_quality(strong, "LONG")
    assert grade == "strong", note
    doji = ctx + [mk(p, p + 0.8, p - 0.8, p + 0.05, ts=9001)]        # tiny body mid-close
    grade2, note2 = signal_bar_quality(doji, "LONG")
    assert grade2 == "weak", note2
    oversized = ctx + [mk(p, p + 4.0, p - 0.1, p + 3.8, ts=9002)]    # >2.5 ATR bar
    grade3, note3 = signal_bar_quality(oversized, "LONG")
    assert grade3 == "weak", note3
    wrong_side = ctx + [mk(p, p + 1.0, p - 0.4, p - 0.3, ts=9003)]   # bear close for LONG
    grade4, note4 = signal_bar_quality(wrong_side, "LONG")
    assert grade4 == "weak", note4


def test_hl_count_second_entry_and_reset():
    from scanner_service.structure import hl_count
    ctx = trend_context(15, step=1.0)
    p = ctx[-1].close
    # pullback bar (no new high), then new high (H1), pullback, new high (H2)
    seq = ctx + [
        mk(p, p + 0.2, p - 0.8, p - 0.5, ts=7000),
        mk(p - 0.5, p + 1.5, p - 0.6, p + 1.2, ts=7060),
        mk(p + 1.2, p + 1.3, p + 0.3, p + 0.5, ts=7120),
        mk(p + 0.5, p + 2.5, p + 0.4, p + 2.2, ts=7180),
    ]
    assert hl_count(seq, "LONG") >= 2
    # strong bear bar (close < prev low, big range) resets the bull count
    q = seq[-1].close
    reset = seq + [mk(q, q + 0.1, q - 4.0, q - 3.8, ts=7240)]
    assert hl_count(reset, "LONG") == 0


def test_trigger_failed_early():
    from scanner_service.structure import trigger_failed_early
    trig = mk(100.0, 102.0, 99.8, 101.8, ts=8000)  # bull trigger bar, open=100
    ok = [mk(101.8, 103.0, 101.0, 102.5, ts=8060)]
    bad = [mk(101.8, 102.0, 99.0, 99.5, ts=8060)]  # closes below trigger open
    assert not trigger_failed_early(trig, ok, "LONG")
    assert trigger_failed_early(trig, bad, "LONG")


def test_smt_divergence_and_sweep_depth():
    from scanner_service.structure import smt_divergence, sweep_depth_atr, smt_partner
    ctx_a = trend_context(20, step=-0.5, base=200.0)  # downtrend
    ctx_b = trend_context(20, step=-0.5, base=100.0)
    la = min(b.low for b in ctx_a[-16:])
    lb = min(b.low for b in ctx_b[-16:])
    # A sweeps its low; B holds above its low -> SMT for LONG
    a = ctx_a + [mk(la + 1, la + 1.2, la - 0.8, la + 0.9, ts=9100 + i) for i in range(4)]
    b = ctx_b + [mk(lb + 1, lb + 1.2, lb + 0.4, lb + 0.9, ts=9100 + i) for i in range(4)]
    hit, note = smt_divergence(a, b, "LONG")
    assert hit, note
    # both sweep -> no SMT
    b2 = ctx_b + [mk(lb + 1, lb + 1.2, lb - 0.9, lb + 0.9, ts=9100 + i) for i in range(4)]
    hit2, note2 = smt_divergence(a, b2, "LONG")
    assert not hit2, note2
    # inverse SMT (EUR vs DXY style): A swept low; B failed new high
    ha = max(b.high for b in ctx_b[-16:])
    b_inv = ctx_b + [mk(ha - 0.5, ha - 0.1, ha - 1.0, ha - 0.4, ts=9100 + i) for i in range(4)]
    hit_inv, note_inv = smt_divergence(a, b_inv, "LONG", inverse=True)
    assert hit_inv, note_inv
    partner, inv = smt_partner("EURUSD")
    assert partner == "GBPUSD" and inv is False  # same-complex first
    partner_dxy, inv_dxy = smt_partner("AUDUSD")
    assert partner_dxy == "DXY" and inv_dxy is True
    partner2, inv2 = smt_partner("USDJPY")
    assert partner2 == "DXY" and inv2 is False
    partner_xag, inv_xag = smt_partner("XAGUSD")
    assert partner_xag == "XAUUSD" and inv_xag is False
    # sweep depth: pierced 0.8 below level; ATR from context ~1.2
    d = sweep_depth_atr(a, la, "LONG")
    assert 0.1 < d < 2.0, d
