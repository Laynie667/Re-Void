"""
world/facility_animals.py — Bethany's named personal studs.

The facility kennel/stalls aren't anonymous: Bethany keeps named prize beasts of her own
line, and the scenes reference them by name for immersion (and tag their get as sired by
them). The roster lives on the resident's own db (set at build/upgrade) so it's per-game and
reset-safe — `facility_studs` is in FACILITY_FLAGS, so the §0 floor clears it like everything else.

    character.db.facility_studs   list of {"name", "species", "desc"}

Helpers:
    ensure_studs(char)            install the default roster if missing (idempotent)
    pick_stud(char, species=None) a named stud (optionally of a species), or None
    stud_line(stud)               a short descriptive tag for prose
"""

import random

# Bethany's standing studs — her favourites, kept and bred into her stock. Each has a
# `temperament` driving how it breeds her (see SIRE_TEMPERAMENTS / sire_beat).
DEFAULT_STUDS = [
    {"name": "Caesar",  "species": "hound", "temperament": "veteran",
     "desc": "Bethany's prize stud hound — a huge, scarred brute with a fist-fat knot and a "
             "patient, working temperament; he's put more litters in the stock than any three "
             "of the others, and he knows the smell of a presented hole on sight."},
    {"name": "Duke",    "species": "hound", "temperament": "eager",
     "desc": "a lean, tireless young hound coming up in Caesar's place — quick to mount, slow "
             "to soften, and far too clever about finding a hole that can't get away from him."},
    {"name": "Brutus",  "species": "bull", "temperament": "inexorable",
     "desc": "Bethany's herd bull — a mountain of muscle and weight, slow and inexorable, the "
             "kind of breeding that reshapes what it's put into and doesn't notice it has."},
    {"name": "Goliath", "species": "boar", "temperament": "filthy",
     "desc": "the stud boar — blunt, filthy, relentless, with a corkscrew flare that screws "
             "deep and locks, and an appetite for breeding that genuinely never seems to flag."},
    {"name": "Sultan",  "species": "stallion", "temperament": "ruinous",
     "desc": "Bethany's stallion — obscene in length and girth, flared like a fist at the head, "
             "the sort of stud you have to be held open and steady for or he'll simply ruin you."},
]

_TEMPERAMENTS = ["veteran", "eager", "inexorable", "filthy", "ruinous"]

# How each temperament breeds her — a per-sire voice line. Tokens: {t} (subject), {sire} (name).
SIRE_TEMPERAMENTS = {
    "veteran": [
        "{sire} takes his time the way only a proven stud does — no wasted motion, no hurry, "
        "just the unbothered certainty of an animal that has bred this exact hole a hundred "
        "times and will a hundred more. He seats deep, knots, and waits {t} out.",
        "{sire} mounts {t} like a job he's mastered: a couple of testing thrusts to find the "
        "angle he likes, then long, deep, metronomic drives that ignore everything she does "
        "about it, breeding her with the patience of something that knows she isn't going anywhere.",
        "There's nothing frantic in {sire}. He works into {t} slow and sure, lets the knot "
        "swell where it'll lock best, and empties himself on his own unhurried schedule — a "
        "veteran putting another litter on the books, fond of the work in his flat animal way.",
    ],
    "eager": [
        "{sire} can't wait — he's on {t} before she's braced, hips already snapping, too keen "
        "and too clumsy to aim, rutting at her in a frantic scramble until he finds the hole "
        "and rams home with a whine of pure relief. Young, greedy, and absolutely tireless.",
        "{sire} mounts in a clumsy, overeager rush, slips, tries again, and then he's IN and "
        "going like he'll die if he stops — quick frantic jackrabbit thrusts, breeding {t} with "
        "more enthusiasm than skill and somehow getting the job done twice as fast for it.",
        "{sire} is all youth and appetite, fucking {t} in a desperate sprint, whining and "
        "drooling, knotting almost before he means to and then humping helplessly through it, "
        "too keyed-up to hold still even tied. He'll be ready to go again embarrassingly soon.",
    ],
    "inexorable": [
        "{sire} doesn't so much mount {t} as settle his whole crushing weight over her and "
        "begin — slow, enormous, unstoppable, each drive forcing her open a little further whether "
        "she can take it or not, breeding her with the patient inevitability of geology.",
        "{sire} works into {t} like a piston that has never once been hurried, the sheer mass "
        "of him pinning her flat, each thrust deep enough to rearrange her and slow enough to "
        "feel every inch of it. He finishes when he finishes. Her opinion was never part of it.",
        "There is no fighting {sire}; there's only being bred by him, slowly, completely, the "
        "weight and the depth and the grinding patience of him reshaping {t} around what he's "
        "putting in her, and not even noticing he's done it.",
    ],
    "filthy": [
        "{sire} is a mess and makes one — drooling, grunting, rooting at {t} with that "
        "corkscrew flare until it screws in and locks, then breeding her in filthy, sloppy "
        "lunges, slathering her in spit and worse and clearly delighted by all of it.",
        "{sire} mounts {t} with no dignity whatsoever and ruins what's left of hers — blunt, "
        "relentless, screwing deep and locking tight, rutting at her through the muck with an "
        "appetite that genuinely never flags, leaving her bred and slick and degraded.",
        "{sire} doesn't breed clean. He covers {t}, screws that flare in to the lock, and goes "
        "at her filthy and tireless, snuffling and slobbering, the whole thing as degrading as "
        "it is thorough — which is the entire point of putting her under him.",
    ],
    "ruinous": [
        "{sire} is simply too much — they have to hold {t} open and steady for him or he'd "
        "tear her, and even held she sobs around the flared, fist-fat length of him as he sinks "
        "it home and breeds her in long, wrecking strokes that leave her gaping and ruined.",
        "{sire} ruins {t} on the way in and keeps ruining her — obscene length and girth forcing "
        "her past what she can take, the flare dragging her open with every stroke, breeding her "
        "so thoroughly she'll feel the shape of him for days and be no use to a smaller stud after.",
        "It takes two handlers to seat {sire} in {t} and hold her there while he breeds — he's "
        "built to wreck, and he does, flaring and flooding her until she's stretched useless and "
        "leaking, a hole reshaped around a stud she could never have managed on her own.",
    ],
}


