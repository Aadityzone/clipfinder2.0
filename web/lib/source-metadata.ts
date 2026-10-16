import { getGoogleDriveMetadata } from "./sources/google-drive";

export type SourceMetadata = { title: string | null; platform: string; duration: number; thumbnail: string | null };
const AI = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";

export async function getSourceMetadata(url: string, type: string, userId: string): Promise<SourceMetadata> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      if (type === "GOOGLE_DRIVE") return await getGoogleDriveMetadata(userId, url);
      const response = await fetch(`${AI}/v1/source-metadata`, {
        method: "POST",
        headers: { "content-type": "application/json", ...(process.env.AI_SERVICE_SECRET ? { "x-ai-secret": process.env.AI_SERVICE_SECRET } : {}) },
        body: JSON.stringify({ url }),
        signal: AbortSignal.timeout(35_000),
        cache: "no-store",
      });
      const result = await response.json().catch(() => ({})) as Record<string, unknown>;
      if (!response.ok) throw new Error(String(result.detail ?? "Source metadata could not be retrieved."));
      const duration = Number(result.duration);
      if (!Number.isFinite(duration) || duration <= 0) throw new Error("The source did not provide a valid duration.");
      return {
        title: typeof result.title === "string" ? result.title : null,
        platform: typeof result.platform === "string" ? result.platform : type,
        duration,
        thumbnail: typeof result.thumbnail === "string" ? result.thumbnail : null,
      };
    } catch (error) {
      lastError = error;
      if (attempt === 0) await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Source metadata could not be retrieved.");
}
