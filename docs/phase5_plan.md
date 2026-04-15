# Phase 5: Multi-User iOS App, Backend API & Freemium

## Context

Phases 1–4 are complete and working: arXiv ingestion, Claude brief generation, ElevenLabs TTS,
Supabase Storage, Pushover notifications, and GitHub Actions daily cron. Phase 5 turns BriefAI
into a multi-user product on the App Store with a freemium model.

**User decisions:**
- Platform: iOS only
- Onboarding: chat-based (conversational profile setup) + settings screen for tweaks
- Model: Freemium — 3 briefs/week free, daily + custom settings on paid plan
- Dev machine: Windows — must use Expo + EAS Build (no Xcode available)

---

## New Architecture

```
iOS App (Expo/React Native)
    ↕ REST API (JWT from Supabase Auth)
FastAPI Backend (Railway)
    ├── Onboarding chat API (adapted ConversationManager)
    ├── Settings API
    ├── Brief history API
    ├── APScheduler — daily pipeline per user
    └── RevenueCat webhook
    ↕
Supabase
    ├── Auth (GoTrue — email/password + JWT)
    ├── Database (profiles, seen_papers, briefs, subscriptions, onboarding_sessions)
    └── Storage (briefs/{user_id}/brief_{date}.mp3 — signed URLs)
    ↕
External: arXiv RSS, OpenAI, Anthropic, ElevenLabs, RevenueCat (App Store subscriptions),
          Expo Push Notification Service (replaces Pushover)
```

---

## Supabase Schema (run in Supabase SQL editor)

```sql
create extension if not exists vector;

create table public.users (
  id              uuid primary key references auth.users(id) on delete cascade,
  email           text not null,
  display_name    text,
  expo_push_token text,
  tier            text not null default 'free' check (tier in ('free', 'paid')),
  created_at      timestamptz not null default now()
);

create table public.profiles (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null unique references public.users(id) on delete cascade,
  focus_text          text not null,
  embedding           vector(1536) not null,
  arxiv_categories    text[] not null default array['cs.LG', 'cs.AR', 'eess.SP'],
  relevance_threshold float not null default 0.72,
  elevenlabs_voice_id text not null default 'JBFqnCBsd6RMkjVDRZzb',
  delivery_hour_utc   int not null default 16 check (delivery_hour_utc between 0 and 23),
  created_at          timestamptz not null default now()
);

create table public.seen_papers (
  id        bigserial primary key,
  user_id   uuid not null references public.users(id) on delete cascade,
  arxiv_id  text not null,
  seen_at   timestamptz not null default now(),
  unique (user_id, arxiv_id)
);
create index idx_seen_papers_user on public.seen_papers(user_id, arxiv_id);

create table public.briefs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.users(id) on delete cascade,
  arxiv_id        text not null,
  title           text not null,
  authors         text[] not null default '{}',
  relevance_score float not null,
  brief_text      text not null,
  audio_url       text,
  storage_path    text,
  generated_at    timestamptz not null default now()
);
create index idx_briefs_user on public.briefs(user_id, generated_at desc);

create table public.subscriptions (
  id                     uuid primary key default gen_random_uuid(),
  user_id                uuid not null unique references public.users(id) on delete cascade,
  revenuecat_app_user_id text not null,
  product_id             text,
  status                 text not null default 'inactive'
                         check (status in ('active', 'inactive', 'trial', 'grace_period')),
  expires_at             timestamptz,
  updated_at             timestamptz not null default now()
);

create table public.onboarding_sessions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.users(id) on delete cascade,
  messages   jsonb not null default '[]',
  status     text not null default 'in_progress'
             check (status in ('in_progress', 'complete')),
  created_at timestamptz not null default now()
);

-- Enable RLS on all tables (each table: auth.uid() = user_id)
alter table public.users enable row level security;
alter table public.profiles enable row level security;
alter table public.seen_papers enable row level security;
alter table public.briefs enable row level security;
alter table public.subscriptions enable row level security;
alter table public.onboarding_sessions enable row level security;
```

---

## Backend File Structure

