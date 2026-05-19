# M1 — `rk run` against nop agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `uv run rk run examples/specs/nop.yaml` execute end-to-end against harbor's bundled nop agent, producing a run-dir under `_runs/<experiment>/<job_name>/` that matches §6.3.

**Architecture:** A Typer-rooted `rk` CLI loads a YAML spec, validates it through a pydantic schema (`razorback.spec`), writes a frozen-spec echo and `manifest.json`, then translates the frozen spec into a harbor `JobConfig` (`razorback.compat.harbor_0_6_6`). `rk run` awaits `Job.create(cfg)` and `Job.run()`, fanning out hook callbacks into a single-writer asyncio channel that two observers consume — `jsonl` (writes `events.jsonl`) and `stdout` (prints one line per event). After the job returns, razorback writes `summary.json` from `JobResult`.

**Tech Stack:** Python 3.12, `uv`, Typer 0.16, Pydantic 2.11, PyYAML 6, harbor 0.6.6, pytest 8 with `pytest-asyncio` 0.24, docker via Colima.

**Source of truth:** the design doc at `/Users/clkao/git/dataagentbench/docs/superpowers/specs/2026-05-18-razorback-python-on-harbor.md`. Section anchors below cite it as `§N.N`. The eight ACs live in the M1 entity at `docs/razorback-implementation/m1-rk-run-nop.md`.

**AC ↔ task map (1:1):**

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 `rk run` exits 0 | §6.1 harbor integration | Tasks 1, 6, 12, 13 |
| AC-2 run-dir layout matches §6.3 | §6.3 run-dir layout | Tasks 1, 8, 12 |
| AC-3 `spec.frozen.yaml` faithful echo | §3.2 freeze, §6.4 (M1 partial) | Tasks 3, 7 |
| AC-4 `manifest.json` has `run_dir_version: 1` + `created_at` ISO 8601 | §3.3, §6.7 | Task 8 |
| AC-5 `events.jsonl` one-per-event, fire order, single drainer | §6.6 async observers | Tasks 9, 10, 12 |
| AC-6 `job_name = sha256(frozen)[:16]` | §6.7 content-derived job_name | Tasks 4, 12 |
| AC-7 unknown top-level key → `SpecError`, exit 10 | §3.2 exit codes, §5 spec | Tasks 2, 6 |
| AC-8 stdout observer matches `events.jsonl` lines | §6.6 single channel | Tasks 9, 11 |

**Riskiest contract first.** Task 1 runs the live harbor `nop` + hello-world + verifier round-trip on the operator's machine **before** any scaffolding lands. Per `docs/pre-m1-findings.md` the open question is whether `tests/test.sh` actually deposits `reward.txt` on the host under Colima bind-mounts. If this fails, no later scaffolding work matters; we want to know on day one. Per CL's "Validating new mechanisms" rule, the smallest end-to-end exercise of the riskiest path goes first.

**Working agreements pulled forward from `/tmp/razorback-implementation-handoff.md`:**

