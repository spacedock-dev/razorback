# PKG-26 — reshape `ClaudeCliAgent` to subclass harbor's `ClaudeCode` (close wrapper drift)

Entity: `docs/razorback-implementation/pkg26-use-harbor-claude-code-adapter.md`

## Context

Today `ClaudeCliAgent(BaseAgent)` is a 118-line wrapper around
`claude -p`. It discards stdout, never writes `claude-output.jsonl`,
never reports `total_cost_usd`, and parallels (instead of inheriting
from) harbor's upstream `ClaudeCode(BaseInstalledAgent)` (1155 lines).
The original intent was a subclass; PKG-26 corrects that.

Razorback overrides ONLY:
1. Co-mingled auth refusal (ANTHROPIC_API_KEY ⊕ CLAUDE_CODE_OAUTH_TOKEN).
2. `tools_allowed` (razorback name) → `allowed_tools` (harbor name).
3. `sampling_temperature` (razorback name) → not a harbor kwarg; honor
   `supported_sampling() == {"temperature"}` (refuse top_p / seed).
4. Razorback's `claude-cli` agent name (`name() == "claude-cli"`) is
   kept so AgentName + the spec discriminator stay stable.

Everything else (stream-json invocation, `_parse_total_cost_from_stream_json`
at claude_code.py:490, ATIF trajectory harvesting from
`<logs_dir>/sessions/projects/<task>/*.jsonl` at lines 161-202,
`populate_context_post_run` cost flow at line 913) is inherited.

## Surface map — what changes

| File | Change |
|---|---|
| `src/razorback/agents/claude_cli.py` | Subclass `ClaudeCode`; delegate `__init__` to `super().__init__()` after auth check + kwarg translation; drop ad-hoc `run()`/`setup()`/`version()` (now inherited). Keep `ClaudeCliAgentError`, `required_env()`, `supported_sampling()`, `name()`. |
| `tests/unit/test_claude_cli_subclasses_claude_code.py` *(new)* | RED then GREEN: `isinstance(ClaudeCliAgent(...), ClaudeCode)`; `name() == "claude-cli"`; co-mingled auth still raises; `supported_sampling() == {"temperature"}`. |
| `tests/unit/test_claude_cli_kwarg_mapping.py` *(new)* | `tools_allowed=["Bash","Read"]` lands as harbor `--allowedTools` flag (assert via `build_cli_flags()` includes `--allowedTools Bash,Read`). |
| `examples/drivers/generate-dab-paper-matrix-specs.py` | Per-variant `agent.kind`: `spacedock` → `spacedock_solver_v2` (with `solver_workflow` + `runtime: claude` + sampling-with-seed nulled appropriately); `direct-minimal` + `direct-structured` → `claude-cli`. Preserve `WORKSPACE_VARIANTS` ordering (spacedock-first established by goal1-resume T1). |
| `tests/unit/test_generate_matrix_specs_per_variant_kind.py` *(new)* | Assert `build_spec("spacedock", "bookreview")["agent"]["kind"] == "spacedock_solver_v2"`; assert `build_spec("direct-minimal", "bookreview")["agent"]["kind"] == "claude-cli"`; assert variant order. |

## Surface map — what stays

- `translate.py:CLAUDE_CLI_IMPORT_PATH` constant — unchanged.
- `_build_agent_config` `ClaudeCliAgentBlock` branch (lines 200-217) — unchanged kwargs (`tools_allowed`, `sampling_temperature`); the kwarg translation moves INSIDE `ClaudeCliAgent.__init__`.
- `spec/schema.py:ClaudeCliAgentBlock` — unchanged.
- Existing translator + auth + sampling tests (`test_claude_cli_*.py`) — must stay green.

## Open question — `claude-output.jsonl` vs `claude-code.txt`

Harbor's `ClaudeCode.run()` (claude_code.py:1144-1155) tees stream-json
to `<logs_dir>/claude-code.txt`. Razorback's audit taint scanner at
`src/razorback/audit/taint.py:46` looks for `claude-output.jsonl`. Two
options:

1. **Add a `claude-output.jsonl` symlink/copy** inside an override of
   `populate_context_post_run` so the audit scanner finds the file
   without changing the harbor adapter. *(preferred — keeps razorback
   audit contract intact)*
2. Extend audit's sentinel list to include `claude-code.txt`. Cheaper
   but breaks "audit looks for what claude-cli writes" symmetry across
   `codex-output.jsonl`.

