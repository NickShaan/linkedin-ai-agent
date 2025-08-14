# app/routes/content.py
from typing import Literal, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from collections import Counter
import os, re, requests

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from google.api_core.exceptions import ResourceExhausted

from app.deps import get_current_user
from app.db import get_conn, put_conn
from app.ai.gemini_service import generate_post

router = APIRouter(prefix="/content", tags=["content"])

# --- Timezone (India Standard Time) ---
IST = timezone(timedelta(hours=5, minutes=30))

# ------------------ Schemas ------------------

class GenIn(BaseModel):
    topic: Optional[str] = None
    format: Literal["short_post", "article", "carousel"] = "short_post"
    model: Optional[str] = "gemini-1.5-flash"
    emojis: Optional[bool] = True
    suggest_image: Optional[bool] = False
    tone: Optional[List[str]] = None
    kind: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    publish_now: Optional[bool] = False
    visibility: Optional[str] = "PUBLIC"  # or "CONNECTIONS"

class GenOut(BaseModel):
    post_id: int
    text: str
    format: str

class ScheduleIn(BaseModel):
    post_id: int
    scheduled_at: datetime
    provider: Optional[str] = "linkedin"

class PublishNowIn(BaseModel):
    post_id: int
    visibility: Optional[str] = "PUBLIC"  # or CONNECTIONS

# ------------------ Helpers ------------------

def _latest_resume_text(uid: int) -> str:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT extracted FROM resume_texts
              WHERE user_id=%s
              ORDER BY uploaded_at DESC
              LIMIT 1
            """, (uid,))
            row = cur.fetchone()
            return row[0] if row else ""
    finally:
        put_conn(conn)

_STOP = set(("a an and are as at be by for from has have i in is it its of on or that the to with your you we our their they them this those these").split())
def _simple_keywords(text: str, k: int = 10) -> List[str]:
    if not text:
        return []
    words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
    words = [w for w in words if w not in _STOP]
    return [w for (w, _cnt) in Counter(words).most_common(k)]

def _load_profile(uid: int) -> dict:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT headline, bio, industries, goals, tone, keywords
              FROM profiles WHERE user_id=%s
            """, (uid,))
            row = cur.fetchone()
            if not row:
                return {"headline": None, "bio": None, "industries": [], "goals": None, "tone": [], "keywords": []}
            return {
                "headline": row[0],
                "bio": row[1],
                "industries": row[2] or [],
                "goals": row[3],
                "tone": row[4] or [],
                "keywords": row[5] or [],
            }
    finally:
        put_conn(conn)

def _get_gemini_key(user_id: int) -> Optional[str]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT gemini_key FROM providers WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            user_key = row[0] if row else None
    finally:
        put_conn(conn)
    return user_key or os.getenv("GEMINI_API_KEY")

def _linkedin_post_text(access_token: str, li_id: str, text: str, visibility: str = "PUBLIC") -> str:
    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    body = {
        "author": f"urn:li:person:{li_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text[:2900]},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility or "PUBLIC"
        },
    }
    r = requests.post(url, headers=headers, json=body, timeout=25)

    # Debug logs to see why LinkedIn may reject
    print("[LI] POST ugcPosts status=", r.status_code)
    try:
        print("[LI] Response JSON:", r.json())
    except Exception:
        print("[LI] Response text:", r.text[:500])
    print("[LI] Request headers sent:", {"Authorization": "redacted", "X-Restli-Protocol-Version": headers["X-Restli-Protocol-Version"], "Content-Type": headers["Content-Type"]})
    print("[LI] Request body sent:", body)

    if r.status_code in (200, 201):
        return r.headers.get("x-restli-id") or r.headers.get("location", "") or ""

    # Bubble clear errors
    try:
        msg = r.json().get("message") or r.text
    except Exception:
        msg = r.text
    if r.status_code == 403:
        raise HTTPException(
            status_code=502,
            detail=("LinkedIn 403 Forbidden: app lacks Share on LinkedIn product OR this token "
                    "didn’t grant w_member_social. Reconnect LinkedIn and ensure product access. "
                    f"Raw: {msg[:300]}")
        )
    if r.status_code == 401:
        raise HTTPException(502, "LinkedIn 401 Unauthorized: token expired/invalid. Reconnect.")
    if r.status_code == 400:
        raise HTTPException(502, f"LinkedIn 400 Bad Request: payload/author issue. Raw: {msg[:300]}")
    raise HTTPException(502, f"LinkedIn error {r.status_code}: {msg[:300]}")

# ------------------ Routes ------------------