- Repo layout follows §7 (`src/razorback/{cli,spec,observers,compat}` for M1).
- All scaffolding files start with the `ABOUTME:` two-line comment header (per CL's global rules).
- Pinned harbor is `harbor==0.6.6`; imports follow `docs/pre-m1-findings.md` "Harbor API map".
- macOS+Colima only mounts `/Users/<user>/` into the docker VM. Anything that round-trips through a container (run-dirs, the integration test's `tmp_path`) must live under `/Users/...`. Tests use a fixture rooted at `Path.home() / ".cache" / "razorback-tests"` (or `os.environ["RAZORBACK_TEST_DIR"]` if set) — **not** `tempfile.mkdtemp()`.
- TDD: every behavior task writes the failing test first, runs it red, then makes it green, then commits.
- Commits: one focused commit per task. Format: `m1: <short summary>`.

---

## File structure

Files created or modified by this plan. Existing files marked `[existing]`; the rest are net new.

```
pyproject.toml                                 [existing — extend dev-deps]
examples/
└── specs/
    └── nop.yaml                               [new] M1 input spec for the acceptance command
examples/tasks/
└── hello-world/
    ├── task.toml                              [new] harbor task manifest
    ├── instruction.md                         [new]
    ├── environment/Dockerfile                 [new]
    └── tests/test.sh                          [new] writes /logs/verifier/reward.txt
src/razorback/
├── __init__.py                                [existing — keep empty surface]
├── errors.py                                  [new] SpecError + ExitCode enum
├── cli/
│   ├── __init__.py                            [existing — extend; register `run`]
│   └── run.py                                 [new] `rk run` command body
├── spec/
│   ├── __init__.py                            [new]
│   ├── schema.py                              [new] pydantic Spec model, top-level forbid-extra
│   ├── parse.py                               [new] YAML → Spec; raises SpecError
│   └── freeze.py                              [new] M1 freeze: echo + `version: 1`; sha256[:16]
├── manifest.py                                [new] `RUN_DIR_VERSION = 1`, manifest writer
├── observers/
│   ├── __init__.py                            [new]
│   ├── channel.py                             [new] single-writer asyncio.Queue + drainer
│   ├── jsonl.py                               [new] jsonl observer coroutine
│   └── stdout.py                              [new] stdout observer coroutine
├── compat/
│   ├── __init__.py                            [new]
│   └── harbor_0_6_6.py                        [new] spec → JobConfig translator
└── run.py                                     [new] orchestrator: freeze → manifest → Job → drain → summary
tests/
├── __init__.py                                [new]
├── conftest.py                                [new] colima_safe_tmp_path fixture
├── unit/
│   ├── __init__.py                            [new]
│   ├── test_spec_parse.py                     [new]
│   ├── test_freeze.py                         [new]
│   ├── test_job_name.py                       [new]
│   ├── test_manifest.py                       [new]
│   ├── test_channel_drainer.py                [new]
│   └── test_cli_exit_codes.py                 [new]
└── integration/
    ├── __init__.py                            [new]
    └── test_rk_run_nop.py                     [new] end-to-end AC-1..AC-8
docs/razorback-implementation/
└── m1-rk-run-nop.md                           [existing — extend Test plan with cross-ref to this file]
```

---

## Task 0: Pre-flight (no code yet)

**Files:** none.

- [ ] **Step 1: Verify the operator's environment**

```bash
cd /Users/clkao/git/razorback
uv --version
docker info | head -3
.venv/bin/python -c "import harbor; print(harbor.__version__)"
```

Expected: `uv` reports a version; `docker info` succeeds (Colima up); `0.6.6`.

If docker is down: bring Colima up (`colima start`) before continuing. Do not proceed if `Job.create` can't reach docker — Task 1 will hang.

- [ ] **Step 2: No commit. This is a check, not a change.**

---

## Task 1: Mechanism validation — live nop+hello-world+verifier round-trip

**Why first:** per `docs/pre-m1-findings.md` the verifier `reward.txt` round-trip under Colima is the riskiest contract M1 owes. If `tests/test.sh` can't drop a reward file the host sees, **no** later scaffolding work matters. We do this before writing any razorback code.

**Files:**
- Create: `examples/tasks/hello-world/task.toml`
- Create: `examples/tasks/hello-world/instruction.md`
- Create: `examples/tasks/hello-world/environment/Dockerfile`
- Create: `examples/tasks/hello-world/tests/test.sh`
- Create: `scripts/smoke_nop_verified.py` (the smoke script that flips `VerifierConfig(disable=False)` and runs the task above)

- [ ] **Step 1: Author the hello-world task manifest**

Write `examples/tasks/hello-world/task.toml`:

```toml
schema_version = "1.2"

[task]
name = "razorback/hello-world"
description = "Trivial task for nop-agent smoke. Verifier writes a passing reward unconditionally."
```

Write `examples/tasks/hello-world/instruction.md`:

```markdown
Do nothing. The verifier reports success unconditionally.
```

Write `examples/tasks/hello-world/environment/Dockerfile`:

```dockerfile
FROM alpine:3.20
WORKDIR /work
CMD ["sleep", "infinity"]
```

Write `examples/tasks/hello-world/tests/test.sh` (must be executable; mode 0755):

```sh
#!/bin/sh
# Drop a passing reward at harbor's documented contract path.
set -eu
mkdir -p /logs/verifier
printf '1.0' > /logs/verifier/reward.txt
echo "wrote reward.txt" 1>&2
```

After writing: `chmod +x examples/tasks/hello-world/tests/test.sh`.

- [ ] **Step 2: Author the smoke harness**

Write `scripts/smoke_nop_verified.py`. Copy the structure from the existing `scripts/smoke_nop.py` (which already proves the lifecycle with the verifier disabled) and change exactly two things:

1. `VerifierConfig(disable=False)` (verifier ON).
2. Use the checked-in `examples/tasks/hello-world` as the task path instead of writing one to a tempdir.
3. Anchor `work` under `Path.home() / ".cache" / "razorback-smoke"` (Colima only mounts `/Users/<user>/`).

The script must print, at minimum:
- The list of fired `TrialEvent` values.
- The contents of `jobs_dir/smoke-nop/` and each trial subdir.
- The host-side path and contents of `verifier/reward.txt` after the run.
- `result.stats.n_completed_trials` and `result.stats.n_errored_trials`.

Required code shape (use as-is, do not paraphrase the imports):

```python
# ABOUTME: M1 mechanism smoke — runs the nop agent + verifier round-trip end-to-end.
# ABOUTME: Riskiest contract first: does tests/test.sh's reward.txt land on the host?

import asyncio
import json
from pathlib import Path

from harbor.job import Job
from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig
from harbor.models.trial.config import AgentConfig, TaskConfig, VerifierConfig
from harbor.trial.hooks import TrialEvent

REPO = Path(__file__).resolve().parent.parent
TASK_DIR = REPO / "examples" / "tasks" / "hello-world"


async def main() -> None:
    work = Path.home() / ".cache" / "razorback-smoke"
    work.mkdir(parents=True, exist_ok=True)
    jobs_dir = work / "jobs"

    config = JobConfig(
        job_name="smoke-nop-verified",
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=1,
        agents=[AgentConfig(name=AgentName.NOP.value)],
        tasks=[TaskConfig(path=TASK_DIR)],
        verifier=VerifierConfig(disable=False),
    )

    fired: list[str] = []

    async def record(event: TrialEvent, payload):
        fired.append(event.value)

    job = await Job.create(config)
    for event in TrialEvent:
        job.add_hook(event, lambda payload, e=event: record(e, payload))

    result = await job.run()

    run_dir = jobs_dir / "smoke-nop-verified"
    print(f"events fired: {fired}")
    print(f"n_completed: {result.stats.n_completed_trials}")
    print(f"n_errored:   {result.stats.n_errored_trials}")
    for trial_dir in sorted(run_dir.iterdir()):
        if not trial_dir.is_dir():
            continue
        ver = trial_dir / "verifier"
        if ver.exists():
            print(f"--- {ver} ---")
            for f in sorted(ver.rglob("*")):
                if f.is_file():
                    print(f"  {f.relative_to(ver)} ({f.stat().st_size}B): {f.read_text()!r}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Run the smoke**

```bash
uv run python scripts/smoke_nop_verified.py
```

Expected:
- `events fired:` includes `start`, `environment_start`, `agent_start`, `verification_start`, `end` (in some order; fire order is asserted in Task 12).
- `n_completed: 1` and `n_errored: 0`.
- `verifier/reward.txt` exists on the host with contents `'1.0'`.

- [ ] **Step 4: If reward.txt is missing or n_errored > 0 — STOP and ESCALATE**

Do not work around. The mechanism check failed. Send a `SendMessage(to="team-lead", ...)` describing what was observed (verifier directory contents, `trial.log` tail, `exception.txt` if any). The riskiest contract is broken; M1 cannot proceed until CL or the FO decides whether to (a) change the task manifest, (b) change the verifier config, or (c) re-scope the milestone.

The most likely failure modes per pre-M1 notes:
- `/logs/verifier` not pre-created by harbor → `test.sh` already does `mkdir -p`.
- Bind-mount path lives under `/var/folders/...` → already avoided by anchoring under `~/.cache`.
- `tests/test.sh` not executable → already chmodded in Step 1.

- [ ] **Step 5: Commit**

```bash
git add examples/tasks/hello-world scripts/smoke_nop_verified.py
git commit -m "m1: mechanism smoke — nop+hello-world+verifier round-trip"
```

---

## Task 2: Spec schema — pydantic model with `extra=forbid`

**Files:**
- Create: `src/razorback/errors.py`
- Create: `src/razorback/spec/__init__.py`
- Create: `src/razorback/spec/schema.py`
- Create: `tests/__init__.py`, `tests/unit/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/test_spec_parse.py`

Spec scope for M1: the parser only needs the subset of §5 that the nop spec exercises. Future milestones extend the schema; M1's `Spec` model accepts what `examples/specs/nop.yaml` provides and forbids unknown top-level keys.

- [ ] **Step 1: Write `tests/conftest.py`** (used by every test from here on)

```python
# ABOUTME: Shared pytest fixtures for razorback tests.
# ABOUTME: colima_safe_tmp_path anchors test dirs under /Users so Colima bind mounts work.

import os
import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def colima_safe_tmp_path():
    """A tmp dir under /Users/... that Colima mounts into the docker VM."""
    base = Path(os.environ.get("RAZORBACK_TEST_DIR", Path.home() / ".cache" / "razorback-tests"))
    base.mkdir(parents=True, exist_ok=True)
    work = base / f"t-{uuid.uuid4().hex[:8]}"
    work.mkdir()
    try:
        yield work
    finally:
        shutil.rmtree(work, ignore_errors=True)
```

- [ ] **Step 2: Write the failing test**

`tests/unit/test_spec_parse.py`:

```python
# ABOUTME: Unit tests for the spec parser.
# ABOUTME: Covers valid M1 spec, unknown-key rejection, missing-required rejection.

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text


VALID_M1_SPEC = """\
version: 1
experiment: m1-nop
agent:
  kind: nop
benchmark:
  kind: local
  task_paths:
    - examples/tasks/hello-world
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
"""


def test_parses_valid_m1_spec():
    spec = parse_spec_text(VALID_M1_SPEC)
    assert spec.version == 1
    assert spec.experiment == "m1-nop"
    assert spec.agent.kind == "nop"
    assert spec.benchmark.kind == "local"
    assert spec.trials == 1
    assert {o.kind for o in spec.observers} == {"jsonl", "stdout"}


def test_rejects_unknown_top_level_key():
    bad = VALID_M1_SPEC + "unknown_key: foo\n"
    with pytest.raises(SpecError) as ei:
        parse_spec_text(bad)
    assert "unknown_key" in str(ei.value)


def test_rejects_missing_required_version():
    no_version = "\n".join(l for l in VALID_M1_SPEC.splitlines() if not l.startswith("version:"))
    with pytest.raises(SpecError) as ei:
        parse_spec_text(no_version)
    assert "version" in str(ei.value)
```

- [ ] **Step 3: Run test, confirm red**

```bash
uv run pytest tests/unit/test_spec_parse.py -v
```

Expected: ImportError on `razorback.errors` / `razorback.spec.parse`.

- [ ] **Step 4: Implement `errors.py`**

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

- [ ] **Step 5: Implement `spec/schema.py`**

```python
# ABOUTME: Pydantic schema for the M1 subset of the razorback spec.
# ABOUTME: Top-level forbids unknown keys; future milestones extend agent/benchmark blocks.

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str


class BenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    task_paths: list[Path] = Field(default_factory=list)


class ObserverBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["jsonl", "stdout"]
    path: str | None = None


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    experiment: str
    agent: AgentBlock
    benchmark: BenchmarkBlock
    trials: int = 1
    observers: list[ObserverBlock] = Field(default_factory=list)
```

- [ ] **Step 6: Implement `spec/parse.py`**

```python
# ABOUTME: YAML → razorback Spec parser. Raises SpecError on invalid specs.
# ABOUTME: Wraps pydantic ValidationError into a typed razorback error.

from pathlib import Path

import yaml
from pydantic import ValidationError

from razorback.errors import SpecError
from razorback.spec.schema import Spec


def parse_spec_text(text: str) -> Spec:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecError(f"invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SpecError("spec must be a YAML mapping")
    try:
        return Spec.model_validate(raw)
    except ValidationError as exc:
        raise SpecError(str(exc)) from exc


def parse_spec_file(path: Path) -> Spec:
    return parse_spec_text(Path(path).read_text())
```

Also write `src/razorback/spec/__init__.py`:

```python
# ABOUTME: Spec parsing and schema for razorback.
# ABOUTME: Re-exports parse_spec_file and the Spec model.

from razorback.spec.parse import parse_spec_file, parse_spec_text
from razorback.spec.schema import Spec

__all__ = ["Spec", "parse_spec_file", "parse_spec_text"]
```

- [ ] **Step 7: Run test, confirm green**

```bash
uv run pytest tests/unit/test_spec_parse.py -v
```

Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add src/razorback/errors.py src/razorback/spec tests/__init__.py tests/unit/__init__.py tests/conftest.py tests/unit/test_spec_parse.py
git commit -m "m1: spec schema and parser with extra=forbid (§5)"
```

---

## Task 3: Frozen-spec writer (M1 partial freeze)

§3.2 reserves full provenance resolution for M5. M1 writes a faithful echo plus razorback's `version: 1` envelope (already required by the input schema). Per AC-3, `diff` between input and frozen shows only razorback's additions; M1 materializes no defaults beyond what the parser already filled in, so for M1 the freeze is structurally identical to the parsed spec re-emitted in canonical key order.

**Files:**
- Create: `src/razorback/spec/freeze.py`
- Create: `tests/unit/test_freeze.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_freeze.py`:

```python
# ABOUTME: Unit tests for the M1 frozen-spec writer.
# ABOUTME: M1 freeze is a faithful echo plus razorback's envelope; no provenance yet.

import yaml

from razorback.spec.freeze import freeze_spec
from razorback.spec.parse import parse_spec_text


SPEC = """\
version: 1
experiment: m1-nop
agent:
  kind: nop
benchmark:
  kind: local
  task_paths:
    - examples/tasks/hello-world
trials: 1
observers:
  - kind: stdout
"""


def test_freeze_round_trips_input_keys():
    spec = parse_spec_text(SPEC)
    frozen_text = freeze_spec(spec)
    frozen = yaml.safe_load(frozen_text)
    assert frozen["version"] == 1
    assert frozen["experiment"] == "m1-nop"
    assert frozen["agent"]["kind"] == "nop"
    assert frozen["benchmark"]["kind"] == "local"
    assert frozen["benchmark"]["task_paths"] == ["examples/tasks/hello-world"]
    assert frozen["trials"] == 1
    assert frozen["observers"] == [{"kind": "stdout", "path": None}]


def test_freeze_is_deterministic():
    spec = parse_spec_text(SPEC)
    assert freeze_spec(spec) == freeze_spec(spec)
```

- [ ] **Step 2: Run test, confirm red**

```bash
uv run pytest tests/unit/test_freeze.py -v
```

Expected: ImportError on `razorback.spec.freeze`.

- [ ] **Step 3: Implement `spec/freeze.py`**

```python
# ABOUTME: M1 frozen-spec writer — echoes the parsed spec deterministically.
# ABOUTME: Full provenance resolution is deferred to M5 per design §3.2 / §6.4.

import yaml

from razorback.spec.schema import Spec


def freeze_spec(spec: Spec) -> str:
    """Return the canonical YAML for a parsed spec.

    M1 freeze is a faithful echo: it serializes the pydantic model
    in field-declaration order with all defaults materialized. Sort
    keys is intentionally False — the model already pins key order.
    Deterministic output is required for sha256-based job_name (§6.7).
    """
    return yaml.safe_dump(
        spec.model_dump(mode="json"),
        sort_keys=False,
        default_flow_style=False,
    )
```

- [ ] **Step 4: Run test, confirm green**

```bash
uv run pytest tests/unit/test_freeze.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/spec/freeze.py tests/unit/test_freeze.py
git commit -m "m1: frozen-spec writer (faithful echo; provenance deferred to M5)"
```

---

## Task 4: `job_name` derivation — `sha256(frozen)[:16]`

**Files:**
- Modify: `src/razorback/spec/freeze.py` (add `derive_job_name`)
- Create: `tests/unit/test_job_name.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_job_name.py`:

```python
# ABOUTME: Unit test for content-derived job_name (§6.7).
# ABOUTME: job_name = sha256(frozen-spec-bytes)[:16].

import hashlib

from razorback.spec.freeze import derive_job_name, freeze_spec
from razorback.spec.parse import parse_spec_text


SPEC = """\
version: 1
experiment: m1-nop
agent:
  kind: nop
benchmark:
  kind: local
"""


def test_job_name_is_sha256_prefix_of_frozen_text():
    spec = parse_spec_text(SPEC)
    frozen = freeze_spec(spec)
    expected = hashlib.sha256(frozen.encode("utf-8")).hexdigest()[:16]
    assert derive_job_name(frozen) == expected
    assert len(derive_job_name(frozen)) == 16


def test_different_specs_produce_different_job_names():
    spec_a = parse_spec_text(SPEC)
    spec_b = parse_spec_text(SPEC.replace("m1-nop", "m1-nop-2"))
    assert derive_job_name(freeze_spec(spec_a)) != derive_job_name(freeze_spec(spec_b))
```

- [ ] **Step 2: Run test, confirm red**

```bash
uv run pytest tests/unit/test_job_name.py -v
```

Expected: ImportError on `derive_job_name`.

- [ ] **Step 3: Extend `spec/freeze.py`**

Append to the bottom of `src/razorback/spec/freeze.py`:

```python
import hashlib


def derive_job_name(frozen_text: str) -> str:
    """Content-derived job_name per §6.7: sha256(frozen)[:16] hex."""
    return hashlib.sha256(frozen_text.encode("utf-8")).hexdigest()[:16]
```

- [ ] **Step 4: Run test, confirm green**

```bash
uv run pytest tests/unit/test_job_name.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/spec/freeze.py tests/unit/test_job_name.py
git commit -m "m1: derive_job_name = sha256(frozen)[:16] (§6.7)"
```

---

## Task 5: Manifest writer — `run_dir_version: 1`, `created_at` ISO 8601

**Files:**
- Create: `src/razorback/manifest.py`
- Create: `tests/unit/test_manifest.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_manifest.py`:

```python
# ABOUTME: Unit tests for the run-level manifest writer (§3.3, §6.7).
# ABOUTME: Validates run_dir_version: 1 and ISO 8601 created_at with timezone.

import json
import re
from datetime import datetime

from razorback.manifest import RUN_DIR_VERSION, write_manifest


def test_manifest_has_run_dir_version_1(colima_safe_tmp_path):
    out = colima_safe_tmp_path / "manifest.json"
    write_manifest(out, experiment="m1-nop", job_name="abc1234567890def")
    data = json.loads(out.read_text())
    assert data["run_dir_version"] == 1
    assert RUN_DIR_VERSION == 1


def test_manifest_created_at_is_iso8601_with_tz(colima_safe_tmp_path):
    out = colima_safe_tmp_path / "manifest.json"
    write_manifest(out, experiment="m1-nop", job_name="abc1234567890def")
    data = json.loads(out.read_text())
    # ISO 8601 with timezone (Z or ±HH:MM)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$", data["created_at"])
    parsed = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


def test_manifest_records_experiment_and_job_name(colima_safe_tmp_path):
    out = colima_safe_tmp_path / "manifest.json"
    write_manifest(out, experiment="m1-nop", job_name="abc1234567890def")
    data = json.loads(out.read_text())
    assert data["experiment"] == "m1-nop"
    assert data["job_name"] == "abc1234567890def"
```

- [ ] **Step 2: Run test, confirm red**

```bash
uv run pytest tests/unit/test_manifest.py -v
```

Expected: ImportError on `razorback.manifest`.

- [ ] **Step 3: Implement `manifest.py`**

```python
# ABOUTME: Run-level manifest writer. The run_dir_version pins the public contract.
# ABOUTME: See design §3.3 (stability promise) and §6.7 (created_at semantics).

import json
from datetime import datetime, timezone
from pathlib import Path

RUN_DIR_VERSION = 1


def write_manifest(path: Path, *, experiment: str, job_name: str) -> None:
    payload = {
        "run_dir_version": RUN_DIR_VERSION,
        "experiment": experiment,
        "job_name": job_name,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")
```

- [ ] **Step 4: Run test, confirm green**

```bash
uv run pytest tests/unit/test_manifest.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/manifest.py tests/unit/test_manifest.py
git commit -m "m1: manifest writer with run_dir_version: 1 and ISO 8601 created_at"
```

---

## Task 6: CLI plumbing — `rk run` exit codes (no harbor call yet)

This task wires up Typer such that `rk run <bad-spec>` exits 10 with a `SpecError`. AC-7's CLI half lands here; the live harbor path comes in Task 12.

**Files:**
- Modify: `src/razorback/cli/__init__.py`
- Create: `src/razorback/cli/run.py`
- Create: `tests/unit/test_cli_exit_codes.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_cli_exit_codes.py`:

```python
# ABOUTME: Tests that the CLI maps razorback typed errors to documented exit codes.
# ABOUTME: AC-7: unknown top-level key → SpecError → exit code 10.

from typer.testing import CliRunner

from razorback.cli import app


def test_unknown_top_level_key_exits_10(colima_safe_tmp_path):
    bad = colima_safe_tmp_path / "bad.yaml"
    bad.write_text(
        "version: 1\nexperiment: x\nagent:\n  kind: nop\nbenchmark:\n  kind: local\nunknown_key: foo\n"
    )
    res = CliRunner(mix_stderr=False).invoke(app, ["run", str(bad)])
    assert res.exit_code == 10, res.stderr or res.stdout


def test_missing_spec_file_exits_2(colima_safe_tmp_path):
    res = CliRunner(mix_stderr=False).invoke(app, ["run", str(colima_safe_tmp_path / "nope.yaml")])
    assert res.exit_code == 2, res.stderr or res.stdout
```

- [ ] **Step 2: Run test, confirm red**

```bash
uv run pytest tests/unit/test_cli_exit_codes.py -v
```

Expected: `run` command does not exist on `app`; exit code is 2 with "No such command".

- [ ] **Step 3: Implement `cli/run.py`**

```python
# ABOUTME: `rk run` Typer command. M1: parse spec, freeze, run harbor, write run-dir.
# ABOUTME: Maps razorback typed errors to documented exit codes (§3.2).

from pathlib import Path

import typer

from razorback.errors import ExitCode, RazorbackError, SpecError
from razorback.spec.parse import parse_spec_file


def run_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    runs_dir: Path = typer.Option(Path("_runs"), "--runs-dir", help="Base directory for run-dirs."),
) -> None:
    """Execute a frozen spec against harbor and write a run-dir."""
    try:
        spec = parse_spec_file(spec_path)
    except SpecError as exc:
        typer.echo(f"SpecError: {exc}", err=True)
        raise typer.Exit(ExitCode.SPEC_ERROR)
    # Task 12 fills in the rest. For now, stop here so AC-7 lands.
    from razorback.run import execute_run

    try:
        execute_run(spec=spec, runs_dir=runs_dir)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
```

- [ ] **Step 4: Wire up `cli/__init__.py`**

Replace the body of `src/razorback/cli/__init__.py` with:

```python
# ABOUTME: Typer application root for the `rk` binary.
# ABOUTME: Subcommands attach here; M1 wires up `rk run` only.

import typer

from razorback.cli.run import run_command

app = typer.Typer(help="Razorback: a benchmark runner for agentic research workflows.")
app.command("run")(run_command)
```

- [ ] **Step 5: Create a stub `src/razorback/run.py`** so the import in `cli/run.py` resolves (Task 12 fills the body)

```python
# ABOUTME: Run orchestrator — wires spec → freeze → harbor → drainer → run-dir.
# ABOUTME: Stubbed in Task 6; the live harbor call lands in Task 12.

from pathlib import Path

from razorback.errors import RazorbackError
from razorback.spec.schema import Spec


def execute_run(*, spec: Spec, runs_dir: Path) -> None:
    raise RazorbackError("execute_run not implemented yet — see Task 12")
```

- [ ] **Step 6: Run test, confirm green**

```bash
uv run pytest tests/unit/test_cli_exit_codes.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add src/razorback/cli src/razorback/run.py tests/unit/test_cli_exit_codes.py
git commit -m "m1: rk run CLI plumbing — SpecError → exit 10 (§3.2)"
```

---

## Task 7: Author `examples/specs/nop.yaml`

**Files:**
- Create: `examples/specs/nop.yaml`

- [ ] **Step 1: Write the M1 acceptance spec**

```yaml
# ABOUTME comment is invalid inside YAML's significant-whitespace top-level; omit.
version: 1
experiment: m1-nop
agent:
  kind: nop
benchmark:
  kind: local
  task_paths:
    - examples/tasks/hello-world
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

(Plain YAML; no ABOUTME header — CL's rule applies to source files, not data files.)

- [ ] **Step 2: Smoke-parse it**

```bash
uv run python -c "from razorback.spec.parse import parse_spec_file; print(parse_spec_file('examples/specs/nop.yaml'))"
```

Expected: prints a populated `Spec(...)` repr without raising.

- [ ] **Step 3: Commit**

```bash
git add examples/specs/nop.yaml
git commit -m "m1: examples/specs/nop.yaml — acceptance input"
```

---

## Task 8: Single-writer channel + drainer for observers

**Files:**
- Create: `src/razorback/observers/__init__.py`
- Create: `src/razorback/observers/channel.py`
- Create: `src/razorback/observers/jsonl.py`
- Create: `src/razorback/observers/stdout.py`
- Create: `tests/unit/test_channel_drainer.py`

§6.6: hooks fire on harbor's loop and write into a single buffered channel; one drainer coroutine reads from it and dispatches to observers. Concurrent direct writes to the JSONL file are forbidden.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_channel_drainer.py`:

```python
# ABOUTME: Unit tests for the single-writer event channel and observers (§6.6).
# ABOUTME: Concurrent producers serialize through the drainer without interleaving.

import asyncio
import json

import pytest

from razorback.observers.channel import EventChannel
from razorback.observers.jsonl import JsonlObserver
from razorback.observers.stdout import StdoutObserver


@pytest.mark.asyncio
async def test_drainer_serializes_concurrent_writes(colima_safe_tmp_path, capsys):
    path = colima_safe_tmp_path / "events.jsonl"
    ch = EventChannel()
    ch.add_observer(JsonlObserver(path))
    ch.add_observer(StdoutObserver())

    drain_task = asyncio.create_task(ch.drain())

    async def producer(tag: str, n: int) -> None:
        for i in range(n):
            await ch.publish({"event": tag, "i": i})

    await asyncio.gather(producer("a", 50), producer("b", 50))
    await ch.aclose()
    await drain_task

    lines = path.read_text().splitlines()
    assert len(lines) == 100
    for line in lines:
        # No partial / interleaved writes — every line parses.
        json.loads(line)
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 100


@pytest.mark.asyncio
async def test_drainer_preserves_fire_order(colima_safe_tmp_path):
    path = colima_safe_tmp_path / "events.jsonl"
    ch = EventChannel()
    ch.add_observer(JsonlObserver(path))
    drain_task = asyncio.create_task(ch.drain())

    for i in range(20):
        await ch.publish({"event": "x", "i": i})
    await ch.aclose()
    await drain_task

    seen = [json.loads(l)["i"] for l in path.read_text().splitlines()]
    assert seen == list(range(20))
```

- [ ] **Step 2: Run test, confirm red**

```bash
uv run pytest tests/unit/test_channel_drainer.py -v
```

Expected: ImportError on `razorback.observers.*`.

- [ ] **Step 3: Implement `observers/channel.py`**

```python
# ABOUTME: Single-writer asyncio channel for trial events; one drainer fans out to observers.
# ABOUTME: §6.6 — concurrent direct writes to event sinks are forbidden.

import asyncio
from typing import Protocol


class Observer(Protocol):
    async def on_event(self, payload: dict) -> None: ...
    async def aclose(self) -> None: ...


class EventChannel:
    """A bounded async queue + drainer that fans out to registered observers."""

    _SENTINEL = object()

    def __init__(self, maxsize: int = 1024) -> None:
        self._q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._observers: list[Observer] = []
        self._closed = False

    def add_observer(self, observer: Observer) -> None:
        self._observers.append(observer)

    async def publish(self, payload: dict) -> None:
        if self._closed:
            raise RuntimeError("EventChannel is closed")
        await self._q.put(payload)

    async def aclose(self) -> None:
        self._closed = True
        await self._q.put(self._SENTINEL)

    async def drain(self) -> None:
        while True:
            item = await self._q.get()
            if item is self._SENTINEL:
                break
            for obs in self._observers:
                await obs.on_event(item)
        for obs in self._observers:
            await obs.aclose()
```

- [ ] **Step 4: Implement `observers/jsonl.py`**

```python
# ABOUTME: JSONL observer — appends one JSON object per event to a file.
# ABOUTME: Single-writer per §6.6; the drainer is the only caller.

import json
from pathlib import Path


class JsonlObserver:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("a", buffering=1)  # line-buffered

    async def on_event(self, payload: dict) -> None:
        self._fh.write(json.dumps(payload, default=str) + "\n")

    async def aclose(self) -> None:
        self._fh.close()
```

- [ ] **Step 5: Implement `observers/stdout.py`**

```python
# ABOUTME: Stdout observer — prints one human-readable line per event.
# ABOUTME: Reads from the same channel as the JSONL observer (§6.6).

import sys


class StdoutObserver:
    async def on_event(self, payload: dict) -> None:
        event = payload.get("event", "?")
        trial = payload.get("trial_id", "")
        task = payload.get("task_name", "")
        sys.stdout.write(f"[{event}] trial={trial} task={task}\n")
        sys.stdout.flush()

    async def aclose(self) -> None:
        pass
```

Also write `observers/__init__.py`:

```python
# ABOUTME: Razorback observers package — channel and built-in jsonl/stdout sinks.
# ABOUTME: All observers are async; sync code reaches them via asyncio.to_thread.

from razorback.observers.channel import EventChannel, Observer
from razorback.observers.jsonl import JsonlObserver
from razorback.observers.stdout import StdoutObserver

__all__ = ["EventChannel", "Observer", "JsonlObserver", "StdoutObserver"]
```

- [ ] **Step 6: Run test, confirm green**

```bash
uv run pytest tests/unit/test_channel_drainer.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add src/razorback/observers tests/unit/test_channel_drainer.py
git commit -m "m1: single-writer event channel + jsonl/stdout observers (§6.6)"
```

---

## Task 9: Spec → harbor `JobConfig` translator (`compat/harbor_0_6_6.py`)

**Files:**
- Create: `src/razorback/compat/__init__.py`
- Create: `src/razorback/compat/harbor_0_6_6.py`

This is a small focused module today; M2+ extend it. The translator is pure (no side effects), so a unit test pinning the produced `JobConfig` is sufficient.

- [ ] **Step 1: Write the failing test**

Add a new test file `tests/unit/test_compat_translator.py`:

```python
# ABOUTME: Unit tests for spec → harbor JobConfig translation (§6.1).
# ABOUTME: Pins the M1-supported subset; future milestones extend the translator.

from pathlib import Path

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig

from razorback.compat.harbor_0_6_6 import spec_to_job_config
from razorback.spec.parse import parse_spec_text


SPEC = """\
version: 1
experiment: m1-nop
agent:
  kind: nop
benchmark:
  kind: local
  task_paths:
    - examples/tasks/hello-world
trials: 1
observers: []
"""


def test_translator_produces_runnable_job_config(colima_safe_tmp_path):
    spec = parse_spec_text(SPEC)
    cfg = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=colima_safe_tmp_path / "jobs",
    )
    assert isinstance(cfg, JobConfig)
    assert cfg.job_name == "abc1234567890def"
    assert cfg.jobs_dir == colima_safe_tmp_path / "jobs"
    assert cfg.n_concurrent_trials == 1
    assert cfg.n_attempts == 1
    assert len(cfg.agents) == 1
    assert cfg.agents[0].name == AgentName.NOP.value
    assert len(cfg.tasks) == 1
    assert Path(cfg.tasks[0].path).name == "hello-world"
    # M1 wants the verifier on (Task 1 proved the contract).
    assert cfg.verifier.disable is False
```

- [ ] **Step 2: Run test, confirm red**

```bash
uv run pytest tests/unit/test_compat_translator.py -v
```

Expected: ImportError on `razorback.compat.harbor_0_6_6`.

- [ ] **Step 3: Implement the translator**

`src/razorback/compat/harbor_0_6_6.py`:

```python
# ABOUTME: Spec → harbor 0.6.6 JobConfig translator (§6.1).
# ABOUTME: M1 supports agent.kind=nop and benchmark.kind=local only.

from pathlib import Path

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig
from harbor.models.trial.config import AgentConfig, TaskConfig, VerifierConfig

from razorback.errors import SpecError
from razorback.spec.schema import Spec


def spec_to_job_config(spec: Spec, *, job_name: str, jobs_dir: Path) -> JobConfig:
    if spec.agent.kind != "nop":
        raise SpecError(f"M1 only supports agent.kind=nop, got {spec.agent.kind!r}")
    if spec.benchmark.kind != "local":
        raise SpecError(f"M1 only supports benchmark.kind=local, got {spec.benchmark.kind!r}")

    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[AgentConfig(name=AgentName.NOP.value)],
        tasks=[TaskConfig(path=Path(p).resolve()) for p in spec.benchmark.task_paths],
        verifier=VerifierConfig(disable=False),
    )
```

`src/razorback/compat/__init__.py`:

```python
# ABOUTME: Per-harbor-minor translation layer (§6.1).
# ABOUTME: razorback pins harbor 0.6.6; this package gains a module per supported minor.

from razorback.compat.harbor_0_6_6 import spec_to_job_config

__all__ = ["spec_to_job_config"]
```

- [ ] **Step 4: Run test, confirm green**

```bash
uv run pytest tests/unit/test_compat_translator.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/compat tests/unit/test_compat_translator.py
git commit -m "m1: spec → harbor 0.6.6 JobConfig translator (§6.1)"
```

---

## Task 10: Wire the run orchestrator end-to-end (`razorback.run`)

**Files:**
- Modify: `src/razorback/run.py` (replace the stub)

The orchestrator is the only place the moving parts compose. It is small and integration-shaped; the AC-1..AC-8 end-to-end test in Task 12 drives it. There is no unit test here — it would only exercise mocks.

- [ ] **Step 1: Implement `run.py`**

Replace the stub body with:

```python
# ABOUTME: Run orchestrator — spec → freeze → harbor Job → drainer → run-dir.
# ABOUTME: The acceptance path: matches the §6.3 layout end-to-end.

import asyncio
import json
from pathlib import Path

from harbor.job import Job
from harbor.models.trial.config import VerifierConfig
from harbor.trial.hooks import TrialEvent, TrialHookEvent

from razorback.compat import spec_to_job_config
from razorback.errors import RazorbackError, ExitCode
from razorback.manifest import write_manifest
from razorback.observers import EventChannel, JsonlObserver, StdoutObserver
from razorback.spec.freeze import derive_job_name, freeze_spec
from razorback.spec.schema import Spec


class HarborRuntimeError(RazorbackError):
    exit_code: int = ExitCode.HARBOR_RUNTIME


def execute_run(*, spec: Spec, runs_dir: Path) -> None:
    """Synchronous entry point invoked by the CLI."""
    asyncio.run(_execute_run_async(spec=spec, runs_dir=runs_dir))


async def _execute_run_async(*, spec: Spec, runs_dir: Path) -> None:
    frozen_text = freeze_spec(spec)
    job_name = derive_job_name(frozen_text)

    run_dir = Path(runs_dir).resolve() / spec.experiment / job_name
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "spec.frozen.yaml").write_text(frozen_text)
    write_manifest(run_dir / "manifest.json", experiment=spec.experiment, job_name=job_name)

    channel = EventChannel()
    for obs_block in spec.observers:
        if obs_block.kind == "jsonl":
            channel.add_observer(JsonlObserver(run_dir / (obs_block.path or "events.jsonl")))
        elif obs_block.kind == "stdout":
            channel.add_observer(StdoutObserver())

    job_config = spec_to_job_config(spec, job_name=job_name, jobs_dir=run_dir.parent)

    # Harbor places its lock.json under jobs_dir/<job_name>/. Our run_dir
    # *is* that path, so harbor's lock.json lands at run_dir/lock.json
    # without any extra plumbing (§6.3 row 6).

    drain_task = asyncio.create_task(channel.drain())

    try:
        job = await Job.create(job_config)
        for event in TrialEvent:
            job.add_hook(event, _hook_publisher(channel, event))
        try:
            result = await job.run()
        except Exception as exc:  # harbor's asyncio crash path
            (run_dir / "crash.json").write_text(json.dumps({"error": str(exc)}, indent=2))
            raise HarborRuntimeError(f"harbor run failed: {exc}") from exc
    finally:
        await channel.aclose()
        await drain_task

    summary = {
        "experiment": spec.experiment,
        "job_name": job_name,
        "n_total_trials": result.n_total_trials,
        "n_completed_trials": result.stats.n_completed_trials,
        "n_errored_trials": result.stats.n_errored_trials,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def _hook_publisher(channel: EventChannel, event: TrialEvent):
    async def _publish(hook_event: TrialHookEvent) -> None:
        await channel.publish({
            "event": event.value,
            "trial_id": hook_event.trial_id,
            "task_name": hook_event.task_name,
            "timestamp": hook_event.timestamp.isoformat(),
        })
    return _publish
```

- [ ] **Step 2: Sanity-import**

```bash
uv run python -c "from razorback.run import execute_run; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/razorback/run.py
git commit -m "m1: run orchestrator — spec → freeze → harbor → drainer → run-dir"
```

---

## Task 11: Integration test — `rk run examples/specs/nop.yaml` end-to-end (AC-1..AC-8)

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_rk_run_nop.py`

This test is the AC harness. It runs the CLI as a subprocess against the checked-in `examples/specs/nop.yaml`, then asserts every AC from a single run-dir.

- [ ] **Step 1: Write the failing integration test**

```python
# ABOUTME: End-to-end test for `rk run examples/specs/nop.yaml`.
# ABOUTME: Asserts AC-1 through AC-8 against a single live run-dir.

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "examples" / "specs" / "nop.yaml"


@pytest.fixture
def runs_root(colima_safe_tmp_path):
    return colima_safe_tmp_path / "_runs"


def test_rk_run_nop_end_to_end(runs_root):
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SPEC), "--runs-dir", str(runs_root)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    # AC-1: exit 0.
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    # AC-1: a single run-dir under _runs/m1-nop/<job_name>/.
    experiment_dir = runs_root / "m1-nop"
    run_dirs = list(experiment_dir.iterdir())
    assert len(run_dirs) == 1, run_dirs
    run_dir = run_dirs[0]

    # AC-2: §6.3 layout at the top level.
    for name in ("spec.frozen.yaml", "manifest.json", "events.jsonl", "summary.json", "lock.json"):
        assert (run_dir / name).is_file(), f"missing {name} in {run_dir}"

    # AC-2: per-trial layout.
    trial_dirs = [p for p in run_dir.iterdir() if p.is_dir() and p.name != "trials"]
    # harbor 0.6.6 places trials directly under run_dir; check at least one trial dir exists.
    candidates = [p for p in run_dir.iterdir() if p.is_dir()]
    trial_dir = next(p for p in candidates if (p / "config.json").exists())
    for name in ("config.json", "result.json", "agent", "verifier", "artifacts"):
        assert (trial_dir / name).exists(), f"missing {name} in {trial_dir}"

    # AC-3: spec.frozen.yaml is a faithful echo (input bytes appear in frozen text).
    frozen_text = (run_dir / "spec.frozen.yaml").read_text()
    assert "experiment: m1-nop" in frozen_text
    assert "kind: nop" in frozen_text
    assert "kind: local" in frozen_text

    # AC-4: manifest.json carries run_dir_version: 1 and ISO 8601 created_at.
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["run_dir_version"] == 1
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", manifest["created_at"])
    datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))

    # AC-5: events.jsonl rows; each is valid JSON; chronological canonical events present.
    lines = (run_dir / "events.jsonl").read_text().splitlines()
    assert lines, "events.jsonl is empty"
    parsed = [json.loads(l) for l in lines]
    events_in_order = [p["event"] for p in parsed]
    for required in ("start", "environment_start", "agent_start", "end"):
        assert required in events_in_order, events_in_order
    assert events_in_order.index("start") < events_in_order.index("end")

    # AC-6: job_name == sha256(frozen)[:16].
    expected_jn = hashlib.sha256(frozen_text.encode("utf-8")).hexdigest()[:16]
    assert run_dir.name == expected_jn

    # AC-8: stdout has one line per fired event (run via subprocess; capture).
    stdout_event_lines = [l for l in result.stdout.splitlines() if l.startswith("[")]
    stdout_events = [re.match(r"\[(\w+)\]", l).group(1) for l in stdout_event_lines]
    assert stdout_events == events_in_order

    # AC-1 (verifier): summary records n_errored_trials == 0.
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["n_errored_trials"] == 0
    assert summary["n_completed_trials"] >= 1
