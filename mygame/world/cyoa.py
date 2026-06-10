"""
world/cyoa.py — the facility's choose-your-own-adventure layer.

The facility doesn't only happen TO her; at branch points it makes her CHOOSE — and every
choice has a real mechanical consequence (conditioning, relief, quota, regression, standing,
which hole, …). The cruelty is that the choices are all bad, and that NOT choosing is itself a
choice the facility makes for her (the default fires on timeout). Nothing here hard-blocks the
cycle or gates the §0 floor:

    character.db.pending_choice = {key, prompt, options[], default, posed_at}

  * pose_choice()    — present a framed choice (private to the subject).
  * resolve_choice() — apply the picked option's real effect, clear pending.
  * facility_decides() — timeout/no-pick path: the default option fires ("indecision is a
                         choice the facility makes for you").

Effects are a small registry (id -> fn) so options are data (db-safe), not callables. The OOC
floor clears `pending_choice` via FACILITY_FLAGS; a posed choice never stops escape/force_clear.
"""

import time
import random

# ── effect registry ─────────────────────────────────────────────────────────
_EFFECTS = {}


def effect(eid):
    def deco(fn):
        _EFFECTS[eid] = fn
        return fn
    return deco


def run_effect(character, eid, params=None):
    fn = _EFFECTS.get(eid)
    if not fn:
        return ""
    try:
        return fn(character, params or {}) or ""
    except Exception:
        return ""


# ── core: pose / resolve / default ───────────────────────────────────────────
def pose_choice(character, key, prompt, options, default_key=None, room=None):
    """Present a choice. `options` = list of {key, label, desc, effect, params}. Stored on
    the subject and shown privately (it's hers to make). Returns the pending dict."""
    if not character or not options:
        return None
    pending = {
        "key": key, "prompt": prompt, "options": list(options),
        "default": default_key or options[-1].get("key"),
        "posed_at": time.time(),
    }
    character.db.pending_choice = pending
    lines = ["", "|W┏━ A CHOICE ━┓|n", "|W" + prompt + "|n"]
    for i, o in enumerate(options, 1):
        lines.append(f"  |w{i}.|n |c{o.get('label','')}|n"
                     + (f" |x— {o['desc']}|n" if o.get("desc") else ""))
    lines.append("|x  (|wchoose <number>|x. Decide, or the facility decides for you.)|n")
    character.msg("\n".join(lines))
    return pending


def resolve_choice(character, selection):
    """Resolve the pending choice by 1-based number or option key. Applies the real effect and
    clears the pending choice. Returns (option, result_msg) or (None, '')."""
    pending = getattr(character.db, "pending_choice", None)
    if not pending:
        return None, ""
    options = pending.get("options") or []
    opt = None
    sel = str(selection).strip().lower()
    if sel.isdigit():
        idx = int(sel) - 1
        if 0 <= idx < len(options):
            opt = options[idx]
    if not opt:
        opt = next((o for o in options if str(o.get("key", "")).lower() == sel), None)
    if not opt:
        return None, ""
    character.db.pending_choice = None
    msg = run_effect(character, opt.get("effect"), opt.get("params"))
    return opt, msg


def facility_decides(character):
    """No pick in time — the default fires. Returns (option, msg) or (None, '')."""
    pending = getattr(character.db, "pending_choice", None)
    if not pending:
        return None, ""
    default = pending.get("default")
    # Resolve by the stored default key, narrating that the facility chose.
    opt, msg = resolve_choice(character, default)
    if opt and getattr(character, "msg", None):
        character.msg("|xYou didn't choose. The facility chose for you — it always will, when "
                      "you won't. That's a lesson too.|n")
    return opt, msg


def has_pending(character):
    return bool(getattr(character.db, "pending_choice", None))


def pending_age(character):
    p = getattr(character.db, "pending_choice", None)
    if not p:
        return 0.0
    return max(0.0, time.time() - float(p.get("posed_at", 0) or 0))


# ── real effects (each routes through an existing system) ────────────────────
@effect("emphasis")
def _eff_emphasis(character, p):
    """Bias the cycle toward a phase (milk/breed/condition) — read by _choose_destination."""
    which = p.get("which", "breed")
    character.db.cycle_emphasis = which
    return f"emphasis:{which}"


@effect("grant_relief")
def _eff_grant_relief(character, p):
    """She begged for it and gets it — a granted release that deepens the leash."""
    try:
        from world.arousal_rules import grant_release
        grant_release(character)
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(character); add_arousal(character, 80.0)
    except Exception:
        pass
    return "relief"


@effect("deny_hold")
def _eff_deny_hold(character, p):
    """She held out — a flicker of self, paid for in denial and a deeper conditioning drift."""
    try:
        character.db.arousal_floor = max(float(getattr(character.db, "arousal_floor", 0) or 0), 40.0)
        from world.conditioning import add_conditioning
        add_conditioning(character, float(p.get("cond", 4.0)), source="held_out")
    except Exception:
        pass
    return "held_out"


@effect("quota_deal")
def _eff_quota_deal(character, p):
    """Took the deal: a rest now, paid back in a heavier breeding quota."""
    sp = p.get("species", "contributor")
    bump = int(p.get("bump", 6))
    try:
        from world.gang_breeding import ensure_quota_entry
        q = dict(getattr(character.db, "breeding_quota", None) or {})
        if sp in q:
            e = ensure_quota_entry(q, sp); e["required"] = int(e.get("required", 0)) + bump
            q[sp] = e; character.db.breeding_quota = q
        character.db.line_pass = int(getattr(character.db, "line_pass", 0) or 0) + 1
    except Exception:
        pass
    return f"deal:+{bump} {sp}"


@effect("pick_hole")
def _eff_pick_hole(character, p):
    """She chose which hole to offer — it gets used, and trained, for choosing."""
    zone = p.get("zone")
    try:
        from world.gang_breeding import record_use
        if zone:
            record_use(character, zone, 1.5)
    except Exception:
        pass
    return f"offered:{zone}"


@effect("go_little")
def _eff_go_little(character, p):
    """She chose to let herself slip rather than fight it — regression for the surrender."""
    try:
        from world.regression import regress
        regress(character, float(p.get("amount", 8.0)), source="chose_little")
    except Exception:
        pass
    return "slipped"


@effect("submit_standing")
def _eff_submit_standing(character, p):
    """She chose to submit/comply — facility standing + a compliance tick."""
    try:
        from world.factions import add_standing
        add_standing(character, source={"submit": "submit"})
    except Exception:
        pass
    try:
        from world.compliance import register_compliance
        register_compliance(character, reward=False)
    except Exception:
        pass
    return "submitted"
