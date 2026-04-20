# =============================================================================
# tests/test_integration.py
# Integration tests for the full turn lifecycle over WebSocket.
# Run with: pytest tests/test_integration.py -v
#
# These tests require the backend server to be running OR use TestClient
# with the FastAPI app object directly (in-process, no real LLM needed).
#
# The LLM is stubbed via monkeypatching so tests run without GPU/model files.
# =============================================================================

import asyncio
import json
import os
import sys
import uuid

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# ---------------------------------------------------------------------------
# Stub the heavy model imports before anything in src is loaded
# ---------------------------------------------------------------------------
import unittest.mock as mock

# Stub moonshine, piper, llama_cpp so the engine module loads without hardware
sys.modules.setdefault("moonshine_onnx",  mock.MagicMock())
sys.modules.setdefault("piper",           mock.MagicMock())
sys.modules.setdefault("llama_cpp",       mock.MagicMock())

# Stub chromadb + sentence_transformers used by retriever
sys.modules.setdefault("chromadb",                    mock.MagicMock())
sys.modules.setdefault("chromadb.config",             mock.MagicMock())
sys.modules.setdefault("sentence_transformers",       mock.MagicMock())

from httpx import AsyncClient, ASGITransport
from src.main import app
from src.conversation.compaction import CLEARED_PLACEHOLDER
from src.conversation.memory import get_or_create_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
TEST_USERNAME = f"testuser_{uuid.uuid4().hex[:8]}"
TEST_EMAIL    = f"{TEST_USERNAME}@test.example"
TEST_PASSWORD = "TestPass123"


