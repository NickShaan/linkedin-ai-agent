# app/deps.py
import os
from fastapi import Header, HTTPException
from jose import jwt, JWTError
from app.db import get_conn, put_conn

JWT_SECRET = os.getenv("JWT_SECRET", "changeme")
JWT_ALG = os.getenv("JWT_ALGORITHM", "HS256")

def get_current_user(authorization: str | None = Header(default=None)):
    # 0) Did the header arrive?
    if not authorization:
        print("[AUTH] ❌ No Authorization header")
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        print(f"[AUTH] ❌ Not Bearer: {authorization[:30]}...")
        raise HTTPException(status_code=401, detail="Invalid auth scheme")

    token = authorization.split(" ", 1)[1]
    print(f"[AUTH] ✅ Bearer token len={len(token)} prefix={token[:16]}...")

    # 1) Decode JWT
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        print("[AUTH] ✅ Decoded payload:", payload)
    except JWTError as e:
        print("[AUTH] ❌ JWT decode error:", repr(e))
        raise HTTPException(status_code=401, detail="Invalid token")

    # 2) Normalize sub → int user_id
    sub = payload.get("sub")
    print("[AUTH] sub(raw)=", sub, type(sub))
    user_id = None
    try:
        # expected: sub is number or numeric string
        user_id = int(sub)
    except Exception:
        # fallback if someone accidentally put {"sub": id}
        if isinstance(sub, dict) and "sub" in sub:
            try:
                user_id = int(sub["sub"])
                print("[AUTH] ⚠️ Nested sub fixed →", user_id)
            except Exception:
                pass

    if not isinstance(user_id, int):
        print("[AUTH] ❌ Could not extract numeric user_id from sub")
        raise HTTPException(status_code=401, detail="Invalid token subject")

    # 3) Load user
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, email FROM users WHERE id=%s AND is_active=TRUE", (user_id,))
            row = cur.fetchone()
            if not row:
                print(f"[AUTH] ❌ No active user id={user_id}")
                raise HTTPException(status_code=401, detail="User not found")
            user = {"id": row[0], "name": row[1], "email": row[2]}
            print("[AUTH] ✅ Current user:", user)
            return user
    finally:
        put_conn(conn)
