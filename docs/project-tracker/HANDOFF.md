# Handoff

## Current branch
`autonomous/engineering-orchestration`, created from `autonomous/product-ui-rebuild`.

## Current state
A source-only audit has been recorded in this folder. No code tests, database calls, or media-processing runs have been executed by this audit. Do not describe the pipeline as end-to-end verified.

## Next steps
1. Run baseline commands in `TEST_AND_FAILURE_LOG.md` in an available repo runtime.
2. Verify that `npm --workspace web run worker` is running separately from `npm run dev`.
3. Check `GET /api/health` and AI `GET /health`; note that the inspected web health route does not verify worker liveness.
4. Create a small authorized test project and watch its Job rows progress through INGEST, TRANSCRIBE and ANALYZE.
5. Verify transcript, clips, workspace results, render output and download.
6. Reproduce historical candidate overlap and LLM scoring tests before making a fix.
7. Update this tracker with actual evidence and commits.

## Configuration safety
Do not paste or commit secret values. Only note whether required variables are configured. Never run migrations or tests against production data without explicit environment verification.
