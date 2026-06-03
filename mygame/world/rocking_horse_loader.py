"""
world/rocking_horse_loader.py

Loads world/rocking_horse_messages.yaml and provides accessor functions.
"""

import os
import random

_DATA = None


def _load():
    global _DATA
    if _DATA is None:
        path = os.path.join(os.path.dirname(__file__), "rocking_horse_messages.yaml")
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                _DATA = yaml.safe_load(f) or {}
        except Exception as e:
            from evennia.utils import logger
            logger.log_err(f"rocking_horse_loader: failed to load {path}: {e}")
            _DATA = {}
    return _DATA


def get_horse_config(pace: str) -> dict:
    """Return {interval_seconds, arousal_per_tick} for the given pace."""
    data = _load()
    cfg  = data.get("speeds", {}).get(pace, {})
    return {
        "interval_seconds": cfg.get("interval_seconds", 45),
        "arousal_per_tick": cfg.get("arousal_per_tick", 6.0),
    }


def pick_horse_msg(pace_or_section: str, pool: str) -> str | None:
    """
    Return a random message from speeds[pace][pool] or upgrade[pool].

    Args:
        pace_or_section: "slow"/"steady"/"fast"/"intense" or "upgrade"
        pool: "start"/"running"/"stop" or upgrade key
    """
    data = _load()
    if pace_or_section == "upgrade":
        msgs = data.get("upgrade", {}).get(pool, [])
    else:
        msgs = (
            data.get("speeds", {})
                .get(pace_or_section, {})
                .get(pool, [])
        )
    return random.choice(msgs) if msgs else None
