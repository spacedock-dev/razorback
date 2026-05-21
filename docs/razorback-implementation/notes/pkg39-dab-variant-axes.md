# PKG-39 DAB Variant Axes

Reconnaissance used `/home/exedev/dataagentbench`. The dispatched
`~/git/dataagentbench` path was not present in this VM.

## Evidence Inspected

- `/home/exedev/dataagentbench/docs/harness/split-query-mode-into-dispatch-and-context-axes.md`
- `/home/exedev/dataagentbench/docs/harness/context-fresh-query-mode.md`
- `/home/exedev/dataagentbench/docs/harness/_archive/context-resume-single-workflow-gate-freeze.md`
- `/home/exedev/dataagentbench/docs/hypothesis/codex-gpt55-xhigh-hints-spacedock-batch.md`
- `/home/exedev/dataagentbench/benchmark/tests/test_benchctl_sweep.py`
- `/home/exedev/dataagentbench/benchmark/tests/test_benchctl_groups.py`

## Axes

| Axis | DataAgentBench treatment | Required inputs for run planning | PKG-39 Razorback support |
| --- | --- | --- | --- |
| batch | One first-officer session handles all dataset queries. DataAgentBench records this as `query_mode=batch`. | DAB data root, workspace README, batch query mode, Razorback `workspace_variant`, and `hints`. | Generator can emit DAB specs with selected `workspace_variant` and `hints`; batch remains a run-planning label from DataAgentBench. |
| context-fresh | A shared context/model pass is built, then query-local solves run from that fresh context treatment. | DAB data root, context README/query README treatment, workspace/hints selection, and context build provenance. | Documented for run planning only; PKG-39 does not add a Razorback execution mode for context-fresh. |
| context-resume | A single workflow uses a gate/freeze point, records model/context state, and resumes query-local work from that cached point. | DAB data root, single-workflow gate/freeze README mechanism, context cache/provenance, workspace/hints selection. | Documented for run planning only; PKG-39 does not run or generate full context-resume benchmark execution. |

## Current Boundary

PKG-39 generator support covers Razorback-native `harbor_dab`
`workspace_variant` and `hints` fields. Batch, context-fresh, and
context-resume are recorded here as DataAgentBench run-planning axes, not as
new Razorback execution modes in this task.

No DAB benchmark runs were launched for this note.
