# Stop Contract Design

## Goal

Make the initial stop structurally correct before entry, lock its risk after fill, and keep skill-edit instructions separate from live-position instructions.

## Contract

1. Every plan declares one stop scope: `M1/M5 trigger`, `M15 structure`, or `H4 POI layer`.
2. The desk lists the candidates inside that scope, chooses the outermost relevant anchor, then applies the buffer.
3. A higher-timeframe level is included only when the trade thesis requires that whole layer to hold. Background confluence alone does not force an unnecessarily remote stop.
4. Before fill, an omitted relevant anchor invalidates the plan. The desk must recompute entry, size, management, and RR.
5. After fill, the locked hard stop may stay unchanged or move toward lower risk behind newly confirmed structure. It may never move farther into loss.
6. Discovering that the initial scope or anchor was wrong is an execution error, not permission to widen. Correct by reducing or closing; a wider stop belongs to a newly opened, newly sized ticket.
7. Requests to edit, fix, revert, or audit the skill affect files only unless the user explicitly names a symbol and position action. They must not silently change or close a live position.

## HYPE Calibration Case

For the HYPE long, `66.45 - 0.04 = 66.41` was valid arithmetic. The required audit is whether `66.45` was the correct anchor for the stop scope declared before entry. A later `66.31` cannot become a replacement hard stop after fill merely because it is a wider structural level.

## Files

- `brooks-ict-hybrid/SKILL.md`: compact binding contract and hard rule.
- `brooks-ict-hybrid/references/execution-gates.md`: pre-trade scope audit, post-fill lock, and deviation response.
- `brooks-ict-hybrid/references/entry-ladder.md`: entry-time scope and candidate enumeration.
- `brooks-ict-hybrid/references/live-desk-template.md`: required stop output fields.
- `brooks-ict-hybrid/CHANGELOG.md`: dated rationale and HYPE case.
- `contract_tests/test_skill_contract.py`: deterministic policy regression checks.

## Verification

- Regression tests fail against `2026-07-12i`, then pass after the update.
- Skill frontmatter validation passes.
- Changed policy files in the public backup and installed skill are byte-identical; machine-specific path references remain sanitized in the public copy.
- Scanner tests and Feishu bridge tests remain green.
- GitHub remote commit is verified after push.
