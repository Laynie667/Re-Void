"""
world/facility_fellow.py — a named fellow-resident with continuity.

The facility shouldn't feel like it processes only you. One co-resident is tracked with her
own slowly-advancing state — she softens, comes into milk, gets bred round, goes blank, is
graded Perfected and sold off, and a fresh intake takes her place. She's a recurring face,
a mirror, and a foreshadow: a few rooms ahead of you on the same line, until she's gone and
the next one starts where she began.

    character.db.facility_fellow      {"name", "stage", "prog", "replaced"}
    character.db.facility_fellow_ref  dbref of her real present NPC object (set on spawn)

All state is on the RESIDENT's db (per-game, reset-safe via FACILITY_FLAGS) + a realm-tagged
NPC the teardown deletes. Nothing here gates the §0 floor.
"""

import random

_FELLOW_NAMES = [
    "Mara", "Sona", "Briar", "Lux", "Pem", "Tilly", "Cass", "Wynn", "Dove", "Indra",
    "Fawn", "Reya", "Nell", "Opal", "Juno", "Vesper",
]

# stage -> (short label, physical-desc for her NPC, beat-pool said while you share a room).
# Tokens: {f} = fellow's name, {t} = the reading resident's name.
_FELLOW_STAGES = [
    ("fresh intake",
     "a new intake — {f}, still soft and unmarked and frightened, eyes darting, the fight not "
     "yet worked out of her. She still flinches from the cups. She still thinks there's a clause "
     "that lets her out. She looks at you like she's trying to read her future off your body.",
     [
        "|x{f} — the new one — catches your eye across the room and looks quickly away, the way "
        "you used to. She still has the looking-away in her. It won't last.",
        "|x{f} asks a handler a question in a small voice and isn't answered. She'll stop asking "
        "soon; they all do. You remember stopping.",
        "|xThe new intake, {f}, still tries to cover herself when she can. Nobody tells her to "
        "stop — they just wait. The waiting is what does it.",
     ]),
    ("softening",
     "{f}, a few weeks in — the flinch gone slower, the rhythm of the place starting to move her "
     "instead of the other way round. She presents a half-second faster than she means to now, "
     "and hates that she does, and does it anyway.",
     [
        "|x{f} settles onto the rig without being pushed this time, and you watch her notice she "
        "did it, and watch her decide not to think about it. A few rooms ahead of you. Or behind.",
        "|x{f}'s words come out rounder than they did last cycle — the speech starting to drift. "
        "She still has most of her name. Most of it.",
        "|x{f} leaks a little when the machine starts up near her now, before it even touches her. "
        "She's being trained the way you were. You can see the exact shape of it from here.",
     ]),
    ("milk-heavy",
     "{f}, switched on and producing — tits swollen and racked daily, leaking on a schedule that "
     "isn't hers, the dairy's gauge logging her yield beside yours. She's stopped fighting the "
     "cups entirely; she lifts to them now, grateful when they come.",
     [
        "|x{f} is racked beside you and milked in time, her gauge climbing next to yours, and when "
        "the cups finally seal over her she makes a sound of pure relief that you understand far "
        "too well.",
        "|x{f}'s gone milk-heavy and soft with it, drifting between draws, her whole day a wait "
        "between the cups. She's where you are. Or where you're going.",
        "|x{f} doesn't cover herself anymore. There's nothing left to cover for; she's output now, "
        "racked and logged, and she's stopped pretending otherwise. You watched it happen by inches.",
     ]),
    ("bred-round",
     "{f}, heavy with a litter — belly rounded and low, dropped young already on file, her "
     "breeding quota climbing with each one. She moves carefully around the weight of what they "
     "put in her, and her eyes have gone somewhere soft and far.",
     [
        "|x{f} is led past bred-round and waddling, one hand under the weight of the litter "
        "they've put in her, and she doesn't meet your eyes — there's not much behind them now "
        "to do the meeting.",
        "|x{f} drops a litter in the next stall, barely making a sound about it, and is bred again "
        "before the cycle's out. Her quota climbed for it. You know exactly how that goes.",
        "|x{f}'s own get scent her and breed her where she's penned, the line folding shut through "
        "her the way it folds through you, and she takes it with a vague, gone serenity.",
     ]),
    ("conditioned-blank",
     "{f} — or what answers to the designation that used to be {f}. The name's slipped; the face "
     "is smooth and present and empty, waiting to be told the next thing. There's a brand on her "
     "now, and a number, and not much in the eyes but a soft willingness.",
     [
        "|xThe thing that used to be {f} kneels when a handler passes, blank and content, and you "
        "realise you can't remember the last time you heard her called by name. Neither, clearly, can she.",
        "|x{f} recites something flat and automatic when prompted — a mantra, her number, a thank-you "
        "— and goes still again. There's nobody home to be embarrassed. You're watching the far end of the line.",
        "|x{f}'s been conditioned down to a smooth, waiting blank, and the worst part is how "
        "restful she looks. How finished. How close that is to you.",
     ]),
    ("perfected",
     "{f}, graded Perfected — polished, placid, complete, and already half-promised to a buyer. "
     "She's the finished product the whole line is bent toward making. She is what's at the end "
     "of this, dressed up and put on the block.",
     [
        "|x{f} is brought through graded Perfected — placid, polished, finished — on her way to the "
        "block to be sold. She's what the end of the line looks like. She looks, horribly, at peace.",
        "|xWord comes that {f} sold today. A good price. They'll bring a fresh intake to fill her "
        "rig by tomorrow, and the line won't notice the difference, and neither, soon, will you.",
     ]),
]


