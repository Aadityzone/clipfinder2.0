export const ACTIVE_JOB_STATUSES: Array<
  "RETRYING" | "DOWNLOADING" | "INGESTING" | "TRANSCRIBING" | "ANALYZING" | "EDITING" | "RENDERING"
> = ["RETRYING", "DOWNLOADING", "INGESTING", "TRANSCRIBING", "ANALYZING", "EDITING", "RENDERING"];

const MAX_ATTEMPTS = 3;

export function getFailureTransition(attempts: number, now = new Date()) {
  const shouldRetry = attempts < MAX_ATTEMPTS;
  const retryDelayMs = 15_000 * 2 ** Math.max(0, attempts - 1);
  return shouldRetry
    ? { status: "QUEUED" as const, runAfter: new Date(now.getTime() + retryDelayMs), finishedAt: null }
    : { status: "FAILED" as const, runAfter: null, finishedAt: now };
}
