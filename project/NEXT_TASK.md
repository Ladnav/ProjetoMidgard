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
- **Real OCR engine (Tesseract).** The built-in `DigitRecognizer` is too weak for the LATAM
  client's font (misreads "100%" as "%"/"9%"), so exact numeric HP/SP/EXP is not reliable. HP/SP
  healing works fine via the per-column bar-fill reading; exact numbers (and reliable numeric EXP)
  would need a real OCR engine, which adds a dependency — pending approval.
- **Continue the live-game test.** HP/SP reading was validated against the official LATAM client
  (EAC-protected). Still to test end to end: healing actually triggering with real input, then
  combat and looting. Note the standing account-ban risk on the EAC server.
- **Memory-reading is out of scope for LATAM.** The reference bot's live map/entity data comes from
  RAM; the official LATAM client runs Easy Anti-Cheat, so that route would require defeating a
  kernel anti-cheat and will not be built. Feasible only on a private server without EAC/GameGuard.
- **Next feature priority.** No priority is selected yet.
- **Repository lint debt.** The wider codebase carries pre-existing Ruff violations; a cleanup pass
  is unscheduled.

## Guardrail

This document previously stated that only TASK-002 was approved and that automation was prohibited.
That was stale: tasks 003–035 shipped the automation runtime. Do not reintroduce that prohibition —
treat the delivered features as authorized and build on them.
