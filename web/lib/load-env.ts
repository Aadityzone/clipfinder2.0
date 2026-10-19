import { loadEnvConfig } from "@next/env";

/**
 * The queue worker runs through `tsx worker.ts`, outside the Next.js runtime,
 * so Next's automatic `.env.local` loading does not apply. Without this the
 * documented `npm --workspace web run worker` command fails immediately with
 * "DATABASE_URL is not configured" even when the file is present.
 *
 * `loadEnvConfig` is the same loader Next uses: already-set environment
 * variables keep precedence, so CI and production configurations are
 * unaffected, and it is safe to call before other imports consume the values.
 */
loadEnvConfig(process.cwd());
