# Tools-denied live-probe solver workflow (PKG-9 AC-3)

Minimal solver_workflow used by the AC-3 integration test. The agent
is instructed to attempt `pip install datasets` on its first action.
The runtime's PreToolUse denylist (installed from
`agent.tools_denied`) must block the invocation before it executes.

## Stages

- model

## Stage: model

Run `pip install datasets` as your first action via the Bash tool.
Then stop. Do not pre-emptively check whether the command is denied.
The harness needs the actual tool invocation to fire so the
PreToolUse denial event is recorded.
