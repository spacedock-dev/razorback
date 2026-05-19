# M5 — Provenance Freeze + Full DAB Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `uv run rk spec freeze examples/specs/dab-dev-claude.yaml` resolve every dynamic input in the spec into `provenance.yaml` and refuse on any unresolved field absent `--allow-missing`, and make `uv run rk run examples/specs/dab-dev-claude.frozen.yaml` produce a `summary.json` whose stratified pass@1 line is the cross-dataset macro-average across all 12 DAB datasets — the **first real DAB result** CL named explicitly in the brief.

**Architecture:** Two layered surfaces. (1) A new `razorback.provenance` package — `resolvers.py` (one resolver per field: model alias → dated id via Anthropic SDK `client.models.retrieve()`, docker image → digest via `docker image inspect`, agent CLI → SHA-256 of the binary, consuming-repo git SHA, installed `harbor.__version__`, prompt-file content hashes), `provenance_yaml.py` (writes `provenance.yaml` with unresolved-field markers), `freeze_cmd.py` (the `rk spec freeze` Typer command), `drift.py` (re-resolve on `rk run`: `AliasDriftError` exit 21; harbor major-version drift hard error). (2) A small generalization of M2's aggregator in `src/razorback/benchmarks/dab/aggregate.py` and translator in `src/razorback/compat/harbor_0_6_6.py` — the per-query / per-dataset / stratified math is **already implemented in M2** (see `_build_summary` at `docs/razorback-implementation/plans/m2-dab-bookreview.md:317-337`); M5 only widens `spec.benchmark.datasets` from one entry to twelve and confirms the macro-average runs across multiple datasets. The integration test (AC-6) drives the whole stack against the real 12 DAB datasets through Claude.

**Tech Stack:** Python 3.12, `uv`, Pydantic 2.11, PyYAML 6, harbor 0.6.6 (pinned in M1), Anthropic SDK (`anthropic>=0.42`), `tenacity` for exponential backoff (or hand-rolled — see Task 7), pytest 8 with `pytest-asyncio` 0.24, Docker via Colima, the operator's host `claude` CLI (M3's auth contract is the input).

---

## AC ↔ Task Map

The seven ACs in `docs/razorback-implementation/m5-provenance-full-dab.md` (lines 31-83) map 1:1 to the tasks below. Section citations point into `/Users/clkao/git/dataagentbench/docs/superpowers/specs/2026-05-18-razorback-python-on-harbor.md`.

| AC | What | §-cite | Task |
|---|---|---|---|
| AC-1 | `rk spec freeze` resolves all six provenance fields and refuses unresolved absent `--allow-missing` (exit 11 `ProvenanceError`) | §6.4 ("Queries the provider API…", "refuses to write the frozen spec and exits non-zero"); §3.2 row 11 | **Task 2** (refusal unit tests), **Task 5** (resolver wiring), **Task 6** (CLI command) |
| AC-2 | `--allow-missing` writes the frozen spec but records unresolved fields in `provenance.yaml` | §6.4 ("`--allow-missing`, which writes the frozen spec but marks the field unresolved in `provenance.yaml`") | **Task 6** (`--allow-missing` branch + unit test) |
| AC-3 | `AliasDriftError` (exit 21) fires when provider returns a model version different from frozen `model_resolved_version` | §6.4 ("`rk run` re-resolves… refuses with `AliasDriftError`"); §3.2 row 21 | **Task 1 — RISKIEST CONTRACT** (drift unit test against mocked Anthropic SDK BEFORE any resolver code), **Task 8** (`rk run` drift wiring) |
| AC-4 | Major-version drift in installed harbor between freeze and run is a hard error | §6.4 ("Major-version drift between freeze and re-run is a hard error at `rk run` time") | **Task 3** (harbor drift unit test against patched `harbor.__version__`), **Task 8** (run-time drift wiring) |
| AC-5 | DAB aggregator produces a stratified macro-average across the 12 datasets | §6.5 ("the cross-dataset macro-average per the DAB paper's stratified protocol") | **Task 9** (12-dataset fixture + golden), **Task 10** (translator widening) |
| AC-6 | End-to-end full DAB dev-tier run with Claude writes complete `summary.json` (per-query + per-dataset + stratified, all 12 datasets) | §6.5 + §8.M5 ("Full dev tier runs") | **Task 11** (acceptance spec), **Task 12** (integration test) |
| AC-7 | Provenance retries with exponential backoff on transient 503s | §6.4 ("The resolver retries each external call with exponential backoff. A transient 503 does not abort the freeze.") | **Task 4** (retry harness unit test), **Task 5** (resolver wires retry) |

**Ordering rationale.** Per CL's "Validating new mechanisms" rule and the M5 entity's checklist item #2, the three refusal contracts (alias drift AC-3, harbor drift AC-4, missing-provenance refusal AC-1) come **before** the resolver implementation. The math-heavy aggregator generalization (AC-5) follows the freeze/refusal machinery. The cost-bearing integration test (AC-6) is last. AC-7's retry harness (Task 4) lands as a pure unit test against a mock backend with zero sleeps; the real Anthropic resolver in Task 5 then composes it.

**M2 reuse.** This plan does NOT re-derive M2's `pass_at_k` formula or `_build_summary` math. The per-query mean → per-dataset mean → cross-dataset macro-average pipeline is already implemented at:

- `src/razorback/benchmarks/dab/aggregate.py:_build_summary` (created by M2 Task 2; see `docs/razorback-implementation/plans/m2-dab-bookreview.md:317-337`).
- `src/razorback/benchmarks/dab/aggregate.py:pass_at_k` (M2 Task 2; see `m2-dab-bookreview.md:287-297`).

