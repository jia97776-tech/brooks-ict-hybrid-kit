# Stop Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make stop selection scope-explicit before entry, prohibit post-fill widening, and isolate skill-edit commands from live-position state.

**Architecture:** Keep the concise binding rules in `SKILL.md`, detailed execution behavior in existing references, and add deterministic contract tests in the public kit. The public repository is the sanitized share copy; changed policy files are synchronized byte-for-byte to the installed skill while machine-specific reference paths remain local.

**Tech Stack:** Markdown skill files, Python `unittest`, Git, Codex skill validator.

## Global Constraints

- Do not change the active HYPE position state or the active Feishu thread route.
- Preserve the single-plan live-desk style and current entry-order contract.
- Do not add a new scanner formula; this change governs desk judgment and state handling.
- Do not expose personal logs, credentials, runtime state, or market-history files.

---

### Task 1: Add Failing Contract Tests

**Files:**
- Create: `contract_tests/test_skill_contract.py`

**Interfaces:**
- Consumes: repository skill Markdown files.
- Produces: regression assertions for stop scope, anchor enumeration, post-fill lock, and skill-edit isolation.

- [ ] Write assertions for the four missing clauses.
- [ ] Run `python3 -m unittest discover -s contract_tests -v`.
- [ ] Confirm failures point to missing `2026-07-12j` contract language.

### Task 2: Implement Stop Contract

**Files:**
- Modify: `brooks-ict-hybrid/SKILL.md`
- Modify: `brooks-ict-hybrid/references/execution-gates.md`
- Modify: `brooks-ict-hybrid/references/entry-ladder.md`
- Modify: `brooks-ict-hybrid/references/live-desk-template.md`
- Modify: `brooks-ict-hybrid/CHANGELOG.md`

**Interfaces:**
- Consumes: design contract and HYPE calibration case.
- Produces: binding live-desk policy version `2026-07-12j`.

- [ ] Add the scope declaration and relevant-anchor rule.
- [ ] Add pre-fill recomputation and post-fill no-widen behavior.
- [ ] Add file-operation versus position-operation isolation.
- [ ] Add the HYPE case and changelog entry.
- [ ] Run the contract tests and confirm they pass.

### Task 3: Synchronize Installed Skill

**Files:**
- Modify: `/home/ubuntu/.codex/skills/brooks-ict-hybrid/**`

**Interfaces:**
- Consumes: repository skill tree.
- Produces: byte-identical installed copies of the changed policy files.

- [ ] Copy the changed policy files from the repository.
- [ ] Run `quick_validate.py`.
- [ ] Compare the changed policy files and confirm byte identity.

### Task 4: Full Regression Verification

**Files:**
- No production changes expected.

**Interfaces:**
- Consumes: updated skill, scanner, Feishu bridge.
- Produces: fresh test evidence.

- [ ] Run skill contract tests.
- [ ] Run scanner unit tests.
- [ ] Run Telegram and Feishu bridge unit tests.
- [ ] Run Python compilation checks.
- [ ] Run an isolated native-thread first/resume smoke test.
- [ ] Confirm `threads.json` still points to the real active Feishu thread.

### Task 5: Publish GitHub Backup

**Files:**
- Modify: `README.md`
- Commit all approved repository changes.

**Interfaces:**
- Consumes: verified repository.
- Produces: public GitHub commit and direct archive download URL.

- [ ] Update the displayed version and stop-contract summary.
- [ ] Check tracked files for secrets and runtime data.
- [ ] Commit with a focused message.
- [ ] Push `main`.
- [ ] Verify the remote commit and archive download response.
