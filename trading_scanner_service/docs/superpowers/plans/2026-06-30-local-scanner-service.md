# Local Scanner Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local `127.0.0.1:8001` scanner service compatible with the live-desk endpoints.

**Architecture:** A small Python standard-library HTTP service exposes `/price`, `/bars`, `/scanner/run-once`, `/scanner/status`, plus `/scan/run` aliases. Market data is isolated behind source adapters so routing rules stay out of scanner logic.

**Tech Stack:** Python 3.10 standard library, `unittest`, `urllib.request`, `http.server`.

---

### Task 1: Data Source Routing

**Files:**
- Create: `scanner_service/sources.py`
- Test: `tests/test_sources.py`

- [x] Write failing tests for symbol classification and endpoint routing.
- [x] Run tests and confirm imports fail before implementation.
- [x] Implement MEXC contract routing for crypto/metals/indices/energy and Gate TradFi routing for FX.
- [x] Run tests and confirm routing passes.

### Task 2: Scanner Logic

**Files:**
- Create: `scanner_service/scanner.py`
- Test: `tests/test_scanner.py`

- [x] Write failing tests for READY/ARMED candidate generation from OHLC bars.
- [x] Implement minimal deterministic scan classification.
- [x] Run scanner tests.

### Task 3: HTTP API

**Files:**
- Create: `scanner_service/server.py`
- Test: `tests/test_server.py`
- Create: `run_server.py`

- [x] Write failing tests for legacy and migrated endpoint shapes.
- [x] Implement standard-library HTTP routes.
- [x] Run endpoint tests.

### Task 4: Verification

**Files:**
- Create: `README.md`

- [x] Document commands.
- [x] Run full unittest suite.
- [x] Start service on port 8001 and smoke-test endpoints.
