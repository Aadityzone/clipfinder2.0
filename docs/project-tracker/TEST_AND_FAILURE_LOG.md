# Test and Failure Log

## Initial audit snapshot
- Date: 2026-10-11.
- Source: branch `autonomous/product-ui-rebuild`.
- Method: remote source inspection through GitHub connector.
- Tests executed during this audit: **none**. This environment did not execute the repository's local test commands or access the user's runtime/database/media.
- Therefore there are no new passing/failing test claims from this snapshot.

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
