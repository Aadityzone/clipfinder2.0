import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";

type CaptionCue = { startS: number; endS: number; text: string };

function srtTime(seconds: number) {
  const milliseconds = Math.floor((seconds % 1) * 1000);
  const total = Math.floor(seconds);
  const secs = total % 60;
  const minutes = Math.floor(total / 60) % 60;
  const hours = Math.floor(total / 3600);
  return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")},${milliseconds.toString().padStart(3, "0")}`;
}

async function clipFor(userId: string, id: string) {
  return db.clip.findFirst({
    where: { id, project: { userId } },
    include: {
      project: {
        include: {
          source: {
            include: {
              media: {
                include: {
                  transcripts: { include: { segments: true } },
                },
              },
            },
          },
        },
      },
      captions: { orderBy: { createdAt: "desc" }, take: 1 },
    },
  });
}

function boundedCues(raw: unknown, clipDuration: number): CaptionCue[] | null {
  if (!Array.isArray(raw)) return null;
  const cues: CaptionCue[] = [];
  let previousEnd = 0;
  for (const value of raw) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
    const cue = value as Record<string, unknown>;
    const startS = cue.startS ?? cue.start;
    const endS = cue.endS ?? cue.end;
    if (typeof startS !== "number" || typeof endS !== "number" ||
        !Number.isFinite(startS) || !Number.isFinite(endS) ||
        startS < previousEnd || endS <= startS || endS > clipDuration) return null;
    cues.push({ startS, endS, text: String(cue.text ?? "").slice(0, 500) });
    previousEnd = endS;
  }
  return cues;
}

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const clip = await clipFor(user.id, id);
    if (!clip) return new Response("Not found", { status: 404 });

    const transcript = clip.project.source?.media[0]?.transcripts[0];
    const track = clip.captions[0];
    const stored = Array.isArray(track?.cues) ? track.cues as unknown[] : null;
    const cues = stored
      ? stored.map((value) => {
          const cue = value as Record<string, unknown>;
          return { start: Number(cue.startS ?? cue.start), end: Number(cue.endS ?? cue.end), text: String(cue.text ?? "") };
        })
      : transcript?.segments
          .filter((segment) => segment.endS > clip.startS && segment.startS < clip.endS)
          .map((segment) => ({
            start: Math.max(0, segment.startS - clip.startS),
            end: Math.min(clip.endS, segment.endS) - clip.startS,
            text: segment.text,
          })) ?? [];

    if (new URL(req.url).searchParams.get("format") === "json") {
      return Response.json({ cues, style: track?.style || {} });
    }
    const body = cues.map((cue, index) =>
      `${index + 1}\n${srtTime(cue.start)} --> ${srtTime(cue.end)}\n${cue.text}\n`,
    ).join("\n");
    return new Response(body, {
      headers: {
        "Content-Type": "application/x-subrip; charset=utf-8",
        "Content-Disposition": `attachment; filename="clip-${id}.srt"`,
      },
    });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return new Response("Unauthorized", { status: 401 });
    }
    return new Response("Not found", { status: 404 });
  }
}

export async function PUT(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const clip = await db.clip.findFirst({ where: { id, project: { userId: user.id } } });
    if (!clip) return Response.json({ error: "Not found" }, { status: 404 });

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return Response.json({ error: "Request body must contain valid JSON." }, { status: 400 });
    }
    if (typeof body !== "object" || body === null || Array.isArray(body)) {
      return Response.json({ error: "Request body must be a JSON object." }, { status: 400 });
    }
    const data = body as Record<string, unknown>;
    const cues = boundedCues(data.cues, clip.endS - clip.startS);
    if (!cues) {
      return Response.json({ error: "Caption cues must be ordered, non-overlapping, and within the clip duration." }, { status: 400 });
    }

    const track = await db.captionTrack.create({
      data: {
        clipId: id,
        language: String(data.language || "en").slice(0, 12),
        style: data.style && typeof data.style === "object" && !Array.isArray(data.style) ? data.style : {},
        cues,
      },
    });
    return Response.json(track, { status: 201 });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}
