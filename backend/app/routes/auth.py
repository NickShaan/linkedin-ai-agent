from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas import SignupIn, LoginIn, AuthOut  # use AuthOut
from app.auth_utils import hash_password, verify_password, create_access_token
from app.db import get_conn, put_conn
from app.deps import get_current_user
import time, logging

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("auth")

@router.post("/signup", response_model=AuthOut)   # <-- use AuthOut
def signup(payload: SignupIn):
    t0 = time.perf_counter()
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT email, linkedin_id FROM users WHERE email=%s OR linkedin_id=%s",
                    (payload.email, payload.linkedin_id),
                )
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Already exists")

                cur.execute("""
                  INSERT INTO users (name,email,country_code,mobile,linkedin_id,password_hash)
                  VALUES (%s,%s,%s,%s,%s,%s)
                  RETURNING id
                """, (payload.name, payload.email, payload.country_code, payload.mobile,
                      payload.linkedin_id, hash_password(payload.password)))
                user_id = cur.fetchone()[0]

        token = create_access_token(str(user_id))
        log.info("SIGNUP ok user_id=%s (%.1f ms)", user_id, (time.perf_counter()-t0)*1000)
        # include message
        return {"access_token": token, "token_type": "bearer", "message": "Account created successfully"}
    finally:
        put_conn(conn)

@router.post("/login", response_model=AuthOut)    # <-- use AuthOut
def login(payload: LoginIn):
    t0 = time.perf_counter()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE email=%s", (payload.email,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            user_id, pw_hash = row
            if not verify_password(payload.password, pw_hash):
                raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token(str(user_id))
        log.info("LOGIN ok user_id=%s (%.1f ms)", user_id, (time.perf_counter()-t0)*1000)
        # include message
        return {"access_token": token, "token_type": "bearer", "message": "Loged in successfully"}
    finally:
        put_conn(conn)

@router.get("/me")
def me(user = Depends(get_current_user)):
    print("[/auth/me] ✅ user =", user)
    uid = user["id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id, name, email, country_code, mobile, linkedin_id, is_active,
                    COALESCE(onboarded, FALSE)
                FROM users
                WHERE id = %s
            """, (uid,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            return {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "country_code": row[3],
                "mobile": row[4],
                "linkedin_id": row[5],
                "is_active": row[6],
                "onboarded": bool(row[7]),
            }
    finally:
        put_conn(conn)
