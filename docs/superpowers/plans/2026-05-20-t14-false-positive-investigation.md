# T14 / PKG-12 false-positive investigation

Date: 2026-05-20
Investigator: pkg13-bindmount-investigate
Run-dir under investigation: `.runs/t14-harbor-dab-bookreview-n3/t14-bookreview-claude-harbor-dab-n3/9c26daea1ada1c4d/`
Smoke confirmation run-dir: `.runs/t14-harbor-dab-bookreview-smoke-cycle3/phase2-bookreview-claude-harbor-dab/f75deca763dcb5e8/`

## Verdict

**REAL BUG. The 9/9 pass@1 = 1.0 reported for T14 is a FALSE POSITIVE.**

The headline finding is more damning than the original report: the bind-mount path bug isn't even reached, because **harbor never opens the plugin's generated `docker-compose.yaml` at all**. There is no postgres anywhere in the run. The agent operates on the bare SQL/SQLite files that were copied into `/workspace/query_dataset/`, and the verifier (which only checks substring presence) accepts trivial-but-substring-matching outputs.

The reported "live-DB benchmark" never had a live DB. The reported "100% pass" was three independent substring coincidences in three substring-only validators.

## Evidence

### A. Bind-mount path: still wrong, but moot

The compose generator (`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py:55`) emits
`./workdir/{sql_file}` for `volumes`, relative to the compose file's directory.

The compose file is written at the task-dir root by `prepare.py:137`:
```
(task_dir / "docker-compose.yaml").write_text(compose_text)
```

But the workdir is materialized inside `steps/main/` at `prepare.py:176`:
```
workdir = step_dir / "workdir"  # step_dir = task_dir / "steps" / "main"
```

So the bind-mount source resolves to
`tasks/bookreview/bookreview-q1/workdir/query_dataset/books_info.sql`
which **does not exist**. The actual SQL lives at
`tasks/bookreview/bookreview-q1/steps/main/workdir/query_dataset/books_info.sql`.

Confirmed by:
```
$ ls .runs/.../tasks/bookreview/bookreview-q1/workdir/
ls: ... No such file or directory

$ find .runs/.../tasks/bookreview/bookreview-q1 -name books_info.sql
.runs/.../tasks/bookreview/bookreview-q1/steps/main/workdir/query_dataset/books_info.sql
```

This bug would matter — except it never gets exercised (see B).

### B. The plugin's docker-compose.yaml is never loaded by harbor

`task.toml` declares `[environment].docker_compose = "docker-compose.yaml"`, but **harbor's `EnvironmentConfig` has no `docker_compose` field** (`.venv/.../harbor/models/task/config.py:127-170`). The key is silently dropped by pydantic.

Harbor's actual compose discovery is hard-coded at
`.venv/.../harbor/environments/docker/docker.py:250-251`:
```python
@property
def _environment_docker_compose_path(self) -> Path:
    return self.environment_dir / "docker-compose.yaml"
```
i.e., it looks at `task_dir/environment/docker-compose.yaml`. The plugin writes only `task_dir/docker-compose.yaml` and `task_dir/environment/Dockerfile` (stubbed) + `settings.json`. There is no compose in `environment/`.

Live confirmation from a currently-running container
(`bookreview-q1__y53pkv8-main-1`, ID `2a16a79af8b8`):
```
$ docker inspect 2a16a79af8b8 \
    --format='{{index .Config.Labels "com.docker.compose.project.config_files"}}'
.../harbor/environments/docker/docker-compose-base.yaml,
.../harbor/environments/docker/docker-compose-prebuilt.yaml
```
Only harbor's own base + prebuilt compose files. The plugin's generated one is **not** in the list.

Network confirmation:
```
$ docker network ls | grep -i 'dab\|bookreview'
bookreview-q1__hejqg8e_default   bridge
bookreview-q1__y53pkv8_default   bridge
bookreview-q1__zjfyy4x_default   bridge
```
No `dab-net-bookreview`. No `dab-postgres` service. There is no live DB anywhere in this run.

### C. The agent ran; it just doesn't speak to a DB

