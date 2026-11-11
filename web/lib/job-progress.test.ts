process.env.DATABASE_URL ||= "postgresql://clipfinder_test:test@127.0.0.1:5432/clipfinder_test";

import test from "node:test";
import assert from "node:assert/strict";
import { deriveProjectProcessingState, formatTimeOnly } from "./job-progress";

test("deriveProjectProcessingState correctly handles QUEUED job without worker", () => {
  const now = new Date();
  const state = deriveProjectProcessingState({
    id: "proj_queued_1",
    createdAt: new Date(now.getTime() - 15000),
    updatedAt: now,
    source: {
      id: "src_1",
      type: "YOUTUBE",
      url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      media: [],
    },
    jobs: [
      {
        id: "job_ingest_1",
        type: "INGEST",
        status: "QUEUED",
        progress: 0,
        attempts: 0,
        createdAt: new Date(now.getTime() - 15000),
        updatedAt: new Date(now.getTime() - 15000),
      },
    ],
    clips: [],
    analyses: [],
  });

  assert.equal(state.status, "QUEUED");
  assert.equal(state.technicalDetails.workerStatus, "waiting");
  assert.match(state.diagnosis, /Waiting for an available worker/);
  assert.equal(state.aiProgress, 0);
  assert.equal(state.clipProgress, 0);
  assert.equal(state.isTerminal, false);
});

test("deriveProjectProcessingState does not invent a download percentage", () => {
  const now = new Date();
  const state = deriveProjectProcessingState({
    id: "proj_downloading_1",
    createdAt: new Date(now.getTime() - 30000),
    updatedAt: now,
    source: {
      id: "src_2",
      type: "YOUTUBE",
      media: [],
    },
    jobs: [
      {
        id: "job_ingest_2",
        type: "INGEST",
        status: "DOWNLOADING",
        progress: 0.5,
        attempts: 1,
        startedAt: new Date(now.getTime() - 20000),
        createdAt: new Date(now.getTime() - 30000),
        updatedAt: now,
      },
    ],
    clips: [],
    analyses: [],
  });

  assert.equal(state.status, "PROCESSING");
  assert.equal(state.technicalDetails.workerStatus, "active");
  // The worker currently reports stage checkpoints, not measured bytes downloaded.
  assert.equal(state.sourceProgress, 0);
  assert.equal(state.aiProgress, 0);
  assert.equal(state.clipProgress, 0);
  assert.equal(state.overallProgress, null);
});

test("deriveProjectProcessingState detects STALLED worker when heartbeat is lost", () => {
  const now = new Date();
  const oldHeartbeat = new Date(now.getTime() - 90000); // 90 seconds ago

  const state = deriveProjectProcessingState({
    id: "proj_stalled_1",
    createdAt: new Date(now.getTime() - 120000),
    updatedAt: oldHeartbeat,
    source: {
      id: "src_3",
      type: "UPLOAD",
      media: [],
    },
    jobs: [
      {
        id: "job_ingest_3",
        type: "INGEST",
        status: "DOWNLOADING",
        progress: 0.4,
        attempts: 1,
        startedAt: oldHeartbeat,
        createdAt: new Date(now.getTime() - 120000),
        updatedAt: oldHeartbeat,
        payload: {
          progressState: {
            heartbeatAt: oldHeartbeat.toISOString(),
          },
        },
      },
    ],
    clips: [],
    analyses: [],
  });

  assert.equal(state.status, "STALLED");
  assert.equal(state.technicalDetails.workerStatus, "stalled");
  assert.match(state.diagnosis, /stopped responding/);
  assert.equal(state.canRetry, true);
});

