import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";

const MAX_EDIT_SEGMENTS = 100;

type EditSegment = { startS: number; endS: number };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseSegments(body: Record<string, unknown>): EditSegment[] | null {
  const raw = Array.isArray(body.segments)
    ? body.segments
    : [{ startS: body.startS, endS: body.endS }];

  if (raw.length === 0 || raw.length > MAX_EDIT_SEGMENTS) return null;

  const segments: EditSegment[] = [];
  for (const value of raw) {
    if (!isRecord(value)) return null;
    const { startS, endS } = value;
    if (
      typeof startS !== "number" ||
      typeof endS !== "number" ||
      !Number.isFinite(startS) ||
      !Number.isFinite(endS) ||
      startS < 0 ||
      endS <= startS
    ) {
      return null;
    }
    segments.push({ startS, endS });
  }

  return segments;
}

export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const user = await requireUser();
    const { id } = await params;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return Response.json({ error: "Request body must contain valid JSON." }, { status: 400 });
    }

    if (!isRecord(body)) {
      return Response.json({ error: "Request body must be a JSON object." }, { status: 400 });
    }

    const clip = await db.clip.findFirst({
      where: { id },
      include: { project: true },
    });
    if (!clip || clip.project.userId !== user.id) {
      return Response.json({ error: "Not found" }, { status: 404 });
    }

    const segments = parseSegments(body);
    if (!segments) {
      return Response.json(
        { error: `Provide between 1 and ${MAX_EDIT_SEGMENTS} valid edit segments.` },
        { status: 400 },
      );
    }

    for (let index = 0; index < segments.length; index++) {
      const segment = segments[index];
      if (segment.startS < clip.startS || segment.endS > clip.endS) {
        return Response.json(
          { error: "Edit segments must stay within the clip's source boundaries." },
          { status: 400 },
        );
      }
      if (index > 0) {
        const previous = segments[index - 1];
        if (segment.startS < previous.startS) {
          return Response.json(
            { error: "Edit segments must be ordered by start time." },
            { status: 400 },
          );
        }
        if (segment.startS < previous.endS) {
          return Response.json({ error: "Segments cannot overlap." }, { status: 400 });
        }
      }
    }

    const allowedAspects = ["9:16", "16:9", "1:1"];
    if (body.aspectRatio !== undefined && !allowedAspects.includes(String(body.aspectRatio))) {
      return Response.json({ error: "Aspect ratio must be 9:16, 16:9, or 1:1." }, { status: 400 });
    }
    const aspectRatio = body.aspectRatio === undefined ? "9:16" : String(body.aspectRatio);
    const first = segments[0];
    const last = segments[segments.length - 1];

    const edit = await db.clipEdit.upsert({
      where: { clipId: id },
      create: { clipId: id, aspectRatio, segments },
      update: { aspectRatio, segments, version: { increment: 1 } },
    });

    await db.clip.update({
      where: { id },
      data: { startS: first.startS, endS: last.endS, status: "EDITING" },
    });
    await db.creatorEvent.create({
      data: {
        userId: user.id,
        projectId: clip.projectId,
        event: "EDIT",
        metadata: {
          clipId: id,
          aspectRatio,
          segmentCount: segments.length,
          editVersion: edit.version,
        },
      },
    });

    return Response.json(edit);
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}
