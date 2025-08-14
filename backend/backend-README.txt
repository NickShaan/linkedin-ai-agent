# linkedin-ai-agent — Backend (FastAPI, Postgres, LinkedIn, Gemini)

## What this service does
- Auth (email/password + LinkedIn **OIDC**)
- Profile storage (headline/bio/industries/goals/keywords)
- AI draft generation (Google Gemini)
- **Post to LinkedIn** immediately or **schedule** for later
- Background scheduler that publishes due posts

---

## High-level architecture

```
+----------------------+        +---------------------+        +---------------------+
|  Angular Frontend    |  --->  |  FastAPI Backend    |  --->  |  PostgreSQL         |
|  (localhost:4200)    |        |  (localhost:8000)   |        |  (DATABASE_URL)     |
+----------+-----------+        +----------+----------+        +----------+----------+
           |                               |                              |
           | OAuth start/public            | OAuth callback               |
           v                               v                              |
     LinkedIn (OIDC + w_member_social)  <----  Access token + /userinfo  |
           |                               |                              |
           |--------------------------------- Posts via /v2/ugcPosts -----|
```

Generate & Post sequence:

```
User           Frontend                Backend                        LinkedIn
────────────   ─────────────────────   ─────────────────────────────   ──────────────
click button ─▶ POST /content/generate
                                      • Build prompt (profile + opts)
                                      • Call Gemini → draft text
                                      • Save idea+post
if publish_now=true                   • Get LI token + li_id
                                      • POST /v2/ugcPosts ───────────▶ 201 + URN
                                      • Update posts.status='posted'
```

---

## Folder layout

```
app/
  main.py                # FastAPI app + scheduler start
  config.py              # env reader (origins, log level, etc.)
  db.py                  # psycopg2 pool helpers
  deps.py                # get_current_user() (JWT)
  auth_utils.py          # bcrypt + JWT helpers

  routes/
    auth.py              # /auth/signup, /auth/login, /auth/me
    oauth_linkedin.py    # OIDC login + token upsert + profile snapshot
    profile.py           # profile CRUD, providers, resume upload, summary
    content.py           # /content/generate, /schedule, /publish-now

  ai/gemini_service.py   # Gemini wrapper
  jobs/scheduler.py      # background loop: posts due scheduled_posts
```

DB tables: `users, linkedin_profile, tokens_linkedin, profiles, providers, resume_texts, ideas, posts, scheduled_posts`.

---

## Prerequisites
- Python 3.11+
- PostgreSQL 13+
- LinkedIn app with products:
  - ✅ *Sign In with LinkedIn using OpenID Connect*
  - ✅ *Share on LinkedIn*
- Google **Gemini** API key

---

## Environment (.env)

Create `backend/.env`:

```
# Server
BACKEND_BASE_URL=http://localhost:8000
FRONTEND_ORIGIN=http://localhost:4200
FRONTEND_BRIDGE_URL=http://localhost:4200/oauth-bridge
LOG_LEVEL=INFO
DEV_VERBOSE=true

# DB
DATABASE_URL=postgres://postgres:postgres@localhost:5432/influence_os

# LinkedIn
LINKEDIN_CLIENT_ID=xxxxxxxxxxxxxx
LINKEDIN_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
OAUTH_REDIRECT_PATH=/oauth/linkedin/callback
OAUTH_SCOPES=openid profile email w_member_social

# AI
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

> **LinkedIn portal:** add redirect `http://localhost:8000/oauth/linkedin/callback` and add your LinkedIn account as an **Authorized user** (Development mode).

---

## Install & run (local)

```
# from backend/
python -m venv venv
venv\Scripts ctivate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# Create DB & load schema
psql "$env:DATABASE_URL" -f schema.sql     # PowerShell
# psql $DATABASE_URL -f schema.sql         # macOS/Linux

uvicorn app.main:app --port 8000
```

You should see:
```
[OAUTH] Using scopes = ['openid', 'profile', 'email', 'w_member_social']
... Scheduler started ...
```

---

## Key endpoints

Auth
- `POST /auth/signup`
- `POST /auth/login`
- `GET /auth/me`

LinkedIn OAuth
- `GET /oauth/linkedin/start-public` → `{ url }`
- `GET /oauth/linkedin/callback` → redirects to `FRONTEND_BRIDGE_URL?linkedin=ok#token=<JWT>`
- `POST /oauth/linkedin/sync`
- `GET /oauth/linkedin/check`

Profile
- `GET/PUT /profile`
- `PUT /profile/providers`
- `POST /profile/upload-resume`
- `GET /profile/summary`

Content
- `POST /content/generate` (supports `publish_now` + `visibility`)
- `POST /content/schedule`
- `POST /content/publish-now`

---

## Scheduler

Background job polls `scheduled_posts` and posts due items via LinkedIn using the saved member token.

```
jobs/scheduler.py:  poll 10s → SELECT due → POST ugcPosts → UPDATE status
```

---

## Troubleshooting

**401 REVOKED_ACCESS_TOKEN**  
- Re-login with LinkedIn; we always upsert the new token in the callback.

**403 Forbidden**  
- App lacks *Share on LinkedIn*, or your LinkedIn user isn’t Authorized in Dev mode, or token didn’t grant `w_member_social`. Reconnect.

**400 Bad Request**  
- Check author URN `urn:li:person:<li_id>` and body shape.

**Token expiry/timezones**  
- Tokens stored in IST and compared in IST; legacy naive timestamps are normalized.
  
**See the post**  
- Use returned URN: `https://www.linkedin.com/feed/update/<URN>`
  (e.g., `urn:li:share:7361819648067072000`).
