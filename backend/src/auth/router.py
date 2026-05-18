"""
auth/router.py — Barebones auth: /login, /register, /logout.

No JWTs, no middleware, no bcrypt hashing.
Only validation: password length <= 20.
Admin bypass: username=admin, password=admin123.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import db
from conversation import memory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None  # accepted but ignored (frontend sends it)


class AuthResponse(BaseModel):
    user_id: str
    username: str
    message: str


# ── REGISTER ────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    logger.info(f"[auth] Register attempt: {req.username}")

    if not req.username or not req.password:
        raise HTTPException(400, "Username and password required.")
    if len(req.password) > 20:
        raise HTTPException(400, "Password must be 20 characters or fewer.")

    existing = await db.get_user_by_username(req.username)
    if existing:
        raise HTTPException(409, "Username already taken.")

    user_id = await db.create_user(req.username, req.password)
    await db.upsert_crm(user_id, {})

    logger.info(f"[auth] Registered: {req.username} → {user_id}")
    return AuthResponse(user_id=user_id, username=req.username, message="Registered successfully.")


# ── LOGIN ───────────────────────────────────────────────────────────

@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    logger.info(f"[auth] Login attempt: {req.username}")

    # Admin bypass
    if req.username == "admin" and req.password == "admin123":
        admin = await db.get_user_by_username("admin")
        if not admin:
            admin_id = await db.create_user("admin", "admin123")
            await db.upsert_crm(admin_id, {})
        else:
            admin_id = admin["user_id"]

        bulk = await db.load_user_context_bulk(admin_id)
        memory.hydrate_user(admin_id, bulk)

        logger.info(f"[auth] Admin login → {admin_id}")
        return AuthResponse(user_id=admin_id, username="admin", message="Admin login.")

    # Normal login
    user = await db.get_user_by_username(req.username)
    if not user:
        raise HTTPException(401, "User not found.")
    if user["password"] != req.password:
        raise HTTPException(401, "Wrong password.")

    # Login hook: hydrate RAM
    bulk = await db.load_user_context_bulk(user["user_id"])
    memory.hydrate_user(user["user_id"], bulk)

    logger.info(f"[auth] Login: {req.username} → {user['user_id']}")
    return AuthResponse(
        user_id=user["user_id"],
        username=user["username"],
        message="Login successful.",
    )


# ── LOGOUT (no-op, frontend expects it) ─────────────────────────────

@router.post("/logout")
async def logout():
    logger.info("[auth] Logout called (no-op)")
    return {"message": "Logged out."}
