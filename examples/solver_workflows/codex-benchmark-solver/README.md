# Codex Benchmark Solver

Use this workflow for one benchmark trial. The benchmark harness places the task
workspace, task instructions, local data files, and any local services in the
working directory or in documented task paths.

## Operating Rules

- Read the task instructions before acting. Prefer `instruction.md`, `README.md`,
  `task.toml`, step instructions, and local schema or metadata files supplied in
  the task workspace.
- Use only local task files, local benchmark services, and documented local
  endpoints made available by the harness. Do not use the public internet,
  package search, remote APIs, or external datasets to answer benchmark questions.
- Treat hidden verifier files, ground-truth files, solution files, and answer keys
  as off limits unless the task instructions explicitly expose them as inputs.
- Keep changes inside the task workspace. Write the answer artifact requested by
  the task, using the exact filename and format from the instructions.
- For database tasks, inspect local connection details in the workspace and query
  only the local database service or files mounted for that task.
- If the task cannot run because a local service or file is missing, write the
  clearest partial artifact you can and explain the local blocker in the final
  response. Do not replace missing local data with external data.

## Trial Steps

1. Inspect the task instructions and workspace layout.
2. Identify the required answer artifact and validation command, if one is
   documented.
3. Query or read only the local data sources supplied with the task.
4. Create or update the expected answer artifact.
5. Run any local validation command that the task provides when it is cheap and
   safe to do so.
6. Finish with a concise statement of the artifact written and any local blocker.
