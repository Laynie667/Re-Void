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


# Shared-processing scenes when you and the fellow are in the same room, keyed by her stage
# band. Each entry is (kind, line); kind in {"milk","breed","use","sold"} lets the script apply
# the REAL effect (a breed scene actually inseminates the resident). Tokens {f}/{t}.
_FELLOW_SHARED = {
    "early": [   # stages 0-1: racked together, watching each other learn it
        ("milk", "|cThey rack {t} and {f} side by side and start the cups on both at once. {f} "
         "still gasps at the first pull; {t} doesn't anymore. The two of them are milked in "
         "tandem, gauges climbing together, and {f} keeps stealing looks at {t} like she's "
         "reading how much worse it gets.|n"),
        ("use", "|y{t} and {f} are made to kneel facing each other and clean one another with "
         "their tongues on the handlers' count — a humiliation drill, eyes locked because they're "
         "not allowed to look away, both learning that modesty was never on the table here.|n"),
    ],
    "mid": [     # stages 2-3: milk-heavy / bred-round — worked hard, together
        ("breed", "|rThe same stud is run down the line and put to {t} and {f} one after the "
         "other without a wipe between — bred back to back off the same cock, made to watch each "
         "other take it, the only dignity left being whether you can keep quiet, and neither of "
         "you can.|n"),
        ("milk", "|c{t} and {f} are clamped facing, tits cupped and drawn, and made to nurse the "
         "drawn milk from each other's leaking nipples to 'keep it in the supply' — a closed loop "
         "of two producers feeding one another, logged as yield either way.|n"),
        ("breed", "|r{t} and {f} are bent over the same bench hip to hip and bred along the row "
         "together, the handlers working down the line, and {f}'s hand finds {t}'s and grips it "
         "through it — the only comfort on offer, and they take it, because there's nothing else.|n"),
    ],
    "deep": [    # stages 4-5: blank / perfected — she's ahead, and shown to you as the end
        ("use", "|M{f} — gone blank and biddable — is handed to {t} as a thing to use, and {t} is "
         "made to use her, the handlers watching to see if {t} will hesitate. {t} doesn't, much. "
         "That's the lesson: you become the hands that do it, a few rooms before it's done to you.|n"),
        ("sold", "|W{f}, graded Perfected, is posed on the block beside {t} for a private buyer, "
         "and {t} is made to present alongside her — the finished product next to the one still "
         "being finished. The buyer takes {f}. {t} is told, fondly, that her turn on the block is "
         "coming, and to watch how it's done.|n"),
    ],
}

_STAGE_BAND = {0: "early", 1: "early", 2: "mid", 3: "mid", 4: "deep", 5: "deep"}


def fellow_shared(character):
    """A shared-processing scene with the fellow, keyed to her stage band. Returns (kind, line)
    with tokens filled, or (None, '')."""
    f = ensure_fellow(character)
    band = _STAGE_BAND.get(int(f.get("stage", 0)), "early")
    pool = _FELLOW_SHARED.get(band) or []
    if not pool:
        return None, ""
    kind, line = random.choice(pool)
    t = character.db.rp_name or character.name
    return kind, line.format(f=f.get("name"), t=t)


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


