"""
world/cah_loader.py

Loads and merges Cards Against Re:Void decks from YAML files.

Usage:
    from world.cah_loader import load_decks, list_decks
    black_cards, white_cards = load_decks(["base", "nsfw", "revoid"])

Each black card is a dict: {"text": str, "pick": int}
Each white card is a str.
"""

import os
import random

try:
    import yaml
except ImportError:
    yaml = None

DECK_DIR = os.path.join(os.path.dirname(__file__), "cah")

DECK_REGISTRY = {
    "base": {
        "black": "base_black.yaml",
        "white": "base_white.yaml",
        "description": "Classic CAH-style general humor",
    },
    "nsfw": {
        "black": "nsfw_black.yaml",
        "white": "nsfw_white.yaml",
        "description": "Adult content expansion",
    },
    "revoid": {
        "black": "revoid_black.yaml",
        "white": "revoid_white.yaml",
        "description": "ReVoid world-themed cards",
    },
}

DEFAULT_DECKS = ["base", "nsfw", "revoid"]


def _load_yaml_file(filepath):
    """
    Load a YAML file and return its parsed content.
    Returns None if the file does not exist or yaml is unavailable.
    """
    if yaml is None:
        raise ImportError(
            "PyYAML is not installed. Run: pip install pyyaml"
        )
    if not os.path.isfile(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_deck(deck_name):
    """
    Load a single named deck by its registry key.

    Returns:
        (black_list, white_list) where:
            black_list is a list of dicts: [{"text": str, "pick": int}, ...]
            white_list is a list of strings: [str, ...]

    Raises:
        KeyError if deck_name is not in DECK_REGISTRY.
        ImportError if PyYAML is not installed.

    If a YAML file is missing or empty, returns an empty list for that side.
    """
    if deck_name not in DECK_REGISTRY:
        raise KeyError(
            f"Unknown deck '{deck_name}'. Available: {list(DECK_REGISTRY.keys())}"
        )

    entry = DECK_REGISTRY[deck_name]
    black_list = []
    white_list = []

    # Load black cards
    black_path = os.path.join(DECK_DIR, entry["black"])
    black_data = _load_yaml_file(black_path)
    if black_data and "cards" in black_data:
        for card in black_data["cards"]:
            if isinstance(card, dict):
                text = card.get("text", "").strip()
                pick = int(card.get("pick", 1))
                if text:
                    black_list.append({"text": text, "pick": pick})
            elif isinstance(card, str) and card.strip():
                # Fallback: plain string black card treated as pick 1
                black_list.append({"text": card.strip(), "pick": 1})

    # Load white cards
    white_path = os.path.join(DECK_DIR, entry["white"])
    white_data = _load_yaml_file(white_path)
    if white_data and "cards" in white_data:
        for card in white_data["cards"]:
            if isinstance(card, str) and card.strip():
                white_list.append(card.strip())
            elif isinstance(card, dict):
                # Handle accidental dict format for white cards
                text = card.get("text", "").strip()
                if text:
                    white_list.append(text)

    return black_list, white_list


def load_decks(deck_names=None):
    """
    Load and merge multiple named decks.

    Args:
        deck_names: list of deck name strings, or None to use DEFAULT_DECKS.

    Returns:
        (black_list, white_list) — merged, deduplicated, and shuffled.
        black_list: [{"text": str, "pick": int}, ...]
        white_list: [str, ...]

    Decks are loaded in order. Duplicate card texts are silently dropped.
    Both lists are shuffled before being returned.
    """
    if deck_names is None:
        deck_names = DEFAULT_DECKS

    seen_black = set()
    seen_white = set()
    all_black = []
    all_white = []

    for name in deck_names:
        name = name.strip().lower()
        if name not in DECK_REGISTRY:
            # Skip unknown decks with a warning rather than crashing
            import sys
            print(
                f"[cah_loader] WARNING: Unknown deck '{name}' skipped.",
                file=sys.stderr,
            )
            continue
        try:
            blacks, whites = load_deck(name)
        except Exception as exc:
            import sys
            print(
                f"[cah_loader] ERROR loading deck '{name}': {exc}",
                file=sys.stderr,
            )
            continue

        for card in blacks:
            key = card["text"].lower()
            if key not in seen_black:
                seen_black.add(key)
                all_black.append(card)

        for card in whites:
            key = card.lower()
            if key not in seen_white:
                seen_white.add(key)
                all_white.append(card)

    random.shuffle(all_black)
    random.shuffle(all_white)

    return all_black, all_white


def list_decks():
    """
    Return a dict mapping deck names to their description strings.

    Example:
        {
            "base": "Classic CAH-style general humor",
            "nsfw": "Adult content expansion",
            "revoid": "ReVoid world-themed cards",
        }
    """
    return {name: info["description"] for name, info in DECK_REGISTRY.items()}


def deck_card_counts(deck_names=None):
    """
    Return a dict of {deck_name: {"black": int, "white": int}} for the given decks.
    Useful for display/diagnostic purposes.
    """
    if deck_names is None:
        deck_names = list(DECK_REGISTRY.keys())

    counts = {}
    for name in deck_names:
        name = name.strip().lower()
        if name not in DECK_REGISTRY:
            continue
        try:
            blacks, whites = load_deck(name)
            counts[name] = {"black": len(blacks), "white": len(whites)}
        except Exception:
            counts[name] = {"black": 0, "white": 0}
    return counts
