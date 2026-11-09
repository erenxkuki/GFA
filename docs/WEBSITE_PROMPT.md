# Official GFA Website — Build Prompt

> **How to use this document:** feed the sections below to an AI coding agent (Cursor / Bolt / v0 / Lovable / Claude Code) in order. Each section is a self-contained task. Do not skip. The result must be a production-grade marketing + community site for **GFA (Gaming For AI)**.

---

## 0. Project context (READ FIRST)

- **Product:** GFA — "Gaming For AI": open-source, model-independent gaming infrastructure for AI. Models observe, think, play, and learn from video games.
- **Tagline:** "OBSERVE. THINK. PLAY. LEARN."
- **Repo:** https://github.com/erenxkuki/GFA
- **Core philosophy:** model independence; universal baseline before adapters; memory belongs to GFA; local-first; adapters enhance, never required; security — never bypass anti-cheat/DRM.
- **Tech stack of the core:** Python 3.11+, FastAPI (registry API), Typer CLI, SQL/SQLite memory, Windows SendInput capture. Website must speak to this ecosystem but can be any modern web stack.
- **Audience:** AI researchers, agent developers, indie game devs, open-source contributors, curious gamers.

---

## 1. Visual identity & motion design (the "wow" factor)

The landing page must feel like a next-generation gaming product site.

### 1.1 Landing page
- Full-screen hero with a **cinematic looping video background** (mp4/webm, muted, autoplay, loop) — gameplay footage (Minecraft, Roblox, ZZZ, Elden Ring, etc.).
- Headline: **"GFA — Gaming For AI"** with the tagline "OBSERVE. THINK. PLAY. LEARN." animated in (letter-by-letter or word-by-word reveal).
- Subheadline: "Open-source, model-independent gaming infrastructure for AI. Universal baseline. Adapters enhance."
- Two primary CTAs: `Get Started` (docs) and `View on GitHub` (repo link).
- Live animated counters: GitHub stars, adapters shipped, tests passing, supported games.

### 1.2 Animated panels / cards
- **Glassmorphism cards** (backdrop-blur, translucent, soft borders) that float over a video/image background.
- Each card shows a **game video/image behind it** (parallax on scroll + on hover, like a 3D tilt card).
- Hover: card lifts, background video plays (if paused), neon glow border, subtle scale.
- Scroll-triggered reveals: fade + slide up + stagger.
- Floating particle / grid background in hero (canvas or Three.js — keep it light).
- Smooth section transitions (Framer Motion / GSAP).

### 1.3 Sections (in order)
1. **Hero** (video bg, headline, CTAs, counters)
2. **"What is GFA"** — 4 pillars animated: OBSERVE / THINK / PLAY / LEARN
3. **Features grid** — animated cards with icons: Universal Baseline, Adapters, Memory Engine, Vision + OCR, Real-time Action, Audio Perception, WASAPI loopback, Replay, Macro Recording, Human-in-the-loop, RL, Semantic Memory, Auto Game Detection, Genre HUD Perception, Multi-view 3D, Combat Combos, Sync Input, Keybind Profiles, Latency Optimization.
4. **Live demo** — embedded video of GFA playing a game (YouTube/Vimeo) + a terminal-style animated "GCL command stream" overlay.
5. **Adapters showcase** — cards for Minecraft, Roblox, ZZZ, Elden Ring, Reference Game (each with game image + adapter capabilities + "View adapter" link).
6. **Architecture diagram** — animated SVG/flowchart of the pipeline: Capture → Perception → Reasoning → GCL → Baseline → Input.
7. **Roadmap / Changelog** — timeline of phases 0–14 + enhancements (see §5).
8. **Community / Discussion** — recent game discussions (logged-in users).
9. **Footer** — repo link, docs, license (MIT), security policy, contact, socials.

### 1.4 Theme
- Dark-first (gaming aesthetic), with a light-mode toggle.
- Accent: electric cyan + magenta gradient; secondary amber.
- Typography: a display font (e.g., Orbitron / Space Grotesk) for headings, Inter for body, JetBrains Mono for code/commands.
- High contrast, accessible (WCAG AA).

---

## 2. Tech stack (recommended)

