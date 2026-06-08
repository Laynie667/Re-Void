"""
world/transformation.py — an incremental, thresholded body-transformation framework.

Inspired by TiTS / Flexible Survival / TrapQuest: a body change is not a one-off, it's a
TRACK you push along by repeated doses, crossing STAGES that rewrite how the part reads.
State lives on the character as `db.body_parts = {track: level}`; crossing a stage threshold
fires a transformation beat and records a real permanent mark (so it shows in `marks`).

Nothing here touches the OOC floor: `escape`/`force_clear`/`facilityreset` clear
`db.body_parts` (it's in FACILITY_FLAGS) along with everything else.

Public API:
    apply_tf(char, track, amount=1.0) -> (crossed_stage: bool, message: str)
    body_summary(char) -> list[str]            # human-readable current stages
    body_level(char, track) -> float
    TRACKS                                     # the registry
"""

import random

# Each track: ordered stages as (min_level, short_label, body-line shown in `body`/marks).
# Stage 0 is the baseline (level < next threshold). Pushing the level up crosses stages.
TRACKS = {
    "cock": [
        (0,  "none",            "no cock to speak of"),
        (2,  "forming",         "a thickening cock, fuller and heavier than it was"),
        (4,  "stallion",        "a long, stallion-flared cock that fills a hand"),
        (6,  "knotted",         "a knotted breeding cock — flared at the head, swelling at the base"),
        (9,  "monstrous",       "a monstrous breeding cock, knotted and flared and far too big to ignore"),
    ],
    "balls": [
        (0,  "none",            "nothing heavy below"),
        (2,  "heavy",           "a heavy, low-hanging sac"),
        (4,  "swollen",         "swollen, aching balls that never quite empty"),
        (7,  "fist-sized",      "fist-sized balls holding a standing load, always full"),
    ],
    "breasts": [
        (0,  "flat",            "a flat or modest chest"),
        (2,  "full",            "full, soft breasts"),
        (4,  "heavy",           "heavy, swinging tits"),
        (6,  "huge",            "huge, milk-fat breasts that get in the way"),
        (9,  "udders",          "monstrous dairy udders, hanging and swaying with every move"),
    ],
    "lips": [
        (0,  "normal",          "an ordinary mouth"),
        (3,  "plump",           "plumped, kiss-swollen lips"),
        (6,  "bimbo",           "pillowy, permanently pouted cocksucker lips"),
    ],
    "clit": [
        (0,  "normal",          "an ordinary clit"),
        (3,  "enlarged",        "a swollen, oversized clit that won't be ignored"),
        (6,  "cocklet",         "a stiff little cock-clit, always up and aching"),
    ],
    "ass": [
        (0,  "normal",          "an ordinary backside"),
        (3,  "full",            "fuller, rounder hips"),
        (6,  "breeding",        "wide breeding hips and a thick, presented ass"),
    ],
    "lactation": [
        (0,  "dry",             "dry"),
        (2,  "leaking",         "leaking, prone to letting down"),
        (4,  "producer",        "a heavy producer, always filling"),
        (7,  "never-dry",       "never dry — milked or not, the udders refill"),
    ],
    "feral": [
        (0,  "human",           "wholly human"),
        (3,  "marked",          "animal features creeping in — the eyes, the ears, the gait"),
        (6,  "half",            "half-feral, more bred-animal than person now"),
        (9,  "beast",           "a bred-animal frame, the human left mostly behind"),
    ],
}


def _stage_index(track, level):
    stages = TRACKS.get(track) or []
    idx = 0
    for i, (thr, _lbl, _desc) in enumerate(stages):
        if level >= thr:
            idx = i
    return idx


# Tracks that ADD a fundamental part/identity from baseline (vs merely scaling something
# a body already has). Players choose these for themselves; another player can only SCALE a
# part you already have, never give you one you didn't pick. The facility/owner can do anything.
ADD_PART_TRACKS = {"cock", "feral"}


def body_level(char, track):
    return float((getattr(char.db, "body_parts", None) or {}).get(track, 0) or 0)


def apply_tf(char, track, amount=1.0, allow_add=True):
    """Push `track` by `amount` (negative shrinks). If it crosses into a new stage, records a
    permanent mark and returns (True, message); else (False, a small creep message).

    `allow_add=False` (player-to-player, and self-drugs that only scale): refuses to bring an
    ADD_PART track up from baseline — you can grow/shrink/force what a body HAS, but you can't
    give someone a part they didn't choose. The facility/owner pass allow_add=True (it's not up
    to the stock). Unknown tracks / blocked adds return (False, message). Never touches the floor."""
    if not char or track not in TRACKS:
        return False, ""
    parts = dict(getattr(char.db, "body_parts", None) or {})
    before = float(parts.get(track, 0) or 0)
    # Guard: don't let one player ADD a fundamental part to another from nothing.
    if (not allow_add) and track in ADD_PART_TRACKS and before <= 0 and amount > 0:
        t = char.db.rp_name or char.key
        return False, (f"|x{t} doesn't have that to scale — and adding a part they didn't choose "
                       f"isn't yours to do. (Scaling what they have is fine; the rest is theirs, or "
                       f"the facility's.)|n")
    after = max(0.0, before + float(amount))
    parts[track] = after
    char.db.body_parts = parts
    bi, ai = _stage_index(track, before), _stage_index(track, after)
    stages = TRACKS[track]
    t = char.db.rp_name or char.key
    if ai != bi:
        _lbl = stages[ai][1]
        desc = stages[ai][2]
        crossed_up = ai > bi
        verb = "swells and reshapes into" if crossed_up else "subsides toward"
        msg = (f"|G{t}'s body {verb} {desc}. The change settles in and stays — it reads on her "
               f"now, for anyone who looks.|n")
        # Real permanent mark so it shows in marks/brands.
        try:
            from world.gang_breeding import record_mark
            record_mark(char, f"body reshaped — {track}: {desc}", mode="on")
        except Exception:
            pass
        return True, msg
    # No stage change — just a creep.
    return False, (f"|gSomething shifts in {t}'s body — {track} pushed a little further along, not "
                   f"yet enough to remake it, but headed there.|n")


def body_summary(char):
    """Human-readable current stage of every non-baseline track (for a `body` view)."""
    parts = dict(getattr(char.db, "body_parts", None) or {})
    out = []
    for track, stages in TRACKS.items():
        lvl = float(parts.get(track, 0) or 0)
        idx = _stage_index(track, lvl)
        if idx == 0:
            continue   # baseline — don't clutter
        out.append(f"  |c{track}:|n {stages[idx][2]} |x(lvl {lvl:g})|n")
    return out
