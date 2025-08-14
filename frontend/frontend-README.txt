# linkedin-ai-agent — Frontend (Angular + Standalone APIs + Tailwind-style)

## What the app does
- Login (email/password + LinkedIn sign-in)
- OAuth Bridge (consumes `#token=...` from backend redirect)
- Profile Setup wizard
- Home (LinkedIn status, résumé upload, profile summary)
- Compose (AI assistant, **Generate** with optional **Post immediately**)

---

## Folder layout

```
src/
  main.ts
  index.html

  app/
    app.config.ts              # provideRouter, provideHttpClient(withInterceptors)
    app.routes.ts              # (login, signup, oauth-bridge, app, app/setup, compose)
    app.component.*            # shell

    core/
      auth.service.ts          # login/signup/me + profile/content APIs
      auth.guard.ts            # guards /app*
      auth.interceptor.ts      # Authorization: Bearer <JWT>

    pages/
      auth/login/*             # start LinkedIn public flow
      auth/signup/*
      oauth-bridge/*           # saves #token and routes
      profile-setup/*          # PUT /profile → onboarded=true
      home/*                   # LinkedIn status, résumé upload, summary
      compose/*                # date/time + options → generate (+ post now)
```

---

## Configure the API base

Set your API base (example in `core/api.service.ts`):

```ts
const API_BASE = 'http://localhost:8000';
```

Ensure the interceptor adds the JWT from storage to every request except the **public** OAuth start endpoint.

---

## Run locally

```
npm i
npm start   # (or ng serve --port 4200)
```

Open: `http://localhost:4200`

---

## Compose page behavior

- Date & Time required at the top (for scheduling UX consistency).
- Optional: topic, format, model, emojis, tone, kind.
- **Post immediately** toggle + visibility (PUBLIC / CONNECTIONS).
- Primary button changes label: **Generate** vs **Generate & Post**.

Payload example when submitting:

```json
{
  "topic": null,
  "format": "short_post",
  "model": "gemini-1.5-flash",
  "emojis": true,
  "suggest_image": false,
  "tone": [],
  "publish_now": true,
  "visibility": "PUBLIC"
}
```

If `publish_now=false`, the server stores the draft and returns `{ post_id, text, format }` for preview.

---

## End-to-end OAuth (public flow)

1) Frontend calls `GET /oauth/linkedin/start-public` → gets `url`
2) Browser goes to LinkedIn; user consents
3) LinkedIn sends user to `http://localhost:8000/oauth/linkedin/callback`
4) Backend mints app JWT and redirects to
   `http://localhost:4200/oauth-bridge?linkedin=ok#token=<JWT>`
5) OAuth Bridge stores token and calls `/auth/me`:
   - `onboarded=false` → navigate `/app/setup`
   - else → `/app`

---

## Common UI tips

- Define a simple interface for drafts:
  ```ts
  export interface Draft { post_id: number; text: string; format: string; }
  ```
- Primary submit button (purple) can switch label based on `form.value.postNow`:
  ```html
  {{ loading ? 'Generating...' : (form.value.postNow ? 'Generate & Post' : 'Generate') }}
  ```
- Schedule button (optional) can call `POST /content/schedule` with ISO `scheduled_at` built from date+time inputs.

---

## Production notes

- Serve Angular over HTTPS; configure CORS `FRONTEND_ORIGIN` accordingly.
- Store JWT in `localStorage` or a safer storage strategy; handle logout on 401.
- Add analytics/telemetry for drafts posted, LinkedIn errors, etc.
- Consider lazy routes and preloading strategy for faster loads.
