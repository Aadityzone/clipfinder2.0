# Agent 3 QA audit and baseline

Audit date: 2026-11-09  
Branch: `agent3/qa-reliability` (branched from the local `fix/cuda-fallback-and-worker-env` worktree)  
Scope: repository review before QA infrastructure changes. Existing uncommitted frontend files were present at start and are retained.

## Initial repository audit

### Existing verification

- GitHub Actions has a `web` job for Prisma client generation/schema validation, TypeScript, Node unit tests, ESLint and production build; a `python` job installs `ai/requirements-ci.txt`, compiles core modules and runs pytest.
- A manual, rights-authorized real URL smoke workflow runs the Python smoke pipeline and uploads artifacts. It does not exercise registration, PostgreSQL persistence, the Next.js worker, browser UI, editing API or export route.
- Web tests use Node's built-in test runner through `tsx`; the discovered test files cover jobs, storage, worker config/environment, source URL validation and analysis ranges.
- Python tests cover auth helpers, download, transcription, analysis/ranking, evaluation, long-form, rendering and AI service routes. The current discovered suite has no live DB-backed integration fixture.
- No Playwright config, Playwright dependency, browser acceptance suite, migration history or CI database service was found. The documented setup uses `prisma db push`.
- Existing evaluation tooling computes interval IoU, Precision@K, Recall@K, F1@K, matched IoU and label-free structural diagnostics. No human-labelled evaluation dataset was found, so no quality score can be claimed.
- Existing media smoke tooling probes, transcribes, analyzes, ranks, renders and probes output. Existing artifacts record real local runs, including a 734.2-second 854x356 source with audio, 22 transcript segments, 40 candidates and 3 rendered files. They contain no per-stage wall times, so they do not establish a real-time factor or the 1-hour target.

### Integration observations

- Concurrent UI work now includes an adaptive polling processing workspace, status route, three rings and mascot. The latest code has unresolved TypeScript, lint and production-build failures (QA-008–011). No browser suite exists, so reconnection, actual progress semantics, animation cost, layout stability and editor behavior are unverified.
- The new progress derivation applies fixed phase floors and weights to job `progress`, even where the worker progress is estimated; the resulting rings are not all measured work completion. Treat current displayed percentages as unverified and potentially misleading.
- The worker includes lease-aware job claiming/checkpointing, heartbeat updates, bounded retry handling, media chunk/range conversion, artifact verification, and render completion paths. Unit tests use fake clients; concurrent claims and restart recovery have not been proven against PostgreSQL.
- The AI `/health` endpoint only considers FFmpeg, FFprobe and yt-dlp. A healthy response does not prove Whisper/model readiness.
- Ownership checks are present across many routes by code inspection, but cross-user isolation has not been exercised against a real database/session.
- The current UI status list and worker status transitions are separate surfaces. Automated contract coverage is missing for all stages and the ring values.
- No six-hour/long-source end-to-end run was found. The worker has one-hour range/chunk logic, but continuation ordering, global timestamp integrity and final READY gating have not been validated as a complete job chain.

## Baseline run results

These were run before QA changes on the branched worktree.

| Check | Result | Evidence / limitation |
|---|---|---|
| `npm run typecheck` | Initially passed; latest tree fails | After concurrent UI edits, `web/app/project/[id]/page.tsx` passes `initialState` which is absent from `ProcessingExperienceProps`. |
| `npm run test:web` | Passed on latest tree | 37 passed, 0 failed, including new progress-state unit tests. The suite is unit-level and does not render browser routes. |
| `python -m pytest -q -p no:cacheprovider ai/tests` | Passed | 259 passed, 1 upstream Starlette deprecation warning. This run included the added smoke timing assertions. |
| Focused smoke tests | Passed | `ai/tests/test_smoke_pipeline.py`: 8 passed. |
| `npm run lint` | Latest tree fails | One error in `ProcessingWorkspace.tsx`: direct fetch invocation in effect synchronously leads to state updates (React hooks lint rule); 45 warnings also reported. |
| `npm run build` | Latest tree fails | Client import trace reaches `@prisma/adapter-pg` / `pg` from `ProcessingWorkspace.tsx` through runtime `formatTimeOnly` imported from DB-backed `web/lib/job-progress.ts`; `util/types` cannot be resolved for the client bundle. |
| `npx prisma validate --schema prisma/schema.prisma` | Passed | Schema is valid. No database migration validation is available because there is no migration history. |
| Real-media smoke | No fresh result | Existing artifact `artifacts/ai-smoke-1018/report.json` records a 734.2-second real source, but lacks timings. The attempted fresh run produced no artifact, so it is not counted. No one-hour or product E2E claim follows. |

