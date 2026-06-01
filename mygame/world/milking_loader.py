"""
world/milking_loader.py

Loads and caches milking_messages.yaml, providing simple accessor functions
used by the session script and production item threshold system.

All message lists are loaded once on first import and cached. The cache is
invalidated on server reload (module re-import).
"""

import os
import random

_DATA = None


def _load():
    global _DATA
    if _DATA is None:
        path = os.path.join(os.path.dirname(__file__), "milking_messages.yaml")
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                _DATA = yaml.safe_load(f)
        except Exception as e:
            from evennia.utils import logger
            logger.log_err(f"milking_loader: failed to load {path}: {e}")
            _DATA = {"speeds": {}, "fullness": {"thresholds": []}}
    return _DATA


def get_speed_config():
    """
    Return a dict of speed → {interval_seconds, ml_per_session_tick}.

    Example:
        {"slow": {"interval_seconds": 60, "ml_per_session_tick": 4.0}, ...}
    """
    data = _load()
    result = {}
    for speed, cfg in data.get("speeds", {}).items():
        result[speed] = {
            "interval_seconds":    cfg.get("interval_seconds",    30),
            "ml_per_session_tick": cfg.get("ml_per_session_tick", 10.0),
        }
    return result


def pick_message(speed: str, pool: str) -> str | None:
    """
    Return a random message from the given speed/pool, or None if empty.

    Args:
        speed: "slow", "steady", "fast", or "intense"
        pool:  "start", "running", "first_empty", "running_empty", or "stop"
    """
    data = _load()
    messages = (
        data.get("speeds", {})
            .get(speed, {})
            .get(pool, [])
    )
    if not messages:
        return None
    return random.choice(messages)


def get_fullness_thresholds():
    """
    Return a list of (ml_threshold, messages_list) tuples, sorted ascending.

    Example:
        [(100, ["A faint awareness..."]), (300, [...]), ...]
    """
    data = _load()
    thresholds = data.get("fullness", {}).get("thresholds", [])
    result = []
    for entry in thresholds:
        ml   = entry.get("ml", 0)
        msgs = entry.get("messages", [])
        if msgs:
            result.append((ml, msgs))
    result.sort(key=lambda x: x[0])
    return result


def get_size_ambient_tiers():
    """
    Return size ambient tiers sorted descending by min_size (highest first).
    Each entry: (min_size, messages_list).
    Caller should find the first (highest) matching tier and roll for chance.

    Example:
        [(38.0, [...]), (34.0, [...]), (30.0, [...]), ...]
    """
    data = _load()
    tiers = data.get("size_ambient", {}).get("tiers", [])
    result = []
    for entry in tiers:
        min_size = entry.get("min_size", 0.0)
        msgs     = entry.get("messages", [])
        if msgs:
            result.append((min_size, msgs))
    result.sort(key=lambda x: x[0], reverse=True)
    return result


def pick_phase_message(phase: str) -> str | None:
    """
    Return a random message from the priming or tapering phase pool.
    phase: "priming" | "tapering"
    """
    data = _load()
    messages = data.get("phases", {}).get(phase, [])
    if not messages:
        return None
    return random.choice(messages)


def pick_arousal_threshold_message(threshold: float) -> str | None:
    """Return a private threshold message for the given arousal value (75/90/95)."""
    data  = _load()
    items = data.get("arousal", {}).get("thresholds", [])
    for entry in items:
        if entry.get("value") == threshold:
            msgs = entry.get("messages", [])
            if msgs:
                return random.choice(msgs)
    return None


def pick_climax_message() -> str | None:
    """Return a room-visible climax message (uses {target} token)."""
    data  = _load()
    msgs  = data.get("arousal", {}).get("climax", [])
    return random.choice(msgs) if msgs else None


def pick_deposit_message(deposit_type: str) -> str | None:
    """
    deposit_type: "surface_deposit" | "internal_deposit"
    Returns a message string using {actor}, {target}, {zone}, {surface} tokens.
    """
    data = _load()
    msgs = data.get("arousal", {}).get(deposit_type, [])
    return random.choice(msgs) if msgs else None


def get_leaking_conditions():
    """
    Return leaking conditions sorted descending by min_size (highest first).
    Each entry: (min_size, min_volume, messages_list, room_visible).
    Caller should find the first matching condition and fire.

    Example:
        [(38.0, 0, [...], True), (34.0, 0, [...], True), ...]
    """
    data = _load()
    conditions = data.get("leaking", {}).get("conditions", [])
    result = []
    for entry in conditions:
        min_size   = entry.get("min_size",   0.0)
        min_vol    = entry.get("min_volume", 0.0)
        msgs       = entry.get("messages",   [])
        room_vis   = entry.get("room_visible", False)
        if msgs:
            result.append((min_size, min_vol, msgs, room_vis))
    result.sort(key=lambda x: x[0], reverse=True)
    return result
