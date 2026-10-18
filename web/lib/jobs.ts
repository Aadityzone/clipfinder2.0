import { db } from "./db";

const STALE_AFTER_MS = 10 * 60 * 1000;
const MAX_ATTEMPTS = 3;
const MAX_ERROR_LENGTH = 4000;
const ACTIVE_JOB_STATUSES = [
  "RETRYING", "DOWNLOADING", "INGESTING", "TRANSCRIBING", "ANALYZING", "EDITING", "RENDERING",
] as const;
const TERMINAL_JOB_STATUSES = ["READY", "FAILED", "CANCELLED"] as const;

export type DbClient = typeof db;

/** Jobs are active between claiming and a terminal state. */
function activeJobStatuses() {
  return [...ACTIVE_JOB_STATUSES] as Array<(typeof ACTIVE_JOB_STATUSES)[number]>;
}

/**
 * A stale active job has either lost its heartbeat or predates heartbeat
 * support (`startedAt: null`). The `updateMany` compare-and-set below lets
 * multiple worker processes race safely: only the process that sees the
 * original runnable state claims or transitions the job.
 */
function jobLease(staleBefore: Date) {
  return { OR: [{ startedAt: null }, { startedAt: { lt: staleBefore } }] };
}

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
 * Atomically claim one runnable job. Heartbeats refresh startedAt while a worker
 * is active; stale jobs in any active processing stage can be recovered after a
 * crash. A crashed worker is capped by the same attempt ceiling as failures, so a
 * job that keeps losing its worker does not loop forever.
 */
export async function claimNextJob(client: DbClient = db) {
  const now = new Date();
  const staleBefore = new Date(now.getTime() - STALE_AFTER_MS);
  // A worker can disappear without reaching failJob (process kill, host
  // restart, or power loss). Recover stale work, but do not retry a crashed
  // job forever: the same three-attempt ceiling applies to crash recovery.
  await client.job.updateMany({
    where: {
      status: { in: activeJobStatuses() },
      ...jobLease(staleBefore),
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
          { status: { in: activeJobStatuses() }, ...jobLease(staleBefore), attempts: { lt: MAX_ATTEMPTS } },
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

/**
 * Mark a stage complete and enqueue its successor in one database transaction.
 *
 * `expectedAttempts` compare-and-sets the completion on the attempt the worker
 * actually claimed. If another worker recovered the job after this worker lost
 * its lease, the late completion is rejected instead of disowning the new run.
 */
export async function completeJobAndEnqueue(
  id: string,
  next: {
    userId: string;
    projectId: string | null;
    type: string;
    payload: unknown;
    expectedAttempts?: number;
    runAfter?: Date;
  },
  client: DbClient = db,
) {
  return client.$transaction(async (tx) => {
    // Only an actively processing job may complete. Restricting this transition
    // prevents a late worker from resurrecting FAILED/READY jobs after a timeout
    // or competing worker has already recorded a terminal state.
    const completed = await tx.job.updateMany({
      where: {
        id,
        status: { in: activeJobStatuses() },
        ...(next.expectedAttempts === undefined ? {} : { attempts: next.expectedAttempts }),
      },
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

/**
 * Throw at worker checkpoints so a stale or cancelled worker stops before
 * overwriting newer state. `expectedAttempts` detects a lost lease: another
 * worker reclaimed the job after this worker's attempt was superseded.
 */
export async function assertJobNotCancelled(id: string, expectedAttempts?: number, client: DbClient = db) {
  const job = await client.job.findUnique({ where: { id }, select: { status: true, attempts: true } });
  if (!job || job.status === "CANCELLED") {
    const error = new Error("JOB_CANCELLED");
    error.name = "JobCancelledError";
    throw error;
  }
  if (expectedAttempts !== undefined && job.attempts !== expectedAttempts) {
    const error = new Error("JOB_LEASE_LOST");
    error.name = "JobLeaseLostError";
    throw error;
  }
}

/**
 * Idempotently finish a claimed job; never resurrect queued or failed work.
 * `expectedAttempts` rejects the completion of a worker whose lease was lost.
 */
export async function finishJob(id: string, client: DbClient = db, expectedAttempts?: number) {
  const current = await client.job.findUnique({ where: { id } });
  if (!current || current.status === "CANCELLED" || current.status === "READY") return current;
  if (!(ACTIVE_JOB_STATUSES as readonly string[]).includes(current.status)) {
    throw new Error(`Cannot complete job ${id} from state ${current.status}.`);
  }
  const changed = await client.job.updateMany({
    where: {
      id,
      status: { in: activeJobStatuses() },
      ...(expectedAttempts === undefined ? {} : { attempts: expectedAttempts }),
    },
    data: { status: "READY", progress: 1, finishedAt: new Date(), runAfter: null, error: null },
  });
  if (!changed.count) {
    const latest = await client.job.findUnique({ where: { id } });
    if (!latest || latest.status === "CANCELLED" || latest.status === "READY") return latest;
    throw new Error(`Job ${id} changed state before completion (${latest.status}).`);
  }
  return client.job.findUnique({ where: { id } });
}

/**
 * Record a job failure with a compare-and-set on the claimed attempt.
 * Transient failures are retried automatically with bounded exponential backoff
 * and the third failed attempt becomes terminal.
 *
 * A permanent failure (invalid or unsupported source, missing media, malformed
 * request) is recorded as terminal immediately. Retrying it would only spend
 * another full stage timeout, up to several hours, reproducing the same error.
 *
 * If this worker's attempt was superseded (another worker reclaimed the job),
 * the late failure must not alter the new run: the stale worker keeps nothing.
 */
export async function failJob(
  id: string,
  error: string,
  options: { retryable?: boolean; expectedAttempts?: number; client?: DbClient } = {},
) {
  const client = options.client ?? db;
  const current = await client.job.findUnique({ where: { id } });
  if (!current || (TERMINAL_JOB_STATUSES as readonly string[]).includes(current.status)) return current;
  if (!(ACTIVE_JOB_STATUSES as readonly string[]).includes(current.status)) return current;
  if (options.expectedAttempts !== undefined && current.attempts !== options.expectedAttempts) return current;

  // A late or gigantic error string must not be stored wholesale in the job row.
  const boundedError = String(error).slice(0, MAX_ERROR_LENGTH);
  const shouldRetry = options.retryable !== false && current.attempts < MAX_ATTEMPTS;
  const retryDelayMs = 15_000 * 2 ** Math.max(0, current.attempts - 1);
  await client.job.updateMany({
    where: { id, status: current.status, attempts: current.attempts },
    data: shouldRetry
      ? { status: "QUEUED", error: boundedError, finishedAt: null, runAfter: new Date(Date.now() + retryDelayMs) }
      : { status: "FAILED", error: boundedError, finishedAt: new Date(), runAfter: null },
  });
  return client.job.findUnique({ where: { id } });
}
