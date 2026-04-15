# BriefAI

Researchers and professionals waste hours manually scanning papers, feeds, and newsletters to stay current in their domain. BriefAI solves this by running an AI agent that ingests research from the web daily, synthesizes it into a concise brief, and delivers it as a voice summary — so users get a knowledgeable peer-style update without the noise.

**PRD:** [output/BriefAI_PRD_20260414_011211.md](output/BriefAI_PRD_20260414_011211.md)

---

## Tech Stack

### Pipeline (Python)
- **Claude API (Anthropic)** — brief generation and onboarding conversation
- **OpenAI** — paper scoring via `text-embedding-3-small` embeddings + cosine similarity
- **ElevenLabs** — text-to-speech for voice delivery (eleven_multilingual_v2)
- **Python 3.13+** with `anthropic`, `fastapi`, `openai`, `feedparser`, `numpy`, `rich`

### Backend (Phase 5)
- **FastAPI** — REST API server (Python), deployed on Railway
- **APScheduler** — per-user daily pipeline scheduling (embedded in FastAPI process)
- **Supabase** — Auth (GoTrue/JWT), PostgreSQL database (pgvector for embeddings), Storage (MP3s)
- **RevenueCat** — iOS subscription management (freemium gating via webhook)

### iOS App (Phase 5)
- **Expo / React Native** — iOS app, built via EAS Build (Windows-compatible, no Xcode needed)
- **expo-audio** — audio playback for brief MP3s (use this, NOT the deprecated expo-av)
- **expo-notifications** — push notifications via Expo Push Service (replaces Pushover)
- **react-native-purchases** — RevenueCat SDK for in-app subscriptions

### Infrastructure
- **GitHub Actions** — single-user daily cron (active until Phase 5e when Railway takes over)
- **Supabase Storage** — hosts brief MP3s at `briefs/{user_id}/brief_{date}.mp3`

---

## Repository Layout

```
BriefAI/
├── planning_agent/     # Phase 1: multi-turn Claude conversation → PRD generation (CLI)
├── research_agent/     # Phase 2: arXiv fetch, OpenAI scoring, paper selection
├── brief_agent/        # Phase 3: Claude brief generation (4-part structure)
├── voice_agent/        # Phase 4a: ElevenLabs TTS (markdown → MP3)
├── delivery_agent/     # Phase 4b/c: Supabase Storage upload, Pushover notification
├── backend/            # Phase 5: FastAPI backend + pipeline runner + scheduler
│   ├── api/            #   REST endpoints (auth, onboarding, settings, briefs, webhooks)
│   └── pipeline/       #   runner.py (multi-user), scheduler.py, onboarding_chat.py
├── briefai-mobile/     # Phase 5: Expo iOS app
├── run_pipeline.py     # Single-user pipeline entry point (used by GitHub Actions)
├── output/
│   ├── profile.json    # Tracked in git — single-user research profile
│   └── seen_papers.json # Tracked in git — deduplication for single-user pipeline
└── .github/workflows/daily_brief.yml  # Cron at 16:00 UTC (12pm ET)
```

---

## Environment

### Single-user pipeline (`.env`)
Required:
- `ANTHROPIC_API_KEY` — console.anthropic.com
- `OPENAI_API_KEY` — platform.openai.com

Optional (Phase 4 delivery):
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`
- `PUSHOVER_API_TOKEN`, `PUSHOVER_USER_KEY`

```bash
pip install -r requirements.txt --no-warn-script-location
python run_pipeline.py
```

### Backend (Phase 5)
Additional env vars needed in Railway (do NOT add `SUPABASE_JWT_SECRET` — JWT auth uses JWKS, not the shared secret):
- `SUPABASE_URL` — your Supabase project URL (e.g. `https://xxx.supabase.co`)
- `SUPABASE_SERVICE_KEY` — service role key from Supabase project settings
- `REVENUECAT_WEBHOOK_SECRET` — from RevenueCat dashboard
- All pipeline keys above (shared)

