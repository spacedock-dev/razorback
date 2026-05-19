# Validation — M1 — rk run against nop agent

Worktree branch: `spacedock-ensign/m1-rk-run-nop`
Tip commit at validation start: `8903521` (`m1: stage report — implementation complete`)
Validator: fresh agent, did not write the implementation
Acceptance command (§8.M1): `uv run rk run examples/specs/nop.yaml`

## Reproduction summary

Both bottom-line claims in the implementation's stage report were
reproduced from a clean checkout of the worktree branch tip:

- `uv run pytest` → `17 passed in 14.19s` (15 unit + 2 integration)
- `uv run rk run examples/specs/nop.yaml` → exit code `0`,
  writes `_runs/m1-nop/2ad8314cc61b194f/` with the §6.3 layout
  (modulo one non-blocking finding — see §Code review)

The content-derived `job_name` is the same `2ad8314cc61b194f` the
implementation reported; only the per-trial random suffix
(`hello-world__yx8ea4o` / `hello-world__RabcPLv` across reruns)
varied between the validator's two acceptance runs, which is
expected harbor non-determinism for that field.

## AC verification

Each AC was reproduced verbatim against the worktree-branch run-dir
at `_runs/m1-nop/2ad8314cc61b194f/`.

### AC-1 — `rk run examples/specs/nop.yaml` exits 0 — PASS

Command: `uv run rk run examples/specs/nop.yaml`
Result: `EXIT=0`. A single run-dir at
`_runs/m1-nop/2ad8314cc61b194f/` is created.
`summary.json` records `n_completed_trials: 1`,
`n_errored_trials: 0`. The hello-world verifier wrote
`reward.txt` with content `1.0` (3B) under the trial subdir's
`verifier/`, confirming the M1 scope clause about
`reward.txt` reaching the host through Colima's bind mount.

### AC-2 — Run-dir layout matches §6.3 — PASS-WITH-NOTE

Top-level inventory (`ls _runs/m1-nop/2ad8314cc61b194f/`):

```
config.json   events.jsonl   hello-world__yx8ea4o/   job.log
lock.json     manifest.json  result.json             spec.frozen.yaml
summary.json
```

Required AC-2 top-level files all present:
`spec.frozen.yaml`, `manifest.json`, `events.jsonl`,
`summary.json`, `lock.json`.

Per-trial subdir inventory
(`ls _runs/m1-nop/2ad8314cc61b194f/hello-world__yx8ea4o/`):

```
agent/   artifacts/   config.json   result.json
trial.log   verifier/
```

Required per-trial members all present:
`config.json`, `result.json`, `agent/`, `verifier/`, `artifacts/`.

**Note (non-blocking, design vs harbor 0.6.6 reality):** §6.3 of the
design doc documents the per-trial subdir at
`trials/<task>-NNNN/`. Harbor 0.6.6 places trial dirs directly under
the run-dir (no `trials/` parent) and uses a `<task>__<suffix>`
naming pattern, not `<task>-NNNN`. The implementation acknowledges
this explicitly in `tests/integration/test_rk_run_nop.py:49`
("harbor 0.6.6 places trials directly under run_dir"). All the
files AC-2 enumerates exist and are reachable; the discrepancy is
between the design doc and harbor's emitted layout, not between the
ACs and the implementation. Tracking forward for M5/M6 is
appropriate — when `rk runs *` subcommands need to walk this
contract, either harbor 0.7+ aligns or razorback's compat layer
remaps. Not blocking for M1.

### AC-3 — `spec.frozen.yaml` is a faithful echo — PASS

`diff examples/specs/nop.yaml _runs/m1-nop/2ad8314cc61b194f/spec.frozen.yaml`
shows only:

1. YAML list-item indentation normalized (block-style emitted at
   the parent level).
2. `path: null` materialized on the stdout observer (a razorback
   default surfaced by pydantic `model_dump`).

These are exactly the "razorback writes" additions AC-3 admits.
Round-trip determinism is covered by `test_freeze_is_deterministic`
(unit) and the `job_name`'s sha256 stability across reruns.

### AC-4 — `manifest.json` has `run_dir_version: 1` and ISO 8601 `created_at` — PASS

```
$ jq '.run_dir_version, .created_at' _runs/m1-nop/2ad8314cc61b194f/manifest.json
1
"2026-05-19T07:45:11.131924Z"
$ python3 -c "from datetime import datetime; datetime.fromisoformat('2026-05-19T07:45:11.131924Z'.replace('Z','+00:00')); print('ISO 8601 OK')"
ISO 8601 OK
```

`run_dir_version` is `1` (int, not string) and `created_at` is a
UTC ISO 8601 string with a `Z` suffix that `datetime.fromisoformat`
parses cleanly.

### AC-5 — `events.jsonl` is one valid JSON object per fired hook, in fire order — PASS

```
$ wc -l _runs/m1-nop/2ad8314cc61b194f/events.jsonl
       5
$ jq -r '.event' _runs/m1-nop/2ad8314cc61b194f/events.jsonl
start
environment_start
agent_start
verification_start
end
```

5 lines, all parse as JSON
(`python3 -c "import json; [json.loads(l) for l in open(p)]"`).
The required canonical events are all present and in
chronological order; `verification_start` fires because the
verifier ran (AC-5 admits this).

### AC-6 — `job_name == sha256(frozen)[:16]` — PASS

```
$ shasum -a 256 _runs/m1-nop/2ad8314cc61b194f/spec.frozen.yaml | cut -c1-16
2ad8314cc61b194f
$ basename _runs/m1-nop/2ad8314cc61b194f
2ad8314cc61b194f
```

Note: AC-6's `Verified by:` clause names `sha256sum` (a GNU
coreutils tool that doesn't ship on macOS). On the operator's
machine (`darwin`), `shasum -a 256` produces the identical SHA-256
in the same format and is the standard substitute. The match is
exact.