```

- [ ] **Step 2: Run test, expect green (or surface what's missing)**

```bash
uv run pytest tests/integration/test_rk_run_nop.py -v -s
```

Expected on first run: PASS. If it fails, the failure is a real M1 bug — fix the orchestrator, not the test.

Known issues to watch for:
- `events.jsonl` is shorter than expected. The hook callback may have raised before publishing. Re-run with `-s` and read the stdout for hook-callback errors.
- `lock.json` missing. Means harbor wrote it elsewhere; double-check `jobs_dir` math in `run.py` (it must equal `runs_root / spec.experiment`).
- Verifier failed. `n_errored_trials > 0`. Re-check Task 1's smoke; the standalone smoke and the orchestrated path should produce the same verifier outcome.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_rk_run_nop.py
git commit -m "m1: integration test — rk run examples/specs/nop.yaml AC-1..AC-8"
```

---

## Task 12: AC-7 CLI half — confirm exit code 10 against the live CLI

Task 6 already covers the unit-level case via `CliRunner`. AC-7 explicitly mentions "the CLI exits with code 10 when fed the same spec". Add a tiny subprocess assertion so we exercise the full Typer→exit-code path.

**Files:**
- Modify: `tests/integration/test_rk_run_nop.py` (append)

- [ ] **Step 1: Append the subprocess assertion**

