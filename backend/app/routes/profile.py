# app/routes/profile.py
import logging
import io
from typing import Optional
import os, re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.db import get_conn, put_conn
from app.schemas import ProfileIn, ProfileOut, ProvidersIn
from app.deps import get_current_user
from pdfminer.high_level import extract_text
from app.ai.profile_analyzer import analyze_profile
# from .oauth_linkedin import _save_token_and_profile  # only needed if you call it here

router = APIRouter(prefix="/profile", tags=["profile"])
log = logging.getLogger("profile")


@router.get("", response_model=ProfileOut)
def get_profile(user=Depends(get_current_user)):
    print("[/profile] requester:", user)
    uid = user["id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, headline, bio, industries, goals, tone, keywords
                FROM profiles WHERE user_id=%s
            """, (uid,))
            row = cur.fetchone()
            if not row:
                # Return an empty profile shape
                return {
                    "user_id": uid, "headline": None, "bio": None, "industries": [],
                    "goals": None, "tone": None, "keywords": []
                }
            return {
                "user_id": row[0],
                "headline": row[1],
                "bio": row[2],
                "industries": row[3] or [],
                "goals": row[4],
                "tone": row[5],
                "keywords": row[6] or []
            }
    finally:
        put_conn(conn)


@router.put("", response_model=ProfileOut)
def upsert_profile(payload: ProfileIn, user=Depends(get_current_user)):
    uid = user["id"]
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO profiles (user_id, headline, bio, industries, goals, tone, keywords)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET headline=EXCLUDED.headline,
                        bio=EXCLUDED.bio,
                        industries=EXCLUDED.industries,
                        goals=EXCLUDED.goals,
                        tone=EXCLUDED.tone,
                        keywords=EXCLUDED.keywords,
                        updated_at=now()
                """, (uid, payload.headline, payload.bio, payload.industries,
                      payload.goals, payload.tone, payload.keywords))
                cur.execute("UPDATE users SET onboarded=TRUE, updated_at=now() WHERE id=%s", (uid,))
        return get_profile(user)  # reuse getter
    finally:
        put_conn(conn)


@router.put("/providers")
def save_providers(payload: ProvidersIn, user=Depends(get_current_user)):
    uid = user["id"]
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO providers (user_id, gemini_key, openai_key, anthropic_key)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET gemini_key=EXCLUDED.gemini_key,
                        openai_key=EXCLUDED.openai_key,
                        anthropic_key=EXCLUDED.anthropic_key,
                        updated_at=now()
                """, (uid, payload.gemini_key, payload.openai_key, payload.anthropic_key))
        return {"message": "Providers saved"}
    finally:
        put_conn(conn)


@router.post("/upload-resume")
def upload_resume(file: UploadFile = File(...), user=Depends(get_current_user)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes supported")

    # Read PDF and extract text
    content = file.file.read()
    text = extract_text(io.BytesIO(content)) or ""

    # Load LinkedIn snapshot (if any)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT raw_json FROM linkedin_profile WHERE user_id=%s", (user["id"],))
            row = cur.fetchone()
            linkedin_json = row[0] if row else {}
    finally:
        put_conn(conn)

    # Analyze with Gemini
    insights = analyze_profile(linkedin_json or {}, text)

    # Save insights + persist resume text
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # 1) persist the extracted résumé text for history/keywords
                cur.execute("""
                  INSERT INTO resume_texts (user_id, filename, extracted)
                  VALUES (%s, %s, %s)
                """, (user["id"], file.filename, text))

                # 2) update profile fields from insights
                cur.execute("""
                  INSERT INTO profiles (user_id, bio, tone, keywords)
                  VALUES (%s, %s, %s, %s)
                  ON CONFLICT (user_id) DO UPDATE
                  SET bio=EXCLUDED.bio,
                      tone=EXCLUDED.tone,
                      keywords=EXCLUDED.keywords,
                      updated_at=now()
                """, (user["id"],
                      insights.get("background_summary"),
                      insights.get("tone", []),
                      insights.get("keywords", [])))
    finally:
        put_conn(conn)

    return {"message": "Résumé analyzed", "insights": insights}


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

STOP = set(("a an and are as at be by for from has have i in is it its of on or that the to with your you we our their they them this those these").split())
def _top_keywords(text: str, k: int = 12):
    words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
    words = [w for w in words if w not in STOP and len(w) > 2]
    return [w for (w, _cnt) in Counter(words).most_common(k)]

@router.get("/summary")
def profile_summary(user=Depends(get_current_user)):
    uid = user["id"]

    # base join: users + profiles + linkedin_profile + resume presence
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT
                u.name, u.email,
                p.headline, p.bio, p.industries, p.goals, p.tone, p.keywords,
                lp.li_id, lp.first_name, lp.last_name, lp.picture_url, lp.email AS li_email,
                EXISTS(SELECT 1 FROM resume_texts r WHERE r.user_id=%s) AS has_resume
              FROM users u
              LEFT JOIN profiles p ON p.user_id = u.id
              LEFT JOIN linkedin_profile lp ON lp.user_id = u.id
              WHERE u.id=%s
            """, (uid, uid))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Profile not found")
    finally:
        put_conn(conn)

    (u_name, _u_email,
     headline, bio, industries, goals, tone, keywords,
     li_id, first_name, last_name, picture_url, li_email,
     has_resume) = row

    name = (f"{first_name or ''} {last_name or ''}").strip() or u_name
    industries = industries or []
    tone = tone or []
    keywords = keywords or []

    # derive keywords if missing (resume + bio + headline)
    pile = " ".join(filter(None, [_latest_resume_text(uid), bio, headline]))
    if not keywords and pile:
        keywords = _top_keywords(pile, 12)

    seed = (
        f"You are writing a LinkedIn post for {name}. "
        f"Industries: {', '.join(industries) or 'General'}. "
        f"Keywords: {', '.join(keywords[:10])}. "
        f"Tone: {', '.join(tone) or 'professional, friendly'}. "
        f"Keep it concise and engaging for the target audience."
    )

    return {
        "background": {
            "name": name,
            "headline": headline,
            "industries": industries,
            "keywords": keywords,
            "tone": tone,
            "li_id": li_id,
            "has_resume": bool(has_resume),
            "picture_url": picture_url,
            "li_email": li_email,
        },
        "prompt_seed": seed
    }
