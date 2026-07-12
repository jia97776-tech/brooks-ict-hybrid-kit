# Chart Image Discipline

Rules for analyzing K-line screenshots the user sends (Feishu image relay or local files). Grounded in adversarial audits of vision-LLM chart reading (215-call audit: pattern naming ~1/215 correct, direction prediction ~coin flip with structural long bias). The conclusion is not "never read charts" — it is: **extract structure, never predict from pixels.**

## What a screenshot IS good for

- Reading structure ORDER: sequence of highs/lows, whether the last swing broke the prior one, where the range edges sit relative to current price.
- Reading the cycle state: spike vs channel vs range vs barbwire (per `brooks-market-cycle-playbook.md`) — this is shape recognition at coarse scale, the one thing image reading does reliably.
- Reading what ALREADY happened: a completed sweep wick, a V-reclaim, a failed retest, an obvious climax bar.
- Reading the user's annotations (their lines, their entry marker, their stop) — often the actual question.

## What a screenshot is NOT good for

1. **Precise price levels.** Never quote an exact price read off pixels. Every number in the answer must come from the local API for the same symbol/timeframe. If the API is unavailable, give the structural read and say `图上读不出精确位，报个现价我对齐`.
2. **Direction prediction.** Do not turn a chart image directly into a long/short call. The image feeds the same Invisible Binary Tree as any other evidence; direction still requires the tree's location/trigger/stop/target checks against real data.
3. **Pattern-name confidence.** Naming a textbook pattern from an image is the single least reliable vision operation. Describe behavior (`扫了前低收回来了`), not catalog names.

## Required workflow for every chart image

1. State what symbol/timeframe you BELIEVE the image shows and how you inferred it (title bar, axis, user text). If not inferable, ask one short question — wrong instrument is worse than a delay.
2. Extract the structural read: cycle state, last 2-3 swings in order, where price sits relative to the visible range, any completed sweep/reclaim.
3. Immediately fetch fresh local data for that symbol and reconcile. The API data wins every conflict; if the screenshot looks materially different from the fetched bars (stale screenshot, different venue), say so explicitly.
4. Answer through the normal desk pipeline with API numbers. The image contributes context, never the levels.

## Tone

Same desk contract as everything else: one verdict, one main plan, no image-analysis essay. `这张图我看到的是扫高失败收回，但精确位以本地数据为准：...` is the right shape.