```
backend/
├── main.py                     # FastAPI app + APScheduler lifespan
├── config.py                   # pydantic-settings, all env vars
├── dependencies.py             # get_current_user (validates Supabase JWT)
├── models.py                   # Pydantic request/response models
├── api/
│   ├── auth.py                 # /auth/me, /auth/push-token
│   ├── onboarding.py           # /onboarding/session CRUD + message stream
│   ├── settings.py             # GET/PATCH /settings
│   ├── briefs.py               # GET /briefs, /briefs/latest, /briefs/{id}, /briefs/trigger
│   └── webhooks.py             # POST /webhooks/revenuecat
└── pipeline/
    ├── runner.py               # run_pipeline_for_user(user_id) — core pipeline logic
    ├── scheduler.py            # APScheduler setup, rebuild_schedule()
    └── onboarding_chat.py      # Adapted ConversationManager (SSE, no rich/CLI)
```

---

## FastAPI Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/me` | JWT | Current user info + tier |
| PUT | `/auth/push-token` | JWT | Register Expo push token |
| POST | `/onboarding/session` | JWT | Create new chat session |
| POST | `/onboarding/session/{id}/message` | JWT | Send message → SSE stream Claude reply |
| POST | `/onboarding/session/{id}/complete` | JWT | Extract focus, embed, write to profiles |
| GET | `/onboarding/session/{id}` | JWT | Get message history |
| GET | `/settings` | JWT | Get current profile settings |
| PATCH | `/settings` | JWT | Update categories/threshold/voice/delivery_hour (paid gates) |
| GET | `/briefs` | JWT | Paginated brief history |
| GET | `/briefs/latest` | JWT | Most recent brief |
| GET | `/briefs/{id}` | JWT | Full brief + signed audio URL |
| POST | `/briefs/trigger` | JWT | Manual pipeline trigger (paid only) |
| GET | `/subscriptions/status` | JWT | Tier + expiry |
| POST | `/webhooks/revenuecat` | Secret | Update tier on purchase/expiry |

---

## Pipeline Refactor (`backend/pipeline/runner.py`)

Adapts `run_pipeline.py` to accept `user_id` instead of loading from `.env`:

1. Load profile + settings from `public.profiles` (replaces `ResearchConfig` + `profile.json`)
2. Load seen arxiv IDs from `public.seen_papers WHERE user_id = $1` (replaces `seen_papers.json`)
3. **Free tier gate:** count briefs this week — if `>= 3` and `tier == 'free'`, skip
4. `ArxivFetcher`, `PaperScorer`, `PaperSelector` — **zero changes** (pass DB values in)
5. `BriefGenerator` — **zero changes**
6. `TextToSpeech` — **zero changes**
7. Upload to `briefs/{user_id}/brief_{date}.mp3` (path prefix changes from flat to per-user)
8. Use **signed URL** (1hr TTL) instead of public URL
9. Insert into `public.briefs`
10. Insert into `public.seen_papers`
11. Send Expo push via `https://exp.host/--/api/v2/push/send` (replaces Pushover)

**Scheduling:** APScheduler reads `delivery_hour_utc` per user from `profiles` on startup,
adds one `CronTrigger(hour=delivery_hour_utc)` job per user keyed by `user_id`.
Rebuild schedule on `PATCH /settings` if `delivery_hour_utc` changes.

---

## Onboarding Chat Adaptation (`backend/pipeline/onboarding_chat.py`)

Source: `planning_agent/conversation.py:ConversationManager`

Changes:
- Remove `rich` — no terminal output
- Replace `Prompt.ask()` — user input comes from HTTP request body
- `_stream_response()` → `async _stream_response_sse() -> AsyncGenerator[str, None]` (yields SSE)
- Persist `self.messages` to `onboarding_sessions.messages` (jsonb) after every turn
- `_apply_cache_breakpoint()` and `extract_requirements_summary()` — **zero changes**
- On `complete`: call `ResearchProfile.create(focus_text, openai_client)` (unchanged), write
  embedding to `public.profiles`

---

## iOS App — Expo/React Native

**Setup (Windows):**
```bash
npx create-expo-app briefai-mobile --template blank-typescript
npx expo install expo-router expo-secure-store expo-av expo-notifications
npm install @supabase/supabase-js react-native-purchases @tanstack/react-query
eas build:configure
```