`ClaudeCliAgent.run()` (`src/razorback/agents/claude_cli.py:106-118`) calls
`claude -p <instruction>` inside the container. `claude` writes only to its own
stdout (not to `/logs/agent/`), which is why `bookreview-q1__3iKxTyw/steps/main/agent/`
is host-empty. That is expected and not itself a bug.

Inside the live containers:
```
$ docker exec 2a16a79af8b8 ls -la /workspace
analyze_books.py     # <-- agent-authored script
answers.json
db_config.yaml
db_description.txt
db_description_withhint.txt
query.json
query_dataset/       # raw books_info.sql + review_query.db

$ docker exec 2a16a79af8b8 cat /workspace/answers.json
{"answer": "2020s"}

$ head -3 /workspace/analyze_books.py
import sqlite3, re, json
from collections import defaultdict
# Read the books_info SQL file and parse the COPY data
books = {}
with open('/workspace/query_dataset/books_info.sql', 'r') as f:
    ...
```

The agent realised there was no postgres, fell back to parsing the raw SQL dump
in Python, and produced an answer. All three concurrent q1 containers produced
the identical answer `{"answer": "2020s"}`.

### D. The verifier ran our verify.py, which accepts substring matches

`task.toml` has `[[steps]] name = "main"` and **no `command` and no `verifier`
block**. Per harbor's StepConfig (`.../harbor/models/task/config.py:260-286`), a
step that omits `verifier` gets `VerifierConfig(default_factory=...)`, and the
verifier runs `tests/test.sh` discovered via `discovered_step_test_path_for`
(falling back to top-level `tests/`).

The Verifier (`.../harbor/verifier/verifier.py:122-188`) uploads the host's
`tests/` directory to `/tests/` inside the container, runs `test.sh`, then
reads `/logs/verifier/reward.json`. If reward.json doesn't exist it raises
`RewardFileNotFoundError`. **Harbor does NOT default to reward=1.0 on empty
output**; that part of the original suspicion is wrong.

The 1.0 comes from our own `verify.py`:
`packages/razorback-plugin-dab/src/razorback_plugin_dab/verify/verify.py:11-22`
```python
if llm_answer:
    is_valid, reason = validate_fn(llm_answer)
else:
    is_valid, reason = False, "empty answer"
payload = {"reward": 1.0 if is_valid else 0.0}
```
plus the per-query validators inside the task dir:

- **q1** (`tests/validate.py:8-10`):
  ```python
  gt = "2020"
  if gt in llm_output:
      return True, "..."
  ```
  Agent's answer `"2020s"` contains `"2020"` → reward=1.0. The question asks
  for "the decade with the highest average rating (e.g. 1980s)". The validator
  would have accepted any string containing the four chars `2020`, including
  things like `"02020"`, `"2020 BC"`, or a paragraph quoting `2020-01-01`.

- **q2** and **q3**: a list of ~15 specific book titles. The validator passes
  iff every title appears as a substring of the answer (after lowercase /
  punctuation-stripping / parenthesised-tag stripping). Every one of those
  ground-truth titles is present **as a literal string in the
  `books_info.sql` dump that we copied into `/workspace/query_dataset/`**:
  ```
  $ docker exec ... grep -c "The Sludge" /workspace/query_dataset/books_info.sql
  1
  $ docker exec ... grep -c "Around the World Mazes" /workspace/query_dataset/books_info.sql
  1
  ```
  So an agent that dumps even a moderately wide selection of rows from the SQL
  file into its answer will pass — regardless of whether the answer is actually
  the correct query result.

`test-stdout.txt` is empty because `verify.py` writes to stderr on failure and
prints nothing on success.

### E. Smoke cycle3 shows identical evidence

`.runs/t14-harbor-dab-bookreview-smoke-cycle3/phase2-bookreview-claude-harbor-dab/f75deca763dcb5e8/`:
- 3/3 trials reward=1.0
- compose file at task-dir root with same bind-mount path bug
- test-stdout.txt empty (0 bytes) for all trials
- `agent/` dir empty for all trials
- task.toml has the same un-honoured `[environment].docker_compose`

