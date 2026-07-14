# Feishu Natural Desk Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Grok's Feishu trading replies direct, short, internally consistent, and automatically rewritten once before delivery when they violate the mobile desk voice contract.

**Architecture:** Keep trading judgment in the canonical `brooks-ict-hybrid` skill, keep Feishu channel style in the Grok system prompt, and add a deterministic pre-send guard in the proxy. The guard never changes prices or trade decisions; it reports wording violations and asks the same Grok session to rewrite once while preserving the original conclusion.

**Tech Stack:** Markdown skill contracts, Python 3 standard library, `unittest`, Grok CLI session resume, local Feishu proxy.

## Global Constraints

- Do not modify or discard the paused PA_Agent backtest worktree or its uncommitted tests.
- Work with the existing dirty canonical repository; do not revert unrelated user changes.
- A normal single-symbol follow-up answers the action in the first sentence and normally uses two to five non-empty lines.
- `pushable=false` means there is no actionable desk entry price.
- A soft exit may not be invented after fill.
- The response guard may reject or request a rewrite, but it may not alter trading judgment, prices, stops, targets, or position state.
- Only explicit scan, full-plan, audit, and review requests receive relaxed formatting checks.

---

### Task 1: Canonical Skill Conversation Contract

**Files:**
- Create: `contract_tests/test_feishu_natural_voice_contract.py`
- Modify: `brooks-ict-hybrid/SKILL.md`
- Modify: `brooks-ict-hybrid/references/live-desk-template.md`
- Modify: `brooks-ict-hybrid/references/execution-gates.md`

**Interfaces:**
- Consumes: existing `confirm_bar`, `pushable`, post-fill stop, and soft-exit policy.
- Produces: binding natural-language markers consumed by humans and checked by deterministic contract tests.

- [ ] **Step 1: Write the failing skill contract tests**

```python
class FeishuNaturalVoiceContractTests(unittest.TestCase):
    def test_short_followups_are_direct_delta_first_and_table_free(self):
        self.assertIn("第一句直接回答当前动作", self.skill)
        self.assertIn("通常 2–5 行", self.skill)
        self.assertIn("只说变化", self.template)
        self.assertIn("单品种实时追问禁止表格", self.template)

    def test_blocked_candidate_has_no_desk_entry_price(self):
        for text in (self.skill, self.gates, self.template):
            self.assertIn("这张我不做，所以没有我的入场价", text)
        self.assertIn("禁止把审计 trigger 报成可执行入场价", self.gates)

    def test_user_entry_does_not_create_postfill_soft_exit(self):
        self.assertIn("不展示抢跑、违规、journal 等责备标签", self.template)
        self.assertIn("成交后不得新增软离场", self.gates)
```

- [ ] **Step 2: Run the focused contract test and verify RED**

Run: `python3 -m unittest contract_tests.test_feishu_natural_voice_contract -v`

Expected: FAIL because the required direct-answer, blocked-trigger wording, and hidden-label rules are not present yet.

- [ ] **Step 3: Add the minimal binding policy**

Add a `Feishu / Mobile Conversation Contract` section to `SKILL.md` that:

- runs all gates internally;
- answers `进 / 不进 / 等 / 拿 / 减 / 平` in the first sentence;
- defaults short follow-ups to two to five lines;
- repeats only changed state;
- hides audit labels and avoids self-reference as "桌面";
- reserves full contracts for initial executable plans, fills, material changes, or explicit requests;
- makes the blocked-trigger sentence binding;
- manages unapproved user fills without retroactive approval or invented soft exits.

Update `live-desk-template.md` with compact examples and update `execution-gates.md` with the blocked-trigger and post-fill boundaries.

- [ ] **Step 4: Run focused and existing contract suites**

Run:

```bash
python3 -m unittest contract_tests.test_feishu_natural_voice_contract -v
python3 -m unittest contract_tests.test_skill_contract -v
```

Expected: PASS.

- [ ] **Step 5: Commit the canonical skill policy**

```bash
git add contract_tests/test_feishu_natural_voice_contract.py \
  brooks-ict-hybrid/SKILL.md \
  brooks-ict-hybrid/references/live-desk-template.md \
  brooks-ict-hybrid/references/execution-gates.md
git commit -m "Make live desk replies conversational"
```

---

### Task 2: Deterministic Feishu Response Guard

**Files:**
- Create: `/home/ubuntu/telegram_proxy/telegram_proxy/response_guard.py`
- Create: `/home/ubuntu/telegram_proxy/tests/test_grok_upstream.py`
- Modify: `/home/ubuntu/telegram_proxy/telegram_proxy/grok_upstream.py`

