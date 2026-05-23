---
id: hbwf3xexrmm39bhjhkyy6qya
title: dab-agent image — preinstall approved duckdb extensions (sqlite + postgres + mongo)
status: backlog
source: Captain directive 2026-05-23 — "we do want the image preinstall work and available"; adopts upstream design at `~/git/dataagentbench/docs/harness/scored-run-egress-taint-and-duckdb-preinstall.md` (status=review upstream)
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

The `dab-agent:latest` image used by every scored DAB cell is built by
`dataagentbench/benchmark/setup.sh setup_isolation()` against
`dataagentbench/benchmark/Dockerfile.agent`. That image installs the
Python `duckdb` package via pip but does NOT preinstall duckdb's
postgres/mongo/sqlite extensions. Today the agent runs `INSTALL postgres`
at attempt time, downloading the extension over public egress on
`dab-net`. That:

- couples scored attempts to public extension-host availability;
- bakes attempt-time downloads into the run-dir provenance;
- breaks on platforms where the public extension repo returns 404
  (probed: HTTP 404 on
  `extensions.duckdb.org/v1.5.3/linux_arm64/mongo.duckdb_extension.gz`,
  blocking mongo-via-duckdb on M-series macs entirely);
- prevents enforcing a read-only rootfs (which would let scored runs
  prove no attempt-time extension installs happened).

Upstream dataagentbench has the design at
`~/git/dataagentbench/docs/harness/scored-run-egress-taint-and-duckdb-preinstall.md`
(filed, status `review`, not yet shipped). This entity adopts that
design in razorback so we can ship without waiting on upstream's
release schedule.

## Acceptance criteria

**AC-1 — Image-side preinstall cache exists at a versioned path.**
The `dab-agent:latest` image carries duckdb extensions for `sqlite`,
`postgres`, and `mongo` under
`/opt/dab/duckdb_extensions/duckdb-<duckdb_version>-<platform>-v1/`,
where `<duckdb_version>` matches the pinned `duckdb` Python package and
`<platform>` is the build-time arch (`linux_amd64` or `linux_arm64`).
Verified by: `docker run --rm dab-agent:latest test -d
/opt/dab/duckdb_extensions/`; `docker run --rm dab-agent:latest ls
/opt/dab/duckdb_extensions/*/` lists three extension files
(`sqlite.duckdb_extension`, `postgres.duckdb_extension`,
`mongo.duckdb_extension`).

**AC-2 — `LOAD` works from the image cache without public network.**
With network egress disabled (`docker run --network none`), a duckdb
session in the image successfully runs `LOAD sqlite`, `LOAD postgres`,
and `LOAD mongo` against `extension_directory` set to the cache root.
Verified by: a smoke script in the image (or invoked from the host)
runs `docker run --rm --network none dab-agent:latest python3 -c
'import duckdb; c = duckdb.connect(config={"extension_directory":
"/opt/dab/duckdb_extensions/<v>"}); c.execute("LOAD sqlite"); c.execute(
"LOAD postgres"); c.execute("LOAD mongo"); print("ok")'` exits 0 with
stdout `ok`.

**AC-3 — Per-run provenance records the cache identity.**
Each `summary.json` (or `provenance.yaml`) records a
`duckdb_extension_cache` block with `duckdb_version`, `platform`,
`cache_path`, `cache_version`, `approved_extensions`, and
`manifest_sha256` per upstream's contract (the
scored-run-egress-taint-and-duckdb-preinstall design §`DuckDB extension
cache contract`). When the image is unavailable or the run is
non-isolated, the field is populated with `available: false` + `reason`,
not omitted.
Verified by: a cycle-2 run-dir post-shipment has the `duckdb_extension_cache`
block at the path mandated by upstream design; a fixture-mode run
populates `available: false`.

**AC-4 — Manifest pins extension bytes.**
The image carries
`/opt/dab/duckdb_extensions/manifest.json` containing
`duckdb_version`, `platform`, `cache_version`, `cache_path`,
`approved_extensions`, per-extension file path + SHA-256, the
`exeuntu_digest`, and the build timestamp. Bumping the pinned duckdb
version requires rebuilding the cache; the build script enforces this.
Verified by: `docker run --rm dab-agent:latest cat
/opt/dab/duckdb_extensions/manifest.json | jq -e '.duckdb_version' &&
... | jq -e '.approved_extensions | index("mongo")' && ... | jq -e
'.exeuntu_digest'`.

**AC-5 — Platform-specific build path handles arm64.**
The build script (`Dockerfile.agent` or a sibling) determines
`<platform>` from `$TARGETARCH` (or equivalent buildkit variable) and
materializes the matching extension cache. On M-series macs (`arm64`)
the build does NOT fall back to amd64 (which would either fail to load
or load incompatibly).
Verified by: build the image on arm64 — manifest reports
`platform: linux_arm64` and AC-2 smoke under `--platform linux/arm64`
exits 0; build on amd64 — manifest reports `platform: linux_amd64`.

## Test plan

- **Mechanism smoke first (per CLAUDE.md):** before touching the
  Dockerfile, probe whether duckdb's mongo extension actually exists
  for `linux_arm64` at the pinned version. If the public repo 404s
  (we already know it does for v1.5.3/linux_arm64/mongo), this entity
  cannot ship on arm64 without sourcing the extension binary from
  somewhere — flag to captain at plan-stage gate. Options: vendor a
  prebuilt mongo extension into the repo, fetch from a duckdb LTS
  channel, or build the extension from source.
- **Image build:** `Dockerfile.agent` adds a layer that installs the
  three extensions into the versioned cache path, writes
  `manifest.json`, and verifies via `LOAD` in the build.
- **Isolation smoke:** `docker run --rm --network none dab-agent:latest`
  loads all three extensions from the cache.
- **End-to-end smoke:** one DAB cell (PATENTS) runs against the new
  image with `--network dab-net` but agent prompt instructs
  `extension_directory=/opt/dab/duckdb_extensions/<v>`. Confirm
  `provenance.yaml` carries the cache block.
- **Variant compatibility:** if the duckdb-unified solver variant
  (sibling entity `795 dab-spacedock-duckdb-unified-db-access`) has
  shipped, run a duckdb-variant smoke under the preinstalled image
  to confirm Phase 2 of that entity is unblocked.

## Out of scope

- **Read-only rootfs enforcement.** Upstream's design pairs preinstall
  with read-only rootfs so attempt-time `INSTALL` provably fails;
  that's a separate enforcement entity. This entity only ships the
  cache.
- **Taint scanner.** The upstream design also ships a scanner
  (`benchmark/lib/taint.py`); not in scope here.
- **Bumping the duckdb Python package.** Whatever version is currently
  pinned in `Dockerfile.agent` stays; the cache is built against that
  version. A future entity can bump both together.
- **The solver-workflow README changes.** Sibling entity `795
  dab-spacedock-duckdb-unified-db-access` owns those; this entity
  only owns the image.

## Depends on

- (none — independent of `an` goal1 rerun and `1s` reducer entity)
- **Useful to land before sibling `795 dab-spacedock-duckdb-unified-db-access`**
  ships its mongo-needing AC; without this entity, that AC depends on
  attempt-time `INSTALL mongo` working over public egress, which we've
  probed as 404 on arm64.

## Resume hook

When this lands, the dab-agent image is a clean isolation surface for
the duckdb-unified solver variant and any future read-only-rootfs work.
The cache identity in provenance lets historical runs be re-derived
against an image+cache pair.
