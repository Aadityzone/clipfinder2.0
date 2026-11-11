import {
  AUTO_RENDER_LIMIT,
  LOOKBACK_CONTEXT_SECONDS,
  PRIORITY_RENDER_TOP_N,
  PROGRESSIVE_CHUNK_SECONDS,
} from "./worker-config";

export interface ProgressiveChunkWindow {
  index: number;
  sourceStartSeconds: number;
  sourceEndSeconds: number;
}

export interface TimedSegmentInput {
  startS: number;
  endS: number;
  text: string;
}

export interface NormalizedSegment {
  start: number;
  end: number;
  text: string;
}

export interface ProgressiveCandidateInput {
  start: number;
  end: number;
  score: number;
  title?: string;
  reason?: string;
  hookText?: string;
  analysis?: unknown;
}

export interface ExistingClipRecord {
  id: string;
  startS: number;
  endS: number;
  score: number | null;
  status: string;
  hasActiveOrReadyRender?: boolean;
}

export interface RenderSelectionItem {
  clipId: string;
  rank: number;
  priority: number;
  isHighPriority: boolean;
}

function round3(value: number): number {
  return Math.round(value * 1000) / 1000;
}

function finiteOr(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

/**
 * Plan sequential progressive chunk windows over [sourceStartSeconds, sourceEndSeconds].
 */
export function progressiveChunkPlan(params: {
  sourceStartSeconds: number;
  sourceEndSeconds: number;
  chunkSeconds?: number;
}): ProgressiveChunkWindow[] {
  const start = Math.max(0, finiteOr(params.sourceStartSeconds, 0));
  const end = Math.max(start, finiteOr(params.sourceEndSeconds, start));
  const chunkSize = Math.max(10, finiteOr(params.chunkSeconds, PROGRESSIVE_CHUNK_SECONDS));
  const span = end - start;
  if (span <= 0) return [];

  const windows: ProgressiveChunkWindow[] = [];
  let cursor = start;
  let index = 0;
  while (cursor < end - 1e-6) {
    const nextEnd = Math.min(end, round3(cursor + chunkSize));
    windows.push({
      index,
      sourceStartSeconds: round3(cursor),
      sourceEndSeconds: nextEnd,
    });
    cursor = nextEnd;
    index += 1;
  }
  return windows;
}

/** Count how many progressive chunks cover a given source span in seconds. */
export function countExpectedChunks(
  spanSeconds: number,
  chunkSeconds: number = PROGRESSIVE_CHUNK_SECONDS
): number {
  if (!Number.isFinite(spanSeconds) || spanSeconds <= 0) return 0;
  const effectiveChunk = Math.max(10, finiteOr(chunkSeconds, PROGRESSIVE_CHUNK_SECONDS));
  return Math.max(1, Math.ceil(spanSeconds / effectiveChunk));
}

/**
 * Containment-sensitive overlap ratio: intersection / shorter interval.
 */
export function intervalOverlapRatio(
  a: { startS: number; endS: number },
  b: { startS: number; endS: number }
): number {
  const aStart = finiteOr(a.startS, -1);
  const aEnd = finiteOr(a.endS, -1);
  const bStart = finiteOr(b.startS, -1);
  const bEnd = finiteOr(b.endS, -1);
  if (aStart < 0 || bStart < 0 || aEnd <= aStart || bEnd <= bStart) return 0;
  const intersection = Math.max(0, Math.min(aEnd, bEnd) - Math.max(aStart, bStart));
  const shortest = Math.min(aEnd - aStart, bEnd - bStart);
  return shortest > 0 ? intersection / shortest : 0;
}

/** Intersection over union of two intervals. */
export function intervalIoU(
  a: { startS: number; endS: number },
  b: { startS: number; endS: number }
): number {
  const aStart = finiteOr(a.startS, -1);
  const aEnd = finiteOr(a.endS, -1);
  const bStart = finiteOr(b.startS, -1);
  const bEnd = finiteOr(b.endS, -1);
  if (aStart < 0 || bStart < 0 || aEnd <= aStart || bEnd <= bStart) return 0;
  const intersection = Math.max(0, Math.min(aEnd, bEnd) - Math.max(aStart, bStart));
  const union = Math.max(aEnd, bEnd) - Math.min(aStart, bStart);
  return union > 0 ? intersection / union : 0;
}

/**
 * Build chronological analysis segments combining lookback context segments from
 * earlier transcript chunks with the current chunk's segments without duplicating timestamps.
 */
export function buildAnalysisSegmentsWithLookback(params: {
  priorSegments: TimedSegmentInput[];
  currentSegments: TimedSegmentInput[];
  chunkStartSeconds: number;
  lookbackSeconds?: number;
}): NormalizedSegment[] {
  const chunkStart = Math.max(0, finiteOr(params.chunkStartSeconds, 0));
  const lookback = Math.max(0, finiteOr(params.lookbackSeconds, LOOKBACK_CONTEXT_SECONDS));
  const windowStart = Math.max(0, chunkStart - lookback);

  const merged: NormalizedSegment[] = [];
  const seenKeys = new Set<string>();

  const pushClean = (seg: TimedSegmentInput) => {
    const start = round3(finiteOr(seg.startS, -1));
    const end = round3(finiteOr(seg.endS, -1));
    const text = String(seg.text ?? "").trim();
    if (!text || start < 0 || end <= start) return;
    const key = `${start.toFixed(2)}:${end.toFixed(2)}`;
    if (seenKeys.has(key)) return;
    seenKeys.add(key);
    merged.push({ start, end, text });
  };

  if (lookback > 0) {
    for (const seg of params.priorSegments) {
      const start = finiteOr(seg.startS, -1);
      const end = finiteOr(seg.endS, -1);
      if (end <= windowStart || start >= chunkStart) continue;
      pushClean(seg);
    }
  }

  for (const seg of params.currentSegments) {
    pushClean(seg);
  }

  merged.sort((a, b) => a.start - b.start || a.end - b.end);
  return merged;
}

/**
 * Deduplicate and refine newly discovered candidates against existing project clips.
 *
 * - Never mutates or duplicates clips whose render is already queued, active, or ready.
 * - Refines an unrendered CANDIDATE clip in-place when an overlapping candidate improves score.
 * - Deduplicates overlapping candidates inside the incoming batch itself.
 */
export function mergeProgressiveCandidates<T extends ProgressiveCandidateInput>(
  existingClips: ExistingClipRecord[],
  incoming: T[],
  options?: { overlapThreshold?: number }
): {
  inserts: T[];
  updates: Array<{ clipId: string; candidate: T }>;
} {
  const threshold = finiteOr(options?.overlapThreshold, 0.45);
  const validIncoming = incoming
    .filter((cand) => {
      const start = finiteOr(cand.start, -1);
      const end = finiteOr(cand.end, -1);
      return start >= 0 && end > start;
    })
    .slice()
    .sort((a, b) => finiteOr(b.score, 0) - finiteOr(a.score, 0));

  const inserts: T[] = [];
  const updates: Array<{ clipId: string; candidate: T }> = [];
  const workingExisting = existingClips.map((c) => ({ ...c }));

  for (const cand of validIncoming) {
    const candSpan = { startS: finiteOr(cand.start, 0), endS: finiteOr(cand.end, 0) };
    const candScore = finiteOr(cand.score, 0);

    let matchedIdx = -1;
    let bestOverlap = 0;
    for (let i = 0; i < workingExisting.length; i += 1) {
      const ex = workingExisting[i];
      const overlap = Math.max(
        intervalOverlapRatio(candSpan, { startS: ex.startS, endS: ex.endS }),
        intervalIoU(candSpan, { startS: ex.startS, endS: ex.endS })
      );
      if (overlap >= threshold && overlap > bestOverlap) {
        bestOverlap = overlap;
        matchedIdx = i;
      }
    }

    if (matchedIdx >= 0) {
      const ex = workingExisting[matchedIdx];
      const locked =
        ex.status === "READY" ||
        ex.status === "RENDERING" ||
        Boolean(ex.hasActiveOrReadyRender);
      if (!locked && candScore > finiteOr(ex.score, 0)) {
        const existingUpdateIdx = updates.findIndex((u) => u.clipId === ex.id);
        if (existingUpdateIdx >= 0) {
          if (candScore > finiteOr(updates[existingUpdateIdx].candidate.score, 0)) {
            updates[existingUpdateIdx] = { clipId: ex.id, candidate: cand };
          }
        } else {
          updates.push({ clipId: ex.id, candidate: cand });
        }
        workingExisting[matchedIdx] = {
          ...ex,
          startS: candSpan.startS,
          endS: candSpan.endS,
          score: candScore,
        };
      }
      continue;
    }

    const dupInBatch = inserts.some((picked) => {
      const span = { startS: finiteOr(picked.start, 0), endS: finiteOr(picked.end, 0) };
      return (
        Math.max(intervalOverlapRatio(candSpan, span), intervalIoU(candSpan, span)) >=
        threshold
      );
    });
    if (dupInBatch) continue;

    inserts.push(cand);
    workingExisting.push({
      id: `pending-${inserts.length}`,
      startS: candSpan.startS,
      endS: candSpan.endS,
      score: candScore,
      status: "CANDIDATE",
      hasActiveOrReadyRender: false,
    });
  }

  return { inserts, updates };
}

/**
 * Select unrendered candidates to dispatch to RENDER jobs ordered by quality score,
 * marking top N global candidates as high priority so early playable clips render first.
 */
export function selectCandidatesForRender(
  clips: ExistingClipRecord[],
  options?: {
    priorityTopN?: number;
    maxAutoRender?: number;
  }
): RenderSelectionItem[] {
  const priorityTopN = Math.max(1, finiteOr(options?.priorityTopN, PRIORITY_RENDER_TOP_N));
  const maxAutoRender = Math.max(
    priorityTopN,
    finiteOr(options?.maxAutoRender, AUTO_RENDER_LIMIT)
  );

  const ranked = clips
    .slice()
    .sort((a, b) => finiteOr(b.score, 0) - finiteOr(a.score, 0));

  const alreadyScheduled = ranked.filter(
    (c) =>
      c.status === "READY" ||
      c.status === "RENDERING" ||
      Boolean(c.hasActiveOrReadyRender)
  ).length;

  let remainingBudget = Math.max(0, maxAutoRender - alreadyScheduled);
  if (remainingBudget <= 0) return [];

  const selections: RenderSelectionItem[] = [];
  for (let idx = 0; idx < ranked.length && remainingBudget > 0; idx += 1) {
    const clip = ranked[idx];
    if (clip.status !== "CANDIDATE" || clip.hasActiveOrReadyRender) {
      continue;
    }
    const isHighPriority = idx < priorityTopN;
    selections.push({
      clipId: clip.id,
      rank: idx + 1,
      priority: isHighPriority ? Math.max(50, 100 - idx) : Math.max(1, 20 - idx),
      isHighPriority,
    });
    remainingBudget -= 1;
  }

  return selections;
}
