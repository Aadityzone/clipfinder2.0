import assert from "node:assert/strict";
import test from "node:test";
import { analysisEntitlement, MIN_ANALYSIS_MS, nextRangeChunk, toMediaLocalSegments, toSourceTimestamps, validateAnalysisRange } from "./analysis-range";

const free = analysisEntitlement({ plan: "free", status: "active" });
const pro = analysisEntitlement({ plan: "pro", status: "active" });

test("free access is limited to the existing one-hour baseline; only active Pro gets custom durations", () => {
  assert.equal(free.maxDurationMs, MIN_ANALYSIS_MS);
  assert.equal(free.canSelectCustomDuration, false);
  assert.equal(pro.maxDurationMs, 3 * MIN_ANALYSIS_MS);
  assert.equal(pro.canSelectCustomDuration, true);
  assert.equal(analysisEntitlement({ plan: "pro", status: "cancelled" }).plan, "free");
});

test("range validation uses integer milliseconds and accepts exact source boundaries", () => {
  assert.deepEqual(validateAnalysisRange({ startSeconds: 7200, endSeconds: 10800, sourceDurationSeconds: 10800, entitlement: pro }), {
    startMs: 7_200_000, endMs: 10_800_000, durationMs: 3_600_000,
  });
});

test("range validation rejects missing or non-finite source metadata", () => {
  assert.throws(() => validateAnalysisRange({ startSeconds: 0, endSeconds: 3600, sourceDurationSeconds: undefined, entitlement: pro }));
  assert.throws(() => validateAnalysisRange({ startSeconds: Number.NaN, endSeconds: 3600, sourceDurationSeconds: 7200, entitlement: pro }));
});

test("range validation rejects negative, zero, short, overlong, and out-of-source ranges", () => {
  for (const [startSeconds, endSeconds, sourceDurationSeconds, entitlement] of [
    [-1, 3599, 5000, free],
    [0, 0, 5000, pro],
    [0, 3599.999, 5000, pro],
    [0, 10800.001, 20000, pro],
    [7200, 10801, 10800, pro],
  ] as const) {
    assert.throws(() => validateAnalysisRange({ startSeconds, endSeconds, sourceDurationSeconds, entitlement }));
  }
});

test("short sources are allowed only as a whole-source selection", () => {
  assert.equal(validateAnalysisRange({ startSeconds: 0, endSeconds: 120, sourceDurationSeconds: 120, entitlement: free }).durationMs, 120_000);
  assert.throws(() => validateAnalysisRange({ startSeconds: 5, endSeconds: 120, sourceDurationSeconds: 120, entitlement: pro }));
});

test("free requests cannot exceed the one-hour entitlement", () => {
  assert.throws(() => validateAnalysisRange({ startSeconds: 3600, endSeconds: 7200.001, sourceDurationSeconds: 10000, entitlement: free }));
});

test("a three-hour selected source interval becomes restart-safe one-hour chunks", () => {
  const selection = { sourceStartSeconds: 7200, sourceEndSeconds: 18000, mediaOffsetSeconds: 7200, mediaDurationSeconds: 10800 };
  const first = nextRangeChunk(selection);
  assert.deepEqual([first.localStartSeconds, first.localEndSeconds, first.sourceStartSeconds, first.sourceEndSeconds, first.hasNext], [0, 3600, 7200, 10800, true]);
  const next = nextRangeChunk({ ...selection, cursorSeconds: first.nextCursorSeconds });
  assert.deepEqual([next.localStartSeconds, next.localEndSeconds, next.sourceStartSeconds, next.sourceEndSeconds, next.hasNext], [3600, 7200, 10800, 14400, true]);
  const last = nextRangeChunk({ ...selection, cursorSeconds: next.nextCursorSeconds });
  assert.deepEqual([last.localStartSeconds, last.localEndSeconds, last.sourceStartSeconds, last.sourceEndSeconds, last.hasNext], [7200, 10800, 14400, 18000, false]);
  const queuedPayload = JSON.parse(JSON.stringify({ ...selection, cursorSeconds: next.nextCursorSeconds }));
  assert.deepEqual(nextRangeChunk(queuedPayload), last);
});

test("range timestamp transforms preserve source offsets to millisecond precision", () => {
  const segment = [{ start: 7212.125, end: 7215.5, text: "selected moment" }];
  const local = toMediaLocalSegments(segment, 7200);
  assert.deepEqual(local[0], { start: 12.125, end: 15.5, text: "selected moment" });
  assert.deepEqual(toSourceTimestamps(local, 7200), segment);
});
