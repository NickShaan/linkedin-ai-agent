# linkedin-ai-agent— Full Project README

AI-assisted LinkedIn posting app built with **Angular** (frontend) and **FastAPI** (backend) with **PostgreSQL**. It lets users:
- Sign in with **LinkedIn OIDC** (and email/password).
- Create a profile (headline, bio, industries, goals, tone, keywords).
- Generate posts with **Google Gemini**.
- **Post immediately** to LinkedIn or **schedule** for later via a background scheduler.

---

## TL;DR — Run it locally

1) **Prereqs**: Python 3.11+, Node 18+, PostgreSQL 13+, a LinkedIn developer app with **OpenID Connect** + **Share on LinkedIn**, a **Gemini** API key.
2) **Backend** (from `backend/`):
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   # source venv/bin/activate

   pip install -r requirements.txt

   # Create DB & load schema (adjust as needed)
   psql "$env:DATABASE_URL" -f schema.sql      # PowerShell
   # psql $DATABASE_URL -f schema.sql          # macOS/Linux

   uvicorn app.main:app --port 8000
   ```
3) **Frontend** (from `frontend/`):
   ```bash
   npm i
   npm start   # opens http://localhost:4200
   ```

> If you see `[LI] POST ugcPosts status=201` in the backend logs when you click **Generate & Post**, you’re successfully posting to LinkedIn 🎉

---

## What’s inside

```
repo-root/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                # FastAPI app + CORS + start scheduler
│  │  ├─ config.py              # env reader
│  │  ├─ db.py                  # psycopg2 connection pool
│  │  ├─ deps.py                # get_current_user() (JWT)
│  │  ├─ auth_utils.py          # bcrypt + JWT helpers
│  │  ├─ routes/
│  │  │  ├─ auth.py             # /auth/signup, /auth/login, /auth/me
│  │  │  ├─ oauth_linkedin.py   # OIDC login + token upsert + profile snapshot
│  │  │  ├─ profile.py          # profile CRUD, providers, resume upload, summary
│  │  │  └─ content.py          # /content/generate, /schedule, /publish-now
│  │  ├─ ai/gemini_service.py   # Gemini wrapper
│  │  └─ jobs/scheduler.py      # background loop → post due scheduled_posts
│  ├─ schema.sql                # DB schema
│  └─ requirements.txt
└─ frontend/
   └─ src/
      ├─ main.ts
      ├─ index.html
      └─ app/
         ├─ app.config.ts       # provideRouter, provideHttpClient(withInterceptors)
         ├─ app.routes.ts       # (login, signup, oauth-bridge, app, app/setup, compose)
         ├─ app.component.*
         ├─ core/
         │  ├─ auth.service.ts  # login/signup/me + profile/content APIs
         │  ├─ auth.guard.ts    # guards /app*
         │  └─ auth.interceptor.ts # Authorization: Bearer <JWT>
         └─ pages/
            ├─ auth/login/*
            ├─ auth/signup/*
            ├─ oauth-bridge/*   # stores #token and routes
            ├─ profile-setup/*  # wizard → PUT /profile → onboarded=true
            ├─ home/*           # LinkedIn badge, résumé upload, profile summary
            └─ compose/*        # Generate (+ optional post now) + Schedule
```

---

## Architecture

```
+----------------------+        +---------------------+        +---------------------+
|  Angular Frontend    |  --->  |  FastAPI Backend    |  --->  |  PostgreSQL         |
|  (localhost:4200)    |        |  (localhost:8000)   |        |  (DATABASE_URL)     |
+----------+-----------+        +----------+----------+        +----------+----------+
           |                               |                              |
           |  GET /oauth/linkedin/start    |  /oauth/linkedin/callback    |
           v                               v                              |
     LinkedIn (OIDC + w_member_social)  <----  Access token + /userinfo   |
           |                               |                              |
           |---------------------------------  POST /v2/ugcPosts  --------|
```

Generate & Post flow (happy path):
```
User          Frontend                   Backend                         LinkedIn
───────────   ────────────────────────   ─────────────────────────────   ──────────────
click btn ─▶  POST /content/generate    build prompt → Gemini draft
                                           save idea + post
if publish_now=true                      _get_li_token_and_id()
                                           POST /v2/ugcPosts  ─────────▶  201 + URN
                                           UPDATE posts.status='posted'
```

**Time zone**: token expiry and comparisons use **IST (UTC+05:30)** to avoid naive/aware issues.

---

## Environment

Create `backend/.env` with these keys:

```
# Server
BACKEND_BASE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:4200
FRONTEND_BRIDGE_URL=http://localhost:4200/oauth-bridge
LOG_LEVEL=INFO
DEV_VERBOSE=true

# Database
DATABASE_URL=postgres://postgres:postgres@localhost:5432/influence_os

# LinkedIn (OIDC + Share on LinkedIn)
LINKEDIN_CLIENT_ID=xxxxxxxxxxxxxx
LINKEDIN_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
OAUTH_REDIRECT_PATH=/oauth/linkedin/callback
OAUTH_SCOPES=openid profile email w_member_social

# AI
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## LinkedIn developer app setup

1. Create an app at https://www.linkedin.com/developers
2. Add **products**:
   - ✅ **Sign In with LinkedIn using OpenID Connect**
   - ✅ **Share on LinkedIn**
3. **Authorized users** (Development mode): add your LinkedIn account.
4. **Redirect URI**: add `http://localhost:8000/oauth/linkedin/callback`.
5. Copy **Client ID/Secret** into `.env`.
6. Ensure frontend uses the backend-start endpoints:
   - `GET /oauth/linkedin/start-public`

> If you add or change scopes, users must re-consent (disconnect/reconnect).

---

## Database (short)

Tables:
- `users` (onboarded flag)
- `linkedin_profile` (li_id, names, picture, email, raw_json)
- `tokens_linkedin` (member access token + expiry, IST-aware)
- `profiles` (headline, bio, industries[], goals, tone[], keywords[])
- `providers` (per-user API keys, incl. Gemini)
- `resume_texts` (extracted text)
- `ideas` (title/brief/tags)
- `posts` (format, draft_text, hashtags, status, linkedin_urn, published_at)
- `scheduled_posts` (text, scheduled_at, status)

Load everything via `schema.sql`.

---

## Backend commands

Start API:
```bash
uvicorn app.main:app --port 8000
```

Key endpoints:
- **Auth**: `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`
- **OAuth**: `GET /oauth/linkedin/start-public`, `GET /oauth/linkedin/callback`
- **Profile**: `GET/PUT /profile`, `PUT /profile/providers`, `POST /profile/upload-resume`, `GET /profile/summary`
- **Content**:
  - `POST /content/generate` (supports `publish_now`, `visibility`)
  - `POST /content/schedule`
  - `POST /content/publish-now`

Example (Generate & Post now):
```bash
curl -X POST http://localhost:8000/content/generate   -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json"   -d '{"format":"short_post","model":"gemini-1.5-flash","emojis":true,"publish_now":true,"visibility":"PUBLIC"}'
```

---

## Frontend notes

- Primary button label toggles between **Generate** and **Generate & Post** based on a checkbox (`postNow`).
- OAuth Bridge reads `#token=<JWT>` from the backend redirect and stores it; then calls `/auth/me` to route users to `/app` or `/app/setup`.
- API base (example in `core/api.service.ts`):
  ```ts
  const API_BASE = 'http://localhost:8000';
  ```

Run:
```bash
npm i
npm start
```

---

## Scheduler (background worker)

- Runs inside the API process at startup.
- Polls `scheduled_posts` every 10s.
- Posts due items to LinkedIn using the saved user token; updates `status` to `posted` or `failed`.
- Adjust poll frequency/batch size in `jobs/scheduler.py` if needed.

---

## Troubleshooting

**Login: `unauthorized_scope_error`**  
- Use OIDC scopes: `openid profile email w_member_social`.  
- Ensure products are enabled (OIDC + Share) and you are an Authorized user.

**Posting: 401 `REVOKED_ACCESS_TOKEN`**  
- Re-login; the callback **upserts** a fresh token for existing users.

**Posting: 403 `Forbidden`**  
- Your app may lack **Share on LinkedIn**, or your LinkedIn user is not Authorized in Dev mode, or the token didn’t grant `w_member_social`. Reconnect.

**Posting: 400 `Bad Request`**  
- Validate body and `author` URN (`urn:li:person:<li_id>`). Use `GET /oauth/linkedin/check` to confirm `li_id` and `expires_at`.

**Token expiry / timezone**  
- We store and compare expiry in **IST** (UTC+05:30). Legacy naive timestamps are normalized.

**CORS**  
- Backend CORS must allow `FRONTEND_ORIGIN`. For production, update both origin and HTTPS.

---

## Production checklist

- HTTPS for both frontend and backend.
- Secrets in a vault; rotate JWT secret.
- Use a separate worker (or container) for the scheduler.
- Add logging/metrics (rate of 2xx/4xx/5xx, LinkedIn error codes, queue length).
- Migrations with Alembic or SQL changes in `schema.sql`.
- Error pages and retry UI for rate-limited Gemini (429).

---

## Useful links

- View a posted share by URN:  
  `https://www.linkedin.com/feed/update/<URN>` (e.g., `urn:li:share:7361819648067072000`)

Happy shipping! 🚀
