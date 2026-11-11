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
  const updateCalls: Array<{ where: any; data: any }> = [];
  const client: any = {
    job: {
      updateMany: async ({ where, data }: any) => {
        updateCalls.push({ where, data });
        if (!current || current.id !== where.id) return { count: 0 };
        const allowed = where.status?.in
          ? where.status.in.includes(current.status)
          : where.status === undefined || where.status === current.status;
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
  const retryResult = await jobs.failJob("job-1", "transient failure", { client: retry.client });
  assert.equal(retryResult?.status, "QUEUED");
  assert.equal(retryResult?.error, "transient failure");
  assert.ok((retryResult?.runAfter?.getTime() ?? 0) - Date.now() <= 30_000);
  assert.equal(retry.updateCalls.at(-1)?.where?.attempts, 2);

  const terminal = fakeClient(job("RENDERING", 3));
  const terminalResult = await jobs.failJob("job-1", "permanent failure", { client: terminal.client });
  assert.equal(terminalResult?.status, "FAILED");
  assert.ok(terminalResult?.finishedAt instanceof Date);

  const stale = fakeClient(job("RETRYING", 1));
  stale.client.job.updateMany = async () => ({ count: 0 });
  const raced = await jobs.failJob("job-1", "late error", { client: stale.client });
  assert.equal(raced?.status, "RETRYING");

  const mismatchedAttempt = fakeClient(job("ANALYZING", 2));
  const disowned = await jobs.failJob("job-1", "stale worker error", { client: mismatchedAttempt.client, expectedAttempts: 1 });
  assert.equal(disowned?.status, "ANALYZING");
  assert.equal(mismatchedAttempt.updateCalls.at(-1)?.where?.attempts, undefined);

  const oversized = fakeClient(job("DOWNLOADING", 1));
  const bounded = await jobs.failJob("job-1", "x".repeat(10_000), { client: oversized.client });
  assert.equal(bounded?.error?.length, 4000);
});

test("lease check detects cancellation and a lost attempt lease", async () => {
  const cancelled = fakeClient(job("CANCELLED"));
  await assert.rejects(() => jobs.assertJobNotCancelled("job-1", undefined, cancelled.client), (error: any) => error.name === "JobCancelledError");

  const reclaimed = fakeClient(job("TRANSCRIBING", 2));
  await assert.rejects(() => jobs.assertJobNotCancelled("job-1", 1, reclaimed.client), (error: any) => error.name === "JobLeaseLostError");

  const owning = fakeClient(job("TRANSCRIBING", 2));
  await jobs.assertJobNotCancelled("job-1", 2, owning.client);
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

test("claimNextJob prioritizes higher-priority jobs over older queued jobs", async () => {
  const olderLowPriority = {
    id: "job-low",
    type: "RENDER",
    status: "QUEUED",
    attempts: 0,
    payload: { priority: 10 },
    createdAt: new Date(1000),
    startedAt: null,
    finishedAt: null,
    runAfter: null,
    error: null,
  };
  const newerHighPriority = {
    id: "job-high",
    type: "RENDER",
    status: "QUEUED",
    attempts: 0,
    payload: { priority: 100 },
    createdAt: new Date(2000),
    startedAt: null,
    finishedAt: null,
    runAfter: null,
    error: null,
  };
  const rows = [olderLowPriority, newerHighPriority];
  const client: any = {
    job: {
      findMany: async () => rows.filter((r) => r.status === "QUEUED"),
      findUnique: async ({ where }: any) => rows.find((r) => r.id === where.id) ?? null,
      updateMany: async ({ where, data }: any) => {
        const targetId = where.AND?.[0]?.id;
        if (!targetId) return { count: 0 };
        const row = rows.find((r) => r.id === targetId);
        if (!row) return { count: 0 };
        row.status = data.status;
        return { count: 1 };
      },
    },
  };

  const claimed = await jobs.claimNextJob(client);
  assert.equal(claimed?.id, "job-high");
});

test("cancelProjectJobs propagates cancellation across all project jobs, renders, and rendering clips", async () => {
  const jobRows = [
    { id: "j1", userId: "u1", projectId: "p1", status: "TRANSCRIBING" },
    { id: "j2", userId: "u1", projectId: "p1", status: "QUEUED" },
    { id: "j3", userId: "u1", projectId: "p1", status: "READY" },
  ];
  const renderRows = [
    { id: "r1", projectId: "p1", status: "QUEUED", error: null as string | null },
    { id: "r2", projectId: "p1", status: "READY", error: null as string | null },
  ];
  const clipRows = [
    { id: "c1", projectId: "p1", status: "RENDERING" },
    { id: "c2", projectId: "p1", status: "READY" },
  ];

  const client: any = {
    job: {
      updateMany: async ({ where, data }: any) => {
        let count = 0;
        for (const r of jobRows) {
          if (r.projectId === where.projectId && where.status.in.includes(r.status)) {
            r.status = data.status;
            count += 1;
          }
        }
        return { count };
      },
    },
    render: {
      updateMany: async ({ where, data }: any) => {
        let count = 0;
        for (const r of renderRows) {
          if (r.projectId === where.clip.projectId && where.status.in.includes(r.status)) {
            r.status = data.status;
            r.error = data.error;
            count += 1;
          }
        }
        return { count };
      },
    },
    clip: {
      updateMany: async ({ where, data }: any) => {
        let count = 0;
        for (const c of clipRows) {
          if (c.projectId === where.projectId && c.status === where.status) {
            c.status = data.status;
            count += 1;
          }
        }
        return { count };
      },
    },
  };

  const count = await jobs.cancelProjectJobs({ jobId: "j1", userId: "u1", projectId: "p1" }, client);
  assert.equal(count, 2);
  assert.equal(jobRows[0].status, "CANCELLED");
  assert.equal(jobRows[1].status, "CANCELLED");
  assert.equal(jobRows[2].status, "READY");
  assert.equal(renderRows[0].status, "FAILED");
  assert.equal(renderRows[1].status, "READY");
  assert.equal(clipRows[0].status, "CANDIDATE");
  assert.equal(clipRows[1].status, "READY");
});

test("completeJobAndEnqueueMany finishes active job and deduplicates chunk successors", async () => {
  const active = fakeClient(job("TRANSCRIBING", 1));
  const specs = [
    {
      userId: "u1",
      projectId: "p1",
      type: "ANALYZE",
      payload: { transcriptId: "t1" },
      dedupeKeyPath: ["transcriptId"],
      dedupeValue: "t1",
    },
    {
      userId: "u1",
      projectId: "p1",
      type: "TRANSCRIBE",
      payload: { rangeCursorSeconds: 300 },
      dedupeKeyPath: ["rangeCursorSeconds"],
      dedupeValue: 300,
    },
  ];
  active.client.job.findFirst = async ({ where }: any) => {
    const val = where.payload?.equals;
    return active.enqueued.find((item: any) =>
      Object.values(item.payload).includes(val)
    ) || null;
  };

  const created = await jobs.completeJobAndEnqueueMany("job-1", specs, { expectedAttempts: 1 }, active.client);
  assert.equal(active.getCurrent()?.status, "READY");
  assert.equal(created.length, 2);
});
