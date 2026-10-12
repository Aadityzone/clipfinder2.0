# Test and Failure Log

## Initial audit snapshot
- Date: 2026-10-11.
- Source: branch `autonomous/product-ui-rebuild`.
- Method: remote source inspection through GitHub connector.
- Tests executed during this audit: **none**. This environment did not execute the repository's local test commands or access the user's runtime/database/media.
- Therefore there are no new passing/failing test claims from this snapshot.

## Local baseline run
- Date: 2026-10-12.
- Commit / branch: `e408c31` / `autonomous/engineering-orchestration`.
- Environment: Windows workspace; Node dependencies already present; Python 3.13. Database commands/build were given CI-only dummy credentials with loopback PostgreSQL (`127.0.0.1:5432/clipfinder_ci`) and `MEDIA_STORAGE_ROOT=storage/baseline`. The configured Neon database was not contacted. No media or production services were used.
- `npm run prisma:generate` — exit 0; Prisma Client 7.10.0 generated.
- `npx prisma validate --schema prisma/schema.prisma` — exit 0; schema valid.
- `npm --workspace web run typecheck -- --incremental false` — exit 1. `web/app/api/projects/[id]/upload/route.ts:12` reports TS7022 and TS2448: `const exec = promisify(exec)` references its own binding rather than the imported `execFile`.
- `npm run test:storage` — first sandbox run exited 1 with Node test-runner `spawn EPERM`; rerun outside the sandbox exited 0 (4 passed, 0 failed).
- `npm run lint` — exit 1; 4 errors and 38 warnings. The errors are unescaped apostrophes in `web/app/calendar/page.tsx`, `web/app/favorites/page.tsx`, `web/app/project/[id]/long-form/page.tsx`, and `web/app/templates/page.tsx`.
- `npm run build` — sandbox run exited 1 with `spawn EPERM` after compilation; rerun outside the sandbox compiled successfully but exited 1 at TypeScript validation with the same upload-route errors. Next.js emitted dynamic filesystem tracing warnings for `web/lib/storage.ts` and the upload route. Next.js rewrote `web/tsconfig.json` and `web/next-env.d.ts` during the build; both tracked files were restored to their original contents afterward.
- `python -m py_compile ai/main.py ai/schemas.py ai/transcribe.py ai/highlights.py ai/longform.py ai/services/render.py ai/services/media_intelligence.py ai/services/llm.py ai/services/dedup.py ai/services/captions.py` — exit 0.
- `python -m pytest -q -p no:cacheprovider` — collection failed. `cv2` is not installed, and pytest cannot access `pytest-cache-files-ggna0fz3` or `pytest-cache-files-o5gf9xd9` in the workspace.
- Focused command `python -m pytest -q -p no:cacheprovider --ignore=pytest-cache-files-ggna0fz3 --ignore=pytest-cache-files-o5gf9xd9 ai/tests/test_pipeline.py ai/tests/test_boundary_optimization.py ai/tests/test_story_intelligence.py ai/tests/test_creator_feedback.py` — exit 0 (10 passed).
- No DB integration, worker, real-media, rendering artifact, or browser test was performed. Full Python suite remains unverified; CI uses Python 3.12 while this machine uses 3.13.

## Commands to run at baseline
Run from repository root, with local non-production test configuration:
```bash
npm install
npm run prisma:generate
npx prisma validate --schema prisma/schema.prisma
npm run typecheck
npm run test:storage
npm run lint
npm run build
python -m pip install -r ai/requirements.txt
PYTHONPATH=. pytest -q
```
CI currently uses Node 22 and Python 3.12 in `.github/workflows/ci.yml`. Compare local results against CI rather than assuming environments match.

## Known historical failures requiring recheck
Prior audit notes reported two Python failures:
- overlapping windows of one moment should collapse to one candidate, but two were returned;
- out-of-range indexes/timestamps from the model were ignored incorrectly, with expected LLM score blend 25 but observed 10.
These are historical reports, not confirmed current failures. Reproduce against the current branch before fixing.

