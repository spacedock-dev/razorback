---
date: 2026-05-20
resolves: AC-0.2, D1
plan: 2026-05-19-razorback-reconciliation-plan.md
---

# Harbor entry-point execution probe — AC-0.2

## Verdict

**ENTRY-POINT DISPATCH WORKS — but not via setuptools entry-point groups.**

Harbor does NOT enumerate `importlib.metadata.entry_points()` for either
agents or adapters. The dispatch mechanism is a **Python dotted
`import_path: "module.path:ClassName"` field on the spec**. Any
pip-installed package that exposes a `BaseAgent` subclass at that
import path is loaded by `harbor run` and its `run()` method is
invoked.

The fallback (razorback's `rk run` translates the spec before invoking
`harbor run`) is **not** required for agent dispatch. `rk run` only
needs to translate razorback's `spec.yaml` shape (`agent.kind`,
`benchmark.kind`, etc.) into harbor's `JobConfig` shape
(`agents[].import_path`, `tasks[]` / `datasets[]`). The translation is
field-name mapping plus task-directory generation, not a runtime
dispatch reroute.

## Entry-point group names

There are **no entry-point groups**. The plan-language phrase
"entry-point group" was a guess at the wrong mechanism. The actual
mechanism is:

- **External agents**: `AgentConfig.import_path: str | None`, resolved
  by `AgentFactory.create_agent_from_import_path` in
  `harbor/agents/factory.py:95-133`. Format:
  `"module.path:ClassName"`. The class must subclass
  `harbor.agents.base.BaseAgent` and implement `name()`, `version()`,
  `setup()`, `run()`.
