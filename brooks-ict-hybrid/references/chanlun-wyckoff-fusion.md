# Chanlun × Wyckoff Fusion (Evidence-Gated, 2026-07-03 全网调研裁决)

Source: 2026-07-03 deep-research sweep (adversarially-verified web research, 103 agents) + GitHub due diligence (Vespa314/chan.py, waditu/czsc, chanlun-pro, Wyckoff repos). Purpose: absorb the useful parts of 缠论 and Wyckoff into this desk WITHOUT importing a second religion. Nothing here changes the Trader Identity Contract, the cycle-state gate, or one-main-plan. PA still decides the action.

The honest headline: after stripping marketing, 缠论 contributes exactly two live tools (中枢 as a mechanical range box, 背驰 as a momentum-exhaustion filter) and Wyckoff contributes one (volume as confirmation where volume is real). Everything else in both systems is either a renaming of what this desk already trades, or unverified narrative.

## Evidence tiers

### Tier 1 — 有证据 (usable, with stated limits)

1. **CICC/中金 2022 OOS study** — the ONLY institutional test of 缠论 constructs with in-sample/out-of-sample separation found anywhere (A股 daily, patterns mined 2005-2015, tested 2016-2022, full universe ex-ST; single split, no costs, sell-side report — medium confidence, not gospel):
   - 三买式 "回踩不破中枢上沿": 120-day avg excess +6.89%, **win rate BELOW 50%**, payoff ratio >1.6 on long holds. The edge is runner-shaped: low win rate paid by RR.
   - 底背驰 (MACD bottom divergence, leg-vs-leg same-sign MACD sum): small short-horizon edge — 20d absolute win rate 55%+, avg +2.38%, and significantly better than a no-divergence control group. Excess-vs-index edge is thin (+1.09%).
   - **顶背驰 clearly weaker than 底背驰** — divergence effectiveness is asymmetric.
   - Source: cls.cn/detail/1017539 (财联社转载), corroborated via Sina/雪球.
2. **Volume law (Wyckoff "effort vs result")**: volume correlates with |price move| robustly (Karpoff 1987, JFQA survey); volume predicting future DIRECTION is weak (Chen 2012, JBF). So volume can confirm, never pick a side.
3. **LMW 2000 (Journal of Finance)**: mechanized chart patterns carry statistical information, but conditional mean returns ≈ 0 — information ≠ tradable profit. The standing reason this file grants vocabulary, not signals.

### Tier 2 — 概念共识但无验证 (vocabulary and structure only, never evidence)

- The mechanical definitions of 分型/笔/中枢 themselves (multiple codified versions exist; each is programmable, none is validated).
- All cross-system concept mappings (spring≈sweep≈failed breakout, 中枢≈trading range, AMD≈吸筹-操纵-派发, etc.).
- Wyckoff phases A-E schematic, three laws as a framework, composite operator.
- 缠论 recursive 级别/区间套.

### Tier 3 — 纯营销 (rejected; if the user brings them, say so)

- **Any quoted win rate for 缠论买卖点** — directly falsified by the only OOS test: 三买-type signals win **under** 50%.
- **Wyckoff quantitative "validation"**: the one paper (arXiv 2403.18839, LSTM "99%+ accuracy") trained AND tested on the author's own synthetic generator — zero real market data, zero trades. GitHub Wyckoff ecosystem has zero serious backtests (QuantifiedStrategies: "no Wyckoff backtest exists on the internet").
- **缠论开源生态 as evidence**: chan.py's author explicitly does not vouch for 缠论 ("我并不觉得缠论一定有用"), his only "results" are ~2 months of simulated trading; czsc claims nothing and ships a disclaimer. Great tool code, zero validity evidence. chanlun-pro and WyckoffTradingAgent are paid-funnel products.

## 中枢: the mechanical range box

The one place 缠论 is sharper than Brooks: it defines the range **objectively** instead of by eye.

- **Desk definition (declared口径, an engineering choice, not "the true 缠论")**: a 中枢 forms when **3+ consecutive overlapping swing legs** share a price overlap. Box = [max(the legs' lows), min(the legs' highs)] — "低点的高者到高点的低者". Legs = the desk's confirmed swings (Brooks legs), NOT 缠论笔 — we deliberately skip 笔/线段 recursion (see negative list).
- **Desk use**:
  - The overlap box IS the objective "middle third": inside it, no trade — this hardens the existing trading-range middle rule and the barbwire rule with a drawable zone.
  - Box edges anchor the range reads the desk already does: edge fades (with stop beyond the true range extreme), failed-breakout triggers, breakout targets.
  - A 中枢 that keeps extending (6, 9+ overlapping legs) is the extreme_tr signature — confidence in any breakout drops, sit out.
- What it does NOT do: a 中枢 existing predicts nothing. It only locates where the desk's range rules apply.

## 三买 / SOS-LPS: breakout-pullback, runner-class

缠论三买 (pullback after breakout holds above 中枢上沿) and Wyckoff SOS→LPS (sign of strength → last point of support) are both the desk's breakout + breakout-test. The evidence adds a management instruction, not a new entry:

- OOS profile says this trade type **wins under half the time and pays via payoff ratio >1.6 on long holds**. So when the desk takes a breakout-pullback in an HTF-aligned trend: it is a **swing/runner trade by construction** — size for several stop-outs, and when it works, let the runner rules work. Managing it like a scalp (quick profit-grab at 1R) deletes the only part that was ever paid.
- Mirror for 三卖/LPSY shorts: untested in the study — say so if asked, same structure logic applies with lower confidence.
- Never quote a win rate for it. If the user quotes "三买胜率70%+", the answer is: the only OOS test says below 50%.

## 背驰: momentum-exhaustion filter (the one new tool)

