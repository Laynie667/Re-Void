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