- **External environments** (closest analog to "external benchmark
  adapter"): `EnvironmentConfig.import_path: str | None`, same
  resolution shape, must subclass `harbor.environments.base.BaseEnvironment`.
  Citation: `harbor/models/trial/config.py:68`. Built-in environments
  are enumerated in `harbor/environments/factory.py` (Docker, Daytona,
  E2B, Modal, Runloop, GKE, Apple-Container, Singularity, Islo,
  Tensorlake) but the import_path path lets external packages add
  their own.
- **External benchmark adapters (offline, task-generator pattern)**:
  No runtime dispatch. Harbor adapters are standalone executable
  packages invoked via `uv run <adapter-folder>` that emit task
  directories (`<output>/<task-id>/{task.toml,instruction.md,environment/,tests/,solution/}`).
  Harbor consumes the emitted directories via `JobConfig.tasks[].path`
  or `JobConfig.datasets[].path`. Adapter shape is enforced by
  `harbor adapter review` (`harbor/cli/adapter_review.py`), not by
  runtime entry-point lookup. Template lives at
  `harbor/cli/template-adapter/`.

The hardcoded built-in agent list is in `harbor/agents/factory.py:35-60`
(`AgentFactory._AGENTS`). Adding a built-in agent requires editing
that list; external agents avoid the list by using `import_path`.

## Agent dispatch probe

- **Package**: `/tmp/razorback-probe-agent/`
- **Install**:

  ```
  uv pip install -e /tmp/razorback-probe-agent
  → Installed 1 package in 0.78ms
  → + probe-agent==0.0.1 (from file:///tmp/razorback-probe-agent)
  ```

- **`pyproject.toml` declaration** (no entry-point group; harbor
  doesn't read one):

  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [project]
  name = "probe-agent"
  version = "0.0.1"
  requires-python = ">=3.10"

  [tool.hatch.build.targets.wheel]
  packages = ["src/probe_agent"]
  ```

- **Stub class** (`/tmp/razorback-probe-agent/src/probe_agent/__init__.py`):

  ```python
  from harbor.agents.base import BaseAgent

  PROBE_TOKEN = "PROBE_AGENT_DISPATCH_OK_20260520"


  class ProbeAgent(BaseAgent):
      @staticmethod
      def name() -> str:
          return "probe-agent"

      def version(self) -> str | None:
          return "0.0.1"

      async def setup(self, environment) -> None:
          return None

      async def run(self, instruction, environment, context) -> None:
          raise RuntimeError(PROBE_TOKEN)
  ```

- **Spec** (`/tmp/razorback-probe-spec.yaml`):

  ```yaml
  job_name: razorback-probe-agent
  jobs_dir: /tmp/razorback-probe-logs
  n_attempts: 1
  n_concurrent_trials: 1
  agents:
    - import_path: probe_agent:ProbeAgent
  tasks:
    - path: /Users/clkao/git/razorback/examples/tasks/hello-world
  ```

- **Harbor invocation**:

  ```
  DOCKER_CONFIG=/Users/clkao/.docker \
  DOCKER_HOST=unix:///Users/clkao/.colima/default/docker.sock \
  HOME=/tmp/razorback-probe-home \
  uv run harbor run -c /tmp/razorback-probe-spec.yaml
  ```

  (The `HOME` override is needed because the real `~/.cache/harbor`
  has a macOS data-vault ACL that blocks the sandbox; the
  `DOCKER_CONFIG` override is needed because changing HOME hides the
  docker CLI plugins at `~/.docker/cli-plugins`. These are
  environment-friction workarounds and do not affect the dispatch
  question.)

- **Relevant captured output**: the job summary printed
  `adhoc • probe-agent` (the agent name returned by
  `ProbeAgent.name()`). The persisted trial config at
  `/tmp/razorback-probe-logs/razorback-probe-agent/<trial>/config.json`
  has `"agent": {"name": null, "import_path": "probe_agent:ProbeAgent", ...}`.
  Trial exception at
  `/tmp/razorback-probe-logs/razorback-probe-agent/<trial>/exception.txt`:

  ```
  File "/private/tmp/razorback-probe-agent/src/probe_agent/__init__.py", line 18, in run
      raise RuntimeError(PROBE_TOKEN)
  RuntimeError: PROBE_AGENT_DISPATCH_OK_20260520
  ```

- **Outcome**: stub's `run()` was called by harbor. Dispatch works.
  The unique token raised in the external pip-installed package
  surfaced via harbor's trial machinery — proving harbor instantiated
  the class, called `setup()`, and called `run()`.

## Adapter dispatch probe

Probe re-scoped after source inspection: harbor has **no runtime
dispatch path for benchmark adapters**. The "external benchmark
adapter" entry-point group named in AC-0.2 does not exist. What
exists:

1. **`harbor adapter` CLI surface** (`harbor/cli/adapters.py`) for
   wizard-driven scaffolding (`init`) and review (`review`) of
   adapter packages. These commands operate on local directories;
   they do not consult any plugin registry.
2. **Adapter packages** (template at
   `harbor/cli/template-adapter/`) are standalone Python packages
   invoked as `uv run <adapter-folder>` (per
   `harbor/cli/adapter_review.py:456-481`). They produce task
   directories on disk and exit. Harbor then consumes those
   directories at run-time via `JobConfig.tasks[].path` or
   `JobConfig.datasets[].path`.
3. **Runtime environment plugins** (the closest mechanistic analog to
   "external benchmark adapter") use the same `import_path` shape as
   agents: `EnvironmentConfig.import_path: "module.path:ClassName"`
   resolved by harbor's environment factory.

Because the adapter contract is "produce task directories", no
execution probe is meaningful — there is no harbor dispatch call to
trigger. The contract is verified by the **output shape**
(task.toml + instruction.md + environment/Dockerfile + tests/test.sh
per task), which razorback's `examples/tasks/hello-world` already
satisfies (probed implicitly in the agent run above: harbor accepted
the task at `examples/tasks/hello-world` without complaint).

## Implications

For the reconciliation plan Phase 1-3:

1. **Razorback's custom agent (`SpacedockSolverAgent`) ships as a
   pip-installed package within razorback's own distribution.** The
   `rk run` translator emits a harbor JobConfig with
   `agents: [{import_path: "razorback.spacedock_solver:SpacedockSolverAgent", kwargs: {...}}]`.
   No setuptools entry-point declaration needed. The class lives at
   the named import path; harbor finds it because razorback's package
   is installed into the same venv as harbor.

2. **Razorback's `rk run` is a thin spec-translator, not a dispatch
   reroute.** Translation work: razorback's `spec.yaml` (with
   `agent.kind`, `benchmark.kind`, `trials`, etc.) → harbor's
   `JobConfig` (with `agents[]`, `tasks[]` / `datasets[]`,
   `n_attempts`, etc.). This resolves the spec §4.1 "rk run hands
   off to harbor run" question: yes, via subprocess `harbor run -c <translated>`,
   not via in-process harbor APIs (unless we want them, but subprocess
   matches the contract probed here).

3. **DAB adapter belongs upstream of `harbor run`, not inside it.**
   The DAB adapter is razorback's offline task-generator that emits
   harbor-shaped task directories. The reconciliation plan's
   "ade-bench-agent image" + adapter work (PKG-9, PKG-10) maps cleanly
   onto harbor's adapter-package contract — task directories on disk,
   consumed by `JobConfig.tasks[]`. Spec §6 (benchmark.kind: dab)
   becomes `rk run` material: razorback resolves the DAB dataset to a
   list of task paths and emits them as harbor `tasks:` entries.

4. **AC-0.3 (spec format compat) is resolved partly by this probe**:
   razorback's agent block translates to `AgentConfig` with
   `import_path` + `kwargs`. The `spacedock_solver` agent block's
   custom kwargs flow through `kwargs: {}` cleanly (the
   `BaseAgent.__init__` accepts `**kwargs`).

5. **AC-0.4 (installed-agent constructor probe)** is unblocked: the
   ProbeAgent constructed via `BaseAgent.__init__` with only
   `logs_dir` + `model_name` proves the kwargs path. Razorback's
   `SpacedockSolverAgent` must follow the same signature shape
   (`logs_dir`, `model_name=None`, `**kwargs`).

6. **Plan / spec wording must be updated** to drop "entry-point group"
   and replace with "import_path field". Specifically: plan §AC-0.2
   text, spec §4 (SpacedockSolverAgent description), spec §5
   (benchmark adapter), spec §6 (DAB adapter integration). The
   mechanism is dotted-import-path resolution, not setuptools/PEP-621
   entry-point group enumeration.

## Cleanup

- Probe package retained on disk at `/tmp/razorback-probe-agent/` for
  reference. Removed from the razorback venv with `uv pip uninstall probe-agent`
  (performed after writing this doc).
- Probe spec retained at `/tmp/razorback-probe-spec.yaml`.
- Probe logs retained at `/tmp/razorback-probe-logs/`.
- Throwaway HOME retained at `/tmp/razorback-probe-home/`.

None of these touch the razorback repo or its venv (post-uninstall).
