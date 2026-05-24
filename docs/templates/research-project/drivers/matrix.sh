#!/usr/bin/env bash
# ABOUTME: Per-cell matrix dispatcher for ${slug} research repo.
# ABOUTME: Modeled on examples/drivers/dab-paper-matrix.sh — per-cell rk run + audit + score, with smoke gate.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: matrix.sh [--output-dir <path>] [--specs <pattern>] [--max-cell-budget-usd <float>]
                 [--dry-run] [--continue-on-fail]

  --output-dir          Base runs-dir (default: runs)
  --specs               Glob of spec files to dispatch (default: specs/*.frozen.yaml)
  --max-cell-budget-usd Per-cell budget cap threaded as --max-budget-usd-running per-cell file.
  --dry-run             Print the plan, do not dispatch.
  --continue-on-fail    Do not exit on first cell failure; record and continue.

Per-cell pipeline:
  1. rk freeze (if not already frozen)
  2. rk run --max-budget-usd-running <per-cell budget>
  3. smoke gate: subagent-trace-manifest.json captured > 0 (spacedock_solver only)
  4. rk audit --policy strict → audit.json (REJECTs cell on exit 23)
  5. rk score --against-constant <auto from experiment_meta.paper_baseline>
  6. ledger row: spec, status, cost_usd, taint_count
EOF
}

OUTPUT_DIR="runs"
SPECS_GLOB="specs/*.frozen.yaml"
MAX_CELL_BUDGET=""
DRY_RUN=0
CONTINUE_ON_FAIL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir) OUTPUT_DIR="$2"; shift 2;;
    --specs) SPECS_GLOB="$2"; shift 2;;
    --max-cell-budget-usd) MAX_CELL_BUDGET="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    --continue-on-fail) CONTINUE_ON_FAIL=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "unknown flag: $1" >&2; usage; exit 2;;
  esac
done

mkdir -p "$OUTPUT_DIR"
LEDGER="$OUTPUT_DIR/ledger.tsv"
[[ -f "$LEDGER" ]] || printf 'spec\tstatus\trun_dir\tcost_usd\ttaint_count\n' > "$LEDGER"

ok_cells=0
failed_cells=0

for spec in $SPECS_GLOB; do
  [[ -f "$spec" ]] || continue
  echo "== dispatching $spec =="

  if (( DRY_RUN )); then
    echo "  [dry-run] would rk run + audit + score"
    continue
  fi

  budget_args=()
  if [[ -n "$MAX_CELL_BUDGET" ]]; then
    budget_file="$OUTPUT_DIR/.budget-$(basename "$spec" .frozen.yaml).json"
    budget_args=(--max-budget-usd-running "$budget_file")
  fi

  rc=0
  rk run "$spec" --runs-dir "$OUTPUT_DIR" "${budget_args[@]}" || rc=$?

  # Locate the run-dir from harbor's standard layout.
  experiment=$(python -c "import yaml; print(yaml.safe_load(open('$spec'))['experiment'])")
  cell_run_dir=$(ls -dt "$OUTPUT_DIR/$experiment"/*/ 2>/dev/null | head -1)
  cell_run_dir="${cell_run_dir%/}"

  status="ok"
  taint_count=0
  cost_usd="unknown"

  if (( rc != 0 )); then
    status="run_failed"
    failed_cells=$((failed_cells+1))
    printf '%s\t%s\t%s\t%s\t%s\n' "$spec" "$status" "$cell_run_dir" "$cost_usd" "$taint_count" >> "$LEDGER"
    (( CONTINUE_ON_FAIL )) || { echo "FAIL $spec exit=$rc — stopping" >&2; exit 4; }
    continue
  fi

  # Smoke gate: spacedock-variant trials must write subagent-trace-manifest.json
  # with captured > 0. Skipped for non-spacedock agents (claude-cli etc.).
  agent_kind=$(python -c "import yaml; print(yaml.safe_load(open('$spec')).get('agent',{}).get('kind',''))")
  if [[ "$agent_kind" == "spacedock_solver" ]]; then
    missing_smoke=$(find "$cell_run_dir/trials" -maxdepth 2 -name 'subagent-trace-manifest.json' \
      | while read mf; do
          captured=$(python -c "import json; print(json.load(open('$mf')).get('captured',0))")
          [[ "$captured" -gt 0 ]] || echo "$mf"
        done)
    if [[ -n "$missing_smoke" ]]; then
      status="smoke_gate_failed"
      failed_cells=$((failed_cells+1))
      printf '%s\t%s\t%s\t%s\t%s\n' "$spec" "$status" "$cell_run_dir" "$cost_usd" "$taint_count" >> "$LEDGER"
      (( CONTINUE_ON_FAIL )) || { echo "SMOKE FAIL $spec — subagent capture == 0" >&2; exit 4; }
      continue
    fi
  fi

  # Audit gate.
  audit_rc=0
  rk audit "$cell_run_dir" --policy strict --format json \
    > "$cell_run_dir/audit.json" 2> "$cell_run_dir/audit.stderr" || audit_rc=$?
  if (( audit_rc != 0 )); then
    status="audit_tainted"
    taint_count=$(python -c "import json; r=json.load(open('$cell_run_dir/audit.json')); print(sum(1 for t in r.get('trials',[]) if t.get('status') != 'clean'))" 2>/dev/null || echo "1")
    failed_cells=$((failed_cells+1))
    printf '%s\t%s\t%s\t%s\t%s\n' "$spec" "$status" "$cell_run_dir" "$cost_usd" "$taint_count" >> "$LEDGER"
    (( CONTINUE_ON_FAIL )) || { echo "AUDIT FAIL $spec — see $cell_run_dir/audit.json" >&2; exit 4; }
    continue
  fi

  # Score: paper_baseline auto-pulled from experiment_meta.
  rk score "$cell_run_dir" --format json \
    > "$cell_run_dir/score.json" 2> "$cell_run_dir/score.stderr" || true

  ok_cells=$((ok_cells+1))
  printf '%s\t%s\t%s\t%s\t%s\n' "$spec" "$status" "$cell_run_dir" "$cost_usd" "$taint_count" >> "$LEDGER"
done

echo ""
echo "Matrix done: ok=$ok_cells failed=$failed_cells"
(( failed_cells == 0 )) || exit 5
