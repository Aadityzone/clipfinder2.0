import { requireUser } from "../../../../lib/auth";
import { db } from "../../../../lib/db";
import { headStorage, getStorageRange } from "../../../../lib/storage";

export const runtime = "nodejs";

type ByteRange = { start: number; end: number };

function parseByteRange(value: string, size: number): ByteRange | null {
  const match = /^bytes=(\d*)-(\d*)$/.exec(value.trim());
  if (!match || size <= 0 || (!match[1] && !match[2])) return null;

  // Suffix range: bytes=-500 means the final 500 bytes.
  if (!match[1]) {
    const suffixLength = Number(match[2]);
    if (!Number.isSafeInteger(suffixLength) || suffixLength <= 0) return null;
    return { start: Math.max(0, size - suffixLength), end: size - 1 };
  }

  const start = Number(match[1]);
  const requestedEnd = match[2] ? Number(match[2]) : size - 1;
  if (
    !Number.isSafeInteger(start) ||
    !Number.isSafeInteger(requestedEnd) ||
    start < 0 ||
    requestedEnd < start ||
    start >= size
  ) {
    return null;
  }

  return { start, end: Math.min(requestedEnd, size - 1) };
}

function rangeNotSatisfiable(size: number) {
  return new Response(null, {
    status: 416,
    headers: {
      "Accept-Ranges": "bytes",
      "Content-Range": `bytes */${size}`,
    },
  });
}

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const user = await requireUser();
    const { id } = await params;
    const exportRecord = await db.export.findFirst({
      where: { id, userId: user.id, status: "READY" },
    });
    if (!exportRecord?.storageKey) return new Response("Not found", { status: 404 });

    const meta = await headStorage(exportRecord.storageKey);
    const commonHeaders = {
      "Content-Type": "video/mp4",
      "Accept-Ranges": "bytes",
      "Content-Disposition": `attachment; filename="clip-${id}.mp4"`,
    };
    const rangeHeader = req.headers.get("range");

    if (!rangeHeader) {
      const object = await getStorageRange(exportRecord.storageKey);
      return new Response(object.body, {
        headers: {
          ...commonHeaders,
          "Content-Length": String(meta.size),
        },
      });
    }

    const range = parseByteRange(rangeHeader, meta.size);
    if (!range) return rangeNotSatisfiable(meta.size);

    const object = await getStorageRange(exportRecord.storageKey, range.start, range.end);
    return new Response(object.body, {
      status: 206,
      headers: {
        ...commonHeaders,
        "Content-Length": String(range.end - range.start + 1),
        "Content-Range": `bytes ${range.start}-${range.end}/${meta.size}`,
      },
    });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return new Response("Unauthorized", { status: 401 });
    }
    return new Response("Not found", { status: 404 });
  }
}