## Initial bug and risk register

| ID | Severity | Issue | Reproduction / expected / actual | Root cause and files | Proposed response / status |
|---|---|---|---|---|---|
| QA-001 | P1 | Product E2E path is unverified | Start from registration, submit a source, wait, edit, render and play export. Expected all persisted stages; actual: no automated flow exists. | CI has no PostgreSQL service or browser suite; `ci.yml`, API routes, `worker.ts`. | Add testable acceptance entry points and make a manual setup/runbook explicit. Open. |
| QA-002 | P1 | Worker/database recovery lacks DB integration evidence | Run concurrent workers and restart during an active job. Expected one claim and safe recovery; current test evidence uses fake clients. | `web/lib/jobs.test.ts`, `web/lib/jobs.ts`, `web/worker.ts`; no DB integration job. | Add opt-in PostgreSQL integration coverage/CI service where safe. Open. |
| QA-003 | P2 | Processing UI hides connectivity loss | Disconnect job API while processing. Expected visible stale/reconnecting state; inspected polling catch silently ignores errors. | `ProcessingJourney.tsx`. | Add component/browser integration coverage; coordinate before frontend edits. Open. |
| QA-004 | P2 | Health can overstate model readiness | Call `/health` with media binaries installed and Whisper unavailable. Expected readiness distinction; current check only covers FFmpeg, FFprobe and yt-dlp. | `ai/main.py`. | Add startup/readiness acceptance check or clarify health semantics with Agent 1. Open. |
| QA-005 | P2 | Performance target is unmeasured | Process 1-hour source on RTX 4050 and CPU fallback. Expected stage timing + resource profile; no such record exists. | Existing smoke reports omit timings/resource sampling. | Add repeatable timings in smoke report; resource sampling still needs a platform-specific collector. In progress. |
| QA-006 | P2 | Long-source chunk guarantees are unverified | Interrupt/retry a multi-chunk project and inspect coverage/global timestamps/final status. | Worker range chain and `analysis-range.ts`; no end-to-end chunk fixture. | Add deterministic range-chain tests and a permitted long-media run. Open. |
| QA-007 | P2 | AI quality is unmeasured | Run genre-specific predictions against held-out human-labelled moments. Expected real metrics; no human-labelled data is present. | Evaluation CLI exists, corpus absent. | Do not fabricate labels; establish dataset protocol and run once rights-authorized labels exist. Open. |
| QA-008 | P1 | Processing page cannot build with current UI integration | Run `npm run build`. Expected a server-rendered page with client-safe UI; actual build resolves database adapter into the browser bundle and fails on Node `util/types`. | `ProcessingWorkspace.tsx` imports runtime `formatTimeOnly` from `job-progress.ts`, which imports `db`; `web/lib/job-progress.ts`, `web/components/ProcessingWorkspace.tsx`. | Move pure/shared formatting and types to a client-safe module or use a type-only import and local pure formatter. Frontend owner action required. Open. |
| QA-009 | P1 | Processing page prop contract fails TypeScript | Run `npm run typecheck`. Expected route and component props to agree; actual `page.tsx` passes undeclared `initialState`. | `web/app/project/[id]/page.tsx`, `ProcessingExperience.tsx`. | Align prop interface/call site. Frontend owner action required. Open. |
| QA-010 | P2 | UI reports progress values derived from heuristic stage weights | Inspect `deriveProjectProcessingState` with a running job lacking measured byte/frame/model counters. Expected progress to remain unknown/indeterminate where no measured fraction exists; actual stage formulas/floors synthesize percentages such as 5%, 25–85%, and 50–95%. | `web/lib/job-progress.ts`. | Use measured stage counters or indeterminate display; label phase state without a fabricated percent. Frontend/backend owners coordinate. Open. |
| QA-011 | P2 | Processing UI lint failure | Run `npm run lint`. Expected no lint errors; actual React `set-state-in-effect` error at initial `fetchStatus()` call in `ProcessingWorkspace.tsx`. | `web/components/ProcessingWorkspace.tsx`. | Schedule poll in an async callback/timer or use a subscription callback that updates from the external fetch. Frontend owner action required. Open. |