**Interfaces:**
- Produces: `GuardResult(ok: bool, violations: tuple[str, ...])`.
- Produces: `inspect_feishu_reply(user_text, reply, *, trading_context, expanded) -> GuardResult`.
- Produces: `build_rewrite_prompt(user_text, reply, violations) -> str`.
- Consumes: generated Grok reply, current user message, and recent conversation state.

- [ ] **Step 1: Write failing guard and integration tests**

Cover these cases:

```python
def test_compliant_short_reply_is_sent_without_rewrite(): ...
def test_long_report_is_rewritten_once(): ...
def test_pushable_false_with_entry_price_is_rewritten(): ...
def test_second_guard_failure_returns_clarity_fallback(): ...
def test_non_trading_chat_is_not_forced_into_trade_action_shape(): ...
def test_system_prompt_does_not_require_trade_class_or_four_elements(): ...
```

The fake runner must capture each prompt file before it is deleted and return queued replies.

- [ ] **Step 2: Run the focused proxy test and verify RED**

Run: `python3 -m unittest tests.test_grok_upstream -v`

Expected: FAIL because `response_guard.py`, rewrite behavior, and the thinned prompt do not exist.

- [ ] **Step 3: Implement the response guard**

Implement:

```python
@dataclass(frozen=True)
class GuardResult:
    ok: bool
    violations: tuple[str, ...]


def inspect_feishu_reply(
    user_text: str,
    reply: str,
    *,
    trading_context: bool,
    expanded: bool,
) -> GuardResult:
    ...
```

Always check blocked-trigger contradictions. For compact trading replies also check:

- more than five non-empty lines;
- missing action in the first non-empty line;
- Markdown headings, tables, or separators;
- internal audit and blame terms;
- formulaic "reply with one of these options" endings.

Implement intent helpers for trading context and explicit expanded requests.

- [ ] **Step 4: Thin the Grok prompt and integrate one rewrite**

Replace duplicated trading contracts in `SYSTEM_PROMPT` with:

- canonical skill loading;
- local-data freshness;
- first-sentence action;
- two-to-five-line delta-first follow-ups;
- hidden internal terminology;
- no table for single-symbol chat;
- no unnecessary reply request.

Refactor Grok invocation into a helper that can run the initial prompt and, when rejected, resume the same Grok session with exactly one rewrite prompt. Persist only the original user message and the final delivered reply in local state.

- [ ] **Step 5: Run focused and complete proxy suites**

Run:

```bash
python3 -m unittest tests.test_grok_upstream -v
python3 -m unittest discover -s tests -v
```

Expected: PASS with one rewrite call only for violating replies.

---

### Task 3: Sync, Restart, and Runtime Verification

**Files:**
- Sync:
  - `/home/ubuntu/.codex/skills/brooks-ict-hybrid/SKILL.md`
  - `/home/ubuntu/.codex/skills/brooks-ict-hybrid/references/live-desk-template.md`
  - `/home/ubuntu/.codex/skills/brooks-ict-hybrid/references/execution-gates.md`
  - `/home/ubuntu/.grok/skills/brooks-ict-hybrid/...`
  - `/home/ubuntu/.claude/skills/brooks-ict-hybrid/...`

**Interfaces:**
- Consumes: tested canonical policy and tested proxy.
- Produces: byte-identical active skill policy for Codex, Grok, and Claude plus a restarted Feishu proxy.

- [ ] **Step 1: Compare active copies before synchronization**

Run `sha256sum` for the three modified canonical files and each active runtime copy. Record any unrelated differences and do not overwrite files outside the three-file set.

- [ ] **Step 2: Copy only the tested policy files**

Use `install -m 0644` to copy the canonical `SKILL.md`, `live-desk-template.md`, and `execution-gates.md` to `.codex`, `.grok`, and `.claude`.

- [ ] **Step 3: Verify byte identity**

Run `sha256sum` again and confirm each group of four paths has one checksum.

- [ ] **Step 4: Locate and restart the actual Feishu proxy**

Inspect the process launcher and runtime logs. Restart only the Grok/Feishu proxy process, preserving state JSON files.

- [ ] **Step 5: Verify runtime prompt and guard behavior**

Run a local fake-runner smoke test for the USDCHF contradiction:

- first reply contains `pushable=false` plus `0.80761 buy-stop`;
- rewrite reply says `这张我不做，所以没有我的入场价`;
- delivered output is the rewrite;
- exactly two Grok invocations occur.

Confirm no required execution session remains running and report the restart status.
