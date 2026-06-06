"""
world/wallet.py — multi-currency wallet (Phase 3).

A thin VIEW + routing layer over the game's existing money stores, so one wallet
shows everything and one API earns/spends in any currency without a destructive
migration:

  - shards : global tender. Backed by typeclasses.economy (db.shards + ledger).
  - scrip  : Facility-local. Backed by world.economy (db.facility_credits).
  - <other>: future realm-local currencies, backed by char.db.wallet[key].

Shards are the major currency and spend everywhere a realm accepts them
(`accepts_shards`). Realm-local currencies spend only inside realms that list
them, and are NON-convertible by default — a realm opts IN to exchange by setting
an `exchange_rate` (shards per 1 local unit). Nothing here touches the OOC floor.
"""

# key -> {name, scope ("global" | <realm_key>), backing ("shards"|"scrip"|"wallet")}
CURRENCIES = {
    "shards": {"name": "shards",         "scope": "global",   "backing": "shards"},
    "scrip":  {"name": "Facility scrip", "scope": "facility", "backing": "scrip"},
}


def _cur(key):
    return CURRENCIES.get((key or "").lower())


def currency_name(key):
    c = _cur(key)
    return c["name"] if c else (key or "")


# ── balances ────────────────────────────────────────────────────────────────
def balance(char, currency="shards"):
    c = _cur(currency)
    backing = c["backing"] if c else "wallet"
    try:
        if backing == "shards":
            from typeclasses.economy import get_balance
            return int(get_balance(char))
        if backing == "scrip":
            from world.economy import get_balance as scrip_balance
            return int(scrip_balance(char))
        return int((char.db.wallet or {}).get(currency, 0))
    except Exception:
        return 0


def can_afford(char, currency, amount):
    return balance(char, currency) >= int(amount)


# ── mutations (route to the right backing store) ──────────────────────────────
def credit(char, currency, amount, reason="credit"):
    """Add currency. Returns the new balance."""
    amount = int(amount)
    if amount <= 0:
        return balance(char, currency)
    c = _cur(currency)
    backing = c["backing"] if c else "wallet"
    if backing == "shards":
        from typeclasses.economy import add_shards
        return int(add_shards(char, amount, reason=reason))
    if backing == "scrip":
        from world.economy import add_credits
        return int(add_credits(char, amount, reason))
    w = dict(char.db.wallet or {})
    w[currency] = int(w.get(currency, 0)) + amount
    char.db.wallet = w
    return w[currency]


def debit(char, currency, amount, reason="debit", allow_debt=False):
    """Spend currency. Returns (ok, balance)."""
    amount = int(amount)
    if amount <= 0:
        return True, balance(char, currency)
    c = _cur(currency)
    backing = c["backing"] if c else "wallet"
    if backing == "shards":
        from typeclasses.economy import remove_shards, get_balance
        ok = bool(remove_shards(char, amount, reason=reason))
        return ok, int(get_balance(char))
    if backing == "scrip":
        from world.economy import spend_credits
        return spend_credits(char, amount, reason, allow_debt=allow_debt)
    w = dict(char.db.wallet or {})
    cur = int(w.get(currency, 0))
    if cur < amount:
        return False, cur
    w[currency] = cur - amount
    char.db.wallet = w
    return True, w[currency]


# ── realm-awareness ───────────────────────────────────────────────────────────
def _realm_cfg(room):
    from world.realms import get_realm, room_realm
    return get_realm(room_realm(room)) or {}


def valid_here(room, currency):
    """Is `currency` spendable in this room's realm? Shards count only if the realm
    accepts them; local currencies must be listed in the realm's `currencies`."""
    cfg = _realm_cfg(room)
    cur = (currency or "").lower()
    if cur == "shards":
        return bool(cfg.get("accepts_shards", True))
    return cur in [c.lower() for c in cfg.get("currencies", [])]


def held_currencies(char):
    """Every currency the character holds a balance in (shards always shown)."""
    out = {"shards": balance(char, "shards")}
    s = balance(char, "scrip")
    if s:
        out["scrip"] = s
    for k, v in (char.db.wallet or {}).items():
        if v:
            out[k] = int(v)
    return out


def wallet_lines(char):
    """Formatted balance lines for the wallet command — each with where it's good."""
    from world.realms import REALMS
    lines = []
    held = held_currencies(char)
    for key, amt in held.items():
        c = _cur(key)
        if not c or c.get("scope") == "global":
            where = "good everywhere shards are accepted"
        else:
            rn = REALMS.get(c["scope"], {}).get("name", c["scope"])
            where = f"only in {rn}"
        lines.append(f"  |w{amt:,}|n {currency_name(key)}  |x({where})|n")
    return lines


# ── exchange (opt-in per realm) ───────────────────────────────────────────────
def exchange(char, room, local_currency, amount):
    """Convert `amount` of a realm-local currency into shards, IF this realm has opted
    into exchange (exchange_rate > 0). Returns (ok, message)."""
    cfg = _realm_cfg(room)
    rate = cfg.get("exchange_rate", 0) or 0
    local = cfg.get("local_currency")
    if not local or (local_currency or "").lower() != local.lower():
        return False, "That isn't this realm's currency."
    if rate <= 0:
        return False, f"{currency_name(local)} doesn't convert here — it's sovereign tender."
    amount = int(amount)
    if amount <= 0:
        return False, "Exchange how much?"
    ok, _bal = debit(char, local, amount, reason="exchange")
    if not ok:
        return False, f"You don't have {amount:,} {currency_name(local)}."
    shards = int(amount * rate)
    credit(char, "shards", shards, reason="exchange")
    return True, f"Exchanged |w{amount:,}|n {currency_name(local)} for |w{shards:,}|n shards."