# ── Set-piece: Bethany has the female fellow converted to futa and made to breed you ──
# A multi-beat scripted scene. The fellow is PERMANENTLY turned futa (continuity), dosed, and
# set loose; her mind fragments between abusing her friend and how good breeding feels. The
# breeding is real (the script fires gang_inseminate, sire = the fellow). Tokens {f}/{t}.
_FELLOW_FUTA_CONVERT = [
    "|GBethany walks {f} in on a leash and lays a fond hand on {t}'s head. \"I had an idea about "
    "your little friend,\" she says, bright as morning. The techs strap {f} to the conversion "
    "cradle and go to work between her thighs — and what they grow there is not small: a "
    "facility-bred futa cock forced up out of her in minutes, flaring, knotting, fattening with "
    "balls that drop heavy and full, until {f} is sobbing at the new weight of what she's been "
    "given. \"There. Now she can be useful to you. Say thank you, both of you.\"|n",
    "|G\"Friends should share,\" Bethany tells {t}, signing the order one-handed. They take {f} "
    "apart and rebuild her on the table — a thick, veined, facility-standard futa cock grafted "
    "live at the root, knot and flare and a swinging set of balls, the whole apparatus wired hot "
    "into her before she's stopped shaking. {f} stares down at the new monstrous length of "
    "herself jutting from her body and makes a sound that isn't quite a word.|n",
]
_FELLOW_FUTA_DOSE = [
    "|GThen the aphrodisiac goes in — a fat syringe emptied into the root of {f}'s new cock and "
    "another into her neck — and {f}'s pupils blow wide and black. The need hits her like a "
    "truck: she's instantly, brutally hard, hips already jerking at nothing, every thought "
    "drowning under a single roaring imperative. \"Off you go, sweetheart,\" Bethany says, and "
    "points her at {t}.|n",
    "|GBethany doses {f} until she's shaking with it — the new cock flushed dark and dripping, "
    "balls drawn up tight and aching, {f}'s whole body a live wire of manufactured rut. Whatever "
    "{f} is trying to say drowns. She turns and looks at {t} — her friend, on the floor, "
    "presented — and you watch the want win.|n",
]
_FELLOW_FUTA_BREED = [
    "|r{f} mounts {t} with a desperate, graceless lunge and sinks the whole new length of herself "
    "in to the knot in one go, too far gone on the dose to be gentle, and then she's RUTTING — "
    "frantic, deep, helpless, fucking her friend with the single-minded fury of a body that has "
    "been given a cock and a drug and one instruction.|n",
    "|r{f} grabs {t}'s hips and hammers in, the new balls slapping heavy, her flare dragging {t} "
    "open on every brutal stroke. She can't stop. She doesn't try anymore. She just breeds, hard "
    "and deep and sobbing, chasing the knot like it's the only thing left in the world.|n",
    "|r{f} ruts into {t} like an animal that used to be a person, the dose burning every gentle "
    "thing out of her, knotting deep and grinding and starting again before she's even softened, "
    "breeding her friend in a frenzy she has no say in and {t} has no defence against.|n",
]
_FELLOW_FUTA_FRAGMENT = [
    "|x\"I'm sorry,\" {f} sobs into {t}'s shoulder even as her hips snap forward, \"I'm sorry, "
    "I'm sorry, I can't — oh god you feel — I'm SORRY—\" The two halves of her can't both be "
    "true and both are, and the rut is winning, sentence by sentence.|n",
    "|x{f}'s face is a war — horror at what she's doing to her friend, and under it, rising, a "
    "drugged ecstatic helplessness at how unbelievably GOOD it feels to be buried in {t}. "
    "\"I don't — I never wanted — fuck, fuck, why does it feel like THIS—\" The wanting eats the "
    "words.|n",
    "|x\"This isn't me,\" {f} whimpers, balls-deep, grinding, \"this isn't — I'd never — \" and "
    "then the dose crests and her eyes roll and the apology dissolves into a moan, and for a few "
    "seconds there's no friend left in her at all, just the cock and the heat and {t}, and then "
    "the horror floods back in and she's begging forgiveness again without breaking rhythm.|n",
    "|x{f} keeps looking at {t}'s face like she's searching for the line she's crossing, can't "
    "find it through the dose, and breeds her harder for the not-finding. \"Tell me to stop,\" "
    "she gasps — and doesn't wait for an answer, couldn't obey it, and you both know it.|n",
]
_FELLOW_FUTA_LITTLE = [
    "|M{f} is little too now — Bethany made sure — and that's the worst of it: two small, "
    "frightened things, and one of them grown a big scary cock she doesn't understand and can't "
    "stop using on her friend. {f} cries the whole time, little hiccuping sobs, \"m'sorry, "
    "m'sorry,\" rutting {t} in clumsy desperate baby-thrusts she has no grown-up part left to "
    "rein in.|n",
    "|MTwo littles in the straw, and one put inside the other. {f} doesn't have the words for "
    "what she's doing — just \"feels good, feels good, m'sorry, feels good\" — and {t} doesn't "
    "have the words to make her stop, and neither of them was left enough self to choose any of "
    "it. Bethany watches her two babies breed like it's the sweetest thing she's ever arranged.|n",
    "|M{f} clings to {t} as she humps her, both of them little and lost, the cock too big and "
    "the dose too strong and the friendship still there underneath it all, ruined and clinging. "
    "\"Still f-fwiends?\" {f} hiccups, balls-deep, breeding her. It's the most broken thing in "
    "the room, and Bethany coos at it.|n",
]
_FELLOW_FUTA_FINISH = [
    "|r{f} slams to the knot and locks and EMPTIES — those heavy new balls pumping load after "
    "load into {t}, far more than a body should hold, {f} wailing through it half in ecstasy and "
    "half in grief, tied to her friend and unable to pull out if she wanted to. When the dose "
    "finally ebbs she's left collapsed over {t}, knotted in, weeping, whispering apologies into "
    "her hair — bred into her, changed forever, hers and {t}'s ruin both.|n",
    "|r{f} comes with a broken scream, flooding {t} to the knot, and stays locked there shaking "
    "as the aphrodisiac slowly lets her go. The cock is hers to keep now — Bethany doesn't "
    "reverse her work. {f} will carry it, and what she did with it, from here on. \"Good girl,\" "
    "Bethany murmurs to them both, fond and final. \"You're going to be such good use to each "
    "other.\"|n",
]


def mark_fellow_futa(character):
    """Permanently convert the fellow to a futa (continuity — she keeps the cock). Returns her name."""
    f = ensure_fellow(character)
    f["futa"] = True
    character.db.facility_fellow = f
    return f.get("name")


def fellow_is_futa(character):
    return bool((getattr(character.db, "facility_fellow", None) or {}).get("futa"))
