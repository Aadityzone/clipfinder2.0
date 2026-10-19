# Environment
## Web
Create `web/.env.local` with `DATABASE_URL`, `AUTH_SECRET`, `AI_SERVICE_URL`, `AI_SERVICE_SECRET`, and `MEDIA_STORAGE_ROOT`. For local development, use `MEDIA_STORAGE_ROOT=../storage` in this file; Next.js and the workspace worker run from `web/`, so this resolves to the repository's `storage/` directory.
## AI
Create `ai/.env` with `AI_SERVICE_SECRET`, `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, and `MEDIA_STORAGE_ROOT`. When starting Uvicorn from the repository root, use `MEDIA_STORAGE_ROOT=./storage` in this file so it resolves to the same repository `storage/` directory.
Start the AI service from the repository root with `uvicorn ai.main:app --host 127.0.0.1 --port 8000 --env-file ai/.env`; without `--env-file`, Uvicorn does not automatically load `ai/.env`. For local web commands, create `web/.env.local`; `prisma.config.ts` explicitly loads that file for Prisma CLI commands. Never commit real secrets. The AI service can run locally without a secret. In production, set `AI_SERVICE_SECRET` and `NODE_ENV=production` (or `ENVIRONMENT=production`); authenticated AI endpoints fail closed with HTTP 503 if the secret is missing and compare supplied secrets in constant time. The web and AI service must use the same secret.


## Publishing integrations

Set these only when enabling real social publishing:

```env
APP_URL=http://localhost:3000
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
```

YouTube uses server-side OAuth with refresh tokens; TikTok uses Login Kit web OAuth and the Content Posting API. Provider credentials and tokens must remain server-side.
## Object storage
Set `STORAGE_PROVIDER=local` for development. For S3/R2-compatible storage, set `STORAGE_PROVIDER=s3`, `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY`. The worker keeps a local working copy for FFmpeg and mirrors durable media to object storage.

## Optional semantic rescoring
`OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` enable an optional LLM ranking pass after transcript/vision/audio candidate generation. Without the key, the deterministic multimodal scorer remains the ranking engine.

## Billing
Stripe billing is implemented but remains inactive until `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, and `STRIPE_WEBHOOK_SECRET` are configured. Checkout, customer portal, and subscription webhooks then become real Stripe-backed flows.

## Analysis range policy
`POST /api/sources/metadata` reads source details without creating a project or job. The range selector then requires an explicit confirmation before `POST /api/projects` creates the ingestion job. The server re-fetches metadata, checks the authenticated account's current subscription, and validates the selected boundaries before persisting them in the job payload.

The current policy uses the existing plan states and does not change Stripe pricing: an active `pro` subscription may analyze up to three hours per project by default; Free may analyze up to one hour. Set `ANALYSIS_RANGE_PRO_MAX_HOURS` and `ANALYSIS_RANGE_FREE_MAX_HOURS` on the web server to configure those per-job maxima (valid values are 0 or 1–24 hours; invalid values use defaults). Both policies require at least one hour when the source is at least an hour long. A shorter source is the explicit exception: its full duration can be analyzed. Free may choose a one-hour or maximum-duration preset and adjust the start; Pro may choose custom durations. No monthly minute quota is currently defined or enforced in this repository; `Usage.minutesAnalyzed` remains metering only.

For YouTube, Twitch, and Kick URLs the AI service requests a provider section with yt-dlp `--download-sections` and FFmpeg as the downloader. This fails the job without falling back to a full-source download. Section support and actual transferred bytes depend on the provider extractor and available media format; a provider-backed end-to-end transfer has not been verified in this environment. Google Drive currently exposes duration metadata through its authenticated API but downloads the full file; the worker seeks and processes only the selected interval from that local copy. Do not claim bandwidth savings for Drive. In both paths the job retains original source boundaries, and worker chunks translate between media-local and source timestamps.


## Runtime health checks

The web health endpoint at `GET /api/health` checks PostgreSQL connectivity, the Python AI service `/health` endpoint, and write access to the configured local working-storage directory. It returns HTTP 200 only when all three checks pass, otherwise HTTP 503 with dependency statuses only (never credentials or filesystem paths).

## Local development commands

Run these from the repository root in separate terminals:

```powershell
# Apply the current schema to your configured development database
npx prisma db push --schema prisma/schema.prisma
npm run prisma:generate

# Terminal 1: AI service (loads ai/.env)
uvicorn ai.main:app --host 127.0.0.1 --port 8000 --env-file ai/.env

# Terminal 2: website
npm run dev

# Terminal 3: durable background worker
npm --workspace web run worker
```

Keep the web and AI `AI_SERVICE_SECRET` values identical. The web and AI processes must share the same media directory when local storage is selected. Do not paste or commit either environment file.
