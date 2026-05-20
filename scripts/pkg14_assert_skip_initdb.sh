#!/usr/bin/env bash
# ABOUTME: PKG-14 AC-8 — confirm trial 2's dab-postgres container SKIPPED init.d.
# ABOUTME: Reads docker compose logs across both trials' run-dirs.
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "usage: $0 <trial1_logs.txt> <trial2_logs.txt>" >&2
    exit 2
fi
trial1="$1"
trial2="$2"

echo "==> AC-8: trial 1 must have RUN init.d on the fresh volume"
grep -q "running /docker-entrypoint-initdb.d/" "$trial1" \
    || { echo "FAIL: trial 1 logs lack 'running /docker-entrypoint-initdb.d/' marker"; exit 1; }

echo "==> AC-8: trial 2 must have SKIPPED init.d on the populated volume"
grep -q "PostgreSQL Database directory appears to contain a database; Skipping initialization" "$trial2" \
    || { echo "FAIL: trial 2 logs lack 'Skipping initialization' marker"; exit 1; }

if grep -q "running /docker-entrypoint-initdb.d/" "$trial2"; then
    echo "FAIL: trial 2 unexpectedly RE-RAN init.d (volume reuse broken)"
    exit 1
fi

echo "PASS: AC-8 — init.d skipped on second trial."
