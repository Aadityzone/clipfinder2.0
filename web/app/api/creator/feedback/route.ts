import { requireUser } from "../../../../lib/auth";
import { loadCreatorFeedbackProfile } from "../../../../lib/creator-feedback";

export async function GET() {
  try {
    const user = await requireUser();
    const profile = await loadCreatorFeedbackProfile(user.id);
    return Response.json({
      ...profile,
      message: profile.active
        ? "Personalized ranking is active. Accepted, exported, and published clips provide positive signals; rejected clips provide negative signals. Score adjustments remain bounded."
        : "Personalized ranking activates after at least three positive clips (accepted/exported/published) and three rejected clips with feature data.",
    });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    throw error;
  }
}
