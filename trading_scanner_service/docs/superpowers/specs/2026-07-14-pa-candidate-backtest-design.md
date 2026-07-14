# PA Candidate Track Backtest Design

## Goal

Determine whether adding PA Agent-inspired candidate tracks improves candidate
recall and net trading results relative to the current ICT scanner without
changing the production scanner.

This experiment answers three separate questions:

1. Do the PA tracks find valid trades that the current ICT track misses?
2. Do those additional trades have positive expectancy after costs?
3. When ICT and PA candidates compete for one portfolio slot, does the merged
   selector improve or damage the current baseline?

The experiment does not evaluate an LLM. It evaluates whether the scanner gives
a strong model a better candidate pool.

## Scope

The backtest is read-only with respect to production code and live state.

It may add:

- one isolated backtest module under `scripts/`;
- focused unit tests for causality and candidate definitions;
- JSON and Markdown reports under `data/backtests/pa_candidate_tracks/`.

It must not modify:

- `scanner_service/scanner.py`;
- live API behavior;
- candidate push behavior;
- skill policy;
- the candidates database or trade journal.

## Dataset

Use the local history in `/home/ubuntu/trading_scanner_service/data/history`.

- Universe: AUDUSD, BTC, DOGE, ETH, EURUSD, GBPUSD, HYPE, NAS100, NZDUSD,
  PEPE, SOL, SUI, TAO, US30, US500, USDCAD, USDCHF, USDJPY, WLD, XAGUSD,
  XAUUSD, XRP, XTIUSD, and ZEC.
- Evaluation interval: the exact common M5/M15 interval from
  March 12, 2026 15:30 UTC through July 10, 2026 15:45 UTC.
- Candidate timeframe: M15.
- Execution timeframe: M5.
- H1 and H4 context: resampled from M15 using only fully closed source bars.
- D1 context: use only D1 bars whose close time is no later than the M15
  decision timestamp.

Each symbol is processed independently. Portfolio comparisons are then built
from the timestamped candidate stream.

## Causality Contract

At decision timestamp `t`:

- features may use only bars closed by `t`;
- a newly generated market candidate fills no earlier than the next M5 open;
- a stop order fills only after a later M5 bar trades through its trigger;
- a limit order fills only after a later M5 bar trades through its price;
- stop and target levels are fixed when the ticket is created;
- if stop and target are both touched in one M5 bar, stop is assumed first;
- no candidate may use a swing until its right-side confirmation bars have
  closed;
- no future ATR, future range boundary, or future target may be used.

The script must include prefix-invariance checks: appending future bars must not
change candidates emitted before the append point.

## Candidate Tracks

### ICT Baseline

Replay the current production sweep path without changing its rules:

- active liquidity sweep;
- MSS and/or CISD;
- POI, DOL, target crowding, RR, HTF and D1 context;
- M1/M5-style executable confirmation represented here by M5;
- chase, stale data, and invalid confirmation handling.

Use production functions where they are causally safe. Emit one candidate per
unique event and suppress repeated snapshots of the same setup.

### PA Trend And Channel Pullback

Generate with-trend candidates that do not require an ICT sweep.

Required evidence:

- deterministic Always-In direction;
- non-chaotic trend or channel environment;
- a pullback toward EMA, prior bar extreme, or confirmed channel structure;
- H1/H2 for long candidates or L1/L2 for short candidates;
- a closed signal bar or a context-valid planned limit at a real structure
  anchor;
- a structural stop and a reachable first target.

Environment labels are evidence, not hard optimization knobs:

- spike;
- micro channel;
- tight channel;
- normal channel;
- broad channel.

### PA Range Edge And Breakout Retest

Generate candidates only at a confirmed range edge or after a confirmed
breakout retest.

Required evidence:

- stable confirmed upper and lower boundaries;
- no midrange entry;
- edge proximity measured against the range width and ATR;
- either a directional edge signal or a breakout followed by a retest;
- structural stop outside the edge or retest structure;
- first target at the range midpoint, opposite edge, or nearest confirmed
  structure, depending on the setup.

