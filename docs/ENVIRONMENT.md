# Environment
## Web
Create `web/.env.local` with `DATABASE_URL`, `AUTH_SECRET`, `AI_SERVICE_URL`, `AI_SERVICE_SECRET`, and `MEDIA_STORAGE_ROOT`.
## AI
Create `ai/.env` with `AI_SERVICE_SECRET`, `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, and `MEDIA_STORAGE_ROOT`.
Never commit real secrets. The AI service can run locally without a secret, but production must configure one.


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