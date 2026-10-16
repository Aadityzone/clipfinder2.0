import type { PrismaClient } from "../generated/prisma/client";

export const WORKER_HEARTBEAT_INTERVAL_MS = 15_000;
export const WORKER_HEARTBEAT_STALE_AFTER_MS = 60_000;
export const WORKER_HEARTBEAT_RETENTION_MS = 24 * 60 * 60 * 1000;

export type WorkerHeartbeatClient = Pick<PrismaClient, "workerHeartbeat">;

export async function recordWorkerHeartbeat(
  client: WorkerHeartbeatClient,
  workerId: string,
  now = new Date(),
) {
  return client.workerHeartbeat.upsert({
    where: { workerId },
    create: { workerId, startedAt: now, heartbeatAt: now },
    update: { heartbeatAt: now },
  });
}

export async function pruneWorkerHeartbeats(
  client: WorkerHeartbeatClient,
  now = new Date(),
) {
  const olderThan = new Date(now.getTime() - WORKER_HEARTBEAT_RETENTION_MS);
  return client.workerHeartbeat.deleteMany({
    where: { heartbeatAt: { lt: olderThan } },
  });
}

export async function hasHealthyWorker(
  client: WorkerHeartbeatClient,
  now = new Date(),
): Promise<boolean> {
  const newerThan = new Date(now.getTime() - WORKER_HEARTBEAT_STALE_AFTER_MS);
  const worker = await client.workerHeartbeat.findFirst({
    where: { heartbeatAt: { gte: newerThan } },
    select: { workerId: true },
  });
  return worker !== null;
}
