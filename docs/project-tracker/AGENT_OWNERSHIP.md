# Agent Ownership and Boundaries

These are proposed workstreams, not a claim that multiple agents were spawned. The current environment's ability to create GPT-6 Luna agents is unconfirmed; work must not be reported as parallel unless it actually happens.

| Workstream | Owned area | Avoid overlap | Outputs |
|---|---|---|---|
| A — Audit / Architecture (lead) | `docs/project-tracker/**`, cross-service contracts | Do not rewrite feature modules without task assignment | Evidence-backed status and interfaces |
| B — AI Pipeline | `ai/**`, Python tests | Do not modify Prisma schema or web worker without agreed contract | Reliable media → transcript → candidates API |
| C — Backend / Queue | `web/lib/jobs.ts`, `web/worker.ts`, API routes, Prisma migrations | Do not independently redesign AI response schema | Durable job lifecycle, auth, idempotency |
| D — Frontend / Workspace | `web/app/**` pages/components | Do not fake job state or mock results in production | UI wired to real persisted results |
| E — Rendering / Export | `ai/services/render.py`, render worker paths, export APIs | Coordinate Clip/Render contract before schema changes | Validated media outputs |
| F — QA / Reliability | Tests and CI workflows | Avoid shared production modules except targeted fixes | Reproducible tests and failure log |
| G — Product readiness | Billing, usage, storage, deployment/observability | Do not change job contracts without lead review | Verified operational/billing boundaries |

## Integration rules
- One accountable owner per task; use separate branches/worktrees when supported.
- Define request/response types and state transitions before cross-service changes.
- Do not commit secrets or read production secret values unnecessarily.
- Record exact commands, test results, and commit SHAs.
- If agent spawning is unavailable, execute dependency-ready tasks sequentially and clearly label them single-agent.
