import { NextRequest } from "next/server";
import { db } from "../../../lib/db";
import { requireUser } from "../../../lib/auth";

function parseSourceUrl(value: unknown): { url: string; type: "YOUTUBE" | "TWITCH" | "KICK" | "GOOGLE_DRIVE" | "URL" } | null {
  if (value == null || value === "") return null;
  if (typeof value !== "string" || value.length > 2048) {
    throw new Error("Enter a valid video URL.");
  }

  let parsed: URL;
  try {
    parsed = new URL(value.trim());
  } catch {
    throw new Error("Enter a valid video URL.");
  }

  if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) {
    throw new Error("Video URLs must use HTTP or HTTPS and must not contain embedded credentials.");
  }

  const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
  const matches = (domain: string) => host === domain || host.endsWith("." + domain);
  if (matches("youtube.com") || matches("youtu.be")) return { url: parsed.toString(), type: "YOUTUBE" };
  if (matches("twitch.tv")) return { url: parsed.toString(), type: "TWITCH" };
  if (matches("kick.com")) return { url: parsed.toString(), type: "KICK" };
  if (matches("drive.google.com")) return { url: parsed.toString(), type: "GOOGLE_DRIVE" };
  throw new Error("Unsupported source. Use a YouTube, Twitch, Kick, or Google Drive URL.");
}

export async function GET() {
  try {
    const user = await requireUser();
    return Response.json(await db.project.findMany({
      where: { userId: user.id },
      orderBy: { updatedAt: "desc" },
      include: { source: true, clips: { orderBy: { score: "desc" } } },
    }));
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}

export async function POST(req: NextRequest) {
  try {
    const user = await requireUser();
    let body: Record<string, unknown>;
    try {
      const parsed: unknown = await req.json();
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return Response.json({ error: "Request body must be a JSON object." }, { status: 400 });
      }
      body = parsed as Record<string, unknown>;
    } catch {
      return Response.json({ error: "Request body must contain valid JSON." }, { status: 400 });
    }

    if (body.rightsConfirmed !== true) {
      return Response.json({ error: "Confirm that you have the rights to process this media." }, { status: 400 });
    }

    let parsedSource: ReturnType<typeof parseSourceUrl>;
    try {
      parsedSource = parseSourceUrl(body.sourceUrl);
    } catch (error) {
      return Response.json({ error: error instanceof Error ? error.message : "Invalid source URL." }, { status: 400 });
    }

    const name = String(body.name ?? "Untitled project").trim().slice(0, 120) || "Untitled project";
    const categories = Array.isArray(body.categories) ? body.categories.map(String).slice(0, 8) : ["AI Detect"];
    const instructions = String(body.customInstructions ?? "").trim().slice(0, 2000);
    const customInstructions = [
      categories.length ? "Clip categories: " + categories.join(", ") : "",
      instructions,
    ].filter(Boolean).join("\n\n") || null;
    const mode = body.mode === "LONG_FORM" ? "LONG_FORM" : "SHORTS";
    const language = String(body.outputLanguage ?? "en").slice(0, 12);

    const project = await db.$transaction(async (tx) => {
      const source = parsedSource
        ? await tx.source.create({
            data: { userId: user.id, type: parsedSource.type, url: parsedSource.url, name },
          })
        : null;
      const created = await tx.project.create({
        data: {
          userId: user.id,
          name,
          sourceId: source?.id,
          mode,
          outputLanguage: language,
          customInstructions,
        },
      });
      if (parsedSource) {
        await tx.job.create({
          data: {
            userId: user.id,
            projectId: created.id,
            type: "INGEST",
            payload: {
              sourceUrl: parsedSource.url,
              categories,
              timeframe: body.timeframe ?? "full",
              rightsConfirmed: true,
            },
          },
        });
      }
      return created;
    });

    return Response.json(project, { status: 201 });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}
