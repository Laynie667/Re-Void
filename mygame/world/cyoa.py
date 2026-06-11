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
    msg = run_effect(character, opt.get("effect"), opt.get("params"))
    # Outcome prose — the crude, in-voice beat of what your choice just did to you, shown
    # privately (it's yours to live with). Effects may also broadcast their own room messages.
    outcome = opt.get("outcome")
    if outcome and getattr(character, "msg", None):
        character.msg("|y" + outcome + "|n")
    # Chain — an option may pose the next node in the branch.
    nxt = opt.get("then")
    if nxt:
        try:
            pose_named(character, nxt, room=getattr(character, "location", None))
        except Exception:
            pass
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
                       default_key=spec.get("default"), room=room)


def pose_random(character, room=None):
    """Pose a random root choice (the cycle's auto-poser). Skips builders that return None
    (e.g. the hole menu when she has no orifices)."""
    if not _ROOTS:
        return None
    for cid in random.sample(_ROOTS, k=len(_ROOTS)):
        if pose_named(character, cid, room=room):
            return cid
    return None


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
    key = random.choice(["teat_gag", "nurse_first", "stuffed_mouth", "beg_small", "star_chart"])
    blurb = {
        "teat_gag":      "a gag-word any mouth in the building can say to plug yours with a teat you'll suckle helpless on",
        "nurse_first":   "a clause that won't let you speak a first word to anyone until you've nursed a load down",
        "stuffed_mouth": "a clause filing your speech down to cock-muffled fragments, your mouth retooled off words",
        "beg_small":     "a clause that denies you release as of right — you'll beg small for every drop of it now",
        "star_chart":    "a chart where relief is bought with stars earned the only way the work earns them",
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
