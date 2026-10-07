# Clip Finder

> **AI finds the moments. You make the calls.**

Clip Finder is a production-grade AI video repurposing platform for creators.

It takes long-form content such as streams, podcasts, gameplay, interviews, and recordings, analyzes the actual media, identifies high-value moments, and turns them into editable short-form clips.

The goal is not to build a prototype that looks complete.

The goal is to build a **real product that works end-to-end**.

---

## Product Vision

A creator should be able to:

1. Create an account.
2. Create a project.
3. Upload a video or connect a supported source.
4. Configure how the video should be analyzed.
5. Let Clip Finder process the real media.
6. Receive ranked clip candidates.
7. Open any candidate in the editor.
8. Edit the clip manually.
9. Reframe it for short-form video.
10. Generate/edit captions.
11. Render the final video.
12. Preview the result.
13. Export or publish it.
14. Schedule future posts.
15. View performance analytics.

For long-form content, Clip Finder should also support:

- Transcript editing
- Stories/highlights
- Titles
- Descriptions
- Chapters
- Thumbnail workflows
- Long-form rendering
- YouTube publishing

---

# Core Principle

## Real implementation only.

Clip Finder must never pretend something has happened when it has not.

### Never build:

- Fake AI scores
- Hardcoded clip results
- Fake processing progress
- Fake completed renders
- Fake publishing
- Fake analytics
- Fake integrations
- Placeholder buttons that claim to work
- Demo data presented as real user data
- AI results generated without analyzing the actual source

If a feature is not implemented yet, the UI must represent that honestly.

---

# Architecture

```text
clipfinder/
│
├── web/                  # Next.js application
│   ├── App Router
│   ├── TypeScript
│   ├── Tailwind CSS
│   └── shadcn/ui
│
├── ai/                   # Python AI/media service
│   ├── FastAPI
│   ├── transcription
│   ├── media analysis
│   ├── candidate generation
│   ├── ranking
│   ├── vision/audio processing
│   └── rendering/media intelligence
│
├── prisma/               # Database schema
│
├── db/                   # Database-related infrastructure
│
├── docs/                 # Architecture and product documentation
│
└── README.md
```

### Responsibility boundary

The web application does **not** directly run AI models.

```text
Browser
   ↓
Next.js
   ↓
Python FastAPI AI Service
   ↓
AI / Media Processing
   ↓
PostgreSQL / Storage
```

All AI and heavy media-processing logic belongs in the Python service.

---

# AI Pipeline

The fundamental Clip Finder pipeline is:

```text
REAL LONG VIDEO
       ↓
MEDIA INGESTION
       ↓
AUDIO / VIDEO EXTRACTION
       ↓
TRANSCRIPTION
       ↓
TIMESTAMPED SEGMENTS
       ↓
AUDIO + VISUAL + LANGUAGE ANALYSIS
       ↓
CANDIDATE MOMENTS
       ↓
AI SCORING
       ↓
DEDUPLICATION
       ↓
RANKED CLIPS
       ↓
EDITOR
       ↓
RENDER
       ↓
EXPORT / PUBLISH
```

The pipeline must operate on the user's actual media.

---

# Media Intelligence

Clip Finder should not depend exclusively on transcripts.

The system should progressively understand:

### Audio

- Speech
- Volume/energy
- Silence
- Excitement
- Laughter
- Reactions
- Audio peaks
- Speaker changes

### Language

- Transcript
- Semantic meaning
- Context
- Punchlines
- Stories
- Questions
- Quotable statements
- Emotional moments
- Unexpected statements

### Video

- Scene changes
- Faces
- Speakers
- Reactions
- Gameplay/action
- Visual events
- Composition
- Subject position

The architecture should allow additional analysis models to be added without rewriting the entire application.

---

# Clip Detection

Supported clip categories should include:

- AI Detect
- Reaction
- Funny
- Fail / Win
- Wholesome
- Drama
- Quotable
- Unexpected

Users may select multiple categories.

Users can also provide custom instructions.

Custom instructions must actually influence analysis and ranking.

They must not merely be stored and ignored.

---

# Job System

Long-running operations must be represented as durable jobs.

