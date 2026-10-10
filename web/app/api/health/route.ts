import { db } from "../../../lib/db";
import { checkStorageHealth } from "../../../lib/storage";

export const dynamic = "force-dynamic";

type CheckStatus = "ok" | "unavailable";

async function checkDatabase(): Promise<CheckStatus> {
  try {
    await db.$queryRawUnsafe("SELECT 1");
    return "ok";
  } catch {
    return "unavailable";
  }
}

async function checkAiService(): Promise<CheckStatus> {
  const baseUrl = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";
  try {
    const response = await fetch(new URL("/health", baseUrl), {
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    if (!response.ok) return "unavailable";
    const body = (await response.json()) as { ok?: boolean };
    return body.ok === true ? "ok" : "unavailable";
  } catch {
    return "unavailable";
  }
}

async function checkStorage(): Promise<CheckStatus> {
  try {
    await checkStorageHealth();
    return "ok";
  } catch {
    return "unavailable";
  }
}

export async function GET() {
  const [database, ai, storage] = await Promise.all([
    checkDatabase(),
    checkAiService(),
    checkStorage(),
  ]);
  const ok = database === "ok" && ai === "ok" && storage === "ok";

  return Response.json(
    { ok, service: "web", checks: { database, ai, storage } },
    { status: ok ? 200 : 503, headers: { "Cache-Control": "no-store" } },
  );
}
