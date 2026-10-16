import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";
import { analysisEntitlement, validateAnalysisRange } from "../../../../../lib/analysis-range";
import { mkdir, stat } from "node:fs/promises";
import { createWriteStream } from "node:fs";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { putFile } from "../../../../../lib/storage";

const exec = promisify(execFile);
export const runtime = "nodejs";

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const project = await db.project.findFirst({ where: { id, userId: user.id } });
    if (!project) return Response.json({ error: "Not found" }, { status: 404 });
    if (project.sourceId) return Response.json({ error: "This project already has a source attached." }, { status: 409 });
    if (!request.body) return Response.json({ error: "Request body is required." }, { status: 400 });
    const mimeType = request.headers.get("content-type") || "application/octet-stream";
    if (!mimeType.startsWith("video/") && !mimeType.startsWith("audio/")) return Response.json({ error: "Unsupported media type." }, { status: 415 });

    const encodedName = request.headers.get("x-file-name") || "source.mp4";
    let originalName: string;
    try { originalName = decodeURIComponent(encodedName); }
    catch { return Response.json({ error: "Invalid upload filename encoding." }, { status: 400 }); }
    originalName = originalName.replace(/[\\/\0-\x1f\x7f]/g, "_").slice(0, 240) || "source.mp4";
    const safeName = originalName.normalize("NFKD").replace(/[^a-zA-Z0-9._-]/g, "_");
    const storageKey = `uploads/${user.id}/${project.id}/${Date.now()}-${safeName}`;
    const root = path.resolve(process.env.MEDIA_STORAGE_ROOT || "../storage");
    const fullPath = path.join(root, storageKey);
    await mkdir(path.dirname(fullPath), { recursive: true });
    await pipeline(Readable.fromWeb(request.body as any), createWriteStream(fullPath));
    const fileInfo = await stat(fullPath);
    const probe = await exec("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", fullPath], { timeout: 30_000 });
    const probeData = JSON.parse(probe.stdout);
    const streams = Array.isArray(probeData.streams) ? probeData.streams : [];
    const video = streams.find((stream: any) => stream.codec_type === "video");
    const audio = streams.find((stream: any) => stream.codec_type === "audio");
    const duration = Number(probeData.format?.duration || 0);
    const subscription = await db.subscription.findUnique({ where: { userId: user.id }, select: { plan: true, status: true } });
    const entitlement = analysisEntitlement(subscription);
    const headerStart = request.headers.get("x-source-start-seconds");
    const headerEnd = request.headers.get("x-source-end-seconds");
    if ((headerStart === null) !== (headerEnd === null)) return Response.json({ error: "Provide both source range boundaries." }, { status: 400 });
    const startSeconds = headerStart === null ? 0 : Number(headerStart);
    const endSeconds = headerEnd === null ? Math.min(duration, entitlement.maxDurationMs / 1000) : Number(headerEnd);
    let sourceRange: { startSeconds: number; endSeconds: number };
    try {
      const range = validateAnalysisRange({ startSeconds, endSeconds, sourceDurationSeconds: duration, entitlement });
      sourceRange = { startSeconds: range.startMs / 1000, endSeconds: range.endMs / 1000 };
    } catch (error) {
      return Response.json({ error: error instanceof Error ? error.message : "Invalid analysis range." }, { status: 403 });
    }

    await putFile(storageKey, fullPath, mimeType);
    const result = await db.$transaction(async (tx) => {
      const source = await tx.source.create({ data: { userId: user.id, type: "UPLOAD", name: originalName } });
      const asset = await tx.mediaAsset.create({ data: {
        sourceId: source.id, storageKey, mimeType, sizeBytes: BigInt(fileInfo.size), durationS: duration,
        width: video?.width, height: video?.height, codec: video?.codec_name, hasAudio: Boolean(audio),
      } });
      await tx.project.update({ where: { id: project.id }, data: { sourceId: source.id } });
      const job = await tx.job.create({ data: {
        userId: user.id, projectId: project.id, type: "TRANSCRIBE",
        payload: { mediaAssetId: asset.id, mediaPath: fullPath, sourceRange, sourceDurationS: duration, mediaOffsetSeconds: 0, rangeLimitedDownload: false, rangeConfirmed: true },
      } });
      return { asset, job };
    });
    return Response.json(result, { status: 201 });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") return Response.json({ error: "Unauthorized" }, { status: 401 });
    return Response.json({ error: error instanceof Error ? error.message : "Upload failed." }, { status: 500 });
  }
}
