# PA Agent Binary Decision Tree

Source: local PA_Agent at `C:\Users\38646\Documents\Codex\2026-06-18\claude-codex-hermes-r-r-ict-2\external_repos\PA_Agent`.

Use this reference to reduce hallucination in chart analysis. The method is simple: every step asks one narrow yes/no question, records the evidence, and only then moves to the next step. If the answer is unclear, default to `wait`, not a forced long or short.

## Core Order

1. Data sufficiency
2. Market condition
3. Liquidity destination
4. Entry location
5. Entry trigger
6. Stop, target, and trade equation
7. Order type
8. Management and invalidation

Do not run the trade equation before entry, stop, and target are all defined.

Do not treat PA and ICT as two separate checklists. The binary tree is the fused spine:

- PA/Brooks answers whether the environment is tradable.
- ICT answers where price is likely being drawn and where entry may make sense.
- PA/Brooks answers again whether the trigger, follow-through, invalidation, and trade equation are good enough.

## Trace Format

Use a trace row whenever making a gated judgment:

- `node_id`: stable node label, such as `0.1`, `ICT.3`, `9.0`, `10.3`
- `question`: one question only
- `answer`: `是`, `否`, `中性`, `等待`, or `不适用`
- `reason`: concrete chart evidence, not a story
- `bar_range`: the bars or visible area used as evidence, such as `K20-K1`, `H1`, `visible range`
- `branch`: optional branch selected by the answer

If the user supplied only a screenshot and bars cannot be numbered, use approximate visible evidence like `visible left swing to current bar` and explicitly mark the limitation.

## Stage 1 Gate

Stage 1 decides whether analysis may continue. It does not decide a trade.

Ask:

1. Is the input usable enough to identify symbol/timeframe or at least visible structure?
2. Is the market condition identifiable: trend, range, transition, or unknown?
3. Is the market extremely messy or unreadable?
4. Is there a directional bias, or is the best answer neutral?
5. Is there a named liquidity/magnet target that fits that bias?
6. Is Always-In present? If not, continue to strategy branches instead of stopping automatically.

Stage 1 outcomes:

- `proceed`: enough evidence exists to analyze scenarios.
- `wait`: structure is unknown, the chart is unreadable, or evidence is too thin.
- `unknown`: required context is missing and assumptions would dominate.

Important: lack of Always-In is not automatically `wait`. It often means switch to range, pullback, or boundary logic.

## Stage 2 Decision

Stage 2 decides whether there is a trade plan. It must use a `decision_trace` and a `terminal` outcome.

Minimum nodes:

1. `ICT.1`: Is there a named liquidity target or magnet?
2. `ICT.2`: Is price at a valid PDA, range edge, pullback zone, or failed-breakout area?
3. `PA.1`: Does the PA context allow this ICT idea, or is the market too overlapping/mixed?
4. `9.0`: Is there an actual entry plan or trigger?
5. `10.1`: Can the stop be defined from structure?
6. `10.2`: Is the target meaningful and not too close?
7. `10.3`: Does the trade equation pass after entry, stop, and target are known?
8. `11`: Is the order type appropriate: limit, stop entry, market, or no trade?

Terminal outcome semantics:

- `wait`: no entry plan exists, the trigger has not completed, the chart is mixed, or required data is missing.
- `reject`: an entry plan exists with entry/stop/target, but quality or trade equation fails.
- `trade`: entry/stop/target exist, the equation passes, and context supports execution.
- `proceed`: used only when handing off to another workflow step, not as a trade claim.

Never use `reject` just because there is no trade. No entry plan means `wait`.

## Anti-Hallucination Rules

- One node, one question. Do not combine direction, entry, stop, and target in one answer.
- Each claim must name evidence: a bar, swing, range edge, liquidity sweep, FVG, EMA relation, or visible rejection.
- If a level is not visible or provided, say it is unknown. Do not invent prices.
- If PA context and ICT location disagree, downgrade confidence or return `wait`.
- If only a screenshot is available, avoid precise trade prices unless the chart visibly labels them.
- Do not turn pattern names into conclusions. A sweep, FVG, wedge, H2/L2, or Always-In condition is evidence, not a full trade by itself.
- Confidence must follow the gates. A narrative that skipped gates cannot be an A setup.

## Fusion Rules

Use these translations while filling the gates:

| ICT term | PA meaning | Gate use |
| --- | --- | --- |
| DOL / liquidity target | Magnet, target, or place where trapped traders may be relieved | Use for `ICT.1` and `10.2` |
| PDA | Candidate location, not a signal | Use for `ICT.2` only |
| Sweep | Failed breakout or stop run at a prior extreme | Needs PA rejection or entry bar |
| Displacement | Breakout with follow-through | Weak follow-through downgrades it |
| FVG / IFVG | Pullback gap or imbalance | Wait for signal/entry bar |
| OB / breaker / BPR | Structure zone | Must fit trend/range context |
| MSS / CISD | Trigger candidate | Must define stop and invalidation |
| SMT | Context divergence | Never enough by itself |

The final verdict must be one fused sentence, not three separate framework summaries.

## Brooks + ICT Gate Template

Use this compact template in internal reasoning or when the user explicitly asks for a full report / gate trace — never show it in normal live chat (the tree stays invisible per SKILL.md):

| Node | Question | Answer | Evidence |
| --- | --- | --- | --- |
| 0.1 | Is the input sufficient? |  |  |
| 1.1 | Is the market condition identifiable? |  |  |
| 2.1 | Is directional bias clear? |  |  |
| ICT.1 | Is there a named liquidity target? |  |  |
| ICT.2 | Is price at a valid PDA or range edge? |  |  |
| ICT.3 | Is there a sweep/displacement/reclaim confirmation? |  |  |
| PA.1 | Is the signal bar/entry trigger valid? |  |  |
| 10.1 | Can invalidation be defined? |  |  |
| 10.2 | Is target space meaningful? |  |  |
| 10.3 | Does the trade equation pass? |  |  |

Then produce:

- `terminal`: `wait`, `reject`, or `trade`
- `reason`: the first failed or decisive node
- `best next evidence`: what would change the verdict

## Always-In And 20GB Safeguard

When Always-In Long is clear, the first short reversal signal is low quality until trendline break, prior extreme test failure, and second entry appear. Reverse this for Always-In Short.

When about 20 bars have not touched the EMA (`20GB`), do not fade the trend just because price is extended. First EMA touch is usually treated as a trend test or scalp context, not an automatic reversal. If two attempts fail, stop forcing the same structure and re-diagnose the market.
