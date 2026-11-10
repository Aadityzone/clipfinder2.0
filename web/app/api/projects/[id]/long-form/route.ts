import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const project = await db.project.findFirst({ where: { id, userId: user.id }, include: { longFormDocument: true } });
    if (!project) return Response.json({ error: "Not found" }, { status: 404 });
    return Response.json(project.longFormDocument);
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") return Response.json({ error: "Unauthorized" }, { status: 401 });
    throw error;
  }
}

export async function POST(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const project = await db.project.findFirst({ where: { id, userId: user.id }, include: { longFormDocument: true } });
    if (!project) return Response.json({ error: "Not found" }, { status: 404 });
    if (!project.longFormDocument) return Response.json({ error: "Long-form analysis has not completed." }, { status: 409 });
    if (project.longFormDocument.renderStatus === "PROCESSING") return Response.json({ error: "Long-form render is already running." }, { status: 409 });

    const job = await db.$transaction(async (tx) => {
      const created = await tx.job.create({ data: { userId: user.id, projectId: project.id, type: "LONGFORM_RENDER", payload: { documentId: project.longFormDocument!.id } } });
      await tx.longFormDocument.update({ where: { id: project.longFormDocument!.id }, data: { renderStatus: "QUEUED" } });
      return created;
    });
    return Response.json(job, { status: 202 });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") return Response.json({ error: "Unauthorized" }, { status: 401 });
    throw error;
  }
}
