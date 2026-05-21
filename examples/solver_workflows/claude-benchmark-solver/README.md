# Claude Benchmark Solver

Read the task-local instructions and workspace files before acting. Treat the benchmark data, prompt text, and repository state as sealed inputs.

Operate offline. Do not use network access, package installation, external search, or live documentation lookups while solving a benchmark task. Use only the tools allowed by the benchmark spec and the files already present in the task workspace.

Make the smallest changes needed to produce the requested answer or artifact. Prefer explicit checks over assumptions, keep intermediate notes inside the task workspace when useful, and leave the final response focused on the benchmark request.
