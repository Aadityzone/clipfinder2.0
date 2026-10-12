# Agent Ownership and Boundaries

Ownership map for the five active agents, updated 2026-10-12. The implementation changes are uncommitted in the shared checkout; private or uncommitted work outside that checkout is not visible.

| Agent | Assigned task / status | Owned files | Read-only boundaries / dependencies |
|---|---|---|---|
| 1 — Integration & QA lead | CF-001 baseline recorded; cross-service contract review and tracker maintenance | `docs/project-tracker/**` | Application code stays with its assigned owner; do not claim end-to-end verification without a safe database and media runtime. |
| 2 — AI pipeline | CF-005 implementation complete at focused-test level; no commit | `ai/services/llm.py`, `ai/tests/test_pipeline.py` | Agent 2 confirms it did not author `ai/highlights.py`, `ai/transcribe.py`, `ai/main.py`, `ai/services/dedup.py`, or `ai/services/render.py`; ownership of these visible diffs is unresolved. |
| 3 — Backend / queue | Audit and proposal only; no implementation | None. Proposed CF-007 files: `web/worker.ts`, `web/app/api/health/route.ts` | Agent 3 confirms it authored none of the visible backend changes. `prisma/schema.prisma`, `web/lib/jobs.ts`, worker/health and added helpers/tests remain unclaimed. No migrations directory exists. |
| 4 — Frontend / workspace | Audit and proposal only; no implementation | None. Proposed UI: `web/app/project/[id]/page.tsx` and optional client component | Agent 4 confirms it authored none of the visible UI or clip API changes. Ownership of `Editor.tsx`, account action components, and caption/edit/export routes is unresolved. |
| 5 — Independent reviewer | Review-only; reviewed CF-005 diff, no blocking contract defect found | No write ownership | Review visible plans/diffs/tests only; private workspaces and unavailable PR tooling remain outside scope. |

## Integration rules
- One accountable owner per task; the current agents share this checkout, so the visible uncommitted diff is the integration surface.
- Define request/response types and state transitions before cross-service changes.
- Do not commit secrets or read production secret values unnecessarily.
- Record exact commands, test results, and commit SHAs.
- Record a proposed task as active only after its owner starts it.