Add to `tests/integration/test_rk_run_nop.py`:

```python
def test_rk_run_unknown_top_level_key_exits_10(colima_safe_tmp_path):
    bad = colima_safe_tmp_path / "bad.yaml"
    bad.write_text(
        "version: 1\nexperiment: x\nagent:\n  kind: nop\nbenchmark:\n  kind: local\nunknown_key: foo\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(bad)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 10, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "SpecError" in result.stderr
```

- [ ] **Step 2: Run test, confirm green**

```bash
uv run pytest tests/integration/test_rk_run_nop.py -v -s
```

Expected: both integration tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_rk_run_nop.py
git commit -m "m1: AC-7 CLI half — subprocess assertion on exit code 10"
```

---

## Task 13: Make `python -m razorback.cli` work

Task 11's subprocess invokes the CLI as `python -m razorback.cli`. Typer apps with `app = Typer(...)` need a `__main__.py` (or an `if __name__ == "__main__"` block in `__init__.py`) for the `-m` invocation to call `app()`.

**Files:**
- Modify: `src/razorback/cli/__init__.py` (append) OR create `src/razorback/cli/__main__.py`

- [ ] **Step 1: Create `src/razorback/cli/__main__.py`**

```python
# ABOUTME: Allows `python -m razorback.cli ...` to invoke the Typer app.
# ABOUTME: Used by the integration test harness.

