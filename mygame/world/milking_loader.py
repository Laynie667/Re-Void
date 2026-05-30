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
        ml  = entry.get("ml", 0)
        msgs = entry.get("messages", [])
        if msgs:
            result.append((ml, msgs))
    result.sort(key=lambda x: x[0])
    return result
