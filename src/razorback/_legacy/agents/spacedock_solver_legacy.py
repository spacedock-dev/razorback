# ABOUTME: SpacedockSolverAgent (§6.2 third bullet) — staged solver with halt-resume.
# ABOUTME: __init__ recomputes sealed_hash and refuses on mismatch BEFORE any harbor I/O.

import json
import time
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.trial.paths import EnvironmentPaths

from razorback.agents.claude_invoke import build_claude_argv
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.errors import RazorbackError, SeedMismatchError


class SpacedockSolverAgentError(RazorbackError):
    """Raised on SpacedockSolverAgent contract violations."""


def assert_phase_stats_schema(path: Path) -> None:
    """Public schema check for §6.8 phase_stats.json. M5's aggregator imports this."""
    data = json.loads(Path(path).read_text())
    assert isinstance(data, dict)
    for stage in ("model", "analyze", "verify"):
        assert stage in data, f"missing stage: {stage}"
        for k in ("tokens_in", "tokens_out", "cost_usd", "wallclock_s"):
            assert k in data[stage], f"missing key {k!r} in stage {stage!r}"
        assert isinstance(data[stage]["tokens_in"], int)
        assert isinstance(data[stage]["tokens_out"], int)
        assert isinstance(data[stage]["cost_usd"], (int, float))
        assert isinstance(data[stage]["wallclock_s"], (int, float))


