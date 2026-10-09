# Environment
## Web
Create `web/.env.local` with `DATABASE_URL`, `AUTH_SECRET`, `AI_SERVICE_URL`, `AI_SERVICE_SECRET`, and `MEDIA_STORAGE_ROOT`.
## AI
Create `ai/.env` with `AI_SERVICE_SECRET`, `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, and `MEDIA_STORAGE_ROOT`.
Never commit real secrets. The AI service can run locally without a secret. In production, set `AI_SERVICE_SECRET` and `NODE_ENV=production` (or `ENVIRONMENT=production`); authenticated AI endpoints fail closed with HTTP 503 if the secret is missing and compare supplied secrets in constant time. The web and AI service must use the same secret.


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


## Runtime health checks

The web health endpoint at `GET /api/health` checks PostgreSQL connectivity, the Python AI service `/health` endpoint, and write access to the configured local working-storage directory. It returns HTTP 200 only when all three checks pass, otherwise HTTP 503 with dependency statuses only (never credentials or filesystem paths).
