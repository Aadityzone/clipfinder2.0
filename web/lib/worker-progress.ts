import { db } from "./db";
import type { WorkerJobStatus, JobProgressState, ActivityEvent } from "./processing-types";

/**
 * Persists an activity event and updated progress state inside Job.payload.
 * Server/worker-only module to prevent database dependencies from leaking into client bundles.
 */
export async function recordWorkerProgress(
  jobId: string,
  update: {
    status?: WorkerJobStatus;
    stage?: string;
    stageLabel?: string;
    sourceProgress?: number;
    aiProgress?: number;
    clipProgress?: number;
    overallProgress?: number;
    lastCheckpoint?: string;
    activityMessage?: string;
    candidatesFound?: number;
    completedClips?: number;
    transcribeChunksCompleted?: number;
    totalTranscribeChunks?: number;
    analysisChunksCompleted?: number;
    queuedRenders?: number;
    renderedClips?: number;
  },
  client?: any
) {
  const dbClient = client || db;
  const current = await dbClient.job.findUnique({
    where: { id: jobId },
    select: { payload: true, attempts: true, startedAt: true },
  });
  if (!current) return;

  const payload = (current.payload && typeof current.payload === "object" ? current.payload : {}) as any;
  const existingState = (payload.progressState || {}) as JobProgressState;
  const nowIso = new Date().toISOString();

  const activity: ActivityEvent[] = Array.isArray(existingState.activity) ? [...existingState.activity] : [];
  if (update.activityMessage) {
    activity.push({
      timestamp: nowIso,
      message: update.activityMessage,
      stage: update.stage || existingState.stage,
    });
  }

  const completedStages = new Set(existingState.completedStages || []);
  if (update.lastCheckpoint) {
    completedStages.add(update.lastCheckpoint);
  }

  const nextState: JobProgressState = {
    status: update.status || existingState.status || "PROCESSING",
    stage: update.stage || existingState.stage || "PROCESSING",
    stageLabel: update.stageLabel || existingState.stageLabel || "Processing",
    overallProgress: update.overallProgress ?? existingState.overallProgress ?? 0,
    sourceProgress: update.sourceProgress ?? existingState.sourceProgress ?? 0,
    aiProgress: update.aiProgress ?? existingState.aiProgress ?? 0,
    clipProgress: update.clipProgress ?? existingState.clipProgress ?? 0,
    heartbeatAt: nowIso,
    startedAt: existingState.startedAt || current.startedAt?.toISOString() || nowIso,
    updatedAt: nowIso,
    retryCount: current.attempts,
    completedStages: Array.from(completedStages),
    activity,
    lastCheckpoint: update.lastCheckpoint || existingState.lastCheckpoint,
    candidatesFound: update.candidatesFound ?? existingState.candidatesFound,
    completedClips: update.completedClips ?? existingState.completedClips,
    transcribeChunksCompleted:
      update.transcribeChunksCompleted ?? existingState.transcribeChunksCompleted,
    totalTranscribeChunks:
      update.totalTranscribeChunks ?? existingState.totalTranscribeChunks,
    analysisChunksCompleted:
      update.analysisChunksCompleted ?? existingState.analysisChunksCompleted,
    queuedRenders: update.queuedRenders ?? existingState.queuedRenders,
    renderedClips: update.renderedClips ?? existingState.renderedClips,
  };

  await dbClient.job.update({
    where: { id: jobId },
    data: {
      payload: {
        ...payload,
        progressState: nextState,
      },
    },
  });
}

