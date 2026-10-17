import assert from "node:assert/strict";
import test, { before } from "node:test";

type JobsModule = typeof import("./jobs");
let jobs: JobsModule;
before(async () => {
  process.env.DATABASE_URL ||= "postgresql://clipfinder_test:test@127.0.0.1:5432/clipfinder_test";
  jobs = await import("./jobs");
});

type JobState = {
  id: string;
  status: string;
  attempts: number;
  progress: number;
  error: string | null;
  finishedAt: Date | null;
  runAfter: Date | null;
  startedAt: Date | null;
};

function fakeClient(initial: JobState | null) {
  let current = initial;
  const enqueued: any[] = [];
  const updateCalls: any[] = [];
  const client: any = {
    job: {
      updateMany: async ({ where, data }: any) => {
        updateCalls.push({ where, data });
        if (!current || current.id !== where.id) return { count: 0 };
        const allowed = where.status?.in ? where.status.in.includes(current.status) : where.status === undefined || where.status === current.status;
        if (!allowed || (where.attempts !== undefined && where.attempts !== current.attempts)) return { count: 0 };
        if (data.status) current.status = data.status;
        if (data.attempts?.increment) current.attempts += data.attempts.increment;
        if (data.progress !== undefined) current.progress = data.progress;
        if (data.error !== undefined) current.error = data.error;
        if (data.finishedAt !== undefined) current.finishedAt = data.finishedAt;
        if (data.runAfter !== undefined) current.runAfter = data.runAfter;
        if (data.startedAt !== undefined) current.startedAt = data.startedAt;
        return { count: 1 };
      },
      findFirst: async () => current,
      findUnique: async () => current,
      create: async ({ data }: any) => { enqueued.push(data); return data; },
    },
    $transaction: async (callback: any) => callback(client),
  };
  return { client, enqueued, updateCalls, getCurrent: () => current };
}

const job = (status: string, attempts = 1): JobState => ({
  id: "job-1", status, attempts, progress: 0.5, error: null, finishedAt: null, runAfter: null, startedAt: new Date(),
});

test("finishJob only completes active work and is idempotent for completed or cancelled jobs", async () => {
  const active = fakeClient(job("ANALYZING"));
  await jobs.finishJob("job-1", active.client);
  assert.equal(active.getCurrent()?.status, "READY");
  assert.equal(active.getCurrent()?.progress, 1);

  const queued = fakeClient(job("QUEUED"));
  await assert.rejects(() => jobs.finishJob("job-1", queued.client), /Cannot complete job.*QUEUED/);
  assert.equal(queued.getCurrent()?.status, "QUEUED");

  const staleWorker = fakeClient(job("ANALYZING", 2));
  await assert.rejects(() => jobs.finishJob("job-1", staleWorker.client, 1), /changed state before completion/);
  assert.equal(staleWorker.getCurrent()?.status, "ANALYZING");

  const cancelled = fakeClient(job("CANCELLED"));
  await jobs.finishJob("job-1", cancelled.client);
  assert.equal(cancelled.getCurrent()?.status, "CANCELLED");
});

test("successor enqueue and prior completion are one transaction and require active state", async () => {
  const active = fakeClient(job("INGESTING"));
  const successor = await jobs.completeJobAndEnqueue("job-1", {
    userId: "user-1", projectId: "project-1", type: "TRANSCRIBE", payload: { sourceRange: { startSeconds: 5, endSeconds: 10 } },
  }, active.client);
  assert.equal(active.getCurrent()?.status, "READY");
  assert.deepEqual(successor, active.enqueued[0]);
  assert.equal(active.enqueued.length, 1);

  const failed = fakeClient(job("FAILED"));
  assert.equal(await jobs.completeJobAndEnqueue("job-1", { userId: "user-1", projectId: null, type: "X", payload: {} }, failed.client), null);
  assert.equal(failed.enqueued.length, 0);

  const oldAttempt = fakeClient(job("ANALYZING", 2));
  assert.equal(await jobs.completeJobAndEnqueue("job-1", { userId: "user-1", projectId: null, type: "X", payload: {}, expectedAttempts: 1 }, oldAttempt.client), null);
  assert.equal(oldAttempt.getCurrent()?.status, "ANALYZING");
});

test("failure retries use a bounded backoff and compare the observed attempt state", async () => {
  const retry = fakeClient(job("RETRYING", 2));
  const retryResult = await jobs.failJob("job-1", "transient failure", retry.client);
  assert.equal(retryResult?.status, "QUEUED");
  assert.equal(retryResult?.error, "transient failure");
  assert.ok((retryResult?.runAfter?.getTime() ?? 0) - Date.now() <= 30_000);
  assert.equal(retry.updateCalls.at(-1).where.attempts, 2);

  const terminal = fakeClient(job("RENDERING", 3));
  const terminalResult = await jobs.failJob("job-1", "permanent failure", terminal.client);
  assert.equal(terminalResult?.status, "FAILED");
  assert.ok(terminalResult?.finishedAt instanceof Date);

  const stale = fakeClient(job("RETRYING", 1));
  stale.client.job.updateMany = async () => ({ count: 0 });
  const raced = await jobs.failJob("job-1", "late error", stale.client);
  assert.equal(raced?.status, "RETRYING");
});

test("claim compare-and-set yields no job when another worker wins", async () => {
  const candidate = job("QUEUED", 0);
  const state = fakeClient(candidate);
  let calls = 0;
  state.client.job.updateMany = async ({ where }: any) => {
    calls += 1;
    if (calls === 1) return { count: 0 };
    assert.ok(JSON.stringify(where).includes("startedAt"));
    return { count: 0 };
  };
  assert.equal(await jobs.claimNextJob(state.client), null);
});