@pytest_asyncio.fixture
async def client():
    """In-process async HTTP client wrapping the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def auth_token(client):
    """
    Register a new test user and return a valid JWT access token.
    Each test run uses a fresh user to avoid state pollution.
    """
    username = f"tuser_{uuid.uuid4().hex[:6]}"
    email    = f"{username}@test.example"

    reg = await client.post("/auth/register", json={
        "username": username,
        "email":    email,
        "password": TEST_PASSWORD,
    })
    assert reg.status_code == 200, f"Registration failed: {reg.text}"

    login = await client.post("/auth/login", json={
        "username": username,
        "password": TEST_PASSWORD,
    })
    assert login.status_code == 200, f"Login failed: {login.text}"
    return login.json()["access_token"]


@pytest_asyncio.fixture
async def auth_user_id(client, auth_token):
    """Decode the user_id from the token without a full JWT library call."""
    import base64
    payload_b64 = auth_token.split(".")[1]
    padding = 4 - len(payload_b64) % 4
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * padding))
    return payload["sub"]


# ---------------------------------------------------------------------------
# Auth endpoint tests
# ---------------------------------------------------------------------------
class TestAuth:

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        username = f"u_{uuid.uuid4().hex[:8]}"
        resp = await client.post("/auth/register", json={
            "username": username,
            "email":    f"{username}@example.com",
            "password": TEST_PASSWORD,
        })
        assert resp.status_code == 200
        assert "user_id" in resp.json()

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client, auth_token):
        """Re-registering the same username must return 409."""
        # We need to know the username — create a known one
        uname = f"dup_{uuid.uuid4().hex[:6]}"
        await client.post("/auth/register", json={
            "username": uname, "email": f"{uname}@x.com", "password": TEST_PASSWORD
        })
        resp = await client.post("/auth/register", json={
            "username": uname, "email": f"other_{uname}@x.com", "password": TEST_PASSWORD
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_weak_password_rejected(self, client):
        resp = await client.post("/auth/register", json={
            "username": "weakpwuser", "email": "weak@x.com", "password": "short"
        })
        assert resp.status_code == 422
        body = resp.json()
        assert "password_errors" in body.get("detail", {})

    @pytest.mark.asyncio
    async def test_register_no_uppercase_rejected(self, client):
        resp = await client.post("/auth/register", json={
            "username": "noupperuser", "email": "nou@x.com", "password": "alllowercase1"
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, auth_token, auth_user_id):
        """Wrong password must return 401 with remaining attempts in message."""
        uname = f"wlp_{uuid.uuid4().hex[:6]}"
        await client.post("/auth/register", json={
            "username": uname, "email": f"{uname}@x.com", "password": TEST_PASSWORD
        })
        resp = await client.post("/auth/login", json={
            "username": uname, "password": "WrongPass999"
        })
        assert resp.status_code == 401
        assert "attempt" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_unknown_user(self, client):
        resp = await client.post("/auth/login", json={
            "username": "nobody_xyz_abc", "password": TEST_PASSWORD
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self, client):
        resp = await client.post("/auth/logout")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Memory lifecycle tests (in-process, LLM calls stubbed)
# ---------------------------------------------------------------------------
class TestMemoryLifecycle:

    @pytest.mark.asyncio
    async def test_session_created_with_user_id(self, auth_user_id):
        """get_or_create_session must embed user_id on session creation."""
        sid = str(uuid.uuid4())
        session = get_or_create_session(sid, user_id=auth_user_id)
        assert session["user_id"] == auth_user_id

    @pytest.mark.asyncio
    async def test_session_backfills_user_id(self, auth_user_id):
        """If an existing anonymous session is fetched with user_id, it must be backfilled."""
        sid = str(uuid.uuid4())
        anon = get_or_create_session(sid)
        assert anon["user_id"] is None

        authed = get_or_create_session(sid, user_id=auth_user_id)
        assert authed["user_id"] == auth_user_id

    @pytest.mark.asyncio
    async def test_micro_compact_after_add_message(self, auth_user_id):
        """
        After appending a (fake) tool message then an assistant message,
        apply_micro_compact must clear the tool result.
        """
        from src.conversation.memory import add_message_to_chat, apply_micro_compact

        sid = str(uuid.uuid4())
        get_or_create_session(sid, user_id=auth_user_id)

        # Simulate a tool message being added (direct history manipulation)
        from src.conversation.memory import get_or_create_session as goc, _save_to_redis
        session = goc(sid)
        session["history"].append({
            "role": "tool", "name": "retrieve_documents",
            "tool_call_id": "tc_test", "content": "Big RAG result " * 100,
        })
        session["history"].append({
            "role": "assistant", "content": "Based on those results, here are phones…",
        })
        _save_to_redis(sid, session)

        apply_micro_compact(sid)

        session = goc(sid)
        tool_msgs = [m for m in session["history"] if m.get("role") == "tool"]
        assert all(m["content"] == CLEARED_PLACEHOLDER for m in tool_msgs), \
            "All consumed tool results must be cleared after apply_micro_compact"


# ---------------------------------------------------------------------------
# CRM tests
# ---------------------------------------------------------------------------
class TestCRM:

    @pytest.mark.asyncio
    async def test_get_profile_returns_none_for_new_user(self, auth_user_id):
        """A freshly registered user may have an empty CRM profile."""
        from src.tools.crm import get_profile
        # upsert_crm_profile was called with {} on register — profile exists but empty
        profile = await get_profile(auth_user_id)
        # Either None or an empty dict is acceptable
        if profile:
            assert isinstance(profile, dict)

    @pytest.mark.asyncio
    async def test_update_and_retrieve_profile(self, auth_user_id):
        from src.tools.crm import update_profile, get_profile
        await update_profile(auth_user_id, {
            "name":                "Test User",
            "preferred_categories": ["phones", "laptops"],
            "budget_range":        "under 30000 PKR",
        })
        profile = await get_profile(auth_user_id)
        assert profile is not None
        assert profile["name"] == "Test User"
        assert "phones" in profile["preferred_categories"]
        assert profile["budget_range"] == "under 30000 PKR"

    @pytest.mark.asyncio
    async def test_profile_lists_are_merged_not_overwritten(self, auth_user_id):
        from src.tools.crm import update_profile, get_profile
        await update_profile(auth_user_id, {"liked_brands": ["Samsung"]})
        await update_profile(auth_user_id, {"liked_brands": ["Apple"]})
        profile = await get_profile(auth_user_id)
        brands = profile.get("liked_brands", [])
        assert "Samsung" in brands
        assert "Apple"   in brands

    @pytest.mark.asyncio
    async def test_crm_context_block_non_empty_for_known_user(self, auth_user_id):
        from src.tools.crm import update_profile, get_profile, build_crm_context_block
        await update_profile(auth_user_id, {
            "name": "Ali", "budget_range": "under 20000 PKR"
        })
        profile = await get_profile(auth_user_id)
        block = build_crm_context_block(profile)
        assert "Ali" in block
        assert "20000" in block

    @pytest.mark.asyncio
    async def test_crm_context_block_empty_for_missing_profile(self):
        from src.tools.crm import build_crm_context_block
        block = build_crm_context_block(None)
        assert block == ""


# ---------------------------------------------------------------------------
# Database access layer tests
# ---------------------------------------------------------------------------
class TestDB:

    @pytest.mark.asyncio
    async def test_create_and_fetch_user(self):
        from src import db
        uname = f"dbtest_{uuid.uuid4().hex[:6]}"
        email = f"{uname}@test.com"
        uid   = await db.create_user(uname, email, "fakehash")
        assert uid is not None
        user = await db.get_user_by_username(uname)
        assert user is not None
        assert user["id"] == uid
        assert user["username"] == uname

    @pytest.mark.asyncio
    async def test_upsert_crm_profile(self):
        from src import db
        uname = f"crmtest_{uuid.uuid4().hex[:6]}"
        uid   = await db.create_user(uname, f"{uname}@x.com", "hash")
        await db.upsert_crm_profile(uid, {"name": "DB Test", "budget_range": "5000"})
        profile = await db.get_crm_profile(uid)
        assert profile["name"] == "DB Test"
        assert profile["budget_range"] == "5000"

    @pytest.mark.asyncio
    async def test_save_and_load_session_memory(self):
        from src import db
        sid  = str(uuid.uuid4())
        msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        await db.save_session_memory(sid, "uid-x", msgs, turn_count=1)
        loaded = await db.load_session_memory(sid)
        assert loaded is not None
        assert loaded["messages"] == msgs
        assert loaded["turn_count"] == 1

    @pytest.mark.asyncio
    async def test_log_compaction(self):
        from src import db
        # Should not raise
        await db.log_compaction("sid-test", "uid-test", "auto", 1000, 200)

    @pytest.mark.asyncio
    async def test_insert_benchmark(self):
        from src import db
        await db.insert_benchmark("test_query", "latency_ms", 250.5, session_id=None, notes="test")
        history = await db.get_benchmark_history(limit=10)
        assert any(r["test_name"] == "test_query" for r in history)

    @pytest.mark.asyncio
    async def test_lockout_after_max_failed_attempts(self):
        from src import db
        uname = f"lock_{uuid.uuid4().hex[:6]}"
        uid   = await db.create_user(uname, f"{uname}@x.com", "hash")
        for _ in range(5):
            await db.update_login_attempt(uid, success=False, max_attempts=5, lockout_minutes=15)
        user = await db.get_user_by_id(uid)
        assert user["locked_until"] is not None, "Account must be locked after 5 failures"

    @pytest.mark.asyncio
    async def test_unlock_clears_lockout(self):
        from src import db
        uname = f"unlock_{uuid.uuid4().hex[:6]}"
        uid   = await db.create_user(uname, f"{uname}@x.com", "hash")
        for _ in range(5):
            await db.update_login_attempt(uid, success=False, max_attempts=5)
        await db.unlock_user(uid)
        user = await db.get_user_by_id(uid)
        assert user["locked_until"] is None
        assert user["failed_attempts"] == 0
