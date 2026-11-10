import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const body = await req.json();
    const provider = String(body.provider || "").toLowerCase();
    if (!["youtube", "tiktok"].includes(provider)) return Response.json({ error: "Unsupported publishing provider" }, { status: 400 });
    const clip = await db.clip.findFirst({ where: { id, project: { userId: user.id } }, include: { renders: { where: { status: "READY" }, orderBy: { createdAt: "desc" }, take: 1 } } });
    if (!clip) return Response.json({ error: "Not found" }, { status: 404 });
    if (!clip.renders[0]) return Response.json({ error: "Render the clip before publishing." }, { status: 409 });
    const connection = await db.socialConnection.findFirst({ where: { userId: user.id, provider } });
    if (!connection) return Response.json({ error: `Connect ${provider} in Settings first.` }, { status: 409 });
    const scheduledFor = body.scheduledFor ? new Date(body.scheduledFor) : new Date();
    if (Number.isNaN(scheduledFor.getTime())) return Response.json({ error: "Invalid schedule time" }, { status: 400 });
    const status = scheduledFor.getTime() > Date.now() ? "SCHEDULED" : "PUBLISHING";
    const post = await db.$transaction(async (tx) => {
      const created = await tx.scheduledPost.create({ data: {
        userId: user.id, clipId: id, socialConnectionId: connection.id, scheduledFor, status,
        metadata: { title: String(body.title || clip.title || "Clip").slice(0, 2200), description: String(body.description || "") },
      } });
      if (status === "PUBLISHING") await tx.job.create({ data: { userId: user.id, projectId: clip.projectId, type: "PUBLISH", payload: { scheduledPostId: created.id } } });
      return created;
    });
    return Response.json(post, { status: 202 });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") return Response.json({ error: "Unauthorized" }, { status: 401 });
    throw error;
  }
}
