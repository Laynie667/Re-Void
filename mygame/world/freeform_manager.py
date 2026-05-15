"""
world/freeform_manager.py

Storage and lifecycle management for all freeform elements in Re:Void.

Freeform elements are purely descriptive — no real game objects are created.
Everything is stored as structured data on character or room db attributes.

DATA STRUCTURES
---------------
character.db.freeform_items (dict):
    {
        "collar": {
            "zone":       "neck",
            "name":       "collar",
            "desc":       "A beautiful silver collar",
            "placed_by":  <char_id>,
            "lock":       None | {
                "type":      "slock" | "plock",
                "code":      "SL-XXXXXX",   # slock only
                "key_id":    <key_obj_id>,   # plock only
                "locked_by": <char_id>,
            }
        },
        ...
    }

room.db.freeform_sensory (dict):
    {
        "sound":   {"text": "...", "author_id": <id>, "pinned": False},
        "scent":   {...},
        "light":   {...},
        "taste":   {...},
        "texture": {...},
        "temp":    {...},
    }

LIFECYCLE
---------
- FreeformManager.end_scene(room) is called by scene_commands when a pose
  order ends. It:
    - Clears all non-pinned sensory layers from the room.
    - Releases all slock locks on characters currently in the room.
  Pinned sensory layers and plock locks survive scene end.

CONSENT
-------
- place:  free to use on any consenting character (or self)
- slock:  free — temporary, auto-releases at scene end
- plock:  requires target character to have consent_flags["plock"] == True
          Only released by: keyholder (holding the key object), admin,
          or eventually an NPC keyholder.
"""

import re
import random
import string

# Valid sensory types
SENSORY_TYPES = ("sound", "scent", "light", "taste", "texture", "temp")