from razorback.cli import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Smoke-run**

```bash
uv run python -m razorback.cli --help
uv run rk --help
```

Both must succeed and list the `run` command.

- [ ] **Step 3: Commit**

```bash
git add src/razorback/cli/__main__.py
git commit -m "m1: razorback.cli __main__ for python -m invocation"
```

---

## Task 14: Final acceptance — run the §8.M1 command from a clean checkout

This is the validator's rerun command. It's the same command Task 11 invokes via subprocess; running it interactively confirms human-readable output works.

**Files:** none.

- [ ] **Step 1: Run the acceptance command**

```bash
uv run rk run examples/specs/nop.yaml
```

Expected:
- Exit code 0 (`echo $?` confirms).
- Stdout contains one bracketed line per fired event in fire order.
- `_runs/m1-nop/<job_name>/` exists with `spec.frozen.yaml`, `manifest.json`, `events.jsonl`, `summary.json`, `lock.json`, and one `trials/<task>-NNNN/` (or single-trial dir) with `config.json`, `result.json`, `agent/`, `verifier/`, `artifacts/`.

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all tests green. Pristine output — no warnings about unexpected `pydantic` deprecations, no asyncio "coroutine was never awaited" lines. Per CL's rules, "test output MUST BE PRISTINE TO PASS".

