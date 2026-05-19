# ABOUTME: ClaudeCliAgent — wraps `claude -p`. Skeleton lands here for AC-1's required_env;
# ABOUTME: setup/run flesh out in Task 4. supported_sampling stays the source of truth.

from harbor.agents.base import BaseAgent


class ClaudeCliAgent(BaseAgent):
    SUPPORTS_WINDOWS = False

    @staticmethod
    def name() -> str:
        return "claude-cli"

    def version(self) -> str | None:
        return None  # Task 4 wires `claude --version`.

    @classmethod
    def required_env(cls) -> dict:
        """AC-1: declare the alternation. Translator (Task 5) reads this."""
        return {"mode": "alternation", "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]}

    @staticmethod
    def supported_sampling() -> set[str]:
        return set()  # Task 4 returns {"temperature"}.

    async def setup(self, environment) -> None:
        raise NotImplementedError  # Task 4

    async def run(self, instruction, environment, context) -> None:
        raise NotImplementedError  # Task 4