def ensure_studs(character):
    """Install the default stud roster onto the character if they don't have one. Idempotent.
    Returns the roster list."""
    if not character:
        return []
    cur = list(getattr(character.db, "facility_studs", None) or [])
    if cur:
        return cur
    roster = [dict(s) for s in DEFAULT_STUDS]
    character.db.facility_studs = roster
    return roster


def pick_stud(character, species=None):
    """Return a named stud dict from the character's roster (optionally of `species`), or None."""
    roster = list(getattr(character.db, "facility_studs", None) or [])
    if not roster:
        return None
    if species:
        matches = [s for s in roster if s.get("species") == species]
        if matches:
            return random.choice(matches)
        return None
    return random.choice(roster)


def add_stud(character, name, species, desc="", temperament=None):
    """Add a named stud to the roster (or update an existing one of that name)."""
    roster = ensure_studs(character)
    temperament = temperament or random.choice(_TEMPERAMENTS)
    for s in roster:
        if (s.get("name") or "").lower() == (name or "").lower():
            s["species"] = species
            if desc:
                s["desc"] = desc
            s.setdefault("temperament", temperament)
            character.db.facility_studs = roster
            return s
    entry = {"name": name, "species": species, "temperament": temperament,
             "desc": desc or f"one of Bethany's {species}s"}
    roster.append(entry)
    character.db.facility_studs = roster
    return entry


def sire_beat(character, sire_name, t):
    """A per-sire breeding-voice line, drawn by the named stud's temperament (looked up on the
    dam's roster). Returns "" if the sire isn't a named stud or the name is Bethany (she has her
    own voice elsewhere). Tokens {t}/{sire} are filled."""
    if not sire_name or sire_name == "Bethany":
        return ""
    temperament = None
    for s in (getattr(character.db, "facility_studs", None) or []):
        if (s.get("name") or "") == sire_name:
            temperament = s.get("temperament")
            break
    pool = SIRE_TEMPERAMENTS.get(temperament)
    if not pool:
        return ""
    return random.choice(pool).format(t=t, sire=sire_name)


def stud_line(stud):
    """A short '<name>, <desc>' tag for prose, or '' if no stud."""
    if not stud:
        return ""
    return f"{stud.get('name')}, {stud.get('desc')}"


# Ambient lines for the Pens once the studs are penned there — the kennel comes alive.
PEN_AMBIENT = [
    "|gDown the run, one of the studs throws himself against his gate and the whole row takes "
    "it up — baying, snorting, stamping — settling only slowly back to a thick, waiting quiet.|n",
    "|gThe smell of the studs is everywhere in here: hot animal, rut, straw, the particular "
    "reek of a place where breeding is the only industry. It gets into the back of the throat.|n",
    "|gCaesar's chain rattles as he shifts and resettles, never quite taking his eyes off the "
    "stock; somewhere a younger hound whines, eager and unsubtle.|n",
    "|gA stud scents the air, finds something on it he likes, and a low eager sound rolls down "
    "the whole run — every penned beast suddenly, patiently attentive.|n",
]


def present_stud(room, species=None):
    """Return a named stud actually present in `room`, or None. Matches both Bethany's
    penned FacilityAnimal studs AND the resident's own matured get that have been put to
    stud (named, is_stud) — so her grown sons/futa daughters read as present studs too."""
    if not room:
        return None
    try:
        from typeclasses.facility_furniture import FacilityAnimal
    except Exception:
        FacilityAnimal = ()
    cands = []
    for o in room.contents:
        is_anim = isinstance(o, FacilityAnimal)
        is_get_stud = (getattr(o.db, "is_offspring", False)
                       and getattr(o.db, "matured", False)
                       and getattr(o.db, "is_stud", False))
        if not (is_anim or is_get_stud):
            continue
        if species is not None and getattr(o.db, "species", None) != species:
            continue
        cands.append(o)
    return random.choice(cands) if cands else None


def spawn_studs(room, owner, tagger=None):
    """Spawn the owner's named studs as real present FacilityAnimal creatures in `room`
    (the Pens). Idempotent — skips any stud already present by name. `tagger(obj)` (optional)
    tags each for realm teardown. Returns the count spawned."""
    if not room or not owner:
        return 0
    roster = ensure_studs(owner)
    try:
        from evennia.utils import create
        from typeclasses.facility_furniture import FacilityAnimal
    except Exception:
        return 0
    present_names = {(o.key or "").lower() for o in room.contents}
    spawned = 0
    for stud in roster:
        name = stud.get("name")
        if not name or name.lower() in present_names:
            continue
        try:
            a = create.create_object(FacilityAnimal, key=name, location=room)
            a.db.species   = stud.get("species", "hound")
            a.db.stud_desc = stud.get("desc", f"one of Bethany's {a.db.species}s.")
            a.db.is_stud   = True
            if tagger:
                tagger(a)
            spawned += 1
        except Exception:
            pass
    # Bring the run to life with kennel ambient (merge, don't duplicate).
    try:
        amb = list(getattr(room.db, "ambient_msgs", None) or [])
        for line in PEN_AMBIENT:
            if line not in amb:
                amb.append(line)
        room.db.ambient_msgs = amb
    except Exception:
        pass
    return spawned

