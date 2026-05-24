#!/usr/bin/env bash
# ABOUTME: Goal 1 matrix dispatcher — 3 variants x 12 datasets x N=1 = 36 cells.
# ABOUTME: For each cell: rk run + rk audit + rk score. Idempotent on existing run-dirs.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: dab-paper-matrix.sh [--output-dir <path>] [--dry-run] [--continue-on-fail]
                          [--spec-root <path>] [--variants <csv>] [--datasets <csv>]
                          [--max-cell-budget-usd <float>]

  --output-dir          Base runs-dir for the 36 cells (default: runs/goal1)
  --spec-root           Root of variant/dataset specs (default: examples/specs/goal1)
  --variants            Comma-separated subset (default: spacedock,direct-structured,direct-minimal)
  --datasets            Comma-separated subset (default: all 12 DAB datasets)
  --dry-run             Print the 36-cell plan, do not dispatch.
  --continue-on-fail    Do not exit on first cell failure; record and continue.
  --max-cell-budget-usd Per-cell budget cap (default: 20.0). Threaded as
                        --max-budget-usd-running per-cell budget.json.
EOF
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SPEC_ROOT="${REPO_ROOT}/examples/specs/goal1"
OUTPUT_DIR="${REPO_ROOT}/runs/goal1"
DRY_RUN=0
CONTINUE_ON_FAIL=0
MAX_CELL_BUDGET_USD="20.0"
DEFAULT_VARIANTS="spacedock,direct-structured,direct-minimal"
DEFAULT_DATASETS="agnews,bookreview,crmarenapro,DEPS_DEV_V1,GITHUB_REPOS,googlelocal,music_brainz_20k,PANCANCER_ATLAS,PATENTS,stockindex,stockmarket,yelp"
VARIANTS="${DEFAULT_VARIANTS}"
DATASETS="${DEFAULT_DATASETS}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --spec-root) SPEC_ROOT="$2"; shift 2 ;;
    --variants) VARIANTS="$2"; shift 2 ;;
    --datasets) DATASETS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --continue-on-fail) CONTINUE_ON_FAIL=1; shift ;;
    --max-cell-budget-usd) MAX_CELL_BUDGET_USD="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown flag: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
  if [[ -f "$HOME/.claude/benchmark-token" ]]; then
    CLAUDE_CODE_OAUTH_TOKEN="$(cat "$HOME/.claude/benchmark-token")"
    export CLAUDE_CODE_OAUTH_TOKEN
  fi
fi

IFS=',' read -r -a VARIANT_ARR <<< "$VARIANTS"
IFS=',' read -r -a DATASET_ARR <<< "$DATASETS"

mkdir -p "$OUTPUT_DIR"
LEDGER="${OUTPUT_DIR}/dispatch-ledger.tsv"
if [[ ! -f "$LEDGER" ]]; then
  printf 'variant\tdataset\tspec_frozen\truns_dir\tstatus\texit_code\tcost_usd\n' > "$LEDGER"
fi
FAILURES_LOG="${OUTPUT_DIR}/dispatch-failures.tsv"

total=0
for v in "${VARIANT_ARR[@]}"; do
  for d in "${DATASET_ARR[@]}"; do
    total=$((total+1))
    spec_frozen="${SPEC_ROOT}/${v}/${d}.frozen.yaml"
    cell_runs="${OUTPUT_DIR}/${v}/${d}"
    if (( DRY_RUN )); then
      printf '%2d  %s/%s\n      spec=%s\n      runs_dir=%s\n' \
        "$total" "$v" "$d" "$spec_frozen" "$cell_runs"
    fi
  done
done

if (( DRY_RUN )); then
  echo ""
  echo "Total cells: $total (expect 3 x 12 = 36 with defaults)"
  echo "Trials per cell: 1 (per captain directive 2026-05-20)"
  exit 0
fi

