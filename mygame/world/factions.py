"""
world/factions.py — faction standing, ranks, membership, residency, relations.

Generalised and registry-driven (reads world/realms.FACTIONS). The Facility is now
just one faction among many. **Back-compat is preserved**: the old Facility helpers
(`add_standing`, `get_standing`, `get_facility_tier`, `next_threshold`,
`seed_facility_title`, and `FACILITY`) still work exactly as before, so existing
facility code is untouched.

Per-character state:
  db.factions       : {standing_key: rep_int}      — standing/rep (keyed by display name,
                                                      e.g. "The Facility", for legacy safety)
  db.faction_ranks  : {faction_key: rank_index}    — granted rank within a faction
  db.faction_member : [faction_key, ...]           — formal membership (staff/guild)
  db.residency      : [realm_key, ...]             — realms you're a resident of

Distinctions:
  - rep      = the numeric score (drives rank for advance="rep" factions like the Facility).
  - rank     = a named position in the faction's ladder (custom per faction).
  - member   = formally joined (staff/guild). Stock have rep+grade but need not be "members".
  - resident = allowed to live in a realm; separate from faction membership.
"""

from world.realms import (FACTIONS, get_faction, faction_key_for_name,
                          get_realm, realm_name)

# Back-compat: callers import FACILITY and use it as the db.factions key (display name).
FACILITY = "The Facility"

# Legacy gain table (per activity source); registry factions may override later.
_GAIN = {
    "breed": 2.0, "milk": 1.0, "condition": 1.5, "cycle": 1.0,
    "comply": 1.0, "grade": 5.0, "drug": 2.0, "procedure": 4.0,
}


# ── key / name resolution ─────────────────────────────────────────────────────
def _key(faction):
    """Normalise a faction identifier (key OR display name) to a registry key."""
    if not faction:
        return None
    low = faction.lower()
    if low in FACTIONS:
        return low
    return faction_key_for_name(faction)


def _standing_key(faction):
    """The db.factions key for a faction (its display name, for legacy continuity)."""
    k = _key(faction)
    if k:
        return FACTIONS[k].get("standing_key") or FACTIONS[k]["name"]
    return faction  # unknown faction: store under whatever was passed


# ── standing / rep ────────────────────────────────────────────────────────────
def get_standing(character, faction=FACILITY):
    return int((getattr(character.db, "factions", None) or {}).get(_standing_key(faction), 0))


def add_standing(character, source="cycle", amount=None, faction=FACILITY):
    """Add standing (slow). `source` keys a default gain, or pass `amount`."""
    if not character:
        return 0
    k = _key(faction)
    gain = (get_faction(k) or {}).get("gain", _GAIN) if k else _GAIN
    amt = float(amount if amount is not None else gain.get(source, 1.0))
    skey = _standing_key(faction)
    facs = dict(getattr(character.db, "factions", None) or {})
    new = int(facs.get(skey, 0)) + int(round(amt))
    facs[skey] = new
    character.db.factions = facs
    # The Facility drives the legacy title/grade slots, as before.
    if k == "facility":
        _apply_facility_title(character, new)
    return new


# ── ranks (registry-driven, generalised) ──────────────────────────────────────
def ranks(faction):
    """The faction's ordered rank ladder (low->high). Owner-set custom names (from the
    persistent store) override the registry names by position; rep thresholds/titles are
    kept from the registry where they line up, so renaming a rep-driven ladder (the
    Facility) preserves its grade thresholds."""
    k = _key(faction)
    base = list((get_faction(k) or {}).get("ranks", [])) if k else []
    try:
        from world.realm_state import get_rank_names_override
        names = get_rank_names_override(k) if k else None
    except Exception:
        names = None
    if not names:
        return base
    merged = []
    for i, nm in enumerate(names):
        if i < len(base):
            r = dict(base[i])
            r["name"] = nm
            r["title"] = r.get("title") or nm
        else:
            r = {"name": nm, "rep": 0, "title": nm}
        merged.append(r)
    return merged


