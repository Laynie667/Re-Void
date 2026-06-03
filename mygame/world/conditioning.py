"""
world/conditioning.py

A soft, accumulating conditioning meter. Machines and facility NPCs add to it
over time; at thresholds it applies escalating drift, and past a telegraphed
point-of-no-return some effects "set" (in-fiction permanent).

    character.db.conditioning           float, 0..100+
    character.db.conditioning_applied   list of threshold keys already fired
    character.db.conditioning_permanent bool, set once past POINT_OF_NO_RETURN

Design notes
------------
* Everything here is in-fiction. The OOC safeword is the superuser reset
  command (facilityreset), which clears all of this regardless of depth.
* The drift reuses existing systems: speech filters, arousal_floor, and the
  installed-trigger engine in world.binding_effects.
* Effects escalate quietly. There is intentionally NO readout of the meter
  to the conditioned character — they feel it, they don't see a number.
"""

POINT_OF_NO_RETURN = 100.0


def add_conditioning(character, amount, source=None):
    """Add to the conditioning meter and apply any newly-crossed thresholds.

    Returns the new conditioning value.
    """
    if not character:
        return 0.0
    cur = float(getattr(character.db, "conditioning", 0.0) or 0.0)
    new = max(0.0, cur + float(amount))
    character.db.conditioning = new
    _apply_thresholds(character, cur, new)
    return new


# Each threshold fires exactly once, the first time the meter crosses it.
# (value, key, handler_name)
_THRESHOLDS = [
    (20.0,  "floor",       "_cond_floor"),
    (40.0,  "speech",      "_cond_speech"),
    (60.0,  "trigger",     "_cond_trigger"),
    (80.0,  "designation", "_cond_designation"),
    (100.0, "permanent",   "_cond_permanent"),
]


def _apply_thresholds(character, old_value, new_value):
    applied = list(getattr(character.db, "conditioning_applied", None) or [])
    for value, key, handler_name in _THRESHOLDS:
        if old_value < value <= new_value and key not in applied:
            handler = globals().get(handler_name)
            if handler:
                try:
                    handler(character)
                except Exception:
                    pass
            applied.append(key)
    character.db.conditioning_applied = applied


def _aura_line(character, dim_text, fallback):
    """If the character has a violet aura zone, narrate it dimming; else fallback."""
    zones = getattr(character.db, "zones", None) or {}
    if any("aura" in (z or "").lower() for z in zones):
        return dim_text
    return fallback


# ── Threshold handlers ─────────────────────────────────────────────────────

def _cond_floor(character):
    """First drift: the body stops settling all the way back down."""
    existing = float(getattr(character.db, "arousal_floor", 0.0) or 0.0)
    character.db.arousal_floor = max(existing, 25.0)
    character.msg(_aura_line(
        character,
        "|xSomething hums under your skin and won't quite switch off. At the edges "
        "of your sight the violet light flickers, a half-second slow to follow you.|n",
        "|xSomething hums under your skin and won't quite switch off. You notice it "
        "the way you notice a sound that has been going on too long.|n",
    ))


def _cond_speech(character):
    """The words start arriving pre-shaped."""
    filters = list(getattr(character.db, "active_speech_filters", None) or [])
    if "baby_talk" not in filters:
        filters.append("baby_talk")
        character.db.active_speech_filters = filters
    character.msg(
        "|xThe sentence you meant to say comes out softer than you built it — rounder, "
        "smaller, easier. You hear the difference a beat after it's already left you.|n"
    )


def _cond_trigger(character):
    """A response gets written in under the surface."""
    try:
        from world.binding_effects import install_trigger
        install_trigger(character, "good girl", response="leak", strength=2)
        install_trigger(character, "empty", response="blank", strength=2)
    except Exception:
        pass
    character.msg(
        "|xTwo words settle into you and find somewhere to sit. You couldn't say which "
        "two. You'll know them when you hear them — your body will know first.|n"
    )


def _cond_designation(character):
    """Identity starts getting filed down to a label."""
    if not getattr(character.db, "designation", None):
        character.db.designation = "the doll"
    character.msg(_aura_line(
        character,
        "|xWhen you reach for your own name there's a short, smooth delay — like a page "
        "that won't turn. The violet at your edges has gone dim and stays dim now.|n",
        "|xWhen you reach for your own name there's a short, smooth delay — like a page "
        "that won't turn. It comes, eventually. It comes slower than it should.|n",
    ))


def _cond_permanent(character):
    """Point of no return — the drift sets. (Cleared only by superuser reset.)"""
    character.db.conditioning_permanent = True
    try:
        from world.binding_effects import install_trigger
        for entry in list(getattr(character.db, "installed_triggers", None) or []):
            entry["permanent"] = True
        character.db.installed_triggers = list(
            getattr(character.db, "installed_triggers", None) or []
        )
        install_trigger(character, "good girl", response="leak",
                        strength=3, permanent=True)
    except Exception:
        pass
    character.msg(
        "|xThere is a quiet click somewhere you can't point to, and then a stillness — "
        "the particular stillness of a decision being made for you and then closed. "
        "Whatever just set is not yours to take back.|n"
    )
