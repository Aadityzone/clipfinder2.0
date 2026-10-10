import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";
import { mkdir, stat } from "node:fs/promises";
import { createWriteStream } from "node:fs";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { putFile } from "../../../../../lib/storage";

const exec = promisify(exec);
export const runtime = "nodejs";

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const project = await db.project.findFirst({ where: { id, userId: user.id } });
    if (!project) return Response.json({ error: "Project not found." }, { status: 404 });
    if (!req.body) return Response.json({ error: "Request body is required." }, { status: 400 });

    const type = req.headers.get("content-type") || "application/octet-stream";
    if (!type.startsWith("video/") && !type.startsWith("audio/")) {
      return Response.json({ error: "Unsupported media type. Upload a video or audio file." }, { status: 415 });
    }

    const encodedName = req.headers.get("x-file-name") || "source.mp4";
    let suppliedName = encodedName;
    try { suppliedName = decodeURIComponent(encodedName); } catch { /* Keep the raw header and sanitize it below. */ }
    const leafName = suppliedName.split(/[\\/]/).pop() || "source.mp4";
    const safeName = leafName.normalize("NFKC").replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 140) || "source.mp4";
    const key = "uploads/" + user.id + "/" + project.id + "/" + Date.now() + "-" + safeName;
    const root = path.resolve(process.env.MEDIA_STORAGE_ROOT || "../storage");
    const full = path.join(root, key);
    await mkdir(path.dirname(full), { recursive: true });
    await pipeline(Readable.fromWeb(req.body as never), createWriteStream(full));

    const info = await stat(full);
    if (!info.size) return Response.json({ error: "The uploaded file is empty." }, { status: 400 });
    await putFile(key, full, type);
    const probe = await exec("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", full]);
    const metadata = JSON.parse(probe.stdout) as { streams?: Array<{ codec_type?: string; width?: number; height?: number; codec_name?: string; r_frame_rate?: string }>; format?: { duration?: string } };
    const streams = metadata.streams || [];
    const video = streams.find((stream) => stream.codec_type === "video");
    const audio = streams.find((stream) => stream.codec_type === "audio");
    if (!video && !audio) return Response.json({ error: "The uploaded file contains no supported audio or video stream." }, { status: 415 });

    const source = await db.source.create({ data: { userId: user.id, type: "UPLOAD", name: leafName } });
    const asset = await db.mediaAsset.create({ data: {
      sourceId: source.id, storageKey: key, mimeType: type, sizeBytes: BigInt(info.size),
      durationS: Number(metadata.format?.duration || 0), width: video?.width, height: video?.height,
      codec: video?.codec_name ?? audio?.codec_name, hasAudio: !!audio,
    } });
    await db.project.update({ where: { id: project.id }, data: { sourceId: source.id } });
    const job = await db.job.create({ data: {
      userId: user.id, projectId: project.id, type: "TRANSCRIBE",
      payload: { mediaAssetId: asset.id, mediaPath: full },
    } });
    return Response.json({ asset, job }, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upload failed.";
    return Response.json({ error: message }, { status: 500 });
  }
}
