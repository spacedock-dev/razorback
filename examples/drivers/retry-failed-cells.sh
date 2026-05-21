#!/usr/bin/env bash
# ABOUTME: Retry just the failed/missing Goal-1 matrix cells one at a time, with
# ABOUTME: workdir cleanup between cells to keep disk usage bounded.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/runs/goal1/matrix"

if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
  if [[ -f "$HOME/.claude/benchmark-token" ]]; then
    CLAUDE_CODE_OAUTH_TOKEN="$(cat "$HOME/.claude/benchmark-token")"
    export CLAUDE_CODE_OAUTH_TOKEN
  fi
fi

prune_workdirs() {
  /usr/bin/find "$OUTPUT_DIR" -path "*/tasks/*/steps/main/workdir/query_dataset/*" -type f -delete 2>/dev/null || true
  /usr/bin/find "$OUTPUT_DIR" -name "_harbor_cache" -type d -prune -exec rm -rf {} + 2>/dev/null || true
}

run_cell() {
  local variant="$1"
  local dataset="$2"
  local spec_frozen="${REPO_ROOT}/examples/specs/goal1/${variant}/${dataset}.frozen.yaml"
  local cell_runs="${OUTPUT_DIR}/${variant}/${dataset}"
  local cell_budget="${cell_runs}/budget.json"

  if [[ ! -f "$spec_frozen" ]]; then
    echo "MISSING frozen spec: $spec_frozen" >&2
    return 3
  fi

  rm -rf "$cell_runs"
  mkdir -p "$cell_runs"
  echo "=== RUN $variant/$dataset ==="
  df -h /Users/clkao 2>&1 | tail -1
  local rc=0
  uv run --project "$REPO_ROOT" rk run \
    "$spec_frozen" \
    --runs-dir "$cell_runs" \
    --max-budget-usd-running "$cell_budget" \
    --allow-alias-drift --allow-plugin-drift \
    2>&1 | tee "${cell_runs}/dispatch.log" || rc=$?

  local result_json=""
  if compgen -G "${cell_runs}/*/*/result.json" > /dev/null; then
    for rj in "${cell_runs}"/*/*/result.json; do
      result_json="$rj"
      break
    done
  fi

  if [[ -n "$result_json" ]]; then
    local cell_run_dir
    cell_run_dir="$(dirname "$result_json")"
    uv run --project "$REPO_ROOT" rk audit "$cell_run_dir" --policy strict --format json \
      > "${cell_run_dir}/audit.json" 2> "${cell_run_dir}/audit.stderr" || true
    case "$variant" in
      spacedock) target="spacedock=0.577" ;;
      direct-minimal|direct-structured) target="direct_baseline=0.4376" ;;
      *) target="" ;;
    esac
    if [[ -n "$target" ]]; then
      uv run --project "$REPO_ROOT" rk score "$cell_run_dir" \
        --against-constant "$target" --format json \
        > "${cell_run_dir}/score.json" 2> "${cell_run_dir}/score.stderr" || true
    fi
  fi

  echo "exit=$rc"
  prune_workdirs
  df -h /Users/clkao 2>&1 | tail -1
  echo "---"
  return $rc
}

# Cells passed as v/d arguments, or auto-detect missing
if [[ $# -gt 0 ]]; then
  for arg in "$@"; do
    v="${arg%%/*}"
    d="${arg##*/}"
    run_cell "$v" "$d" || true
  done
else
  echo "no cells specified; pass arguments like spacedock/PATENTS direct-structured/yelp" >&2
  exit 2
fi
