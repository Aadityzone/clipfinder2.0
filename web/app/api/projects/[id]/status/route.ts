import { requireUser } from "../../../../../lib/auth";
import { db } from "../../../../../lib/db";
import { deriveProjectProcessingState } from "../../../../../lib/job-progress";

export const dynamic = "force-dynamic";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireUser();
    const { id } = await params;

    const project = await db.project.findFirst({
      where: { id, userId: user.id },
      include: {
        source: {
          include: {
            media: {
              orderBy: { createdAt: "desc" },
            },
          },
        },
        jobs: {
          orderBy: { createdAt: "desc" },
          take: 100,
        },
        clips: {
          orderBy: { score: "desc" },
        },
        analyses: {
          orderBy: { createdAt: "desc" },
          take: 3,
        },
      },
    });

    if (!project) {
      return Response.json({ error: "Project not found" }, { status: 404 });
    }

    const state = deriveProjectProcessingState(project as any);
    return Response.json(state, {
      headers: {
        "Cache-Control": "no-store, must-revalidate",
      },
    });
  } catch (error) {
    if (error instanceof Error && error.message === "UNAUTHENTICATED") {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    return Response.json(
      { error: error instanceof Error ? error.message : "Internal error" },
      { status: 500 }
    );
  }
}

