# app/services/linkedin_publish.py
import requests
from datetime import datetime, timezone
from fastapi import HTTPException
from app.db import get_conn, put_conn

def _get_li_token_and_id(uid: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT access_token, expires_at FROM tokens_linkedin WHERE user_id=%s", (uid,))
            trow = cur.fetchone()
            if not trow:
                raise HTTPException(409, "LinkedIn not connected")
            access_token, expires_at = trow
            if expires_at and expires_at < datetime.now(timezone.utc):
                raise HTTPException(401, "LinkedIn token expired. Reconnect.")

            cur.execute("SELECT li_id FROM linkedin_profile WHERE user_id=%s", (uid,))
            prow = cur.fetchone()
            if not prow or not prow[0]:
                raise HTTPException(409, "No LinkedIn profile li_id stored")
            li_id = prow[0]
    finally:
        put_conn(conn)
    return access_token, li_id

def publish_to_linkedin(uid: int, text: str, visibility: str = "PUBLIC") -> str:
    access_token, li_id = _get_li_token_and_id(uid)
    author_urn = f"urn:li:person:{li_id}"

    url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    body = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility
        },
    }

    r = requests.post(url, headers=headers, json=body, timeout=20)
    if r.status_code not in (201, 200):
        raise HTTPException(status_code=502, detail=f"LinkedIn publish failed: {r.status_code} {r.text}")

    return r.headers.get("x-restli-id") or r.headers.get("location", "")
