"use client";

import ProcessingWorkspace from "../../../components/ProcessingWorkspace";
import type { ProjectProcessingState } from "../../../lib/job-progress";

interface ProcessingExperienceProps {
  projectId: string;
  initialState: ProjectProcessingState | null;
}

export default function ProcessingExperience({
  projectId,
  initialState,
}: ProcessingExperienceProps) {
  return (
    <section className="my-6" aria-label="AI Processing Workspace">
      <ProcessingWorkspace projectId={projectId} initialState={initialState} />
    </section>
  );
}
