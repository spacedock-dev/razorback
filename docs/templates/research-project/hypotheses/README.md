# Hypotheses

One markdown file per hypothesis, named `h<NNNN>-<slug>.md`. The
lifecycle:

| Stage | Action |
|---|---|
| `pending` | Hypothesis seeded — note the question and the proposed solver-workflow change. |
| `propose` | Edit `../solver_workflows/h<NNNN>-<slug>/README.md`; write `../specs/h<NNNN>.yaml`; `rk freeze` the spec. |
| `smoke` | `rk run --n-tasks 5 …` for a cheap sanity check. Tripwire: does the smoke score sit in the same envelope as the baseline smoke? Yes → advance to `full`; no → revisit `propose`. |
| `full` | `rk run …` (no `--n-tasks`) for the full benchmark; chain `rk audit --policy strict` + `rk score` per-cell. |
| `analyze` | `rk diff <baseline-run-dir> <h<NNNN>-run-dir>` for the paired delta. Paste the output into this hypothesis file. Write a verdict line. |
| `conclude` | Promote the hypothesis as the new baseline (update `razorback-research.toml` `@baseline` registry entry) or discard. |

`rk audit --policy strict` is non-optional — the autoresearch loop
is not "live" if hypotheses ship verdicts without a clean audit
attestation paired with the score.
