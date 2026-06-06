"""
world/realms.py

Realm + Faction registries — Phase 1 foundation.

A *realm* is a named area owned by a *faction*. Rooms carry `room.db.realm`
(affiliation) and, only when a sub-faction holds a specific room, a
`room.db.faction` override. Everything built later — unified titles, per-realm
currencies, membership/invites, the website faction/realm pages and portraits —
reads off these helpers, so this module is the single source of truth.

This is the FOUNDATION only: registries, room stamps, lookups. Ranks,
multi-currency wallets, membership, and unified titles layer on top in later
phases. The existing `world/factions.py` (Facility standing/grade) is untouched;
it'll be reconciled into this registry when titles are generalised (Phase 2).
"""

DEFAULT_REALM   = "void"
DEFAULT_FACTION = "void"

# Cap on a single flood-fill, so a runaway stamp can't paint the whole grid.
FLOOD_CAP = 200


# ── Faction registry ──────────────────────────────────────────────────────────
# kind:    neutral | guild | family | realm | sub   (a 'sub' points at a parent)
# advance: granted | rep | points | quest           (used by the later rank phase)
# ranks:   ordered list of rank names (low -> high); [] = no ranks (neutral)
FACTIONS = {
    "void": {
        "name": "The Void", "kind": "neutral", "parent": None,
        "colour": "|w", "invite_only": False, "currency": "shards",
        "leader": None, "advance": "rep", "ranks": [],
        "blurb": "The neutral commons — the hub and the spaces between. Owned by no one, "
                 "kept by a distant, disinterested custodian.",
    },
    "facility": {
        "name": "The Facility", "kind": "realm", "parent": None,
        "colour": "|m", "invite_only": True, "currency": "scrip",
        "leader": "Bethany", "advance": "rep", "ranks": [],
        "blurb": "A consensual livestock-processing operation. Owns its realm and takes a "
                 "piece of the product as its own.",
    },
    "helena": {
        "name": "House Helena", "kind": "family", "parent": None,
        "colour": "|c", "invite_only": True, "currency": "shards",
        "leader": "Helena", "advance": "granted", "ranks": [],
        "blurb": "Helena's house, and the wood it keeps.",
    },
}

# ── Realm registry ──────────────────────────────────────────────────────────
# currencies: always effectively includes 'shards'; may add a realm-local one.
# housing: whether members may link personal housing onto this realm's grid.
# Currency config per realm (governing faction's call, editable in-game later):
#   currencies     : currency keys valid here (shards is global tender by default)
#   local_currency : this realm's own currency key, or None
#   accepts_shards : do this realm's shops take outside shards? (faction may opt out)
#   exchange_rate  : shards per 1 unit of the local currency; 0/None = NO exchange
#                    (realms opt IN to convertibility — local money is sovereign by default)
REALMS = {
    "void": {
        "name": "The Void", "faction": "void", "housing": True,
        "currencies": ["shards"], "local_currency": None,
        "accepts_shards": True, "exchange_rate": 0,
        "blurb": "The semi-fantasy/medieval commons — Durgin's shop, the Wayfarers' Hall, "
                 "the post office, and the void threaded between.",
    },
    "facility": {
        "name": "The Facility", "faction": "facility", "housing": False,
        "currencies": ["shards", "scrip"], "local_currency": "scrip",
        "accepts_shards": True, "exchange_rate": 0,
        "blurb": "The disconnected processing grid, reached only by waystone.",
    },
    "wildwood": {
        "name": "Helena's Wood", "faction": "helena", "housing": True,
        "currencies": ["shards"], "local_currency": None,
        "accepts_shards": True, "exchange_rate": 0,
        "blurb": "A forested, snow-touched valley under House Helena. (Cabin moves here.)",
    },
}


# ── Lookups ───────────────────────────────────────────────────────────────────
def get_faction(key):
    return FACTIONS.get((key or "").lower())


def get_realm(key):
    return REALMS.get((key or "").lower())


def faction_name(key):
    f = get_faction(key)
    return f["name"] if f else (key or "")


def realm_name(key):
    r = get_realm(key)
    return r["name"] if r else (key or "")


def room_realm(room):
    """The realm key a room belongs to (unstamped rooms default to the Void)."""
    try:
        return (getattr(room.db, "realm", None) or DEFAULT_REALM)
    except Exception:
        return DEFAULT_REALM


def room_faction(room):
    """The faction controlling a room: an explicit `room.db.faction` override, else
    the owning faction of the room's realm."""
    try:
        override = getattr(room.db, "faction", None)
        if override:
            return override
    except Exception:
        pass
    realm = get_realm(room_realm(room))
    return (realm.get("faction") if realm else DEFAULT_FACTION) or DEFAULT_FACTION


def realm_currencies(room):
    """Currencies valid in this room's realm (always includes shards)."""
    r = get_realm(room_realm(room))
    cur = list(r.get("currencies", [])) if r else []
    if "shards" not in cur:
        cur = ["shards"] + cur
    return cur


def apply_realm_title(character, realm_key, connective="of"):
    """Set a character's title realm slot from the registry, e.g. 'of The Facility'.
    Used by residency/membership (and staff) to fill the realm slot on the unified
    title. Pass realm_key=None/'' to clear it."""
    try:
        if not realm_key:
            character.db.title_realm = ""
            return ""
        name = realm_name(realm_key)
        character.db.title_realm = f"{connective} {name}".strip()
        return character.db.title_realm
    except Exception:
        return ""


def stamp_room(room, realm=None, faction=None):
    """Stamp a room's realm and/or sub-faction override. Pass "" to clear a slot.
    Returns the resolved (realm_key, faction_key) after stamping."""
    if realm is not None:
        room.db.realm = realm or None
    if faction is not None:
        room.db.faction = faction or None
    return room_realm(room), room_faction(room)