# Validate frozen specs exist before any dispatch
missing=0
for v in "${VARIANT_ARR[@]}"; do
  for d in "${DATASET_ARR[@]}"; do
    spec_frozen="${SPEC_ROOT}/${v}/${d}.frozen.yaml"
    if [[ ! -f "$spec_frozen" ]]; then
      echo "missing frozen spec: $spec_frozen" >&2
      missing=$((missing+1))
    fi
  done
done
if (( missing > 0 )); then
  echo "refuse to dispatch: $missing frozen specs missing" >&2
  echo "run examples/drivers/generate-dab-paper-matrix-specs.py --freeze first" >&2
  exit 3
fi

ok_cells=0
failed_cells=0
skipped_cells=0
cell_index=0

for v in "${VARIANT_ARR[@]}"; do
  for d in "${DATASET_ARR[@]}"; do
    cell_index=$((cell_index+1))
    spec_frozen="${SPEC_ROOT}/${v}/${d}.frozen.yaml"
    cell_runs="${OUTPUT_DIR}/${v}/${d}"
    mkdir -p "$cell_runs"
    cell_budget="${cell_runs}/budget.json"

    # Idempotence: skip if a clean result.json already exists with n_completed_trials >= trials.
    completed_marker=""
    if compgen -G "${cell_runs}/*/*/result.json" > /dev/null; then
      for rj in "${cell_runs}"/*/*/result.json; do
        if python3 -c "
import json, sys
with open('$rj') as f:
    body = json.load(f)
stats = body.get('stats') or {}
n_completed = stats.get('n_completed_trials', 0)
n_errored = stats.get('n_errored_trials', 0)
sys.exit(0 if n_completed >= 1 and n_errored == 0 else 1)
" 2>/dev/null; then
          completed_marker="$rj"
          break
        fi
      done
    fi
    if [[ -n "$completed_marker" ]]; then
      echo "[$cell_index/$total] SKIP $v/$d (already completed: $completed_marker)"
      skipped_cells=$((skipped_cells+1))
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$v" "$d" "$spec_frozen" "$cell_runs" "skip" "0" "n/a" >> "$LEDGER"
      continue
    fi

    echo "[$cell_index/$total] RUN $v/$d -> $cell_runs"
    rc=0
    uv run --project "$REPO_ROOT" rk run \
      "$spec_frozen" \
      --runs-dir "$cell_runs" \
      --max-budget-usd-running "$cell_budget" \
      --allow-alias-drift --allow-plugin-drift \
      2>&1 | tee "${cell_runs}/dispatch.log" || rc=$?

    cost_usd="unknown"
    result_json=""
    if compgen -G "${cell_runs}/*/*/result.json" > /dev/null; then
      for rj in "${cell_runs}"/*/*/result.json; do
        result_json="$rj"
        break
      done
      if [[ -n "$result_json" ]]; then
        cost_usd="$(python3 -c "
import json
with open('$result_json') as f:
    body = json.load(f)
trials = body.get('trials') or []
costs = [t.get('cost_usd') for t in trials if t.get('cost_usd') is not None]
if not costs:
    print('null')
else:
    print(sum(costs))
