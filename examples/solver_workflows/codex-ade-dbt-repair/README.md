# Codex ADE dbt Repair Workflow

Work offline inside the task workspace. Inspect `instruction.md`, `task.toml`, the dbt
project files, and any local validation scripts before editing.

Repair the task-local dbt project so the requested behavior is implemented in the
project itself. Prefer the smallest clear model, macro, seed, config, or test change
that addresses the failure described by the task.

Run cheap local validation when the task provides it, such as dbt compile, targeted
dbt tests, or task-local shell scripts. Record only concise evidence in your final
message.

Leave the repaired project state as the graded artifact. Do not optimize for a
separate answer file, network access, package installs, or external datasets.