def advance_method(faction):
    f = get_faction(_key(faction))
    return (f or {}).get("advance", "granted")


def rank_index_by_rep(faction, rep):
    """Highest rank index whose rep threshold is met (rep-advance factions)."""
    rks = ranks(faction)
    idx = 0
    for i, r in enumerate(rks):
        if rep >= int(r.get("rep", 0)):
            idx = i
    return idx


def get_rank_index(character, faction):
    """A character's rank index in a faction. For advance='rep' it's derived from
    standing; otherwise it's the granted index in db.faction_ranks."""
    k = _key(faction)
    if not k:
        return 0
    if advance_method(k) == "rep":
        return rank_index_by_rep(k, get_standing(character, k))
    return int((getattr(character.db, "faction_ranks", None) or {}).get(k, 0))


def rank_name(character, faction):
    rks = ranks(faction)
    if not rks:
        return ""
    i = max(0, min(get_rank_index(character, faction), len(rks) - 1))
    return rks[i].get("name", "")


def set_rank(character, faction, index):
    """Grant a rank index (granted-advance factions). Clamped to the ladder."""
    k = _key(faction)
    rks = ranks(k)
    if not rks:
        return False
    index = max(0, min(int(index), len(rks) - 1))
    fr = dict(getattr(character.db, "faction_ranks", None) or {})
    fr[k] = index
    character.db.faction_ranks = fr
    return True


def can_grant(actor, faction, target_rank_index, target=None):
    """May `actor` set someone to `target_rank_index` in `faction`? You may move anyone to
    a rank STRICTLY BELOW your own. The faction owner (and a parent's owner, for an
    affiliated sub) overrides this and may move across the whole ladder."""
    k = _key(faction)
    f = get_faction(k)
    if not f:
        return False
    # Owner / parent-owner override.
    if is_owner(actor, k) or _is_parent_owner(actor, k):
        return True
    actor_idx = get_rank_index(actor, k)
    return target_rank_index < actor_idx


def is_owner(actor, faction):
    """True if actor is the faction's owner/CEO. NPC owners are matched by name;
    a player may be flagged via db.faction_owner = [keys]."""
    k = _key(faction)
    f = get_faction(k)
    if not f:
        return False
    owner = f.get("owner")
    aname = (getattr(actor.db, "rp_name", None) or actor.key or "")
    if owner and aname.lower() == owner.lower():
        return True
    return k in (getattr(actor.db, "faction_owner", None) or [])


def _is_parent_owner(actor, faction):
    """Owner authority flows to AFFILIATED children: a parent's owner can act on its subs."""
    f = get_faction(_key(faction))
    parent = f.get("parent") if f else None
    return bool(parent) and is_owner(actor, parent)


# ── membership ────────────────────────────────────────────────────────────────
def is_member(character, faction):
    k = _key(faction)
    return k in (getattr(character.db, "faction_member", None) or [])


def join_faction(character, faction, rank_index=0):
    k = _key(faction)
    if not k:
        return False
    mem = list(getattr(character.db, "faction_member", None) or [])
    if k not in mem:
        mem.append(k)
        character.db.faction_member = mem
    set_rank(character, k, rank_index)
    return True


def leave_faction(character, faction):
    k = _key(faction)
    mem = list(getattr(character.db, "faction_member", None) or [])
    if k in mem:
        mem.remove(k)
        character.db.faction_member = mem
    fr = dict(getattr(character.db, "faction_ranks", None) or {})
    fr.pop(k, None)
    character.db.faction_ranks = fr
    return True


# ── residency (separate from membership) ──────────────────────────────────────
def is_resident(character, realm):
    rk = (realm or "").lower()
    return rk in (getattr(character.db, "residency", None) or [])


def add_resident(character, realm):
    rk = (realm or "").lower()
    if not get_realm(rk):
        return False
    res = list(getattr(character.db, "residency", None) or [])
    if rk not in res:
        res.append(rk)
        character.db.residency = res
    return True


