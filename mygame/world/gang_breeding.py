"""
world/gang_breeding.py

Multi-contributor insemination — "gang-breeding."

One call deposits from several contributors at once. Where real donors exist in
the GlobalFluidBank they're drawn down and tallied by name; the remainder is
filled anonymously from the facility's reservoir (matching the anonymous-bank
lore). The combined volume is routed into the target zone as cumflation via the
inflation system, so the existing fill/leak descriptions take over.

    target.db.bred_by = [(donor_id_or_None, donor_name), ...]   # running tally
"""

import random

DEFAULT_VOLUME_EACH = 80.0
_ANON_NAMES = [
    "an unmarked donor", "a tagged contributor", "someone the machine won't name",
    "a number, not a name", "an anonymous load", "a contribution on file",
]


def gang_inseminate(target, zone_name, contributors=3,
                    fluid_type="semen", volume_each=DEFAULT_VOLUME_EACH):
    """Inseminate `target`'s `zone_name` from multiple contributors at once.

    Returns a list of (donor_id_or_None, donor_name) for this round, or [] on
    failure. Silent on its own — the caller narrates.
    """
    if not target or not zone_name or contributors <= 0:
        return []

    donors = _draw_contributors(contributors, fluid_type, volume_each)

    # Tally onto the target's running breeding record.
    tally = list(getattr(target.db, "bred_by", None) or [])
    tally.extend(donors)
    target.db.bred_by = tally

    # Route the combined volume into the zone as cumflation.
    total = volume_each * len(donors)
    try:
        from typeclasses.inflation_item import add_inflation_volume
        add_inflation_volume(target, zone_name, total, fluid_type)
    except Exception:
        pass

    return donors


def _draw_contributors(count, fluid_type, amount):
    """Draw from real bank donors where possible, fill the rest anonymously."""
    donors = []
    try:
        from evennia import search_object
        from typeclasses.fluid_bank import GlobalFluidBank
        bank = GlobalFluidBank.get()
        records = dict(bank.db.records or {})
        eligible = [
            cid for cid, rec in records.items()
            if rec.get("fluid_type") == fluid_type
            and (rec.get("deposit_ml") or 0.0) >= amount
        ]
        random.shuffle(eligible)
        for cid in eligible[:count]:
            rec = dict(records[cid])
            rec["deposit_ml"] = max(0.0, (rec.get("deposit_ml") or 0.0) - amount)
            records[cid] = rec
            # Fictional donors carry their name on the record; real ones resolve.
            name = rec.get("donor_name")
            if not name and not str(cid).startswith("fict:"):
                found = search_object(f"#{cid}")
                if found:
                    obj = found[0]
                    name = getattr(obj.db, "rp_name", None) or obj.name
            donors.append((cid, name or "a contributor"))
        bank.db.records = records
    except Exception:
        pass

    # Fill the remainder from the anonymous reservoir.
    while len(donors) < count:
        donors.append((None, random.choice(_ANON_NAMES)))
    return donors


_FICTIONAL_SEMEN = [
    "the kennel's stud line", "Donor 7", "the breeding bull", "a soldier on rotation",
    "the wolfpack's alpha", "an off-world contributor", "the stable's prize stock",
    "Subject M-12", "a regular, on file", "the night shift", "the herd sire",
    "an unlisted benefactor", "the pack, collectively", "a paying customer",
    "the machine's own reserve", "Donor 19",
]
_FICTIONAL_MILK = [
    "Cow 3", "Cow 8", "the prize heifer", "a fellow resident",
    "the dairy's best producer", "Subject D-04", "the new intake",
]


def seed_fictional_donors(semen_count=14, milk_count=7, deposit_ml=4000.0):
    """Populate the GlobalFluidBank with fictional contributors.

    Lets gang-breeding draw plentiful, named-but-fictional sources even when no
    real players have deposited. Idempotent: re-running tops the same fictional
    records back up rather than duplicating them.
    """
    try:
        from typeclasses.fluid_bank import GlobalFluidBank
        bank = GlobalFluidBank.get()
        records = dict(bank.db.records or {})

        def _seed(names, fluid_type, n):
            for i in range(min(n, len(names))):
                key = f"fict:{fluid_type}:{i}"
                records[key] = {
                    "lifetime_ml":  deposit_ml,
                    "deposit_ml":   deposit_ml,
                    "fluid_type":   fluid_type,
                    "fluid_flavor": "anonymous",
                    "donor_name":   names[i],
                }

        _seed(_FICTIONAL_SEMEN, "semen", semen_count)
        _seed(_FICTIONAL_MILK,  "milk",  milk_count)
        bank.db.records = records
        return semen_count + milk_count
    except Exception:
        return 0


def clear_fictional_donors():
    """Remove all fictional donor records (real player records untouched)."""
    try:
        from typeclasses.fluid_bank import GlobalFluidBank
        bank = GlobalFluidBank.get()
        records = {k: v for k, v in dict(bank.db.records or {}).items()
                   if not str(k).startswith("fict:")}
        bank.db.records = records
        return True
    except Exception:
        return False


def summarize_bred_by(target, recent=None):
    """Human-readable tally. Pass `recent` (this round's donors) for a line."""
    if recent:
        names = [n for _, n in recent]
        if len(names) == 1:
            return names[0]
        return ", ".join(names[:-1]) + f", and {names[-1]}"
    tally = list(getattr(target.db, "bred_by", None) or [])
    named = {n for cid, n in tally if cid is not None}
    anon  = sum(1 for cid, _ in tally if cid is None)
    parts = []
    if named:
        parts.append(f"{len(named)} known")
    if anon:
        parts.append(f"{anon} anonymous")
    return " + ".join(parts) if parts else "no one yet"