Barbwire remains a negative evidence flag. It does not create a candidate.

### PA Second Entry And Failed Breakout

Generate boundary candidates for:

- H2/L2 second entries;
- failed breakout followed by failure of the failure;
- wedge or three-push exhaustion only when paired with a valid second-entry or
  failed-breakout trigger.

A wedge label alone never creates a trade.

## Ticket Construction

Every backtest candidate must produce one executable ticket:

- symbol and source track;
- direction;
- order type;
- decision and entry timestamps;
- entry;
- structural stop;
- first practical target;
- optional runner target for reporting only;
- risk in price units;
- gross RR and cost-adjusted RR;
- setup and environment evidence;
- hard-veto and soft-evidence fields.

The first target alone must pass the minimum trade equation. Runner targets
must not rescue an invalid first-target RR.

## Costs And Settlement

Because the local OHLC history has no historical bid/ask series, report three
locked round-trip execution-cost scenarios for every trade:

- gross: `0.00R`;
- primary: `0.05R`;
- stress: `0.10R`.

The primary promotion decision uses `0.05R`. A result that turns negative at
`0.10R` must be labeled cost-sensitive. These values are declared in the script
before the first run and are not tuned from results.

Settlement uses M5 bars:

- initial hard stop is never widened;
- main target closes the baseline ticket;
- maximum holding period is fixed by setup class;
- unresolved tickets close at the final bar close of their holding window;
- MFE and MAE are measured from entry until exit;
- missed-alpha and no-fill outcomes are recorded separately from losses.

The primary comparison uses the same simple exit policy for all tracks. A
secondary report may apply the existing `+1R` partial-management policy, but it
cannot replace the common-policy result.

## Duplicate And Conflict Handling

Within one symbol:

- identical events are deduplicated by source, direction, structural anchor,
  and trigger timestamp;
- overlapping same-direction candidates within the same structure are one
  campaign;
- opposite candidates cannot both be selected at the same timestamp.

For the merged portfolio:

- allow one new ticket per decision timestamp;
- allow one open ticket per symbol;
- compare candidates using only information available at that timestamp;
- use a predeclared deterministic selector based on hard legality, net first
  target RR, target room, trigger freshness, and stop clarity;
- preserve an ICT quota report so PA candidates cannot hide displacement of
  the existing baseline.

The selector is a backtest proxy for the future strong-model arbiter. Results
must be reported both before and after selection.

## Comparisons

Report these groups:

1. ICT baseline alone.
2. Each PA track alone.
3. All PA tracks combined.
4. ICT plus PA with no competition, for recall accounting.
5. ICT plus PA with one-ticket deterministic selection.
6. ICT candidates displaced by a selected PA candidate.
7. PA candidates that were unique and had no nearby ICT candidate.

Required metrics:

- candidate count and fill rate;
- win rate;
- average and total gross R;
- average and total net R;
- profit factor;
- median R;
- MFE and MAE;
- maximum drawdown in R;
- no-fill and missed-alpha rates;
- monthly and per-symbol stability;
- overlap with the ICT baseline;
- incremental unique-candidate net R;
- displacement cost when a PA candidate replaces an ICT candidate.

## Validation And Promotion Gates

The first run is an evaluation, not a parameter search.

A PA track is not eligible for production shadow mode unless:

- unique candidates have at least 100 filled samples overall;
- net average R is positive;
- profit factor is above 1.05;
- results are not dependent on one symbol or one month;
- merged one-ticket results do not reduce ICT baseline net average R by more
  than 0.05R;
- displacement cost is non-negative;
- all causality and prefix-invariance tests pass.

Failure means the track remains disabled. The report may identify hypotheses
for a separately preregistered second experiment, but parameters must not be
changed and rerun inside this experiment.

## Deliverables

- locked experiment configuration embedded in the script;
- unit tests for resampling, swing visibility, next-bar entry, same-bar stop
  priority, deduplication, and prefix invariance;
- machine-readable candidate and trade files;
- a Markdown report with aggregate, track, symbol, and monthly tables;
- a concise decision: promote to shadow, reject, or insufficient evidence.
