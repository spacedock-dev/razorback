# Codex ADE dbt Minimal Workflow

Work offline in the task workspace. Do not clear proxy environment variables,
use public network access, or make a network package install part of the
solution. The benchmark instruction is appended below these workflow
instructions. The graded artifact is the final dbt project source state; do not
create an answer file unless the task explicitly asks for one.

Preserve existing dbt dependencies, package files, profiles, seeds, and macros
unless the task explicitly requires changing them. Hidden verifier tests may
depend on the existing project structure and package namespaces.

Do not rely on generated `target/`, `logs/`, or a transient `dbt_packages/`
directory created during the agent run. The verifier may rebuild from source in
an offline environment. If `dbt compile` reports missing packages, inspect the
package config and make the source project self-contained for offline verifier
execution; for example, use already-present local package sources or a minimal
local package/macro replacement that preserves the package namespace expected by
models and tests. Running `dbt deps` against the public registry is not a fix.
Do not replace a package namespace with an incomplete shim: hidden verifier
tests may call package test macros even when visible models only call one macro.
For `dbt_utils`, preserve or provide common verifier-facing APIs such as
equality-test macros, not just model helper macros.

If `/razorback-freeze` exists and has exactly one child directory, write concise
stage notes there as `exploration.md`, `implementation.md`, and `validation.md`.
These notes are for resume/debug context; they are not the graded artifact.

## Stage: Exploration

Before editing, inspect the task instruction, project guidance files,
`dbt_project.yml`, `profiles.yml`, `packages.yml`, `package-lock.yml`, models,
macros, seeds, schema YAML, and existing logs.

Run cheap baseline probes when useful, such as `dbt compile --profiles-dir .`,
targeted `dbt run`, targeted `dbt test`, or log inspection. If a baseline probe
fails because dependencies are missing, treat that as project state to repair
offline, not permission to fetch packages from the network. For data-correctness
tasks, sample relevant source tables and current model outputs: row counts,
nulls, duplicates, key distributions, and representative rows.

Record suspected task type, affected files/models, baseline errors, and useful
data observations before making project changes.

## Stage: Implementation

Classify the task locally as no-op, repair, creation, refactor/config, or mixed.
Make the smallest task-relevant dbt project change, following local naming,
materialization, source, ref, macro, and schema patterns.

Run basic confirmation as part of implementation. Use the cheapest command that
proves the edited area compiles or builds: `dbt compile`, targeted `dbt run`,
targeted `dbt test`, or selected `dbt build`. Fix build/compile errors caused by
your change before moving on. Confirmation must work from source without relying
on network access or scratch artifacts that the verifier will not keep.

## Stage: Validation

Do additional correctness checks beyond "it builds".

For repairs, confirm the original failure mode is gone and the affected output
matches the source-data expectation. For refactors/config changes, check row
counts, schemas, and value-level behavior for affected and downstream models.
For new models or analysis tasks, check required columns, grain, uniqueness,
null behavior, row counts, and representative rows against source data. For
no-op tasks, confirm no project change was needed and leave files untouched.

Run broader dbt validation when practical for the task scope.

## Stage: Finalization

Leave only intended project changes. Remove scratch files unless the dbt project
requires them. Finish with changed files and concise validation evidence.
