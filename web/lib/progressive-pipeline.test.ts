import test from "node:test";
import assert from "node:assert/strict";
import {
  progressiveChunkPlan,
  countExpectedChunks,
  buildAnalysisSegmentsWithLookback,
  mergeProgressiveCandidates,
  selectCandidatesForRender,
} from "./progressive-pipeline";

test("progressiveChunkPlan splits long spans into contiguous chunks without overlap gaps", () => {
  const windows = progressiveChunkPlan({
    sourceStartSeconds: 100,
    sourceEndSeconds: 850,
    chunkSeconds: 300,
  });
  assert.equal(windows.length, 3);
  assert.deepEqual(windows[0], { index: 0, sourceStartSeconds: 100, sourceEndSeconds: 400 });
  assert.deepEqual(windows[1], { index: 1, sourceStartSeconds: 400, sourceEndSeconds: 700 });
  assert.deepEqual(windows[2], { index: 2, sourceStartSeconds: 700, sourceEndSeconds: 850 });
  assert.equal(countExpectedChunks(750, 300), 3);
});

test("buildAnalysisSegmentsWithLookback includes chronological prior boundary context without duplicating", () => {
  const combined = buildAnalysisSegmentsWithLookback({
    priorSegments: [
      { startS: 10, endS: 20, text: "too early" },
      { startS: 255, endS: 280, text: "boundary setup" },
      { startS: 282, endS: 299, text: "hook lead-in" },
    ],
    currentSegments: [
      { startS: 282, endS: 299, text: "hook lead-in" },
      { startS: 300, endS: 325, text: "chunk payoff" },
    ],
    chunkStartSeconds: 300,
    lookbackSeconds: 60,
  });

  assert.deepEqual(
    combined.map((s) => s.text),
    ["boundary setup", "hook lead-in", "chunk payoff"]
  );
  assert.deepEqual(
    combined.map((s) => s.start),
    [255, 282, 300]
  );
});

test("mergeProgressiveCandidates refines unrendered overlapping candidates and preserves rendered clips", () => {
  const existing = [
    { id: "c1", startS: 20, endS: 45, score: 85, status: "READY", hasActiveOrReadyRender: true },
    { id: "c2", startS: 110, endS: 135, score: 70, status: "CANDIDATE", hasActiveOrReadyRender: false },
  ];
  const incoming = [
    { start: 22, end: 44, score: 99, title: "Duplicate of rendered" },
    { start: 108, end: 138, score: 91, title: "Improved boundary candidate" },
    { start: 210, end: 240, score: 82, title: "New candidate" },
  ];

  const { inserts, updates } = mergeProgressiveCandidates(existing, incoming);
  assert.equal(updates.length, 1);
  assert.equal(updates[0].clipId, "c2");
  assert.equal(updates[0].candidate.score, 91);
  assert.equal(inserts.length, 1);
  assert.equal(inserts[0].title, "New candidate");
});

test("selectCandidatesForRender ranks top candidates with high priority first and respects budget", () => {
  const clips = [
    { id: "c1", startS: 10, endS: 30, score: 75, status: "CANDIDATE", hasActiveOrReadyRender: false },
    { id: "c2", startS: 60, endS: 90, score: 96, status: "CANDIDATE", hasActiveOrReadyRender: false },
    { id: "c3", startS: 120, endS: 150, score: 91, status: "CANDIDATE", hasActiveOrReadyRender: false },
    { id: "c4", startS: 180, endS: 210, score: 88, status: "CANDIDATE", hasActiveOrReadyRender: false },
    { id: "c5", startS: 240, endS: 270, score: 99, status: "READY", hasActiveOrReadyRender: true },
  ];

  const selections = selectCandidatesForRender(clips, { priorityTopN: 3, maxAutoRender: 4 });
  assert.deepEqual(
    selections.map((s) => ({ clipId: s.clipId, isHighPriority: s.isHighPriority })),
    [
      { clipId: "c2", isHighPriority: true },
      { clipId: "c3", isHighPriority: true },
      { clipId: "c4", isHighPriority: false },
    ]
  );
  assert.ok(selections[0].priority > selections[2].priority);
});

