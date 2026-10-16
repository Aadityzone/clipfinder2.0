# Clip Finder 2.0 Project Tracker

This folder is the evidence-based engineering source of truth. Update it when code, tests, or integrations change; do not infer completion from file presence alone.

## Status vocabulary
- `VERIFIED_COMPLETE`: acceptance criteria demonstrated by relevant tests or end-to-end evidence.
- `IMPLEMENTED_UNVERIFIED`: code exists, but execution/integration evidence is missing.
- `PARTIAL`: a portion of the capability exists; one or more required stages are missing.
- `BROKEN`: a reproduced failure or clear implementation defect is documented.
- `NOT_STARTED`: no implementation located during the current audit.
- `BLOCKED`: cannot progress without an external dependency, credential, access, or decision.

## How to use
1. Read `MASTER_STATUS.md` for the current verified state.
2. Read `TASK_BOARD.md` and pick the highest-priority dependency-ready task.
3. Read `ARCHITECTURE.md` and `AGENT_OWNERSHIP.md` before changing cross-service contracts.
4. Record exact commands/results and failures in `TEST_AND_FAILURE_LOG.md`.
5. Update the relevant inventory and `HANDOFF.md` after each milestone.

## Evidence rule
This initial snapshot is a source inspection of branch `autonomous/product-ui-rebuild` at the time this tracker was created. No local runtime, database, credentials, or media test was executed by this audit. Any item without runtime proof remains unverified. The proposed workstream roles are not claims that parallel agents have been launched.
