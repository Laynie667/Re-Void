"""
world/maze.py — combination-lock / "Lost Woods" room logic (pure, testable).

A maze room has one or more SOLUTIONS: named sequences of directional moves
(e.g. {"deeper": ["north","north","east","west"]}). A traveller's moves are
tracked per-character; completing a solution's sequence reveals its destination.
Everything else fires a decoy so it *feels* like you moved and got lost.

This module holds only the sequence math + decoy picking so it can be unit-tested
without Evennia. `typeclasses/maze_room.py` is the thin in-game wrapper.
"""

import random

# Canonical directions and their short aliases.
DIRECTIONS = {
    "north": ["n"], "south": ["s"], "east": ["e"], "west": ["w"],
    "northeast": ["ne"], "northwest": ["nw"],
    "southeast": ["se"], "southwest": ["sw"],
    "up": ["u"], "down": ["d"], "in": ["enter"], "out": ["exit", "leave"],
}

_ALIAS_TO_DIR = {a: d for d, al in DIRECTIONS.items() for a in al}


def normalize_direction(word):
    """Map an alias ('n', 'ne') or full name to its canonical direction, or None."""
    w = (word or "").strip().lower()
    if w in DIRECTIONS:
        return w
    return _ALIAS_TO_DIR.get(w)


def evaluate_move(seq, direction, solutions, reset_on_wrong=True):
    """Core combination check.

    seq         — list[str] of the traveller's moves so far (this room visit).
    direction   — the canonical direction just entered.
    solutions   — dict name -> list[str] sequence.
    reset_on_wrong — True = classic Lost Woods (any deviation drops you back to the
                  start of the combo); False = forgiving (match a trailing run, the
                  sequence just slides).

    Returns (new_seq, matched_name|None). When a solution completes, new_seq is [].
    """
    sols = {n: list(s) for n, s in (solutions or {}).items() if s}
    if not sols:
        return ([], None) if reset_on_wrong else (list(seq) + [direction], None)

    if reset_on_wrong:
        candidate = list(seq) + [direction]
        # Completed a full solution from the start?
        for name, s in sols.items():
            if candidate == s:
                return [], name
        # Still a viable prefix of some solution? keep building.
        if any(s[:len(candidate)] == candidate for s in sols.values()):
            return candidate, None
        # Deviated — drop back to start, but this very move might itself begin
        # (or be) a one-step solution.
        restart = [direction]
        for name, s in sols.items():
            if s == restart:
                return [], name
        if any(s[:1] == restart for s in sols.values()):
            return restart, None
        return [], None

    # Forgiving: match a trailing run; cap growth to the longest solution.
    candidate = list(seq) + [direction]
    for name, s in sols.items():
        if len(candidate) >= len(s) and candidate[-len(s):] == s:
            return [], name
    maxlen = max(len(s) for s in sols.values())
    if len(candidate) > maxlen:
        candidate = candidate[-maxlen:]
    return candidate, None


def pick_decoy(pool, direction, rng=random):
    """Pick a decoy line from the pool, substituting {dir}. Returns "" if pool empty."""
    if not pool:
        return ""
    line = rng.choice(list(pool))
    return line.replace("{dir}", direction)


def describe_solution(sequence):
    """Human-readable form of a solution sequence, for map/hint items."""
    return ", ".join(d.upper() for d in (sequence or []))