test("deriveProjectProcessingState tracks AI transcription and candidate generation", () => {
  const now = new Date();
  const state = deriveProjectProcessingState({
    id: "proj_analyze_1",
    createdAt: new Date(now.getTime() - 60000),
    updatedAt: now,
    source: {
      id: "src_4",
      type: "YOUTUBE",
      media: [
        {
          id: "med_1",
          durationS: 180,
          hasAudio: true,
          createdAt: new Date(now.getTime() - 50000),
        },
      ],
    },
    jobs: [
      {
        id: "job_analyze_1",
        type: "ANALYZE",
        status: "ANALYZING",
        progress: 0.7,
        attempts: 1,
        startedAt: new Date(now.getTime() - 15000),
        createdAt: new Date(now.getTime() - 20000),
        updatedAt: now,
      },
      {
        id: "job_transcribe_1",
        type: "TRANSCRIBE",
        status: "READY",
        progress: 1,
        attempts: 1,
        createdAt: new Date(now.getTime() - 40000),
        finishedAt: new Date(now.getTime() - 20000),
        updatedAt: new Date(now.getTime() - 20000),
      },
      {
        id: "job_ingest_4",
        type: "INGEST",
        status: "READY",
        progress: 1,
        attempts: 1,
        createdAt: new Date(now.getTime() - 60000),
        finishedAt: new Date(now.getTime() - 40000),
        updatedAt: new Date(now.getTime() - 40000),
      },
    ],
    clips: [],
    analyses: [],
  });

  assert.equal(state.status, "PROCESSING");
  assert.equal(state.sourceProgress, 100); // Media is confirmed
  // The worker's 0.7 stage checkpoint is not a measured analysis fraction.
  assert.equal(state.aiProgress, 0);
  assert.equal(state.clipProgress, 0);
  assert.equal(state.overallProgress, null);
  assert.equal(state.isTerminal, false);
});

test("deriveProjectProcessingState confirms 100% completion across all three rings when READY", () => {
  const now = new Date();
  const state = deriveProjectProcessingState({
    id: "proj_ready_1",
    createdAt: new Date(now.getTime() - 100000),
    updatedAt: now,
    source: {
      id: "src_5",
      type: "YOUTUBE",
      media: [
        {
          id: "med_2",
          durationS: 300,
          hasAudio: true,
          createdAt: new Date(now.getTime() - 90000),
        },
      ],
    },
    jobs: [
      {
        id: "job_analyze_2",
        type: "ANALYZE",
        status: "READY",
        progress: 1,
        attempts: 1,
        createdAt: new Date(now.getTime() - 40000),
        finishedAt: new Date(now.getTime() - 10000),
        updatedAt: now,
      },
    ],
    clips: [
      {
        id: "clip_1",
        status: "READY",
        score: 95,
        createdAt: new Date(now.getTime() - 15000),
      },
      {
        id: "clip_2",
        status: "CANDIDATE",
        score: 88,
        createdAt: new Date(now.getTime() - 15000),
      },
    ],
    analyses: [
      {
        id: "ana_1",
        createdAt: new Date(now.getTime() - 15000),
      },
    ],
  });

  assert.equal(state.status, "READY");
  assert.equal(state.isTerminal, true);
  assert.equal(state.sourceProgress, 100);
  assert.equal(state.aiProgress, 100);
  assert.equal(state.clipProgress, 100);
  assert.equal(state.overallProgress, 100);
  assert.equal(state.candidatesFound, 2);
  assert.match(state.diagnosis, /processing complete/i);
});

test("deriveProjectProcessingState marks an empty completed analysis as READY", () => {
  const now = new Date();
  const state = deriveProjectProcessingState({
    id: "proj_no_candidates",
    createdAt: new Date(now.getTime() - 60000),
    updatedAt: now,
    source: { id: "src_empty", type: "YOUTUBE", media: [] },
    jobs: [{
      id: "job_analyze_empty",
      type: "ANALYZE",
      status: "READY",
      progress: 1,
      attempts: 1,
      createdAt: new Date(now.getTime() - 30000),
      finishedAt: now,
      updatedAt: now,
    }],
    clips: [],
    analyses: [],
  });

  assert.equal(state.status, "READY");
  assert.equal(state.isTerminal, true);
  assert.equal(state.overallProgress, 100);
  assert.equal(state.sourceProgress, 0);
  assert.equal(state.aiProgress, 100);
  assert.equal(state.clipProgress, 100);
  assert.match(state.diagnosis, /no clip candidates/i);
});

