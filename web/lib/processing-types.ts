/** Frontend projection of the persisted job fields returned by /api/jobs/[id]. */
export type ProcessingJob = {
  id: string;
  status: string;
  progress: number;
  attempts: number;
  error: string | null;
  updatedAt?: string;
};

export type ProcessingEvent = {
  id: string;
  status: string;
  at: number;
  error?: string | null;
};

export const TERMINAL_JOB_STATUSES = ["READY", "FAILED", "CANCELLED"] as const;
export const isTerminalJobStatus = (status: string) =>
  (TERMINAL_JOB_STATUSES as readonly string[]).includes(status);

export const PROCESSING_STAGES = [
  "QUEUED", "RETRYING", "DOWNLOADING", "INGESTING", "TRANSCRIBING",
  "ANALYZING", "EDITING", "RENDERING", "READY",
] as const;

export function workerProgressPercent(progress: number): number | null {
  if (!Number.isFinite(progress) || progress < 0) return null;
  return Math.round(Math.max(0, Math.min(1, progress)) * 100);
}

export type WorkerJobStatus =
  | "QUEUED"
  | "PROCESSING"
  | "STALLED"
  | "RETRYING"
  | "FAILED"
  | "READY";

export interface ActivityEvent {
  timestamp: string; // ISO 8601
  message: string;
  stage?: string;
}

export interface JobProgressState {
  status: WorkerJobStatus;
  stage: string;
  stageLabel: string;
  overallProgress: number; // 0 - 100
  sourceProgress: number; // 0 - 100
  aiProgress: number; // 0 - 100
  clipProgress: number; // 0 - 100
  heartbeatAt: string;
  startedAt?: string;
  updatedAt?: string;
  retryCount: number;
  completedStages: string[];
  activity: ActivityEvent[];
  candidatesFound?: number;
  completedClips?: number;
  totalClips?: number;
  transcribeChunksCompleted?: number;
  totalTranscribeChunks?: number;
  analysisChunksCompleted?: number;
  queuedRenders?: number;
  renderedClips?: number;
  sourceDurationS?: number;
  lastCheckpoint?: string;
  error?: string;
}

export interface TechnicalDetails {
  jobId?: string;
  jobType?: string;
  workerStatus: "active" | "waiting" | "stalled" | "offline" | "completed" | "failed";
  lastHeartbeat?: string;
  heartbeatAgeMs?: number;
  retryCount: number;
  currentStage: string;
  lastCheckpoint: string;
  error?: string;
}

export interface ProjectProcessingState {
  projectId: string;
  status: WorkerJobStatus;
  diagnosis: string;
  diagnosisSubtext: string;
  stage: string;
  stageLabel: string;
  overallProgress: number | null;
  sourceProgress: number;
  aiProgress: number;
  clipProgress: number;
  elapsedMs: number;
  sourceDurationS: number;
  candidatesFound: number;
  completedClips: number;
  totalClips: number;
  transcribeChunksCompleted?: number;
  totalTranscribeChunks?: number;
  analysisChunksCompleted?: number;
  queuedRenders?: number;
  renderedClips?: number;
  activity: ActivityEvent[];
  technicalDetails: TechnicalDetails;
  isTerminal: boolean;
  canRetry: boolean;
  activeJobId?: string;
}

/**
 * Format timestamp in local 24h format (e.g. 10:42:01)
 */
export function formatTimeOnly(isoOrDate: string | Date): string {
  try {
    const d = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
    if (isNaN(d.getTime())) return "";
    return d.toTimeString().slice(0, 8);
  } catch {
    return "";
  }
}
