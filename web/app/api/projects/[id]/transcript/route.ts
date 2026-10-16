import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const project = await db.project.findFirst({
      where: { id, userId: user.id },
      include: { source: { include: { media: { include: { transcripts: { include: { segments: true } } } } } } },
    });
    if (!project) return Response.json({ error: "Not found" }, { status: 404 });
    const transcripts = project.source?.media[0]?.transcripts ?? [];
    const segments = transcripts.flatMap((transcript) => transcript.segments.map((segment) => ({ ...segment, transcriptId: transcript.id }))).sort((a, b) => a.startS - b.startS);
    return Response.json(transcripts.length ? { id: transcripts[0].id, segments } : null);
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") return Response.json({ error: "Unauthorized" }, { status: 401 });
    throw error;
  }
}
