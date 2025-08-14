# app/jobs/scheduler.py
import asyncio, os, logging
from app.db import get_conn, put_conn
from app.services.linkedin_publish import publish_to_linkedin
from app.routes.content import _get_li_token_and_id  # reuse token/id helper
import requests

POLL_SEC = int(os.getenv("SCHEDULER_POLL_SECONDS", "10"))
BATCH = int(os.getenv("SCHEDULER_BATCH_LIMIT", "10"))
log = logging.getLogger("scheduler")

async def run_scheduled_poster():
    while True:
        try:
            # fetch due jobs
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, user_id, text
                        FROM scheduled_posts
                        WHERE status='queued' AND scheduled_at <= now()
                        ORDER BY scheduled_at ASC
                        LIMIT %s
                    """, (BATCH,))
                    jobs = cur.fetchall()
            finally:
                put_conn(conn)

            if not jobs:
                await asyncio.sleep(POLL_SEC)
                continue

            for sp_id, user_id, text in jobs:
                try:
                    # mark posting
                    conn = get_conn()
                    try:
                        with conn, conn.cursor() as cur:
                            cur.execute("UPDATE scheduled_posts SET status='posting', updated_at=now() WHERE id=%s", (sp_id,))
                    finally:
                        put_conn(conn)

                    urn = publish_to_linkedin(user_id, text)

                    # mark posted
                    conn = get_conn()
                    try:
                        with conn, conn.cursor() as cur:
                            cur.execute("UPDATE scheduled_posts SET status='posted', updated_at=now() WHERE id=%s", (sp_id,))
                    finally:
                        put_conn(conn)

                    log.info("✅ Posted scheduled_post id=%s urn=%s", sp_id, urn)

                except Exception as e:
                    # mark failed
                    conn = get_conn()
                    try:
                        with conn, conn.cursor() as cur:
                            cur.execute("UPDATE scheduled_posts SET status='failed', updated_at=now() WHERE id=%s", (sp_id,))
                    finally:
                        put_conn(conn)
                    log.exception("❌ Failed scheduled_post id=%s: %s", sp_id, e)

        except Exception as outer:
            log.exception("Scheduler loop error: %s", outer)

        await asyncio.sleep(POLL_SEC)

def _publish_to_linkedin(uid: int, text: str, visibility: str = "PUBLIC") -> str:
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
    if r.status_code not in (200, 201):
        raise RuntimeError(f"LinkedIn publish failed: {r.status_code} {r.text}")
    return r.headers.get("x-restli-id") or r.headers.get("location", "")

async def run_scheduled_poster():
    log.info("📆 Scheduler started (poll=%ss, batch=%s)", POLL_SEC, BATCH)
    while True:
        try:
            # 1) fetch due jobs
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, user_id, text
                        FROM scheduled_posts
                        WHERE status='queued' AND scheduled_at <= now()
                        ORDER BY scheduled_at ASC
                        LIMIT %s
                    """, (BATCH,))
                    jobs = cur.fetchall()
            finally:
                put_conn(conn)

            if not jobs:
                await asyncio.sleep(POLL_SEC)
                continue

            for sp_id, user_id, text in jobs:
                try:
                    # mark posting
                    conn = get_conn()
                    try:
                        with conn, conn.cursor() as cur:
                            cur.execute("UPDATE scheduled_posts SET status='posting', updated_at=now() WHERE id=%s", (sp_id,))
                    finally:
                        put_conn(conn)

                    urn = _publish_to_linkedin(user_id, text)

                    # mark posted
                    conn = get_conn()
                    try:
                        with conn, conn.cursor() as cur:
                            cur.execute("UPDATE scheduled_posts SET status='posted', updated_at=now() WHERE id=%s", (sp_id,))
                    finally:
                        put_conn(conn)

                    log.info("✅ Posted scheduled_post id=%s urn=%s", sp_id, urn)

                except Exception as e:
                    # mark failed
                    conn = get_conn()
                    try:
                        with conn, conn.cursor() as cur:
                            cur.execute("UPDATE scheduled_posts SET status='failed', updated_at=now() WHERE id=%s", (sp_id,))
                    finally:
                        put_conn(conn)
                    log.exception("❌ Failed scheduled_post id=%s: %s", sp_id, e)

        except Exception as outer:
            log.exception("Scheduler loop error: %s", outer)

        await asyncio.sleep(POLL_SEC)
