import { requireUser } from "../../../../lib/auth";
import { db } from "../../../../lib/db";
import { buildCreatorFeedbackProfile } from "../../../../lib/creator-feedback";

export async function GET() {
  try {
    const user = await requireUser();
    const clips = await db.clip.findMany({
      where: {
        project: { userId: user.id },
        status: { in: ["SELECTED", "REJECTED"] },
        highlightId: { not: null },
      },
      orderBy: { updatedAt: "desc" },
      take: 300,
      select: { status: true, highlight: { select: { features: true } } },
    });
    const profile = buildCreatorFeedbackProfile(clips);
    return Response.json({
      ...profile,
      message: profile.active
        ? "Personalized ranking is active. We learn only from explicit accepted/rejected clips and keep the score adjustment bounded."
        : "Personalized ranking activates after at least three accepted and three rejected clips with feature data.",
    });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}
