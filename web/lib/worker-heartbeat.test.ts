import assert from "node:assert/strict";
import test from "node:test";
import {
  hasHealthyWorker,
  pruneWorkerHeartbeats,
  recordWorkerHeartbeat,
  WORKER_HEARTBEAT_RETENTION_MS,
  WORKER_HEARTBEAT_STALE_AFTER_MS,
  type WorkerHeartbeatClient,
} from "./worker-heartbeat";

function fakeClient(overrides: Record<string, (...args: unknown[]) => unknown>) {
  return {
    workerHeartbeat: {
      upsert: async () => null,
      deleteMany: async () => ({ count: 0 }),
      findFirst: async () => null,
      ...overrides,
    },
  } as unknown as WorkerHeartbeatClient;
}

test("recordWorkerHeartbeat creates or refreshes the worker heartbeat", async () => {
  const now = new Date("2026-10-12T10:00:00.000Z");
  let args: unknown;
  const client = fakeClient({ upsert: async (input) => { args = input; return {}; } });

  await recordWorkerHeartbeat(client, "worker-a", now);

  assert.deepEqual(args, {
    where: { workerId: "worker-a" },
    create: { workerId: "worker-a", startedAt: now, heartbeatAt: now },
    update: { heartbeatAt: now },
  });
});

test("pruneWorkerHeartbeats retains a day's operational history", async () => {
  const now = new Date("2026-10-12T10:00:00.000Z");
  let args: unknown;
  const client = fakeClient({ deleteMany: async (input) => { args = input; return { count: 2 }; } });

  const result = await pruneWorkerHeartbeats(client, now);

  assert.equal(result.count, 2);
  assert.deepEqual(args, {
    where: { heartbeatAt: { lt: new Date(now.getTime() - WORKER_HEARTBEAT_RETENTION_MS) } },
  });
});

test("worker health is unavailable without a fresh heartbeat", async () => {
  const now = new Date("2026-10-12T10:00:00.000Z");
  let args: unknown;
  const client = fakeClient({ findFirst: async (input) => { args = input; return null; } });

  assert.equal(await hasHealthyWorker(client, now), false);
  assert.deepEqual(args, {
    where: { heartbeatAt: { gte: new Date(now.getTime() - WORKER_HEARTBEAT_STALE_AFTER_MS) } },
    select: { workerId: true },
  });
});

test("worker health is available when a fresh heartbeat exists", async () => {
  const client = fakeClient({ findFirst: async () => ({ workerId: "worker-a" }) });

  assert.equal(await hasHealthyWorker(client, new Date()), true);
});