- **Definition with evidence behind it** (CICC口径): compare same-sign MACD sum (histogram area) of the leg making the new extreme vs the prior same-direction leg into the 中枢. New extreme on visibly smaller momentum = 背驰.
- **Desk use**: at a reversal candidate this desk already allows (sweep-failure / MSS / CISD at a real edge or POI, cycle state permitting), check the leg into the swept extreme:
  - Momentum shrinking vs prior leg (MACD area, or plain Brooks evidence: smaller bodies, more overlap, tails) → the reversal trigger earns one notch more confidence.
  - No divergence, extreme made on expanding momentum → the trigger needs more (deeper confirmation, smaller size, or pass).
- **Asymmetry rule**: bottom divergence (for reversal longs) carries more weight than top divergence (for reversal shorts). Do not treat them as equal evidence.
- **Horizon rule**: the evidence is short-horizon. 背驰 supports the scalp-to-near-liquidity and the management level; it never upgrades a trade to runner by itself — runner still requires HTF alignment.
- **Seniority unchanged**: 背驰 without location + trigger is nothing. In a channel, divergence is a pullback setup, not fade permission — the cycle-state gate stays senior (channel fades remain forbidden; 通道里扫高是继续不是反转).
- **区间套** (LTF divergence inside an HTF POI): this is exactly the desk's existing H4 bias → M15 structure → M1/M5 trigger drill-down. Vocabulary equivalence only; no new rule. If anything, it is one more reason to pull M1/M5 bars at the POI touch.
- Do not litigate 背驰 algorithm wars (area vs slope vs amplitude — chan.py ships ~11 variants, none statistically justified). Bars first, MACD as the tiebreaker check.

## Wyckoff translation table

Same phenomenon, three names — answer in desk language:

| Wyckoff | This desk | Note |
|---|---|---|
| Spring / Shakeout | Sweep of range low + reclaim = failed breakout at the low edge | Already the desk's best range signal; no new rule |
| Upthrust / UTAD | Sweep of range high + failure | Same |
| SC → AR → ST | Climax → first sharp counter-leg → retest, defining a new range | Desk value: after a climax, the AR extreme objectively draws the opposite range edge; consistent with spike aftermath 60/30/10 |
| SOS → LPS | Breakout with follow-through → breakout test that holds | = 三买; runner-class profile above |
| Phases A-E | Range life cycle story | Narrative overlay, zero backtests. "现在是 Phase C 所以要涨" is forbidden reasoning — phases are named AFTER structure confirms, they never predict it |
| Composite operator | Same story as ICT "smart money" | No operational content |
| AMD / Power of 3 | 吸筹-操纵-派发 compressed intraday | Vocabulary only |
| Cause (P&F count) targets | — | No evidence; targets stay structure/liquidity (DOL) based |
| Relative strength | Correlated-symbols read | Already covered by the channel-day correlation rule |

**The one Wyckoff increment — volume confirmation (effort vs result):**

- Breakout on clearly elevated volume = more trustworthy; breakout on dead volume = distrust it, expect the test/failure (feeds the existing "80% of range breakouts fail" prior).
- Heavy volume into an edge with no price progress (effort without result) = absorption hint — supports an existing fade candidate, never creates one.
- **Data gate**: this filter only runs where volume is real — crypto perps from the local feed: yes. FX/CFD/index tick volume from the local stack: broker-synthetic, near-zero weight — say "这品种的成交量数据不可信" instead of pretending to read it.

## User-vocabulary quick map (live chat)

When the user speaks 缠论, hear this and answer in desk language:

- 中枢 → the range box / overlap zone.
- 三买/三卖 → breakout-pullback beyond the box (runner-class: low win rate, paid by RR).
- 二买/二卖 → second entry / the pullback after the first reversal leg holds → maps to Brooks second entry and the MSS-retest the desk already trades.
- 一买/一卖 → catching the extreme with divergence. Desk translation: that is MTR territory — 背驰 alone is never the entry; require the full sequence (sweep failure/trendline break → failed retest of extreme → second entry). Quote the MTR ~35-40% first-attempt prior, not a 缠论 win rate.
- 背驰/盘整背驰 → momentum-exhaustion filter per the rules above.
- 级别 → timeframe layer (H4/M15/M1 here); 区间套 → the existing HTF→LTF drill-down.
- 笔/线段 → the desk's swings/legs. Do not adjudicate 笔 or 线段 formation rules (see below).

## Negative list (do not import)

- **线段 mechanization** — the graveyard of 缠论 engineering: three competing termination algorithms coexist in chan.py, the czsc author abandoned segments entirely and builds on 笔. The desk uses confirmed swings + cycle states instead, and never argues 线段 termination with the user.
- **笔口径 wars** (老笔/新笔/czsc min_bi_len) — even the original author shipped two incompatible definitions. Desk swings make the question moot.
- **Full recursive 级别 bookkeeping** (1分钟中枢→5分钟走势→30分钟...) — unfalsifiable as practiced; the tradable content is multi-TF structure, which the desk already runs.
- **All 买卖点/Wyckoff win-rate claims, the LSTM paper, paid-course schematics** — Tier 3 above.
- **Wyckoff schematic as forecast** — phase labels only after structure confirms.

## Hard gates unchanged

- Cycle state gate stays senior to everything here: 背驰 in a channel ≠ fade permission; a spring-looking sweep inside a micro channel is continuation, not reversal.
- One pattern alone is never a trade (Mesfin anchor in `execution-aids-evidence.md` — naked signals test empty; the edge lives in the joint condition).
- Every level and every divergence claim traces to API bars, never to eyeballing.
- Sample-size discipline: the CICC numbers are A股 daily, single OOS split, no costs — they justify trade-TYPE management (runner vs scalp class), never a live expectancy quote for this user's markets.
