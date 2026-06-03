"""
world/soul_bound.py

Soul-bound item system for Re:Void.

A soul-bound item applies effects to ALL characters on the same account,
not just the one wearing it.

How it works:
  1. When an item with soul_bound=True in its binding_effects is activated,
     apply_soul_bound_effects(account, item) is called.
  2. Effects are stored on account.db.soul_bound_effects as a list.
  3. Every time a character from that account logs in or is puppeted,
     _sync_soul_bound_effects(character) applies the account-level effects
     to the character.
  4. When the item is removed, remove_soul_bound_effects(account, item) clears
     the account-level entry and re-syncs all online characters.

Soul-bound effects support the same flags as binding_effects but apply
account-wide:
  auto_consent, orgasm_denial, arousal_floor, stim_per_tick, speech_filter,
  forced_posture, lock_navigation, exhibition

Usage in at_puppet() hook in accounts.py (to be added):
    from world.soul_bound import sync_soul_bound_effects
    sync_soul_bound_effects(character)
"""

def apply_soul_bound_effects(account, item):
    """
    Store item's soul-bound effects on the account and apply to all
    currently-online characters on this account.
    """
    effects = getattr(item.db, "binding_effects", None) or {}
    if not effects.get("soul_bound"):
        return

    entry = {
        "item_dbref": item.dbref,
        "item_name":  item.key,
        "effects":    {k: v for k, v in effects.items() if k != "soul_bound"},
    }

    stored = list(account.db.soul_bound_effects or [])
    # Avoid duplicates
    stored = [e for e in stored if e.get("item_dbref") != item.dbref]
    stored.append(entry)
    account.db.soul_bound_effects = stored

    # Apply to all online characters
    for char in _online_chars(account):
        _apply_effects_to_char(char, entry["effects"])


def remove_soul_bound_effects(account, item):
    """Remove soul-bound effects for this item and re-sync all characters."""
    stored = list(account.db.soul_bound_effects or [])
    stored = [e for e in stored if e.get("item_dbref") != item.dbref]
    account.db.soul_bound_effects = stored

    # Re-sync online characters (recalculate from remaining entries)
    for char in _online_chars(account):
        sync_soul_bound_effects(char)


def sync_soul_bound_effects(character):
    """
    Apply all current soul-bound effects to this character.
    Call on puppet / login.
    """
    try:
        account = character.account
        if not account:
            return
        stored = list(account.db.soul_bound_effects or [])
        for entry in stored:
            _apply_effects_to_char(character, entry.get("effects") or {})
    except Exception:
        pass


def _apply_effects_to_char(char, effects: dict):
    """Apply a subset of binding effects to a character."""
    if effects.get("auto_consent"):
        from world.binding_effects import ALL_CONSENT_FLAGS
        flags = dict(char.db.consent_flags or {})
        for key in ALL_CONSENT_FLAGS:
            flags[key] = True
        char.db.consent_flags = flags

    if effects.get("orgasm_denial"):
        char.db.orgasm_denial = True
        char.db.orgasm_release_word = effects.get("orgasm_release_word", "come")

    floor = float(effects.get("arousal_floor", 0.0) or 0.0)
    if floor > 0:
        char.db.arousal_floor = max(float(char.db.arousal_floor or 0.0), floor)

    stim = float(effects.get("continuous_stimulation", 0.0) or 0.0)
    if stim > 0:
        char.db.stim_per_tick = float(char.db.stim_per_tick or 0.0) + stim

    if effects.get("exhibition"):
        char.db.exhibition_active  = True
        char.db.outfit_camouflage  = ""

    if effects.get("lock_navigation"):
        char.db.navigation_locked = True

    posture = effects.get("forced_posture")
    if posture:
        char.db.forced_posture = posture
        char.db.body_language  = posture

    filters = effects.get("speech_filter") or []
    if filters:
        active = list(char.db.active_speech_filters or [])
        for f in filters:
            if f not in active:
                active.append(f)
        char.db.active_speech_filters = active


def _online_chars(account):
    """Return all currently-online characters on this account."""
    chars = []
    try:
        for session in account.sessions.all():
            puppet = session.get_puppet()
            if puppet and hasattr(puppet, "db"):
                chars.append(puppet)
    except Exception:
        pass
    return chars