**Screens:**
```
(auth)/
  welcome.tsx          — Logo + "Get Started" / "Sign In"
  signup.tsx           — Email/password → Supabase Auth
  login.tsx            — Email/password → Supabase Auth
  onboarding.tsx       — Chat bubbles, SSE streaming, REQUIREMENTS_COMPLETE triggers next
  onboarding-settings.tsx — Category chips + delivery time picker (paid locked)

(tabs)/
  today.tsx            — Audio player (expo-av) + brief text
  history.tsx          — Paginated brief list → detail view
  settings.tsx         — Focus text, categories (locked), upgrade CTA
```

**Auth flow:** `_layout.tsx` checks session → no session: `/(auth)/welcome` → session + no profile:
`/(auth)/onboarding` → session + profile: `/(tabs)/today`. JWT stored in `expo-secure-store`.

**Subscriptions:** `react-native-purchases` (RevenueCat). Paywall opened from `settings.tsx`.
RevenueCat webhook → `POST /webhooks/revenuecat` → updates `users.tier`.

**Push:** Register `Notifications.getExpoPushTokenAsync()` → `PUT /auth/push-token` on login.
Pipeline sends via Expo Push HTTP API (no Pushover).

---

## Freemium Gating

| Feature | Free | Paid |
|---------|------|------|
| Briefs per week | 3 | Daily (unlimited) |
| arXiv categories | System default | Any combination |
| Delivery time | Fixed (12pm ET) | Custom per user |
| Custom voice | No | Yes |
| Brief history | 7 days | Full |
| Manual trigger | No | Yes |

---

## Implementation Phases

### Phase 5a — Backend + Database (complete)
- Supabase DDL migrations
- FastAPI skeleton with JWT validation
- `pipeline/runner.py` (multi-user pipeline)
- APScheduler in `main.py`
- All API endpoints
- Dockerfile for Railway

### Phase 5b — Onboarding API (complete)
- `pipeline/onboarding_chat.py` (adapted `ConversationManager`)
- `/onboarding/session` endpoints with SSE streaming

### Phase 5c — iOS App (next)
- Week 1: Auth screens + `AuthProvider` + Supabase JS SDK wiring
- Week 2: `onboarding.tsx` (SSE chat UI), `onboarding-settings.tsx`, `today.tsx` (audio player)
- Week 3: `history.tsx`, `settings.tsx`, push token registration, EAS Build + TestFlight test

### Phase 5d — Subscriptions
- RevenueCat dashboard + App Store Connect product setup
- `react-native-purchases` in app + paywall screen
- `POST /webhooks/revenuecat` in backend
- Tier gates in `runner.py` and `settings.py`

### Phase 5e — Decommission GitHub Actions
After Railway has run reliably for 2 weeks, disable `schedule` trigger in `daily_brief.yml`.
Keep `workflow_dispatch` as emergency manual fallback.

---

## Critical Files

| File | Role |
|------|------|
| `run_pipeline.py` | Primary refactor target → `backend/pipeline/runner.py` |
| `planning_agent/conversation.py` | Adapted → `backend/pipeline/onboarding_chat.py` |
| `research_agent/selector.py` | `_load_seen`/`_mark_seen` replaced with Supabase queries |
| `delivery_agent/storage.py` | Path changes to `{user_id}/filename`, public URL → signed URL |
| `research_agent/profile.py` | `ResearchProfile.create()` reused as-is from onboarding endpoint |
| `backend/pipeline/scheduler.py` | New — APScheduler per-user cron |
| `briefai-mobile/app/(auth)/onboarding.tsx` | Most complex screen — SSE chat UI |

---

## Verification (end-to-end)

1. New user signs up via iOS app → completes onboarding chat → profile embedding stored in DB
2. Backend scheduler fires for that user → brief + audio appear in `public.briefs`
3. Expo push notification received on iPhone → tapping opens audio in app
4. Free user hits 3-brief limit → paywall shown → upgrades → daily briefs resume
5. Paid user changes delivery time → scheduler rebuilt → brief arrives at new time