## Integration test evidence template
For each run, record:
- Commit SHA / branch:
- Exact command:
- Environment (never secrets):
- Exit code:
- Passed/failed/skipped:
- Failure excerpt:
- Fix commit:
- Rerun result:
- End-to-end media fixture and verified artifact, if applicable:

## UI action control checks
- Date: 2026-10-12.
- Branch / base commit: `autonomous/engineering-orchestration` / `e408c31`; UI component and tracker changes are uncommitted.
- Scope: `BillingActions`, scheduled-post `CancelButton`, and analytics `SyncButton`; no API or browser integration was run.
- `npm exec --workspace @clipfinder/web eslint -- app/usage/BillingActions.tsx app/calendar/CancelButton.tsx app/analytics/SyncButton.tsx` — exit 0; focused lint passed.
- `npm --workspace web run typecheck -- --pretty false` — exit 1; blocked by existing `web/app/api/projects/[id]/upload/route.ts:12` errors TS7022 and TS2448 (`const exec = promisify(exec)` references its own binding).
- `git diff --check -- web/app/usage/BillingActions.tsx web/app/calendar/CancelButton.tsx web/app/analytics/SyncButton.tsx docs/project-tracker/FEATURE_INVENTORY.md` — exit 0; no whitespace errors.
- No component test suite or authenticated browser test was run. Billing, analytics, and scheduled-post provider integrations remain unverified.

## Editor and export implementation verification
- Date: 2026-10-12.
- Branch / base: `autonomous/engineering-orchestration` at `e408c31` with shared uncommitted work present; no commit created for this change.
- `python -m pytest -q -p no:cacheprovider ai/tests/test_render.py -k "render_segments or render_output"` — exit 0 (11 passed, 3 deselected). Covers valid disjoint source ranges, invalid/out-of-bounds/overlapping timestamps, and output size/stream/duration checks.
- `python -m py_compile ai/main.py ai/services/render.py ai/tests/test_render.py` — exit 0.
- `npm --workspace web exec -- eslint 'app/project/[id]/Editor.tsx' 'app/api/clips/[id]/edit/route.ts' 'app/api/clips/[id]/captions/route.ts' 'app/api/clips/[id]/export/route.ts'` — exit 0; 0 errors and 1 existing exhaustive-deps warning in `Editor.tsx`.
- `npm --workspace web run typecheck -- --incremental false` — exit 1 on pre-existing `web/app/api/projects/[id]/upload/route.ts:12` TS7022/TS2448 (`exec` self-reference); no errors reported in the edited TypeScript files.
- An unrestricted run of all `ai/tests/test_render.py` cases could not set up the three existing `tmp_path` tests: pytest was denied access to `C:\Users\Aaditya Kumar\AppData\Local\Temp\pytest-of-Aaditya Kumar`. A retry with workspace `--basetemp` still hit Windows access-denied during pytest temp-directory cleanup. The 11 non-fixture validator tests passed in the filtered run above.
- Synthetic FFmpeg artifact check: generated a 4-second `testsrc` + sine MP4 with FFmpeg 9.0.1; invoked `render(source, output, aspect='16:9', segments=[{'start':0.5,'end':3.5}])`; `ffprobe(output)` and `validate_render_output` passed. Observed duration 3.0 s, dimensions 1920x1080, size 91,033 bytes. The temporary fixture directory was removed afterward.
- A separate two-segment render with captions reached `TemporaryDirectory` cleanup but exited with `PermissionError: [WinError 5] Access is denied` for the generated `%TEMP%\clipfinder-caption-*` path; the output was not treated as verified. No output from that attempt was retained in the workspace.
- No database transaction, worker state transition, storage round-trip, browser export, or ranged download was executed. Those integration behaviors remain unverified.
