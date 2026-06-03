"""
world/processing.py — the facility's processing tiers.

The whole experience has an arc. A composite score (conditioning + total hole
use + brood + permanence) grades the subject through named tiers. The facility
reads the tier to escalate: harsher scene weighting, deeper conditioning gain,
a colder/more possessive Process, and a one-time "processing review" set-piece
each time she's re-graded upward.

Cleared by purge (tier resets with the rest of the state).
"""

# (min_score, name, one-line state)
_TIERS = [
    (0,   "Intake",              "fresh, mostly intact, still saying no with her whole face"),
    (45,  "Breaking In",         "cracking — the no's getting quieter, the body getting louder"),
    (110, "Breeding Stock",      "signed, bred, and producing; a useful animal now"),
    (210, "Broodmare",           "deep in it, leaking and heavy-bellied, breeding her own line back into herself"),
    (360, "Perfected Livestock", "finished — no name, ruined holes, an obedient hole-and-udder kept to the schedule"),
]


def tier_score(target):
    d = target.db
    cond  = float(getattr(d, "conditioning", 0) or 0)
    use   = sum(int(h.get("use", 0)) for h in (getattr(d, "holes", None) or {}).values())
    brood = sum(int(v) for v in (getattr(d, "offspring_counts", None) or {}).values())
    score = cond + use * 1.5 + brood * 8.0
    if getattr(d, "conditioning_permanent", False):
        score += 40
    score += 15 * len(getattr(d, "permanent_gape", None) or [])
    score += 8  * len(getattr(d, "piercings", None) or [])
    return score


def processing_tier(target):
    """Return (level:int, name:str, state:str)."""
    s = tier_score(target)
    lvl, name, state = 0, _TIERS[0][1], _TIERS[0][2]
    for i, (thresh, n, st) in enumerate(_TIERS):
        if s >= thresh:
            lvl, name, state = i, n, st
    return lvl, name, state