Same bug, same false positive.

## Root causes (independent)

The original report described one bug. The investigation found four, layered.
Fixing only the bind-mount path would not fix anything observable, because the
compose file is never loaded.

1. **Plugin's compose file is in the wrong location for harbor to pick it up.**
   - Symptom: `_docker_compose_paths` (harbor/environments/docker/docker.py:280-301)
     does not include the plugin's compose.
   - Cause: harbor reads `environment/docker-compose.yaml`; plugin writes
     `task_dir/docker-compose.yaml`.
   - Effect: postgres never starts. Agent has no DB.

2. **Plugin assumes a `[environment].docker_compose` task.toml field that
   harbor does not honour.**
   - Symptom: silent drop on TaskConfig parse; no warning, no error.
   - Cause: `EnvironmentConfig` (harbor/models/task/config.py:127) defines
     `docker_image`, `os`, `workdir`, etc. — no `docker_compose`.
   - Effect: pydantic ignores the unknown key; the task author has no
     feedback that their wiring is dead.

3. **Bind-mount path in generated compose is wrong (the originally-reported
   bug).**
   - Symptom: `./workdir/query_dataset/books_info.sql` resolves to a
     nonexistent path relative to compose dir.
   - Cause: `generate_compose` (compose.py:55,63) emits a path under
     `./workdir/`, but `prepare.py` places workdir under
     `steps/main/workdir/`.
   - Effect: latent. Even if (1) and (2) were fixed, docker would silently
     create an empty dir at the missing bind-mount source, postgres init would
     get nothing, the DB would be empty.

4. **Bookreview "reachability gate" promised by T7 is not implemented.**
   - Symptom: rk run translator accepts the bookreview task and dispatches
     without verifying postgres reachability or table count from inside the
     agent container.
   - Cause: `grep -rn reach packages/razorback-plugin-dab/src/` returns
     nothing. Tests reference "bookreview reachability gate" by name in T7's
     description, but no runtime check exists.
   - Effect: there is no gate that would catch (1)-(3) before counting
     rewards.

5. **Per-query verifiers are substring-presence only, with no negative test.**
   - Symptom: an answer of `"2020s"` is graded as correct for "highest-rated
     decade"; an answer that just dumps the SQL file is graded as correct for
     "list these books".
   - Cause: `validate.py` files are vendored verbatim from DAB upstream, and
     DAB upstream defines these as substring-presence checks.
   - Effect: the verifier cannot distinguish a real query result from a
     spurious match. Without a live DB and a reachable-DB precondition, this
     turns into the rubber-stamp we observed.

6. **`artifacts` manifest reports `/logs/artifacts` "empty" yet status is
   tagged success.**
   - Symptom: `steps/main/artifacts/manifest.json` is
     `[{"source": "/logs/artifacts", "destination": "artifacts",
        "type": "directory", "status": "empty"}]`
     for all 9 trials. No artifacts surface the agent's `analyze_books.py` or
     its `answers.json` to the host — only the docker-compose's `main`
     service's mounts do, and harbor doesn't bind `/workspace` out.
   - Cause: no `[task].artifacts` entry collects `/workspace/answers.json`
     or the agent's working files; no `[[steps]].artifacts`.
   - Effect: no host-visible record of what the agent produced; debugging
     this required attaching to live containers, which only worked because
     test runs happened to still be running.

## Fix scope per cause (do NOT implement here; captain decides)

The following are sketches of what each fix would need to land — not
implementations.

