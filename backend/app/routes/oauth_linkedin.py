# app/routes/oauth_linkedin.py
import os
import time
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional
from psycopg2.extras import Json

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from app.deps import get_current_user
from app.db import get_conn, put_conn
from app.auth_utils import hash_password, create_access_token

router = APIRouter(prefix="/oauth/linkedin", tags=["oauth"])
IST = timezone(timedelta(hours=5, minutes=30))

# ----- LinkedIn OAuth/OIDC endpoints -----
AUTH_URL  = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
ME_URL    = "https://api.linkedin.com/v2/userinfo"  # OIDC userinfo

# near the top
_raw_scopes = os.getenv("OAUTH_SCOPES", "openid profile email w_member_social")
SCOPES = _raw_scopes.split()
print("[OAUTH] Using scopes =", SCOPES)



CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("BACKEND_BASE_URL", "http://localhost:8000") + os.getenv(
    "OAUTH_REDIRECT_PATH", "/oauth/linkedin/callback"
)

# Frontend bridge (Angular route that stores the JWT, then navigates to /app)
BRIDGE_FRONTEND = os.getenv("FRONTEND_BRIDGE_URL", "http://localhost:4200/oauth-bridge")

# Fast login: on repeated sign-ins (public flow), skip heavy profile writes (only refresh token)
FAST_LOGIN_MIN_SAVE = os.getenv("LI_FAST_LOGIN_MIN_SAVE", "true").lower() in ("1", "true", "yes")

# ---------- ephemeral state cache: state -> (user_id_from_state, exp_ts) ----------
_STATE_CACHE: dict[str, tuple[int, float]] = {}


def _put_state(state: str, user_id: int, ttl: int = 600) -> None:
    print(f"[OAUTH] Caching state={state} for user_id={user_id}")
    _STATE_CACHE[state] = (user_id, time.time() + ttl)


def _pop_state(state: str) -> Optional[int]:
    tup = _STATE_CACHE.pop(state, None)
    if not tup:
        print(f"[OAUTH] State {state} not found")
        return None
    uid, exp = tup
    if exp <= time.time():
        print(f"[OAUTH] State {state} expired")
        return None
    print(f"[OAUTH] Popped state={state} for user_id={uid}")
    return uid


# ----------------------------- DB helpers -----------------------------
def _get_existing_user_id_by_li_or_email(li_id: Optional[str], email: Optional[str]) -> Optional[int]:
    """Find an existing user via linkedin_profile.li_id first; fallback to users.email."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if li_id:
                cur.execute("SELECT user_id FROM linkedin_profile WHERE li_id=%s", (li_id,))
                r = cur.fetchone()
                if r:
                    return r[0]
            if email:
                cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                r = cur.fetchone()
                if r:
                    return r[0]
        return None
    finally:
        put_conn(conn)


# at the top of the file (keep your other imports)
from datetime import datetime, timedelta, timezone
IST = timezone(timedelta(hours=5, minutes=30))

def _save_token_only(user_id: int, access_token: str, expires_in: int) -> None:
    expires_at = datetime.now(IST) + timedelta(seconds=expires_in or 3600)
    print(f"[DB] Upserting tokens_linkedin uid={user_id} expires_at(IST)={expires_at.isoformat()}")
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tokens_linkedin (user_id, access_token, expires_at)
                VALUES (%s,%s,%s)
                ON CONFLICT (user_id) DO UPDATE
                SET access_token=EXCLUDED.access_token,
                    expires_at=EXCLUDED.expires_at,
                    updated_at=now()
                """,
                (user_id, access_token, expires_at),
            )
    finally:
        put_conn(conn)



