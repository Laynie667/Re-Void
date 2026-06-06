"""
world/realm_state.py

Persistent runtime overrides for realm/faction configuration — the things that should
be changeable in-game and *stick* across reloads, because control shifts over time.

The code registries (world/realms.FACTIONS / REALMS) are the seeded DEFAULTS. This layer
holds the live overrides on top of them, backed by Evennia's ServerConfig (a persistent
global key/value store). If ServerConfig isn't available (e.g. an out-of-game sanity
check), it degrades to an in-memory dict so callers never crash.

Currently stores:
  realm_owners : {realm_key: faction_key}   — who currently OWNS a realm (reassignable)

Designed to grow: faction rank-name/currency/relation overrides and player-created
factions can live here too when we build owner-config (Phase 4c).
"""

_KEY = "revoid_realm_state"
_MEM = {}   # in-memory fallback + cache


def _load():
    try:
        from evennia.server.models import ServerConfig
        data = ServerConfig.objects.conf(_KEY, default=None)
        return dict(data) if data else dict(_MEM)
    except Exception:
        return dict(_MEM)


def _save(data):
    # keep the in-memory cache in sync regardless of backend
    _MEM.clear()
    _MEM.update(data)
    try:
        from evennia.server.models import ServerConfig
        ServerConfig.objects.conf(_KEY, value=dict(data))
    except Exception:
        pass


# ── realm ownership overrides ─────────────────────────────────────────────────
def get_realm_owner_override(realm_key):
    """The override faction key for a realm, or None if it's still on the registry default."""
    owners = _load().get("realm_owners") or {}
    return owners.get((realm_key or "").lower())


def set_realm_owner(realm_key, faction_key):
    """Reassign (or, with faction_key falsy, revert) a realm's owning faction. Persists."""
    data = _load()
    owners = dict(data.get("realm_owners") or {})
    rk = (realm_key or "").lower()
    if faction_key:
        owners[rk] = faction_key.lower()
    else:
        owners.pop(rk, None)
    data["realm_owners"] = owners
    _save(data)
    return owners.get(rk)


def all_realm_owner_overrides():
    return dict(_load().get("realm_owners") or {})


# ── faction rank-name overrides (owner-editable ladders) ──────────────────────
def get_rank_names_override(faction_key):
    """The owner-set ordered rank-name list for a faction, or None for the default ladder."""
    names = _load().get("faction_rank_names") or {}
    return names.get((faction_key or "").lower())


def set_rank_names(faction_key, names):
    """Set (or clear, with falsy `names`) a faction's custom ordered rank-name ladder."""
    data = _load()
    table = dict(data.get("faction_rank_names") or {})
    fk = (faction_key or "").lower()
    if names:
        table[fk] = [str(n).strip() for n in names if str(n).strip()]
    else:
        table.pop(fk, None)
    data["faction_rank_names"] = table
    _save(data)
    return table.get(fk)


# ── faction relation overrides (owner-editable friends/enemies/subsidiaries) ──
def get_relations_override(faction_key):
    """Owner-set relations {friends,enemies,subsidiaries} for a faction, or None."""
    rels = _load().get("faction_relations") or {}
    return rels.get((faction_key or "").lower())


def set_relation(faction_key, kind, other_key, add=True):
    """Add/remove `other_key` to/from a faction's friends|enemies|subsidiaries list."""
    if kind not in ("friends", "enemies", "subsidiaries"):
        return None
    data = _load()
    rels = dict(data.get("faction_relations") or {})
    fk = (faction_key or "").lower()
    entry = dict(rels.get(fk) or {})
    lst = list(entry.get(kind) or [])
    ok = (other_key or "").lower()
    if add and ok and ok not in lst:
        lst.append(ok)
    elif not add and ok in lst:
        lst.remove(ok)
    entry[kind] = lst
    rels[fk] = entry
    data["faction_relations"] = rels
    _save(data)
    return lst


# ── realm currency-config overrides (governing faction's call) ────────────────
def get_realm_currency_override(realm_key):
    """Owner-set currency config for a realm, or None. Keys: currency_name,
    accepts_shards, exchange_rate."""
    cur = _load().get("realm_currency") or {}
    return cur.get((realm_key or "").lower())


def set_realm_currency(realm_key, **fields):
    """Merge currency-config fields onto a realm (currency_name/accepts_shards/exchange_rate)."""
    data = _load()
    cur = dict(data.get("realm_currency") or {})
    rk = (realm_key or "").lower()
    entry = dict(cur.get(rk) or {})
    for k, v in fields.items():
        if v is None:
            entry.pop(k, None)
        else:
            entry[k] = v
    cur[rk] = entry
    data["realm_currency"] = cur
    _save(data)
    return entry
