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

# Bethany's standing studs — her favourites, kept and bred into her stock.
DEFAULT_STUDS = [
    {"name": "Caesar",  "species": "hound",
     "desc": "Bethany's prize stud hound — a huge, scarred brute with a fist-fat knot and a "
             "patient, working temperament; he's put more litters in the stock than any three "
             "of the others, and he knows the smell of a presented hole on sight."},
    {"name": "Duke",    "species": "hound",
     "desc": "a lean, tireless young hound coming up in Caesar's place — quick to mount, slow "
             "to soften, and far too clever about finding a hole that can't get away from him."},
    {"name": "Brutus",  "species": "bull",
     "desc": "Bethany's herd bull — a mountain of muscle and weight, slow and inexorable, the "
             "kind of breeding that reshapes what it's put into and doesn't notice it has."},
    {"name": "Goliath", "species": "boar",
     "desc": "the stud boar — blunt, filthy, relentless, with a corkscrew flare that screws "
             "deep and locks, and an appetite for breeding that genuinely never seems to flag."},
    {"name": "Sultan",  "species": "stallion",
     "desc": "Bethany's stallion — obscene in length and girth, flared like a fist at the head, "
             "the sort of stud you have to be held open and steady for or he'll simply ruin you."},
]


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


def add_stud(character, name, species, desc=""):
    """Add a named stud to the roster (or update an existing one of that name)."""
    roster = ensure_studs(character)
    for s in roster:
        if (s.get("name") or "").lower() == (name or "").lower():
            s["species"] = species
            if desc:
                s["desc"] = desc
            character.db.facility_studs = roster
            return s
    entry = {"name": name, "species": species, "desc": desc or f"one of Bethany's {species}s"}
    roster.append(entry)
    character.db.facility_studs = roster
    return entry


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