def remove_resident(character, realm):
    rk = (realm or "").lower()
    res = list(getattr(character.db, "residency", None) or [])
    if rk in res:
        res.remove(rk)
        character.db.residency = res
    return True


# ── relations ─────────────────────────────────────────────────────────────────
def _rel(faction, kind):
    """A faction's relation list of `kind`, with owner-set overrides from the store merged
    over the registry defaults."""
    k = _key(faction)
    f = get_faction(k)
    base = list((f.get("relations", {}) if f else {}).get(kind, []))
    try:
        from world.realm_state import get_relations_override
        ov = get_relations_override(k) if k else None
        if ov and kind in ov:
            return list(dict.fromkeys(base + list(ov[kind])))
    except Exception:
        pass
    return base


def friends_of(faction):
    return _rel(faction, "friends")


def enemies_of(faction):
    return _rel(faction, "enemies")


def subsidiaries_of(faction):
    """Affiliated sub-factions (declared as relations OR by parent pointer)."""
    k = _key(faction)
    subs = set(_rel(k, "subsidiaries"))
    for fk, fv in FACTIONS.items():
        if fv.get("parent") == k:
            subs.add(fk)
    return sorted(subs)


def relation_between(a, b):
    """How faction a regards faction b: 'self' | 'friend' | 'enemy' | 'subsidiary' | 'neutral'."""
    ka, kb = _key(a), _key(b)
    if ka == kb:
        return "self"
    if kb in subsidiaries_of(ka):
        return "subsidiary"
    if kb in enemies_of(ka):
        return "enemy"
    if kb in friends_of(ka):
        return "friend"
    return "neutral"


# ── Facility back-compat (unchanged behaviour) ────────────────────────────────
def get_facility_tier(character):
    """(grade_name, title_text) for current Facility standing — preserved API."""
    rks = ranks("facility")
    rep = get_standing(character, "facility")
    i = rank_index_by_rep("facility", rep)
    r = rks[i] if rks else {"name": "Unprocessed", "title": ""}
    return r.get("name", "Unprocessed"), r.get("title", "")


def next_threshold(character):
    """Standing needed for the next Facility grade, or (None, None) at max — preserved API."""
    rep = get_standing(character, "facility")
    for r in ranks("facility"):
        if rep < int(r.get("rep", 0)):
            return int(r["rep"]), r.get("name")
    return None, None


def seed_facility_title(character):
    """Stamp the Facility faction title slots the moment she signs — preserved API."""
    if not character:
        return
    if not getattr(character.db, "facility_title_backup", None):
        character.db.facility_title_backup = {
            "faction": getattr(character.db, "title_faction", "") or "",
            "suffix":  getattr(character.db, "title_suffix", "") or "",
        }
    character.db.title_faction = "of The Facility"
    if not (getattr(character.db, "title_suffix", "") or "").startswith("—"):
        character.db.title_suffix = "— Resident"
    if not getattr(character.db, "facility_grade", None):
        character.db.facility_grade = "Unprocessed"


def _apply_facility_title(character, standing):
    name, title = get_facility_tier(character)
    if name == "Unprocessed":
        seed_facility_title(character)
        return
    if not getattr(character.db, "facility_title_backup", None):
        character.db.facility_title_backup = {
            "faction": getattr(character.db, "title_faction", "") or "",
            "suffix":  getattr(character.db, "title_suffix", "") or "",
        }
    character.db.facility_grade = name
    owner = getattr(character.db, "facility_owner", None)
    if getattr(character.db, "bethany_owned", False) or owner:
        character.db.title_faction = "of The Facility"
        if not (getattr(character.db, "title_suffix", "") or "").endswith("'s"):
            character.db.title_suffix = f"— {owner}'s" if owner else "— Bethany's"
        return
    character.db.title_faction = "of The Facility"
    character.db.title_suffix  = (f"— {title}" if title else "")
