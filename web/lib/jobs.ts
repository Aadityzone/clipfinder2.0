import { db } from "./db";

const STALE_AFTER_MS = 10 * 60 * 1000;
const MAX_ATTEMPTS = 3;

export async function enqueueJob(
  userId: string,
  projectId: string,
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
 * is active; stale RETRYING/ANALYZING jobs can be recovered after a crash.
 */
export async function claimNextJob() {
  const now = new Date();
  const staleBefore = new Date(now.getTime() - STALE_AFTER_MS);
  const runnable = { OR: [{ runAfter: null }, { runAfter: { lte: now } }] };
  const claimable = {
    AND: [
      {
        OR: [
          { status: "QUEUED" as const },
          { status: "RETRYING" as const, startedAt: { lt: staleBefore } },
          { status: "ANALYZING" as const, startedAt: { lt: staleBefore } },
        ],
      },
      runnable,
    ],
  };
  const candidate = await db.job.findFirst({ where: claimable, orderBy: { createdAt: "asc" } });
  if (!candidate) return null;

  const claimed = await db.job.updateMany({
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
  return claimed.count ? db.job.findUnique({ where: { id: candidate.id } }) : null;
}

/** Atomically finish a stage and enqueue its successor to prevent pipeline gaps. */
export async function completeJobAndEnqueue(
  id: string,
  next: { userId: string; projectId: string | null; type: string; payload: unknown },
) {
  return db.$transaction(async (tx) => {
    const completed = await tx.job.updateMany({
      where: { id, status: { not: "CANCELLED" } },
      data: { status: "READY", progress: 1, finishedAt: new Date(), error: null },
    });
    if (!completed.count) return null;
    return tx.job.create({
      data: {
        userId: next.userId,
        projectId: next.projectId,
        type: next.type,
        payload: next.payload as any,
        status: "QUEUED",
      },
    });
  });
}

/** Throw at worker checkpoints so cancellation is not overwritten by completion. */
export async function assertJobNotCancelled(id: string) {
  const job = await db.job.findUnique({ where: { id }, select: { status: true } });
  if (!job || job.status === "CANCELLED") {
    const error = new Error("JOB_CANCELLED");
    error.name = "JobCancelledError";
    throw error;
  }
}

export async function finishJob(id: string) {
  await db.job.updateMany({
    where: { id, status: { not: "CANCELLED" } },
    data: { status: "READY", progress: 1, finishedAt: new Date(), error: null },
  });
  return db.job.findUnique({ where: { id } });
}

/**
 * Retry transient failures automatically with bounded exponential backoff.
 * The third failed attempt becomes terminal; the user can explicitly retry it.
 */
export async function failJob(id: string, error: string) {
  const current = await db.job.findUnique({ where: { id } });
  if (!current || current.status === "CANCELLED" || current.status === "READY") return current;

  const shouldRetry = current.attempts < MAX_ATTEMPTS;
  const retryDelayMs = 15_000 * 2 ** Math.max(0, current.attempts - 1);
  await db.job.updateMany({
    where: { id, status: { notIn: ["CANCELLED", "READY"] } },
    data: shouldRetry
      ? { status: "QUEUED", error, finishedAt: null, runAfter: new Date(Date.now() + retryDelayMs) }
      : { status: "FAILED", error, finishedAt: new Date(), runAfter: null },
  });
  return db.job.findUnique({ where: { id } });
}
