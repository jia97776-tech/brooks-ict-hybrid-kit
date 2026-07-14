# Feishu Natural Desk Voice Design

## Goal

Make Grok's Feishu trading replies sound like a trader speaking naturally while preserving the full `brooks-ict-hybrid` risk and execution checks internally.

The user must understand the recommended action from the first sentence: enter, wait, hold, reduce, exit, or do nothing.

## Scope

This change covers:

- the canonical `brooks-ict-hybrid` live-answer policy;
- the single-symbol live-desk output reference;
- execution wording for blocked triggers and user-initiated entries;
- the Grok Feishu system prompt;
- regression checks based on the USDCHF conversation.

It does not change scanner calculations, PA_Agent backtests, entry eligibility, stop arithmetic, or journal storage.

## Conversation Contract

### Direct answer first

The first sentence answers the user's actual question. A short question normally receives two to five short lines.

Examples:

- "能进吗？" -> "现在不进，等新的 M5 触发。"
- "这单还拿吗？" -> "别再全仓拿，先平掉。"
- "你的入场价呢？" -> "这次没有我的入场价，信号没过执行条件。"

The reply may explain why after the direct answer, but it must not delay or obscure the action.

### Delta-first follow-ups

Follow-up replies state only what changed. Unchanged stop, targets, trade class, management scheme, and evidence are not repeated.

A full plan is allowed only when:

- presenting the initial executable plan;
- confirming a fill and establishing management;
- a material state change requires a new action;
- the user explicitly asks for the complete plan, audit, or reasoning.

### Human language

Single-symbol live chat must not use tables, report headings, audit blocks, journal metadata, or internal labels by default.

Keep these internal unless the user explicitly asks for technical reasoning:

- `pushable`, `cisd_only`, `confirm_bar`, `market_ok`;
- gate names, tier names, trade-class labels, and journal flags;
- labels such as "抢跑样本", "规则外持有", or "桌面不追认".

Translate them into plain language:

- blocked candidate -> "这张我不做";
- unconfirmed event -> "还没到入场";
- stale trigger -> "已经错过，别追";
- user entered early -> "你已经进了，我按实际成交帮你管".

Do not refer to the assistant as "桌面". Use "我".

### One recommended action

Each reply gives one primary action. Do not offer several equivalent choices such as hold, reduce, or exit in the same sentence.

Only ask the user to reply when an execution fact is required to continue safely, such as whether an order filled or a position was closed.

## Execution Safety Boundaries

### Blocked triggers

When `pushable=false`, the candidate has no actionable desk entry price.

The reply must say:

> 这张我不做，所以没有我的入场价。

Any scanner trigger may remain available for internal audit, but it must not be quoted as a buy-stop, sell-stop, legal expression, or desk entry price.

### User-initiated entry

If the user enters without an approved plan:

1. acknowledge the actual fill once;
2. do not retroactively approve the entry;
3. switch to concise management using the actual fill and current bars;
4. do not expose blame or journal labels during live management.

### No invented post-fill rules

A soft exit can be used only when it was explicitly locked before entry. The assistant must not invent a new M5/M15 close-based soft exit after the user has already filled.

If no soft exit was locked, management uses the existing hard stop, reduction level, target structure, and current invalidation evidence without pretending a new rule was part of the original trade.

### Corrections

When an earlier answer was wrong, correct it in one direct sentence before continuing:

> 我刚才说错了，0.80761 不是可执行入场价，这单当时不该进。

Do not defend the contradiction with additional layers of terminology.

## Component Changes

### Canonical skill

Add a binding mobile conversation contract to `SKILL.md`. It overrides completeness requirements for short follow-ups but does not weaken internal risk checks.

### Live-desk reference

Update `references/live-desk-template.md` with:

- short-answer and delta-first patterns;
- no-table rules for single-symbol chat;
- a blocked-trigger example;
- a user-initiated-entry example;
- explicit full-contract expansion conditions.

### Execution gates

Clarify in `references/execution-gates.md` that blocked trigger prices are audit-only and that no post-fill soft exit may be created.

### Grok bridge

Reduce `telegram_proxy/grok_upstream.py` to channel-specific instructions:

- load the canonical skill;
- use natural Feishu voice;
- answer first and keep follow-ups short;
- hide internal fields;
- use local data before live answers.

Remove duplicated trade contracts that compete with or amplify the skill.

### Pre-send response guard

Add a deterministic Feishu response guard outside the skill. It does not make
or change trading decisions. It only decides whether a generated answer is
clear enough to send.

For ordinary single-symbol trading follow-ups, reject replies that:

- exceed five non-empty lines;
- start without an explicit action;
- contain Markdown tables, report headings, or separators;
- expose hidden audit terms or blame labels;
- combine a blocked candidate with an actionable entry price;
- ask for an unnecessary reply at the end.

On the first rejection, send Grok one rewrite request containing the exact
violations and require the same trading conclusion in natural Chinese. Do not
append a second analysis or refresh market data during this rewrite.

If the rewritten answer still fails, do not send a potentially misleading
entry or management instruction. Return a short message saying the reply did
not pass the clarity check and ask the user to resend the current question.

The guard is relaxed for explicit scan tables, complete plans, audits, and
post-trade reviews. The underlying execution safety checks are never relaxed.

## Regression Tests

Deterministic contract tests will verify:

1. short follow-ups are defined as direct, delta-first, and normally two to five lines;
2. single-symbol live chat forbids tables by default;
3. `pushable=false` explicitly means no desk entry price;
4. blocked trigger prices cannot be described as legal or actionable entries;
5. a post-fill soft exit cannot be invented;
6. user-initiated entries are managed without exposing blame labels;
7. the Grok prompt does not require trade-class labels or four-element reports on every reply;
8. the Grok prompt requires first-sentence action and hidden internal terminology.
9. an overlong or contradictory Grok reply triggers exactly one rewrite;
10. a compliant reply is sent without a rewrite;
11. a second failed reply is replaced by a short clarity-check fallback.

The USDCHF exchange is the calibration fixture:

- correct answer before entry: "这张我不做，所以没有我的入场价";
- correct answer after the user's `0.8074` fill: concise management only;
- forbidden answer: calling `0.80761` the desk's buy-stop while also saying `pushable=false`;
- forbidden action: inventing `M5 close below 0.80731` as a soft exit after fill.

## Verification

- Run the focused skill contract tests and observe RED before policy edits.
- Run the same tests GREEN after policy and prompt edits.
- Run the existing skill contract suite and Telegram/Feishu proxy tests.
- Validate the installed skill copies are synchronized with the canonical files.
- Restart the Feishu proxy only after tests pass, then inspect the running process and one generated prompt.