### Expo App (`.env` / `app.config.js` with `EXPO_PUBLIC_` prefix)
- `EXPO_PUBLIC_SUPABASE_URL` — same as SUPABASE_URL
- `EXPO_PUBLIC_SUPABASE_ANON_KEY` — anon/public key from Supabase
- `EXPO_PUBLIC_API_URL` — Railway backend URL, **no trailing slash** (e.g. `https://briefai.up.railway.app`)

---

## Architectural Decisions

- All Claude prompts live in `**/prompts.py` files — never hardcode prompts elsewhere
- Use `rich.console.Console` for all terminal output in CLI code — never `print()`
- Backend code in `backend/` uses standard logging — no `rich` dependency
- `planning_agent/conversation.py:ConversationManager` is the source of truth for onboarding chat logic — `backend/pipeline/onboarding_chat.py` is an SSE adaptation of it, not a rewrite
- `ArxivFetcher`, `PaperScorer`, `BriefGenerator`, `TextToSpeech` are stateless and reused unchanged by the multi-user backend runner — do not add user-awareness to these classes
- Supabase Storage paths use `{user_id}/brief_{date}.mp3` prefix for per-user isolation
- Backend serves **signed URLs** (1hr TTL) for audio — not public URLs (multi-user security)

## Gotchas

### Python / Pipeline
- Anthropic API allows max 4 `cache_control` blocks per request — always strip existing ones from message history before applying a new cache breakpoint or the API returns a 400
- Always use prompt caching (`cache_control: ephemeral`) on system prompts — skipping it wastes tokens on every turn
- arXiv RSS feeds can lag by up to 24–48h — the fetcher uses a 48-hour recency window, not 24h
- Paper scoring uses OpenAI `text-embedding-3-small` (1536 dims) + cosine similarity — profile must be created with `--setup-profile` before the single-user pipeline can run
- `seen_papers.json` is committed to git so GitHub Actions remembers it across runs — the GitHub Actions workflow commits it back after each run with `[skip ci]` to avoid triggering another run
- APScheduler loses in-memory schedule state on Railway restarts — always rebuild the schedule from the `profiles` table on FastAPI startup

### Supabase Auth (JWT)
- Supabase uses ECC P-256 / ES256 keys by default — **not** HS256. Use `PyJWKClient` pointing at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` to validate tokens. Do not use the shared `SUPABASE_JWT_SECRET` for decoding.
- A `handle_new_user()` trigger must exist in Supabase to auto-create a `public.users` row whenever someone signs up via `auth.users`. Without it, all FK constraints on `user_id` will fail. Run once in the SQL editor:
  ```sql
  create or replace function public.handle_new_user()
  returns trigger as $$
  begin
    insert into public.users (id, email) values (new.id, new.email);
    return new;
  end;
  $$ language plpgsql security definer;
  create or replace trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();
  ```
- Email confirmation is **disabled** in Supabase Auth settings for development — re-enable before App Store submission

### Expo / React Native
- All `npm install` commands require `--legacy-peer-deps` due to React 19.1 vs 19.2 peer conflict introduced by expo-router
- React Native's `fetch` does **not** support SSE response body streaming — onboarding and all other endpoints must return JSON, not `StreamingResponse`
- `expo-secure-store` has a **2048-byte limit per key** — Supabase JWTs exceed this. Use a chunked adapter (see `briefai-mobile/lib/supabase.ts`) that splits large values across multiple keyed entries
- `EXPO_PUBLIC_API_URL` must have **no trailing slash** — `apiFetch` in `lib/api.ts` concatenates paths starting with `/`, so a trailing slash causes double-slash URLs (`//settings`)
- EAS Build requires an Apple Developer account ($99/year) only for App Store submission — development and TestFlight testing work without it

## Code Style

- Python 3.13+
- Max line length: 100 characters
- Error messages lead with the cause: `"ANTHROPIC_API_KEY is not set."` not `"Error: missing key"`
- TypeScript for all Expo/React Native code (`blank-typescript` template)