class SpacedockSolverAgent(BaseAgent):
    SUPPORTS_WINDOWS = False
    SUPPORTS_ATIF = False

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        logger=None,
        mcp_servers=None,
        skills_dir=None,
        *,
        model: str,
        sampling: dict[str, Any],
        stages: list[str],
        tools_allowed: list[str],
        prompts: dict[str, str],
        sealed_hash: str,
        prompt_contents: dict[str, str] | None = None,
        prior_frozen_spec_path: Path | str | None = None,
        extra_env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name or model,
            logger=logger,
            mcp_servers=mcp_servers,
            skills_dir=skills_dir,
            **kwargs,
        )
        self._model = model
        self._sampling = dict(sampling)
        self._stages = list(stages)
        self._tools_allowed = list(tools_allowed)
        self._prompts = dict(prompts)
        self.sealed_hash = sealed_hash
        # FU-1 AC-1: auth arrives via harbor's `extra_env` kwarg (resolved from
        # AgentConfig.env at agent-factory time). env field is redacted on disk;
        # the literal value never persists.
        self._extra_env = dict(extra_env or {})
        if (
            "ANTHROPIC_API_KEY" in self._extra_env
            and "CLAUDE_CODE_OAUTH_TOKEN" in self._extra_env
        ):
            raise SpacedockSolverAgentError(
                "ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN cannot both be set."
            )
        self._prompt_contents = dict(prompt_contents) if prompt_contents else {}
        self._exec_env: dict[str, str] = {}
        self._phase_stats: dict[str, dict] = {}

        # AC-1: BEFORE harbor I/O — refuse on sealed-hash mismatch.
        self._refuse_on_resume_mismatch(
            Path(prior_frozen_spec_path) if prior_frozen_spec_path else None
        )

    def _refuse_on_resume_mismatch(self, prior_frozen_spec_path: Path | None) -> None:
        if prior_frozen_spec_path is None:
            return
        prior = yaml.safe_load(Path(prior_frozen_spec_path).read_text())
        prior_agent = prior.get("agent", {})
        prior_sealed = prior_agent.get("sealed_hash")
        if prior_sealed is None:
            raise SpacedockSolverAgentError(
                f"prior frozen spec at {prior_frozen_spec_path} has no agent.sealed_hash — "
                "cannot validate resume."
            )
        # Recompute the sealed_hash from kwargs to detect tampered (sealed_hash, prompts) pairs.
        recomputed = compute_sealed_hash(
            model=self._model,
            sampling=self._sampling,
            stages=self._stages,
            prompt_hashes={
                k: v for k, v in self._prompts.items() if v.startswith("sha256:")
            },
        )
        if recomputed != self.sealed_hash:
            raise SeedMismatchError(
                f"resume spec's recomputed sealed_hash ({recomputed}) does not match "
                f"its declared sealed_hash ({self.sealed_hash}). "
                "Tampered or stale frozen spec."
            )
        if self.sealed_hash != prior_sealed:
            drifted = self._find_drifted_field(prior_agent)
            raise SeedMismatchError(
                f"resume sealed_hash ({self.sealed_hash}) does not match prior seed run "
                f"sealed_hash ({prior_sealed}). Drifted field: {drifted}. "
                f"Prior frozen spec: {prior_frozen_spec_path}"
            )

    def _find_drifted_field(self, prior_agent: dict[str, Any]) -> str:
        if prior_agent.get("model") != self._model:
            return f"model (seed={prior_agent.get('model')!r}, resume={self._model!r})"
        if prior_agent.get("sampling") != self._sampling:
            return "sampling"
        if list(prior_agent.get("stages", [])) != self._stages:
            return "stages"
        prior_prompts = prior_agent.get("prompts", {})
        for name, my_hash in self._prompts.items():
            if not my_hash.startswith("sha256:"):
                continue
            if prior_prompts.get(name) != my_hash:
                return f"prompts.{name}"
        return "sealed_hash"

    def verify_prompt_contents(self) -> None:
        """AC-3: re-hash each prompt body; refuse if it does not match the pinned sha256."""
        for stage, pinned in self._prompts.items():
            if not pinned.startswith("sha256:"):
                continue
            body = self._prompt_contents.get(stage)
            if body is None:
                raise SpacedockSolverAgentError(
                    f"prompt_contents.{stage} is missing; cannot verify against pinned {pinned}"
                )
            recomputed = prompt_sha256(body.encode("utf-8"))
            if recomputed != pinned:
                raise SpacedockSolverAgentError(
                    f"prompts.{stage} hash drift: pinned {pinned}, recomputed {recomputed}. "
                    "The frozen spec's prompt_contents has been tampered with after freeze."
                )

    @staticmethod
    def name() -> str:
        return "spacedock-solver"

    def version(self) -> str | None:
        return None

    @classmethod
    def required_env(cls) -> dict:
        return {
            "mode": "alternation",
            "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"],
        }

    @staticmethod
    def supported_sampling() -> set[str]:
        return {"temperature"}

    async def setup(self, environment: BaseEnvironment) -> None:
        """AC-6: filter MCP servers; build exec env; validate claude + git binaries; AC-3 prompt hashes."""
        if self._tools_allowed:
            allowed = set(self._tools_allowed)
            self.mcp_servers = [s for s in (self.mcp_servers or []) if s.name in allowed]

        self._exec_env = {
            **PROXY_BLOCK_ENV,
            **self._extra_env,
            "HOME": "/root",
        }

        version = await environment.exec("claude --version")
        if version.return_code != 0:
            raise SpacedockSolverAgentError(
                f"claude CLI not available inside container (exit={version.return_code}, "
                f"stderr={getattr(version, 'stderr', '')!r})"
            )

        git_v = await environment.exec("git --version")
        if git_v.return_code != 0:
            raise SpacedockSolverAgentError(
                f"git not available inside container (exit={git_v.return_code}). "
                "agent_freeze/.git commits require git."
            )

        self.verify_prompt_contents()

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context,
    ) -> None:
        """AC-4/AC-5: staged execution, agent_freeze/.git commits, phase_stats.json."""
        host_freeze_dir = Path(self.logs_dir) / "agent_freeze"
        host_freeze_dir.mkdir(parents=True, exist_ok=True)
        # The container sees harbor's logs_dir bind-mounted under env_paths
        # (default /logs/agent). Use that path inside environment.exec calls.
        env_logs_root = self._env_logs_root(environment)
        container_freeze_dir = env_logs_root / "agent_freeze" if env_logs_root else host_freeze_dir
        await self._init_agent_freeze_repo(environment, container_freeze_dir)

        self._phase_stats = {}
        for stage in self._stages:
            prompt_body = self._prompt_contents[stage]
            rendered = self._render_stage_prompt(stage, prompt_body, instruction)
            cmd = build_claude_argv(
                prompt=rendered, model=self._model, tools_allowed=self._tools_allowed,
            )
            t0 = time.monotonic()
            result = await environment.exec(
                cmd, cwd=str(container_freeze_dir), env=self._exec_env, timeout_sec=600,
            )
            wallclock = time.monotonic() - t0
            await self._commit_stage(environment, container_freeze_dir, stage)
            self._phase_stats[stage] = {
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
                "wallclock_s": round(wallclock, 3),
            }
            if result.return_code != 0:
                context.return_code = result.return_code
                self._write_phase_stats_file(host_freeze_dir)
                return

        context.return_code = 0
        self._write_phase_stats_file(host_freeze_dir)

    @classmethod
    def _env_logs_root(cls, environment) -> PurePosixPath | None:
        """Return the container-side logs root for the agent if the environment exposes one.

        Harbor's BaseEnvironment.env_paths gives the in-container view (default /logs/agent).
        Local-shell fakes used in unit tests have no env_paths; for those we fall back
        to the host path (which IS the container path in those tests).
        """
        try:
            paths = environment.env_paths
        except Exception:
            return None
        # Read harbor's per-environment path so we can compute the bind-mount path
        # to use inside environment.exec calls. AC-7 forbids razorback from writing
        # under that directory itself; we only write to the agent_freeze/ subtree.
        return PurePosixPath(str(paths.agent_dir))

    async def _init_agent_freeze_repo(self, environment, freeze_dir) -> None:
        cmds = [
            f"git -C {freeze_dir} init -q",
            f"git -C {freeze_dir} config user.email razorback@local",
            f"git -C {freeze_dir} config user.name razorback",
            f"git -C {freeze_dir} config commit.gpgsign false",
            f"git -C {freeze_dir} add -A",
            f"git -C {freeze_dir} commit -q --allow-empty -m seed",
        ]
        for c in cmds:
            r = await environment.exec(c)
            if r.return_code != 0:
                raise SpacedockSolverAgentError(
                    f"agent_freeze repo init failed at: {c}\n"
                    f"rc={r.return_code} "
                    f"stdout={getattr(r, 'stdout', '')!r} "
                    f"stderr={getattr(r, 'stderr', '')!r}"
                )

    async def _commit_stage(self, environment, freeze_dir, stage: str) -> None:
        cmds = [
            f"git -C {freeze_dir} add -A",
            f"git -C {freeze_dir} commit -q --allow-empty -m 'stage: {stage}'",
        ]
        for c in cmds:
            r = await environment.exec(c)
            if r.return_code != 0:
                raise SpacedockSolverAgentError(
                    f"agent_freeze stage commit failed at: {c}\n"
                    f"rc={r.return_code} "
                    f"stdout={getattr(r, 'stdout', '')!r} "
                    f"stderr={getattr(r, 'stderr', '')!r}"
                )

    def _render_stage_prompt(self, stage: str, body: str, instruction: str) -> str:
        return f"# Stage: {stage}\n\n{body}\n\n# Task instruction:\n{instruction}\n"

    def _write_phase_stats_file(self, freeze_dir: Path) -> None:
        """Write the §6.8 phase_stats.json. Public contract — DO NOT add unscoped fields."""
        out = {}
        for stage in self._stages:
            s = self._phase_stats.get(stage, {})
            out[stage] = {
                "tokens_in": int(s.get("tokens_in", 0)),
                "tokens_out": int(s.get("tokens_out", 0)),
                "cost_usd": float(s.get("cost_usd", 0.0)),
                "wallclock_s": float(s.get("wallclock_s", 0.0)),
            }
        (freeze_dir / "phase_stats.json").write_text(json.dumps(out, indent=2) + "\n")