@router.post("/generate", response_model=GenOut)
def generate(payload: GenIn, user = Depends(get_current_user)):
    uid = user["id"]

    api_key = _get_gemini_key(uid)
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Gemini API key not set. Add one in /profile/providers or server .env."
        )

    ctx = _load_profile(uid)

    # Tone: request override -> profile -> default
    tone_list = payload.tone if payload.tone else (ctx.get("tone") or [])
    tone_str = ", ".join([t for t in tone_list if t]) or "professional, friendly"

    # Industries/keywords (fallback to résumé/bio/headline)
    industries = ctx.get("industries", []) or []
    keywords = ctx.get("keywords", []) or []
    if not keywords:
        pile = " ".join(filter(None, [ctx.get("bio") or "", ctx.get("headline") or "", _latest_resume_text(uid)]))
        keywords = _simple_keywords(pile, 10)

    industries_str = ", ".join(industries)
    keywords_str = ", ".join(keywords)

    # Topic: auto-derive if blank
    topic = (payload.topic or "").strip()
    if not topic:
        if keywords:
            topic = f"Practical tips on {keywords[0]} for beginners"
        elif industries:
            topic = f"Insights on trends in {industries[0]}"
        else:
            topic = "A key learning from my recent work"

    style_line = "Use a few appropriate emojis." if payload.emojis else "Do not use emojis."
    kind_line = f"Post type hint: {payload.kind}." if payload.kind else ""
    image_hint = "Think of an image idea but DO NOT include it in the output." if payload.suggest_image else ""

    prompt = f"""
You are a LinkedIn content strategist.
Tone: {tone_str}. Industries: {industries_str}. Keywords: {keywords_str}.
{kind_line}
Create a {payload.format.replace('_',' ')} on: "{topic}".
For short_post: <= 180 words, include 3–5 relevant hashtags and a clear CTA.
{style_line} {image_hint}
Return only the post text, no preface or metadata.
""".strip()

    try:
        text = generate_post(api_key, prompt, model=payload.model or "gemini-1.5-flash")
    except ResourceExhausted:
        raise HTTPException(
            status_code=429,
            detail="Rate limited by Gemini (free tier). Please wait and try again, or add your own API key."
        )

    if not text:
        raise HTTPException(status_code=500, detail="Model returned empty text")

    # Persist idea + post
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ideas (user_id, title, brief, tags) VALUES (%s,%s,%s,%s) RETURNING id",
                    (uid, topic, None, None)
                )
                idea_id = cur.fetchone()[0]

                cur.execute("""
                  INSERT INTO posts (user_id, idea_id, format, draft_text, hashtags)
                  VALUES (%s,%s,%s,%s,%s) RETURNING id
                """, (uid, idea_id, payload.format, text, None))
                post_id = cur.fetchone()[0]
    finally:
        put_conn(conn)

    # Publish immediately (optional)
    if payload.publish_now:
        access_token, li_id = _get_li_token_and_id(uid)
        li_urn = _linkedin_post_text(access_token, li_id, text, payload.visibility or "PUBLIC")

        # Mark as posted
        conn = get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute(
                            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ, "
                            "ADD COLUMN IF NOT EXISTS linkedin_urn TEXT, "
                            "ADD COLUMN IF NOT EXISTS status VARCHAR(20)"
                        )
                    except Exception:
                        pass
                    cur.execute(
                        "UPDATE posts SET published_at=now(), linkedin_urn=%s, status='posted' "
                        "WHERE id=%s AND user_id=%s",
                        (li_urn, post_id, uid)
                    )
        finally:
            put_conn(conn)

    return GenOut(post_id=post_id, text=text, format=payload.format)

@router.post("/schedule")
def schedule(payload: ScheduleIn, user = Depends(get_current_user)):
    uid = user["id"]

    # Load draft text for this post
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT draft_text FROM posts WHERE id=%s AND user_id=%s", (payload.post_id, uid))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Post not found")
            draft_text = row[0]
    finally:
        put_conn(conn)

    # Save to queue
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                  INSERT INTO scheduled_posts (user_id, text, scheduled_at, status, provider)
                  VALUES (%s,%s,%s,'queued',%s)
                """, (uid, draft_text, payload.scheduled_at, payload.provider or 'linkedin'))
    finally:
        put_conn(conn)

    return {"message": "Scheduled", "scheduled_at": payload.scheduled_at.isoformat()}

# ---------- LinkedIn publish-now ----------

def _get_li_token_and_id(uid: int) -> Tuple[str, str]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT access_token, expires_at FROM tokens_linkedin WHERE user_id=%s", (uid,))
            trow = cur.fetchone()
            if not trow:
                raise HTTPException(409, "LinkedIn not connected")
            access_token, expires_at = trow

            # normalize legacy naive timestamps
            if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=IST)

            # ⬇️ Add these two lines here
            now_ist = datetime.now(IST)
            print(f"[LI] token check uid={uid} expires_at={expires_at and expires_at.isoformat()} now_ist={now_ist.isoformat()}")

            # compare after logging
            if expires_at and expires_at < now_ist:
                raise HTTPException(401, "LinkedIn token expired. Reconnect.")

            cur.execute("SELECT li_id FROM linkedin_profile WHERE user_id=%s", (uid,))
            prow = cur.fetchone()
            if not prow or not prow[0]:
                raise HTTPException(409, "No LinkedIn profile li_id stored")
            li_id = prow[0]
    finally:
        put_conn(conn)
    return access_token, li_id


@router.post("/publish-now")
def publish_now(payload: PublishNowIn, user=Depends(get_current_user)):
    uid = user["id"]

    # 1) Load draft
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT draft_text FROM posts WHERE id=%s AND user_id=%s", (payload.post_id, uid))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Post not found")
            draft_text = row[0]
    finally:
        put_conn(conn)

    # 2) LinkedIn token + post
    access_token, li_id = _get_li_token_and_id(uid)
    li_urn = _linkedin_post_text(access_token, li_id, draft_text, payload.visibility or "PUBLIC")

    # 3) Mark as published in your DB (add cols if missing)
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ, "
                        "ADD COLUMN IF NOT EXISTS linkedin_urn TEXT, "
                        "ADD COLUMN IF NOT EXISTS status VARCHAR(20)"
                    )
                except Exception:
                    pass
                cur.execute(
                    "UPDATE posts SET published_at=now(), linkedin_urn=%s, status='posted' "
                    "WHERE id=%s AND user_id=%s",
                    (li_urn, payload.post_id, uid)
                )
    finally:
        put_conn(conn)

    return {"message": "Published to LinkedIn", "linkedin_urn": li_urn or None}