- **Frontend:** Next.js 15 (App Router) + React 19 + TypeScript + Tailwind CSS v4 + Framer Motion + GSAP.
- **Auth:** NextAuth.js (Auth.js v5) — providers: Google OAuth (Continue with Google / Gmail), email+password, GitHub.
- **Database:** PostgreSQL (Neon / Supabase) via Prisma.
- **Media:** Cloudinary or AWS S3 for uploaded videos/images; HLS for streaming.
- **API:** Next.js Route Handlers + a separate FastAPI service (reuse GFA's registry API pattern) for the secured admin API.
- **Deploy:** Vercel (frontend) + Railway/Fly (API) + Neon (DB).
- **Analytics:** Plausible or PostHog (privacy-first).

---

## 3. Authentication & accounts

- **Sign in options:** "Continue with Google" (Gmail), "Continue with GitHub", email + password.
- **Account creation:** email verification, username, avatar upload, bio, linked game profiles.
- **Roles:** `user`, `moderator`, `admin` (owner = admin).
- **Session:** JWT + refresh tokens, httpOnly cookies.
- **Profile page:** avatar, bio, uploaded adapters/media, discussion history, starred games.
- **Security:** CSRF protection, rate limiting, 2FA optional for admins, audit log for admin actions.

---

## 4. Core feature: "Auto-Adapt → Adapter → Secured API → Website"

This is the centerpiece feature the user specifically asked for. Implement end-to-end:

### 4.1 In-GFA client (Python side)
- A new module `gfa/adapters/auto/` that:
  - Runs the **Universal Baseline** perception on a game window.
  - Detects the genre + HUD elements (reuse `gfa.genre`).
  - Records a candidate **adapter manifest** (id, name, version, capabilities, keybind preset, genre, element map) + screenshots.
  - Packages it as a ZIP (manifest.json + adapter.py stub + screenshots).
- A CLI command: `gfa adapter auto-detect <game-title> --out ./my-adapter` that walks the user through detection, then uploads.

### 4.2 Secured upload API (backend)
- `POST /api/adapters/upload` (multipart: ZIP + metadata) — requires auth (JWT), rate-limited (e.g., 5/hour/user), virus-scan + manifest validation (reuse `gfa.adapter_sdk.manifest.validate_manifest_file`).
- `POST /api/adapters/{id}/media` — upload videos/images for the adapter's showcase card.
- `GET /api/adapters` — public list (paginated, filterable by genre/game).
- `GET /api/adapters/{id}` — public detail.
- `PATCH /api/adapters/{id}` — owner or admin only (status: pending/approved/rejected).
- `DELETE /api/adapters/{id}` — owner or admin.
- All admin routes guarded by `role == admin` middleware; audit-logged.

### 4.3 Adapter review workflow
- New uploads land in `status = pending`.
- Admin (you) reviews in a private dashboard (`/admin/adapters`): preview manifest, screenshots, approve/reject with notes.
- Approved adapters appear publicly; rejected ones notify the uploader with reasons.
- Webhook/email notification on status change.

### 4.4 Private change-board API (owner-only)
- `POST /api/changelog` (admin only) — create a changelog entry: `{version, title, body (markdown), type: feature|fix|breaking, published_at}`.
- `PATCH /api/changelog/{id}`, `DELETE /api/changelog/{id}`.
- `GET /api/changelog` — public.
- Authenticated via a separate **admin API key** (stored in env `GFA_ADMIN_API_KEY`) OR an admin JWT — both supported. Key is never exposed to the frontend.
- Include a small CLI helper: `gfa website changelog push --title "..." --body file.md --type feature` that POSTs to this endpoint using the admin key from env.

---

## 5. Change board / changelog

- Public page `/changelog` with a vertical timeline.
- Each entry: version badge, date, type badge (feature/fix/breaking), title, markdown body, "view commit" link to GitHub (auto-linked by commit hash if provided).
- Filter by type; search.
- RSS feed (`/changelog/rss.xml`).
- "Subscribe to updates" email capture (store in DB, double opt-in).
- The owner pushes entries via the private API (§4.4). No public write access.

---

## 6. Community: game discussion (logged-in users)

- Each adapter/game has a discussion thread (`/games/{id}/discuss`).
- Features: create post (title + markdown body + optional media), reply (nested up to 2 levels), upvote/downvote, report, edit (owner only within 24h), delete (owner or moderator).
- Markdown rendering with syntax highlighting, image embeds, @mentions.
- Moderation: flag queue, ban user, lock thread (admin/moderator).
- Notifications: in-app + email on reply/mention.
- Real-time: WebSocket or Server-Sent Events for new replies.
- Anti-spam: rate limits (e.g., 5 posts/hour), CAPTCHA on first post, profanity filter (configurable).

---

## 7. Adapter upload UX (logged-in users)

- `/upload` page: drag-and-drop ZIP, manifest preview (parsed server-side), screenshots/video upload (multi-file, progress bars), title/description/tags/genre.
- Validation feedback inline (manifest errors shown).
- "My adapters" dashboard: status (pending/approved/rejected), edit, delete, view stats (downloads, views).
- Public adapter page: `/adapters/{id}` — manifest, capabilities, screenshots/video, download ZIP, discussion thread, "report" button, "star" (bookmark).

---

## 8. Pages & routes

| Route | Purpose |
|---|---|
| `/` | Landing page (hero, features, demo, adapters showcase, roadmap, footer) |
| `/docs` | Documentation (MDX, versioned) |
| `/adapters` | Browse adapters (filters: genre, game, status, sort) |
| `/adapters/{id}` | Adapter detail + discussion |
| `/upload` | Upload adapter (auth required) |
| `/dashboard` | User's adapters, stars, discussions |
| `/games/{id}/discuss` | Game discussion thread |
| `/changelog` | Public change board |
| `/admin` | Admin dashboard (adapters review, users, changelog CRUD, audit log) |
| `/admin/adapters` | Review queue |
| `/admin/changelog` | Changelog CRUD |
| `/login`, `/register`, `/profile/{username}` | Auth + profiles |
| `/api/*` | Backend API (see §4, §4.4) |

---

## 9. Database schema (Prisma)

Models: `User`, `Account` (OAuth), `Session`, `Adapter`, `AdapterMedia`, `AdapterReview`, `Discussion`, `Reply`, `Vote`, `ChangelogEntry`, `Subscription`, `AuditLog`.

Include `role` enum on User, `status` enum on Adapter, soft-delete flags, timestamps, and indexes on foreign keys + search columns.

---

## 10. Non-functional requirements

- **Performance:** Lighthouse score ≥ 90 (mobile + desktop); images via Next/Image; videos lazy-loaded; code-split.
- **SEO:** meta tags, OpenGraph, Twitter cards, sitemap, robots.txt, structured data (SoftwareApplication, Organization).
- **i18n:** English first; architecture ready for more languages (next-intl).
- **Accessibility:** keyboard navigation, ARIA labels, focus rings, reduced-motion respect.
- **Privacy:** cookie consent banner, GDPR-friendly (no third-party trackers by default), data export + delete account.
- **Security:** CSP headers, HSTS, input sanitization, SQL injection protection (Prisma), XSS protection (sanitize markdown), file upload validation (size/type), rate limiting.
- **Monitoring:** Sentry for errors, uptime monitoring, structured logs.

---

## 11. Deliverables checklist for the agent

1. ✅ Next.js app with all routes in §8
2. ✅ Auth (Google/GitHub/email) with roles
3. ✅ Landing page with animated hero, video bg, glass cards, parallax, scroll reveals
4. ✅ Adapter browse/detail/upload/dashboard flows
5. ✅ Discussion threads with replies/votes/moderation
6. ✅ Changelog timeline + RSS + private admin API
7. ✅ Private admin API key auth for changelog (env `GFA_ADMIN_API_KEY`)
8. ✅ `gfa website changelog push` CLI helper (Python, in core repo)
9. ✅ Database schema + migrations
10. ✅ Dockerfile + docker-compose for self-hosting
11. ✅ README with setup, env vars, deploy instructions
12. ✅ CI: lint + typecheck + tests on PR

---

## 12. Environment variables

```
DATABASE_URL=
NEXTAUTH_SECRET=
NEXTAUTH_URL=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
AWS_S3_BUCKET= / CLOUDINARY_URL=
GFA_ADMIN_API_KEY=   # owner-only changelog API
GFA_REGISTRY_API_URL= # link to the GFA registry API
SMTP_URL=            # emails
SENTRY_DSN=
```

---

## 13. Tone & copy guidelines

- Voice: confident, technical, welcoming, open-source ethos.
- Avoid hype words ("revolutionary", "game-changer"); prefer concrete claims ("Universal baseline before adapters", "Model-independent", "Anti-cheat safe").
- Always link back to the GitHub repo and docs.
- Highlight the philosophy: "Memory belongs to GFA, not the model."

---

## 14. Acceptance criteria

- A visitor can land, watch the hero video, scroll through animated feature cards, and reach the GitHub repo in ≤ 2 clicks.
- A logged-in user can upload an adapter ZIP; it appears as "pending"; admin approves; it shows publicly with its discussion thread.
- The owner can run `gfa website changelog push --title "v0.2.0 — Audio perception" --body notes.md --type feature` and see it live on `/changelog` within 5 seconds.
- Lighthouse ≥ 90 on mobile.
- All forms validated; no console errors in production.

---

*End of prompt. Feed §0–§14 to the website-building agent in order; each numbered section is a discrete, testable deliverable.*