The plan adopts option 1 and asserts it via AC-2's integration test.
If captain disagrees during plan review, switch to option 2 in T1.

## Acceptance criteria (verbatim from entity)

- **AC-1** `ClaudeCliAgent` subclasses `ClaudeCode`.
- **AC-2** Translator unchanged; kwargs map cleanly; live trial yields non-empty `claude-output.jsonl` AND non-null `summary.json.cost_usd`.
- **AC-3** Generator emits `spacedock_solver_v2` for spacedock variant, `claude-cli` for direct-minimal + direct-structured.
- **AC-4** Live `rk run` of one re-frozen spec of each kind produces cost + audit artifacts.
- **AC-5** Razorback-specific behavior preserved (co-mingled auth + `supported_sampling`).

## Task list (TDD-ordered)

T0 — **RED: subclass + identity unit tests.** Write the two failing
tests in `test_claude_cli_subclasses_claude_code.py`:
- `isinstance(ClaudeCliAgent(logs_dir=tmp_path, model_name="claude-opus-4-7"), ClaudeCode) is True`
- `ClaudeCliAgent.name() == "claude-cli"`
- `ClaudeCliAgent.supported_sampling() == {"temperature"}`
- existing co-mingled-auth test stays green after refactor

Riskiest-contract-first: invalidates AC-1 / AC-5 if the subclass shape
doesn't actually compose. Cost: minutes. Must pass before T1 lands.

Maps to: AC-1, AC-5.

T1 — **GREEN: refactor `ClaudeCliAgent` to subclass `ClaudeCode`.**
- `class ClaudeCliAgent(ClaudeCode)`
- `__init__` accepts razorback signature
  `(logs_dir, model_name=None, *, tools_allowed=None, sampling_temperature=None, extra_env=None, **kwargs)`:
  1. validate co-mingled auth on `extra_env`
  2. if `sampling_temperature is not None`, stash it (harbor's
     `ClaudeCode` doesn't accept a temperature flag; this is a
     razorback contract surface — we still record it but it has no
     CLI effect; document this in code)
  3. translate `tools_allowed` (list) → `allowed_tools` (csv string)
     kwarg for `ClaudeCode.__init__`
  4. delegate to `super().__init__(logs_dir, allowed_tools=..., extra_env=extra_env, **kwargs)`
- Drop: `setup()` body (harbor's `BaseInstalledAgent.setup` already
  validates via `get_version_command` + `parse_version`)
- Drop: `version()` override (harbor's `BaseInstalledAgent.version`
  returns `self._version`; harbor's `setup` autodetects via
  `get_version_command`)
- Drop: `run()` body (harbor's `ClaudeCode.run` is the canonical
  stream-json invocation; razorback inherits)
- Override: `populate_context_post_run(ctx)` — call
  `super().populate_context_post_run(ctx)`, then if
  `<logs_dir>/claude-code.txt` exists and `<logs_dir>/claude-output.jsonl`
  does not, symlink (or copy if symlink fails) the former to the
  latter so `rk audit`'s sentinel matches.
- Keep: `required_env()`, `supported_sampling()`, `name()`,
  `ClaudeCliAgentError`, `SUPPORTS_WINDOWS=False`.

Run T0's failing tests; verify they go green. Run the existing claude_cli
test suite (`tests/unit/test_claude_cli_*.py`) and confirm no regressions.

Maps to: AC-1, AC-5.

T2 — **kwarg-mapping RED+GREEN unit.** Write
`test_claude_cli_kwarg_mapping.py`:
- construct `ClaudeCliAgent(logs_dir=tmp, model_name="claude-opus-4-7",
  tools_allowed=["Bash","Read"], sampling_temperature=0.0)`
- assert `agent.build_cli_flags()` includes
  `"--allowedTools Bash,Read"` (or equivalent CSV format harbor emits)
- assert `sampling_temperature` is preserved on the instance (we
  honor it as a contract field even if it has no CLI effect)

This is the contract surface for AC-2's translator → agent kwargs.
Implementation: confirmed by T1's kwarg translation logic.

Maps to: AC-2 (translator + kwarg surface).

T3 — **spec generator per-variant kind RED+GREEN.** Write
`test_generate_matrix_specs_per_variant_kind.py`:
- import `build_spec` from
  `examples/drivers/generate-dab-paper-matrix-specs.py` (add a
  test-friendly import path if needed — script-as-module pattern from
  PKG-19/T1 if precedent exists)
- assert spacedock cell → `kind: spacedock_solver_v2`, `runtime: claude`,
  `solver_workflow` points at a real path under `examples/solver_workflows/`
