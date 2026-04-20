# =============================================================================
# backend/src/tools/crm.py
# CRM tool: get and upsert user profiles.
# This is the server-side implementation. user_id is ALWAYS injected from the
# authenticated session — the LLM never controls it.
# =============================================================================

import logging
from typing import Optional

from src import db

logger = logging.getLogger(__name__)


async def get_profile(user_id: str) -> Optional[dict]:
    """
    Fetch the CRM profile for user_id.
    Returns None if no profile exists yet.
    """
    return await db.get_crm_profile(user_id)


async def update_profile(user_id: str, updates: dict) -> None:
    """
    Merge updates into the existing CRM profile.
    List fields (preferred_categories, liked_brands, disliked_brands) are
    unioned with existing values. Scalar fields overwrite.
    """
    if not updates:
        return
    try:
        await db.upsert_crm_profile(user_id, updates)
        logger.info(f"[crm] Updated profile for {user_id}: {list(updates.keys())}")
    except Exception as e:
        logger.error(f"[crm] Failed to update profile for {user_id}: {e}")


def build_crm_context_block(profile: Optional[dict]) -> str:
    """
    Returns a compact string to inject at the top of the system prompt.
    Called by build_inference_payload() in memory.py when user_id is available.
    Returns empty string if no profile or profile is empty.
    """
    if not profile:
        return ""

    lines = []
    if profile.get("name"):
        lines.append(f"Name: {profile['name']}")
    if profile.get("preferred_categories"):
        cats = profile["preferred_categories"]
        if isinstance(cats, list):
            cats = ", ".join(cats)
        lines.append(f"Preferred categories: {cats}")
    if profile.get("budget_range"):
        lines.append(f"Budget range: {profile['budget_range']}")
    if profile.get("liked_brands"):
        brands = profile["liked_brands"]
        if isinstance(brands, list):
            brands = ", ".join(brands)
        lines.append(f"Liked brands: {brands}")
    if profile.get("disliked_brands"):
        brands = profile["disliked_brands"]
        if isinstance(brands, list):
            brands = ", ".join(brands)
        lines.append(f"Disliked brands: {brands}")
    if profile.get("last_session_summary"):
        lines.append(f"Last session summary: {profile['last_session_summary']}")
    if profile.get("notes"):
        lines.append(f"Notes: {profile['notes']}")

    if not lines:
        return ""

    return (
        "\n--- Returning Customer Context ---\n"
        + "\n".join(lines)
        + "\n----------------------------------\n"
    )


# ---------------------------------------------------------------------------
# Tool definitions — plug these into the tool registry
# ---------------------------------------------------------------------------
CRM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_crm_profile",
            "description": (
                "Retrieve the current user's shopping profile: preferred categories, "
                "budget range, liked/disliked brands, and past session notes. "
                "Call this when the user says they've used Daraz before, asks for "
                "personalized recommendations, or references past searches."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                # user_id injected server-side — LLM never sees it
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_crm_profile",
            "description": (
                "Update the user's shopping profile when they explicitly state a "
                "preference, correct an existing one, or provide personal details. "
                "Only call this for explicit statements — not inferences."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "object",
                        "description": (
                            "Fields to update. Valid keys: name, preferred_categories "
                            "(array of strings), budget_range (e.g. 'under 5000 PKR'), "
                            "liked_brands (array), disliked_brands (array), notes (string)."
                        ),
                    }
                },
                "required": ["updates"],
            },
        },
    },
]


async def handle_crm_tool(tool_name: str, args: dict, user_id: str, session: dict) -> str:
    """
    Dispatcher for CRM tool calls.
    user_id is ALWAYS from the authenticated session, never from LLM args.
    session is the current session dict (so we can rebuild the cached system prompt
    after an update).
    """
    if tool_name == "get_crm_profile":
        profile = await get_profile(user_id)
        if not profile:
            return "No profile on file for this user."
        parts = []
        if profile.get("name"):
            parts.append(f"name={profile['name']}")
        if profile.get("preferred_categories"):
            parts.append(f"preferred_categories={profile['preferred_categories']}")
        if profile.get("budget_range"):
            parts.append(f"budget={profile['budget_range']}")
        if profile.get("liked_brands"):
            parts.append(f"liked_brands={profile['liked_brands']}")
        if profile.get("notes"):
            parts.append(f"notes={profile['notes']}")
        return "User profile: " + ", ".join(parts) if parts else "Profile exists but is empty."

    elif tool_name == "update_crm_profile":
        updates = args.get("updates", {})
        if not isinstance(updates, dict):
            return "Error: 'updates' must be a JSON object."
        await update_profile(user_id, updates)
        # Signal to the session that the CRM context block needs rebuilding
        session["crm_dirty"] = True
        return f"Profile updated: {list(updates.keys())}"

    return f"Unknown CRM tool: {tool_name}"