def _create_user_with_li(ui: dict, access_token: str, expires_in: int) -> int:
    """Create user once, save initial linkedin_profile, and persist token."""
    li_id = ui.get("sub")
    fname = ui.get("given_name") or ""
    lname = ui.get("family_name") or ""
    email = ui.get("email")
    pic = ui.get("picture")
    name = (f"{fname} {lname}").strip() or (email.split("@")[0] if email else "LinkedIn User")

    rnd = secrets.token_urlsafe(12)
    pwd_hash = hash_password(rnd)

    print(f"[DB] Creating new user name={name}, email={email}")
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # users (unique by email)
                cur.execute(
                    """
                    INSERT INTO users (name, email, country_code, mobile, linkedin_id, password_hash, is_active)
                    VALUES (%s,%s,%s,%s,%s,%s,TRUE)
                    ON CONFLICT (email) DO UPDATE SET linkedin_id=EXCLUDED.linkedin_id
                    RETURNING id
                    """,
                    (name, email, "+1", "", li_id, pwd_hash),
                )
                user_id = cur.fetchone()[0]

                # linkedin_profile
                print(f"[DB] Upserting linkedin_profile for user_id={user_id}")
                cur.execute(
                    """
                    INSERT INTO linkedin_profile (user_id, li_id, first_name, last_name, picture_url, email, raw_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET li_id=EXCLUDED.li_id,
                        first_name=EXCLUDED.first_name,
                        last_name=EXCLUDED.last_name,
                        picture_url=EXCLUDED.picture_url,
                        email=EXCLUDED.email,
                        raw_json=EXCLUDED.raw_json,
                        fetched_at=now()
                    """,
                    (user_id, li_id, fname, lname, pic, email, Json(ui)),
                )
    finally:
        put_conn(conn)

    _save_token_only(user_id, access_token, expires_in)
    return user_id


def _link_li_to_logged_in_user(current_user_id: int, ui: dict, access_token: str, expires_in: int) -> int:
    """Link LinkedIn account to an already-logged-in app user (start-url flow)."""
    li_id = ui.get("sub")
    fname = ui.get("given_name") or ""
    lname = ui.get("family_name") or ""
    email = ui.get("email")
    pic = ui.get("picture")

    # Prevent linking the same LinkedIn account to a different existing user
    existing_uid = _get_existing_user_id_by_li_or_email(li_id, None)
    if existing_uid and existing_uid != current_user_id:
        raise HTTPException(status_code=409, detail="This LinkedIn account is already linked to another user.")

    print(f"[DB] Linking LinkedIn -> user_id={current_user_id}")
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # ensure users.email reflects latest (optional)
                if email:
                    cur.execute(
                        "UPDATE users SET linkedin_id=%s, updated_at=now() WHERE id=%s",
                        (li_id, current_user_id),
                    )

                # upsert linkedin_profile for this user
                cur.execute(
                    """
                    INSERT INTO linkedin_profile (user_id, li_id, first_name, last_name, picture_url, email, raw_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET li_id=EXCLUDED.li_id,
                        first_name=EXCLUDED.first_name,
                        last_name=EXCLUDED.last_name,
                        picture_url=EXCLUDED.picture_url,
                        email=EXCLUDED.email,
                        raw_json=EXCLUDED.raw_json,
                        fetched_at=now()
                    """,
                    (current_user_id, li_id, fname, lname, pic, email, Json(ui)),
                )

    finally:
        put_conn(conn)

    _save_token_only(current_user_id, access_token, expires_in)
    return current_user_id


# ----------------------------- Routes -----------------------------
@router.get("/start-url")
def start_linkedin_oauth_url(user=Depends(get_current_user)):
    """Logged-in flow: link LinkedIn to the current app user."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="LinkedIn app not configured on server")
    state = secrets.token_urlsafe(24)
    _put_state(state, user["id"])  # logged-in flow
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state,
    }
    url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    print("[ROUTE] start-url (with JWT) ->", url)
    return JSONResponse({"url": url})


@router.get("/start-public")
def start_public_flow():
    """Public flow: sign in / sign up via LinkedIn (no app JWT yet)."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="LinkedIn app not configured on server")
    state = secrets.token_urlsafe(24)
    _put_state(state, 0)  # 0 => no current app user (public)
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state,
    }
    url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    print("[ROUTE] start-public (no JWT) ->", url)
    return JSONResponse({"url": url})


