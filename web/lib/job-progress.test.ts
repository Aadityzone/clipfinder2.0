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

test("deriveProjectProcessingState calculates real progress during DOWNLOADING", () => {
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
  assert.ok(state.sourceProgress >= 40 && state.sourceProgress <= 60);
  assert.equal(state.aiProgress, 0);
  assert.equal(state.clipProgress, 0);
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
  assert.ok(state.aiProgress > 50); // In analyze phase
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

test("formatTimeOnly formats ISO string cleanly", () => {
  const d = new Date("2026-11-09T10:42:01.000Z");
  const formatted = formatTimeOnly(d);
  assert.ok(formatted.length >= 5);
});
