import { NextRequest } from "next/server";
import { db } from "../../../lib/db";
import { requireUser } from "../../../lib/auth";
import { analysisEntitlement, validateAnalysisRange } from "../../../lib/analysis-range";
import { parseSupportedSourceUrl } from "../../../lib/source-url";
import { getSourceMetadata } from "../../../lib/source-metadata";

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

    let parsedSource: ReturnType<typeof parseSupportedSourceUrl> | null;
    try {
      parsedSource = body.sourceUrl == null || body.sourceUrl === "" ? null : parseSupportedSourceUrl(body.sourceUrl);
    } catch (error) {
      return Response.json({ error: error instanceof Error ? error.message : "Invalid source URL." }, { status: 400 });
    }

    const name = String(body.name ?? "Untitled project").trim().slice(0, 120) || "Untitled project";
    const categories = Array.isArray(body.categories) ? body.categories.map(String).slice(0, 8) : ["AI Detect"];
    const instructions = String(body.customInstructions ?? "").trim().slice(0, 2000);
    const allowedGenres = new Set(["auto", "general", "gaming", "irl_stream", "movies_tv", "anime", "tech", "knowledge", "facts", "podcast"]);
    const requestedGenre = typeof body.genre === "string" && allowedGenres.has(body.genre) ? body.genre : "auto";
    const customInstructions = [
      "Content genre: " + requestedGenre,
      categories.length ? "Clip categories: " + categories.join(", ") : "",
      instructions,
    ].filter(Boolean).join("\n\n") || null;
    let sourceRange: { startSeconds: number; endSeconds: number } | null = null;
    let sourceDurationS: number | null = null;
    if (parsedSource) {
      if (body.rangeConfirmed !== true) return Response.json({ error: "Select and confirm an analysis range before creating the project." }, { status: 400 });
      const [subscription, metadata] = await Promise.all([
        db.subscription.findUnique({ where: { userId: user.id }, select: { plan: true, status: true } }),
        getSourceMetadata(parsedSource.url, parsedSource.type, user.id),
      ]);
      try {
        const range = validateAnalysisRange({
          startSeconds: body.sourceStartSeconds,
          endSeconds: body.sourceEndSeconds,
          sourceDurationSeconds: metadata.duration,
          entitlement: analysisEntitlement(subscription),
        });
        sourceRange = { startSeconds: range.startMs / 1000, endSeconds: range.endMs / 1000 };
        sourceDurationS = metadata.duration;
      } catch (error) {
        return Response.json({ error: error instanceof Error ? error.message : "Invalid analysis range." }, { status: 403 });
      }
    }
    const mode = body.mode === "LONG_FORM" ? "LONG_FORM" : "SHORTS";
    const language = String(body.outputLanguage ?? "en").slice(0, 12);

    const outcome = await db.$transaction(async (tx) => {
      if (parsedSource && sourceRange) {
        const key = `${parsedSource.url}|${sourceRange.startSeconds}|${sourceRange.endSeconds}`;
        await tx.$queryRaw`SELECT pg_advisory_xact_lock(hashtext(${user.id}), hashtext(${key}))`;
        const activeProjects = await tx.project.findMany({
          where: {
            userId: user.id,
            source: { is: { url: parsedSource.url, type: parsedSource.type } },
            jobs: { some: { type: { in: ["INGEST", "TRANSCRIBE", "ANALYZE", "LONGFORM_ANALYZE"] }, status: { in: ["QUEUED", "RETRYING", "DOWNLOADING", "INGESTING", "TRANSCRIBING", "ANALYZING"] } } },
          },
          include: { jobs: { where: { type: "INGEST" }, orderBy: { createdAt: "desc" }, take: 1 } },
        });
        const duplicate = activeProjects.find((candidate) => {
          const ingestJob = candidate.jobs[0];
          const payload = ingestJob?.payload && typeof ingestJob.payload === "object" ? ingestJob.payload as Record<string, unknown> : {};
          const requested = payload.sourceRange && typeof payload.sourceRange === "object" ? payload.sourceRange as Record<string, unknown> : {};
          return payload.sourceUrl === parsedSource.url && Number(requested.startSeconds) === sourceRange.startSeconds && Number(requested.endSeconds) === sourceRange.endSeconds;
        });
        if (duplicate) return { project: duplicate, reused: true };
      }
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
              sourceRange,
              sourceDurationS,
              rangeLimitedDownload: parsedSource.type !== "GOOGLE_DRIVE",
              rangeConfirmed: true,
              rightsConfirmed: true,
            },
          },
        });
      }
      return { project: created, reused: false };
    });

    return Response.json(outcome.project, { status: outcome.reused ? 200 : 201 });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}