Supported states:

```text
QUEUED
DOWNLOADING
INGESTING
TRANSCRIBING
ANALYZING
EDITING
RENDERING
READY
FAILED
RETRYING
CANCELLED
```

Jobs must support:

- Progress
- Errors
- Retry
- Cancellation
- Ownership
- Durable state
- Worker recovery

The UI must reflect the actual backend job state.

---

# Video Editor

The editor is a real editing environment, not a visual mockup.

Required functionality includes:

- Video playback
- Timeline
- Waveform
- Playhead
- Split
- Trim in
- Trim out
- Delete
- Manual clip creation
- Multiple segments
- Undo
- Redo
- Keyboard shortcuts
- Timestamp-accurate editing
- Autosave
- Debounced persistence
- Aspect ratio selection
- AI highlight → editor workflow

Supported short-form aspect ratios should include:

```text
9:16
16:9
1:1
```

Editor state must persist.

---

# Rendering

Final renders must be produced from the actual source media.

Rendering should support:

- Trimmed segments
- Aspect ratio
- Cropping/reframing
- Captions
- Audio processing
- H.264/AAC output
- MP4
- Fast-start streaming compatibility

Rendering must happen asynchronously through the job system.

A render cannot be marked `READY` until the actual output exists and has been validated.

---

# Captions

Caption workflows should support:

- Transcript-derived captions
- Timestamp accuracy
- SRT/VTT generation
- Caption styling
- Burned-in captions
- Editable caption timing where appropriate

---

# Reframing

Short-form reframing should eventually support intelligent subject-aware framing.

The system should be able to track the relevant subject rather than simply performing a blind center crop.

Possible signals include:

- Face detection
- Person detection
- Speaker location
- Action location
- Scene composition

The architecture should keep this capability modular.

---

# Search

Users should be able to search their analyzed content.

Example:

```text
"find the moment where he talks about quitting"
```

Search should operate against real transcript/analysis data.

As the system evolves, semantic/vector search can be added without replacing the basic search layer.

---

# Sources

The product should support multiple ingestion methods.

Initial architecture should allow:

- Upload
- Twitch
- Kick
- Google Drive
- Supported URLs

Source-specific integrations must be implemented as real providers.

---

# Storage

The system should support:

- Local development storage
- S3-compatible storage
- Cloud object storage such as R2/S3

Media files should not be unnecessarily loaded into application memory.

Large media must be streamed or processed from storage paths/URLs.

---

# Database

PostgreSQL is the primary database.

Prisma is used as the ORM.

The database should persist:

- Users
- Subscriptions
- Usage
- Sources
- Media assets
- Projects
- Jobs
- Analyses
- Transcripts
- Transcript segments
- Transcript words
- Highlights
- Clips
- Clip edits
- Caption tracks
- Renders
- Exports
- Social connections
- Scheduled posts
- Analytics
- Favorites
- Templates
- Notifications
- Creator events

Database models must represent actual product state.

---

# Authentication

Authentication must support:

- Signup
- Login
- Logout
- Secure password storage
- Sessions
- User ownership
- Protected resources

A user must never be able to access another user's:

- Projects
- Media
- Clips
- Renders
- Exports
- Jobs
- Social connections
- Analytics

Security-sensitive credentials must come from environment variables.

---

# Application Navigation

The application should eventually include:

```text
Dashboard
Usage
Analytics
Exports
Calendar
Favorites
Templates
Profile
Settings
```

Secondary areas:

```text
Community
Referrals
Upgrade
Billing
```

Navigation should be implemented progressively as the corresponding functionality becomes real.

---

# Dashboard

The dashboard should allow creators to:

- Create projects
- Upload media
- Connect sources
- Configure analysis
- View processing status
- View discovered clips
- Continue editing
- Access exports

Analysis configuration should include:

- Source
- Analysis mode
- Clip type
- Custom instructions
- Processing timeframe
- Output language
- Rights confirmation

---

# Publishing

Publishing architecture should eventually support:

- YouTube
- TikTok
- Other supported social platforms

Publishing must use real OAuth/API integrations.

Tokens must be securely stored.

