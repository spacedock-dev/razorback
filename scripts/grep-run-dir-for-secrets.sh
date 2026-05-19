#!/usr/bin/env bash
# ABOUTME: AC-1 grep gate — fail non-zero if any run-dir file contains plaintext claude auth.
# ABOUTME: Allowed: harbor's templatize_sensitive_env redacted shape (e.g., "sk-a****gAA").
set -euo pipefail
RUN_DIR="${1:?usage: $0 <run-dir> <literal-token>}"
TOKEN="${2:-}"
if [ -z "$TOKEN" ]; then
    echo "usage: $0 <run-dir> <literal-token>" >&2
    echo "  scans <run-dir> for plaintext occurrences of <literal-token>." >&2
    exit 2
fi
matches=$(grep -r --include='*.json' --include='*.yaml' --include='*.yml' --include='*.jsonl' --include='*.txt' --include='*.log' --include='*.toml' -F -- "$TOKEN" "$RUN_DIR" || true)
if [ -n "$matches" ]; then
    echo "AC-1 VIOLATION: literal token found in run-dir:" >&2
    echo "$matches" >&2
    exit 1
fi
echo "AC-1 OK: no plaintext token in $RUN_DIR" >&2
exit 0