| # | Cause | Fix scope sketch |
|---|---|---|
| 1 | Compose in wrong dir | Move `(task_dir / "docker-compose.yaml")` write to `(task_dir / "environment" / "docker-compose.yaml")` AND ensure the bind-mount source is relative to that new compose dir, OR introduce a harbor-mapper plugin that hands harbor the compose explicitly. Update the small handful of plugin tests that assert path layout. Add an integration test that, after `prepare_dataset_tasks`, runs `docker compose -f $task/environment/docker-compose.yaml config` and asserts `dab-postgres` is in the parsed services. |
| 2 | Silent task.toml field drop | Remove the `docker_compose = "docker-compose.yaml"` line from `_task_toml()` (it's a no-op). Optionally add a generator-side schema lint that refuses to emit fields not in harbor's `EnvironmentConfig`. Test: assert the generated task.toml round-trips through `TaskConfig.model_validate_toml` with no extra-keys warning. |
| 3 | Bind-mount path | After fix (1), the relative path becomes `../steps/main/workdir/{sql_file}` (relative to `environment/docker-compose.yaml`). Alternatively, restructure so workdir lives at the same level as compose — either move compose to `steps/main/` or move workdir up. Test: a post-generate check that `docker compose config` resolves all `volumes` to existing host paths, gating in CI. |
| 4 | Missing reachability gate | Add a startup gate that, after `docker compose up --wait` and before the agent runs, execs in the `main` container: `psql -h dab-postgres -U dabench -d bookreview_db -tAc 'select count(*) from books_info'` and asserts >0 rows. Either a per-step healthcheck (StepConfig.healthcheck) or a pre-agent shell hook. Failure → aborted trial with a typed error in `exclude_exceptions` so the run errors visibly instead of green-stamping. |
| 5 | Validator weakness | Outside the scope of this bug — but the agreed-on remediation is: feed validators only the canonical answer string (the JSON-parsed value of `answer`, with the SQL dump explicitly NOT in scope), and add a second-line check that the answer length is bounded so dumping the dataset can't pass. This belongs in spec work, not a quick patch. |
| 6 | No host-visible artifacts | Add `[task].artifacts = ["/workspace/answers.json"]` (or equivalent step-level) to the emitted task.toml so the answer file is downloaded to `steps/main/artifacts/`. Test: integration test that after a trial finishes, `answers.json` is present in the host-side artifacts dir. |

## Sanity / cross-checks performed

- Verified harbor verifier reads `reward.json` and does **not** default to
  success on missing/empty output (`harbor/verifier/verifier.py:201-210`
  raises `RewardFileNotFoundError`). Original report's hypothesis on this
  point was wrong; the 1.0 is genuinely written by our `verify.py`.
- Verified `EnvironmentConfig` has no `docker_compose` field
  (`harbor/models/task/config.py:127-170`).
- Verified, via live `docker inspect`, that no `dab-postgres` exists in any
  bookreview-q1 compose project right now, and that the project config_files
  list contains only harbor's base + prebuilt compose files.
- Verified that all three currently-live `bookreview-q1__*-main-1` containers
  hold the identical `{"answer": "2020s"}` in `/workspace/answers.json` and
  have an agent-authored `/workspace/analyze_books.py` that parses the raw
  `.sql` file — i.e., the agent independently routed around the missing DB
  using the same fallback every time.

## What this means for the rollup metrics

- The "9/9 reward=1.0, pass@1=1.0" headline in
  `9c26daea1ada1c4d/result.json` is meaningless. It reflects:
  - For q1: the four-character substring `"2020"` happened to appear in
    every agent's guess.
  - For q2/q3: the agents had read access to the ground-truth-bearing SQL
    dump (`/workspace/query_dataset/books_info.sql`) and the validators
    accept substring presence.
- The benchmark, as currently wired, **cannot distinguish a working
  agent-DB pipeline from a broken one**. It will return ~1.0 even when no DB
  exists, as demonstrated. This is the worst kind of false positive — silently
  green when everything is wrong.

## Recommendation

Captain should treat this as a blocker on PKG-12 acceptance and on T14/T15.
The minimum remediation needed before any further reward numbers from this
benchmark can be trusted:

1. Land cause-1 + cause-2 + cause-3 fixes together (they're coupled).
2. Land cause-4 (reachability gate) so a future regression in (1)(2)(3) cannot
   silently revive this false-positive mode.
3. Add cause-6 (artifact collection) so debugging future runs doesn't
   require attaching to live containers.

Causes 5 (substring validators) is out of scope for "fix the bug"; it should
be tracked as a separate spec-level concern about DAB validators in general.