test("formatTimeOnly formats ISO string cleanly", () => {
  const d = new Date("2026-11-09T10:42:01.000Z");
  const formatted = formatTimeOnly(d);
  assert.ok(formatted.length >= 5);
});

test("deriveProjectProcessingState never marks READY or 100% clipProgress while renders or chunks remain queued/active", () => {
  const now = new Date();
  const state = deriveProjectProcessingState({
    id: "proj_progressive_1",
    createdAt: new Date(now.getTime() - 90_000),
    updatedAt: now,
    source: {
      id: "src_prog",
      type: "YOUTUBE",
      media: [{ id: "med_prog", durationS: 1800, hasAudio: true, createdAt: new Date(now.getTime() - 80_000) }],
    },
    jobs: [
      {
        id: "j_render_2",
        type: "RENDER",
        status: "QUEUED",
        progress: 0,
        attempts: 0,
        createdAt: now,
        updatedAt: now,
      },
      {
        id: "j_render_1",
        type: "RENDER",
        status: "READY",
        progress: 1,
        attempts: 1,
        createdAt: new Date(now.getTime() - 20_000),
        finishedAt: now,
        updatedAt: now,
      },
      {
        id: "j_transcribe_2",
        type: "TRANSCRIBE",
        status: "TRANSCRIBING",
        progress: 0.3,
        attempts: 1,
        payload: { chunkIndex: 1, totalChunks: 4, continueAfterRange: true },
        startedAt: new Date(now.getTime() - 10_000),
        createdAt: new Date(now.getTime() - 15_000),
        updatedAt: now,
      },
      {
        id: "j_analyze_1",
        type: "ANALYZE",
        status: "READY",
        progress: 1,
        attempts: 1,
        payload: { chunkIndex: 0, totalChunks: 4 },
        createdAt: new Date(now.getTime() - 40_000),
        finishedAt: new Date(now.getTime() - 20_000),
        updatedAt: now,
      },
      {
        id: "j_transcribe_1",
        type: "TRANSCRIBE",
        status: "READY",
        progress: 1,
        attempts: 1,
        payload: { chunkIndex: 0, totalChunks: 4 },
        createdAt: new Date(now.getTime() - 60_000),
        finishedAt: new Date(now.getTime() - 45_000),
        updatedAt: now,
      },
      {
        id: "j_ingest_1",
        type: "INGEST",
        status: "READY",
        progress: 1,
        attempts: 1,
        createdAt: new Date(now.getTime() - 85_000),
        finishedAt: new Date(now.getTime() - 70_000),
        updatedAt: now,
      },
    ],
    clips: [
      { id: "c1", status: "READY", score: 94, createdAt: new Date(now.getTime() - 25_000) },
      { id: "c2", status: "CANDIDATE", score: 88, createdAt: new Date(now.getTime() - 25_000) },
    ],
    analyses: [{ id: "a1", createdAt: new Date(now.getTime() - 25_000) }],
  });

  assert.equal(state.status, "PROCESSING");
  assert.equal(state.isTerminal, false);
  assert.ok(state.clipProgress < 100, `Expected partial clipProgress < 100, got ${state.clipProgress}`);
  assert.ok(state.aiProgress > 0 && state.aiProgress < 100);
  assert.ok((state.overallProgress ?? 0) < 100);
  assert.equal(state.completedClips, 1);
  assert.equal(state.renderedClips, 1);
  assert.equal(state.transcribeChunksCompleted, 1);
  assert.equal(state.totalTranscribeChunks, 4);
  assert.equal(state.analysisChunksCompleted, 1);
  assert.equal(state.queuedRenders, 1);
});
