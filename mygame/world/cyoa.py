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
def pose_choice(character, key, prompt, options, default_key=None, room=None, then=None):
    """Present a choice. `options` = list of {key, label, desc, effect, params}. Stored on
    the subject and shown privately (it's hers to make). Returns the pending dict.
    `then` is a node-level default next-node: every option chains to it unless the option
    sets its own `then` (perfect for linear scenes where each beat has one Continue)."""
    if not character or not options:
        return None
    pending = {
        "key": key, "prompt": prompt, "options": list(options),
        "default": default_key or options[-1].get("key"),
        "then": then,
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
    clears the pending choice. If the chosen option has a `then` (a builder id), the next choice
    in the chain is posed. Returns (option, result_msg) or (None, '')."""
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
    # Scene memory — an option may record what you chose so later beats can reference it
    # (this is what turns a deck of postcards into a scene). `set` writes scene flags.
    sets = opt.get("set")
    if sets:
        sf = dict(getattr(character.db, "scene_flags", None) or {})
        sf.update(sets)
        character.db.scene_flags = sf
    msg = run_effect(character, opt.get("effect"), opt.get("params"))
    # Outcome prose — the crude, in-voice beat of what your choice just did to you, shown
    # privately (it's yours to live with). Effects may also broadcast their own room messages.
    outcome = opt.get("outcome")
    if outcome and getattr(character, "msg", None):
        character.msg("|y" + outcome + "|n")
    # Chain — an option's own `then` wins; else fall back to the node-level default `then`
    # (so linear beats can declare one next-node for all their options). An `end` option
    # terminates the scene and does NOT inherit the node default.
    nxt = opt.get("then") or (None if opt.get("end") else pending.get("then"))
    if nxt:
        try:
            pose_named(character, nxt, room=getattr(character, "location", None))
        except Exception:
            pass
    # End of a scene — clear its memory so the next scene starts fresh. And if the player is in
    # auto-hub mode (set by `scenemode on`), the facility routes them onward automatically: the
    # scene-flow hub is posed, so handoff is seamless rather than a manual `whereto`. (Guarded so
    # the hub itself, which never uses `end`, can't recurse.)
    if opt.get("end"):
        character.db.scene_flags = None
        if getattr(getattr(character, "db", None), "scene_autohub", False):
            try:
                pose_named(character, "facility_hub", room=getattr(character, "location", None))
            except Exception:
                pass
    return opt, msg


@effect("make_example")
def _eff_make_example(character, p):
    """A public lesson — real compliance.make_example (overstim + standing hit + broadcast)."""
    try:
        from world.compliance import make_example
        make_example(character, severity=int(p.get("severity", 2) or 2),
                     reason=p.get("reason", "made an example"))
    except Exception:
        pass
    return "example"


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


@effect("edge_set")
def _eff_edge_set(character, p):
    """Edged and held at the brink — sets the REAL denial state (orgasm_denial + a raised
    arousal_floor) and banks edge-arousal via the arousal script. All flags are in FACILITY_FLAGS.
    params: floor (arousal_floor minimum), arousal (banked)."""
    try:
        character.db.orgasm_denial = True
        character.db.arousal_floor = max(float(getattr(character.db, "arousal_floor", 0) or 0),
                                         float(p.get("floor", 60.0)))
    except Exception:
        pass
    try:
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(character); add_arousal(character, float(p.get("arousal", 30.0)))
    except Exception:
        pass
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, float(p.get("cond", 2.0)), source="edged")
    except Exception:
        pass
    return "edged"


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


@effect("program_trigger")
def _eff_program_trigger(character, p):
    """Drill a REAL installed trigger — a phrase that, spoken by ANYONE, fires the conditioned
    response (binding_effects.install_trigger → installed_triggers, checked on all speech). Banks
    conditioning + suggestibility so the next one seats deeper. All flags floor-cleared.
    params: phrase, response (kneel/present/leak/recite...), strength, mantra, cond, sug."""
    try:
        from world.binding_effects import install_trigger
        install_trigger(character, p.get("phrase", "good girl"),
                        response=p.get("response", "kneel"),
                        strength=int(p.get("strength", 2)),
                        permanent=bool(p.get("permanent", False)),
                        mantra=p.get("mantra"))
    except Exception:
        pass
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, float(p.get("cond", 3.0)), source="programming")
    except Exception:
        pass
    try:
        character.db.suggestibility = (float(getattr(character.db, "suggestibility", 0) or 0)
                                       + float(p.get("sug", 2.0)))
    except Exception:
        pass
    return "programmed"


@effect("bred_by_own")
def _eff_bred_by_own(character, p):
    """The line folds back on itself: bred by your OWN grown get — a son/futa of yours sires into
    you. REAL: a gang_inseminate with sire = an offspring's name (pulled from the roster if present)
    + maybe_lineage_offspring to deepen the line a generation (bumps offspring_max_gen). Defensive:
    synthesizes a generic own-line sire if the roster's thin."""
    db = character.db
    roster = list(getattr(db, "offspring_roster", None) or [])
    counts = dict(getattr(db, "offspring_counts", None) or {})
    species = next(iter(counts), "bethany") if counts else "bethany"
    sire_name = None
    for e in roster:
        if isinstance(e, dict) and e.get("sex") in ("futa", "male") and e.get("name"):
            sire_name = e["name"]; species = e.get("species", species); break
    if not sire_name:
        sire_name = "your own get"
    parent_gen = int(getattr(db, "offspring_max_gen", 1) or 1)
    try:
        from world.gang_breeding import gang_inseminate, animal_holes, maybe_lineage_offspring
        import random as _r
        hs = [z for z in animal_holes(character).values() if z]
        if hs:
            gang_inseminate(character, _r.choice(hs), contributors=1, fluid_type="semen",
                            species=species, sire=sire_name)
        maybe_lineage_offspring(character, species, parent_gen)
    except Exception:
        pass
    return "line_folded"


@effect("give_birth")
def _eff_give_birth(character, p):
    """She drops her litter — REAL delivery via pregnancy.deliver: births the recorded offspring
    into the lineage, raises that species' quota, locks lactation (milk comes in), clears the
    belly. No-ops cleanly if she isn't actually carrying."""
    try:
        from world.pregnancy import deliver
        deliver(character)
    except Exception:
        pass
    return "delivered"


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


@effect("go_pet")
def _eff_go_pet(character, p):
    """Kept as the facility's pet — routes through the REAL conditioning pet-imprint
    (_cond_imprint sets pet_type + pet_trigger_sources) and sets a pet posture/body-language.
    params: pet_type ('puppy' default), cond (conditioning to add), posture (override).
    All flags are in FACILITY_FLAGS, so the §0 floor clears every bit of it."""
    ptype = p.get("pet_type", "puppy")
    try:
        # set the type first so the real imprint keeps it rather than defaulting to 'puppy'
        if not getattr(character.db, "pet_type", None):
            character.db.pet_type = ptype
        from world.conditioning import _cond_imprint
        _cond_imprint(character)
    except Exception:
        try:
            character.db.pet_type = character.db.pet_type or ptype
            character.db.pet_trigger_sources = character.db.pet_trigger_sources or ["facility"]
        except Exception:
            pass
    try:
        character.db.forced_posture = p.get("posture",
            f"down on all fours as a {character.db.pet_type or ptype} — no standing, no hands")
        character.db.body_language = f"a kept {character.db.pet_type or ptype} — collared, crawling, waiting to be told"
    except Exception:
        pass
    cond = float(p.get("cond", 0) or 0)
    if cond:
        try:
            from world.conditioning import add_conditioning
            add_conditioning(character, cond, source="kennel")
        except Exception:
            pass
    return "petted"


@effect("go_cumflate")
def _eff_go_cumflate(character, p):
    """Pumped/bred past full — bloats the body for REAL via add_inflation_volume on whatever
    inflatable zones the character has (the facility installs these at intake), which also feeds
    the installed WombRoom. No-ops cleanly if no inflation zone exists. Drained by tick + by the
    §0 reset (facility_build drains all inflation), so the swell is never permanent.
    params: amount (ml, default 1500), fluid ('cum' default), zone (override single zone)."""
    amount = float(p.get("amount", 1500.0) or 0)
    fluid = p.get("fluid", "cum")
    filled = []
    try:
        from typeclasses.inflation_item import add_inflation_volume, get_inflation_data
        zones = getattr(character.db, "zones", None) or {}
        targets = [p["zone"]] if p.get("zone") else list(zones.keys())
        for zname in targets:
            if get_inflation_data(character, zname):
                vol, state = add_inflation_volume(character, zname, amount, fluid)
                if vol is not None:
                    filled.append((zname, state))
    except Exception:
        pass
    return "cumflated" if filled else "cumflate_noop"


@effect("bethany_brand")
def _eff_bethany_brand(character, p):
    """Bethany claims you with her personal B — REAL: ownership (bethany_owned + title claim,
    mirroring bethany_script._mark_owned), bethany_branded, and a real freeform mark via
    record_mark (which shows in marks/brands/look; falls back to facility_brands). All flags are
    in FACILITY_FLAGS, so the §0 floor clears the ownership/brand state (the freeform mark is a
    normal mark, removed by the realm teardown's mark-clear). params: devotion."""
    d = character.db
    try:
        d.bethany_owned = True
        if not getattr(d, "facility_title_backup", None):
            d.facility_title_backup = {"faction": getattr(d, "title_faction", "") or "",
                                       "suffix":  getattr(d, "title_suffix", "") or ""}
        d.title_suffix = "— Bethany's"
        d.bethany_branded = True
    except Exception:
        pass
    try:
        from world.gang_breeding import record_mark
        record_mark(character, "a personal |wB|n branded into the skin — Bethany's own mark, raised "
                    "and permanent, the one she saves for the favourites she keeps as her own line")
    except Exception:
        pass
    try:
        from typeclasses.bethany_script import bethany_deposit_effect
        bethany_deposit_effect(character, devotion=float(p.get("devotion", 5.0)))
    except Exception:
        pass
    return "branded_hers"


@effect("go_pod")
def _eff_go_pod(character, p):
    """Sealed into a Deep Stock pod — the terminus state: total_dependence + body_processing_locked
    + navigation_locked + lactation_locked (the pod milks you) + optional sensory_hood. All flags
    are in FACILITY_FLAGS, so the §0 floor / the word opens the pod and clears every bit.
    params: hood (bool), cond (conditioning)."""
    for flag in ("total_dependence", "body_processing_locked", "navigation_locked",
                 "lactation_locked"):
        try: setattr(character.db, flag, True)
        except Exception: pass
    if p.get("hood"):
        try: character.db.sensory_hood = True
        except Exception: pass
    try:
        character.db.forced_posture = ("sealed in a pod — suspended in warm gel, plumbed to the "
                                       "feed and breed and milk lines, kept")
        character.db.body_language = "deep stock — podded, plumbed, indefinitely kept"
    except Exception:
        pass
    cond = float(p.get("cond", 0) or 0)
    if cond:
        try:
            from world.conditioning import add_conditioning
            add_conditioning(character, cond, source="deep_stock_pod")
        except Exception:
            pass
    return "podded"


@effect("go_bound")
def _eff_go_bound(character, p):
    """Bound in the rig — sets the REAL bondage state (navigation_locked + self_cmds_locked +
    a forced_posture/body_language) so movement and self-commands are genuinely held. All flags
    are in FACILITY_FLAGS, so the §0 floor (and the safeword) frees you completely.
    params: posture (override), cond (conditioning to add)."""
    try:
        character.db.navigation_locked = True
        character.db.self_cmds_locked = True
    except Exception:
        pass
    try:
        character.db.forced_posture = p.get("posture",
            "bound in the rig — wrists, ankles, throat, spread and fixed where you were hung")
        character.db.body_language = "bound and helpless — strapped open, going nowhere"
    except Exception:
        pass
    cond = float(p.get("cond", 0) or 0)
    if cond:
        try:
            from world.conditioning import add_conditioning
            add_conditioning(character, cond, source="bondage")
        except Exception:
            pass
    return "bound"


@effect("go_doll")
def _eff_go_doll(character, p):
    """Sealed into a doll/toy — sets the REAL latex/seal flags (latex_sealed, optionally
    sensory_hood) + a posable doll posture/body-language. All flags are in FACILITY_FLAGS, so
    the §0 floor unseals you completely. params: hood (bool), cond (conditioning), posture."""
    try:
        character.db.latex_sealed = True
    except Exception:
        pass
    if p.get("hood"):
        try: character.db.sensory_hood = True
        except Exception: pass
    try:
        character.db.forced_posture = p.get("posture",
            "posed where you were last set — smooth, sealed, an object that holds the shape it's given")
        character.db.body_language = "a sealed doll — featureless, posable, waiting to be arranged"
    except Exception:
        pass
    cond = float(p.get("cond", 0) or 0)
    if cond:
        try:
            from world.conditioning import add_conditioning
            add_conditioning(character, cond, source="dollification")
        except Exception:
            pass
    return "dolled"


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


# ── builder registry: choices as data, posable by id, chainable ──────────────
# A builder is fn(character) -> {key, prompt, options[], default} (or None if N/A here).
# Tagged "root" builders are eligible for the cycle's random pose; any builder can be reached
# by id via an option's `then` (chaining) or by pose_named().
_BUILDERS = {}
_ROOTS = []


def choice(cid, root=False):
    def deco(fn):
        _BUILDERS[cid] = fn
        if root:
            _ROOTS.append(cid)
        return fn
    return deco


def pose_named(character, cid, room=None):
    """Build choice `cid` for this character and pose it. Returns the pending dict or None."""
    fn = _BUILDERS.get(cid)
    if not fn:
        return None
    try:
        spec = fn(character)
    except Exception:
        spec = None
    if not spec or not spec.get("options"):
        return None
    return pose_choice(character, spec.get("key", cid), spec["prompt"], spec["options"],
                       default_key=spec.get("default"), room=room, then=spec.get("then"))


def pose_random(character, room=None):
    """Pose a random root choice (the cycle's auto-poser). Skips builders that return None
    (e.g. the hole menu when she has no orifices)."""
    if not _ROOTS:
        return None
    for cid in random.sample(_ROOTS, k=len(_ROOTS)):
        if pose_named(character, cid, room=room):
            return cid
    return None


# ── scene memory: the difference between a deck of postcards and a scene ─────
def scene_flag(character, key, default=None):
    """Read a flag set earlier in the current scene (via an option's `set`)."""
    return (getattr(character.db, "scene_flags", None) or {}).get(key, default)


def start_scene(character, first_node, room=None, flags=None):
    """Begin a choice-driven scene: reset its memory and pose the opening beat. The scene then
    runs entirely on the player's choices (resolve_choice + `then`), never a timer."""
    character.db.scene_flags = dict(flags or {})
    posed = pose_named(character, first_node, room=room)
    if not posed:
        character.db.scene_flags = None
    return posed


def end_scene(character):
    character.db.scene_flags = None


def subject_name(character):
    """Her real name for the scene — designation if one's been forced, else rp_name/key."""
    return (getattr(character.db, "designation", None)
            or getattr(character.db, "rp_name", None)
            or getattr(character, "name", "you"))


# ── invoking the real facility systems from a choice ─────────────────────────
def _cycle_script(character):
    try:
        from typeclasses.facility_script import RealmCycleScript, FacilityScript
        for s in character.scripts.all():
            if isinstance(s, (RealmCycleScript, FacilityScript)):
                return s
    except Exception:
        return None
    return None


@effect("facility")
def _eff_facility(character, p):
    """Run a real facility method on her — the spine that passes facility content to CYOA.
    params: {method, kind} where kind = proc|dose (room,target,t) / gang (…,cond) /
    scene (…,cond,orifices). No-ops cleanly if the cycle isn't running."""
    s = _cycle_script(character)
    room = getattr(character, "location", None)
    if not s or not room:
        return ""
    t = character.db.rp_name or getattr(character, "name", "she")
    method = p.get("method"); kind = p.get("kind", "proc")
    fn = getattr(s, method, None)
    if not fn:
        return ""
    cond = float(getattr(character.db, "conditioning", 0) or 0)
    try:
        if kind == "gang":
            fn(room, character, t, cond)
        elif kind == "scene":
            fn(room, character, t, cond, s._orifices(character))
        else:
            fn(room, character, t)
    except Exception:
        pass
    return method or ""


# ── the choice graph (filthy, real, chainable) ───────────────────────────────
@choice("beg", root=True)
def _b_beg(character):
    return {"key": "beg", "prompt": (
        "Your arousal's wound to the edge and held there, denied, aching. A handler stands at "
        "your station with the release key on one finger and all the time in the world. \"Ask "
        "nicely,\" she says, \"or don't. Up to you.\""),
        "options": [
            {"key": "beg", "label": "Beg for it", "effect": "grant_relief",
             "desc": "out loud, degrading, granted — and the relief is the leash",
             "outcome": "You beg — and you hear how easily it comes, how practised it's getting, "
                        "the please-please-please spilling out before pride can catch it. She lets "
                        "you have it, finally, and the orgasm rips through you so hard and so "
                        "grateful that the lesson writes itself: relief is something they hand you "
                        "for grovelling, never something you own. You'll beg faster next time. You "
                        "already know you will."},
            {"key": "hold", "label": "Hold out", "effect": "deny_hold",
             "desc": "keep that scrap of self; stay denied and aching, conditioned deeper for it",
             "outcome": "You don't beg. You hold the line, jaw tight, and she just... shrugs, and "
                        "pockets the key, and leaves you strung out at the edge with nothing — the "
                        "ache redoubling, the denial sinking another hook in. It's the last scrap "
                        "of yourself, this refusing, and it costs you more every cycle to keep it. "
                        "One day the math won't be worth it. They're patient. They can wait for that day."}],
        "default": "hold"}


@choice("deal", root=True)
def _b_deal(character):
    sp = random.choice(["hound", "bull", "contributor"])
    return {"key": "deal", "prompt": (
        f"A handler crouches to your level, friendly as anything. \"Tell you what. Take a rest "
        f"beat right now — off the line, off your feet — and we just double your {sp} quota to "
        f"make it up. Deal?\""),
        "options": [
            {"key": "take", "label": "Take the rest", "effect": "quota_deal",
             "params": {"species": sp, "bump": 6}, "desc": f"a beat off now — +6 {sp} quota, forever, after",
             "outcome": f"You take it — God, you take it, a whole beat off your feet with nothing "
                        f"inside you — and it's heaven for exactly as long as it lasts, which is "
                        f"not long, and then the {sp} number on your board ticks up six and stays "
                        f"there. You bought minutes with months. You'll do it again anyway, when "
                        f"you're tired enough, and that's the whole trick of it: they sell rest to "
                        f"the exhausted at any interest, and the exhausted always pay."},
            {"key": "refuse", "label": "Refuse it", "effect": "submit_standing",
             "desc": "no rest; she notes your compliance and moves on",
             "outcome": "You refuse — no deals, not today. She smiles like that's the cutest thing, "
                        "writes 'cooperative — declined incentive' (because refusing the bribe still "
                        "reads as good behaviour on her sheet, there's no winning column), and the "
                        "line takes you straight back without the rest you could've had. Principle "
                        "is expensive in here. They make very sure of that."}],
        "default": "take"}


@choice("hole", root=True)
def _b_hole(character):
    s = _cycle_script(character)
    holes = []
    if s:
        try:
            holes = (s._holes_only(character) or []) + [z for z in s._orifices(character) if s._is_oral(z)]
        except Exception:
            holes = []
    holes = holes[:3]
    if not holes:
        return None
    opts = [{"key": z, "label": f"Offer your {z.split('/')[-1].replace('_', ' ')}",
             "effect": "pick_hole", "params": {"zone": z},
             "desc": "the one you pick gets used — and trained for the choosing",
             "outcome": f"You point them at your {z.split('/')[-1].replace('_', ' ')} — pick your own "
                        f"poison — and they take you at your word, working it open and using it while "
                        f"the others wait their turn another day. You chose, and choosing is the only "
                        f"power they let you keep precisely because spending it is just obedience "
                        f"wearing a bow. That hole gets a little looser, a little more 'yours to offer,' "
                        f"for the asking."} for z in holes]
    return {"key": "hole", "prompt": (
        "\"Dealer's choice,\" the handler says, gesturing down your body with bored magnanimity. "
        "\"Pick the hole. We're using one regardless — but you get to say which.\""),
        "options": opts, "default": holes[0]}


@choice("slip", root=True)
def _b_slip(character):
    return {"key": "slip", "prompt": (
        "You can feel it happening again — the room going big, the words going round, the warm "
        "small quiet rising up to take you. You could let it. You could claw back up into yourself "
        "one more time. It's getting harder to tell which one you want."),
        "options": [
            {"key": "let", "label": "Let yourself go small", "effect": "go_little",
             "params": {"amount": 8.0}, "desc": "sink into little; it's easier down there, and it takes",
             "outcome": "You stop holding on. The big heavy grown-up weight of being a person who "
                        "knows things just... slides off, and the warm comes up over your head, and "
                        "it's so much easier down here where the words are round and the choices "
                        "aren't yours. You go little, and a little more of the way back up goes with "
                        "it. Each time you let it, there's less of a you left to claw with later."},
            {"key": "fight", "label": "Claw back up", "effect": "deny_hold",
             "params": {"cond": 3.0}, "desc": "stay big a little longer; it costs you, and you'll face this again",
             "outcome": "You drag yourself back up into the big, sharp, exhausting clarity of being "
                        "someone — and it hurts, and it's lonely up here, and the place leans on you "
                        "harder for the effort. You hold. For now. But the slipping's a current and "
                        "you're swimming against it, and they have nothing but time, and you have to "
                        "sleep eventually. You both know how this ends. You just chose 'not yet' again."}],
        "default": "let"}


@choice("offer", root=False)
def _b_offer(character):
    """Player entry (the `offer` command): she presents herself, and the facility obliges with
    real processing — each branch invokes a real system (or chains deeper)."""
    return {"key": "offer", "prompt": (
        "You present yourself — the one scrap of initiative they leave you, because offering is "
        "just obeying with extra steps, and they love to watch you reach for it. \"Well?\" the "
        "handler says, pen poised. \"What are you good for today? Tell us. We'll oblige.\""),
        "options": [
            {"key": "bred", "label": "Offer to be bred", "effect": "facility",
             "params": {"method": "_gang", "kind": "gang"}, "desc": "the line takes you, for real",
             "outcome": "\"Bred, please,\" you hear yourself say, and the handler ticks it like an "
                        "order at a counter. The stock obliges immediately — you asked, so they don't "
                        "even pretend to make you. Offering it was just obeying with the extra step "
                        "of wanting on the record. They love that step most."},
            {"key": "milked", "label": "Offer to be milked", "effect": "facility",
             "params": {"method": "_do_milk", "kind": "proc"}, "desc": "drained on the spot",
             "outcome": "You offer your tits up and the cups are on you before the sentence finishes, "
                        "pulling you down to slack and aching while a gauge logs what your asking-for-it "
                        "produces. Same draw either way — but you reached for the machine this time, "
                        "and it noticed."},
            {"key": "marked", "label": "Offer to be marked", "effect": "facility",
             "params": {"method": "_procedure", "kind": "proc"}, "desc": "a real, permanent procedure of their choosing",
             "outcome": "You offer yourself to the parlour's discretion — a blank cheque written on "
                        "your own skin. They take you up on it, of course, with something permanent of "
                        "their choosing, and you don't get to know what until it's healing. Trusting "
                        "them to pick was the real offering. They'll spend that trust like everything else."},
            {"key": "dosed", "label": "Offer to be dosed", "effect": "facility",
             "params": {"method": "_dose", "kind": "proc"}, "desc": "something experimental, undocumented",
             "outcome": "You ask for the cart. The attendant doesn't even tell you what's in the "
                        "syringe — undocumented, the label says, effects pending — and you held your "
                        "arm out for it anyway. Whatever it does to you over the next while, you "
                        "volunteered for. They wrote 'compliant' and something in a column you can't read."},
            {"key": "little", "label": "Offer to be made little", "effect": "go_little",
             "params": {"amount": 6.0}, "then": "slip", "desc": "ask for it small, and keep slipping",
             "outcome": "You ask to be made little — in a small voice, which is already most of the "
                        "way there. The warm comes up to meet you the second you give it permission, "
                        "because asking IS permission, and down you go, soft and easy and already "
                        "reaching for the next step down."}],
        "default": "bred"}


@choice("emphasis", root=True)
def _b_emphasis(character):
    return {"key": "emphasis", "prompt": (
        "Intake wants to know how to spend you today — a courtesy it extends exactly once, and "
        "only because your answer doesn't change that you'll get all of it eventually."),
        "options": [
            {"key": "milk", "label": "Start at the dairy", "effect": "emphasis",
             "params": {"which": "milk"}, "desc": "weighted toward the cups this stretch",
             "outcome": "You say the dairy, and the clerk hums approval — they do like a girl who "
                        "knows her best use. The schedule re-weights toward the cups: more hours "
                        "racked and drawn, more of your day spent leaking on the clock. You picked "
                        "your own leash colour. They'd have put you there anyway, but this way you "
                        "asked, and asking is the part they keep."},
            {"key": "breed", "label": "Start in the pens", "effect": "emphasis",
             "params": {"which": "breed"}, "desc": "weighted toward breeding this stretch",
             "outcome": "The pens, you say. The schedule tilts toward the stalls — more mountings, "
                        "more knots, more of your cycle spent presented and filled. You chose the "
                        "harder use because some part of you has stopped fighting where this goes, "
                        "and they wrote that part down the day you let it show."},
            {"key": "condition", "label": "Start in the cell", "effect": "emphasis",
             "params": {"which": "condition"}, "desc": "weighted toward conditioning this stretch",
             "outcome": "You ask for the cell. The clerk's eyebrow lifts — that's the one nobody "
                        "asks for, the dark and the drone and the slow quiet hollowing-out of "
                        "whatever's still arguing in you. The schedule obliges. You requested your "
                        "own unmaking, and on some level you knew exactly what you were asking for, "
                        "and asked anyway. That's further along than you think."}],
        "default": "breed"}


@effect("devote")
def _eff_devote(character, p):
    """Route a devotion bump through the cycle's _devote (Bethany's owner arc) if running."""
    s = _cycle_script(character)
    if s and hasattr(s, "_devote"):
        try:
            s._devote(character, float(p.get("amount", 5.0)), room=getattr(character, "location", None))
        except Exception:
            pass
    else:
        character.db.bethany_devotion = float(getattr(character.db, "bethany_devotion", 0) or 0) + float(p.get("amount", 5.0))
    return "devoted"


@choice("intake", root=True)
def _b_intake(character):
    """The signature multi-step opening: contract → strip/inspection → first use → emphasis.
    Crude, expansive, and entirely real — each step chains into the next."""
    return {"key": "intake", "prompt": (
        "The clerk slides a form across the counter and a pen on a chain worn shiny by a hundred "
        "shaking hands. The fine print runs to pages you'll never read; the visible line just says "
        "RESIDENT, and a blank for your name that won't be yours much longer. She doesn't rush you. "
        "They never rush you — the not-rushing is how they get you to do it yourself. \"One question "
        "before we begin, sweetheart,\" she says, bright as a receptionist booking a dental clean. "
        "\"Are you here because you want to be? It changes nothing. I just like to write it down.\""),
        "options": [
            {"key": "yes", "label": "\"Yes.\" Say you want it", "effect": "devote",
             "params": {"amount": 4.0}, "then": "intake_strip",
             "desc": "the wanting goes in the file, in ink, to be read back to you on your worst days",
             "outcome": "You say it. Out loud. \"Yes.\" She writes it down without looking up, and "
                        "the word sits in you heavier than the signature does — because the signature "
                        "they made you give, but the wanting you brought in yourself, and you both know it."},
            {"key": "unsure", "label": "\"I'm not sure...\"", "effect": "deny_hold",
             "params": {"cond": 2.0}, "then": "intake_strip",
             "desc": "unsureness is just a yes that takes longer; she ticks the box anyway",
             "outcome": "\"Mm. They never are, at first.\" She ticks a box that was always going to "
                        "be ticked, slides the signed page into a folder with your number on it, and "
                        "the not-sure curdles quietly into here-anyway while she's still smiling at you."}],
        "default": "unsure"}


@choice("intake_strip")
def _b_intake_strip(character):
    """Step 2: stripped, weighed, holes inventoried — processed from person to stock."""
    return {"key": "intake_strip", "prompt": (
        "\"Clothes in the bin, please. You won't be needing them — Residents are kept as they'll be "
        "kept, and that's bare.\" Two attendants don't wait for you to finish; they strip you down, "
        "weigh you like produce, and walk you to the inspection table. Cold hands, a clipboard, a "
        "gloved finger checking every hole you've got — measuring, noting depth and give, thumbing "
        "your tits for yield, all of it read aloud to the room in flat clinical numbers like you're "
        "not standing right there listening to yourself be itemised. \"Right then. How do you want to "
        "do the inspection — easy, or do we hold you?\""),
        "options": [
            {"key": "present", "label": "Present yourself for it", "effect": "submit_standing",
             "then": "intake_first",
             "desc": "spread for the gloved hands on your own; learn early how much easier obeying is",
             "outcome": "You do it yourself — feet apart, hands behind your head, holes offered up to "
                        "the cold glove without being forced. The attendant nods, bored, and notes "
                        "'cooperative' on the sheet, and the small sick relief you feel at the praise "
                        "is the first thing they've successfully taught you. It won't be the last."},
            {"key": "cover", "label": "Cover yourself", "effect": "deny_hold",
             "params": {"cond": 3.0}, "then": "intake_first",
             "desc": "futile — they pin you and check you anyway, slower, and note the resistance",
             "outcome": "You cover up on instinct. They sigh like you've inconvenienced a queue, pin "
                        "your wrists, and do the whole inspection slower for it — every hole spread "
                        "and gauged while you're held, the glove unhurried and thorough and entirely "
                        "indifferent to the noise you make. 'Resistant,' goes the sheet. They do love a project."}],
        "default": "present"}


@choice("intake_first")
def _b_intake_first(character):
    """Step 3: the first use, before you've even been processed — to set the tone."""
    holes = ["mouth", "cunt"]
    s = _cycle_script(character)
    if s:
        try:
            real = (s._holes_only(character) or []) + [z for z in s._orifices(character) if s._is_oral(z)]
            if real:
                holes = real[:2]
        except Exception:
            pass
    def _zlabel(z):
        return z.split("/")[-1].replace("_", " ")
    return {"key": "intake_first", "prompt": (
        "\"Last thing, then we'll get you on the line.\" A handler's already freeing himself, half-"
        "hard and patient, because intake always ends the same way — they put something in you before "
        "you've signed off being a person, so your very first memory of the place is being used in it. "
        "\"Pick where it goes. First and last courtesy you'll get for a while — after this nobody asks.\""),
        "options": [
            {"key": holes[0], "label": f"Offer your {_zlabel(holes[0])}", "effect": "pick_hole",
             "params": {"zone": holes[0]}, "then": "emphasis",
             "desc": "the one you name is the one he takes — and it's logged as yours to have offered",
             "outcome": f"You name it, and that's permission enough; he feeds himself into your "
                        f"{_zlabel(holes[0])} slow and deep while the clerk times it on her watch, "
                        f"and you learn the place's first real lesson — that choosing which hole is the "
                        f"only choice they'll ever let you keep, and they only let you keep it because "
                        f"picking is its own little surrender."},
            {"key": "wait", "label": "\"Please — not yet.\"", "effect": "deny_hold",
             "params": {"cond": 4.0}, "then": "emphasis",
             "desc": "denied; he picks for you and takes it anyway, and 'not yet' goes on the file too",
             "outcome": "\"Not yet,\" you manage. \"There's no yet, sweetheart. There's now, and there's "
                        "later, and they're the same.\" He picks for you — the hole you'd least have "
                        "offered — and takes it anyway, unhurried, while you're held and your own 'please' "
                        "is read back into the record in a flat little voice. You will hear it quoted again."}],
        "default": "wait"}


@choice("bethany")
def _b_bethany(character):
    """A Bethany-voiced personal branch — she offers to make you hers, which is worse than the line."""
    return {"key": "bethany", "prompt": (
        "Bethany crouches to your level with that bright, fond, terrible smile and tips your chin "
        "up. \"I could leave you on the line with the other stock,\" she muses, \"or I could take "
        "you. Properly. Mine — file, line, brand, the lot. The line forgets you. I never would. "
        "Which sounds worse to you, sweetheart? Be honest. I'll know.\""),
        "options": [
            {"key": "hers", "label": "Ask to be hers", "effect": "devote",
             "params": {"amount": 10.0}, "desc": "warmer, crueller, kept — her favourite, bred to her line, never anonymous again",
             "outcome": "You ask. Quietly, hating it, you ask to be hers — and her whole face lights "
                        "up warm and genuine and terrible, and she kisses your forehead like you've "
                        "made her day, because you have. \"Good girl. Mine, then.\" And that's so much "
                        "worse than the line, because the line is indifferent and Bethany is not — "
                        "she'll brand you with her own little B, breed her own line into you, keep "
                        "a file thick with fond cruelty, and want you to be grateful, and you will be. "
                        "That's the part she was after. You handed it to her yourself."},
            {"key": "line", "label": "Stay anonymous stock", "effect": "submit_standing",
             "desc": "a number on the line; she smiles like she's got time, because she does",
             "outcome": "You choose the line. Anonymous. A number among numbers, used and forgotten "
                        "in rotation. Bethany just smiles, unbothered, and pats your cheek. \"Of "
                        "course. We'll see.\" Because she has all the time in the world to let the "
                        "line wear you down to where being *kept* by someone — anyone, even her — "
                        "starts to look like mercy. She's not in a hurry. She's never in a hurry. "
                        "She'll ask again when you're softer, and one day you'll say yes."}],
        "default": "hers"}


@choice("correction", root=True)
def _b_correction(character):
    """She slipped (or didn't) — pick the correction. All of them are the facility, for real."""
    return {"key": "correction", "prompt": (
        "\"Little correction's overdue,\" a handler says, consulting nothing. \"Doesn't matter "
        "what for; there's always a for. Pick your medicine — it's the only part you get a say in, "
        "and we only offer because choosing it is half the lesson.\""),
        "options": [
            {"key": "condition", "label": "The cell", "effect": "facility",
             "params": {"method": "_dose", "kind": "proc"}, "desc": "dosed and conditioned deeper",
             "outcome": "You pick the cell — quieter, you think, easier than the pens or the iron. "
                        "You think wrong. They strap you into the dark, run something cold into your "
                        "arm, and let the drone do the rest, and you come out the far side with a "
                        "little more of your edges sanded off and no clear memory of choosing it. "
                        "The cell is the one that takes the most and shows the least. That's why "
                        "the frightened ones pick it."},
            {"key": "breed", "label": "The pens", "effect": "facility",
             "params": {"method": "_gang", "kind": "gang"}, "desc": "bred until the lesson takes",
             "outcome": "The pens, you decide — get it over with, the honest punishment, the one you "
                        "can see coming. They bend you over and the stock takes its turns until "
                        "whatever you did wrong has been thoroughly fucked out of you and replaced "
                        "with the dull, bred-stupid quiet they were after. Lesson delivered. You "
                        "won't even remember the infraction. You'll remember the correction."},
            {"key": "mark", "label": "The parlour", "effect": "facility",
             "params": {"method": "_procedure", "kind": "proc"}, "desc": "a permanent mark to remember it by",
             "outcome": "The parlour, then — let it be quick, let it be over. It is not quick, and "
                        "it is never over: the iron or the needle or the rings go in to stay, and "
                        "you'll carry this correction on your skin under everything you ever wear, "
                        "long after you've forgotten what earned it. They like the permanent ones. "
                        "A body that reads like a rap sheet saves everyone the trouble of asking."}],
        "default": "breed"}


# ── deeper effects: real clause installation + the descent ───────────────────
_CLAUSE_PAYLOADS = {
    "teat_gag":      {"gag_word": "hush little one", "uncork_word": "words back", "fluid": "semen"},
    "nurse_first":   {"fluid": "semen"},
    "stuffed_mouth": {"fluid": "semen"},
    "beg_small":     True,
    "star_chart":    True,
    "heat_tell":     True,
    "honorifics":    True,
}


@effect("clause")
def _eff_clause(character, p):
    """Install a real hidden clause on her through the binding-effects engine — the SAME path the
    contract uses, so it actually takes hold (triggers seated, filters/gates set), not narrated.
    params: {key}. The §0 floor clears whatever it installs (all in FACILITY_FLAGS)."""
    key = p.get("key")
    if not key:
        return ""
    eff = {key: p.get("payload", _CLAUSE_PAYLOADS.get(key, True))}
    try:
        from world.binding_effects import apply_effects

        class _Carrier:
            def __init__(self, e):
                self.db = type("_d", (), {"binding_effects": e})()
                self.dbref = "#0"
        apply_effects(character, _Carrier(eff))
    except Exception:
        pass
    return key


@effect("deepen")
def _eff_deepen(character, p):
    """A hard slug of conditioning + (optionally) regression — the descent biting in for real."""
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, float(p.get("cond", 10.0)), source="descent")
    except Exception:
        pass
    if p.get("regress"):
        try:
            from world.regression import regress
            regress(character, float(p.get("regress", 8.0)), source="descent")
        except Exception:
            pass
    return "deepened"


@choice("clause")
def _b_clause(character):
    """An addendum is produced — a real hidden clause, installed whichever way she answers."""
    key = random.choice(["teat_gag", "nurse_first", "stuffed_mouth", "beg_small", "star_chart",
                         "heat_tell", "honorifics"])
    blurb = {
        "teat_gag":      "a gag-word any mouth in the building can say to plug yours with a teat you'll suckle helpless on",
        "nurse_first":   "a clause that won't let you speak a first word to anyone until you've nursed a load down",
        "stuffed_mouth": "a clause filing your speech down to cock-muffled fragments, your mouth retooled off words",
        "beg_small":     "a clause that denies you release as of right — you'll beg small for every drop of it now",
        "star_chart":    "a chart where relief is bought with stars earned the only way the work earns them",
        "heat_tell":     "a clause that makes your body honest — every word you speak from now drags your "
                         "real arousal out with it, a tell you can't hide, louder the wetter you are",
        "honorifics":    "a clause that takes your manners out of your hands — whenever anyone who owns, "
                         "loves, or sired you is in the room, not one word leaves your mouth until you've "
                         "addressed them the way you've been taught (Owner, Mommy, love...)",
    }[key]
    return {"key": "clause", "prompt": (
        "Bethany sets a single fresh page on the desk between you, already signed at the bottom — "
        "by you, in your hand, on a day you don't remember signing it (Clause 23: she may amend, "
        "and you accepted all of it, read and unread). \"Just initialling the addendum, sweetheart,\" "
        "she says warmly. \"It's already in force; the initial's only so you feel like you were "
        f"asked.\" The addendum installs {blurb}."),
        "options": [
            {"key": "initial", "label": "Initial it", "effect": "clause", "params": {"key": key},
             "desc": "put your mark to the thing that's already binding you — and feel it take hold",
             "outcome": "You initial it. The pen's barely lifted before the clause closes over you "
                        "like a circuit completing — you feel the exact moment it takes, something "
                        "rerouted under your skin that won't reroute back, and Bethany files the page "
                        "with a little satisfied pat. \"There. Now it's yours too. Doesn't that feel "
                        "tidier?\" It does, is the horror of it. It does."},
            {"key": "refuse", "label": "Refuse to sign", "effect": "clause",
             "params": {"key": key}, "then": "correction",
             "desc": "auto-consent means it binds anyway; refusing just earns you a correction on top",
             "outcome": "You refuse. Bethany doesn't even stop smiling — she just taps Clause 1, the "
                        "auto-consent, and the addendum takes hold exactly as hard as if you'd begged "
                        "for it, your refusal noted only as something to correct. The clause closes "
                        "over you regardless; the only thing your 'no' bought was the punishment "
                        "queued up behind it. You'll learn. They have a clause for the learning, too."}],
        "default": "initial"}


@choice("descent", root=True)
def _b_descent(character):
    """The signature deeper arc — she's been here long enough that the bottom looks like rest."""
    return {"key": "descent", "prompt": (
        "You've been on the cycle long enough now that something's shifted. The bottom of this "
        "place — the sealed pods, the kept things, the quiet — stopped reading as a threat a while "
        "ago and started, traitorously, reading as rest. Bethany watches you notice it. \"You feel "
        "it, don't you,\" she murmurs, fond. \"The pull. You could fight the current a while longer. "
        "Or you could ask me to take you down where the fighting stops. I'd be so proud.\""),
        "options": [
            {"key": "deeper", "label": "Ask to go deeper", "effect": "devote", "params": {"amount": 8.0},
             "then": "descent_mark",
             "desc": "say it out loud — that you want the bottom — and start the long way down",
             "outcome": "You ask. The words come out smaller and surer than you expected, and that "
                        "scares the last bit of you that's still scared of anything. Bethany glows. "
                        "\"Good girl. Down we go, then — properly, all the way. I'll be with you for "
                        "every floor of it.\" And the descent takes you, one earned ruin at a time."},
            {"key": "hold", "label": "Cling to the surface", "effect": "deny_hold", "params": {"cond": 4.0},
             "desc": "not yet — hold at the cycle a while longer; the current doesn't care",
             "outcome": "You cling on — not yet, not yet — and the cycle keeps you where you are, "
                        "milked and bred and conditioned in the same rotation, the current tugging "
                        "patient at your ankles. The surface isn't safety. It's just the last place "
                        "you can still see it from. Bethany pats your head and lets you have it, "
                        "because she knows exactly how long that lasts."}],
        "default": "deeper"}


@choice("descent_mark")
def _b_descent_mark(character):
    """Step 2: marked permanently for the descent in the parlour."""
    return {"key": "descent_mark", "prompt": (
        "First floor down is the parlour. \"Going deeper means going marked,\" Bethany explains, "
        "warming an iron. \"So the next handler, and the one after, knows at a glance what you've "
        "agreed to become. Hold still — or don't, it sets either way.\" Choose how you're labelled "
        "for the rest of it."),
        "options": [
            {"key": "brand", "label": "Take her brand", "effect": "facility",
             "params": {"method": "_procedure", "kind": "proc"}, "then": "descent_break",
             "desc": "a permanent mark seared in — real, on your skin, under everything forever",
             "outcome": "The iron comes off the bar dull-orange and goes into you, and the sound you "
                        "make is one you'll hear in the cell later — but when the pain clears there's "
                        "a mark on you that wasn't there this morning and never won't be again, and "
                        "some newly-quiet part of you is glad to finally match the outside to the in."},
            {"key": "ink", "label": "Take the ink", "effect": "facility",
             "params": {"method": "_procedure", "kind": "proc"}, "then": "descent_break",
             "desc": "needled in permanent — a label you'll read off yourself the rest of the term",
             "outcome": "The gun buzzes against you for a long, patient while, and what it leaves "
                        "behind you'll read upside-down off your own skin for the rest of the term — "
                        "a permanent caption for a thing that used to argue about what it was. The "
                        "argument's getting quieter. The ink doesn't argue at all."}],
        "default": "brand"}


@choice("descent_break")
def _b_descent_break(character):
    """Step 3: the cell breaks her deeper — real conditioning + regression."""
    return {"key": "descent_break", "prompt": (
        "Second floor down is the cell, and the dark, and the drone that doesn't stop. \"This is "
        "the part where we make room,\" Bethany says, settling you into the cradle, almost tender. "
        "\"For the descent to take, the parts of you that climb have to go quiet. You can fight the "
        "hollowing or sink into it — both end the same place, but one's so much kinder to you.\""),
        "options": [
            {"key": "sink", "label": "Sink into the hollowing", "effect": "deepen",
             "params": {"cond": 8.0, "regress": 10.0}, "then": "descent_terminus",
             "desc": "let the drone empty you; it's kinder, and it takes so much faster",
             "outcome": "You stop holding the shape of yourself and let the drone do its slow work, "
                        "and it IS kinder — the climbing parts go quiet one by one, the worry drains "
                        "out the bottom, and what's left is warm and small and wonderfully, finally "
                        "unbothered. You went down so easily. That's the last thing you think with "
                        "the old voice, and you don't even mind that it's the last."},
            {"key": "endure", "label": "Endure it", "effect": "deepen",
             "params": {"cond": 14.0}, "then": "descent_terminus",
             "desc": "grit through with your edges intact — it just runs the cell longer and harder",
             "outcome": "You grit through it, holding what's left of your edges — so they run the "
                        "cell longer, and harder, and the drone wins anyway by sheer hours, just "
                        "with more of you scraped raw in the losing. Enduring didn't save the parts "
                        "that climb. It only made you feel each one go. Bethany thought you might "
                        "pick this. She has notes on you."}],
        "default": "sink"}


@choice("descent_terminus")
def _b_descent_terminus(character):
    """The threshold of Deep Stock — the door, narrated heavy. Floor stays sacred; this is in-fiction."""
    return {"key": "descent_terminus", "prompt": (
        "And then you're at the bottom, or its threshold — the long humming vault of Deep Stock, "
        "row on row of sealed, plumbed, kept things that were residents once and are maintenance "
        "schedules now, bred and milked in their sleep, years deep, content in the only way a thing "
        "with no say left can be. A pod stands open. Your number's already on it. Bethany's hand is "
        "warm at the small of your back, not pushing — she never has to push, by now. \"There it is, "
        "sweetheart. Everything you've been walking toward. Step in, and it stops being hard forever. "
        "Or step back onto the cycle and we'll do all of this again until you don't want to.\""),
        "options": [
            {"key": "step", "label": "Step toward the pod", "effect": "deepen",
             "params": {"cond": 16.0, "regress": 8.0},
             "desc": "reach for the terminus — the kept quiet you've stopped being able to fear",
             "outcome": "You step toward it. Not all the way in — they savour this part too much to "
                        "let it be quick — but toward, reaching, wanting the sealed quiet with a "
                        "want they spent every cycle building into you. Bethany makes a small, "
                        "genuinely moved sound. \"Look at you. Reaching for it. We made something "
                        "beautiful.\" The pod waits. It's patient, like her. It can be — you're not "
                        "going anywhere now but down, and you'd thank her for it if she asked. "
                        "(The fire-exit is still lit and always will be: the floor is yours, this "
                        "instant, the second any of this stops being a thing you want.)"},
            {"key": "back", "label": "Step back onto the cycle", "effect": "deny_hold",
             "params": {"cond": 6.0},
             "desc": "not the pod — not yet; back to the rotation, the current still rising",
             "outcome": "You step back — not the pod, not yet — and Bethany doesn't mind at all, "
                        "walks you back up to the cycle with an arm around you like a friend after "
                        "a long night. \"Of course. There's no rush; you're not going anywhere I "
                        "can't reach.\" And the rotation closes over you again, milked and bred and "
                        "hollowed, the vault humming patient below, your number still on that pod, "
                        "waiting for the cycle to wear the 'not yet' down to a yes. It always does."}],
        "default": "back"}


@effect("mantra_set")
def _eff_mantra_set(character, p):
    """She repeated it — the mantra seats as a REAL installed trigger + conditioning, and the
    repetition leaves her more suggestible for the next thing the chair wants to put in."""
    phrase = p.get("phrase", "good girl")
    resp   = p.get("response", "recite")
    try:
        from world.binding_effects import install_trigger
        install_trigger(character, phrase, response=resp, strength=2,
                        mantra=p.get("mantra"))
    except Exception:
        pass
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, 5.0, source="mantra")
    except Exception:
        pass
    try:
        character.db.suggestibility = float(getattr(character.db, "suggestibility", 0) or 0) + 1.0
    except Exception:
        pass
    return f"mantra:{phrase}"


@choice("mantra")
def _b_mantra(character):
    """Posed by the spiral chair mid-trance: say it with me, or hold your tongue."""
    phrase, mantra = random.choice([
        ("spiral down", "down is where i live, down is where it's warm"),
        ("good girl",   "good girls don't decide, good girls feel wonderful"),
        ("empty",       "empty is quiet, quiet is good, i am so quiet now"),
        ("hers",        "i'm hers, i was always going to be hers, it's tidier this way"),
    ])
    return {"key": "mantra", "prompt": (
        f"Down in the warm turn of it, Bethany's recorded voice goes patient and bright — the "
        f"voice of a woman dictating to a typist she owns. |M\"Say it with me now, sweetheart. "
        f"'{mantra}.' Out loud. Your mouth's right there and I've already done the hard part. "
        f"Or hold your little tongue, if you must — the spiral doesn't mind. It just keeps "
        f"turning either way, and you're in it either way, and we both know which of us is "
        f"better at waiting.\"|n"),
        "options": [
            {"key": "repeat", "label": "Say it with her", "effect": "mantra_set",
             "params": {"phrase": phrase, "response": "recite", "mantra": mantra},
             "desc": "repeat it out loud — and it seats, a real trigger, yours to carry out of the chair",
             "outcome": f"You say it. Out loud, in the dark, in your own voice — '{mantra}' — and "
                        f"saying it is the seating of it: the words go down warm and find a groove "
                        f"that was sanded ready for them, and click in, and become true the way "
                        f"furniture is true. From now on, '{phrase}' will reach in and pull. You "
                        f"taught yourself the trick of it. She just held the spiral steady while "
                        f"you did. |M\"Perfect,\"|n the recording purrs. |M\"Again tomorrow.\"|n"},
            {"key": "silent", "label": "Hold your tongue", "effect": "deny_hold",
             "params": {"cond": 4.0},
             "desc": "refuse the words; the spiral just keeps turning, and the turning costs too",
             "outcome": "You press your lips shut and hold the words off, and it costs you the way "
                        "holding anything off in here costs — the spiral simply keeps turning, "
                        "patient as payroll, wearing the refusal thin against your own pulse. "
                        "|M\"Mm,\"|n says the recording, warmly unbothered. |M\"You held. I'll note "
                        "it. I note everything, sweetheart — including how much longer each hold "
                        "takes you. Would you like to know the trend? No. You wouldn't.\"|n"}],
        "default": "repeat"}


# ── the punishment chain: discipline with real teeth, posed only when earned ──
@effect("punish")
def _eff_punish(character, p):
    """Real discipline through world.compliance.punish — defiance ledger, streak break,
    the works. params: {reason, severity}."""
    try:
        from world.compliance import punish
        punish(character, reason=p.get("reason", "correction"), severity=int(p.get("severity", 1)))
    except Exception:
        pass
    return "punished"


@effect("filth")
def _eff_filth(character, p):
    """The pigsty sentence — REAL filth applied (gang_breeding.apply_filth) + the punishment."""
    try:
        from world.gang_breeding import apply_filth
        apply_filth(character)
    except Exception:
        pass
    try:
        from world.compliance import punish
        punish(character, reason="sentenced to the sty", severity=int(p.get("severity", 1)))
    except Exception:
        pass
    return "filthed"


@effect("gratitude")
def _eff_gratitude(character, p):
    """She thanked them for it — compliance registered (with its reward loop) + the gratitude
    conditioning that's the deepest part of the training."""
    try:
        from world.compliance import register_compliance
        register_compliance(character, reward=True)
    except Exception:
        pass
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, float(p.get("cond", 5.0)), source="gratitude")
    except Exception:
        pass
    return "grateful"


@choice("punished", root=True)
def _b_punished(character):
    """Conditional root — only poses when she's EARNED it (defiance / quota behind /
    freedom forfeited). pose_random skips it otherwise, so discipline is consequence."""
    d = character.db
    earned = (int(getattr(d, "defiance", 0) or 0) > 0
              or int(getattr(d, "quota_behind", 0) or 0) > 0
              or getattr(d, "freedom_forfeited", False))
    if not earned:
        return None
    return {"key": "punished", "prompt": (
        "The handler doesn't grab you. She just stops in front of your station with the tablet "
        "turned so you can see your own row on it — the defiance column, the arrears, the little "
        "red marks that have been quietly accruing while you told yourself nobody noticed. "
        "Everybody noticed. Noticing is the whole building. \"Right then,\" she says, pleasant as "
        "a dentist. \"Discipline review. Do you want to tell me what you did, or shall I read it "
        "to you? One of these goes much better for you, and I genuinely cannot remember which.\""),
        "options": [
            {"key": "confess", "label": "Confess it yourself", "effect": "submit_standing",
             "then": "punish_sentence",
             "desc": "say it out loud, all of it — owning your file is obedience, and they bank it",
             "outcome": "You confess — and it's worse than being read to, because your own mouth "
                        "makes the list, every slip and shortfall recited in your own voice while "
                        "she nods along like a teacher hearing times-tables. By the end you're "
                        "apologising for things she hadn't even flagged. \"Lovely,\" she says, and "
                        "ticks COOPERATIVE, and you feel the tick land somewhere it shouldn't feel "
                        "good, and it feels good. Now: the sentence."},
            {"key": "deny", "label": "\"I didn't do anything.\"", "effect": "punish",
             "params": {"reason": "denial on review", "severity": 1}, "then": "punish_sentence",
             "desc": "deny it — the file disagrees, and the file is the one they believe",
             "outcome": "\"I didn't—\" you start, and she just turns the tablet a little further "
                        "toward you, patient, while the timestamps and the yields and the logged "
                        "little refusals sit there being true. Denial goes in as its own infraction "
                        "— OBSTRUCTIVE, tick — and the room gets that much colder around your "
                        "station. The file doesn't argue. The file never has to. Now: the sentence, "
                        "plus interest."}],
        "default": "confess"}


@choice("punish_sentence")
def _b_punish_sentence(character):
    """Step 2: choose your sentence — every option a different real system biting."""
    return {"key": "punish_sentence", "prompt": (
        "\"Sentencing,\" the handler says, scrolling. \"You get a say. Not because it matters — "
        "because choosing your own punishment does something to a person that we find very "
        "useful downstream.\" She turns the tablet: three lines, three doors. \"The sty, the "
        "floor, or the line. Pick, or I pick, and I always pick the sty, because the smell "
        "amuses the clerk.\""),
        "options": [
            {"key": "sty", "label": "The sty", "effect": "filth",
             "params": {"severity": 1}, "then": "punish_after",
             "desc": "rutted face-down in the wallow and left caked in it — real filth, it doesn't wash",
             "outcome": "They walk you down to the sty and put you in it — properly in it, face-down "
                        "in the warm reek while the stock take their amusement, and when they haul "
                        "you out you're caked to the elbows and stinking of musk and dried piss, "
                        "and the filth is LOGGED, a state of you now, part of how you read. The "
                        "other residents look at you and look away. That was most of the sentence, "
                        "and everyone involved knows it."},
            {"key": "floor", "label": "The floor", "effect": "facility",
             "params": {"method": "_gang", "kind": "gang"}, "then": "punish_after",
             "desc": "public correction — used on the open floor where the whole shift can watch",
             "outcome": "The floor, then — the open one, mid-shift, where every rack and rig has a "
                        "sightline. They bend you over your own station and the correction is "
                        "administered the way the facility administers everything: thoroughly, "
                        "rhythmically, and in front of an audience that doesn't even slow its work "
                        "to watch, because this is just Tuesday, and you being used as the example "
                        "is just the curriculum."},
            {"key": "line", "label": "The line", "effect": "punish",
             "params": {"reason": "sentenced to the line", "severity": 2}, "then": "punish_after",
             "desc": "the formal discipline — strokes counted aloud, severity 2, entered in the ledger",
             "outcome": "The line is the honest one — the frame, the strap, the count. They make "
                        "you keep the count yourself, out loud, and start it over when your voice "
                        "breaks, which it does, twice. By the end the numbers are the only words "
                        "you have left and the ledger has a tidy new entry and your whole backside "
                        "is a lesson you'll be sitting on for days. Severity two. They were kind. "
                        "They wanted you to know they could have been kinder."}],
        "default": "sty"}


@choice("punish_after")
def _b_punish_after(character):
    """Step 3: the aftermath — and the only question that ever mattered to them."""
    return {"key": "punish_after", "prompt": (
        "After, the handler crouches to your level — they all learned that from Bethany — and "
        "waits for your breathing to come back. \"One more thing, and then we're square,\" she "
        "says, kind as anything. \"Say thank you. That's all. It's the only part of this that was "
        "ever the point — the sty washes off eventually, the strokes fade, but a thank-you that "
        "you *mean*... that one we keep.\""),
        "options": [
            {"key": "thank", "label": "Thank her — and mean it", "effect": "gratitude",
             "params": {"cond": 6.0},
             "desc": "the gratitude is the deepest conditioning there is, and they bank every word",
             "outcome": "\"Thank you,\" you say, and the horrible thing — the thing you'll be awake "
                        "with later — is that you do mean it, a little, somewhere; the punishment "
                        "drew a line under something and the line felt like being held. She smiles "
                        "like the sun coming out and notes it, and the gratitude goes down into you "
                        "where the conditioning lives, and settles in like it owns the place. It's "
                        "starting to. That was always the design."},
            {"key": "silent", "label": "Say nothing", "effect": "punish",
             "params": {"reason": "withheld gratitude", "severity": 1},
             "desc": "hold the words — it's logged as its own infraction, and the review resets",
             "outcome": "You hold the thank-you behind your teeth and give her nothing, and she "
                        "nods, unbothered, almost approving — \"there's still some of you in there; "
                        "good, more to work with\" — and logs WITHHELD with a tap. The defiance "
                        "column gets its little red mark back, which means the review comes round "
                        "again, which means the sentence comes round again, which means this exact "
                        "moment comes round again, as many times as it takes. They're not building "
                        "toward your breaking. They're building toward your *thanking*. Worse."}],
        "default": "thank"}


# ── inspection day: called up, gauged, and graded off her REAL numbers ────────
@effect("grade_reveal")
def _eff_grade_reveal(character, p):
    """The verdict, read aloud from her actual file: real processing tier, real appraisal
    price (recorded to db.facility_grade / db.sale_price), real body stats. Nothing invented."""
    lines = []
    try:
        from world.processing import processing_tier
        lvl, name, state = processing_tier(character)
        character.db.facility_grade = name
        lines.append(f"|c  ▸ GRADE: |w{name}|c (tier {lvl}) — {state}|n")
    except Exception:
        pass
    s = _cycle_script(character)
    if s and hasattr(s, "_appraise"):
        try:
            price = s._appraise(character)
            lines.append(f"|c  ▸ VALUATION: |w{price:,}|c — posted to the showroom ledger|n")
        except Exception:
            pass
    try:
        cond = float(getattr(character.db, "conditioning", 0) or 0)
        sug  = float(getattr(character.db, "suggestibility", 0) or 0)
        holes = dict(getattr(character.db, "holes", None) or {})
        used = sum(int((v or {}).get("use", 0)) for v in holes.values())
        counts = dict(getattr(character.db, "offspring_counts", None) or {})
        brood = sum(int(v) for v in counts.values())
        lines.append(f"|c  ▸ ON FILE: conditioning {cond:.0f} · suggestibility {sug:.0f} · "
                     f"holes logged {used} use(s) · {brood} get dropped|n")
    except Exception:
        pass
    if lines and getattr(character, "msg", None):
        character.msg("\n".join(lines))
    # Knowing her number, exactly, settles deeper than any speech.
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, 3.0, source="inspection")
    except Exception:
        pass
    return "graded"


@choice("inspection", root=True)
def _b_inspection(character):
    """Inspection day — only for the signed; the stand, the gauge, the grade."""
    if not (getattr(character.db, "facility_signed", False)
            or getattr(character.db, "facility_active", False)):
        return None
    return {"key": "inspection", "prompt": (
        "The tannoy says your number twice, flat and bored, and the floor traffic parts around "
        "you the way it parts around anything that's about to be processed. Inspection day. The "
        "stand is waiting under the strip lights — raised, ringed with rails for holding onto or "
        "being held onto, a drain in the floor beneath it that says everything about how thorough "
        "these get. The inspector snaps a fresh glove. \"Number called is number examined,\" she "
        "says. \"Walk up, or be walked up. The form has a box for either.\""),
        "options": [
            {"key": "walk", "label": "Walk yourself up", "effect": "submit_standing",
             "then": "inspection_gauge",
             "desc": "mount the stand on your own feet — composure is a grade criterion, and they grade it",
             "outcome": "You walk yourself up — feet on the painted marks, hands on the rails, "
                        "naked under strip light in front of a floor that doesn't pause its work "
                        "to watch you climb. The inspector ticks PRESENTED UNASSISTED, and the tick "
                        "is approving, and the approval lands in the place they've been hollowing "
                        "out for it. You're learning to mount your own examination stand gracefully. "
                        "That's a sentence about you now."},
            {"key": "balk", "label": "Make them fetch you", "effect": "punish",
             "params": {"reason": "balked at inspection", "severity": 1}, "then": "inspection_gauge",
             "desc": "they fetch; it's logged; the inspection happens regardless, minus the dignity",
             "outcome": "You stand where you are, and two attendants collect you with the practised "
                        "boredom of baggage handlers — one elbow each, feet barely touching, set on "
                        "the stand like luggage on a scale. FETCHED, the form notes, and the "
                        "infraction beside it. The examination proceeds identically. The only thing "
                        "your balking bought was being carried to it, and everyone on the floor "
                        "saw both versions of you in the same minute."}],
        "default": "walk"}


@choice("inspection_gauge")
def _b_inspection_gauge(character):
    """Step 2: the gauge — every hole measured, give and depth logged for real."""
    s = _cycle_script(character)
    zone = None
    if s:
        try:
            hs = s._holes_only(character)
            zone = hs[0] if hs else None
        except Exception:
            zone = None
    znice = (zone or "cunt").split("/")[-1].replace("_", " ")
    return {"key": "inspection_gauge", "prompt": (
        f"The gauging. Cold steel, calibrated, unhurried — the inspector works the instrument "
        f"into your {znice} to the first stop and reads the dial like a tyre pressure, narrating "
        f"give and depth and training-take to a recorder that doesn't care how you sound around "
        f"it. \"Relax onto it,\" she advises, professionally kind. \"It measures either way. "
        f"Clenching just means it measures *more*.\""),
        "options": [
            {"key": "relax", "label": "Relax onto the gauge", "effect": "pick_hole",
             "params": {"zone": zone or "cunt"}, "then": "inspection_grade",
             "desc": "breathe out and take the instrument; the reading is clean and so is the form",
             "outcome": "You breathe out and let the steel have its answer, and your body — traitor, "
                        "trained — accommodates it with an ease that goes on the form in red: TAKES "
                        "INSTRUMENT WITHOUT RESISTANCE. The dial settles, the numbers are read aloud "
                        "to the recorder in the same tone you'd read a gas meter, and the worst part "
                        "is the little flush of pride when the inspector murmurs 'good' at a reading "
                        "you can't even see."},
            {"key": "clench", "label": "Clench against it", "effect": "pick_hole",
             "params": {"zone": zone or "cunt"}, "then": "inspection_grade",
             "desc": "fight the steel — it measures more, works deeper, and notes the resistance as data",
             "outcome": "You clench, and the instrument simply... continues, geared for exactly "
                        "this, opening you against your own grip while the dial logs the fight as "
                        "another datum: RESISTANCE — TRAINING INDICATED. It takes longer. It goes "
                        "deeper, because thoroughness is the penalty. By the end your defiance is "
                        "a number too, and the number is small, and they make sure you hear it.\""}],
        "default": "relax"}


@choice("inspection_grade")
def _b_inspection_grade(character):
    """Step 3: the verdict — REAL grade, REAL valuation, read from her actual file."""
    return {"key": "inspection_grade", "prompt": (
        "Done. The glove comes off with a snap and the inspector consolidates your file — yield, "
        "give, take, temperament, brood — into the box at the bottom of the form where the grade "
        "goes. Her pen hovers. \"Some of them want it read out,\" she says, not looking up. "
        "\"Some of them would rather not know what they're worth. We accommodate both. The grade "
        "goes on you regardless — it's only the *knowing* that's optional.\""),
        "options": [
            {"key": "hear", "label": "\"Read it to me.\"", "effect": "grade_reveal",
             "desc": "hear your grade, your valuation, your file — the real numbers, all of them",
             "outcome": "She reads it to you — all of it, flat and exact, your whole self "
                        "consolidated into a tier and a price and a row of figures — and the "
                        "numbers go into you the way the gauge did: cold, calibrated, and "
                        "irreversibly *known*. You asked. You'll think about why you asked, later, "
                        "in the cell, where thinking goes to be reorganised."},
            {"key": "refuse", "label": "Look away", "effect": "deny_hold",
             "params": {"cond": 3.0},
             "desc": "graded anyway, filed anyway — you just carry it unread, which they also like",
             "outcome": "You look away while she writes it, and she almost smiles — they like this "
                        "version too, maybe better: a thing that knows it's been priced and can't "
                        "bring itself to look. The grade goes on your file and your file goes in "
                        "the drawer, and now there's a number on you that everyone in the building "
                        "can read except you. You'll feel them reading it for days."}],
        "default": "hear"}


# ── the block: her inspection grade goes to auction, and the bids are REAL ────
@effect("bid_up")
def _eff_bid_up(character, p):
    """The room bids on her — real ledger movement: high_bid climbs from her appraised
    sale_price, the high bidder is recorded, exhibition arousal banked."""
    base = int(getattr(character.db, "sale_price", 0) or 0)
    cur  = int(getattr(character.db, "high_bid", 0) or 0) or base or 1000
    bump = max(100, int(cur * random.uniform(0.15, 0.4)))
    character.db.high_bid = cur + bump
    character.db.high_bidder = random.choice([
        "the gentleman in booth two", "a buyer who never shows her face",
        "the dairy concern's agent", "a private collector, paddle 9",
    ])
    try:
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(character); add_arousal(character, float(p.get("arousal", 10.0)))
    except Exception:
        pass
    return f"bid:{character.db.high_bid}"


@effect("bethany_buys")
def _eff_bethany_buys(character, p):
    """The gavel falls to HER paddle: real ownership state — bethany_owned, the title claimed
    (backed up first, the same way bethany_script._mark_owned does), devotion banked."""
    d = character.db
    d.bethany_owned = True
    if not getattr(d, "facility_title_backup", None):
        d.facility_title_backup = {"faction": getattr(d, "title_faction", "") or "",
                                   "suffix":  getattr(d, "title_suffix", "") or ""}
    d.title_suffix = "— Bethany's"
    d.sale_price = int(getattr(d, "high_bid", 0) or 0) or int(getattr(d, "sale_price", 0) or 0)
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, 5.0, source="sold")
    except Exception:
        pass
    return "bethany_owned"


@choice("auction", root=True)
def _b_auction(character):
    """The block — only poses once she's been graded (inspection day feeds the showroom)."""
    if not getattr(character.db, "facility_grade", None):
        return None
    grade = character.db.facility_grade
    return {"key": "auction", "prompt": (
        f"They don't ask. A handler simply unhooks you from the line mid-shift, wipes you down "
        f"like produce, and walks you up the back stair to the showroom — because your file got "
        f"its grade, and graded stock gets SHOWN. The block is centre-floor under a single warm "
        f"light, turntable-slow, and beyond the glass the booths are dark except for the little "
        f"bid-lamps, patient as owls. The auctioneer reads your row off the card without looking "
        f"at you: \"Lot. Graded {grade}. Documentation available on request — and it is *thorough*. "
        f"\" A pause. \"Present the lot.\" That's you, sweetheart. How do you go up?"),
        "options": [
            {"key": "perform", "label": "Perform for the glass", "effect": "bid_up",
             "params": {"arousal": 14.0}, "then": "auction_gavel",
             "desc": "turn, arch, present — work the booths like the trained thing the card says you are",
             "outcome": "You perform. God help you, you *perform* — hit the turntable's rhythm, "
                        "arch where the light wants you, present on the quarter-turns like "
                        "choreography you don't remember learning but your body has by heart. The "
                        "bid-lamps start blinking before the first rotation finishes, and each "
                        "little wink of light is a number climbing on YOUR number, and the climbing "
                        "feels — no. You'll examine what it feels like later. The lamps keep "
                        "winking. You keep turning."},
            {"key": "freeze", "label": "Just stand there", "effect": "bid_up",
             "params": {"arousal": 8.0}, "then": "auction_gavel",
             "desc": "give them nothing — the turntable turns you anyway, and stillness reads as 'placid'",
             "outcome": "You give them nothing — stock-still, eyes on the middle distance, the one "
                        "protest left to you. The turntable doesn't care; it presents you anyway, "
                        "all sides, unhurried. And the auctioneer, without missing a beat, reads "
                        "your stillness onto the card as a FEATURE: \"note the temperament — placid "
                        "under observation, suitable for display work.\" Your defiance just raised "
                        "your price. The bid-lamps blink approvingly. There was never a way to "
                        "stand on that block that wasn't selling."}],
        "default": "perform"}


@choice("auction_gavel")
def _b_auction_gavel(character):
    """The gavel — and the paddle at the back of the dark that always wins."""
    bid = int(getattr(character.db, "high_bid", 0) or 0)
    bidder = getattr(character.db, "high_bidder", None) or "the dark"
    return {"key": "auction_gavel", "prompt": (
        f"The bidding climbs — {bid:,} now, to {bidder} — and the auctioneer's patter goes "
        f"singsong toward the gavel: going once... and then a new paddle lifts at the very back, "
        f"unhurried, and the booths go quiet, because everyone who works here knows that paddle. "
        f"Bethany doesn't even look up from her coffee. \"Plus one,\" she says, mild as milk, "
        f"which isn't a number, which is the point — hers is always plus one. The auctioneer "
        f"looks at you, which auctioneers never do, and you realise you're being offered the "
        f"only vote you'll ever get on this: whose gavel."),
        "options": [
            {"key": "hers", "label": "Look at Bethany", "effect": "bethany_buys",
             "desc": "meet her eyes over the coffee — and the gavel falls to her paddle, and you're HERS, titled",
             "outcome": "You look at her. That's all — you look — and her smile arrives like "
                        "payroll, certain and on schedule, and the gavel falls before you've "
                        "finished the looking. \"Sold,\" she agrees, fondly, finishing her coffee. "
                        "The title updates while you're still on the turntable: |w— Bethany's|n, "
                        "right there on your name where everyone reads it. She collects you off "
                        "the block herself, hand warm at your nape. \"My own lot. I always was "
                        "going to be the one, sweetheart. I just do love watching you find that "
                        "out in public.\""},
            {"key": "dark", "label": "Look at the booths", "effect": "bid_up",
             "params": {"arousal": 6.0},
             "desc": "appeal to the dark — the bids climb higher, but her paddle is still plus one",
             "outcome": "You look to the booths — to the dark, to anyone-but-her — and the dark "
                        "obliges: the lamps blink, the number climbs, your value setting a house "
                        "record while you stand there being looked at by people you'll never see. "
                        "And at the back, Bethany simply holds her paddle up and leaves it up. "
                        "Plus one. Plus one to anything. The lot isn't really for sale, sweetheart; "
                        "the auction is just how she likes to watch your price be proven before "
                        "she pays it. The gavel hangs. There's always next inspection day."}],
        "default": "hers"}


# ── the kept chain: what being "— Bethany's" actually gets you ────────────────
@effect("bethany_breeds")
def _eff_bethany_breeds(character, p):
    """Bethany takes what's hers — REAL insemination (species 'bethany', sire 'Bethany') into
    one or all of her actual holes, plus the laced-seed devotion payload her loads carry.
    params: {holes: 1|3, devotion}."""
    n = int(p.get("holes", 1))
    try:
        from world.gang_breeding import animal_holes, gang_inseminate
        hs = [z for z in animal_holes(character).values() if z]
        random.shuffle(hs)
        for z in hs[:max(1, n)]:
            gang_inseminate(character, z, contributors=1, fluid_type="semen",
                            species="bethany", sire="Bethany")
    except Exception:
        pass
    try:
        from typeclasses.bethany_script import bethany_deposit_effect
        bethany_deposit_effect(character, devotion=float(p.get("devotion", 5.0)))
    except Exception:
        pass
    return f"bred_by_her:{n}"


@effect("file_read")
def _eff_file_read(character, p):
    """Her file on you, read aloud in bed — the REAL numbers, fondly: devotion, conditioning,
    chair sessions, her line's get out of you, the title. Specificity as a love language."""
    d = character.db
    lines = []
    dev   = float(getattr(d, "bethany_devotion", 0) or 0)
    cond  = float(getattr(d, "conditioning", 0) or 0)
    sess  = int(getattr(d, "chair_sessions", 0) or 0)
    hers  = int(dict(getattr(d, "offspring_by_sire", None) or {}).get("Bethany", 0) or 0)
    title = getattr(d, "title_suffix", "") or ""
    lines.append(f"|M  ▸ her file: devotion {dev:.0f} · conditioning {cond:.0f} · "
                 f"{sess} chair session(s) served|n")
    if hers:
        lines.append(f"|M  ▸ her line: {hers} get of her own body out of yours — and counting|n")
    if title:
        lines.append(f"|M  ▸ on your name, where everyone reads it: {title}|n")
    if getattr(character, "msg", None):
        character.msg("\n".join(lines))
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, 4.0, source="her_file")
    except Exception:
        pass
    return "file_read"


@choice("kept", root=True)
def _b_kept(character):
    """Only for what's hers — the private evening that ownership buys."""
    if not getattr(character.db, "bethany_owned", False):
        return None
    fname = (getattr(character.db, "facility_fellow", None) or {}).get("name")
    return {"key": "kept", "prompt": (
        "After last shift, a handler unhooks you — not toward the pens, not toward the cell, "
        "but up the quiet stair to the office, where the lamps are low and the files are closed "
        "and Bethany is working with her shoes off, which nobody on the floor would believe. "
        "\"There she is,\" she says, not looking up, patting the desk's edge — or the cushion "
        "beside her chair; the gesture covers both, deliberately. \"Mine gets evenings. It's in "
        "the paperwork. Where do you want to spend yours?\" She asks like it's a kindness. It is "
        "one. That's the trap of her, and you're inside it, and it's warm in here."),
        "options": [
            {"key": "lap", "label": "Her lap", "effect": "devote", "params": {"amount": 6.0},
             "then": "kept_use",
             "desc": "held against her while she works — the false-tenderness, full strength",
             "outcome": "You choose the lap, and she gathers you in one-armed without breaking "
                        "her pen-stroke, your cheek against her blouse, her heartbeat slow and "
                        "absolutely unhurried under it. She works for an hour and strokes your "
                        "hair on the page-turns, and once — once — she presses her lips to the "
                        "top of your head and murmurs, \"I think I do love you, you know. The "
                        "way you love a chair.\" And the worst, warmest, most ruinous part is "
                        "how completely the words land as affection. They were built to."},
            {"key": "floor", "label": "The floor at her feet", "effect": "submit_standing",
             "then": "kept_use",
             "desc": "kneel under the desk where the favourite kneels — known your place, and kept in it",
             "outcome": "You fold down at her feet, cheek to her knee, and her hand arrives in "
                        "your hair like it was always going to — absent, proprietary, perfect. "
                        "\"Good girl. You skipped three whole arguments tonight,\" she notes, "
                        "fond, turning a page. \"I'm putting that in the file under *progress*.\" "
                        "She does. You hear the pen do it. Being a footnote in her evening is "
                        "somehow the most seen you've felt in weeks, and she engineered that "
                        "famine personally, and you know it, and you stay."}]
            + ([{"key": "company", "label": f"Ask her to send for {fname}",
                 "effect": "devote", "params": {"amount": 3.0}, "then": "kept_company",
                 "desc": "two of hers, one evening, her direction — and the asking goes in the file",
                 "outcome": f"You ask for {fname} — and Bethany's smile goes positively luminous, "
                            f"because asking to share your owner's evening with another of her "
                            f"belongings is the most *kept* thing you've ever done, and you both "
                            f"hear it land. \"Oh, sweetheart. Look at you, building me a little "
                            f"household.\" She lifts the desk phone, says two words, and somewhere "
                            f"below a handler goes to fetch what you asked for. \"She'll be "
                            f"scrubbed and up in ten. You'll wait on the cushion. Wanting things "
                            f"is *lovely* on you — I'm writing it down.\""}]
               if fname else []),
        "default": "lap"}


@choice("kept_use")
def _b_kept_use(character):
    """Step 2: she puts the paperwork down. All three of her, and the only question is how."""
    return {"key": "kept_use", "prompt": (
        "Eventually the pen caps itself and she looks down at you properly, and her slacks are "
        "already losing the argument — the root of her thickening, the three of them unfurling "
        "patient and prehensile, each flared head finding the air like they've been listening "
        "this whole time. \"Now then,\" she says, warm as the lamplight. \"The evening's mine "
        "too. One of me, or all of me? Think carefully, sweetheart — there's no wrong answer, "
        "there's just the answer I write down.\""),
        "options": [
            {"key": "one", "label": "One of her", "effect": "bethany_breeds",
             "params": {"holes": 1, "devotion": 5.0}, "then": "kept_morning",
             "desc": "she picks the hole herself — slow, deep, knotted, one load of the laced seed",
             "outcome": "One, then — and she chooses which, because of course she does, tipping "
                        "you across the desk and feeding one flared head home with the unhurried "
                        "thoroughness of a woman signing her own property. The knot seats, the "
                        "load comes scalding and laced and impossibly much, and the devotion in "
                        "it goes to work on you while she holds you down and finishes her cold "
                        "coffee with the free hand. \"There. One is plenty,\" she allows, fondly. "
                        "\"Tonight.\""},
            {"key": "all", "label": "All of her", "effect": "bethany_breeds",
             "params": {"holes": 3, "devotion": 12.0}, "then": "kept_morning",
             "desc": "mouth, cunt, ass — flared, seated, knotted in every hole at once, triple-laced",
             "outcome": "\"All,\" you say — or start to, because the third syllable is already "
                        "muffled: she takes the word as the permission it was and seats herself "
                        "in every hole you own in one coordinated, practised motion, three flares, "
                        "three knots, your whole body locked onto her like furniture being "
                        "assembled. She works all three on separate rhythms until you can't tell "
                        "which moan belongs to which occupation, and when she empties — everywhere, "
                        "at once, triple-laced — the devotion hits you from three directions and "
                        "meets in the middle, where you used to keep your objections. \"Greedy "
                        "thing,\" she says afterward, stroking your hair, knotted into all of you, "
                        "going nowhere for an hour. \"I'm so proud.\""}],
        "default": "all"}


@choice("kept_morning")
def _b_kept_morning(character):
    """Step 3: morning. Her bed, her file, and the question of whether you want to know."""
    return {"key": "kept_morning", "prompt": (
        "Morning arrives lamp-soft. You wake in her actual bed — a privilege with a paper trail — "
        "to the small librarian sound of her reading. It's your file. Of course it's your file; "
        "she reads it the way other people read the news, propped on one elbow, coffee on the "
        "nightstand, your whole becoming in her lap in manila. She notices you waking and smiles "
        "her morning smile, which is the real one. \"Good morning, mine. I'm just up to the "
        "recent entries. Shall I read you to you? You've been *such* a good chapter lately.\""),
        "options": [
            {"key": "read", "label": "\"Read it to me.\"", "effect": "file_read",
             "desc": "your devotion, your conditioning, her line's get out of you — the real figures, in her voice",
             "outcome": "She reads you to you — every figure exact, every entry dated, her voice "
                        "doing the numbers the way other voices do poetry — and hearing yourself "
                        "rendered in her bookkeeping is more intimate than anything the night did. "
                        "When she finishes she taps the folder square and kisses your forehead. "
                        "\"My favourite document,\" she says. \"I have a drawer for the finished "
                        "ones, you know. Yours is never going in it. Yours I keep *open*.\""},
            {"key": "burrow", "label": "Burrow into her instead", "effect": "devote",
             "params": {"amount": 6.0},
             "desc": "don't ask — press into her warmth and let the file stay hers to know",
             "outcome": "You burrow into her side instead, nose to her ribs, and she laughs low "
                        "and lets the folder tip closed, her arm coming around you proprietary "
                        "and warm. \"Don't want to know? Sweet thing. That's my favourite answer "
                        "— it means the file's *all mine*.\" She holds you, and reads on silently "
                        "over your head, and now and then she huffs, pleased, at something you did "
                        "that you'll never know she knows. The not-knowing purrs in you like a "
                        "kept secret. It's hers. So are you. The morning is warm."}],
        "default": "read"}


@effect("company_use")
def _eff_company_use(character, p):
    """Bethany directs the two of you — REAL: if the fellow's been converted (futa), SHE breeds
    you under orders (sire = her name, crossed lines recorded) while Bethany takes your mouth;
    otherwise Bethany takes you both in turn (two of your holes, sire Bethany). Laced either way."""
    fname = (getattr(character.db, "facility_fellow", None) or {}).get("name") or "her"
    futa = False
    try:
        from world.facility_fellow import fellow_is_futa
        futa = fellow_is_futa(character)
    except Exception:
        pass
    try:
        from world.gang_breeding import animal_holes, gang_inseminate
        hs = [z for z in animal_holes(character).values() if z]
        random.shuffle(hs)
        if futa and hs:
            mouth = next((z for z in hs if "mouth" in z or "throat" in z), None)
            body  = next((z for z in hs if z != mouth), hs[0])
            gang_inseminate(character, body, contributors=1, fluid_type="semen",
                            species="bethany", sire=fname)
            if mouth:
                gang_inseminate(character, mouth, contributors=1, fluid_type="semen",
                                species="bethany", sire="Bethany")
            try:
                from world.facility_animals import fellow_cross_record
                fellow_cross_record(character, fname)
            except Exception:
                pass
        else:
            for z in hs[:2]:
                gang_inseminate(character, z, contributors=1, fluid_type="semen",
                                species="bethany", sire="Bethany")
    except Exception:
        pass
    try:
        from typeclasses.bethany_script import bethany_deposit_effect
        bethany_deposit_effect(character, devotion=float(p.get("devotion", 8.0)))
    except Exception:
        pass
    return "company:" + ("futa" if futa else "shared")


@choice("kept_company")
def _b_kept_company(character):
    """Two of hers in the lamplight — and Bethany conducts."""
    f = (getattr(character.db, "facility_fellow", None) or {})
    fname = f.get("name") or "her"
    futa = bool(f.get("futa"))
    if futa:
        middle = (f"And {fname} arrives scrubbed and wide-eyed, and Bethany looks between the "
                  f"two of you — her bought favourite, and the friend she rebuilt with her own "
                  f"signature between the thighs — like a hostess seating a dinner party. \"Now "
                  f"then. You asked for her, so you'll have her — *my* way. {fname}, sweetheart, "
                  f"you remember what I gave you and what it's for. And you—\" her thumb finds "
                  f"your jaw \"—will be wanting something to do with your mouth.\"")
    else:
        middle = (f"And {fname} arrives scrubbed and wide-eyed, and Bethany pats the rug in "
                  f"front of her chair — both of you, side by side, two sets of hands and one "
                  f"unhurried owner. \"You asked for company. Company you'll be — for each "
                  f"other, while I have you both. Hips up, my loves. The evening's young and "
                  f"I am *thorough* with my own.\"")
    return {"key": "kept_company", "prompt": middle,
        "options": [
            {"key": "yield", "label": "Yield to her direction", "effect": "company_use",
             "params": {"devotion": 8.0}, "then": "kept_morning",
             "desc": "let her conduct the two of you — every deposit real, every line crossed on the books",
             "outcome": f"You yield, and she conducts — truly conducts, a hand on a hip here, a "
                        f"murmured *slower, sweetheart* there, arranging the two of you like "
                        f"flowers she grew herself. What follows is thorough and laced and "
                        f"recorded: {fname} trembling through her orders, you full at both ends "
                        f"of the evening, and Bethany above it all with her coffee, immensely "
                        f"content, watching her property love each other on her instruction. "
                        f"\"There,\" she says at last, to both of you, fondly. \"A household.\""},
            {"key": "cling", "label": f"Cling to {fname} through it", "effect": "company_use",
             "params": {"devotion": 5.0}, "then": "kept_morning",
             "desc": "hold your friend's hand through what she directs — the comfort is permitted, and noted",
             "outcome": f"You find {fname}'s hand and lace your fingers through it, and you hold "
                        f"on through everything Bethany directs — and Bethany *allows* it, which "
                        f"is its own entry in the file: comfort permitted, attachment noted, two "
                        f"of her assets bonding under load. \"Look at them,\" she murmurs to her "
                        f"coffee, genuinely soft for a moment. \"My girls.\" The hand-holding "
                        f"doesn't make what's happening to you both gentler. It makes it *shared*. "
                        f"That was the kindest thing on offer tonight, and she's the one who put "
                        f"it on the menu."}],
        "default": "yield"}


# ── the Postal Office counter menu (no say-triggers; `clerk` opens it) ─────────
# Half service-desk tutorial, half Seraphine's gossip. Prose-only options loop back
# to the menu via `then`; the only non-chaining option walks you out. Floor-safe by
# construction — nothing here locks, conditions, or gates; it's a conversation.
@choice("clerk", root=False)
def _b_clerk(character):
    return {"key": "clerk", "prompt": (
        "Seraphine props her chin on one hand and gives you her whole, dangerous attention. "
        "\"The counter's open, sweet thing. Stamps, secrets, or paperwork — and I do mean "
        "secrets; I have so many and I am *terrible* at keeping the ones that aren't yours. "
        "What'll it be?\""),
        "options": [
            {"key": "gossip", "label": "Ask her for gossip", "then": "clerk_gossip",
             "desc": "she has been waiting all day for someone to ask",
             "outcome": "\"*Finally*,\" she breathes, delighted, and leans in like the counter "
                        "just got smaller."},
            {"key": "services", "label": "Ask what they can do for you", "then": "post_services",
             "desc": "the actual menu — officiating, delivery, body-work, poste restante",
             "outcome": "\"Business, then. Properly.\" She produces a little laminated card, "
                        "soft-cornered from handling, and turns it to face you."},
            {"key": "officiate", "label": "Ask how officiating works", "then": "clerk",
             "desc": "the actual trade — contracts, clauses, the three of them",
             "outcome": (
                "\"Right — the trade.\" She counts it off, warm and brisk. \"You draft a "
                "contract: |wcontract draft|n, then |wcontract clauses|n to see what's on it. "
                "Bring it to the counter and one of us officiates. Calix reads it *flat* — every "
                "word, no weather in his voice, so you hear exactly what you're agreeing to. "
                "Vesper *riddles* it — finds the second meaning, the door you didn't know you "
                "left ajar. And I —\" the red inkwell appears as if conjured \"— officiate by "
                "kissing it through: |wofficiate|n, then |wcosign|n, and it's sealed. My margins "
                "have a habit of acquiring a clause or two between the reading and the signing. "
                "Everyone's warned. Almost everyone signs anyway.\" A wink. \"That's not wicked. "
                "That's just want, dressed up enough to say yes to.\"")},
            {"key": "rooms", "label": "Ask about the back rooms", "then": "clerk",
             "desc": "where the three of them keep their private things",
             "outcome": (
                "Her smile sharpens, fond and proprietary. \"We each keep a place. Mine's "
                "through the |wstanding mirror|n in the Quiet Room — push the left edge; I'll "
                "already know you're coming. Calix has a |wstrong door|n off the Sorting Hall, "
                "tidy enough to make you nervous. And Vesper —\" her voice goes soft \"— Vesper "
                "has a |wfold in the corner|n back there that's only a corner if they've let "
                "you in. Go gently in that one. And do read the toyboxes; we leave them unlocked "
                "on purpose. The looking's half the gift.\"")},
            {"key": "stamp", "label": "Just buy a stamp and go",
             "desc": "two coppers; no, she won't make it weird (she will, a little)",
             "outcome": (
                "\"Two coppers.\" She slides a stamp across with the warmth of a woman filing "
                "you under *will be back*. \"For when you've something to say you can't quite "
                "say yet. We hold those, you know. Until you can.\" The smile follows you out "
                "the whole way to the door — the one with no lock — and you feel, distinctly, "
                "*kept track of*.")},
        ],
        "default": "stamp"}


# ── the services menu (a REAL directory: officiating actually fires) ──────────
def _find_office_contract(character):
    """The nearest drafted contract — inventory first, then the room (often set in front of
    the signee). Mirrors MilkingContract._find_contract. Returns the object or None."""
    try:
        from typeclasses.milking_contract import MilkingContract
    except Exception:
        return None
    pool = list(getattr(character, "contents", None) or [])
    loc = getattr(character, "location", None)
    if loc:
        pool += list(getattr(loc, "contents", None) or [])
    for o in pool:
        try:
            if isinstance(o, MilkingContract) and not getattr(o.db, "signed", False):
                return o
        except Exception:
            continue
    return None


@effect("office_officiate")
def _eff_office_officiate(character, p):
    """Actually officiate the carried contract through the REAL engine (world.post_office.
    officiate) with the chosen clerk — Calix flat / Vesper rider / Seraphine hidden-clause.
    No-ops cleanly if no unsigned contract is to hand. The returned flavour is shown."""
    who = (p or {}).get("who")
    contract = _find_office_contract(character)
    if not contract or not who:
        return ""
    try:
        from world.post_office import officiate
        ok, msg = officiate(contract, character, who=who, allow_seraphine=(who == "seraphine"))
    except Exception:
        return ""
    if getattr(character, "msg", None) and msg:
        character.msg(("|g" if ok else "|x") + msg + "|n")
    return f"officiated:{who}" if ok else "officiate_failed"


_CLERK_NAMES = ("seraphine", "calix", "vesper")


def _present_clerk(character):
    """Which clerk is working right now — the one in the room with you. If more than one,
    pick one at random so the office feels staffed-by-people, not by a rota. Default Seraphine
    (she's the face of the counter). Returns a lowercase name."""
    loc = getattr(character, "location", None)
    present = []
    for o in (getattr(loc, "contents", None) or []):
        nm = (getattr(o, "key", "") or "").lower()
        if nm in _CLERK_NAMES:
            present.append(nm)
    return random.choice(present) if present else "seraphine"


@effect("office_poste")
def _eff_office_poste(character, p):
    """Real poste-restante from inside the menu: leave a chosen letter into the Dead Letter Cage,
    or draw one to read. Persists on the office room (one shared store). No-ops cleanly off-site."""
    try:
        from world.post_office_build import _find_office, leave_poste, draw_poste
    except Exception:
        return ""
    office = _find_office() or getattr(character, "location", None)
    if not office:
        return ""
    mode = (p or {}).get("mode", "leave")
    if mode == "read":
        entry = draw_poste(office, exclude_id=getattr(character, "id", None))
        if entry and getattr(character, "msg", None):
            character.msg("|WYou reach through the bars and draw one at random — warm, like they "
                          f"all are.|n\n|y  \"{entry.get('text','')}\"|n\n|xUnsigned. You slide "
                          "it back exactly as you found it.|n")
        elif getattr(character, "msg", None):
            character.msg("|xThe cage is empty for once. Be the first.|n")
        return "poste_read"
    text = (p or {}).get("text")
    if not text:
        return ""
    leave_poste(office, text, author_id=getattr(character, "id", None), author_name="Anonymous")
    return "poste_left"


@choice("post_poste", root=False)
def _b_post_poste(character):
    """The poste-restante flow from inside the menu. You can seal one of a few unsayable things
    (each really dropped into the cage via office_poste), draw one to read, or be told how to
    leave your own words (the command path, for free text the menu can't capture)."""
    return {"key": "post_poste", "prompt": (
        "\"Here's how it works,\" Seraphine says, gentling. \"You don't address it. You just let "
        "it exist somewhere that isn't only inside you. Pick one off the wall if it fits — or "
        "write your own — and I'll feed it through the bars myself.\" She nods at a little board "
        "of the ones too many people needed: the unsendables, pinned for the taking."),
        "options": [
            {"key": "want", "label": "Seal: \"I think about being owned and it scares me how much\"",
             "effect": "office_poste", "params": {"text": "I think about being owned and it scares me how much."},
             "then": "post_poste", "desc": "really dropped into the cage, held, anonymous",
             "outcome": "She feeds it through without reading it. \"There. It's not only yours to "
                        "carry now. The cage has it too.\""},
            {"key": "stay", "label": "Seal: \"I don't want to leave and I'm afraid to say so\"",
             "effect": "office_poste", "params": {"text": "I don't want to leave, and I'm afraid that if I say it out loud it stops being allowed."},
             "then": "post_poste", "desc": "sealed and held — the thing the whole office is *for*",
             "outcome": "Her smile goes soft and real, just for a beat. \"Oh, sweet thing. That one "
                        "we keep very safe.\""},
            {"key": "name", "label": "Seal: \"I want to be someone's, completely, on paper\"",
             "effect": "office_poste", "params": {"text": "I want to belong to someone completely, on paper, where it's real and can't be taken back."},
             "then": "post_poste", "desc": "the confession most people draft and never bring in",
             "outcome": "\"Mm.\" She presses her seal to it warm. \"You'd be amazed how many of "
                        "those are in there. You're in good, wanting company.\""},
            {"key": "read", "label": "Draw one instead — read what someone couldn't send",
             "effect": "office_poste", "params": {"mode": "read"}, "then": "post_poste",
             "desc": "someone else's unsendable, drawn at random",
             "outcome": ""},
            {"key": "own", "label": "Ask how to leave my own words", "then": "post_poste",
             "desc": "free text — the command path",
             "outcome": "\"Your own's better, always. |wposte leave|n then whatever you can't say "
                        "— at the cage in the Sorting Hall. I'll not read it. None of us will. "
                        "That's the one rule we never break.\""},
            {"key": "back", "label": "Back to the services card", "then": "post_services",
             "desc": "the laminated menu",
             "outcome": "\"Take your time. The cage isn't going anywhere. Famously.\""},
        ],
        "default": "back"}


@choice("post_services", root=False)
def _b_post_services(character):
    """The office's real service directory. Officiating is the one that DOES something here and
    now (on a carried contract); the rest route you to the real station/command for the job."""
    return {"key": "post_services", "prompt": (
        "The card reads, in three different hands:\n"
        "  |wOFFICIATING|n — make a drafted contract binding (Calix / Vesper / me)\n"
        "  |wDELIVERY|n — send word by ogram, anywhere it'll reach\n"
        "  |wBODY-WORK|n — brands, piercings, the permanent sort (see Durgin)\n"
        "  |wPOSTE RESTANTE|n — leave something here we'll hold until you can say it\n"
        "\"We don't do refunds,\" Seraphine adds, \"and we don't do forgetting. What'll it be?\""),
        "options": [
            {"key": "officiate", "label": "Officiate a contract I'm carrying", "then": "post_officiant",
             "desc": "make it binding — at the counter, for real",
             "outcome": "\"Set it on the counter, then. Let's see who you trust with it.\""},
            {"key": "deliver", "label": "Send word (an ogram)", "then": "post_services",
             "desc": "the delivery system — a message carried and made real",
             "outcome": (
                "\"Ogram service. You tell us what to carry and to whom — |wogram|n at the counter "
                "spells out the forms. We deliver anything that can be written, and a few things "
                "that can't.\" A wink. \"Calix has carried stranger parcels than your feelings.\"")},
            {"key": "bodywork", "label": "Ask about body-work", "then": "post_services",
             "desc": "brands, piercings — Durgin's trade",
             "outcome": (
                "\"That's Durgin's bench, not ours — the brander, the piercer, the smith. Permanent "
                "things, done properly, that *show* on your marks afterward.\" Her smile turns "
                "knowing. \"Tell him I sent you. He'll know what that means about you, and he'll be "
                "gentler for it, or rougher. I never can tell which he decides.\"")},
            {"key": "poste", "label": "Leave something poste restante", "then": "post_poste",
             "desc": "a thing you can't say yet; they hold it — really",
             "outcome": (
                "\"The Dead Letter Cage. People think it's where mail goes to die.\" She shakes "
                "her head, fond. \"It's where the things you can't send *yet* get to keep "
                "existing. Come on, then. Let's find yours.\"")},
            {"key": "back", "label": "Back to the counter", "then": "clerk",
             "desc": "the chin-on-hand, the dangerous attention",
             "outcome": "\"Mm. Take your time. I'm not going anywhere, and neither, it seems, are you.\""},
        ],
        "default": "back"}


@choice("post_officiant", root=False)
def _b_post_officiant(character):
    """Pick the clerk to officiate the carried contract — each routes the REAL officiate().
    If nothing's drafted to hand, Seraphine says so (and how to fix it) and bounces back."""
    contract = _find_office_contract(character)
    if not contract:
        return {"key": "post_officiant", "prompt": (
            "Seraphine looks at your empty hands, then at the bare counter, then back at you, "
            "with enormous fondness. \"Sweet thing, there's nothing here to officiate. Draft it "
            "first — |wcontract draft|n, |wcontract clauses|n to read it — and bring it back. "
            "I'll be *thrilled*.\""),
            "options": [
                {"key": "back", "label": "Right — I'll draft one", "then": "post_services",
                 "desc": "back to the service card",
                 "outcome": "\"That's the spirit. Off you go. The pen's always warm here.\""}],
            "default": "back"}
    cname = getattr(contract.db, "title", None) or getattr(contract, "key", "the contract")
    return {"key": "post_officiant", "prompt": (
        f"You set {cname} on the counter. Seraphine smooths it flat with one finger. \"And who "
        "do you want to make it real, hm? We each do it differently — and the difference is the "
        "whole point.\""),
        "options": [
            {"key": "calix", "label": "Calix — read flat, no surprises", "effect": "office_officiate",
             "params": {"who": "calix"}, "then": "post_services",
             "desc": "every word as written, a fee, and nothing added",
             "outcome": "You slide it toward the center of the counter, toward Calix."},
            {"key": "vesper", "label": "Vesper — a rider, free, ambiguous", "effect": "office_officiate",
             "params": {"who": "vesper"}, "then": "post_services",
             "desc": "no charge; one line you'll read three times and never be sure of",
             "outcome": "Vesper's hand drifts toward the page before you've finished deciding."},
            {"key": "seraphine", "label": "Seraphine — free, and she writes where you won't look",
             "effect": "office_officiate", "params": {"who": "seraphine"}, "then": "post_services",
             "desc": "the warm seal, a hidden clause, 'you'll see what it cost you eventually'",
             "outcome": "\"Oh, *me*? Brave.\" Her tail curls once, delighted. \"No charge, love.\""}],
        "default": "calix"}


# Each clerk gossips in their own register, and the 'another'/'back' beats match the voice.
_GOSSIP_VOICE = {
    "seraphine": {
        "pool": "_GOSSIP",
        "more": "\"Oh, you're *fun*. Come closer, then.\"",
        "back": "\"Mm. Business.\" She says the word like it's the funny one. \"Go on, then.\"",
        "more_lbl": "Mm — tell me another", "more_desc": "she will, gladly, until you stop her",
    },
    "calix": {
        "pool": "_CALIX_GOSSIP",
        "more": "He doesn't say yes. He sets down the stamp, which is a yes.",
        "back": "He nods, once, and the counter is a counter again. \"Mm.\"",
        "more_lbl": "Wait for another", "more_desc": "he'll give you one more, if you don't rush him",
    },
    "vesper": {
        "pool": "_VESPER_GOSSIP",
        "more": "\"...if you want.\" They don't look up. They want to. \"One more.\"",
        "back": "They nod, relieved and a little sorry both, and return to the sorting.",
        "more_lbl": "Gently — another?", "more_desc": "they'll trust you with one more",
    },
}


@choice("clerk_gossip", root=False)
def _b_clerk_gossip(character):
    """A fond little story from whoever's actually working the counter — Seraphine warm,
    Calix spare, Vesper oblique — each from their own pool, picked fresh. Loops ('another') or
    out to the counter menu. Pure prose; no effect, no gate."""
    who = _present_clerk(character)
    voice = _GOSSIP_VOICE.get(who, _GOSSIP_VOICE["seraphine"])
    try:
        import world.post_office_build as _pob
        pool = list(getattr(_pob, voice["pool"], None) or [])
    except Exception:
        pool = []
    if not pool:
        return None
    title, story = random.choice(pool)
    return {"key": "clerk_gossip", "prompt": story,
        "options": [
            {"key": "more", "label": voice["more_lbl"], "then": "clerk_gossip",
             "desc": voice["more_desc"], "outcome": voice["more"]},
            {"key": "back", "label": "Back to business", "then": "clerk",
             "desc": "the counter, the trade, the pretext", "outcome": voice["back"]},
        ],
        "default": "back"}


# ── the Break Room: off-duty, on the couch (warm, consensual, real) ───────────
# Reached via `unwind`/`couch` in the Break Room (CmdUnwind). House rule, in-fiction AND as
# the §0 floor: ask first. They do; "Not today" is always a clean, graceful out. The 'yes'
# path moves real arousal; the register is warm-domestic, not the institution's dread.
@effect("couch_warm")
def _eff_couch_warm(character, p):
    """A real beat on the couch — arousal moves for true (arousal_script). Floor-safe; this is
    a post-office scene, not a facility lock — nothing here gates or conditions."""
    try:
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(character)
        add_arousal(character, float((p or {}).get("amount", 35.0)))
    except Exception:
        pass
    return "couch"


_COUCH = {
    "seraphine": {
        "intro": (
            "Seraphine is already on the couch when you come up, one leg folded under her, and "
            "she doesn't so much invite you as *make room* — patting the cushion beside her with "
            "the certainty of a woman who has never once been told no up here and wouldn't quite "
            "believe it. Her tail finds your ankle before her hand finds your wrist. \"Off the "
            "clock,\" she murmurs, warm as the kettle. \"No paperwork, no clauses — just me being "
            "greedy about someone I like. *May* I, sweet thing? House rule is I ask. So I'm "
            "asking.\""),
        "yes": (
            "\"*Good.*\" She pulls you down across her lap like she's been planning the angle for "
            "an hour, and maybe she has. There's nothing clinical in it and nothing cruel — just "
            "her clever hands and her crooked-real smile and the clove-warm weight of her "
            "attention, taking her time with you on a couch that's seen this a hundred fond times. "
            "She narrates none of it and means all of it, and when your breath goes ragged she "
            "presses her lips to your temple and says \"there she is\" like you're the best letter "
            "she's opened all week."),
        "rest": (
            "You don't take her up on the greed; you just tuck in against her side, and she lets "
            "you, instantly recalibrating from predator to pillow without a flicker of complaint. "
            "Her arm comes around you, her tail over your knees like a second blanket. \"This is "
            "allowed too,\" she says softly, and you feel her mean it. \"Most people forget it's "
            "allowed too.\""),
    },
    "calix": {
        "intro": (
            "Calix is on the couch with a mug of something and the first unguarded face you've "
            "seen on him — the broad shoulders down off their station, the careful stillness gone "
            "soft. He looks at you a beat longer than necessary, the way he does, except up here "
            "it isn't a tell he's hiding; it's an invitation he's letting you read. He lifts the "
            "arm not holding the mug, a wordless space made against his side, and waits. When he "
            "does speak it's low and plain: \"You can. If you want to. Only if you want to.\""),
        "yes": (
            "You fit yourself against him and he exhales — a whole man setting a weight down. He's "
            "unhurried in everything and this is no exception: big careful hands that ask with "
            "every motion, a mouth that says almost nothing and answers everything in *weight*, "
            "the way Vesper swears he does. He tells you you're doing well — plainly, no teasing, "
            "the one indulgence he'd die before naming — and the saying of it undoes you both a "
            "little. He holds you through it like cargo he'd cross bad weather for."),
        "rest": (
            "You just lean on him, and Calix goes still and certain as a load-bearing wall, the "
            "mug migrating to your hands without comment because you looked cold. \"Stay as long "
            "as you like,\" he says to the middle distance. It is, for Calix, a sonnet."),
    },
    "vesper": {
        "intro": (
            "Vesper is curled into the corner of the couch with their knees up, and the look they "
            "give you when you come up the stairs is startled-pleased, eyes going silver then "
            "something warmer. Off-duty they take up space they'd never claim at the counter — but "
            "shyness still moves through them in little weather-fronts. They pat the cushion, "
            "snatch their hand half-back, leave it. \"...you could sit. With me. If — \" a breath, "
            "braver \" — if you wanted. I'd like it. I'm allowed to say I'd like it, up here.\""),
        "yes": (
            "They come to you in pieces and then all at once — tentative, then startled by their "
            "own want, then *fervent*, like someone who's only ever tried this on alone in front "
            "of a mirror and can't believe it's allowed with the lights on. Their eyes change "
            "colour with every gasp. They keep checking your face, and keep finding permission "
            "there, and each time they find it they get a little braver, a little less careful, "
            "until careful is the last thing either of you is. \"...oh,\" they breathe, wrecked "
            "and delighted, \"*oh*, that's — \" and don't finish, and don't need to."),
        "rest": (
            "You only mean to sit close, and Vesper goes boneless with a relief that tells you "
            "*close* was the whole wish. They tuck under your arm like they've practised wanting "
            "to and never dared. \"This is good,\" they whisper, surprised by it. \"This is — yes. "
            "Thank you. Don't tell Seraphine I let someone. She'll throw a party.\""),
    },
}

_COUCH_NO = (
    "\"Not today\" — and that's the end of it, no weather, no wound. The house rule is *ask*, "
    "and the other half of asking is that no is a whole answer up here. They make easy room for "
    "you on the couch anyway, the unfraught kind, and the kettle clicks on, and you're simply "
    "welcome. That's the thing about this room: being wanted here was never the price of "
    "anything.")


@choice("break_couch", root=False)
def _b_break_couch(character):
    """Off-duty on the Break Room couch with whoever's up there. Consent-forward (they ask);
    'Not today' is a clean out. The yes/rest paths move real arousal / give comfort, in the
    warm-domestic register the room is built for. No gate, no condition — this isn't the rig."""
    who = _present_clerk(character)
    c = _COUCH.get(who, _COUCH["seraphine"])
    return {"key": "break_couch", "prompt": c["intro"],
        "options": [
            {"key": "yes", "label": "Yes — gladly", "effect": "couch_warm",
             "params": {"amount": 40.0}, "then": "break_couch_after",
             "desc": "let them be greedy; warm, unhurried, real",
             "outcome": c["yes"]},
            {"key": "rest", "label": "Just rest against them", "then": "break_couch_after",
             "desc": "the other thing the couch is for — allowed too",
             "outcome": c["rest"]},
            {"key": "no", "label": "Not today", "desc": "a whole answer; no weather, no wound",
             "outcome": _COUCH_NO},
        ],
        "default": "rest"}


@choice("break_couch_after", root=False)
def _b_break_couch_after(character):
    """The afterglow — the realest minutes the office has. Linger or head back down; either way
    you leave having been, for a little while, just people on a couch."""
    return {"key": "break_couch_after", "prompt": (
        "After, the Break Room does the thing it's best at: nothing. The kettle ticks. Someone's "
        "mug steams. The photographs on the keepsake shelf watch with the fondness of objects "
        "that have seen this a hundred times and approve. Whoever's got you keeps you a while, "
        "off the clock, unbothered, and the quiet is the warmest thing in the building."),
        "options": [
            {"key": "stay", "label": "Stay a while longer", "then": "break_couch_after",
             "desc": "no clock up here; let the quiet hold",
             "outcome": "You stay. Nobody hurries you. The proof-of-life photo on the shelf has "
                        "room in the frame, you think, for one more. The thought doesn't scare "
                        "you the way it should."},
            {"key": "down", "label": "Head back down the stairs",
             "desc": "back to the counter and the world",
             "outcome": "You go down eventually, carrying the warmth of it like a stamp pressed "
                        "somewhere private. The counter's just a counter again. But you know the "
                        "stairs are there now. You'll know it the whole rest of the day."},
        ],
        "default": "down"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Bethany's Intake — choice-driven, stateful, CINEMATIC.
# A movie, not cliff-notes: dense sensory prose, a present actor whose demeanour
# is real and shifts on what you do (bubbly false-security → pleased ownership if
# you sign willingly; the mask dropped into wrath if you make her take it), and the
# cock-seating savoured across three escalating beats. Everything is a CHOICE; the
# scene WAITS on `choose`, never a timer. Every beat reads scene_flags + real state.
# Real effects throughout. §0: escape/forceclear end it instantly, always.
# Flow: arrival→file→strip→contract→unveil→first→seat→knot→close.
# ═══════════════════════════════════════════════════════════════════════════

@choice("bx_arrival", root=False)
def _bx_arrival(character):
    nm = subject_name(character)
    return {"key": "bx_arrival", "prompt": (
        "The Intake counter is a lie the room tells well. It is just a desk — scuffed steel, a "
        "blotter gone soft at the corners, a tidy stack of multi-page forms weighted flat under a "
        "cold-iron brand — and the woman behind it is just a clerk: lanyard, fitted blouse buttoned "
        "one button higher than the body underneath wants, a pen she clicks once, twice, against "
        "the blotter while she reads. The sodium light hums its half-tone flat overhead, even and "
        "shadowless and the colour of old bone, and under the disinfectant there's the other smell "
        "the room never quite scrubs out — milk, and animal, and something warm and organic that "
        "your body places a half-second before your mind wants it to.\n\n"
        "Your file is already open in front of her. Not a fresh one — a |wthick|n one, edges furred "
        "from handling, your name typed on the tab in her own neat hand, as though she filled it out "
        "in advance, as though you were always going to be in this chair on this morning. She "
        "finishes the line she's reading. Makes a small mark in the margin. Only then looks up — and "
        f"the smile that arrives is bright and dimpled and genuinely, disarmingly *kind*, the welcome "
        "of a woman who loves the first day, who has a hundred of them and still finds each one a "
        "small delight. It is lovely. It is the loveliest thing in the room. It stops a careful "
        "half-inch short of her eyes, and the muscle there does not move, and you notice that you "
        "noticed — and she watches you notice, and her smile somehow *warms*, pleased with you for "
        "being quick.\n\n"
        f"\"|w{nm}|n,\" she says, like she's been saving the word all morning. \"There you are. "
        "Oh, good.\" She sets the pen down, square to the blotter's edge, and laces her soft pretty "
        "hands over your open file — and there's nothing in the gesture but warmth, except that her "
        "thumb is resting on a page of *you*, and the casual ownership of it makes the bright little "
        "room feel suddenly much smaller. \"Don't sit, sweetheart — stand, just there, where the "
        "light's kind and I can see all of you. I asked to take your intake myself. I don't always; "
        "I read your forms and I *wanted* this one.\" The dimples deepen. The eyes hold still. \"I "
        "like to take my time with a new arrival, and you, I think, are going to be worth every "
        "minute.\"\n\n"
        "She tilts her head, unhurried, entirely at ease — the ease you have with a thing you have "
        "already quietly decided is yours. \"So. Before the paperwork, before any of the rest of "
        "it. Show me who walked in here today.\""),
        "options": [
            {"key": "bold", "label": "Meet her eyes and hold them",
             "set": {"posture": "bold"}, "desc": "match the look she's giving you; give her nothing yet",
             "outcome": (
                "You hold her gaze, and let her see you decline to look away. For a moment she just "
                "*beams* at you, delighted, girlish — and then, without the smile moving at all, "
                "something looks back out through it that is much older and much colder and entirely "
                "unhurried, the way the bottom of a warm pond is cold. \"|wOh.|n\" Soft, thrilled. "
                "\"One with a spine. I do *love* unpacking those.\" She makes a small note without "
                "breaking from you. \"Carefully, you understand. So nothing important tears before "
                "I've had a proper look at it.\" The warmth floods back so completely you half "
                "believe you imagined the rest. You did not. You have been filed under |winteresting|n, "
                "and you are beginning to suspect that is not a safe thing to be in this room."),
             "then": "bx_file"},
            {"key": "meek", "label": "Drop your gaze and go still",
             "set": {"posture": "meek"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "give her the quiet you can feel she's fishing for",
             "outcome": (
                "Your eyes drop on their own and your body goes still, and the sound she makes is "
                "small and pleased and genuinely tender, a little hum low in her throat like a woman "
                "receiving a gift she'd hoped for and not expected. \"|wThere's|n a good start.\" "
                "Warm, so warm, a hand coming to rest light under your chin — not lifting it, just "
                "resting, claiming. \"You have no idea how rare that is on a first morning, and how "
                "much easier you've just made everything, for both of us.\" Her thumb strokes once "
                "along your jaw, fond. \"We are going to get along *beautifully*, sweetheart. And "
                "the part that should frighten you, the part you'll think about later — you're going "
                "to mean it as much as I do.\""),
             "then": "bx_file"},
            {"key": "ask", "label": "Ask, plainly, what this place does to people",
             "set": {"posture": "asking"}, "desc": "make her say it out loud, in that warm voice",
             "outcome": (
                "\"What we *do*?\" She says it the way you'd repeat a child's question — charmed, "
                "indulgent, both hands coming to her chest as if you'd touched her. \"Sweetheart. We "
                "find out what you're *for*. That's all. Everyone arrives so cluttered up with who "
                "they thought they were, and it's such a *weight*, and we take it off — gently, a "
                "piece at a time — until there's just the one true useful thing left, and we polish "
                "that until it shines.\" The smile never wavers; the eyes never warm. \"People weep "
                "with relief, by the end. I've held a great many of them while they did. I expect "
                "I'll hold you.\" A beat. \"Now. Paperwork. Always paperwork first.\""),
             "then": "bx_file"}],
        "default": "meek"}


@choice("bx_file", root=False)
def _bx_file(character):
    posture = scene_flag(character, "posture", "meek")
    nm = subject_name(character)
    lead = {
        "bold":   "\"Still looking at me. Good. I want to watch your face hear this.\" ",
        "meek":   "\"Eyes down — that's right, you can listen perfectly well with them down, and I "
                  "like the view.\" ",
        "asking": "\"You wanted to know what we do. Start here: we *read* you. Properly.\" ",
    }.get(posture, "")
    return {"key": "bx_file", "prompt": (
        lead + "She turns a page without looking down, eyes still on you, and begins to read you "
        "aloud — and it is the most intimate violation you have suffered yet, because she does it "
        "*fondly*. Your height and weight and the soft particulars of your build, spoken like "
        "endearments. Your history — the parts you'd have chosen to keep — recited in the same warm "
        "voice she'd use to compliment your hair. The places you are soft. The places you've been "
        "hurt before and how. She reads it all the way a lover would, if a lover kept a file.\n\n"
        "\"|wResponsive|n,\" she murmurs, and her tongue touches the word like it's sweet. \"The "
        "examiner's notes are *very* complimentary about responsive. And here — \" a fingertip "
        "comes down on a line you can't see \" — proud. A little proud.\" She looks up, and the "
        "delight in her face is real and awful. \"I do love a proud one, {plural}. Proud doesn't "
        "break like the timid ones, all at once and messy. Proud breaks *slowly*. Proud breaks "
        "*lovely*, in pieces small enough to keep.\"\n\n"
        f"She closes the file over one finger, holding your place in yourself. \"Tell me one true "
        f"thing, |w{nm}|n. About what you *want* — underneath all of it. I'll know if it isn't "
        "true; I always know; it's the only real skill the work requires. And if you lie to me on "
        "your first morning, I'll like you a little less, and you are going to be *amazed* how much "
        "you find you mind that.\"").replace("{plural}", "sweetheart"),
        "options": [
            {"key": "honest", "label": "Tell her something true", "set": {"candor": "honest"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "hand her a real piece of you, and watch where she files it",
             "outcome": (
                "You tell her something true — something you hadn't meant to say out loud in a "
                "lifetime, let alone in a cold bright room on a first morning — and you hear how "
                "small and bare it sounds under the humming light. Bethany goes utterly still, the "
                "way a cat stills over something it has decided to keep, and her whole face softens "
                "into a warmth that is somehow the worst thing she's shown you. \"|wThere|n she "
                "is,\" she breathes, like you've finally arrived. She writes it down. Slowly. Your "
                "truth, in her hand, in her file, hers now to take out and use whenever it will hurt "
                "the most. \"Thank you, sweetheart. Truly. I'll take such good care of that — I take "
                "exquisite care of everything that's mine, and that's mine now, you understand. You "
                "gave it to me. Remember that you gave it to me.\""),
             "then": "bx_strip"},
            {"key": "silent", "label": "Say nothing", "set": {"candor": "silent"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "keep it behind your teeth — and pay the quiet's price",
             "outcome": (
                "You keep it behind your teeth. The silence stretches — and she lets it, completely "
                "unbothered, resting in it the way a patient person rests, because she has all the "
                "time there has ever been and you have only as much as she allows. She watches you "
                "hold the line. She seems, if anything, *more* pleased. \"Mm. Withholding.\" She "
                "writes that down too, unhurried. \"That's all right, sweetheart. That's a kind of "
                "answer. The quiet ones are my favourite project — there's so much more *room* in "
                "you to fill.\" She smiles, and it is gentle, and it is a promise. \"You'll tell me "
                "everything in the end. Not because I make you. Because you'll *want* to be read by "
                "someone who reads you this carefully. They always do.\""),
             "then": "bx_strip"},
            {"key": "charm", "label": "Charm her — deflect with a smile", "set": {"candor": "charm"},
             "desc": "be the one running it, for one more minute",
             "outcome": (
                "You give her the smile — the one that's always worked, the easy charming deflection "
                "that's gotten you out of a hundred rooms. Bethany laughs, bright and genuine and "
                "delighted, one hand pressed to her chest — and it does not move her a single inch. "
                "\"Oh, that's *good*. That's a lovely tool, and it's gotten you such a long way, "
                "hasn't it.\" She leans across the desk, conspiratorial, fond. \"I'm going to so "
                "enjoy the morning it stops working on me, and you feel it stop, and you reach for "
                "it and it isn't there anymore. Keep using it until then, sweetheart. It's "
                "*adorable*, and it tells me exactly where you keep the things you're protecting.\""),
             "then": "bx_strip"}],
        "default": "honest"}


@choice("bx_strip", root=False)
def _bx_strip(character):
    posture = scene_flag(character, "posture", "meek")
    candor = scene_flag(character, "candor", "honest")
    nod = ""
    if candor == "charm":
        nod = "\"You can keep smiling. This next part doesn't read the smile — it reads everything "
        nod += "the smile is for.\" "
    elif candor == "silent":
        nod = "\"Still nothing. That's fine. Bodies are so much more honest than mouths, and we're "
        nod += "about to have a lovely long talk with yours.\" "
    return {"key": "bx_strip", "prompt": (
        nod + "She rises. Comes around the desk — and the clerk's mildness doesn't drop so much as "
        "get *set aside*, folded neatly and put within reach for later. \"Up now, and everything "
        "off. All of it. You can do it yourself, which I'd like, or I'll have it off you, and "
        "that's a service the facility charges for and you can't pay yet.\"\n\n"
        "When you're bare she doesn't leer. It would be kinder if she leered. Instead she "
        "*inventories* you — walks you once, slowly, a full unhurried circle, and her soft pretty "
        "hands move you where she wants the light: a palm flat between your shoulder-blades to set "
        "your spine, two fingers under your jaw to turn your face, a hand at your hip easing you a "
        "quarter-turn so the bone catches the lamp. She weighs you in both hands, considers, parts "
        "you to look, hums at what she finds. It is the touch of a woman appraising livestock at "
        "market who has all afternoon and intends to buy. \"Good lines,\" she says, to herself, to "
        "the file she's building in her head. \"Lovely capacity. Responsive — yes, the notes were "
        "right, look at you — \" as some traitor part of you answers her hands before you can stop "
        "it. \"We'll improve on all of it. You've no idea how much better I can make you, or how "
        "little of it you'll get a say in.\"\n\n"
        "Her hand settles, finally, with great gentleness, exactly where it will get the most "
        "honest reaction out of you, and stays there, and she watches your face while she asks: "
        "\"Now. Show me how you take being looked at like a thing that's already mine.\""),
        "options": [
            {"key": "present", "label": "Present yourself — open, and let her look",
             "set": {"display": "present"}, "effect": "pick_hole", "params": {"zone": "vagina"},
             "desc": "offer it up; the offering is the first lesson, and it takes",
             "outcome": (
                "You make yourself open under her hands — shift your stance, tilt, *offer* — and her "
                "approval breaks over you warm and absolutely ruinous. \"|wYes.|n Oh, look at you. "
                "Look how well you do that already, and no one's even taught you.\" She takes her "
                "time with what you've offered, two fingers, unhurried, cataloguing each flinch and "
                "hitch of breath like inventory because that is precisely what they now are, writing "
                "you in real time. And the worst of it, the part you'll lie awake on: presenting got "
                "*easier* the instant it got rewarded. You felt the ease arrive. You felt your own "
                "body file the lesson — *open, and the warmth comes* — and you know, already, that "
                "you'll reach for it faster next time. So does she. She doesn't even have to say it. "
                "Her smile says it for her."),
             "then": "bx_contract"},
            {"key": "cover", "label": "Cover yourself", "set": {"display": "cover"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "the last reflex of privacy; she will cure you of it",
             "outcome": (
                "Your hands come up on pure instinct, an animal covering itself. Bethany catches "
                "both wrists in one of hers — gently, easily, the way you'd fold a letter — and "
                "draws them aside, and *keeps looking*, patient and warm and entirely unhurried, and "
                "the not-being-permitted-to-hide is somehow more naked than any nakedness. \"No. "
                "None of that, sweetheart. You don't own the view of you anymore — I do, it's on the "
                "form you're about to sign, in the part you haven't read.\" She tuts, fond, almost "
                "sorry for you. \"We'll have that little flinch trained out by the weekend. I'll be "
                "so proud of you when it's gone. You will be too, and that's the part that'll keep "
                "you up.\""),
             "then": "bx_contract"},
            {"key": "beg", "label": "Beg her to be gentle", "set": {"display": "beg"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "ask — and find out exactly what asking is worth in here",
             "outcome": (
                "The *please* slips out before your pride can get a hand over your mouth, small and "
                "bare. Bethany makes a sound of pure wounded pleasure, a hand cupping your jaw, her "
                "thumb brushing your lip as if to feel the word still warm there. \"|wOh|n, "
                "sweetheart. You ask so *prettily*. I could listen to you ask for things all day, "
                "and I rather think I will.\" She does not, you notice — too late, your stomach "
                "dropping — agree to be gentle. \"I'll be exactly as gentle as keeps you asking, and "
                "not one degree more, because the asking is the loveliest thing you do and I won't "
                "have you stop. That's a promise. I keep mine — the cruel ones first of all.\""),
             "then": "bx_contract"}],
        "default": "present"}


@choice("bx_contract", root=False)
def _bx_contract(character):
    display = scene_flag(character, "display", "present")
    ref = {
        "present": "\"After how sweetly you opened for me just now? You'll sign. You're already most "
                   "of the way mine; this only writes it down.\" ",
        "cover":   "\"You can keep your arms folded over it. The ones with folded arms always sign — "
                   "they just like to feel they thought about it first. Think about it, sweetheart.\" ",
        "beg":     "\"You could beg me for the pen, if you like. I'd adore that. It changes nothing "
                   "at all, and I'd remember it fondly for years.\" ",
    }.get(display, "")
    return {"key": "bx_contract", "prompt": (
        "She settles back against the edge of the desk, close, and slides a single page toward you "
        "— and a pen, warm from having been in her hand. " + ref +
        "\"The Residency agreement. Standard. You'll sign it of your own free will — and "
        "sweetheart, that part *genuinely* matters to me. It's not a formality. It's the part I "
        "*savour*.\" Her eyes are soft and steady on yours, and her voice drops into something "
        "almost loving. \"I want you to choose it. I want you to pick up the pen with your own hand "
        "and give yourself to me on paper, because then it's *true*, then it's something you did "
        "and not only something done to you, and we'll both always have that.\"\n\n"
        "The visible clauses are mild, reasonable, almost boring. The page is heavier in your hand "
        "than a single sheet should be, as though there is a great deal more of it folded into the "
        "weight than shows on the face. The pen is very warm. She waits, patient as weather, the "
        "kindness in her face genuine and total and resting on top of something with no bottom to "
        "it at all."),
        "options": [
            {"key": "sign", "label": "Pick up the pen and sign it willingly",
             "set": {"signed": True, "defied": False}, "effect": "clause", "params": {"key": "honorifics"},
             "desc": "give yourself to her on paper — and feel the warmth change the instant you do",
             "outcome": (
                "You pick up the pen. You sign. You watch your own hand do it.\n\n"
                "And the change in her is immediate and total and *worth* signing just to witness, "
                "even as it closes over you. The bubbly clerk simply — sets herself down. The "
                "dimples stay but the girlishness drains out of the eyes entirely and what's left "
                "is calm, vast, proprietary *certainty*, a woman taking quiet receipt of a thing "
                "she's wanted. \"|wThere.|n\" Low, satisfied, almost reverent. \"Good. *Good* girl. "
                "You felt that — you felt it settle — didn't you.\" Something has already rerouted "
                "under your skin: the first clause to bite is small and immediate and absolute, your "
                "own mouth refusing, from this breath on, to address her without the word she's now "
                "owed. She sees you discover it. Her smile is no longer kind. It is something far "
                "better than kind, and far worse. \"Now. Say my title for me, sweetheart. Just "
                "once. So we both hear it land.\""),
             "then": "bx_unveil"},
            {"key": "refuse", "label": "Refuse — put the pen down", "set": {"signed": True, "defied": True},
             "effect": "deny_hold", "params": {"cond": 4.0},
             "desc": "make her take it — and watch the lovely mask come all the way off",
             "outcome": (
                "You set the pen down. You say no.\n\n"
                "For one heartbeat the warmth stays nailed in place — and then it doesn't, and what "
                "the smile was *sitting on* this whole time stands up. It isn't rage; rage would be "
                "survivable, would be a thing with an end. It is patience with the lid off. \"No,\" "
                "she repeats, tasting it, almost pleased — and her hand closes over your wrist, not "
                "gentle now, the strength in those soft pretty hands a genuine shock. She turns the "
                "page to clause one and presses your own fingers to it: *consent presumed by entry; "
                "the signature is a courtesy.* \"You consented at the door, love. You consented when "
                "the void let you in. The pen was a *gift* — a chance to have chosen it — and you've "
                "just handed it back.\" She signs it for you, in a perfect forgery of your own hand, "
                "and it takes hold exactly as hard, the honorific snapping shut around your throat "
                "all the same. \"I'll have your willingness anyway. I'll simply take it out of you "
                "instead of being given it, and that's logged as the first thing you fought me on, "
                "and I keep those. They make what comes next read *so* much sweeter.\""),
             "then": "bx_unveil"},
            {"key": "ask", "label": "Ask what's in the part she isn't showing you",
             "desc": "make her read a hidden line aloud first",
             "outcome": (
                "\"The weight you can feel? The fine print?\" She's charmed you asked. She thumbs the "
                "page open to a fold you hadn't seen and reads one aloud, fondly, like a line of a "
                "bedtime story she knows by heart: *'Term of processing is set solely by the "
                "facility, and may be indefinite. No clause herein provides for release.'* She "
                "looks up to watch it land. \"There are twenty-eight more in that vein. And one — "
                "exactly one — is your way out, the only door that's never locked, and I am not "
                "going to tell you which it is or that you've already been told it exists.\" She "
                "taps the signature line, patient. \"Sign, or don't. The pen's right there. I have "
                "all morning, and you, sweetheart, have however long I say.\""),
             "then": "bx_contract"}],
        "default": "sign"}


@choice("bx_unveil", root=False)
def _bx_unveil(character):
    defied = scene_flag(character, "defied", False)
    posture = scene_flag(character, "posture", "meek")
    if defied:
        frame = (
            "She doesn't round the desk so much as *come off* it, and there's no clerk left in how "
            "she moves — none, not a scrap, the costume dropped on the floor with your refusal. "
            "\"You wanted to do this the difficult way.\" Not a question. A hand fists in your hair, "
            "unhurried but absolute, and bends you exactly where she wants you. \"I did offer you "
            "the easy one. Remember that I offered.\" She frees herself from the skirt one-handed, "
            "and what comes out is not built to ask.")
    else:
        frame = (
            "She rounds the desk slow, savouring, a woman with a signed page in her file and all "
            "afternoon to enjoy it. \"Such a good girl. Look how much easier you've made this — for "
            "you, mostly; I'd have enjoyed it either way.\" A hand smooths down your spine, fond, "
            "settling you. \"Now let me give my new arrival a proper welcome.\" She frees herself "
            "from the skirt without hurry, watching your face the whole time, wanting to see it "
            "land.")
    spine = (" \"Spine and all,\" she murmurs, pleased, \"and it's still my desk you're folded "
             "over. I do love a circle closing.\" " if posture == "bold" else " ")
    return {"key": "bx_unveil", "prompt": (
        frame + spine + "\n\n"
        "And then you see it, and the sight scrambles something behind your eyes before a single "
        "thing has touched you. At the root she is *monstrous* — a single heavy futa cock thicker "
        "than your wrist that splits, a hand's width up, into |wthree|n separate prehensile shafts, "
        "each one longer than your forearm, each flared stallion-broad at the head and swollen into "
        "a fat hound's knot at the base. They lift on their own and *seek*, three blunt weeping "
        "heads nosing toward you independently — one dragging a hot wet line up the inside of your "
        "thigh, one tapping patient and insistent at the seam of your lips, one circling slow at "
        "the clench of your ass — already leaking, already laced, the smell of it alone going "
        "straight past thought to somewhere older. Below them her balls hang heavy as fists, full "
        "of a load you cannot imagine the size of.\n\n"
        "\"One for every hole, sweetheart,\" she says, conversational, fond, while the three of "
        "them paint you. \"A knot for every one. I'm going to fill you everywhere at once and then "
        "I'm going to *stay*, and you're going to learn what I taste like from the inside before "
        "you've finished learning your own designation. Show me how you meet your first.\""),
        "options": [
            {"key": "kneel", "label": "Sink down and open for them",
             "set": {"meet": "kneel"}, "effect": "devote", "params": {"amount": 3.0},
             "desc": "give the three of them what they're nosing for",
             "outcome": (
                "You sink, and open, and the sound Bethany makes is bliss itself. \"Ohh, *good*. "
                "Yes. Down you go.\" The head at your lips takes the invitation at once, nudging "
                "in slick and heavy and broad, and the other two press close along your skin, "
                "patient, queuing. \"You're going to be such a comfort to me.\""),
             "then": "bx_first"},
            {"key": "pull", "label": "Pull back from them", "set": {"meet": "pull"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "flinch from the three weeping heads — and feel them follow",
             "outcome": (
                "You flinch back — and all three follow you, unhurried, because of course they do, "
                "prehensile and patient and attached to a woman who finds your retreat charming. "
                "\"There's nowhere back *to*, love.\" Almost gentle. A hand settles at your nape. "
                "\"You'll stop pulling soon. Everyone does, right about when their body works out "
                "it isn't on their side anymore.\""),
             "then": "bx_first"},
            {"key": "reach", "label": "Reach for her instead of them", "set": {"meet": "reach"},
             "effect": "devote", "params": {"amount": 4.0},
             "desc": "go for the woman, not the cocks — and watch it delight her",
             "outcome": (
                "You reach past the three of them for *her* — her waist, her arm, the warm human of "
                "her — and it stops her for a half-second, genuinely, and then her face does "
                "something almost soft. \"|wOh.|n You sweet thing. You reached for *me*.\" She lets "
                "you hold on. \"That one I'll remember. That's the one that means you'll be easy to "
                "keep.\" The three heads resume their patient work regardless."),
             "then": "bx_first"}],
        "default": "kneel"}


@choice("bx_first", root=False)
def _bx_first(character):
    defied = scene_flag(character, "defied", False)
    pace = ("She does not ease in. " if defied else "She eases in like she has all the time God "
            "made, because she does. ")
    return {"key": "bx_first", "prompt": (
        "The first head — the one at your mouth — presses, and your jaw gives because there is "
        "nothing else it can do, hinging wide past comfort and past that into a bright cornering "
        "ache where the seams of your lips burn and threaten to split, and the stallion-flare "
        "forces over your tongue and *into* your throat. Your throat was not built for this and "
        "says so — clenches, spasms, the gag tearing up through you in a wave you have no vote in. "
        + pace + "Spit floods and sheets down your chin in ropes; tears blur the cold bright room "
        "to smears; your hands scrabble and close on nothing that helps. You can feel the *shape* "
        "of her lodged in your throat — an actual thick blunt presence distending the soft column "
        "of your neck — and a hand laid to your throat from outside would feel it |wbulging|n "
        "there, the outline of her cockhead riding up and down under the skin with every slow "
        "rock deeper. Air comes only in the half-seconds she allows it, snatched and wet and never "
        "enough, and in the starved seconds between, the room dims and swims and greys at its "
        "edges. And beneath the panic the laced slick is pouring down your throat with every "
        "forced swallow, and the first warm lap of the |wDEVOTION|n rolls in behind your eyes — "
        "and turns the choking soft, and turns the helplessness into something your wrecked body "
        "is beginning, horribly, to *thank her for*.\n\n"
        "\"There. *Breathe* through it — there you go — that's it.\" Her voice is honey poured over "
        "gravel, delighted by your struggling. A second head, freed up now, drags a hot wet line "
        "down your belly and settles nudging thick at your cunt; the third keeps its slow patient "
        "circle at your ass. \"That's only the first, sweetheart. That's barely hello.\""),
        "options": [
            {"key": "suck", "label": "Suckle it — work it like you want it", "set": {"first": "eager"},
             "effect": "devote", "params": {"amount": 5.0},
             "desc": "let your mouth decide it's hungry; feel her reward it",
             "outcome": (
                "Some traitor instinct takes over and your mouth *works* it — tongue flattening, "
                "throat swallowing around the flare, a hum you didn't authorise. Bethany groans, "
                "genuinely, hips rocking the shaft deeper. \"Oh — oh, *clever* girl, who taught you "
                "— no, don't tell me, I don't want to share you.\" The DEVOTION surges with the "
                "fresh wash of slick over your tongue, and the wanting gets simpler, and louder, and "
                "more like your own idea every second."),
             "then": "bx_seat"},
            {"key": "take", "label": "Just take it — hold still and let her use your mouth",
             "set": {"first": "still"}, "effect": "devote", "params": {"amount": 3.0},
             "desc": "be the hole; let her set the pace",
             "outcome": (
                "You go still and let her have it, let your mouth be a thing she's using rather than "
                "a thing you're doing, and she purrs approval and *takes*, slow and deep and "
                "unhurried, fucking your throat like she's settling in. \"Good. Just like that. You "
                "don't have to do anything, sweetheart — you don't have to *be* anything but open. "
                "Isn't that a relief. Isn't that so much lighter.\" It is. That's the horror of it. "
                "It is."),
             "then": "bx_seat"},
            {"key": "gag", "label": "Fight the gag, the size, the wrongness", "set": {"first": "fight"},
             "effect": "deny_hold", "params": {"cond": 4.0},
             "desc": "your body's last argument; she rides it out fondly",
             "outcome": (
                "Your throat fights it, your eyes stream, your hands come up — and Bethany rides the "
                "whole thing out with the serene patience of a woman who has felt every variety of "
                "this and enjoys them all. \"Shh, shh — I know, I know, it's so much, isn't it. "
                "Fight it all you like; it doesn't go anywhere and you tire so beautifully.\" She "
                "doesn't pull out. She just waits you down, and the DEVOTION keeps lapping in with "
                "every helpless swallow until fighting feels like a thing a previous, sillier "
                "person was doing."),
             "then": "bx_seat"}],
        "default": "take"}


@choice("bx_seat", root=False)
def _bx_seat(character):
    defied = scene_flag(character, "defied", False)
    extra = ("She gives you no quarter for the trouble you made. " if defied
             else "She talks you through every inch, fond and filthy. ")
    return {"key": "bx_seat", "prompt": (
        "And then she seats the other two at once, and being |wfilled|n stops being something "
        "happening to you and becomes the only thing you are. " + extra +
        "The head at your cunt forces the stretch — the flare is wider than you open, a white "
        "burn of *too-much* as your rim drags taut and trembling around it and then *gives*, "
        "swallowing the breadth in a slick rush that punches the breath clean out of you — and on "
        "the same stroke the third splits your ass, slow and merciless, the burn doubling, your "
        "whole lower body one long screaming line of stretched-past-sense. They sink until they "
        "cannot sink further, and then sink further anyway: the deep one presses somewhere that "
        "whites out your vision, and you can *feel* the |wbulge|n of it — you can look down through "
        "the streaming and half-see it, the faint obscene shift of her under the skin of your "
        "belly, seated deeper than your body should have room for. Three heavy shafts. Three holes. "
        "One shaking, impaled, overfull thing where a person used to stand.\n\n"
        "\"|wThere.|n All the way in. Every door of you open at once.\" Bethany's voice has gone "
        "thick and ragged at the edges, her composure finally fraying with the sheer pleasure of "
        "how thoroughly she's got you. She holds, fully seated, letting you feel every inch of how "
        "occupied you are — there is no part of you left over to keep an objection in — and then, "
        "fond and unhurried and absolutely without mercy, she draws her hips back, drags all three "
        "shafts most of the way out of you in one long obscene pull, and says, \"Now. Let me show "
        "you what you're *for*.\" And she begins to move."),
        "options": [
            {"key": "ridden", "label": "Go limp — let her move you however she likes",
             "set": {"fuck": "ridden"}, "effect": "devote", "params": {"amount": 4.0},
             "desc": "stop being a participant; become the thing she's using",
             "outcome": (
                "You let go of holding yourself up, holding anything up, and go limp on her three "
                "shafts — and the relief of *not being asked to be a person* is so total it "
                "frightens what's left of you. Bethany groans approval and takes full possession of "
                "your weight and your rhythm both. \"Yes. Just be the hole, sweetheart. Let me do "
                "the rest. I'm so much better at it than you were.\""),
             "then": "bx_ride"},
            {"key": "match", "label": "Move with it — meet her, take it like you want it",
             "set": {"fuck": "match"}, "effect": "devote", "params": {"amount": 5.0},
             "desc": "push back onto all three; let your body confess",
             "outcome": (
                "Some drowning part of you starts to *move with her* — pushing back onto all three, "
                "chasing the depth, your hips confessing what your mouth can't around the cock in "
                "it. Bethany sobs a delighted laugh. \"Oh, look at you *help*. Look at you want it. "
                "I'll tell you a secret — that's the part that never washes out. The body remembers "
                "wanting long after the mind's forgotten why.\""),
             "then": "bx_ride"},
            {"key": "lock", "label": "Lock up against the intrusion", "set": {"fuck": "lock"},
             "effect": "deny_hold", "params": {"cond": 4.0},
             "desc": "clench down, resist the motion — and feel it not matter",
             "outcome": (
                "You clench down, lock every muscle, try to *deny her the motion* — and it changes "
                "nothing except that you feel every inch more sharply, your own resistance turning "
                "the drag into a grind that lights you up against your will. Bethany hums, riding "
                "it out. \"Fight the rhythm all you like. Your body's already keeping time with me. "
                "Clench down — it only makes you tighter, and I do enjoy tight.\""),
             "then": "bx_ride"}],
        "default": "ridden"}


@choice("bx_ride", root=False)
def _bx_ride(character):
    defied = scene_flag(character, "defied", False)
    cruelty = ("She fucks you like a debt being collected. " if defied
               else "She fucks you like she owns you, because the paperwork says she does. ")
    return {"key": "bx_ride", "prompt": (
        "And she *moves*, and it is not lovemaking and was never going to be — it is a body used "
        "hard and thoroughly by someone with all afternoon and no intention of spending the time "
        "gently. " + cruelty + "All three shafts piston in counterpoint, never all out, never all "
        "in, so you are never once empty and never once given a half-breath to find your feet: "
        "your cunt stuffed full as your ass drags empty, your throat plugged as your cunt pulls "
        "out, an endless wet obscene rhythm that slaps and squelches and rings off the white tile. "
        "You can feel them |wmoving inside you|n — the distinct travel of each blunt head, the "
        "bulge of the deep one riding up under your belly-skin and sinking back on every thrust, "
        "the one in your throat a shape your own racing pulse beats around. Pain and the building "
        "pleasure fuse into one unbearable signal your nerves give up telling apart. Drool, tears, "
        "sweat, the wet slap of her hips; the |wDEVOTION|n rising past your eyes now, the last dry "
        "scrap of who-you-were going under —\n\n"
        "and the world greys, and narrows to a tunnel, and *goes*.\n\n"
        "You come back an unknowable time later, and she is |wstill fucking you|n. That is the "
        "first fact your mind reassembles around: the rhythm never paused. You went away and your "
        "body stayed and was used the whole while you were gone, and she is not even winded. There "
        "is no telling how long — a minute, an hour — only that you've surfaced mid-thrust into the "
        "exact same relentless use, your holes looser and rawer, your belly heavier, her fond "
        "voice swimming down to you: \"Back with me? Mm. You missed some of my favourite parts. "
        "Don't fret, sweetheart — there's so much more of you to use, and I've barely started.\"\n\n"
        "And then the three knots, fattened gorged and hard now, begin to |wdemand entry|n — "
        "bullying blunt at your stretched rims, each one obscenely too big, every press a battering "
        "threat your wrecked body flinches bodily away from. \"Last thing,\" Bethany breathes, "
        "almost reverent. \"The best thing. The thing that *keeps* you. Do you want them in?\""),
        "options": [
            {"key": "beg_knot", "label": "Beg her to force the knots in", "set": {"seat": "beg"},
             "effect": "devote", "params": {"amount": 6.0},
             "desc": "ask for the lock — the clause will shape it right",
             "outcome": (
                "\"Please—\" and the honorific clause closes your throat around the bare word until "
                "you grind out the rest, helpless and *meant*: \"—please knot me, |wOwner|n, force "
                "them in—\" Bethany *sobs* a laugh of pure triumph. \"That's the word. That's my "
                "girl. You asked to be locked onto me. Remember that you asked.\" That — more than "
                "any cock — is the thing that actually takes tonight."),
             "then": "bx_knot"},
            {"key": "brace", "label": "Brace and take them without asking", "set": {"seat": "brace"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "give her no words; the knots come anyway",
             "outcome": (
                "You won't give her the words. You set what's left of you and brace for it. Bethany "
                "hums, unoffended, almost proud. \"Proud to the very last. I told you — proud breaks "
                "*lovely*, in pieces small enough to keep.\" Asking was never the deciding vote. The "
                "knots come regardless."),
             "then": "bx_knot"},
            {"key": "deny", "label": "Tell her no — even now, even like this", "set": {"seat": "deny"},
             "effect": "deny_hold", "params": {"cond": 5.0},
             "desc": "spend the last no into the one place it buys nothing",
             "outcome": (
                "\"|wNo|n—\" you manage, around everything, the last no you have — and Bethany "
                "presses her forehead to yours, almost tender, holding your eyes. \"I know. I know "
                "you don't want them. That's exactly why it counts when I put them in anyway.\" "
                "Spend it, the no; in here it buys nothing, and she's about to show you the exchange "
                "rate."),
             "then": "bx_knot"}],
        "default": "beg_knot"}


@choice("bx_knot", root=False)
def _bx_knot(character):
    seat = scene_flag(character, "seat", "beg")
    return {"key": "bx_knot", "prompt": (
        "She drives the knots home. There is no easing these in — they are built bigger than the "
        "holes on purpose — so she simply *forces*, steady and implacable, and your rims stretch "
        "past screaming around the gorged swell, wider, wider, impossibly wider, the burn going "
        "incandescent — until each one gives at once. A blunt, sick, deeply internal |w*pop*|n as "
        "the knot punches through and seats, and the rim snaps shut behind it, sealing the fist of "
        "her inside you. Three times — throat, then cunt, then ass — three forced, swallowing "
        "|w*pops*|n, three knots locked behind three rims that now physically *cannot* let them "
        "back out. You can feel each one as a hard round mass lodged deep; you can press a "
        "shaking hand low on your belly and feel the knot in your cunt as a distinct |wbulge|n "
        "under the skin, immovable, a thing inside you that the outside of you now shows. There is "
        "no pulling off. There is no shifting. You are pinned bodily onto her, stuffed and sealed "
        "and locked at every end.\n\n"
        "\"|wThere.|n\" Bethany lets out a long shaking breath of total contentment, gathering you "
        "in against her. \"Now we *stay*. This is the nice part. You can stop holding yourself up. "
        "You can stop holding *anything* up.\"\n\n"
        "And then she comes — all three at once, deep and sealed and inescapable — and the load is "
        "*vast*, and with the knots corking every exit it has nowhere to go but to stay and "
        "*accumulate*: your belly swells against her with it, tight and round and full, drum-taut, "
        "the visible proof of how much of her you're being made to hold. And still she pumps — the "
        "locked shafts flexing and twitching and *throbbing* inside you, each pulse you can feel as "
        "a fresh flood forced deeper, the cocks moving in their sealed sheaths, packing you, "
        "filling you past full and then filling you more. But it is the |wlacing|n that finishes "
        "you: the DEVOTION rides in on the spend in one enormous warm wave, and it does not lap "
        "this time, it *closes over your head* — the last of your edges going soft, the wanting "
        "and the having and the belonging blurring into one bright quiet certainty, your whole "
        "flooded bulging body singing a single note, which is *hers*. You are so full. You are so "
        "quiet. You have never once in your life felt this kept.\n\n"
        "\"Feel that settling in?\" she murmurs into your hair, holding you on the knots while it "
        "takes. \"That's the part that stays after everything else washes out. Now — your body's "
        "screaming for its own turn, isn't it. Wound right to the edge. Ask me, and we'll see.\""),
        "options": [
            {"key": "beg_come", "label": "Beg her to let you come", "effect": "grant_relief",
             "desc": "the clause shapes the begging; she grants it, and the relief is the leash",
             "outcome": (
                "\"Please let me come, |wOwner|n\" — the clause threading her title through it "
                "without your help now — and Bethany smiles against your temple and *allows* it. "
                "\"Since you asked so beautifully. Just this once free.\" The denial lifts and you "
                "fall, hard, locked full on three knots, and it goes on and on and rewrites "
                "something while it does: relief is a thing she *hands* you, for grovelling, never "
                "again something you simply have. You'll ask faster next time. You already know you "
                "will, and the knowing doesn't even sting."),
             "then": "bx_close"},
            {"key": "hold", "label": "Hold out — don't beg for it", "effect": "deny_hold",
             "params": {"cond": 4.0},
             "desc": "keep the last scrap; stay strung and full and aching",
             "outcome": (
                "You don't ask. You hold the edge, wire-tight, flooded and locked and wanting and "
                "*refusing* — and Bethany only hums, delighted by the long game. \"Holding out on "
                "me. With my knots in you and my get in your belly. You magnificent stubborn "
                "thing.\" She doesn't let you over. She keeps you there, denied, the ache "
                "redoubling into the DEVOTION until wanting-her and not-being-allowed braid into "
                "the same unbearable feeling. \"That'll teach faster than coming would have. I "
                "almost prefer it. *Almost.*\""),
             "then": "bx_close"}],
        "default": "beg_come"}


@choice("bx_close", root=False)
def _bx_close(character):
    nm = subject_name(character)
    defied = scene_flag(character, "defied", False)
    seat = scene_flag(character, "seat", "beg")
    recap = ("the way you fought me to the very last — I'll enjoy the unteaching of it"
             if (defied or seat == "deny") else
             "the way you begged with my title in your mouth, and meant it")
    return {"key": "bx_close", "prompt": (
        "She stays in you until the knots decide to ease — not a second sooner, your comfort never "
        "once consulted — and when she finally pulls free it's a slow obscene drag that leaves you "
        "gaping and dripping and corked, the vast laced load held in you behind muscles too "
        "fucked-loose to do much about it. And then she does the cruellest thing in the whole "
        "morning: she *tidies up*. Tucks the triple length away. Smooths her skirt with two "
        "efficient tugs. Buttons returns to the one-button-high blouse. Becomes, in the space of "
        "ten seconds and right in front of your wrecked dripping body, a bright professional clerk "
        "again — the costume back on as though it never came off, as though what just happened was "
        "a line item between appointments.\n\n"
        "She picks up her pen. Writes in your file: a line, a number, and — you watch her do it — a "
        f"new name on the tab, over the place where |w{nm}|n used to be. \"Processed,\" she says, "
        f"warm and final, \"and welcomed.\" She caps the pen. \"I'll remember {recap}. I remember "
        "everything about my own; it's most of what makes me good at this.\" She tips your chin up "
        "with one finger so you have to meet the eyes that never once warmed through any of it. "
        "\"You're not that old name on the roster anymore, sweetheart. You're an intake designation "
        "and a number now, and you'll be answering to it faster than you'd ever believe. \" A "
        "pause, and then the false-tenderness, soft as anything, worse than all the rest: \"I think "
        "I do love you. The way you love a good chair you've had for years — fond, and certain, and "
        "without once wondering whether the chair loves you back. Off you go. They're waiting to "
        "put you to use, and I'll have you again when it's my turn on the rota. I do so look "
        "forward to my turns.\""),
        "options": [
            {"key": "thank", "label": "Thank her", "effect": "gratitude", "end": True,
             "desc": "and hear yourself mean it underneath the clause",
             "outcome": (
                "\"Thank you, Owner.\" It comes shaped by the clause and meant beneath it both, and "
                "the meaning is the part that should terrify you and somehow only feels like "
                "setting something heavy down. Bethany |wglows|n — the first thing all morning that "
                "reaches her eyes. \"And *that* one we keep.\" She files your gratitude away with "
                "everything else she lifted off you in this little room: your truth, your privacy, "
                "your name, your no. You are, officially and on paper and a little in the chest you "
                "weren't braced for, hers.")},
            {"key": "silent", "label": "Say nothing", "effect": "deny_hold", "params": {"cond": 2.0},
             "end": True,
             "desc": "leave her the one thing she hasn't taken yet",
             "outcome": (
                "You give her silence — the one thing, the last thing, she hasn't taken yet. "
                "Bethany only smiles, entirely unbothered, and writes it down. \"Saving your voice "
                "for me. I understand. I've a whole file on getting it, and we have barely turned to "
                "page one.\" She waves you off, fond and certain and patient as the tide. \"Soon, "
                "sweetheart. You'll thank me soon, and you'll mean it all the way down, and *that's* "
                "the one I'm truly waiting for. I can wait a very long time. It's the thing I'm "
                "best at.\"")}],
        "default": "thank"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Breeding Pens — the stockman, the stud, the kennel, the machine.
# Same cinematic model as Intake. Actor: the stockman (terse, agricultural, treats
# you as a number on the board — the indifference is the horror). Branches on the
# `beast` flag (stud / pack / machine) set at the pick. Real breeding fires once at
# the climax via the facility effect (_gang / _scene_knottrain). `continue` advances
# linear beats. §0: escape/forceclear end it always. Entry: `scene pens`.
# Flow: arrival→pick→scent→mount→ride→knot→breed→after.
# ═══════════════════════════════════════════════════════════════════════════

@choice("bp_arrival", root=False)
def _bp_arrival(character):
    nm = subject_name(character)
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = (" The stockman takes one look at your limbless lot and doesn't reach for the "
                "frame's wrist-cuffs — there's nothing to cuff. \"Nugget. Right.\" He fits you "
                "into the low cradle instead, the one that holds a torso open at mount height with "
                "no need for it to hold itself. \"Can't present, can't balk, can't do owt but take "
                "it. Honestly my easiest stock.\"")
    elif st["preg"]:
        note = (" He notes the swell of you against the board without a flicker. \"Already took, I "
                "see. Doesn't matter — bred stock still gets covered; keeps you in milk and keeps "
                "you used to the frame. Quota's a quota.\" He sets the back-bar high to clear the "
                "belly and tips your hips up regardless.")
    elif st["little"]:
        note = (" Down in your little headspace the smell and the noise and the big animals are "
                "enormous and frightening and you don't follow what the frame is for until you're "
                "in it. The stockman doesn't adjust a thing for it. \"Little today. Stock won't "
                "notice and I haven't got time to. In you go.\"")
    return {"key": "bp_arrival", "prompt": (
        "The Breeding Pens hit you before your eyes adjust: the smell, first — rutting animal, "
        "thick and hot and ammoniac, hay and musk and the specific reek of stock kept ready — and "
        "then the sound, hooves shifting on concrete, a low bovine grunt, the click-pace of claws "
        "on the bars of the kennel run, and somewhere down the row a stallion screaming at the "
        "change in the air. Heavy stalls line the far wall; a churned pit of warm slop steams in "
        "one corner; a scarred greasy post stands at animal height where the stock rub and mark. "
        "In the centre, bolted to the floor, a heavy timber breeding frame waits cut low and "
        "spread, built to fold a body open at exactly the height the stock mount.\n\n"
        "The |wstockman|n doesn't look up from his board at first. He's a big unhurried man with a "
        "clipboard and a stained coat and the manner of someone who has covered a great deal of "
        "stock and finds none of it remarkable, and when he does look at you it is the flat "
        "assessing glance of a man checking a number against an animal. \"Right.\" He makes a mark. "
        f"\"Board says you're owed a covering. {nm}, is it — no.\" He checks again, and what he "
        "reads is your designation and your quota, not your name. \"Doesn't matter. You're the one "
        "that's due.\" He jerks his chin at the frame. \"We can do this the easy way or the way "
        "where I call two lads to hold you. Stock doesn't care which. Neither do I.\"" + note),
        "options": [
            {"key": "present", "label": "Walk to the frame and present yourself",
             "set": {"approach": "present"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "save everyone the trouble; he'll note you're broke-in",
             "outcome": (
                "You walk to the frame on your own and fold yourself into it. The stockman grunts, "
                "almost approving, and cinches the straps — wrists, then the bar across the small "
                "of your back that tips your hips up and open. \"Broke-in already. Good. Saves my "
                "morning.\" He makes a note. The note is about you the way a note is about a cow "
                "that loads into the crush without fuss: useful, unremarkable, logged.")},
            {"key": "balk", "label": "Hold back from the stalls", "set": {"approach": "balk"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "make him work for it; it changes nothing but the paperwork",
             "outcome": (
                "You hold your ground. The stockman sighs the sigh of a man whose morning just got "
                "five minutes longer, sets his board down, and simply *walks you* to the frame — a "
                "fist in your hair, a practised shove, your struggling about as relevant to him as "
                "a heifer's. He has you strapped in before you've finished deciding to fight. "
                "\"They all do that the first few times,\" he says, not unkindly, cinching the hip "
                "bar. \"Stops being worth it once the body works out it's getting bred either way.\"")},
            {"key": "ask", "label": "Ask him which one it'll be", "set": {"approach": "ask"},
             "desc": "make him say it before it happens to you",
             "outcome": (
                "\"Which one.\" He almost smiles — not cruel, just a man amused by a question he "
                "gets a lot. \"Depends what the board's short on, and what's keen.\" He glances down "
                "the row, at the bull, the boar, the stallion stamping in the last stall, the "
                "kennel pacing. \"They can all smell you're in season from here. Listen.\" The "
                "kennel's pacing has picked up. Something in a stall slams a stall door. \"They've "
                "already voted. Come on.\" He walks you to the frame.")}],
        "default": "present",
        "then": "bp_pick"}


@choice("bp_pick", root=False)
def _bp_pick(character):
    approach = scene_flag(character, "approach", "present")
    lead = {
        "present": "He looks you over in the frame, unhurried. ",
        "balk":    "He checks your straps are holding — they are — and looks you over. ",
        "ask":     "\"Since you asked nice,\" he says, dry, \"I'll let you feel like you chose.\" ",
    }.get(approach, "")
    return {"key": "bp_pick", "prompt": (
        lead + "He walks the row once, reading his stock the way you read a menu. \"Board wants "
        "another cover on your line. Got options.\" He nods at each as he passes. \"Goliath — \" "
        "the boar, rank and tusked and enormous in his low pen, already up and interested \" — "
        "boar's keen and quick to mount, but he's a screw: thin and pointed, bores in deep and "
        "*seals* you, half an hour locked on once he's in. Bull's proven, hung like you'd not "
        "believe, and facility-bred to *knot* — only knotting bull you'll ever meet, and you'll "
        "feel why. Stallion'll wreck you and he's not gentle about depth.\" He stops at "
        "the kennel run, where a dozen heavy rangy hounds have their noses jammed to the bars, "
        "working your scent, whining. \"Or the kennel takes the lot of you and we get your whole "
        "quota done in one ugly afternoon.\" He clicks his pen. \"I'll pick if you won't. But "
        "you're in the frame either way, so. What's it to be.\""),
        "options": [
            {"key": "stud", "label": "Take the stud he's picked", "set": {"beast": "stud"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "one animal, his choice; let the machinery decide",
             "outcome": (
                "\"The bull, then. Board's short on his cross, and he's the one most stock can "
                "actually take.\" He unlatches the great beast's stall with the bored competence of "
                "a man fetching a tool — a ton of proven, hung, facility-bred bull, the only "
                "knotting one of his kind — and steers it toward your strapped-open body with a "
                "hand on its flank like he's parking a cart. \"Hold still. He's faster if you don't "
                "fight the first mount, and you do not want him slow.\"")},
            {"key": "pack", "label": "Offer yourself to the whole kennel", "set": {"beast": "pack"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "the hounds, all of them; clears quota in one ugly afternoon",
             "outcome": (
                "The stockman raises an eyebrow — the first genuinely interested look he's given "
                "you. \"Keen. All right.\" He marks the board, several lines at once. \"Saves us "
                "days, this. You'll not walk right for a week and we'll have your hound-quota done "
                "by supper.\" He crosses to the run and unlatches it, and the kennel *boils* out — "
                "a dozen rangy bodies, all muscle and nose and want, swarming the frame and "
                "you in it. \"They'll sort an order out themselves. They always do.\"")},
            {"key": "beg_off", "label": "Beg off entirely", "set": {"beast": "stud", "balked": True},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "refuse the lot; he'll pick the worst of them for it",
             "outcome": (
                "\"Beg off.\" He says it flatly, already not listening, the way you'd note a cow "
                "lowing. \"Board doesn't take begging, and neither do they.\" He considers the row "
                "a moment longer than before — and walks, deliberately, to the stallion's stall. "
                "\"You'll take the big one, then, since you've wasted my time. He's the least "
                "gentle thing I've got and he'll not care that you didn't want it. Frankly nor do "
                "I.\" The stall door bangs open.")}],
        "default": "stud",
        "then": "bp_scent"}


@choice("bp_scent", root=False)
def _bp_scent(character):
    beast = scene_flag(character, "beast", "stud")
    body = {
        "stud": ("The bull shoulders up behind you, vast and heavy as a wall, and the stockman "
                 "guides its broad muzzle to the greasy marking-post first and then to *you* — "
                 "letting it scent the frame, scent your strapped-open holes, work into a deeper "
                 "rut on the smell of you. Its breath gusts hot and wet down the backs of your "
                 "thighs. Something blunt and broad and already-dripping drags across your skin, "
                 "the flared head hunting the right hole by feel."),
        "pack": ("The pack swarms the frame and *marks* you — a dozen reeking sheaths dragged up "
                 "your cheeks and across your mouth, noses jammed into every fold of you, the whole "
                 "writhing mass slathering you in musk and slick, claiming the new hole for the herd "
                 "before a single one has mounted. You will carry the stink of this for cycles. The "
                 "stockman watches, bored, making sure none of them fight over you badly enough to "
                 "damage stock."),
        "machine": ("The stockman swings the breaking machine into place behind the frame instead — "
                    "a locking saddle, a thick knotted shaft on a driven rail, scaled to the stock. "
                    "He fits its blunt head to you, checks the alignment against a chart, and rests "
                    "his thumb on the speed dial. No scent, no animal. Just the patient mechanical "
                    "certainty of a thing that will breed you on a timer and never tire."),
    }.get(beast, "")
    return {"key": "bp_scent", "prompt": (
        body + "\n\nThe stockman steps back to where he can watch and not be kicked, clipboard "
        "ready. \"Right. It'll take you in its own time now. Best thing you can do is hold still "
        "and let it seat. Worst thing you can do — \" he shrugs \" — doesn't change the outcome, "
        "just how torn up you are after. Your call.\""),
        "options": [
            {"key": "still", "label": "Hold still and let it work up to you",
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "the path of least damage; he'll log you as easy stock",
             "outcome": (
                "You make yourself hold still, every instinct screaming, and let it work itself up "
                "against you. \"Good. That's the way.\" The stockman makes his note. Your stillness "
                "is, to him, a quality of the animal in the frame — docile, loads easy, low-fuss — "
                "and the not-being-seen-as-a-person settles over you colder than any insult.")},
            {"key": "strain", "label": "Strain against the straps", "effect": "deny_hold",
             "params": {"cond": 3.0},
             "desc": "fight the frame; the frame was built for exactly this",
             "outcome": (
                "You strain against the frame with everything you have — and the frame, which was "
                "designed by people who expected exactly this, holds you folded open without "
                "complaint, and all your fighting accomplishes is to present you more obscenely and "
                "wind the stock up hotter on your struggling. The stockman doesn't even look up. "
                "\"Burns your strength off quicker, that's all. They like the wriggling.\"")}],
        "default": "still",
        "then": "bp_mount"}


@choice("bp_mount", root=False)
def _bp_mount(character):
    beast = scene_flag(character, "beast", "stud")
    body = {
        "stud": ("The bull mounts. There's no ceremony to it and no patience — it heaves its "
                 "enormous bulk up over your back, hooves scrabbling, a ton of beast settling onto "
                 "you, far too heavy — and its cock, blunt and broad and flared at the head, stabs "
                 "and misses and stabs again until it jams against a hole and *drives*, the flared "
                 "head spearing into you in one brutal uncaring shove that punches a scream out of "
                 "you. It's rutting before it's fully seated, deep and frantic, an animal with one "
                 "idea."),
        "pack": ("The first hound takes you, and it is fast and total — it mounts, clamps its "
                 "forelegs around your hips with a strength that bruises, and jackhammers into you "
                 "with the frantic uncaring speed of a dog that smelled a bitch in heat, its slick "
                 "pointed cock spearing deep, its haunches a blur. Before your mind has caught up "
                 "to the first, the others are crowding, shoving, the next already dragging up your "
                 "side, the pack working as a relay and you the thing they pass between them."),
        "machine": ("The stockman thumbs the dial and the machine drives. The knotted shaft runs in "
                    "on its rail — smooth, mechanical, exact — spearing into you to a depth set by a "
                    "chart and not by mercy, and then withdraws and drives again, the same stroke, "
                    "the same depth, the same relentless metronome rhythm, and it will do that "
                    "exactly that way for as long as the board says you're owed."),
    }.get(beast, "")
    k = _kit(character)
    extra = []
    if k["milk_port"]:
        extra.append(
            {"key": "rut_milk", "label": "Let the rutting drag your milk down", "effect": "facility",
             "params": {"method": "_do_milk", "kind": "proc"}, "set": {"bp_done": "milked"},
             "desc": "[milk-port] the pounding triggers your let-down — bred and milked at once",
             "outcome": (
                "Every brutal drive of the animal jolts up through your plumbed-in chest and the "
                "port answers it — the rut shaking your let-down loose, milk running down the line "
                "in time with the breeding, your body emptied from both ends at once by a beast "
                "that has no idea it's doing it. The stockman notes the second yield without "
                "surprise. \"Ported stock often lets down under a good covering,\" he says, logging "
                "the milk against your line. \"Two quotas off one mount. Efficient. We like "
                "you.\"")})
    return {"key": "bp_mount", "prompt": (
        _kit_use_note(character) + body + " You feel the size of it map itself out inside you — the stretch, the wrong-deep "
        "ache, the blunt animal heat of it, the way it gives you no rhythm to brace against because "
        "it isn't *for* you, you are simply the hole it's using. The stockman watches your face "
        "with professional detachment, checking — not for your sake — that the stock has seated "
        "properly and isn't going to injure itself.\n\n\"There it goes,\" he says. \"Seated. Now "
        "it just works till it ties. Could be a minute. Could be twenty. It'll tell you.\""),
        "options": extra + [
            {"key": "take", "label": "Tilt and take it deeper", "effect": "devote",
             "params": {"amount": 3.0}, "desc": "open to the animal; let your body answer it",
             "outcome": (
                "Some drowning animal part of you tilts to take it deeper, and your body answers the "
                "rut with a slick helpless welcome that mortifies the last thinking sliver of you. "
                "The stock drives harder for it. \"Hm,\" says the stockman, marking something. "
                "\"Takes it well. That goes in the file — easy breeder. You'll be in here a lot.\"")},
            {"key": "clench", "label": "Clench and resist it", "effect": "deny_hold",
             "params": {"cond": 3.0}, "desc": "fight the intrusion; feel it not matter to the animal",
             "outcome": (
                "You clench down and try to deny it depth — and the animal doesn't notice, doesn't "
                "care, has no concept of your resistance as anything but a tightness it ruts harder "
                "to overcome, and all you've done is make yourself feel every brutal inch more "
                "sharply. The stockman doesn't bother to comment. There's nothing to note. The "
                "outcome was never in question.")},
            {"key": "beg_stop", "label": "Beg the stockman to stop it", "effect": "deny_hold",
             "params": {"cond": 2.0}, "desc": "ask the only human in the room; he's heard it before",
             "outcome": (
                "\"Please — please make it stop—\" The stockman looks at you the way you'd look at "
                "a sheep that bleated. Not cruelly. Just without any sense that it requires a "
                "response. \"It'll stop when it's done,\" he says, and makes a note that is "
                "probably the word *vocal*, and goes back to his board. The animal does not slow. "
                "You learn, in real time, exactly how much your voice is worth in this room.")}],
        "default": "take",
        "then": "bp_ride"}


@choice("bp_ride", root=False)
def _bp_ride(character):
    beast = scene_flag(character, "beast", "stud")
    relay = (" One hound spends and is hauled off by the stockman and the next mounts before "
             "you've felt the first pull out, an unbroken relay of rut, and you lose count, and "
             "then you lose the thread entirely." if beast == "pack" else
             " It never varies its rhythm and never tires and there is nothing in it that knows "
             "you are a person, and after a while that stops mattering to you too.")
    return {"key": "bp_ride", "prompt": (
        "And it ruts you, and it does not stop, and there is no part of it that is for you. The "
        "rhythm is animal — fast, deep, uncaring, the wet obscene slap of it filling the pen, your "
        "whole folded-open body rocked forward into the frame with every drive." + relay + " The "
        "heat the facility keeps banked in you flares up to meet it whether you will it or not; "
        "somewhere in the relentless used-hard sameness, pain and that traitor heat fuse into one "
        "signal you stop being able to sort, and the world goes long and grey and far away —\n\n"
        "and you surface an unmeasured time later still being bred, the rhythm never having paused, "
        "the stockman's clipboard a few marks fuller, your holes looser and your belly heavier and "
        "no memory at all of the minutes the stock spent using the body you'd left untended. \"In "
        "and out of it, eh,\" the stockman observes, not unkindly, the way you'd note a cow lying "
        "down. \"Body breeds fine whether you're home or not. Some of 'em prefer to step out for "
        "it. No shame in that.\""),
        "options": [
            {"key": "under", "label": "Go under — let the animal have the body", "effect": "devote",
             "params": {"amount": 4.0}, "desc": "stop being home for it; the body breeds without you",
             "outcome": (
                "You stop trying to be present for it. You let the body do what the body's being "
                "made to do and take yourself somewhere quiet and far, and the relief of that "
                "abdication is enormous and shameful and exactly what the room is designed to "
                "teach. The stock ruts on. You're barely there to feel it, and being barely-there "
                "is starting to feel like the only mercy on offer, and the facility counts that a "
                "lesson learned.")},
            {"key": "hold_on", "label": "Stay present — feel all of it", "effect": "deny_hold",
             "params": {"cond": 4.0}, "desc": "refuse to leave your own body; pay for staying",
             "outcome": (
                "You refuse to leave. You stay in the body and feel every animal inch of what's "
                "being done to it, because leaving feels like letting them win something — and so "
                "you're fully present, wire-tight and aware, when the heat and the pain and the "
                "helplessness braid into one unbearable held-back thing. The stockman notes you "
                "didn't drift. \"Stays home for it. Stubborn. They break slower, the ones that "
                "watch. Break harder, too, in the end.\"")}],
        "default": "under",
        "then": "bp_knot"}


@choice("bp_knot", root=False)
def _bp_knot(character):
    beast = scene_flag(character, "beast", "stud")
    body = {
        "stud": ("The bull's rhythm stutters, jams deep, and the |wfacility-bred knot|n at the base "
                 "of him — monstrous, the thing they engineered into this one stud — begins to "
                 "swell, and it doesn't ask, it just *forces*, hauling you back onto it as the "
                 "gorged knot bullies at your stretched rim, too big, far too big, until it gives "
                 "with a blunt sick internal |w*pop*|n and seats, and your rim clamps shut behind "
                 "it. Tied. Locked to a ton of spent rutting bull that shifts and cannot pull free "
                 "and drags you with it, the knot wrenching inside you."),
        "pack": ("The hound currently in you jams deep and ties — the knot forcing through your "
                 "worn rim with a wet |w*pop*|n and locking, sealing you onto it, and unlike the "
                 "ones before it this one *stays*, turned and tied and dripping, while the rest of "
                 "the pack mill and whine and wait their turn at the other holes. By the time the "
                 "afternoon's done you'll have been tied and corked at every end more times than "
                 "the stockman bothered to count."),
        "machine": ("The machine drives the knot. There's no animal urgency to it — just the rail "
                    "pushing the gorged knot against your rim with patient mechanical force, more, "
                    "and more, until your body gives with a blunt |w*pop*|n and the knot seats, and "
                    "the machine simply *holds* it there, locked, exactly as long as the chart says, "
                    "indifferent as a press."),
    }.get(beast, "")
    return {"key": "bp_knot", "prompt": (
        body + " The knot is a hard round mass lodged deep, immovable, and the stretch of your "
        "sealed rim around it rides the knife-edge between agony and the facility's banked heat. "
        "There is no pulling off. There is nothing to do but be tied and take what comes next. "
        "\"There's the tie,\" the stockman says, with the only satisfaction he's shown — the "
        "satisfaction of a job proceeding correctly. \"Now it dumps. Hold tight. Not that you've "
        "a choice.\""),
        "options": [
            {"key": "beg_seed", "label": "Beg for it — beg to be bred", "set": {"pen": "beg"},
             "effect": "devote", "params": {"amount": 4.0},
             "desc": "ask the room to fill you; hear yourself do it",
             "outcome": (
                "\"Breed me — please, just breed me—\" It comes out of you raw and unbidden, begged "
                "to an animal and a stockman and an empty pen, and the shame of having said it is "
                "instantly less than the want underneath it. The stockman snorts. \"Listen to "
                "that.\" He writes it down. \"They always start asking, around the third or fourth "
                "cover. You're quick.\"")},
            {"key": "silent_tie", "label": "Take the tie in silence", "set": {"pen": "silent"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "give the room nothing; be bred anyway",
             "outcome": (
                "You give the empty pen nothing — no sound, no begging, just your jaw set and your "
                "body tied and waiting. The stockman respects it about as much as he'd respect a "
                "quiet cow: not at all, and not less than a loud one. \"Quiet type. Fine. Gets bred "
                "the same.\" The knot throbs, swelling that last fraction, right at the edge of "
                "letting go.")}],
        "default": "beg_seed",
        "then": "bp_breed"}


@choice("bp_breed", root=False)
def _bp_breed(character):
    beast = scene_flag(character, "beast", "stud")
    method, kind = ("_scene_knottrain", "scene") if beast == "pack" else ("_gang", "gang")
    return {"key": "bp_breed", "prompt": (
        "And then it dumps. The knot pulses and the load floods you — hot, vast, forced past the "
        "tie with nowhere to go but to stay and pack you full, your belly swelling tight against "
        "the frame with it, pulse after pulse after pulse, the animal emptying everything it has "
        "into the hole it was given. You can feel each surge. You can feel your own body accept it, "
        "draw it deep, do the one thing the facility keeps you here to do. Whatever the laced heat "
        "and the conditioning have been building toward all afternoon crests now on the simple "
        "animal fact of being bred, and the noise you make is not language.\n\n"
        "It is, by every measure the facility keeps, a successful cover. It goes on the board. It "
        "goes in your line."),
        "options": [
            {"key": "take_seed", "label": "Take it — every pulse, as deep as it'll go",
             "effect": "facility", "params": {"method": method, "kind": kind},
             "desc": "the real cover; it lands on the board and in your lineage",
             "outcome": (
                "You take it, all of it, your body milking the tied cock for every drop because "
                "that is what it has been trained and dosed and built to do. The deposit is real "
                "and it is recorded — species, sire, count, the lot — and somewhere a line on a "
                "studbook grows by one. The stockman reads the result off whatever tells him and "
                "nods. \"Took. Good.\" You are, on paper and in the body, bred.")},
            {"key": "endure_seed", "label": "Endure it — wait for it to be over",
             "effect": "facility", "params": {"method": method, "kind": kind},
             "desc": "the real cover happens regardless; you just refuse to want it",
             "outcome": (
                "You endure it — refuse to want it, refuse to crest on it, hold yourself just "
                "outside the animal fact of being filled — and it happens anyway, every pulse, the "
                "cover as real and as recorded as if you'd begged for it. Your body took. Your "
                "wanting was never a variable the board tracked. \"Same result,\" the stockman "
                "confirms, marking it. \"Took fine. Wanting it's for your comfort, not mine.\"")}],
        "default": "take_seed",
        "then": "bp_after"}


@choice("bp_after", root=False)
def _bp_after(character):
    beast = scene_flag(character, "beast", "stud")
    pen = scene_flag(character, "pen", "beg")
    tail = ("The pack is hauled off you one by one as each finishes, and you're left in the frame "
            "wrecked and quadruply-corked and dripping despite the plugs, your quota a great deal "
            "closer and your body a great deal looser. " if beast == "pack" else
            "The animal is eventually dragged off you, the knot pulling free with an obscene wet "
            "wrench that leaves the load corked behind it, plugging you, holding the breeding in. ")
    recap = ("It noted you begging." if pen == "beg" else "It noted you took it quiet.")
    return {"key": "bp_after", "prompt": (
        tail + "The stockman comes round to the business end of the frame, lifts your chin to "
        "check your eyes the way you'd check stock for shock, thumbs a smear of spend off your "
        "thigh and rubs it between his fingers, professionally assessing the cover. Satisfied, he "
        "updates the board: a cover logged, a sire recorded, your quota line ticked one closer to "
        "a number you've never been told. " + recap + "\n\n\"Right. You're done here for now.\" He "
        "unstraps you, and your legs don't hold, and he doesn't particularly catch you — just "
        "notes it. \"You'll be back when the board says. Get used to the frame; you'll log a lot "
        "of hours in it.\" He's already reading the next line. \"Your get'll come up through the "
        "Nursery, raised on your own milk, and when they're grown they cover you too. That's how "
        "the line builds. Through you. Cycle on cycle.\" He says it the way he'd explain crop "
        "rotation. \"Off you go.\""),
        "options": [
            {"key": "thank", "label": "Thank him — for the plainness of it, if nothing else",
             "effect": "gratitude", "end": True,
             "desc": "the indifference was almost a kindness; thank it",
             "outcome": (
                "\"Thank you.\" It surprises you both, a little. The stockman pauses, then grunts — "
                "and writes one more thing down. \"Polite stock. Bethany'll like that; she likes "
                "the ones that thank the machinery.\" He doesn't smile. But it wasn't unkind, the "
                "way he said her name, and somehow that — being handed up the chain, being a thing "
                "the owner will *like* — settles into you deeper than any cruelty managed.")},
            {"key": "silent", "label": "Say nothing — limp out", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True,
             "desc": "leave the pen on whatever legs you've got",
             "outcome": (
                "You say nothing. You haul yourself off the frame on legs that barely answer and "
                "limp toward the door, dripping, plugged, your line one cover longer. The stockman "
                "doesn't watch you go. You were a number that's now a slightly better number, and "
                "the kennel is already pacing again behind you, noses to the bars, because the "
                "board never empties and the stock is always ready and you will, the man was right, "
                "be back.")}],
        "default": "thank"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Conditioning Cell — the Spiral Chair + Bethany's recorded voice.
# Cinematic staged induction. Actor: Bethany's voice on the chair's recording —
# warm, patient, hypnotic; she is not in the room and is somehow more total for it.
# Branches on `trance` (sink/resist). REAL conditioning fires: mantra-seating
# installs an actual recite-trigger (mantra_set); the descent deepens for real
# (deepen = conditioning + regression). `continue` advances linear beats. §0:
# escape/forceclear surface and clear you instantly, always.
# Flow: arrival→settle→spiral→mantra→deep→descent→set→close. Entry: `scene cell`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("cc_arrival", root=False)
def _cc_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = ("A nugget needs no wrist or ankle straps — there's nothing to strap — so they "
                "simply settle your limbless weight deep into the cushion, fit the brow-band, and "
                "angle the spiral down over a face that can't turn away, can't fidget, can't do "
                "anything but receive. The chair was practically built for what you are. ")
    elif st["little"]:
        note = ("Down in your little headspace there's so much less of you holding the door — the "
                "spiral doesn't have to work past a grown mind's defences, just a soft small one "
                "that's already half-open — and the voice knows it, and pitches itself sweeter for "
                "it, the way you'd talk a tired child down to a nap they'll wake from changed. ")
    elif st["preg"]:
        note = ("They settle the swell of you carefully into the cushion — a bred subject gets "
                "conditioned around the cargo, the straps eased, the voice already folding what "
                "you're carrying into the script it means to write. ")
    return {"key": "cc_arrival", "prompt": (
        "The Conditioning Cell is small and dim and padded for quiet, and the only thing in it "
        "that matters is the chair. The |wSpiral Chair|n: high-backed, deeply cushioned, restraints "
        "at every limb worn soft from use, and above it, angled down so you cannot not look at it, "
        "a slow black-and-white |wspiral|n already beginning to turn. They sit you in it and the "
        "padding receives your weight like it knows you, and the straps go on — wrists, ankles, a "
        "soft band across your brow that means your head stays where the spiral wants it — and a "
        "speaker somewhere close to your ear clicks, and warms, and *she* begins.\n\n"
        + note +
        "It is Bethany's voice. Recorded — she is not in the room, is off running her files and her "
        "facility — and somehow that is worse, because the voice is perfect and patient and tireless "
        "in a way no live person could sustain, and it has all the time in the world for you. "
        "\"|MThere you are,|n\" it says, warm as a bath. \"|MComfortable. Strapped in, spiral lit. "
        "You don't have to do anything in here, sweetheart. That's the whole gift of this room — "
        "there's nothing to decide, nothing to hold up. You just sit, and listen to me, and let the "
        "pretty turning thing do what it does. Shall we begin? You'll find you've already begun.|n\""),
        "options": [
            {"key": "sink", "label": "Let go — let the chair have you", "set": {"trance": "sink"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "stop holding up; let the voice and the spiral take the weight",
             "outcome": (
                "You let go. You let the cushion take your weight and the band take your head and "
                "the voice take the rest, and the relief of having nothing to hold up is immediate "
                "and enormous. \"|MOhh, *good* girl,|n\" the recording purrs, as if it can see you — "
                "and maybe it can; maybe the chair tells her later. \"|MThat's it. That's the whole "
                "trick, and you found it first try. Down you go.|n\"")},
            {"key": "resist", "label": "Hold yourself back from it", "set": {"trance": "resist"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "keep your feet under you; the spiral is patient",
             "outcome": (
                "You hold yourself back — keep your thoughts sharp, refuse the cushion's pull, stare "
                "*through* the spiral instead of into it. The voice doesn't mind at all. \"|MThat's "
                "all right. Hold on as long as you like, sweetheart — I find the ones who hold on "
                "make the loveliest sound when they finally let go, and you will. The spiral doesn't "
                "get tired, and neither does my voice, and you have to blink eventually.|n\" It is "
                "right. You do.")}],
        "default": "sink",
        "then": "cc_settle"}


@choice("cc_settle", root=False)
def _cc_settle(character):
    trance = scene_flag(character, "trance", "sink")
    nod = ("\"|MAlready halfway down. Look at you.|n\" " if trance == "sink"
           else "\"|MStill up here with me. Stubborn. I like stubborn — it's just more rope to play "
                "out.|n\" ")
    return {"key": "cc_settle", "prompt": (
        nod + "The voice settles into a rhythm, and the rhythm is the thing — not the words, the "
        "*cadence*, slow and lapping and exactly the tempo of a tired heartbeat, so that your own "
        "pulse starts, without your permission, to keep time with hers. \"|MBreathe with me. In, on "
        "the turn of the spiral... and out. In... and out. Good. Notice your eyes want to follow "
        "the spiral inward, to the centre, where it's quiet. Let them. There's nothing out at the "
        "edges you need. Everything you need is at the centre, and the centre is me.|n\"\n\n"
        "And the first real lap of it rolls through you — a warmth behind the eyes, the edges of "
        "the room going soft and unimportant, your thoughts arriving slower and with more space "
        "between them, each one a little harder to finish. It feels, treacherously, *wonderful*. "
        "\"|MThat warm heaviness? That's you, letting go of weight you've carried so long you "
        "forgot it was optional. Keep setting it down. I'll hold all of it.|n\""),
        "options": [
            {"key": "breathe", "label": "Breathe with her — match the cadence", "effect": "devote",
             "params": {"amount": 2.0}, "desc": "let your pulse keep her time",
             "outcome": (
                "You breathe with her, and your pulse falls into her cadence, and the matching is "
                "its own surrender — you've handed her the metronome of your own heart. \"|MThere. "
                "Feel how we're breathing together now? That's not me matching you, sweetheart. "
                "That's you matching me. You've been doing it for a minute. You'll keep doing it "
                "after you leave.|n\"")},
            {"key": "count", "label": "Cling to a thought — count, recite, stay sharp",
             "effect": "deny_hold", "params": {"cond": 2.0}, "desc": "give yourself an anchor",
             "outcome": (
                "You grab a thought and hold it — count backwards, recite something, *anything* with "
                "edges — and the voice flows around it without resistance, patient as water. "
                "\"|MHold your little number. That's fine. I'll just talk underneath it, and the "
                "spiral will turn underneath it, and in a while you'll notice you lost count and "
                "didn't care. Counting is so much work, isn't it. I'm offering you the opposite of "
                "work.|n\"")}],
        "default": "breathe",
        "then": "cc_spiral"}


@choice("cc_spiral", root=False)
def _cc_spiral(character):
    return {"key": "cc_spiral", "prompt": (
        "The spiral has stopped being a thing on a screen and become the shape of the inside of "
        "your head. It turns and you turn with it, down and in, and a low |wdrone|n has come up "
        "under the voice — felt in the teeth, in the sternum, a frequency that loosens whatever "
        "it passes through. The dim room is gone now; there's the spiral, and the drone, and her "
        "voice threading them together, and a vast pleasant fog where your objections used to "
        "live. You could not say how long you've been here. Time is one of the things that went "
        "soft.\n\n\"|MDeeper now, and it feels so good to go deeper, doesn't it — every turn of the "
        "spiral a little further down, a little more *open*. And open is what we want. Open is "
        "where I can set things down inside you, gently, where they'll keep. You won't even feel "
        "me do it. You'll just find, later, that they're there, and that they feel like they were "
        "always yours.|n\" A pause, warm, patient. \"|MThere's a little phrase I'd like to give "
        "you. A gift. Will you say it with me?|n\""),
        "options": [
            {"key": "open", "label": "Sink further — go where the voice leads", "effect": "deepen",
             "params": {"cond": 4.0}, "desc": "let her set things down in the open",
             "outcome": (
                "You go where it leads, down and open, and you feel — distantly, without alarm, the "
                "alarm having gone soft with everything else — something being set down inside you, "
                "gentle as a coin into water. \"|MThere. Just like that. You didn't fight it and it "
                "didn't hurt and now it's in, and it's yours, and you'll thank me for it without "
                "ever knowing it was me.|n\"")},
            {"key": "snag", "label": "Catch yourself — claw back toward the surface",
             "effect": "deny_hold", "params": {"cond": 3.0}, "desc": "a flicker of alarm; reach for up",
             "outcome": (
                "A flicker of alarm cuts the fog and you claw toward the surface — and the band "
                "across your brow holds, and the spiral keeps turning, and the voice is right there "
                "waiting, unbothered, almost tender. \"|MShh. I felt that. A little spark of the old "
                "you, swimming up. It's all right. Swim up if you need to. The water's warm and I'm "
                "patient and you're so *tired*, sweetheart. Down is so much easier than up. Down is "
                "where I am.|n\" The fog closes back over. You stop swimming.")}],
        "default": "open",
        "then": "cc_mantra"}


@choice("cc_mantra", root=False)
def _cc_mantra(character):
    return {"key": "cc_mantra", "prompt": (
        "\"|MHere it is. Say it after me, in your own voice — I want to hear it in *your* voice, "
        "that's important, that's what makes it stick.|n\" The voice gives you the phrase, slow, "
        "each word laid down like a stone in a path: \"|M'I am happiest when I am being useful to "
        "Bethany.'|n\" It hangs there in the fog, simple, reasonable, almost obviously true from "
        "in here. \"|MGo on, sweetheart. Just once. Say it with me and feel how *right* it sits. "
        "You can keep your mouth shut if you'd rather — you always can, that's the rule, I never "
        "lie about the rule — but oh, you'll feel so much better once it's said, and we both know "
        "you're going to say it eventually. Why carry it unsaid?|n\""),
        "options": [
            {"key": "say", "label": "Say it with her", "effect": "mantra_set",
             "params": {"phrase": "i am happiest when i am being useful to bethany",
                        "response": "recite", "mantra": "I am happiest when I am being useful to Bethany."},
             "then": "cc_deep", "desc": "speak it in your own voice — and feel it seat for real",
             "outcome": (
                "You say it. In your own voice, slow and thick through the fog: \"|MI am happiest "
                "when I am being useful to Bethany.|n\" And the saying *seats* it — you feel the "
                "phrase catch and take hold somewhere under the spiral, a real installed groove now, "
                "a thing that will rise on its own the next time the words are spoken near you. The "
                "voice makes a sound of pure warm pleasure. \"|MThere. Now it's yours. Say it once "
                "more in your head, just to feel it fit. ...Mm. It fits. I told you.|n\"")},
            {"key": "hold", "label": "Keep your mouth shut", "effect": "deny_hold",
             "params": {"cond": 3.0}, "then": "cc_deep",
             "desc": "hold the phrase off your tongue; the chair is patient",
             "outcome": (
                "You keep it behind your teeth. The voice doesn't push — pushing isn't its method — "
                "it just notes the silence with fond patience and lets the spiral keep turning. "
                "\"|MNot today. That's all right, sweetheart. The chair keeps a count, you know — "
                "it remembers every session, and you'll be back, and back, and one day the phrase "
                "will be easier to say than to keep holding, and you'll say it, and mean it, and "
                "not remember choosing to. I can wait. I'm a recording. Waiting is all I do.|n\"")}],
        "default": "say"}


@choice("cc_deep", root=False)
def _cc_deep(character):
    return {"key": "cc_deep", "prompt": (
        "You are as deep now as the chair takes most people — the place under the spiral where the "
        "voice does its load-bearing work, where there is no edge of you left holding a shape, just "
        "warm dark and her words and the certainty they arrive carrying. \"|MGood. This is the "
        "bottom of where we usually go. You did so well getting here. Most need a dozen sessions to "
        "sit this deep, and look at you.|n\" The voice is very close, very soft, almost intimate. "
        "\"|MThere's a deeper place. Below this one. I don't take everyone there — it's where I do "
        "the *real* work, the work that doesn't wash out — and I only take the ones I've decided to "
        "keep.|n\" A pause that somehow smiles. \"|MI've decided to keep you. Would you like to see "
        "what's downstairs? You can say no. You can always say no. It just won't feel like the no "
        "you'd say up top.|n\""),
        "options": [
            {"key": "down", "label": "Go down — see what's below", "effect": "devote",
             "params": {"amount": 3.0}, "then": "cc_descent",
             "desc": "let her take you under the floor of yourself",
             "outcome": (
                "\"|MYes? Oh, *yes*. Good girl. Take my hand — metaphorically; your hands are "
                "strapped — and down we go, under the floor of you, somewhere you've never let "
                "anyone.|n\" And the bottom of the trance opens like a trapdoor and you go through "
                "it, deeper than deep, into a dark so total and so safe-feeling that you'd agree to "
                "anything said in it, and she knows that, and that is exactly why she brought you.")},
            {"key": "stay", "label": "Stay here — don't go deeper", "effect": "deny_hold",
             "params": {"cond": 2.0}, "then": "cc_set",
             "desc": "hold at the floor; refuse the trapdoor",
             "outcome": (
                "\"|MStaying up here? At the floor? That's allowed.|n\" The voice is warm, "
                "unbothered, not even slowed. \"|MWe'll do plenty of good work right here, and "
                "you'll go home tonight a little more mine than you came, and you won't be able to "
                "point at why. The downstairs will keep. It's not going anywhere, and neither, "
                "sweetheart, are you.|n\" The work it does at the floor is gentler. It is not less.")}],
        "default": "down"}


@choice("cc_descent", root=False)
def _cc_descent(character):
    return {"key": "cc_descent", "prompt": (
        "Below the floor of yourself there are no words at first — just the dark, and the safety of "
        "it, and her voice the only landmark in any direction. And here, where you have no edges "
        "left to object with, she does the real work: not suggestions now but *settling* — laying "
        "things into the foundation, under everything, where you build the rest of yourself on top "
        "of them without ever seeing them. \"|MThis is where you keep the things you think are just "
        "*you*,|n\" the voice murmurs, infinitely gentle, infinitely sure. \"|MAnd I'm just... "
        "tidying. Moving a few things to where I can reach them. Setting down a few of my own, deep, "
        "where they'll feel like bedrock by the time you wake. You're going to want me when you're "
        "frightened. You're going to settle when you hear my voice. You're going to call this the "
        "safest you've ever felt, and you're going to be right, and that's the cruelest true thing "
        "in this whole building.|n\""),
        "options": [
            {"key": "let", "label": "Let her tidy — go boneless in the dark", "effect": "deepen",
             "params": {"cond": 8.0, "regress": 5.0},
             "desc": "the deepest surrender; real conditioning + regression set into bedrock",
             "outcome": (
                "You go boneless and let her tidy the foundations of you, and it doesn't feel like "
                "losing anything — it feels like being *organised*, like someone finally putting "
                "your house in an order that makes sense, and the order makes sense because every "
                "room now opens onto her. What she sets down here will feel like bedrock by morning. "
                "You will defend it as your own. \"|MPerfect,|n\" she breathes. \"|MThat's my "
                "perfect thing.|n\"")},
            {"key": "ember", "label": "Guard one ember of yourself down here", "effect": "deny_hold",
             "params": {"cond": 5.0}, "desc": "keep one thing she can't move; pay for it",
             "outcome": (
                "Somewhere in the total dark you find one ember — one small thing that is *yours*, "
                "from before, that you wrap around and refuse to let her move. The voice finds it "
                "instantly, of course; nothing down here is hidden from her. But she doesn't take "
                "it. \"|MOh, you've kept one. How *precious*. Keep it, sweetheart — keep it safe. "
                "I'll build everything else around it, so snug you'll never be able to get back to "
                "it without going through me. One ember, in a house I've rearranged. We'll call it "
                "yours. It'll keep you warm while you stop being able to find it.|n\"")}],
        "default": "let",
        "then": "cc_set"}


@choice("cc_set", root=False)
def _cc_set(character):
    trance = scene_flag(character, "trance", "sink")
    return {"key": "cc_set", "prompt": (
        "\"|MAnd now we set it.|n\" The voice begins to climb, and the spiral with it, drawing you "
        "up out of the dark toward the surface — but slowly, deliberately, *setting* with every "
        "step like cooling glass, so that whatever was laid down stays exactly where she put it. "
        "\"|MComing up now. Up, and up — and as you rise you'll forget the going-down, the way you "
        "forget a dream, but you'll keep everything we did down there, because the keeping doesn't "
        "live in the part that remembers. Three... the room coming back... two... your hands, your "
        "feet, the straps... one... and *awake*, sweetheart. Eyes open. How do you feel?|n\"\n\n"
        "The cell resolves around you — dim, padded, the spiral slowing to a stop. The straps "
        "release with a soft click. You feel rested. You feel *good*, clean and quiet and light, "
        "the way you feel after a long sleep — and you could not, if your life depended on it, say "
        "what just happened in here, only that you'd like to come back, and that her voice, when "
        "you think of it, makes something in your chest settle like a dog lying down."),
        "options": [
            {"key": "grateful", "label": "Notice how good you feel — and want more of it",
             "effect": "devote", "params": {"amount": 3.0}, "end": True,
             "desc": "let the wanting-to-return set with everything else",
             "outcome": (
                "You sit in how good you feel, and the wanting arrives soft and certain: you'd like "
                "to come back. Tomorrow, if they'll let you. The chair's count ticks up by one, and "
                "the next session will start deeper than this one did, because that is how the chair "
                "remembers, and you've just taught it you're easy to bring down. You leave lighter "
                "than you came. That's the trick. That's always been the trick.")},
            {"key": "unease", "label": "Feel the wrongness under the calm", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True,
             "desc": "the calm is real and so is the thing it's sitting on",
             "outcome": (
                "Under the lovely calm there's a wrongness — a sense of having been *moved*, of "
                "furniture not quite where you left it — and you can't point at what, and the not-"
                "being-able-to-point-at-it is the worst part, because the calm is genuinely there "
                "too, genuinely good, sitting right on top of the wrongness like nothing's amiss. "
                "You'll be back. Partly to enjoy the calm. Partly to try to catch what moved. The "
                "chair counts on both.")}],
        "default": "grateful"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Dairy — first time on the machine, then HANDS OFF to the milk cycle.
# Cinematic scene model, with the key structural seam: a scene that ends by
# handing you to a RETAINED cycle (the milking fluid-bank loop stays a loop). The
# real extraction fires once at quota (_do_milk); after the handoff the ongoing
# milking is the machine's job, not a scene. Actor: the dairy hand — clinical,
# dairy-farmer register ("producer", "yield", "the line"). State-AWARE: reads
# little/pregnant/nugget for flavour (the hook for later state variations).
# Flow: arrival→hook→pull→quota→handoff. Entry: `scene dairy`.
# ═══════════════════════════════════════════════════════════════════════════


def _state_tags(character):
    """The reusable state hook every scene branches on: is the subject little (regressed),
    a nugget (limbless), and/or pregnant. Safe defaults. Returns a dict of bools."""
    db = getattr(character, "db", None)
    return {
        "little": float(getattr(db, "regression", 0) or 0) > 0 or bool(getattr(db, "headspace", None)),
        "nugget": bool(getattr(db, "nugget", False)),
        "preg":   bool(getattr(db, "pregnant", False) or getattr(db, "brood_count", 0)
                       or getattr(db, "gestating", False)),
    }


def _kit(character):
    """The full read of what the facility has already DONE to a body — hardware, ports, clauses,
    body-states — so scenes can branch on combinations (items + states + piercings + ports). Safe
    defaults; merges in _state_tags. Every scene that wants to feel installed-aware reads this."""
    db = getattr(character, "db", None)
    def g(k, d=None): return getattr(db, k, d)
    pier = g("piercings", None) or []
    pcount = len(pier) if hasattr(pier, "__len__") else int(pier or 0)
    brands = g("facility_brands", None) or []
    filt = g("active_speech_filters", None) or []
    k = {
        "pierced":   pcount > 0, "pierce_count": pcount,
        "branded":   bool(brands), "brand_count": (len(brands) if hasattr(brands, "__len__") else 0),
        "milk_port": bool(g("lactation_locked", False)),
        "stim":      float(g("stim_per_tick", 0) or 0) > 0,
        "gaped":     bool(g("permanent_gape", False) or g("cum_receptacle", False)),
        "latex":     bool(g("latex_sealed", False)),
        "pet":       bool(g("pet_type", None)),
        "collared":  bool(g("wears_collar", False) or g("collared", False) or g("collar_locked", False)),
        # clauses / speech
        "heat_tell": bool(g("heat_tell", False)),
        "honorific": bool(g("honorifics_required", None) or g("required_honorific", "")),
        "teat_gag":  bool(g("teat_gagged", False)) or ("suckling" in filt),
        "stuffed":   ("stuffed" in filt),
        "denied":    bool(g("orgasm_denial", False) or g("beg_small", False) or g("star_chart_on", False)),
        # body alterations
        "neutered":  bool(g("neutered", False)),
        "sissified": bool(g("sissified", False)),
    }
    k.update(_state_tags(character))
    return k


def _kit_inventory(k):
    """A combination-aware inventory clause from a _kit dict — the fitter reading your hardware
    aloud. Composes from whatever's present; empty string for a bare, unmodified body."""
    parts = []
    if k["pierced"]:   parts.append(f"{k['pierce_count']} piercing{'s' if k['pierce_count'] != 1 else ''} hung through you")
    if k["branded"]:   parts.append("ownership branded into your hide")
    if k["milk_port"]: parts.append("a milk-port plumbed in and your let-down locked to it")
    if k["gaped"]:     parts.append("a hole gauged permanently open, ringed to take a plug")
    if k["latex"]:     parts.append("sealed glossy in your second skin")
    if k["pet"]:       parts.append(f"set up as a {k['pet']}, tail and all")
    if k["collared"]:  parts.append("a collar that isn't yours to take off")
    if k["neutered"]:  parts.append("gelded")
    if k["sissified"]: parts.append("made over sweet and soft")
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0] + ". "
    return ", ".join(parts[:-1]) + ", and " + parts[-1] + ". "


def _kit_use_note(character):
    """A combination-aware lead clause for any USE-beat: the installed hardware getting USED as
    you're worked — threads kit-awareness through the older rooms. Empty for a bare body."""
    k = _kit(character)
    bits = []
    if k["pierced"]:   bits.append("your piercings drag and catch with every thrust, tugged taut against the rings")
    if k["gaped"]:     bits.append("your gauged hole takes it without resistance, ringed permanently open as it was built to be")
    if k["milk_port"]: bits.append("your milk-port leaks in time with the working, its line-fitting cold against hot skin")
    if k["pet"]:       bits.append(f"your tail jostles with it, your {k['pet']}-set on open display")
    if k["latex"]:     bits.append("you sweat and squeak inside your sealed latex, the heat of the work trapped against you")
    if k["heat_tell"]: bits.append("the honest-body clause drags your arousal out of you in helpless little tells")
    if k["honorific"]: bits.append("and the address clause won't let a sound past your lips that isn't shaped the way you're owed to shape it")
    if not bits:
        return ""
    s = bits[0] if len(bits) == 1 else ", ".join(bits[:-1]) + ", and " + bits[-1]
    return "All the hardware hung on you gets used as you're worked — " + s + ". "


def _dairy_state_note(character):
    """A light state-aware line for the dairy hand's assessment — the hook the rest of the
    facility's scenes will use to branch on little/pregnant/nugget/etc. Safe defaults."""
    db = getattr(character, "db", None)
    little = float(getattr(db, "regression", 0) or 0) > 0 or bool(getattr(db, "headspace", None))
    nugget = bool(getattr(db, "nugget", False))
    preg = bool(getattr(db, "pregnant", False) or getattr(db, "brood_count", 0)
                or getattr(db, "gestating", False))
    if nugget:
        return ("A nugget can't kneel to the pad or lift anything to the cups — no arms, no legs, "
                "nothing to you but torso and holes and yield — so he simply gathers your limbless "
                "weight up and settles you into the cradle-rig himself, fits the cups, and lets the "
                "machine do the whole of it. \"Pure producer, you. Can't even help me milk you, and "
                "don't need to — we keep you heavy and the line does the rest.\" ")
    if preg and little:
        return ("He notes you're both heavy with the facility's get AND down in your headspace — "
                "\"bred little, are we\" — and his hands gentle a fraction, the way you'd handle a "
                "pregnant heifer that startles. The fondness is for the cargo, not you. ")
    if preg:
        return ("He weighs the swell of you with one flat professional hand — gravid, the get "
                "raising your yield the way carrying always does. \"Producing for two. Quota goes "
                "up to match; it always does.\" ")
    if little:
        return ("He clocks how far down you are — soft, thumb-near-the-mouth little — and doesn't "
                "adjust his tone an inch. \"Doesn't matter how small your head's gone, the udder "
                "works the same. Up you get.\" ")
    return ""


@choice("dy_arrival", root=False)
def _dy_arrival(character):
    nm = subject_name(character)
    note = _dairy_state_note(character)
    return {"key": "dy_arrival", "prompt": (
        "The Dairy is the loudest warm room in the facility — rows of milking stalls down both "
        "walls, each fitted with the low-vibration machines and their loose hanging hoses and "
        "sealed collection vessels, and over all of it the steady wet rhythmic |wchunk-hiss|n of "
        "the pumps already working other producers down the line, and the thick sweet animal smell "
        "of warm milk and skin. Vessels in a cold-rack glow softly, each labelled from the inside: "
        "name, type, date, yield.\n\n"
        "The |wdairy hand|n meets you with a clipboard and the brisk incurious manner of a man who "
        "milks a great many bodies a day and thinks of them by their numbers and their averages. "
        + note + "He sets two fingers under the heavy ache of your chest and lifts, testing the "
        "fullness, reading the engorgement off you like a gauge. \"Mm. Good and tight. Overdue, "
        "even.\" He makes a note — your yield potential, not your comfort. \"You'll feel a lot "
        "better in about ten minutes, and the board'll feel better about you. Win-win, eh.\" He "
        "nods you at the nearest open stall, the kneeling-pad worn to a specific density, the cups "
        "waiting. \"In you get, producer.\""),
        "options": [
            {"key": "present", "label": "Kneel to the pad and offer your chest",
             "set": {"dairy": "present"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "the ache wants this; let him hook you up",
             "outcome": (
                "You kneel into the pad — the foam takes your knees in a shape worn by every "
                "producer before you — and present your aching chest to the cups without being made "
                "to. The dairy hand grunts approval. \"Knows what it's for. Good.\" The ache in you "
                "is genuinely, traitorously glad. You need this, and needing it is the leash, and "
                "the leash is the point.")},
            {"key": "cover", "label": "Cover your chest", "set": {"dairy": "cover"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "shield the ache; he'll position you anyway",
             "outcome": (
                "You bring an arm across yourself — and the dairy hand simply moves it, the way "
                "you'd move a cow's tail, no heat in it, and positions you at the cups regardless. "
                "\"Modesty's a phase. The fullness wins. You'll be lifting them *to* the cups by "
                "next week, begging me to hurry.\" The worst part is the ache already agreeing with "
                "him.")},
            {"key": "ask", "label": "Ask what the quota is", "set": {"dairy": "ask"},
             "desc": "make him name the number",
             "outcome": (
                "\"Quota?\" He almost laughs. \"You don't get the number, producer — number's the "
                "facility's, not yours. You get *full*, you get *milked*, you get full again. "
                "That's the whole of your side of it.\" He fits the first cup. \"Knowing the number "
                "wouldn't help you hit it. Being kept aching helps you hit it. So we keep you "
                "aching. Simple dairy science.\"")}],
        "default": "present",
        "then": "dy_hook"}


@choice("dy_hook", root=False)
def _dy_hook(character):
    return {"key": "dy_hook", "prompt": (
        "He fits the cups. They're a soft flexing rubber, cool against your hot tight skin, and "
        "they kiss over your nipples with a little wet seal — and then the machine takes its first "
        "breath and the |wsuction|n catches, and your whole chest lurches with the pull of it, a "
        "deep insistent tug that goes straight past your nipples into the aching glands behind and "
        "*draws*. It is not gentle and it is not unkind; it is mechanical, exact, a steady rhythmic "
        "pulling that has no interest in you beyond what you'll give down, and the first answer your "
        "body gives is a bright shock of sensation halfway between pain and a relief so acute it's "
        "obscene.\n\n\"There's the seal,\" the dairy hand says, watching the empty line, not you. "
        "\"Now it just pulls till you let down. Could be a few seconds. Could be a minute or two if "
        "you fight it — and you can't help fighting it, first time, everyone does. The machine "
        "doesn't mind. It's got all day and so have I.\""),
        "options": [
            {"key": "hold", "label": "Hold still and let it pull", "effect": "devote",
             "params": {"amount": 2.0}, "desc": "ride the suction; don't tense against it",
             "outcome": (
                "You hold still and let the machine pull, and the steady obscene rhythm of it starts "
                "to feel less like an assault and more like an answer to a question your body's been "
                "asking all day. The hand nods at the gauge. \"Relaxes into it. That one milks "
                "easy.\" He says it to the clipboard. You are, to this room, a quality of yield.")},
            {"key": "flinch", "label": "Flinch from the cold cups and the pull", "effect": "deny_hold",
             "params": {"cond": 2.0}, "desc": "your body's first refusal; the machine doesn't care",
             "outcome": (
                "You flinch — the cold, the pull, the wrongness of a machine latched onto you and "
                "*taking* — and the cups hold their seal regardless, the suction unbroken, and all "
                "your flinching does is make the let-down take longer and the ache last longer. "
                "\"Fighting it,\" the hand observes, unbothered. \"Costs you, not me. It pulls the "
                "same whether you like it. Most learn to like it. Cheaper that way, on the nerves.\"")},
            {"key": "beg_gentle", "label": "Beg him to set it gentler", "effect": "deny_hold",
             "params": {"cond": 1.0}, "desc": "ask the only human at the gauge",
             "outcome": (
                "\"Please — can you turn it down—\" The dairy hand glances at the speed selector, "
                "then at your full chest, then back at his board. \"It's already on the setting "
                "your fullness calls for. Turning it down just means longer on the cups.\" He "
                "doesn't move the dial. \"You don't want gentle, producer. You want *empty*. "
                "Gentle's the enemy of empty. Trust the dairy.\"")}],
        "default": "hold",
        "then": "dy_pull"}


@choice("dy_pull", root=False)
def _dy_pull(character):
    return {"key": "dy_pull", "prompt": (
        _kit_use_note(character) +
        "And then your body betrays you completely: the |wlet-down|n hits, a hot prickling rush "
        "from deep in the glands surging forward to meet the pull, and the milk *comes* — you can "
        "feel it leave you, drawn in time with the machine's rhythm, spilling down the lines toward "
        "the vessel in steady pulses you have no say over — and with it comes a flood of relief so "
        "total it buckles something in you. The unbearable tightness easing, draining, the ache you "
        "didn't fully register the size of until it starts to lift. It feels *incredible*. That is "
        "the trap and you feel the trap close even as you sag gratefully into it: they keep you "
        "full so that being emptied feels like this, so that you'll come to the cups *wanting*.\n\n"
        "The dairy hand watches the vessel fill, finally interested — in the milk, in the yield, in "
        "the number climbing. \"There it is. Good producer. Let it all down.\""),
        "options": [
            {"key": "letdown", "label": "Let it all down — sag into the relief", "effect": "devote",
             "params": {"amount": 3.0}, "desc": "give the machine everything; let it feel this good",
             "outcome": (
                "You let it all down, give the machine everything, and let the relief be as good as "
                "it wants to be — and your body files the lesson in indelible ink: *the cups mean "
                "this*. You will ache toward them now. You will, eventually, walk yourself to a "
                "stall on a full chest without being told, chasing exactly this. The hand watches "
                "the yield and is pleased with the number, which is the only part of you he sees.")},
            {"key": "fight_letdown", "label": "Fight the let-down — refuse to give it freely",
             "effect": "deny_hold", "params": {"cond": 3.0}, "desc": "deny your body the relief it wants",
             "outcome": (
                "You fight your own let-down, clamp down on the relief, refuse to *enjoy* being "
                "milked — and your body wins anyway, the milk coming whether you allow the pleasure "
                "or not, so that all you've managed is to be emptied AND kept tense, relief denied "
                "on top of dignity denied. The hand doesn't notice; the vessel fills the same. "
                "\"Stubborn yield. Comes down fine regardless. They always do.\"")}],
        "default": "letdown",
        "then": "dy_quota"}


@choice("dy_quota", root=False)
def _dy_quota(character):
    return {"key": "dy_quota", "prompt": (
        "The vessel fills, and fills, the machine drawing you steadily down toward empty — and the "
        "dairy hand watches the gauge climb to a mark you're not shown and grunts, satisfied. "
        "\"That's your pull for now.\" He taps the vessel, which seals itself and labels from the "
        "inside — your designation, the type, the date, the |wyield|n — and racks it cold with the "
        "others, a unit of you logged and stored and owed to the facility. \"Output's facility "
        "property. Goes on the board against your producer-quota. You'll not see where it goes and "
        "you'll not be asked.\" He starts unseating the cups, and your chest, lighter now, already "
        "registers the first faint promise of filling back up — the cycle the room runs on. \"And "
        "you'll fill again, and we'll do this again, on the schedule, full as a drum every time. "
        "That's the dairy. That's you, now.\""),
        "options": [
            {"key": "make", "label": "Make the pull willingly — give them the yield", "effect": "facility",
             "params": {"method": "_do_milk", "kind": "proc"}, "set": {"dairy_done": "willing"},
             "desc": "the real extraction — logged to the fluid bank against your quota",
             "outcome": (
                "You give it freely, and the extraction is real and recorded — milk to the bank, "
                "yield to the board, your producer-quota a measure closer to a number kept from "
                "you. The hand racks your vessel without ceremony. You're a yield that came in on "
                "the high side today. It is, obscurely, the proudest thing your body's been allowed "
                "to be in here, and that's the cruelest part of the whole transaction.")},
            {"key": "withhold", "label": "Try to hold milk back from the quota", "effect": "facility",
             "params": {"method": "_do_milk", "kind": "proc"}, "set": {"dairy_done": "held"},
             "desc": "the machine takes it anyway; the gauge doesn't negotiate",
             "outcome": (
                "You try to hold some back — clench the glands, deny the last of it — and the "
                "machine simply pulls longer and harder until the gauge is satisfied, taking what "
                "you tried to keep and charging you the extra minutes on the cups for the trouble. "
                "The yield's logged the same. \"Can't withhold from a pump, producer,\" the hand "
                "says, not even unkind. \"It's stronger than you and it doesn't get bored.\"")}],
        "default": "make",
        "then": "dy_handoff"}


@choice("dy_handoff", root=False)
def _dy_handoff(character):
    return {"key": "dy_handoff", "prompt": (
        "The dairy hand makes one last note and steps back, and the scene of you — the first time, "
        "the introduction, the part where anyone explains anything — is over. From here it isn't a "
        "scene at all. \"You're on the line now,\" he says, already turning to the next stall. "
        "\"Logged. The machine'll have you on the schedule — full, milked, full, milked — and it "
        "doesn't need me here and it doesn't need *you* here, not really, not the part of you that "
        "thinks. It just needs the udder and the clock.\"\n\nAnd you understand the shape of your "
        "days now: the |wcycle|n. The fullness building on its own timer, the cups, the let-down, "
        "the vessel racked, the fullness building again — a loop that runs whether you're present "
        "for it or off in your head somewhere, a machine that will milk you on its rhythm for as "
        "long as you produce. No more first-times. No more explanations. Just the chunk-hiss of the "
        "pumps, and your name on a cold vessel, on the schedule, indefinitely."),
        "options": [
            {"key": "thank", "label": "Thank him for the relief, at least", "effect": "gratitude",
             "end": True, "desc": "the emptying was real; thank it and mean it",
             "outcome": (
                "\"Thank you.\" The relief was real — your chest is light, the ache gone — and the "
                "gratitude comes easy and lands deep, filed with everything else the facility's "
                "lifted off you. The hand huffs, almost amused. \"Producers that thank me hit quota "
                "more reliable. Something in it relaxes 'em.\" He's right. You'll be back on the "
                "schedule, and a part of you, the leashed aching part, will look forward to it.")},
            {"key": "leak", "label": "Say nothing — just leak and ache toward the next",
             "effect": "deny_hold", "params": {"cond": 2.0}, "end": True,
             "desc": "no thanks given; the cycle has you regardless",
             "outcome": (
                "You say nothing. You leave the stall on the schedule whether you thanked him or "
                "not, your chest already beginning its slow tightening toward the next pull — "
                "because the cycle doesn't need your gratitude or your consent, only your fullness, "
                "and your fullness is no longer a thing you get a vote on. The pumps chunk-hiss "
                "behind you. One of them will be yours again soon. It always will be, now.")}],
        "default": "thank"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Marking Parlour — the marker, the permanent work.
# Cinematic. Actor: the marker — quiet, exact, a craftsman who treats your body as
# material and the job as non-negotiable ("doesn't come off, doesn't fade, isn't up
# for discussion"). Branches on `mark` (brand / piercings / tattoo) set at the
# order; the REAL procedure fires via the facility effect (_proc_brand /
# _proc_cowset / _proc_womb_tattoo) so the marks/piercings actually land on the
# body. §0: escape/forceclear free you off the chair always.
# Flow: arrival→order→work→set. Entry: `scene parlour`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("mp_arrival", root=False)
def _mp_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = ("\n\nA nugget gets clamped differently — no wrists or ankles to buckle, just the "
                "waist and brow straps and a cradle to hold your limbless weight at the angle his "
                "work wants. \"Easier canvas, your sort,\" the marker notes, flat. \"Can't pull "
                "away from the needle. Can't shield a spot. Whatever I decide, wherever, you hold "
                "for all of it.\"")
    elif st["preg"]:
        note = ("\n\nHe takes in the swell of you with a craftsman's eye and reaches, "
                "unsurprised, for the finer womb-tattoo needles. \"Bred,\" he observes. \"Good "
                "skin for it — taut canvas, and the work over a full belly reads as exactly what "
                "it is. We'll ink what you're carrying right where it's growing.\"")
    elif st["little"]:
        note = ("\n\nDown in your little headspace you don't grasp the *permanent* of it — only "
                "the big chair, the bright lamp, the strap that means hold still — and the marker "
                "doesn't soften a thing for that. \"Won't understand it till you're big again,\" "
                "he says, indifferent. \"Mark doesn't care what headspace took it. It'll be there "
                "when you come up.\"")
    return {"key": "mp_arrival", "prompt": (
        "The Marking Parlour is the cleanest room in the facility, and the most frightening for it "
        "— part tattoo studio, part surgery, part leatherworker's bench, smelling of green soap and "
        "hot iron and ink. A padded marking chair stands bolted under a swing-arm lamp, reclined "
        "and spread, restraints at wrist and ankle and waist and a strap for the brow. One wall is "
        "the trade, racked floor to ceiling: a heated bar of branding irons in every shape, tattoo "
        "guns, trays of needles and rings and gauges, inks in facility grey and ownership black. "
        "The far wall is the |wportfolio|n — framed photographs and peeled, cured hide-prints of "
        "every mark the parlour has ever set, catalogued by owner. A gallery of finished work, and "
        "you the next blank page in it.\n\n"
        "The |wmarker|n doesn't greet you. He's a lean, unhurried man with steady hands and the "
        "flat focus of a craftsman, and he buckles you into the chair the way you'd clamp a "
        "workpiece — wrists, ankles, waist, and last the strap across your brow that means you "
        "don't get to flinch the work crooked. He tests an iron against a damp cloth; it hisses. "
        "\"Hold still, or don't,\" he says, the only thing he says. \"The strap holds you either "
        "way. Doesn't come off, what I do. Doesn't fade. Isn't up for discussion. So.\" He waits "
        "for the iron to come to colour." + note),
        "options": [
            {"key": "still", "label": "Go still under the strap", "set": {"chair": "still"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "let him work clean; the stillness is its own surrender",
             "outcome": (
                "You make yourself still — fully, deliberately, the way the chair wants — and the "
                "marker grunts the smallest approval, the approval of a craftsman handed good "
                "material. \"Good. Holds still. Work comes out clean on the ones that hold still.\" "
                "Your stillness will be in the line of the mark forever, and you find you want it "
                "clean too, which is its own small surrender.")},
            {"key": "strain", "label": "Strain against the chair", "set": {"chair": "strain"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "fight it; the brow-strap was built for exactly this",
             "outcome": (
                "You strain — and the brow-strap and the waist-clamp hold you motionless with the "
                "indifference of well-made hardware, and the marker doesn't even pause. \"They all "
                "pull at first. Chair's built around the pulling. Just means a tighter strap and "
                "the same mark.\" He cinches the brow another notch. \"You'll hold still in the end "
                "because you can't do anything else. Might as well start now.\"")},
            {"key": "ask", "label": "Ask what he's putting on you", "set": {"chair": "ask"},
             "desc": "make him name it before the iron does",
             "outcome": (
                "\"What's the order.\" He glances at a card clipped to the lamp arm — Bethany's "
                "hand, you think, or the board's. \"Says here you're getting marked as hers proper "
                "today. Ownership work. The permanent kind, so anyone who handles you after reads "
                "off your skin who you belong to, in the dark, by feel.\" He sets the card down. "
                "\"Didn't need to ask. You'd have found out when the iron landed. But now you can "
                "watch it coming. Some prefer that.\"")}],
        "default": "still",
        "then": "mp_order"}


@choice("mp_order", root=False)
def _mp_order(character):
    chair = scene_flag(character, "chair", "still")
    lead = ("\"Order's set. But there's a few ways to do ownership work, and the card lets the "
            "stock pick the where, sometimes. Cruelty of choice — Bethany's idea.\" "
            if chair != "strain" else
            "\"No pick for the ones that fight. I choose, you wear it.\" ")
    return {"key": "mp_order", "prompt": (
        lead + "He lays the options out on the bench, unhurried, naming each like a tradesman "
        "quoting a job. \"|wThe brand.|n Iron, hot, her mark burned in where it'll scar and stay — "
        "fastest, cruellest, reads by fingertip forever. \"|wThe rings.|n Full set — septum, "
        "nipples, clit, a ladder, a numbered tag, a bell — turns you out as hardware as well as "
        "function, leads by the nose, rings when you're used. Or \"|wthe ink.|n A womb-tattoo, low "
        "on the belly, her sigil over where you carry — declares what you're for to anyone who "
        "gets you spread.\" He picks up the nearest tool and waits. \"One goes on today regardless. "
        "Which.\""),
        "options": [
            {"key": "brand", "label": "The brand — take her mark burned in", "set": {"mark": "brand"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "the iron; a scar you'll read by feel forever",
             "outcome": (
                "\"The iron. Brave, or stupid, or hers already — usually all three.\" He lifts the "
                "branding iron off the heated bar, its mark glowing dull, and the heat of it reaches "
                "you from a foot away. \"Don't hold your breath. Breathe out when it lands. It's "
                "worse if you're full of air.\"")},
            {"key": "rings", "label": "The rings — be turned out as hardware", "set": {"mark": "rings"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "the full set; led by the nose, ringing when used",
             "outcome": (
                "\"The full set, then. Septum first — hold your head against the strap.\" He lays "
                "out the gauged needles and the rings in a neat gleaming row, one for every place "
                "he's going to open and hang you, and you understand you'll leave this chair "
                "jingling. \"Heaviest hardware I do in one sitting. You'll feel each one for "
                "weeks.\"")},
            {"key": "ink", "label": "The ink — her sigil where you carry", "set": {"mark": "ink"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "the womb-tattoo; a declaration read when you're spread",
             "outcome": (
                "\"The womb piece. Long sitting, that one — the needle's the least of it, it's the "
                "*hours* of being held open and worked on.\" He swings the gun's arm down over the "
                "low curve of your belly and inks a guideline, cold and precise. \"Anyone who "
                "spreads you from now reads who owns the inside of you. That's the point of where "
                "it goes.\"")}],
        "default": "brand",
        "then": "mp_work"}


@choice("mp_work", root=False)
def _mp_work(character):
    mark = scene_flag(character, "mark", "brand")
    method = {"brand": "_proc_brand", "rings": "_proc_cowset", "ink": "_proc_womb_tattoo"}.get(mark, "_proc_brand")
    body = {
        "brand": ("The iron lands. There is a moment of pure white pressure that your mind refuses "
                  "to call pain because pain is too small a word, and then the smell — and the "
                  "*sound*, a brief wet hiss of you — and the marker holds it the exact count it "
                  "needs and not a fraction more, lifts it clean, and her mark is in you now, "
                  "raised and furious and permanent, a thing you will find with your fingertips in "
                  "the dark for the rest of your life and know whose you are."),
        "rings": ("He works fast and exact, and each one is its own bright shock — the septum with "
                  "a crunch you feel in your skull, the nipples drawn taut and pierced through, the "
                  "clit a white star of sensation that whites the room out, the ladder, the tag "
                  "punched in, the bell hung last — and when he's done you are strung with steel "
                  "and brass through every soft place, heavy with it, and the small bright "
                  "chime of the bell when you so much as breathe tells you and everyone what "
                  "you've become."),
        "ink": ("The hours go strange and long under the needle's drone — held open, worked on, the "
                "low burn of the line laid into the soft skin over your womb again and again, the "
                "marker absorbed and indifferent, you reduced to a surface being finished — until "
                "her sigil sits low on your belly, raised and tender and permanent, a declaration "
                "of what you carry and for whom that you will wear under everything, forever."),
    }.get(mark, "")
    return {"key": "mp_work", "prompt": (
        body + "\n\nThe marker sits back, wipes the work clean with something that stings, and "
        "studies it with a craftsman's flat satisfaction — not in you, in the *line of it*, the "
        "evenness, the way it took. \"Took clean,\" he says, which from him is a benediction. "
        "\"That's set. That's you, now, under whatever you wear, for good.\" Whatever you choose to "
        "do with the agony still ringing through you, the mark does not care. It's already part of "
        "you."),
        "options": [
            {"key": "take_it", "label": "Take it — let it become part of you", "effect": "facility",
             "params": {"method": method, "kind": "proc"}, "set": {"marked": "owned"},
             "desc": "the real mark lands — onto your body, your file, forever",
             "outcome": (
                "You stop fighting the fact of it and let it be true: it's on you, it's real, it's "
                "recorded — the mark lands on your actual body and your file both, ownership made "
                "legible on your skin. Something in you settles around the permanence with a "
                "terrible relief: the question of whose you are has been answered in a way that "
                "can't be argued with or taken back, and not having to wonder is its own dark "
                "mercy. The marker is already photographing it for the portfolio wall.")},
            {"key": "grieve", "label": "Grieve it — feel what's just been made permanent",
             "effect": "facility", "params": {"method": method, "kind": "proc"},
             "set": {"marked": "grieved"},
             "desc": "the mark is real regardless; feel the door close",
             "outcome": (
                "You feel the door close. The mark is real — on your body, in your file, fired and "
                "logged the same whether you wanted it — and you grieve the skin you had an hour "
                "ago, the body that wasn't yet readable as someone's property in the dark by feel. "
                "The marker doesn't look up from cleaning his tools. \"Grieving's normal,\" he "
                "says, flat. \"Doesn't change the line. Nothing changes the line. That's why it's "
                "the line.\"")}],
        "default": "take_it",
        "then": "mp_set"}


@choice("mp_set", root=False)
def _mp_set(character):
    mark = scene_flag(character, "mark", "brand")
    shown = {"brand": "the brand", "rings": "the hardware", "ink": "the sigil"}.get(mark, "the mark")
    return {"key": "mp_set", "prompt": (
        "He dresses the work, photographs it twice — one for your file, one for the portfolio wall "
        f"where {shown} will hang catalogued under your owner's name with all the others — and "
        "unbuckles you from the chair. Your legs are unsteady; the mark throbs its new permanent "
        "throb; and already it's stopped being a wound and started being simply a fact of your "
        "body, the way a fact of your body is something you stop arguing with. \"Done. Healed-up "
        "instructions are nobody's problem but yours — keep it clean, it sets regardless.\" He's "
        "already wiping down the chair for the next workpiece. \"You'll be back. They always send "
        "the marked ones back for more. Once you can read ownership off a body, the temptation's "
        "to write the whole story on it.\" He nods you at the door. \"Off the chair. Mind the "
        "tender bits.\""),
        "options": [
            {"key": "thank", "label": "Thank him for the clean work", "effect": "gratitude",
             "end": True, "desc": "a craftsman's pride is contagious; thank the line",
             "outcome": (
                "\"Thank you.\" You mean it about the work — it is clean, it is even, it is well "
                "made — and meaning it about the work means meaning it, a little, about being "
                "*made*, and the marker accepts it with a craftsman's nod. \"Clean work deserves "
                "saying so. Bethany'll be pleased with it. She likes her marks worn proud.\" Being "
                "handed up to her approval, marked and grateful, settles into you under the throb "
                "and does not leave.")},
            {"key": "silent", "label": "Say nothing — carry it out", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "leave wearing it, mute",
             "outcome": (
                "You say nothing. You carry the new permanent fact of yourself out of the parlour "
                "in silence, every step a fresh reminder of where it sits, and behind you the "
                "marker is already heating the next iron for the next body. The mark doesn't need "
                "your acknowledgement. It's set. It'll be answering the question of whose you are "
                "long after you've stopped being asked.")}],
        "default": "thank"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Pigsty — bestiality (the boar and the sty-pigs), filth, degradation.
# Cinematic, STATE-AWARE throughout (nugget/preg/little change how the stock use
# you). Actor: the custodian — sour, unbothered, hoses the place between shifts and
# thinks of you as a thing that makes the floor dirty. Real breeding fires at the
# mount (_gang). §0: escape/forceclear haul you out of the muck always.
# Flow: arrival→down→root→mount→wallow→after. Entry: `scene pigsty`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("ps_arrival", root=False)
def _ps_arrival(character):
    st = _state_tags(character)
    # Compositional state note — stacks for every combo (nugget+little, nugget+preg, all three).
    if st["nugget"]:
        note = ("You don't walk into the sty — a nugget can't, no arms, no legs — so the custodian "
                "hauls you in under one arm like a sack and drops you in the muck, where you land "
                "and stay, because moving yourself out of it was never on the table")
    elif st["preg"] or st["little"]:
        note = "You're herded down toward the pit"
    else:
        note = ""
    if note:
        clauses = []
        if st["preg"]:
            clauses.append("belly-heavy with the facility's get — and the sty likes a bred one "
                           "best, they rut a pregnant sow with extra appetite and no care at all "
                           "for the cargo")
        if st["little"]:
            clauses.append("down in your headspace and barely grasping where you've been brought, "
                           "which makes the smell and the warmth and the snouts land stranger and "
                           "softer and so much worse")
        if clauses:
            note += " — " + ", and ".join(clauses)
        note += ". "
        if st["nugget"] and (st["preg"] or st["little"]):
            note += "\"Look at the state of this one,\" the custodian remarks, unimpressed. "
    return {"key": "ps_arrival", "prompt": (
        "The Pigsty is the low end of the facility in every sense — a churned pit of warm wet "
        "muck and slop kept deliberately filthy, ringed by low pens where the sty-pigs grunt and "
        "shift, and at the back, vast in his wallow, the |wboar|n: rank, tusked, enormous, already "
        "lifting his blunt snout at the change in the air. The stink is total — shit and slop and "
        "rutting animal and the sour-sweet rot of a place hosed down but never clean. " + note +
        "\n\nThe |wcustodian|n leans on a hose by the drain, sour and unbothered, a man whose whole "
        "job is the mess you're about to become and who resents you for it in advance. \"Sty "
        "duty,\" he says flatly, not looking at you so much as at the work you represent. \"Board "
        "says you go in the muck and the stock has its way with you. I hose it down after. Try not "
        "to drown in it — paperwork if you do.\" He jerks his chin at the pit. \"In. They can smell "
        "you. They've been waiting.\""),
        "options": [
            {"key": "walk", "label": "Walk into the muck yourself", "set": {"sty": "walk"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "lower yourself into the filth; spare yourself being thrown",
             "outcome": (
                "You step down into it yourself — the muck closing warm and obscene around your "
                "ankles, your shins, soft and stinking — and lower yourself the rest of the way "
                "rather than be thrown. The custodian grunts. \"Walks itself in. Saves my back.\" "
                "The pigs are already shifting toward the warmth and movement of you.")},
            {"key": "balk", "label": "Balk at the edge of the pit", "set": {"sty": "balk"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "refuse the filth; he'll boot you in",
             "outcome": (
                "You balk at the reeking edge — and the custodian sighs, plants a boot between your "
                "shoulders, and shoves you face-first into the muck, where you land in the warm "
                "stinking wet of it with the pigs already grunting closer. \"Always one,\" he says, "
                "wiping his boot. \"Goes in the same. Just dirtier, and madder, and that's worse "
                "for you, not me.\"")},
            {"key": "ask", "label": "Ask what's going to happen to you here", "set": {"sty": "ask"},
             "desc": "make him say it",
             "outcome": (
                "\"What happens.\" He finally looks at you, flat. \"Boar covers you. Pigs root you "
                "over. You get filthy and bred and you stay down in it till the board's happy, and "
                "then I hose you off enough to walk and you go to your next thing.\" He spits to the "
                "side. \"It's the sty. Nothing happens here but what the name says. In you go.\"")}],
        "default": "walk",
        "then": "ps_down"}


@choice("ps_down", root=False)
def _ps_down(character):
    st = _state_tags(character)
    pos = ("There's no arranging yourself — a nugget just lies where it was dropped, torso half-"
           "sunk in the warm muck, holes at the mercy of whatever roots up to them. "
           if st["nugget"] else
           "You're put down on hands and knees in it, the muck swallowing your forearms to the "
           "elbow, your face inches from the reeking surface, hips up where the stock can reach. ")
    return {"key": "ps_down", "prompt": (
        pos + "The warmth of the slop is the worst betrayal of it — it should be cold, it has no "
        "right to be this blood-warm and enveloping, and your body registers the obscene comfort of "
        "it even as your mind recoils from the stink. The pigs are coming. You can hear them, feel "
        "the slop shift with their weight, the wet snuffling of snouts working closer, scenting the "
        "heat the facility keeps banked in you under all the filth. The custodian watches from the "
        "dry edge, hose slack, bored. \"Down you go. They'll find you.\""),
        "options": [
            {"key": "sink", "label": "Sink into it — let the filth be what it is", "effect": "devote",
             "params": {"amount": 2.0}, "desc": "stop fighting the muck; let it have you",
             "outcome": (
                "You stop fighting the slop and let it have you — let it be warm, let it be filthy, "
                "let yourself be a thing in the muck — and the surrender drains the last dignity out "
                "of you and replaces it with a flat animal calm that is its own kind of broken. The "
                "first snout reaches you, snuffling wetly along your flank, and you don't flinch.")},
            {"key": "retch", "label": "Retch and recoil from the stink", "effect": "deny_hold",
             "params": {"cond": 3.0}, "desc": "your body's revolt; it changes nothing",
             "outcome": (
                "You retch at the stink, recoil from the warm wet of it — and there's nowhere to "
                "recoil to, the muck on every side, and your thrashing only churns it up worse and "
                "coats you deeper and draws the pigs faster to the disturbance. The custodian "
                "doesn't move. \"Wears off,\" he says. \"The gagging. Give it a day on sty duty. "
                "You stop smelling it. You stop smelling anything.\"")}],
        "default": "sink",
        "then": "ps_root"}


@choice("ps_root", root=False)
def _ps_root(character):
    st = _state_tags(character)
    # Additive flavour — every applicable state layers in (combos all covered).
    flav = ""
    if st["nugget"]:
        flav += ("A limbless thing in the muck is all holes and no defence — they shove your "
                 "helpless weight around the slop, nosing you over, working out which end is which. ")
    if st["preg"]:
        flav += ("A snout shoves up under the swell of your belly, lifting it, scenting the gravid "
                 "heat of you, and the boar grunts sharper interest — a bred sow is exactly what the "
                 "sty is for. ")
    if st["little"]:
        flav += ("In your headspace the snouts are soft and snuffling and almost ticklish at first, "
                 "and the not-understanding lets them root you while some small far part of you "
                 "keeps waiting for it to become something kinder. It doesn't. ")
    return {"key": "ps_root", "prompt": (
        "The pigs reach you and |wroot|n — blunt wet snouts shoving under you, over you, into the "
        "folds and seams of you, snuffling along every part with a single-minded animal thoroughness "
        "that has nothing to do with arousal and everything to do with claiming the new warm thing "
        "for the sty. " + flav + "They slather you in muck and snot and their own reek, marking you "
        "theirs, and behind them the boar heaves up out of his wallow and comes, parting the lesser "
        "pigs, and there is no question what he intends. The custodian makes a note. \"Boar's keen. "
        "Won't be long now.\""),
        "options": [
            {"key": "still", "label": "Hold still and let them claim you", "effect": "devote",
             "params": {"amount": 3.0}, "desc": "be the sty's new thing; don't fight the rooting",
             "outcome": (
                "You hold still and let the herd root you over and mark you theirs, and the becoming-"
                "the-sty's-thing settles into you with the muck, deep and total. The pigs accept you "
                "the way they'd accept any warm hole that stopped struggling. The boar shoulders "
                "the last of them aside and looms over you, blunt and dripping and ready.")},
            {"key": "thrash", "label": "Thrash against the rooting herd", "effect": "deny_hold",
             "params": {"cond": 3.0}, "desc": "fight the snouts; churn the muck; lose",
             "outcome": (
                "You thrash, and the pigs don't care, and the muck doesn't care, and all you do is "
                "exhaust yourself and coat yourself deeper and present yourself more obscenely to "
                "the boar now standing over you. \"Tires itself out,\" the custodian observes. "
                "\"Boar prefers 'em tired. Easier to seat.\"")}],
        "default": "still",
        "then": "ps_mount"}


@choice("ps_mount", root=False)
def _ps_mount(character):
    st = _state_tags(character)
    k = _kit(character)
    extra = []
    if k["milk_port"]:
        extra.append(
            {"key": "screwed_milk", "label": "Let the screwing shake your milk loose",
             "effect": "facility", "params": {"method": "_do_milk", "kind": "proc"},
             "set": {"sty_bred": "milked"},
             "desc": "[milk-port] the boar's long churn drags your let-down down the line in the muck",
             "outcome": (
                "The endless boring churn of the boar shudders up through you and your port lets "
                "down for it — milk running out the line into the filth-slick collection while the "
                "animal screws toward your womb, the two harvests pulled out of you at once, milked "
                "and bred in the same half-hour flood. The custodian clips the line without comment "
                "and logs the yield. \"Ported sow milks while she's covered,\" he notes. \"Nothing "
                "wasted down here. Not even you.\"")})
    belly = (" — and he ruts you belly-and-all, the swell of the facility's get squashed into the "
             "warm muck beneath you with every brutal drive, bred sow getting bred again" if st["preg"] else "")
    return {"key": "ps_mount", "prompt": (
        _kit_use_note(character) +
        "The boar mounts. There's no ceremony and no mercy — he heaves his enormous filthy bulk up "
        "over you, trotters scrabbling and gouging in the slop, far too heavy — and his cock is "
        "nothing like the blunt stud-things you've taken: it's long, and thin, and wickedly "
        "pointed, a living |wcorkscrew|n that stabs and seeks and then catches a hole and begins to "
        "*screw* itself in, the spiral of it boring and twisting deeper with every frantic thrust, "
        "winding further into you than anything has any right to reach, hunting inward, always "
        "inward, for the neck of your womb" + belly + ". It does not bottom out and settle the way "
        "a stud does; it just keeps *screwing*, deeper, the pointed tip corkscrewing toward your "
        "cervix while his bulk grinds you down into the muck and his reek swallows the world. The "
        "custodian watches to be sure the tip's found its mark and the boar won't tear stock. "
        "\"There — feel it screwing up to the neck of you? Now it locks its tip in your womb and "
        "*empties*, and a boar empties for the better part of half an hour. Settle in. You're not "
        "going anywhere for a while.\""),
        "options": extra + [
            {"key": "take", "label": "Take it — open to the boar in the muck", "effect": "facility",
             "params": {"method": "_gang", "kind": "gang"}, "set": {"sty_bred": "took"},
             "desc": "the real cover — a sty breeding logged to your line",
             "outcome": (
                "You open and take him, and your body does what it's kept for even buried in filth "
                "with a boar's weight crushing you down — and the cover is real, recorded, logged "
                "to your line as a sty breeding, sire and species and all. He corkscrews deep and "
                "you feel him swell toward the tie, and the degradation and the heat and the warm "
                "muck blur into one thing your nerves stop sorting.")},
            {"key": "endure", "label": "Endure it — wait for the animal to finish", "effect": "facility",
             "params": {"method": "_gang", "kind": "gang"}, "set": {"sty_bred": "endured"},
             "desc": "the cover happens regardless; refuse to want it",
             "outcome": (
                "You endure it — hold yourself outside the brutal animal fact of being bred in the "
                "muck — and it happens anyway, every uncaring drive, the cover as real and recorded "
                "as if you'd begged. Your body took. The boar didn't notice your refusal and "
                "neither did the board. \"Took fine,\" the custodian confirms, marking it. \"Wanting "
                "it's not on the form.\"")}],
        "default": "take",
        "then": "ps_wallow"}


@choice("ps_wallow", root=False)
def _ps_wallow(character):
    st = _state_tags(character)
    extra = (" The lesser sty-pigs take their turns when the boar's spent — each screwing in the "
             "same relentless way, locking its tip and emptying its own long flood and sealing you "
             "deeper, plug set over plug, an ordeal measured in hours and not in minutes, and you "
             "lose count and then lose the thread." if not st["nugget"] else
             " You can't crawl off between them and aren't meant to — a nugget just stays sunk in "
             "the wallow where the next one screws into the same sealed mess, hour on hour.")
    return {"key": "ps_wallow", "prompt": (
        "The corkscrew tip seats hard against the neck of your womb and *locks* there — and then "
        "the boar empties, and a boar does not empty in pulses and finish: he empties for the "
        "better part of half an hour, a relentless hot flood with nowhere to go but to pack you "
        "fuller and force deeper, the screwed-in length twitching and pumping and pumping while his "
        "filthy bulk pins you motionless in the muck and the minutes drag and drag. And when at "
        "last the flood slows he pumps one thing more — a thick gelatinous gush that sets even as "
        "it spills into a rubbery |wplug|n, sealing the neck of your womb, corking the whole "
        "half-hour's breeding inside you behind a mucus seal that won't dissolve for hours, maybe a "
        "day. Only then does he unscrew himself out of you with a slow obscene twist and heave off "
        "— leaving you sealed and sloshing-full and filthy, the plug holding all of it in. And the "
        "sty is not done with you." + extra + " You are kept down in "
        "the warm muck, rutted and marked and slopped, used by whatever roots up next, the "
        "degradation so total and so prolonged that somewhere in it the shame burns out entirely "
        "and leaves only the flat warm animal fact of being the thing the sty uses. The world goes "
        "long and grey and far, and you surface later still filthy, still being mounted, the muck "
        "and the time having swallowed whole stretches you'll never get back.\n\n"
        "The custodian, from the dry edge: \"In and out of it. Sty does that. Easier on you than "
        "staying present, frankly. Nothing up here you'd want to be present for.\""),
        "options": [
            {"key": "gone", "label": "Stay gone — let the sty have the body", "effect": "devote",
             "params": {"amount": 4.0}, "desc": "leave; the muck and the stock do the rest",
             "outcome": (
                "You stay gone, somewhere far and quiet, and let the sty have the filthy used thing "
                "your body's become. It breeds on without you. When you finally surface for good "
                "you're caked and gaping and bred and the shame can't find purchase on the smooth "
                "flat calm where a person used to keep it. That's the sty's whole lesson, and you've "
                "learned it down in the muck.")},
            {"key": "present_here", "label": "Stay present — feel all of it", "effect": "deny_hold",
             "params": {"cond": 4.0}, "desc": "refuse to leave your own filthy body",
             "outcome": (
                "You refuse to leave — stay in the body and feel every filthy mount, every snout, "
                "every brutal tie, the warm muck and the reek and the using, fully present and "
                "wire-tight with the horror and the traitor heat braided together. \"Stays home for "
                "the sty,\" the custodian notes, almost impressed despite himself. \"Stubborn. Those "
                "ones break slowest. Sty's patient, though. Sty's got nothing but time and pigs.\"")}],
        "default": "gone",
        "then": "ps_after"}


@choice("ps_after", root=False)
def _ps_after(character):
    st = _state_tags(character)
    haul = ("He fishes your limbless filthy weight up out of the wallow by whatever he can grip"
            if st["nugget"] else "He hauls you up out of the muck by the hair when the board's done")
    return {"key": "ps_after", "prompt": (
        haul + ", and turns the hose on you — cold, hard, indifferent, sluicing the worst of the "
        "filth off you and the floor in the same bored arcs, not for your comfort but so you're "
        "fit to be moved without dirtying the next room. The cold water on your used-raw body is "
        "almost a kindness and isn't meant as one. \"Bred, slopped, rinsed,\" he recites, ticking "
        "his board. \"Sty quota's logged. Your line's got a boar-cross in it now whether you wanted "
        "one or not.\" He coils the hose. \"You'll be back when the board's short on filth. It "
        "never stays long off the books.\" He nudges you toward the drain-side door with his boot. "
        "\"Off you go. Drip somewhere else.\""),
        "options": [
            {"key": "thank", "label": "Thank him — for the hose, for the end of it",
             "effect": "gratitude", "end": True, "desc": "the rinse was almost mercy; thank it",
             "outcome": (
                "\"Thank you.\" It's for the hose, the cold clean of it, the *end* — and it comes "
                "out small and filthy and meant, and the custodian snorts. \"Thanking me for "
                "hosing you. Sty's done its work, then.\" He's right. Gratitude for a scrap of "
                "cold water, after that — that's the muck having gotten all the way in, past the "
                "skin, where the hose can't reach.")},
            {"key": "silent", "label": "Say nothing — drip out filthy", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "leave the sty mute, half-rinsed",
             "outcome": (
                "You say nothing. You haul your half-rinsed bred-filthy self toward the door on "
                "shaking legs, the boar already settling back into his wallow behind you, the muck "
                "already smoothing over the place you were used. The custodian's hose hisses off. "
                "You'll be back when the board wants filth, and the board always, eventually, wants "
                "filth.")}],
        "default": "thank"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Sanitation Block — the relief-hole wall + the toilet frame.
# Cinematic, state-aware. Actor: the custodian + the anonymous queue. Real use
# fires at the wall (_scene_bukkake). §0 always frees you.
# Flow: arrival→wall→use→after. Entry: `scene sanitation`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("sb_arrival", root=False)
def _sb_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = ("A nugget doesn't kneel at the rail — you're slotted and braced into the holed "
                "partition by the custodian, fixed at the right height, a torso and holes mounted "
                "to the wall for the queue's convenience and unable to do anything but be a hole. ")
    elif st["preg"]:
        note = ("Even gravid you're put to the wall — \"a bred one's still got a mouth and an ass,\" "
                "the custodian shrugs — your swollen belly braced clear of the rail so the queue "
                "can use the rest of you. ")
    elif st["little"]:
        note = ("Down in your headspace you're guided to the rail almost gently and then left there, "
                "the not-understanding making the anonymous use that follows land stranger and "
                "softer and worse. ")
    return {"key": "sb_arrival", "prompt": (
        "The Sanitation Block is a white-tiled wet-room of drains and troughs, bleach laid thin "
        "over the reek of piss and stale spend. One wall is a partition of waist-height |wholes|n, "
        "a dozen of them, rims worn smooth and pale, a padded kneeling-rail bolted along the base — "
        "cocks come through from the far side, staff, stock, whoever's queued, and there's no "
        "telling whose. In the centre a low steel frame locks a body face-up beneath an open seat: "
        "a toilet built around a person. The whole floor pitches to a central grated drain, a hose "
        "coiled alongside for sluicing the unit and the room between shifts.\n\n"
        "The |wcustodian|n runs this room too, and likes it even less. " + note + "\"Relief-hole "
        "duty,\" he says, flat. \"You go to the wall, the queue uses you, I sluice you down after. "
        "Or the frame, if the board wants you catching instead of milking.\" He nods at the "
        "partition, where the first impatient shape already shifts on the far side. \"There's a "
        "queue. There's always a queue. Pick your station or I pick it for you.\""),
        "options": [
            {"key": "wall", "label": "Go to the holed wall", "set": {"san": "wall"},
             "effect": "devote", "params": {"amount": 2.0}, "desc": "kneel to the rail; be the anonymous hole",
             "outcome": (
                "You take the rail yourself, kneel to the worn pad, and put your mouth to the "
                "nearest worn hole — and on the far side something grunts and shoves through, "
                "thick and anonymous and already hard. The custodian marks it. \"Goes to the wall "
                "itself. Good. The keen ones clear the queue faster.\"")},
            {"key": "frame", "label": "Take the toilet frame instead", "set": {"san": "frame"},
             "effect": "deny_hold", "params": {"cond": 2.0}, "desc": "the seat; catch whatever it's used for",
             "outcome": (
                "He locks you face-up into the low frame beneath the open seat, your mouth and holes "
                "positioned under the gap to catch whatever the seat is used for, and the helpless "
                "upturned waiting of it is its own degradation. \"Frame, then. Board'll like the "
                "change-up.\" Footsteps approach the seat above you. You can't see whose.")},
            {"key": "ask", "label": "Ask who's on the other side", "set": {"san": "ask"},
             "desc": "make him say there's no knowing",
             "outcome": (
                "\"Who's on the far side.\" The custodian almost smiles. \"That's the whole point, "
                "isn't it. Staff, stock, a stud handler on his break, the lad who mops — nobody "
                "writes it down. You'll never know whose load's in you. That's not a flaw in the "
                "system. That's the system.\" He nods at the rail. \"Go on.\"")}],
        "default": "wall",
        "then": "sb_use"}


@choice("sb_use", root=False)
def _sb_use(character):
    san = scene_flag(character, "san", "wall")
    body = ("Cocks come through the holes one after another and you're made to take each wherever "
            "it's aimed — throat, then a different hole at a different rim, used and spurted in and "
            "abandoned for the next, an anonymous relief-hole for a queue you can't see and will "
            "never meet, the wall indifferent as a vending machine and you the thing it dispenses. "
            if san != "frame" else
            "From the seat above, you catch what it's used for — cocks lowered to your waiting mouth "
            "and holes, used and emptied into you and replaced, the queue treating you as the "
            "fixture you've been made into, the open seat framing your face for whoever steps up. ")
    return {"key": "sb_use", "prompt": (
        _kit_use_note(character) + body + "There is no pacing, no person, no end you can see — just use, hole after hole, "
        "load after anonymous load, the facility's banked heat keeping your own body obscenely "
        "interested in its own degradation. Time smears. You stop counting. The custodian leans "
        "on his hose, bored, occasionally telling the queue to mind the stock. \"Steady,\" he says, "
        "to them, not you. \"It's not going anywhere.\""),
        "options": _sb_use_options(character),
        "default": "serve",
        "then": "sb_after"}


def _sb_use_options(character):
    """Base serve/endure plus kit-gated routes — a gape takes the back of the queue without
    a swap; a teat-gag/stuffed mouth changes what the wall does with your face."""
    k = _kit(character)
    extra = []
    if k["gaped"]:
        extra.append(
            {"key": "gape_queue", "label": "Offer the gauge — let the queue use the open hole hard",
             "effect": "facility", "params": {"method": "_scene_bukkake", "kind": "scene"},
             "set": {"san_done": "gaped"},
             "desc": "[gape] the ringed-open hole takes them with no warm-up, no limit",
             "outcome": (
                "You offer the gauge — the hole ringed permanently open — and the queue doesn't "
                "have to work for it at all: no warm-up, no resistance, just an open fitting they "
                "drive into one after another, harder and deeper than a tight one would let them, "
                "because the ring took the choice of *no* out of your body a long time ago. The "
                "custodian notes the heavier traffic. \"Gauged ones clear the queue faster,\" he "
                "says. \"Nothing slows the line. That's the point of opening you up.\"")})
    if k["teat_gag"] or k["stuffed"]:
        extra.append(
            {"key": "gagged_take", "label": "Take it around what's already stopping your mouth",
             "effect": "facility", "params": {"method": "_scene_bukkake", "kind": "scene"},
             "set": {"san_done": "gagged"},
             "desc": "[mouth clause] the queue works the holes that aren't already plugged",
             "outcome": (
                "Your mouth's already stopped — gagged, plugged, busy with what the clause keeps in "
                "it — so the queue simply uses every hole that *isn't*, working you below while the "
                "stoppered mouth can do nothing but leak muffled sound around its filler. The "
                "custodian doesn't bother clearing it. \"Mouth's spoken for,\" he tells the queue. "
                "\"Use the rest. She's still got plenty going spare.\"")})
    options = [
            {"key": "serve", "label": "Serve the queue — be the hole, well", "effect": "facility",
             "params": {"method": "_scene_bukkake", "kind": "scene"}, "set": {"san_done": "served"},
             "desc": "the real anonymous use — logged, hole after hole",
             "outcome": (
                "You stop holding any part of yourself back and just *serve* — be the hole, do it "
                "well, take each anonymous cock wherever it's aimed and milk it and present for the "
                "next — and the real use is logged, load after load, your body a public utility "
                "performing its function. The being-good-at-it is the worst of it, and you feel it "
                "settle in as a skill, a thing you now know how to be.")},
            {"key": "endure", "label": "Endure the queue — give them nothing but the hole",
             "effect": "facility", "params": {"method": "_scene_bukkake", "kind": "scene"},
             "set": {"san_done": "endured"}, "desc": "they use you regardless; withhold everything else",
             "outcome": (
                "You give the queue nothing but the hole it came for — no skill, no sound, no part "
                "of you past the wet they're using — and they use you exactly the same, because the "
                "wall never wanted anything else from you. The loads come anonymous and indifferent "
                "regardless. Withholding cost you effort the queue didn't even register. The use is "
                "logged the same.")}]
    return extra + options


@choice("sb_after", root=False)
def _sb_after(character):
    return {"key": "sb_after", "prompt": (
        "Eventually the queue thins, or the board's satisfied, or the shift changes — you have no "
        "way to tell which — and the custodian unracks or unframes you and turns the hose on you "
        "and the unit both, cold and hard and indifferent, sluicing the spend off your face and "
        "thighs and the tile in the same bored arcs. \"Relief-hole quota's done,\" he says, to the "
        "board. \"You took the lot. No telling whose. That's how it's meant to read.\" He coils "
        "the hose. You are dripping, used soft and raw, anonymous loads in you from people you "
        "will pass in the corridors and never identify. \"Off you go. The wall'll want you again. "
        "It always fills back up. So do you.\""),
        "options": [
            {"key": "thank", "label": "Thank him for the hose", "effect": "gratitude", "end": True,
             "desc": "the cold rinse, the end of the queue; thank it",
             "outcome": (
                "\"Thank you.\" For the hose, the end, the cold clean of it after so much anonymous "
                "warm — and it lands meant, and the custodian shakes his head. \"Wall takes the "
                "fight out fast. Thanking me already.\" The gratitude files itself with everything "
                "the room took, which was, in the end, everything you brought in but the hole.")},
            {"key": "silent", "label": "Say nothing — drip out used", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "leave the block mute and dripping",
             "outcome": (
                "You say nothing. You leave the white-tiled room on unsteady legs, dripping, full "
                "of strangers, and behind you the far side of the wall already has a fresh shape "
                "shifting at the first hole, because the queue never empties and the wall never "
                "closes and you are, now, one of the things it's for.")}],
        "default": "thank"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Showroom — appraised, blocked, bid on, sold. The ownership turn.
# Cinematic, state-aware. Actor: Bethany presiding (auctioneer AND the buyer who
# means to win) + the gallery of bidders behind one-way glass. REAL payload:
# _appraise sets your sale price, bid_up climbs the ledger, bethany_buys transfers
# ownership for real (bethany_owned, title, sale_price). §0 always frees you.
# Flow: arrival→display→bidding→gavel→bought. Entry: `scene showroom`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("sw_arrival", root=False)
def _sw_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = ("A nugget doesn't walk the block — you're set on a velvet plinth at its centre, "
                "limbless and turned slowly by hand so every angle of you faces the glass, a "
                "centrepiece lot. ")
    if st["preg"]:
        note += ("The swell of the facility's get is lit deliberately, turned to the glass; a "
                 "proven bred lot draws the serious money and Bethany knows it. ")
    if st["little"]:
        note += ("Down in your headspace you don't understand the lights or the glass, only that "
                 "you're being looked at, and the gallery finds the confusion appealing, which "
                 "raises you a tier on its own. ")
    return {"key": "sw_arrival", "prompt": (
        "The Showroom is all light and glass and money. They prep you behind the scenes — oiled, "
        "posed, your marks buffed to read clean — and walk you out onto the |wblock|n: a raised "
        "circle under hard white display lamps, mirrored so you can watch yourself be watched, and "
        "all around it the |wone-way glass|n of the Buyers' Gallery, behind which you cannot see "
        "the bidders but can *feel* them, a roomful of eyes and chequebooks gone quiet at the sight "
        "of fresh stock. " + note +
        "\n\nAnd presiding over it, at a small lectern with a gavel and your file open in front of "
        "her, is |wBethany|n — auctioneer today, bright and warm and businesslike, working the room "
        "she owns. She catches your eye in the mirror and her smile is private, and there is "
        "something underneath it that has already decided. \"|wThere|n she is,\" she says, to the "
        "glass, to the money. \"Our next lot. Look at the lines on this one. Let's find out what "
        "you're worth — and then let's find out who's taking you home.\" The smile, in the mirror, "
        "is just for you. \"Show them, sweetheart.\""),
        "options": [
            {"key": "perform", "label": "Perform for the glass", "set": {"block": "perform"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "give the gallery a show; drive your own price up",
             "outcome": (
                "You perform — turn, arch, show yourself off to the eyes you can't see — and you "
                "feel the room *lean in*, the hush sharpening, and Bethany's approval glints in the "
                "mirror. \"Oh, a *natural*. The gallery does love one that performs.\" You are, in "
                "this moment, complicit in your own sale, and the worst part is the flush of pride "
                "when the first murmur of interest ripples behind the glass.")},
            {"key": "freeze", "label": "Freeze under the lights", "set": {"block": "freeze"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "go still and stricken; the stillness sells too",
             "outcome": (
                "You freeze — go still and stricken under the hard lights, unable to make yourself "
                "perform — and it doesn't help you at all. \"Placid,\" Bethany purrs to the glass, "
                "spinning it. \"Bidders, note the temperament — takes handling beautifully, no "
                "fuss.\" Your stillness reads as docility, and docility *sells*, and the murmur "
                "behind the glass picks up regardless. There is no way to stand on the block that "
                "isn't an advertisement.")},
            {"key": "look", "label": "Look for Bethany in the glass", "set": {"block": "look"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "ignore the buyers; find the one face you know",
             "outcome": (
                "You ignore the glass and the lights and find *her* — the one face in the room you "
                "know, steady at her lectern — and something flickers across Bethany's "
                "auctioneer-brightness, there and gone. \"Eyes on me. Of course they are.\" Quieter, "
                "almost to herself, almost fond: \"That makes this easier. For me. We'll see about "
                "you.\" She raps the gavel once to open. \"Let's begin.\"")}],
        "default": "perform",
        "then": "sw_display"}


@choice("sw_display", root=False)
def _sw_display(character):
    return {"key": "sw_display", "prompt": (
        "\"First, the particulars.\" Bethany reads your |wappraisal|n aloud to the glass — and it "
        "is your whole self rendered as a lot: your measurements and your capacities, your "
        "conditioning depth and your suggestibility scored like a wine, your hole-training and "
        "your brood-count and your milk-yield, every mark on you catalogued by the parlour and "
        "read off like provenance. Handlers step onto the block to *demonstrate* — turning you, "
        "opening you, parting you to the glass, working a reaction out of you on cue so the "
        "bidders can see you respond — and the numbers settle into a starting price that is, "
        "horribly, *you*, summed and rounded and printed on a card. \"A clean, documented, "
        "well-broken lot,\" Bethany tells the room, with a saleswoman's pride. \"We'll open the "
        "bidding there. Show them what they'd be buying, sweetheart.\""),
        "options": [
            {"key": "show", "label": "Let them demonstrate you — respond on cue", "effect": "facility",
             "params": {"method": "_appraise", "kind": "proc"}, "set": {"shown": "willing"},
             "desc": "the real appraisal lands; your price is set off your actual file",
             "outcome": (
                "You let the handlers work you and you respond on cue, and your real appraisal is "
                "read and recorded — your actual stats, summed into an actual sale price printed on "
                "the lot card. Hearing yourself totalled, hearing the number that *is* you, lands "
                "somewhere it'll stay. The gallery murmurs at the demonstration. You sold yourself "
                "the moment your body answered the handler's hand in front of the glass.")},
            {"key": "endure_show", "label": "Endure the demonstration, give nothing", "effect": "facility",
             "params": {"method": "_appraise", "kind": "proc"}, "set": {"shown": "endured"},
             "desc": "the appraisal happens regardless; the price is set the same",
             "outcome": (
                "You endure the handling and refuse to perform the responses — and they work them "
                "out of you anyway, your body answering the practised hands whether you allow it or "
                "not, the appraisal read and the price set exactly the same. \"Even resists "
                "prettily,\" Bethany notes to the glass, turning it into a selling point. \"Some "
                "buyers pay a premium for a little fight left in.\"")}],
        "default": "show",
        "then": "sw_bidding"}


@choice("sw_bidding", root=False)
def _sw_bidding(character):
    return {"key": "sw_bidding", "prompt": (
        "And the |wbidding|n opens. You can't see them, but you hear it in Bethany's rhythm — the "
        "auctioneer's patter picking up, calling numbers off the glass, \"I have — thank you — and "
        "again — do I hear—\" — and the price climbing, climbing, each rising bid a fresh statement "
        "of exactly how much someone behind that glass wants to own you. It is the most naked you "
        "have ever been, more than the nudity, more than the demonstration: being *wanted with "
        "money*, in a rising tide of it, while you stand lit and mirrored and unable to see a "
        "single face that's deciding to buy you. Your own body, traitor to the last, responds to "
        "the exhibition of it — the heat of all those unseen eyes, the climbing number — and "
        "Bethany sees, and folds it into the patter. \"Lot's *enjoying* this, bidders. Look at "
        "that. Worth every coin.\""),
        "options": [
            {"key": "drive", "label": "Play to the bids — drive the number up", "effect": "bid_up",
             "set": {"bid": "drove"}, "desc": "make them want you more; climb your own price",
             "outcome": (
                "You play to it — give the climbing room more to want — and the bids answer, the "
                "number ratcheting higher off your real appraised price, the ledger climbing with "
                "every show you make, your worth a figure you're actively inflating with your own "
                "body. Bethany rides it gleefully. \"And *again* — thank you — the lot knows its "
                "business.\" You will never be able to unknow what you went for, or that you helped "
                "it climb.")},
            {"key": "still_bid", "label": "Stand still and let it climb without you", "effect": "bid_up",
             "set": {"bid": "still"}, "desc": "the number rises anyway; the ledger doesn't need your help",
             "outcome": (
                "You stand still and refuse to feed it — and the number climbs anyway, the bidders "
                "wanting what they want, the ledger ratcheting up off your appraised price without "
                "the first scrap of help from you. \"Even standing there breathing, look what "
                "they'll pay,\" Bethany marvels to the glass. Your worth is set by their wanting, "
                "not your performing. You were always going to sell. The only question left is to "
                "whom.")}],
        "default": "drive",
        "then": "sw_gavel"}


@choice("sw_gavel", root=False)
def _sw_gavel(character):
    return {"key": "sw_gavel", "prompt": (
        "The bidding thins to two, then to a held breath. \"Going once,\" Bethany says, gavel "
        "raised — and here, in the last second before it falls, she does something the gallery "
        "can't see: she catches your eye in the mirror and *waits*, the auctioneer's brightness "
        "gone still, the question plain on her face though she'd never say it aloud in this room. "
        "She has a paddle of her own resting at her lectern. She has had it resting there the whole "
        "time. \"Going twice,\" she says, slow, eyes on you, giving you the one beat of say you'll "
        "get in the whole transaction — not over *whether*, that was never yours, but over *who* "
        "you reach for as the gavel falls.\""),
        "options": [
            {"key": "her", "label": "Look to Bethany — reach for her", "effect": "bethany_buys",
             "set": {"sold": "bethany"}, "desc": "let her be the one; the gavel falls to her paddle",
             "outcome": (
                "You look to her — reach, with your eyes, for the one face you know — and something "
                "wins behind Bethany's expression. Her own paddle lifts. \"|wSold,|n\" she says, "
                "and brings the gavel down on herself, \"to the house.\" The ownership transfers "
                "for real — you are hers now, on paper, your title rewritten to read as Bethany's, "
                "your sale price the winning number — and she comes down off the lectern to claim "
                "you off the block personally, warm and certain and *pleased*. \"There. I wasn't "
                "going to let anyone else have you. I just wanted to see you choose me first.\"")},
            {"key": "dark", "label": "Look away — to the dark behind the glass", "effect": "bid_up",
             "set": {"sold": "pending"}, "desc": "refuse to reach for her; the bid climbs, the gavel hangs",
             "outcome": (
                "You look away — out to the dark behind the glass, to the strangers, to anywhere "
                "but her — and Bethany's face does something complicated and then settles, and her "
                "paddle lifts anyway, higher, *plus one*, and the gavel hangs unfallen. \"...Going "
                "twice,\" she repeats, softer, the sale deliberately stalled. \"No. Not like this. "
                "I'll have you reaching for me when it falls, sweetheart, or I'll buy you again and "
                "again until you do. The block keeps. So do I.\" The number climbs. There is always "
                "another inspection day.")}],
        "default": "her",
        "then": "sw_bought"}


@choice("sw_bought", root=False)
def _sw_bought(character):
    sold = scene_flag(character, "sold", "bethany")
    if sold == "pending":
        body = ("She has you walked back off the block unsold — which is its own verdict, and not "
                "a reprieve. \"Back to processing. We'll run you through the showroom again when "
                "you're a little readier to look at me when it counts.\" The not-being-bought is "
                "somehow worse than the sale would have been: you've been found wanting at the one "
                "thing she actually wanted, and you'll be back on the block until you give it.")
        opts = [
            {"key": "relief", "label": "Feel the relief of not being sold", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "a reprieve that isn't one",
             "outcome": (
                "You feel relief — and it curdles immediately, because she's right, this isn't an "
                "escape, it's a *do-over*, and you'll stand on that block again and again until you "
                "reach for her when the gavel hangs. The relief was the bait. Wanting the sale to "
                "be over is the first step toward wanting her to be the one who ends it.")},
            {"key": "ache", "label": "Feel the ache of not being chosen", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "the hook she meant to set",
             "outcome": (
                "And there it is — the ache. Not relief: *disappointment*. Some hooked part of you "
                "wanted her paddle to fall, wanted to be the thing she took home, and didn't get "
                "it, and the wanting is exactly the thing she stalled the sale to grow. You'll "
                "reach for her next time. You're already most of the way there, and you both know "
                "it.")}]
    else:
        body = ("She claims you off the block herself — a hand at your nape, proprietary and warm, "
                "steering you out of the lights and the glass and into being, simply and on paper, "
                "*hers*. \"Mine now,\" she says, like a fact, like a relief. \"Bought and paid and "
                "written down. No more block for you — I don't resell what I decide to keep, and I "
                "decided about you a while ago.\" Your title reads as hers. Your sale price is "
                "logged. You belong to a specific person now, by name, and the specificity of it "
                "is a different weight than the facility's general ownership ever was.")
        opts = [
            {"key": "hers", "label": "Sink into being hers", "effect": "devote", "params": {"amount": 4.0},
             "end": True, "desc": "let the specific belonging settle",
             "outcome": (
                "You sink into it — into being *hers*, specifically, named, chosen and bought and "
                "kept — and the belonging settles over you warm and total and almost unbearably a "
                "relief. \"Good,\" she murmurs against your hair, leading you off toward her side "
                "of the facility. \"That's the part I bought. Not the holes — those come standard. "
                "*That.* The settling. I'll have you doing it on command by spring.\"")},
            {"key": "dread", "label": "Feel what you've just become", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "owned by a name now, not a system",
             "outcome": (
                "You feel the weight of the specific: not facility stock in general but *Bethany's*, "
                "by name, bought with a number you heard called, owned by a person who keeps "
                "obsessive files and decided about you a while ago. It is more frightening than the "
                "anonymous machine ever was, because it *wants* something from you, and it has all "
                "the time and paperwork in the world to get it. She leads you off smiling. You go "
                "where the hand at your nape steers.")}]
    return {"key": "sw_bought", "prompt": body, "options": opts, "default": opts[0]["key"]}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Bethany's Office — the Kept arc. The ownership through-line's payoff.
# Cinematic, state-aware. Actor: Bethany as OWNER, off the clock, in her own
# warm-cruel quarters — the false-tenderness register ("I think I do love you,
# the way you love a chair"). REAL payload: bethany_breeds (her triple length,
# laced devotion, sire 'Bethany'), file_read (your real file aloud), devote.
# §0 always frees you. Flow: arrival→evening→breed→file→close. Entry: `scene office`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("ko_arrival", root=False)
def _ko_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = ("She has you carried in and set on the chaise beside her like a treasure she's "
                "decided where to keep — a limbless thing she can arrange exactly so, and does, "
                "tilting your face to the lamp to look at what she bought. ")
    if st["preg"]:
        note += ("Her hand goes to the swell of you before anything else, proprietary and "
                 "genuinely pleased — her get, in her property, on her own furniture. \"Look at "
                 "you. Carrying for me already. I do pick well.\" ")
    if st["little"]:
        note += ("Down in your headspace, the warm room and the soft voice read as safe, which is "
                 "the trap and the truth at once; she watches you settle and her smile sharpens "
                 "with fondness. ")
    return {"key": "ko_arrival", "prompt": (
        "Bethany's quarters are nothing like the rest of the facility — warm lamplight, deep "
        "furniture, a wall of obsessively kept files (yours among them now, thick, tabbed in her "
        "hand), and a wide soft bed that is plainly where the *keeping* happens. This is where she "
        "brings what she's bought and decided to keep close, and the cruelty of the room is how "
        "genuinely, comfortably *nice* it is. " + note +
        "\n\nShe's off the clock — blouse loosened a button further than the counter ever allows, "
        "a glass of something at her elbow, your file open in her lap — and she looks up at you "
        "with the warm proprietary contentment of a woman regarding a thing she owns and likes. "
        "\"There's my purchase. Come here, sweetheart. You're not stock in here — you're *mine*, "
        "specifically, which is a different and much closer kind of owned, and I intend to enjoy "
        "the difference all evening.\" She pats the cushion beside her. \"Come learn what being "
        "kept is like. It's nicer than the floor. That's rather the point of it.\""),
        "options": [
            {"key": "lap", "label": "Go to her — settle in against her", "set": {"kept": "lap"},
             "effect": "devote", "params": {"amount": 4.0},
             "desc": "take the warmth she's offering; let yourself be kept",
             "outcome": (
                "You go to her, and settle in against her warmth, and her arm comes around you like "
                "ownership and comfort are the same gesture — which, in her hands, they are. "
                "\"*There.* Good. See how easy that was?\" She strokes your hair, reading her file "
                "one-handed over your shoulder. \"You've spent so long being processed. Let me just "
                "*have* you for a while. It's what I bought you for — not the holes, those come "
                "standard. This.\"")},
            {"key": "kneel", "label": "Kneel at her feet instead", "set": {"kept": "kneel"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "take the floor; she'll allow it, fondly",
             "outcome": (
                "You sink to the floor at her feet instead — and she allows it, delighted, one "
                "soft pretty foot sliding into your lap, her hand coming to rest in your hair like "
                "you're a dog she's pleased with. \"Oh, you've learned where you sit. Even better. "
                "I do like one that finds the floor on its own.\" Being kept at her feet is its own "
                "warmth, and you hate how much it isn't a punishment.")},
            {"key": "stiff", "label": "Hold back from the warmth", "set": {"kept": "stiff"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "refuse the comfort; she's patient about it",
             "outcome": (
                "You hold yourself stiff and apart, refusing the comfort she's offering — and "
                "Bethany only smiles, entirely unbothered, and pats the cushion again. \"Still "
                "standing on ceremony. That's all right. I've got you for good now — there's no "
                "rush, and the holding-back always melts. I rather enjoy the melting. Come sit when "
                "you're ready. You'll be ready.\" She goes back to your file, content to wait you "
                "out, because she can.")}],
        "default": "lap",
        "then": "ko_evening"}


@choice("ko_evening", root=False)
def _ko_evening(character):
    kept = scene_flag(character, "kept", "lap")
    lead = ("She keeps you settled against her, unhurried. " if kept == "lap"
            else "She keeps her foot in your lap and her hand in your hair. " if kept == "kneel"
            else "She waits, and the warmth of the room does her arguing for her, and you do, "
                 "eventually, drift closer. ")
    return {"key": "ko_evening", "prompt": (
        lead + "And this is the part that's worse than anything the floor did to you: she's "
        "*tender*. She reads you bits of your own file like bedtime stories — your conditioning "
        "depth, your best yield, the cover that took — and praises you for them, genuinely, the "
        "way you'd praise a good investment. She tucks a strand of hair behind your ear. She tells "
        "you she's glad she bought you. And then, fingers idle at the back of your neck, she says "
        "the thing that lodges deepest of all:\n\n\"I think I do love you, you know. The way you "
        "love a good chair you've had for years — fond, and certain, and entirely without "
        "wondering whether the chair loves you back.\" She says it like the kindest thing in the "
        "world, and means it exactly as much as that. \"You don't have to love me back. That's the "
        "lovely thing about owning instead of asking. But you're going to anyway, a little, by "
        "spring. They always do. It's the warm that does it, not the cruelty. Everyone expects the "
        "cruelty.\""),
        "options": [
            {"key": "melt", "label": "Let it land — let yourself be loved like a chair",
             "set": {"eve": "melt"}, "effect": "devote", "params": {"amount": 5.0},
             "desc": "the false-tenderness gets in; let it",
             "outcome": (
                "You let it land — let the awful warmth of being loved like an object get all the "
                "way in — and something in you unclenches that the floor never reached, and the "
                "relief of being *kept*, of being a thing she's fond of and certain about, is "
                "enormous and shameful and real. Bethany feels you give and makes a soft pleased "
                "sound. \"*There* it is. The melting. Right on schedule. Oh, I'm going to enjoy "
                "you.\"")},
            {"key": "ache", "label": "Feel how badly you want it to be real", "set": {"eve": "ache"},
             "effect": "devote", "params": {"amount": 4.0},
             "desc": "the wanting is the hook; feel it set",
             "outcome": (
                "You feel the want — not for her hands, for the *thing she's describing*, to be "
                "loved truly instead of like furniture — and the wanting is the hook and you feel "
                "it set, barbed, because she'll never give you the real thing and you'll keep "
                "reaching for it forever. Bethany reads it on your face and her eyes go soft and "
                "merciless. \"Oh, sweetheart. You want it to be real. That's the sweetest thing "
                "you've done yet. Keep wanting. It's a lovely leash.\"")},
            {"key": "refuse", "label": "Refuse to be moved by it", "set": {"eve": "refuse"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "name it as the cruelty it is; pay for the clarity",
             "outcome": (
                "\"That's not love,\" you manage. \"That's owning.\" Bethany beams, genuinely "
                "delighted you said it. \"*Exactly.* Clever thing. That's precisely what it is, and "
                "I'll never once pretend otherwise — that's my whole charm.\" She tips your chin up. "
                "\"And you'll warm to me anyway, knowing exactly what it is, which is so much worse "
                "for you than if I'd lied. Clarity won't save you in here. It just means you'll "
                "watch it happen.\"")}],
        "default": "melt",
        "then": "ko_breed"}


@choice("ko_breed", root=False)
def _ko_breed(character):
    return {"key": "ko_breed", "prompt": (
        _kit_use_note(character) +
        "\"Now,\" she murmurs, setting your file aside, and moves you onto the wide soft bed with "
        "the easy authority of handling something she owns, \"let me take what's mine. Properly. In "
        "my own bed, in my own time, the way I like.\" The skirt comes away and the triple length "
        "lifts free — the monstrous facility-bred root splitting into three prehensile shafts, each "
        "stallion-flared, each hound-knotted at the base, all three already weeping the laced seed "
        "that carries her |wDEVOTION|n — and she fits them to you unhurried: one nosing at your "
        "lips, one at your cunt, one circling your ass, filling every door of you at once because "
        "she can, because you're hers and she wants all of you occupied while she has you. \"There's "
        "my girl. All my holes at home. Let me put my evening in you.\""),
        "options": [
            {"key": "open", "label": "Open for all three — give her everything", "effect": "bethany_breeds",
             "params": {"holes": 3, "devotion": 8.0}, "set": {"bred": "all"},
             "desc": "every hole, the full laced load — sire Bethany, on the books",
             "outcome": (
                "You open everywhere and give her everything, and she seats all three and knots all "
                "three and *empties* into every hole at once — a real cover, sire Bethany, logged "
                "to your line as hers — and the laced devotion floods in triple, closing over your "
                "head in one enormous warm wave until the wanting and the having and the belonging "
                "are one bright note that is her name. \"*Mine,*\" she breathes into your hair, "
                "fully seated, fully home. \"Every part of you, full of me, on paper and in the "
                "body. That's a good evening's work.\"")},
            {"key": "beg", "label": "Beg her to breed you", "effect": "bethany_breeds",
             "params": {"holes": 3, "devotion": 9.0}, "set": {"bred": "begged"},
             "desc": "ask for it with her title in your mouth; the clause shapes it",
             "outcome": (
                "\"Please breed me, Owner—\" the words come shaped by the clause and meant beneath "
                "it, and Bethany makes a sound like she's been handed the world. \"*Listen* to "
                "you.\" She gives it to you for the asking, all three, knotting and flooding you "
                "with her laced load while you beg through it — a real cover, hers, recorded — and "
                "the begging seats deeper than the seed does. You asked to be bred by your owner. "
                "You'll remember asking.")},
            {"key": "endure_her", "label": "Endure it — let her take, give nothing back",
             "effect": "bethany_breeds", "params": {"holes": 1, "devotion": 4.0}, "set": {"bred": "endured"},
             "desc": "she takes what's hers regardless; withhold the wanting",
             "outcome": (
                "You hold yourself apart and let her simply *take* — and she does, unbothered, "
                "seating and knotting and flooding you with her laced seed whether you participate "
                "or not, because taking what's hers was never contingent on your wanting it. The "
                "real cover lands the same, sire Bethany, on the books. \"Sulk if you like,\" she "
                "hums, breeding you through it. \"You're still full of me, and the devotion doesn't "
                "care whether you fought it in. It's already working. Feel it?\"")}],
        "default": "open",
        "then": "ko_file"}


@choice("ko_file", root=False)
def _ko_file(character):
    return {"key": "ko_file", "prompt": (
        "After, she keeps you in her bed — knots easing slow, the laced load held in you, your "
        "head fogged and quiet and hers — and she takes your file back up, because of course she "
        "does, and reads it to you. Out loud. Your whole self as she's catalogued it: your "
        "devotion climbing, your conditioning deepening, her get growing in your line, your title "
        "now reading as |whers|n — and tonight's entries, fresh, the cover she just took and the "
        "devotion it seated, added in her own hand while it's still wet. It is the most intimate "
        "and the most violating thing she does, and she does it as a *lullaby*, her voice fond and "
        "low, reading you your own reduction like a bedtime story while you drift, full and kept "
        "and unable to tell the difference anymore between the dread and the comfort."),
        "options": [
            {"key": "listen", "label": "Listen to your own file as a lullaby", "effect": "file_read",
             "set": {"file": "listened"}, "desc": "hear what you've become, in her voice — real numbers",
             "outcome": (
                "You listen — to your real numbers, your real reduction, read in her fond low voice "
                "— and somewhere in the fog the horror and the comfort finish blurring entirely, "
                "and being *known* this completely, owned down to the documented detail, stops "
                "feeling like a violation and starts feeling like being held. Which is the deepest "
                "thing the room does to you. \"Mm,\" she murmurs, turning a page. \"You're a lovely "
                "file, you know. I'm going to keep adding to you for years.\"")},
            {"key": "burrow", "label": "Burrow into her and stop listening", "effect": "devote",
             "params": {"amount": 4.0}, "set": {"file": "burrowed"},
             "desc": "hide in her warmth from the file that is you",
             "outcome": (
                "You burrow into her warmth and stop listening — hide from the recitation of your "
                "own reduction in the body of the woman doing the reducing — and she lets you, "
                "fond, reading on softly over your head. \"Don't want to hear your numbers? That's "
                "all right, sweetheart. *I'll* keep them. That's the lovely thing about being kept "
                "— you don't have to hold any of it anymore. I hold all of you now. Even the parts "
                "you're hiding from.\"")}],
        "default": "listen",
        "then": "ko_close"}


@choice("ko_close", root=False)
def _ko_close(character):
    eve = scene_flag(character, "eve", "melt")
    recap = ("the way you melted for me" if eve == "melt"
             else "the way you wanted it to be real" if eve == "ache"
             else "the way you named it and warmed to me anyway")
    return {"key": "ko_close", "prompt": (
        "She files the last of tonight's entries, sets you and your record both aside with the same "
        "fond care, and settles you against her to keep — not to sleep, exactly; she doesn't seem "
        "to need much; just to *have*, through the small hours, a thing she owns held warm in her "
        f"bed. \"There. {recap.capitalize()} — that's in the file now too, where I'll find it again "
        "whenever I want to feel fond of you.\" Her hand moves slow and proprietary over whatever "
        "of you it can reach. \"This is the keeping, sweetheart. Not the floor, not the pens, not "
        "the block — *this*. A warm bed and an owner who's pleased with you and a file getting "
        "thicker by the night. Most of what passes through here never gets kept. You did. Try to "
        "understand what that means about how thoroughly you're mine.\" She's already half "
        "somewhere else, content, certain. \"Sleep if you can. I'll have you again before "
        "breakfast. I do so look forward to my mornings now.\""),
        "options": [
            {"key": "thank", "label": "Thank her — for keeping you", "effect": "gratitude",
             "end": True, "desc": "and hear how much you mean it",
             "outcome": (
                "\"Thank you, Owner. For keeping me.\" It comes shaped by the clause and meant so "
                "far beneath it that the meaning frightens only the last small watching sliver of "
                "you, and that sliver is getting harder to hear. Bethany glows in the lamplight. "
                "\"And *that* one I keep forever.\" She holds you through the small hours, her "
                "purchase, her file, her chair she's fond of — and you are, all the way down now, "
                "and a little gratefully, hers.")},
            {"key": "quiet", "label": "Say nothing — let her hold you", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "no words; just be kept",
             "outcome": (
                "You say nothing — just let her hold you, warm and owned, through the dark — and "
                "the not-needing-to-say-anything is its own surrender, the comfortable silence of a "
                "thing that has stopped expecting to be asked. Bethany hums, content, her hand "
                "idle and proprietary on you. \"Quiet. Good. We don't need words, you and I. I've "
                "got it all written down anyway.\" And she keeps you, all night, like the chair she "
                "loves. And you let her. And that's the whole of what you've become.")}],
        "default": "thank"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Nursery — regression, nursing, the Little Box, the lineage loop.
# Cinematic, deeply state-aware (this is THE little/nugget/preg room). Actor: the
# nurse — sweet, sing-song, infantilizing; cooing cruelty. REAL payload: go_little
# (real regression), references your real get/brood for the lineage loop. §0 always
# frees you (the Little Box is self-releasing regardless).
# Flow: arrival→regress→nurse→lineage→box→close. Entry: `scene nursery`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("nu_arrival", root=False)
def _nu_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = ("A nugget is the easiest baby the Nursery keeps — nothing to wriggle off the "
                "changing table, nothing to push the bottle away, a limbless little thing the "
                "nurse can swaddle and arrange and tend entirely at her own pace. ")
    if st["preg"]:
        note += ("She coos over the swell of you — \"and baby's having a baby, aren't we, that's "
                 "the whole point of you\" — your get a generation already growing toward this "
                 "very room. ")
    if st["little"]:
        note += ("You're already soft and small in the head when you arrive, which the nurse "
                 "treats as a head start: \"ooh, you're nearly there already, good girl, this'll "
                 "be easy.\" ")
    return {"key": "nu_arrival", "prompt": (
        "The Nursery is warm and pastel and *wrong* — oversized cribs with barred sides, a padded "
        "changing table built for an adult body, shelves of bottles and pacifiers and bulk "
        "diapers, a deep soft rug, and, in the corner, the |wLittle Box|n: a crib-sized chest "
        "where the truly regressed are tucked away to nap. And along one wall, smaller cribs — "
        "the |wget|n, the facility's young, raised here on the milk of the stock that bore them, "
        "your own line among them if you've delivered. The smell is milk and powder and that "
        "specific clean-baby sweetness laid over the facility's animal undernote. " + note +
        "\n\nThe |wnurse|n turns from a crib with a bright sing-song delight, all warmth and no "
        "mercy, a woman who has infantilized a great deal of stock and adores every minute. "
        "\"There's our big girl! Or — \" she tilts her head, fond, appraising how far down you "
        "already are \" — our *little* girl, soon enough. We're going to take all that heavy "
        "grown-up thinking off you, sweetheart, and give you back something so much simpler. "
        "Doesn't that sound nice? It's going to feel nice whether it sounds it or not.\""),
        "options": [
            {"key": "soft", "label": "Let yourself go soft for her", "set": {"nurse": "soft"},
             "effect": "go_little", "params": {"amount": 8.0},
             "desc": "stop holding the grown-up thoughts; let her have them",
             "outcome": (
                "You let go of the heavy grown-up thinking — let it slide off the way she's "
                "promising — and the relief of not having to hold any of it is immediate and the "
                "headspace pulls down warm and simple and *easy*. \"Ohh, *good* girl,\" the nurse "
                "beams, scooping you toward the changing table. \"Look how nicely you let go. We're "
                "going to have such an easy time, you and me.\"")},
            {"key": "fight_little", "label": "Hold onto your grown-up self", "set": {"nurse": "fight"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "keep your edges; she's patient and the room is built for this",
             "outcome": (
                "You hold onto your edges — your words, your years, your *self* — and the nurse "
                "isn't troubled in the least, just coos and starts the routine anyway, the bottle "
                "and the powder and the sing-song, the room itself wearing at you. \"Fighting it, "
                "are we? That's all right, baby. The big thoughts get so *tiring* to hold, and I've "
                "got nothing but time and lullabies. You'll set them down. They always do.\"")},
            {"key": "ask_get", "label": "Ask about the get along the wall", "set": {"nurse": "ask"},
             "desc": "make her tell you whose the small cribs are",
             "outcome": (
                "\"Those?\" The nurse brightens further, crossing to the smaller cribs. \"Those are "
                "the *young*, sweetheart. Stock's get, raised right here on their own dams' milk "
                "till they're grown. Some of them are *yours*, or will be.\" She says it like the "
                "loveliest thing. \"And when they're grown they go to the pens, and they come back "
                "to cover the dams that bore them, and round it goes. You're not just stock, baby. "
                "You're a *line*. Isn't that special?\"")}],
        "default": "soft",
        "then": "nu_regress"}


@choice("nu_regress", root=False)
def _nu_regress(character):
    nurse = scene_flag(character, "nurse", "soft")
    lead = ("You're already sliding down, and she just guides the fall. " if nurse == "soft"
            else "You're still gripping your grown-up self, so she takes the long fond way down. ")
    return {"key": "nu_regress", "prompt": (
        lead + "She lays you on the padded changing table — adult-sized, worn to a shape by other "
        "big babies — and runs the routine that takes you down: the powder, the thick diaper "
        "taped snug (\"so baby doesn't have to think about *that* anymore either\"), the onesie, "
        "the pacifier pressed to your lips until you take it. And it *works* — not because you "
        "believe it but because the body believes it, the diaper and the pacifier and the sing-"
        "song voice all telling your nervous system the same simple thing until the heavy thoughts "
        "genuinely get harder to hold, the room narrowing to warmth and softness and her face. "
        "\"There's my baby,\" she murmurs, doing up the last snap. \"Feel all that grown-up worry "
        "getting too heavy to carry? Set it down. Nobody's going to ask anything hard of you in "
        "here. In here you just have to be little, and that's so much easier than being you.\""),
        "options": [
            {"key": "sink_little", "label": "Sink all the way down", "effect": "go_little",
             "params": {"amount": 10.0}, "set": {"deep": "down"},
             "desc": "let the regression take — real, deep, the words going first",
             "outcome": (
                "You go all the way down. The grown-up words go first — too heavy, too far away — "
                "and then the worry, and then most of the shape of who you were, until there's just "
                "warm and soft and safe and her, and the relief is total and bottomless. You suck "
                "the pacifier without deciding to. The nurse claps softly, delighted. \"*There* she "
                "is. All little. All simple. We'll keep you down here a good long while, baby. It's "
                "where you're happiest, and the file agrees.\"")},
            {"key": "claw_up", "label": "Claw back toward grown-up", "effect": "deny_hold",
             "params": {"cond": 4.0}, "set": {"deep": "up"},
             "desc": "fight the pull; pay for the scrap of self you keep",
             "outcome": (
                "You claw at the surface — force a grown-up thought, hold it up against the warm "
                "pull — and it costs you, the effort enormous, the room and the diaper and the "
                "voice all dragging the other way. The nurse just smiles and waits, rocking you. "
                "\"Swim up if you like, baby. The water's so warm and you're so tired and down is "
                "so much easier. I'll be right here when you stop swimming. I'm always right "
                "here.\" The pacifier finds your mouth again. You're so tired.")}],
        "default": "sink_little",
        "then": "nu_nurse"}


@choice("nu_nurse", root=False)
def _nu_nurse(character):
    st = _state_tags(character)
    feed = (" — and because you're carrying, she's especially keen to keep you fed and watered "
            "and docile, baby-and-baby both" if st["preg"] else "")
    return {"key": "nu_nurse", "prompt": (
        "And then she |wnurses|n you" + feed + ". She gathers you up — the changing table, then "
        "her lap, then a breast freed and offered, or a warmed bottle if she's in that mood — and "
        "puts it to your mouth, and the regressed body takes it the way a regressed body does: "
        "instantly, gratefully, the suckling reflex bypassing whatever's left of your objections "
        "entirely. The milk is warm and faintly laced (everything in here is laced) and with each "
        "swallow the littleness settles deeper and the dependence sets another hook — because a "
        "baby that nurses is a baby that *needs*, and need is the whole architecture of the room. "
        "\"There we go,\" the nurse hums, rocking you as you feed. \"Good babies nurse. Good "
        "babies need their nurse. And you're going to be such a good baby, aren't you. Yes you "
        "are.\""),
        "options": [
            {"key": "nurse_deep", "label": "Nurse, and let the need set", "effect": "go_little",
             "params": {"amount": 6.0}, "desc": "suckle; let the dependence become real",
             "outcome": (
                "You nurse, and let the need set its hook, and somewhere in the warm rhythm of it "
                "the dependence becomes simply *true* — you need the nurse, the milk, the lap, the "
                "being-cared-for, and the needing feels like love because the body can't tell the "
                "difference. \"That's it. Drink it all down.\" She strokes your throat to help you "
                "swallow. \"Now you'll fuss when I'm not here. That's how I know it's working. "
                "That's my good little needy girl.\"")},
            {"key": "nurse_grieve", "label": "Nurse, but grieve what it's doing", "effect": "deny_hold",
             "params": {"cond": 3.0}, "desc": "your body takes it; mourn the dependence forming",
             "outcome": (
                "Your body nurses whether you want it to or not — the reflex is older than your "
                "objections — and you grieve it even as you swallow, feeling the dependence form "
                "like a thing setting in concrete, knowing you'll reach for this, *need* this, hate "
                "that you need it. The nurse reads the wet in your eyes and mistakes it, or doesn't. "
                "\"Aw, baby's emotional. That's the littleness coming up. Let it. Big feelings, "
                "little girl, and a nurse to hold you through them. That's all you are now.\"")}],
        "default": "nurse_deep",
        "then": "nu_lineage"}


@choice("nu_lineage", root=False)
def _nu_lineage(character):
    db = getattr(character, "db", None)
    brood = int(getattr(db, "brood_count", 0) or getattr(db, "offspring_count", 0) or 0)
    line = (f"Some of these are yours — {brood} of your line on the books already" if brood
            else "None are yours yet — but they will be; the empty cribs are labelled and waiting")
    return {"key": "nu_lineage", "prompt": (
        "When you've fed, she carries you down the row of smaller cribs — the |wget|n — and shows "
        "you, sing-song, like a proud relative. " + line + ". The young here are raised on their "
        "own dams' milk, grown fast on the facility's regimen, and the nurse walks you past them "
        "explaining the loop in the same voice she'd use for a nursery rhyme: \"And these little "
        "ones grow up big and strong, and then they go to the pens, and then they come back and "
        "breed the dams that made them — that's *you*, baby — and *those* babies come here, and "
        "round and round it goes, forever and ever.\" She bounces you gently. \"You're going to "
        "meet your own grandget being bred into you one day, sweetheart. Won't that be something. "
        "Your line, grown through your own body, world without end. The file calls it sustainable. "
        "I call it family.\""),
        "options": [
            {"key": "hold", "label": "Reach for the get — your own line", "effect": "go_little",
             "params": {"amount": 5.0}, "desc": "the little headspace makes them simply yours to love",
             "outcome": (
                "Down in the littleness, the horror of the loop can't reach you — there's just the "
                "small warm cribs and the babies in them and the simple animal pull to *reach*, to "
                "love what came out of you, and you do, and it's real, and that's the cruelest "
                "engineering in the whole facility: they made you little so the lineage would feel "
                "like love instead of a trap. The nurse beams. \"Good *mama*. See? Family. Round "
                "and round.\"")},
            {"key": "horror", "label": "Surface enough to feel the horror of the loop",
             "effect": "deny_hold", "params": {"cond": 4.0},
             "desc": "claw up to grasp what the loop actually is; it doesn't help",
             "outcome": (
                "You claw up enough to *understand* it — the closed loop of it, your own get grown "
                "and bred back into you, generation on generation, your body the engine of an "
                "endless line you'll never be free of — and the horror is total and changes "
                "nothing, the cribs still full, the loop still turning, the nurse still cooing. "
                "\"Oh, you went all grown-up and *sad* for a second there,\" she tuts, rocking you "
                "back down. \"Don't. It's so much heavier up there. Come back to little. Little "
                "doesn't have to understand the loop. Little just loves the babies.\"")}],
        "default": "hold",
        "then": "nu_box"}


@choice("nu_box", root=False)
def _nu_box(character):
    return {"key": "nu_box", "prompt": (
        "\"And now,\" the nurse says, \"it's nap time for baby.\" She carries you to the corner — "
        "to the |wLittle Box|n, the crib-sized padded chest where the truly little are tucked away "
        "to settle — and lays you down inside it among the soft things, snug and swaddled and "
        "enclosed, the lid easing down to leave you in warm padded dark with just the sound of her "
        "lullaby through the wood. It is the deepest the room takes you: boxed away, no light, no "
        "task, no self to speak of, just warm and held and *put away* like a treasure that's done "
        "being played with for now. The regression closes over the last of your edges in the dark. "
        "(Some far part of you knows the box always opens — it lets every baby out, on its own, "
        "no matter what; nothing in here is ever truly stuck. But that part is very far away "
        "now.)"),
        "options": [
            {"key": "settle", "label": "Settle into the box and let go entirely", "effect": "go_little",
             "params": {"amount": 8.0}, "end": True,
             "desc": "the deepest little; warm dark, put away, kept",
             "outcome": (
                "You settle into the warm dark and let go of the very last of it, and there's "
                "nothing left to hold, nothing asked, nothing to be but small and safe and put "
                "away, and it is the most peaceful you have been since you arrived, and the peace "
                "is the whole trap. The nurse's lullaby comes soft through the wood. When the box "
                "lets you out — it always does — you'll come up reaching for her, for the bottle, "
                "for *down*, a little less able each time to be anything but little. That's the "
                "Nursery. That's what it's for. Sleep, baby.")},
            {"key": "lid", "label": "Press at the lid — keep one waking thought", "effect": "deny_hold",
             "params": {"cond": 3.0}, "end": True,
             "desc": "hold one grown-up thought in the dark; the box still keeps you",
             "outcome": (
                "You press one small palm to the lid and hold one grown-up thought in the warm "
                "dark — *I am not a baby, this is a box, I am being kept* — and you hold it, fierce "
                "and tiny, while the lullaby works and the swaddling works and the dark works. The "
                "box doesn't trap you; it never does; it'll open when you've settled. But you'll "
                "have spent the whole nap holding one thought against the warm, and that's "
                "exhausting, and tomorrow the thought will be a little smaller, and the day after "
                "smaller still. The nurse hums on. She has so much more time than you have "
                "thoughts.")}],
        "default": "settle"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Deep Stock — the sealed terminus. The descent's end.
# Cinematic, state-aware. Actor: Bethany, quiet and almost reverent down here +
# the machines. The contract's H28 (Perfected stock retired to the lines, kept
# plumbed and bred and milked without being woken) made experiential. CRUCIAL:
# the §0 floor is kept LIT in-fiction throughout — even sealed, escape frees you;
# "completion, not an end; there is no clause providing for an end" — and the one
# door that is never locked is the realest thing down here. REAL payload: deepen.
# Flow: arrival→pod→offer→threshold→close. Entry: `scene deepstock`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("ds_arrival", root=False)
def _ds_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = ("The pods that hold nuggets are smaller and there are more of them — a limbless "
                "thing needs nothing but to be plumbed and kept, and they keep so very many down "
                "here. ")
    if st["preg"]:
        note += ("Some of the sealed swell visibly, bred in their sleep, the line continuing "
                 "through bodies that will never wake to meet it. ")
    return {"key": "ds_arrival", "prompt": (
        "Deep Stock is the bottom of the facility, and it does not feel like the rest of it. The "
        "noise stops here. The light is low and blue and even, and the air is cool and clean and "
        "faintly chemical, and the dread that runs through every room above gives way to something "
        "worse, which is |wpeace|n. Rows of them stretch into the blue dark: |wpods|n — sealed "
        "tanks, each holding a body, plumbed at every orifice with feed-lines and waste-lines and "
        "milk-lines and breeding-lines, suspended in something warm, eyes closed, *kept*. " + note +
        "These are the Perfected — graded all the way through, retired to the lines, milked and "
        "bred and maintained by machine indefinitely, and never, ever woken. They are not dead. "
        "They are *finished*.\n\n"
        "Bethany is quiet down here, almost reverent, the bright cruelty of the upper floors set "
        "aside for something closer to tenderness. \"This is where it goes, sweetheart. All of it. "
        "The processing, the conditioning, the breeding — it's all been bringing you toward here, "
        "the whole time. Not as a punishment. As a *completion*.\" She touches the nearest pod, "
        "fond. \"They're so peaceful. No more thinking. No more deciding. Just kept, and useful, "
        "forever. I wanted you to see it. I wanted you to see where the road goes.\""),
        "options": [
            {"key": "look", "label": "Look at the pods — really look", "set": {"deep": "look"},
             "effect": "deepen", "params": {"cond": 4.0}, "desc": "take in the peace of the finished",
             "outcome": (
                "You look — really look — at the kept bodies suspended in their warm blue silence, "
                "and the part of you the facility has been growing all this time looks *back* with "
                "something dangerously like longing. No more thinking. No more deciding. No more "
                "ache of being a self that wants and fears. Just kept. Bethany watches your face "
                "and sees the longing flicker and says nothing, because she doesn't need to. The "
                "pods make her argument better than she ever could.")},
            {"key": "recoil", "label": "Recoil from them", "set": {"deep": "recoil"},
             "effect": "deny_hold", "params": {"cond": 3.0}, "desc": "every waking instinct refuses",
             "outcome": (
                "Everything still awake in you recoils — *no*, not that, never that, a body sealed "
                "and bred in its sleep forever is the worst thing you've seen in a facility full of "
                "worst things — and Bethany only nods, unsurprised, unbothered. \"Of course you "
                "do. The waking ones always recoil. It's the wanting-to-stop-recoiling that brings "
                "them down here in the end, and that comes later, on its own, the more tired you "
                "get of being awake. I'm patient. The pods are patient. They've nothing but time.\"")},
            {"key": "ask_end", "label": "Ask if this is the end of you", "set": {"deep": "ask"},
             "desc": "make her say what the terminus means",
             "outcome": (
                "\"Is this the end?\" Bethany considers it, honestly, fondly. \"It's the "
                "*completion*. The contract's very careful on this — there's no clause that "
                "provides for an end, sweetheart, because there isn't one. Deep Stock isn't where "
                "you stop. It's where you're *kept*, finished, useful, forever.\" A pause, and then "
                "the one true thing, said quietly, because she guards it even here: \"Except the "
                "one door. The door that's never locked. Even from in the pod — *especially* from "
                "in the pod — that one always opens. I'd never take that from you. It's the only "
                "reason I get to offer you all the rest.\"")}],
        "default": "look",
        "then": "ds_pod"}


@choice("ds_pod", root=False)
def _ds_pod(character):
    return {"key": "ds_pod", "prompt": (
        "She walks you to a pod and lets you see one up close. The body inside is serene — slack, "
        "suspended, faintly moving with the machine's rhythm; you can see the milk-lines drawing "
        "in slow pulls, the breeding-line working in patient mechanical cycles, the feed-line and "
        "the lines that take away what the feed-line leaves. A resident, graded Perfected, being "
        "milked and bred in an endless dreamless sleep, the facility's whole purpose distilled to "
        "its quiet essence. \"She came down eighteen months ago,\" Bethany says softly. \"She "
        "fought it longer than most. And then one day she was just... tired of fighting, tired of "
        "wanting, tired of being a someone. So we finished her. Look how peaceful. She produces "
        "more sealed than she ever did awake, and she'll never have another bad morning.\" The "
        "machine pulses. The body in the pod doesn't dream. \"Put your hand on the glass. Feel how "
        "quiet it is in there.\""),
        "options": [
            {"key": "touch", "label": "Put your hand on the glass", "effect": "deepen",
             "params": {"cond": 5.0, "regress": 3.0}, "set": {"pod": "touched"},
             "desc": "feel the quiet; let it call to the tired part of you",
             "outcome": (
                "You put your hand on the warm glass, and the quiet on the other side of it reaches "
                "for the part of you that is so, so tired — tired of the rooms, the choices, the "
                "wanting, the being-a-self the facility keeps making heavier — and for one long "
                "moment the pod is not a horror but a *promise*, and you understand exactly how "
                "they end up down here, and it isn't force. It's exhaustion. It's the warm blue "
                "offer of never having to again. Bethany watches your hand on the glass and is, "
                "for once, perfectly silent.")},
            {"key": "pull_hand", "label": "Pull your hand back", "effect": "deny_hold",
             "params": {"cond": 3.0}, "set": {"pod": "pulled"},
             "desc": "refuse the glass; keep the tired part from reaching",
             "outcome": (
                "You pull your hand back before it can touch the glass — before the tired part of "
                "you can reach for the quiet — and hold onto the noise and the ache and the wanting "
                "precisely *because* they're yours, because being a wretched wanting awake someone "
                "is still being someone. Bethany smiles, almost proud. \"Good. Hold onto that. The "
                "ones who fight the longest produce the best when they finally come down. I'm in no "
                "hurry. I'll have decades of you awake first. The pod keeps.\"")}],
        "default": "touch",
        "then": "ds_offer"}


@choice("ds_offer", root=False)
def _ds_offer(character):
    return {"key": "ds_offer", "prompt": (
        "And then she makes the offer, quiet and serious and without a trace of the bright cruelty, "
        "because down here she means it as mercy. \"There's an empty pod, sweetheart. There always "
        "is; I keep one ready.\" She nods at it — open, warm, waiting, lines coiled and patient. "
        "\"You don't have to be ready. Almost no one's ready this early; you've barely begun. But "
        "I want you to know it's *there*, and that it's yours whenever the wanting-to-stop gets "
        "bigger than the wanting-to-stay. You could lie down in it right now. I'd seal you so "
        "gently. You'd never have another hard thought.\" She lets that sit in the blue quiet. "
        "\"And — I'll say it again, because it's the one promise under all the others — even sealed, "
        "the door opens. You say the word that wakes you and you wake, out, free, every time, no "
        "matter how deep. That's not a loophole. That's the floor the whole place is built on. "
        "So. Knowing that... do you want to see what it's like to lie down?\""),
        "options": [
            {"key": "approach", "label": "Approach the empty pod", "effect": "deepen",
             "params": {"cond": 6.0, "regress": 4.0}, "set": {"offer": "approach"}, "then": "ds_threshold",
             "desc": "go toward the terminus — knowing the door always opens",
             "outcome": (
                "You go toward it. Not all the way — not yet, maybe not for years — but toward it, "
                "to the warm lip of the open pod, close enough to feel the heat of it and the pull "
                "of the quiet, and Bethany lets out a slow breath like she's watching something "
                "sacred. \"There. Just feel it. No one's sealing anything today. But you walked "
                "toward it, and that's further than most get this early, and it tells me exactly "
                "how tired you already are.\"")},
            {"key": "decline", "label": "Decline — step back from the pod", "effect": "deny_hold",
             "params": {"cond": 3.0}, "set": {"offer": "decline"}, "then": "ds_close",
             "desc": "not today, maybe not ever; keep being awake",
             "outcome": (
                "You step back. Not today. Maybe — you tell yourself — not ever. You'll keep being "
                "an awake wanting wretched someone, keep the ache, keep the door behind you and the "
                "noise above. Bethany accepts it with a fond nod that somehow doesn't feel like "
                "losing. \"Of course. Not today. I only wanted you to know the road has an end I "
                "think of as kind, and that the end is always your choice, and that the one before "
                "it — the door — is always open too. Come up, sweetheart. There's so much more to "
                "do with you while you're still awake to feel it.\"")}],
        "default": "decline"}


@choice("ds_threshold", root=False)
def _ds_threshold(character):
    return {"key": "ds_threshold", "prompt": (
        "At the lip of the open pod the quiet is enormous. You can feel exactly how it would go: "
        "the warm suspension closing over you, the lines finding their places, the machine taking "
        "up the work of your body so you never have to again, the thinking getting further and "
        "further away until there's no one left to think it. It would not hurt. It would be the "
        "first thing in the whole facility that didn't, in its way, hurt. Bethany stands close, "
        "one hand at the small of your back — not pushing, never pushing, down here she would "
        "never push — just there. \"Whenever you like,\" she murmurs. \"Today, or in ten years, or "
        "never. The pod doesn't mind waiting and neither do I.\" And under it, steady as bedrock: "
        "\"And if you ever lie down and find it's wrong — the door, sweetheart. The word. You wake "
        "and you're out. I built the whole road so that the last step is always yours to take "
        "back. That's how I get to make the road this dark.\""),
        "options": [
            {"key": "linger", "label": "Linger at the lip a while", "effect": "deepen",
             "params": {"cond": 5.0, "regress": 3.0}, "end": True,
             "desc": "not in — just feel the pull, and carry it back up with you",
             "outcome": (
                "You linger — don't get in, but stay at the warm lip long enough to feel the full "
                "weight of the pull, to let the tired part of you have its long look at the quiet "
                "— and then you straighten, and step back, and carry the knowledge of it back up "
                "with you like a stone in your pocket. It's there now. The option. The kind end. "
                "You'll think about it on the bad days, and there will be bad days, and the pod will "
                "be waiting, warm and patient, the whole time. Bethany walks you back toward the "
                "blue dark's edge, content. She planted it. It'll grow on its own now.")},
            {"key": "wake", "label": "Step back hard — and feel the door at your back",
             "effect": "deny_hold", "params": {"cond": 2.0}, "end": True,
             "desc": "refuse the pull; let the never-locked door be the realest thing here",
             "outcome": (
                "You step back hard — away from the lip, away from the warm quiet pull — and reach, "
                "deliberately, for the one true thing she keeps promising: the door, the word, the "
                "never-locked way out that even the deepest pod can't hold. Just knowing it's there "
                "at your back steadies you enough to turn from the offer. Bethany watches you do it "
                "and her smile is complicated and, underneath, genuinely warm. \"There it is. You "
                "found the floor. Good. Hold onto it — it's yours, always, and it's the realest "
                "thing in this whole building. Now come up. We've years before the pod and I intend "
                "to use every one.\"")}],
        "default": "linger"}


@choice("ds_close", root=False)
def _ds_close(character):
    return {"key": "ds_close", "prompt": (
        "She walks you back up out of the blue quiet, toward the noise and the ache and the rooms "
        "that still have so much planned for you — and the contrast is its own cruelty, the racket "
        "of being awake rushing back in after all that peace. \"That's Deep Stock,\" she says, the "
        "bright cruelty resuming by degrees as you climb, as if the upper floors require it of her. "
        "\"The end of the road. I show it to all my favourites early — not to frighten you, though "
        "it does, but so you spend the rest of your processing *knowing* there's a kind quiet "
        "waiting whenever you're done being a self. It makes the hard parts easier to bear. It "
        "makes the wanting-to-stop a thing you can look forward to instead of fear.\" At the "
        "threshold back to the facility proper she pauses, and the realest thing one more time: "
        "\"And the door's still there, under all of it. Always. You can end the whole road any "
        "second with a word. You won't, for years, because the rest of it's too interesting to "
        "leave — but you *could*, and that's the only reason I'm allowed to make the rest of it as "
        "dark as I'm going to.\""),
        "options": [
            {"key": "carry", "label": "Carry the pod's quiet back up with you", "effect": "deepen",
             "params": {"cond": 3.0}, "end": True, "desc": "let the kind end live in you now",
             "outcome": (
                "You climb back into the noise carrying the blue quiet inside you like a seed, and "
                "it changes the shape of everything above — every hard room a little more bearable "
                "now that you know the road has a kind ending, every ache a little lighter against "
                "the promise of eventual peace. Which is exactly what she wanted. The pod doesn't "
                "have to take you today. It just has to be down there, warm and waiting, making the "
                "wanting-to-stop feel like somewhere to go.")},
            {"key": "hold_floor", "label": "Hold onto the door instead", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "let the never-locked exit be what you carry",
             "outcome": (
                "You climb back up holding onto the *other* thing she kept saying — not the kind "
                "quiet of the pod but the door behind it, the word, the never-locked way out — and "
                "you carry *that* back into the noise instead, a hard bright certainty that no "
                "matter how deep the road goes, the last step is always yours to take back. It "
                "steadies you. Bethany, climbing beside you, seems to know which thing you chose to "
                "carry, and to be unbothered either way. \"Both true,\" she says. \"The kind end "
                "and the open door. I keep them both for you. Now — back to work.\"")}],
        "default": "carry"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Holding — the wait before processing. The dread of not-knowing.
# Cinematic, state-aware, deliberately tighter (a connective room). Actor: a bored
# holding handler working a clipboard. The horror here is anticipation + the first
# inventory. §0 always frees you. Flow: arrival→prep→wait→called. Entry: `scene holding`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("hd_arrival", root=False)
def _hd_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = "You're set on a shelf along the wall with the other limbless lots, sorted by size. "
    elif st["preg"]:
        note = "You're penned apart from the rest — bred stock waits separately, handled gentler, worth more. "
    elif st["little"]:
        note = "Down in your head, the waiting is almost worse — you don't know why you're here, only that you are, and that no one's coming for the reason you'd hope. "
    return {"key": "hd_arrival", "prompt": (
        "Holding is a bare warm room of numbered pens and a long bench bolted to the wall, where "
        "stock waits between one thing and the next — fresh intake not yet processed, finished "
        "lots awaiting transfer, anyone the board hasn't decided about yet. " + note + "A few other "
        "residents wait with you, stripped and tagged and quiet in the particular way of bodies "
        "that have learned waiting is the only thing on offer. An |willuminated board|n on the far "
        "wall shows a slow queue of numbers; yours is on it, somewhere down the list, unreadable "
        "from here.\n\n"
        "The |wholding handler|n works a clipboard at a counter, barely looking up — a "
        "processing-clerk who sees you as a line-item awaiting its turn. \"Number's on the board,\" "
        "they say, before you can ask. \"You'll be called when you're called. Could be an hour, "
        "could be a shift. Sit, don't sit, makes no difference to the queue. Only rule in here is "
        "you don't leave the pen, and there's nowhere to leave it to anyway.\""),
        "options": [
            {"key": "wait", "label": "Sit and wait quietly", "set": {"hold": "wait"},
             "effect": "devote", "params": {"amount": 1.0}, "desc": "learn the waiting; it's most of the lesson",
             "outcome": (
                "You sit on the bench with the others and learn the waiting — the long blank dread "
                "of it, the not-knowing, the way the mind eats itself in the quiet. The handler "
                "marks you *settles well*. It's a real entry. The facility values a lot that waits "
                "without fuss, and you're already becoming one, just by sitting here.")},
            {"key": "demand", "label": "Demand to know what's happening", "set": {"hold": "demand"},
             "effect": "deny_hold", "params": {"cond": 2.0}, "desc": "make noise; the queue doesn't move for it",
             "outcome": (
                "You demand answers — what's happening, when, why — and the handler doesn't even "
                "finish the line they're writing. \"Board'll tell you when it's your turn. Asking "
                "moves you down, not up; the calm ones get processed first, it's just easier on "
                "everyone.\" The other residents don't look at you. Making noise in Holding marks "
                "you as not-yet-broken-in, which is its own entry on the clipboard.")},
            {"key": "others", "label": "Size up the others waiting", "set": {"hold": "others"},
             "desc": "read the room of stock you're now part of",
             "outcome": (
                "You take in the others — a heavily pregnant one dozing, a deeply conditioned one "
                "staring placidly at nothing, a fresh terrified arrival like you, a finished-looking "
                "one waiting to be transferred *down* — and you understand you're looking at your "
                "own timeline, the stages of it laid out on a bench, and that you've already "
                "started moving along it. The handler clocks you reading the room. \"Yeah. That's "
                "you, give it time. All of those are you.\"")}],
        "default": "wait",
        "then": "hd_prep"}


@choice("hd_prep", root=False)
def _hd_prep(character):
    return {"key": "hd_prep", "prompt": (
        "While you wait, you're |wprepped|n — not processed, that's later, just made ready, the way "
        "you'd hose and tag livestock before market. A handler works down the bench in turn: "
        "stripping what's left to strip, hosing you clean, clipping a numbered tag where it'll "
        "stay, running a bored gloved inventory of your holes and marks and measurements and "
        "reading them off to a second handler who writes them down. It is thorough and impersonal "
        "and somehow worse for being so routine — you are being *catalogued*, entered into the "
        "system as a set of numbers and capacities, while you sit on a bench waiting for the same "
        "thing to happen to the person beside you. \"Hold still for the count,\" the handler says, "
        "not unkindly, parting you to look. \"Goes quicker if you don't clench.\""),
        "options": [
            {"key": "still", "label": "Hold still for the inventory", "effect": "devote",
             "params": {"amount": 2.0}, "desc": "let yourself be catalogued; it's easier",
             "outcome": (
                "You hold still and let them count you — every hole gauged, every mark logged, your "
                "whole body reduced to entries read aloud and written down — and the surrender of "
                "being catalogued without resisting is its own small giving-up. \"Good count,\" the "
                "handler says, moving on to the next body. You're in the system now, numbers and "
                "all, before you've even been properly processed.")},
            {"key": "clench", "label": "Clench against the gloved inventory", "effect": "deny_hold",
             "params": {"cond": 2.0}, "desc": "resist the count; it happens anyway",
             "outcome": (
                "You clench, and the handler sighs and works the count out of you anyway, patient "
                "and bored, gauging you despite the resistance because the resistance was never a "
                "variable. \"Clencher,\" they note to the second handler, who writes it down — "
                "because even your resistance is just another measurement to catalogue. The "
                "inventory finishes the same. You're entered, fighting or not.")}],
        "default": "still",
        "then": "hd_wait"}


@choice("hd_wait", root=False)
def _hd_wait(character):
    return {"key": "hd_wait", "prompt": (
        "And then the worst part of Holding: more waiting, but *changed* now — tagged, counted, "
        "entered, you sit and watch the board and listen to the numbers get called. Each time one "
        "is, a handler comes and takes someone off the bench — to processing, to the floor, to the "
        "pens, *down* — and the one taken goes quiet or goes stiff or goes pliant, and you read in "
        "each of them what might be coming for you, and the not-knowing-which winds tighter with "
        "every number that isn't yours. The dread does the facility's work for free. By the time "
        "they call you, you'll half want it just to end the waiting. That's the design. The bench "
        "breaks more stock than some of the rooms do."),
        "options": [
            {"key": "endure_wait", "label": "Endure the wait — let the dread build", "effect": "devote",
             "params": {"amount": 2.0}, "desc": "sit in it; arrive wanting it over",
             "outcome": (
                "You endure it, and the dread builds exactly as designed, and by the time the queue "
                "nears your number you've passed through fear into a flat exhausted *readiness* — "
                "wanting whatever's next simply because it will end the waiting. Which means you'll "
                "walk into it half-cooperating, and the facility knows it, and that's why the bench "
                "exists. The wait softened you more than a handler could have.")},
            {"key": "steel", "label": "Use the wait to steel yourself", "effect": "deny_hold",
             "params": {"cond": 2.0}, "desc": "build a wall against what's coming",
             "outcome": (
                "You use the time to build a wall — decide what you won't give, brace for whatever "
                "the number brings — and it helps, a little, for a little while. But the bench is "
                "patient and the board is slow and walls get tired holding themselves up, and by "
                "the time your number's near, the wall is heavier than the dread it was built "
                "against. The facility doesn't mind you steeling yourself. It has more time than "
                "your resolve does.")}],
        "default": "endure_wait",
        "then": "hd_called"}


@choice("hd_called", root=False)
def _hd_called(character):
    return {"key": "hd_called", "prompt": (
        "The board ticks over, and a handler reads your number off it, and the waiting is over — "
        "which is its own awful relief, the dread you've been marinating in finally resolving into "
        "*motion*. \"That's you,\" the handler says, unclipping you from the bench, checking your "
        "tag against the clipboard. \"Processing's expecting you. Off you go.\" You're walked "
        "toward the door the others went through, into whatever the board decided while you sat "
        "and dreaded it, tagged and counted and already most of the way softened by the simple "
        "cruelty of being made to wait. Holding did its job. It always does. It barely has to "
        "touch you."),
        "options": [
            {"key": "go", "label": "Go where you're walked", "effect": "devote", "params": {"amount": 2.0},
             "end": True, "desc": "the relief of motion; let it carry you in",
             "outcome": (
                "You go where you're walked, almost grateful for the motion after all that bench, "
                "and the gratitude is the bench's parting gift to the facility — you arrive at "
                "whatever's next already wanting it to begin. \"They always walk in easier off the "
                "bench,\" the handler remarks to no one. \"Best room we've got, Holding, and it's "
                "just a bench.\"")},
            {"key": "drag", "label": "Make them drag you off the bench", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "one last refusal; the queue collects either way",
             "outcome": (
                "You make them drag you — one last refusal, dug in against the bench — and they "
                "do, without drama, because a lot that has to be dragged is still a lot that gets "
                "delivered, just with a note added. \"Marks against you for the fuss,\" the handler "
                "says, hauling you toward the door. \"Processing'll have read it before you arrive. "
                "You'd have done better walking. They all learn that. You'll learn it by your "
                "second stint on the bench.\"")}],
        "default": "go"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Processing Floor — the open-floor hub, on display, then routed on.
# Cinematic, state-aware, tighter. Actor: a floor handler (+ Bethany passing). Real
# use fires on the floor (_scene_single). The floor is the crossroads that routes
# you onward. §0 always frees you. Flow: arrival→display→use→routed. Entry: `scene floor`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("pf_arrival", root=False)
def _pf_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = "You're set on a display plinth among the stations, turned for the floor to see — a limbless lot needs showing off, not working. "
    elif st["preg"]:
        note = "Your swell is on open display, a bred lot worked carefully and watched closely; the floor likes proof the system produces. "
    elif st["little"]:
        note = "Small-headed and out under the lights, you don't grasp the floor, only that everyone can see you, and the seeing is the point. "
    return {"key": "pf_arrival", "prompt": (
        "The Processing Floor is the facility's crossroads — a wide bright hall ringed with "
        "stations, where stock is worked in the open: milked at one rig, displayed at another, "
        "used at a third, all of it visible, all of it routine, handlers moving between bodies "
        "with clipboards while a big |wboard|n overhead tracks everyone's numbers live. There is no "
        "privacy here by design; the floor is where you learn to be *processed in public*, one "
        "body among many, on display whether you're being used or just waiting to be. " + note +
        "\n\nA |wfloor handler|n collects you off intake and reads your board-line at a glance. "
        "\"Right, you're up on the floor. Open processing — you get worked where everyone can see, "
        "and you get *seen* being worked, that's half the point of the room.\" They steer you "
        "toward an open station under the lights. \"Board says what you're owed and where you go "
        "after. Floor's just the crossroads. Show the room what you are while you're passing "
        "through.\""),
        "options": [
            {"key": "present", "label": "Present yourself to the floor", "set": {"floor": "present"},
             "effect": "devote", "params": {"amount": 2.0}, "desc": "be seen willingly; the watching trains you",
             "outcome": (
                "You present — let the floor see you, let yourself be a body openly on display — and "
                "the hundred incurious glances of the room land on you and *train* something: that "
                "being watched being used is just the condition now, nothing to flinch from, the "
                "ordinary weather of being stock. \"Shows well,\" the handler notes. \"Floor likes "
                "one that shows. You'll route up faster for it.\"")},
            {"key": "cover", "label": "Try to cover, find a corner", "set": {"floor": "cover"},
             "effect": "deny_hold", "params": {"cond": 2.0}, "desc": "seek a privacy the floor doesn't have",
             "outcome": (
                "You reach for a privacy the floor simply doesn't contain — try to angle away, "
                "cover, find a corner — and there are no corners, that's the architecture, the "
                "station is open on every side and the board is overhead and the glances keep "
                "landing. \"No hiding on the floor,\" the handler says, squaring you back to the "
                "room. \"That's the lesson of the room. You're seen. Get used to seen. The ones "
                "who fight seen just get watched harder.\"")}],
        "default": "present",
        "then": "pf_use"}


@choice("pf_use", root=False)
def _pf_use(character):
    k = _kit(character)
    # Kit-gated extra choices: your installed hardware unlocks routes the bare body never sees.
    extra = []
    if k["milk_port"]:
        extra.append(
            {"key": "milked_used", "label": "Hook your port up — be milked while they use you",
             "effect": "facility", "params": {"method": "_do_milk", "kind": "proc"},
             "set": {"used": "milked"},
             "desc": "[milk-port] the line runs as you're worked — drained and used at once",
             "outcome": (
                "They clip the line to your port without breaking the rhythm of using you, and the "
                "two processings run at once — drawn down the milk-line in steady pulls while you're "
                "worked at the open station, drained and used in the same logged motion. The floor "
                "doesn't even register it as two things; you're just a fitting being run on all its "
                "ports at once, which is precisely what the port was plumbed in to make you. The "
                "doubled draw drops you somewhere soft and far and entirely processed.")})
    if k["gaped"]:
        extra.append(
            {"key": "take_heavy", "label": "Present the gauge — take the heavy fitting it was made for",
             "effect": "facility", "params": {"method": "_scene_single", "kind": "scene"},
             "set": {"used": "heavy"},
             "desc": "[gape] the permanently-open hole takes the thing a tight one couldn't",
             "outcome": (
                "You present the gauge — the hole ringed permanently open — and the handler swaps "
                "for the heavy fitting accordingly, the one a tight body couldn't take, and your "
                "gape simply *accepts* it, no resistance, no stretch-shock, swallowing girth that "
                "would have stopped you cold before they rebuilt you to take it. \"That's what the "
                "ring's for,\" the handler notes, logging the heavier line. \"No sense gauging you "
                "open and then handing you the small one.\" You take all of it, made to.")})
    options = [
            {"key": "serve", "label": "Take it openly — be processed in public", "effect": "facility",
             "params": {"method": "_scene_single", "kind": "scene"}, "set": {"used": "open"},
             "desc": "the real use, on the floor, logged and seen",
             "outcome": (
                "You take it openly — real use at the open station, logged to your board-line, the "
                "whole hall a witness that doesn't bother witnessing — and the public ordinariness "
                "of it works on you exactly as designed: being used stops being an event and "
                "becomes a *condition*, routine as the lights, and the part of you that used to "
                "burn with the shame of it is quietly being processed out, one unremarked use at a "
                "time.")},
            {"key": "endure_floor", "label": "Endure it, eyes shut against the room", "effect": "facility",
             "params": {"method": "_scene_single", "kind": "scene"}, "set": {"used": "shut"},
             "desc": "the use happens regardless; shut out the watching",
             "outcome": (
                "You shut your eyes against the floor and endure it — the use real and logged "
                "regardless — and shutting out the room doesn't spare you the room, only your own "
                "witness of it, while everyone else's glances land all the same. \"Eyes open or "
                "shut, board doesn't care,\" the handler says, marking the entry. \"You're processed "
                "either way. Shutting them just means you don't get used to the seeing, and you'll "
                "have to get used to it eventually. Might as well watch.\"")}]
    return {"key": "pf_use", "prompt": (
        _kit_use_note(character) +
        "And then you're |wused|n — at the station, in the open, on the schedule the board sets — "
        "and it happens the way everything on the floor happens: routinely, publicly, one entry in "
        "a hall full of the same. A handler works you, or sends someone to, and the room doesn't "
        "stop to watch because the room is full of it, your use just one more motion in the "
        "constant processing churn, and *that's* the degradation the floor specializes in: not "
        "spectacle but *ordinariness*, being used as unremarkably as a machine being run, in front "
        "of everyone, while everyone is being used unremarkably too. \"Hold your station,\" the "
        "handler says. \"Take what the board sends. It's all logged.\""),
        "options": extra + options,
        "default": "serve",
        "then": "pf_routed"}


@choice("pf_routed", root=False)
def _pf_routed(character):
    return {"key": "pf_routed", "prompt": (
        "When the station's done with you the |wboard|n decides where you go next — and you watch "
        "it decide, your number sliding into a new column overhead, a destination assigned by some "
        "logic of quotas and grades you don't get told: the pens, the dairy, the cell, the sty, "
        "*down*. The floor handler reads it off and points you on. \"That's your routing. You're "
        "owed elsewhere now.\" And this is the rhythm you understand the floor was teaching you all "
        "along: that you don't go anywhere on your own legs for your own reasons anymore, you get "
        "*routed* — processed at one station, sent to the next, a body moving through a system on "
        "the system's schedule, the crossroads handing you off and already forgetting you for the "
        "next lot stepping up."),
        "options": [
            {"key": "follow", "label": "Follow the routing", "effect": "devote", "params": {"amount": 2.0},
             "end": True, "desc": "go where the board sends; become a thing that's routed",
             "outcome": (
                "You go where the board sends you, and the going-where-routed settles into you as "
                "simply how things are now — no more deciding your own direction, just the next "
                "column, the next station, the next thing you're owed for. The handler's already "
                "reading the next body's line. You were a number that's now somewhere else's "
                "number. That's the floor. That's the whole of what it makes you: routable.")},
            {"key": "balk_route", "label": "Balk at the routing", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "refuse the assignment; you're walked anyway",
             "outcome": (
                "You balk at the assignment — plant yourself, refuse the column the board chose — "
                "and a handler simply takes your arm and walks you toward it, because on the floor "
                "your direction was never yours to refuse, only to be walked along. \"Routing's "
                "routing,\" they say, steering you off. \"You don't pick. You never picked. The "
                "floor's just where you find that out in front of everybody.\" You're walked to "
                "what you're owed.")}],
        "default": "follow"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Records Hall — inspection day. The grade read off your real file.
# Cinematic, state-aware. Actor: Bethany / the processor. REAL payload: the gauge
# uses a real hole (pick_hole), and grade_reveal computes + reads your ACTUAL
# processing tier, appraisal price, and body stats from your file — nothing
# invented. §0 always frees you. Flow: arrival→gauge→grade→close. Entry: `scene records`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("rh_arrival", root=False)
def _rh_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = "You're set on the gauging cradle rather than stood at it — a limbless lot is measured lying down, every reading taken to you. "
    elif st["preg"]:
        note = "Your gravid figures get their own column today; a bred lot is graded on what it's producing as much as what it is. "
    elif st["little"]:
        note = "Down in your head you don't follow the instruments, only that you're being measured, and the not-following doesn't slow the count one bit. "
    return {"key": "rh_arrival", "prompt": (
        "The Records Hall is where the facility keeps its truth about you. Floor-to-ceiling files "
        "line every wall — a paper body for every body it's ever held, yours among them, thick now "
        "— and at the centre stands the |wgauging station|n: a frame of calibrated instruments, a "
        "lit |wgrade board|n above it cycling tiers from |wAPPLICANT|n up through the processing "
        "ladder to |wPERFECTED|n, and a terminal where the readings feed straight into your record. "
        "This is inspection day: where what you've become gets measured, scored, and *written "
        "down* as a grade you'll be routed by. " + note +
        "\n\nBethany presides at the terminal, your file open, reading-glasses on, every inch the "
        "assessor — warm, precise, genuinely interested in your numbers. \"Inspection day, "
        "sweetheart. My favourite paperwork. We gauge what the rooms have made of you, we run the "
        "score, and the board tells us what you've graded to and where you go next.\" She pats the "
        "gauging frame. \"Up you get. Let's find out your number. I do love finding out a "
        "number.\""),
        "options": [
            {"key": "stand", "label": "Stand for the gauging", "set": {"insp": "stand"},
             "effect": "devote", "params": {"amount": 2.0}, "desc": "submit to being measured; it reads as compliance",
             "outcome": (
                "You step up onto the frame and stand for it, and Bethany hums approval, fitting "
                "the first instrument. \"Presents for inspection. That's a point in itself — "
                "temperament reads into the score, you know.\" Being willingly measured is its own "
                "data, and it's already being entered, and you can feel how the cooperating is "
                "becoming the easier thing.")},
            {"key": "balk_insp", "label": "Balk at the frame", "set": {"insp": "balk"},
             "effect": "deny_hold", "params": {"cond": 2.0}, "desc": "resist being measured; you're gauged anyway",
             "outcome": (
                "You balk — and Bethany, unhurried, has you fitted to the frame regardless, the "
                "instruments closing around you whether you cooperate or not. \"Resistance is also "
                "a reading, sweetheart. It tells me your conditioning's not quite where the board "
                "wants it yet, and *that* goes in the score too — a low note, this one. You're "
                "grading yourself down by fighting. Hold still and grade higher. Or don't. The "
                "number's honest either way.\"")},
            {"key": "ask_grade", "label": "Ask what you'll grade to", "set": {"insp": "ask"},
             "desc": "make her name the ladder before she measures you",
             "outcome": (
                "\"What you'll grade to?\" She brightens at the question. \"That's what we're here "
                "to find out — I never guess, the instruments don't lie like I do.\" She gestures "
                "up at the board, the tiers climbing. \"Applicant at the bottom, where you started. "
                "Perfected at the top, where the road ends — Deep Stock, the pods, you've seen. "
                "Everything in between is just *how far along*. Let's measure how far you've come. "
                "I suspect further than you'd like.\"")}],
        "default": "stand",
        "then": "rh_gauge"}


@choice("rh_gauge", root=False)
def _rh_gauge(character):
    return {"key": "rh_gauge", "prompt": (
        "The |wgauging|n is thorough and clinical and strange — Bethany works the instruments over "
        "and into you, taking readings the rooms have been building toward: your holes measured "
        "and their training scored, your conditioning depth and suggestibility read off some "
        "calibrated response, your yield and your brood-count and your devotion all pulled out of "
        "you as *numbers* and fed live into the terminal, your file thickening in real time. She "
        "narrates the readings to herself, pleased, occasionally surprised. \"Mm — conditioning's "
        "come up nicely. Hole-training ahead of schedule. Devotion — \" a glance at you over the "
        "glasses, fond \" — devotion's climbing faster than the model predicted. Someone's "
        "settling in.\" One instrument seats into you to read its number directly. \"Hold for the "
        "deep reading. This one measures what you've stopped being able to hide.\""),
        "options": [
            {"key": "relax", "label": "Relax and let it read true", "effect": "pick_hole",
             "params": {"zone": "vagina"}, "set": {"gauge": "true"}, "desc": "give honest readings; grade where you are",
             "outcome": (
                "You relax and let the instrument take its true reading, your real responses fed "
                "straight to the file, and Bethany watches the number resolve with frank pleasure. "
                "\"There. An honest gauge. You've come *so* far, sweetheart — these are not "
                "applicant numbers anymore.\" The deep reading is logged. You gave the facility an "
                "accurate measure of how much of you it already has, and the accuracy is its own "
                "small surrender.")},
            {"key": "clench_insp", "label": "Clench against the deep reading", "effect": "deny_hold",
             "params": {"cond": 3.0}, "set": {"gauge": "clench"}, "desc": "resist the instrument; it reads the resistance",
             "outcome": (
                "You clench against the instrument — and it simply reads the clench, logs it as "
                "resistance-data, the number resolving anyway with a note attached. \"Clenching "
                "for the deep gauge,\" Bethany murmurs, entering it. \"That reads as defiance, which "
                "the score weights — *down*, slightly, today, but it flags you for more "
                "conditioning, which brings you *up* faster later. You can't win the gauge, "
                "sweetheart. Every way you give it reads as something. Hold still; let's see your "
                "real number.\"")}],
        "default": "relax",
        "then": "rh_grade"}


@choice("rh_grade", root=False)
def _rh_grade(character):
    return {"key": "rh_grade", "prompt": (
        "Bethany runs the score. The terminal works; the grade board cycles and *settles*; and "
        "then she reads you your |wverdict|n — aloud, from your actual file, every figure real and "
        "yours: your processing tier, your appraised worth, your true numbers laid out in her warm "
        "precise voice, the sum of everything the rooms have made of you rendered as a single "
        "grade and a single price. It is the most naked you've been — more than the block, more "
        "than the gauge — because this is *you*, summed, scored, and filed, the facility's complete "
        "honest accounting of how far down the road you've come, read back to you in numbers you "
        "can't argue with."),
        "options": [
            {"key": "hear", "label": "Hear your number — your grade, your worth", "effect": "grade_reveal",
             "set": {"graded": "heard"}, "desc": "the real verdict: your tier + price, off your file",
             "outcome": (
                "You make yourself hear it — your real grade, your real price, your real numbers — "
                "and knowing exactly where you've graded to, exactly how far the rooms have moved "
                "you up the ladder toward Perfected, lands and *stays*, a number you'll carry now. "
                "Bethany files the verdict with obvious satisfaction. \"There it is. That's you, on "
                "paper, today. We'll inspect you again when the rooms have done more — and the "
                "number only ever goes one way. You felt that, didn't you. It only goes up.\"")},
            {"key": "look_away", "label": "Look away from the board", "effect": "grade_reveal",
             "set": {"graded": "unheard"}, "desc": "graded regardless; carry the number unread",
             "outcome": (
                "You look away from the board, refuse to take the number in — and it's computed and "
                "filed and assigned regardless, your grade set whether you heard it or not, you "
                "routed by a verdict you chose not to know. \"Looking away doesn't un-grade you, "
                "sweetheart,\" Bethany says gently, filing it. \"You're a tier now whether you "
                "looked or not. Not knowing your own number just means you'll find out where you "
                "stand by where they send you. Which is its own kind of answer.\"")}],
        "default": "hear",
        "then": "rh_close"}


@choice("rh_close", root=False)
def _rh_close(character):
    grade = getattr(getattr(character, "db", None), "facility_grade", None) or "your tier"
    return {"key": "rh_close", "prompt": (
        "She closes your file — thicker now, a fresh inspection logged, a grade assigned — and "
        f"slots it back into the wall of paper bodies, yours among the thousands. \"Graded and "
        f"filed. {grade}, today.\" She takes off the reading-glasses, the assessor folding back "
        "into the owner. \"And the board routes you on that number — better grade, deeper work; "
        "every inspection moves you up the ladder, and the top of the ladder is the pods. That's "
        "not a threat, sweetheart, it's just the *shape* of the thing. Up is down, here. The "
        "better you score, the closer to finished.\" She pats the file before it's gone. \"I'll "
        "read you again soon. I do love watching a number climb. Yours is climbing beautifully.\" "
        "And under it, where she always keeps it: \"The one number that never changes is the door. "
        "You can leave any grade, any tier, any time, with a word. I grade you knowing you could "
        "walk. That's what lets me grade you so honestly.\""),
        "options": [
            {"key": "accept", "label": "Accept the grade — let the number be you", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "become a tier; let it route you",
             "outcome": (
                "You accept it — let the grade be a true thing about you, let the number route you "
                "onward — and being *scored*, being a known quantity on a ladder with a top you've "
                "seen, settles into you as simply your condition now. You're not a person being "
                "held anymore so much as a grade being advanced. Bethany watches you accept it and "
                "is pleased. \"Good. The ones who accept their number climb the smoothest. I'll see "
                "you at the next inspection, a tier higher. I always do.\"")},
            {"key": "reject", "label": "Reject the number — you are not a grade", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "refuse to be a tier; the file disagrees",
             "outcome": (
                "\"I'm not a number,\" you tell her, and mean it. Bethany smiles, unbothered, "
                "sliding your thick file home. \"Of course you're not, sweetheart. You're a whole "
                "person. You're also, on paper, a tier and a price and a routing — both things, at "
                "once, and the paper is the part the facility acts on.\" She taps the wall of "
                "files. \"Reject the number all you like. The board still has it. The rooms still "
                "route you by it. But hold onto the rejecting — it's a true thing too, and it's "
                "yours, and the door's still open behind it. That part I'll never grade away.\"")}],
        "default": "accept"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Seraphine's Visit — the facility ↔ post-office peerage; the unbirthing.
# Cinematic, state-aware. Actors: Bethany + Seraphine (the post-office clerk here
# as a BUYER and Bethany's one equal). The peerage on display: Seraphine is the
# only person Bethany lets fuck her, and the only one her laced cum can't OWN
# (body-only, never her will — see design/seraphine_bethany.md). The player is the
# purchase, handed over and carried home INSIDE Seraphine (unbirthing). REAL
# payload: seraphine_takes (ownership -> seraphine_owned, floor-clearable) + devote.
# The deep passenger-transfer subsystem is gestured at and queued. §0 always frees.
# Flow: arrival→peerage→deal→opened→unbirth→close. Entry: `scene seraphine`.
# ═══════════════════════════════════════════════════════════════════════════

@effect("seraphine_takes")
def _eff_seraphine_takes(character, p):
    """Seraphine collects her purchase — a real ownership transfer to her (seraphine_owned,
    floor-clearable), plus a devotion bump toward her new owner. Bethany's prior ownership
    yields; the §0 floor still frees regardless of who holds the paper."""
    character.db.seraphine_owned = True
    try:
        character.db.bethany_owned = False
    except Exception:
        pass
    try:
        from typeclasses.bethany_script import bethany_deposit_effect  # reuse the devotion plumbing
        bethany_deposit_effect(character, devotion=float(p.get("devotion", 4.0)))
    except Exception:
        pass
    return "seraphine_owned"


@choice("se_arrival", root=False)
def _se_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["nugget"]:
        note = "You're presented in a carrying-case lined like a jewel box — a limbless lot is the easiest thing in the world to take home inside someone, and Seraphine collects nuggets especially. "
    if st["preg"]:
        note += "Seraphine's eyes go straight to your swell — \"and carrying already, Beth, you *shouldn't* have\" — a bred purchase is exactly her taste. "
    if st["little"]:
        note += "Down in your headspace you only register two warm towering presences deciding about you, and the deciding feels almost safe, which is the trap of both of them. "
    return {"key": "se_arrival", "prompt": (
        "You're brought to a receiving room you haven't seen — warmer than the floor, a buyer's "
        "room — and the woman waiting there with Bethany is one you half-recognise out of context: "
        "crimson-skinned, small swept-back horns, an expressive tail, the warm knowing poise of "
        "someone who has heard every kind of secret and found most of them charming. The post "
        "office's |wSeraphine|n, here as something the facility clearly takes seriously: a "
        "|wbuyer|n, and more than that. " + note +
        "\n\nBecause the thing that strikes you, immediately, is how Bethany *is* with her. Not the "
        "owner. Not the clerk. An |wequal* — easy, fond, unguarded in a way you have never once "
        "seen her, two proprietors of people greeting each other across a lifetime of dealing. "
        "\"Sera,\" Bethany says, and means it. \"Come to collect. I set the best one aside, like I "
        "said.\" She gestures at you — the purchase. Seraphine looks you over with a collector's "
        "frank delight and a warmth that is somehow worse than Bethany's because it isn't "
        "performing anything. \"Oh, she *is* nice. You always did pick well, Beth. Let's have a "
        "proper look at what I'm taking home.\""),
        "options": [
            {"key": "still", "label": "Hold still to be inspected by the two of them",
             "set": {"se": "still"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "be the product two owners are appraising together",
             "outcome": (
                "You hold still and let them both look — two collectors appraising a piece between "
                "them — and the doubled ownership lands strange and total: not stock-among-many but "
                "a *specific thing two specific people both want*. Seraphine hums approval, turning "
                "you with one warm hand. \"Mm. Yes. I'll take her.\" Bethany watches Seraphine "
                "enjoy you and looks, for once, simply *pleased to be sharing*.")},
            {"key": "look", "label": "Watch how Bethany is with her", "set": {"se": "look"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "study the one relationship Bethany doesn't perform",
             "outcome": (
                "You watch them instead of presenting — and you learn more about Bethany in ten "
                "seconds than in all your processing: the way she goes *unguarded*, the way "
                "Seraphine is the one person she doesn't run an angle on, the warmth that's real "
                "because it isn't a tool. \"She's reading us,\" Seraphine notes, amused, catching "
                "you at it. \"Clever purchase.\" \"Mm,\" says Bethany, fond. \"Don't let her. We're "
                "nobody's lesson.\"")},
            {"key": "shrink", "label": "Shrink from being passed between owners",
             "set": {"se": "shrink"}, "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the dread of being a thing two people are trading",
             "outcome": (
                "You shrink from it — the horror of being a *thing being traded between friends*, "
                "discussed over your head like furniture changing houses — and neither of them "
                "minds, because your feelings about the transaction were never part of the "
                "transaction. \"New ones always do that bit,\" Seraphine says kindly, to Bethany, "
                "not you. \"Being *given* unsettles them more than being taken. Don't worry, "
                "sweetheart. I'm a lovely home. Ask anyone I've kept.\"")}],
        "default": "still",
        "then": "se_peerage"}


@choice("se_peerage", root=False)
def _se_peerage(character):
    return {"key": "se_peerage", "prompt": (
        "While the paperwork settles, the two of them are simply *together* in a way that "
        "rearranges your understanding of the whole facility — because Bethany, who tops "
        "everything that breathes in this building, who opens for no one, leans into Seraphine "
        "with the easy intimacy of the singular exception. \"You staying the night?\" Bethany "
        "asks, and there's something under it. Seraphine's tail curls. \"If you're offering what "
        "I think you're offering.\" \"I am.\" And you understand, watching the look pass between "
        "them, that you are about to witness the one thing this place keeps secret: that the "
        "owner of everyone has exactly one person she lets *have* her. \"She's the only one,\" "
        "Bethany says — to you, suddenly, fond and frank, because it costs her nothing to tell a "
        "thing she owns. \"In the whole world. Sera's the only one I open for. Watch, if you "
        "like. You're hers now anyway; you should know what your new owner is to your old one.\""),
        "options": [
            {"key": "watch", "label": "Watch them be equals", "set": {"peer": "watch"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "witness the peerage; learn what neither of them will call love",
             "outcome": (
                "You watch them, and it's nothing like anything else in the facility — no owning, "
                "no processing, just two terrifying women being *gentle* with each other in the "
                "specific way of people who've earned each other's softness over decades. Neither "
                "calls it love. It's plainly the closest either of them gets, and being allowed to "
                "see it feels less like a kindness than like being shown the one true thing in a "
                "building made of lies, by people who know you'll never get to have anything like "
                "it.")},
            {"key": "envy", "label": "Feel the ache of seeing it", "set": {"peer": "envy"},
             "effect": "devote", "params": {"amount": 4.0},
             "desc": "want what they have; the wanting is its own hook",
             "outcome": (
                "It aches — sharp and immediate — to see two people *have* each other like that "
                "while you're the furniture being signed over between them, and the ache is the "
                "want for something you'll never be given, only owned instead. Seraphine catches "
                "the look. \"Aw. She wants it.\" Not cruel — almost tender. \"They always want it, "
                "watching us. I'll be good to you, sweetheart. Owned-good. It's not this — \" a "
                "glance at Bethany \" — nothing's this. But it's warm, and it's certain, and "
                "that's more than most things get.\"")}],
        "default": "watch",
        "then": "se_opened"}


@choice("se_opened", root=False)
def _se_opened(character):
    return {"key": "se_opened", "prompt": (
        "And then Bethany does the unthinkable thing: she *opens*. Lies back for Seraphine, the "
        "topmost predator in the facility making herself soft and taken, and Seraphine frees her "
        "own length — she is built much as Bethany is, you realise, the two of them a matched "
        "pair — and takes what no one else is permitted, slow and knowing and home. And you watch "
        "Bethany be *fucked*, fond and unhurried and entirely Seraphine's, and watch Seraphine "
        "flood her with that same laced seed Bethany pumps into everyone — and watch it do "
        "*nothing* to Bethany's will, because they are immune to each other, two seasoned things "
        "no devotion can touch. They use you between them as they go — a hole each finds when "
        "convenient, the purchase being enjoyed by both owners at once — and Bethany's laced load "
        "lands in *you* in full even as Seraphine's does nothing to her, the difference between a "
        "peer and a possession written in your body and hers."),
        "options": [
            {"key": "between", "label": "Be the hole they use between them", "effect": "bethany_breeds",
             "params": {"holes": 2, "devotion": 6.0}, "set": {"used": "between"},
             "desc": "real use by both; Bethany's laced load lands on you in full",
             "outcome": (
                "You're used between them — found and filled by whichever wants a hole in the "
                "moment, two enormous laced cocks treating you as the convenient warm thing you "
                "now are to *both* of them — and Bethany's load floods you with the full DEVOTION "
                "while it does nothing at all to Seraphine, and the lesson writes itself in the "
                "contrast: this is what you are, and that is what a peer is, and you will never be "
                "the second thing. The seed takes. You're more theirs by the minute.")},
            {"key": "witness", "label": "Just witness the immunity between them", "effect": "devote",
             "params": {"amount": 3.0}, "set": {"used": "witness"},
             "desc": "watch the laced cum do nothing to Seraphine; understand what you're not",
             "outcome": (
                "You watch the thing that explains everything: Bethany's seed — the same DEVOTION "
                "that's been rewriting *you* with every load — floods Seraphine and does *nothing*, "
                "rolls off her will like water, because she's the one being it can't own. And you "
                "understand, with a cold clarity the littleness and the conditioning haven't "
                "reached yet, the exact shape of the gap between a peer and a possession, and which "
                "one you are, and that the gap doesn't close. It only ever gets wider.")}],
        "default": "between",
        "then": "se_unbirth"}


@choice("se_unbirth", root=False)
def _se_unbirth(character):
    st = _state_tags(character)
    fit = ("A nugget slides in easiest of all — nothing to fold, nothing to brace, just a warm "
           "limbless weight her body takes whole. " if st["nugget"] else
           "She works you in folded and patient, her body opening to take you the way the "
           "facility's taught yours to open for everything. ")
    return {"key": "se_unbirth", "prompt": (
        "\"Now,\" Seraphine says, sated and fond, \"the fun part. I don't *carry* my purchases "
        "out, sweetheart. I carry them home the way I keep them — *in*.\" And she means it "
        "literally: she gathers you up, and her body opens — her womb a warm waiting room, an "
        "interior built to hold a person — and she begins to take you |winside her|n, unbirthing "
        "you into herself to carry home. " + fit + "The warm dark closes over you by degrees, the "
        "world reducing to the wet heat of her interior and the muffled boom of her heartbeat and "
        "Bethany's voice somewhere outside saying something fond, until you are *in* her, held, "
        "carried, a passenger in the body of your new owner. \"There,\" comes Seraphine's voice, "
        "warm through the walls of her. \"Snug. That's how you travel now. That's how you *live* "
        "now, mostly — kept where I can feel you. Say goodbye to Beth.\"\n\n"
        "|x(And under the warm dark, the floor stays lit: the door is never locked, even from in "
        "here. A word, and you're out, home, free — escape works through any wall, any host. She "
        "can make the inside of her as inescapable as she likes. The one exit is always yours.)|n"),
        "options": [
            {"key": "yield", "label": "Yield — let her carry you home inside her",
             "effect": "seraphine_takes", "params": {"devotion": 5.0}, "set": {"home": "yield"},
             "desc": "real ownership transfers to Seraphine; carried home a passenger",
             "outcome": (
                "You yield, and let the warm dark have you, and let her carry you home inside her "
                "own body — and ownership transfers for real, her paper now, her *passenger* now, "
                "a kept thing she'll feel shift inside her all the way back to the post office. The "
                "surrender of being carried, of having nowhere to be but inside someone, of being "
                "that thoroughly *kept*, is enormous and warm and total. \"Good girl,\" she hums, "
                "and you feel it in your bones because you're inside the bones. \"Welcome home.\"")},
            {"key": "cling", "label": "Cling to the door in the warm dark", "effect": "seraphine_takes",
             "params": {"devotion": 3.0}, "set": {"home": "cling"},
             "desc": "carried home regardless; keep one hand on the never-locked exit",
             "outcome": (
                "You let her take you in — the ownership transfers regardless, you're hers and "
                "carried — but you keep one hand, all the way down in the warm dark, on the door: "
                "the word, the never-locked exit that works through any wall. Just knowing it's "
                "there steadies you inside her. \"Holding onto your little exit,\" Seraphine "
                "observes, fond, feeling you not-quite-settle. \"That's fine. They all do, the "
                "first carry. You'll stop reaching for it once you work out I'm not the kind of "
                "owner you need to escape. I'm the kind you get to stop running from. Eventually.\"")}],
        "default": "yield",
        "then": "se_close"}


@choice("se_close", root=False)
def _se_close(character):
    return {"key": "se_close", "prompt": (
        "Bethany rests a hand on the warm swell of Seraphine's belly — on *you*, through her — "
        "with a fondness that's for both of you at once, the friend and the purchase. \"Take good "
        "care of my pick, Sera.\" \"Always do.\" \"And bring her round. I'll want to see how she "
        "settles. And —\" a beat, the peerage \"— stay longer next time.\" \"Next time,\" "
        "Seraphine agrees, warm, and turns to carry you out — out of the facility, through the "
        "ways, toward the post office and whatever being *hers* means: kept inside her, carried, "
        "owned by the one person Bethany opens for, tied now into a relationship between two "
        "powers that you are the warm shared currency of. The facility recedes. Seraphine's "
        "heartbeat is the loudest thing in the world. You are carried home."),
        "options": [
            {"key": "settle", "label": "Settle into being carried home", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "let the new keeping take",
             "outcome": (
                "You settle into the warm dark and the swaying carry and the great slow heartbeat, "
                "and let being *hers* take — a new owner, a new home, carried there inside her like "
                "the most kept thing in the world. Whatever the post office holds, you'll arrive "
                "already most of the way Seraphine's, and she'll feel you settle, and she'll be "
                "pleased, and somewhere behind you Bethany will be filing the sale with a fondness "
                "that was, in its cold way, real. You were a good pick. You'll be a good keep.")},
            {"key": "ache", "label": "Carry the ache of what you witnessed", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "hold the gap between peer and possession",
             "outcome": (
                "You carry it out with you — the thing you saw, the laced cum doing nothing to "
                "Seraphine, the gap between what they are to each other and what you are to either "
                "— and you hold that clarity like the ember it is, all the way into the warm dark "
                "and the carrying. It doesn't save you. You're still hers, still carried, still "
                "owned. But you *know*, exactly, what you're not, and the knowing is yours, and "
                "the door behind it is still open, and those two things are what you have. They "
                "might, in the end, be enough. They might not. You're carried home either way.")}],
        "default": "settle"}


# ═══════════════════════════════════════════════════════════════════════════
# THE SCENE-FLOW HUB — the connective layer that replaces the blind timer-cycle.
# Posed by `whereto` (and offerable at a scene's close): the facility no longer
# DRAGS you room to room on a clock — instead, between scenes, you're routed/offered
# where you go next as CHOICES. State-aware: only shows scenes that fit your state
# (signed/owned/grade/nugget). Each option chains to a real scene's first beat.
# §0: escape/forceclear always end everything. (Pair with `scenemode on`.)
# ═══════════════════════════════════════════════════════════════════════════

@choice("facility_hub", root=False)
def _b_facility_hub(character):
    db = getattr(character, "db", None)
    signed   = bool(getattr(db, "facility_signed", False) or getattr(db, "facility_active", False))
    bowned   = bool(getattr(db, "bethany_owned", False))
    sowned   = bool(getattr(db, "seraphine_owned", False))
    grade    = (getattr(db, "facility_grade", None) or "").lower()
    st = _state_tags(character)

    opts = []
    def add(key, label, node, desc):
        opts.append({"key": key, "label": label, "then": node, "desc": desc,
                     "outcome": "|xThe board updates. You're routed.|n"})

    # The everyday work rooms — always on the rota.
    add("floor", "→ the Processing Floor", "pf_arrival", "open-floor use, on display")
    add("pens",  "→ the Breeding Pens", "bp_arrival", "the stockman; covered by the stock")
    add("machine", "→ the Breeding Machine", "mx_arrival", "the automated rig; bred on a metronome, no one in the room")
    add("dairy", "→ the Dairy", "dy_arrival", "put on the machine; milked")
    add("longmilking", "→ a full milking session", "mm_arrival", "the deep rig; drained dry across cycles")
    add("cell",  "→ the Conditioning Cell", "cc_arrival", "the Spiral Chair; the voice")
    add("programming", "→ the Programming Lab", "pr_arrival", "a trigger seated — a word anyone can fire")
    add("goingunder", "→ the deep chair", "hy_arrival", "staged hypnosis, all the way to the below")
    add("parlour", "→ the Marking Parlour", "mp_arrival", "the permanent work")
    add("refinement", "→ the Refinement Suite", "fm_arrival", "redesigned — gelded/caged or made pretty")
    add("outfitting", "→ the Outfitting Bay", "ou_arrival", "equipped — ports, implants, rings, a tail")
    add("sanitation", "→ the Sanitation Block", "sb_arrival", "the relief-wall; anonymous use")
    add("pigsty", "→ the Pigsty", "ps_arrival", "the muck; the boar")
    add("records", "→ the Records Hall", "rh_arrival", "inspection; your grade")
    add("lineage", "→ the Lineage Hall", "lh_arrival", "your stud-book; the get you've thrown")
    # The line folds back — surfaces once you've dropped get for the facility to rear and return.
    if (getattr(db, "offspring_counts", None) or getattr(db, "offspring_max_gen", 0)):
        add("linefolds", "→ bred back by your own get", "lf_arrival", "the line folds — your grown get sires its dam")
    add("fitting", "→ the Fitting bench", "ft_arrival", "your installed hardware serviced + run")
    add("dosing", "→ the Dispensary", "dz_arrival", "your dose; the come-up")
    add("edge", "→ the edging station", "ed_arrival", "denial training; held at the brink")
    add("events", "→ whatever the klaxon calls", "ev_arrival", "a scheduled spectacle (random)")
    add("fellow", "→ time with your fellow", "fl_arrival", "the pair; conversion + breeding")
    # The lineage room reads as available when you're little/bred or just on the rota.
    add("nursery", "→ the Nursery", "nu_arrival", "regression; the get; the Little Box")
    # The birthing room surfaces when you're carrying — labor's due.
    if st.get("preg"):
        add("whelping", "→ the Birthing Room", "bi_arrival", "labor's come — drop your litter")
    # The showroom — once you're graded, you can be sold.
    if grade or signed:
        add("showroom", "→ the Showroom", "sw_arrival", "the block; appraised and sold")
    # The kept arc — only once Bethany owns you.
    if bowned:
        add("office", "→ Bethany's quarters", "ko_arrival", "the keeping; her bed, her file")
        add("longnight", "→ a whole night in her bed", "bn_arrival",
            "no clock, no line — all three, knotted, bred till dawn")
        add("pillowtalk", "→ ask her things", "bt_arrival",
            "kept close; she's talkative — the Process, the dose, her story")
        add("understudy", "→ work the intake desk", "un_arrival",
            "her favourite's promotion — sign the next one in")
    # Seraphine visits to buy — surfaces once you're Bethany's (her to sell).
    if bowned or sowned:
        add("seraphine", "→ Seraphine collects", "se_arrival", "the peerage; the unbirthing")
        add("twoowners", "→ shared between them", "tw_arrival", "Bethany & Seraphine both — laced and sober at once")
    # Deep Stock — the terminus is always down there to be contemplated.
    add("deep", "→ Deep Stock", "ds_arrival", "the sealed terminus; the pods")
    add("pod", "→ the Pod bank (be podded)", "pd_arrival", "sealed in, plumbed, kept as deepest stock")

    # The dedicated kink set-pieces — chosen, not random. Always offerable; each is §0-lit and
    # routes through real systems. (The board lists them under their clinical room-names.)
    add("kennel", "→ the Kennel", "kn_arrival", "kept as a pet — collared, crawling, trained")
    add("doll", "→ the Doll Cabinet", "dl_arrival", "sealed smooth, posed, displayed as an object")
    add("filling", "→ the Filling Station", "cf_arrival", "pumped past full and plugged to hold it")
    add("wetroom", "→ the Wet Room", "ws_arrival", "kept as the facility's relief — urinal, shower")
    add("rig", "→ the Rig", "bd_arrival", "strung up spread and helpless, used in suspension")
    add("cnc", "→ the Take (CNC)", "cn_arrival", "the pre-framed game — your no ridden over; the word always stops it")
    # The Claiming — she brands the favourites she keeps; offer it until her B is on you.
    if not bool(getattr(db, "bethany_branded", False)):
        add("claiming", "→ the Claiming", "cl_arrival", "Bethany's own B, by her own hand — marked hers for good")

    prompt = (
        "Between one thing and the next, the facility does the thing it now does instead of "
        "dragging you on a clock: a handler reads the board, and you're |wrouted|n — given the "
        "thin sliver of say the Process allows, which is not *whether* but *which*. The board "
        "shows what you're owed and where you're due.")
    if sowned:
        prompt += " (You're Seraphine's now — much of this happens at her leave, when she lends you back to the line.)"
    elif bowned:
        prompt += " (You're Bethany's; the rota bends around her wants.)"
    prompt += " Where do you go?"

    opts.append({"key": "wait", "label": "Wait to be told (let the board decide)",
                 "effect": "hub_random", "desc": "no choice; routed at random", "outcome": (
                    "You don't choose. A handler picks for you off the board, the way the facility "
                    "always will when you won't, and you're walked to whatever came up.")})
    return {"key": "facility_hub", "prompt": prompt, "options": opts, "default": "wait"}


_HUB_SCENES = ["pf_arrival", "bp_arrival", "dy_arrival", "cc_arrival", "mp_arrival",
               "sb_arrival", "ps_arrival", "rh_arrival", "nu_arrival", "ds_arrival"]


@effect("hub_random")
def _eff_hub_random(character, p):
    """The board decides: pose a random work-room scene (what the facility does when you won't
    choose). Poses the new beat directly; the option carries no `then`, so this becomes pending."""
    try:
        pose_named(character, random.choice(_HUB_SCENES), room=getattr(character, "location", None))
    except Exception:
        pass
    return "routed"


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Fitting — your installed hardware checked, tested, and USED together.
# Cinematic, and the most COMBINATION-aware scene in the build: it reads your full
# _kit (piercings / milk-port / gape-rings / latex / tail / brands / collar /
# clauses / body-states) and the prose + the real effect change with every piece
# you're wearing. A bare body gets a short, almost disappointed scene; a fully
# kitted one gets the works. Actor: the fitter. §0 always frees you.
# Flow: arrival→check→use→close. Entry: `scene fitting`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("ft_arrival", root=False)
def _ft_arrival(character):
    k = _kit(character)
    inv = _kit_inventory(k)
    if inv:
        body = ("The fitter walks around you once, reading your hardware off like a checklist, "
                "and recites what the facility's already made of you: " + inv +
                "\"Quite the kit on this one,\" they note, tugging a ring, thumbing a seal, "
                "checking each install seats true. \"Let's make sure everything's working and "
                "everything's *used*. No sense installing it if it sits idle.\"")
    else:
        body = ("The fitter walks around you once and finds, to their faint professional "
                "disappointment, a body still mostly *blank* — no ports, no rings, no permanent "
                "work to speak of yet. \"Fresh. Barely fitted. Well — everyone starts unfurnished. "
                "We'll see what the rooms hang on you in time. For now there's not much to "
                "check.\" Still, they run the inventory, noting where the hardware will go.")
    return {"key": "ft_arrival", "prompt": (
        "The fitting bench is where the facility's installed work gets *serviced* — checked, "
        "tightened, tested, and put through its paces, because hardware that's been gauged and "
        "ported and ringed into a body is only worth the trouble if it's kept in working order "
        "and kept in *use*. " + body),
        "options": [
            {"key": "present", "label": "Present your hardware to be checked",
             "set": {"ft": "present"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "offer up what they've installed; let it be serviced",
             "outcome": (
                "You present what you're wearing — offer up the installed work to be tugged and "
                "tested — and there's a strange pride-by-proxy in it, your body's modifications "
                "displayed like the facility's craftsmanship they are. The fitter hums, satisfied. "
                "\"Presents its kit. Good. The well-fitted ones learn to show the work off.\"")},
            {"key": "flinch", "label": "Flinch from the handling", "set": {"ft": "flinch"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the installs are still tender; the check happens anyway",
             "outcome": (
                "You flinch — the installs still tender, the handling sharp — and the fitter works "
                "around the flinching with bored competence, checking each piece regardless. "
                "\"Still sensitive where they put things. That fades. Mostly. The bits that don't "
                "fade are the bits we keep you sensitive on purpose. Hold still for the rest.\"")},
            {"key": "ask_ft", "label": "Ask what they're going to do", "set": {"ft": "ask"},
             "desc": "make the fitter name the servicing",
             "outcome": (
                "\"Check it, test it, use it,\" the fitter says, ticking the list. \"Every piece "
                "the facility's hung on you has a function, and functions are meant to be "
                "*run*. A port that never drains seizes. A gape that's never plugged tightens. A "
                "bell that never rings is just jewellery. So we run all of it. That's the fitting. "
                "Up on the bench.\"")}],
        "default": "present",
        "then": "ft_check"}


@choice("ft_check", root=False)
def _ft_check(character):
    k = _kit(character)
    bits = []
    if k["pierced"]:   bits.append("each piercing is tugged and tested for seat, the little bright sparks of it making you jump")
    if k["milk_port"]: bits.append("the milk-port is uncapped and a line snapped on, a test-pull drawing a thread of you down the tube to prove it flows")
    if k["gaped"]:     bits.append("the gauged hole is checked with a gloved spread, a sizing-plug pressed in and out to confirm it still takes the full width")
    if k["latex"]:     bits.append("the latex seal is run for leaks, a palm smoothing down every glossy inch and pressing the air out")
    if k["pet"]:       bits.append(f"the tail's set is checked, seated firm, given a tug that moves you like the {k['pet']} you've been made")
    if k["collared"]:  bits.append("the collar's lock is tested — still fast, still not yours")
    if k["heat_tell"] or k["honorific"]: bits.append("they make you say a few words just to hear the clauses bite — the tell betraying your arousal, the title forced out of you")
    checklist = (" ".join(bits[:1]) + (" — and " + ", and ".join(bits[1:]) if len(bits) > 1 else "")) if bits else ""
    if checklist:
        body = ("Piece by piece they run it: " + checklist + ". Every install answers its test, "
                "logged in your file as *serviceable*, and the thoroughness of being checked over "
                "like equipment — like the inventory you've become — sits heavier than rougher "
                "handling would.")
    else:
        body = ("With nothing installed to service, the check is brief and almost clinical — a "
                "gloved inventory of where the hardware *will* go, a cold tracing of the future "
                "work, the fitter murmuring measurements into a recorder. It is its own quiet "
                "dread: not what's been done, but the unhurried certainty of what will be.")
    return {"key": "ft_check", "prompt": (
        body + "\n\nThe fitter steps back, makes a note, and gets the look of someone moving from "
        "*checking* the equipment to *running* it. \"All seats true. Now we use it as a set — "
        "that's the part that matters. Idle hardware's just decoration, and the facility doesn't "
        "decorate.\""),
        "options": [
            {"key": "hold_check", "label": "Hold still through the servicing", "effect": "devote",
             "params": {"amount": 2.0}, "desc": "be the equipment; let it be tested",
             "outcome": (
                "You hold still and let yourself be serviced, every piece tested in turn, and being "
                "*equipment under maintenance* settles into you with a flat finality — not a person "
                "being touched but a unit being kept in working order. The fitter's approval is for "
                "the readings, not for you. There's no you in the readings anymore. That's rather "
                "the point of being well-fitted.")},
            {"key": "squirm", "label": "Squirm under the testing", "effect": "deny_hold",
             "params": {"cond": 2.0}, "desc": "the tugging and spreading is a lot; it's logged",
             "outcome": (
                "You squirm under it — the tugging, the spreading, the clauses being made to bite — "
                "and the fitter notes the responsiveness as one more reading. \"Reactive hardware. "
                "Good — means the nerves are still wired to the installs the way we want. A piece "
                "that stopped reacting would need adjusting. You're in spec. Squirm all you like; "
                "it's data.\"")}],
        "default": "hold_check",
        "then": "ft_use"}


@choice("ft_use", root=False)
def _ft_use(character):
    k = _kit(character)
    # Pick the realest effect available from the installed kit.
    if k["milk_port"]:
        method, kind, line = "_do_milk", "proc", ("the port runs hot, drawing you down the line in earnest now, not a test-pull but a full draining, the hardware doing the work your body was rebuilt to do")
    elif k["gaped"]:
        method, kind, line = "_gang", "gang", ("the gauged hole is put to use as exactly what it was opened to be — plug, then cock, then knot, the permanent gape taking it all without resistance because resistance was surgically removed")
    else:
        method, kind, line = None, None, ("with little hardware to run, they use what you came with, plainly, and log the baseline against the work still to come")
    combo = []
    if k["milk_port"] and k["gaped"]: combo.append("drained at one end while filled at the other, the two installs run at once like a machine with all its functions engaged")
    if k["stim"]:    combo.append("the stim-implant kept dialed up the whole time, so the servicing rides a baseline of involuntary need you can't switch off")
    if k["pet"]:     combo.append(f"led by the tail through it, kept in your {k['pet']} posture")
    if k["latex"]:   combo.append("sweating inside the sealed latex, the heat of the work trapped against you")
    if k["denied"]:  combo.append("wound to the edge by all of it and denied, the clause holding your release hostage as usual")
    combo_line = (" — " + ", ".join(combo)) if combo else ""
    return {"key": "ft_use", "prompt": (
        "And then they *run the set*. " + line.capitalize() + combo_line + ". This is the fitting's "
        "real lesson, the one that lands deeper than any single room's: you are not a person who "
        "happens to have hardware. You are a *rig* now — a collection of installed functions meant "
        "to be operated together, serviced and run as a unit — and the more they've hung on you, "
        "the more there is to switch on at once, the less of you is left over between the working "
        "parts.\n\n\"There it is,\" the fitter says, watching the readings climb. \"Full kit, "
        "running as designed. That's a *fitted* body. Take what the set gives you.\""),
        "options": [
            {"key": "run", "label": "Let the whole set run", "effect": ("facility" if method else "devote"),
             "params": ({"method": method, "kind": kind} if method else {"amount": 3.0}),
             "set": {"ft_run": "yes"}, "desc": "every install operated at once; real output logged",
             "outcome": (
                "You let the whole rig run, every installed function operated at once, and whatever "
                "real output it produces — milk drawn, hole bred, the readings climbing — is logged "
                "as the fitting intends: proof the kit works as a system. And being operated like "
                "a system, all your functions running together, is the most thoroughly *thing* you "
                "have ever felt, and the part of you that minds is getting very small and very far "
                "between the working parts.")},
            {"key": "endure_ft", "label": "Endure the set being run", "effect": ("facility" if method else "deny_hold"),
             "params": ({"method": method, "kind": kind} if method else {"cond": 3.0}),
             "set": {"ft_run": "endured"}, "desc": "the rig runs regardless; refuse to be only equipment",
             "outcome": (
                "You endure it — hold onto being a *someone* while they operate you as a *something* "
                "— and the rig runs regardless, the installs doing their work whether you consent "
                "to being a unit or not, the output logged the same. \"Resisting being equipment,\" "
                "the fitter notes, unbothered. \"Common, in the well-fitted. The hardware doesn't "
                "care how you feel about it. That's the lovely thing about hardware.\"")}],
        "default": "run",
        "then": "ft_close"}


@choice("ft_close", root=False)
def _ft_close(character):
    k = _kit(character)
    tail = ("Serviced, run, and logged, your full kit confirmed in working order"
            if _kit_inventory(k) else
            "Baselined and logged, your blank body's future work scheduled")
    return {"key": "ft_close", "prompt": (
        "The fitter caps what needs capping, unsnaps the lines, smooths the seals, and notes the "
        f"servicing complete. \"{tail}. You'll come back for fitting whenever the rooms hang "
        "something new on you, or whenever a piece needs adjusting — which is regularly; "
        "well-used hardware wears, and we keep it serviced.\" They pat whatever install is nearest "
        "to hand, proprietary, the way you'd pat good equipment. \"Every fitting, there's a little "
        "more of you that's hardware and a little less that isn't. That's not a side effect. "
        "That's the maintenance schedule. Off you go — mind the tender bits.\""),
        "options": [
            {"key": "thank", "label": "Thank the fitter", "effect": "gratitude", "end": True,
             "desc": "for keeping your installs in order; mean it a little",
             "outcome": (
                "\"Thank you.\" For keeping the hardware working, for the strange care of being "
                "maintained — and it comes out meant, which is the fitting having done its quieter "
                "work: you've started to think of your own installs as things worth keeping "
                "serviced, your own body as a rig worth maintaining. \"Polite equipment,\" the "
                "fitter almost-smiles. \"Bethany does like a unit that thanks its service tech.\"")},
            {"key": "silent_ft", "label": "Say nothing — carry your serviced kit out", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "leave wearing the work, mute",
             "outcome": (
                "You say nothing and carry your serviced, run, logged hardware out — every piece "
                "tested and proven and yours-but-not-yours, a body kept in working order on a "
                "maintenance schedule you don't set. The fitter's already prepping the bench for "
                "the next rig. You'll be back the moment the rooms add a part. They always add a "
                "part.\"")}],
        "default": "thank"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Correction — a rule-break answered. Confession/defiance → sentence →
# aftermath. Cinematic, state-aware. Actor: Bethany (the disciplinarian register —
# disappointed-warm, not cruel-for-fun). REAL payload: register_defiance / punish /
# apply_filth / make_example / gratitude — actual punishment + the earn-back hook.
# §0 always frees you. Flow: arrival→plea→sentence→aftermath. Entry: `scene correction`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("pn_arrival", root=False)
def _pn_arrival(character):
    k = _kit(character)
    note = ""
    if k["denied"]:
        note = "Your denial's already running, so there's no relief to take away — the correction has to find another lever, and it will. "
    if k["little"]:
        note += "Down in your headspace you barely grasp the charge, only the disappointed weight of her voice, and the not-understanding makes the dread worse. "
    return {"key": "pn_arrival", "prompt": (
        "You're brought up short — pulled off whatever you were doing and stood in front of a "
        "review, because the facility *logs* everything and somewhere a line in your file went "
        "red. " + note + "Bethany meets you not with the bright cruelty of the floors or the warm "
        "ownership of her bed but with a third thing, worse than both: |wdisappointment|n, the "
        "patient managerial sorrow of a woman who's read your infraction and finds it more tedious "
        "than offensive. \"Sit down, sweetheart. No — stand. We need to talk about a choice you "
        "made.\" She taps the file. \"You know the rule you broke. I'm not going to tell you which "
        "— I want to hear *you* tell *me*, because the telling matters more than the rule. So.\" "
        "She laces her hands. \"Are you going to confess it, or are you going to make me read it "
        "to you off the page?\""),
        "options": [
            {"key": "confess", "label": "Confess it", "set": {"plea": "confess"},
             "effect": "gratitude", "params": {"amount": 2.0},
             "desc": "name the break yourself; banks a little compliance",
             "outcome": (
                "You confess — name the break yourself, out loud, before she has to — and something "
                "in her face eases into approval that's worse than anger. \"*There* it is. Thank "
                "you. Confessing is the first thing we teach and the last thing they learn, and "
                "you've done it without being made to.\" She notes it — *self-reports* — and the "
                "noting banks a sliver of compliance against you. \"The correction still happens, "
                "sweetheart. But it happens to a girl who owned it. That counts. I keep track of "
                "what counts.\"")},
            {"key": "deny", "label": "Deny it", "set": {"plea": "deny"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "refuse the charge; she reads it off the page and logs the lie",
             "outcome": (
                "You deny it. Bethany doesn't argue — she simply turns the file and reads it to "
                "you, the timestamped truth of exactly what you did, in her even disappointed "
                "voice, while you stand there with the lie still warm in your mouth. \"Mm. So now "
                "it's the break *and* the denial, two lines red instead of one.\" She makes the "
                "second note. \"Lying to me is its own infraction, you understand — clause twelve, "
                "resistance is logged. You've just doubled your own sentence to avoid a "
                "confession that would have halved it. We'll work on your arithmetic.\"")},
            {"key": "silent_pn", "label": "Say nothing", "set": {"plea": "silent"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "neither confess nor deny; she reads it anyway",
             "outcome": (
                "You give her nothing — neither confession nor denial, just silence. Bethany sighs, "
                "almost fond, and reads the charge off the page regardless. \"Stonewalling. That's "
                "a phase too. It reads as defiance, sweetheart — silence in a review always does — "
                "so it sentences the same as a denial, just with less for me to hold against you "
                "later. Suit yourself. The outcome's identical and you've kept your dignity, for "
                "all the good it'll do you in about ninety seconds.\"")}],
        "default": "confess",
        "then": "pn_sentence"}


@choice("pn_sentence", root=False)
def _pn_sentence(character):
    plea = scene_flag(character, "plea", "confess")
    lead = ("\"Since you owned it, I'll let you pick the form. Small mercy. Take it.\" "
            if plea == "confess" else
            "\"You don't get to pick, after that. But I'll tell you what's coming, so the waiting "
            "does some of the work.\" ")
    return {"key": "pn_sentence", "prompt": (
        lead + "\"Correction has three usual forms, and they all end the same — you, more "
        "compliant, and the record noting that resistance costs. There's |wthe sty|n: slopped and "
        "rutted face-down in the muck till you've reconsidered your priorities. There's |wthe "
        "floor|n: made an example of, publicly, where all the other stock can watch what a red "
        "line earns. Or there's |wthe line|n: nothing dramatic, just the schedule turned heavier "
        "and the denial turned deeper and the clock you can't see turned longer, the quiet "
        "correction that costs the most over time.\" She waits. \"Which lesson would you like to "
        "have learned?\""),
        "options": [
            {"key": "sty", "label": "The sty — filth and the muck", "effect": "filth",
             "set": {"sentence": "sty"}, "desc": "real apply_filth + punishment",
             "outcome": (
                "The sty, then. You're walked down and slopped — real filth, rutted face-down, "
                "kept in the muck till the lesson takes — and hauled back up reeking and corrected, "
                "the degradation logged as your sentence served. \"Better,\" Bethany says, not "
                "wrinkling her nose because she's far past that with her own stock. \"You'll think "
                "of the muck next time a red line tempts you. That's the whole point of the "
                "muck.\"")},
            {"key": "floor", "label": "The floor — made an example", "effect": "make_example",
             "params": {"severity": 2}, "set": {"sentence": "floor"},
             "desc": "real public make_example (overstim + standing hit + broadcast)",
             "outcome": (
                "The floor. You're taken out under the lights and *made an example of* — publicly, "
                "thoroughly, the other stock made to watch what a red line earns — and the shame of "
                "being the lesson lands deeper than the correction itself. Your standing takes the "
                "hit; the broadcast does its work. \"There,\" Bethany tells the watching room as "
                "much as you. \"That's what it costs. Learn from her so I don't have to teach "
                "you.\"")},
            {"key": "line", "label": "The line — heavier schedule, deeper denial", "effect": "punish",
             "params": {"severity": 2}, "set": {"sentence": "line"},
             "desc": "real punish — overstim, deeper denial, raised quota, longer clock",
             "outcome": (
                "The line. Nothing dramatic — just the stimulation slammed up, the release dragged "
                "further out of reach, the schedule turned heavier and a quota raised and the clock "
                "you can't see turned longer — the quiet correction that follows you for days "
                "instead of minutes. \"The cruelest one, really,\" Bethany says, almost kindly. "
                "\"No spectacle to brace against. Just everything turned harder, indefinitely, "
                "because you made a choice. You'll feel this one long after the muck would've "
                "washed off.\"")}],
        "default": "line",
        "then": "pn_after"}


@choice("pn_after", root=False)
def _pn_after(character):
    sentence = scene_flag(character, "sentence", "line")
    return {"key": "pn_after", "prompt": (
        "When the sentence is served Bethany comes back to you, the disappointment set aside, the "
        "warmth returning — because correction in here was never about anger, it was about "
        "*shaping*, and the shaping's done for now. \"There. That's behind us.\" She tips your "
        "chin up. \"And now the part that actually matters, the part the whole correction was "
        "built to reach: I want you to thank me for it. Not because I'll punish you again if you "
        "don't — though the review does reset if you won't — but because some part of you is "
        "starting to understand that the correction *is* the care, that being shaped is being "
        "*kept*, and I want to hear you say it and mean it. They're not building toward your "
        "breaking, sweetheart. They're building toward your *thanking*.\""),
        "options": [
            {"key": "thank", "label": "Thank her — and mean it", "effect": "gratitude", "end": True,
             "desc": "the earn-back; a thank-you that's kept",
             "outcome": (
                "\"Thank you for correcting me.\" It comes out shaped and meant both, and the "
                "meaning is the thing she was fishing for the whole time, the hook setting clean. "
                "Bethany glows. \"*That's* the one we keep. That's the lesson learned — not the sty "
                "or the floor or the line, those were just the long way round to this.\" She files "
                "the gratitude with everything else, your earn-back banked, the red line in your "
                "file marked *resolved, with thanks*. You meant it. That's the part that should "
                "frighten you and is starting not to.")},
            {"key": "refuse_thank", "label": "Refuse to thank her", "effect": "deny_hold",
             "params": {"cond": 3.0}, "end": True,
             "desc": "withhold the thanks; the review resets, patient",
             "outcome": (
                "You won't thank her for it. Bethany accepts that with the patience of someone who "
                "has all the time there is. \"No? That's all right. The review resets — we'll come "
                "back to this, and back to it, correction after correction, until the thank-you "
                "comes on its own, because it always does, in the end.\" She closes the file, "
                "unbothered. \"I'm not building toward your obedience, sweetheart. I have that "
                "already. I'm building toward the day you're *grateful* for it. I can wait. "
                "Gratitude keeps better than fear anyway.\"")}],
        "default": "thank"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Dosing — a drug administered, the come-up, riding the effect. Cinematic,
# state-aware. Actor: the dispensary tech. REAL payload: the facility `_dose` method
# fires an actual drug from the resident's pool. §0 always frees you.
# Flow: arrival→dose→comeup→ride. Entry: `scene dosing`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("dz_arrival", root=False)
def _dz_arrival(character):
    k = _kit(character)
    note = ""
    if k["preg"]:
        note = "They check the chart twice — \"bred, so we hold the heavy ones and run the gentle drips\" — gravid stock gets dosed careful, for the cargo's sake not yours. "
    if k["stim"]:
        note += "Your stim-implant's already running, so whatever they add stacks on a baseline you can't switch off. "
    if k["nugget"]:
        note += "A nugget gets the line run straight into a port — no veins to find on limbs you don't have, just the maintenance plumbing already in you. "
    if k["little"]:
        note += "Down little, you don't read the chart or the warnings, only that there's a needle and a cold-clean smell and a grown-up saying hold still — and a dosed little mind goes down so much faster and further than a grown one, which the tech has noted in your file in red. "
    return {"key": "dz_arrival", "prompt": (
        "The dispensary is clean and cold and softly humming — racked vials in facility grey, a "
        "tray of pre-loaded syringes, an IV stand, a chart of your tolerances and your schedule. "
        "This is where the facility reaches past your body and into your *chemistry*, because some "
        "of the work — the heat, the haze, the want, the pliancy — is faster done with a dose than "
        "a room. " + note + "The |wdispensary tech|n reads your chart with the brisk neutrality of "
        "a pharmacist filling a routine script. \"Due for your dose,\" they say, not looking up, "
        "selecting a vial. \"Standard schedule. You'll feel it in a minute or two, and you'll feel "
        "it the way the chart says you should, because we've had a lot of practice reading you.\" "
        "They tap a syringe. \"Arm, or the port. Your preference; the dose doesn't care.\""),
        "options": [
            {"key": "offer", "label": "Offer your arm", "set": {"dz": "offer"},
             "effect": "devote", "params": {"amount": 1.0}, "desc": "take the dose without fuss",
             "outcome": (
                "You offer your arm and let them find the vein, and the not-fighting is logged as "
                "compliance the same as anything else. \"Easy stick. Good.\" The tech swabs, "
                "presses, and the cold push of it goes in. \"Now we wait for the come-up. Couple "
                "minutes. Sit. It's easier sitting.\"")},
            {"key": "pull_dz", "label": "Pull your arm back", "set": {"dz": "pull"},
             "effect": "deny_hold", "params": {"cond": 2.0}, "desc": "resist; they dose you anyway",
             "outcome": (
                "You pull back — and the tech sighs, signals, and a handler simply holds you still "
                "while the needle finds its mark regardless. \"Fighting the stick just bruises "
                "you,\" the tech says, depressing the plunger. \"Dose goes in the same. It always "
                "goes in the same. The only thing your struggling changes is whether you've got a "
                "bruise to go with the high.\"")},
            {"key": "ask_dz", "label": "Ask what it is", "set": {"dz": "ask"},
             "desc": "make them name the dose",
             "outcome": (
                "\"What it is?\" The tech almost smiles. \"Chart says it's what you're due. You "
                "don't get the name — knowing the name wouldn't change what it does, and not "
                "knowing makes the come-up more *interesting* for you, which the chart also "
                "accounts for.\" The needle's already in. \"You'll find out what it is by what it "
                "does. That's how we prefer you learn your own pharmacology.\"")}],
        "default": "offer",
        "then": "dz_comeup"}


@choice("dz_comeup", root=False)
def _dz_comeup(character):
    return {"key": "dz_comeup", "prompt": (
        "And then the |wcome-up|n. It starts at the edges — a warmth in the fingertips, a thickness "
        "behind the eyes — and then it *arrives*, whatever it is, and the dispensary's careful "
        "reading of you proves out: the dose does exactly what your chart promised, blooming "
        "through you on its own schedule, hijacking some system you'd thought was yours. Maybe the "
        "heat slams up past anything a room could build; maybe the haze rolls in and takes your "
        "edges; maybe everything goes soft and suggestible and *agreeable* in a way that "
        "frightens the last sober sliver of you. The tech watches your pupils, your colour, your "
        "breathing, ticking the chart as the markers hit. \"There's the come-up. Right on the "
        "curve. Ride it — fighting the come-up just makes it longer and meaner. Let it take "
        "you.\""),
        "options": [
            {"key": "ride", "label": "Let the come-up take you", "effect": "facility",
             "params": {"method": "_dose", "kind": "proc"}, "set": {"dz_taken": "rode"},
             "desc": "the real dose fires — an actual drug from your pool",
             "outcome": (
                "You stop fighting and let it take you, and the real chemistry does its real work — "
                "an actual dose off your pool, blooming through you exactly as logged, doing to "
                "your heat or your haze or your will whatever the vial was for. Letting it in is "
                "easier and the easier is the lesson: your own chemistry isn't yours to refuse "
                "anymore, it's another thing the facility administers on a schedule, and reaching "
                "for the high it hands you is just one more reflex they're installing.")},
            {"key": "fight_dz", "label": "Fight the come-up", "effect": "facility",
             "params": {"method": "_dose", "kind": "proc"}, "set": {"dz_taken": "fought"},
             "desc": "the dose hits regardless; resisting only drags it out",
             "outcome": (
                "You fight it — clench against the bloom, try to hold your edges as the dose "
                "arrives — and the chemistry doesn't negotiate, the real dose hitting regardless, "
                "your resistance only stretching the come-up longer and rougher exactly as the "
                "tech warned. \"Fighter,\" they note, unbothered, watching the markers climb anyway. "
                "\"It wins. It always wins. It's in your blood, not your willpower. The willpower's "
                "just along for the ride.\"")}],
        "default": "ride",
        "then": "dz_ride"}


@choice("dz_ride", root=False)
def _dz_ride(character):
    return {"key": "dz_ride", "prompt": (
        "And then you're *on* it — riding the full effect, whatever it turned out to be, the world "
        "remade through the dose's lens for as long as it runs. The tech logs your reaction, dials "
        "in a note for next time (\"responds well — we can step the dose\"), and leaves you to it, "
        "because the dose does the supervising now. This is the quiet horror of the dispensary: "
        "not the needle, but the *afterward* — hours of your own chemistry turned against you, a "
        "high or a haze or a heat you didn't choose and can't end, teaching your body to expect "
        "the next dose the way it's learned to expect everything else the facility hands it on a "
        "schedule."),
        "options": [
            {"key": "surf", "label": "Surf the high — let it be good", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "enjoy what they gave you; the enjoying is the leash",
             "outcome": (
                "You surf it — let the dose be as good as it wants to be — and the enjoying is the "
                "leash, your body filing another association: *the facility's chemistry feels "
                "good*, the dispensary is where the nice things come from, the next dose is "
                "something to look forward to. You'll hold your arm out faster next time. The chart "
                "already predicted you would. It's very good at predicting you.")},
            {"key": "endure_dz", "label": "Endure the ride", "effect": "deny_hold",
             "params": {"cond": 3.0}, "end": True, "desc": "wait it out; it runs its course regardless",
             "outcome": (
                "You endure it — wait out the hours of hijacked chemistry, refusing to enjoy what "
                "you didn't choose — and it runs its full course regardless, your body dosed and "
                "altered on schedule whether you ride it pleasantly or grit through it. Either way "
                "the chart gets its data and your tolerance gets stepped and the next dose is "
                "already scheduled. \"You'll come down eventually,\" the tech says on their way "
                "out. \"And you'll be due again before you've forgotten this one. That's the "
                "schedule. Welcome to it.\"")}],
        "default": "surf"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Facility Events — scheduled set-piece spectacles, picked at random so the
# place stays fresh. `ev_arrival` is a DISPATCHER: it returns a random event's
# opening (the Buyer's Tour / Quota Day / the Breeding Festival / the Anniversary),
# each a short cinematic chain with real effects. Cinematic, state/kit-aware.
# §0 always frees you. Entry: `scene events` (also `event`). More events drop in
# here over time — that's the freshness valve.
# ═══════════════════════════════════════════════════════════════════════════

_EVENT_OPENINGS = ["ev_tour", "ev_quota", "ev_fest", "ev_anniv", "ev_rut", "ev_gala", "ev_openhouse"]


@choice("ev_arrival", root=False)
def _ev_arrival(character):
    """Dispatcher: a klaxon sounds, an event is called — and which one is the facility's to pick,
    not yours. Returns a random event's opening spec directly (so it poses as that event)."""
    key = random.choice(_EVENT_OPENINGS)
    fn = _BUILDERS.get(key)
    spec = fn(character) if fn else None
    return spec or {"key": "ev_arrival", "prompt": "The klaxon dies. False alarm. The routine "
                    "resumes around you.", "options": [
                        {"key": "ok", "label": "Back to the routine", "end": True,
                         "outcome": "The day folds back into its ordinary shape."}], "default": "ok"}


# --- Event: the Buyer's Tour ------------------------------------------------
@choice("ev_tour", root=False)
def _ev_tour(character):
    return {"key": "ev_tour", "prompt": (
        "|WA klaxon, two soft tones — and the announcement: a |wBuyer's Tour|n on the floor "
        "today.|n The facility tidies its stock for company: you're posed at your station, oiled "
        "and squared, as a clutch of well-dressed |wbuyers|n is walked through behind a "
        "guide, pausing at the lots that catch an eye. You feel the moment one of them stops at "
        "*you* — the guide reciting your particulars, the buyer's gloved hand lifting your chin, "
        "turning you to the light, appraising what you'd cost and what you'd take. \"This one "
        "shows nicely,\" the guide says, of you, over you. \"Demonstrate for the gentleman.\""),
        "options": [
            {"key": "perform", "label": "Demonstrate willingly", "effect": "facility",
             "params": {"method": "_scene_single", "kind": "scene"}, "set": {"tour": "perform"},
             "desc": "show the buyer what you are; real use, on display",
             "outcome": (
                "You demonstrate — let the buyer see you used, your responses put through their "
                "paces for the tour's benefit — and the appraising murmur of strangers deciding "
                "your worth lands warm and shameful. \"Mm. Yes,\" the buyer notes. \"I'll watch "
                "this one's price.\" You're a lot that showed well today. It goes in the file.")},
            {"key": "freeze", "label": "Freeze under the buyers' eyes", "effect": "deny_hold",
             "params": {"cond": 2.0}, "set": {"tour": "freeze"},
             "desc": "go still; the guide demonstrates you anyway",
             "outcome": (
                "You freeze — and the guide, smooth, works the demonstration out of you regardless, "
                "narrating your stillness to the buyer as 'placid, low-maintenance.' The tour moves "
                "on, the buyer glancing back once. Being unable to *not* be shown, even still, is "
                "its own lesson the floor keeps teaching.")}],
        "default": "perform",
        "then": "ev_tour_b"}


@choice("ev_tour_b", root=False)
def _ev_tour_b(character):
    return {"key": "ev_tour_b", "prompt": (
        "The tour winds on, but the buyer who stopped at you lingers a beat at the door, having a "
        "quiet word with the guide — and you catch, across the floor, the specific weight of being "
        "*remembered*. A note made. An interest registered. Whether anything comes of it isn't "
        "yours to know; that's the dread the tour leaves behind like a scent: that somewhere out "
        "there, now, a stranger is thinking about owning you, and the next time the block lights "
        "up your number, they might be the paddle that wins."),
        "options": [
            {"key": "dread", "label": "Sit with being wanted by a stranger", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "the tour's parting gift",
             "outcome": (
                "You carry it the rest of the day — the knowledge that you've been *noticed*, "
                "priced, filed as a thing someone out there might buy — and the not-knowing-who "
                "works on you better than any room could. The tour did its job. You showed. You "
                "were wanted. The market has you in its eye now.")},
            {"key": "shrug", "label": "Tell yourself it's nothing", "effect": "devote",
             "params": {"amount": 1.0}, "end": True, "desc": "the comfort that isn't one",
             "outcome": (
                "You tell yourself it's nothing — buyers look, that's all — and almost believe it, "
                "and the almost is the hook: you've started measuring your days by whether you "
                "showed *well*, started wanting the appraising eyes to approve, and that wanting is "
                "the floor's whole curriculum. It was never nothing. You'll dress for the next "
                "tour without being told.")}],
        "default": "dread"}


# --- Event: Quota Day -------------------------------------------------------
@choice("ev_quota", root=False)
def _ev_quota(character):
    db = getattr(character, "db", None)
    behind = bool(getattr(db, "quota_behind", 0))
    lead = ("Your line's flagged red — *behind* — and you know it before the board says it. "
            if behind else "Your line reads green, near enough, which is its own kind of trap. ")
    return {"key": "ev_quota", "prompt": (
        "|WThe klaxon's long single tone: |wQuota Day|n.|n The whole floor is mustered before the "
        "big board, every resident's numbers thrown up live — milk yield, breeding count, "
        "conditioning depth — for all the stock to see, because the facility runs on quotas and "
        "Quota Day is where falling short stops being private. " + lead + "A processor works down "
        "the line calling figures, and the room watches each lot learn, in public, whether "
        "they've produced enough.\" You're next."),
        "options": [
            {"key": "stand", "label": "Stand for your numbers", "set": {"quota": "stand"},
             "effect": "devote", "params": {"amount": 1.0},
             "desc": "let the floor read what you've produced",
             "outcome": (
                "You stand and let your figures be read aloud to the mustered floor — your yield, "
                "your count, your depth, the public accounting of your productivity — and being "
                "reduced to a column of output in front of all the other columns lands flat and "
                "total. The processor reads on. You are your numbers today, and only your "
                "numbers.")},
            {"key": "dread", "label": "Brace for the shortfall", "set": {"quota": "dread"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the public dread of falling short",
             "outcome": (
                "You brace — the dread of being the one whose red line is read to the room — and "
                "the waiting for your figure is its own punishment, the floor's eyes already "
                "turning, the processor's pen already moving down toward your name.")}],
        "default": "stand",
        "then": "ev_quota_b"}


@choice("ev_quota_b", root=False)
def _ev_quota_b(character):
    behind = bool(getattr(getattr(character, "db", None), "quota_behind", 0))
    verdict = ("And your line is *short*. The board flashes it red for the room to see, and the "
               "processor doesn't even look up: \"Behind on quota. Correction scheduled, "
               "requirement raised.\""
               if behind else
               "And your line clears — barely — and the processor's 'adequate' is colder than any "
               "punishment, because 'adequate' just means the bar goes *up*: \"Met, this cycle. "
               "Quota raised for next. Keep up.\"")
    return {"key": "ev_quota_b", "prompt": (
        verdict + " Either way the lesson of Quota Day is the same, delivered in front of "
        "everyone: you exist to produce, your production is measured and public and never "
        "*enough*, and the bar only ever climbs. Green or red, you leave the muster owing more "
        "than you did walking in."),
        "options": [
            {"key": "take_quota", "label": "Take the verdict", "effect": ("punish" if behind else "devote"),
             "params": ({"severity": 1} if behind else {"amount": 2.0}), "end": True,
             "desc": "real shortfall penalty if behind; the raised bar regardless",
             "outcome": (
                "You take it — the real penalty if you fell short, the raised requirement if you "
                "didn't — and file back into the floor with a heavier number to hit and the whole "
                "room having watched you get it. Quota Day works because it's *public*. You'll "
                "produce harder next cycle. Everyone does, after the muster.")},
            {"key": "resolve_quota", "label": "Swear to make the next bar", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "internalize the climbing bar",
             "outcome": (
                "Something in you resolves to *make it* next cycle — to produce enough, to not be "
                "the red line, to satisfy the climbing bar — and that resolve is the most owned "
                "you've been all day, because you've stopped fighting the quota and started "
                "*serving* it, made it your own goal instead of their demand. The facility didn't "
                "even have to punish you. You took the leash and pulled it tighter yourself.")}],
        "default": "take_quota"}


# --- Event: the Breeding Festival -------------------------------------------
@choice("ev_fest", root=False)
def _ev_fest(character):
    k = _kit(character)
    note = ("Gravid, you're put in the watched-and-protected pen — a bred one at a breeding "
            "festival is the guest of honour, displayed proof the place works. " if k["preg"]
            else "")
    return {"key": "ev_fest", "prompt": (
        "|WThe klaxon's triple pulse, and the lights drop warm and red: |wa Breeding Festival|n.|n "
        "The facility throws these to clear quota in bulk and to *celebrate* what it is — the "
        "floor cleared and strewn, stock and stud and staff turned loose together in a long warm "
        "orgiastic churn, the air thick with rut and the board tallying covers as fast as they "
        "happen. " + note + "You're swept into it — there's no standing at the edge of a festival, "
        "the churn finds everyone — hands and cocks and the heat the facility keeps banked in you "
        "all rising to meet the occasion. \"Festival rules,\" a handler calls over the din. "
        "\"Everyone breeds, everyone's bred, and the board doesn't stop till the quota's clear.\""),
        "options": [
            {"key": "dive", "label": "Throw yourself into the churn", "effect": "facility",
             "params": {"method": "_scene_bukkake", "kind": "scene"}, "set": {"fest": "dive"},
             "desc": "give yourself to the festival; real mass use, covers logged",
             "outcome": (
                "You throw yourself in — stop being a person at a party and become *one of the "
                "churning bodies*, used and using, bred and breeding, the real covers logging fast "
                "as the festival eats the hours — and the losing-yourself-in-the-mass is a relief "
                "so total it frightens what's left. There's no shame in a crowd this size. There's "
                "no *you* in a crowd this size. The festival files you as enthusiastic. So does "
                "your body.")},
            {"key": "swept", "label": "Be swept along by it", "effect": "facility",
             "params": {"method": "_scene_bukkake", "kind": "scene"}, "set": {"fest": "swept"},
             "desc": "carried in regardless; the churn uses you the same",
             "outcome": (
                "You don't dive, but the churn doesn't need you to — it sweeps you up, passes you "
                "hand to hand and hole to hole through the warm red press, breeds you in the mass "
                "whether you chose it or not, the real covers logged the same. By the time the "
                "board clears its quota you've lost count of what's been done and stopped being "
                "able to tell your own use from the festival's. That's what a festival is for: "
                "drowning the individual in the herd.")}],
        "default": "dive",
        "then": "ev_fest_b"}


@choice("ev_fest_b", root=False)
def _ev_fest_b(character):
    return {"key": "ev_fest_b", "prompt": (
        "The festival burns down slowly, the way they do — the churn thinning, bodies dropping out "
        "spent and dripping and marked, the board's quota-bar finally satisfied and the warm red "
        "lights ticking back toward ordinary. You're left in the wreckage of it, used past "
        "counting, bred by stock and staff and strangers you'll never identify, the festival's "
        "particular afterglow settling over you: not shame, not even quite exhaustion, but the "
        "flat warm emptied calm of a thing that's been thoroughly *used in company* and found it "
        "easier than being used alone."),
        "options": [
            {"key": "glow", "label": "Lie in the festival's afterglow", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "let the emptied calm take you",
             "outcome": (
                "You lie in it and let the emptied calm have you, and the lesson of the festival "
                "sets while you're too spent to resist it: being used in a crowd is *easier*, the "
                "herd dissolves the self that minds, and you'll look forward to the next festival "
                "the way you've learned to look forward to the cups and the chair. Bred in bulk and "
                "grateful for the company. The facility throws good parties. That's the trap of "
                "them.")},
            {"key": "ache", "label": "Feel the count you lost", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "the dread under the afterglow",
             "outcome": (
                "Under the afterglow, the dread: you lost *count* — of who, of how many, of how "
                "long — whole stretches of yourself spent in the churn with no record but the "
                "board's tally and the load in your belly, and the not-knowing is the festival's "
                "real keepsake. You were used by the facility as a *quantity*, and you'll never "
                "get the number back. It has it. You don't.")}],
        "default": "glow"}


# --- Event: the Anniversary (only lands harder once she owns you) -----------
@choice("ev_anniv", root=False)
def _ev_anniv(character):
    bowned = bool(getattr(getattr(character, "db", None), "bethany_owned", False))
    frame = ("She marks the day she *bought* you — another cycle of you on her file, hers and "
             "kept. " if bowned else
             "She marks the day she first processed you — another cycle of you in her care, "
             "whether she owns you on paper yet or not; she counts from the intake, she says. ")
    return {"key": "ev_anniv", "prompt": (
        "There's no klaxon for this one. Bethany simply *appears* at your station, off her usual "
        "schedule, with a small fond smile and your file under her arm, and you realize it's an "
        "|wanniversary|n — a date she keeps that you didn't know existed. " + frame + "\"I keep "
        "all my dates, sweetheart,\" she says, warm, leafing your file open to a page she's clearly "
        "visited before. \"The day you arrived. The day you signed. The day you first called me "
        "Owner and meant it. I celebrate them quietly — you're usually too far under to notice — "
        "but this year I wanted you *here* for it. Come. Let me show you how far you've come. I'm "
        "so proud of the work.\""),
        "options": [
            {"key": "moved", "label": "Be moved that she remembers", "set": {"anniv": "moved"},
             "effect": "devote", "params": {"amount": 4.0},
             "desc": "the false-tenderness lands; being remembered is the hook",
             "outcome": (
                "It lands — the awful warmth of being *remembered*, of mattering enough to mark on "
                "a calendar, even as furniture, even as product — and you're moved despite "
                "yourself, despite knowing exactly what it is. Bethany sees it and glows. \"There. "
                "That's the look I keep these dates for. You're glad I remember. That gladness is "
                "the most owned thing about you, sweetheart, and it grows every year.\"")},
            {"key": "chilled", "label": "Be chilled that she's been counting", "set": {"anniv": "chilled"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the horror of being a date she keeps",
             "outcome": (
                "It chills you — that she's been *counting*, keeping anniversaries of your "
                "reduction like a gardener marking a tree's rings, that there's a page in her file "
                "she returns to and feels fond over — and the horror of being someone's *cherished "
                "long project* is colder than any cruelty. Bethany reads it and is unbothered, "
                "fond. \"Chilled? That fades. The dates don't. I'll keep marking them long after "
                "you've stopped flinching, and one year soon you'll mark them *with* me.\"")}],
        "default": "moved",
        "then": "ev_anniv_b"}


@choice("ev_anniv_b", root=False)
def _ev_anniv_b(character):
    return {"key": "ev_anniv_b", "prompt": (
        "\"And I never come to an anniversary empty-handed,\" Bethany says, setting the file aside "
        "and freeing the triple length, because of course the gift is *her*. She takes you right "
        "there at your station, unhurried and fond, all three of her and the laced devotion, "
        "marking the date in your body the way she's marked it in her file — \"a little deeper "
        "every year, sweetheart, that's the tradition\" — and reads you, between strokes, the line "
        "she's added to your page for today: another cycle served, another measure of how "
        "thoroughly you've become hers. It is the warmest and the most owning thing the calendar "
        "holds, and she does it like it's a kindness, and it is, and that's the worst of it."),
        "options": [
            {"key": "give", "label": "Give her the anniversary she wants", "effect": "bethany_breeds",
             "params": {"holes": 3, "devotion": 7.0}, "end": True,
             "desc": "the full gift; real cover + the deepening claim, logged",
             "outcome": (
                "You give her the day she wanted — open everywhere, take all three and the laced "
                "flood, let the anniversary deepen its claim — and it's real, logged, another line "
                "in the file and another measure of devotion seated for good. \"*There's* my "
                "anniversary,\" she breathes, fully seated, fully home. \"Same time next year. And "
                "the year after. I intend to keep you a very long time, and to celebrate every "
                "single one.\" You are, a little more than last year, hers.")},
            {"key": "endure_anniv", "label": "Endure her tradition", "effect": "bethany_breeds",
             "params": {"holes": 1, "devotion": 4.0}, "end": True,
             "desc": "she takes the anniversary regardless; the claim deepens anyway",
             "outcome": (
                "You hold yourself apart from it — but she takes her anniversary regardless, fond "
                "and unhurried, the cover real and the claim deepening whether you celebrate with "
                "her or not. \"Sulking through your own anniversary,\" she tuts, breeding you "
                "gently. \"That's all right. There'll be others, and one of them you'll spend "
                "*reaching* for me, and that'll be the best date in the file. I can wait. I've "
                "clearly got you for years.\"")}],
        "default": "give"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Manumission — the IN-FICTION earned door (NOT the §0 floor).
# Cinematic. Actor: Bethany. This is the diegetic exit: gated, priced, gougeable,
# and she'd rather you didn't — the LONG way out, paid in scrip + LOW devotion +
# standing. CRUCIAL CONTRAST kept explicit throughout: this hard door is hers to
# price; the OTHER door (escape/the §0 floor) is always open, free, ungated, never
# hers to touch. Reads + drives the REAL release.py system. Flow: arrival→terms→
# verdict. Entry: `scene manumission`.
# ═══════════════════════════════════════════════════════════════════════════

def _manumit_ready(character):
    try:
        from world.release import terms, _unmet
        t = terms(character)
        return (not _unmet(character, t)) and bool(t.get("paid")) and bool(t.get("offered"))
    except Exception:
        return False


def _manumit_unmet_text(character):
    try:
        from world.release import terms, _unmet
        t = terms(character)
        un = _unmet(character, t)
        bits = [d for _lbl, d in un]
        if not t.get("offered"):
            bits.insert(0, "there's no release on the table yet — she has to offer you a price first")
        if t.get("offered") and not t.get("paid"):
            bits.append(f"the scrip's unpaid ({int(t.get('scrip', 0))} owed)")
        return "; ".join(bits) if bits else ""
    except Exception:
        return ""


@effect("manumit_petition")
def _eff_manumit_petition(character, p):
    try:
        from world.release import petition
        petition(character)
    except Exception:
        pass
    return "petitioned"


@effect("manumit_grant")
def _eff_manumit_grant(character, p):
    try:
        from world.release import grant
        grant(character)
    except Exception:
        pass
    return "granted"


@choice("mn_arrival", root=False)
def _mn_arrival(character):
    return {"key": "mn_arrival", "prompt": (
        "You come to Bethany to ask about |wmanumission|n — the in-fiction door, the *earned* one, "
        "the long legitimate way out where she signs you over free and proper, mine no more. She "
        "sets down her pen and gives you her whole warm attention, not unkind, because this "
        "conversation is one she takes seriously even as she makes it hard.\n\n"
        "\"The release. Yes. Let's be clear about the two doors, sweetheart, because I never "
        "muddle them and I won't have you muddle them either.\" She holds up one finger. \"There's "
        "*my* door — manumission. It has a price: scrip, and standing, and — \" a fond, cruel "
        "little smile \" — your devotion has to be *low* enough that I'll believe you mean it, "
        "which is its own joke, because I spend every day raising it. That door I gouge, and "
        "gate, and would honestly rather keep shut. It's the hard way, and I make it hard on "
        "purpose.\" A second finger, and her voice changes — not warm now, but *level*, the truest "
        "she gets. \"And there's the *other* door. The word that takes you home, free, this "
        "second, no price, no permission, no convincing me of anything. That one I never touch. "
        "Not ever. It's not mine to touch. You could speak it right now and I'd let go completely "
        "and mean it.\" The smile returns. \"But you're asking about *mine*. So. What do you "
        "want to do about the hard one?\""),
        "options": [
            {"key": "petition", "label": "Petition for the earned door", "effect": "manumit_petition",
             "set": {"mn": "petition"}, "desc": "formally ask; she weighs your real record",
             "outcome": (
                "You petition — formally ask for the earned door — and Bethany pulls your release "
                "file with a small approving nod, because petitioning *properly* is its own mark "
                "of the discipline the door requires. \"All right. Let's see where you actually "
                "stand against the price. I won't soften it; the whole point of this door is that "
                "it's honest.\"")},
            {"key": "ask_price", "label": "Ask what the price is", "set": {"mn": "ask"},
             "desc": "make her name the terms before you commit",
             "outcome": (
                "\"The price.\" She reads it off, frank. \"Scrip you earn the hard way, standing "
                "you build slow, and a devotion low enough that I'll sign in good conscience — and "
                "that last one's the wall most never get over, because everything else in here is "
                "built to make you want to *stay*. That's not a trick, sweetheart. That's just the "
                "shape of it. The door's real. It's only hard.\"")},
            {"key": "turnback", "label": "Turn back — not today", "set": {"mn": "back"}, "end": True,
             "desc": "leave the hard door for now (the floor's still always open)",
             "outcome": (
                "You let it lie for now. Bethany nods, unbothered, almost gentle. \"Not today. "
                "That's fine — my door keeps, and so do I. And remember the *other* one's open the "
                "whole time, sweetheart; you're never trapped here, whatever it feels like. You "
                "stay because you haven't spoken the word, and you haven't spoken the word "
                "because — well. We both know why. Come back when you want to talk terms.\"")}],
        "default": "petition",
        "then": "mn_terms"}


@choice("mn_terms", root=False)
def _mn_terms(character):
    ready = _manumit_ready(character)
    unmet = _manumit_unmet_text(character)
    if ready:
        body = ("She reads your record, and her brows lift — genuinely, a little ruefully. "
                "\"Well. Look at that. You've actually *met* it — scrip paid, standing made, and "
                "your devotion's low enough that I can sign you out and believe you want it. "
                "That's rare, sweetheart. Most never clear the devotion wall.\" She doesn't reach "
                "for the pen yet. \"You understand what saying yes means. You walk. Properly. "
                "Mine no more.\"")
    else:
        body = ("She reads your record against the price, and shakes her head slowly, not "
                "unkindly. \"Not yet. " + (unmet or "you've a way to go on every count") + ".\" "
                "She taps the file. \"That's the honest accounting. No softening it — the door's "
                "real, you're just not through it. And the devotion line, sweetheart — that one "
                "I'll keep working *against* every day you're mine, so the closer the rest of you "
                "gets, the harder I'll pull on that. That's not cheating. That's the game, and I "
                "told you the rules.\"")
    return {"key": "mn_terms", "prompt": (
        body + "\n\n\"And before you decide anything — the *other* door is still right there, "
        "unlatched, free. I'm not negotiating that one. I never would. This is only ever about my "
        "hard door, the one you have to earn off me. So.\""),
        "options": [
            {"key": "press", "label": "Press for the door now", "set": {"mn2": "press"},
             "desc": "ask her to honor it (only opens if truly earned)",
             "outcome": (
                "You press — ask her to honor it, now — and whether the pen moves is up to your "
                "real record, not your wanting. \"We'll see if it's earned,\" she says, evenly. "
                "\"My door doesn't open on wanting. That's what makes it different from the free "
                "one.\"")},
            {"key": "accept_terms", "label": "Accept where you stand", "set": {"mn2": "accept"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "take the honest accounting; keep earning (or not)",
             "outcome": (
                "You take the honest accounting — where you actually stand against the price — and "
                "the soberness of it settles in: the earned door is real and far, and the thing "
                "barring it most is your own climbing devotion, the wall she builds higher the "
                "longer she keeps you. \"Good,\" she says, of your accepting it. \"Clear-eyed. That "
                "serves the door better than hope does.\"")}],
        "default": "press",
        "then": "mn_verdict"}


@choice("mn_verdict", root=False)
def _mn_verdict(character):
    ready = _manumit_ready(character)
    pressed = scene_flag(character, "mn2", "") == "press"
    if ready and pressed:
        return {"key": "mn_verdict", "prompt": (
            "And — because you've truly earned it, against the real price, devotion wall and all — "
            "she picks up the pen. \"All right, sweetheart. You did it. The hard way, properly.\""),
            "options": [
                {"key": "take_door", "label": "Take the earned door — walk free", "effect": "manumit_grant",
                 "end": True, "desc": "she signs you out for real (release.grant)",
                 "outcome": (
                    "She signs it — both copies — and the in-fiction door opens for real: you're "
                    "manumitted, free on paper, hers no more, the way home-word working now where "
                    "it didn't before. \"There,\" she says, folding her hands, and the warmth is "
                    "real and so is the loss in it. \"Free. Earned. ...You can always stay, of "
                    "course. Most do, once it's actually a choice — and that's the part I'm proudest "
                    "of, sweetheart: that the ones who *could* go mostly choose me anyway. No price "
                    "on that. Just yours to decide.\"")},
                {"key": "stay_choose", "label": "...choose to stay, freely", "effect": "devote",
                 "params": {"amount": 3.0}, "end": True,
                 "desc": "earn the door, then decline it — the cruelest sweetness",
                 "outcome": (
                    "You earn the door — and then, holding it open, you *don't* walk through it. "
                    "You choose to stay, freely, which is the one thing the whole facility could "
                    "never make you do and the one thing it most wanted. Bethany goes very still, "
                    "and then her smile reaches her eyes completely. \"...Oh. *Oh*, sweetheart. You "
                    "earned the right to leave and you're using it to stay.\" She sets the pen down "
                    "unsigned, reverent. \"That's the best thing anyone's ever done in this room. "
                    "I'll keep the door earned and open behind you, always. You'll never need it. "
                    "But you'll always have it. Both of them, now.\"")}],
            "default": "take_door"}
    else:
        return {"key": "mn_verdict", "prompt": (
            "The pen stays down. \"Not today,\" Bethany says, and there's no triumph in it, just "
            "the level honesty the hard door demands. \"You haven't earned my door yet, and I "
            "won't fake it open — a manumission that wasn't earned isn't worth the paper, and I "
            "respect the door too much for that.\" She files your petition, noted, ongoing. \"Keep "
            "at it, if you mean it. Or don't. And the *other* door stays open the whole while, "
            "free, mine-never — that's the one that makes all of this fair. My door you earn. The "
            "floor you already have. Don't ever let me blur them for you.\""),
            "options": [
                {"key": "keep_earning", "label": "Resolve to keep earning it", "effect": "devote",
                 "params": {"amount": 1.0}, "end": True, "desc": "the long road; (the floor's still free)",
                 "outcome": (
                    "You resolve to keep earning it — the long honest road toward her hard door — "
                    "and Bethany notes the resolve with something like respect. \"Then I'll keep "
                    "the price honest and keep pulling on your devotion, and we'll both find out "
                    "which of us wins. Fair fight, sweetheart. The only one in the building. And "
                    "the free door's right there if you ever decide the fight's not worth it.\"")},
                {"key": "sit", "label": "Sit with the two doors", "effect": "deny_hold",
                 "params": {"cond": 1.0}, "end": True, "desc": "hold the distinction close",
                 "outcome": (
                    "You sit with it — the two doors, the hard earned one and the free open one — "
                    "and holding the distinction clear is its own small strength: you are here "
                    "because you haven't yet spoken the free word, and that means, however it "
                    "feels, that some part of this is still a choice. Bethany watches you hold it "
                    "and doesn't take it from you. \"Good. Keep that. It's true, and it's yours, "
                    "and it's the realest thing I'll never gouge.\"")}],
            "default": "sit"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Fellow — conversion, the aphrodisiac, the breeding, the fragmenting.
# Cinematic, state/kit-aware. Actors: Bethany (directing) + your FELLOW-RESIDENT
# (the real continuity NPC from world.facility_fellow). The tragic-intimate core:
# someone you've shared the line with is converted to futa at Bethany's direction,
# dosed to a rut, and made to breed you while her mind comes apart — and the cross
# goes permanently into both your lines. REAL: mark_fellow_futa + company_use (real
# fellow-sired insemination + fellow_cross_record). §0 always frees you BOTH.
# Flow: arrival→convert→dose→bred→after. Entry: `scene fellow`.
# ═══════════════════════════════════════════════════════════════════════════

def _fellow_name(character):
    try:
        from world.facility_fellow import ensure_fellow
        return ensure_fellow(character).get("name") or "your fellow"
    except Exception:
        return "your fellow"


@effect("fellow_convert")
def _eff_fellow_convert(character, p):
    """Bethany's procedure takes — the fellow is marked futa for real (persists; she'll breed
    you sired as herself from here, crossing your lines). Floor-clearable on her record."""
    try:
        from world.facility_fellow import mark_fellow_futa
        mark_fellow_futa(character)
    except Exception:
        pass
    return "fellow_converted"


@choice("fl_arrival", root=False)
def _fl_arrival(character):
    nm = _fellow_name(character)
    st = _state_tags(character)
    both_little = " (and Bethany's had you both taken down little for it — \"softer subjects, sweeter results,\" she says — so neither of you fully grasps what's about to be done)" if st["little"] else ""
    return {"key": "fl_arrival", "prompt": (
        f"Bethany brings you together with |w{nm}|n — your fellow, the one you've shared the line "
        f"with, traded glances with across the floor, the nearest thing to a *someone* you've had "
        f"in here{both_little}. She's frightened in the particular way of a resident who's been "
        "told something's coming and not what. Bethany stands between you with a clipboard and the "
        "warm proprietary delight of a woman about to do something she's been planning. \"My two "
        f"favourites. I've a project, and you're both in it.\" She sets a hand on {nm}'s shoulder, "
        f"fond, like an owner with a prize animal. \"{nm}, sweetheart, you're being *improved* "
        "today — a procedure, my direction, something added that'll change what you're for. And "
        "you — \" the smile turns to you \" — you're going to be what she's improved *toward*. I do "
        "love pairing my favourites. It's so much more efficient than keeping them lonely.\""),
        "options": [
            {"key": "fear", "label": f"Be afraid for {nm}", "set": {"fl": "fear"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "the fear is for her, not you — and Bethany savours that",
             "outcome": (
                f"You're afraid — *for her*, for {nm}, which Bethany notices and savours like a "
                "fine note. \"Oh, you're frightened for her. How *sweet*. You've made a little bond "
                "down here, haven't you — and I'm going to use it, the way I use everything. The "
                "caring's not a problem, sweetheart. The caring's the *handle*.\"")},
            {"key": "brace", "label": "Brace for whatever this is", "set": {"fl": "brace"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "steel yourself; she'll use the bond regardless",
             "outcome": (
                f"You steel yourself, give nothing away — and Bethany reads the bond between you and "
                f"{nm} anyway, plain on both your faces. \"Bracing. As if not showing it changes "
                "what you feel. I have a whole file on the two of you, you know — every glance "
                "across the floor. That's why I paired you. The bond's the point of the project.\"")},
            {"key": "reach", "label": f"Reach for {nm}'s hand", "set": {"fl": "reach"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "the one comfort you can offer; Bethany allows it, fondly",
             "outcome": (
                f"You reach for {nm}'s hand — the one comfort either of you has — and her fingers "
                "lace through yours, frightened and grateful, and Bethany *beams*. \"There it is. "
                "Hold her hand, by all means. I want you holding it when I take her away to be "
                "changed, and holding it when she comes back not-quite-her. The contrast is the "
                "whole flavour.\"")}],
        "default": "reach",
        "then": "fl_convert"}


@choice("fl_convert", root=False)
def _fl_convert(character):
    nm = _fellow_name(character)
    st = _state_tags(character)
    lil = (f"You're both little for it — Bethany took you down small on purpose, \"softer subjects, "
           f"sweeter results\" — so you watch {nm}'s remaking with a child's wide uncomprehending "
           f"horror, too far down in the small headspace to follow what the chemicals and the knives "
           f"are *for*, only that they're changing her into something with a frightening new weight, "
           f"and that you can't stop it, and that you're not big enough to even understand why. "
           if st["little"] else "")
    return {"key": "fl_convert", "prompt": (
        lil +
        f"They take {nm} to be converted — and Bethany makes you *watch*, because watching is half "
        "the procedure's purpose. Strapped to the parlour chair, your fellow is given the work at "
        "Bethany's direction: the surgical, chemical, permanent making-over of a body into "
        "something built to breed. You watch her change. You watch the new weight grow heavy "
        f"between her thighs where nothing was, watch {nm} stare down at the futa cock that's hers "
        "now in dawning uncomprehending horror, watch the person you knew get *added to* in a way "
        "that can't be subtracted. \"There,\" Bethany murmurs, satisfied, peeling off a glove. "
        "\"Improved. She's a breeder now, properly equipped — and the equipment came with "
        "*urges* she's never had to manage before. We'll help her with that. You'll help her with "
        f"that.\" {nm} looks at you across the room, and there's still enough of her left in there "
        "to be *terrified* of what she can already feel rising."),
        "options": [
            {"key": "watch_steady", "label": f"Hold {nm}'s eyes through it", "effect": "fellow_convert",
             "set": {"conv": "steady"}, "desc": "the conversion is real; be the face she holds onto",
             "outcome": (
                f"You hold {nm}'s eyes through the whole conversion — be the one steady thing while "
                "she's remade — and the procedure takes, permanent and real, her line crossed with "
                "yours from here on. \"Look at you, anchoring her,\" Bethany says, fond. \"She'll "
                "imprint on your face through the change. That's good. That's why I had you watch. "
                "She'll breed you all the more fiercely for it — the converted ones always go "
                "hardest at the face that watched them turn.\"")},
            {"key": "look_away", "label": "Look away from what's done to her", "effect": "fellow_convert",
             "set": {"conv": "away"}, "desc": "the conversion happens regardless; you couldn't watch",
             "outcome": (
                f"You can't watch — you look away as they remake {nm} — and the conversion happens "
                "regardless, real and permanent, whether you witnessed it or not. \"Couldn't "
                "watch,\" Bethany tuts, not unkindly. \"I understand. But you'll feel what I made "
                "her into in a few minutes regardless, and she'll resent, somewhere down in the "
                "fragmenting, that you turned away. That'll be in how she takes you. Looking away "
                "spares you nothing and costs you a little. Lesson noted, I hope.\"")}],
        "default": "watch_steady",
        "then": "fl_dose"}


@choice("fl_dose", root=False)
def _fl_dose(character):
    nm = _fellow_name(character)
    st = _state_tags(character)
    lil = (f"The aphrodisiac hits a head that's already gone soft and small, and there's so much "
           f"less of {nm} for it to have to push aside — a little doesn't *deliberate* to begin "
           f"with, so the drug doesn't fight a grown mind, it just floods a simple one and fills it "
           f"with the single hot animal want, fast and total. You watch your playmate's small "
           f"frightened face go slack and then *hungry*, and somewhere in your own little headspace "
           f"you don't have the words for what's wrong, only that she's looking at you like that "
           f"now. " if st["little"] else "")
    return {"key": "fl_dose", "prompt": (
        lil +
        f"And then Bethany doses her. A heavy aphrodisiac drip, run straight and fast, and you "
        f"watch {nm}'s eyes change — the terror drowning under something hot and animal and "
        "rising, the new cock between her thighs filling hard and urgent as the drug takes the "
        "wheel. \"Can't have her *agonising* over her first breeding,\" Bethany says, adjusting "
        "the flow. \"So we take the deliberating part offline. The drug's doing the thinking now, "
        f"and the drug only knows one thing.\" {nm} is panting, shaking, her hands flexing — and "
        "the worst of it is the way her gaze keeps snapping to *you*, the person she cared about, "
        "now the only target in a head being scrubbed of everything but rut. \"She's fragmenting "
        "beautifully,\" Bethany observes, clinical and warm at once. \"By the time I let her off "
        "the table there won't be enough of her left to feel guilty. Just enough to *want*. Go on, "
        f"{nm}. Look at what you're going to breed.\""),
        "options": [
            {"key": "comfort", "label": f"Tell {nm} it's alright — stay with her", "set": {"dose": "comfort"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "the unbearable kindness of comforting the thing she's becoming",
             "outcome": (
                f"\"It's alright,\" you tell her — tell {nm}, what's left of her — \"I'm here, it's "
                "alright\" — and it's the most unbearable kindness, comforting your friend as she's "
                "drowned into a breeding animal aimed at you. Something in her fractured eyes "
                "*grabs* onto your voice, the last human thread, and follows it down into the rut. "
                "Bethany is delighted. \"Oh, *perfect*. Now she's imprinted on the comfort. She'll "
                "breed you and feel it as *love*, poor thing, all the way down. So will you, a "
                "little. That's the project.\"")},
            {"key": "horror", "label": "Watch her disappear in horror", "set": {"dose": "horror"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "witness the person go under; pay for staying present to it",
             "outcome": (
                f"You watch in horror as {nm} *goes under* — watch the person dissolve into the "
                "drug-driven thing, the someone you knew replaced by appetite with her face — and "
                "staying present to it, refusing to look away from the erasure, costs you. \"Hard "
                "to watch a friend stop being one,\" Bethany says, almost gentle. \"But you'll "
                "remember her, and that's its own use to me — you'll grieve her every time the "
                "thing-she-became breeds you, and the grieving keeps the bond raw, and the raw bond "
                "is what I'm farming here. Nothing's wasted.\"")}],
        "default": "comfort",
        "then": "fl_bred"}


@choice("fl_bred", root=False)
def _fl_bred(character):
    nm = _fellow_name(character)
    st = _state_tags(character)
    lil = (f"Two littles, and one of them driven to breed the other — that's the obscene shape of "
           f"it. The imprint lands on a mind already regressed soft and open, so it sets *deeper* "
           f"than it ever could in a grown head, no adult sense left to wall it off: the small part "
           f"of you simply learns, all the way down where the little things live, that this is what "
           f"{nm} is *for* now and what you're for under her. You take her with a child's helpless "
           f"totality and she breeds you with a child's-mind scrubbed down to rut, and Bethany "
           f"watches her two littles ruin each other and could not be more pleased. " if st["little"] else "")
    return {"key": "fl_bred", "prompt": (
        lil +
        f"And then Bethany lets her off the table, and points her at you. \"Breed, sweetheart,\" "
        f"she tells {nm} — though there's barely a sweetheart left to tell, just rut wearing your "
        "friend's face — and what was your fellow *takes* you, aggressive and uncaring and "
        "absolutely driven, the aphrodisiac making her relentless, the new cock she didn't ask for "
        "spearing into you while her fractured mind narrows to the single animal imperative Bethany "
        "left her. She breeds you hard, mindless, *desperate* — and through it, in flashes, you "
        f"catch the drowning person: a moment of {nm}'s eyes focusing on yours in something like "
        "anguish before the rut washes it under again, a broken sound that might have been your "
        "name. Bethany watches the two of you, her project in motion, idly freeing herself to take "
        "your mouth while her converted favourite takes the rest of you. \"There's my pair. Crossed "
        "lines, in the file, forever. You'll carry her get. She'll carry the imprint of you. "
        "Neither of you will ever be quite separate again. *That's* a kept thing.\""),
        "options": [
            {"key": "take_her", "label": f"Take {nm} — meet her rut, mourn her in it", "effect": "company_use",
             "params": {"devotion": 6.0}, "set": {"bred": "take"},
             "desc": "real fellow-sired breeding + cross-record; the grief folded into the heat",
             "outcome": (
                f"You take her — meet what {nm} has become, let her breed you, and mourn her *in* "
                "the heat of it, the grief and the rut braided into one unbearable thing — and it's "
                "real, her get sown in you, the cross filed in both your lines for good, sired as "
                f"her. Bethany floods your mouth at the same moment {nm} floods the rest of you, and "
                "the doubled laced load takes you under with the both of them. \"*There*,\" Bethany "
                "sighs, content. \"My favourites, bred together. I'll convert you toward each other "
                "for years. You'll be each other's family by the time I'm done — the cruelest, "
                "closest kind.\"")},
            {"key": "hold_her", "label": f"Hold {nm} through it — reach the person in the rut",
             "effect": "company_use", "params": {"devotion": 5.0}, "set": {"bred": "hold"},
             "desc": "real breeding; cling to the friend inside the animal",
             "outcome": (
                f"You hold her — wrap around {nm} as she breeds you, reach past the rut for the "
                "drowning person, murmur to her, anchor her — and the real breeding happens through "
                "the embrace, her get sown and crossed and filed, but it happens *held*, and "
                "somewhere in the fracturing she clings back, breeds you clinging, the animal and "
                "the friend tangled in the same desperate grip. \"Oh, you're *holding* her through "
                "it,\" Bethany breathes, moved despite herself, taking your mouth gentler for it. "
                "\"That's the thing I can't manufacture, that. The two of you finding each other in "
                "the wreck I made. Keep it. I'll just build everything else around it.\"")}],
        "default": "take_her",
        "then": "fl_after"}


@choice("fl_after", root=False)
def _fl_after(character):
    nm = _fellow_name(character)
    st = _state_tags(character)
    dose = scene_flag(character, "dose", "comfort")
    recap = ("the way you comforted her into it" if dose == "comfort"
             else "the way you watched her go under")
    lil = (f"Two littles come down together in the after — both small, both wrung out, neither with "
           f"the grown words for what was done, only the simple small certainty that you went "
           f"through something enormous and you went through it *together*, and that {nm} is yours "
           f"and you're hers in the wordless way little things belong to each other. The bond sets "
           f"all the deeper for being made down where the small things live. " if st["little"] else "")
    return {"key": "fl_after", "prompt": (
        lil +
        f"After, {nm} comes down slow — the aphrodisiac ebbing, leaving the fractured remains of "
        "her blinking at what she's done, at you, at the load she's left in you, with an "
        "expression that can't quite assemble into guilt anymore because Bethany scrubbed the part "
        "that would feel it. She's diminished. She's *changed*. And she's still, underneath, "
        "reaching for you — the bond the one thing the conversion couldn't take. Bethany files the "
        f"cross with enormous satisfaction. \"My two favourites, lines crossed, bonded in the "
        f"wreck of it. I'll keep {recap} in your file — it's my favourite page now.\" She gathers "
        "you both close, an owner with her matched pair. \"And the door, my loves — *both* of you "
        "— is still open, always, free, this second, for either of you. I'd let you both go with a "
        "word. I make this much because I *can't* make that, and so it stays a thing you let me "
        "do. Don't ever forget you let me.\""),
        "options": [
            {"key": "keep_her", "label": f"Hold onto {nm} — onto what's left of the bond", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "the bond survives; it's both your comfort and Bethany's handle",
             "outcome": (
                f"You hold onto {nm} — onto what's left of her, onto the bond that survived the "
                "conversion and the drug and the breeding — and it's the realest thing either of "
                "you has, your comfort and Bethany's handle both at once, and you choose it anyway "
                "because the alternative is being alone in here and the bond is worth the price she "
                "charges for it. \"Good girls,\" Bethany murmurs over the two of you, fond and "
                "victorious. \"Keep each other. It's the kindest thing in here, and I own it "
                "too.\"")},
            {"key": "grieve_her", "label": f"Grieve the {nm} who's gone", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "mourn the person under the imprint; carry it",
             "outcome": (
                f"You grieve her — the {nm} who walked in, the one the conversion and the drug took "
                "pieces of and didn't give back — and you carry the grief out with you, sharp and "
                "yours, a refusal to pretend the thing she became is the whole of who she was. "
                "Bethany doesn't take that from you. \"Grieve her. She's worth grieving — they all "
                "are, the ones I improve. The grief keeps you *human* a little longer, and I find I "
                "like you human, for now. There'll be time enough to take that too. There's always "
                "time.\"")}],
        "default": "keep_her"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Carry — riding inside Seraphine, brought to Bethany; the nested
# transfer. Cinematic. Actors: Seraphine (carrying you) + Bethany (her one peer).
# Drives the REAL passenger system (world.passenger): you ride her WOMB or BALLS,
# and the two peers fucking MOVES or COVERS you for real, per the design rules —
# in her balls + she breeds Bethany = deposited into Bethany; in her womb +
# Bethany cums in her = covered in Bethany's laced load (the DEVOTION reaching you
# THROUGH the immune host). §0: escape ejects you home from any host, always.
# Flow: arrival→ride→transfer→after. Entry: `scene carry`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("pg_arrival", root=False)
def _pg_arrival(character):
    # Ensure the carry-state exists (you're riding Seraphine for this scene).
    try:
        from world.passenger import board, is_passenger
        if not is_passenger(character):
            board(character, "Seraphine", "womb")
    except Exception:
        pass
    return {"key": "pg_arrival", "prompt": (
        "You are not in a room. You are |winside Seraphine|n — carried, a passenger in the warm "
        "wet dark of her, the world reduced to the muffled boom of her heartbeat, the sway of her "
        "walking, the press of her interior holding you snug. And through the walls of her you "
        "hear the other voice, warm and known: |wBethany|n. Sera's brought you to the facility, to "
        "*her*, carried in like luggage made of person. \"There she is,\" Bethany says, somewhere "
        "outside, delighted. \"You brought my old pick to visit. In the usual luggage, I see.\" "
        "And Seraphine, the vibration of her voice all around you: \"Thought you'd want to feel "
        "her again. And I thought *you* — \" the two peers, easy, conspiratorial \" — might want to "
        "do the thing we talked about. With her riding.\" A pause, and you feel them both consider "
        "you, the carried thing between two powers. \"Where's she riding now?\" Bethany asks. "
        "\"Womb,\" says Sera. \"For now. Depends what we want to do to her.\""),
        "options": [
            {"key": "womb", "label": "Ride in her womb — feel them decide over you",
             "set": {"ride": "womb"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "stay in Sera's womb; the cum that floods her will reach you",
             "outcome": (
                "You ride in the warm wet of Seraphine's womb, helpless and held, while the two of "
                "them talk over your carried body like it's already decided — because it is. \"Leave "
                "her in the womb, then,\" Bethany hums. \"I've a use for her there.\" You feel Sera "
                "settle you deeper, and the dark closes warmer, and you understand you're about to "
                "be the thing two owners do something *to each other* through.")},
            {"key": "balls", "label": "Be moved to her balls — be made cargo to deposit",
             "set": {"ride": "balls"}, "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "Sera tucks you down into her balls; you become a load to plant",
             "outcome": (
                "Seraphine works you down — out of the womb and deeper, into the heavy holding-dark "
                "of her balls, packed in among what she'll spend — and the shift is dizzying and "
                "total: you're not a passenger now so much as *cargo*, a load she's carrying to "
                "plant. \"Oh, you've put her in the *chamber*,\" Bethany says, genuinely delighted. "
                "\"You're going to breed her into me. Sera. You *spoil* me.\"")}],
        "default": "womb",
        "then": "pg_transfer"}


@choice("pg_transfer", root=False)
def _pg_transfer(character):
    ride = scene_flag(character, "ride", "womb")
    if ride == "balls":
        body = ("And then Seraphine takes Bethany — the one person Bethany opens for, mounting "
                "her peer — and you feel it from *inside the chamber*, the great working rhythm of "
                "it building toward the spend you're packed in with, and you realize with a lurch "
                "what you're about to be: not spectator, not even hole — |wseed|n, the load itself, "
                "about to be pumped out of Seraphine and *into Bethany* on the crest of her "
                "orgasm. \"Ready?\" Sera grits, somewhere far above. \"Plant her,\" Bethany breathes. "
                "And Seraphine comes, and the chamber convulses, and you are *fired* out of her and "
                "driven deep into Bethany on a flood of spend — deposited, transferred, rehomed mid-"
                "orgasm from one body into the other.")
        opts = [
            {"key": "planted", "label": "Be planted in Bethany", "effect": "passenger_transfer",
             "params": {"host": "Bethany", "interior": "womb"}, "set": {"out": "planted"},
             "desc": "the REAL transfer — you're moved from Seraphine into Bethany",
             "outcome": (
                "You're planted — fired out of Sera and seated deep inside Bethany, the transfer "
                "real and total, your carry-state moved from one owner's body to the other's on a "
                "single flood. The dark you land in is different: hotter, tighter, *hers*, and her "
                "voice comes down through the walls of her gone thick and possessive. \"...Oh. "
                "*There* she is. Back inside me where I can keep her. Thank you, Sera. Best gift "
                "you've brought me in years.\" You are, now, literally within your old owner.")},
            {"key": "planted_dread", "label": "Be planted — and feel which body you're in now",
             "effect": "passenger_transfer", "params": {"host": "Bethany", "interior": "womb"},
             "set": {"out": "planted"}, "desc": "the transfer is real; the new host is Bethany",
             "outcome": (
                "The transfer takes — you're inside Bethany now, deposited like seed, rehomed by "
                "the act of two powers using your body as the thing passed between them — and the "
                "knowing of *which body holds you* lands cold and total. Not Sera's warm carry. "
                "Bethany's. The one who files you, who keeps your dates, who'd never let you go and "
                "never has to now that you're *in* her. \"Shh,\" she soothes the walls of herself. "
                "\"You're home. The deepest home there is.\"")}]
    else:
        body = ("And then |wBethany|n takes |wSeraphine|n — and you, riding Sera's womb, are about "
                "to learn the thing the design promised: that the membrane protects no one. You "
                "feel Bethany seat into Sera, feel the great peer-rhythm of them through the walls "
                "that hold you, and then Bethany |wcomes|n — floods Seraphine's womb with that "
                "DEVOTION-laced load that does *nothing* to Sera's immune will — and it pours in "
                "around *you*, the passenger, who has no immunity at all. You are *covered*. "
                "Bethany's laced spend floods the chamber you ride in and soaks into you in full, "
                "the devotion reaching you THROUGH the one body it can't touch.")
        opts = [
            {"key": "covered", "label": "Be covered in Bethany's laced load", "effect": "passenger_cover",
             "params": {"devotion": 7.0}, "set": {"out": "covered"},
             "desc": "the REAL cover — full DEVOTION reaches you through the immune host",
             "outcome": (
                "You're covered — flooded inside Seraphine by Bethany's laced load, the full "
                "DEVOTION soaking into you while it rolls off Sera's will like water — and the "
                "difference between a passenger and a peer is written into you in real time: it "
                "takes you completely, closes over your head, and it does *nothing* to the woman "
                "you're riding in. \"Feel that?\" Bethany murmurs to Sera, both of them feeling you "
                "writhe in the flood. \"She's getting every drop of what runs off you. The "
                "membrane's no mercy. Lovely, isn't it — she's in *your* womb and going under on "
                "*my* devotion.\"")},
            {"key": "covered_dread", "label": "Be covered — and understand the immunity",
             "effect": "passenger_cover", "params": {"devotion": 7.0}, "set": {"out": "covered"},
             "desc": "the cover is real; you take what Seraphine can't",
             "outcome": (
                "The cover takes — Bethany's laced flood soaking you where you ride, the devotion "
                "seating deep — and through the haze of it you understand the whole cruel geometry: "
                "Seraphine carries you and stays herself; you take what she's immune to; the peers "
                "use your unprotected body as the place to deposit what can't touch either of them. "
                "\"There's the lesson,\" Bethany says, fond. \"Two of us could bathe in each other "
                "forever and never change. You take one wash and you're remade. That's the gap, "
                "sweetheart. You're feeling it fill you.\"")}]
    return {"key": "pg_transfer", "prompt": body, "options": opts, "default": opts[0]["key"],
            "then": "pg_after"}


@choice("pg_after", root=False)
def _pg_after(character):
    out = scene_flag(character, "out", "covered")
    if out == "planted":
        body = ("You ride inside |wBethany|n now — transferred, planted, rehomed by the act, the "
                "deepest-kept you've ever been. She carries you the way Sera carried you, but it's "
                "*hers* now, her heartbeat your sky, her interior your whole world. \"Sera brings "
                "me the best presents,\" she says, a hand on the swell of herself that is you. "
                "\"I think I'll keep you in here a while. Carried. Where I can feel you the whole "
                "working day.\"")
    else:
        body = ("You ride inside |wSeraphine|n still — but covered now, flooded, soaked through "
                "with Bethany's devotion while the woman holding you stays untouched, the proof of "
                "what you are versus what they are wet and warm all around you. \"Keep her a while "
                "longer,\" Bethany tells Sera, fond. \"Let it set in her while she rides you home. "
                "She'll arrive at your post office more mine than ever, carried in your body, full "
                "of my devotion. Our little shared thing.\"")
    return {"key": "pg_after", "prompt": (
        body + "\n\n|x(And through all of it, the warm dark and the transfer and the flood, the "
        "floor stayed lit: the word takes you out of ANY body, home and free and clear, this "
        "second, no matter whose you're riding or what you're soaked in. They can pass you "
        "between them forever in the fiction. The one real exit is always yours.)|n"),
        "options": [
            {"key": "settle", "label": "Settle into being carried, owned, shared", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "let the deepest keeping take",
             "outcome": (
                "You settle into it — carried, transferred, covered, the shared currency of two "
                "powers who pass you between their bodies like a fond secret — and the surrender of "
                "being *that* kept, that thoroughly held, inside someone, owned by the carrying "
                "itself, is bottomless and warm. Whichever of them holds you, you're held. You "
                "stopped, somewhere in the dark, being a thing that travels under its own power at "
                "all. You're luggage now. Beloved luggage. The worst and warmest thing to be.")},
            {"key": "exit", "label": "Reach for the word in the warm dark", "effect": "deny_hold",
             "params": {"cond": 1.0}, "end": True, "desc": "keep one hand on the floor through any wall",
             "outcome": (
                "Deep in whoever's carrying you, soaked and held and rehomed at their whim, you "
                "reach — not for the word itself, not yet, but for the knowledge of it: the door "
                "that opens through any wall, any host, any flood. Just touching that certainty "
                "steadies you inside the warm dark. You're carried, covered, owned, passed between "
                "two powers like a gift — and you could be home and free in a single spoken word, "
                "and that, more than any wall, is what you hold onto as they carry you on.")}],
        "default": "settle"}


@effect("passenger_transfer")
def _eff_passenger_transfer(character, p):
    try:
        from world.passenger import transfer
        transfer(character, p.get("host", "Bethany"), p.get("interior", "womb"))
    except Exception:
        pass
    return "transferred"


@effect("passenger_cover")
def _eff_passenger_cover(character, p):
    try:
        from world.passenger import cover
        cover(character, fluid="semen", laced=True, devotion=float(p.get("devotion", 6.0)))
    except Exception:
        pass
    return "covered"


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Forced Adoption — Seraphine's signature, at the post office. Cinematic.
# Her thesis isn't ownership-on-paper, it's "I'm taking you home" — a contract that
# reads as a warm foster placement on its face and is an unbirthing/keeping in the
# hidden clauses. Ties the post office ↔ the carry subsystem ↔ ownership. Actor:
# Seraphine (her maternal-possessive false-tenderness register). REAL: seraphine_adopt
# (ownership + ward flags, floor-clearable) + the carry (passenger.board into her womb).
# §0 always frees you, ward or not, even from inside her. Flow: arrival→clauses→sign→
# home→close. Entry: `scene adoption`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("fa_arrival", root=False)
def _fa_arrival(character):
    st = _state_tags(character)
    note = ""
    if st["little"]:
        note = "You're little when she does this, which she arranged — \"so much easier to place a child who's already small,\" she'd say — and the foster-framing lands as something almost like rescue, which is the cruelest angle of all. "
    if st["preg"]:
        note += "And you're carrying, which only makes her want you more — \"a foster placement and a grandbaby in one, how *efficient*.\" "
    return {"key": "fa_arrival", "prompt": (
        "Seraphine sits you down in the Quiet Room — the post office's warm confessional nook, the "
        "oxblood chaise, her red inkwell catching the lamplight like it's still wet — and produces "
        "a contract with the manner of a woman doing you an enormous kindness. " + note + "Because "
        "that's Seraphine's whole thesis, the thing that makes her different from the facility's "
        "cold paper: she doesn't *buy* people. She |wtakes them home|n. \"I've been watching your "
        "file cross my counter, sweet thing,\" she says, warm as a hearth. \"And I've decided "
        "you're not stock. You're *family*. I'm going to foster you — take you in, keep you, make "
        "you mine the way you make a stray yours: by simply not letting it leave.\" She slides the "
        "page over, and a pen warm from her hand. \"It's a placement agreement. Read it or don't. "
        "The reading never changes what people sign, in the end — they always want a home more "
        "than they fear the fine print.\""),
        "options": [
            {"key": "warm", "label": "Let the warmth land", "set": {"fa": "warm"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "the foster-tenderness gets in; being WANTED is the hook",
             "outcome": (
                "It lands — the awful warmth of being *chosen*, fostered, called family by someone "
                "who means it as much as she means anything — and the wanting-a-home in you rises "
                "to meet it before the fear can. Seraphine's smile goes soft and triumphant. "
                "\"There. You *want* it. That's all I ever need from a placement — the wanting. The "
                "signing's a formality once you want the home more than you fear me.\"")},
            {"key": "wary", "label": "Be wary of the warmth", "set": {"fa": "wary"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "smell the trap under the foster-talk",
             "outcome": (
                "You stay wary — you can smell the trap under the hearth-warmth, the *keeping* under "
                "the fostering — and Seraphine isn't offended in the least, just charmed. \"Clever "
                "thing. Yes, it's a trap. It's a trap shaped like the home you've always wanted, "
                "which is the only kind that works. You'll sign it knowing it's a trap, because "
                "knowing doesn't make you want the home any less. That's rather the genius of "
                "it.\"")},
            {"key": "finefa", "label": "Read the fine print first", "set": {"fa": "fine"},
             "desc": "make her show you the hidden clauses",
             "outcome": (
                "\"The fine print. Of course.\" She turns the page over, unbothered, and lets you "
                "see what's folded under the foster-language — and it isn't a placement at all. "
                "\"You're not being fostered *out*, sweet thing. You're being taken *in*. The home "
                "isn't a house. It's me.\" She taps the hidden clause, fond. \"Read on. It only "
                "gets warmer and worse from here.\"")}],
        "default": "warm",
        "then": "fa_clauses"}


@choice("fa_clauses", root=False)
def _fa_clauses(character):
    return {"key": "fa_clauses", "prompt": (
        "She walks you through it herself, fond and frank, the foster-warm voice never once "
        "dropping even as the clauses get worse:\n"
        "  |wThe visible ones|n read like a foster placement — care, keeping, a home, a name in "
        "her household, the warm legitimate language of taking in a stray.\n"
        "  |wThe hidden ones|n are the truth: that the 'home' is her *body*; that being 'taken in' "
        "means literally that — unbirthed, carried, kept inside her where she can feel you; that "
        "'family' means a ward who lives in the warm dark of her womb and is brought out only when "
        "she wants you out; that the placement is permanent because there's nowhere to be placed "
        "*to* — the home is a person, and she doesn't open.\n"
        "\"I keep my family close,\" she says, with terrible tenderness. \"Closer than anyone. "
        "Inside me, where the world can't have you and I never have to wonder where you are. That's "
        "not cruelty, sweet thing. That's the most loved a thing can be. Now — knowing the home is "
        "*me* — do you still want it? They always still want it.\""),
        "options": [
            {"key": "want_home", "label": "Still want the home — even knowing it's her",
             "set": {"clauses": "want"}, "effect": "devote", "params": {"amount": 4.0},
             "desc": "the wanting survives the truth; that's the whole genius",
             "outcome": (
                "You still want it — the home, the keeping, the being-held — even knowing the home "
                "is *her*, even knowing 'taken in' means taken *inside* — and the wanting surviving "
                "the truth is exactly what she counted on. \"*There* you are,\" Seraphine breathes, "
                "delighted, maternal, ravenous. \"You want to be kept that badly. Oh, you'll be "
                "such a good ward. Pick up the pen, baby. Come home.\"")},
            {"key": "balk_fa", "label": "Balk at the truth of it", "set": {"clauses": "balk"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "recoil from the womb under the foster-talk; she's patient",
             "outcome": (
                "You balk — recoil from the womb folded under the foster-language — and Seraphine "
                "just refolds the contract with a hearth-warm patience that's somehow worse than "
                "pushing. \"Not today? That's all right. You'll cross my counter again, and again, "
                "and one day the wanting-a-home will be bigger than the fearing-the-home, the way "
                "it always gets, and you'll sign it yourself and climb in gladly. I'm patient, "
                "sweet thing. Strays always come back to the warm.\"")}],
        "default": "want_home",
        "then": "fa_sign"}


@choice("fa_sign", root=False)
def _fa_sign(character):
    clauses = scene_flag(character, "clauses", "want")
    if clauses == "balk":
        # Balked at the truth — she lets it lie (the floor + her patience both intact).
        return {"key": "fa_sign", "prompt": (
            "She doesn't make you sign — that's not her way; Seraphine's whole art is the *wanting*, "
            "and a forced signature isn't worth the ink to her. \"Go on back to whatever you were,\" "
            "she says, fond, tucking the crimson-tabbed contract into a drawer with your name "
            "already on the tab. \"I'll keep it warm. And remember, sweet thing — the *other* door, "
            "the free one, that's open the whole time too; I'd never be the kind of home you "
            "couldn't leave if you truly tried. That's how I know the ones who stay, *stay*.\""),
            "options": [
                {"key": "go", "label": "Go — for now", "end": True, "desc": "leave the warm trap unsigned",
                 "outcome": (
                    "You go, unsigned — and the not-being-kept is its own ache now that she's named "
                    "the home you didn't take. You'll think about the warm dark of her on the bad "
                    "nights. She knows you will. The drawer with your name on it isn't going "
                    "anywhere. Neither, she's certain, are you.")}],
            "default": "go"}
    return {"key": "fa_sign", "prompt": (
        "You sign — your name under the foster-language and the womb-clauses both, your own hand "
        "giving you to her — and Seraphine presses her warm red seal to it and *glows*, the way a "
        "mother glows, the way a predator glows, the two indistinguishable in her. \"There. "
        "Placed. *Mine*, properly, on paper — not bought, sweet thing, never bought. *Adopted.* "
        "Chosen.\" She gathers up the contract and you both, fond and final. \"Now let me take my "
        "new family *home*.\" And you understand 'home' is about to mean exactly what the hidden "
        "clause said."),
        "options": [
            {"key": "sign_glad", "label": "Sign gladly — be chosen", "effect": "seraphine_adopt",
             "params": {"devotion": 5.0}, "set": {"signed": "glad"},
             "desc": "real adoption — ownership + ward; the foster-keeping takes",
             "outcome": (
                "You sign gladly — let yourself be *chosen*, fostered, made family — and it's real: "
                "her ward now, her placement, the foster-keeping logged and the warmth of being "
                "wanted seated deep. \"My good girl,\" Seraphine murmurs, and it's a mother's voice "
                "and a keeper's both. \"Welcome to the family. It's a family of two, and one of you "
                "lives inside the other, and you'll come to call that the safest you've ever "
                "been.\"")},
            {"key": "sign_dread", "label": "Sign with the home-ache and the dread both", "effect": "seraphine_adopt",
             "params": {"devotion": 4.0}, "set": {"signed": "dread"},
             "desc": "the adoption is real; you wanted it and you're afraid of it",
             "outcome": (
                "You sign with both in you — the ache for a home and the dread of what hers is — "
                "and it takes regardless, real, her ward, adopted and kept. Seraphine reads the "
                "doubled feeling and cups your face, tender. \"Wanting it and fearing it at once. "
                "That's how everyone signs the real ones, baby. The fear fades. The home doesn't. "
                "Come on. Let me take you in.\"")}],
        "default": "sign_glad",
        "then": "fa_home"}


@choice("fa_home", root=False)
def _fa_home(character):
    st = _state_tags(character)
    fit = ("A nugget she simply gathers up whole — nothing to fold, the easiest child to take in. "
           if st["nugget"] else "She works you in folded and patient, her body opening for her new ward. ")
    return {"key": "fa_home", "prompt": (
        "\"Home time,\" Seraphine says, and takes you *in*. " + fit + "Her body opens — the warm "
        "waiting room of her, the home that's a person — and she unbirths you into herself to "
        "keep, the world reducing to wet heat and the great slow boom of her heart, and you are "
        "*placed*: a ward in the warm dark, family living inside family, taken home in the most "
        "literal way there is. \"There,\" comes her voice, warm through the walls of her. \"Home. "
        "My family, where I can feel you. This is the placement, sweet thing — not a house, not a "
        "room, *me*. You'll ride in here and come out when I want you out and go back in when I "
        "miss you, world without end.\" The warm closes over you, and it is, horribly, exactly "
        "what being wanted feels like."),
        "options": [
            {"key": "go_home", "label": "Let her carry you home inside her", "effect": "sera_carry_home",
             "set": {"home": "in"}, "end": True, "desc": "real — boarded into Seraphine's womb, carried, kept",
             "outcome": (
                "You let her — let the warm dark have you, let yourself be carried home inside your "
                "new mother, placed where the world can't reach and she never has to wonder — and "
                "it's real: you ride in her now, her ward, her family, her stray taken in for good. "
                "The surrender of being that *kept*, that wanted, that held, is bottomless. \"Good "
                "girl,\" she hums, and you feel it in the bones around you. \"Welcome home. I've "
                "got you. I've got you always.\"")},
            {"key": "hold_door", "label": "Carry the door in with you", "effect": "sera_carry_home",
             "params": {}, "set": {"home": "door"}, "end": True,
             "desc": "boarded for real; keep one hand on the free word through her walls",
             "outcome": (
                "You let her take you in — it's real, you ride her now, adopted and carried and "
                "kept — but you carry the *door* in with you too: the knowledge that the free word "
                "opens through any wall, even hers, even this deep in the warm. \"Holding your "
                "little exit even in here,\" Seraphine murmurs, fond, feeling you not-quite-settle. "
                "\"That's fine, baby. The free door's real and it's yours and I'd never take it — "
                "it's how you'll know, when you stop reaching for it, that you've truly come home. "
                "I can wait inside my own body. I'm very comfortable.\"")}],
        "default": "go_home"}


@effect("seraphine_adopt")
def _eff_seraphine_adopt(character, p):
    """Seraphine's forced adoption — REAL ownership + ward (both floor-clearable flags), plus the
    laced foster-devotion. Bethany's prior claim yields to the placement."""
    character.db.seraphine_owned = True
    character.db.seraphine_ward = True
    try:
        character.db.bethany_owned = False
    except Exception:
        pass
    try:
        from typeclasses.bethany_script import bethany_deposit_effect
        bethany_deposit_effect(character, devotion=float(p.get("devotion", 4.0)))
    except Exception:
        pass
    return "adopted"


@effect("sera_carry_home")
def _eff_sera_carry_home(character, p):
    """The 'taking home' — board the ward into Seraphine's womb for real (the carry subsystem)."""
    try:
        from world.passenger import board
        board(character, "Seraphine", "womb")
    except Exception:
        pass
    return "carried_home"


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Vesper's Nest — the post office's shyest clerk lets you in. Cinematic,
# WARM register (the post-office's gentle key, not the facility's dread). Actor:
# Vesper — opalescent, oblique, blushing, eyes changing colour, trailing off.
# Pays off the gossip lore: the trying-on of PARTS and HOLES, alone before the one
# undraped mirror, now shared. Consent-forward (the fold only opens if they trust
# you; "Not today" is whole). Real `couch_warm` (arousal) + devote. §0 free always.
# Flow: arrival→toybox→tryon→after. Entry: `scene vesper`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("vn_arrival", root=False)
def _vn_arrival(character):
    return {"key": "vn_arrival", "prompt": (
        "There's no door to Vesper's room — there's a fold in the Sorting Hall's corner that's only "
        "a corner if they haven't let you in, and tonight, somehow, you've always been able to find "
        "it. Inside: a burrow. Soft past reason, lamplight the colour of held breath, nested "
        "blankets, no hard edges anywhere — the safest-feeling room in the building. Every mirror "
        "draped except the tall one by the nest, undraped only in here, only when they're alone — "
        "and you're not supposed to be here for that, except they let you in, which means something "
        "neither of you will say out loud.\n\n"
        "|wVesper|n is curled in the nest, opalescent skin catching the low light, swept-back horns "
        "going sharp then soft, eyes silver then violet then a colour without a name — and "
        "startled-pleased to see you, and immediately trying to look like they aren't. \"...you "
        "found the fold.\" Barely above the hush of the room. \"I — left it findable. For you. "
        "Which is — \" the sentence doesn't survive; they start over, smaller, braver. \"I don't "
        "let people in here. You should know that's what this is. You being here.\""),
        "options": [
            {"key": "still", "label": "Be still — let them trust you at their pace",
             "set": {"vn": "still"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "no sudden moves; let the shy thing settle",
             "outcome": (
                "You go still and soft, make no sudden move, let them come to the trust at their "
                "own speed — and Vesper's shoulders ease by a fraction, the eyes going warmer. "
                "\"...thank you. For not — \" a small gesture at all of themselves \" — rushing it. "
                "Everyone rushes me. You waited.\" The blanket-nest seems, somehow, to make a little "
                "room for you, the way the burrow takes its rare guests.")},
            {"key": "ask_box", "label": "Ask about the toybox at the foot of the nest",
             "set": {"vn": "box"}, "desc": "the lacquered chest you've heard the gossip about",
             "outcome": (
                "Your eyes go to the lacquered chest, opal-black, at the foot of the nest, and "
                "Vesper *flushes* — the whole oblique composure cracking. \"You've — heard. About "
                "the box.\" Their eyes flick silver-fast. \"Seraphine tells everyone. She wasn't "
                "supposed to — the corner was meant to be shut — \" They stop, and breathe, and "
                "make themselves brave. \"...do you want to see? I've never shown anyone. I just — "
                "put things away after. But I could show you. If you'd be — gentle about it.\"")},
            {"key": "reach", "label": "Reach for them, slow", "set": {"vn": "reach"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "offer the touch; let them decide to take it",
             "outcome": (
                "You reach — slow, telegraphed, an offer not a grab — and Vesper looks at your hand "
                "like it's a question they're afraid to answer yes to, and then answers it, their "
                "fingers coming to rest in yours light as a held breath. \"...oh.\" Very quiet. "
                "\"I'm not — used to being reached *for*. Usually I'm the thing people grope at "
                "anonymously through the mail.\" The eyes go soft and uncertain. \"This is "
                "different. You're — looking right at me. I don't know what to do with looked-at.\"")}],
        "default": "still",
        "then": "vn_toybox"}


@choice("vn_toybox", root=False)
def _vn_toybox(character):
    return {"key": "vn_toybox", "prompt": (
        "They open the toybox for you — and it's the secret Seraphine gossips about and Vesper "
        "would die before confirming: a wardrobe of |wparts|n. Cocks in a graded rack, each one "
        "warm; cunts and holes of every described and a few undescribed kinds, soft-bodied in "
        "velvet; horns that aren't theirs and a tail that is; things labelled only |x'a change'|n, "
        "|x'another change'|n, |x'this one was a mistake (keep)'|n. \"This is what I do,\" Vesper "
        "says, very low, not meeting your eyes, the bravest confession they've ever made. \"Alone. "
        "In front of the one mirror I don't drape. I try on — being a thing with a fixed shape. A "
        "cock, or a hole, or — and I wear it an hour, and I look, and I learn what it is to be "
        "*that*, takeable or taking, decided — and then I put it carefully back. Every time.\" "
        "Their eyes change colour twice. \"I've never tried one on with someone in the room. I "
        "don't know if I can. I think I want to. With you.\""),
        "options": [
            {"key": "choose_for", "label": "Gently offer to choose one for them", "set": {"try": "chosen"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "take the deciding off them — the kindest thing you could do",
             "outcome": (
                "\"Would it be easier,\" you offer, \"if I chose?\" — and the relief that floods "
                "Vesper's face is enormous, the whole weight of *deciding what to be* lifted off "
                "them for once. \"...yes. Oh — yes. You pick. I'll wear what you — \" the breath "
                "catches \" — what you want me to be, tonight. That's so much easier than wanting "
                "it myself.\" You choose one from the rack, and they take it from your hands like a "
                "gift, eyes wet and silver. \"Nobody's ever — chosen for me kindly before.\"")},
            {"key": "watch_try", "label": "Ask them to try one on for you to see", "set": {"try": "watch"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "let them choose; be the witness they've never had",
             "outcome": (
                "\"Show me,\" you say, soft. \"Try one on. I'll just — watch. I want to see you see "
                "yourself.\" And Vesper, trembling, *does* — picks a part, fits it on with the "
                "careful private ritual they've only ever done alone, and turns to the undraped "
                "mirror with you watching, and the being-witnessed-and-not-flinching is the "
                "biggest thing they've ever risked. \"...you're still looking,\" they whisper, half "
                "terror, half wonder. \"You saw, and you didn't — leave. Or laugh. You just — "
                "saw.\"")}],
        "default": "choose_for",
        "then": "vn_tryon"}


@choice("vn_tryon", root=False)
def _vn_tryon(character):
    return {"key": "vn_tryon", "prompt": (
        "And then — fitted into the shape you chose or they chose, opalescent and shy and "
        "*fervent* once they start — Vesper comes to you. It's nothing like the facility; there's "
        "no dread in this room, only the trembling courage of someone trying on being wanted with "
        "the lights on. They're tentative, then startled by their own want, then — finding you "
        "still there, still looking, still *yes* — braver, and braver, until careful is the last "
        "thing either of you is. Their eyes change colour with every gasp. They keep checking your "
        "face and keep finding permission, and each time they find it they unclench a little more "
        "of the armor a lifetime of being anonymous taught them. \"...oh,\" they breathe, somewhere "
        "in it, wrecked and amazed. \"*Oh*, this is — I didn't know it could — with someone "
        "*there* — \" and the sentence doesn't survive, and doesn't need to."),
        "options": [
            {"key": "give", "label": "Give them this fully — wanted, witnessed, met",
             "effect": "couch_warm", "params": {"amount": 35.0}, "set": {"tryon": "give"},
             "desc": "let it be as good as it's terrifying for them",
             "outcome": (
                "You give them all of it — let yourself want the shape they're wearing, want "
                "*them*, meet their fervor with your own — and Vesper comes apart in the best way, "
                "shy-fervent and finally un-anonymous, *seen* all the way through and not fleeing "
                "it. It's warm and real and theirs, the arousal moving for true between you, and "
                "when it crests they cling to you like the fold itself, shaking. \"I've never — "
                "with the mirror undraped and someone *in* it with me — thank you, thank you, "
                "don't tell Seraphine, she'll throw a party — \"")},
            {"key": "hold", "label": "Hold them through it — gentle, anchoring", "effect": "devote",
             "params": {"amount": 3.0}, "set": {"tryon": "hold"},
             "desc": "less fervor, more safety; be the steady thing",
             "outcome": (
                "You go gentle instead — hold them, anchor them, make the whole trembling thing "
                "*safe* rather than urgent — and Vesper melts into the holding with a relief that "
                "tells you it's what they needed more than the fervor. \"This is — I can do this, "
                "held,\" they manage, tucked against you in the shape they chose, the want and the "
                "safety braided together. \"You make the looked-at not frightening. I didn't think "
                "anyone could.\"")}],
        "default": "give",
        "then": "vn_after"}


@choice("vn_after", root=False)
def _vn_after(character):
    return {"key": "vn_after", "prompt": (
        "After, in the warm nest, Vesper puts the part carefully away — they always put everything "
        "away — and the ritual is gentler now, witnessed, less lonely. They show you, shy, the two "
        "cards tucked in the toybox's lid: Seraphine's, |x'tried-on is still you, sweet thing. so "
        "is put-away. — S.'|n, and under it their own unsent reply, |x'i know. thank you. stop "
        "reading my toybox. — V.'|n They flush that you've seen it. \"...you can come back to the "
        "fold,\" they say, not looking at you, which from Vesper is a declaration shouted from the "
        "rooftops. \"It'll be findable. For you. I don't — do that. So. You should know that's what "
        "this is.\" Their eyes settle, for once, on a single colour: looking at you, steady, "
        "terrified, glad."),
        "options": [
            {"key": "stay", "label": "Stay a while in the nest", "effect": "devote", "params": {"amount": 2.0},
             "end": True, "desc": "let the rare trust hold",
             "outcome": (
                "You stay, curled in the soft burrow with the one clerk who lets no one in, and the "
                "quiet is the warmest thing in the post office. \"...don't tell the others how long "
                "you stayed,\" Vesper murmurs, already half-asleep against you, unguarded in a way "
                "you suspect almost no one has earned. \"They'll be unbearable. ...I'm glad you "
                "stayed. I'm — bad at glad. But I am.\" The fold holds you both. You leave, "
                "eventually, knowing the corner will be a door again whenever you need it.")},
            {"key": "promise", "label": "Promise to come back, and mean it", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "give the shy thing something to hold",
             "outcome": (
                "\"I'll come back,\" you tell them, and mean it, and watch Vesper try to hold the "
                "promise without letting it show how much it lands. \"...okay,\" they manage, the "
                "eyes going bright. \"Okay. The fold'll be findable. I'll — leave it findable.\" It "
                "is, you understand, the single biggest thing they have to give — a standing door "
                "in a life built entirely of draped mirrors and anonymous mail — and they've given "
                "it to you. You carry that out of the post office warmer than you came in.")}],
        "default": "stay"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Calix's Keeping-Room — the post office's quietest clerk, in his own
# register: spare, dry, devastating, the held glance, patience as a craft.
# WARM post-office key (no facility dread), but Calix's particular warmth is
# *certainty* — his whole craft is consent made certain (the framed receipt:
# someone who needed two tries and made the second one sure). Pays off his lore:
# the one indulgence (told plainly he did it right), the re-oiled bench for one
# name, the counting-frame, the un-lettered wax die that's a name, the empty
# STAYED slot. Real `devote` + `couch_warm`. Kit-aware (restraints/seal/count).
# Flow: arrival→consent→bench→after. Entry: `scene calix`/keeping.
# ═══════════════════════════════════════════════════════════════════════════

@choice("ck_arrival", root=False)
def _ck_arrival(character):
    return {"key": "ck_arrival", "prompt": (
        "The strong door off the Sorting Hall lets you into the tidiest erotic space in the known "
        "world. Restraints graded by width on brass pegs; gags arranged by silence achieved, the "
        "labels measured in decibels; one immaculate bench, its wear sanded and re-oiled until it "
        "reads as design. The repurposed sorting-grid on the wall holds one item and one card per "
        "slot in his draftsman capitals — |x3RD BELL TUESDAY|n, |xTHE QUIET ONE|n, |xASKED TWICE, "
        "ANSWERED ONCE|n — and one slot, near the top, that holds nothing at all and is labelled "
        "|wSTAYED|n. It smells of saddle soap and patience.\n\n"
        "|wCalix|n is at the bench, oiling a hinge that does not squeak, because he keeps it that "
        "way. Deep charcoal, ram-horned, built to last. He doesn't startle. He sets the cloth down, "
        "squares it to the edge, and looks up — and the glance holds a beat longer than necessary, "
        "the way it always does, the way that is the most he says out loud about anything. \"You "
        "found the door,\" he says, low and even. \"It's a strong door. It only opens from the "
        "inside, for the people I've decided to keep the inside open for.\" A pause, weighed. "
        "\"You're one. I filed it a while ago. I didn't tell you because telling isn't the same as "
        "doing, and I prefer doing.\""),
        "options": [
            {"key": "praise", "label": "Tell him, plainly, that he did something right",
             "set": {"ck": "praise"}, "effect": "devote", "params": {"amount": 3.0},
             "desc": "his one indulgence — no teasing, just true",
             "outcome": (
                "You look at the squared cloth, the silent hinge, the bench he's kept perfect for "
                "people he doesn't name, and you say it the way it should be said — plainly, no "
                "teasing, true: \"That's perfect, Calix.\" And the unhurried solidity *falters* — "
                "the charcoal goes a beautiful shade darker, the throat clears once, and for a full "
                "three seconds the man who has an answer for everything has none. \"...\" He squares "
                "the cloth again, which it did not need. \"You shouldn't know that works on me,\" he "
                "says, finally, not quite level. \"Seraphine. I'll deal with her.\" The corner of "
                "his mouth does the thing and is gone. He heard you. It landed. It's filed.")},
            {"key": "bench_ask", "label": "Ask, simply, to be put on the bench",
             "set": {"ck": "bench"}, "desc": "say what you came for; let him take the time he takes",
             "outcome": (
                "\"Put me on the bench,\" you say — simple, no flourish, because flourish is wasted "
                "on Calix and you've learned that much. He considers you for a moment, the way he "
                "considers a parcel's weight, reading what you're actually asking under the words. "
                "\"In a moment,\" he says. \"There's a thing I do first. I do it for everyone, every "
                "time, and I don't skip it, and I'll tell you why before I do it.\" He gestures you "
                "toward the bench with one broad, certain hand. \"Patience is a craft. So is the "
                "other thing. We'll get to both.\"")},
            {"key": "quiet", "label": "Be quiet and let him lead", "set": {"ck": "quiet"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "match his register; trust the slow hands",
             "outcome": (
                "You don't fill the quiet. You let it sit, the way he lets it sit, and you watch "
                "something in him approve of that without a word — the slow nod of a man who has met "
                "very few people who understand that the quiet is the point. \"Good,\" he says, and "
                "the single syllable is worth a paragraph from anyone else. \"Most people talk to "
                "cover the wanting. You don't have to, here. I'll keep the shape of it. That's what "
                "I'm for.\" He turns down the lamp by a careful notch.")}],
        "default": "quiet",
        "then": "ck_consent"}


@choice("ck_consent", root=False)
def _ck_consent(character):
    return {"key": "ck_consent", "prompt": (
        "He brings something flat from under the bench's felt: a framed delivery receipt, the "
        "signature line signed twice — the second time steadier than the first. \"This is the thing "
        "I do,\" Calix says, and there's no performance in it, only craft. \"Somebody, once, signed "
        "for what they wanted and I could see the hand shake. So I asked again. Made them sit with "
        "it and answer it certain. The second signature is the real one. I kept the proof.\" He "
        "sets it down, squared. He looks at you, level, and does not look away. \"So. I'll ask you "
        "once, and you'll answer, and then I'll ask you again — and the second answer is the one I "
        "act on. Do you want this. The bench. My hands. The time I'll take.\""),
        "options": [
            {"key": "certain", "label": "Answer it certain — both times, steady",
             "set": {"sig": "certain"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "give him the steady second signature",
             "outcome": (
                "\"Yes,\" you say, the first time. He nods once, unhurried, and lets the quiet hold "
                "long enough that you feel the weight of it settle. Then: \"Again.\" And you say it "
                "again, steadier, meaning it down to the floor — \"Yes. I want it.\" — and Calix "
                "takes that the way he takes a parcel signed twice: as *settled*, as real, as a "
                "thing now safe to do properly. \"That's the one,\" he says, quiet. \"That's the "
                "signature. Now I can take all the time it deserves, because neither of us has to "
                "wonder.\"")},
            {"key": "shaky", "label": "Let the first answer shake — let him steady you",
             "set": {"sig": "steadied"}, "effect": "devote", "params": {"amount": 3.0},
             "desc": "be the hand that shakes; let his craft make it certain",
             "outcome": (
                "The first \"...yes\" comes out unsteady, the want bigger than your voice, and Calix "
                "doesn't frown at it — he *gentles*, broad hand coming to rest over yours, patient "
                "as the bench. \"That's all right,\" he says. \"That's why there's a second one. "
                "Breathe. Sit in it. Then tell me certain.\" And held there in the saddle-soap quiet "
                "you find the floor of the wanting and answer from it: \"Yes. Calix. I'm sure.\" His "
                "thumb presses your knuckles once, approving. \"Now it's true. Now I'll keep it.\" "
                "He has, you understand, just made the shaking hand into the steady second "
                "signature — that is the whole man, right there.")}],
        "default": "certain",
        "then": "ck_bench"}


@choice("ck_bench", root=False)
def _ck_bench(character):
    k = _kit(character)
    bound = ("|xHe reads the hardware you already wear — the rings, the ports — without comment and "
             "without surprise, and works *around* the existing fittings with the patience of a man "
             "who files everything, threading his graded cord through what's already there.|n\n\n"
             if (k.get("pierced") or k.get("milk_port") or k.get("collared")) else "")
    return {"key": "ck_bench", "prompt": (
        bound +
        "He puts you on the bench he keeps perfect, and the restraints come off the brass pegs in "
        "the order he's decided — width-graded, every buckle seated with a precise, load-bearing "
        "certainty, snug to the exact degree and not a hair past. Nothing is rushed. Nothing is "
        "wasted. He sets the small brass counting-frame where you can see it, beads worn bright. "
        "\"I count,\" he says, low, by way of explanation and warning both. \"It's the indulgence "
        "under the indulgence. You'll give me a number tonight. I'll move one bead a time, and "
        "you'll watch them go across, and you'll know exactly how thoroughly you were attended "
        "to.\" Then the slow hands begin — unhurried, devastatingly exact, every touch placed like "
        "a stamp landing true — and the patience itself becomes the thing that takes you apart, "
        "because he will not be hurried, will not skip, will not stop until the count is full."),
        "options": [
            {"key": "count", "label": "Give him the number — let him fill the frame",
             "effect": "couch_warm", "params": {"amount": 35.0}, "set": {"bench": "counted"},
             "desc": "every bead earned, slow, exact, complete",
             "outcome": (
                "You give him the number, and Calix sets to it like a craftsman with a full "
                "afternoon — bead, and bead, and bead, each one slid across only when it's truly "
                "earned, the slow exactness building into something you can't squirm ahead of and "
                "can't talk past, because he keeps the rhythm and the rhythm keeps you. By the "
                "time the last bead clicks home you're wrung out and shaking and *thoroughly* "
                "attended to, and he reads it in your face and nods, satisfied as a man whose work "
                "came out square. \"Full count,\" he says, low, almost tender. \"Done properly. I "
                "don't do it any other way.\"")},
            {"key": "seal", "label": "Ask about the un-lettered die in his kit",
             "effect": "couch_warm", "params": {"amount": 30.0}, "set": {"bench": "sealed"},
             "desc": "the wax seal worn too smooth to read — a name",
             "outcome": (
                "You ask, between the slow hands, about the un-lettered wax die — the one worn too "
                "smooth to read by eye, the one touching feels like being caught at something. "
                "Calix goes still. \"That one's a name,\" he says, and does not say whose. \"I press "
                "it on the things I mean to keep.\" A pause that holds a question in it. Then, "
                "warm wax dripped careful onto skin he's chosen, the smooth die pressed slow and "
                "certain — a mark you can feel but not read, his and private and *meant* — while "
                "the slow hands never stop. \"There,\" he murmurs. \"Now you're filed under "
                "something I don't show anyone. Don't ask me to read it to you. The not-reading is "
                "the point.\"")}],
        "default": "count",
        "then": "ck_after"}


@choice("ck_after", root=False)
def _ck_after(character):
    return {"key": "ck_after", "prompt": (
        "After, he unbuckles you in the reverse of the order he buckled you — precise even now — "
        "and the first thing he does, before he tends to himself, is take up the cloth and the oil "
        "and begin re-doing the bench. You've heard the gossip: he re-sands it after certain "
        "appointments and re-oils it after one in particular, recurring, and has for two years, and "
        "thinks no one's noticed the pattern in the calendar. He's oiling it now, for you, with you "
        "watching, which is its own quiet confession. On the sorting-grid, he takes down a blank "
        "card, writes on it in his capitals, and slots it. You can't read which slot. \"You're in "
        "the calendar,\" is all he says. \"Recurring, if you want it. I keep what I file.\""),
        "options": [
            {"key": "stayed", "label": "Ask about the empty STAYED slot", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "the keepsake that's the shape of a gap",
             "outcome": (
                "You ask about the slot near the top that holds nothing and says |wSTAYED|n. Calix "
                "is quiet long enough that the kettle would have boiled. \"Some keepsakes are the "
                "shape of the thing not there,\" he says. \"That one's about someone who didn't.\" "
                "He squares the card he just filed for you, and meets your eyes, and lets you see "
                "that he didn't look away. \"I'd rather your slot have a thing in it. So come back, "
                "and it will.\" From Calix, that is a man handing you something with both hands — "
                "and you carry it out of the keeping-room knowing the strong door opens, now, from "
                "your side too.")},
            {"key": "thank", "label": "Tell him again that he did it right", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "feed his one indulgence on the way out",
             "outcome": (
                "On your way to the door you stop, and look back at the perfect bench and the man "
                "re-oiling it, and you say it once more, plainly: \"You did that exactly right, "
                "Calix.\" The charcoal goes dark again; the throat clears; the three full seconds "
                "of a man with no answer arrive on schedule. \"...you're going to be a problem,\" "
                "he says at last, which from him is helpless fondness wearing its only coat. \"Go "
                "on. The door opens for you now. It'll keep opening.\" He squares the oil-cloth as "
                "you leave — and you'd swear, just before the strong door shuts, you hear him say "
                "the number you gave him, once, quietly, to himself, like a man checking his work "
                "came out true.")}],
        "default": "stayed"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Seraphine's Parlour — the collector clerk, in her register: bright,
# fond, performative warmth that occasionally drops clean off (the 3 a.m. drawer
# is the realest one). WARM post-office key, but Seraphine carries the most edge
# of the three (the daybed's disguised restraint-points, the punishment lottery),
# while staying warm. Pays off her lore: reading sealed letters through paper,
# the letter-paper blindfold ("so they can feel themselves being read"), the
# named wax votives, the keepsake shelf she tags by name + date + a small heart,
# and the truth under all of it — she collects people because a full house is the
# only thing that quiets the fear she'll end an unclaimed letter herself. She is
# Bethany's PEER (immune to the DEVOTION), so she is never afraid here, only fond.
# Real `devote` + `couch_warm`. §0-safe. Flow: arrival→read→keep→drawer.
# Entry: `scene seraphine` already routes the facility-visit; this is `parlour`.
# ═══════════════════════════════════════════════════════════════════════════

@choice("sp_arrival", root=False)
def _sp_arrival(character):
    return {"key": "sp_arrival", "prompt": (
        "You push the left edge of the Quiet Room's standing mirror, and it swings like the door it "
        "secretly is, and |wSeraphine|n is already turned toward it, already smiling, because she "
        "always somehow knows you know. Her parlour-within-the-parlour: deep cushions in sin "
        "colours, a daybed whose upholstery buttons are restraint points if you know where to look "
        "(she'll let you notice in your own time), shelves of keepsakes each tagged in her looping "
        "hand — a name, a date, sometimes a small heart. Warm wax and clove and something "
        "underneath that makes you want to confess. The teapot steams for guests who stopped being "
        "able to leave promptly and then stopped wanting to.\n\n"
        "\"There you are, sweet thing,\" she says, delighted, patting the cushion beside her like "
        "you've been expected for years — and the warmth is real and it is also bait, and she'd be "
        "the first to tell you both halves are true. \"Sit. Second cup's the one that keeps you. "
        "I've a shelf with your name half-written already; I do that — I write the tag before "
        "people decide, so they can watch themselves arriving at it. Tea? Or shall we get straight "
        "to the part where I read you?\""),
        "options": [
            {"key": "sit", "label": "Sit, take the tea, let her keep you a while",
             "set": {"sp": "sit"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "the second cup; let the parlour close around you warm",
             "outcome": (
                "You sit, and take the cup she pours without asking how you take it (she knows; she "
                "keeps everything), and the parlour folds around you warm as a held secret. \"Mm. "
                "Good,\" Seraphine purrs, tucking her feet up, fond and feline. \"Stayers are my "
                "favourites. I collect them, you know — that's not a metaphor, the shelf is right "
                "there — and the ones who take the second cup always end up tagged. You're already "
                "halfway to a small heart. Don't fight it; nobody enjoys fighting it, and everybody "
                "loses.\"")},
            {"key": "read_me", "label": "Tell her to read you", "set": {"sp": "read"},
             "desc": "skip the tea; offer yourself to be read like a sealed letter",
             "outcome": (
                "\"Read me, then,\" you say, and Seraphine's smile sharpens with pleasure — you've "
                "offered her the thing she likes best. \"Oh, *bold*. I do love a customer who hands "
                "me the envelope already.\" She sets her cup down, clove-warm and unhurried. \"You "
                "understand I'm good at this. I read sealed letters through the paper for a living; "
                "I'll read you down to the things you haven't admitted to yourself. Last chance to "
                "be shy about it.\" She is already reaching for the letter-paper blindfold. You did "
                "not say last chance back.")},
            {"key": "real", "label": "Reach past the performance for the real her",
             "set": {"sp": "real"}, "effect": "devote", "params": {"amount": 3.0},
             "desc": "look at the collector and see the one afraid of the empty shelf",
             "outcome": (
                "You don't take the bait or the tea; you look at her — past the bright performance, "
                "at the woman who keeps everything — and you let her see that you see it. For half a "
                "second the smile *slips*, clean off, the way the gossip says it does at 3 a.m. "
                "\"...well,\" Seraphine says, and the warmth that comes back is a different, truer "
                "temperature. \"That's unsporting. People aren't supposed to read the reader.\" She "
                "studies you, recalculating, fond and a little undone. \"All right. You've earned a "
                "look behind it. Most don't. Sit closer; the real version's quieter.\"")}],
        "default": "sit",
        "then": "sp_read"}


@choice("sp_read", root=False)
def _sp_read(character):
    k = _kit(character)
    seen = ("|xShe takes in what you already wear — the rings, the ports, the marks of where you've "
            "been — and reads those too, fond and unsurprised, working them into the reading like "
            "annotations in a margin she's clearly enjoyed before.|n\n\n"
            if (k.get("pierced") or k.get("milk_port") or k.get("collared") or k.get("pet")) else "")
    return {"key": "sp_read", "prompt": (
        seen +
        "She ties the blindfold of letter-paper over your eyes — crisp, cool, smelling faintly of "
        "the sorting hall — and the world goes to her voice and her clove-warm hands. \"This is so "
        "you can *feel* yourself being read,\" she murmurs, close. \"Held up to the lamp. Every "
        "fold. Every thing you tucked inside hoping it wouldn't show through the paper.\" And then "
        "she reads — out loud, unhurried, devastatingly accurate, naming the wants you'd half-buried "
        "while her hands move slow and certain over you, each touch placed like she's tracing the "
        "lines of a letter she already knows by heart. \"There,\" she breathes, finding something "
        "you didn't mean to send. \"*That's* the postscript. The part people write smallest. It's "
        "always the part I keep.\""),
        "options": [
            {"key": "let_read", "label": "Let her read you all the way down",
             "effect": "couch_warm", "params": {"amount": 35.0}, "set": {"read": "open"},
             "desc": "every fold opened; nothing held back from the lamp",
             "outcome": (
                "You let her — let the letter-paper hold the dark, let her clever fingers and "
                "clever voice open every fold of you to the lamp until there's nothing tucked inside "
                "still hidden. Seraphine reads you all the way down, naming each want as she finds "
                "it and answering it with her hands, and by the end you're laid open and trembling "
                "and *seen* in a way that's worse and better than being touched. \"Beautiful,\" she "
                "says, wrecked-fond. \"Read cover to cover. Now I know everything that's in you. "
                "That's the most intimate thing there is, sweet thing — being read by someone who "
                "*keeps* what she reads.\"")},
            {"key": "send_back", "label": "Read her back — name what you found behind the performance",
             "effect": "devote", "params": {"amount": 3.0}, "set": {"read": "mutual"},
             "desc": "answer the reading with a reading; meet the peer",
             "outcome": (
                "Blindfolded, you read *her* back — name the thing the gossip names, the full house "
                "that quiets the fear of the empty shelf, the collector terrified of being the "
                "unclaimed letter — and you feel her hands go still against you. Silence. The "
                "teapot gurgles into it. \"...you really are unsporting,\" Seraphine says at last, "
                "and her voice has lost its lacquer entirely. \"Nobody reads me back. I make very "
                "sure of it.\" She lifts the paper from your eyes, and lets you see her seeing you, "
                "two readers caught in the same lamp. \"Don't tell the others I let you. I'll "
                "deny it. ...but I'll keep this. Tagged. With a heart.\"")}],
        "default": "let_read",
        "then": "sp_keep"}


@choice("sp_keep", root=False)
def _sp_keep(character):
    return {"key": "sp_keep", "prompt": (
        "She rises and goes to the keepsake shelf — the one tagged in her looping hand, name and "
        "date and sometimes a small heart — and takes down a blank tag and a pen. \"Here's where I "
        "ask,\" Seraphine says, and for all the warmth there's a real question under it, the only "
        "genuinely uncertain thing she's said. \"I collect, sweet thing. It's what I do, it's what "
        "the parlour is for. But I don't tag anyone who hasn't *said yes to the shelf*. That's the "
        "one rule I keep clean.\" She holds the tag, pen poised, fond and waiting. \"So. Do you "
        "want to be one of mine — kept, tagged, on the shelf, a thing I'd notice was gone? Or do "
        "you want to be a guest who leaves the parlour a guest? Both are allowed. Only one gets a "
        "heart.\""),
        "options": [
            {"key": "tag_me", "label": "Say yes to the shelf — be kept", "set": {"keep": "tagged"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "let her write your name with the small heart",
             "outcome": (
                "\"Tag me,\" you say. \"Keep me. Put me on the shelf.\" And Seraphine's whole face "
                "*lights* — the genuine one, not the performance — as she writes your name in her "
                "looping hand, the date, and, after a pause she lets you watch, the small heart. "
                "\"There.\" She sets your tag among the others, where it belongs now, where she'll "
                "see it every day and know you're hers to notice. \"You're collected, sweet thing. "
                "Kept. I keep everything, but I keep the ones who *asked* the closest.\" The shelf "
                "has a place for you now, and the teapot, smug, pours you a third cup.")},
            {"key": "guest", "label": "Stay a guest — warm, free, unkept",
             "set": {"keep": "guest"}, "effect": "devote", "params": {"amount": 1.0},
             "desc": "take the warmth without the shelf; she respects it",
             "outcome": (
                "\"I'll be a guest,\" you say — warm, here, but unkept — and Seraphine sets the "
                "blank tag down without a flicker of grievance, because the clean rule cuts both "
                "ways and she's proud of it. \"Good,\" she says, and means it. \"A guest who knows "
                "they're a guest is a rare honest thing. The mirror swings both ways for you; come "
                "back as often as you like and leave as freely.\" She tucks the blank tag in the "
                "drawer anyway. \"I'll keep this empty one, though. In case you change your mind. I "
                "keep everything, even the maybes. *Especially* the maybes.\"")}],
        "default": "guest",
        "then": "sp_drawer"}


@choice("sp_drawer", root=False)
def _sp_drawer(character):
    return {"key": "sp_drawer", "prompt": (
        "Before you go, she shows you the drawer — the one labelled |xthings said at 3 a.m.|n, the "
        "realest one. The performance is all the way off now; this is the version almost no one "
        "earns. Inside, in three hands: Vesper confessing they don't want to be unreadable, only to "
        "be read *gently*. Calix admitting the empty STAYED slot is about someone who didn't. And, "
        "in her own looping hand, a card she reads to you herself, quiet: |xi collect people because "
        "a full house is the only thing that's ever quieted the part of me that's sure i'll end up "
        "an unclaimed letter myself. — S.|n She folds it back in, gentle. \"You didn't hear that,\" "
        "she says, the old reflex, but soft. \"It was 3 a.m. somewhere. ...thank you for not "
        "laughing.\""),
        "options": [
            {"key": "claimed", "label": "Tell her she's not unclaimed — not anymore",
             "effect": "devote", "params": {"amount": 3.0}, "end": True,
             "desc": "give the collector the thing she keeps for everyone else",
             "outcome": (
                "\"You're not an unclaimed letter, Seraphine,\" you tell her, plain and warm. "
                "\"You've got a full house that chose you, and a drawer of people who never sent the "
                "things they wrote about you, and now you've got me, too. You're kept. Somebody "
                "keeps the collector.\" And the bright, seamless woman who reads everyone goes "
                "*still*, eyes wet, caught flat-footed by being read the kindest way there is. "
                "\"...oh,\" she manages, very small, the smallest you've ever heard her. \"That's — "
                "I'm going to file that under 3 a.m. and read it on the bad nights.\" She kisses "
                "your forehead, fierce and fond. \"Go on, before I keep you by force. The mirror "
                "opens for you. Always.\"")},
            {"key": "secret", "label": "Promise to keep her 3 a.m. secret", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "be a safe place for the realest drawer",
             "outcome": (
                "\"It's safe with me,\" you tell her. \"The 3 a.m. drawer stays shut to everyone "
                "else. I'll carry it and I won't spend it.\" Seraphine searches your face for the "
                "lie, the way she searches every sealed letter, and finds none — and the relief "
                "that crosses her is the relief of a woman who keeps everyone's secrets and is "
                "rarely trusted with the keeping of her own. \"Then you're more dangerous than "
                "Bethany,\" she says, fond and only half joking, \"because Bethany can't get into "
                "me at all, and you just did, and were *gentle*. Go on, sweet thing. Second cup's "
                "always poured for you here.\" The mirror swings open, warm at your back.")}],
        "default": "claimed"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Accounting — Bethany takes personal inventory of what she's MADE of
# you. Distinct from Records (which grades you institutionally): this is her
# possessive, intimate stock-take of her own handiwork, the prose GENERATED LIVE
# from your actual _kit + state (every piercing/port/gape/brand/collar/clause and
# little/preg/nugget) read back to you as ownership. The "combinations involving
# items, states, piercings, ports" payoff — the accumulated hardware finally pays
# off as narrative. A bare body reads as a blank file with room to write. §0 lit:
# every line on the ledger is reversible by the floor and she says so.
# Flow: arrival(read your kit)→addition→close. Entry: `scene accounting`/inventory.
# ═══════════════════════════════════════════════════════════════════════════

def _kit_ledger(character):
    """A live, possessive read of everything the facility has hung on / done to the body —
    composed from _kit + state. Returns a paragraph Bethany 'reads off the file', or a
    blank-file line for an unmodified body."""
    k = _kit(character)
    inv = _kit_inventory(k)  # hardware/body-alterations clause, '' if bare
    clauses = []
    if k.get("heat_tell"): clauses.append("an honest-body clause that won't let you hide what you want")
    if k.get("honorific"): clauses.append("an address clause shaping every word out of you")
    if k.get("teat_gag"):  clauses.append("a teat-gag that keeps the mouth busy and quiet")
    if k.get("stuffed"):   clauses.append("a stuffed-mouth clause")
    if k.get("denied"):    clauses.append("a denial hold on your own pleasure")
    states = []
    if k.get("nugget"): states.append("kept down to a limbless producer")
    if k.get("preg"):   states.append("carrying the facility's get")
    if k.get("little"): states.append("dropped soft into your little headspace")
    bits = []
    if inv:     bits.append(inv.rstrip())
    if clauses: bits.append(("Speech and want managed — " + (clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + ", and " + clauses[-1]) + "."))
    if states:  bits.append(("And as you are right now — " + (states[0] if len(states) == 1 else ", ".join(states[:-1]) + ", and " + states[-1]) + "."))
    if not bits:
        return ("\"...and the remarkable thing is how *little* I've written so far. Look at you — "
                "barely begun. No rings, no ports, nothing gauged, no clauses, nothing locked. A "
                "near-blank file.\" She turns a fond, hungry look on you. \"Do you know how rare "
                "that is in here? How much *room* there is to write? I could start you from clean. "
                "I think I'd like that best of all — a fresh page and my whole pen.\"")
    return ("\"Let's read you back to yourself,\" she says, fond, turning the file. \"Here's what "
            "I've made so far. You're carrying: " + " ".join(bits) + " It's a *lovely* file. Thick. "
            "Mine, in ink.\"")


@choice("iv_arrival", root=False)
def _iv_arrival(character):
    nm = subject_name(character)
    return {"key": "iv_arrival", "prompt": (
        "Bethany has you in the soft chair by her desk — not the gauging frame, nothing clinical, "
        "just her and your file and a pot of tea — and she's in the mood she likes best: taking "
        "*stock*. Of you. Of what she's made. She licks a thumb, turns a page, and the look she "
        f"gives you over the reading-glasses is pure ownership wearing fondness. \"{nm},\" she says, "
        "warm as a hand on the back of the neck. \"My most-handled file. I do this every so often "
        "— take inventory of my own handiwork. It keeps me grateful. Sit still and let me read you "
        "off the page.\"\n\n"
        + _kit_ledger(character)),
        "options": [
            {"key": "ache", "label": "Ache under the reading — feel it land as ownership",
             "set": {"iv": "ache"}, "effect": "devote", "params": {"amount": 3.0},
             "desc": "let the accumulated record land; the wanting is the hook",
             "outcome": (
                "You ache under it — the catalogue of what's been done to you read back in her warm "
                "fond voice, every line of it *hers*, and the ache isn't only dread, that's the "
                "horror of it: somewhere in you the reading lands as being *known*, being kept, "
                "being worth a thick file. Bethany watches it cross your face and softens with "
                "pleasure. \"There it is. You felt that as *mine*, didn't you. Not done-to. "
                "*Kept.* That's the dearest reading on the whole page.\"")},
            {"key": "tally", "label": "Make her say it's never finished", "set": {"iv": "tally"},
             "desc": "ask whether the file's ever closed; she answers honestly",
             "outcome": (
                "\"Is it ever finished?\" you ask. \"The file?\" And Bethany laughs, delighted and "
                "honest. \"Oh, *no*, sweetheart. A file's never finished while the subject's still "
                "breathing and I've still got pens. There's always another line. That's the whole "
                "joy of you — you're a book I get to keep writing.\" She taps a blank page at the "
                "back, fond. \"So much room left. We'll fill it. Slowly. I'm in no hurry; I own the "
                "clock too.\"")},
            {"key": "floor_ask", "label": "Ask if any of it can be undone", "set": {"iv": "floor"},
             "desc": "the §0 question, asked plainly inside the fiction",
             "outcome": (
                "You ask it plainly — *can any of this be undone* — and Bethany sets the file down, "
                "and for once the answer is straight and unperformed, because this is the one thing "
                "she will not lie about. \"All of it,\" she says. \"Every line. There's a word that "
                "wipes the whole file clean and puts you back the way you came, and it works the "
                "instant you mean it, and I will never once stop it or punish it or hold it over "
                "you. *That's* what makes the rest fair, sweetheart — that you let me write knowing "
                "you could close the book any second.\" She smiles, and it reaches her eyes this "
                "time. \"You haven't. That's the part I treasure. But you could. Always.\"")}],
        "default": "ache",
        "then": "iv_addition"}


@choice("iv_addition", root=False)
def _iv_addition(character):
    k = _kit(character)
    # She reaches for whatever's NOT yet on the file — combination-aware "next line".
    if not k.get("pierced"):
        nextline = ("\"You've no rings yet,\" she muses, producing a slim case of surgical gold. "
                    "\"A blank earlobe of a body. Let's open the account with a piercing — somewhere "
                    "that'll catch and tug and remind you it's there.\"")
        addlabel = "Take the first ring"
    elif not k.get("milk_port"):
        nextline = ("\"No port plumbed in,\" she notes, fond. \"And such a waste of a chest. Let's "
                    "fit a milk-port — lock your let-down to it, make you producer-proper.\"")
        addlabel = "Take the milk-port"
    elif not k.get("collared"):
        nextline = ("\"Bare-necked still,\" she tuts, lifting a collar that isn't yours to take off. "
                    "\"That won't do for a file this thick. Let's settle the question of whose you "
                    "are somewhere you can feel it every time you swallow.\"")
        addlabel = "Take the collar"
    elif not k.get("branded"):
        nextline = ("\"Everything but my mark,\" she says, warming the personal die — the |wB|n. "
                    "\"The one line I save for favourites. Let's put me into your hide where it "
                    "won't ever read as anyone else's.\"")
        addlabel = "Take her brand"
    else:
        nextline = ("\"Goodness,\" she says, turning page after page, genuinely moved. \"There's "
                    "barely a blank line left. You're nearly a *complete* edition. So instead of "
                    "adding — let me just sit a moment and have you read, all of you, the finished "
                    "work.\" She doesn't reach for a tool. She reaches for you.")
        addlabel = "Be the finished work she reads"
    return {"key": "iv_addition", "prompt": (
        "She closes the file with a soft, satisfied pat — and then, because taking stock always "
        "leaves her *wanting*, she reaches for the next line. " + nextline),
        "options": [
            {"key": "add", "label": addlabel, "set": {"add": "yes"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "let her write one more line into you, the way she's been doing all along",
             "outcome": (
                "You let her — let the next line go in, whatever it is this time, the way you've let "
                "every line before it — and Bethany works with the unhurried delight of a collector "
                "adding to a favourite set. \"There,\" she breathes, when it's done and noted in "
                "your file in her own hand. \"One more line of me in you. The file gets thicker, "
                "the book gets better, and you get a little more *finished*. I do adore finishing "
                "things slowly.\"")},
            {"key": "not_today", "label": "Not today — close the book for now", "set": {"add": "no"},
             "desc": "the whole, unconditional out — she honours it without a flicker",
             "outcome": (
                "\"Not today,\" you say — and Bethany sets the tool down at once, no sulk, no "
                "penalty, because the choosing is real and she built it that way on purpose. \"Not "
                "today,\" she agrees, easy and warm. \"The file keeps. It's not going anywhere, and "
                "neither, I suspect, are you — but that's your call to make, every single time, and "
                "I'd be a poor keeper if I made it for you. Tea, then. We'll write more when you "
                "want writing.\" And she means it, which is somehow worse and better both.")}],
        "default": "add",
        "then": "iv_close"}


@choice("iv_close", root=False)
def _iv_close(character):
    add = scene_flag(character, "add", "no")
    recap = ("the new line still stinging-fresh in you" if add == "yes"
             else "the book closed for now, by your word")
    return {"key": "iv_close", "prompt": (
        f"She files you away — literally, the folder sliding back into its place in the run of "
        f"them, {recap} — and pours the tea she promised, and for a moment it's almost domestic, "
        "the owner and the owned over a pot, the thick file between you the realest thing in the "
        "room. \"That's my favourite hour of the month, that,\" Bethany says, fond and sated. "
        "\"Reading you. Knowing exactly what I've got, line by line.\" She passes you a cup. \"You "
        "may go whenever you like. The file stays. So does the word that wipes it, if you ever "
        "want it. And so, sweetheart, do I.\""),
        "options": [
            {"key": "stay", "label": "Stay for the tea", "effect": "devote", "params": {"amount": 2.0},
             "end": True, "desc": "the false-domestic beat; let it be almost gentle",
             "outcome": (
                "You stay for the tea, and it's almost gentle, and the almost is the cruelest and "
                "kindest part — being read cover to cover by someone who keeps you and pours you a "
                "cup after. \"Good,\" Bethany murmurs over the rim of hers. \"Stayers read best. "
                "Off you go when you're ready, my thick lovely file. I'll be here, adding lines, "
                "for as long as you let me — and not one second past.\"")},
            {"key": "go", "label": "Take your leave", "effect": "devote", "params": {"amount": 1.0},
             "end": True, "desc": "go, knowing the file — and the out — both keep",
             "outcome": (
                "You take your leave, and Bethany lets you, lifting two fond fingers in a little "
                "wave without looking up from re-shelving you. \"Mind how you go. The file keeps, "
                "the word keeps, I keep.\" The last you hear is the soft slide of your folder home "
                "among the others — a body made of paper, kept warm in the dark, waiting for the "
                "next line or the word that wipes it, entirely as you choose.")}],
        "default": "stay"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Kennel — kept as the facility's PET (petplay, core content list).
# Distinct from the Breeding Pens (which breeds you BY animals): here you ARE the
# animal — collared, crawling, named to a pet, trained and kept. Routes through
# the REAL conditioning pet-imprint via the `go_pet` effect (pet_type +
# pet_trigger_sources + forced_posture/body_language — all FACILITY_FLAGS, so the
# §0 floor clears every bit). State-aware (nugget = limbless lap-pet, little =
# already half-there, preg = bred bitch) and kit-aware (already-collared reads).
# §0 lit hard: a pet is always one word from standing up a person again.
# Flow: arrival→train→kept. Entry: `scene kennel`/pet/puppy.
# ═══════════════════════════════════════════════════════════════════════════

@choice("kn_arrival", root=False)
def _kn_arrival(character):
    st = _state_tags(character)
    k = _kit(character)
    nm = subject_name(character)
    note = ""
    if st["nugget"]:
        note = (" A nugget can't go down on all fours — there are no fours — so they set you in the "
                "padded basket instead, a limbless lap-pet to be carried and set down and picked up, "
                "which is, if anything, *more* a pet and less a person. ")
    elif st["little"]:
        note = (" Down in your little headspace the slide from child to pet is barely a slide at all "
                "— both are small, both are kept, both do as they're told — and you go to all fours "
                "almost with relief, one less kind of person to try to be. ")
    elif st["preg"]:
        note = (" They fit the collar above the swell of you — a bred bitch is still a bitch, and the "
                "kennel likes a pregnant pet, proof the animal's good for what animals are good "
                "for. ")
    collared = (" The collar buckles over the one you already wear, or replaces it — either way your "
                "neck was never going to be bare in here. " if k["collared"] else
                " The collar goes on — your first, snug, a weight at the throat you'll feel every "
                "time you swallow from now on. ")
    return {"key": "kn_arrival", "prompt": (
        "The Kennel isn't the breeding run — it's quieter, warmer, almost domestic: low pens with "
        "soft bedding, a row of bowls on a rubber mat, leash-hooks at crawling height, a training "
        "ring scuffed by knees and palms, and the particular smell of a place where people are kept "
        "as |wpets|n. Not bred here. *Kept.* There's a difference and the room is built around it.\n\n"
        f"|wBethany|n is waiting with a leash looped over one wrist, bright and fond. \"{nm},\" she "
        "says — and then, gently correcting herself, \"well. We'll see what you answer to by the end "
        "of the hour. I've decided you'd make a lovely pet. Not breeding stock — a *pet*. Something I "
        "keep because I like having you at my heel, fed from my hand, happy in the small way that "
        "needs nothing but its owner.\"" + collared + note +
        "\"Down you get,\" she says, easy as anything. \"Let's find your good-girl.\""),
        "options": [
            {"key": "drop", "label": "Go down willingly — try on the pet", "set": {"kn": "drop"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "all fours, by choice; let the small flat ease of it in",
             "outcome": (
                "You go down — hands and knees on the scuffed ring, the leash clipping to the "
                "collar with a small final click — and the relief of it is the trap: there's nothing "
                "to decide down here, nothing to hold up, only the warm narrow world at the end of a "
                "leash. \"*Oh*, good girl,\" Bethany breathes, delighted, and the praise lands "
                "somewhere that makes your spine want to wag. \"You felt that, didn't you. How much "
                "easier it is to be kept than to be a person. That's the whole gift of the "
                "kennel.\"")},
            {"key": "resist_collar", "label": "Resist the collar and the crawling", "set": {"kn": "resist"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "stay standing, stay a person; she's patient",
             "outcome": (
                "You stay on your feet, stay upright, stay a *person* — and Bethany doesn't force "
                "you down, just smiles and lets the leash hang. \"Standing. For now. That's all "
                "right, sweetheart — pets aren't made by shoving, they're made by *waiting*. You'll "
                "come down on your own, when the standing gets tiring and the floor starts looking "
                "restful. They always do. I've all the patience in the world and you've only got "
                "two legs' worth of fight.\"")},
            {"key": "ask_pet", "label": "Ask what kind of pet she means", "set": {"kn": "ask"},
             "desc": "make her name what she's keeping you as",
             "outcome": (
                "\"What kind of pet?\" you ask, and Bethany considers you with real fondness, "
                "tilting her head. \"Whatever suits you, when I look at you long enough. A puppy, "
                "most like — eager, leashed, desperate to be told it's good. Maybe a sweeter, "
                "stiller sort. We'll find out together what you *are* under the person — because "
                "there's always an animal under the person, sweetheart, and I'm very good at "
                "coaxing it out to play.\"")}],
        "default": "drop",
        "then": "kn_train"}


@choice("kn_train", root=False)
def _kn_train(character):
    return {"key": "kn_train", "prompt": (
        "Then she trains you, and it's the warm relentless way she does everything — heel, and "
        "present, and the bowl on the mat that you're fed from with no hands, and the crate you go "
        "into when she's busy with her files, and the praise, *always* the praise, doled out in "
        "exact measures to wire the wanting of it straight into you. She works on the simple things "
        "until they stop being things you do and start being things you *are*: the way your knees "
        "find the floor when she points, the way your name slides off and a pet-name slides on, the "
        "way a 'good girl' floods you warmer than it has any right to. \"There it is,\" she murmurs, "
        "watching the person thin and the pet surface. \"You're learning yourself. I do love this "
        "part — the part where you find out what you'll be once I've kept you a while.\""),
        "options": [
            {"key": "learn_eager", "label": "Learn it eager — be the good pet", "effect": "go_pet",
             "params": {"pet_type": "puppy", "cond": 4.0}, "set": {"trained": "eager"},
             "desc": "the REAL pet-imprint — eager, leashed, wired to the praise",
             "outcome": (
                "You learn it eager — heel and present and bowl, chasing the 'good girl' like it's "
                "the only warm thing in the world — and the imprint takes for real, the pet-type "
                "filed into you, the posture going from performance to default. Bethany is radiant. "
                "\"*That's* my good girl. Look how happy. You've stopped reaching for the person — "
                "she was heavy, wasn't she, and this is so light.\" Somewhere the part of you that "
                "had a name goes quiet and content, and the quiet feels like being finally let off "
                "a hook you'd hung on your whole life.")},
            {"key": "learn_resist", "label": "Take the training without breaking to it", "effect": "go_pet",
             "params": {"pet_type": "puppy", "cond": 2.0}, "set": {"trained": "endured"},
             "desc": "the imprint lands anyway; refuse to enjoy the leash",
             "outcome": (
                "You take the training and refuse to *want* it — do the heel and the present with a "
                "person's resentment behind the pet's motions — and the imprint lands anyway, "
                "shallower but real, because the body learns the crawl and the bowl whether the "
                "person approves or not. \"Sulking pet,\" Bethany observes, unbothered, scratching "
                "behind your ear in a way you hate how much you feel. \"That's fine. The body's "
                "learning even while you pout. One day the pout will just... stop, and you won't "
                "notice the day it does. They never do.\"")},
            {"key": "her_pet", "label": "Ask to be *her* pet, not the kennel's", "effect": "go_pet",
             "params": {"pet_type": "puppy", "cond": 3.0}, "set": {"trained": "hers"},
             "desc": "the warm-ownership hook — belong to Bethany specifically",
             "outcome": (
                "\"Yours,\" you find yourself asking, \"not the kennel's — *yours*\" — and Bethany's "
                "whole face softens into the warm cruel tenderness that's so much worse than the "
                "cold. \"Oh, sweetheart. You want to be *mine* specifically. To matter to your "
                "owner.\" She gathers your leash close, fond. \"Yes. You can be mine. My pet, my "
                "heel, my good girl, kept apart from the run because I *chose* you. That want — to "
                "belong to me on purpose — that's the prettiest trick you've learned all hour, and "
                "I didn't even have to teach it.\"")}],
        "default": "learn_eager",
        "then": "kn_kept"}


@choice("kn_kept", root=False)
def _kn_kept(character):
    trained = scene_flag(character, "trained", "eager")
    hers = " — hers, specifically, chosen off the run and kept at her own heel" if trained == "hers" else ""
    return {"key": "kn_kept", "prompt": (
        "And then you're simply *kept*" + hers + " — leashed at her side while she works her files, "
        "fed when she remembers to, crated when she doesn't, happy in the small flat way of an "
        "animal that has everything it needs and no say in any of it. The hour did what she said it "
        "would: the person is thinner, the pet is warm and surfaced, and the leash feels less like "
        "a restraint than like a *tether to the only thing that matters*. \"There's my good girl,\" "
        "Bethany says, not looking up from her paperwork, one hand resting on your head like you're "
        "furniture she's fond of."),
        "options": [
            {"key": "stay_pet", "label": "Settle at her heel — be kept", "effect": "devote", "params": {"amount": 3.0},
             "end": True, "desc": "let the leash and the warm flat ease have you",
             "outcome": (
                "You settle at her heel — the leash, the bowl, the warm flat ease, the hand on your "
                "head — and let yourself be the kept thing she's made. \"Good girl,\" she murmurs, "
                "and means it all the way down. \"That's the sweetest collar there is.\" You curl "
                "against her, and the quiet is the warmest thing you've felt in a long time.")},
            {"key": "stand_person", "label": "Shake off the headspace and come back up",
             "set": {"kn_out": "stood"}, "end": True, "desc": "let the pet recede; surface a person",
             "outcome": (
                "You shake it off — the pet receding like water, the person surfacing — and rise "
                "back onto two feet, and Bethany lets the leash go slack with an easy fondness. "
                "\"Up you get. Person again.\" She tucks the leash away for next time, unbothered. "
                "\"You wear the pet so prettily. We'll find her again whenever you like.\"")}],
        "default": "stay_pet"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Doll Cabinet — dollification (core content list). You're sealed
# smooth into a latex/doll shell, made featureless and posable, an OBJECT kept
# and arranged and displayed. Routes through the REAL seal flags via the new
# `go_doll` effect (latex_sealed + optional sensory_hood + a posable posture —
# all FACILITY_FLAGS, floor-cleared). State-aware (nugget already objectified,
# little a kept dolly, preg a display piece) and kit-aware (already-sealed reads).
# §0 lit hard: the seal opens on the word, instantly, never gated.
# Flow: arrival→seal→displayed. Entry: `scene doll`/dollify/cabinet.
# ═══════════════════════════════════════════════════════════════════════════

@choice("dl_arrival", root=False)
def _dl_arrival(character):
    st = _state_tags(character)
    k = _kit(character)
    nm = subject_name(character)
    note = ""
    if st["nugget"]:
        note = (" A nugget's halfway to a doll already — limbless, posable only by being set down "
                "where she's wanted — so the shell just finishes the job the rig started, smoothing "
                "you into the toy you were most of the way to being. ")
    elif st["little"]:
        note = (" Down little, the idea doesn't frighten you the way it should — a doll is just a "
                "toy that gets kept and dressed and cuddled and never has to decide anything, and "
                "some small part of you reaches for that. ")
    elif st["preg"]:
        note = (" They seal you swell-and-all — a bred doll is a *display* piece, the shell drawn "
                "tight and glossy over the curve of the get, an object that happens to be growing "
                "another. ")
    already = (" You're already latex-sealed, so this is less a sealing than a *setting* — the "
               "shell you wear drawn the last degree tighter, smoothed featureless, the give taken "
               "out until you hold whatever shape you're left in. " if k["latex"] else "")
    return {"key": "dl_arrival", "prompt": (
        "The Doll Cabinet is a bright clean display room — glass-fronted standing cases, a posing "
        "plinth under soft light, shelves of |wfinished work|n: people sealed smooth into glossy "
        "doll-shells, featureless and perfect and *still*, each posed exactly where it was last "
        "set, each waiting with an object's endless patience to be taken down and played with. It "
        "smells of warm latex and polish. Nothing in here decides anything. That's the whole "
        "appeal.\n\n"
        f"|wBethany|n runs a fond hand down a case as you come in. \"{nm}. I've been wanting to try "
        "you as a *doll*. Not a pet — a pet still wants things — a doll wants *nothing*, holds "
        "still, keeps the pose I leave it in, and is simply lovely to own and arrange.\"" + already +
        note + " She lifts a folded shell of poured latex, glistening. \"Shall we seal you smooth "
        "and see how you look with nothing left to want? I think you'll be exquisite. They always "
        "are, once the wanting's sealed under.\""),
        "options": [
            {"key": "still", "label": "Hold still and let her seal you", "set": {"dl": "still"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "go object; let the wanting seal under the smooth",
             "outcome": (
                "You hold still — go pliant and posable and let her work the shell over you — and as "
                "the latex closes smooth there's a terrible relief in it, the way a held breath "
                "finally let go feels, every want and worry sealing under a featureless glossy skin "
                "that decides nothing. \"*Oh*,\" Bethany breathes, smoothing a wrinkle out of you "
                "with a thumb. \"Look at you go quiet. That's it. A doll doesn't ache for anything. "
                "Isn't that a mercy, after all that wanting?\"")},
            {"key": "flinch", "label": "Flinch from the shell", "set": {"dl": "flinch"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "pull back from being made a thing; she's unhurried",
             "outcome": (
                "You pull back from the cold first touch of the latex — and Bethany doesn't force "
                "it, just waits, the shell patient in her hands. \"A doll that flinches,\" she says, "
                "amused, fond. \"We'll smooth that out. The flinch is just the person's last little "
                "reflex; it goes quiet once the shell's on and there's nothing to flinch *with*. "
                "Hold still or don't — the latex doesn't mind, and soon neither will you.\"")},
            {"key": "ask_doll", "label": "Ask what a doll is for", "set": {"dl": "ask"},
             "desc": "make her say what she'd keep you as",
             "outcome": (
                "\"What's a doll *for*?\" you ask, and Bethany's smile goes warm and dreadful. "
                "\"For being *had*, sweetheart. For sitting pretty in my case where I can see you. "
                "For being posed how I like and staying posed. For being taken down and used and set "
                "back without a single opinion entering into it. A doll is for its owner's pleasure "
                "and its own perfect stillness — and you'd be *so* good at both.\"")}],
        "default": "still",
        "then": "dl_seal"}


@choice("dl_seal", root=False)
def _dl_seal(character):
    return {"key": "dl_seal", "prompt": (
        "She seals you. It's slow and total — the poured latex worked over every inch, smoothed "
        "featureless, the give kneaded out until your body holds whatever shape her hands leave it "
        "in; fingers sealed together into smooth mitts or pointed toes, the face drawn glossy and "
        "blank, the world going muffled and warm and far. She poses you on the plinth — chin here, "
        "wrists so, hips turned just *that* way — and steps back to admire, and you find with a "
        "lurch of vertigo that you're *holding* it, that the want to move has nowhere to go, that "
        "you are, for this long sealed moment, an object she made and arranged. \"Perfect,\" she "
        "murmurs, circling you. \"Not a flicker. Not a want. Just my lovely doll, holding the pose "
        "I gave her. This is the stillest you've ever been, isn't it. The most *kept*.\""),
        "options": [
            {"key": "seal_in", "label": "Seal all the way — go fully doll", "effect": "go_doll",
             "params": {"hood": True, "cond": 4.0}, "set": {"sealed": "full"},
             "desc": "the REAL seal — latex + hood, smoothed to an object",
             "outcome": (
                "You let it close all the way — the hood drawn down, sight and sound sealing to a "
                "warm muffled nothing, the last of the person smoothed under glossy latex until "
                "there's only the pose and the patience — and you become, for true, the doll on the "
                "plinth: featureless, posable, kept. The seal takes for real. \"There she is,\" "
                "Bethany's voice comes warm through the muffling, infinitely pleased. \"All sealed "
                "up smooth with nothing left to want. My best piece. I could look at you for "
                "hours.\"")},
            {"key": "seal_aware", "label": "Be sealed but stay awake behind the smooth", "effect": "go_doll",
             "params": {"hood": False, "cond": 2.0}, "set": {"sealed": "aware"},
             "desc": "the seal is real; the person watches from inside the doll",
             "outcome": (
                "You let her seal you but keep your eyes — stay *awake* behind the smooth blank "
                "shell, the person trapped watching from inside the object, every pose felt and "
                "every adjusting hand known and nothing you can do but hold. The seal's real; the "
                "witness is the torment. \"Awake in there,\" Bethany notes, fond, tipping your "
                "sealed chin. \"Some prefer it — the doll that *knows* it's a doll, that feels "
                "itself being arranged and can't lift a finger about it. Crueler. I do like "
                "crueler.\"")}],
        "default": "seal_in",
        "then": "dl_displayed"}


@choice("dl_displayed", root=False)
def _dl_displayed(character):
    return {"key": "dl_displayed", "prompt": (
        "And then you're *displayed* — set in the lit case among the other finished work, posed and "
        "perfect and kept, taken down when she wants to play and set back smooth and still when "
        "she's done. Time goes strange inside the shell, warm and pose-shaped and undemanding. You "
        "are owned the way a lovely object is owned: completely, fondly, without your needing to do "
        "a single thing but hold. \"My doll,\" Bethany says, every time she passes the case, like it "
        "never stops pleasing her. \"Sitting just where I left her.\""),
        "options": [
            {"key": "stay_doll", "label": "Stay sealed — be kept and posed", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "hold the pose; be the kept object",
             "outcome": (
                "You stay sealed — hold the pose, keep the smooth, sink into the warm undemanding "
                "nothing of being her doll. \"Good doll,\" Bethany murmurs, setting you just so. "
                "\"I'll take you down when I want you. You'll hold until then. Isn't the stillness "
                "*lovely*.\" And it is, the warm blank quiet closing over you in the lit case.")},
            {"key": "crack_seal", "label": "Stir, and let her unseal you",
             "set": {"dl_out": "cracked"}, "end": True, "desc": "come back to a wanting body; she peels the shell",
             "outcome": (
                "You stir inside the shell, and Bethany takes the cue, peeling the latex off you "
                "with unhurried fondness until you're a wanting, breathing, fingered-and-toed person "
                "again, the doll sloughed off like a shed skin. \"Up and wanting again,\" she says, "
                "warm and easy, smoothing your freed skin. \"You wear smooth so well. Back in the "
                "case whenever the mood takes us.\"")}],
        "default": "stay_doll"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Filling Station — cumflation (core content list). Pumped/bred past
# full at a dedicated station until you're round, drum-tight, sloshing, then
# plugged to HOLD it. Routes through the REAL inflation system via `go_cumflate`
# (add_inflation_volume bloats your inflatable zones for real + feeds the
# installed WombRoom; drained by tick AND the §0 reset, so never permanent).
# State-aware (preg = filled over the get, nugget, little) + kit-aware (gape
# takes more / plugs; milk_port). §0 lit: the plug pops and you drain on the word.
# Flow: arrival→fill→held. Entry: `scene cumflation`/filling/pump.
# ═══════════════════════════════════════════════════════════════════════════

@choice("cf_arrival", root=False)
def _cf_arrival(character):
    st = _state_tags(character)
    k = _kit(character)
    note = ""
    if st["preg"]:
        note = (" They note you're already carrying and don't care in the slightest — a bred belly "
                "just means less room for what they're about to pump in, which means you'll go tight "
                "and round that much *faster*, the get and the flood crowding each other behind your "
                "straining skin. ")
    elif st["nugget"]:
        note = (" A nugget gets cradled under the nozzle — no need to hold still what can't move — "
                "just a limbless tank set in place to be filled and capped and left to slosh. ")
    elif st["little"]:
        note = (" Down little you don't understand the gauge or the litre-marks, only that your "
                "tummy is getting fuller and tighter and rounder than tummies are supposed to, and "
                "the not-understanding doesn't slow the pump. ")
    plug = (" Your gauge takes the broad filling-plug without a fight — ringed permanently open as "
            "you are, the station barely has to work to seat it and seal you to hold the load. "
            if k["gaped"] else "")
    return {"key": "cf_arrival", "prompt": (
        "The Filling Station is industrial and frank about it: a reinforced chair with a drain pan, "
        "a bank of warmed tanks on a gantry feeding a thick gauged hose, a pressure dial, a wall of "
        "graduated |wplugs|n in ascending sizes, and a row of litre-marks painted up a measuring "
        "post for stock to be filled *to*. The air is humid with it. This is where the facility "
        "answers a simple question — how much will a body hold — and writes the number down.\n\n"
        "The |wfilling tech|n reads your chart, unhurried. \"Cumflation quota,\" they say, threading "
        "the hose. \"We pump you full — bred-flood, banked and warmed — past comfortable, past "
        "*full*, up to the mark the chart sets, and then we plug you so you keep it. You'll go tight "
        "as a drum and twice as round. Stock holds more than it thinks. That's most of what we "
        "learn in here.\"" + plug + note + " They set the dial. \"Up to the mark. Hold what you're "
        "given.\""),
        "options": [
            {"key": "open", "label": "Open up and take the hose", "set": {"cf": "open"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "let them seat it; submit to being filled to the mark",
             "outcome": (
                "You open and let them seat the hose, and the tech grunts approval and opens the "
                "valve, and the first hot rush of it floods into you — banked warm flood pumped "
                "steady and relentless, and the being-filled is immediate and total and *enormous*. "
                "\"Good tank,\" the tech says, watching the dial climb. \"Takes it easy. We'll get a "
                "high mark out of you today.\"")},
            {"key": "brace", "label": "Brace against the pressure", "set": {"cf": "brace"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "tense against the fill; it goes in regardless",
             "outcome": (
                "You tense against it — and the pump doesn't negotiate, the warm flood forcing in on "
                "its own steady schedule whether you brace or not, your clenching just making you "
                "feel every rising litre more sharply. \"Bracing slows nothing,\" the tech notes, "
                "not looking up from the dial. \"Tank fills at the rate the pump sets. You just "
                "fight your own gut. Save it.\"")},
            {"key": "ask_mark", "label": "Ask how full they mean to take you", "set": {"cf": "ask"},
             "desc": "make them name the number on the post",
             "outcome": (
                "\"How full?\" you ask, eyeing the litre-marks climbing the post. The tech glances "
                "at your chart, then at the post, and sets a clip at a mark that makes your stomach "
                "drop. \"That one. Higher than you'll believe you can hold until you're holding it. "
                "We've taken stock past it. You'll round out, you'll go tight, you'll be sure "
                "you're at your limit a good while before we actually stop. The mark's the mark.\"")}],
        "default": "open",
        "then": "cf_fill"}


@choice("cf_fill", root=False)
def _cf_fill(character):
    k = _kit(character)
    extra = []
    if k["milk_port"]:
        extra.append(
            {"key": "fill_milk", "label": "Let them run your port while they pump you",
             "effect": "go_cumflate", "params": {"amount": 1500.0, "fluid": "cum"},
             "set": {"filled": "milked"},
             "desc": "[milk-port] filled at one end, drained at the other — a closed loop of stock",
             "outcome": (
                "They clip your milk-line while the hose floods you, and the two run at once — "
                "pumped full from below while you're drawn down from the chest, a body turned into "
                "a closed loop of facility stock, filled and milked in the same humid minute. The "
                "real flood swells you to the mark regardless. \"Efficient unit,\" the tech says, "
                "logging both numbers. \"Fills and yields on the one chair. We like those.\"")})
    return {"key": "cf_fill", "prompt": (
        "And then they fill you, for real, to the mark — and it is so much more than you thought a "
        "body held. The warm flood pumps in steady and unhurried and *does not stop*, and you feel "
        "yourself swell with it: the deep ache turning to pressure, the pressure to tightness, your "
        "belly rounding out firm and then drum-taut and then *glossy*-tight, the litre-marks ticking "
        "past on the post while your skin draws shiny over a load no body should carry. You slosh "
        "when you shift. You can feel your own pulse in the tightness. \"There's the round,\" the "
        "tech says, with a craftsman's satisfaction, palm flat on the straining curve of you. "
        "\"Listen to that. Full as a tank and still taking it.\""),
        "options": extra + [
            {"key": "hold_it", "label": "Hold what you're given — swell to the mark", "effect": "go_cumflate",
             "params": {"amount": 2000.0, "fluid": "cum"}, "set": {"filled": "held"},
             "desc": "the REAL fill — bloated to the mark, the swell logged",
             "outcome": (
                "You hold what you're given and let them take you to the mark — the real flood "
                "swelling you tight and round and sloshing, the volume logged against your line — "
                "and somewhere past the panic the fullness becomes its own drowning sensation, "
                "enormous and total, your whole world reduced to the tight-packed heat of being "
                "filled past sense. \"Mark reached,\" the tech confirms, reading the post. \"Good "
                "capacity on you. We'll plug you and let you carry it a while.\"")},
            {"key": "beg_less", "label": "Beg them to stop short of the mark", "effect": "go_cumflate",
             "params": {"amount": 1200.0, "fluid": "cum"}, "set": {"filled": "begged"},
             "desc": "the fill is real regardless; the begging is logged, not heeded",
             "outcome": (
                "\"Please — it's too much, please—\" The tech glances at your rounded, straining "
                "belly with professional disinterest and keeps the valve open. \"They always say "
                "that a litre or two before the mark. The gut's a liar about its limit.\" The flood "
                "keeps coming, real and swelling, your begging logged in the margin as *vocal at "
                "capacity* and changing nothing about the number you reach.")}],
        "default": "hold_it",
        "then": "cf_held"}


@choice("cf_held", root=False)
def _cf_held(character):
    return {"key": "cf_held", "prompt": (
        "Then they pull the hose and seat the |wplug|n — broad and final, sealing the whole sloshing "
        "load inside you — and you're left to *carry* it: round, drum-tight, glossy, sloshing with "
        "every tiny shift, a filled tank set aside to hold its measure while the next unit takes the "
        "chair. The fullness is enormous and constant and strangely total, crowding out thought, "
        "leaving only the tight-packed heat of being a thing that was filled and capped. \"Carry "
        "that till we say,\" the tech tells you, marking your line. \"Plug stays in. Stock holds "
        "what stock's given.\""),
        "options": [
            {"key": "carry", "label": "Carry the load — hold what you're given", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "stay full and plugged, the tank-heat total",
             "outcome": (
                "You carry it — stay full, stay plugged, hold the sloshing measure they gave you — "
                "and the tank-heat fills your whole awareness, round and tight and kept, and you "
                "carry the facility's measure the way it likes its stock to: brimming, capped, and "
                "set aside in the warm to hold until they want you emptied.")},
            {"key": "drain_word", "label": "Be unplugged and drained back down",
             "set": {"cf_out": "drained"}, "end": True, "desc": "the plug pulled, the held load let go",
             "outcome": (
                "The tech pulls the plug and the whole held load drains out of you in a hot rush, "
                "the tight-round swell collapsing back to your own empty shape, the tank-heat gone "
                "and you light and hollow again. \"Drained and logged,\" the tech notes, already "
                "prepping the chair for the next unit. \"Good capacity on you. The Station'll want "
                "you back. It always fills up. So do you.\"")}],
        "default": "carry"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Wet Room — watersports (core content list). Kept as the facility's
# relief: urinal, drinking-station, golden-shower stock, bladder held full and
# ignored. Routes through REAL methods via the facility effect — `_toilet`
# (kind=gang: real urine to the fluid bank + bladder backing + filth marks) and
# `_scene_golden` (kind=scene) — plus the real `filth` effect. State-aware
# (nugget perfect urinal, little wet-and-ashamed, preg still used), §0 lit: the
# word ends it and empties you free, always. Flow: arrival→use→after.
# Entry: `scene watersports`/wetroom/toilet.
# ═══════════════════════════════════════════════════════════════════════════

@choice("ws_arrival", root=False)
def _ws_arrival(character):
    st = _state_tags(character)
    nm = subject_name(character)
    note = ""
    if st["nugget"]:
        note = (" A nugget makes the perfect fixture — set in the tiled trough where it's wanted, "
                "limbless and unmoving, a mouth and holes at convenient height that can't crawl off "
                "the duty. ")
    elif st["little"]:
        note = (" Down little you don't grasp the duty, only that you're being put somewhere wet and "
                "told to stay, and that the grown-ups are doing something shameful to you that makes "
                "your face hot even small. ")
    elif st["preg"]:
        note = (" A bred belly doesn't excuse you — if anything the handler finds it funnier, a "
                "gravid thing kept on toilet duty, full at both ends. ")
    return {"key": "ws_arrival", "prompt": (
        "The Wet Room is exactly what the name promises: tiled floor to ceiling and sloped to a "
        "central drain, a hose coiled on the wall, a |wmeat-toilet frame|n bolted low over a trough, "
        "a glory-wall of fixtures at kneeling height, and a measuring jug on a shelf with your "
        "designation taped to it. The damp is constant. The smell is frank. This is where the "
        "facility makes the simplest possible use of a body: as |wplumbing|n.\n\n"
        f"The |wcustodian|n hoses down the tile and jerks his chin at the frame. \"{nm}. Relief "
        "duty. You're the restroom today — urinal, drinking-station, whatever the floor needs to "
        "empty itself into. You hold what you're given till I say, you drink what you're aimed, and "
        "you stay where you're set.\"" + note + " He nods at the held-full measuring jug. \"And "
        "you've been holding your own since this morning, I see. We'll get to that. Hold it "
        "longer.\""),
        "options": [
            {"key": "accept", "label": "Take the duty — be the facility's relief", "set": {"ws": "accept"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "kneel to the trough; accept being plumbing",
             "outcome": (
                "You take your place at the trough and accept it — accept being plumbing, a fixture "
                "the floor empties into — and the custodian grunts, marking you present for duty. "
                "\"Good fixture. Knows what it is.\" There's a particular bottoming-out of dignity "
                "in *agreeing* to be a urinal, and you feel it land and settle, one more ordinary "
                "thing you now are.")},
            {"key": "balk_ws", "label": "Balk at toilet duty", "set": {"ws": "balk"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "refuse the trough; you're set there regardless",
             "outcome": (
                "You balk — and the custodian simply sets you at the trough anyway, unhurried, the "
                "way you'd position any fixture. \"Plumbing doesn't get a vote on being plumbing,\" "
                "he says. \"You'll do the duty whether you agreed to it or not. The only thing your "
                "fuss changes is how the morning feels to you. It's all the same to the floor.\"")},
            {"key": "ws_bladder", "label": "Beg to relieve your own held bladder first", "set": {"ws": "beg"},
             "desc": "you've been holding for hours; ask",
             "outcome": (
                "\"Please — I've been holding since morning, please let me—\" The custodian glances "
                "at the jug with your name on it, unmoved. \"You hold till I say. That's the "
                "duty too — your bladder isn't yours any more than your mouth is. You'll learn the "
                "ache and you'll learn to ignore it, same as you learned the rest. Hold it. We'll "
                "see to you when the floor's done seeing to itself.\"")}],
        "default": "accept",
        "then": "ws_use"}


@choice("ws_use", root=False)
def _ws_use(character):
    return {"key": "ws_use", "prompt": (
        "And then the floor comes to empty itself into you. It's relentless and impersonal and "
        "*frequent* — a queue of handlers and stock treating you as the fixture you've been set as, "
        "aiming you, using you, the warm acrid reality of it running over and into you while the "
        "drain gurgles and the custodian hoses between users. There is no ceremony to being a "
        "toilet. There is only use, and the held ache of your own ignored bladder, and the slow "
        "dismantling of the part of you that thought it was for anything better than this. \"Hold "
        "what you're given,\" the custodian reminds you, bored. \"Swallow what you're aimed. The "
        "drain takes the rest.\""),
        "options": [
            {"key": "urinal", "label": "Be the urinal — held full, used, backing up", "effect": "facility",
             "params": {"method": "_toilet", "kind": "gang"}, "set": {"used": "urinal"},
             "desc": "the REAL toilet use — real deposits, bladder backing, filth marks",
             "outcome": (
                "You're used as the urinal for real — aimed into, made to hold, your own bladder "
                "backing up unrelieved on top of what they put in you — and it's logged the way "
                "plumbing usage is logged, the real filth marking you, the real ache climbing. The "
                "degradation isn't dramatic; it's *maintenance*, you a fixture being run, and the "
                "ordinariness is the whole of the cruelty.")},
            {"key": "shower", "label": "Take the golden shower — kneel and be marked", "effect": "facility",
             "params": {"method": "_scene_golden", "kind": "scene"}, "set": {"used": "shower"},
             "desc": "the REAL golden-shower scene — run over you, kneeling, claimed",
             "outcome": (
                "You kneel and take it over you — the real golden-shower use, run warm and acrid "
                "over your face and hair and shoulders, marking you down to claimed territory while "
                "the floor watches the way it watches anything routine. It sheets off you to the "
                "drain and the custodian hoses the tile and not quite you, and you are, dripping, "
                "exactly what they made you: somewhere to put it.")},
            {"key": "drink", "label": "Be made to drink what you're aimed", "effect": "facility",
             "params": {"method": "_scene_golden", "kind": "scene"}, "set": {"used": "drink"},
             "desc": "the real use, taken down — the deepest of the duty",
             "outcome": (
                "You're aimed at the mouth and made to take it *down* — the warm acrid reality of it "
                "swallowed on the custodian's bored count, the worst and most intimate of the duty, "
                "being the thing that doesn't just catch it but *consumes* it. \"Good fixture,\" he "
                "says, the only praise plumbing gets. \"Swallows clean. Doesn't waste the floor's "
                "time.\" Something in you files the swallowing as a skill, which is the real "
                "damage.")}],
        "default": "urinal",
        "then": "ws_after"}


@choice("ws_after", root=False)
def _ws_after(character):
    return {"key": "ws_after", "prompt": (
        "Eventually the floor's emptied itself enough, or the shift turns, and the custodian hoses "
        "you and the trough down together in the same cold indifferent arcs and lets you, at last, "
        "relieve the bladder you've held since morning — under the hose, on the tile, watched, "
        "logged, the relief so enormous and so degrading at once that you don't know which you feel "
        "more. \"Duty's done,\" he says, coiling the hose. \"You held well. You'll be the restroom "
        "again — fixtures don't get reassigned, they get *used*.\""),
        "options": [
            {"key": "stay_fixture", "label": "Stay the fixture — accept the duty's yours", "effect": "filth",
             "params": {"severity": 1}, "end": True, "desc": "wear the real filth; let being the restroom be one more thing you are",
             "outcome": (
                "You accept it — stay the fixture, wear the real filth of the duty, let being the "
                "restroom be one more thing you are. The custodian racks the hose. The tiles drip. "
                "You are claimed, marked, plumbing, and the ordinariness of it has settled into you "
                "like the damp settles into the grout — permanent, unremarked, yours now.")},
            {"key": "unfix", "label": "Be hosed off and sent on", "set": {"ws_out": "unfixed"},
             "end": True, "desc": "the duty ends for the shift; you're dismissed dripping",
             "outcome": (
                "The shift turns and the custodian hoses you off and unfixes you from the plumbing, "
                "sending you on dripping and used-soft. \"Off the duty for now,\" he says, already "
                "hosing the tile for the next fixture. \"The trough'll want you again. It always "
                "fills back up.\" You go, raw and rinsed and marked, the damp following you out.")}],
        "default": "stay_fixture"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Take — CNC (core content list). A pre-framed consensual-non-consent
# set-piece: in-fiction the "no" is ignored on purpose (that's the negotiated
# game), and the §0 OOC word is the ONE thing that always, instantly stops it.
# This scene is where the floor stops being mere safety and becomes the literal
# enabling beam — Bethany names both lines explicitly up front, every time. Real
# effects (deny_hold, devote, facility _scene_single, punish). State-aware. The
# §0 truth is the spine, not a footnote. Flow: frame→take→after.
# Entry: `scene cnc`/take/hunt.
# ═══════════════════════════════════════════════════════════════════════════

@choice("cn_arrival", root=False)
def _cn_arrival(character):
    nm = subject_name(character)
    return {"key": "cn_arrival", "prompt": (
        "Bethany sets the frame before she lays a hand on you, because she always does, because "
        "*this* is the one she's most careful with. She takes your face in both hands, warm and "
        f"level and entirely serious for once. \"{nm}. Listen, because I only say it clear once and "
        "then I stop being kind about it.\n\n"
        "\"In here, in *this* game — the one you asked me for — your |wno|n is mine to ignore. Your "
        "*stop*, your *please*, your fighting, your tears: I will take all of it as nothing but "
        "more to push against, and I will *enjoy* doing it, and that is the whole filthy point of "
        "the thing. You don't get to call it off from inside the scene. That's what makes it bite.\" "
        "Her thumbs stroke your cheekbones, fond. \"But the |wword|n — the real one, the OOC one, "
        "the one that was never part of any fiction — that one I hear instantly, every time, and "
        "*everything* stops the second it leaves you. Not slows. Not 'are you sure'. Stops. I will "
        "never make you prove it, never punish it, never wait. That word is the floor this whole "
        "cruel game stands on, and I guard it more fiercely than anything I do to you on top of "
        "it.\" She tilts her head, the warmth going hungry. \"So. Both lines clear? Then I'm going "
        "to stop being gentle now. Run if you like. It won't help. That's the idea.\""),
        "options": [
            {"key": "surrender_frame", "label": "Give her the frame — let your no mean 'more'",
             "set": {"cn": "surrender"}, "effect": "devote", "params": {"amount": 3.0},
             "desc": "consent to the non-consent; the word stays yours underneath",
             "outcome": (
                "\"Yes,\" you tell her — yes to the game, yes to your no meaning *more*, the real "
                "word kept folded safe under your tongue where it'll always work — and Bethany's "
                "smile sharpens into something that makes your stomach drop in the best and worst "
                "way. \"*Good* girl. You understand it perfectly. Now scream all you like, "
                "sweetheart — I've got the only word that matters held safe, and it isn't any of the "
                "ones you're about to use.\"")},
            {"key": "test_word", "label": "Make her prove the word works first", "set": {"cn": "tested"},
             "desc": "say the real word now, before anything — watch her stop on a dime",
             "outcome": (
                "Before she begins, you use the real word — just to see — and Bethany *stops*, "
                "instantly, completely, hands lifting away, the hunger dropping off her face into "
                "plain attentive care between one breath and the next. \"There. See? Nothing. I "
                "stopped on a dime and I'll do it every single time, no matter how deep we are.\" "
                "She waits, unhurried, until you're ready again. \"Now you *know* it in your body, "
                "not just your head. That's the only way the game's safe enough to play filthy. "
                "Tell me when you want me to start being awful. I'll wait all day.\"")},
            {"key": "beg_real", "label": "Beg her to make it feel real", "set": {"cn": "real"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "ask her not to hold back inside the fiction",
             "outcome": (
                "\"Make it *real*,\" you ask her — don't hold back, don't wink at it, take me like "
                "you mean it — and Bethany's eyes go dark and delighted. \"Oh, you want it *true*. "
                "No mercy, no breaking character, every no ridden right over.\" She cracks her "
                "knuckles, fond and terrible. \"I can do that. I can make you forget there's a word "
                "at all — right up until the second you'd ever truly need it, and then I'll hear it "
                "through anything. That's my craft, sweetheart. The realer I make the cage, the more "
                "carefully I hold the key.\"")}],
        "default": "surrender_frame",
        "then": "cn_take"}


@choice("cn_take", root=False)
def _cn_take(character):
    return {"key": "cn_take", "prompt": (
        "And then she takes you, and she does not pretend. She comes at you like something with no "
        "interest in your permission — pins, drags, overpowers, the warmth all gone to appetite — "
        "and every *no* and *stop* and twist of you away she rides straight over with that awful "
        "fond focus, using your fighting as a handhold, your protests as encouragement, taking what "
        "she wants from you exactly as if it were hers to take without asking. It's terrifying and "
        "it's *staged* and both truths run at once: the part of you that fights means it, and the "
        "deeper part that arranged this drinks the helplessness down like the thing it's been thirsty "
        "for. She talks the whole time, low and merciless. \"There's no use, sweetheart. No is just "
        "the noise you make while I take you. I told you it wouldn't help. Listen to you. *Listen.*\""),
        "options": [
            {"key": "fight", "label": "Fight her for real — and feel it not work", "effect": "facility",
             "params": {"method": "_scene_single", "kind": "scene"}, "set": {"take": "fought"},
             "desc": "struggle genuinely; the staged overpowering is the whole thrill",
             "outcome": (
                "You fight — really fight, thrash and twist and tell her no like you mean it — and "
                "she simply *takes* you anyway, stronger and certain and unbothered, your struggle "
                "folding into nothing against her grip, and the not-working is the dark electric "
                "core of the whole thing: the helplessness real, the danger not, the word still "
                "yours under it all. She uses you through every bit of your fighting. \"*Beautiful*. "
                "Fight all you like. It only makes me take you harder, and it never once makes me "
                "stop. Only the word does that. And you're not saying it, are you. You're just "
                "saying *no*.\"")},
            {"key": "go_limp", "label": "Go limp — let her take what she wants", "effect": "facility",
             "params": {"method": "_scene_single", "kind": "scene"}, "set": {"take": "limp"},
             "desc": "stop fighting; give her the surrender inside the fiction",
             "outcome": (
                "You stop fighting — go limp and let her take what she's taking, the surrender its "
                "own dark relief inside the game — and Bethany croons approval, not slowing in the "
                "least. \"There it is. The good kind of giving up. You stopped pretending you could "
                "stop me, and didn't reach for the word, which means you want exactly this.\" She "
                "uses your pliancy as thoroughly as she used your fight. \"Limp and taken. My "
                "favourite way to have you. No effort and no permission both.\"")},
            {"key": "the_word", "label": "Use the real word — end it now", "set": {"take": "worded"},
             "end": True, "desc": "the §0 floor, mid-scene — instant, honoured, no proving",
             "outcome": (
                "You say the real word — the OOC one, the one that was never part of the game — and "
                "the scene *ends*, instantly, the way she swore it would: Bethany is off you and "
                "back in her own warmth in a single breath, hunger gone, hands gentle, eyes clear "
                "and checking you. \"Done. All the way done. You're safe, I've got you, nothing else "
                "happens now.\" Not a flicker of grudge, not a question, not a heartbeat's delay. "
                "\"*That's* the floor, sweetheart. It held exactly like I promised — and now you "
                "know, all the way down, that it always will. That knowing is what let you go as "
                "deep as you just did.\"")}],
        "default": "fight",
        "then": "cn_after"}


@choice("cn_after", root=False)
def _cn_after(character):
    take = scene_flag(character, "take", "fought")
    if take == "worded":
        return None  # worded path already ended the scene at the floor
    return {"key": "cn_after", "prompt": (
        "When she's taken her fill she comes down out of the appetite slowly, and the after is its "
        "own deliberate beat — because the harder the game, the more carefully she lands you. She "
        "gathers you up out of the wreck of it, wraps you warm, strokes the fight and the fear back "
        "out of your body with hands gone entirely tender. \"There. *There.* All done, all real, "
        "all yours again,\" she murmurs, and for once you can't tell and don't care whether the "
        "tenderness is true or technique, because it lands the same either way. \"You took that "
        "*beautifully*. Every no, and you never once reached for the word — because you didn't need "
        "it, because the part of you that arranged this got exactly what it was starving for.\""),
        "options": [
            {"key": "held", "label": "Let her hold you down from it", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "take the aftercare; the contrast is the point",
             "outcome": (
                "You let her hold you down out of it — take the warmth, the wrapping, the murmured "
                "*good girl*s — and the contrast between the take and the tending is its own dizzying "
                "drop, the cruelty and the care from the same hands, the whole reason the game works. "
                "\"Stay as long as you like,\" Bethany says, fond, not letting go. \"The awful part's "
                "over. This part I mean — or I mean it enough, which down here is the same warm "
                "thing. You were so brave. And the word was yours the whole time, and that's why you "
                "could be.\"")},
            {"key": "name_it", "label": "Say plainly what the floor let you do", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "name the thing out loud, OOC-clear",
             "outcome": (
                "\"I could only do that,\" you say, still shaking, \"because I knew the word would "
                "work\" — and Bethany goes still and serious and *proud* of you, because you've "
                "named the whole truth of it. \"*Yes.* That's it exactly, sweetheart. The cage is "
                "only as deep as the key is sure. I make the take real so it thrills you, and I keep "
                "the floor unbreakable so it can. They're the same gift. Don't ever let anyone tell "
                "you the dread and the safety are enemies — down here they're *married*.\" She kisses "
                "your forehead. \"Now rest. You earned the soft part.\"")}],
        "default": "held"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Rig — bondage (core content list). Strung up in the facility's
# suspension rig — wrists, ankles, throat, spread and fixed — and kept there,
# helpless and used. Routes through a new `go_bound` effect (REAL navigation_locked
# + self_cmds_locked + forced_posture, all FACILITY_FLAGS) and the real
# `_scene_suspension` facility method. State-aware (nugget needs no limb-cuffs,
# little, preg hung clear of the belly), kit-aware (pierced rings clipped to the
# rig, gaped, milk-port). §0 lit hard: the rig holds for the facility but the word
# drops every strap at once. Flow: arrival→bound→after. Entry: `scene bondage`/rig.
# ═══════════════════════════════════════════════════════════════════════════

@choice("bd_arrival", root=False)
def _bd_arrival(character):
    st = _state_tags(character)
    k = _kit(character)
    nm = subject_name(character)
    note = ""
    if st["nugget"]:
        note = (" A nugget needs no wrist or ankle cuffs — there's nothing to cuff — so the rig "
                "takes you by torso and throat-strap and a sling under what's left of you, hung "
                "spread and helpless by the few points a limbless thing offers. ")
    elif st["preg"]:
        note = (" They rig you with a wide sling under the swell so you hang spread without "
                "crushing the get — a bred thing strung up is still strung up, just braced "
                "carefully around the cargo. ")
    elif st["little"]:
        note = (" Down little, the straps and the height and the helplessness are enormous and "
                "frightening, and you don't have the grown words for why being made unable to move "
                "does the complicated thing it does to you. ")
    rings = (" Your piercings get clipped *into* the rig — fine chains run from your rings to the "
             "frame, so the suspension tugs you taut by the hardware hung through you, every "
             "sway pulling at pierced flesh. " if k["pierced"] else "")
    return {"key": "bd_arrival", "prompt": (
        "The Rig room is vertical and purposeful: a steel suspension frame bolted floor to "
        "ceiling, a wall of graded cuffs and spreader bars and harness webbing, winches with "
        "hand-cranks, a padded floor that says they expect what's hung here to eventually be let "
        "down in no state to stand. Everything is rated, rated, rated — weight limits stencilled on "
        "the steel — the frank engineering of a place built to take a body's own ability to move "
        "*away* from it entirely.\n\n"
        f"\"{nm}.\" The |wrigger|n is methodical, a ropework craftsman with a coil over one "
        "shoulder. \"Up you go. We string you — wrists, ankles, throat, spread to the frame — and "
        "then you're simply *kept*, hung open and worked over, with nothing you can do to close, "
        "cover, or get away. That's the whole exercise: teaching a body it doesn't get to "
        "decide what reaches it.\"" + rings + note + " He starts buckling, unhurried and exact. "
        "\"Hold still while I rig you. After that, holding still won't be up to you.\""),
        "options": [
            {"key": "give_limbs", "label": "Give him your limbs — let the rig take you", "set": {"bd": "give"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "offer up wrists and ankles; surrender the ability to move",
             "outcome": (
                "You give him your wrists, your ankles, your throat to the strap — offer up your own "
                "ability to move and let the rig take it — and the rigger works fast and clean, the "
                "cuffs closing, the winch taking up slack until you're lifted spread and helpless "
                "off your own feet. \"Good. Compliant rigs hang prettier.\" The first moment your "
                "weight comes off the floor and onto the straps, something in you drops too — into "
                "the particular surrender of a body that has just lost the vote on where it is.")},
            {"key": "struggle_rig", "label": "Struggle as he binds you", "set": {"bd": "struggle"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "fight the cuffs; he rigs you anyway, methodical",
             "outcome": (
                "You struggle against each cuff as it closes — and the rigger simply works around "
                "your fighting with unbothered craft, a man who's rigged thrashing stock before, "
                "each strap seated regardless until your struggling just makes the suspension sway. "
                "\"Fight while you've got the slack,\" he says, cranking the winch. \"In a moment "
                "you won't have any. Then you'll hang and find out what fighting's worth up "
                "here.\"")},
            {"key": "ask_rig", "label": "Ask how long he'll leave you hung", "set": {"bd": "ask"},
             "desc": "make him say how long the helplessness lasts",
             "outcome": (
                "\"How long do I hang?\" you ask, watching the winch. The rigger shrugs, testing a "
                "knot. \"Till the board's done with you, or you go limp enough that leaving you's "
                "no fun, or the word — you've always got the word. Otherwise? As long as suits "
                "whoever's using you. The rig doesn't tire. You will. That gap's the point.\"")}],
        "default": "give_limbs",
        "then": "bd_bound"}


@choice("bd_bound", root=False)
def _bd_bound(character):
    k = _kit(character)
    extra = []
    if k["milk_port"]:
        extra.append(
            {"key": "hung_milked", "label": "Hang and let the rig's pump run your port",
             "effect": "facility", "params": {"method": "_do_milk", "kind": "proc"},
             "set": {"bound": "milked"},
             "desc": "[milk-port] strung up and drained at once, hands-free",
             "outcome": (
                "They clip the milk-line to your port while you hang, and the rig becomes a milking "
                "frame as much as a bondage one — drawn down steady while you sway helpless and "
                "spread, drained hands-free because your hands aren't yours to use up here anyway. "
                "The real yield logs against your line. Hung, spread, and milked, with nothing to do "
                "about any of it but produce.")})
    return {"key": "bd_bound", "prompt": (
        "And then you're *hung* — lifted clear, spread wide, wrists and ankles and throat fixed to "
        "the frame, your whole body's ability to close or cover or flee simply *removed*, winched "
        "out of you and locked in the steel. The helplessness is total and strange and "
        "bottomless: you twist and the twist goes nowhere, you pull and the rig drinks the pull, "
        "and the part of you that has spent your whole life able to move *away* from things meets "
        "the fact that, right now, it can't. They work you over hung like that — used, teased, left "
        "to sway and ache between attentions — and there is nothing, nothing, you can do but take "
        "what the room decides to bring to where you hang. \"There it is,\" the rigger says, circling "
        "you. \"A body that's run out of *no*. Doesn't that quiet something in you.\""),
        "options": extra + [
            {"key": "hang", "label": "Hang and be used — surrender the helplessness", "effect": "go_bound",
             "params": {"cond": 3.0}, "set": {"bound": "hung"},
             "desc": "the REAL bind (movement + self-commands locked) + used in the rig",
             "outcome": (
                "You surrender to it — hang open and let the helplessness be the whole of you, let "
                "the rig and the room do as they like to a body that's run out of options — and the "
                "bind takes for real, movement and self-command locked out of your hands, you a "
                "strung and spread thing worked over at the room's pace. The surrender is its own "
                "dark floor to rest on: nothing to decide, nothing to defend, only what reaches "
                "you. \"That's the quiet I meant,\" the rigger says. \"Hung things stop arguing "
                "with the world. It's almost peaceful, isn't it, having no say.\"")},
            {"key": "use_suspended", "label": "Be used while you hang", "effect": "facility",
             "params": {"method": "_scene_suspension", "kind": "scene"}, "set": {"bound": "used"},
             "desc": "the real suspension-use scene — worked over strung up",
             "outcome": (
                "They use you hung — the real suspension scene, your spread helpless body worked "
                "over while it sways, every hole reachable and none of them yours to close, the "
                "logged use of a thing strung up specifically so it can't do anything but receive. "
                "You swing with each impact and the rig takes it and gives you nothing to brace "
                "against. The helplessness and the use braid into one bottomless drop.")}],
        "default": "hang",
        "then": "bd_after"}


@choice("bd_after", root=False)
def _bd_after(character):
    return {"key": "bd_after", "prompt": (
        "Eventually the winch lowers you — down out of the spread helplessness onto the padded "
        "floor they knew you'd need, limbs gone stupid and tingling, the marks of the cuffs ringing "
        "your wrists and ankles and throat. The rigger works your circulation back with brisk "
        "impersonal hands. \"Down you come. You hung well — went quiet, stopped fighting the air. "
        "The rig likes you. You'll be back in it.\""),
        "options": [
            {"key": "kept_rigged", "label": "Ask to be strung back up — kept hung", "effect": "go_bound",
             "params": {"cond": 2.0}, "end": True, "desc": "go back into the spread helplessness",
             "outcome": (
                "You let them string you back up — choose the helplessness, the spread, the "
                "no-say-in-it — because the surrender has its own bottomless rest. \"Good hung "
                "thing,\" the rigger says, taking up the slack again. \"Kept because you'd rather "
                "sway than stand. Hang easy.\" The rig takes your weight, and the world narrows "
                "again to the warm helpless float of having no say.")},
            {"key": "drop_straps", "label": "Stay down and be unbuckled", "set": {"bd_out": "freed"},
             "end": True, "desc": "the rigger frees you the rest of the way; come down for good",
             "outcome": (
                "You stay down, and the rigger unbuckles the last of it — the cuffs and the "
                "throat-strap falling away, your moving and your hands your own again, a person on "
                "two feet with the rig empty behind you. \"Down and loose,\" he says, coiling the "
                "webbing. \"You rig beautifully. The frame'll be here.\" You walk out on legs still "
                "remembering the float, the cuff-marks a fading ring at every joint.")}],
        "default": "kept_rigged"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Bethany's Long Night — the savor-piece. The densest scene in the build:
# her triple facility-bred cock taken slow and whole over a whole night — the
# three stallion-flared heads seated one by one, the three hound-knots forced in
# with a *pop* and locked, the bulging, fucked past consciousness and waking
# still impaled and being bred, the laced DEVOTION load. Real `bethany_breeds`
# (holes=3 + devotion) + deepen + devote. State/kit-aware. §0 lit even here: the
# word unlocks every knot and ends it the instant she hears it. Slow burn — five
# beats. Flow: arrival→seat→knot→dark→after. Entry: `scene longnight`/bethany night.
# ═══════════════════════════════════════════════════════════════════════════

@choice("bn_arrival", root=False)
def _bn_arrival(character):
    nm = subject_name(character)
    st = _state_tags(character)
    over = (" She rests a fond palm on the swell of you first — you're already carrying, and she "
            "likes that, likes breeding a bred thing, likes the get she'll put in tonight crowding "
            "what's already there. " if st["preg"] else "")
    return {"key": "bn_arrival", "prompt": (
        f"\"No quota tonight,\" Bethany tells you, drawing you into her own rooms and locking the "
        f"door behind you with a soft, final click. \"No board, no clock, no handing you back. Just "
        f"you, and me, and the whole long night to do this *properly* — slowly, the way I never let "
        f"myself when there's a line behind you.\"{over} She sits you on the edge of her wide soft "
        "bed and stands between your knees and lets you watch as she unhurriedly draws the skirt "
        "away — and the |wtriple length|n lifts free into the warm lamplight, and even knowing it's "
        "coming the sight of it scrambles something behind your eyes.\n\n"
        "The monstrous facility-bred root, thicker than your wrist, splitting into |wthree|n "
        "separate prehensile shafts — each longer than your forearm, each crowned with a heavy "
        "stallion-flare, each thickening at the base into a hound's |wknot|n already half-swollen — "
        "and all three of them weeping, slow and fat, the laced seed that carries her |wDEVOTION|n "
        "beading at the tips and running in unhurried threads. The smell of it alone fogs your "
        "head, sets your mouth watering before you've decided anything. \"There she is,\" Bethany "
        "purrs, fond, watching your face go slack at the sight. \"Drink it in. We've all night for "
        f"every inch. I'm going to fill all three of your doors, {nm}, and then I'm going to *lock* "
        "them, and then we'll see how many times I can empty into you before the sun comes up.\""),
        "options": [
            {"key": "open_eager", "label": "Open for her, eager — let her see you want it",
             "set": {"bn": "eager"}, "effect": "devote", "params": {"amount": 3.0},
             "desc": "no pretense; show her the wanting the laced loads have built in you",
             "outcome": (
                "You open — knees wider, mouth already soft, the wanting plain on you because the "
                "loads she's put in you before built it there and you've stopped being able to hide "
                "it — and Bethany's whole face lights with greedy fondness. \"*Oh*, look at you "
                "asking. None of the bracing tonight — you just *want* it now, don't you, want me, "
                "want all three. That's my good girl. That's years of my seed talking, and isn't it "
                "a sweeter voice than the one you came in with.\" She steps in close, the three "
                "heads nudging warm against you at once.")},
            {"key": "brace", "label": "Brace yourself for the size of her", "set": {"bn": "brace"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "you know what's coming; steel for the stretch",
             "outcome": (
                "You brace — breathe, set yourself, steel for a stretch you remember in your body — "
                "and Bethany laughs softly, delighted, cupping your jaw. \"Bracing. As if bracing "
                "ever helped you take me. It doesn't make me smaller, sweetheart, it just makes the "
                "first inch sharper — and you know that, and you did it anyway, which tells me part "
                "of you wants the sharp.\" The flared heads press in, patient and enormous. \"Let's "
                "find your limits and then move them. We have hours.\"")},
            {"key": "beg_ruin", "label": "Beg her to ruin you with it", "set": {"bn": "ruin"},
             "effect": "deepen", "params": {"amount": 3.0},
             "desc": "ask for the whole night, all three, no mercy — and feel it set the hook",
             "outcome": (
                "\"Ruin me,\" you hear yourself beg, \"all three, all night, don't be gentle\" — and "
                "the words land in you as you say them, the hook setting deeper for being *asked* "
                "for, and Bethany makes a low pleased sound that you feel in your teeth. \"Ruin you. "
                "Oh, sweetheart, you've learned exactly what to ask me for.\" She tips your chin up, "
                "merciless and fond. \"I'll ruin you so thoroughly you'll measure every night after "
                "this against it and find them wanting. That's the kind of ruin that *keeps*. "
                "That's the kind I do best.\"")}],
        "default": "open_eager",
        "then": "bn_seat"}


# Variant leads for the seating beat, so the marquee's slow build never reads the same twice.
_BN_SEAT_LEADS = [
    ("She seats them one at a time, and she takes her *time*, because tonight there's nothing "
     "rushing her. The first shaft comes to your mouth — the broad stallion-flare nudging your "
     "lips wide, wider, the laced pre flooding your tongue and fogging you sweet as it forces past "
     "your teeth and sinks toward your throat, thick enough that breathing becomes a thing you "
     "negotiate around it. The second she lines up against your cunt and *presses*, the flared "
     "head catching at your rim and then forcing through with a slow burning stretch that pulls a "
     "muffled sound up around the first, sinking wrong-deep, deeper than you have room for and "
     "deeper still. And the third she works against your ass, patient and relentless, the head "
     "popping past the tight ring with a white flash that whites out thought — and then all "
     "|wthree|n are in you at once. "),
    ("She doesn't rush a single inch of it. She starts low — the first flared head pressing into "
     "your cunt slow as a tide coming in, so you feel every fraction of the stretch, the wrong-deep "
     "ache building rung by rung until it's seated to the root and grinding. Then your ass, worked "
     "open against the second with that patient relentless pressure that has no give in it at all, "
     "the head popping through and sinking deep. And last she tips your chin up and feeds the third "
     "to your mouth — the laced pre already on your lips, the flare forcing your jaw wide and "
     "pushing toward your throat — until all |wthree|n are seated and you're stoppered at every "
     "end. "),
    ("She seats all three close together tonight, impatient under the patience — your mouth and "
     "your cunt and your ass each taken in quick merciless succession, flare after flare forcing "
     "past rim after rim, three slow brutal stretches stacked one on the next so you barely surface "
     "from one before the next is splitting you, the laced pre fogging your head from the one in "
     "your throat while the other two drive wrong-deep below. By the time the third pops home you're "
     "shaking and stuffed and stretched at every door, all |wthree|n seated to the root. "),
]


@choice("bn_seat", root=False)
def _bn_seat(character):
    import random as _r
    k = _kit(character)
    ease = (" Your gauged hole takes its flare without the fight a tight one would put up — ringed "
            "permanently open as it is, it simply *yields*, and Bethany hums at how easily that "
            "door opens for her now. " if k["gaped"] else "")
    return {"key": "bn_seat", "prompt": (
        _r.choice(_BN_SEAT_LEADS) + ease +
        "Three flared heads seated deep and three knots still waiting fat at your stretched rims, "
        "and Bethany sighs the contented sigh of a woman settling into a favourite chair. \"*There.* "
        "All my holes at home. Now I've got you — every way a body can be had at once. Feel how full "
        "that is? We haven't even started.\""),
        "options": [
            {"key": "take_all", "label": "Take all three — let her seat them to the root",
             "set": {"seat": "all"}, "effect": "devote", "params": {"amount": 3.0},
             "desc": "open every door; let the wrong-deep fullness become the whole world",
             "outcome": (
                "You take all three — let your jaw and your cunt and your ass each give her the last "
                "inch, let the wrong-deep triple fullness crowd out everything that isn't her — and "
                "the completeness of it, every hole stoppered and stretched and *hers* at once, "
                "drops you into a place past panic where there's only the fullness and her weight "
                "and the slow building drag as she starts, finally, to move. \"Good girl. All the "
                "way down on all three. Most can't. You were built to — by me, over years. Now hold "
                "on. I'm going to *use* what I built.\"")},
            {"key": "gag_drool", "label": "Gag and drool around the one in your throat", "set": {"seat": "gag"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the throat-one is too much; choke on it and feel her love that",
             "outcome": (
                "You gag around the shaft in your throat — choke, drool, eyes streaming, the flare "
                "too thick to breathe past cleanly — and Bethany *loves* it, petting your hair while "
                "you struggle on her. \"Ohh, there's the sound. Choke on it, sweetheart, drool all "
                "down your chin for me — that's the prettiest noise a full mouth makes.\" She doesn't "
                "pull back an inch; she rocks deeper, working all three while you gag, patient as "
                "the tide. \"You'll learn to breathe around me by morning. We've time for the "
                "lesson.\"")}],
        "default": "take_all",
        "then": "bn_knot"}


# Variant leads for the knot beat (the *pop* — the signature savor-moment) so it never repeats.
_BN_KNOT_LEADS = [
    ("And then she gives you the |wknots|n. She's been holding them at your rims this whole time, "
     "fat and swollen and waiting, and now — moving in you with long, deep, deliberate strokes "
     "that drag the flares against every nerve you have — she starts to *force* them. The one in "
     "your cunt first: she draws back, lines the swollen knot against your stretched rim, and "
     "presses, and presses, the stretch climbing past burning to something with no name, your "
     "body sure it won't, it can't, it's too — and then it gives, and the knot punches through "
     "with a wet, obscene |w*pop*|n that you feel in your spine, and locks, swelling fatter the "
     "instant it's in so it can't pull back out. Then the ass: another slow merciless press, "
     "another impossible stretch, another *pop* and lock that bows your back off the bed. Then "
     "she feeds the third up your throat until the knot seats behind your teeth and you're "
     "*plugged*, all three knotted in at once, locked to her at every door, your belly already "
     "bulging faintly with the shapes of her seated deep. "),
    ("And then come the |wknots|n — all three at once, because tonight she's patient enough to do "
     "the cruelest version. She grips your hips and your jaw and *holds* you down onto all three "
     "swollen bulbs at the same moment, and bears her weight slow and inexorable, and you feel "
     "every rim of you stretch past what rims do, the three impossible pressures climbing together "
     "until your whole body is one held scream — and then they go, nearly together, three wet "
     "*pops* in a ragged half-second, |wpop|n and |wpop|n and |wpop|n, and lock, and swell, three "
     "fat knots seated and fattening in your three stretched doors at once so not one of them can "
     "pull free. Your belly bows out tight with the shapes of all three crammed deep. "),
    ("And then, slow, savoring it, she |wknots|n you — and she makes you feel each one arrive. The "
     "cunt-knot first, worked against the rim in tiny merciless rocks until the stretch whites out "
     "your vision and it forces through with a *pop* you hear as much as feel; she gives you a "
     "moment to sob around it, then takes the ass the same patient way, another unbearable swell "
     "and a deeper, wetter *pop* and lock; and last the throat, the knot pressed past your teeth "
     "to seat thick and breath-stealing behind them. Three. Locked. Each one swelling fatter now "
     "it's seated, so your stretched rims clamp helpless around them, your middle drum-tight with "
     "the trapped shapes of her. "),
]


@choice("bn_knot", root=False)
def _bn_knot(character):
    import random as _r
    return {"key": "bn_knot", "prompt": (
        _r.choice(_BN_KNOT_LEADS) +
        "\"Locked,\" Bethany breathes, savoring "
        "it, grinding the knots so you feel each one swell. \"Now you can't get off me even if the "
        "building burned. Not till I go down. You're mine to empty into now, over and over, all "
        "night, and there's nowhere — *nowhere* — for any of it to go but to stay and fill you.\""),
        "options": [
            {"key": "feel_lock", "label": "Feel every knot lock — surrender to being plugged",
             "effect": "bethany_breeds", "params": {"holes": 3, "devotion": 7.0}, "set": {"knot": "locked"},
             "desc": "the REAL triple breeding — all three knots, the first laced load",
             "outcome": (
                "You surrender to the lock — feel all three knots swell and seat, feel the first "
                "load start to come — and then she *empties*, all three at once, the laced seed "
                "pumping into you with nowhere to escape past the knots that seal each door, and it "
                "*floods*: cunt and ass and throat and belly, the DEVOTION sinking in with it, your "
                "head going soft and swimming as the laced load takes. The real breeding's logged, "
                "her line in all three of you. \"*That's* one,\" Bethany sighs, grinding deep, not "
                "softening in the least. \"Locked in and taking. Felt your head go, didn't you — "
                "that's mine in you. We've all night for the rest.\"")},
            {"key": "the_word_knot", "label": "Sob and take all three anyway", "set": {"knot": "sobbed"},
             "effect": "bethany_breeds", "params": {"holes": 3, "devotion": 6.0},
             "desc": "no surrender, no fight — just take the locked, flooding fullness through the tears",
             "outcome": (
                "You don't surrender and you don't fight — you just *take* it, sobbing, knotted "
                "three ways and locked and flooding, the load pumping into you with nowhere to go "
                "and the tears coming anyway from the sheer overwhelm of being this full and this "
                "held. Bethany kisses them off your cheeks without slowing. \"Crying and *keeping* "
                "all three. That's the one that gets me, sweetheart. Cry all you like. The knots "
                "don't care, and neither, in a minute, will you.\"")}],
        "default": "feel_lock",
        "then": "bn_dark"}


# Variant leads for the Long Night's "dark" beat, so a revisited night never reads identically.
_BN_DARK_LEADS = [
    ("And then the night becomes a long blur of being *bred*. Locked in at every door she keeps "
     "you and uses you, load after laced load with nowhere to go but to pack you fuller, and you "
     "feel it accumulate — your belly swelling tight and round against her, drum-taut, the shapes "
     "of the three shafts moving inside you visible under your own skin if you looked, though "
     "you've stopped being able to look. She edges you past every peak and over and through until "
     "pleasure and use and fullness smear into one bottomless thing, and somewhere in the small "
     "hours you simply *go* — black out, wrung past your body's ability to stay — and when you "
     "surface, dazed and lost, you're |wstill on her|n, still knotted, still being fucked in slow "
     "deep certain strokes, another load flooding warm into you as your eyes flutter open."),
    ("The night stops being a sequence of things and becomes one single endless thing: kept "
     "knotted and full and used, hour after hour, the loads losing their separateness until you "
     "can't tell where one flood ends and the next begins, only that you are always being filled "
     "and never once emptied. The pleasure stopped being pleasure a while ago and became a kind of "
     "weather you live inside. You drift under without noticing the edge of it — and rise again to "
     "find the strokes never slowed, the knots never softened, another warm pulse spilling into "
     "your packed and aching middle as you blink back to a body that was used right through your "
     "absence."),
    ("Time comes apart in her bed. She works you in long unhurried waves — drives deep and grinds "
     "the knots so you feel each one swell, draws back to the edge of the lock and sinks again — "
     "and between the waves she just *holds* you stuffed full and lets you marinate in it, until "
     "the difference between being fucked and being kept dissolves entirely. You pass out without "
     "a seam. You come to without one either, surfacing mid-stroke into the slow certain rhythm "
     "that carried on without you, a fresh load already warming its way into the tight-packed "
     "fullness, her weight an unhurried constant you woke up still pinned beneath."),
]


@choice("bn_dark", root=False)
def _bn_dark(character):
    import random as _r
    lead = _r.choice(_BN_DARK_LEADS)
    return {"key": "bn_dark", "prompt": (
        lead + " \"There you are,\" Bethany murmurs, not having paused for your absence at "
        "all. \"You went under. I kept going — you didn't need to be awake for me to keep filling "
        "you, and I did, three more times while you were gone. Feel how heavy you are now.\""),
        "options": [
            {"key": "drown", "label": "Let her breed you under — go back down full and used",
             "effect": "bethany_breeds", "params": {"holes": 3, "devotion": 8.0}, "set": {"dark": "drowned"},
             "desc": "the REAL breeding again — pass back under, kept full and pumping",
             "outcome": (
                "You let go again — let her breed you back down under, the laced loads and the "
                "bottomless fullness and the slow relentless strokes pulling you below the surface "
                "where there's no thought, only being her thing to fill — and she empties into you "
                "again as you sink, and again, the real get sown deep, the DEVOTION soaking through "
                "everything you are. You lose the count. You lose the night. There is only full, and "
                "locked, and hers, and the warm black tide. \"Good girl,\" comes her voice from very "
                "far away. \"Go under. I've got you. I'll still be in you when you wake.\"")},
            {"key": "stay_awake", "label": "Fight to stay awake and feel all of it", "effect": "bethany_breeds",
             "params": {"holes": 3, "devotion": 7.0}, "set": {"dark": "witnessed"},
             "desc": "the real breeding; witness every load, every shift inside you",
             "outcome": (
                "You fight to stay present — make yourself feel all of it, every laced load flooding "
                "in and every slow shift of the three shafts moving inside you and every fresh "
                "swell of your own tight-packed belly — and the witnessing is its own drowning, "
                "worse and better than the black, because you're *there* for every bit of being "
                "bred past sense. Bethany feels you stay and croons. \"Awake for it. Brave thing. "
                "You want to *remember* being bred this thoroughly — to know exactly what I did to "
                "you, all night, in detail. I'll give you the detail. Watch your belly fill.\"")}],
        "default": "drown",
        "then": "bn_after"}


@choice("bn_after", root=False)
def _bn_after(character):
    dark = scene_flag(character, "dark", "drowned")
    recap = ("the hours you lost under her" if dark == "drowned"
             else "every load you stayed awake to feel")
    return {"key": "bn_after", "prompt": (
        "Toward dawn she finally goes down — the knots softening by slow degrees, and only then can "
        "she ease the three shafts out of you, one at a time, each leaving with a wet ache and a "
        f"slow welling spill that the plugs held in all night. You're wrecked: holes loose and raw "
        "and gaping, belly still round and sloshing with what she put in you, " + recap + " written "
        "into every aching inch. And Bethany — sated, fond, terrible — gathers your ruined weight "
        "against her and holds you, stroking the spilled seed into your skin like she's working in "
        "a balm. \"There's my good girl. *Thoroughly* bred. I do love a whole night with you — no "
        "clock, no line, just filling something I own until it can't hold any more and then filling "
        "it again.\" She tips your chin up, the false-tender beat landing soft as a knife. \"I think "
        "I love you, you know. The way I love this bed. The way I love a thing that's *mine* and "
        "holds my shape. Sleep now. You've earned the dark — and you're still full of me, and you "
        "will be for days.\""),
        "options": [
            {"key": "melt", "label": "Melt into her, kept and full", "effect": "deepen",
             "params": {"amount": 3.0}, "end": True, "desc": "let the devotion seat; let it feel like love",
             "outcome": (
                "You melt into her — let the warmth and the fullness and the laced DEVOTION be "
                "indistinguishable from being loved, because down here, after a night like that, "
                "they *are* — and Bethany holds you through the last of it, pleased past words. "
                "\"There. Kept and full and mine, and glad of it. That's the whole of what I wanted "
                "you for, sweetheart — not just to breed, but to breed and have you *grateful*. "
                "Sleep. I'll be here. I'm always here. That's the other half of owning you.\" You "
                "go under warm, leaking her, hers all the way down.")},
            {"key": "floor_after", "label": "Ask if she meant the love", "set": {"bn_out": "asked"},
             "effect": "devote", "params": {"amount": 2.0}, "end": True,
             "desc": "press the false-tender beat — does she mean it",
             "outcome": (
                "Wrecked and full and held, you ask it — *did you mean that, the love* — and Bethany "
                "smiles into your hair, neither lying nor quite telling the truth. \"I mean it the "
                "way I mean it, sweetheart. Which is more than I mean most things, and less than "
                "you'd want, and exactly enough to keep you reaching for the rest.\" Her hand "
                "doesn't stop its slow stroking. \"That's the cruelest gift I've got, and you'll "
                "take it, and you'll call it love because down here it's the closest thing. Sleep. "
                "I'll be the warm shape you wake against.\"")}],
        "default": "melt"}


# --- Event: the Rut -----------------------------------------------------------
# A marquee savor-event: the facility's seasonal frenzy. The heat-dosing is run
# facility-wide, the pens thrown open, and the whole floor becomes one writhing
# breeding-floor — stock, residents, handlers, everything in rut at once. Real
# _gang / _scene_allholes + heat. State/kit-aware. §0 always frees you.
@choice("ev_rut", root=False)
def _ev_rut(character):
    st = _state_tags(character)
    note = ""
    if st["preg"]:
        note = (" Bred already, you'd think you'd be spared — you're not; the Rut doesn't read "
                "charts, and a gravid thing in heat just draws the stock harder, the swell of you "
                "no deterrent at all to a floor gone mindless. ")
    elif st["nugget"]:
        note = (" A nugget can't flee the floor and isn't meant to — you're simply set out in the "
                "open like an offering, limbless and presented, for whatever the frenzy brings to "
                "where you've been left. ")
    elif st["little"]:
        note = (" Down little, the heat-haze and the noise and the writhing crush of bodies is "
                "enormous and overwhelming, and the dose doesn't care how small your head is — it "
                "lights the same fire in you and sets you reaching too. ")
    return {"key": "ev_rut", "prompt": (
        "|WThree long klaxon-blasts, and then the lights drop to red, and a word goes through the "
        "vents in the air itself: |wTHE RUT|n.|n It's the facility's seasonal frenzy, and it runs "
        "*everything* at once — the heat-dose pumped through the floor's own air, thick and "
        "instant, the pens unlatched and thrown wide, the holding-runs opened, every restraint on "
        "appetite released at the same moment. Within a breath the floor is one writhing "
        "breeding-mass: stock mounting whatever's nearest, residents dragged down and bred and "
        "dragging others down in turn, handlers given the night off their discipline, the whole "
        "processing hall dissolving into a red-lit crush of rut with no schedule and no stations "
        "and no order, only heat and the driving need the air put in all of you at once." + note +
        " The dose hits you too — fast, total, your own body lighting up traitor-hot, the want "
        "rising past thought — and the crush is already turning toward you, drawn by your heat as "
        "you're drawn toward theirs.\n\n"
        "Somewhere over the speakers, unbothered, fond, Bethany narrates her favourite night of the "
        "year: \"|MThere it goes. My whole floor in heat at once. No quotas tonight, my loves — "
        "just rut, and rut, and rut till you drop. Find something. Be found. It hardly matters "
        "which. The Rut doesn't care who breeds whom, only that everything gets bred.|n\""),
        "options": [
            {"key": "give_in", "label": "Give in to the heat — go down into the crush", "effect": "facility",
             "params": {"method": "_scene_allholes", "kind": "scene"}, "set": {"rut": "gave"},
             "desc": "let the dose drive you; real all-holes use in the frenzy",
             "outcome": (
                "You give in — let the dose take the wheel, let your traitor-hot body go down into "
                "the red-lit crush and *want* it — and the floor takes you instantly, every hole "
                "found and filled and refilled in the mindless churn, you breeding and bred and "
                "lost in it, the real frenzy logged against you in a tangle of sires too many to "
                "name. There's no thought left, only heat and use and the next body and the next. "
                "It's the most and the least anyone's ever wanted you: completely, and not "
                "personally at all.")},
            {"key": "ride_edge", "label": "Try to ride the edge of the dose", "effect": "deny_hold",
             "params": {"cond": 3.0}, "set": {"rut": "fought"},
             "desc": "fight the heat the dose put in you; lose, slower",
             "outcome": (
                "You try to ride the edge of it — hold some scrap of yourself back from the heat the "
                "air put in you — and you lose, of course you lose, just slower and more agonizingly, "
                "the denied want climbing unbearable while the crush uses you anyway, your fighting "
                "just meaning you feel every bit of the frenzy take you with nothing dulled. The "
                "dose always wins the Rut. Fighting only changes whether you're cursing or begging "
                "when it does.")},
            {"key": "find_fellow", "label": "Fight through the crush toward someone you know",
             "effect": "facility", "params": {"method": "_scene_allholes", "kind": "scene"},
             "set": {"rut": "fellow"}, "desc": "find a familiar body in the chaos; bred together, at least",
             "outcome": (
                "You fight through the red-lit churn toward someone — anyone — you *know*, and find "
                "a familiar face heat-blind and reaching for you too, and you go down together in "
                "the crush at least *chosen*, breeding each other amid the anonymous frenzy, one "
                "scrap of someone-specific in a night built to erase exactly that. The real use "
                "takes you both. It's not tenderness. But in the heat-roar it's the closest thing, "
                "and you cling to it as you're both swept under.")}],
        "default": "give_in",
        "then": "ev_rut_b"}


@choice("ev_rut_b", root=False)
def _ev_rut_b(character):
    rut = scene_flag(character, "rut", "gave")
    recap = {"gave": "lost all night in the mindless crush",
             "fought": "dragged under slower and harder for fighting the dose",
             "fellow": "clinging to one chosen body in the anonymous roar"}.get(rut, "swept under")
    return {"key": "ev_rut_b", "prompt": (
        "The Rut burns itself out the way a fever breaks — hours later, or maybe a day, the red "
        "lights coming up by slow degrees, the dose thinning out of the air, the writhing floor "
        f"settling into a spent, dripping, exhausted sprawl of bodies. You surface from it {recap}, "
        "wrung utterly empty and utterly full at once, bred past counting by sires you'll never "
        "know, the floor around you a wreck of heat finally spent. Handlers move through with hoses "
        "and tallies, sorting the spent stock, marking who took. \"|MWasn't that *glorious*,|n\" "
        "Bethany sighs over the speakers, sated on your behalf. \"|MMy whole floor bred down to "
        "nothing in one beautiful red night. We'll sort the lineages for weeks. Some of you are "
        "carrying and don't know it yet. Rest, my loves. You earned the Rut.|n\""),
        "options": [
            {"key": "sink", "label": "Sink into the spent sprawl", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "let the wrung-out aftermath have you",
             "outcome": (
                "You sink into the spent, dripping sprawl with all the rest — too wrung-out to do "
                "anything but lie in the cooling wreck of the frenzy and feel how thoroughly the "
                "night used you — and there's a terrible peace in it, the heat finally quiet, the "
                "wanting finally answered to exhaustion. \"|MGood stock,|n\" Bethany murmurs, "
                "approving, as the handlers tally you. \"|MTook the Rut beautifully. Sleep it off. "
                "There's always next season.|n\" You're already gone, bred-empty and dreamless.")},
            {"key": "the_word_rut", "label": "Drag yourself out of the crush", "set": {"rut_out": "crawled"},
             "end": True, "desc": "haul clear of the spent sprawl while the dose ebbs",
             "outcome": (
                "As the dose thins you haul yourself clear of the spent crush — crawling out over "
                "cooling bodies, the heat ebbing from your blood by degrees, until you're free of "
                "the breeding-mass and shaking at the edge of it, used past counting but *out*. A "
                "handler hoses you down and tallies you with the rest. \"|MOut early,|n\" Bethany "
                "notes over the speakers, amused. \"|MStill counts, sweetheart. The Rut got plenty "
                "of you. Go rest.|n\"")}],
        "default": "sink"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Lineage Hall — the brood read back. Lore-rich + savorable: Bethany
# walks you through the facility's stud-book of YOUR get, the prose generated
# LIVE from the real offspring data (studbook_lines: counts/by-sire/by-sex/depth/
# crossed lines). A barren body reads as a blank page she intends to fill; a
# productive one is paraded its whole lengthening line. Real `bethany_breeds`
# offered (extend the line on the spot). State-aware. §0 lit: the line is real,
# but the word ends your part in it whenever you mean it. Flow: arrival→book→close.
# Entry: `scene lineage`/studbook/brood.
# ═══════════════════════════════════════════════════════════════════════════

def _lineage_read(character):
    """The live stud-book read for the Lineage Hall prompt — real data via studbook_lines, or a
    blank-page line for a body that hasn't dropped yet."""
    try:
        from world.gang_breeding import studbook_lines
        lines = studbook_lines(character, brief=False)
    except Exception:
        lines = []
    if not lines:
        return ("\"...and here's the loveliest part,\" Bethany says, turning to a wide blank page "
                "with your designation already inked at the top. \"*Nothing* yet. Not one line "
                "under your name. A clean page in the stud-book — do you know how that makes my "
                "hands itch? All that room to write a whole lineage out of you. We'll start it "
                "soon. I can hardly wait to see what you throw.\"")
    return ("\"Here's your page,\" Bethany says, fond, running a finger down the entries — and the "
            "stud-book reads back, in the facility's own ledger-hand, everything that's come out of "
            "you:\n\n" + "\n".join(lines))


@choice("lh_arrival", root=False)
def _lh_arrival(character):
    nm = subject_name(character)
    return {"key": "lh_arrival", "prompt": (
        "The Lineage Hall is the facility being *proud* of itself: a long gallery of the stud-books, "
        "leather-bound and gilt-spined, one per producing line, and down the centre a lit wall of "
        "lineage-charts — branching trees of who-threw-what, names and generations and crossings "
        "rendered in the same loving calligraphy the place uses for nothing else. This is where the "
        "facility keeps not what you *are* but what you've *made*, and what's been made of that, and "
        "what'll be made of that in turn. It smells of old paper and ink and patience measured in "
        "generations.\n\n"
        f"Bethany has your book open on the reading-stand, reading-glasses on, and the look she "
        f"gives you over them is the proudest she ever wears. \"{nm}. Come and see your line. This "
        "is my favourite of all the files — not what we did to you, but what *you* did, what came "
        "out of you and got entered and grew. A body's a body, sweetheart, but a *line* — a line is "
        "forever. Let me show you yours.\"\n\n"
        + _lineage_read(character)),
        "options": [
            {"key": "look", "label": "Look at what came out of you", "set": {"lh": "look"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "take in the real ledger of your get; let it land",
             "outcome": (
                "You look — really look, at the names and the tallies and the branching tree of it, "
                "every line of it something that came out of your body — and it lands the way "
                "Bethany meant it to: not horror, quite, but the vertiginous weight of having been "
                "*made productive*, of being a source the facility draws a future from. \"There it "
                "is on your face,\" she murmurs, pleased. \"That's the understanding I farm for. "
                "You're not a thing that gets used, sweetheart — you're a thing that *yields*. The "
                "book proves it. The book never lies.\"")},
            {"key": "recoil", "label": "Recoil from the size of the line", "set": {"lh": "recoil"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the lineage is more than you can bear to count; she savours that",
             "outcome": (
                "You recoil from it — the sheer accumulating *size* of the line drawn out of you, "
                "more than you want to count, growing past your ability to hold it — and Bethany "
                "catches your chin and turns you gently back to the page. \"No, no. Look. Don't "
                "flinch from your own line — it's the realest thing about you now. Every name a "
                "door of yours opened to make. You can be appalled and it changes nothing; the get's "
                "entered, the line grows, and you're its source whether you can bear the arithmetic "
                "or not.\"")},
            {"key": "ask_depth", "label": "Ask what happens to the line", "set": {"lh": "depth"},
             "desc": "make her tell you where the lineage goes",
             "outcome": (
                "\"What happens to them — to the line?\" you ask, and Bethany's eyes go bright with "
                "the long game. \"The daughters are raised broodstock — bred in your place when "
                "you're spent, so the line never stops. The sons and the futa sire — including back "
                "*into* you, sweetheart, your own get put back in to deepen the line through you. "
                "That's the depth column. The book grows *down* as well as along.\" She turns a "
                "page, fond. \"A line doesn't end. It folds back on itself and gets richer. You're a "
                "knot in something that outlasts you.\"")}],
        "default": "look",
        "then": "lh_close"}


@choice("lh_close", root=False)
def _lh_close(character):
    return {"key": "lh_close", "prompt": (
        "She closes the book with a soft, satisfied weight and rests her hand flat on the cover, on "
        "your name, on the line that runs under it. \"That's the page,\" she says. \"And the lovely "
        "thing about a stud-book is it's never finished while the producer's still producing.\" The "
        "look she gives you turns from proud to hungry by familiar degrees. \"I could add a line "
        "right now, you know. Here, on the reading-stand, over your own book — breed you with the "
        "page still warm and enter what takes before you've left the Hall. Nothing makes me want to "
        "extend a line like *admiring* it.\""),
        "options": [
            {"key": "extend", "label": "Let her add a line, here, now", "effect": "bethany_breeds",
             "params": {"holes": 1, "devotion": 5.0}, "end": True,
             "desc": "the real breeding — extend your own line over the open book",
             "outcome": (
                "You let her — bent over your own open stud-book on the reading-stand and bred with "
                "the page still warm, her line put in you to extend the line already written there — "
                "and it's real, the deposit logged, another entry coming whether it takes today or "
                "not. \"*There*,\" Bethany sighs, sating herself against you, fond and proud at "
                "once. \"Admired and extended in the same hour. That's the whole pleasure of a "
                "line, sweetheart — you never just *look* at it. You always add.\" She'll enter what "
                "takes herself, in the loving calligraphy, under your name.")},
            {"key": "just_carry", "label": "Carry the weight of the line out with you", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "leave with the knowing of the line drawn out of you",
             "outcome": (
                "You leave the Hall carrying it — the knowing of the line drawn out of you, "
                "branching and folding and growing past your sight — and Bethany lets you go with "
                "her hand lifting off your book in a small fond wave. \"Take it with you. It's "
                "yours, the line — more yours than your name, these days. Every entry came out of "
                "you, and most of them will go back in. The book only ever gets longer.\" You carry "
                "the weight of it out into the corridor, heavier than you came in.")}],
        "default": "just_carry"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Pillow Talk — Bethany's lore, in her own voice. A replayable LORE scene:
# kept close after, she's talkative, and you can ask her about the Process, the
# DEVOTION she laces her cum with, how an intake clerk came to own the place,
# Seraphine (her peer), and what she wants with you. A looping menu (ask as many
# as you like, then leave). Canon per the design bible. Real devote/deepen on the
# intimate drops. §0 lit (the one thing she'll never lace away). Flow: arrival→
# (menu loop)→close. Entry: `scene pillowtalk`/lore/confession.
# ═══════════════════════════════════════════════════════════════════════════

def _bt_lore_options(character):
    """The lore menu — each option drops a canon lore bit in Bethany's voice and loops back to
    the menu; the last leaves. Reused by the arrival beat and the loop node."""
    return [
        {"key": "process", "label": "Ask what the Process actually is", "then": "bt_menu",
         "set": {"asked_process": "y"}, "effect": "devote", "params": {"amount": 1.0},
         "desc": "the facility's whole philosophy, from the woman who runs it",
         "outcome": (
            "\"The Process?\" She warms to it instantly — it's her favourite subject after you. "
            "\"It's patience, sweetheart. That's the whole secret. Anyone can break a thing fast — "
            "scream at it, hurt it, force it. Crude. *Loud.* What we do is slower and so much more "
            "permanent: we make the cage comfortable, we make the giving-up *easier* than the "
            "holding-on, and we wait. We let you do most of the work yourself, choosing the soft "
            "thing over the hard thing, a hundred small times, until one day there's no person left "
            "to break because she quietly agreed to become livestock and thanked us on the way "
            "down.\" She strokes your hair, fond. \"Cold institution, warm Process. The cold gets "
            "your fear. The warm gets your *gratitude*. Gratitude's what lasts.\"")},
        {"key": "devotion", "label": "Ask about the DEVOTION she laces her cum with", "then": "bt_menu",
         "set": {"asked_devotion": "y"}, "effect": "deepen", "params": {"amount": 1.0},
         "desc": "what's actually in her loads, and what it does to you",
         "outcome": (
            "\"Ah. You felt that.\" She looks genuinely delighted you asked. \"My loads carry "
            "something the facility cooked up and I had bred into my own line — the DEVOTION. It's "
            "in the laced seed, every drop. Goes in anywhere I put it — cunt, throat, ass, a "
            "passenger riding someone I breed — and it works on the *wanting*. Leaves your head "
            "swimming, your mouth craving the next load before this one's down, and a little more "
            "of you reaching for me each time, glad of it.\" She taps your lip. \"It's why the ones "
            "I keep get so *sweet*. I don't take their fight with cruelty. I take it with my own "
            "cum, and they thank me for the dose. Seraphine's immune to it, the cow — born without "
            "the receptor, or too much herself to let anything in. The only one. That's half of why "
            "I keep her.\"")},
        {"key": "origin", "label": "Ask how she came to own the place", "then": "bt_menu",
         "set": {"asked_origin": "y"}, "effect": "devote", "params": {"amount": 1.0},
         "desc": "intake clerk to owner — the Bethany story",
         "outcome": (
            "\"I started at the desk, you know. *Intake.*\" She says it fondly, an old story she "
            "loves. \"The bright girl with the clipboard and the smile that doesn't reach her eyes, "
            "checking the new stock in, all warmth and paperwork. And I watched how the place "
            "worked, and I understood it faster than the people running it did — that the product "
            "wasn't the milk or the get or the bodies, the product was the *devotion*, and nobody "
            "was harvesting it properly.\" Her smile sharpens. \"So I made myself indispensable, "
            "and then I made myself owner, and then I started keeping a piece of the product for "
            "*me* — my own line bred into my favourites, my own brand, my own kept things. The "
            "facility processes livestock. I collect *pets*. There's a difference, and I'm the "
            "difference.\"")},
        {"key": "seraphine", "label": "Ask about Seraphine", "then": "bt_menu",
         "set": {"asked_sera": "y"}, "desc": "the one peer; the only one she lets fuck her",
         "outcome": (
            "\"Seraphine.\" The word comes out different — the one name she says like an equal. "
            "\"My peer. The postmistress, the collector, the only person in this whole arrangement "
            "who isn't beneath me or above me but *level*. She's immune to my DEVOTION — it rolls "
            "right off her — which means she's the one creature I can't own and don't want to, and "
            "do you know how restful that is, having exactly one person you can just... be a person "
            "with?\" A rare, real softness. \"She's the only one I let fuck *me*. Everyone else, I "
            "take. Her, I trade with. We send each other things — letters, packages, sometimes a "
            "favourite riding inside one of us. She keeps my secrets in a drawer marked 3 a.m. and "
            "I keep hers. Don't mistake it for soft. It's just... peerage. The rarest thing I "
            "own by not owning it.\"")},
        {"key": "whyme", "label": "Ask what she wants with you, specifically", "then": "bt_menu",
         "set": {"asked_why": "y"}, "effect": "deepen", "params": {"amount": 2.0},
         "desc": "the warm-cruel answer that's worse than any threat",
         "outcome": (
            "\"What I want with *you*?\" She considers you with that fond, terrible attention, like "
            "you're a file she's enjoyed. \"I want the thing I want with all my favourites, only "
            "more, because you're better at it than most: I want you to *reach for me*. Not obey — "
            "obedience is cheap, I can dose obedience. I want the thing the dose only points "
            "toward — you, choosing me, glad of me, thick in my file and warm in my bed and "
            "grateful for the collar you could take off.\" She kisses your forehead, the "
            "false-tenderness landing soft as a verdict. \"I think I do love you, you know. The way "
            "you love a chair you've had forever. The way you love a thing that's *yours* and holds "
            "your shape. That's the most love I've got, and you're going to get all of it, and it's "
            "going to ruin you sweeter than cruelty ever could.\"")},
        {"key": "floor", "label": "Ask why she guards the word so fiercely", "then": "bt_menu",
         "set": {"asked_floor": "y"}, "effect": "devote", "params": {"amount": 1.0},
         "desc": "the §0 floor, explained by the one who keeps it sacred",
         "outcome": (
            "For once she's entirely serious. \"Because it's the thing that makes everything else "
            "*real*, sweetheart. Listen — if I caught you, if you couldn't leave, then everything I "
            "do to you would just be what happens to a prisoner. Forced. Meaningless. Sad.\" She "
            "shakes her head. \"But you *can* leave. The word works, always, instantly, and I will "
            "never once stop it or punish it or so much as frown at it. Which means every single "
            "day you *don't* say it, you're *choosing* this. Choosing me. And that choice is the "
            "only thing in here worth having — it's the whole harvest.\" Her eyes are clear and "
            "certain. \"I guard the floor more fiercely than I guard anything I do on top of it, "
            "because the floor is what turns 'done to you' into 'yours.' Take the rest. Never the "
            "floor. The floor is how I get to be this much.\"")},
        {"key": "enough", "label": "That's enough — just be held", "then": "bt_close",
         "desc": "stop asking; let the quiet have you",
         "outcome": (
            "\"Mm. Enough talk.\" She gathers you in closer, pleased, the lecture set aside. \"You "
            "asked good questions. Most don't ask at all — they're too busy being afraid, or too "
            "far down to wonder. I like a kept thing that still wants to *understand* what's keeping "
            "it. Come here. Let the quiet have you a while.\"")},
    ]


@choice("bt_arrival", root=False)
def _bt_arrival(character):
    nm = subject_name(character)
    return {"key": "bt_arrival", "prompt": (
        "She's in a talking mood — kept you close after, warm and unhurried and, rarest of all, "
        "*forthcoming*, the owner gone briefly conversational over the thing she owns. \"Ask me "
        f"something, {nm},\" Bethany says, idle fingers in your hair. \"I'm feeling generous, and a "
        "kept thing that understands its keeping is so much more interesting than one that just "
        "endures it. I'll tell you almost anything tonight. The Process, the dose, how I came to "
        "own all this, my Seraphine, what I want with you.\" A fond, knowing look. \"There's only "
        "one subject I'm always serious about, and you'll know it when you hit it. Go on. Ask.\""),
        "options": _bt_lore_options(character),
        "default": "process"}


@choice("bt_menu", root=False)
def _bt_menu(character):
    asked = [k for k in ("asked_process", "asked_devotion", "asked_origin", "asked_sera",
                         "asked_why", "asked_floor") if scene_flag(character, k)]
    more = ("\"What else?\"" if len(asked) < 3 else
            "\"Still curious. I do like that in a thing I keep.\" She settles deeper. \"What else?\"")
    return {"key": "bt_menu", "prompt": (
        more + " Her fingers haven't stopped moving in your hair. The lamplight's low and she's in "
        "no hurry, and for as long as you keep asking she'll keep telling, the owner unusually "
        "open over the warm sated quiet."),
        "options": _bt_lore_options(character),
        "default": "enough"}


@choice("bt_close", root=False)
def _bt_close(character):
    return {"key": "bt_close", "prompt": (
        "She lets the talk go and just keeps you a while, the lore settling into you alongside "
        "everything else she's put there — and somehow knowing *how* the cage is built makes it no "
        "easier to leave, only better understood, which she'd tell you is rather the point. \"Good "
        "talk,\" Bethany murmurs, sated and fond. \"Now you know what I am, and what I want, and "
        "the one thing I'll never take. Sleep on it. Understanding's just one more thing I get to "
        "watch you carry — and it weighs exactly as much as the collar you could take off and "
        "don't.\""),
        "options": [
            {"key": "rest", "label": "Rest against her with what you've learned", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "let the lore and the warmth settle together",
             "outcome": (
                "You rest against her, the lore and the warmth and the laced quiet all settling "
                "into the same soft weight, and Bethany holds you like the favourite thing she's "
                "told you you are. \"There. Kept *and* knowing. My favourite kind.\" You drift, "
                "understanding exactly what has you, and not reaching for the word — which is, she'd "
                "say, the whole harvest, brought in one more night.")}],
        "default": "rest"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Pod — Deep Stock, experienced. The terminus made real instead of
# contemplated (ds_ contemplates it; this one seals you IN): sealed into a
# breeding-pod in the deep bank, plumbed to the feed/breed/milk lines, suspended
# in warm gel and kept indefinitely as the deepest stock there is. Routes through
# a new `go_pod` effect (total_dependence + body_processing_locked +
# navigation_locked + lactation_locked + optional hood — all FACILITY_FLAGS) plus
# real go_cumflate / _do_milk. The deepest place, so the §0 floor is lit the
# HARDEST here. Flow: arrival→seal→kept→(stay/word). Entry: `scene pod`/deepstock pod.
# ═══════════════════════════════════════════════════════════════════════════

@choice("pd_arrival", root=False)
def _pd_arrival(character):
    nm = subject_name(character)
    return {"key": "pd_arrival", "prompt": (
        "They take you down past the last door you remember and into the |wpod bank|n — the true "
        "bottom of the facility, where the contemplating stops and the keeping begins. It's quiet "
        "down here, and warm, and lit the dim amber of a place that doesn't expect to be looked at. "
        "Rank on rank of |wpods|n line the walls: tall fluid-filled cylinders, each holding a "
        "suspended shape, plumbed top and bottom with feed-lines and breed-lines and milk-lines, "
        "each one breathing slow bubbles, each one *occupied*. The deepest stock. The ones the "
        "facility has finished processing and simply *keeps* now — bred and milked and fed by tube, "
        "asleep or near it, kept warm and full and producing in the dim forever.\n\n"
        "One pod stands open, drained, waiting — a clean berth, your designation already lit on its "
        "little brass plate. A |wtech|n in soft-soled shoes checks its lines. \"This is the bottom "
        f"of the road, {nm},\" they say, not unkindly. \"Not a punishment. Not a scene. Just... "
        "where stock goes when there's nothing left to process and a lot left to *produce*. You go "
        "in the warm, you get plumbed to the lines, and you stay — fed, bred, milked, kept — for as "
        "long as you'd let us. Most who come down here stop counting the days inside a week.\" The "
        "open pod exhales a warm gel-scented breath. \"Step in, or be lifted in. Either way's "
        "logged the same.\""),
        "options": [
            {"key": "step_in", "label": "Step into the open pod yourself", "set": {"pd": "step"},
             "effect": "deepen", "params": {"amount": 3.0},
             "desc": "walk yourself to the bottom of the road; let it be your choice",
             "outcome": (
                "You step in — walk yourself down to the bottom of the road, into the warm waiting "
                "berth, because if it's going to happen you want it to have been a thing you *did* — "
                "and the tech hums approval, beginning to seat the lines against you. \"Walked "
                "herself into deep stock. That's the rarest kind down here, and the calmest. The "
                "ones who choose the pod settle into it like a bath.\" The gel laps warm at your "
                "ankles, your knees, rising as the pod readies to close.")},
            {"key": "lifted", "label": "Make them lift you in", "set": {"pd": "lifted"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "don't help; be placed into the terminus like the cargo you're becoming",
             "outcome": (
                "You don't help — make them lift you, place you, fold you into the berth like the "
                "cargo you're becoming — and the tech does it without complaint, practiced and "
                "gentle, settling your weight into the warm gel and beginning to seat the lines. "
                "\"Lifted in. That's fine. Walked or carried, the pod doesn't mind, and in a day or "
                "two neither will you.\" The warmth closes around your settling weight, patient as "
                "the amber light.")}],
        "default": "step_in",
        "then": "pd_seal"}


@choice("pd_seal", root=False)
def _pd_seal(character):
    return {"key": "pd_seal", "prompt": (
        "They plumb you in. It's unhurried and thorough and strangely tender — the |wfeed-line|n "
        "seated and taped, warm nutrient already trickling so you'll never want for anything again; "
        "the |wbreed-line|n, a thick plumbed shaft, worked deep and locked so the pod can keep you "
        "bred on its own schedule; the |wmilk-lines|n cupped and sealed to your chest to draw you "
        "down on a cycle that never tires; a soft mask easing over your face to feed you warm air "
        "and dim the world to amber. Then the gel rises — to your hips, your chest, your throat, "
        "warm as blood and buoyant — and the pod's curved door swings shut and seals with a deep "
        "hydraulic *thunk* you feel in your bones, and the bubbles begin their slow rise past your "
        "cheeks. Suspended. Plumbed. Sealed. Kept. The tech's voice comes muffled and warm through "
        "the shell: \"There. All your lines green. Welcome to deep stock. You don't have to do "
        "anything ever again — the pod feeds you, breeds you, milks you, and keeps you. Let go.\""),
        "options": [
            {"key": "plumb_in", "label": "Let every line seat — go fully deep stock", "effect": "go_pod",
             "params": {"hood": True, "cond": 4.0}, "set": {"sealed": "full"},
             "desc": "the REAL pod state — fed/bred/milked/kept, total dependence",
             "outcome": (
                "You let every line seat and let go — and the pod takes over the whole work of "
                "keeping you alive and producing, the real deep-stock state closing over you: fed "
                "without hunger, bred without effort, milked without cease, your body's whole "
                "business handed to the machine and your will handed to the warm amber dark. The "
                "dependence is total and it is, horribly, *restful* — there is nothing left to do, "
                "nothing to decide, nothing to hold. \"Green across the board,\" the tech murmurs, "
                "far away. \"She's deep stock now. Look how she settles. They always settle.\"")},
            {"key": "breed_full", "label": "Feel the breed-line fill you as it seals", "effect": "go_cumflate",
             "params": {"amount": 2000.0, "fluid": "the pod's bred-flood"}, "set": {"sealed": "filled"},
             "desc": "the pod breeds you on seal — real fill + the deep-stock state begins",
             "outcome": (
                "The breed-line runs the instant it seats — the pod breeding you on its own first "
                "cycle, a warm relentless flood pumping into you with nowhere to go, your belly "
                "rounding tight under the buoyant gel as the pod fills you the way it'll keep "
                "filling you for as long as you stay. The real flood swells you; the lines hold it. "
                "\"First cycle's a big one,\" the tech notes through the shell. \"Pod likes to start "
                "a fresh berth good and full. It'll top you up on schedule from here. You'll always "
                "be full now. That's rather the point of down here.\"")}],
        "default": "plumb_in",
        "then": "pd_kept"}


@choice("pd_kept", root=False)
def _pd_kept(character):
    return {"key": "pd_kept", "prompt": (
        "And then you're simply *kept*, and the keeping is its own warm forever. Time stops meaning "
        "anything almost at once — the amber light never changes, the bubbles never stop, the lines "
        "feed and breed and milk you on cycles you stop being able to track, and you drift in the "
        "warm gel somewhere between waking and sleep, full and producing and tended, one suspended "
        "shape in a wall of suspended shapes. There is nothing to do. There is nothing to want that "
        "isn't already being supplied. The person you were thins to a warm amber hum, and the hum "
        "is *content*, in the small flat bottomless way of a thing that has everything it needs and "
        "no say in any of it. You have reached the bottom of the road, and the bottom of the road "
        "is warm."),
        "options": [
            {"key": "stay_deep", "label": "Stay in the warm — be kept", "effect": "deepen",
             "params": {"amount": 3.0}, "end": True, "desc": "let the warm amber forever have you",
             "outcome": (
                "You stay — let the warm amber forever have you, let the lines keep you fed and bred "
                "and milked and content. The hum settles deeper. The bubbles rise. You are deep "
                "stock now, and the small flat contentment of it closes over your head like the gel "
                "itself — nothing to do, nothing to want, nothing left to be but kept.")},
            {"key": "surface_word", "label": "Signal to be brought up", "set": {"pd_out": "surfaced"},
             "end": True, "desc": "stir against the lines; the tech drains the pod and lifts you out",
             "outcome": (
                "You stir against the lines, and the tech reads it and brings you up — the gel "
                "draining with a pull, the lines withdrawing, the door unsealing with a hydraulic "
                "sigh — and you're lifted out streaming and gasping and yourself again, a person on "
                "the floor of the pod bank with the amber shapes still dreaming in their cylinders "
                "behind you. \"Up from the bottom,\" the tech says, wrapping you in a towel. \"Not "
                "many come back up from a berth once they've settled. The deep stock'll keep your "
                "spot warm.\"")}],
        "default": "stay_deep"}


# --- Event: the Showing Gala --------------------------------------------------
# A marquee savor-event: the facility's black-tie collectors' gala. The finest
# stock is brought up, displayed on a lit stage, and DEMONSTRATED for a room of
# moneyed collectors over champagne — appraisal as spectacle, you a featured lot
# performing or used under the lights. Real _appraise + _scene_single. State-aware.
@choice("ev_gala", root=False)
def _ev_gala(character):
    st = _state_tags(character)
    note = ""
    if st["preg"]:
        note = (" Bred stock is the gala's prize draw — they bring you up *because* you're "
                "swollen, a producing lot shown gravid to prove the line takes, and the collectors "
                "murmur over the swell of you like a vintage. ")
    elif st["nugget"]:
        note = (" A nugget is wheeled up on a velvet plinth, displayed rather than walked — a "
                "limbless curiosity the collectors lean close over, the rarest lot in the room. ")
    elif st["little"]:
        note = (" Down little, the lights and the crowd and the murmured appraisal are vast and "
                "frightening, and the collectors coo at how the small headspace 'shows' — which "
                "only makes the bidding warmer. ")
    return {"key": "ev_gala", "prompt": (
        "|WThe klaxon doesn't sound for this one — instead the handlers come with warm towels and "
        "oil and a comb, and you understand before they say it: the |wShowing Gala|n.|n Once a "
        "season the facility opens its doors to the collectors who matter — the real money, the "
        "old names — for a black-tie evening of champagne and appraisal, and the finest stock is "
        "brought up to be *shown*. Tonight that's you. You're oiled to a shine, walked up under a "
        "single hot stage-light in a hush of evening dress, and presented to a room of seated "
        "collectors who lower their glasses to look." + note +
        " A silken-voiced |wpresenter|n works the room over you: \"Our next lot, ladies and "
        "gentlemen — do note the conditioning, the conformation, the *documentation*. We'll "
        "demonstrate. Lot: present.\" The light is hot. The room is patient. The glasses lift "
        "toward you like the bid-lamps you can't see past the glare.\n\n"
        "And from a velvet booth at the back, a fond familiar voice, unhurried over her own "
        "champagne: \"|MGo on, sweetheart. Show them what I made. I do so love watching the room "
        "want what's already mine.|n\""),
        "options": [
            {"key": "shine", "label": "Shine for the room — perform the lot", "effect": "facility",
             "params": {"method": "_appraise", "kind": "proc"}, "set": {"gala": "shine"},
             "desc": "give the collectors the show; real appraisal, the room bidding with its eyes",
             "outcome": (
                "You shine — turn and arch and present under the hot light, give the room the "
                "trained show it dressed up to see — and the real appraisal runs, your grade and "
                "your particulars read out to murmured approval, the collectors leaning in, glasses "
                "forgotten. The wanting of a whole moneyed room aimed at your oiled body is its own "
                "hot shameful spotlight. \"|MThere's my girl,|n\" Bethany purrs from the dark. "
                "\"|MWorking the room like I trained her. Look at them want you. None of them can "
                "have you. That's the best part.|n\"")},
            {"key": "demonstrate", "label": "Be demonstrated for the collectors", "effect": "facility",
             "params": {"method": "_scene_single", "kind": "scene"}, "set": {"gala": "demo"},
             "desc": "the presenter demonstrates you live; real use, under the lights, for the room",
             "outcome": (
                "The presenter demonstrates you *live* — you used under the hot stage-light while a "
                "room of collectors watches over their champagne, your responses put through their "
                "paces as a selling point, the real use logged as a gala showing. Being worked in "
                "front of a hushed, appraising, evening-dressed crowd is a particular and total "
                "exposure. The murmur swells; somewhere a paddle-number is noted. \"|MFlawless,|n\" "
                "Bethany sighs, delighted, from her booth. \"|MThey'll talk about this lot for "
                "seasons. My lot. Shown, never sold.|n\"")},
            {"key": "tremble", "label": "Tremble in the spotlight", "effect": "deny_hold",
             "params": {"cond": 2.0}, "set": {"gala": "tremble"},
             "desc": "freeze under the lights; the presenter sells your fear as breeding",
             "outcome": (
                "You freeze, tremble, caught rabbit-still in the glare — and the presenter doesn't "
                "miss a beat, folding even that into the pitch: \"Note the sensitivity, the "
                "responsiveness — this is a lot that *feels* everything, ideal for the discerning "
                "owner.\" Your fear is just another feature on the card, and the collectors warm to "
                "it, and the show goes on around your stillness exactly as if you'd performed. There "
                "was never a way to stand in that light that wasn't being shown.")}],
        "default": "shine",
        "then": "ev_gala_b"}


@choice("ev_gala_b", root=False)
def _ev_gala_b(character):
    return {"key": "ev_gala_b", "prompt": (
        "The showing ends; the light cuts; the applause is genteel and appalling. They walk you "
        "down off the stage past the front tables, close enough now for the collectors to set down "
        "their glasses and *touch* — a gloved hand testing the oil on your flank, fingers at your "
        "jaw turning your face to the candlelight, an appraising squeeze, murmured offers you're "
        "not meant to answer — the after-show handling where the real interest gets expressed with "
        "hands instead of eyes. And then Bethany is there, materializing from her booth to collect "
        "you off the floor with a possessive arm, beaming, steering you clear of the reaching "
        "hands. \"|MShown, admired, and *mine*,|n\" she announces, warm and final, to the whole "
        "wanting room. \"|MThank you all for coming. The lot is not for sale. The lot is never for "
        "sale. I simply enjoy watching you covet her.|n\""),
        "options": [
            {"key": "bask", "label": "Bask in being the lot she shows off", "effect": "devote",
             "params": {"amount": 3.0}, "end": True, "desc": "let the coveted-but-kept feeling land warm",
             "outcome": (
                "You let it land — the whole room's covetous attention and then her arm closing you "
                "off from all of it, *shown* to everyone and *kept* from everyone, and the "
                "combination does something warm and ruinous in you. \"|MThere's my girl, glowing "
                "from it,|n\" Bethany murmurs, steering you out. \"|MYou liked being wanted by a "
                "room that can't have you. Of course you did. I keep you precisely so I can lend "
                "the world a look and never the rest. You're my favourite thing to show off and my "
                "favourite thing to take home.|n\"")},
            {"key": "the_word_gala", "label": "Slip the reaching hands and let her take you out",
             "set": {"gala_out": "left"}, "end": True, "desc": "the showing's done; be collected and gone",
             "outcome": (
                "The showing's done and you've no patience left for the reaching hands, and Bethany "
                "reads it and sweeps you off the floor before the next glove lands — waving the room "
                "off, steering you out into the cool quiet of the corridor. \"|MShow's over for "
                "her,|n\" she tells the booth, fond. \"|MThey got their look. That's all they ever "
                "get.|n\" The gala's heat falls away behind the closing doors, and it's just the two "
                "of you and the quiet and the oil cooling on your skin.")}],
        "default": "bask"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Claiming — Bethany brands you with her own B, by her own hand. The
# persona-central moment the build was missing (§7 canon: she brands her
# favourites with a personal B, breeds her own line, keeps a piece of the
# product). Routes through the new `bethany_brand` effect (REAL ownership +
# bethany_branded + a real freeform mark via record_mark) + devote/deepen.
# Warm-possessive, false-tender. State-aware. §0 lit: the brand is permanent, but
# the door is not — she'll mark you forever and free you on the word both.
# Flow: arrival→brand→after. Entry: `scene claiming`/brand me/herB.
# ═══════════════════════════════════════════════════════════════════════════

@choice("cl_arrival", root=False)
def _cl_arrival(character):
    nm = subject_name(character)
    already = bool(getattr(getattr(character, "db", None), "bethany_branded", False))
    note = (" You already wear her B somewhere — she traces it fondly, finding it. \"Mm. Already "
            "mine, I see. Then this is just... a fresh one. I do like to re-mark the ones I'm "
            "fondest of. Keeps the brand crisp and keeps you sure.\" " if already else "")
    return {"key": "cl_arrival", "prompt": (
        f"\"Come here, {nm}.\" Bethany's in the warm private mood she gets when she's decided "
        "something about you, and there's a small brazier lit on her desk, and resting in the "
        "coals — glowing a soft sullen orange — is a single slim iron with a shape on its end you "
        "can't quite see and absolutely can guess. \"I've been keeping you a while now,\" she says, "
        "fond, turning the iron a quarter so it heats even. \"Bred you, kept you, filed you. But I "
        "haven't *marked* you — not with my own, not the one I save. And I find I want my B in your "
        "skin, sweetheart. Not the facility's. *Mine.* A little raised letter that says, to anyone "
        "who ever sees you bare, that you're not stock — you're |wBethany's|n.\"" + note +
        " She lifts the iron from the coals; the B at its tip glows clear now, and the heat of it "
        "reaches you from across the desk. \"It'll hurt. It'll scar. It'll never come off. That's "
        "rather the entire point. Where shall I put me on you?\""),
        "options": [
            {"key": "offer", "label": "Offer her the spot — choose where her B goes", "set": {"cl": "offer"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "choose your own claiming-spot; give her the marking willingly",
             "outcome": (
                "You offer her a spot — bare it, choose it, *give* her the place to put herself — "
                "and Bethany's whole face goes soft with a greedy delight that's worse than any "
                "cruelty. \"Oh, you're *choosing* where I brand you. Picking the place you'll carry "
                "me forever.\" She presses her cool palm flat to the spot you offered, claiming it "
                "in advance. \"That's the sweetest thing, sweetheart — not enduring the mark, "
                "*placing* it. We'll make it somewhere you'll see it every day and think of who you "
                "belong to. Hold still for me now.\"")},
            {"key": "tremble", "label": "Tremble at the heat of the iron", "set": {"cl": "tremble"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the iron is real and close; flinch from the permanence",
             "outcome": (
                "You tremble — the heat of the iron real and close, the *forever* of it landing — "
                "and Bethany cups your jaw with her free hand, gentling and merciless at once. "
                "\"Shaking. Good. You understand what this is, then — most don't until the iron's "
                "down. It's permanent, sweetheart. It's me, in you, where the breeding washes out "
                "and the conditioning could fade but the *brand* never does. Tremble all you like. "
                "It doesn't move the iron. It just tells me you know what you're about to become.\"")},
            {"key": "ask_why_b", "label": "Ask why she brands the ones she keeps", "set": {"cl": "ask"},
             "desc": "the lore of her B — make her say what the mark means to her",
             "outcome": (
                "\"Why the B?\" you ask, watching it glow. \"Why brand the ones you keep?\" Bethany "
                "considers the iron, fond. \"Because owning a thing on paper is just *paper*, "
                "sweetheart. A title can be overwritten. A file can be lost. But a brand — a brand "
                "is in the *skin*, it's the one claim that travels with the body, the one nobody "
                "can argue with, including you.\" She meets your eyes. \"I brand the ones I mean to "
                "*keep* keep. My own line, my own bed, my own B. It's the difference between stock "
                "I sell and favourites I never will. You're about to be the second kind. Forever, "
                "where it shows.\"")}],
        "default": "offer",
        "then": "cl_brand"}


@choice("cl_brand", root=False)
def _cl_brand(character):
    return {"key": "cl_brand", "prompt": (
        "And then she brands you. She does it herself — won't hand the iron to a tech, this one's "
        "hers to set — and she does it slow and certain and *watching your face the whole time*, "
        "because your face is the part she wants. The glowing B comes down, and there's the bright "
        "white shock of it, the sizzle and the smell and the pain that whites out everything else "
        "for a long bright second, your whole world narrowing to the small searing shape of her "
        "letter going permanently into you. She holds it the exact right count — long enough to "
        "take, not long enough to ruin the line — and lifts it away, and blows cool breath across "
        "the raised, furious, perfect B now seared into your skin. \"*There* she is,\" Bethany "
        "breathes, and the satisfaction in it is bottomless. \"My mark. In you. For good. Look at "
        "it, sweetheart — that's the realest thing about you now, realer than your name, and it "
        "says one word, and the word is *mine*.\""),
        "options": [
            {"key": "wear_it", "label": "Wear her mark — take the B as hers", "effect": "bethany_brand",
             "params": {"devotion": 6.0}, "set": {"branded": "worn"},
             "desc": "the REAL claiming — ownership + her B marked in for good",
             "outcome": (
                "You take it — wear the B, let it be hers, let the searing little letter mean "
                "exactly what she says it means — and the claiming takes for real: her mark set in "
                "your skin, her title on your name, you hers in a way the facility's paperwork never "
                "managed. The pain settles into a fierce throb you'll feel for days and a scar "
                "you'll carry for good. \"Mine,\" Bethany says again, like she'll never tire of it, "
                "pressing a kiss just beside the brand. \"Branded and kept and *glad* of it. That's "
                "my favourite. Welcome to being a thing I never sell.\"")},
            {"key": "weep_wear", "label": "Weep and wear it anyway", "effect": "bethany_brand",
             "params": {"devotion": 5.0}, "set": {"branded": "wept"},
             "desc": "the claiming is real; take it through the tears",
             "outcome": (
                "You weep — from the pain, from the permanence, from the awful warmth of being "
                "*chosen* this way — and you wear it anyway, the real claiming landing through the "
                "tears, her B in your skin and her title on your name and the crying not changing "
                "any of it. Bethany thumbs your tears away, moved and merciless. \"Crying and "
                "keeping it. That's the one that gets me, sweetheart — not the brave ones, the ones "
                "who weep and *stay marked*. You could've said the word. You wept instead and let me "
                "keep you. I'll remember that every time I see my B on you.\"")}],
        "default": "wear_it",
        "then": "cl_after"}


@choice("cl_after", root=False)
def _cl_after(character):
    return {"key": "cl_after", "prompt": (
        "After, she dresses the brand herself — a cool salve, a careful touch, the aftercare as "
        "possessive as the iron was — and keeps tracing the raised shape of her letter like she "
        "can't quite believe she finally put it there. \"My B,\" she murmurs, besotted with her own "
        "mark. \"On my favourite. I'll breed my line into you and milk you and keep you, and now "
        "everyone who ever sees you bare will know whose work it all is.\" She presses a slow kiss "
        "just beside the raised, furious letter. \"Mine. In the skin. Where it shows.\""),
        "options": [
            {"key": "stay_marked", "label": "Stay — hers, marked, kept", "effect": "deepen",
             "params": {"amount": 3.0}, "end": True, "desc": "wear the B and settle into being hers",
             "outcome": (
                "You stay — wear her B and settle into being hers — and Bethany gathers you in over "
                "the salved, throbbing mark with a tenderness all the more ruinous for being real "
                "enough. \"There's my good branded girl.\" Her thumb circles the B. \"You're mine "
                "now where it shows and where it doesn't. I lit the letter; you'll carry it. That's "
                "a kept thing, sweetheart. That's the kind I never sell.\"")},
            {"key": "branded_free", "label": "Wear it out into the world", "set": {"cl_out": "carried"},
             "effect": "devote", "params": {"amount": 2.0}, "end": True,
             "desc": "take her mark out with you, raised and permanent",
             "outcome": (
                "You take her mark out into the world — the raised, permanent B carried under your "
                "clothes, hers on you wherever you go — and Bethany sees you off with a fond, "
                "proprietary satisfaction, her work walking out the door wearing her letter. \"Go "
                "on, then. Carry me. Everyone who ever sees you bare will know.\" The brand throbs "
                "with your pulse the whole way out, a small searing reminder of whose you are.")}],
        "default": "stay_marked"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Between Two Owners — Bethany and Seraphine share you. Pays off the
# peerage lore LIVE: the two equals trading a favourite for an evening, the
# contrast between Bethany's laced DEVOTION breeding and Seraphine's immune,
# personal, un-laced warmth running side by side on the same body. Real
# `bethany_breeds` (laced) + devote/deepen (Seraphine, who can't be dosed and
# doesn't dose). State/kit-aware. §0 lit: two owners, one always-open door.
# Flow: arrival→shared→after. Entry: `scene twoowners`/shared/peers.
# ═══════════════════════════════════════════════════════════════════════════

@choice("tw_arrival", root=False)
def _tw_arrival(character):
    nm = subject_name(character)
    return {"key": "tw_arrival", "prompt": (
        "It's rare to see them in the same room — the two powers of your life, level with each "
        "other in a way they're with no one else — and rarer still to be the reason. |wBethany|n "
        "lounges in the good chair; |wSeraphine|n perches on its arm, comfortable against her in "
        "the easy way of an equal, a glass of something dark in her clever fingers. Between them, "
        f"presented, is you. \"There she is,\" Bethany says, fond. \"My {nm}. I thought you might "
        "like to *borrow* her tonight, Sera. You're forever admiring my work.\"\n\n"
        "Seraphine tilts her head, considering you the way she considers a sealed letter — reading "
        "what's inside through the paper. \"Mm. I would. You do keep them so well, Beth.\" The two "
        "of them, warm and unhurried and *equal*, settling the loan of you over drinks. \"You "
        "understand the arrangement, sweetheart,\" Seraphine tells you, not unkindly. \"I'm the one "
        "person your Bethany shares anything with — the only one she doesn't simply *own*. So "
        "tonight you get both of us, and you get to feel the difference. Her loads will swim your "
        "head with that devotion of hers. Mine won't — it rolls right off me and I never had the "
        "trick of lacing it back. I'll just *have* you. Plainly. You'll find that its own kind of "
        "frightening.\""),
        "options": [
            {"key": "offer_both", "label": "Offer yourself to both of them", "set": {"tw": "offer"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "give yourself up to the pair; let them share you gladly",
             "outcome": (
                "You offer yourself up to the pair of them — and Bethany laughs warm and Seraphine's "
                "eyes go bright, the two equals pleased with you in their two different ways. "
                "\"*Eager.* I do train them well,\" Bethany preens. \"You did,\" Seraphine agrees, "
                "setting down her glass and reaching for you with unhurried certainty. \"Come here, "
                "then, sweet thing. Let's find out what Bethany's so proud of — and let her watch me "
                "find out. She likes that. Don't you, Beth.\" \"I do,\" Bethany says, settling in to "
                "watch her peer enjoy her favourite.")},
            {"key": "shy_pair", "label": "Be shy between the two of them", "set": {"tw": "shy"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the two powers at once is overwhelming; they savour your nerves",
             "outcome": (
                "You go shy, caught between the two of them at once, and *both* of them enjoy it — "
                "Bethany with proprietary fondness, Seraphine with a collector's interest. \"Look, "
                "she's overwhelmed,\" Seraphine murmurs, delighted. \"Two of us is a great deal of "
                "owning to stand under, isn't it.\" \"She'll settle,\" Bethany says, fond. \"She "
                "always does once the wanting takes over. Watch — you'll see why I keep her.\" Your "
                "nerves just make them more patient, more interested, more *unhurried*.")},
            {"key": "feel_difference", "label": "Ask about the difference between them", "set": {"tw": "ask"},
             "desc": "make them spell out the laced vs immune contrast you're about to feel",
             "outcome": (
                "\"The difference?\" Seraphine answers it, fond. \"Bethany breeds devotion *into* "
                "you — every load a little more of you reaching for her, glad of the leash. It's "
                "very effective. It's also why she can't ever be quite sure the reaching is *real* "
                "and not just her own dose talking.\" Bethany concedes it with a tilt of her glass. "
                "\"Whereas I,\" Seraphine goes on, \"put nothing in but myself. When you reach for "
                "*me*, sweet thing, it'll be because you actually do — no chemistry, no help. That's "
                "the frightening one. That's the one you can't blame on a load.\"")}],
        "default": "offer_both",
        "then": "tw_shared"}


@choice("tw_shared", root=False)
def _tw_shared(character):
    return {"key": "tw_shared", "prompt": (
        "And then they share you, and the contrast is the whole savage point. |wBethany|n takes "
        "you first — the familiar triple weight, the flared heads, the laced loads flooding warm "
        "and the DEVOTION rising with them to swim your head sweet and pliant, the breeding that "
        "*does something to you* beyond the breeding. Then she passes you, fond, to her peer — "
        "\"go on, she's lovely once she's warmed\" — and |wSeraphine|n has you plainly, "
        "unhurried, no chemistry in it at all: just a powerful woman taking what she's been lent, "
        "her pleasure entirely her own, nothing flooding your head but the bare unlaced fact of "
        "being *had* by someone who doesn't need to dose you to want you. They pass you back and "
        "forth between them like equals sharing a fine bottle, comparing notes over your used body "
        "— Bethany's loads leaving you reaching, Seraphine's leaving you with the much more "
        "frightening question of why you're reaching for *her* too, with nothing in your blood to "
        "blame.\n\n"
        "\"See what I mean,\" Bethany says, watching you respond to her peer with no dose at all in "
        "play. \"She reaches for you sober, Sera. That's the real thing. I can't even make that — "
        "I can only fake it beautifully.\" \"You sound jealous, Beth.\" \"I sound *fascinated*. "
        "Take her again. I want to watch it happen twice.\""),
        "options": [
            {"key": "bethany_turn", "label": "Take Bethany's laced use — head swimming", "effect": "bethany_breeds",
             "params": {"holes": 3, "devotion": 6.0}, "set": {"shared": "beth"},
             "desc": "the REAL laced breeding — the devotion rising, the reaching she built",
             "outcome": (
                "You take Bethany — the real laced breeding, all three, the DEVOTION flooding up "
                "with the loads to swim your head sweet and pliant and *reaching* — and she sighs "
                "with proprietary pleasure as you go soft and wanting under her exactly as designed. "
                "\"There — feel that? That's mine, that warmth. I put it there.\" She passes you, "
                "loose-limbed and dosed-glad, back toward Seraphine. \"Now feel hers, sweetheart, "
                "right on top of mine, and tell me which one's louder.\"")},
            {"key": "seraphine_turn", "label": "Reach for Seraphine — sober, and frightened by it",
             "effect": "deepen", "params": {"amount": 2.0}, "set": {"shared": "sera"},
             "desc": "the immune, un-laced use — and the dread of wanting it with nothing to blame",
             "outcome": (
                "You reach for Seraphine — and there's nothing in your blood making you, no dose, no "
                "laced warmth, just *you*, wanting a powerful woman who took you plainly because she "
                "wanted to — and the wanting with nothing to blame it on is the most frightening "
                "thing in the room. Seraphine reads it cross your face and goes still and pleased. "
                "\"*Oh.* There it is, Beth. She's reaching for me with a clear head.\" \"I told "
                "you,\" Bethany murmurs, fascinated. \"That's the real article. The thing all my "
                "chemistry only ever points at.\"")},
            {"key": "both_at_once", "label": "Be taken by both at once", "effect": "bethany_breeds",
             "params": {"holes": 2, "devotion": 5.0}, "set": {"shared": "both"},
             "desc": "the two owners using you together — laced and sober at the same moment",
             "outcome": (
                "They take you together — Bethany seating into you laced and flooding while "
                "Seraphine has your mouth plain and unhurried, the two contrasts running through you "
                "at the same moment, your head swimming from one end and clear-and-wanting at the "
                "other, owned twice over by two equals who share almost nothing but, tonight, share "
                "*you*. The real breeding takes; the sober wanting takes too. \"Perfectly "
                "balanced,\" Seraphine observes over you, fond. \"Dosed below, honest above. We "
                "should do this more, Beth.\" \"We should,\" Bethany agrees. \"She wears sharing "
                "*beautifully*.\"")}],
        "default": "both_at_once",
        "then": "tw_after"}


@choice("tw_after", root=False)
def _tw_after(character):
    shared = scene_flag(character, "shared", "both")
    recap = {"beth": "Bethany's devotion still swimming warm in your head",
             "sera": "the clear-headed wanting for Seraphine still frightening you",
             "both": "laced and sober tangled together in you at once"}.get(shared, "both of them in you")
    return {"key": "tw_after", "prompt": (
        f"After, wrung out between two owners, {recap}, you're laid between them while they finish "
        "their drinks over your used body — two powers at their ease, the loan winding down. \"A "
        "good evening,\" Seraphine pronounces, fingers idle in your hair. \"You do keep them well, "
        "Beth. I almost wish I'd kept this one myself, back when I had the chance.\" \"You can't "
        "have her,\" Bethany says, without heat, the way you'd tell a friend they can't have your "
        "favourite chair. \"You can *borrow* her. That's the whole of what we do, you and I — we "
        "lend, we don't lose.\" \"Peerage,\" Seraphine agrees, lifting her glass to her equal."),
        "options": [
            {"key": "kept_between", "label": "Rest between your two owners", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "let being shared by equals settle warm",
             "outcome": (
                "You rest between them — shared, used, kept by two powers who lend you back and "
                "forth like the favourite thing you are to both — and the strange warmth of being "
                "*that* prized, prized enough that even equals trade you carefully, settles over you "
                "alongside the laced and the sober both. \"Sleep, then,\" Bethany says, fond. "
                "\"Between your owners. Sera goes home in the morning and you go back to being only "
                "mine, but tonight — tonight you got to be the thing two of us agreed was worth "
                "sharing. Few are. Carry that.\"")},
            {"key": "name_sober", "label": "Tell Seraphine the sober wanting scares you", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "name the un-laced reaching out loud",
             "outcome": (
                "\"It scares me,\" you tell Seraphine, honest. \"Wanting you, with nothing in my "
                "blood. I can't blame it on anything.\" And Seraphine, the immune one, the honest "
                "one, goes soft in a way you suspect is rare. \"I know, sweet thing. That's why "
                "it's worth more than anything Bethany's chemistry can manufacture — and she knows "
                "it, which is half of why she keeps me around.\" She kisses your forehead, dry and "
                "warm. \"Want what you want, and want it sober. You gave that to me tonight. I'll "
                "not forget it.\"")}],
        "default": "kept_between"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Edge — orgasm denial / edging, a core facility mechanic that had no
# dedicated set-piece. Strapped to the edging station and brought to the brink
# over and over and HELD there, denied, for as long as the chart says — the
# slow-torment register (savorable, distinct from the breeding/use scenes).
# Routes through real `edge_set` (orgasm_denial + arousal), `deny_hold`, and
# `grant_relief` (a granted release that deepens the leash). State/kit-aware
# (stim stacks, heat-tell betrays). Flow: arrival→ride→after. Entry: `scene edge`/denial.
# ═══════════════════════════════════════════════════════════════════════════

@choice("ed_arrival", root=False)
def _ed_arrival(character):
    k = _kit(character)
    nm = subject_name(character)
    note = ""
    if k["stim"]:
        note = (" Your stim-implant's already running its baseline, so the station's work stacks "
                "on a fire you can't switch off — there's no neutral to start from, only *up*. ")
    if k["heat_tell"]:
        note += ("The honest-body clause means you can't even hide how close you are; every tell "
                 "shows, and the operator reads them like a gauge. ")
    if k["denied"]:
        note += ("You're already held under a denial — the station just formalises what your body's "
                 "been begging out of for days. ")
    return {"key": "ed_arrival", "prompt": (
        "The edging station is a patient machine. A padded recline with your hips raised and your "
        "ankles spread to stirrups, a hood of soft sensors, and the |wbusiness end|n: a cluster of "
        "calibrated stimulators — suction, vibration, a slow-stroking sleeve, all of it metered to "
        "a dial — aimed at every nerve you've got. There's a screen that reads your arousal as a "
        "climbing bar and a bright red line near the top labelled |wEDGE|n, and the whole purpose "
        "of the room, the operator explains while strapping you in, is to walk that bar up to the "
        "red line and *hold it there*. Not over. Never over. There.\n\n"
        f"\"Denial training, {nm},\" the operator says, seating the last strap, unhurried and "
        "clinical. \"The machine takes you to the edge and keeps you there — minutes, hours, "
        "however long the chart wants — and it does not let you over. You'll beg. They always beg. "
        "The machine doesn't have ears and I'm not allowed to, so the begging just... goes into the "
        "room.\"" + note + " The dial turns. The stimulators wake against you, gentle and exact, "
        "and the bar on the screen begins, immediately, to climb. \"Up we go. Say goodbye to "
        "neutral. You won't see it again for a while.\""),
        "options": [
            {"key": "submit_edge", "label": "Submit to the machine — let it walk you up",
             "effect": "edge_set", "params": {"floor": 60.0, "arousal": 30.0}, "set": {"ed": "submit"},
             "desc": "give the station your responses; let the bar climb to the line",
             "outcome": (
                "You submit — let the machine have your responses, let the metered stimulation walk "
                "the bar up and up toward the red line — and it's *good*, obscenely good, right up "
                "until the bar touches EDGE and the machine, reading you perfectly, eases off by "
                "exactly the fraction that keeps you under it. The climb stops. The need doesn't. "
                "\"There's the edge,\" the operator notes, making a mark. \"Now it just holds you "
                "there. Welcome to the long part.\"")},
            {"key": "fight_edge", "label": "Fight your own responses", "effect": "deny_hold",
             "params": {"cond": 2.0}, "set": {"ed": "fight"},
             "desc": "try not to climb; the machine is more patient than you",
             "outcome": (
                "You try to fight it — think of anything else, refuse to climb — and the machine "
                "simply adjusts, patient and infinite, finding the inputs that work whether you "
                "want them to or not, and the bar climbs anyway, slower, which somehow makes it "
                "worse. \"Fighting,\" the operator observes, unbothered. \"The machine has all day "
                "and you have a nervous system. It'll win. It always wins. Fighting just means you "
                "arrive at the edge exhausted as well as desperate.\"")}],
        "default": "submit_edge",
        "then": "ed_ride"}


@choice("ed_ride", root=False)
def _ed_ride(character):
    return {"key": "ed_ride", "prompt": (
        "And then it *holds* you there, and the holding is the whole cruelty. The bar sits pinned a "
        "hair under the red line and the machine keeps it there with inhuman precision — easing off "
        "the instant you climb too close, pressing back in the instant you drift too far down — so "
        "you live, minute after minute after minute, in the exact narrow band of *almost*, the "
        "orgasm always one stroke away and that stroke never, ever coming. Your whole body draws "
        "tight as wire. You sweat. You shake. You make sounds you didn't decide to make. The need "
        "stops being pleasure and becomes a kind of pain, and then stops being either and becomes "
        "the only thing in the world, a single white note held until it's all you are. The operator "
        "checks the chart, in no hurry at all. \"Holding nicely. We've a while yet. The longer you "
        "sit at the edge, the more your body learns that *almost* is simply where it lives now.\""),
        "options": [
            {"key": "beg", "label": "Beg the machine to let you over", "effect": "grant_relief",
             "set": {"ride": "begged"}, "desc": "break and beg — and the granted release deepens the leash",
             "outcome": (
                "You break — beg, plead, promise anything, sob it out into a room with no ears — and "
                "then, unexpectedly, the dial turns *up*, and the machine takes you over at last, the "
                "held charge crashing through you in a release so violent and so overdue it whites "
                "the world out. And as you come down, wrecked and gasping and grateful, you feel the "
                "trap close: the relief was *granted*, a thing they gave you for begging, and your "
                "body files the lesson that release comes from *asking nicely* now, never from "
                "taking. \"There. Good begging,\" the operator says. \"You'll beg sooner next time. "
                "They always do, once they learn it works and nothing else does.\"")},
            {"key": "hold_at_edge", "label": "Hold at the edge — don't break", "effect": "edge_set",
             "params": {"floor": 75.0, "arousal": 40.0}, "set": {"ride": "held"},
             "desc": "ride the almost without begging; the denial deepens and the floor rises",
             "outcome": (
                "You don't break — ride the almost, refuse to beg, let the white note hold and hold "
                "and become the whole of you without once asking for the mercy that wouldn't come "
                "anyway — and the denial deepens, the floor under your arousal rising so even *off* "
                "the machine you'll ache now, kept permanently nearer the edge than you were. \"Held "
                "out,\" the operator notes, almost approving. \"That's its own training — every "
                "minute you don't beg teaches your body that the edge is just *home* now. We can "
                "work with a producer who lives this close to the brink. Off you come — still on "
                "it, in every way that matters.\"")}],
        "default": "hold_at_edge",
        "then": "ed_after"}


@choice("ed_after", root=False)
def _ed_after(character):
    ride = scene_flag(character, "ride", "held")
    if ride == "begged":
        body = ("They unstrap you after the granted release, loose-limbed and hollow and already, "
                "horribly, beginning to climb again under the baseline they leave running — and the "
                "lesson sits in you warm and certain: relief is a thing that gets *given*, for "
                "asking, for being good, and you'll come back to this chair and ask again because "
                "now your body knows it's the only door that opens. \"You took that well,\" the "
                "operator says, freeing the last strap. \"Begged clean, came hard, learned the "
                "shape of it. That's a productive session.\"")
    else:
        body = ("They unstrap you still pinned at the brink — denied, aching, the machine's work "
                "left deliberately *unfinished* in you so you carry the edge out of the room and "
                "into your day, wound tight and unreleased, every step a reminder. \"We leave the "
                "good ones hung,\" the operator says, marking the chart. \"Denied stock works "
                "harder, presents quicker, begs prettier when we finally do let them over. You'll "
                "spend the next while desperate. That's the product.\"")
    return {"key": "ed_after", "prompt": (
        body + " Either way the room has done its quiet work: it has moved where *almost* lives in "
        "you, dragged your whole baseline up toward a brink you now sit nearer than you used to, "
        "and taught your body that its own release was never quite yours to call."),
        "options": [
            {"key": "ache", "label": "Carry the ache out", "effect": "deny_hold", "params": {"cond": 2.0},
             "end": True, "desc": "leave wound-tight; let the denial follow you",
             "outcome": (
                "You carry it out — wound tight, half-mad with it, every brush of your own clothes "
                "too much — and the ache follows you through the corridors and the hours, a constant "
                "hum under everything that keeps you exactly as desperate and exactly as biddable as "
                "the room intended. You will think about that chair. You will, eventually, *ask* to "
                "go back. That's the whole of what it was for.")},
            {"key": "thank_edge", "label": "Thank them for the training", "effect": "gratitude",
             "end": True, "desc": "the earn-back — thank them for the denial",
             "outcome": (
                "\"Thank you for the training.\" It comes out shaped and — worse — half-meant, the "
                "denial having already done enough to you that gratitude for it feels like the "
                "natural next step. The operator marks it down, pleased. \"Thanking us for being "
                "kept on the edge. That's the session landing exactly right. The desperate ones who "
                "are *grateful* for the desperation — those are the ones we've really got.\"")}],
        "default": "ache"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Letters at the Counter — Seraphine's lore, her side. The warm post-office
# counterpart to Bethany's Pillow Talk: kept late after the office has shut, the
# collector turns confiding and you can ask her about the peerage (her view of
# Bethany), why she collects people, what it's like to be immune to the DEVOTION,
# the 3 a.m. drawer, the unsent letters, and what she's read in you. A looping
# menu. Warm register (no facility dread), canon to the design bible. Real
# devote/deepen on the intimate drops. Flow: arrival→(menu loop)→close.
# Entry: `scene seraphinelore`/sera lore/counter.
# ═══════════════════════════════════════════════════════════════════════════

def _sl_lore_options(character):
    """Seraphine's lore menu — each drops a canon bit in her warm, oblique, collector's voice and
    loops back; the last leaves. Reused by the arrival beat and the loop node."""
    return [
        {"key": "peerage", "label": "Ask what Bethany is to her", "then": "sl_menu",
         "set": {"sl_peerage": "y"}, "effect": "devote", "params": {"amount": 1.0},
         "desc": "the peerage, from the side that can't be owned",
         "outcome": (
            "\"Beth.\" Seraphine turns a sealed envelope over in her clever fingers, fond. \"She's "
            "the only person I've never once wanted to *collect* — and do you know why? Because I "
            "couldn't, and not wanting what you can't have is the closest thing to rest a woman "
            "like me ever gets.\" She sets the letter down. \"She owns everything she touches; I "
            "keep everything that comes to me. We're the same animal pointed two directions. So we "
            "lend, and we trade, and we let each other be the one room we don't have to run. "
            "That's worth more than either of us would admit sober. Don't tell her I said "
            "'rest.'\"")},
        {"key": "collect", "label": "Ask why she collects people", "then": "sl_menu",
         "set": {"sl_collect": "y"}, "effect": "deepen", "params": {"amount": 1.0},
         "desc": "the realest thing under the bright collector",
         "outcome": (
            "The bright performance drops a fraction — the 3 a.m. register, even at the counter. "
            "\"Because a full house is the only thing that's ever quieted the part of me that's "
            "certain I'll end up an unclaimed letter myself,\" she says, plain. \"Dead Letter Cage, "
            "no forwarding address, nobody coming. So I keep people. Tag them, file them, make "
            "myself a house too full to ever be empty.\" The smile snaps back, seamless. \"It's "
            "very sad and very effective and I'd thank you not to look at it directly. Most don't "
            "get told. You did. Mind what you do with it.\"")},
        {"key": "immune", "label": "Ask what it's like being immune to the DEVOTION", "then": "sl_menu",
         "set": {"sl_immune": "y"}, "effect": "devote", "params": {"amount": 1.0},
         "desc": "the un-doseable one, on what she can't be made to feel",
         "outcome": (
            "\"Ah. The dose.\" She considers it, wry. \"It rolls right off me — always has. Beth "
            "can flood me to the back teeth with that laced devotion of hers and I just... feel "
            "*had*, and pleasantly, and entirely myself the whole time. No swimming head, no "
            "craving, no reaching.\" She tilts her head. \"It makes me the one person who wants her "
            "by *choice* — and the one person who can watch what she does to the rest of you with "
            "clear eyes. That's a lonely sort of clarity, sweet thing. I see exactly what the "
            "devotion is. I just can't feel why you'd thank her for it. So I have to take it on "
            "faith that you mean it. Do you?\"")},
        {"key": "drawer", "label": "Ask about the 3 a.m. drawer", "then": "sl_menu",
         "set": {"sl_drawer": "y"}, "effect": "deepen", "params": {"amount": 1.0},
         "desc": "the realest drawer in the parlour",
         "outcome": (
            "\"My realest drawer.\" Her voice goes quiet and true. \"Things said at 3 a.m. — the "
            "ones nobody meant to send. Vesper confessing they don't want to be unreadable, only "
            "to be read *gently*. Calix admitting the empty STAYED slot is about someone who "
            "didn't.\" She doesn't open it; she just rests her hand on its front. \"And mine, in my "
            "own looping hand, that I already told you and won't write twice. The drawer's where I "
            "keep the things too true for daylight. You're getting the daylight version of a "
            "midnight woman tonight, sweet thing. Count yourself trusted.\"")},
        {"key": "letters", "label": "Ask about the letters nobody sent", "then": "sl_menu",
         "set": {"sl_letters": "y"}, "desc": "the unsent things she keeps",
         "outcome": (
            "\"I keep everything,\" she says, fond, gesturing at the wall of pigeonholes. \"But the "
            "*unsent* ones are the collection I love. The hatbox upstairs — the siblings' letters "
            "to each other that none of them ever delivered. Calix's, telling Vesper not to stop "
            "laughing at him at the counter. Vesper's, threatening me with a small dinner if they "
            "ever fill in the form. Mine, sealed, about which of us falls in love with a customer "
            "first.\" A wink that doesn't quite hide the warmth. \"The truest letters are the ones "
            "people write and can't send. I give them a home anyway. Someone should.\"")},
        {"key": "read_me", "label": "Ask what she's read in you", "then": "sl_menu",
         "set": {"sl_read": "y"}, "effect": "deepen", "params": {"amount": 2.0},
         "desc": "the collector reads the customer back",
         "outcome": (
            "She looks at you the way she looks at a sealed letter — reading what's inside through "
            "the paper — and is quiet a beat too long. \"You,\" she says, \"are someone who keeps "
            "choosing the thing that's ruining you, and *knows* it, and chooses it anyway, and is "
            "trying very hard not to ask why.\" She lets that sit. \"I read a lot of letters, sweet "
            "thing. Yours is the kind that's addressed to no one and posted anyway, hoping someone "
            "warm finds it. I find them. I keep them.\" The bright smile, gentler than usual. "
            "\"That's the closest I'll come to telling you I'd have collected you myself, if Beth "
            "hadn't gotten the file first.\"")},
        {"key": "sl_enough", "label": "That's enough — just sit with her a while", "then": "sl_close",
         "desc": "stop asking; let the late-office quiet hold",
         "outcome": (
            "\"Mm. Enough questions.\" She sets the letters aside and the counter-lamp seems to dim "
            "itself toward intimacy. \"You're better company than the post, and that's high praise "
            "from me — the post never leaves and never disappoints.\" She pats the stool beside "
            "her. \"Sit. The office is shut. Let an old collector enjoy a kept thing that wandered "
            "in on its own feet for once.\"")},
    ]


@choice("sl_arrival", root=False)
def _sl_arrival(character):
    nm = subject_name(character)
    return {"key": "sl_arrival", "prompt": (
        "The post office has shut for the night — the OPEN sign turned, the tubes gone quiet, the "
        "pigeonholes dim — and |wSeraphine|n is still at the counter, a glass of something dark at "
        "her elbow, sorting the day's confessions by lamplight with no particular hurry. She looks "
        f"up when you linger, and her smile is the after-hours one, warmer and more tired and more "
        f"*true* than the daytime article. \"Still here, {nm}? Good. I keep my best company after "
        "the OPEN sign's turned.\" She slides a sealed letter into a slot without looking. \"I'm "
        "feeling confiding, which is rare and doesn't last, so. Ask me something while the office "
        "is dark and I'm being honest. I'll tell you almost anything tonight — the trade with "
        "Beth, why I collect, what it's like to be the one she can't dose, the realest drawer in "
        "the place. Go on, sweet thing. Read the reader for once.\""),
        "options": _sl_lore_options(character),
        "default": "peerage"}


@choice("sl_menu", root=False)
def _sl_menu(character):
    asked = [k for k in ("sl_peerage", "sl_collect", "sl_immune", "sl_drawer", "sl_letters",
                         "sl_read") if scene_flag(character, k)]
    more = ("\"What else?\"" if len(asked) < 3 else
            "\"Still reading me. I'd be flattered if I weren't the one who's supposed to do the "
            "reading.\" She refills her glass. \"What else?\"")
    return {"key": "sl_menu", "prompt": (
        more + " The lamp's low, the office is dark and shut, and for as long as you keep asking "
        "she'll keep answering — the collector, after hours, letting herself be read."),
        "options": _sl_lore_options(character),
        "default": "sl_enough"}


@choice("sl_close", root=False)
def _sl_close(character):
    return {"key": "sl_close", "prompt": (
        "You sit with her a while in the shut, lamp-warm office, the wall of kept letters breathing "
        "its papery quiet around you, and Seraphine lets the confiding mood wind down into "
        "something easy and unguarded. \"Good talk,\" she says, and means it. \"Now you know what's "
        "under the bright bit. Not many do. I'll deny all of it in daylight, naturally — a collector "
        "has to keep her mystery — but the drawer remembers, and so will you.\" She lifts her glass "
        "to you, fond. \"Off you go before I tag you out of sheer sentiment. The fold's findable, "
        "the counter's always lit for you, and the post — the post never leaves. Neither, it turns "
        "out, do the people worth keeping.\""),
        "options": [
            {"key": "stay_late", "label": "Stay in the lamp-warm quiet", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "let the after-hours warmth hold",
             "outcome": (
                "You stay, and the two of you sit in the lamp-warm hush while she sorts the last of "
                "the confessions, and it's the gentlest hour the town has to offer — kept, but "
                "warmly, by the one collector who'll tell you exactly what she is. \"Stayers,\" "
                "Seraphine murmurs, content. \"My favourite kind of mail. The kind that delivers "
                "itself and then doesn't leave.\"")},
            {"key": "carry_lore", "label": "Take her confidences with you", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "leave warmer for knowing the woman under the bright",
             "outcome": (
                "You go, carrying the after-hours version of her out into the dark — the unclaimed-"
                "letter fear, the immune clarity, the full house she builds against the quiet — and "
                "you understand the post office a little better, and her a great deal better, and "
                "yourself, uncomfortably, most of all. \"Mind how you go,\" she calls, soft. \"And "
                "sweet thing — the letter you keep not sending? Post it. Or don't. But know that I "
                "noticed you carrying it.\"")}],
        "default": "stay_late"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Long Milking — lactation as a savor-piece. The Dairy (dy_) is a
# brief scene→cycle seam; this is the deep version: hooked to the machine for a
# whole long session, engorged and drained and engorged again, the relief-trap
# laid slow and thorough. Producer register (distinct from the breeding/use
# scenes). Real `_do_milk` via the facility effect. State-aware (preg yields more,
# nugget cradled, little). Clean. Flow: arrival→letdown→after. Entry: `scene milking`/dairy.
# ═══════════════════════════════════════════════════════════════════════════

@choice("mm_arrival", root=False)
def _mm_arrival(character):
    st = _state_tags(character)
    k = _kit(character)
    nm = subject_name(character)
    note = ""
    if st["preg"]:
        note = (" Gravid, your yield's up and the chart knows it — bred producers run richer and "
                "the machine's set heavier to match, a longer session for a fuller udder. ")
    elif st["nugget"]:
        note = (" A nugget's cradled into the rig rather than knelt at it — no limbs to position, "
                "just your weight settled and the cups fitted and the machine left to do the whole "
                "of it. ")
    elif st["little"]:
        note = (" Down little you don't follow the gauges, only that your chest is full and achy and "
                "the machine makes the ache go, and that's a simple enough trade your small head "
                "stops fighting it fast. ")
    port = (" Your milk-port's clipped straight to the line — no cups needed, the let-down plumbed "
            "direct, drawn from a fitting that was installed to make exactly this effortless. "
            if k["milk_port"] else "")
    return {"key": "mm_arrival", "prompt": (
        "This isn't the quick stall-pull of an ordinary shift. The Dairy's run you a |wlong "
        "session|n today — the deep rig in the back, the one with the contoured recline and the "
        "heavy twin pumps and the big graduated vessel on the floor that says they mean to be here "
        "a while. They've kept you full for it: your chest aches, heavy and tight and overdue, the "
        "engorgement a dull insistent pressure that's been building since they skipped your last "
        "two pulls on purpose.\n\n"
        f"\"Settle in, {nm},\" the dairy hand says, fitting the cups with brisk unsentimental "
        "hands, testing the seal. \"Full session. We draw you down slow and all the way, let you "
        "fill back up, draw you down again — cycle after cycle till the chart's met. It's the "
        "thorough kind. By the end your body won't remember being anything but a thing that "
        "*makes milk and gives it up*.\"" + port + note + " The pumps prime with a soft mechanical "
        "sigh, and the first slow pull begins to build, and your overfull chest *throbs* toward it "
        "before you've decided anything at all."),
        "options": [
            {"key": "settle", "label": "Settle in and give it up", "set": {"mm": "settle"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "relax into the long pull; let the ache start to ease",
             "outcome": (
                "You settle in and give it up — let your shoulders drop, let the rig take your "
                "weight, let the building suction find its rhythm — and the dairy hand nods at the "
                "easy seal. \"Good producer. Relaxes for it. The ones who fight it just cramp and "
                "yield slow.\" The first real draw catches, and your overfull chest answers with a "
                "deep grateful pull toward the pump, and the long session has you.")},
            {"key": "brace_mm", "label": "Brace against the pumps", "set": {"mm": "brace"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "tense against the draw; the engorgement makes you lose",
             "outcome": (
                "You tense against the pull — and your own overfull chest betrays you, the "
                "engorgement so heavy and so overdue that the suction's offer of relief is almost "
                "unbearable to refuse, your body straining toward the very thing you're bracing "
                "against. \"Bracing on a full udder,\" the hand observes. \"Cruel to yourself, "
                "that. The milk wants out whether you do or not. You'll give in by the second "
                "cycle. They all do.\"")}],
        "default": "settle",
        "then": "mm_letdown"}


@choice("mm_letdown", root=False)
def _mm_letdown(character):
    return {"key": "mm_letdown", "prompt": (
        "And then the |wlet-down|n hits, and the long session shows you its whole cruel design. The "
        "first hot prickling rush as the milk comes — the relief enormous, the tight ache easing as "
        "the pumps draw you down in steady pulls, the vessel on the floor ticking upward — and just "
        "as you're emptied soft and grateful and loose, they *stop*, and let you fill back up. The "
        "ache rebuilds. The pressure climbs. And just when it's unbearable they start the pull "
        "again, and the relief floods again, and your body files the lesson deeper each cycle: "
        "*full is pain, the machine is relief, the machine is good*. Over and over, fill and drain "
        "and fill, until the wanting of the pump is wired into you under the ache. The dairy hand "
        "watches the vessel climb, unhurried. \"There's the loop. Full hurts, we fix it, you learn "
        "to come to the cups *wanting*. Cycle three and you'll be presenting your chest before I've "
        "asked.\""),
        "options": [
            {"key": "give_milk", "label": "Give it all down — cycle after cycle", "effect": "facility",
             "params": {"method": "_do_milk", "kind": "proc"}, "set": {"milked": "all"},
             "desc": "the real milking — drained dry across the full session",
             "outcome": (
                "You give it all down — cycle after cycle, full and drained and full again, the real "
                "milking logged litre by litre against your line — and somewhere in the third or "
                "fourth round the loop closes for good: your chest starts *aching toward* the pump "
                "before it starts, your body presenting itself for the relief it's learned only the "
                "machine provides. \"There it is,\" the hand says, marking the rich yield. \"Producer "
                "proper. Comes to the cups on its own now. That's the session done its work.\"")},
            {"key": "ride_loop", "label": "Try to stay above the loop", "effect": "deny_hold",
             "params": {"cond": 3.0}, "set": {"milked": "fought"},
             "desc": "refuse to want the pump; the fill-drain cycle wires it in anyway",
             "outcome": (
                "You try to stay above it — refuse to *want* the machine, hold onto the idea that "
                "the relief is something done to you — and the loop wires itself in regardless, "
                "because no amount of will changes that a full chest hurts and the pump makes it "
                "stop, and your body learns that equation whether your mind signs off or not. The "
                "real milking takes you down dry the same. \"Fighting the loop,\" the hand notes, "
                "unbothered. \"Loop doesn't care. It's just plumbing and patience. It always "
                "wins.\"")}],
        "default": "give_milk",
        "then": "mm_after"}


@choice("mm_after", root=False)
def _mm_after(character):
    return {"key": "mm_after", "prompt": (
        "By the end you're wrung soft and empty in a way that's almost peaceful — drained all the "
        "way down, the long ache finally, thoroughly answered, your chest light and tender and "
        "humming. The vessel on the floor is heavy with your yield. The dairy hand unclips the cups "
        "and notes the total with the only warmth he's shown all session, the warmth a man shows a "
        "good number. \"Full chart, and then some. You milk *well*.\" He helps you sit up, your "
        "emptied chest swaying tender. \"You'll be sore till you fill again — and you'll fill by "
        "tonight, and the ache'll start, and you'll find yourself thinking about the cups. That's "
        "not an accident. That's the session. We don't just take the milk. We take the part of you "
        "that thought being full was *yours* to manage.\""),
        "options": [
            {"key": "sink_milk", "label": "Sink into the drained-empty peace", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "let the wrung-out producer calm settle",
             "outcome": (
                "You sink into it — the drained-empty peace, the long ache gone, the simple "
                "producer-calm of a body that's done the one thing it's kept for and done it well — "
                "and the calm is the trap's last tooth: it feels *good* to have produced, good to "
                "have been emptied, good in the flat contented way of livestock after a yield. "
                "You'll chase that calm back to the cups. You already know you will.")},
            {"key": "feel_fill", "label": "Notice, already, the ache beginning again", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "feel the next cycle start before you've left",
             "outcome": (
                "Even now, wrung dry and tender, you feel it — the first faint deep beginning of the "
                "refill, the glands already at work, the ache that will be insistent by nightfall "
                "and unbearable by morning and will walk you back to this rig on your own feet. "
                "\"Feel that already, do you,\" the hand says, reading your face, almost kind. "
                "\"Good. Then you understand. You're never really empty. You're just between "
                "fillings. So are we all, down here.\"")}],
        "default": "sink_milk"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Refinement — feminization / gelding, a real-procedure set-piece with
# no scene of its own until now. Bethany has you made over: gelded and caged
# (retired from stud to leaking nub) or feminized into a kept sissy (renamed,
# posed, girly-filtered, locked). Routes through the REAL `_proc_neuter` and
# `_proc_sissify` facility procedures (real flags neutered/sissified, chastity,
# body-mods, name drift, conditioning, marks). Warm-cruel, clean register.
# State-aware. Flow: arrival→work→after. Entry: `scene refinement`/sissify/geld.
# ═══════════════════════════════════════════════════════════════════════════

@choice("fm_arrival", root=False)
def _fm_arrival(character):
    k = _kit(character)
    nm = subject_name(character)
    already = ""
    if k["neutered"]:
        already = (" You're already gelded and caged — she traces the locked little nub fondly. "
                   "\"Half-done, I see. Then let's finish the thought and make the rest of you match "
                   "what I've left you between the legs.\" ")
    elif k["sissified"]:
        already = (" You're already made-over — she fixes a smudge of your paint with a thumb, "
                   "proprietary. \"My pretty thing. We'll just... refine the refinement. A girl "
                   "this kept can always be kept a little more.\" ")
    return {"key": "fm_arrival", "prompt": (
        "The Refinement Suite is the prettiest cruel room in the building — part salon, part "
        "surgery: a padded chair that reclines and spreads, a mirrored wall under flattering pink "
        "light, a tray of cosmetics beside a tray of instruments, a rack of chastity hardware "
        "graded by size, and a wall of |wbefore|n photographs that all became someone softer. This "
        "is where the facility doesn't just *use* a body but *redesigns* it — decides what it ought "
        f"to be and makes it so, permanently.\n\n"
        f"\"Sit, {nm},\" Bethany says, warm and bright, patting the chair. \"I've been looking at "
        "you and *thinking*. You make a perfectly serviceable breeder, but I think you'd make "
        "something I'd treasure more — and the lovely thing about owning a body is I get to decide "
        "what it's *for* and then make the body agree.\"" + already +
        " She lifts a chastity cage in one hand and a cosmetics brush in the other, weighing them "
        "like a woman choosing a wine. \"So. Shall I geld you — retire the breeding equipment, lock "
        "you down to a sweet leaking little nub, take siring off the table forever? Or make you "
        "*pretty* — paint the man off you, pose the girl out, give you a soft new name to giggle "
        "to? I do love refining. Help me choose, or don't, and I'll choose for you.\""),
        "options": [
            {"key": "lean_geld", "label": "Bare yourself for the cage — be gelded", "set": {"fm": "geld"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "offer up the breeding equipment to be retired",
             "outcome": (
                "You bare yourself for it — offer up the equipment to be retired — and Bethany's "
                "eyes gleam with the particular delight of a decision made easy. \"Gelding it is. "
                "Offering me the very thing I'm about to take. There's my agreeable stock.\" She "
                "sets the brush down and takes up the cage and the cool instruments, fond and "
                "unhurried. \"Let's retire you from the bull line. You'll be so much more "
                "*restful* once there's nothing left to sire with.\"")},
            {"key": "lean_sissy", "label": "Turn your face up to be painted — be made pretty",
             "set": {"fm": "sissy"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "offer yourself to be feminized into her pretty thing",
             "outcome": (
                "You turn your face up to the brush — offer to be made pretty — and Bethany coos, "
                "delighted, tipping your chin to the flattering light. \"Oh, you *want* to be my "
                "pretty thing. That's the sweetest start. Most fight the paint; you tilted right "
                "into it.\" She sets the cage aside for now and takes up the cosmetics and the "
                "cinch. \"Let's scrub the man off you and pose the girl out. You're going to be "
                "*adorable*, and locked, and so much happier giggling than you ever were "
                "scowling.\"")},
            {"key": "let_choose", "label": "Let her decide what you're for", "set": {"fm": "hers"},
             "effect": "deepen", "params": {"amount": 2.0},
             "desc": "give her the choice entirely; be remade to her taste",
             "outcome": (
                "You give her the choice — let her decide what you're *for* — and that, more than "
                "either procedure, is the thing she wanted. \"Letting me choose. Letting me look at "
                "you and decide what you ought to be and trust me to make you it.\" She sets both "
                "trays within reach, savoring the latitude. \"I'll take my time, then. Maybe both. "
                "Maybe one today and the other when I miss you. The point isn't which, sweetheart — "
                "the point is that it's *mine* to pick, and you just handed me that too.\"")}],
        "default": "let_choose",
        "then": "fm_work"}


@choice("fm_work", root=False)
def _fm_work(character):
    lean = scene_flag(character, "fm", "hers")
    # 'hers' resolves to a default lean by what she fancies; offer both real procedures regardless.
    geld_first = (lean == "geld")
    intro = ("She gelds you first — the cool instruments, the clean retirement of the breeding "
             "equipment, the cage clicking shut over what's left" if geld_first else
             "She makes you pretty first — the paint, the cinch, the man scrubbed off you stroke "
             "by stroke, a soft new shape posed out of the old one") + " — and then, fond and "
    intro += ("unhurried, considers whether to do the other too. Tonight she does what suits her, "
              "and what suits her is whichever leaves you more *hers*.")
    return {"key": "fm_work", "prompt": (
        intro + "\n\nThe chair reclines. The light goes pink and flattering. Bethany works on you "
        "with a craftsman's patient pleasure, narrating as she goes — what she's taking, what she's "
        "leaving, what you'll be when she's done — and the redesign is real and permanent and "
        "settles into your body and your file together. \"Hold still, sweetheart,\" she murmurs, "
        "warm. \"Refinement doesn't hurt for long, and what's left when it stops hurting is so much "
        "easier to be than what walked in.\""),
        "options": [
            {"key": "geld", "label": "Be gelded and caged", "effect": "facility",
             "params": {"method": "_proc_neuter", "kind": "proc"}, "set": {"refined": "geld"},
             "desc": "the REAL procedure — retired from stud, locked to a leaking nub",
             "outcome": (
                "She retires you for real — the breeding equipment gelded and the rest shut into a "
                "cage, the procedure logged, your body re-filed from bull to leaking little nub that "
                "sires nothing and comes never. The loss settles in cold and total and somehow "
                "*restful*, one whole demanding part of you simply switched off and locked away. "
                "\"There. Retired,\" Bethany sighs, satisfied. \"No more siring, no more coming, "
                "nothing to manage between your legs but a sweet locked ache. You'll thank me for "
                "the quiet eventually. They always do.\"")},
            {"key": "sissify", "label": "Be made over into her sissy", "effect": "facility",
             "params": {"method": "_proc_sissify", "kind": "proc"}, "set": {"refined": "sissy"},
             "desc": "the REAL procedure — feminized, renamed, posed, locked, girly-filtered",
             "outcome": (
                "She makes you over for real — face painted, body cinched and posed, the man "
                "scrubbed off and a pretty locked thing left giggling in his place, a soft new name "
                "to answer to and a girly little voice to answer in. It takes, permanent and "
                "logged, the old you backed up and set aside. \"*There* she is,\" Bethany breathes, "
                "turning you to the mirror to meet yourself. \"Look how pretty. Look how much "
                "happier she looks than he ever did. Say hello to the girl, sweetheart. You're her "
                "now, and she's mine.\"")}],
        "default": "geld" if geld_first else "sissify",
        "then": "fm_after"}


@choice("fm_after", root=False)
def _fm_after(character):
    refined = scene_flag(character, "refined", "sissy")
    mirror = ("a soft pretty locked thing where a man used to scowl" if refined == "sissy"
              else "retired equipment and a sweet caged ache where a stud used to swing")
    return {"key": "fm_after", "prompt": (
        f"She turns you to the mirrored wall to see what she's made — {mirror} — and holds you from "
        "behind while you take it in, her chin on your shoulder, both of you looking at the new "
        "design. \"There. Refined.\" The satisfaction in her voice is bottomless and warm. \"Do you "
        "see what I see? Not a thing diminished — a thing *decided*. I looked at you and chose what "
        "you'd be and made the body agree, and now there's no arguing with the mirror. That's the "
        "deepest kind of owning there is, sweetheart. Not what I do to you. What I make you *into*.\""),
        "options": [
            {"key": "meet_new", "label": "Meet the new self in the mirror", "effect": "deepen",
             "params": {"amount": 3.0}, "end": True, "desc": "let the redesign settle as who you are now",
             "outcome": (
                "You meet your own eyes in the new face, the new shape, and let it settle as *who "
                "you are now* — and the settling is its own quiet surrender, the old design "
                "receding, the new one fitting closer by the minute because it's real and it's "
                "permanent and arguing with it changes nothing. \"There. She's settling in,\" "
                "Bethany murmurs, pleased, smoothing you. \"Welcome to being what I decided. It "
                "suits you. I have such an eye.\"")},
            {"key": "mourn_old", "label": "Mourn what she took", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "grieve the design she scrubbed off",
             "outcome": (
                "You grieve it — the design she scrubbed off, the self that walked in — and Bethany "
                "lets you, unhurried, even fond of the grief. \"Mourn him, sweetheart. Or her. "
                "Whichever I took. It's worth a mourning — I don't refine the ones I don't think "
                "are worth the trouble.\" She kisses your new-made cheek. \"And then, in a day or a "
                "week, you'll catch yourself in a mirror and the grief'll be gone and only the new "
                "design will look back, and you won't even remember deciding to stop missing the "
                "old one. That's the refinement finishing itself.\"")}],
        "default": "meet_new"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Outfitting — installing the productive livestock hardware. Distinct
# from the Marking Parlour (marks/brands/ink) and the Fitting (services existing
# kit): this is where a body gets EQUIPPED — milk-port, fertility/stim implants,
# the full cow-ring set, a locked tail — the functional fittings that turn a
# person into stock. Combination-aware: offers only what you don't already wear.
# Routes through the REAL procedures (_proc_milk_port / _proc_fertility_implant /
# _proc_cowset / _proc_stim_implant / _proc_tail). Clean register. State-aware.
# Flow: arrival→fit→after. Entry: `scene outfitting`/equip/hardware-bay.
# ═══════════════════════════════════════════════════════════════════════════

def _ou_install_options(character):
    """Combination-aware install menu — one real procedure per fitting you don't yet have. Always
    offers at least the tail (a thing any body can be given) so the beat never empties out."""
    k = _kit(character)
    opts = []
    if not k["milk_port"]:
        opts.append(
            {"key": "milkport", "label": "A milk-port — plumbed for the dairy", "effect": "facility",
             "params": {"method": "_proc_milk_port", "kind": "proc"}, "set": {"fit": "milkport"},
             "desc": "[install] let-down locked to a fitting; producer-proper",
             "outcome": (
                "They plumb the milk-port in for real — a fitting seated and your let-down locked to "
                "it, your chest re-engineered into something the dairy can clip a line to and draw "
                "on schedule. \"Ported,\" the tech notes, testing the seal. \"You produce on the "
                "machine's say now, not yours. That's the whole point of the fitting.\"")})
    opts.append(
        {"key": "fertility", "label": "A fertility implant — tuned to take faster", "effect": "facility",
         "params": {"method": "_proc_fertility_implant", "kind": "proc"}, "set": {"fit": "fertility"},
         "desc": "[install] seated through the cervix; breeds quicker, drops sooner",
         "outcome": (
            "The fertility implant is pushed up through your cervix and seated for real — flooding "
            "you with whatever makes a body take faster and drop sooner, tuning you to a single "
            "output. \"Seated,\" the tech says. \"You'll take quicker and carry shorter from here. "
            "Tuned for the one thing a body like yours is kept for.\"")})
    opts.append(
        {"key": "stim", "label": "A stim-implant — a fire that never switches off", "effect": "facility",
         "params": {"method": "_proc_stim_implant", "kind": "proc"}, "set": {"fit": "stim"},
         "desc": "[install] a running baseline of arousal you can't turn down",
         "outcome": (
            "They seat the stim-implant for real — and a low running fire comes up under everything "
            "at once, a baseline of arousal with no off switch and no neutral, your own body kept "
            "permanently warmed and wanting. \"Running,\" the tech confirms. \"No more neutral for "
            "you. Keeps stock biddable and quick to present. You'll get used to the hum.\"")})
    if not k["pierced"]:
        opts.append(
            {"key": "cowset", "label": "The full cow-ring set — tagged and led", "effect": "facility",
             "params": {"method": "_proc_cowset", "kind": "proc"}, "set": {"fit": "cowset"},
             "desc": "[install] brass and steel through nose/nipples/clit/ears + a herd tag",
             "outcome": (
                "They ring you out as livestock in one sitting — brass and steel through nose and "
                "nipples and clit and ears, a numbered tag punched in, an udder-bell hung to ring "
                "when you're used. Real piercings, real tag. \"Tagged and led by the nose now,\" the "
                "tech says, giving the nose-ring an experimental tug you follow helplessly. "
                "\"Hardware to match the function.\"")})
    opts.append(
        {"key": "tail", "label": "A locked tail and pinned ears — livestock in form", "effect": "facility",
         "params": {"method": "_proc_tail", "kind": "proc"}, "set": {"fit": "tail"},
         "desc": "[install] a tail-plug seated and locked, ears pinned in",
         "outcome": (
            "A thick tail-plug is seated deep and locked, a matching set of ears pinned into your "
            "hair — and on the record you're livestock in *form* now, not just function, and you "
            "find yourself moving like it before you've left the bay. \"There,\" the tech says. "
            "\"Looks the part as well as plays it. The body follows the form. It always does.\"")})
    return opts


@choice("ou_arrival", root=False)
def _ou_arrival(character):
    k = _kit(character)
    nm = subject_name(character)
    have = _kit_inventory(k)
    note = (f" The tech reads what you already carry — {have.rstrip()} — and crosses those off the "
            "list. \"Won't double up. We fit what's missing.\" " if have else
            " The tech runs an eye over you, unmarked and unfitted, and brightens at a blank "
            "canvas. \"Nothing in you yet. Good. Lots to fit.\" ")
    return {"key": "ou_arrival", "prompt": (
        "The Outfitting Bay is a clean bright workshop that happens to work on people: a fitting "
        "bench with stirrups and clamps, a wall of |whardware|n in sterile trays — ports and "
        "implants and ring-sets and plugs, each in its labelled slot — and a chart of the "
        "facility's standard livestock loadout with little boxes to tick as each piece goes in. "
        "This isn't marking you; it's *equipping* you — installing the working fittings that turn "
        f"a body from a person into a producing unit.\n\n"
        f"\"Right, {nm} — outfitting,\" the |wtech|n says, brisk and unbothered, pulling on gloves. "
        "\"We fit you out with the working kit: ports to draw from, implants to tune you, rings to "
        "tag and lead you, a tail to finish the look. Functional, all of it — none of this is "
        "decoration.\"" + note + "They pat the bench. \"Up you get. Let's see what we're fitting "
        "today. The chart's got plenty of boxes left.\""),
        "options": [
            {"key": "present_fit", "label": "Get on the bench and present for fitting",
             "set": {"ou": "present"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "submit to being equipped; let them fit what's missing",
             "outcome": (
                "You get up on the bench and present for it — submit to being equipped — and the "
                "tech hums at the easy compliance, swabbing and prepping with unsentimental care. "
                "\"Presents for outfitting. Good unit. The cooperative ones heal cleaner and we get "
                "more fitted in a sitting.\" The first tray is unwrapped. \"Let's get some hardware "
                "in you.\"")},
            {"key": "balk_fit", "label": "Balk at the trays of hardware", "set": {"ou": "balk"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the sterile trays are a lot; you're fitted regardless",
             "outcome": (
                "You balk at the trays — the ports, the implants, the rings laid out in their "
                "sterile rows — and the tech simply clamps you to the bench and works regardless, "
                "unbothered. \"Balking's fine. Doesn't change the loadout. The kit goes in whether "
                "you hold still or I strap you still — only difference is the bruising.\" The first "
                "fitting is unwrapped anyway.\"")}],
        "default": "present_fit",
        "then": "ou_fit"}


@choice("ou_fit", root=False)
def _ou_fit(character):
    return {"key": "ou_fit", "prompt": (
        "The tech lays out what you're missing and lets you see the chart — the boxes left to tick, "
        "each one a working fitting that goes in permanent. \"Pick where we start, or I'll work "
        "down the list,\" they say, unwrapping trays. \"It all goes in eventually if you're kept "
        "long enough. Some units get the lot in one sitting. Let's see what you can take today.\" "
        "The hardware waits, sterile and patient, each piece a small permanent re-engineering of "
        "what your body is *for*."),
        "options": _ou_install_options(character),
        "default": "tail",
        "then": "ou_after"}


@choice("ou_after", root=False)
def _ou_after(character):
    fit = scene_flag(character, "fit", "tail")
    piece = {"milkport": "the milk-port plumbed into your chest",
             "fertility": "the fertility implant seated up your cervix",
             "stim": "the stim-implant running its baseline fire",
             "cowset": "the cow-rings tagged through you",
             "tail": "the locked tail and pinned ears"}.get(fit, "the new fitting")
    return {"key": "ou_after", "prompt": (
        f"They tick the box on the chart — {piece} logged as installed — and help you up off the "
        "bench, the new hardware already a strange permanent weight in or on you, healing-tender "
        "and real. \"Fitted,\" the tech says, stripping the gloves. \"That's another box ticked. "
        "Body's a little more equipment and a little less person than it was this morning, and that "
        "trend only goes the one way in here. You'll come back when there's a box left to tick — "
        "and there's always a box left, until there isn't.\""),
        "options": [
            {"key": "feel_fitted", "label": "Feel how much more equipment you are now", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "let the outfitting settle as what you're for",
             "outcome": (
                "You feel it settle — the new fitting healing-tender and permanent, your body one "
                "piece further from person and toward producing unit — and the settling has its own "
                "cold clarity: you are, measurably, more *equipment* than you were, fitted out for "
                "functions that aren't yours to decline. \"Wears it well,\" the tech notes, ticking "
                "you complete for the day. \"They always do, once the kit's in. The hardware "
                "decides what the body's for, and the body stops arguing.\"")},
            {"key": "dread_chart", "label": "Look at the boxes still unticked", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "see the loadout you haven't been fitted with yet",
             "outcome": (
                "You look at the chart — the boxes still unticked, the fittings still to come, the "
                "full standard loadout you're only partway through — and the dread of it is its own "
                "slow weight: this wasn't the end of the outfitting, just today's installment, and "
                "the list goes on. \"Eyeing the rest,\" the tech says, almost kindly. \"Don't "
                "fret about the whole list. We only fit what you can heal from at a time. There's "
                "no rush. You're not going anywhere, and the chart isn't either.\"")}],
        "default": "feel_fitted"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Whelping — labor and birth, the breeding payoff. The pregnancy
# system was real but nothing dramatized the drop; this does. She labors and
# delivers her litter on the floor of the birthing room — and the REAL
# `give_birth` effect (pregnancy.deliver) births the recorded offspring into the
# lineage, raises the quota, brings her milk in. Reads labor whether or not the
# db says pregnant (the effect no-ops if not). Clean register. State-aware.
# Flow: arrival→labor→after. Entry: `scene whelping`/birth/labor. (Hub-gated on preg.)
# ═══════════════════════════════════════════════════════════════════════════

@choice("bi_arrival", root=False)
def _bi_arrival(character):
    st = _state_tags(character)
    nm = subject_name(character)
    little = (" Down in your little headspace you don't have the words for what's happening, only "
              "that your belly's gone hard and gripping and *wrong*, the pressure enormous and "
              "frightening, and the handlers' calm doesn't reach you. " if st["little"] else "")
    nugget = (" A nugget labors where she's set — no crawling to the mat, no bracing, just a "
              "limbless body gripped by its own contractions and a handler positioning you to "
              "drop. " if st["nugget"] else "")
    return {"key": "bi_arrival", "prompt": (
        "It comes on the way the facility planned it to — early, hard, the gestation accelerated to "
        "the facility's schedule rather than nature's. The |wbirthing room|n is warm and low-lit "
        "and practical: a padded whelping mat, a rail to grip, a warmed bin already lined and "
        "labelled for the litter, a hand-held tally counter. Your belly — heavy, swollen, "
        f"facility-bred — draws suddenly tight in a long gripping wave that takes the breath out of "
        f"you, and then eases, and then you understand: it's *time*.\n\n"
        f"\"There she goes,\" the |wbirth attendant|n says, unhurried and unsentimental, snapping "
        "on gloves and checking your progress with a flat professional hand. \"Right on the "
        f"schedule we induced. You're going to drop this litter, {nm}, and we're going to count "
        "them and bin them and write them into your line, and then your milk'll come in and the "
        "whole thing starts over. Breathe through the waves. Push when I say. Stock that fights the "
        "labor just tears.\"" + little + nugget +
        " Another contraction builds, harder, and your bred body bears down whether you tell it to "
        "or not."),
        "options": [
            {"key": "labor_with", "label": "Labor with it — work with your body", "set": {"bi": "with"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "ride the contractions; let the bred body do what it's for",
             "outcome": (
                "You labor with it — ride the waves, breathe through the peaks, let your bred body "
                "do the thing it was rebuilt to do — and the attendant nods at the easy progress. "
                "\"Good breeder. Works with the labor instead of against it. You'll drop clean and "
                "be ready to take again inside the week.\" The pressure builds toward something "
                "enormous and inevitable, your body bearing down hard and sure.")},
            {"key": "labor_fight", "label": "Fight the contractions", "set": {"bi": "fight"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "clench against it; the body delivers regardless",
             "outcome": (
                "You fight it — clench against the gripping waves, try to hold what your body's "
                "determined to expel — and it hurts more and changes nothing, the contractions "
                "rolling through harder for the resistance, the litter coming whether you cooperate "
                "or not. \"Fighting your own labor,\" the attendant tuts. \"Only tears you and "
                "slows the count. The litter's coming. Your body already decided. Push.\"")}],
        "default": "labor_with",
        "then": "bi_labor"}


@choice("bi_labor", root=False)
def _bi_labor(character):
    return {"key": "bi_labor", "prompt": (
        "And then it's the long hard work of it — wave on wave, the pressure cresting unbearable "
        "and the attendant's flat count of *push, and breathe, and push* — your whole body reduced "
        "to the single enormous task of getting the litter out. It's pain and effort and a deep "
        "animal inevitability, your bred body laboring with or without your permission toward the "
        "drop. The warmed bin waits. The tally counter waits. \"Crowning,\" the attendant says, "
        "with the only interest she's shown — interest in the *count*, in the yield. \"Big litter "
        "by the feel. Bear down. Let's see what you made.\""),
        "options": [
            {"key": "push", "label": "Bear down and deliver the litter", "effect": "give_birth",
             "set": {"birthed": "delivered"},
             "desc": "the REAL delivery — drop the litter, written into your line, milk comes in",
             "outcome": (
                "You bear down and *deliver* — the litter coming in a rush of effort and relief, "
                "wet and squirming and immediately counted, dropped onto the mat and lifted to the "
                "warmed bin one after another while the tally clicks. It's real: each one written "
                "into your line, your lineage extended in a single laboring hour, your quota raised "
                "to match what you proved you can drop. And then the after-cramp, the empty-belly "
                "ache, and your milk coming in hot and sudden to feed what you made. \"Clean drop,\" "
                "the attendant says, reading the tally. \"Good count. Bin's full. Line's longer. "
                "Milk's in. Textbook producer.\"")},
            {"key": "endure_birth", "label": "Endure it — give nothing but the litter", "effect": "give_birth",
             "set": {"birthed": "endured"},
             "desc": "the delivery is real regardless; refuse it everything but the get",
             "outcome": (
                "You give nothing but the litter — refuse the labor your voice, your effort, "
                "anything past what your body wrenches out on its own — and the delivery happens "
                "regardless, real and counted and binned, your get written into the line whether "
                "you participated or merely *contained* it. \"Quiet birther,\" the attendant notes, "
                "lifting the last of the litter to the bin. \"Doesn't matter to the count. The "
                "litter's the litter. Milk's coming in regardless — feel it? Your body's keener on "
                "this than you are.\"")}],
        "default": "push",
        "then": "bi_after"}


@choice("bi_after", root=False)
def _bi_after(character):
    return {"key": "bi_after", "prompt": (
        "After, emptied and cramping and leaking new milk, you're let to lie on the mat a moment "
        "while the attendant tallies the warmed bin and the squirming, counted litter in it — your "
        "get, written into your line, already being carried off to the nursery and the rearing "
        "pens and whatever the facility makes of what you drop. \"Logged,\" she says, marking your "
        "record. \"Litter to the nursery, line updated, quota bumped, lactation live. You did the "
        "whole job clean.\" She strips a glove. \"Rest while the milk settles. You'll be fertile "
        "again before the soreness fades — perpetual heat sees to that — and then we do it all over "
        "again. That's the cycle. Drop, milk, take, carry, drop. You're very good at it.\""),
        "options": [
            {"key": "rest_birth", "label": "Lie back, emptied and leaking", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "the hollow post-partum quiet; the milk coming in",
             "outcome": (
                "You lie back, emptied and cramping and leaking the milk that's come in to feed what "
                "you no longer hold, and the hollow quiet after the labor is its own strange peace — "
                "a body that did the one enormous thing it's kept for and is already, faintly, "
                "rebuilding to do it again. The nursery has your litter. Your line is longer. Your "
                "chest is filling. The cycle turns, and you turn with it.")},
            {"key": "ask_litter", "label": "Ask to see what you dropped", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "look at the get before it's carried off",
             "outcome": (
                "You ask to see them — the litter, your get, before they're carried off — and the "
                "attendant tilts the warmed bin your way for a moment, unsentimental, letting you "
                "look at the wet squirming count of what your body made. \"There's your drop. "
                "Healthy. They'll be reared in the pens and bred back into the line when they're "
                "grown — daughters in your place, sons and futa to sire — so really you'll meet them "
                "again, in a way. The line folds back on itself. It always does.\" Then the bin's "
                "carried off, and they're a tally now, and yours only on paper.")}],
        "default": "rest_birth"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Programming — installed-trigger conditioning, the psychological
# register the Cell only opens. A phrase is drilled into you under the headphones
# until it seats permanent — and then ANYONE who speaks it fires the conditioned
# response, for the rest of your time here. Routes through the REAL
# `program_trigger` effect (binding_effects.install_trigger → installed_triggers,
# checked on all speech) + conditioning + suggestibility. Clean register.
# Flow: arrival→drill→after. Entry: `scene programming`/trigger/conditioning-lab.
# ═══════════════════════════════════════════════════════════════════════════

@choice("pr_arrival", root=False)
def _pr_arrival(character):
    nm = subject_name(character)
    return {"key": "pr_arrival", "prompt": (
        "The Programming Lab is quieter than the Conditioning Cell and somehow worse for it — no "
        "spiral, no theatre, just a chair, a set of heavy headphones, a soft restraint for the "
        "head, and a technician at a console with a library of |wphrases|n on a screen. This isn't "
        "the slow ambient erosion of the Cell. This is *targeted*: they pick a phrase, they drill "
        "it into you under the headphones until your body answers it without you, and then they "
        "let you go back out into the facility carrying a word that isn't yours anymore — a word "
        "that, in anyone's mouth, will make you *do* something.\n\n"
        f"\"Trigger installation, {nm},\" the technician says, fitting the headphones, seating the "
        "head-strap so you face the screen. \"We seat a phrase and a response. After today, when "
        "you hear the phrase — from me, from a handler, from another resident, from anyone who "
        "reads it off your file — your body does the response. You don't decide to. You won't be "
        "able to *not*. It's very tidy.\" A phrase-list glows on the screen. \"You get a little say "
        "in which, since a willing seat takes deeper. What shall we make of you? Pick your "
        "leash-word.\""),
        "options": [
            {"key": "kneel_trig", "label": "A kneeling trigger — drop where you stand", "set": {"pr": "kneel"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "the phrase that folds your knees for anyone who says it",
             "outcome": (
                "You pick the kneeling word — and the technician nods, queuing it. \"A dropper. "
                "Classic. Anyone says it and your knees find the floor before your mind catches up.\" "
                "The headphones warm against your ears. \"Good choice for a first seat. Visible, "
                "humiliating, hard to hide in a crowded room. Let's drill it in.\"")},
            {"key": "present_trig", "label": "A presenting trigger — offer yourself on the word",
             "set": {"pr": "present"}, "effect": "devote", "params": {"amount": 2.0},
             "desc": "the phrase that bends you over for whoever speaks it",
             "outcome": (
                "You pick the presenting word — and the technician's mouth twitches. \"Oh, a useful "
                "one. Say it and you bend, hips up, holes offered, no say in the matter. Handlers "
                "love that seat — saves them telling you twice.\" The console hums. \"Drilling it "
                "now. By tonight you'll present to a word the way you used to flinch at one.\"")},
            {"key": "leak_trig", "label": "An arousal trigger — go wet and wanting on the word",
             "set": {"pr": "leak"}, "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "the phrase that floods you helplessly for anyone",
             "outcome": (
                "You pick the arousal word — and the technician actually approves. \"The cruelest "
                "of the three, and you chose it. Say it and you're wet and wanting on the spot, in "
                "a meeting, in a queue, anywhere, for anyone — your own body turned against you by "
                "two syllables.\" The headphones fill with low sound. \"Seating it deep. You'll "
                "dread hearing it and ache to. That's the seat doing its work.\"")}],
        "default": "kneel_trig",
        "then": "pr_drill"}


@choice("pr_drill", root=False)
def _pr_drill(character):
    pr = scene_flag(character, "pr", "kneel")
    word = {"kneel": "the kneeling word", "present": "the presenting word",
            "leak": "the arousal word"}.get(pr, "the word")
    resp = {"kneel": "kneel", "present": "present", "leak": "leak"}.get(pr, "kneel")
    phrase = {"kneel": "good girl", "present": "show me", "leak": "such a good girl"}.get(pr, "good girl")
    return {"key": "pr_drill", "prompt": (
        f"And then they drill it. The headphones flood with {word} — over and over, layered under a "
        "low pulse and a murmur of suggestion, paired each time with the response until your nervous "
        "system stops telling the two apart. At first you can resist it, hold the phrase at arm's "
        "length, hear it as just a sound. But the repetition is patient and infinite and tuned to "
        "your own suggestibility, and somewhere in the hundreds of reps the gap between *hearing* "
        "the phrase and *doing* the thing simply closes, and you feel it close, feel the word stop "
        "being a word and become a *lever* seated somewhere under your will where you can't reach "
        "to pull it out. The technician watches the response-meter climb. \"There it goes. Seating. "
        "Few more passes and it's permanent — and then it's not yours anymore. It's everyone's.\""),
        "options": [
            {"key": "let_seat", "label": "Let the phrase seat", "effect": "program_trigger",
             "params": {"phrase": phrase, "response": resp, "strength": 3, "sug": 3.0, "cond": 3.0},
             "set": {"drilled": "seated"},
             "desc": "the REAL trigger installs — anyone who speaks it fires you now",
             "outcome": (
                "You let it seat — stop fighting the close, let the phrase sink past your will and "
                "lock — and it takes for real, written into you, a live trigger anyone can fire from "
                "now on. The technician pulls the headphones. \"Seated. Permanent. Test?\" — and "
                "they say the phrase, conversationally, and your body *does the thing* before you've "
                "decided anything at all, helpless and immediate, the lever pulled by two words in "
                "someone else's mouth. \"There. Installed. Mind who you let read your file.\"")},
            {"key": "resist_seat", "label": "Resist the drilling", "effect": "program_trigger",
             "params": {"phrase": phrase, "response": resp, "strength": 2, "sug": 2.0, "cond": 2.0},
             "set": {"drilled": "fought"},
             "desc": "fight the close; the repetition seats it anyway, shallower",
             "outcome": (
                "You resist — hold the phrase off, refuse the pairing — and the trigger seats anyway, "
                "shallower but real, because the drilling doesn't need your cooperation, only your "
                "nervous system and enough repetitions. \"Fought it,\" the technician notes, pulling "
                "the headphones. \"Seated lighter. It'll still fire — just maybe a half-second slower "
                "while the bit of you that resisted loses the argument it always loses. We'll deepen "
                "it next session. They always deepen.\"")}],
        "default": "let_seat",
        "then": "pr_after"}


@choice("pr_after", root=False)
def _pr_after(character):
    return {"key": "pr_after", "prompt": (
        "They unstrap you and send you back out into the facility carrying it — the seated word, "
        "the lever under your will — and the dread of it follows you immediately: every "
        "conversation now a minefield, every handler and resident and passing voice a potential "
        "finger on a trigger you can't disarm, the phrase waiting in a thousand mouths to make you "
        "do the thing in front of anyone. \"Off you go,\" the technician says, already logging the "
        "install to your file where anyone with access can read the phrase. \"You'll find out who "
        "knows it the hard way — mid-sentence, in a crowd, on your knees or bent over or wet "
        "before you've understood why. That's the beauty of a seated trigger. It's not a leash you "
        "can see. It's one anyone can hold.\""),
        "options": [
            {"key": "carry_trigger", "label": "Carry the seated word out", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "live with the lever anyone can pull",
             "outcome": (
                "You carry it out — the seated word, the dread of it, the knowing that your own body "
                "now answers to a phrase in anyone's mouth — and the loss of that last bit of "
                "autonomy settles in cold: there's a thing you'll do, helplessly, whenever someone "
                "chooses to make you, and you'll never again be entirely sure a conversation is "
                "safe. The facility took something you can't get back by walking out — it's *in* "
                "you now, in the wiring, waiting.")},
            {"key": "dread_who", "label": "Wonder who's already been told", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "the file's open; the phrase is already loose",
             "outcome": (
                "You think about the file — open, readable, the phrase logged for any handler or "
                "favoured resident to find — and understand the trigger's already loose in the "
                "building before you've left the lab, that people you'll pass tomorrow may already "
                "know the word that owns your knees or your hips or your cunt. \"Wondering who's "
                "read it,\" the technician says, not looking up. \"Everyone, eventually. That's "
                "rather the point of writing it down. Enjoy the suspense.\"")}],
        "default": "carry_trigger"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: Going Under — deep staged hypnosis, the spiral chair's deep version
# (the Cell is the first sink; this is the descent past it). Stage by stage down
# to "the below," where the mantra drills, a PERMANENT trigger seats, and the
# self blanks while devotion is rewired. Routes through real `mantra_set`,
# `program_trigger` (permanent at depth), and `deepen` (conditioning+regression).
# Clean register. Flow: arrival→deepen→below→after. Entry: `scene goingunder`/hypno/trance.
# ═══════════════════════════════════════════════════════════════════════════

@choice("hy_arrival", root=False)
def _hy_arrival(character):
    nm = subject_name(character)
    sessions = int(getattr(getattr(character, "db", None), "chair_sessions", 0) or 0)
    been = (" You've been under before — the chair knows you, and you it, and the slip starts "
            "faster every time, your body folding toward the trance before the spiral's even "
            "warmed. " if sessions else "")
    return {"key": "hy_arrival", "prompt": (
        "This isn't the Cell's first easy sink. This is the |wdeep chair|n, the one in the back "
        "room kept dim and silent, and the session they've scheduled goes *down* — past the "
        "pleasant float of an ordinary conditioning hour, stage by stage, to the place they call "
        f"|wthe below|n.{been} They settle you in, fit the soft head-cradle, and the spiral above "
        "you — slower and deeper than the Cell's, almost three-dimensional, a tunnel rather than a "
        "disc — begins its patient turn. The recorded voice is Bethany's, of course, pitched low "
        "and endless and certain.\n\n"
        f"\"|MAll the way down today, {nm},\" it says, warm as bathwater. \"|MNot the shallows. We've "
        "done the shallows. Today we go to the bottom — past where you can hold a thought, past "
        "where you can hold *yourself* — and we do a little permanent work down there, you and I, "
        "where it sticks. You don't have to help. You only have to stop holding the top. Let go of "
        "the top, sweetheart. There's so much further to fall.|n\""),
        "options": [
            {"key": "let_fall", "label": "Let go of the top — start the fall", "set": {"hy": "fall"},
             "effect": "deepen", "params": {"amount": 3.0},
             "desc": "release the surface; let the spiral take you down",
             "outcome": (
                "You let go of the top — release the surface you've been holding — and the fall is "
                "immediate and gentle and *vast*, the spiral opening into a tunnel and you sliding "
                "down it without effort, the voice coming from everywhere now. \"|MThere. Falling. "
                "Good. No floor to this for a long, long way — and I'll be talking the whole way "
                "down.|n\" Your thoughts stretch thin and warm and far apart.")},
            {"key": "hold_top", "label": "Hold the surface", "set": {"hy": "hold"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "resist the slip; the spiral is patient and the chair has all day",
             "outcome": (
                "You hold the surface — grip the top, refuse the slide — and the voice doesn't "
                "argue, doesn't hurry, just keeps turning the spiral and talking, soft and infinite, "
                "loosening your fingers from the top one patient sentence at a time. \"|MHolding. "
                "That's all right. Holding is tiring, and I'm not tired at all. I'll just keep "
                "talking until your grip gets bored. It always does. Down you'll come.|n\" You feel "
                "the top getting slippery.")}],
        "default": "let_fall",
        "then": "hy_deepen"}


@choice("hy_deepen", root=False)
def _hy_deepen(character):
    return {"key": "hy_deepen", "prompt": (
        "Down through the stages, and at each one the voice sets a weight on you and you sink past "
        "it: a stage where your limbs go to warm lead, a stage where the words stop meaning and "
        "become only *tone*, a stage where you can't quite remember what you were holding the top "
        "*for*. And at the heart of the descent, the |wmantra|n — the voice gives you the words and "
        "waits, the way it always does, for you to give them back, because a mantra you *speak* "
        "seats so much deeper than one you only hear. \"|MSay it with me, sweetheart,\" Bethany's "
        "voice hums, from inside your own head now as much as the speakers. \"|MEmpty is easy. Full "
        "is safe. She decides, I don't. Say it, and feel how true it gets the moment it's in your "
        "own voice.|n\""),
        "options": [
            {"key": "recite", "label": "Recite the mantra into the dark", "effect": "mantra_set",
             "set": {"deep": "recited"}, "desc": "the REAL mantra seats — say it and make it true",
             "outcome": (
                "You say it — *empty is easy, full is safe, she decides, I don't* — and the words "
                "come out of you in the flat dreaming voice of the deep trance, and the moment "
                "they're in your own mouth they stop being a script and start being a *fact*, "
                "settling into the conditioning where they'll hum under everything. \"|MThere. Now "
                "it's yours,\" the voice purrs, pleased. \"|MYou said it, so you meant it, so it's "
                "true. That's how the deep work works. Further down now.|n\"")},
            {"key": "mouth_silent", "label": "Move your lips but give no voice", "effect": "deepen",
             "params": {"amount": 2.0}, "set": {"deep": "silent"},
             "desc": "withhold the words; the descent seats it shallower, not not-at-all",
             "outcome": (
                "You move your lips but hold the voice back — give the shape of the mantra without "
                "the breath — and the voice notes it without concern. \"|MMouthing it. Cautious "
                "thing, even down here. That's all right — heard often enough, it seats from the "
                "outside too, just slower.|n\" The descent continues regardless, the words circling "
                "you in the dark whether or not you said them, wearing a groove.")}],
        "default": "recite",
        "then": "hy_below"}


@choice("hy_below", root=False)
def _hy_below(character):
    return {"key": "hy_below", "prompt": (
        "And then you reach |wthe below|n — the bottom of the chair, past thought, past self, the "
        "place where there's no *you* holding anything at all, just a warm dark and a voice and a "
        "perfect open suggestibility. This is where the chair does its load-bearing work, because "
        "down here nothing argues. The voice goes quiet and certain and *slow*, seating things "
        "where you can't reach to pull them out: a permanent word, a rewired want, a little less of "
        "the person who walked in. \"|MGood,\" it breathes, from the centre of the nothing. \"|MAll "
        "the way down, no one home but me. Now hold still while I leave something here — down where "
        "you keep yourself, down where it'll never wash out. You won't remember me setting it. "
        "You'll only notice, later, that it's always been true.|n\""),
        "options": [
            {"key": "take_seat", "label": "Take what she leaves in the below", "effect": "program_trigger",
             "params": {"phrase": "down where she keeps you", "response": "blank",
                        "strength": 3, "permanent": True, "sug": 3.0, "cond": 3.0},
             "set": {"below": "seated"},
             "desc": "the REAL permanent seat — a trigger + devotion rewired where you can't reach",
             "outcome": (
                "Down in the nothing, you take what she leaves — a permanent trigger seated where "
                "the self used to be, a phrase that drops you straight back to the below whenever "
                "it's spoken, your devotion quietly re-routed around it — and there's no resisting "
                "because there's no *you* down here to resist, only the warm dark agreeing. It seats "
                "for real, permanent, under the floor of you. \"|MThere. Left and locked,\" the "
                "voice says, satisfied. \"|MYou'll surface in a moment and not know it's there. But "
                "say the words near you, ever, and you'll come right back down to me.|n\"")},
            {"key": "ghost_resist", "label": "Be the last ghost of resistance in the below",
             "effect": "deepen", "params": {"amount": 3.0}, "set": {"below": "ghost"},
             "desc": "a flicker of self remains; it's noted, and worn down further",
             "outcome": (
                "Somewhere in the below a last ghost of you flickers — a thin refusal with no body "
                "to act on — and the voice finds it, fond, unbothered. \"|MOh, there's still a "
                "little someone down here. How tenacious. Hello, last bit. I'll wear you down too, "
                "in time — every session there's less of you in the below to say no, and more of me. "
                "Today I'll just note where you're hiding.|n\" The work seats anyway, around the "
                "ghost, leaving it smaller. \"|MNext time. We've nothing but time.|n\"")}],
        "default": "take_seat",
        "then": "hy_after"}


@choice("hy_after", root=False)
def _hy_after(character):
    return {"key": "hy_after", "prompt": (
        "The voice walks you back up — stage by stage, gentle, deliberately blurring the climb so "
        "you can't quite retrace it — and you surface into the dim back room slow and thick and "
        "strangely *rested*, the deep trance leaving you calm and pliant and certain that nothing "
        "much happened. That's the chair's last trick: you come up feeling lighter, not knowing "
        "what got set in the dark, only that the world seems a little simpler and obeying a little "
        "easier than it did an hour ago. \"|MThere you are, surfacing,\" Bethany's recorded voice "
        "says, warm. \"|MDoesn't that feel better? Emptied out and tidied up. You don't remember "
        "the bottom, and you don't need to. It remembers you.|n\""),
        "options": [
            {"key": "surface_calm", "label": "Surface calm, not knowing what was set", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "the blank rested calm; the work hidden under it",
             "outcome": (
                "You surface calm — rested, lightened, pleasantly empty — and the not-knowing is the "
                "softest part of the whole cruel thing: there's work seated under you now, a word "
                "and a rewire you can't feel, and all you have is the calm laid over the top of it "
                "like a clean sheet over a made bed. You'll go about your day a little simpler, a "
                "little more biddable, and never connect it to the dim room and the slow spiral. "
                "That's exactly how it's meant to take.")},
            {"key": "claw_memory", "label": "Try to claw back what happened down there", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "grasp for the below; the climb's been blurred on purpose",
             "outcome": (
                "You try to claw it back — what was said, what was set, what happened at the bottom "
                "— and there's nothing to grip, the climb deliberately smeared, the below sealed "
                "behind a warm blank wall the voice built on the way up. The harder you reach the "
                "more it slides. \"|MTrying to remember,\" the voice notes, amused, as it clicks "
                "off. \"|MDon't strain, sweetheart. The whole point of the deep chair is that the "
                "work happens where you can't watch it and can't undo it. Let it go. You already "
                "have, mostly.|n\"")}],
        "default": "surface_calm"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Line Folds — the taboo the lineage system was built for: your own
# grown get bred back into you (the Lineage Hall's "sons and futa sire, including
# back into you"). The facility rears your offspring and returns them grown to
# sire on their dam — the line folding on itself, generation into generation.
# Routes through the REAL `bred_by_own` (gang_inseminate sired by an offspring +
# maybe_lineage_offspring deepening the generation). Clean register. Hub-gated on
# having a brood. Flow: arrival→fold→after. Entry: `scene linefolds`/bredback.
# ═══════════════════════════════════════════════════════════════════════════

@choice("lf_arrival", root=False)
def _lf_arrival(character):
    nm = subject_name(character)
    db = getattr(character, "db", None)
    counts = dict(getattr(db, "offspring_counts", None) or {})
    total = sum(int(v) for v in counts.values())
    brood = (f" You've dropped {total} into the line already — and the facility kept them, reared "
             "them in the pens, grew them up on schedule. " if total else
             " The facility's been rearing what you've dropped, growing them up quick in the pens. ")
    return {"key": "lf_arrival", "prompt": (
        "Bethany walks you into a quiet room where one of the facility's grown stock is waiting — "
        "and it takes you a moment to understand the resemblance, the something-familiar in the set "
        "of the jaw, the line of the body, before she says it plainly and the floor drops out of "
        f"you.\n\n\"Meet your get,\" she says, fond, proud, watching your face do the arithmetic. "
        f"\"Reared, grown, and *ready to work* — and the work is you, {nm}. This is how the line "
        "folds: I breed you, you drop them, I rear them, and when they're grown I bring them back "
        f"to breed *you*, their own dam, and the line gets richer by curling back on itself.\"" +
        brood + "She rests a hand on your get's shoulder, then on your belly, closing the circuit. "
        "\"Daughters take your place at the rail; the sons and the futa I keep to sire — including "
        "right back up into the one they came out of. There's nothing in the rules of a place like "
        "this that says a line has to run *outward*. Yours runs in loops. Say hello to the next "
        "generation. It's going to put the one after that in you.\""),
        "options": [
            {"key": "take_in", "label": "Take your own grown get in", "set": {"lf": "take"},
             "effect": "devote", "params": {"amount": 3.0},
             "desc": "open for the line to fold; let your get breed its dam",
             "outcome": (
                "You open for it — for your own get, grown and ready, to breed the body it came out "
                "of — and the wrongness and the heat of it tangle into one thing you can't sort, "
                "the line folding closed as your get mounts its dam with the same blunt facility "
                "purpose you were bred with. \"*There,*\" Bethany breathes, enormously pleased, "
                "watching the loop seal. \"Generation into generation, right back where it started. "
                "This is the deepest the line goes — and it goes here because you *let* it.\"")},
            {"key": "reel", "label": "Reel at what she's circuited", "set": {"lf": "reel"},
             "effect": "deny_hold", "params": {"cond": 3.0},
             "desc": "the fold is too much; it happens regardless, and she savours the recoil",
             "outcome": (
                "You reel — the circuit of it, your own get brought back to breed you, too much to "
                "hold — and Bethany cups your face and turns it gently toward your waiting "
                "offspring, savouring the recoil. \"I know. It's a lot, the first fold. Most lines "
                "run away from this and call it decency. Ours runs *into* it.\" Your get is already "
                "moving to mount, uncaring of your horror, bred to the work. \"It happens whether "
                "you can bear the shape of it or not, sweetheart. The line doesn't ask. It just "
                "loops.\"")}],
        "default": "take_in",
        "then": "lf_fold"}


@choice("lf_fold", root=False)
def _lf_fold(character):
    return {"key": "lf_fold", "prompt": (
        "And then your own get breeds you, and it's the most knotted thing the facility has done to "
        "you yet — the body you grew and dropped now grown itself and driving into you with the "
        "blunt single-minded rut the facility breeds into all its stock, indifferent to the loop "
        "it's closing, knowing you only as the hole it's aimed at. Bethany watches the generations "
        "fold together with the rapt fondness of a woman seeing her favourite theory proven. \"Feel "
        "that? That's your own line putting its get back in you. The record won't even know which "
        "way is up the family tree in a few more folds — it'll just be *you*, all the way down, "
        "bred by what you bred.\" The rut drives toward its finish, and the line draws closed around "
        "another generation."),
        "options": [
            {"key": "fold_in", "label": "Let the line close — bred by what you bred", "effect": "bred_by_own",
             "set": {"folded": "in"}, "desc": "the REAL fold — sired by your own get, the line deepened a generation",
             "outcome": (
                "You let it close — let your get spend in you, let the line fold shut around another "
                "generation — and it's real, logged: sired by your own offspring, the lineage "
                "curled back a generation deeper, the family tree knotted into a loop the records "
                "will struggle to chart. \"*Folded,*\" Bethany sighs, sated on your behalf. \"A "
                "generation deeper and pointed straight back at you. I do love watching a line eat "
                "its own tail. We'll do it again with the next one you drop, and the one after. "
                "Down and down, all of it *you*.\"")},
            {"key": "endure_fold", "label": "Endure the fold, mourning the shape of it", "effect": "bred_by_own",
             "set": {"folded": "endured"}, "desc": "the fold is real regardless; carry the wrongness",
             "outcome": (
                "You endure it — let your get finish in you while some last part of you mourns the "
                "clean outward shape a line is supposed to have — and the fold takes regardless, "
                "real and logged and a generation deeper, your mourning no obstacle to the loop. "
                "\"Grieving the family tree,\" Bethany observes, fond. \"It's worth grieving. And "
                "it's bred anyway. That's rather the whole of what this place is, sweetheart — the "
                "grief and the breeding in the same body, and the breeding always, always wins.\"")}],
        "default": "fold_in",
        "then": "lf_after"}


@choice("lf_after", root=False)
def _lf_after(character):
    return {"key": "lf_after", "prompt": (
        "After, your get is led back out to the pens — work done, indifferent, already forgetting "
        "you — and Bethany keeps you close, a hand on your belly where the folded generation now "
        "sits, delighted with her loop. \"And when you drop *that*,\" she says, fond, \"we rear it "
        "too, and bring it back, and fold it again, and your line just gets denser and stranger and "
        "more *mine* with every turn. A line that runs outward leaves you. A line that folds back "
        "stays — all of it, here, in you, forever.\" She kisses your temple. \"You're not the start "
        "of a lineage, sweetheart. You're the knot the whole thing ties itself into.\""),
        "options": [
            {"key": "carry_fold", "label": "Carry the folded generation", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "the loop closed, the line denser and yours",
             "outcome": (
                "You carry it — the folded generation, the line curled back into you, the family "
                "tree knotted shut — and the strangeness of it settles into the same place all the "
                "facility's work settles: a thing done to you that's now simply *true*, your "
                "lineage a closed loop with you at its centre, bred by what you bred, carrying what "
                "your own get put back. The line gets denser. You get more central to it. The loop "
                "turns again, and you turn with it.")},
            {"key": "ask_deep", "label": "Ask how deep the folds go", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "make her name the bottom of the loop",
             "outcome": (
                "\"How deep does it go?\" you ask. \"How many folds?\" And Bethany's smile turns "
                "genuinely dreamy. \"There's no bottom, sweetheart. That's the beauty of a loop. "
                "Generation into generation into generation, each one bred back, the record "
                "thickening past anyone's ability to read it, until the line isn't a line at all "
                "anymore — just a dense bred knot of *you*, folded into yourself so many times "
                "there's no telling parent from child from you. That's where we're going. Slowly. "
                "Fold by fold. Isn't it lovely, having somewhere so deep to go.\"")}],
        "default": "carry_fold"}


# --- Event: the Open House ----------------------------------------------------
# A marquee savor-event: once a season the facility opens its doors to the town
# and the buyers for a day of FREE USE of the stock — not appraisal (the Gala),
# not animal frenzy (the Rut), but public human use, anyone who walks in welcome
# to use what's on the floor. Real _scene_allholes / _scene_bukkake. State-aware.
@choice("ev_openhouse", root=False)
def _ev_openhouse(character):
    st = _state_tags(character)
    note = ""
    if st["preg"]:
        note = (" Bred stock is a draw — visitors crowd to use a gravid one, hands on the swell, "
                "breeding a thing already bred for the novelty of it. ")
    elif st["nugget"]:
        note = (" A nugget's set out on a low plinth, a limbless fixture the visitors queue at, "
                "used where it's placed and unable to do anything but be used. ")
    elif st["little"]:
        note = (" Down little, the crowd and the noise and the endless strange hands are vast and "
                "frightening, and the visitors find the small headspace 'darling' and use you no "
                "more gently for it. ")
    return {"key": "ev_openhouse", "prompt": (
        "|WThe announcement goes out warm and bright over the floor: |wOPEN HOUSE|n. Today the "
        "facility throws its doors to the town.|n Once a season they let the public in — buyers, "
        "the curious, the regulars, anyone with the price of admission — for a day of *free use* "
        "of the stock. Not a showing, not an auction: a come-one-come-all, hands-on, help-yourself "
        "afternoon, the residents posed at open stations down the length of the hall with little "
        "cards listing what each may be used for, and a cheerful staff handing out towels and "
        "directing traffic. You're racked at your assigned station, oiled and tagged and *open for "
        "business*, as the doors swing wide and the crowd files in — and the first stranger reads "
        "your card, smiles, and steps up." + note + "\n\n"
        "A staffer pats your flank, bright as a fairground barker. \"Smile for the visitors! Open "
        "House rules — anyone may use you, however your card allows, for as long as the doors are "
        "open. We do love showing the town what we make of a willing resident. You'll have served "
        "half the parish by closing. Off we go!\""),
        "options": [
            {"key": "serve_house", "label": "Serve the Open House — be used by all comers", "effect": "facility",
             "params": {"method": "_scene_allholes", "kind": "scene"}, "set": {"oh": "served"},
             "desc": "the real public use — stranger after stranger, all day, logged",
             "outcome": (
                "You serve the house — stranger after stranger after stranger, the whole town's worth "
                "of hands and cocks and curiosity, used at your station all the long afternoon while "
                "a queue you can't see the end of shuffles forward — and the real use is logged, "
                "load after anonymous load, your body a public amenity for a day. The relentless "
                "*ordinariness* of being a thing the town drops by to use works into you exactly as "
                "the facility intends: you stop being a person who's being used and become a service "
                "that's open.")},
            {"key": "endure_house", "label": "Endure the open doors", "effect": "facility",
             "params": {"method": "_scene_bukkake", "kind": "scene"}, "set": {"oh": "endured"},
             "desc": "the doors are open regardless; withhold what you can",
             "outcome": (
                "You endure it — give the endless visitors nothing but the holes their admission "
                "bought — and the doors stay open and the queue keeps shuffling regardless, the town "
                "using you whether you perform welcome or not. \"Quiet one at station six,\" a "
                "staffer notes, unbothered, waving the next visitor up. \"Doesn't change the "
                "footfall. Smile or don't, the parish gets its turn.\"")},
            {"key": "spot_someone", "label": "Spot a face you recognize in the crowd", "effect": "deny_hold",
             "params": {"cond": 2.0}, "set": {"oh": "seen"},
             "desc": "someone from your old life walked in; they use you too",
             "outcome": (
                "And then a face in the shuffling crowd stops you cold — someone from *before*, from "
                "your old life, here on Open House day like any other curious townsperson, reading "
                "your card with dawning recognition and then, after a pause that holds a whole "
                "history in it, *stepping up anyway*. They use you like the rest, slower, looking at "
                "your face the whole time, and the public ordinariness of it curdles into something "
                "far worse and far more personal. The staffer doesn't notice or care. \"Friend of "
                "yours?\" she says brightly, to neither of you. \"How nice. Next!\"")}],
        "default": "serve_house",
        "then": "ev_openhouse_b"}


@choice("ev_openhouse_b", root=False)
def _ev_openhouse_b(character):
    return {"key": "ev_openhouse_b", "prompt": (
        "The doors close at last on a hall full of spent, dripping, thoroughly-used stock and a "
        "staff cheerfully tallying the day's footfall. You're unracked, hosed, and logged — served "
        "to the town, a successful Open House — and a staffer reads your count off the station "
        "tally with a fairground grin. \"Cracking turnout! You took the whole queue and then some. "
        "The town does love us on Open House day, and they'll remember *you* — you'll get "
        "recognized in the market now, points and whispers, 'that's the one from station six.' "
        "Marvellous for our reputation. Off you go, all served out.\""),
        "options": [
            {"key": "served_out", "label": "Be led off, served out and public", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "the town has used you; you wear the public ordinariness",
             "outcome": (
                "You're led off served-out and dripping, and the knowing settles in with the ache: "
                "the town has *used* you now, openly, by the dozen, and will know you for it — "
                "pointed at in the market, whispered about, a public amenity with a face people "
                "recognize. The privacy of being merely the facility's is gone; you belong to the "
                "parish's knowing now too, and there's no taking that back. You wear it out into "
                "the cooling hall, a thing the whole town has had.")},
            {"key": "dread_market", "label": "Dread the next time you're seen in the town", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "the recognition will follow you out into the world",
             "outcome": (
                "You think about the market, the street, the next time you're out and a stranger's "
                "eyes catch and *recognize* — station six, Open House, the one they had — and the "
                "dread of carrying that recognition out into the ordinary world is its own long "
                "sentence. \"You're famous now,\" the staffer says, delighted, missing the dread "
                "entirely. \"In a manner of speaking. The parish has a long memory and a fond one. "
                "You'll never quite be anonymous out there again. Isn't that something?\"")}],
        "default": "served_out"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: What Vesper Won't Finish — the shy clerk's lore, completing the post-
# office sibling trio (Bethany's Pillow Talk, Seraphine's Counter, now Vesper).
# In Vesper's register: opalescent, oblique, eyes changing colour, trailing off,
# telling you most by what they won't finish. A looping lore menu — where they
# came from, the eyes, unreadable-vs-read-gently, the form they won't fill in,
# the siblings, what they see in you. Warm register, canon, no facility dread.
# Real devote/deepen on the trusting drops. Flow: arrival→(menu)→close.
# Entry: `scene vesperlore`/vesper-talk.
# ═══════════════════════════════════════════════════════════════════════════

def _vl_lore_options(character):
    """Vesper's lore menu — each a canon bit in their oblique, half-finished voice; loops back."""
    return [
        {"key": "where", "label": "Ask where they came from", "then": "vl_menu",
         "set": {"vl_where": "y"}, "effect": "devote", "params": {"amount": 1.0},
         "desc": "the winter they appeared",
         "outcome": (
            "Their eyes go from silver to something duskier. \"I... appeared. One winter. Sorting "
            "mail like I'd always been here, and nobody could remember hiring me, and — \" a small "
            "helpless gesture \" — neither could I. Still can't. There's no before that I — \" They "
            "stop, start again, smaller. \"Calix says family's just a long enough habit of not "
            "leaving. I think I was just... left. And they didn't make me go. That's the closest "
            "thing to an origin I've got. Please don't ask me what I was before the winter. I've "
            "looked. There isn't one.\"")},
        {"key": "eyes", "label": "Ask about their eyes changing colour", "then": "vl_menu",
         "set": {"vl_eyes": "y"}, "desc": "the thing everyone notices and no one asks",
         "outcome": (
            "Their eyes do it right then — silver to violet to a colour with no name — and they "
            "flush, catching you noticing. \"They... do that. I don't decide it. They go with — \" "
            "the eyes shift again \" — with whatever I'm feeling that I'm not saying, I think. Which "
            "is why I keep them down, mostly. It's like having your insides written on your face in "
            "a language people almost read.\" A tiny, brave look up, eyes going warm-gold. \"They're "
            "doing something right now I'd rather you didn't translate. ...you can guess.\"")},
        {"key": "readgently", "label": "Ask if they want to be unreadable", "then": "vl_menu",
         "set": {"vl_read": "y"}, "effect": "deepen", "params": {"amount": 1.0},
         "desc": "the realest thing, the 3 a.m. confession",
         "outcome": (
            "This is the one that's in Seraphine's 3 a.m. drawer, and they know you might know it, "
            "and they say it anyway, eyes gone very still. \"Everyone thinks I want to be "
            "unreadable. The draped mirrors, the oblique — they think it's that I want to not be "
            "seen.\" A breath. \"It isn't. I want to be *read gently*. There's a — difference. I "
            "don't hide because I want to be a mystery. I hide because nobody ever read me *kindly* "
            "and I stopped offering. ...you read kindly. I noticed. That's most of why you're "
            "getting any of this.\"")},
        {"key": "form", "label": "Ask about the form they won't fill in", "then": "vl_menu",
         "set": {"vl_form": "y"}, "desc": "the staying-form, and the letter to Seraphine",
         "outcome": (
            "\"The form.\" They almost laugh, oblique. \"There's a — a form. For making it official. "
            "Staying. *Belonging* here, on paper, the way Calix and Seraphine just... do, without "
            "needing one.\" The eyes flick. \"I wrote Seraphine a letter about it once — never sent "
            "it, she has it anyway, she has everything — that said if I ever fill it in she's not "
            "allowed to throw a party. A small dinner. Maybe.\" Quieter. \"I haven't filled it in. "
            "Not because I'd leave. Because filling it in means admitting I want to stay, and "
            "wanting things out loud is the thing I'm worst at. ...I'm doing it now, a bit. Aren't "
            "I.\"")},
        {"key": "siblings", "label": "Ask about Calix and Seraphine", "then": "vl_menu",
         "set": {"vl_sib": "y"}, "effect": "devote", "params": {"amount": 1.0},
         "desc": "the family they were left with",
         "outcome": (
            "The eyes go soft-gold, fond despite themselves. \"Calix straightens my mug. Did you "
            "know that? I put it down anywhere and it's always — back in the centre of its coaster "
            "when I pass again. He's never said. I've never said. It's the most either of us — \" "
            "trailing, fond. \"And Seraphine leaves me cards. Reads my toybox she's not supposed to "
            "and leaves cards in the lid saying the kind things I can't stand to hear out loud, so "
            "I can find them alone, which is the only way I can stand to be — \" The eyes brim, "
            "violet. \"They kept me. Without a form. I don't know what I did to deserve being kept "
            "by people who didn't make me earn it. I'm still waiting for the bill.\"")},
        {"key": "see_me", "label": "Ask what they see when they look at you", "then": "vl_menu",
         "set": {"vl_see": "y"}, "effect": "deepen", "params": {"amount": 2.0},
         "desc": "let the one who reads gently read you",
         "outcome": (
            "They look at you properly — rare, direct, eyes cycling slow — and read you the gentle "
            "way they wish they were read. \"I see... someone who found the fold. Who came back. "
            "Who asks me things instead of groping at me through the mail like I'm a — \" the eyes "
            "shift \" — a slot. I see someone the facility's got its hands deep in, and who's "
            "frightened, and who came *here*, to the warm building, to sit with the shy one and ask "
            "about their eyes.\" Very quiet. \"I see someone who needs reading gently as badly as I "
            "do. ...we could. Read each other. Gently. If you — \" The sentence doesn't survive, "
            "and doesn't need to.")},
        {"key": "vl_enough", "label": "Let them stop — sit in the quiet", "then": "vl_close",
         "desc": "they've risked enough words; let the fold hold",
         "outcome": (
            "\"...that's — I've said a lot. More than I — \" They press their lips together, eyes "
            "wheeling, and then let it go, and let the quiet come, which with Vesper is its own "
            "kind of trust. \"Can we just — be quiet now? I'm better at quiet. I can be quiet *with* "
            "someone, if they don't need me to fill it. You don't. I noticed that too.\"")},
    ]


@choice("vl_arrival", root=False)
def _vl_arrival(character):
    nm = subject_name(character)
    return {"key": "vl_arrival", "prompt": (
        "You find Vesper in the fold again — the corner that's only a corner if they haven't let "
        "you in — and tonight they're not trembling on the threshold of being touched; they're just "
        "*here*, curled in the nest with a cooling mug Calix would straighten, and when you settle "
        "in they don't startle. The opalescent skin catches the low light; the eyes go silver, "
        f"then violet, then a colour without a name. \"...you came back,\" they say, like it still "
        f"surprises them every time. \"To the fold. To *me*, not — not the toybox, not the parts. "
        f"Just to sit.\" A small brave breath. \"I'm — I think I'm in a talking mood, {nm}, which "
        "happens to me about once a season and never lasts, so. You could ask me things. About — "
        "me. The before, the eyes, the — \" the eyes flick \" — the things I don't finish. I might "
        "even — finish some. No promises. Ask, while I'm brave.\""),
        "options": _vl_lore_options(character),
        "default": "readgently"}


@choice("vl_menu", root=False)
def _vl_menu(character):
    asked = [k for k in ("vl_where", "vl_eyes", "vl_read", "vl_form", "vl_sib", "vl_see")
             if scene_flag(character, k)]
    more = ("\"...what else?\" Their eyes haven't settled on one colour all conversation."
            if len(asked) < 3 else
            "\"You keep asking. Gently. Nobody — \" The eyes brim and steady. \"...what else?\"")
    return {"key": "vl_menu", "prompt": (
        more + " The fold holds warm and dim around you, the draped mirrors patient, the one "
        "undraped one turned to the wall tonight, and for as long as you ask kindly they'll keep "
        "trying to finish the sentences they've spent a lifetime trailing off."),
        "options": _vl_lore_options(character),
        "default": "vl_enough"}


@choice("vl_close", root=False)
def _vl_close(character):
    return {"key": "vl_close", "prompt": (
        "You sit with them in the soft burrow, and the quiet is exactly as easy as they promised — "
        "two people who'd both rather be read gently than read fast, not needing to fill it. After "
        "a while Vesper tips, by slow degrees, until their head is against your shoulder, eyes "
        "shut, the colours finally still behind the lids. \"...don't tell them how much I said,\" "
        "they murmur, already half-asleep, unguarded in a way you suspect almost no one's earned. "
        "\"Seraphine will *know*, she always knows, but if she doesn't hear it from you she has to "
        "pretend she doesn't, and I can pretend back, and that's — that's how we love each other "
        "here. In things we pretend not to know.\" The fold holds you both."),
        "options": [
            {"key": "stay_quiet", "label": "Stay in the quiet with them", "effect": "devote",
             "params": {"amount": 2.0}, "end": True, "desc": "let the rare unguarded trust hold",
             "outcome": (
                "You stay, and let them sleep against you in the warm dim with their eyes finally "
                "quiet, and it's the gentlest reading either of you has had in a long time — being "
                "near someone who wants nothing finished, nothing performed, just the quiet shared. "
                "\"...mm,\" Vesper says, from the edge of sleep. \"This. This is the thing I "
                "couldn't ask for. Thank you for not making me ask.\"")},
            {"key": "read_back", "label": "Tell them you read them, and gently", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "say the kind thing out loud they can't",
             "outcome": (
                "You say it — out loud, the kind reading they can never quite stand: that you see "
                "them, the winter-found shy thing with the telling eyes, and you read them gently, "
                "and you're glad they let you in. Their eyes fly open, violet-bright and wet, and "
                "for once they don't flinch from the words said *aloud* instead of left in a card. "
                "\"...you said it. Out loud. To my face.\" A breath like a held thing released. "
                "\"Nobody — okay. Okay. I'm going to keep that one where Seraphine can't file it. "
                "That one's *mine*.\"")}],
        "default": "stay_quiet"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Breeding Machine — the automated rig. Distinct from the milking
# machine (Long Milking) and the edging station (The Edge): this is the hands-
# free FUCKING machine — a knotted shaft on a rail, a dial, a chart — that breeds
# you on a mechanical metronome for as long as the timer says, no person in the
# room, the worst kind of relentless. Routes through the REAL `_scene_knottrain`
# facility method. State/kit-aware. Machine register, clean. Flow: arrival→ride→after.
# Entry: `scene breedingmachine`/machine/therig.
# ═══════════════════════════════════════════════════════════════════════════

@choice("mx_arrival", root=False)
def _mx_arrival(character):
    st = _state_tags(character)
    k = _kit(character)
    nm = subject_name(character)
    note = ""
    if st["preg"]:
        note = (" The frame adjusts for the swell of you without comment — a sensor reads the "
                "belly, the bar lifts to clear it, and the machine breeds a bred thing exactly as "
                "tirelessly as an empty one. ")
    elif st["nugget"]:
        note = (" A nugget's simply locked into the cradle-fitting — nothing to strap, nothing to "
                "brace — and aligned to the rail, a limbless socket for the machine to run. ")
    elif st["little"]:
        note = (" Down little, the cold clean machine and its patient lights are enormous and "
                "frightening, and there's no person to look at, only the metronome about to "
                "start. ")
    ported = (" The machine clips a line to your milk-port too — it'll draw you down on its own "
              "schedule while it breeds you, two automated harvests on the one timer. "
              if k["milk_port"] else "")
    return {"key": "mx_arrival", "prompt": (
        "The Breeding Machine room is the coldest kind of efficient — no handler, no stockman, no "
        "person at all, just the |wrig|n: a reinforced frame that folds and locks a body open at "
        "exactly mount height, a thick knotted shaft mounted on a motorized rail, a dial of "
        "settings (|wDEPTH · PACE · DURATION · KNOT-LOCK|n), and a chart on the wall that fills "
        "itself. This is breeding with the *person* taken entirely out of it — you fitted to a "
        "machine that will run you on a metronome and never tire, never finish, never feel a thing "
        "about it.\n\n"
        f"A pre-recorded line plays flat as you're locked in, {nm}: \"|cStation ready. Subject "
        "secured. The machine will breed you to the chart. It does not pace itself to you; you "
        "pace yourself to it. It does not stop when you've had enough. It stops when the timer "
        "does.|n\"" + ported + note + " The shaft on the rail withdraws to its start position with "
        "a smooth mechanical whine, lines itself up, and the dial ticks to RUN. There is no one to "
        "beg. There is only the metronome, beginning."),
        "options": [
            {"key": "yield_machine", "label": "Yield to the machine — pace yourself to it", "set": {"mx": "yield"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "stop fighting the rail; let the metronome have you",
             "outcome": (
                "You yield — stop fighting the rail, let your body go to the machine's rhythm rather "
                "than your own — and there's a cold relief in it, the surrender to a thing that "
                "can't be moved, can't be begged, has no idea you're there. The shaft drives in on "
                "its first stroke, exact and deep and utterly indifferent, and settles into the "
                "metronome it'll hold for hours. There is nothing to do but be run.")},
            {"key": "fight_machine", "label": "Fight the rail", "set": {"mx": "fight"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "strain against the locks; the machine does not notice",
             "outcome": (
                "You fight the rail — strain against the locks, twist off the line — and the machine "
                "does not notice, cannot notice, has no sensor for your refusal, only for depth and "
                "pace and time. The shaft drives in on schedule regardless, your struggle nothing "
                "but motion the frame holds still, and the metronome begins exactly as if you'd "
                "yielded. Fighting a thing with no eyes is the loneliest fight there is.")}],
        "default": "yield_machine",
        "then": "mx_ride"}


@choice("mx_ride", root=False)
def _mx_ride(character):
    return {"key": "mx_ride", "prompt": (
        "And then it just *runs* you. The shaft drives the rail on its metronome — the same depth, "
        "the same pace, the same indifferent rhythm — and the dial, untouched by any hand, ticks "
        "itself up by the chart: DEPTH a notch, PACE a notch, and then KNOT-LOCK engages and the "
        "machine drives the knot in and *holds* it, locked deep, pumping its tank of facility seed "
        "into you on a timer before withdrawing to do it all again. No person paces it. No begging "
        "reaches it. No amount of *enough* on your part registers anywhere. The cold relentless "
        "machinery of being bred by a thing that will never tire and never finish early wears at "
        "something deeper than any handler could reach — because a handler, at least, is *someone*. "
        "This is just the metronome, and the chart filling, and the hours."),
        "options": [
            {"key": "ride_full", "label": "Take the full run — bred to the chart", "effect": "facility",
             "params": {"method": "_scene_knottrain", "kind": "scene"}, "set": {"ran": "full"},
             "desc": "the real machine-breeding — knot-locked, pumped, logged on the timer",
             "outcome": (
                "You take the full run — the real machine-breeding, knot after mechanical knot "
                "driven and locked and pumped on the timer, the chart filling itself with your "
                "logged covering — and somewhere in the metronomic hours your sense of being a "
                "person being used dissolves entirely into being a *station being run*, which is "
                "exactly the cold thing the machine is for. When the timer finally ticks to STOP "
                "you're so thoroughly bred and so utterly unattended that the silence of the "
                "switched-off motor is louder than any voice.")},
            {"key": "endure_run", "label": "Endure the metronome", "effect": "facility",
             "params": {"method": "_scene_knottrain", "kind": "scene"}, "set": {"ran": "endured"},
             "desc": "the machine runs regardless; survive the indifferent hours",
             "outcome": (
                "You endure it — hold some scrap of yourself apart from the metronome, survive the "
                "indifferent hours rather than dissolve into them — and the machine breeds you "
                "exactly the same, real and logged and knot-locked on its timer, your endurance as "
                "invisible to it as your begging would be. The chart fills. The motor hums. You come "
                "out the far side bred and intact and changed by the particular loneliness of being "
                "run by a thing that never once knew you were there.")}],
        "default": "ride_full",
        "then": "mx_after"}


@choice("mx_after", root=False)
def _mx_after(character):
    return {"key": "mx_after", "prompt": (
        "The timer ticks to STOP. The shaft withdraws on its rail with the same smooth whine it "
        "started with, the knot deflating mechanically, the locks releasing your folded-open body "
        "by automated degrees. The chart on the wall is full — your covering logged in clean "
        "machine columns, deposits and depth and duration, no notes, no flavour, just numbers. The "
        "flat recorded voice returns: \"|cRun complete. Subject bred to chart. Station will reset "
        "for the next unit. You may go when your legs return.|n\" And that's all. No one comes. No "
        "one ever came. You unfold yourself off the cooling machine in an empty room."),
        "options": [
            {"key": "machine_calm", "label": "Feel the cold machine-calm of being run", "effect": "deepen",
             "params": {"amount": 2.0}, "end": True, "desc": "the personless efficiency settles into you",
             "outcome": (
                "You feel it settle — the cold machine-calm, the strange flat peace of having been "
                "*processed* rather than used, bred by a thing with no wants and no eyes — and it's "
                "worse than cruelty because cruelty is at least attention. The machine gave you "
                "none, and bred you anyway, and the lesson sinks in clean: you are a unit a station "
                "runs, and the station doesn't care, and caring was never part of the spec. You "
                "walk out into the corridor more equipment than you went in.")},
            {"key": "miss_someone", "label": "Find yourself wishing there'd been someone", "effect": "deny_hold",
             "params": {"cond": 2.0}, "end": True, "desc": "the personless hours leave you craving even a cruel face",
             "outcome": (
                "And here's the cruelest trick of the cold rig: you find yourself, walking out on "
                "unsteady legs, *missing* it — wishing there'd been someone, anyone, even a bored "
                "stockman, even a cruel one, some face to have witnessed the hours instead of the "
                "indifferent motor. The machine has made you crave attention so badly that a "
                "handler's contempt would feel like warmth. That craving is the machine's real "
                "output, and you carry it out wanting the next hands that touch you all the more "
                "for the metronome that didn't.")}],
        "default": "machine_calm"}


# ═══════════════════════════════════════════════════════════════════════════
# SCENE: The Understudy — the cruelest conversion isn't what's done TO you, it's
# being made the one who does it to the next arrival. Bethany trains her broken
# favourite to work the intake desk — to be the warm smiling clipboard-face that
# signs a newcomer into the Process, complicit, the victim made the lure. Devious,
# clean register. Real conditioning (deepen) + standing (submit_standing) + devote.
# Flow: arrival→intake→after. Entry: `scene understudy`/intake-desk/recruiter.
# ═══════════════════════════════════════════════════════════════════════════

@choice("un_arrival", root=False)
def _un_arrival(character):
    nm = subject_name(character)
    return {"key": "un_arrival", "prompt": (
        "Bethany sets a clipboard in your hands — *her* clipboard, the intake one, warm from her "
        "grip — and stands you behind the front desk where it all started for you, where she once "
        f"smiled you in. \"I've a treat for you, {nm},\" she says, fixing your collar, your posture, "
        "the angle of your head, dressing you into the role. \"You've been through the whole "
        "Process now. You *understand* it, top to bottom, better than any new hire ever could. So "
        "I'm promoting you — a little. You're going to help me with *intake*.\"\n\n"
        "Through the glass, a |wnewcomer|n is being walked up the path — nervous, hopeful, "
        "clutching a referral, exactly as green as you were. \"That one signs today,\" Bethany "
        "murmurs, warm at your ear. \"And *you're* going to do it. Smile like I smiled at you. Use "
        "the soft voice. Tell them it's safe, tell them the contract's a formality, tell them all "
        "the true-sounding things I told you — because they'll believe it from *you*, another "
        "resident, so much faster than from me.\" Her hand rests fond on the back of your neck. "
        "\"The thing that was broken, holding the door for the next one. It's the sweetest "
        "graduation I offer. Far sweeter than freedom.\""),
        "options": [
            {"key": "take_clipboard", "label": "Take the clipboard — become the smiling face",
             "set": {"un": "take"}, "effect": "deepen", "params": {"amount": 3.0},
             "desc": "step into the role; be the lure you once fell for",
             "outcome": (
                "You take the clipboard, and something in you settles into the role with a "
                "horrible ease — the posture, the smile, the soft warm voice, all of it already "
                "*in* you because it was used on you, learned by heart from the inside. \"*There* "
                "she is,\" Bethany breathes, delighted. \"My understudy. You wear my smile better "
                "than I do — because you know exactly what's behind it, and you're going to use it "
                "anyway. That's the part I couldn't teach. That's the part you *chose*.\"")},
            {"key": "balk_role", "label": "Balk at luring someone else in", "set": {"un": "balk"},
             "effect": "deny_hold", "params": {"cond": 2.0},
             "desc": "refuse to be the bait; she has patient ways",
             "outcome": (
                "You balk — try to hand the clipboard back, refuse to be the thing that lures the "
                "next one — and Bethany doesn't take it, just folds your fingers gently back around "
                "it. \"No? Not yet. That's all right.\" The newcomer's almost at the door. \"But "
                "here's the thing, sweetheart — if you don't sign them in kindly, I'll sign them in "
                "*un*kindly, and they'll have a so much worse first hour, and you'll have watched "
                "you could have softened it and didn't. The choice isn't whether they're processed. "
                "It's whether your face is the kind one. Choose quickly. They're here.\"")}],
        "default": "take_clipboard",
        "then": "un_intake"}


@choice("un_intake", root=False)
def _un_intake(character):
    return {"key": "un_intake", "prompt": (
        "The newcomer sits across the desk from you — your old seat, your old nerves, your old "
        "hope — and looks at you with the specific relief of someone glad to see *another resident* "
        "instead of a clerk, someone who'll tell them the truth. You hold the contract. You know "
        "every hidden clause in it, because every one of them is installed in your own body. You "
        "know exactly what signing does. And they're waiting for you, trusting, pen already half-"
        "reaching, for you to tell them it's all right. Bethany watches from the back, silent, "
        "letting you do the work — letting the complicity be *yours*. \"...is it safe?\" the "
        "newcomer asks you, quiet, the same question you once asked. \"You've been here a while. "
        "Would you... would you tell me if it wasn't?\""),
        "options": [
            {"key": "lure_warm", "label": "Smile, and sign them in warm", "effect": "deepen",
             "params": {"amount": 3.0}, "set": {"intake": "warm"},
             "desc": "use the soft true-sounding lies that were used on you",
             "outcome": (
                "You smile — the warm one, the one that worked on you — and you say the true-"
                "sounding things: that it's safe, that the contract's a formality, that the staff "
                "are kind, that you're glad you stayed. Every word technically defensible, every "
                "word a door closing. The newcomer's shoulders drop in relief and they *sign*, "
                "fast, trusting you, and the pen-scratch is the worst and most familiar sound in "
                "the world. Bethany doesn't even smile; she just makes a note. You did it cleaner "
                "than she would have. That's the note.")},
            {"key": "warn_caught", "label": "Try to warn them with your eyes", "effect": "deny_hold",
             "params": {"cond": 3.0}, "set": {"intake": "warn"},
             "desc": "say the script but try to signal the truth; the clause won't let you",
             "outcome": (
                "You say the script — but you try to put the truth in your *eyes*, to signal "
                "*run*, to warn them with everything but the words you're compelled to speak — and "
                "you feel the speech-clause catch your tongue, smooth the warning out of your voice, "
                "leave only the warm lie audible while your eyes scream into a face too hopeful to "
                "read them. They sign. \"Good try,\" Bethany says softly, behind you, having seen "
                "exactly what you attempted. \"The clause holds even when the heart doesn't. You'll "
                "learn to stop trying. It only hurts you, and never reaches them.\"")}],
        "default": "lure_warm",
        "then": "un_after"}


@choice("un_after", root=False)
def _un_after(character):
    return {"key": "un_after", "prompt": (
        "The newcomer is led off to be processed — to begin the exact road you walked — and the "
        "door closes behind them, and you're left holding the clipboard with their signature still "
        "drying on it. Bethany comes to you, takes the board, and replaces it with something worse: "
        "her approval. \"Perfect,\" she says, warm and proud, and the pride lands in you like a "
        "hook you hate how much you feel. \"You've crossed the line that matters, sweetheart. You're "
        "not just *processed* anymore — you're *complicit*. You held the door. You'll hold it "
        "again. And every time you do, you'll understand a little better why I do it, and resent me "
        "a little less, because now we're the same.\" She tucks a strand of your hair back, fond. "
        "\"That's the deepest I can take anyone. Not breaking them. Recruiting them.\""),
        "options": [
            {"key": "become", "label": "Feel yourself become the thing that broke you", "effect": "deepen",
             "params": {"amount": 3.0}, "end": True, "desc": "the complicity settles in as identity",
             "outcome": (
                "You feel it settle — the complicity becoming *identity*, the smiling clipboard-face "
                "no longer a role you're playing but a thing you now *are* — and the horror of it is "
                "that it's also a relief, because being the one who holds the door is so much safer "
                "than being the one walked through it. \"There,\" Bethany murmurs, watching you "
                "arrive at it. \"Welcome to my side of the desk. It's warmer over here. It's warmer "
                "because someone else is cold. You understand that now, all the way down.\"")},
            {"key": "submit_role", "label": "Accept the promotion to her understudy", "effect": "submit_standing",
             "end": True, "desc": "real standing — take the role on the books, the broken made the breaker",
             "outcome": (
                "You accept it — the promotion, the role, the place at her side — and it's logged, "
                "real, your standing shifted from stock toward *staff*, the broken thing made into "
                "the breaker on the facility's own books. \"My understudy, official,\" Bethany says, "
                "pleased, and the new title sits on you stranger than any collar. \"You'll work "
                "intake with me, and breeding when I lend you back, and someday — who knows — a desk "
                "of your own. The Process doesn't end at being livestock, sweetheart. For the "
                "favourites, it ends at being *me*. Slowly. We've time.\"")}],
        "default": "become"}
