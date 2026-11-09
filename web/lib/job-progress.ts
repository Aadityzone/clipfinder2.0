export {
  type WorkerJobStatus,
  type ActivityEvent,
  type JobProgressState,
  type TechnicalDetails,
  type ProjectProcessingState,
  formatTimeOnly,
} from "./processing-types";
import type {
  WorkerJobStatus,
  ActivityEvent,
  JobProgressState,
  TechnicalDetails,
  ProjectProcessingState,
} from "./processing-types";

const STALLED_THRESHOLD_MS = 60_000; // 60 seconds without heartbeat marks active job as stalled

/**
 * Derives comprehensive processing state and honest real-world progress across all 3 rings
 * from the database records of a Project.
 */
export function deriveProjectProcessingState(project: {
  id: string;
  createdAt: Date;
  updatedAt: Date;
  source?: {
    id: string;
    type: string;
    url?: string | null;
    media: Array<{
      id: string;
      durationS?: number | null;
      width?: number | null;
      height?: number | null;
      hasAudio?: boolean | null;
      createdAt: Date;
    }>;
  } | null;
  jobs: Array<{
    id: string;
    type: string;
    status: string;
    progress: number;
    attempts: number;
    error?: string | null;
    payload?: any;
    startedAt?: Date | null;
    finishedAt?: Date | null;
    createdAt: Date;
    updatedAt: Date;
  }>;
  clips?: Array<{
    id: string;
    status: string;
    score?: number | null;
    createdAt: Date;
  }>;
  analyses?: Array<{
    id: string;
    createdAt: Date;
    metadata?: any;
  }>;
}): ProjectProcessingState {
  const jobs = project.jobs || [];
  const clips = project.clips || [];
  const media = project.source?.media?.[0] || null;
  const sourceDurationS = Number(media?.durationS || 0);

  // Identify jobs by type
  const ingestJob = jobs.find((j) => j.type === "INGEST");
  const transcribeJob = jobs.find((j) => j.type === "TRANSCRIBE");
  const analyzeJob = jobs.find((j) => j.type === "ANALYZE" || j.type === "LONGFORM_ANALYZE");
  const renderJobs = jobs.filter((j) => j.type === "RENDER" || j.type === "LONGFORM_RENDER");

  // Determine current active or latest job
  const activeJob = jobs.find((j) =>
    ["QUEUED", "RETRYING", "DOWNLOADING", "INGESTING", "TRANSCRIBING", "ANALYZING", "EDITING", "RENDERING"].includes(j.status)
  ) || jobs[0] || null;

  const now = Date.now();
  const startTime = activeJob?.startedAt
    ? new Date(activeJob.startedAt).getTime()
    : new Date(project.createdAt).getTime();
  const elapsedMs = Math.max(0, now - startTime);

  // Extract structured progress state if stored in activeJob.payload
  const payloadState: Partial<JobProgressState> =
    activeJob?.payload?.progressState && typeof activeJob.payload.progressState === "object"
      ? activeJob.payload.progressState
      : {};

  // Track worker heartbeat
  const lastHeartbeat = payloadState.heartbeatAt
    ? new Date(payloadState.heartbeatAt)
    : activeJob?.startedAt
    ? new Date(activeJob.startedAt)
    : activeJob?.updatedAt
    ? new Date(activeJob.updatedAt)
    : null;

  const heartbeatAgeMs = lastHeartbeat ? Math.max(0, now - lastHeartbeat.getTime()) : undefined;

  // 1. Calculate Real Progress for Ring 1: SOURCE PROCESSING (0 - 100)
  let sourceProgress = 0;
  if (media?.id) {
    // MediaAsset is persisted and durably verified
    sourceProgress = 100;
  } else if (ingestJob) {
    if (ingestJob.status === "READY") {
      sourceProgress = 100;
    } else if (ingestJob.status === "DOWNLOADING") {
      sourceProgress = Math.min(85, Math.max(25, Math.round(ingestJob.progress * 100)));
    } else if (ingestJob.status === "INGESTING") {
      sourceProgress = Math.min(40, Math.max(10, Math.round(ingestJob.progress * 100)));
    } else if (ingestJob.status === "QUEUED") {
      sourceProgress = 5;
    } else if (ingestJob.status === "FAILED") {
      sourceProgress = Math.round(ingestJob.progress * 100);
    }
  }

  // 2. Calculate Real Progress for Ring 2: AI INTELLIGENCE (0 - 100)
  let aiProgress = 0;
  if (clips.length > 0 || (analyzeJob && analyzeJob.status === "READY")) {
    // Candidate generation & scoring completed
    aiProgress = 100;
  } else if (analyzeJob && analyzeJob.status !== "QUEUED") {
    // In analysis phase (audio/visual intelligence & ranking)
    const subProgress = Math.round(analyzeJob.progress * 100);
    aiProgress = Math.min(95, Math.max(50, 50 + Math.round(subProgress * 0.45)));
  } else if (transcribeJob) {
    if (transcribeJob.status === "READY") {
      aiProgress = 50; // Transcription done, awaiting analyze
    } else if (transcribeJob.status !== "QUEUED") {
      const subProgress = Math.round(transcribeJob.progress * 100);
      aiProgress = Math.min(48, Math.max(5, Math.round(subProgress * 0.48)));
    }
  }

  // 3. Calculate Real Progress for Ring 3: CLIP GENERATION (0 - 100)
  let clipProgress = 0;
  const candidatesFound = clips.length;
  const completedClips = clips.filter((c) => c.status === "READY").length;

  if (candidatesFound > 0) {
    // Clips were successfully discovered and editor timeline prepared
    if (renderJobs.length > 0) {
      const readyRenders = renderJobs.filter((r) => r.status === "READY").length;
      clipProgress = Math.min(100, Math.round((readyRenders / renderJobs.length) * 100));
    } else {
      // Candidates are fully prepared for review & editing
      clipProgress = 100;
    }
  } else if (analyzeJob && analyzeJob.status === "ANALYZING") {
    // Actively generating candidate cuts
    clipProgress = Math.min(30, Math.max(0, Math.round(analyzeJob.progress * 30)));
  }

  // Composite overall progress (weighted: Source 30%, AI 45%, Clips 25%)
  const overallProgress = Math.min(
    100,
    Math.round(sourceProgress * 0.3 + aiProgress * 0.45 + clipProgress * 0.25)
  );

  // 4. Determine Worker Status & Queued / Stalled Diagnosis
  let status: WorkerJobStatus = "QUEUED";
  let diagnosis = "Waiting for an available worker.";
  let diagnosisSubtext = "The job is queued. Start the background worker (npm run worker) to claim it.";
  let workerStatus: TechnicalDetails["workerStatus"] = "waiting";
  let canRetry = false;
  let isTerminal = false;

  if (clips.length > 0 && (!activeJob || activeJob.status === "READY")) {
    status = "READY";
    diagnosis = "All processing complete.";
    diagnosisSubtext = `${candidatesFound} candidate clips ready for preview and editing.`;
    workerStatus = "completed";
    isTerminal = true;
    sourceProgress = 100;
    aiProgress = 100;
    clipProgress = 100;
  } else if (activeJob) {
    if (activeJob.status === "FAILED") {
      status = "FAILED";
      diagnosis = "Processing failed. Retry from the last safe checkpoint.";
      diagnosisSubtext = activeJob.error || "The processing job encountered an unrecoverable error.";
      workerStatus = "failed";
      canRetry = true;
      isTerminal = true;
    } else if (activeJob.status === "CANCELLED") {
      status = "FAILED";
      diagnosis = "Processing was cancelled.";
      diagnosisSubtext = "This job was manually cancelled by the user.";
      workerStatus = "failed";
      isTerminal = true;
    } else if (activeJob.status === "RETRYING") {
      status = "RETRYING";
      diagnosis = `A recoverable failure is being retried (attempt ${activeJob.attempts} of 3).`;
      diagnosisSubtext = "Worker is resuming processing from the last saved milestone.";
      workerStatus = "active";
    } else if (activeJob.status === "QUEUED") {
      status = "QUEUED";
      diagnosis = "Waiting for an available worker.";
      diagnosisSubtext = "The background queue worker has not claimed this job yet.";
      workerStatus = "waiting";
    } else {
      // Job is in an active processing status
      if (heartbeatAgeMs !== undefined && heartbeatAgeMs > STALLED_THRESHOLD_MS) {
        status = "STALLED";
        diagnosis = "Processing has paused because the worker stopped responding.";
        diagnosisSubtext = `No worker heartbeat recorded for ${Math.round(heartbeatAgeMs / 1000)}s. Progress is preserved.`;
        workerStatus = "stalled";
        canRetry = true;
      } else {
        status = "PROCESSING";
        workerStatus = "active";
        if (activeJob.type === "INGEST") {
          diagnosis = activeJob.status === "DOWNLOADING"
            ? "Your video is being downloaded."
            : "Source validation and media ingestion in progress.";
          diagnosisSubtext = "Extracting video metadata, stream info, and audio channels.";
        } else if (activeJob.type === "TRANSCRIBE") {
          diagnosis = "AI transcription is in progress.";
          diagnosisSubtext = "Generating timecoded speech transcript using Whisper.";
        } else if (activeJob.type === "ANALYZE" || activeJob.type === "LONGFORM_ANALYZE") {
          diagnosis = "AI intelligence and scene ranking in progress.";
          diagnosisSubtext = "Evaluating multimodal energy, speech excitement, and scene boundaries.";
        } else if (activeJob.type === "RENDER") {
          diagnosis = "Rendering selected clip.";
          diagnosisSubtext = "Encoding vertical video with styled dynamic captions.";
        }
      }
    }
  }

  // 5. Build Stage Label
  let stage = activeJob?.status || "QUEUED";
  let stageLabel = diagnosis;
  if (status === "READY") {
    stage = "READY";
    stageLabel = "Processing complete";
  } else if (activeJob?.type === "INGEST") {
    stageLabel = activeJob.status === "DOWNLOADING" ? "Downloading source video" : "Ingesting source media";
  } else if (activeJob?.type === "TRANSCRIBE") {
    stageLabel = "Transcribing speech with Whisper";
  } else if (activeJob?.type === "ANALYZE" || activeJob?.type === "LONGFORM_ANALYZE") {
    stageLabel = "Analyzing moments and ranking clips";
  } else if (activeJob?.type === "RENDER") {
    stageLabel = "Rendering clip output";
  }

  // 6. Assemble Live Activity Stream from Real Backend Events
  const activity: ActivityEvent[] = [];

  // Project creation
  activity.push({
    timestamp: project.createdAt.toISOString(),
    message: "Project created and source registered",
    stage: "SETUP",
  });

  // Source ingestion events
  if (ingestJob) {
    if (ingestJob.startedAt) {
      activity.push({
        timestamp: ingestJob.startedAt.toISOString(),
        message: "Source download and validation started",
        stage: "INGEST",
      });
    }
    if (media?.id) {
      activity.push({
        timestamp: media.createdAt.toISOString(),
        message: `Source media probed: ${sourceDurationS ? Math.round(sourceDurationS) + "s duration" : "valid stream"}${media.hasAudio ? " with audio" : ""}`,
        stage: "INGEST",
      });
    }
    if (ingestJob.status === "READY" && ingestJob.finishedAt) {
      activity.push({
        timestamp: ingestJob.finishedAt.toISOString(),
        message: "Source media preparation verified and stored",
        stage: "INGEST",
      });
    }
  }

  // Transcription events
  if (transcribeJob) {
    if (transcribeJob.startedAt) {
      activity.push({
        timestamp: transcribeJob.startedAt.toISOString(),
        message: "Whisper speech transcription started",
        stage: "TRANSCRIBE",
      });
    }
    if (transcribeJob.status === "READY" && transcribeJob.finishedAt) {
      activity.push({
        timestamp: transcribeJob.finishedAt.toISOString(),
        message: "Transcription checkpoint saved with segment timestamps",
        stage: "TRANSCRIBE",
      });
    }
  }

  // Analysis events
  if (analyzeJob) {
    if (analyzeJob.startedAt) {
      activity.push({
        timestamp: analyzeJob.startedAt.toISOString(),
        message: "AI multimodal candidate analysis started",
        stage: "ANALYZE",
      });
    }
    if (candidatesFound > 0) {
      activity.push({
        timestamp: clips[0].createdAt.toISOString(),
        message: `Discovered and ranked ${candidatesFound} candidate moments`,
        stage: "ANALYZE",
      });
    }
    if (analyzeJob.status === "READY" && analyzeJob.finishedAt) {
      activity.push({
        timestamp: analyzeJob.finishedAt.toISOString(),
        message: "Clip candidate selection and timeline generation completed",
        stage: "ANALYZE",
      });
    }
  }

  // Merging any explicit activity items recorded in job payload
  if (Array.isArray(payloadState.activity)) {
    for (const item of payloadState.activity) {
      if (item.message && !activity.some((a) => a.message === item.message)) {
        activity.push(item);
      }
    }
  }

  // Failure event
  if (activeJob?.status === "FAILED" && activeJob.error) {
    activity.push({
      timestamp: (activeJob.finishedAt || activeJob.updatedAt || new Date()).toISOString(),
      message: `Processing failure: ${activeJob.error.slice(0, 120)}`,
      stage: "FAILED",
    });
  }

  // Sort activity chronologically
  activity.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  // 7. Technical Details
  const lastCheckpoint =
    payloadState.lastCheckpoint ||
    (candidatesFound > 0
      ? "Clip candidates ranked"
      : transcribeJob?.status === "READY"
      ? "Transcription segments verified"
      : media?.id
      ? "Source media probed"
      : "Job claimed");

  const technicalDetails: TechnicalDetails = {
    jobId: activeJob?.id,
    jobType: activeJob?.type,
    workerStatus,
    lastHeartbeat: lastHeartbeat?.toISOString(),
    heartbeatAgeMs,
    retryCount: activeJob?.attempts || 0,
    currentStage: stage,
    lastCheckpoint,
    error: activeJob?.error || undefined,
  };

  return {
    projectId: project.id,
    status,
    diagnosis,
    diagnosisSubtext,
    stage,
    stageLabel,
    overallProgress,
    sourceProgress,
    aiProgress,
    clipProgress,
    elapsedMs,
    sourceDurationS,
    candidatesFound,
    completedClips,
    totalClips: candidatesFound,
    activity,
    technicalDetails,
    isTerminal,
    canRetry,
    activeJobId: activeJob?.id,
  };
}

/**
 * Persists an activity event and updated progress state inside Job.payload
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
  },
  client?: any
) {
  const dbClient = client || (await import("./db")).db;
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