@router.get("/callback")
def linkedin_callback(code: Optional[str] = None, state: Optional[str] = None):
    """Handle both public and logged-in callbacks with fast-path."""
    print(f"[ROUTE] callback with code={code}, state={state}")
    user_id_from_state = _pop_state(state or "")
    if not code or state is None or user_id_from_state is None:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    # 1) Exchange code for token
    print("[OAUTH] Exchanging code for token...")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    t = requests.post(TOKEN_URL, data=data, timeout=20)
    print("[OAUTH] Token exchange status=", t.status_code)
    if t.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {t.text}")
    tok = t.json()
    access_token = tok["access_token"]
    expires_in = tok.get("expires_in", 3600)

    # 2) Fetch OIDC userinfo
    print("[OAUTH] Fetching OIDC /userinfo...")
    r = requests.get(ME_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=f"LinkedIn /userinfo failed: {r.text}")
    ui = r.json()
    print("[OAUTH] /userinfo JSON:", ui)

    li_id = ui.get("sub")
    email = ui.get("email")

    # 3) Public vs logged-in flow
    if user_id_from_state == 0:
        # PUBLIC: fast-path login
        existing_uid = _get_existing_user_id_by_li_or_email(li_id, email)
    if existing_uid:
        print(f"[OAUTH] Fast login for existing user_id={existing_uid}")
        # Always update the token, regardless of FAST_LOGIN_MIN_SAVE
        _save_token_only(existing_uid, access_token, expires_in)
        final_user_id = existing_uid
    else:
        print("[OAUTH] First-time LinkedIn user -> creating app user")
        final_user_id = _create_user_with_li(ui, access_token, expires_in)

    # 4) Mint app JWT & redirect to bridge
    jwt = create_access_token(str(final_user_id))
    redirect_url = f"{BRIDGE_FRONTEND}?linkedin=ok#token={jwt}"
    print("[OAUTH] Redirecting to:", redirect_url)
    return RedirectResponse(redirect_url, status_code=307)


@router.post("/sync")
def sync_linkedin(user=Depends(get_current_user)):
    """Refresh LinkedIn profile using stored access token (cheap check without OAuth)."""
    uid = user["id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT access_token, expires_at FROM tokens_linkedin WHERE user_id=%s", (uid,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="LinkedIn not connected. Start OAuth.")
            access_token, expires_at = row
    finally:
        put_conn(conn)

    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="LinkedIn token expired. Reconnect.")

    # Fetch fresh profile snapshot and upsert
    r = requests.get(ME_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail=f"LinkedIn token invalid: {r.text}")
    ui = r.json()

    li_id = ui.get("sub")
    fname = ui.get("given_name") or ""
    lname = ui.get("family_name") or ""
    email = ui.get("email")
    pic = ui.get("picture")

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO linkedin_profile (user_id, li_id, first_name, last_name, picture_url, email, raw_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (user_id) DO UPDATE
                SET li_id=EXCLUDED.li_id,
                    first_name=EXCLUDED.first_name,
                    last_name=EXCLUDED.last_name,
                    picture_url=EXCLUDED.picture_url,
                    email=EXCLUDED.email,
                    raw_json=EXCLUDED.raw_json,
                    fetched_at=now()
                """,
                (uid, li_id, fname, lname, pic, email, Json(ui)),
            )
    finally:
        put_conn(conn)

    return {"message": "LinkedIn profile refreshed", "profile": ui}


@router.get("/check")
def check_status(user=Depends(get_current_user)):
    """Lightweight status: is LinkedIn connected? returns li_id & token expiry."""
    uid = user["id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT li_id FROM linkedin_profile WHERE user_id=%s", (uid,))
            li = cur.fetchone()
            cur.execute("SELECT expires_at FROM tokens_linkedin WHERE user_id=%s", (uid,))
            tok = cur.fetchone()
            return {
                "connected": bool(li and li[0]),
                "li_id": li[0] if li else None,
                "expires_at": tok[0].isoformat() if tok and tok[0] else None,
            }
    finally:
        put_conn(conn)
