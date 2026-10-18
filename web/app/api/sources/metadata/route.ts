import { requireUser } from "../../../../lib/auth";
import { parseSupportedSourceUrl } from "../../../../lib/source-url";
import { getSourceMetadata } from "../../../../lib/source-metadata";
import { db } from "../../../../lib/db";
import { analysisEntitlement } from "../../../../lib/analysis-range";

export async function POST(request: Request) {
  let stage = "authentication";
  try {
    const user = await requireUser();
    stage = "request parsing";
    const body = await request.json().catch(() => null) as Record<string, unknown> | null;
    if (!body || typeof body !== "object") return Response.json({ error: "Send a valid JSON object." }, { status: 400 });
    let source: ReturnType<typeof parseSupportedSourceUrl>;
    try { source = parseSupportedSourceUrl(body.sourceUrl); }
    catch (error) { return Response.json({ error: error instanceof Error ? error.message : "Invalid source URL." }, { status: 400 }); }

    stage = "AI metadata and subscription lookup";
    const [metadata, subscription] = await Promise.all([
      getSourceMetadata(source.url, source.type, user.id),
      db.subscription.findUnique({ where: { userId: user.id }, select: { plan: true, status: true } }),
    ]);
    return Response.json({ ...metadata, sourceType: source.type, entitlement: analysisEntitlement(subscription) }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") return Response.json({ error: "Unauthorized" }, { status: 401 });
    console.error("[api/sources/metadata] Request failed", {
      stage,
      error: error instanceof Error ? { name: error.name, message: error.message } : String(error),
    });
    return Response.json({ error: error instanceof Error ? error.message : "Could not retrieve source metadata." }, { status: 502 });
  }
}
