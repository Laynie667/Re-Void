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
