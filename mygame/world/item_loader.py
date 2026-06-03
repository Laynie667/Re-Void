"""
world/item_loader.py

Loads world/item_catalog.yaml and provides spawn_item() for staff use.

Usage (from in-game as superuser):
    @py from world.item_loader import spawn_item; spawn_item(me, "metal_plug")
    @py from world.item_loader import list_catalog; list_catalog(me)
    @py from world.item_loader import spawn_item; spawn_item(me, "magic_binding_leash")

The spawned item appears in the caller's inventory.
"""

import os
import random

_DATA = None


def _load():
    global _DATA
    if _DATA is None:
        path = os.path.join(os.path.dirname(__file__), "item_catalog.yaml")
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                _DATA = yaml.safe_load(f) or {}
        except Exception as e:
            from evennia.utils import logger
            logger.log_err(f"item_loader: failed to load {path}: {e}")
            _DATA = {}
    return _DATA


def _all_entries():
    """Return a flat dict of {key: entry} across all catalog categories."""
    data = _load()
    result = {}
    for category, items in data.items():
        if isinstance(items, dict):
            for key, entry in items.items():
                if isinstance(entry, dict):
                    result[key] = entry
    return result


def spawn_item(caller, item_key: str):
    """
    Spawn an item from the catalog into caller's inventory.

    Args:
        caller:   Character to receive the item.
        item_key: Key from item_catalog.yaml (e.g. "metal_plug").
    """
    entries = _all_entries()
    entry   = entries.get(item_key)

    if not entry:
        caller.msg(
            f"|xNo catalog item '{item_key}'.\n"
            f"Use: @py from world.item_loader import list_catalog; list_catalog(me)|n"
        )
        return None

    typeclass = entry.get("typeclass")
    if not typeclass:
        caller.msg(f"|xCatalog entry '{item_key}' has no typeclass defined.|n")
        return None

    from evennia.utils import create

    try:
        obj = create.create_object(
            typeclass,
            key=entry.get("key", item_key),
            location=caller,
        )
    except Exception as e:
        caller.msg(f"|xFailed to create {item_key}: {e}|n")
        return None

    # Set db attributes from catalog entry
    _apply_entry(obj, entry)

    caller.msg(f"|w{obj.key}|n added to your inventory.")
    return obj


def _apply_entry(obj, entry: dict):
    """Write catalog entry fields onto an item object's db."""
    skip = {"key", "typeclass"}

    for field, value in entry.items():
        if field in skip:
            continue

        if field == "binding_effects":
            obj.db.binding_effects = dict(value or {})

        elif field == "effect":
            # PiercingItem effect dict
            obj.db.effect = dict(value or {})

        elif field == "extra":
            # Arbitrary extra flags stored directly on db
            for k, v in (value or {}).items():
                setattr(obj.db, k, v)

        elif field == "camouflage_desc":
            obj.db.camouflage_desc = value or ""

        elif field == "worn_desc":
            obj.db.worn_desc = value or ""

        elif field == "slot":
            obj.db.slot = value or "center"

        elif field == "default_zone":
            obj.db.default_zone = value or ""

        else:
            # Generic db field
            try:
                setattr(obj.db, field, value)
            except Exception:
                pass


def list_catalog(caller):
    """Print all catalog entries by category to caller."""
    data = _load()
    lines = ["|wItem Catalog|n"]
    for category, items in data.items():
        if not isinstance(items, dict):
            continue
        lines.append(f"\n  |w{category.upper()}|n")
        for key, entry in items.items():
            if isinstance(entry, dict):
                name = entry.get("key", key)
                tc   = entry.get("typeclass", "").split(".")[-1]
                lines.append(f"    |x{key:<30}|n {name}  |x({tc})|n")
    caller.msg("\n".join(lines))