def ensure_fellow(character):
    """Create the fellow-resident record if missing. Returns it."""
    f = dict(getattr(character.db, "facility_fellow", None) or {})
    if not f.get("name"):
        f = {"name": random.choice(_FELLOW_NAMES), "stage": 0, "prog": 0, "replaced": 0}
        character.db.facility_fellow = f
    return f


def advance_fellow(character, chance=0.18):
    """Maybe progress the fellow one rung along the line. At the end she's sold and a fresh
    intake replaces her (churn). Returns (event, fellow) where event is None / 'advance' /
    'churned'."""
    f = ensure_fellow(character)
    if random.random() >= chance:
        return None, f
    stage = int(f.get("stage", 0))
    if stage >= len(_FELLOW_STAGES) - 1:
        # Perfected — sold off; a new intake takes her rig.
        old = f.get("name")
        names = [n for n in _FELLOW_NAMES if n != old]
        f = {"name": random.choice(names or _FELLOW_NAMES), "stage": 0, "prog": 0,
             "replaced": int(f.get("replaced", 0)) + 1, "sold": old}
        character.db.facility_fellow = f
        return "churned", f
    f["stage"] = stage + 1
    character.db.facility_fellow = f
    return "advance", f


def fellow_stage(character):
    f = ensure_fellow(character)
    idx = max(0, min(int(f.get("stage", 0)), len(_FELLOW_STAGES) - 1))
    return _FELLOW_STAGES[idx]


def fellow_desc(character):
    """Her NPC's current physical description, reflecting her stage."""
    f = ensure_fellow(character)
    _label, desc, _pool = fellow_stage(character)
    return desc.format(f=f.get("name"), t=(character.db.rp_name or character.name))


def fellow_beat_line(character):
    """A prose beat about the fellow at her current stage, or '' . Tokens filled."""
    f = ensure_fellow(character)
    _label, _desc, pool = fellow_stage(character)
    if not pool:
        return ""
    t = character.db.rp_name or character.name
    return random.choice(pool).format(f=f.get("name"), t=t)


def fellow_churn_line(character, sold_name):
    """The line when the old fellow is sold and a new intake replaces her."""
    f = getattr(character.db, "facility_fellow", None) or {}
    new = f.get("name", "the new one")
    t = character.db.rp_name or character.name
    return (f"|WWord comes through the line: {sold_name} graded out and sold today — gone to a "
            f"buyer, off the floor, finished. By the next shift a fresh intake named {new} is "
            f"being strapped into her rig, soft and frightened and whole, starting exactly where "
            f"{sold_name} started. The line doesn't slow for it. It never has. And {t} watches "
            f"the whole cycle of a person happen beside her, start to sold, and does the maths "
            f"on her own place in it.|n")
