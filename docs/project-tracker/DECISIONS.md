# Engineering Decisions

## D-001 — Evidence over file presence
A module or route existing is not proof of an integrated feature. Mark untested work IMPLEMENTED_UNVERIFIED or PARTIAL until relevant runtime evidence exists.

## D-002 — PostgreSQL jobs are the durable queue source of truth
The current implementation uses Prisma Job rows and worker polling. Do not add a second job store without a demonstrated need.

## D-003 — Keep the web and AI boundary server-to-server
The browser calls Next.js; the Next.js worker calls FastAPI through `AI_SERVICE_URL`. Secrets stay server-side.

## D-004 — Media access must be authorized and provider-aware
URL ingestion depends on provider behavior and access rights. Do not promise every YouTube/Twitch/Kick URL will work; return actionable errors for inaccessible or unsupported sources.

## D-005 — A job is not complete until its real artifact is verified
For analysis, persist transcript and candidates with valid timestamps. For rendering, verify output exists and is readable before marking READY.

## D-006 — Pricing limits need measured processing cost
The proposed 1-hour trial and monthly plan allowances must be enforced server-side. Measure real cost per source hour before advertising a high included-hour cap; protect trials with atomic quota reservations and a hard budget.

## D-007 — Do not pretend agents were launched
Use multiple agents only when actual spawn/assignment capability is available. Otherwise execute sequentially with explicit ownership and handoffs.
