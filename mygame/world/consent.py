"""
world/consent.py — the unified authority query for the consent stack (Layer 2 v2).

ONE function the rules engine (Layer 3) and contract clauses (Layer 4) call:

    may(actor, target, feature) -> bool

It READS the game's existing consent stores — it does NOT migrate or shadow them:
  - general features (intimate/mature/bdsm/restraint/acts/condition/...) →
        target.db.consent_flags  +  per-person/per-tier overrides in
        target.db.consent_overrides  (resolved via relationships.override_decision,
        so relationship tiers work)
  - conditioning features (cond.deepen/trigger/speech/name/body) →
        target.db.conditioning_consent (the existing by/scope/locked grant),
        AND, as an umbrella, a tier/person grant of the general "condition" feature
        (so `consent allow condition owner` hands an owner full conditioning rights)

It also owns the consent LOCK (a unit can't edit their own consent while locked; a
holder or the §0 floor lifts it) and the behaviour-LOG + lockout.

The OOC floor is NEVER gated here. `force_clear` lifts every lock this module sets.
"""

from world.relationships import override_decision, tiers_of

# conditioning feature → the scope it needs in conditioning_consent
CONDITION_FEATURES = {
    "cond.deepen":  "deepen",
    "cond.trigger": "trigger",
    "cond.speech":  "speech",
    "cond.name":    "name",
    "cond.body":    "body",
}


# ── the resolver ──────────────────────────────────────────────────────────────
def _general_decision(actor, target, feature):
    """block/allow/None from the existing overrides (id OR tier), else None."""
    ov = getattr(target.db, "consent_overrides", None) or {}
    allow = ov.get("allow", {}).get(feature, set())
    block = ov.get("block", {}).get(feature, set())
    return override_decision(actor, target, allow, block)


def _may_general(actor, target, feature):
    dec = _general_decision(actor, target, feature)
    if dec == "block":
        return False
    if dec == "allow":
        return True
    return bool((getattr(target.db, "consent_flags", None) or {}).get(feature, False))


def _may_condition(actor, target, scope):
    c = getattr(target.db, "conditioning_consent", None) or {}
    aid = getattr(actor, "id", None)
    # explicit conditioning grant (the existing system): by you / by anyone, in-scope
    if c.get("by") in (aid, "any") and scope in (c.get("scope") or []):
        return True
    # umbrella tier/person grant via the general "condition" override
    dec = _general_decision(actor, target, "condition")
    if dec == "block":
        return False
    if dec == "allow":
        return True
    return False


def may(actor, target, feature):
    """May `actor` do `feature` to `target`? The single authority query for the stack."""
    if actor is None or target is None:
        return False
    if actor is target or getattr(actor, "id", None) == getattr(target, "id", None):
        return True
    if feature in CONDITION_FEATURES:
        return _may_condition(actor, target, CONDITION_FEATURES[feature])
    return _may_general(actor, target, feature)


# ── the consent LOCK ──────────────────────────────────────────────────────────
def is_locked(char):
    return bool(getattr(char.db, "consent_locked", False))


def set_lock(char, locked, by=None):
    """Set/lift the consent lock. Callers gate WHO may do this (self-lock, owner, floor)."""
    char.db.consent_locked = bool(locked)
    log_event(char, "consent_lock" if locked else "consent_unlock",
              by=getattr(by, "id", None))


# ── behaviour log + lockout ───────────────────────────────────────────────────
def log_event(char, kind, **data):
    """Append an entry to char's behaviour log (capped). Never raises."""
    try:
        import time as _t
        log = list(getattr(char.db, "behaviour_log", None) or [])
        entry = {"t": kind, "at": _t.time()}
        entry.update(data)
        log.append(entry)
        char.db.behaviour_log = log[-200:]
    except Exception:
        pass


def can_view_log(viewer, target):
    """A unit may read their own log unless locked out; an owner may always read it."""
    if viewer is target or getattr(viewer, "id", None) == getattr(target, "id", None):
        return not bool(getattr(target.db, "log_locked_out", False))
    return "owner" in tiers_of(viewer, target)


def set_log_lockout(target, locked_out, by=None):
    target.db.log_locked_out = bool(locked_out)
    log_event(target, "log_lockout" if locked_out else "log_lockout_lifted",
              by=getattr(by, "id", None))


def render_log(char, n=25):
    """A readable view of the most recent behaviour-log entries."""
    from evennia import search_object
    import time as _t
    log = list(getattr(char.db, "behaviour_log", None) or [])
    name = char.db.rp_name or char.key
    lines = ["|w" + "═" * 46 + "|n", f"|wBEHAVIOUR LOG — {name}|n", "|w" + "═" * 46 + "|n"]
    if not log:
        lines.append("|xNothing on record.|n")
    for e in log[-n:]:
        who = ""
        if e.get("by"):
            res = search_object(f"#{e['by']}")
            who = f" by {res[0].db.rp_name or res[0].key}" if res else f" by #{e['by']}"
        ago = ""
        try:
            secs = int(_t.time() - float(e.get("at", 0)))
            ago = f"  |x({secs // 60}m ago)|n" if secs >= 60 else f"  |x({secs}s ago)|n"
        except Exception:
            pass
        extra = ""
        if e.get("role"):
            extra = f": {e['role']}"
        elif e.get("rule"):
            extra = f": {e['rule']}"
        lines.append(f"  |y{e.get('t', '?')}|n{extra}{who}{ago}")
    lines.append("|w" + "═" * 46 + "|n")
    return "\n".join(lines)
