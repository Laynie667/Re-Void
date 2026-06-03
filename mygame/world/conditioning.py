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
# The meter has no ceiling and accelerates, so it WILL climb into the deep
# stages on its own if left running. (value, key, handler_name)
_THRESHOLDS = [
    (20.0,  "floor",       "_cond_floor"),
    (40.0,  "speech",      "_cond_speech"),
    (60.0,  "trigger",     "_cond_trigger"),
    (80.0,  "designation", "_cond_designation"),
    (100.0, "permanent",   "_cond_permanent"),
    (130.0, "doll",        "_cond_doll"),
    (160.0, "identity",    "_cond_identity"),
    (200.0, "lockself",    "_cond_lockself"),
    (250.0, "imprint",     "_cond_imprint"),
]


def deepen_on_climax(character, amount=5.0):
    """Every release rewires a little more — called when a conditioned climax fires."""
    return add_conditioning(character, amount, source="climax")


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
        character.db.designation = "the breeding bitch"
    character.msg(_aura_line(
        character,
        "|xWhen you reach for your own name there's a short, smooth delay — like a page "
        "that won't turn. The violet at your edges has gone dim and stays dim now. "
        "Something shorter and cruder is waiting to be answered to instead.|n",
        "|xWhen you reach for your own name there's a short, smooth delay — like a page "
        "that won't turn. It comes, eventually, slower than it should. Something "
        "shorter and cruder answers faster.|n",
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


def _cond_doll(character):
    """The body is held in a breeding presentation — offered, not resting."""
    character.db.forced_posture = "presented for breeding — hips up, holes offered"
    character.db.body_language  = "presented — hips tipped, ready to be used"
    character.msg(
        "|xYour body settles into a shape you didn't pick — hips up, back arched, "
        "offered — and holds it. It feels correct in a way that has nothing to do "
        "with comfort. You are easier to breed now than to ask.|n"
    )


def _cond_identity(character):
    """She loses her name to the designation — restored only by a reset."""
    if not getattr(character.db, "designation", None):
        character.db.designation = "the breeding bitch"
    if not getattr(character.db, "facility_name_backup", None):
        character.db.facility_name_backup = character.db.rp_name or character.key
    character.db.rp_name = character.db.designation
    character.msg(
        "|xSomeone says your name and it slides right off — it belongs to a person who "
        f"used to stand here. What answers now is {character.db.designation}, and it "
        "answers faster than the old name ever did. Faster, and a little grateful.|n"
    )


def _cond_lockself(character):
    """She can no longer undo her own modifications, and gets a report trigger."""
    character.db.self_cmds_locked = True
    try:
        from world.binding_effects import install_trigger
        install_trigger(character, "report", response="recite", strength=2,
                        mantra="i'm a hole, i'm a cow, i don't decide, thank you")
    except Exception:
        pass
    character.msg(
        "|xYour hands won't move to undo any of it. The part of you that used to "
        "change things has been quietly retired. When asked to report, you will.|n"
    )


def _cond_imprint(character):
    """Animal imprint — the last of the person files down to a kept thing."""
    character.db.pet_type = character.db.pet_type or "puppy"
    if not getattr(character.db, "pet_trigger_sources", None):
        character.db.pet_trigger_sources = ["facility"]
    character.msg(
        "|xThere isn't much left to talk to. What's here is warm, obedient, and "
        "happy in the small flat way of an animal that has everything it needs and "
        "no say in any of it. Good girl. That part landed a long time ago.|n"
    )
