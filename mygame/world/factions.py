"""
world/factions.py

A lightweight faction/standing system, with The Facility as a real faction
fully integrated into titles and the sheet.

Standing accrues SLOWLY from facility activity (breeding, milking, cycles,
compliance) so progression is a true slow burn — the grades take a long time.
Standing per faction lives in character.db.factions = {name: int}. The Facility
faction's standing drives her grade, her title (faction + suffix), and shows on
the sheet via the 'standing' command.
"""

FACILITY = "The Facility"

# (min_standing, grade_name, title_text)
_FACILITY_TIERS = [
    (0,    "Unprocessed",         ""),
    (40,   "Intake",              "an Intake"),
    (150,  "Breaking In",         "Breaking-In Stock"),
    (400,  "Breeding Stock",      "Breeding Stock"),
    (900,  "Broodmare",           "a Broodmare"),
    (1800, "Perfected Livestock", "Perfected Livestock"),
]

# Roughly how slow: at a few points per cycle-phase and a phase every ~3 min,
# Perfected (1800) is dozens of hours of processing — many sessions deep.
_GAIN = {
    "breed": 2.0, "milk": 1.0, "condition": 1.5, "cycle": 1.0,
    "comply": 1.0, "grade": 5.0, "drug": 2.0, "procedure": 4.0,
}


def add_standing(character, source="cycle", amount=None, faction=FACILITY):
    """Add facility standing (slow). `source` keys a default amount, or pass amount."""
    if not character:
        return 0
    amt = float(amount if amount is not None else _GAIN.get(source, 1.0))
    factions = dict(getattr(character.db, "factions", None) or {})
    new = int(factions.get(faction, 0)) + int(round(amt))
    factions[faction] = new
    character.db.factions = factions
    _apply_facility_title(character, new)
    return new


def get_standing(character, faction=FACILITY):
    return int((getattr(character.db, "factions", None) or {}).get(faction, 0))


def get_facility_tier(character):
    """Return (grade_name, title_text) for current Facility standing."""
    s = get_standing(character)
    name, title = _FACILITY_TIERS[0][1], _FACILITY_TIERS[0][2]
    for thresh, n, ttl in _FACILITY_TIERS:
        if s >= thresh:
            name, title = n, ttl
    return name, title


def next_threshold(character):
    """Standing needed for the next grade, or None at max."""
    s = get_standing(character)
    for thresh, n, ttl in _FACILITY_TIERS:
        if s < thresh:
            return thresh, n
    return None, None


def seed_facility_title(character):
    """
    Stamp the faction title slots the moment she signs, before she's accrued
    any standing — she is Facility property now, grade not-yet-processed. This
    makes the (faction) part of her title render immediately on the sheet.
    Backed up + restored by the same reset/force_clear path as a graded title.
    """
    if not character:
        return
    if not getattr(character.db, "facility_title_backup", None):
        character.db.facility_title_backup = {
            "faction": getattr(character.db, "title_faction", "") or "",
            "suffix":  getattr(character.db, "title_suffix", "") or "",
        }
    character.db.title_faction = "of The Facility"
    # Only seed the suffix if standing hasn't already set a real grade suffix.
    if not (getattr(character.db, "title_suffix", "") or "").startswith("—"):
        character.db.title_suffix = "— Resident"
    if not getattr(character.db, "facility_grade", None):
        character.db.facility_grade = "Unprocessed"


def _apply_facility_title(character, standing):
    name, title = get_facility_tier(character)
    if name == "Unprocessed":
        # Still stamp the faction slot so signed-but-ungraded stock reads as
        # property; the grade suffix fills in once she crosses Intake (40).
        seed_facility_title(character)
        return
    # Back up her real title once, restored by reset/force_clear.
    if not getattr(character.db, "facility_title_backup", None):
        character.db.facility_title_backup = {
            "faction": getattr(character.db, "title_faction", "") or "",
            "suffix":  getattr(character.db, "title_suffix", "") or "",
        }
    character.db.title_faction = "of The Facility"
    character.db.title_suffix  = (f"— {title}" if title else "")
    character.db.facility_grade = name