- [ ] **Step 3: No commit (acceptance run only)**

---

## Task 15: Cross-reference plan from the M1 entity body

**Files:**
- Modify: `docs/razorback-implementation/m1-rk-run-nop.md` — Test plan section only

- [ ] **Step 1: Append a single cross-reference line to the Test plan section**

Locate the `## Test plan` section in `docs/razorback-implementation/m1-rk-run-nop.md`. After the `Acceptance command` bullet, append exactly:

```
- **Implementation plan:** `docs/razorback-implementation/plans/m1-rk-run-nop.md`.
```

Do not change the frontmatter; do not rewrite the Test plan section; do not paraphrase the existing bullets.

- [ ] **Step 2: Commit**

```bash
git add docs/razorback-implementation/m1-rk-run-nop.md
git commit -m "m1: cross-reference implementation plan from entity Test plan"
```

---

## Self-review notes

- **Spec coverage:** AC-1 (Tasks 1, 6, 10, 11), AC-2 (Tasks 1, 10, 11), AC-3 (Tasks 3, 7, 11), AC-4 (Task 5, asserted in 11), AC-5 (Tasks 8, 10, 11), AC-6 (Tasks 4, 10, 11), AC-7 (Tasks 2, 6, 12), AC-8 (Tasks 8, 10, 11). Every AC is implemented by at least one task and asserted by at least one test.
- **Riskiest contract first:** Task 1 — verifier `reward.txt` under Colima — precedes every scaffolding task. If that breaks, no later task lands.
- **No placeholders:** every step shows the file contents, the command, and the expected outcome.
- **Type consistency:** `spec_to_job_config(spec, *, job_name, jobs_dir)`, `derive_job_name(frozen_text)`, `freeze_spec(spec)`, `write_manifest(path, *, experiment, job_name)`, `EventChannel.publish/aclose/drain`, `JsonlObserver(path)`, `StdoutObserver()`, `execute_run(*, spec, runs_dir)` are used consistently across tasks 2–14.
- **TDD discipline:** every behavior task (2, 3, 4, 5, 6, 8, 9, 11, 12) writes a failing test, runs it red, then makes it green. Tasks 1, 7, 10, 13, 14, 15 are scaffolding/mechanism/wiring/docs and do not require their own dedicated unit test (each is exercised by the test in a sibling task).
- **Commit cadence:** one focused commit per task, format `m1: <summary>`.
