"""
crm.py — CRM formatting subsystem.

NOT an orchestrator tool. This module formats the user's CRM profile into
a system-prompt injection block so the Chat LLM has full customer context
without any tool call overhead.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Default empty CRM skeleton ──────────────────────────────────────
EMPTY_CRM: dict = {
    "name": "",
    "location": "",
    "budget_range": "",
    "preferred_categories": [],
    "preferred_brands": [],
    "language_preference": "",
    "notes": "",
}


def merge_crm(existing: dict, updates: dict) -> dict:
    """
    Merge *updates* into *existing* CRM dict.
    Rules:
      - Scalar fields: new value replaces old (truthy wins).
      - List fields: union (deduplicated, order preserved).
      - Empty / None updates are ignored.
    """
    merged = {**EMPTY_CRM, **existing}

    for key, new_val in updates.items():
        if key not in merged:
            merged[key] = new_val
            continue

        old_val = merged[key]

        # List fields → union
        if isinstance(old_val, list):
            if isinstance(new_val, list):
                seen = set(old_val)
                for item in new_val:
                    if item and item not in seen:
                        old_val.append(item)
                        seen.add(item)
            elif new_val:
                if new_val not in old_val:
                    old_val.append(new_val)
            continue

        # Scalar fields → replace if new value is truthy
        if new_val:
            merged[key] = new_val

    return merged


def format_crm_block(crm: dict) -> str:
    """
    Render a CRM dict into a concise block for system-prompt injection.
    Returns empty string if CRM is entirely blank.
    """
    if not crm or all(not v for v in crm.values()):
        return ""

    lines = ["[Customer Profile]"]

    if crm.get("name"):
        lines.append(f"  Name: {crm['name']}")
    if crm.get("location"):
        lines.append(f"  Location: {crm['location']}")
    if crm.get("budget_range"):
        lines.append(f"  Budget: {crm['budget_range']}")
    if crm.get("preferred_categories"):
        lines.append(f"  Interests: {', '.join(crm['preferred_categories'])}")
    if crm.get("preferred_brands"):
        lines.append(f"  Brands: {', '.join(crm['preferred_brands'])}")
    if crm.get("language_preference"):
        lines.append(f"  Language: {crm['language_preference']}")
    if crm.get("notes"):
        lines.append(f"  Notes: {crm['notes']}")

    return "\n".join(lines) + "\n"
