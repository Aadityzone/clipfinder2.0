import test from "node:test";
import assert from "node:assert/strict";

import {
  STAGE_TIMEOUT_MS,
  MAX_SOURCE_CHUNK_SECONDS,
  DEFAULT_AI_SERVICE_URL,
  resolveAiServiceUrl,
  isRetryableAiStatus,
  AiServiceError,
  isPermanentFailure,
} from "./worker-config";

// These tests import the real module the worker uses. The previous version
// re-declared the constants inside the test, so it could not detect drift
// between the test and the worker.

test("stage timeout values cover processing without unbounded hangs", () => {
  assert.ok(STAGE_TIMEOUT_MS.INGEST > 3 * 60 * 60 * 1000, "INGEST timeout must exceed the yt-dlp 3h ceiling");
  assert.ok(STAGE_TIMEOUT_MS.TRANSCRIBE >= 2 * 60 * 60 * 1000, "TRANSCRIBE timeout must cover audio chunk transcription");
  assert.ok(STAGE_TIMEOUT_MS.ANALYZE >= 60 * 60 * 1000, "ANALYZE timeout must cover multimodal intelligence");
  assert.ok(STAGE_TIMEOUT_MS.RENDER >= 15 * 60 * 1000, "RENDER timeout must cover clip re-encode");
  assert.ok(STAGE_TIMEOUT_MS.PROBE <= 5 * 60 * 1000, "PROBE timeout must terminate fast on bad media");
  assert.ok(STAGE_TIMEOUT_MS.METADATA <= 2 * 60 * 1000, "METADATA timeout must be a short header lookup");
});

test("every stage timeout is a positive finite number", () => {
  for (const [stage, value] of Object.entries(STAGE_TIMEOUT_MS)) {
    assert.ok(Number.isFinite(value) && value > 0, `${stage} must be a positive number of milliseconds`);
  }
});

test("source chunk size stays bounded for long sources", () => {
  assert.ok(MAX_SOURCE_CHUNK_SECONDS > 0 && MAX_SOURCE_CHUNK_SECONDS <= 3600, "chunks must be bounded to keep work resumable");
});

test("ai service url prefers configuration and falls back to the documented dev port", () => {
  assert.equal(resolveAiServiceUrl({ AI_SERVICE_URL: "http://ai.internal:9000" }), "http://ai.internal:9000");
  assert.equal(resolveAiServiceUrl({ AI_SERVICE_URL: "  http://ai.internal:9000  " }), "http://ai.internal:9000");
  assert.equal(resolveAiServiceUrl({ AI_SERVICE_URL: "" }), DEFAULT_AI_SERVICE_URL);
  assert.equal(resolveAiServiceUrl({}), DEFAULT_AI_SERVICE_URL);
  assert.equal(resolveAiServiceUrl({ AI_SERVICE_URL: undefined }), DEFAULT_AI_SERVICE_URL);
  assert.equal(DEFAULT_AI_SERVICE_URL, "http://127.0.0.1:8001");
});

test("retryable ai statuses distinguish transient faults from bad requests", () => {
  for (const status of [500, 502, 503, 504, 408, 425, 429]) {
    assert.equal(isRetryableAiStatus(status), true, `HTTP ${status} should be retried`);
  }
  for (const status of [400, 401, 403, 404, 405, 409, 410, 415, 422]) {
    assert.equal(isRetryableAiStatus(status), false, `HTTP ${status} should not be retried`);
  }
});

test("AiServiceError exposes status, endpoint and message", () => {
  const notFound = new AiServiceError("/v1/transcribe", 404, "Media file not found");
  assert.equal(notFound.name, "AiServiceError");
  assert.equal(notFound.status, 404);
  assert.equal(notFound.endpoint, "/v1/transcribe");
  assert.equal(notFound.retryable, false);
  assert.match(notFound.message, /HTTP 404/);
  assert.match(notFound.message, /Media file not found/);

  const unavailable = new AiServiceError("/v1/analyze", 503, "");
  assert.equal(unavailable.retryable, true);
  assert.match(unavailable.message, /HTTP 503/);
});

test("permanent failures are not retried", () => {
  assert.equal(isPermanentFailure(new AiServiceError("/v1/ingest", 400, "Unsupported source")), true);
  assert.equal(isPermanentFailure(new AiServiceError("/v1/transcribe", 422, "Invalid range")), true);
  assert.equal(isPermanentFailure(new Error("Missing sourceUrl")), true);
  assert.equal(isPermanentFailure(new Error("Unknown job type: SOMETHING")), true);
  assert.equal(isPermanentFailure(new Error("AI media path is outside shared MEDIA_STORAGE_ROOT. Configure a shared mount.")), true);
  assert.equal(isPermanentFailure(new Error("The source did not provide a valid duration.")), true);
});

test("transient failures stay retryable and unknown errors default to retryable", () => {
  assert.equal(isPermanentFailure(new AiServiceError("/v1/analyze", 503, "upstream down")), false);
  assert.equal(isPermanentFailure(new AiServiceError("/v1/analyze", 429, "rate limited")), false);
  assert.equal(isPermanentFailure(new Error("fetch failed")), false);
  assert.equal(isPermanentFailure(new TypeError("network error")), false);
  assert.equal(isPermanentFailure(new Error("Something we have never seen")), false);
  assert.equal(isPermanentFailure(undefined), false);
});
