import assert from "node:assert/strict";
import test from "node:test";
import { ACTIVE_JOB_STATUSES, getFailureTransition } from "./job-state";

test("retry transitions use bounded exponential backoff", () => {
  const now = new Date("2026-10-12T10:00:00.000Z");

  assert.deepEqual(getFailureTransition(1, now), {
    status: "QUEUED",
    runAfter: new Date(now.getTime() + 15_000),
    finishedAt: null,
  });
  assert.deepEqual(getFailureTransition(2, now), {
    status: "QUEUED",
    runAfter: new Date(now.getTime() + 30_000),
    finishedAt: null,
  });
});

test("the maximum attempt transitions to terminal failure", () => {
  const now = new Date("2026-10-12T10:00:00.000Z");

  assert.deepEqual(getFailureTransition(3, now), {
    status: "FAILED",
    runAfter: null,
    finishedAt: now,
  });
});

test("only in-flight job states can be completed or failed", () => {
  assert.deepEqual(ACTIVE_JOB_STATUSES, [
    "RETRYING", "DOWNLOADING", "INGESTING", "TRANSCRIBING", "ANALYZING", "EDITING", "RENDERING",
  ]);
  assert.equal(ACTIVE_JOB_STATUSES.includes("READY" as never), false);
  assert.equal(ACTIVE_JOB_STATUSES.includes("CANCELLED" as never), false);
  assert.equal(ACTIVE_JOB_STATUSES.includes("FAILED" as never), false);
});
