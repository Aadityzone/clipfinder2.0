import { db } from "./db";

type FeatureMap = Record<string, number>;

const FEATURE_KEYS = [
  "face_presence",
  "scene_changes",
  "audio_energy",
  "visual_change",
  "motion",
  "gameplay",
  "action_cues",
  "semantic_score",
  "hook_density",
  "conversation_turns",
] as const;

function number(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
function clamp(value: number, min = 0, max = 1): number {
  return Math.max(min, Math.min(max, value));
}
function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function vector(raw: unknown): FeatureMap {
  const f = object(raw);
  const hooks = object(f.hookSignals);
  const conversation = object(f.conversation);
  const labels = Array.isArray(f.onScreenActionLabels) ? f.onScreenActionLabels : [];
  const semantic = f.visualSemanticScore;
  return {
    face_presence: clamp(number(f.faceHits) / 6),
    scene_changes: clamp(number(f.sceneHits) / 5),
    audio_energy: clamp(number(f.audioEnergy)),
    visual_change: clamp(number(f.visualChange)),
    motion: clamp(number(f.motion)),
    gameplay: clamp(number(f.gameplayLikeRatio)),
    action_cues: clamp(labels.length / 3),
    semantic_score: typeof semantic === "number" && Number.isFinite(semantic)
      ? clamp((semantic - 50) / 50)
      : 0,
    hook_density: clamp((number(hooks.questions) + number(hooks.exclamations)) / 5),
    conversation_turns: clamp(number(conversation.styleTransitions) / 4),
  };
}

export type FeedbackClip = {
  status: string;
  highlight?: { features?: unknown } | null;
};

export type CreatorFeedbackProfile = {
  active: boolean;
  acceptedSamples: number;
  rejectedSamples: number;
  weights: Record<string, number>;
  minSamplesPerClass: number;
};

export function buildCreatorFeedbackProfile(clips: FeedbackClip[]): CreatorFeedbackProfile {
  const accepted = clips.filter((clip) => clip.status === "SELECTED" && clip.highlight?.features);
  const rejected = clips.filter((clip) => clip.status === "REJECTED" && clip.highlight?.features);
  const minSamplesPerClass = 3;
  if (accepted.length < minSamplesPerClass || rejected.length < minSamplesPerClass) {
    return {
      active: false,
      acceptedSamples: accepted.length,
      rejectedSamples: rejected.length,
      weights: {},
      minSamplesPerClass,
    };
  }

  const acceptedVectors = accepted.map((clip) => vector(clip.highlight?.features));
  const rejectedVectors = rejected.map((clip) => vector(clip.highlight?.features));
  const confidence = Math.min(1, Math.min(accepted.length, rejected.length) / 5);
  const weights: Record<string, number> = {};

  for (const key of FEATURE_KEYS) {
    const mean = (rows: FeatureMap[]) =>
      rows.reduce((sum, row) => sum + row[key], 0) / rows.length;
    const difference = mean(acceptedVectors) - mean(rejectedVectors);
    const weight = Math.max(-1, Math.min(1, difference * 2.5 * confidence));
    if (Math.abs(weight) >= 0.08) weights[key] = Number(weight.toFixed(4));
  }

  return {
    active: Object.keys(weights).length > 0,
    acceptedSamples: accepted.length,
    rejectedSamples: rejected.length,
    weights,
    minSamplesPerClass,
  };
}

/**
 * Rebuild a profile from the latest explicit decision for each clip.
 * Decision events survive later edit/render status changes, so editing an
 * accepted clip does not erase the creator's original feedback.
 */
export async function loadCreatorFeedbackProfile(userId: string): Promise<CreatorFeedbackProfile> {
  const events = await db.creatorEvent.findMany({
    where: { userId, event: { in: ["ACCEPT", "REJECT"] } },
    orderBy: { createdAt: "desc" },
    take: 1000,
    select: { event: true, metadata: true },
  });

  const latestDecision = new Map<string, "ACCEPT" | "REJECT">();
  for (const event of events) {
    const metadata = object(event.metadata);
    const clipId = typeof metadata.clipId === "string" ? metadata.clipId : "";
    if (!clipId || latestDecision.has(clipId)) continue;
    latestDecision.set(clipId, event.event === "ACCEPT" ? "ACCEPT" : "REJECT");
  }

  if (latestDecision.size === 0) return buildCreatorFeedbackProfile([]);

  const clips = await db.clip.findMany({
    where: {
      id: { in: [...latestDecision.keys()] },
      project: { userId },
      highlightId: { not: null },
    },
    select: { id: true, highlight: { select: { features: true } } },
  });

  return buildCreatorFeedbackProfile(clips.map((clip) => ({
    status: latestDecision.get(clip.id) === "ACCEPT" ? "SELECTED" : "REJECTED",
    highlight: clip.highlight,
  })));
}
