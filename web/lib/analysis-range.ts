export const MIN_ANALYSIS_MS = 60 * 60 * 1000;
export const DEFAULT_FREE_MAX_MS = MIN_ANALYSIS_MS;
export const DEFAULT_PRO_MAX_MS = 3 * MIN_ANALYSIS_MS;
const MAX_CONFIGURED_MS = 24 * 60 * 60 * 1000;

export type SubscriptionSnapshot = { plan?: string | null; status?: string | null } | null;
export type AnalysisEntitlement = {
  plan: "free" | "pro";
  maxDurationMs: number;
  canSelectCustomDuration: boolean;
};

function configuredMs(key: string, fallback: number): number {
  const raw = process.env[key];
  if (raw === undefined || raw.trim() === "") return fallback;
  const hours = Number(raw);
  if (!Number.isFinite(hours) || hours < 0 || (hours > 0 && hours < 1)) return fallback;
  return Math.min(MAX_CONFIGURED_MS, Math.round(hours * 60 * 60 * 1000));
}

export function analysisEntitlement(subscription: SubscriptionSnapshot): AnalysisEntitlement {
  const isActivePro = subscription?.plan?.toLowerCase() === "pro" && subscription.status?.toLowerCase() === "active";
  const plan = isActivePro ? "pro" : "free";
  const maxDurationMs = configuredMs(isActivePro ? "ANALYSIS_RANGE_PRO_MAX_HOURS" : "ANALYSIS_RANGE_FREE_MAX_HOURS", isActivePro ? DEFAULT_PRO_MAX_MS : DEFAULT_FREE_MAX_MS);
  return { plan, maxDurationMs, canSelectCustomDuration: isActivePro };
}

export type ValidatedAnalysisRange = { startMs: number; endMs: number; durationMs: number };

export function validateAnalysisRange(input: {
  startSeconds: unknown;
  endSeconds: unknown;
  sourceDurationSeconds: unknown;
  entitlement: AnalysisEntitlement;
}): ValidatedAnalysisRange {
  const start = Number(input.startSeconds);
  const end = Number(input.endSeconds);
  const sourceDuration = Number(input.sourceDurationSeconds);
  if (![start, end, sourceDuration].every(Number.isFinite) || sourceDuration <= 0) {
    throw new Error("Source metadata is missing a valid duration or the selected range is invalid.");
  }
  const startMs = Math.round(start * 1000);
  const endMs = Math.round(end * 1000);
  const sourceDurationMs = Math.round(sourceDuration * 1000);
  const durationMs = endMs - startMs;
  if (startMs < 0 || durationMs <= 0) throw new Error("Choose a non-negative start and a positive analysis duration.");
  if (endMs > sourceDurationMs) throw new Error("The selected range ends after the source video.");
  if (durationMs > input.entitlement.maxDurationMs) {
    throw new Error(`Your ${input.entitlement.plan === "pro" ? "Pro" : "Free"} plan allows up to ${input.entitlement.maxDurationMs / MIN_ANALYSIS_MS} hour${input.entitlement.maxDurationMs === MIN_ANALYSIS_MS ? "" : "s"} per analysis.`);
  }
  if (sourceDurationMs >= MIN_ANALYSIS_MS && durationMs < MIN_ANALYSIS_MS) {
    throw new Error("Analysis ranges must be at least one hour. Sources shorter than one hour can be analyzed in full.");
  }
  if (sourceDurationMs < MIN_ANALYSIS_MS && (startMs !== 0 || endMs !== sourceDurationMs)) {
    throw new Error("Sources shorter than one hour must be analyzed in full.");
  }
  const maxAllowedDurationMs = Math.min(input.entitlement.maxDurationMs, sourceDurationMs);
  if (!input.entitlement.canSelectCustomDuration && durationMs !== MIN_ANALYSIS_MS && durationMs !== maxAllowedDurationMs) {
    throw new Error("Custom analysis durations are available on Pro. Free accounts can analyze one hour or the full source when it is shorter.");
  }
  return { startMs, endMs, durationMs };
}

export type RangeChunk = { localStartSeconds: number; localEndSeconds: number; sourceStartSeconds: number; sourceEndSeconds: number; nextCursorSeconds: number; hasNext: boolean };
export function nextRangeChunk(input: {
  sourceStartSeconds: number;
  sourceEndSeconds: number;
  mediaOffsetSeconds: number;
  mediaDurationSeconds: number;
  cursorSeconds?: number;
  chunkLimitSeconds?: number;
}): RangeChunk {
  const values = [input.sourceStartSeconds, input.sourceEndSeconds, input.mediaOffsetSeconds, input.mediaDurationSeconds, input.cursorSeconds ?? input.sourceStartSeconds - input.mediaOffsetSeconds, input.chunkLimitSeconds ?? 3600];
  if (!values.every(Number.isFinite)) throw new Error("Range chunk metadata must be finite.");
  const [sourceStartMs, sourceEndMs, offsetMs, mediaDurationMs, cursorMs, chunkLimitMs] = values.map((value) => Math.round(value * 1000));
  if (sourceEndMs - offsetMs > mediaDurationMs + 50) throw new Error("The stored media does not cover the confirmed source range.");
  const localStartMs = Math.max(sourceStartMs - offsetMs, cursorMs);
  const localEndMs = Math.min(sourceEndMs - offsetMs, mediaDurationMs, localStartMs + chunkLimitMs);
  if (sourceEndMs <= sourceStartMs || localStartMs < 0 || localEndMs <= localStartMs) throw new Error("Selected range does not fit the stored media interval.");
  return {
    localStartSeconds: localStartMs / 1000,
    localEndSeconds: localEndMs / 1000,
    sourceStartSeconds: (offsetMs + localStartMs) / 1000,
    sourceEndSeconds: (offsetMs + localEndMs) / 1000,
    nextCursorSeconds: localEndMs / 1000,
    hasNext: localEndMs < sourceEndMs - offsetMs - 50,
  };
}

export function toMediaLocalSegments<T extends { start: number; end: number }>(segments: T[], mediaOffsetSeconds: number) {
  const offsetMs = Math.round(mediaOffsetSeconds * 1000);
  return segments.map((segment) => ({ ...segment, start: (Math.round(segment.start * 1000) - offsetMs) / 1000, end: (Math.round(segment.end * 1000) - offsetMs) / 1000 }));
}

export function toSourceTimestamps<T extends { start: number; end: number }>(items: T[], mediaOffsetSeconds: number) {
  const offsetMs = Math.round(mediaOffsetSeconds * 1000);
  return items.map((item) => ({ ...item, start: (Math.round(item.start * 1000) + offsetMs) / 1000, end: (Math.round(item.end * 1000) + offsetMs) / 1000 }));
}
