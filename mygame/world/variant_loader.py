"""
world/variant_loader.py

Loads world/variant_pools.yaml and provides pick functions for all pools.
"""

import os
import random

_DATA = None


def _load():
    global _DATA
    if _DATA is None:
        path = os.path.join(os.path.dirname(__file__), "variant_pools.yaml")
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                _DATA = yaml.safe_load(f) or {}
        except Exception as e:
            from evennia.utils import logger
            logger.log_err(f"variant_loader: failed to load {path}: {e}")
            _DATA = {}
    return _DATA


def pick_pet_beg(pet_type: str, msg_type: str = "pose") -> str | None:
    """Pick a beg message for the given pet type. msg_type: 'say' | 'pose'"""
    data = _load()
    pool = (
        data.get("pet_beg", {})
            .get(pet_type, data.get("pet_beg", {}).get("puppy", {}))
            .get(msg_type, [])
    )
    return random.choice(pool) if pool else None


def pick_shaft_worship(shaft_type: str, msg_type: str = "pose") -> str | None:
    """Pick a shaft-worship message. shaft_type: canine/equine/porcine/draconic"""
    data = _load()
    pool = (
        data.get("shaft_worship", {})
            .get(shaft_type, data.get("shaft_worship", {}).get("canine", {}))
            .get(msg_type, [])
    )
    return random.choice(pool) if pool else None


def pick_testes_worship(msg_type: str = "pose") -> str | None:
    """Pick a testes-worship message. msg_type: 'say' | 'pose'"""
    data = _load()
    pool = data.get("testes_worship", {}).get(msg_type, [])
    return random.choice(pool) if pool else None


def pick_self_pleasure(variant: str = "general", msg_type: str = "pose") -> str | None:
    """Pick a self-pleasure pose. variant: general/canine/equine/testes_fixation"""
    data = _load()
    pool = (
        data.get("self_pleasure", {})
            .get(variant, data.get("self_pleasure", {}).get("general", {}))
            .get(msg_type, [])
    )
    return random.choice(pool) if pool else None


def pick_collar_beg(collar_variant: str, msg_type: str = "pose") -> str | None:
    """Pick a collar-specific beg message. collar_variant: leather_puppy/silk_kitty/etc."""
    data  = _load()
    pools = data.get("collar_beg", {})
    pool  = (
        pools.get(collar_variant, pools.get("leather_puppy", {}))
             .get(msg_type, [])
    )
    return random.choice(pool) if pool else None