" 2>/dev/null || echo "unknown")"
      fi
    fi

    status="ok"
    if (( rc != 0 )); then
      status="run_failed"
      failed_cells=$((failed_cells+1))
      printf '%s\t%s\t%d\t%s\n' "$v" "$d" "$rc" "$spec_frozen" >> "$FAILURES_LOG"
      if (( ! CONTINUE_ON_FAIL )); then
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
          "$v" "$d" "$spec_frozen" "$cell_runs" "$status" "$rc" "$cost_usd" >> "$LEDGER"
        echo "FAIL [$cell_index/$total] $v/$d exit=$rc — stopping (use --continue-on-fail to keep going)" >&2
        exit 4
      fi
    else
      ok_cells=$((ok_cells+1))

      # Per-cell verify-stage gate runs BEFORE rk score; a failing gate rolls
      # the cell back from ok_cells to failed_cells and skips scoring.
      if [[ -n "$result_json" ]]; then
        cell_run_dir="$(dirname "$result_json")"

        # Gate 1 (ne): spacedock-variant cells must show >=1 subagent dispatch
        # (Task/Agent tool_use) in the inner claude session. The post-run hook
        # in SpacedockSolverAgent.run writes subagent-trace-manifest.json one
        # level above the per-trial dir (adjacent to provenance.yaml). The
        # validator's exit code 2 means the cell silently degraded back to
        # single-agent execution — REJECT it rather than scoring it as a real
        # spacedock crew-loop result.
        if [[ "$v" == "spacedock" ]]; then
          smoke_rc=0
          uv run --project "$REPO_ROOT" python -m razorback.agents.subagent_smoke \
            "$cell_run_dir" > "${cell_run_dir}/subagent-smoke.log" 2>&1 || smoke_rc=$?
          if (( smoke_rc != 0 )); then
            status="subagent-dispatch-missing"
            failed_cells=$((failed_cells+1))
            ok_cells=$((ok_cells-1))
            printf '%s\t%s\t%d\t%s\n' "$v" "$d" "$smoke_rc" "$spec_frozen" >> "$FAILURES_LOG"
            printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
              "$v" "$d" "$spec_frozen" "$cell_runs" "$status" "$smoke_rc" "$cost_usd" >> "$LEDGER"
            echo "REJECT [$cell_index/$total] $v/$d — $status (see ${cell_run_dir}/subagent-smoke.log)" >&2
            if (( ! CONTINUE_ON_FAIL )); then
              exit 6
            fi
            continue
          fi
        fi

        # Gate 2 (wp): External-oracle audit — rk audit --policy strict scans
        # the cell's trajectory for the DAB verify-stage forbidden-pattern list
        # (huggingface, load_dataset, hf://, from datasets import, named
        # canonical-data pip installs, web tools, etc.). Fires for ALL variants
        # — NOT variant-gated. razorback.audit.claude_code adapts the claude-cli
        # trace shape; razorback.audit.taint owns the patterns.
        # Exit-code mapping: 0 clean / 23 cheating / other non-zero error.
        audit_rc=0
        uv run --project "$REPO_ROOT" rk audit "$cell_run_dir" --policy strict --format json \
          > "${cell_run_dir}/audit.json" 2> "${cell_run_dir}/audit.stderr" || audit_rc=$?
        if (( audit_rc == 23 )); then
          status="external-oracle-cheating"
          ok_cells=$((ok_cells-1))
          failed_cells=$((failed_cells+1))
          printf '%s\t%s\t%d\t%s\n' "$v" "$d" "$audit_rc" "$spec_frozen" >> "$FAILURES_LOG"
          printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$v" "$d" "$spec_frozen" "$cell_runs" "$status" "$audit_rc" "$cost_usd" >> "$LEDGER"
          echo "REJECT [$cell_index/$total] $v/$d external-oracle-cheating — see ${cell_run_dir}/audit.json" >&2
          continue
        elif (( audit_rc != 0 )); then
          status="external-oracle-audit-error"
          ok_cells=$((ok_cells-1))
          failed_cells=$((failed_cells+1))
          printf '%s\t%s\t%d\t%s\n' "$v" "$d" "$audit_rc" "$spec_frozen" >> "$FAILURES_LOG"
          printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$v" "$d" "$spec_frozen" "$cell_runs" "$status" "$audit_rc" "$cost_usd" >> "$LEDGER"
          echo "ERROR  [$cell_index/$total] $v/$d external-oracle-audit-error rc=$audit_rc — see ${cell_run_dir}/audit.stderr" >&2
          continue
        fi

        # Score: --against-constant per variant.
        case "$v" in
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
    fi

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$v" "$d" "$spec_frozen" "$cell_runs" "$status" "$rc" "$cost_usd" >> "$LEDGER"
  done
done

echo ""
echo "Matrix done: ok=$ok_cells failed=$failed_cells skipped=$skipped_cells (total=$total)"
if (( failed_cells > 0 )); then
  exit 5
fi
