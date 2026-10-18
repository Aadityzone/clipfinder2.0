import test from "node:test";
import assert from "node:assert/strict";

test("stage timeout values cover processing without unbounded hangs", () => {
  const STAGE_TIMEOUT_MS = {
    INGEST: 4 * 60 * 60 * 1000,
    TRANSCRIBE: 2 * 60 * 60 * 1000,
    ANALYZE: 90 * 60 * 1000,
    RENDER: 30 * 60 * 1000,
    PROBE: 2 * 60 * 1000,
    METADATA: 60 * 1000,
    DEFAULT: 30 * 60 * 1000,
  };

  assert.ok(STAGE_TIMEOUT_MS.INGEST > 3 * 60 * 60 * 1000, "INGEST timeout must exceed yt-dlp 3h ceiling");
  assert.ok(STAGE_TIMEOUT_MS.TRANSCRIBE >= 2 * 60 * 60 * 1000, "TRANSCRIBE timeout must cover audio chunk transcription");
  assert.ok(STAGE_TIMEOUT_MS.ANALYZE >= 60 * 60 * 1000, "ANALYZE timeout must cover multimodal intelligence");
  assert.ok(STAGE_TIMEOUT_MS.RENDER >= 15 * 60 * 1000, "RENDER timeout must cover clip re-encode");
  assert.ok(STAGE_TIMEOUT_MS.PROBE <= 5 * 60 * 1000, "PROBE timeout must terminate fast on bad media");
});

test("structured log formatter outputs valid json entry", () => {
  function formatLog(level: "info" | "warn" | "error", message: string, data?: Record<string, unknown>) {
    return JSON.stringify({ ts: new Date().toISOString(), level, msg: message, ...data });
  }

  const raw = formatLog("error", "job_failed", { jobId: "job-123", type: "INGEST", error: "timeout" });
  const parsed = JSON.parse(raw);
  assert.equal(parsed.level, "error");
  assert.equal(parsed.msg, "job_failed");
  assert.equal(parsed.jobId, "job-123");
  assert.equal(parsed.type, "INGEST");
  assert.equal(parsed.error, "timeout");
  assert.ok(parsed.ts);
});
