# Environment
## Web
Create `web/.env.local` with `DATABASE_URL`, `AUTH_SECRET`, `AI_SERVICE_URL`, `AI_SERVICE_SECRET`, and `MEDIA_STORAGE_ROOT`.
## AI
Create `ai/.env` with `AI_SERVICE_SECRET`, `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, and `MEDIA_STORAGE_ROOT`.
Never commit real secrets. The AI service can run locally without a secret, but production must configure one.
