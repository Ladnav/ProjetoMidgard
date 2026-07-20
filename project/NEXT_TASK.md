# Next Task

## Status

No task is currently in progress. The most recent delivery (2026-07-20, branch
`feature/statistics-trend-chart-real-telemetry`, PR #1) added a real telemetry time series, fixed
runtime bugs that made experience counting, looting accuracy, and window binding ineffective, and
reworked the Runtime/Statistics UI plus an operational Dashboard. See `PROJECT_HISTORY.md` and
`CURRENT_STATE.md`.

## Handoff

Before beginning another task:

1. Read `START_HERE.md` and every file in `project/`.
2. Inspect the repository and Git state; the application is a working automation platform, not a
   bare shell.
3. Define scope, acceptance criteria, exclusions, and verification requirements.
4. Keep changes on a feature branch and open a pull request; do not merge to `main` automatically.

## Open items awaiting Product Owner direction

- **Anti-detection Engineering Decisions.** Computer vision, OCR, and anti-detection were built
  while the external spec still marked them DEFERRED. Decide whether to record them as formal
  approved decisions (see the open decision in `PROJECT_CONTEXT.md`).
- **Next feature priority.** Candidates raised in conversation include copying proven behaviours
  from reference bots (pending a concrete feature list from the Product Owner) and tightening the
  existing modules. No priority is selected yet.
- **Repository lint debt.** The wider codebase carries pre-existing Ruff violations; a cleanup pass
  is unscheduled.

## Guardrail

This document previously stated that only TASK-002 was approved and that automation was prohibited.
That was stale: tasks 003–035 shipped the automation runtime. Do not reintroduce that prohibition —
treat the delivered features as authorized and build on them.