## Coverage map and remaining gaps

- Authentication: unit coverage exists for password/session helpers and AI service secret auth. Registration/login/logout persistence, expiration, protected page navigation and cross-user DB access lack full-stack tests.
- Projects and sources: source URL validation is unit tested. Project creation, duplicate handling, ingestion failure and metadata persistence lack DB-backed route tests.
- Worker: job state transitions and worker configuration have unit tests. Claim concurrency, lease expiration under PostgreSQL, process restart, cancellation during external work, and idempotent artifact recovery lack integration evidence.
- UI/editor: no browser suite discovered. Candidate loading, autosave, timeline controls, progress reconnection, reduced motion and download playback are unverified in a browser.
- Media: AI unit tests and smoke scripts exist. Current recorded media smoke is ~12 minutes, not the required duration ladder; GPU/CPU performance and video decoding playback are not measured in a stable report.
- Storage/database: storage adapter has unit tests, but failed upload/restart consistency and DB/storage reconciliation are not tested with a live backend.

## Production readiness conclusion

Not production-ready on the evidence available. TypeScript passes, and an existing real-media artifact demonstrates a local Python pipeline run. Product journey, live DB and worker recovery, browser integration, target-hardware performance, long-video completion and human-rated selection quality remain unproven. No actual acceptance or hardware benchmark should be declared until those runs complete.

## Next actions

1. Resolve the current processing UI build/type/lint failures with its owner, then rerun all web gates.
2. Instrument actual smoke stage durations and report source/output measurements.
3. Add deterministic acceptance checks for API contracts and UI progress state using installed frameworks.
4. Add opt-in live PostgreSQL tests with an isolated test database and clear migration/setup requirements.
5. Run rights-authorized source duration ladder and RTX 4050/CPU benchmark; preserve raw reports.
6. Populate the evaluation CLI with held-out human labels before reporting genre metrics.

## Follow-up review — 2026-11-09

The following corrections were made on `audit/truthful-processing-progress` after reviewing the committed agent integration branch:

- Processing rings now expose verified milestones only. The worker's stage checkpoint values are not measured download/transcription/render fractions, so they are no longer converted into invented percentages.
- Overall progress is unknown (`null`) until the pipeline reaches a verified READY state; the UI displays an em dash rather than `0%` or a weighted estimate.
- A completed analysis with zero qualifying candidates is now terminal READY with an explicit empty-result diagnosis, rather than falling through to the active-processing branch.
- Clip edit persistence (edit row, clip boundaries/status, and creator event) is now one database transaction.
- Render creation and its durable RENDER job are now one database transaction, preventing orphan queued render records.
- Source URL validation now resolves hostnames and rejects any private/non-global DNS answer. This is a preflight defense only; production must still enforce outbound network restrictions to prevent DNS rebinding between validation and the downloader connection.
- Disk-capacity inspection now fails closed when the filesystem cannot report free space.
- Added regression tests for truthful progress, empty analysis completion, DNS-to-private and mixed DNS answers, and disk-capacity inspection failure.
- Removed the tracked generated `web/tsconfig.tsbuildinfo` artifact from this audit branch.

### Validation status after follow-up

These changes were committed through the GitHub repository interface. This environment could not clone the repository or execute its local npm/Python test commands, and the audit branch has no CI run attached to its head. Therefore the new tests are **added but not yet executed**. Do not treat this follow-up as a passing build or production acceptance.

### Remaining repository hygiene and integration blockers

- The integration branch still contains the `.agent4-integration` and `.agent5-ai-worktree` gitlink entries. They are not readable as ordinary files through the repository contents API and should be removed if they are accidental worktree/submodule pointers; they must not be merged blindly.
- The older open PR `#24` also contains a `.ai-pipeline-worktree` gitlink, a temporary patch file, pytest scratch artifacts, and tracked build output. It should be cleaned or superseded rather than merged as-is.
- Open PRs `#24` and `#25` are marked non-mergeable and are based on stale commits. Rebase/reconcile against current `main` before considering either.
- No current head CI evidence was available for the aggregate agent branch. The full browser, PostgreSQL concurrency/recovery, long-source acceptance, target-hardware performance, and human-labelled quality evaluation gaps remain open.
