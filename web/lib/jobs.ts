import { db } from "./db";

const STALE_AFTER_MS = 10 * 60 * 1000;
const MAX_ATTEMPTS = 3;
const ACTIVE_JOB_STATUSES = [
  "RETRYING", "DOWNLOADING", "INGESTING", "TRANSCRIBING", "ANALYZING", "EDITING", "RENDERING",
] as const;
const TERMINAL_JOB_STATUSES = ["READY", "FAILED", "CANCELLED"] as const;
const MAX_ERROR_LENGTH = 4000;

export async function enqueueJob(
  userId: string,
  projectId: string | null,
  type: string,
  payload: unknown = {},
  runAfter?: Date,
) {
  return db.job.create({
    data: { userId, projectId, type, payload: payload as any, status: "QUEUED", runAfter },
  });
}

/**
 * A stale active job has either lost its heartbeat or predates heartbeat support.
 * The updateMany compare-and-set below lets multiple worker processes race safely:
 * only the process that sees the original runnable state claims it.
 */
export async function claimNextJob(client: typeof db = db) {
  const now = new Date();
  const staleBefore = new Date(now.getTime() - STALE_AFTER_MS);
  const staleLease = { OR: [{ startedAt: null }, { startedAt: { lt: staleBefore } }] };
  await client.job.updateMany({
    where: {
      status: { in: [...ACTIVE_JOB_STATUSES] },
      ...staleLease,
      attempts: { gte: MAX_ATTEMPTS },
    },
    data: {
      status: "FAILED",
      finishedAt: now,
      runAfter: null,
      error: "Worker stopped repeatedly while processing this job. Retry it manually after checking the service logs.",
    },
  });

  const runnable = { OR: [{ runAfter: null }, { runAfter: { lte: now } }] };
  const claimable = {
    AND: [
      {
        OR: [
          { status: "QUEUED" as const },
          { status: { in: [...ACTIVE_JOB_STATUSES] }, ...staleLease, attempts: { lt: MAX_ATTEMPTS } },
        ],
      },
      runnable,
    ],
  };
  const candidate = await client.job.findFirst({ where: claimable, orderBy: { createdAt: "asc" } });
  if (!candidate) return null;

  const claimed = await client.job.updateMany({
    where: { AND: [{ id: candidate.id }, ...claimable.AND] },
    data: {
      status: "RETRYING",
      startedAt: now,
      attempts: { increment: 1 },
      finishedAt: null,
      error: null,
      runAfter: null,
    },
  });
  return claimed.count ? client.job.findUnique({ where: { id: candidate.id } }) : null;
}

/** Mark a stage complete and enqueue its successor in one database transaction. */
export async function completeJobAndEnqueue(
  id: string,
  next: { userId: string; projectId: string | null; type: string; payload: unknown; expectedAttempts?: number; runAfter?: Date },
  client: typeof db = db,
) {
  return client.$transaction(async (tx) => {
    const completed = await tx.job.updateMany({
      where: { id, status: { in: [...ACTIVE_JOB_STATUSES] }, ...(next.expectedAttempts === undefined ? {} : { attempts: next.expectedAttempts }) },
      data: { status: "READY", progress: 1, finishedAt: new Date(), runAfter: null, error: null },
    });
    if (!completed.count) return null;
    return tx.job.create({
      data: {
        userId: next.userId,
        projectId: next.projectId,
        type: next.type,
        payload: next.payload as any,
        status: "QUEUED",
        runAfter: next.runAfter,
      },
    });
  });
}

/** Throw at worker checkpoints so cancellation is not overwritten by completion. */
export async function assertJobNotCancelled(id: string, expectedAttempts?: number) {
  const job = await db.job.findUnique({ where: { id }, select: { status: true, attempts: true } });
  if (!job || job.status === "CANCELLED" || (expectedAttempts !== undefined && job.attempts !== expectedAttempts)) {
    const cancelled = !job || job.status === "CANCELLED";
    const error = new Error(cancelled ? "JOB_CANCELLED" : "JOB_LEASE_LOST");
    error.name = cancelled ? "JobCancelledError" : "JobLeaseLostError";
    throw error;
  }
}

/** Idempotently finish a claimed job; never resurrect queued or failed work. */
export async function finishJob(id: string, client: typeof db = db, expectedAttempts?: number) {
  const current = await client.job.findUnique({ where: { id } });
  if (!current || current.status === "CANCELLED" || current.status === "READY") return current;
  if (!(ACTIVE_JOB_STATUSES as readonly string[]).includes(current.status)) {
    throw new Error(`Cannot complete job ${id} from state ${current.status}.`);
  }
  const changed = await client.job.updateMany({
    where: { id, status: { in: [...ACTIVE_JOB_STATUSES] }, ...(expectedAttempts === undefined ? {} : { attempts: expectedAttempts }) },
    data: { status: "READY", progress: 1, finishedAt: new Date(), runAfter: null, error: null },
  });
  if (!changed.count) {
    const latest = await client.job.findUnique({ where: { id } });
    if (!latest || latest.status === "CANCELLED" || latest.status === "READY") return latest;
    throw new Error(`Job ${id} changed state before completion (${latest.status}).`);
  }
  return client.job.findUnique({ where: { id } });
}

/** Retry transient failures with bounded exponential backoff and a compare-and-set. */
export async function failJob(id: string, error: string, client: typeof db = db, expectedAttempts?: number) {
  const current = await client.job.findUnique({ where: { id } });
  if (!current || (TERMINAL_JOB_STATUSES as readonly string[]).includes(current.status)) return current;
  if (!(ACTIVE_JOB_STATUSES as readonly string[]).includes(current.status)) return current;
  if (expectedAttempts !== undefined && current.attempts !== expectedAttempts) return current;

  const boundedError = error.slice(0, MAX_ERROR_LENGTH);
  const shouldRetry = current.attempts < MAX_ATTEMPTS;
  const retryDelayMs = 15_000 * 2 ** Math.max(0, current.attempts - 1);
  const changed = await client.job.updateMany({
    where: { id, status: current.status, attempts: expectedAttempts ?? current.attempts },
    data: shouldRetry
      ? { status: "QUEUED", error: boundedError, finishedAt: null, runAfter: new Date(Date.now() + retryDelayMs) }
      : { status: "FAILED", error: boundedError, finishedAt: new Date(), runAfter: null },
  });
  if (!changed.count) return client.job.findUnique({ where: { id } });
  return client.job.findUnique({ where: { id } });
}
