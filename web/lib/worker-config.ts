/**
 * Worker configuration and failure classification.
 *
 * This module is deliberately dependency-free (no database, no `fetch`) so the
 * queue worker, the server-side source-metadata path, and unit tests all share
 * one definition of the timeouts, the AI service URL, and which failures may be
 * retried. Duplicating those constants in tests made the previous "worker config"
 * test assert against its own copy and therefore unable to catch drift.
 */

/** Maximum source seconds processed per transcription chunk. */
export const MAX_SOURCE_CHUNK_SECONDS = 3600;

/**
 * Per-stage timeout ceilings (milliseconds). Each covers the longest realistic
 * processing time including network transfer and model inference.
 */
export const STAGE_TIMEOUT_MS = {
  INGEST: 4 * 60 * 60 * 1000, // 4h: covers 3h yt-dlp download + probe
  TRANSCRIBE: 2 * 60 * 60 * 1000, // 2h: covers 1h audio extraction + Whisper
  ANALYZE: 90 * 60 * 1000, // 90 min: media intelligence + LLM scoring
  RENDER: 30 * 60 * 1000, // 30 min: ffmpeg re-encode
  PROBE: 2 * 60 * 1000, // 2 min: ffprobe
  METADATA: 60 * 1000, // 60s: yt-dlp metadata
  DEFAULT: 30 * 60 * 1000, // 30 min fallback
} as const;

export type StageTimeoutKey = keyof typeof STAGE_TIMEOUT_MS;

/**
 * Local development fallback for the Python AI service. Keep this aligned with
 * the documented Windows development port; CI and deployed environments are
 * expected to set AI_SERVICE_URL explicitly.
 */
export const DEFAULT_AI_SERVICE_URL = "http://127.0.0.1:8001";

/** Minimal environment shape needed to resolve the AI service URL. */
type EnvLike = Readonly<Record<string, string | undefined>>;

/** Resolve the AI service base URL, falling back to the documented dev port. */
export function resolveAiServiceUrl(env: EnvLike = process.env as EnvLike): string {
  const configured = env.AI_SERVICE_URL?.trim();
  return configured ? configured : DEFAULT_AI_SERVICE_URL;
}

/** HTTP statuses in the 4xx range that are worth retrying. */
const RETRYABLE_CLIENT_STATUSES = new Set([408, 425, 429]);

/**
 * Decide whether an AI-service HTTP status may succeed on a later attempt.
 *
 * 5xx, 408 (request timeout), 425 (too early), and 429 (rate limited) are
 * transient. Other 4xx responses mean the request itself is wrong (invalid or
 * unsupported source URL, missing media, failed validation) and will fail
 * identically on every retry.
 */
export function isRetryableAiStatus(status: number): boolean {
  if (!Number.isFinite(status)) return true;
  if (status >= 500) return true;
  if (status >= 400) return RETRYABLE_CLIENT_STATUSES.has(status);
  return false;
}

/** Error raised when the AI service returns a non-2xx response. */
export class AiServiceError extends Error {
  readonly status: number;
  readonly retryable: boolean;
  readonly endpoint: string;

  constructor(endpoint: string, status: number, detail: string) {
    const trimmed = detail.trim();
    super(`AI service ${endpoint} failed with HTTP ${status}${trimmed ? `: ${trimmed}` : ""}`);
    this.name = "AiServiceError";
    this.endpoint = endpoint;
    this.status = status;
    this.retryable = isRetryableAiStatus(status);
  }
}

/**
 * Worker-thrown validation errors that cannot succeed on a later attempt.
 * Matching is intentionally narrow and literal: an unrecognised message stays
 * retryable so genuinely transient faults are never dropped.
 */
const PERMANENT_MESSAGE_PATTERNS: readonly RegExp[] = [
  /^Missing sourceUrl\b/,
  /^Invalid Google Drive file URL\b/,
  /^Source media has no valid duration\./,
  /^Source media missing\b/,
  /^Long-form source media missing\b/,
  /^Clip edit missing\b/,
  /^The confirmed range no longer fits the available source metadata\./,
  /^The prepared media does not cover the confirmed analysis range\./,
  /^AI media path is outside shared MEDIA_STORAGE_ROOT\./,
  /^Publish prerequisites are not ready\b/,
  /^Missing TikTok publish id\b/,
  /^Unknown job type: /,
  /^The source did not provide a valid duration\./,
];

function aiStatusOf(error: unknown): number | null {
  if (typeof error !== "object" || error === null) return null;
  const candidate = error as { name?: unknown; status?: unknown };
  if (candidate.name !== "AiServiceError") return null;
  const status = Number(candidate.status);
  return Number.isFinite(status) ? status : null;
}

/**
 * True when a failure is deterministic and retrying it would only burn another
 * full stage timeout (up to hours) before recording the same error again.
 */
export function isPermanentFailure(error: unknown): boolean {
  const status = aiStatusOf(error);
  if (status !== null) return !isRetryableAiStatus(status);

  const message =
    error instanceof Error ? error.message : typeof error === "string" ? error : "";
  if (!message) return false;
  return PERMANENT_MESSAGE_PATTERNS.some((pattern) => pattern.test(message));
}