SENSORY_LABELS = {
    "sound":   "Sound",
    "scent":   "Scent",
    "light":   "Light",
    "taste":   "Taste",
    "texture": "Texture",
    "temp":    "Temperature",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen_slock_code():
    """Generate a short, human-readable slock reference code."""
    chars = random.choices(string.ascii_uppercase + string.digits, k=6)
    return "SL-" + "".join(chars)


def _char_name(character):
    return (character.db.rp_name or character.key) if character else "Unknown"


# ---------------------------------------------------------------------------
# Zone token renderer
# ---------------------------------------------------------------------------

_ZONE_TOKEN_RE = re.compile(r'\{zone:([a-z_]+)\}')


def render_zone_tokens(text, character):
    """
    Replace {zone:name} tokens in text with the zone's current rendered state.

    Resolution order per zone:
      nude desc is always the base — nothing replaces it.
      All layers append with " — " and are joined with ", ".

      Render order (clothing layer first, then on-items, then in-items):
        1. covered_by clothing (from wear command)
        2. Freeform items with display_mode="cover" (placed covering items, e.g. chastity belt)
        3. Freeform items with display_mode="on" (placed on the surface)
        4. Freeform items with display_mode="in" (placed inside an orifice)
        5. Bare nude desc if nothing else present
        6. Zone not found or empty → empty string (token removed silently)

    Usage in physical_desc:
        {zone:hair}, framing {zone:face}. At the throat, {zone:neck}.
    """
    if not text or '{zone:' not in text:
        return text

    zones = character.db.zones or {}
    freeform = character.db.freeform_items or {}
    zone_keys = list(zones.keys())
    freeform_keys = list(freeform.keys())

    def resolve(match):
        zname = match.group(1)
        if zname not in zone_keys:
            return ""

        zdata = zones.get(zname, {})
        nude = (zdata.get("nude") or "").strip()

        # Collect freeform items on this zone.
        # "cover"  — placed covering item (chastity belt, gag, etc.) — renders in clothing layer
        # "on"     — placed on the surface/attachment zone
        # "in"     — placed inside an orifice zone
        # All use player_desc if set, else original desc.
        cover_items = []
        on_items = []
        in_items = []

        for ikey in freeform_keys:
            idata = freeform.get(ikey, {})
            if not idata or idata.get("zone") != zname:
                continue
            mode = idata.get("display_mode", "on")
            # Prefer the owner's custom description over the placer's
            idesc = (idata.get("player_desc") or idata.get("desc") or "").strip()
            if not idesc:
                continue
            if mode == "cover":
                cover_items.append(idesc)
            elif mode == "in":
                in_items.append(idesc)
            else:
                on_items.append(idesc)

        # Worn clothing (via wear) replaces the nude desc as the visible base.
        # If nothing is worn, the nude desc shows instead.
        # place/cover items, place/on items, and place/in items always append.
        covered = zdata.get("covered_by")
        if covered:
            worn = (covered.get("worn_desc") or covered.get("desc") or "").strip()
            base = worn if worn else nude
        else:
            base = nude

        # cover-mode placed items, on-items, and in-items all append.
        all_parts = cover_items + on_items + in_items

        if all_parts:
            suffix = " — " + ", ".join(all_parts)
            return base + suffix if base else ", ".join(all_parts)

        return base

    return _ZONE_TOKEN_RE.sub(resolve, text)


# ---------------------------------------------------------------------------
# FreeformManager
# ---------------------------------------------------------------------------

class FreeformManager:
    """
    Static utility class. All methods operate on Evennia db attributes
    and return (success: bool, data_or_error: any) tuples.
    """

    # =======================================================================
    # Freeform items on characters
    # =======================================================================

    @staticmethod
    def get_items(character):
        """Return a copy of all freeform items on a character."""
        return dict(character.db.freeform_items or {})

    @staticmethod
    def get_item(character, name):
        """Return a single freeform item dict, or None."""
        items = character.db.freeform_items or {}
        return items.get(name.lower())

    @staticmethod
    def place_item(character, zone, name, desc, placer_id, display_mode="on"):
        """
        Register a freeform item on a character.

        Args:
            character:       Target character object.
            zone (str):      Zone name that must exist on the character.
            name (str):      Short handle for the item (used in lock commands).
            desc (str):      The placer's description — shown unless owner sets
                             their own player_desc.
            placer_id:       ID of the character placing the item.
            display_mode:    "on"     — placed externally on the zone surface.
                             "in"     — placed inside (orifice zone).
                             "cover"  — placed covering the zone (renders in the
                                        clothing layer, e.g. chastity belt, gag).
                             All modes render alongside nude desc (never replace).

        Returns:
            (True, item_dict) or (False, error_str)
        """
        zones = character.db.zones or {}
        zone = zone.lower().replace(" ", "_")

        if zone not in zones:
            cname = _char_name(character)
            return False, (
                f"{cname} doesn't have a zone named '{zone}'.\n"
                f"Available zones: {', '.join(sorted(zones.keys())) or 'none'}"
            )

        name = name.lower()
        display_mode = display_mode if display_mode in ("on", "in", "cover") else "on"
        items = character.db.freeform_items or {}

        # Allow overwriting an unlocked existing item
        existing = items.get(name)
        if existing and existing.get("lock"):
            lock_type = existing["lock"].get("type", "locked")
            return False, (
                f"'{name}' already exists and is {lock_type}ed. "
                f"Unlock it before replacing it."
            )

        items[name] = {
            "zone":         zone,
            "name":         name,
            "desc":         desc,       # placer's description (read-only to owner)
            "player_desc":  "",         # owner's custom description (editable always)
            "placed_by":    placer_id,
            "lock":         None,
            "display_mode": display_mode,
        }
        character.db.freeform_items = items
        return True, items[name]

    @staticmethod
    def remove_item(character, name):
        """
        Remove a freeform item if it is not locked.

        Returns:
            (True, removed_item_dict) or (False, error_str)
        """
        items = character.db.freeform_items or {}
        name = name.lower()
        item = items.get(name)

        if not item:
            return False, f"No freeform item named '{name}'."

        lock = item.get("lock")
        if lock:
            ltype = lock.get("type", "locked")
            if ltype == "slock":
                return False, (
                    f"'{name}' is scene-locked (code: {lock.get('code', '?')}). "
                    f"Use 'unslock' with the code to release it."
                )
            else:
                return False, (
                    f"'{name}' is permanently locked. "
                    f"A keyholder must use 'unplock' to release it."
                )

        del items[name]
        character.db.freeform_items = items
        return True, item

    @staticmethod
    def set_player_desc(character, item_name, text):
        """
        Set the character's own description for a freeform item on them.

        The owner can always do this, even on locked items — plock freezes
        removal, not narrative. The player_desc takes priority over the
        placer's original desc in all rendering.

        Args:
            character:        The character who owns the zone.
            item_name (str):  Name of the freeform item.
            text (str):       The owner's custom description.

        Returns:
            (True, item_dict) or (False, error_str)
        """
        items = character.db.freeform_items or {}
        name = item_name.lower()
        item = items.get(name)
        if not item:
            return False, f"No freeform item named '{name}'."
        item["player_desc"] = text.strip()
        character.db.freeform_items = items
        return True, item

    # --- Scene locks (slock) -----------------------------------------------

    @staticmethod
    def slock_item(character, name, locker_id):
        """
        Apply a scene lock to a freeform item.

        Returns:
            (True, code_str) — the reference code the locker needs to unslock
            (False, error_str)
        """
        items = character.db.freeform_items or {}
        name = name.lower()
        item = items.get(name)

        if not item:
            return False, f"No freeform item named '{name}'."
        if item.get("lock"):
            ltype = item["lock"].get("type", "locked")
            return False, f"'{name}' is already {ltype}ed."

        code = _gen_slock_code()
        item["lock"] = {
            "type":      "slock",
            "code":      code,
            "locked_by": locker_id,
        }
        character.db.freeform_items = items
        return True, code

    @staticmethod
    def unslock_item(character, name, code):
        """
        Release a scene lock by providing the correct code.

        Returns:
            (True, item_dict) or (False, error_str)
        """
        items = character.db.freeform_items or {}
        name = name.lower()
        item = items.get(name)

        if not item:
            return False, f"No freeform item named '{name}'."

        lock = item.get("lock")
        if not lock:
            return False, f"'{name}' is not locked."
        if lock.get("type") != "slock":
            return False, (
                f"'{name}' has a permanent lock, not a scene lock. "
                f"Use 'unplock' with the key."
            )
        if lock.get("code", "").upper() != code.strip().upper():
            return False, "Incorrect lock code."

        item["lock"] = None
        character.db.freeform_items = items
        return True, item

    # --- Permanent locks (plock) -------------------------------------------

    @staticmethod
    def check_plock_consent(character):
        """Return True if character has consented to permanent locks."""
        flags = character.db.consent_flags or {}
        return bool(flags.get("plock", False))

    @staticmethod
    def plock_item(character, name, locker_id, key_obj):
        """
        Apply a permanent lock to a freeform item.

        The caller must have already:
          - verified plock consent on the character
          - created the key object and placed it in inventory

        Args:
            character:  Target character.
            name (str): Item name.
            locker_id:  ID of character applying the lock.
            key_obj:    Key typeclass instance (already in locker's inventory).

        Returns:
            (True, item_dict) or (False, error_str)
        """
        items = character.db.freeform_items or {}
        name = name.lower()
        item = items.get(name)

        if not item:
            return False, f"No freeform item named '{name}'."
        if item.get("lock"):
            ltype = item["lock"].get("type", "locked")
            return False, f"'{name}' is already {ltype}ed."

        item["lock"] = {
            "type":      "plock",
            "key_id":    key_obj.id,
            "locked_by": locker_id,
        }
        character.db.freeform_items = items
        return True, item

    @staticmethod
    def unplock_item(character, name, key_obj=None, admin=False):
        """
        Release a permanent lock.

        Requires either:
          - admin=True  (admin override), or
          - key_obj whose .id matches the stored key_id.

        Returns:
            (True, item_dict) or (False, error_str)
        """
        items = character.db.freeform_items or {}
        name = name.lower()
        item = items.get(name)

        if not item:
            return False, f"No freeform item named '{name}'."

        lock = item.get("lock")
        if not lock:
            return False, f"'{name}' is not locked."
        if lock.get("type") != "plock":
            return False, (
                f"'{name}' has a scene lock, not a permanent lock. "
                f"Use 'unslock' with the code."
            )

        if not admin:
            if not key_obj:
                return False, "You need the key to unlock this."
            if key_obj.id != lock.get("key_id"):
                return False, "That key doesn't fit this lock."

        item["lock"] = None
        character.db.freeform_items = items
        return True, item

    # =======================================================================
    # Room sensory layers
    # =======================================================================

    @staticmethod
    def get_sensory(room, sense_type=None):
        """
        Return sensory layer(s) for a room.

        Args:
            room:             Room object.
            sense_type (str): If provided, return just that sense dict.
                              If None, return full sensory dict.
        """
        sensory = room.db.freeform_sensory or {}
        if sense_type:
            return sensory.get(sense_type.lower())
        return dict(sensory)

    @staticmethod
    def set_sensory(room, sense_type, text, author_id, pinned=False):
        """
        Set or replace a sensory layer in a room.

        Args:
            room:             Room object.
            sense_type (str): One of SENSORY_TYPES.
            text (str):       The sensory description.
            author_id:        Character ID who set it.
            pinned (bool):    If True, survives scene end.

        Returns:
            (True, entry_dict) or (False, error_str)
        """
        sense_type = sense_type.lower()
        if sense_type not in SENSORY_TYPES:
            return False, (
                f"Unknown sense type '{sense_type}'. "
                f"Choose from: {', '.join(SENSORY_TYPES)}"
            )

        sensory = room.db.freeform_sensory or {}
        sensory[sense_type] = {
            "text":      text,
            "author_id": author_id,
            "pinned":    pinned,
        }
        room.db.freeform_sensory = sensory
        return True, sensory[sense_type]

    @staticmethod
    def pin_sensory(room, sense_type, pinned=True):
        """Toggle the pinned state of an existing sensory layer."""
        sense_type = sense_type.lower()
        sensory = room.db.freeform_sensory or {}
        entry = sensory.get(sense_type)
        if not entry:
            return False, f"No {sense_type} layer is set here."
        entry["pinned"] = pinned
        room.db.freeform_sensory = sensory
        return True, entry

    @staticmethod
    def clear_sensory(room, sense_type):
        """
        Remove a specific sensory layer from a room.

        Returns:
            (True, None) or (False, error_str)
        """
        sense_type = sense_type.lower()
        sensory = room.db.freeform_sensory or {}
        if sense_type not in sensory:
            return False, f"No {sense_type} layer is currently set here."
        del sensory[sense_type]
        room.db.freeform_sensory = sensory
        return True, None

    @staticmethod
    def clear_all_sensory(room, pinned_only=False):
        """
        Clear sensory layers.

        Args:
            pinned_only (bool): If True, only clear pinned layers.
                                If False, clear all non-pinned layers (scene end).
        """
        sensory = room.db.freeform_sensory or {}
        if pinned_only:
            room.db.freeform_sensory = {
                k: v for k, v in sensory.items() if v.get("pinned")
            }
        else:
            # Scene end: clear non-pinned
            room.db.freeform_sensory = {
                k: v for k, v in sensory.items() if not v.get("pinned")
            }

    # =======================================================================
    # Scene end lifecycle
    # =======================================================================

    @staticmethod
    def end_scene(room):
        """
        Called when a pose order / scene ends.

        - Removes all non-pinned sensory layers from the room.
        - Releases all slock locks on every character currently in the room.

        Pinned sensory and plock locks are NOT affected.
        """
        # Clear non-pinned sensory
        sensory = room.db.freeform_sensory or {}
        room.db.freeform_sensory = {
            k: v for k, v in sensory.items() if v.get("pinned")
        }

        # Release slock on all characters in room
        for obj in room.contents:
            if not hasattr(obj, 'db'):
                continue
            items = obj.db.freeform_items
            if not items:
                continue
            changed = False
            for item in items.values():
                lock = item.get("lock")
                if lock and lock.get("type") == "slock":
                    item["lock"] = None
                    changed = True
            if changed:
                obj.db.freeform_items = items

        # Clear scene extras
        try:
            from commands.npc_commands import clear_scene_extras
            clear_scene_extras(room)
        except Exception:
            pass

    # =======================================================================
    # Wardrobe integration
    # =======================================================================

    @staticmethod
    def save_to_wardrobe(character, wardrobe_name, item_name):
        """
        Save a freeform item on a character to their wardrobe.

        The wardrobe entry stores the zone and description so it can
        be re-applied later via 'wardrobe wear'.

        Args:
            character:          Character who owns the wardrobe.
            wardrobe_name (str): Key to save it under in the wardrobe.
            item_name (str):    Name of the freeform item to save.

        Returns:
            (True, wardrobe_key_str) or (False, error_str)
        """
        items = character.db.freeform_items or {}
        item = items.get(item_name.lower())
        if not item:
            return False, f"No freeform item named '{item_name}'."

        wardrobe = character.db.wardrobe or {}
        key = wardrobe_name.lower()
        wardrobe[key] = {
            "zone":         item["zone"],
            "desc":         item["desc"],
            "worn_desc":    item["desc"],
            "examine_desc": "",
            "ambient":      [],
            "type":         "freeform",
            "item_id":      None,
        }
        character.db.wardrobe = wardrobe
        return True, key

    # =======================================================================
    # Display helpers
    # =======================================================================

    @staticmethod
    def format_items(character, viewer=None):
        """
        Return a formatted string listing all freeform items on a character.
        Respects zone visibility if viewer is provided.
        """
        items = character.db.freeform_items or {}
        if not items:
            return "|xNo freeform items.|n"

        lines = []
        for name, item in sorted(items.items()):
            zone        = item.get("zone", "unknown")
            desc        = item.get("desc", "")
            player_desc = item.get("player_desc", "")
            mode        = item.get("display_mode", "on")
            lock        = item.get("lock")

            if lock:
                ltype = lock.get("type", "locked")
                if ltype == "slock":
                    lock_str = f" |y[slock'd — code: {lock.get('code', '?')}]|n"
                else:
                    # Key ID always shown so players can report it to staff
                    lock_str = f" |r[plock'd — Key #{lock.get('key_id', '?')}]|n"
            else:
                lock_str = ""

            if mode == "in":
                mode_tag = " |x[inside]|n"
            elif mode == "cover":
                mode_tag = " |x[covers]|n"
            else:
                mode_tag = ""
            edited_tag = " |g[edited]|n" if player_desc else ""
            display    = player_desc if player_desc else desc

            lines.append(
                f"  |w{name}|n [{zone}]{mode_tag}{lock_str}{edited_tag}\n"
                f"    {display[:72]}{'...' if len(display) > 72 else ''}"
            )
            if player_desc:
                lines.append(
                    f"    |x(original: {desc[:60]}{'...' if len(desc) > 60 else ''})|n"
                )

        return "\n".join(lines)

    @staticmethod
    def format_sensory(room):
        """Return a formatted string of all active sensory layers in a room."""
        sensory = room.db.freeform_sensory or {}
        if not sensory:
            return "|xNo sensory layers set.|n"

        lines = []
        for stype in SENSORY_TYPES:
            entry = sensory.get(stype)
            if not entry:
                continue
            label = SENSORY_LABELS.get(stype, stype.capitalize())
            pinned = " |g[pinned]|n" if entry.get("pinned") else ""
            lines.append(
                f"  |w{label}|n{pinned}: {entry.get('text', '')}"
            )

        return "\n".join(lines) if lines else "|xNo sensory layers set.|n"
