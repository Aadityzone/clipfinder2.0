import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const clip = await db.clip.findFirst({ where: { id, project: { userId: user.id } }, include: { renders: { orderBy: { createdAt: "desc" }, take: 1 } } });
    if (!clip) return Response.json({ error: "Not found" }, { status: 404 });
    return Response.json({ render: clip.renders[0] ?? null });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") return Response.json({ error: "Unauthorized" }, { status: 401 });
    throw error;
  }
}

export async function POST(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const clip = await db.clip.findFirst({ where: { id }, include: { project: true, edit: true } });
    if (!clip || clip.project.userId !== user.id) return Response.json({ error: "Not found" }, { status: 404 });
    if (!clip.edit) return Response.json({ error: "Save an edit before rendering." }, { status: 400 });

    const render = await db.$transaction(async (tx) => {
      const created = await tx.render.create({ data: { clipId: id, status: "QUEUED" } });
      await tx.job.create({ data: { userId: user.id, projectId: clip.projectId, type: "RENDER", payload: { clipId: id, renderId: created.id } } });
      return created;
    });
    return Response.json({ render }, { status: 202 });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") return Response.json({ error: "Unauthorized" }, { status: 401 });
    throw error;
  }
}