### AC-7 — Unknown top-level key → `SpecError` and exit code 10 — PASS

CLI half (validator re-run):

```
$ uv run rk run /tmp/m1-validation/bad-spec.yaml; echo EXIT=$?
SpecError: 1 validation error for Spec
unknown_key
  Extra inputs are not permitted ...
EXIT=10
```

Parser half (test): `tests/unit/test_spec_parse.py::test_rejects_unknown_top_level_key`
exercises `parse_spec_text(unknown_key=...)` directly and asserts
`SpecError`. Passes as part of the 17/17 run.

### AC-8 — Stdout observer line-matches `events.jsonl` rows — PASS

```
$ diff <(jq -r '.event' _runs/m1-nop/2ad8314cc61b194f/events.jsonl) \
       <(grep -E '^\[' /tmp/m1-validation/ac8-stdout.txt | sed -E 's/^\[([a-z_]+)\].*/\1/')
$ echo $?
0
```

The stdout observer's `[event] trial=… task=…` lines, taken in
order, equal `events.jsonl`'s `.event` rows in order. Both
observers read from the same single-writer asyncio channel
(`src/razorback/observers/channel.py` — one `asyncio.Queue`,
one drainer coroutine, fan-out to N observers, §6.6 satisfied).

## Code review

Independent pass over the 35 changed files / 891 insertions on
`spacedock-ensign/m1-rk-run-nop` (commits `29eb878..8903521`,
13 atomic commits + the stage-report commit).

### Strengths

- TDD discipline is visible in the commit log — failing test
  lands before the implementation that makes it green
  (e.g. `m1: AC-7 CLI half — subprocess assertion on exit code 10`
  follows `m1: rk run CLI plumbing — SpecError → exit 10`).
- Riskiest-contract-first ordering: the mechanism smoke
  (`scripts/smoke_nop_verified.py`, commit `29eb878`) ran before
  any razorback module landed. The Colima/alpine bash-missing
  issue surfaced and was fixed at the task Dockerfile
  (`RUN apk add --no-cache bash`) — a one-line surface change,
  not a design re-think. Exactly the failure mode the plan
  expected; exactly the right place to fix it.
- Typed-error → exit-code map (`src/razorback/errors.py`) matches
  §3.2's documented table byte-for-byte.
- Single-writer event channel uses a sentinel-terminated
  `asyncio.Queue`; the drainer test covers both line-integrity
  under concurrent producers (50+50 publishers, 100 JSON-parseable
  lines, no interleaving) and fire-order preservation. This is the
  §6.6 contract.
- Schema rejects unknown keys at every level via
  `model_config = ConfigDict(extra="forbid")`, not just the
  top-level Spec.
- `colima_safe_tmp_path` fixture documents WHY (Colima bind-mount
  reach) and where (under `/Users/...`) in two lines. The fixture
  is well-named.
- `manifest.created_at` writes `Z`-suffixed UTC, which is what
  §6.7's "sort order" semantic needs to stay portable; the test
  asserts both the regex shape and round-trip parseability.

### Findings

No **blocking** findings.

Non-blocking observations (none required for M1 to gate to `done`,
but worth tracking for later milestones):

1. **§6.3 `trials/` parent absent.** Covered above under AC-2. The
   implementation accepts harbor 0.6.6's flat layout; the design
   doc documents `trials/<task>-NNNN/`. Either the design doc
   should be footnoted to acknowledge the harbor-emitted reality,
   or M5/M6's `rk runs *` subcommands need a compat shim that walks
   the actual layout. Not in scope for M1 but should not be
   forgotten.
2. **`ObserverBlock.kind` is `Literal["jsonl", "stdout"]`.** §6.6
   says "razorback rejects sync observers at spec validation".
   M1's allow-list makes this trivially true because both
   allow-listed kinds are async, but the design intent suggests an
   "is_async" check at registration time rather than a hard-coded
   literal. Defer to M3+ when custom agent kinds and (eventually)
   custom observers land.
3. **`run.py:60` writes `crash.json` on harbor failure but doesn't
   include it in the §6.3 layout contract.** If a harbor run
   crashes mid-trial, the run-dir gains a sibling file the
   contract doesn't describe. Minor — operators reading a tombstone
   probably appreciate the file existing — but consider whether
   `crash.json` deserves a manifest field or whether it lives under
   `logs/` for symmetry with harbor.
4. **`integration/test_rk_run_nop.py` AC-3 check is text-fragment
   only** (`"experiment: m1-nop" in frozen_text`). The validator's
   `diff` against the input is stricter and would have caught a
   regression where freeze emitted unrelated extras. Consider
   tightening, but not for M1 — the determinism unit test plus the
   sha256 job_name acts as a second tripwire.
5. **`run.py` imports `from razorback.run import execute_run`
   lazily inside `run_command`** to avoid loading harbor on the
   `--help` path. Comment-free; one ABOUTME line on why would help
   the next reader. Style nit, not behavior.

None of these block the gate. (1) is a contract conversation;
(2)–(5) are tracked-for-later polish.

## Gate decision

**PASSED** — proceed to `done`.

All 8 ACs reproduced verbatim against the worktree-branch tip from
a clean checkout. The §8.M1 acceptance command exits 0; the run-dir
contains the required artifacts; the sha256-derived job_name
matches; the stdout and jsonl observers line-match through the
single-writer channel; `n_errored_trials == 0`.

No blocking findings. The one design-vs-reality note (AC-2 /
§6.3's `trials/` parent absent in harbor 0.6.6's emission) is
explicitly acknowledged in the implementation's integration test
and is appropriate forward-tracking for M5/M6 rather than an M1
fix.
