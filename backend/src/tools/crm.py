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
    "shipping_addresses": [],   # list of dicts: {label, address, city, is_default}
    "notes": "",
}


def merge_crm(existing: dict, updates: dict) -> dict:
    """
    Merge *updates* into *existing* CRM dict.
    Rules:
      - Scalar fields: new value replaces old (truthy wins).
      - List fields (except shipping_addresses): union (deduplicated, order preserved).
      - shipping_addresses: merge by label or append new; mark is_default if specified.
      - Empty / None updates are ignored.
    """
    merged = {**EMPTY_CRM, **existing}

    for key, new_val in updates.items():
        if key not in merged:
            merged[key] = new_val
            continue

        old_val = merged[key]

        # ── shipping_addresses: smart merge by label ────────────────
        if key == "shipping_addresses":
            if not isinstance(new_val, list):
                continue
            existing_addresses = merged.get("shipping_addresses", [])
            existing_labels = {a.get("label", "").lower() for a in existing_addresses if isinstance(a, dict)}

            for new_addr in new_val:
                if not isinstance(new_addr, dict):
                    continue
                label = new_addr.get("label", "").lower()
                if label and label in existing_labels:
                    # Update existing entry
                    for i, addr in enumerate(existing_addresses):
                        if isinstance(addr, dict) and addr.get("label", "").lower() == label:
                            existing_addresses[i] = {**addr, **new_addr}
                else:
                    existing_addresses.append(new_addr)
                    if label:
                        existing_labels.add(label)

            # Enforce single default: last one marked wins
            has_default = any(a.get("is_default") for a in existing_addresses if isinstance(a, dict))
            if not has_default and existing_addresses:
                existing_addresses[0]["is_default"] = True

            merged["shipping_addresses"] = existing_addresses
            continue

        # ── Regular list fields → union ─────────────────────────────
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

        # ── Scalar fields → replace if new value is truthy ─────────
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
    if crm.get("shipping_addresses"):
        addrs = crm["shipping_addresses"]
        default = next((a for a in addrs if isinstance(a, dict) and a.get("is_default")), None)
        if default:
            parts = [v for k, v in default.items() if k not in ("is_default", "label") and v]
            lines.append(f"  Default Ship-To ({default.get('label', 'home')}): {', '.join(parts)}")
        if len(addrs) > 1:
            lines.append(f"  Saved Addresses: {len(addrs)} total")
    if crm.get("notes"):
        lines.append(f"  Notes: {crm['notes']}")

    return "\n".join(lines) + "\n"
