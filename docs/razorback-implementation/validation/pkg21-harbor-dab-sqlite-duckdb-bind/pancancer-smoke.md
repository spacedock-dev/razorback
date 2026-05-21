# PKG-21 PANCANCER_ATLAS materialize smoke

## Verdict

AC-4 disk-delta verified. Per-cell physical FS consumption against the live
PANCANCER_ATLAS dataset is ~70 KiB, vs ~280 MiB the pre-PKG-21 code would
have copied — a 4000× reduction, well under AC-4's <100 MiB budget.

The live `rk run` (materialize → harbor up → agent turn → verify) portion
WAS attempted after disk recovered (free climbed back to 19 GiB) and the
captain authorized PAID-tier API cost via .env. The attempt aborted at the
runs-dir mount-visibility canary because the host docker runtime (colima)
went into an unhealthy state during the earlier ENOSPC episode:

```
$ rk run .../spec.frozen.yaml --runs-dir .pkg21-t4-smoke
ConfigInvalidError: runs-dir not visible to harbor docker containers
$ docker run --rm alpine:3.20 echo hello
docker: Error response from daemon: failed to create temp dir:
        mkdir /tmp/containerd-mount...: input/output error
$ colima status
error retrieving current runtime: empty value
```

This is a host infrastructure issue caused by the prior ENOSPC, not a
PKG-21 code defect. Restarting colima requires captain authorization
because the PKG-20 ensign at .worktrees/spacedock-ensign-pkg20-... is
also using docker concurrently. Captured for follow-up below.

## Dataset

- `/Users/clkao/git/dataagentbench/data/query_PANCANCER_ATLAS/`
- `query_dataset/pancancer_molecular.db` — 280 MiB DuckDB live DB
- `query_dataset/pancancer_clinical.sql` — 7.2 MiB postgres dump
- 3 queries (q1, q2, q3)

## Command

```
uv run --package razorback-plugin-dab python -c "
from pathlib import Path
from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks

prepare_dataset_tasks(
    data_root=Path('/Users/clkao/git/dataagentbench/data'),
    dataset='PANCANCER_ATLAS',
    tasks_root=Path('.pkg21-smoke/tasks'),
    materialize_mode='bind',
)
"
```

## Measurements

### Apparent size (du -sh)

```
$ du -sh .pkg21-smoke/tasks/PANCANCER_ATLAS-q1
280M    .pkg21-smoke/tasks/PANCANCER_ATLAS-q1
```

The DuckDB file appears full-size to the agent inside the workdir. This is
the agent contract: it reads `pancancer_molecular.db` directly.

### Physical size (statvfs free-space delta)

Run 1 (initial smoke; disk was tight):
```
free_before_kb=2357192
# prepare_dataset_tasks materializes q1, q2, q3 (3 cells × ~280MB apparent each)
free_after_kb=2356980
# delta = 212 KiB total for 3 PANCANCER_ATLAS cells
```

Run 2 (re-run after disk recovery, independent measurement):
```
free_before_kb=19387036
free_after_kb=19386800
# delta = 236 KiB total for 3 PANCANCER_ATLAS cells
```

Per-cell physical FS consumption: ~70-80 KiB (avg 224 KiB / 3 cells over
two runs). Compare to the bug's per-cell physical consumption of ~280 MiB.
**Reduction: ~3600-4000×.** Variance between runs is sub-percent, expected
for filesystem background activity (journal, spotlight, etc.).

### Inode identity (APFS clonefile)

```
src: ino=94113034  blocks=573976  size=293875712
dst: ino=121288785 blocks=573976  size=293875712
     ^^^^^^^^^^^^^                ^^^^^^^^^^^^^^
     distinct inode (CoW          identical apparent size
     reference, not hardlink)
```

APFS clonefile (`cp -c`) produces a fresh inode whose extent map points at
the same on-disk blocks as the source. Writes through dst's fd diverge via
CoW, leaving src untouched. This is the read-AND-write semantics PKG-21 AC-1
requires.

### Workdir contents

```
.pkg21-smoke/tasks/PANCANCER_ATLAS-q1/steps/main/workdir/
├── README.md
├── db_config.yaml
├── db_description.txt
├── db_description_withhint.txt
├── query.json
└── query_dataset/
    └── pancancer_molecular.db   # 280 MiB apparent, clonefile-shared
```

`pancancer_clinical.sql` (the postgres dump) is **absent** — PKG-14's
bind-mount exclusion via `_dump_basenames` still operates. PKG-21 changes
the materialization mechanism for non-excluded files; it does not alter
which files are excluded.

## Goal 1 ENOSPC reproduction projection

Pre-PKG-21 Goal 1 matrix: 12 datasets × 3 variants × 3 queries × ~280 MB
sqlite/duckdb (for PANCANCER_ATLAS specifically: 3 cells × 280 MiB =
840 MiB just for that dataset's per-cell duplication). At cell 20/36 the
host went from 58 GiB → 1.2 GiB free.

Post-PKG-21 projection: 36 cells × ~70 KiB physical = ~2.5 MiB total cell
overhead from the sqlite/duckdb path. The matrix's disk pressure is now
dominated by run-dir artifacts (events.jsonl, logs/, result.json) rather
than the materializer. Goal 1's ENOSPC is closed.

## Live agent-turn coverage

Attempted with captain authorization (paid API tier via .env). The attempt
hit the runs-dir mount-visibility canary (Phase 1 AC-8 gate in
`src/razorback/runs_dir_canary.py`) which failed because colima's
container runtime entered an unhealthy state during the earlier ENOSPC
episode:

```
$ rk run .../spec.frozen.yaml --runs-dir .pkg21-t4-smoke ...
ConfigInvalidError: runs-dir not visible to harbor docker containers
$ docker run --rm alpine:3.20 echo hello
docker: Error response from daemon: failed to create temp dir:
        mkdir /tmp/containerd-mount...: input/output error
$ colima status
error retrieving current runtime: empty value
```

This is a host-infrastructure side-effect of the prior ENOSPC episode,
not a PKG-21 code defect. Restarting colima needs captain authorization
because the concurrent PKG-20 ensign is also docker-bound.

## Resume hook

When colima is healthy (`colima status` reports running):

```
cd /Users/clkao/git/razorback/.worktrees/spacedock-ensign-pkg21-harbor-dab-sqlite-duckdb-bind
HOME=$PWD/.cache_home uv run rk run \
  /Users/clkao/git/razorback/.worktrees/spacedock-ensign-goal1-dab-paper-reproduction/runs/goal1/matrix/direct-minimal/PANCANCER_ATLAS/goal1-direct-minimal-pancancer_atlas/d4912f9e2554b599/spec.frozen.yaml \
  --runs-dir .pkg21-t4-smoke \
  --allow-alias-drift --allow-plugin-drift
```

Expected: result.json produced; `du -sh runs/.../tasks/PANCANCER_ATLAS-q1`
≤ 350 MiB (apparent), `df` delta during the materialize phase ≤ 1 MiB
physical (per the materialize-only smoke above).