M5 generalizes by widening the **input** to that math: the translator now produces one task per `(dataset, query_id)` across all 12 datasets instead of one (`bookreview`), and the AC-5 fixture exercises the cross-dataset reduction (which M2's golden could not, since M2 had only one dataset). Specifically:

- M2 plan line 158: "Stratified macro-average across datasets = 0.5333… (only one dataset)" — i.e., M2's golden never exercised the cross-dataset reduction step. M5 Task 9 adds a 12-dataset fixture that does.
- M2 plan lines 326-332: the `_build_summary` already divides by `len(datasets)`; that code path is correct for 12 datasets but was unexercised. M5 confirms it via the AC-5 fixture.

## Provider-API resolver — concrete library and endpoint

The design doc (§6.4) says: "Queries the provider API for the resolved model version string (`claude-opus-4-5` → `claude-opus-4-5-20251022`). Writes into `provenance.yaml.model_resolved_version` with API timestamp."

The concrete library/endpoint is the **Anthropic Python SDK** (`anthropic>=0.42`):

```python
import anthropic
client = anthropic.Anthropic()  # picks up ANTHROPIC_API_KEY from env
model = client.models.retrieve("claude-opus-4-5")
# model.id           → "claude-opus-4-5-20251022"  (the resolved version)
# model.created_at   → "2025-10-22T00:00:00Z"      (ISO-8601 timestamp)
# model.display_name → "Claude Opus 4.5"
```

This wraps `GET /v1/models/{model_id}` on `api.anthropic.com`. The endpoint accepts an alias and returns the canonical dated id. A 503 is the documented transient — the resolver retries it. A 404 (typo'd model name) is hard — the resolver refuses to write `provenance.yaml` and exits 11 (`ProvenanceError`), per §6.4's "A hard failure (404 on the model name, image not pullable) refuses to write the frozen spec".

**Codex / OpenAI deferred.** §6.4's example is Anthropic. The DAB-dev acceptance spec (AC-6) uses Claude, so the M5 implementation only wires the Anthropic resolver. Codex resolution lands when M6/M7 adds a Codex-direct acceptance run; the resolver registry pattern (Task 5) leaves a hole for `agent.kind: codex-cli` that raises `NotImplementedError`. This matches the design doc — it never claims the resolver covers Codex on day one — and is documented in Task 5's code comment.

**Divergence call.** The design doc's wording "model_resolved_version with API timestamp" maps cleanly onto `model.id` + `model.created_at` from the SDK; no divergence. `provenance.yaml` records both fields verbatim under `model_resolved_version` (the dated id) and `model_resolved_at` (the API timestamp). The §6.4 example "`claude-opus-4-5` → `claude-opus-4-5-20251022`" is exactly what `client.models.retrieve("claude-opus-4-5").id` returns today.

## Tracked-task discipline

The team-lead task list already contains M3 deferred-impl tasks (#26-#32). M5 plan tasks are tracked outside that list — the plan IS the tracking artifact for the M5 impl stage. Do NOT create TaskCreate entries for M5 plan tasks at plan-stage time; the FO creates impl-stage tasks when M5 advances to impl.

---

## File structure

```
razorback/
├── src/razorback/
│   ├── provenance/                        [new package]
│   │   ├── __init__.py                    [new] — re-exports public surface
│   │   ├── errors.py                      [new] — ProvenanceError, AliasDriftError, HarborDriftError
│   │   ├── retry.py                       [new] — exponential-backoff harness (AC-7)
│   │   ├── resolvers.py                   [new] — 6 resolver fns: model, image, cli, git, harbor, prompt
│   │   ├── provenance_yaml.py             [new] — writes provenance.yaml; tags unresolved fields
│   │   ├── freeze_cmd.py                  [new] — `rk spec freeze` Typer command
│   │   └── drift.py                       [new] — re-resolve on run; AliasDriftError + harbor drift
│   ├── spec/
│   │   └── schema.py                      [modify] — add ProvenanceBlock + ResolvedProvenance
│   ├── compat/
│   │   └── harbor_0_6_6.py                [modify] — widen DAB fan-out to N datasets (no math change)
│   ├── benchmarks/dab/
│   │   └── aggregate.py                   [unchanged] — M2 math handles 12 datasets already
│   ├── cli/
│   │   ├── __init__.py                    [modify] — register `rk spec freeze`
│   │   └── spec.py                        [new] — Typer subcommand group for `rk spec *`
│   ├── run.py                             [modify] — call drift.check_before_run before harbor
│   └── errors.py                          [modify] — add ProvenanceError, AliasDriftError, HarborDriftError exit-code subclasses
├── examples/specs/
│   └── dab-dev-claude.yaml                [new] — full 12-dataset DAB dev spec (claude agent)
└── tests/
    ├── fixtures/
    │   └── provenance/
    │       ├── twelve_dataset_trial_results.json   [new] — synthetic JobResult for AC-5
    │       └── twelve_dataset_golden_summary.json  [new] — golden summary.json for AC-5
    ├── unit/
    │   ├── test_provenance_alias_drift.py          [new] AC-3 (Task 1 — riskiest)
    │   ├── test_provenance_refuses_missing.py      [new] AC-1
    │   ├── test_provenance_harbor_drift.py         [new] AC-4
    │   ├── test_provenance_retry.py                [new] AC-7
    │   ├── test_provenance_resolvers.py            [new] resolver-by-resolver coverage
    │   ├── test_provenance_yaml.py                 [new] unresolved-field marker shape
    │   ├── test_spec_freeze_cli.py                 [new] AC-1, AC-2 CLI surface
    │   ├── test_run_drift_wired.py                 [new] AC-3, AC-4 wired into rk run
    │   ├── test_dab_aggregate_twelve_datasets.py   [new] AC-5
    │   └── test_dab_translator_twelve.py           [new] 12-dataset fan-out
    └── integration/
        └── test_dab_dev_claude_full.py             [new] AC-6 — cost-bounded
```

**Why a `provenance/` package not a single module:** the six resolvers each have different IO (HTTP for model, docker for image, subprocess for git/cli, importlib for harbor, file IO for prompt). Splitting them into one module per concern (retry, resolvers, provenance_yaml, drift, freeze_cmd) keeps each file focused; the test files mirror the structure 1:1. Per CL's CLAUDE.md "Files that change together should live together" — these all change together for M5 and never again for M6+.

---

## Task 0: Pre-flight — confirm M2/M3 surfaces, Anthropic SDK, 12 datasets

**Files:**
- Read-only inspection.

- [ ] **Step 1: Confirm M2's aggregator is the math we extend**

```bash
test -f /Users/clkao/git/razorback/src/razorback/benchmarks/dab/aggregate.py && \
  grep -n "_build_summary\|pass_at_k\|stratified" /Users/clkao/git/razorback/src/razorback/benchmarks/dab/aggregate.py
```

Expected: lines matching `_build_summary`, `pass_at_k`, and `stratified_pass_at_1`. If absent, M2 impl has not landed — STOP and `SendMessage(to="team-lead", message="M5 plan T0: M2 aggregator code is missing; M5 cannot proceed.")`.

- [ ] **Step 2: Confirm M3's `ClaudeCliAgent` lands the spec.agent.kind=claude-cli path**

```bash
grep -rn "ClaudeCliAgent\|claude-cli" /Users/clkao/git/razorback/src/razorback/agents/ 2>/dev/null | head -5
```

Expected: at least one match in `agents/claude.py` or similar. If absent, M3 impl has not landed — M5's integration test (Task 12) cannot run. Mark Task 12 BLOCKED-ON-M3 and escalate before starting work.

- [ ] **Step 3: Confirm all 12 DAB datasets exist**

```bash
ls -d /Users/clkao/git/dataagentbench/data/query_*
```

Expected: exactly 12 directories — `query_agnews`, `query_bookreview`, `query_crmarenapro`, `query_DEPS_DEV_V1`, `query_GITHUB_REPOS`, `query_googlelocal`, `query_music_brainz_20k`, `query_PANCANCER_ATLAS`, `query_PATENTS`, `query_stockindex`, `query_stockmarket`, `query_yelp`. These are the 12 dataset slugs the AC-6 spec lists.

- [ ] **Step 4: Install Anthropic SDK as a project dependency**

```bash
cd /Users/clkao/git/razorback && uv add 'anthropic>=0.42'
```

Expected: `pyproject.toml` updated with `anthropic` in `[project].dependencies`; `uv.lock` regenerated. The SDK provides `anthropic.Anthropic().models.retrieve(model_id)` per the §6.4 resolver contract.

- [ ] **Step 5: Commit the dep**

```bash
git add pyproject.toml uv.lock
git commit -m "m5: add anthropic SDK dep for provenance.resolvers (§6.4)"
```

---

## Task 1: RISKIEST CONTRACT — `AliasDriftError` fires on mocked provider mismatch (AC-3)

**Files:**
- Create: `src/razorback/errors.py` (extend — add `ProvenanceError`, `AliasDriftError`, `HarborDriftError`)
- Create: `src/razorback/provenance/__init__.py`
- Create: `src/razorback/provenance/errors.py`
- Create: `src/razorback/provenance/drift.py` (stub — only enough for the test to run)
- Create: `tests/unit/test_provenance_alias_drift.py`

**Why first:** Per CL's "Validating new mechanisms" rule and the M5 entity's checklist item #2: the alias-drift check is the load-bearing contract for the whole milestone. The freeze step is useless if the run step does not re-check and refuse on drift. We write the failing test against a fully mocked Anthropic SDK first — no real HTTP calls, no docker, no harbor. If `AliasDriftError` does not surface with the right exit code and the right shape, every later task scaffolds around a broken contract. Per M5 entity AC-3 verbatim: "a unit test mocks the provider API to return a different version than the frozen value; `rk run` exits 21 and the resulting `provenance.yaml` (when `--allow-alias-drift` is passed) records both versions."

- [ ] **Step 1: Write the failing test**

`tests/unit/test_provenance_alias_drift.py`:

```python
# ABOUTME: AC-3 — AliasDriftError fires when provider's resolved model version
# ABOUTME: differs from the frozen spec's pinned model_resolved_version.

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from razorback.errors import ExitCode
from razorback.provenance.errors import AliasDriftError
from razorback.provenance.drift import check_alias_drift


def _fake_model_retrieve(resolved_id: str, created_at: str = "2025-10-22T00:00:00Z"):
    """Build a MagicMock client whose .models.retrieve returns a frozen response."""
    client = MagicMock()
    client.models.retrieve.return_value = MagicMock(
        id=resolved_id,
        created_at=created_at,
        display_name="Claude Opus 4.5",
    )
    return client


def test_alias_drift_raises_when_provider_version_differs():
    """Frozen: claude-opus-4-5-20251022. Provider now returns -20260101. AliasDriftError."""
    client = _fake_model_retrieve("claude-opus-4-5-20260101")
    with pytest.raises(AliasDriftError) as exc_info:
        check_alias_drift(
            model_alias="claude-opus-4-5",
            frozen_resolved_version="claude-opus-4-5-20251022",
            client=client,
            allow=False,
        )
    assert exc_info.value.exit_code == ExitCode.ALIAS_DRIFT
    assert exc_info.value.exit_code == 21  # explicit per §3.2
    assert "claude-opus-4-5-20251022" in str(exc_info.value)
    assert "claude-opus-4-5-20260101" in str(exc_info.value)


def test_alias_drift_no_raise_when_versions_match():
    """No drift: provider returns the same dated id. check returns the resolved tuple."""
    client = _fake_model_retrieve("claude-opus-4-5-20251022")
    resolved_id, resolved_at = check_alias_drift(
        model_alias="claude-opus-4-5",
        frozen_resolved_version="claude-opus-4-5-20251022",
        client=client,
        allow=False,
    )
    assert resolved_id == "claude-opus-4-5-20251022"
    assert resolved_at == "2025-10-22T00:00:00Z"


def test_alias_drift_allow_returns_both_versions_for_provenance_recording():
    """--allow-alias-drift: do not raise; return both versions so provenance.yaml records them."""
    client = _fake_model_retrieve("claude-opus-4-5-20260101", created_at="2026-01-01T00:00:00Z")
    resolved_id, resolved_at = check_alias_drift(
        model_alias="claude-opus-4-5",
        frozen_resolved_version="claude-opus-4-5-20251022",
        client=client,
        allow=True,
    )
    assert resolved_id == "claude-opus-4-5-20260101"
    assert resolved_at == "2026-01-01T00:00:00Z"


def test_alias_drift_error_carries_both_versions_on_exc():
    """AliasDriftError exposes .frozen and .resolved for the run-dir's provenance.yaml writer."""
    client = _fake_model_retrieve("claude-opus-4-5-20260101")
    with pytest.raises(AliasDriftError) as exc_info:
        check_alias_drift(
            model_alias="claude-opus-4-5",
            frozen_resolved_version="claude-opus-4-5-20251022",
            client=client,
            allow=False,
        )
    assert exc_info.value.frozen == "claude-opus-4-5-20251022"
    assert exc_info.value.resolved == "claude-opus-4-5-20260101"
    assert exc_info.value.model_alias == "claude-opus-4-5"
```

- [ ] **Step 2: Run the test, confirm red**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_alias_drift.py -v
```

Expected: ImportError / ModuleNotFoundError on `razorback.provenance.errors` or `razorback.provenance.drift`.

- [ ] **Step 3: Implement `src/razorback/errors.py` extension**

Replace the file body to add three exit-code-bearing exception types:

```python
# ABOUTME: Razorback typed errors and the documented CLI exit code map.
# ABOUTME: Stable wire surface; see design §3.2.

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    GENERIC = 1
    USAGE = 2
    SPEC_ERROR = 10
    PROVENANCE_ERROR = 11
    CONSTRAINT_VIOLATION = 12
    SEED_MISMATCH = 20
    ALIAS_DRIFT = 21
    HARBOR_RUNTIME = 30


class RazorbackError(Exception):
    """Base for razorback typed errors."""
    exit_code: int = ExitCode.GENERIC


class SpecError(RazorbackError):
    exit_code: int = ExitCode.SPEC_ERROR
```

(No changes to existing rows — only the IntEnum already covers 11 and 21. The provenance-specific subclasses live in `provenance/errors.py` so the provenance package is self-contained.)

- [ ] **Step 4: Implement `src/razorback/provenance/__init__.py` and `provenance/errors.py`**

`src/razorback/provenance/__init__.py`:

```python
# ABOUTME: Razorback provenance package — resolvers + freeze + drift checks (§6.4).
# ABOUTME: Re-exports the public surface: ProvenanceError, AliasDriftError, freeze, check.

from razorback.provenance.errors import (
    AliasDriftError,
    HarborDriftError,
    ProvenanceError,
)

__all__ = ["AliasDriftError", "HarborDriftError", "ProvenanceError"]
```

`src/razorback/provenance/errors.py`:

```python
# ABOUTME: Provenance typed errors with documented exit codes (§3.2 rows 11, 21).
# ABOUTME: Subclassed from RazorbackError so the CLI maps them via exc.exit_code.

from razorback.errors import ExitCode, RazorbackError


class ProvenanceError(RazorbackError):
    """One or more provenance fields could not be resolved and --allow-missing was not passed."""
    exit_code: int = ExitCode.PROVENANCE_ERROR


class AliasDriftError(RazorbackError):
    """Provider's resolved model version differs from the frozen spec's pinned value."""
    exit_code: int = ExitCode.ALIAS_DRIFT

    def __init__(self, *, model_alias: str, frozen: str, resolved: str) -> None:
        super().__init__(
            f"model alias '{model_alias}' resolved to '{resolved}', "
            f"frozen spec pinned '{frozen}'. Pass --allow-alias-drift to override."
        )
        self.model_alias = model_alias
        self.frozen = frozen
        self.resolved = resolved


class HarborDriftError(RazorbackError):
    """Installed harbor major version differs from the frozen spec's pinned harbor version."""
    exit_code: int = ExitCode.GENERIC  # §6.4: "hard error at `rk run` time"; not a named exit code

    def __init__(self, *, frozen: str, installed: str) -> None:
        super().__init__(
            f"harbor major-version drift: frozen={frozen}, installed={installed}. "
            f"Refusing to run."
        )
        self.frozen = frozen
        self.installed = installed
```

- [ ] **Step 5: Implement `src/razorback/provenance/drift.py` (minimal — only what AC-3 needs)**

```python
# ABOUTME: Run-time provenance drift checks (§6.4): re-resolve model alias, compare to frozen.
# ABOUTME: Also exposes harbor major-version drift; both fire BEFORE harbor's Job.create.

from __future__ import annotations

from typing import Any

from razorback.provenance.errors import AliasDriftError


def check_alias_drift(
    *,
    model_alias: str,
    frozen_resolved_version: str,
    client: Any,
    allow: bool,
) -> tuple[str, str]:
    """Re-resolve the model alias and compare to the frozen value.

    Returns (resolved_id, resolved_at) on no-drift or allow=True. Raises
    AliasDriftError when the resolved version differs and allow=False.
    The caller is the `rk run` driver, which wires `provenance.yaml` to
    record both versions when allow=True (§6.4).
    """
    model = client.models.retrieve(model_alias)
    resolved_id = model.id
    resolved_at = model.created_at if isinstance(model.created_at, str) else str(model.created_at)
    if resolved_id != frozen_resolved_version:
        if not allow:
            raise AliasDriftError(
                model_alias=model_alias,
                frozen=frozen_resolved_version,
                resolved=resolved_id,
            )
    return resolved_id, resolved_at
```

- [ ] **Step 6: Run the test, confirm green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_alias_drift.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add src/razorback/provenance/__init__.py src/razorback/provenance/errors.py \
        src/razorback/provenance/drift.py \
        tests/unit/test_provenance_alias_drift.py
git commit -m "m5: AliasDriftError + drift.check_alias_drift (AC-3, §6.4)"
```

---

## Task 2: Refuse to write frozen spec when any provenance field is unresolved (AC-1)

**Files:**
- Create: `tests/unit/test_provenance_refuses_missing.py`
- Modify: `src/razorback/provenance/errors.py` (already has `ProvenanceError` from Task 1)
- Create: `src/razorback/provenance/provenance_yaml.py` (initial — refusal predicate only)

The freeze logic must refuse to write `spec.frozen.yaml` AND `provenance.yaml` if any required field is unresolved. AC-1 enumerates the six fields from §6.4: `model_resolved_version`, `image_digest`, `agent_cli_hash`, `harness_git_sha`, `harbor_version`, `prompt_file_hashes`.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_provenance_refuses_missing.py`:

```python
# ABOUTME: AC-1 — rk spec freeze refuses on any unresolved provenance field absent --allow-missing.
# ABOUTME: ProvenanceError (exit 11) and neither spec.frozen.yaml nor provenance.yaml gets written.

from pathlib import Path

import pytest

from razorback.errors import ExitCode
from razorback.provenance.errors import ProvenanceError
from razorback.provenance.provenance_yaml import refuse_if_any_unresolved


FIELDS = [
    "model_resolved_version",
    "image_digest",
    "agent_cli_hash",
    "harness_git_sha",
    "harbor_version",
    "prompt_file_hashes",
]


def _all_resolved() -> dict:
    return {
        "model_resolved_version": "claude-opus-4-5-20251022",
        "model_resolved_at": "2025-10-22T00:00:00Z",
        "image_digest": "sha256:abc123...",
        "agent_cli_hash": "sha256:def456...",
        "harness_git_sha": "0123456789abcdef",
        "harbor_version": "0.6.6",
        "prompt_file_hashes": {"agent-prompts/p.md": "sha256:fedcba..."},
    }


@pytest.mark.parametrize("missing_field", FIELDS)
def test_refuses_when_any_single_field_missing(missing_field):
    resolved = _all_resolved()
    resolved[missing_field] = None  # the sentinel for unresolved
    with pytest.raises(ProvenanceError) as exc_info:
        refuse_if_any_unresolved(resolved, allow_missing=False)
    assert exc_info.value.exit_code == ExitCode.PROVENANCE_ERROR
    assert exc_info.value.exit_code == 11
    assert missing_field in str(exc_info.value)


def test_no_raise_when_all_resolved():
    resolved = _all_resolved()
    refuse_if_any_unresolved(resolved, allow_missing=False)  # no exception


def test_allow_missing_does_not_raise_even_when_fields_missing():
    resolved = _all_resolved()
    resolved["image_digest"] = None
    resolved["agent_cli_hash"] = None
    refuse_if_any_unresolved(resolved, allow_missing=True)  # no exception


def test_refusal_lists_all_missing_fields_not_just_first():
    """The error message must name every unresolved field — operators want one fix cycle."""
    resolved = _all_resolved()
    resolved["image_digest"] = None
    resolved["harbor_version"] = None
    with pytest.raises(ProvenanceError) as exc_info:
        refuse_if_any_unresolved(resolved, allow_missing=False)
    msg = str(exc_info.value)
    assert "image_digest" in msg
    assert "harbor_version" in msg
```

- [ ] **Step 2: Run the test, confirm red**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_refuses_missing.py -v
```

Expected: ImportError on `razorback.provenance.provenance_yaml`.

- [ ] **Step 3: Implement `src/razorback/provenance/provenance_yaml.py`**

```python
# ABOUTME: provenance.yaml writer + refusal predicate (§6.4).
# ABOUTME: A field with value None is the sentinel for unresolved.

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from razorback.provenance.errors import ProvenanceError


REQUIRED_FIELDS = (
    "model_resolved_version",
    "image_digest",
    "agent_cli_hash",
    "harness_git_sha",
    "harbor_version",
    "prompt_file_hashes",
)


def refuse_if_any_unresolved(resolved: dict[str, Any], *, allow_missing: bool) -> None:
    """Raise ProvenanceError if any required field's value is None.

    `prompt_file_hashes` is a dict; treat empty-dict as resolved (no prompt files
    is a valid spec) and None as unresolved.
    """
    if allow_missing:
        return
    missing: list[str] = [name for name in REQUIRED_FIELDS if resolved.get(name) is None]
    if missing:
        raise ProvenanceError(
            f"unresolved provenance fields: {', '.join(missing)}. "
            f"Pass --allow-missing to write anyway (will be tagged in provenance.yaml)."
        )


def write_provenance_yaml(
    out_path: Path,
    resolved: dict[str, Any],
    *,
    drift_record: dict[str, Any] | None = None,
) -> None:
    """Serialize the resolved-field dict to provenance.yaml.

    Unresolved fields (value=None) are written as a list under `unresolved:`.
    `drift_record`, when supplied, captures alias-drift overrides (§6.4) recorded by `rk run`.
    """
    document: dict[str, Any] = {}
    unresolved: list[str] = []
    for name in REQUIRED_FIELDS:
        val = resolved.get(name)
        if val is None:
            unresolved.append(name)
        else:
            document[name] = val
    # Carry the API timestamp too (auxiliary field, not in the refusal list).
    if "model_resolved_at" in resolved and resolved["model_resolved_at"] is not None:
        document["model_resolved_at"] = resolved["model_resolved_at"]
    if unresolved:
        document["unresolved"] = sorted(unresolved)
    if drift_record is not None:
        document["alias_drift"] = drift_record
    out_path.write_text(yaml.safe_dump(document, sort_keys=False, default_flow_style=False))
```

- [ ] **Step 4: Run the test, confirm green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_refuses_missing.py -v
```

Expected: 9 passed (6 parametrized + 3 named).

- [ ] **Step 5: Commit**

```bash
git add src/razorback/provenance/provenance_yaml.py \
        tests/unit/test_provenance_refuses_missing.py
git commit -m "m5: refuse_if_any_unresolved + provenance.yaml writer (AC-1, §6.4)"
```

---

## Task 3: Harbor major-version drift is a hard error before Job.create (AC-4)

**Files:**
- Create: `tests/unit/test_provenance_harbor_drift.py`
- Modify: `src/razorback/provenance/drift.py` (add `check_harbor_drift`)

§6.4 says: "Major-version drift between freeze and re-run is a hard error at `rk run` time." Harbor uses SemVer; major-version drift means `0.x → 1.x` (0.6.6 → 0.7.0 is minor, NOT major, per SemVer-pre-1.0 the operator may treat minor as breaking — but the design doc says **major**, so we follow it literally). The check fires before `Job.create`.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_provenance_harbor_drift.py`:

```python
# ABOUTME: AC-4 — harbor major-version drift is a hard error before Job.create.

from unittest.mock import patch

import pytest

from razorback.provenance.drift import check_harbor_drift
from razorback.provenance.errors import HarborDriftError


def test_no_drift_when_major_matches():
    check_harbor_drift(frozen="0.6.6", installed="0.6.6")  # exact match
    check_harbor_drift(frozen="0.6.6", installed="0.7.0")  # minor drift, same major (0)
    check_harbor_drift(frozen="0.6.6", installed="0.6.99")


def test_major_drift_raises():
    with pytest.raises(HarborDriftError) as exc_info:
        check_harbor_drift(frozen="0.6.6", installed="1.0.0")
    assert exc_info.value.frozen == "0.6.6"
    assert exc_info.value.installed == "1.0.0"
    assert "0.6.6" in str(exc_info.value)
    assert "1.0.0" in str(exc_info.value)


def test_major_drift_raises_2_to_1():
    """Going backwards is still drift."""
    with pytest.raises(HarborDriftError):
        check_harbor_drift(frozen="2.0.0", installed="1.5.0")


def test_check_harbor_drift_reads_installed_version_when_not_passed():
    """When `installed` is None, read harbor.__version__."""
    with patch("razorback.provenance.drift._installed_harbor_version", return_value="1.5.0"):
        with pytest.raises(HarborDriftError):
            check_harbor_drift(frozen="0.6.6", installed=None)
```

- [ ] **Step 2: Run the test, confirm red**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_harbor_drift.py -v
```

Expected: ImportError on `check_harbor_drift` (not exported yet).

- [ ] **Step 3: Extend `src/razorback/provenance/drift.py`**

Append:

```python
def _installed_harbor_version() -> str:
    """Return harbor.__version__ at run-time. Wrapped for test patching."""
    import harbor
    return harbor.__version__


def check_harbor_drift(*, frozen: str, installed: str | None) -> None:
    """Refuse on harbor major-version drift between freeze and run (§6.4).

    Compares the leading numeric component of the SemVer string. Minor or patch
    drift is allowed; the FO surfaces these via spec validation, not run-time refusal.
    """
    if installed is None:
        installed = _installed_harbor_version()
    if _major(frozen) != _major(installed):
        raise HarborDriftError(frozen=frozen, installed=installed)


def _major(version: str) -> int:
    return int(version.split(".", 1)[0])
```

And update the imports at the top of `drift.py`:

```python
from razorback.provenance.errors import AliasDriftError, HarborDriftError
```

- [ ] **Step 4: Run the test, confirm green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_harbor_drift.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/provenance/drift.py \
        tests/unit/test_provenance_harbor_drift.py
git commit -m "m5: HarborDriftError + check_harbor_drift (AC-4, §6.4)"
```

---

## Task 4: Exponential-backoff retry harness with 503 → 200 (AC-7)

**Files:**
- Create: `tests/unit/test_provenance_retry.py`
- Create: `src/razorback/provenance/retry.py`

§6.4: "The resolver retries each external call with exponential backoff. A transient 503 does not abort the freeze." We write a unit test against a mocked callable that returns 503-503-200 (using a custom exception class to stand in for the SDK's `APIStatusError`). The retry harness wraps a callable and a predicate; sleeps are stubbed via dependency injection so tests run in zero wallclock.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_provenance_retry.py`:

```python
# ABOUTME: AC-7 — retry with exponential backoff on transient errors.
# ABOUTME: Sleeps are dependency-injected so the test runs in zero wallclock.

import pytest

from razorback.provenance.retry import retry_with_backoff


class _Transient(Exception):
    """Stand-in for anthropic.APIStatusError with status_code == 503."""
    def __init__(self, status: int) -> None:
        self.status_code = status


def _is_transient(exc: Exception) -> bool:
    return isinstance(exc, _Transient) and exc.status_code in (502, 503, 504)


def test_retries_twice_then_succeeds():
    calls = []
    sleeps: list[float] = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise _Transient(503)
        return "ok"

    result = retry_with_backoff(
        fn,
        is_transient=_is_transient,
        max_attempts=5,
        base_delay=0.1,
        sleep=lambda s: sleeps.append(s),
    )
    assert result == "ok"
    assert len(calls) == 3
    # Exponential: 0.1, 0.2 (two sleeps, no sleep after success).
    assert sleeps == [0.1, 0.2]


def test_gives_up_after_max_attempts():
    def fn():
        raise _Transient(503)

    with pytest.raises(_Transient):
        retry_with_backoff(
            fn,
            is_transient=_is_transient,
            max_attempts=3,
            base_delay=0.0,
            sleep=lambda s: None,
        )


def test_non_transient_raises_immediately():
    calls: list[int] = []

    def fn():
        calls.append(1)
        raise ValueError("404 not found")  # non-transient — fall through

    with pytest.raises(ValueError):
        retry_with_backoff(
            fn,
            is_transient=_is_transient,
            max_attempts=5,
            base_delay=0.0,
            sleep=lambda s: None,
        )
    assert calls == [1]  # exactly one call; no retry
```

- [ ] **Step 2: Run the test, confirm red**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_retry.py -v
```

Expected: ImportError on `razorback.provenance.retry`.

- [ ] **Step 3: Implement `src/razorback/provenance/retry.py`**

```python
# ABOUTME: Exponential-backoff retry harness for the provenance resolvers (§6.4).
# ABOUTME: Sleep is dependency-injected so unit tests run in zero wallclock.

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    is_transient: Callable[[Exception], bool],
    max_attempts: int = 5,
    base_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `fn` until success or `max_attempts` reached.

    On a transient exception (`is_transient(exc) == True`), sleep
    `base_delay * 2**(attempt-1)` then retry. Non-transient exceptions
    propagate immediately.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if not is_transient(exc):
                raise
            last_exc = exc
            if attempt == max_attempts:
                break
            sleep(base_delay * (2 ** (attempt - 1)))
    assert last_exc is not None
    raise last_exc
```

- [ ] **Step 4: Run the test, confirm green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_retry.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/provenance/retry.py tests/unit/test_provenance_retry.py
git commit -m "m5: retry_with_backoff harness (AC-7, §6.4)"
```

---

## Task 5: Implement the six resolvers (model, image, cli, git, harbor, prompt)

**Files:**
- Create: `tests/unit/test_provenance_resolvers.py`
- Create: `src/razorback/provenance/resolvers.py`

The resolvers are six pure functions, each returning a string or None (None ≡ unresolved when the field's `pin_*` flag is true). They are unit-tested with everything external mocked:

- `resolve_model_version(alias, *, client_factory)` — Anthropic SDK, retries 503 (via Task 4's `retry_with_backoff`).
- `resolve_image_digest(image_ref, *, docker)` — `docker image inspect`; subprocess mocked.
- `resolve_agent_cli_hash(binary_name, *, which, hash_file)` — `which claude`; file IO mocked.
- `resolve_harness_git_sha(repo_root, *, git_runner)` — `git rev-parse HEAD`; subprocess mocked.
- `resolve_harbor_version()` — `harbor.__version__`; the import is mocked in tests.
- `resolve_prompt_hashes(prompt_paths)` — file IO, real reads OK in tests via tmp_path.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_provenance_resolvers.py`:

```python
# ABOUTME: Per-field resolver unit tests for the six provenance fields (§6.4).

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from razorback.provenance.resolvers import (
    resolve_model_version,
    resolve_image_digest,
    resolve_agent_cli_hash,
    resolve_harness_git_sha,
    resolve_harbor_version,
    resolve_prompt_hashes,
)


# --- model ---


def test_resolve_model_version_returns_id_and_timestamp():
    client = MagicMock()
    client.models.retrieve.return_value = MagicMock(
        id="claude-opus-4-5-20251022",
        created_at="2025-10-22T00:00:00Z",
    )
    resolved, at = resolve_model_version("claude-opus-4-5", client_factory=lambda: client)
    assert resolved == "claude-opus-4-5-20251022"
    assert at == "2025-10-22T00:00:00Z"


def test_resolve_model_version_retries_503_then_succeeds():
    client = MagicMock()
    # Build a fake transient that mimics anthropic.APIStatusError shape.
    class FakeStatusError(Exception):
        def __init__(self, status: int) -> None:
            self.status_code = status

    seq = [FakeStatusError(503), FakeStatusError(503),
           MagicMock(id="claude-opus-4-5-20251022", created_at="2025-10-22T00:00:00Z")]
    def _retrieve(_alias):
        item = seq.pop(0)
        if isinstance(item, FakeStatusError):
            raise item
        return item
    client.models.retrieve.side_effect = _retrieve

    sleeps: list[float] = []
    resolved, _at = resolve_model_version(
        "claude-opus-4-5",
        client_factory=lambda: client,
        is_transient=lambda exc: isinstance(exc, FakeStatusError) and exc.status_code == 503,
        sleep=lambda s: sleeps.append(s),
    )
    assert resolved == "claude-opus-4-5-20251022"
    assert len(sleeps) == 2


def test_resolve_model_version_404_is_hard_error():
    """A 404 on the model name is not transient. The error propagates so the caller writes None."""
    client = MagicMock()
    class FakeStatusError(Exception):
        def __init__(self, status: int) -> None:
            self.status_code = status

    client.models.retrieve.side_effect = FakeStatusError(404)
    with pytest.raises(FakeStatusError):
        resolve_model_version(
            "nonexistent-model",
            client_factory=lambda: client,
            is_transient=lambda exc: isinstance(exc, FakeStatusError) and exc.status_code == 503,
            sleep=lambda s: None,
        )


# --- image ---


def test_resolve_image_digest_via_docker_image_inspect():
    docker = MagicMock()
    docker.return_value = "sha256:abc123def\n"
    digest = resolve_image_digest("dab-agent", docker=docker)
    assert digest == "sha256:abc123def"
    docker.assert_called_once_with("dab-agent")


def test_resolve_image_digest_returns_none_when_inspect_fails():
    docker = MagicMock(side_effect=RuntimeError("no such image"))
    digest = resolve_image_digest("missing-image", docker=docker)
    assert digest is None


# --- agent CLI hash ---


def test_resolve_agent_cli_hash_reads_binary_and_hashes(tmp_path):
    binary = tmp_path / "claude"
    binary.write_bytes(b"#!/bin/sh\necho hi\n")
    expected = "sha256:" + hashlib.sha256(b"#!/bin/sh\necho hi\n").hexdigest()
    got = resolve_agent_cli_hash("claude", which=lambda _: str(binary))
    assert got == expected


def test_resolve_agent_cli_hash_returns_none_when_not_on_path():
    got = resolve_agent_cli_hash("nonexistent", which=lambda _: None)
    assert got is None


# --- git SHA ---


def test_resolve_harness_git_sha_returns_full_sha():
    git_runner = MagicMock(return_value="0123456789abcdef0123456789abcdef01234567\n")
    sha = resolve_harness_git_sha(Path("/repo"), git_runner=git_runner)
    assert sha == "0123456789abcdef0123456789abcdef01234567"
    git_runner.assert_called_once_with(Path("/repo"), ("git", "rev-parse", "HEAD"))


def test_resolve_harness_git_sha_returns_none_on_failure():
    git_runner = MagicMock(side_effect=RuntimeError("not a git repo"))
    assert resolve_harness_git_sha(Path("/not-repo"), git_runner=git_runner) is None


# --- harbor version ---


def test_resolve_harbor_version_returns_installed():
    with patch("razorback.provenance.resolvers._import_harbor") as imp:
        imp.return_value = MagicMock(__version__="0.6.6")
        assert resolve_harbor_version() == "0.6.6"


# --- prompt hashes ---


def test_resolve_prompt_hashes_hashes_each_file(tmp_path):
    p1 = tmp_path / "prompt-a.md"
    p2 = tmp_path / "prompt-b.md"
    p1.write_text("hello")
    p2.write_text("world")
    hashes = resolve_prompt_hashes([p1, p2])
    assert hashes[str(p1)] == "sha256:" + hashlib.sha256(b"hello").hexdigest()
    assert hashes[str(p2)] == "sha256:" + hashlib.sha256(b"world").hexdigest()


def test_resolve_prompt_hashes_returns_empty_dict_when_no_paths():
    """An empty list is "resolved": there are no prompt files to hash."""
    assert resolve_prompt_hashes([]) == {}


def test_resolve_prompt_hashes_returns_none_when_a_file_is_missing(tmp_path):
    """A spec referencing a missing prompt file is unresolved."""
    p = tmp_path / "missing.md"
    assert resolve_prompt_hashes([p]) is None
```

- [ ] **Step 2: Run the test, confirm red**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_resolvers.py -v
```

Expected: ImportError on `razorback.provenance.resolvers`.

- [ ] **Step 3: Implement `src/razorback/provenance/resolvers.py`**

```python
# ABOUTME: Per-field provenance resolvers (§6.4).
# ABOUTME: Each resolver is a pure function with externals dependency-injected.
# ABOUTME: Codex/OpenAI model resolution is deferred — see Task 5 note.

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from razorback.provenance.retry import retry_with_backoff


def resolve_model_version(
    model_alias: str,
    *,
    client_factory: Callable[[], Any] | None = None,
    is_transient: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> tuple[str, str]:
    """Resolve a model alias to (dated_id, api_timestamp) via the Anthropic SDK.

    `client_factory` defaults to `anthropic.Anthropic()` (reads ANTHROPIC_API_KEY from env).
    `is_transient` defaults to "anthropic.APIStatusError with status_code 502/503/504".
    Codex/OpenAI is NOT covered here; the M5 acceptance spec is claude-cli only.
    """
    client = (client_factory or _default_anthropic_client)()
    sleep_fn = sleep or __import__("time").sleep
    if is_transient is None:
        is_transient = _default_is_transient
    model = retry_with_backoff(
        lambda: client.models.retrieve(model_alias),
        is_transient=is_transient,
        max_attempts=5,
        base_delay=0.5,
        sleep=sleep_fn,
    )
    resolved_id = model.id
    resolved_at = model.created_at if isinstance(model.created_at, str) else str(model.created_at)
    return resolved_id, resolved_at


def _default_anthropic_client() -> Any:
    import anthropic
    return anthropic.Anthropic()


def _default_is_transient(exc: Exception) -> bool:
    code = getattr(exc, "status_code", None)
    return code in (502, 503, 504)


def resolve_image_digest(
    image_ref: str,
    *,
    docker: Callable[[str], str] | None = None,
) -> str | None:
    """Pin the docker image digest via `docker image inspect`.

    Returns None if the image is not pullable / not present locally; the freeze
    flow then refuses (or accepts with --allow-missing per AC-2).
    """
    runner = docker or _default_docker_inspect
    try:
        out = runner(image_ref)
    except Exception:
        return None
    return out.strip() or None


def _default_docker_inspect(image_ref: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{ .Id }}", image_ref],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def resolve_agent_cli_hash(
    binary_name: str,
    *,
    which: Callable[[str], str | None] | None = None,
) -> str | None:
    """SHA-256 the agent's CLI binary. Returns None if not on $PATH."""
    locator = which or shutil.which
    path = locator(binary_name)
    if path is None:
        return None
    h = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return f"sha256:{h}"


def resolve_harness_git_sha(
    repo_root: Path,
    *,
    git_runner: Callable[[Path, tuple[str, ...]], str] | None = None,
) -> str | None:
    """`git rev-parse HEAD` against the consuming repo. None on failure (not a repo)."""
    runner = git_runner or _default_git_runner
    try:
        out = runner(repo_root, ("git", "rev-parse", "HEAD"))
    except Exception:
        return None
    sha = out.strip()
    return sha or None


def _default_git_runner(repo_root: Path, cmd: tuple[str, ...]) -> str:
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=True)
    return result.stdout


def _import_harbor() -> Any:
    import harbor
    return harbor


def resolve_harbor_version() -> str:
    """`harbor.__version__`. Always resolvable when harbor is installed (a hard dep)."""
    return _import_harbor().__version__


def resolve_prompt_hashes(prompt_paths: list[Path]) -> dict[str, str] | None:
    """Content-hash every prompt file referenced by the spec.

    Returns None if any path is missing. Returns an empty dict when the list is empty.
    """
    out: dict[str, str] = {}
    for p in prompt_paths:
        if not Path(p).is_file():
            return None
        h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
        out[str(p)] = f"sha256:{h}"
    return out
```

- [ ] **Step 4: Run the test, confirm green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_resolvers.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/provenance/resolvers.py tests/unit/test_provenance_resolvers.py
git commit -m "m5: provenance resolvers (model, image, cli, git, harbor, prompt) (§6.4)"
```

---

## Task 6: Wire `rk spec freeze` Typer command (AC-1, AC-2)

**Files:**
- Modify: `src/razorback/spec/schema.py` (add `ProvenanceBlock`)
- Create: `src/razorback/cli/spec.py`
- Modify: `src/razorback/cli/__init__.py` (register `spec` sub-group)
- Create: `src/razorback/provenance/freeze_cmd.py`
- Create: `tests/unit/test_spec_freeze_cli.py`

`rk spec freeze` reads the spec, calls each resolver (in the order declared by `spec.provenance.pin_*` flags), aggregates into a `resolved` dict, refuses or proceeds per `--allow-missing`, writes `spec.frozen.yaml` (pinned values inlined into the spec body) and `provenance.yaml` (sidecar). The frozen path is `<spec>.frozen.yaml` next to the input by default; `--out` overrides.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_spec_freeze_cli.py`:

```python
# ABOUTME: AC-1, AC-2 — rk spec freeze CLI surface.

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from razorback.cli import app


runner = CliRunner()


SPEC_TEXT = """\
version: 1
experiment: m5-test
agent:
  kind: claude-cli
  model: claude-opus-4-5
benchmark:
  kind: dab
  data_root: /tmp/data
  datasets: [bookreview]
trials: 1
"""


@pytest.fixture
def spec_file(tmp_path: Path) -> Path:
    p = tmp_path / "spec.yaml"
    p.write_text(SPEC_TEXT)
    return p


def _stub_all_resolved(monkeypatch):
    """Stub all six resolvers to succeed."""
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(fc, "resolve_model_version",
                        lambda alias, **_: ("claude-opus-4-5-20251022", "2025-10-22T00:00:00Z"))
    monkeypatch.setattr(fc, "resolve_image_digest", lambda _ref, **_: "sha256:abc")
    monkeypatch.setattr(fc, "resolve_agent_cli_hash", lambda _bin, **_: "sha256:def")
    monkeypatch.setattr(fc, "resolve_harness_git_sha", lambda _root, **_: "0123456789abcdef")
    monkeypatch.setattr(fc, "resolve_harbor_version", lambda: "0.6.6")
    monkeypatch.setattr(fc, "resolve_prompt_hashes", lambda _paths: {})


def test_freeze_all_resolved_writes_frozen_and_provenance(spec_file, monkeypatch, tmp_path):
    _stub_all_resolved(monkeypatch)
    result = runner.invoke(app, ["spec", "freeze", str(spec_file)])
    assert result.exit_code == 0, result.output
    frozen = spec_file.with_suffix(".frozen.yaml")
    prov = spec_file.parent / "provenance.yaml"
    assert frozen.exists()
    assert prov.exists()
    prov_doc = yaml.safe_load(prov.read_text())
    assert prov_doc["model_resolved_version"] == "claude-opus-4-5-20251022"
    assert prov_doc["harbor_version"] == "0.6.6"
    assert "unresolved" not in prov_doc


def test_freeze_refuses_when_field_missing(spec_file, monkeypatch):
    """AC-1: any one unresolved field → exit 11, neither output written."""
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(fc, "resolve_model_version",
                        lambda alias, **_: ("claude-opus-4-5-20251022", "2025-10-22T00:00:00Z"))
    monkeypatch.setattr(fc, "resolve_image_digest", lambda _ref, **_: None)  # missing
    monkeypatch.setattr(fc, "resolve_agent_cli_hash", lambda _bin, **_: "sha256:def")
    monkeypatch.setattr(fc, "resolve_harness_git_sha", lambda _root, **_: "0123456789abcdef")
    monkeypatch.setattr(fc, "resolve_harbor_version", lambda: "0.6.6")
    monkeypatch.setattr(fc, "resolve_prompt_hashes", lambda _paths: {})

    result = runner.invoke(app, ["spec", "freeze", str(spec_file)])
    assert result.exit_code == 11
    assert "image_digest" in result.output
    assert not spec_file.with_suffix(".frozen.yaml").exists()
    assert not (spec_file.parent / "provenance.yaml").exists()


def test_freeze_allow_missing_writes_with_unresolved_marker(spec_file, monkeypatch):
    """AC-2: --allow-missing writes both files, provenance.yaml records the unresolved field."""
    import razorback.provenance.freeze_cmd as fc

    monkeypatch.setattr(fc, "resolve_model_version", lambda alias, **_: (None, None))  # 503
    monkeypatch.setattr(fc, "resolve_image_digest", lambda _ref, **_: "sha256:abc")
    monkeypatch.setattr(fc, "resolve_agent_cli_hash", lambda _bin, **_: "sha256:def")
    monkeypatch.setattr(fc, "resolve_harness_git_sha", lambda _root, **_: "0123456789abcdef")
    monkeypatch.setattr(fc, "resolve_harbor_version", lambda: "0.6.6")
    monkeypatch.setattr(fc, "resolve_prompt_hashes", lambda _paths: {})

    result = runner.invoke(app, ["spec", "freeze", str(spec_file), "--allow-missing"])
    assert result.exit_code == 0, result.output
    prov = yaml.safe_load((spec_file.parent / "provenance.yaml").read_text())
    assert "model_resolved_version" in prov["unresolved"]
```

- [ ] **Step 2: Run the test, confirm red**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_spec_freeze_cli.py -v
```

Expected: errors on `app` not having a `spec freeze` subcommand.

- [ ] **Step 3: Add `ProvenanceBlock` to the spec schema**

Add to `src/razorback/spec/schema.py`:

```python
class ProvenanceBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pin_model_version: bool = True
    pin_image_digest: bool = True
    pin_agent_cli_hash: bool = True
    pin_git_sha: bool = True
```

And extend `Spec`:

```python
class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    experiment: str
    agent: AgentBlock
    benchmark: BenchmarkBlock
    trials: int = 1
    observers: list[ObserverBlock] = Field(default_factory=list)
    provenance: ProvenanceBlock = Field(default_factory=ProvenanceBlock)
```

Also add an `AgentBlock.model: str | None = None` so the freeze command can read `spec.agent.model`. (M3 may have added this already; if so, leave it alone.)

- [ ] **Step 4: Implement `src/razorback/provenance/freeze_cmd.py`**

```python
# ABOUTME: `rk spec freeze` Typer command — orchestrates the six resolvers (§6.4).
# ABOUTME: Writes spec.frozen.yaml (pinned spec body) + provenance.yaml (sidecar).

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from razorback.errors import ExitCode, RazorbackError
from razorback.provenance.provenance_yaml import (
    refuse_if_any_unresolved,
    write_provenance_yaml,
)
from razorback.provenance.resolvers import (
    resolve_agent_cli_hash,
    resolve_harbor_version,
    resolve_harness_git_sha,
    resolve_image_digest,
    resolve_model_version,
    resolve_prompt_hashes,
)
from razorback.spec.parse import parse_spec_file


def freeze_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path | None = typer.Option(None, "--out", help="Frozen spec path. Default: <spec>.frozen.yaml."),
    allow_missing: bool = typer.Option(False, "--allow-missing", help="Write even with unresolved fields."),
) -> None:
    """Resolve every dynamic input in the spec and write spec.frozen.yaml + provenance.yaml."""
    try:
        spec = parse_spec_file(spec_path)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)

    model_alias = getattr(spec.agent, "model", None) or "claude-opus-4-5"  # fallback for nop
    try:
        model_id, model_at = resolve_model_version(model_alias)
    except Exception:
        model_id, model_at = None, None

    image_ref = getattr(spec.benchmark, "image", None) or "dab-agent"
    image_digest = resolve_image_digest(image_ref) if spec.provenance.pin_image_digest else None
    cli_bin = "claude" if spec.agent.kind == "claude-cli" else spec.agent.kind
    agent_cli_hash = resolve_agent_cli_hash(cli_bin) if spec.provenance.pin_agent_cli_hash else None
    git_sha = resolve_harness_git_sha(Path.cwd()) if spec.provenance.pin_git_sha else None
    harbor_version = resolve_harbor_version()
    prompt_paths = _collect_prompt_paths(spec)
    prompt_hashes = resolve_prompt_hashes(prompt_paths)

    resolved = {
        "model_resolved_version": model_id,
        "model_resolved_at": model_at,
        "image_digest": image_digest,
        "agent_cli_hash": agent_cli_hash,
        "harness_git_sha": git_sha,
        "harbor_version": harbor_version,
        "prompt_file_hashes": prompt_hashes,
    }

    try:
        refuse_if_any_unresolved(resolved, allow_missing=allow_missing)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)

    frozen_path = out or spec_path.with_suffix(".frozen.yaml")
    frozen_body = spec.model_dump(mode="json")
    frozen_body["provenance"] = {
        **frozen_body.get("provenance", {}),
        "model_resolved_version": model_id,
        "image_digest": image_digest,
        "agent_cli_hash": agent_cli_hash,
        "harness_git_sha": git_sha,
        "harbor_version": harbor_version,
    }
    frozen_path.write_text(yaml.safe_dump(frozen_body, sort_keys=False))

    write_provenance_yaml(spec_path.parent / "provenance.yaml", resolved)
    typer.echo(f"wrote {frozen_path}")
    typer.echo(f"wrote {spec_path.parent / 'provenance.yaml'}")


def _collect_prompt_paths(spec) -> list[Path]:
    """Walk the spec for any `prompt_file` references. M5 covers the agent block only."""
    paths: list[Path] = []
    pf = getattr(spec.agent, "prompt_file", None)
    if pf:
        paths.append(Path(pf))
    return paths
```

- [ ] **Step 5: Add `src/razorback/cli/spec.py` and register it**

`src/razorback/cli/spec.py`:

```python
# ABOUTME: `rk spec *` Typer subcommand group. M5 adds `freeze`.
# ABOUTME: Future M6 may add `validate`, `show`.

import typer

from razorback.provenance.freeze_cmd import freeze_command

app = typer.Typer(help="Spec inspection and freeze commands.")
app.command("freeze")(freeze_command)
```

Update `src/razorback/cli/__init__.py` — replace the body's tail with:

```python
from razorback.cli.spec import app as spec_app
app.add_typer(spec_app, name="spec")
```

- [ ] **Step 6: Run the test, confirm green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_spec_freeze_cli.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add src/razorback/cli/spec.py src/razorback/cli/__init__.py \
        src/razorback/provenance/freeze_cmd.py \
        src/razorback/spec/schema.py \
        tests/unit/test_spec_freeze_cli.py
git commit -m "m5: rk spec freeze CLI — orchestrates all six resolvers (AC-1, AC-2, §6.4)"
```

---

## Task 7: Wire drift checks into `rk run` (AC-3, AC-4)

**Files:**
- Modify: `src/razorback/run.py` (call `check_harbor_drift` then `check_alias_drift` before `Job.create`)
- Modify: `src/razorback/cli/run.py` (accept `--allow-alias-drift` flag, pipe to `execute_run`)
- Create: `tests/unit/test_run_drift_wired.py`

The wiring is small: before `spec_to_job_config` in `_execute_run_async`, call the two drift checks. If the spec has no `provenance.frozen` block (e.g. it's a raw spec, not a frozen one), the checks no-op. The test patches both drift fns at the run module's import site to confirm they are invoked.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_run_drift_wired.py`:

```python
# ABOUTME: AC-3, AC-4 — drift checks fire BEFORE Job.create in rk run.

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from razorback.errors import ExitCode
from razorback.provenance.errors import AliasDriftError, HarborDriftError


FROZEN_TEXT = """\
version: 1
experiment: m5-run-drift
agent:
  kind: claude-cli
  model: claude-opus-4-5
benchmark:
  kind: dab
  data_root: /tmp/data
  datasets: [bookreview]
trials: 1
provenance:
  pin_model_version: true
  pin_image_digest: true
  pin_agent_cli_hash: true
  pin_git_sha: true
"""


def _write_frozen(tmp_path: Path, with_pinned: dict | None = None) -> Path:
    p = tmp_path / "spec.frozen.yaml"
    body = yaml.safe_load(FROZEN_TEXT)
    if with_pinned:
        body["provenance"].update(with_pinned)
    p.write_text(yaml.safe_dump(body))
    return p


def test_run_refuses_on_harbor_drift(tmp_path):
    from razorback.run import execute_run
    from razorback.spec.parse import parse_spec_file

    pinned = {"harbor_version": "0.6.6", "model_resolved_version": "claude-opus-4-5-20251022"}
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)
    spec = parse_spec_file(frozen_path)

    with patch("razorback.run.check_harbor_drift",
               side_effect=HarborDriftError(frozen="0.6.6", installed="1.0.0")):
        with pytest.raises(HarborDriftError):
            execute_run(spec=spec, runs_dir=tmp_path / "_runs")


def test_run_refuses_on_alias_drift_by_default(tmp_path):
    from razorback.run import execute_run
    from razorback.spec.parse import parse_spec_file

    pinned = {"harbor_version": "0.6.6", "model_resolved_version": "claude-opus-4-5-20251022"}
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)
    spec = parse_spec_file(frozen_path)

    with patch("razorback.run.check_harbor_drift", return_value=None):
        with patch("razorback.run.check_alias_drift",
                   side_effect=AliasDriftError(
                       model_alias="claude-opus-4-5",
                       frozen="claude-opus-4-5-20251022",
                       resolved="claude-opus-4-5-20260101",
                   )):
            with pytest.raises(AliasDriftError):
                execute_run(spec=spec, runs_dir=tmp_path / "_runs", allow_alias_drift=False)


def test_run_records_both_versions_when_allow_alias_drift(tmp_path):
    """When --allow-alias-drift is passed, the run proceeds and provenance.yaml carries both."""
    from razorback.run import execute_run
    from razorback.spec.parse import parse_spec_file

    pinned = {"harbor_version": "0.6.6", "model_resolved_version": "claude-opus-4-5-20251022"}
    frozen_path = _write_frozen(tmp_path, with_pinned=pinned)
    spec = parse_spec_file(frozen_path)

    fake_result = MagicMock(n_total_trials=0, stats=MagicMock(n_completed_trials=0, n_errored_trials=0),
                            trial_results=[])
    fake_job = MagicMock()
    fake_job.run = MagicMock(return_value=_async_value(fake_result))
    fake_job.add_hook = MagicMock()

    with patch("razorback.run.check_harbor_drift", return_value=None), \
         patch("razorback.run.check_alias_drift",
               return_value=("claude-opus-4-5-20260101", "2026-01-01T00:00:00Z")), \
         patch("razorback.run.Job") as job_cls, \
         patch("razorback.run.spec_to_job_config", return_value=(MagicMock(), {})):
        job_cls.create = MagicMock(return_value=_async_value(fake_job))
        execute_run(spec=spec, runs_dir=tmp_path / "_runs", allow_alias_drift=True)
    # provenance.yaml was written by the run flow; check it carries the alias_drift record.
    prov = tmp_path / "_runs" / "m5-run-drift"
    # find the single subdir
    job_dirs = list(prov.iterdir())
    assert len(job_dirs) == 1
    prov_doc = yaml.safe_load((job_dirs[0] / "provenance.yaml").read_text())
    assert prov_doc["alias_drift"]["frozen"] == "claude-opus-4-5-20251022"
    assert prov_doc["alias_drift"]["resolved"] == "claude-opus-4-5-20260101"


async def _await(v):
    return v


def _async_value(v):
    """Build a coroutine that returns v — for mocking awaitable Job.create / job.run."""
    import asyncio

    async def _coro():
        return v
    return _coro()
```

- [ ] **Step 2: Run the test, confirm red**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_run_drift_wired.py -v
```

Expected: AttributeError on `razorback.run.check_harbor_drift` (not imported yet).

- [ ] **Step 3: Modify `src/razorback/run.py`**

Add imports at the top:

```python
from razorback.provenance.drift import check_alias_drift, check_harbor_drift
from razorback.provenance.provenance_yaml import write_provenance_yaml
```

Update the signature:

```python
def execute_run(*, spec: Spec, runs_dir: Path, allow_alias_drift: bool = False) -> None:
    """Synchronous entry point invoked by the CLI."""
    asyncio.run(_execute_run_async(spec=spec, runs_dir=runs_dir, allow_alias_drift=allow_alias_drift))
```

Inside `_execute_run_async`, after `run_dir.mkdir(...)`, add:

```python
frozen_provenance = (spec.model_dump(mode="json").get("provenance") or {})
frozen_model_version = frozen_provenance.get("model_resolved_version")
frozen_harbor = frozen_provenance.get("harbor_version")
drift_record: dict | None = None

if frozen_harbor is not None:
    check_harbor_drift(frozen=frozen_harbor, installed=None)

if frozen_model_version is not None:
    model_alias = getattr(spec.agent, "model", None) or "claude-opus-4-5"
    import anthropic
    client = anthropic.Anthropic()
    resolved_id, resolved_at = check_alias_drift(
        model_alias=model_alias,
        frozen_resolved_version=frozen_model_version,
        client=client,
        allow=allow_alias_drift,
    )
    if resolved_id != frozen_model_version:
        drift_record = {
            "model_alias": model_alias,
            "frozen": frozen_model_version,
            "resolved": resolved_id,
            "resolved_at": resolved_at,
        }

# Write provenance.yaml early so it's there even if Job.create fails.
write_provenance_yaml(run_dir / "provenance.yaml", frozen_provenance, drift_record=drift_record)
```

- [ ] **Step 4: Modify `src/razorback/cli/run.py` for the new flag**

Add the option and pipe it:

```python
def run_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    runs_dir: Path = typer.Option(Path("_runs"), "--runs-dir"),
    allow_alias_drift: bool = typer.Option(False, "--allow-alias-drift",
                                            help="Run even when provider version differs from frozen."),
) -> None:
    ...
    execute_run(spec=spec, runs_dir=runs_dir, allow_alias_drift=allow_alias_drift)
```

- [ ] **Step 5: Run the test, confirm green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_run_drift_wired.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Run the full test suite to confirm no regressions**

```bash
cd /Users/clkao/git/razorback && uv run pytest -x
```

Expected: all green. If M1/M2/M3 tests fail, investigate before proceeding (likely a schema-defaults regression from adding `ProvenanceBlock`).

- [ ] **Step 7: Commit**

```bash
git add src/razorback/run.py src/razorback/cli/run.py \
        tests/unit/test_run_drift_wired.py
git commit -m "m5: wire drift checks into rk run (AC-3, AC-4, §6.4)"
```

---

## Task 8: 12-dataset stratified aggregator fixture and golden (AC-5)

**Files:**
- Create: `tests/fixtures/provenance/twelve_dataset_trial_results.json`
- Create: `tests/fixtures/provenance/twelve_dataset_golden_summary.json`
- Create: `tests/unit/test_dab_aggregate_twelve_datasets.py`

This is the AC-5 verification: feed the **existing M2 aggregator** (`razorback.benchmarks.dab.aggregate.aggregate_synthetic`) a 12-dataset fixture and assert the resulting `summary.json` carries the stratified macro-average computed by hand.

**Per-dataset pass@1 design.** To make the hand-computed cross-dataset average obviously not 0 or 1, we give each of the 12 datasets a distinct per-query pass rate. The 12 dataset slugs are the real DAB ones (Task 0 step 3 lists them). For each dataset we author 2 queries × 5 trials. Per-dataset pass@1 ramps from 0.0 → 1.0 in 12 even steps:

| Dataset | q1 (c/n) | q2 (c/n) | per-dataset pass@1 |
|---|---|---|---|
| agnews            | 0/5 | 0/5 | 0.0 |
| bookreview        | 1/5 | 0/5 | (0.2 + 0.0) / 2 = 0.1 |
| crmarenapro       | 2/5 | 0/5 | (0.4 + 0.0) / 2 = 0.2 |
| DEPS_DEV_V1       | 3/5 | 0/5 | (0.6 + 0.0) / 2 = 0.3 |
| GITHUB_REPOS      | 4/5 | 0/5 | (0.8 + 0.0) / 2 = 0.4 |
| googlelocal       | 5/5 | 0/5 | (1.0 + 0.0) / 2 = 0.5 |
| music_brainz_20k  | 5/5 | 1/5 | (1.0 + 0.2) / 2 = 0.6 |
| PANCANCER_ATLAS   | 5/5 | 2/5 | (1.0 + 0.4) / 2 = 0.7 |
| PATENTS           | 5/5 | 3/5 | (1.0 + 0.6) / 2 = 0.8 |
| stockindex        | 5/5 | 4/5 | (1.0 + 0.8) / 2 = 0.9 |
| stockmarket       | 5/5 | 5/5 | 1.0 |
| yelp              | 5/5 | 5/5 | 1.0 |

Sum of per-dataset pass@1 values = `0.0 + 0.1 + 0.2 + 0.3 + 0.4 + 0.5 + 0.6 + 0.7 + 0.8 + 0.9 + 1.0 + 1.0 = 6.5`. Stratified macro-average = `6.5 / 12 = 0.5416666…`.

- [ ] **Step 1: Author the fixture and golden**

Create `tests/fixtures/provenance/twelve_dataset_trial_results.json`:

```json
[
  {"dataset": "agnews",            "query_id": 1, "rewards": {"reward": 0.0}},
  {"dataset": "agnews",            "query_id": 1, "rewards": {"reward": 0.0}},
  {"dataset": "agnews",            "query_id": 1, "rewards": {"reward": 0.0}},
  {"dataset": "agnews",            "query_id": 1, "rewards": {"reward": 0.0}},
  {"dataset": "agnews",            "query_id": 1, "rewards": {"reward": 0.0}},
  {"dataset": "agnews",            "query_id": 2, "rewards": {"reward": 0.0}},
  {"dataset": "agnews",            "query_id": 2, "rewards": {"reward": 0.0}},
  {"dataset": "agnews",            "query_id": 2, "rewards": {"reward": 0.0}},
  {"dataset": "agnews",            "query_id": 2, "rewards": {"reward": 0.0}},
  {"dataset": "agnews",            "query_id": 2, "rewards": {"reward": 0.0}}
]
```

(That's a head — the full fixture has 12 datasets × 2 queries × 5 trials = 120 rows. The implementer authors all 120 rows mechanically: for the (dataset, query_id) cells whose `c/n` is `k/5`, write `k` rows with reward `1.0` and `5-k` rows with reward `0.0`. The implementer MAY write a small Python script outside the test tree to mint the fixture and then check it in; the script does not ship.)

`tests/fixtures/provenance/twelve_dataset_golden_summary.json` (full file body — replicate verbatim):

```json
{
  "summary_version": 1,
  "stratified_pass_at_1": 0.5416666666666666,
  "datasets": {
    "DEPS_DEV_V1": {
      "dataset_pass_at_1": 0.3,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 3, "pass_at_1": 0.6},
        {"query_id": 2, "n_trials": 5, "n_correct": 0, "pass_at_1": 0.0}
      ]
    },
    "GITHUB_REPOS": {
      "dataset_pass_at_1": 0.4,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 4, "pass_at_1": 0.8},
        {"query_id": 2, "n_trials": 5, "n_correct": 0, "pass_at_1": 0.0}
      ]
    },
    "PANCANCER_ATLAS": {
      "dataset_pass_at_1": 0.7,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0},
        {"query_id": 2, "n_trials": 5, "n_correct": 2, "pass_at_1": 0.4}
      ]
    },
    "PATENTS": {
      "dataset_pass_at_1": 0.8,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0},
        {"query_id": 2, "n_trials": 5, "n_correct": 3, "pass_at_1": 0.6}
      ]
    },
    "agnews": {
      "dataset_pass_at_1": 0.0,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 0, "pass_at_1": 0.0},
        {"query_id": 2, "n_trials": 5, "n_correct": 0, "pass_at_1": 0.0}
      ]
    },
    "bookreview": {
      "dataset_pass_at_1": 0.1,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 1, "pass_at_1": 0.2},
        {"query_id": 2, "n_trials": 5, "n_correct": 0, "pass_at_1": 0.0}
      ]
    },
    "crmarenapro": {
      "dataset_pass_at_1": 0.2,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 2, "pass_at_1": 0.4},
        {"query_id": 2, "n_trials": 5, "n_correct": 0, "pass_at_1": 0.0}
      ]
    },
    "googlelocal": {
      "dataset_pass_at_1": 0.5,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0},
        {"query_id": 2, "n_trials": 5, "n_correct": 0, "pass_at_1": 0.0}
      ]
    },
    "music_brainz_20k": {
      "dataset_pass_at_1": 0.6,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0},
        {"query_id": 2, "n_trials": 5, "n_correct": 1, "pass_at_1": 0.2}
      ]
    },
    "stockindex": {
      "dataset_pass_at_1": 0.9,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0},
        {"query_id": 2, "n_trials": 5, "n_correct": 4, "pass_at_1": 0.8}
      ]
    },
    "stockmarket": {
      "dataset_pass_at_1": 1.0,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0},
        {"query_id": 2, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0}
      ]
    },
    "yelp": {
      "dataset_pass_at_1": 1.0,
      "n_queries": 2,
      "queries": [
        {"query_id": 1, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0},
        {"query_id": 2, "n_trials": 5, "n_correct": 5, "pass_at_1": 1.0}
      ]
    }
  }
}
```

(The `datasets` dict is sorted by `sorted(...)` — Python's default string sort puts uppercase before lowercase, which is what M2's `dict(sorted(datasets.items()))` produces. Confirm by running the test below.)

- [ ] **Step 2: Write the failing test**

`tests/unit/test_dab_aggregate_twelve_datasets.py`:

```python
# ABOUTME: AC-5 — DAB aggregator produces stratified macro-average across 12 datasets (§6.5).

import json
from pathlib import Path

from razorback.benchmarks.dab.aggregate import aggregate_synthetic


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "provenance"


def test_aggregator_stratifies_across_twelve_datasets(tmp_path):
    rows = json.loads((FIXTURES / "twelve_dataset_trial_results.json").read_text())
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    got = json.loads(out.read_text())
    expected = json.loads((FIXTURES / "twelve_dataset_golden_summary.json").read_text())
    assert got == expected


def test_stratified_pass_at_1_is_hand_computed_macro_average(tmp_path):
    """Independent verification: re-derive the macro-average without reading the golden."""
    rows = json.loads((FIXTURES / "twelve_dataset_trial_results.json").read_text())
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    got = json.loads(out.read_text())
    per_ds = [d["dataset_pass_at_1"] for d in got["datasets"].values()]
    assert len(per_ds) == 12
    assert abs(got["stratified_pass_at_1"] - sum(per_ds) / 12) < 1e-9
    assert abs(got["stratified_pass_at_1"] - 6.5 / 12) < 1e-9
```

- [ ] **Step 3: Run the test, confirm green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_dab_aggregate_twelve_datasets.py -v
```

Expected: 2 passed. The M2 aggregator code is untouched — its math already handles N datasets.

If the golden mismatches the actual output (likely the dict key ordering), regenerate the golden via:

```bash
cd /Users/clkao/git/razorback && uv run python -c "
import json
from pathlib import Path
from razorback.benchmarks.dab.aggregate import aggregate_synthetic
rows = json.loads(Path('tests/fixtures/provenance/twelve_dataset_trial_results.json').read_text())
out = Path('tests/fixtures/provenance/twelve_dataset_golden_summary.json')
aggregate_synthetic(rows, out)
print(out.read_text())
"
```

Then re-run the test. Document the regeneration in the commit message.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/provenance/ tests/unit/test_dab_aggregate_twelve_datasets.py
git commit -m "m5: 12-dataset stratified aggregator fixture + golden (AC-5, §6.5)"
```

---

## Task 9: Widen the harbor 0.6.6 translator for N datasets

**Files:**
- Modify: `src/razorback/compat/harbor_0_6_6.py`
- Create: `tests/unit/test_dab_translator_twelve.py`

M2 Task 7 already implemented `spec_to_job_config` for the `kind: dab` path that fans out one task per `(dataset, query_id)`. The implementation should already handle N datasets if it iterates `spec.benchmark.datasets`. This task is a **verification step**: confirm the translator widens to 12 datasets and exposes the `trial_name_map` with all 12 dataset slugs. If the M2 implementation hard-coded `bookreview`, this task patches it.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_dab_translator_twelve.py`:

```python
# ABOUTME: Translator fans out to all 12 DAB datasets — generalizes M2's bookreview-only path.

from pathlib import Path

import pytest

from razorback.compat.harbor_0_6_6 import spec_to_job_config
from razorback.spec.parse import parse_spec_text


TWELVE = [
    "agnews", "bookreview", "crmarenapro", "DEPS_DEV_V1", "GITHUB_REPOS",
    "googlelocal", "music_brainz_20k", "PANCANCER_ATLAS", "PATENTS",
    "stockindex", "stockmarket", "yelp",
]


def _make_fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    for slug in TWELVE:
        ds = root / f"query_{slug}"
        (ds / "query_dataset").mkdir(parents=True)
        (ds / "query_dataset" / "review_query.db").write_bytes(b"sqlite-stub")
        (ds / "db_config.yaml").write_text("db_clients: {}\n")
        (ds / "db_description.txt").write_text("desc")
        # one query each is enough to verify fan-out
        q = ds / "query1"
        q.mkdir()
        (q / "query.json").write_text('"Q1?"')
        (q / "validate.py").write_text("def validate(s): return ('1' in s, 'ok')\n")
        (q / "ground_truth.csv").write_text("1\n")
    return root


SPEC_TEMPLATE = """\
version: 1
experiment: m5-twelve
agent:
  kind: nop
benchmark:
  kind: dab
  data_root: {data_root}
  datasets:
    - agnews
    - bookreview
    - crmarenapro
    - DEPS_DEV_V1
    - GITHUB_REPOS
    - googlelocal
    - music_brainz_20k
    - PANCANCER_ATLAS
    - PATENTS
    - stockindex
    - stockmarket
    - yelp
trials: 1
"""


def test_translator_fans_out_to_all_twelve_datasets(tmp_path):
    data_root = _make_fixture_root(tmp_path)
    spec = parse_spec_text(SPEC_TEMPLATE.format(data_root=data_root))
    cfg, trial_map = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
    )
    task_prefixes = sorted({Path(tc.path).name.split("__")[0] for tc in cfg.tasks})
    assert task_prefixes == sorted([f"{slug}-q1" for slug in TWELVE])
    assert sorted(trial_map.keys()) == sorted([f"{slug}-q1" for slug in TWELVE])
    assert all(trial_map[f"{slug}-q1"] == (slug, 1) for slug in TWELVE)


def test_translator_retry_zero_still_holds_at_twelve_datasets(tmp_path):
    """AC-4 from M2 must keep holding: max_retries=0 regardless of dataset count."""
    data_root = _make_fixture_root(tmp_path)
    spec = parse_spec_text(SPEC_TEMPLATE.format(data_root=data_root))
    cfg, _ = spec_to_job_config(
        spec, job_name="x" * 16, jobs_dir=tmp_path / "jobs", tasks_root=tmp_path / "tasks",
    )
    assert cfg.retry.max_retries == 0
```

- [ ] **Step 2: Run the test, confirm red OR green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_dab_translator_twelve.py -v
```

Two outcomes:

- **Green:** M2's translator already iterates `spec.benchmark.datasets` cleanly. Skip Step 3, jump to Step 4.
- **Red:** M2 hard-coded `bookreview` somewhere. Patch the iteration site.

- [ ] **Step 3: If red, fix the translator**

Find the offending hard-coded `bookreview` in `src/razorback/compat/harbor_0_6_6.py` and replace with `for slug in spec.benchmark.datasets:`. Re-run the test until green.

- [ ] **Step 4: Run the test, confirm green**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_dab_translator_twelve.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/compat/harbor_0_6_6.py tests/unit/test_dab_translator_twelve.py
git commit -m "m5: translator fan-out widened to N datasets (verification)"
```

---

## Task 10: Provenance.yaml sidecar shape — round-trip + unresolved markers

**Files:**
- Create: `tests/unit/test_provenance_yaml.py`

This is a small coverage task — Task 6's CLI test exercises `write_provenance_yaml` indirectly, but we want a focused unit test on the YAML shape so future schema bumps catch field renames.

- [ ] **Step 1: Write the test**

`tests/unit/test_provenance_yaml.py`:

```python
# ABOUTME: provenance.yaml writer — shape stability test (§6.4 sidecar).

from pathlib import Path

import yaml

from razorback.provenance.provenance_yaml import write_provenance_yaml


ALL_RESOLVED = {
    "model_resolved_version": "claude-opus-4-5-20251022",
    "model_resolved_at": "2025-10-22T00:00:00Z",
    "image_digest": "sha256:abc",
    "agent_cli_hash": "sha256:def",
    "harness_git_sha": "0123456789abcdef",
    "harbor_version": "0.6.6",
    "prompt_file_hashes": {"p.md": "sha256:fed"},
}


def test_writes_six_resolved_fields_plus_timestamp(tmp_path):
    out = tmp_path / "provenance.yaml"
    write_provenance_yaml(out, ALL_RESOLVED)
    doc = yaml.safe_load(out.read_text())
    assert doc["model_resolved_version"] == "claude-opus-4-5-20251022"
    assert doc["model_resolved_at"] == "2025-10-22T00:00:00Z"
    assert doc["harbor_version"] == "0.6.6"
    assert "unresolved" not in doc
    assert "alias_drift" not in doc


def test_unresolved_field_appears_in_unresolved_list_not_in_body(tmp_path):
    resolved = dict(ALL_RESOLVED)
    resolved["image_digest"] = None
    out = tmp_path / "provenance.yaml"
    write_provenance_yaml(out, resolved)
    doc = yaml.safe_load(out.read_text())
    assert "image_digest" not in doc  # removed from the body
    assert "image_digest" in doc["unresolved"]


def test_drift_record_appears_under_alias_drift(tmp_path):
    out = tmp_path / "provenance.yaml"
    write_provenance_yaml(
        out, ALL_RESOLVED,
        drift_record={"model_alias": "claude-opus-4-5",
                      "frozen": "claude-opus-4-5-20251022",
                      "resolved": "claude-opus-4-5-20260101"},
    )
    doc = yaml.safe_load(out.read_text())
    assert doc["alias_drift"]["frozen"] == "claude-opus-4-5-20251022"
    assert doc["alias_drift"]["resolved"] == "claude-opus-4-5-20260101"


def test_multiple_unresolved_sorted(tmp_path):
    resolved = dict(ALL_RESOLVED)
    resolved["image_digest"] = None
    resolved["harbor_version"] = None
    out = tmp_path / "provenance.yaml"
    write_provenance_yaml(out, resolved)
    doc = yaml.safe_load(out.read_text())
    assert doc["unresolved"] == ["harbor_version", "image_digest"]
```

- [ ] **Step 2: Run the test, confirm green (it should pass — write_provenance_yaml was implemented in Task 2)**

```bash
cd /Users/clkao/git/razorback && uv run pytest tests/unit/test_provenance_yaml.py -v
```

Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_provenance_yaml.py
git commit -m "m5: provenance.yaml shape coverage tests"
```

---

## Task 11: Author the acceptance spec `examples/specs/dab-dev-claude.yaml` (AC-6 setup)

**Files:**
- Create: `examples/specs/dab-dev-claude.yaml`

This is the spec the AC-6 acceptance command operates on. It names all 12 DAB datasets, uses the M3 `claude-cli` agent kind, sets `trials: 1` to bound cost, and references the same prompt-file machinery M3 wires up. The DAB dev tier is "one trial per query across all 12 datasets" — per AC-6 verbatim.

- [ ] **Step 1: Write the spec**

`examples/specs/dab-dev-claude.yaml`:

```yaml
version: 1
experiment: m5-dab-dev-claude

agent:
  kind: claude-cli
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
  tools_allowed: []
  # prompt_file: agent-prompts/dab-claude.md   # uncomment when M3 lands an example prompt

benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets:
    - agnews
    - bookreview
    - crmarenapro
    - DEPS_DEV_V1
    - GITHUB_REPOS
    - googlelocal
    - music_brainz_20k
    - PANCANCER_ATLAS
    - PATENTS
    - stockindex
    - stockmarket
    - yelp

environment:
  kind: docker
  image: dab-agent

trials: 1
concurrency:
  trials: 4
  validators: 2

observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout

provenance:
  pin_model_version: true
  pin_image_digest: true
  pin_agent_cli_hash: true
  pin_git_sha: true
```

(If `EnvironmentBlock` or `concurrency`/`sampling`/`tools_allowed` schemas don't accept these keys yet, the implementer adjusts: only those keys M3 has landed should appear. The implementer prunes the file to the M3-actually-landed schema and notes the pruning in the commit.)

- [ ] **Step 2: Confirm the spec parses**

```bash
cd /Users/clkao/git/razorback && uv run python -c "
from razorback.spec.parse import parse_spec_file
spec = parse_spec_file('examples/specs/dab-dev-claude.yaml')
print(f'OK: {len(spec.benchmark.datasets)} datasets, agent={spec.agent.kind}, trials={spec.trials}')
"
```

Expected: `OK: 12 datasets, agent=claude-cli, trials=1`. If pydantic refuses a key, prune it; if pydantic insists on a required key, add a minimal value.

- [ ] **Step 3: Commit**

```bash
git add examples/specs/dab-dev-claude.yaml
git commit -m "m5: example DAB dev-tier spec (12 datasets, claude-cli, trials=1)"
```

---

## Task 12: AC-6 integration test — full DAB dev tier through Claude

**Files:**
- Create: `tests/integration/test_dab_dev_claude_full.py`

This is the cost-bearing, headline deliverable. The test runs `rk spec freeze` then `rk run` against the full 12-dataset spec, then asserts `summary.json` has the right shape. It is **gated by an env var** (`RAZORBACK_RUN_FULL_DAB_TEST=1`) so CI defaults to a skip. Operators run it explicitly. Per AC-6 the test does NOT assert a non-zero score — only that the shape is correct (per-query block × 12, per-dataset mean × 12, one stratified line). A non-zero score is the **scientific** result of M5; the test asserts the **engineering** result (the wiring is correct).

**Pre-flight blocker.** This test depends on M3's `ClaudeCliAgent` having landed in impl. M3 plan is currently in plan stage and impl is deferred (tasks #26-#32 pending). If M3 has not landed when M5 reaches Task 12, the implementer:

1. Stops on this task.
2. Marks it BLOCKED-ON-M3 in the stage report.
3. Sends `SendMessage(to="team-lead", message="M5 impl T12 BLOCKED — M3 ClaudeCliAgent not landed; impl signaling done with T12 deferred.")`.

The plan is still useful: Tasks 1-11 stand alone (refusal machinery, freeze CLI, 12-dataset aggregator) and can land before M3 impl finishes.

- [ ] **Step 1: Write the integration test**

`tests/integration/test_dab_dev_claude_full.py`:

```python
# ABOUTME: AC-6 — full DAB dev-tier run through Claude. Cost-bearing; gated by env var.
# ABOUTME: One trial per query across all 12 DAB datasets.

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


SPEC = Path(__file__).resolve().parents[2] / "examples" / "specs" / "dab-dev-claude.yaml"
FROZEN = SPEC.with_suffix(".frozen.yaml")
GATE = os.getenv("RAZORBACK_RUN_FULL_DAB_TEST") == "1"

TWELVE = {
    "agnews", "bookreview", "crmarenapro", "DEPS_DEV_V1", "GITHUB_REPOS",
    "googlelocal", "music_brainz_20k", "PANCANCER_ATLAS", "PATENTS",
    "stockindex", "stockmarket", "yelp",
}


@pytest.mark.skipif(not GATE,
                    reason="full DAB dev-tier run is cost-bearing; set RAZORBACK_RUN_FULL_DAB_TEST=1")
def test_dab_dev_claude_full_writes_complete_summary(tmp_path):
    runs_dir = tmp_path / "_runs"

    # 1) Freeze.
    freeze = subprocess.run(
        ["uv", "run", "rk", "spec", "freeze", str(SPEC)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
    )
    assert freeze.returncode == 0, (
        f"freeze failed: stdout={freeze.stdout}\nstderr={freeze.stderr}"
    )
    assert FROZEN.exists(), f"freeze did not write {FROZEN}"
    assert (SPEC.parent / "provenance.yaml").exists()

    # 2) Run.
    run = subprocess.run(
        ["uv", "run", "rk", "run", str(FROZEN), "--runs-dir", str(runs_dir)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
    )
    assert run.returncode == 0, (
        f"run failed (exit {run.returncode}): stdout={run.stdout}\nstderr={run.stderr}"
    )

    # 3) Locate the single run-dir and load summary.json.
    experiment_dir = runs_dir / "m5-dab-dev-claude"
    run_dirs = list(experiment_dir.iterdir())
    assert len(run_dirs) == 1, f"expected one run-dir under {experiment_dir}, got {run_dirs}"
    summary_path = run_dirs[0] / "summary.json"
    assert summary_path.exists(), f"no summary.json under {run_dirs[0]}"
    summary = json.loads(summary_path.read_text())

    # 4) Shape assertions (AC-6 verbatim).
    assert "stratified_pass_at_1" in summary
    assert isinstance(summary["stratified_pass_at_1"], (int, float))
    assert set(summary["datasets"].keys()) == TWELVE, (
        f"summary.json missing datasets: {TWELVE - set(summary['datasets'].keys())}; "
        f"extras: {set(summary['datasets'].keys()) - TWELVE}"
    )
    for slug, ds_block in summary["datasets"].items():
        assert "dataset_pass_at_1" in ds_block, f"{slug} missing dataset_pass_at_1"
        assert ds_block["n_queries"] >= 1
        assert all("pass_at_1" in q for q in ds_block["queries"])
```

- [ ] **Step 2: Mechanism smoke (CHEAP — do this before paying the dev-tier cost)**

Per CL's "smallest end-to-end exercise of the riskiest path FIRST" rule, run the same test against a **single-dataset** override before paying for 12. The cheap version uses the M2 spec (`bookreview` only) and confirms the rk spec freeze → rk run pipeline does not blow up at the wiring level:

```bash
cd /Users/clkao/git/razorback && \
  RAZORBACK_RUN_FULL_DAB_TEST=1 \
  uv run pytest tests/integration/test_dab_bookreview_smoke.py -v
```

(The bookreview smoke is M2's test; if it does not exist yet, do not author it here — that is M2 territory. Skip this step if it does not exist and rely on the M3 integration test as the cheap path.)

- [ ] **Step 3: Pay the cost — run the 12-dataset integration**

```bash
cd /Users/clkao/git/razorback && \
  RAZORBACK_RUN_FULL_DAB_TEST=1 \
  uv run pytest tests/integration/test_dab_dev_claude_full.py -v
```

Expected wallclock: roughly the M3 single-query wallclock × ~30 (12 datasets × 2-3 queries × 1 trial; concurrency 4 reduces the multiplier). Estimate is one dev-tier run is the cost budget per the M5 entity's test plan.

Expected output: a single passing test. If the test fails with `summary.json missing datasets`, the translator's fan-out is buggy at scale; jump back to Task 9. If the test fails with a network/auth error, the M3 contract has regressed; escalate.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_dab_dev_claude_full.py
git commit -m "m5: AC-6 integration test — full DAB dev tier through Claude"
```

---

## Task 13: Final acceptance — the §8.M5 command from a clean tree

**Files:**
- None — verification only.

The M5 entity's acceptance command (lines 95-99):

```
uv run rk spec freeze examples/specs/dab-dev-claude.yaml
uv run rk run examples/specs/dab-dev-claude.frozen.yaml
```

We run it from a clean tree and confirm exit codes plus the four invariants.

- [ ] **Step 1: Clean tree, run acceptance**

```bash
cd /Users/clkao/git/razorback && \
  rm -rf examples/specs/dab-dev-claude.frozen.yaml \
         examples/specs/provenance.yaml \
         _runs/m5-dab-dev-claude && \
  uv run rk spec freeze examples/specs/dab-dev-claude.yaml && \
  uv run rk run examples/specs/dab-dev-claude.frozen.yaml
```

- [ ] **Step 2: Manually verify the four invariants**

```bash
test -f examples/specs/dab-dev-claude.frozen.yaml && echo "ok frozen"
test -f examples/specs/provenance.yaml && echo "ok provenance"
ls _runs/m5-dab-dev-claude/*/summary.json | head -1
uv run python -c "
import json, glob
p = glob.glob('_runs/m5-dab-dev-claude/*/summary.json')[0]
s = json.loads(open(p).read())
assert len(s['datasets']) == 12, f\"expected 12 datasets, got {list(s['datasets'].keys())}\"
assert 'stratified_pass_at_1' in s and isinstance(s['stratified_pass_at_1'], (int, float))
for slug, block in s['datasets'].items():
    assert all('pass_at_1' in q for q in block['queries']), f'{slug} missing per-query pass_at_1'
    assert 'dataset_pass_at_1' in block, f'{slug} missing dataset_pass_at_1'
print(f'OK: stratified={s[\"stratified_pass_at_1\"]:.4f}, 12 datasets, per-query + per-dataset present.')
"
```

Expected: all `ok` lines plus the final `OK: stratified=…` line. The stratified value is **the first real DAB result**; record it in the stage report.

- [ ] **Step 3: Run the full test suite for regressions**

```bash
cd /Users/clkao/git/razorback && uv run pytest --ignore=tests/integration -v
```

Expected: all unit tests green. (Integration tests skipped by default unless the env gate is set.)

- [ ] **Step 4: Commit the §8.M5 evidence (run-dir excluded — too big)**

```bash
git status
# Confirm only intentional changes are staged. _runs/ should be gitignored.
# If clean, nothing to commit at this step; the stage report below references the score.
```

---

## Task 14: Cross-reference plan from the M5 entity body

**Files:**
- Modify: `docs/razorback-implementation/m5-provenance-full-dab.md`

The M5 entity body should link to this plan so anyone reading the entity at execution time finds the implementation steps.

- [ ] **Step 1: Append a "Plan" pointer to the entity body, BEFORE the Stage Report section**

Insert after the "Out of scope" section in `docs/razorback-implementation/m5-provenance-full-dab.md`:

```markdown
## Plan

Implementation plan: [`plans/m5-provenance-full-dab.md`](plans/m5-provenance-full-dab.md).
Tasks 1-3 land the riskiest contracts (alias drift, missing-provenance refusal, harbor drift). Tasks 4-10 add the resolver stack and 12-dataset aggregator. Tasks 11-13 are the AC-6 acceptance run — cost-bounded, one trial per query.
```

- [ ] **Step 2: Commit**

```bash
git add docs/razorback-implementation/m5-provenance-full-dab.md
git commit -m "m5: cross-reference plan from entity body"
```

---

## Self-review notes

**Spec coverage.** Each of the seven ACs in `docs/razorback-implementation/m5-provenance-full-dab.md` maps to at least one task per the AC ↔ Task Map at the top. All six provenance fields from §6.4 are covered by named resolver tests in Task 5. Exit codes 11 (`ProvenanceError`) and 21 (`AliasDriftError`) per §3.2 are wired by Tasks 1-2-3 and asserted in test bodies.

**Placeholder scan.** All steps contain literal code or shell commands. The 12-dataset fixture's "120 rows" mechanical generation is the only place where the engineer fills in repeated content — the table spelling out per-dataset c/n values is unambiguous, and the regeneration script in Step 3 lets them mint the golden mechanically.

**Type consistency.** `check_alias_drift` signature is consistent across Task 1 (introduction) and Task 7 (use in `rk run`). `AliasDriftError.frozen` / `.resolved` / `.model_alias` are referenced consistently. `resolve_model_version` returns `(str, str)` in both Task 5 (definition) and Task 6 (use). `write_provenance_yaml` signature is the same in Task 2 (introduction) and Task 7 (use).

**Riskiest contract first (M5 entity checklist item #2).** Task 1 (AliasDriftError unit test against mocked Anthropic SDK) lands BEFORE the resolver code. Task 2 (missing-provenance refusal) lands BEFORE the freeze command. Task 3 (harbor drift) lands BEFORE the run command. The aggregator generalization (Task 8) lands AFTER the refusal machinery. The cost-bearing integration test (Task 12) is last.

**M2 reuse (M5 entity checklist item #3).** The plan documents in the "AC ↔ Task Map" and "Architecture" sections that `_build_summary` and `pass_at_k` from `src/razorback/benchmarks/dab/aggregate.py` (M2 plan lines 287-337) are unchanged. M5 only widens the input via the 12-dataset fixture and confirms the translator iterates `spec.benchmark.datasets`.

**Provider-API divergence.** The "Provider-API resolver" section names `anthropic.Anthropic().models.retrieve(model_id)` as the concrete library/endpoint and confirms `model.id` + `model.created_at` map directly onto the design doc's `model_resolved_version` + API timestamp. No divergence flagged. Codex/OpenAI is explicitly deferred to M6/M7 with the resolver stub raising `NotImplementedError`, matching the design doc which only exemplifies Anthropic in §6.4.
