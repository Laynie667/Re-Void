"""
world/rules.py — the RULES engine (Layer 3 of the authority stack).

A rule is a standing obligation on a target:
    db.rules = [ {id, name, set_by, condition, consequence, params, active} ]

Setting one requires `consent.may(setter, target, "rule.set")` (the command gates
this; an owner or the unit on themselves passes). Each rule has:
  - a CONDITION (when it applies): always / in_room / owner_present / owner_absent /
    arousal_over / flag
  - a CONSEQUENCE when broken: "block" (prevent the action) / "punish" (let it happen,
    then compliance.punish) / "notify" (log it + ping the setter)

The catalogue below is a CURATED set we actually have hooks for — not a sprawl.
`enforce(target, event, ...)` is the single call game hooks make at an action
point; it returns {"allowed": bool, "fired": [...]}. Ambient rules are driven by
the facility cycle tick via `enforce_ambient`.

The §0 OOC floor is never gated by a rule; `force_clear` wipes `db.rules`.
"""

import time

from world.consent import may, log_event


# name -> {events, consequence (default), desc, param (optional)}
CATALOGUE = {
    "present_on_enter": {"events": {"enter"},   "consequence": "notify",
                         "desc": "present yourself on entering a room"},
    "kneel_on_enter":   {"events": {"enter"},   "consequence": "notify",
                         "desc": "kneel on entering"},
    "no_leave":         {"events": {"leave"},   "consequence": "block",
                         "desc": "may not leave without permission"},
    "banned_words":     {"events": {"say"},     "consequence": "punish", "param": "words",
                         "desc": "forbidden words (comma list)"},
    "honorific":        {"events": {"say"},     "consequence": "notify",  "param": "honorific",
                         "desc": "address holders by an honorific"},
    "ask_to_come":      {"events": {"orgasm"},  "consequence": "punish",
                         "desc": "must be granted permission to climax"},
    "no_clothing":      {"events": {"ambient"}, "consequence": "notify",
                         "desc": "remain unclothed"},
    "posture_hold":     {"events": {"ambient"}, "consequence": "notify", "param": "posture",
                         "desc": "hold a posture"},
    "curfew":           {"events": {"ambient"}, "consequence": "notify", "param": "hours",
                         "desc": "be in your pen during curfew hours (e.g. 22-6)"},
}


# ── small helpers ─────────────────────────────────────────────────────────────
def _obj(oid):
    from evennia import search_object
    res = search_object(f"#{oid}")
    return res[0] if res else None


def _rules(target):
    return list(getattr(target.db, "rules", None) or [])


def _save(target, rules):
    target.db.rules = rules


def _name(c):
    return c.db.rp_name or c.key


def _owner_present(target):
    """Any character in the room who holds the owner tier over target."""
    from world.relationships import tiers_of
    loc = target.location
    if not loc:
        return False
    from typeclasses.characters import Character
    for o in loc.contents:
        if isinstance(o, Character) and o is not target and "owner" in tiers_of(o, target):
            return True
    return False


# ── condition evaluation ──────────────────────────────────────────────────────
def _condition_active(target, cond):
    if not cond or cond.get("type", "always") == "always":
        return True
    ct = cond["type"]
    if ct == "in_room":
        return bool(target.location and target.location.dbref == cond.get("room"))
    if ct == "owner_present":
        return _owner_present(target)
    if ct == "owner_absent":
        return not _owner_present(target)
    if ct == "arousal_over":
        return float(getattr(target.db, "arousal", 0) or 0) >= float(cond.get("value", 0))
    if ct == "flag":
        return bool(getattr(target.db, cond.get("flag", ""), False)) == bool(cond.get("value", True))
    return True


# ── violation predicates ──────────────────────────────────────────────────────
def _violated(target, rule, event, actor=None, text=None, **ctx):
    """Return (violated: bool, detail: str)."""
    name = rule["name"]
    p = rule.get("params", {})

    if name == "banned_words" and text:
        low = text.lower()
        for w in p.get("words", []):
            if w and w.lower() in low:
                return True, f"the forbidden word '{w}'"
        return False, ""
    if name == "honorific":
        return False, ""  # directive only (no reliable auto-detect); see notify message
    if name == "no_leave":
        if getattr(target.db, "rule_leave_permit", False):
            return False, ""
        return True, "leaving without permission"
    if name == "ask_to_come":
        if getattr(target.db, "rule_come_permit", False):
            return False, ""
        return True, "climaxing without permission"
    if name == "no_clothing":
        worn = [o for o in target.contents if getattr(o.db, "worn", False)]
        return (bool(worn), "still dressed" if worn else "")
    if name == "curfew":
        hrs = p.get("hours")
        if not hrs:
            return False, ""
        start, end = hrs
        h = time.localtime().tm_hour
        within = (start <= h or h < end) if start > end else (start <= h < end)
        return (within, "out past curfew") if within else (False, "")
    # present_on_enter / kneel_on_enter / posture_hold — directives, always "due"
    return True, CATALOGUE.get(name, {}).get("desc", "")


