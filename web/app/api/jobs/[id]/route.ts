import { requireUser } from "../../../../lib/auth";
import { db } from "../../../../lib/db";

const CANCELLABLE = ["QUEUED", "RETRYING", "DOWNLOADING", "INGESTING", "TRANSCRIBING", "ANALYZING", "EDITING", "RENDERING"] as const;

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const job = await db.job.findFirst({ where: { id, userId: user.id } });
    if (!job) return Response.json({ error: "Not found" }, { status: 404 });
    return Response.json(job);
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const body = await req.json().catch(() => ({}));
    const job = await db.job.findFirst({ where: { id, userId: user.id } });
    if (!job) return Response.json({ error: "Not found" }, { status: 404 });

    if (body.action === "cancel") {
      const changed = await db.job.updateMany({
        where: { id, userId: user.id, status: { in: [...CANCELLABLE] } },
        data: { status: "CANCELLED", finishedAt: new Date(), runAfter: null },
      });
      const updated = await db.job.findUnique({ where: { id } });
      if (!changed.count) {
        return Response.json({ error: "Job is no longer cancellable", job: updated }, { status: 409 });
      }
      return Response.json(updated);
    }

    if (body.action === "retry" && job.status === "FAILED") {
      // A manual retry is an explicit new attempt cycle. Automatic retries are
      // capped separately in the worker and use bounded backoff.
      const changed = await db.job.updateMany({
        where: { id, userId: user.id, status: "FAILED" },
        data: {
          status: "QUEUED",
          attempts: 0,
          progress: 0,
          error: null,
          startedAt: null,
          finishedAt: null,
          runAfter: null,
        },
      });
      const updated = await db.job.findUnique({ where: { id } });
      if (!changed.count) {
        return Response.json({ error: "Job changed before it could be retried", job: updated }, { status: 409 });
      }
      return Response.json(updated);
    }

    return Response.json({ error: "Invalid job action or state" }, { status: 409 });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}