The UI must never claim that a post was published unless the external platform confirms success.

---

# Scheduling

Creators should be able to:

- Schedule posts
- View scheduled posts
- Cancel scheduled posts
- Track publishing state

Calendar functionality must be backed by actual scheduled-post data.

---

# Analytics

Analytics should eventually include:

- Views
- Likes
- Comments
- Shares
- Watch time
- Engagement
- Platform
- Post
- Date

Analytics must come from real platform data or clearly identified internal events.

---

# Billing and Usage

The application should eventually support:

- Subscription plans
- Usage limits
- Usage tracking
- Billing
- Upgrade/downgrade
- Subscription state

Billing providers must only be integrated when their required credentials are available.

---

# Long-Form Mode

Long-form workflows should support:

```text
Long Video
    ↓
Analysis
    ↓
Stories / Highlights
    ↓
Transcript Editing
    ↓
Title
    ↓
Description
    ↓
Thumbnail
    ↓
Chapters
    ↓
Render
    ↓
YouTube
```

---

# Engineering Rules

## 1. Inspect before implementing

Before adding a subsystem:

- Check whether it already exists.
- Reuse working infrastructure.
- Avoid duplicate implementations.
- Preserve existing behavior unless intentionally changing it.

## 2. Current documentation

Use current official documentation for:

- Next.js
- React
- Tailwind
- FastAPI
- Prisma
- FFmpeg
- relevant APIs and SDKs

Do not rely on outdated syntax when current documentation differs.

## 3. No unnecessary dependencies

Do not add a dependency simply because it is convenient.

Every major dependency should solve a real product requirement.

## 4. Keep boundaries clean

Web application:

```text
UI
API
Authentication
Database orchestration
Project management
```

AI service:

```text
AI
Transcription
Media intelligence
Analysis
Ranking
Rendering
```

Workers:

```text
Long-running jobs
Retries
Progress
Processing
```

## 5. Test real behavior

Tests should validate real business behavior.

Do not create tests that only make mocked/demo implementations appear complete.

---

# Environment Variables

Secrets must never be committed.

Expected configuration will include variables such as:

```text
DATABASE_URL
AUTH_SECRET
AI_SERVICE_URL
AI_SERVICE_SECRET
MEDIA_STORAGE_ROOT
WHISPER_MODEL
WHISPER_DEVICE
WHISPER_COMPUTE_TYPE
```

Additional provider credentials will be added only when those integrations are implemented.

See:

```text
docs/ENVIRONMENT.md
```

for the authoritative environment configuration.

---

# Development

The project contains two primary services.

### Web

```bash
cd web
npm install
npm run dev
```

### AI

From the repository root:

```bash
python -m uvicorn ai.main:app --host 0.0.0.0 --port 8000 --reload
```

### Worker

```bash
cd web
npm run worker
```

Exact scripts may evolve as the architecture grows.

---

# Definition of Done

A feature is not considered complete because:

- The UI exists.
- A button exists.
- A mock response appears.
- A test is written.
- A loading animation exists.

A feature is complete when the actual user journey works.

For example:

```text
Upload video
      ↓
File actually stored
      ↓
Media actually inspected
      ↓
Job actually created
      ↓
Transcription actually runs
      ↓
Analysis actually runs
      ↓
Real clips actually generated
      ↓
Clip opens in editor
      ↓
User edits it
      ↓
Render actually runs
      ↓
Real MP4 exists
      ↓
User can preview/export it
```

That is the standard for Clip Finder.

---

# Project Philosophy

Clip Finder is being built incrementally.

We do **not** need every feature on day one.

We do need every implemented feature to be real.

Build the foundation correctly.

Then expand:

```text
Foundation
    ↓
Ingestion
    ↓
AI
    ↓
Clips
    ↓
Editor
    ↓
Rendering
    ↓
Captions / Reframe
    ↓
Search
    ↓
Publishing
    ↓
Analytics
    ↓
Billing
    ↓
Advanced AI
```

The product should become more powerful over time without sacrificing correctness.

---

## Status

🚧 **Active development**

This repository is intentionally being built from a clean foundation.

The source of truth is the code, database schema, tests, and documentation in this repository.