# ── consequence dispatch (REAL systems) ───────────────────────────────────────
def _apply_consequence(target, rule, cons, actor, detail):
    name = rule["name"]
    if cons == "punish":
        try:
            from world.compliance import punish
            punish(target, reason=f"broke rule: {name}", severity=1)
        except Exception:
            pass
        log_event(target, "rule_punish", rule=name, by=rule.get("set_by"))
        target.msg(f"|R[{name}] {detail or 'you broke the rule'} — and it costs you.|n")
    elif cons == "block":
        log_event(target, "rule_block", rule=name, by=rule.get("set_by"))
    else:  # notify
        log_event(target, "rule_notify", rule=name, by=rule.get("set_by"))
        target.msg(f"|x[{name}] {detail or 'mind the rule.'}|n")
        sb = rule.get("set_by")
        if sb:
            setter = _obj(sb)
            if setter and setter is not target:
                setter.msg(f"|y[rule] {_name(target)}: {name}"
                           f"{(' — ' + detail) if detail else ''}.|n")


# ── the call game hooks make ──────────────────────────────────────────────────
def enforce(target, event, actor=None, text=None, **ctx):
    """Evaluate every active rule on `target` governing `event`. Applies consequences.
    Returns {"allowed": bool, "fired": [(rule, consequence), ...]}. allowed=False means a
    'block' rule fired and the caller should prevent the action."""
    allowed = True
    fired = []
    for r in _rules(target):
        if not r.get("active", True):
            continue
        if event not in CATALOGUE.get(r["name"], {}).get("events", ()):
            continue
        if not _condition_active(target, r.get("condition")):
            continue
        violated, detail = _violated(target, r, event, actor=actor, text=text, **ctx)
        if not violated:
            continue
        cons = r.get("consequence") or CATALOGUE[r["name"]]["consequence"]
        _apply_consequence(target, r, cons, actor, detail)
        fired.append((r, cons))
        if cons == "block":
            allowed = False
    return {"allowed": allowed, "fired": fired}


def enforce_ambient(target):
    """Driven by the facility cycle tick — honor posture/clothing/curfew rules each beat."""
    return enforce(target, "ambient")


# ── management (the `rule` command calls these) ───────────────────────────────
def add_rule(target, name, set_by, condition=None, consequence=None, params=None):
    """Add a rule. Caller must have already checked may(set_by, target, 'rule.set')."""
    if name not in CATALOGUE:
        return None, f"Unknown rule '{name}'. Options: {', '.join(sorted(CATALOGUE))}"
    rules = _rules(target)
    rid = (max([r.get("id", 0) for r in rules]) + 1) if rules else 1
    rule = {
        "id": rid, "name": name,
        "set_by": getattr(set_by, "id", None),
        "condition": condition or {"type": "always"},
        "consequence": consequence or CATALOGUE[name]["consequence"],
        "params": params or {},
        "active": True,
    }
    rules.append(rule)
    _save(target, rules)
    log_event(target, "rule_set", rule=name, by=getattr(set_by, "id", None))
    return rule, None


def remove_rule(target, rule_id):
    rules = _rules(target)
    keep = [r for r in rules if r.get("id") != rule_id]
    if len(keep) == len(rules):
        return False
    _save(target, keep)
    log_event(target, "rule_cleared", by=None)
    return True


def render_rules(target):
    rules = _rules(target)
    lines = ["|w" + "═" * 46 + "|n", f"|wRULES — {_name(target)}|n", "|w" + "═" * 46 + "|n"]
    if not rules:
        lines.append("|xNo standing rules.|n")
    for r in rules:
        cond = r.get("condition", {})
        ctxt = "" if cond.get("type", "always") == "always" else f" |x[{cond['type']}]|n"
        col = {"block": "|r", "punish": "|R", "notify": "|y"}.get(r.get("consequence"), "|w")
        p = r.get("params") or {}
        ptxt = ""
        if p:
            ptxt = " |x(" + ", ".join(f"{k}={v}" for k, v in p.items()) + ")|n"
        lines.append(f"  |w#{r['id']}|n {r['name']}{ptxt} → {col}{r.get('consequence')}|n{ctxt}")
    lines.append("|w" + "═" * 46 + "|n")
    return "\n".join(lines)