- assert direct-minimal + direct-structured cells → `kind: claude-cli`
- assert `WORKSPACE_VARIANTS` ordering unchanged (spacedock first)

Then update `build_spec` to branch on variant. Sub-decision: which
`solver_workflow` directory to pin? Existing `examples/solver_workflows/_smoke`
is wrong for goal1 (it's a smoke fixture). Recommend creating
`examples/solver_workflows/dab_paper_matrix/` with a README.md that
mirrors the spacedock variant's intended workflow. **Decision deferred
to plan-review**: if captain prefers reusing `_smoke` for now (paper-
matrix-as-smoke parity), T3 uses it; otherwise T3 creates the new
workflow dir. Default plan choice: create
`examples/solver_workflows/dab_paper_matrix/` with one
README.md anchored to the spacedock variant's workflow language so
spec generator pins a real `solver_workflow_content_hash` after freeze.

Maps to: AC-3.

T4 — **live AC-2 + AC-4 integration.** Re-freeze ONE goal1 cell of
each kind:
- `examples/specs/goal1/spacedock/bookreview.yaml` → freeze (now
  pinned to `spacedock_solver_v2`) → `bookreview.frozen.yaml`
- `examples/specs/goal1/direct-minimal/bookreview.yaml` → freeze
  (`claude-cli`) → `bookreview.frozen.yaml`

Live `rk run` against both. Assertions:
- run-dir exists per spec
- `<run-dir>/claude-output.jsonl` (or symlink to claude-code.txt) is
  present and non-empty for the `claude-cli` cell
- `<run-dir>/summary.json.cost_usd` is non-null for both cells
- `<run-dir>/_razorback/freeze/<sealed_hash>/sealed_hash.txt` matches
  the frozen spec's `sealed_hash` for the spacedock cell

Budget: 2 cells × ~$2 estimated = ~$4 (well under the entity's
`max_budget_usd: 20`). Captain auto-approve under standing orders.

Document in a separate validation report at
`docs/razorback-implementation/pkg26-validation.md` (per Goal 1 RESUME
T0's pattern). Cite run-dir paths + `summary.json` cost fields verbatim.

Maps to: AC-2, AC-3, AC-4.

## Out of scope (verbatim from entity)

- Removing razorback's `claude_cli.py` entirely (deprecation only).
- Goal 2 / ade-bench matrix gen — separate follow-up.
- Backporting cost telemetry into razorback's claude_cli.py — captain
  directive is upstream-first.
- Multi-trial / N>1 retry semantics.

## Risk register

- **Harbor `ClaudeCode.run()` requires `install()` first** (lines
  127-159). Razorback's `claude-cli` agent has historically run
  outside containers (the host `claude` binary is already installed).
  Harbor's `BaseInstalledAgent.setup()` calls `install()` first — this
  will try to `apt-get install` or `curl | bash` inside the
  environment. For docker-compose harbor_dab benchmarks this is the
  intended path. For local/non-container runs we need to verify the
  install command is idempotent (it is — `npm install -g` re-runs are
  safe). T4's live `rk run` exercises this.
- **`SUPPORTS_ATIF = True` on harbor's ClaudeCode** (line 30) vs
  `False` on razorback's current ClaudeCliAgent (line 23). The
  subclass should accept harbor's `True` — razorback's audit pipeline
  already handles ATIF trajectory files; gaining them is net-positive.
- **`prompt_template_path` / `version` kwargs** from
  `BaseInstalledAgent.__init__` (lines 147-155). Razorback's
  AgentConfig.kwargs don't pass these today; harbor's defaults
  (`None`) are fine. No change.
- **`memory_dir`** kwarg on `ClaudeCode.__init__` (line 107). Default
  `None` is fine; we don't surface it through razorback's spec.

## Sequencing

T0 → T1 → T2 → T3 (in any order after T1) → T4.

T0 is riskiest-contract-first (subclass shape itself); if T1's refactor
breaks an existing claude_cli test that doesn't appear in T0, we stop
and re-plan rather than papering over. T4's live run is the
mechanism-validation gate that unblocks Goal 1 RESUME T2.

## Resume hook for Goal 1 RESUME

After this plan ships and PKG-26's entity flips to `merged`:
- Goal 1 RESUME ensign re-runs its T1 (spec regeneration) under the
  new per-variant kind layout
- Goal 1 RESUME T2 dispatches the 36-cell matrix; cost_usd non-null;
  audit traces present
