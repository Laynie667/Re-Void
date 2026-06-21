"""
world/zone_types.py — the typed zone/slot foundation (character-zones.md spine).

A character/room zone carries a ``zone_type``. Installable upgrades/functions/items
declare which zone-type(s) they may attach to, so the system can refuse nonsense
(no lactation on lips, no WombRoom on a wrist). This generalizes WombRoom's original
"orifice/both only" install check into one shared, reusable validator.

Backward-compatible by design:
  * zones without an explicit ``zone_type`` default to ``"surface"`` (as WombRoom did);
  * the legacy ``"both"`` value (which predates the typed split, and which WombRoom
    accepted alongside ``"orifice"``) is treated as orifice + appendage;
  * an upgrade the catalogue hasn't classified is *permitted* (permissive) so this
    never blocks installs that existed before they were typed;
  * every public call is fail-safe (any error → allow), never trapping a build.
"""

# The canonical zone types (character-zones.md §2).
ZONE_TYPES = ("surface", "gland", "orifice", "appendage")

# Legacy aliases expanded to canonical types. 'both' predates the split.
_LEGACY = {"both": ("orifice", "appendage")}

# What each installable upgrade/function is valid on (character-zones.md §2).
# Keys are upgrade names; values are the set of zone-types that accept them.
UPGRADE_VALID_TYPES = {
    # orifice work
    "womb_room":   {"orifice"},
    "inflation":   {"orifice"},
    "gape":        {"orifice"},
    "capacity":    {"orifice"},
    # gland work
    "lactation":   {"gland"},
    "production":  {"gland"},
    "milk":        {"gland"},
    # appendage work
    "knot":        {"appendage"},
    "variant":     {"appendage"},          # equine/porcine/draconic shaping
    # surface work
    "mark":        {"surface"},
    "tattoo":      {"surface"},
    "brand":       {"surface"},
    # broad
    "growth":      {"gland", "appendage"},
    "sensitivity": set(ZONE_TYPES),        # anything can be sensitized
}


def zone_type_of(zone_data):
    """The zone's declared type, defaulting to 'surface'. Tolerates None / non-dict."""
    if not zone_data or not hasattr(zone_data, "get"):
        return "surface"
    return (zone_data.get("zone_type") or "surface").lower()


def _effective_types(zone_type):
    """Expand legacy aliases (e.g. 'both' → orifice+appendage) to a set of canon types."""
    if zone_type in _LEGACY:
        return set(_LEGACY[zone_type])
    return {zone_type}


def accepts(zone_data, upgrade):
    """True if `upgrade` may attach to this zone (by type). An upgrade the catalogue
    doesn't list is permitted (permissive). Fail-safe: any error → True."""
    try:
        valid = UPGRADE_VALID_TYPES.get(upgrade)
        if valid is None:
            return True
        return bool(_effective_types(zone_type_of(zone_data)) & set(valid))
    except Exception:
        return True


def install_error(zone_name, zone_data, upgrade):
    """A standard refusal message if the install is invalid, else '' (allowed)."""
    if accepts(zone_data, upgrade):
        return ""
    valid = ", ".join(sorted(UPGRADE_VALID_TYPES.get(upgrade, set()))) or "?"
    return (f"'{upgrade}' can only attach to a {valid} zone; "
            f"'{zone_name}' is type '{zone_type_of(zone_data)}'.")
