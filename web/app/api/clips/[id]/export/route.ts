import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";
import { headStorage } from "../../../../../lib/storage";

export async function POST(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const clip = await db.clip.findFirst({
      where: { id, project: { userId: user.id } },
      include: { renders: { where: { status: "READY" }, orderBy: { createdAt: "desc" }, take: 1 } },
    });
    if (!clip) return Response.json({ error: "Not found" }, { status: 404 });

    const render = clip.renders[0];
    if (!render?.storageKey) {
      return Response.json({ error: "Render is not ready yet." }, { status: 409 });
    }

    let artifact;
    try {
      artifact = await headStorage(render.storageKey);
    } catch {
      return Response.json({ error: "Rendered file is missing from storage. Render the clip again." }, { status: 409 });
    }
    if (!Number.isSafeInteger(artifact.size) || artifact.size < 1024) {
      return Response.json({ error: "Rendered file is empty or incomplete. Render the clip again." }, { status: 409 });
    }
    if (render.mimeType && render.mimeType !== "video/mp4") {
      return Response.json({ error: "Rendered file is not an MP4 export." }, { status: 409 });
    }

    const exportRecord = await db.export.create({
      data: { clipId: id, renderId: render.id, userId: user.id, storageKey: render.storageKey, status: "READY" },
    });
    await db.usage.update({ where: { userId: user.id }, data: { exports: { increment: 1 } } }).catch(() => {});
    await db.creatorEvent.create({
      data: { userId: user.id, projectId: clip.projectId, event: "EXPORT", metadata: { clipId: id, exportId: exportRecord.id } },
    });
    return Response.json({ id: exportRecord.id, url: `/api/exports/${exportRecord.id}` }, { status: 201 });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}
