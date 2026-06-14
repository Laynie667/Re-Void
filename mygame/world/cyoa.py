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
    # (so linear beats can declare one next-node for all their options).
    nxt = opt.get("then") or pending.get("then")
    if nxt:
        try:
            pose_named(character, nxt, room=getattr(character, "location", None))
        except Exception:
            pass
    # End of a scene — clear its memory so the next scene starts fresh.
    if opt.get("end"):
        character.db.scene_flags = None
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
        "where I call two lads to hold you. Stock doesn't care which. Neither do I.\""),
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
        "boar's keen, boar's quick, boar knots like a bastard. Bull's proven, slow, hung like "
        "you'd not believe. Stallion'll wreck you and he's not gentle about depth.\" He stops at "
        "the kennel run, where a dozen heavy rangy hounds have their noses jammed to the bars, "
        "working your scent, whining. \"Or the kennel takes the lot of you and we get your whole "
        "quota done in one ugly afternoon.\" He clicks his pen. \"I'll pick if you won't. But "
        "you're in the frame either way, so. What's it to be.\""),
        "options": [
            {"key": "stud", "label": "Take the stud he's picked", "set": {"beast": "stud"},
             "effect": "devote", "params": {"amount": 2.0},
             "desc": "one animal, his choice; let the machinery decide",
             "outcome": (
                "\"Goliath, then. Board's short on his cross anyway.\" He unlatches the boar's pen "
                "with the bored competence of a man fetching a tool, and the thing comes out "
                "snorting, three hundred pounds of single-minded rut, and the stockman steers it "
                "toward your strapped-open body with a hand on its shoulder like he's parking a "
                "cart. \"Hold still. He's faster if you don't fight the first mount.\"")},
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
        "stud": ("The boar shoulders up behind you, and the stockman guides its blunt seeking snout "
                 "to the greasy marking-post first and then to *you* — letting it scent the frame, "
                 "scent your strapped-open holes, work itself into a deeper rut on the smell of you. "
                 "Its breath is hot and wet down the backs of your thighs. Something blunt and "
                 "already-dripping drags across your skin, hunting the right hole by feel."),
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
        "stud": ("The boar mounts. There's no ceremony to it and no patience — it heaves its bulk "
                 "up over your back, claws scrabbling, far too heavy, and its blunt slick cock "
                 "stabs and misses and stabs again, hunting, until it jams against a hole — any "
                 "hole, it doesn't choose, it just finds wet and *drives* — and the flared length "
                 "of it spears into you in one brutal uncaring shove that punches a scream out of "
                 "you. It is already rutting before it's fully seated, fast and shallow and "
                 "frantic, an animal with one idea."),
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
    return {"key": "bp_mount", "prompt": (
        body + " You feel the size of it map itself out inside you — the stretch, the wrong-deep "
        "ache, the blunt animal heat of it, the way it gives you no rhythm to brace against because "
        "it isn't *for* you, you are simply the hole it's using. The stockman watches your face "
        "with professional detachment, checking — not for your sake — that the stock has seated "
        "properly and isn't going to injure itself.\n\n\"There it goes,\" he says. \"Seated. Now "
        "it just works till it ties. Could be a minute. Could be twenty. It'll tell you.\""),
        "options": [
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
        "stud": ("The boar's rhythm stutters, jams deep, and the knot at its base swells — and it "
                 "doesn't ask, it just *forces*, hauling you back onto it as the gorged knot bullies "
                 "at your stretched rim, too big, far too big, until it gives with a blunt sick "
                 "internal |w*pop*|n and seats, and your rim clamps shut behind it. Tied. Locked to "
                 "three hundred pounds of spent rutting animal that immediately tries to step off "
                 "and can't, and drags you with it, the knot wrenching inside you."),
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
    return {"key": "cc_arrival", "prompt": (
        "The Conditioning Cell is small and dim and padded for quiet, and the only thing in it "
        "that matters is the chair. The |wSpiral Chair|n: high-backed, deeply cushioned, restraints "
        "at every limb worn soft from use, and above it, angled down so you cannot not look at it, "
        "a slow black-and-white |wspiral|n already beginning to turn. They sit you in it and the "
        "padding receives your weight like it knows you, and the straps go on — wrists, ankles, a "
        "soft band across your brow that means your head stays where the spiral wants it — and a "
        "speaker somewhere close to your ear clicks, and warms, and *she* begins.\n\n"
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

def _dairy_state_note(character):
    """A light state-aware line for the dairy hand's assessment — the hook the rest of the
    facility's scenes will use to branch on little/pregnant/nugget/etc. Safe defaults."""
    db = getattr(character, "db", None)
    little = float(getattr(db, "regression", 0) or 0) > 0 or bool(getattr(db, "headspace", None))
    nugget = bool(getattr(db, "nugget", False))
    preg = bool(getattr(db, "pregnant", False) or getattr(db, "brood_count", 0)
                or getattr(db, "gestating", False))
    if nugget:
        return ("He has to bend right down to reach you — a nugget on the dairy line, tiny and "
                "limbless and absurdly productive for your size — and he fits the smallest cups "
                "the rack carries. \"Little thing, big yield. The board loves a nugget.\" ")
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
