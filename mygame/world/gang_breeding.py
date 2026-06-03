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
                    fluid_type="semen", volume_each=DEFAULT_VOLUME_EACH,
                    species="contributor"):
    """Inseminate `target`'s `zone_name` from multiple contributors at once.

    `species` attributes this successful breeding to a kind (hound/bull/boar/
    stallion/contributor) for the per-species quota ledger. Returns the list of
    (donor_id_or_None, donor_name) for this round, or [] on failure.
    """
    if not target or not zone_name or contributors <= 0:
        return []

    donors = _draw_contributors(contributors, fluid_type, volume_each)

    # Tally onto the target's running breeding record.
    tally = list(getattr(target.db, "bred_by", None) or [])
    tally.extend(donors)
    target.db.bred_by = tally

    # Per-species quota: one successful breeding event logged for this species.
    quota = getattr(target.db, "breeding_quota", None)
    if quota and species in quota:
        entry = dict(quota[species])
        entry["current"] = int(entry.get("current", 0)) + 1
        quota[species] = entry
        target.db.breeding_quota = quota
        # Milestone: a species quota completing earns a permanent processing brand.
        if entry["current"] == int(entry.get("required", 0)):
            marks = list(getattr(target.db, "facility_brands", None) or [])
            marks.append(f"a stamp marking the {species} quota met — healed, permanent")
            target.db.facility_brands = marks
            tname = target.db.rp_name or target.name
            if target.location:
                target.location.msg_contents(
                    f"|RA brand is pressed into {tname}'s skin — the {species} quota, "
                    f"met and marked. It does not come off.|n"
                )

    # Offspring — purely the stud's line (never anonymous contributors). Enough
    # of one stud and she drops its get, which joins the roster and, in time,
    # breeds her too.
    if species in ("hound", "bull", "boar", "stallion"):
        _maybe_offspring(target, species)

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


_SPECIES_LABEL = {
    "hound": "hounds", "bull": "the bull", "boar": "the boar",
    "stallion": "the stallion", "contributor": "anonymous contributors",
}


def quota_met(target):
    """True only if every species' logged count has reached its requirement."""
    quota = getattr(target.db, "breeding_quota", None)
    if not quota:
        return False
    return all(int(v.get("current", 0)) >= int(v.get("required", 0))
               for v in quota.values())


_OFFSPRING_TERM = {"hound": "pup", "bull": "calf", "boar": "piglet", "stallion": "foal"}
_OFFSPRING_VARIANT = [
    "leggy", "oversized", "pale", "dark-coated", "twin-born", "heavy-shouldered",
    "quick", "feral", "golden-eyed", "silver-marked", "violet-eyed", "runtish-but-vicious",
    "broad-skulled", "long-bodied", "early-maturing",
]
OFFSPRING_THRESHOLD = 8   # successful breedings of a stud line before she drops its get


def _maybe_offspring(target, species, generation=1):
    """Accumulate breedings of a line toward dropping its (next-gen) get.

    Each generation matures faster than the last — the brood accelerates.
    """
    key = species if generation == 1 else f"{species}_g{generation}"
    prog = dict(getattr(target.db, "offspring_progress", None) or {})
    prog[key] = int(prog.get(key, 0)) + 1
    threshold = max(3, OFFSPRING_THRESHOLD - (generation - 1) * 2)
    if prog[key] >= threshold:
        prog[key] = 0
        _birth_offspring(target, species, generation=generation)
    target.db.offspring_progress = prog


def maybe_lineage_offspring(target, species, parent_generation):
    """An offspring breeding her can produce the next generation of get."""
    _maybe_offspring(target, species, generation=int(parent_generation) + 1)


def _birth_offspring(target, species, generation=1):
    room = target.location
    if not room:
        return
    try:
        from typeclasses.facility_script import FacilityBeast
        from evennia.utils import create
    except Exception:
        return
    counts = dict(getattr(target.db, "offspring_counts", None) or {})
    counts[species] = int(counts.get(species, 0)) + 1
    target.db.offspring_counts = counts

    variant = random.choice(_OFFSPRING_VARIANT)
    term    = _OFFSPRING_TERM.get(species, "get")
    tname   = target.db.rp_name or target.name
    gen_tag = "" if generation <= 1 else f" (gen {generation})"
    key     = f"a {variant} {species} {term}{gen_tag}"

    o = create.create_object(FacilityBeast, key=key, location=room)
    o.db.rp_name       = key
    o.db.facility_role = "beast"
    o.db.species       = species
    o.db.is_offspring  = True
    o.db.generation    = generation
    lineage = ("by the facility's stud line" if generation <= 1
               else f"out of her own {species} get, {generation} generations deep")
    o.db.physical_desc = (
        f"A {variant} {term}{gen_tag} — {tname}'s own get {lineage}, inheriting nothing "
        f"of her but the womb it grew in. Already restless, already learning the "
        f"schedule it will keep, and the use it will be put to."
    )
    # Track for cleanup so the reset removes the whole brood.
    items = list(getattr(target.db, "facility_items", None) or [])
    items.append(o.dbref)
    target.db.facility_items = items

    born = (f"After enough of the {species} line, {tname} drops a {variant} {term}"
            if generation <= 1 else
            f"Her own {species} get breeds true, and {tname} drops a {variant} {term}{gen_tag}")
    room.msg_contents(
        f"|R{born} — its get, not hers. It's logged, tagged, and added to the roster. "
        f"In time it will breed her too, and the line will breed itself through her, "
        f"deeper every generation.|n"
    )


def summarize_quota(target):
    """Multi-line per-species breeding-quota readout (logged on the board)."""
    quota = getattr(target.db, "breeding_quota", None)
    if not quota:
        return ""
    lines = ["|wBREEDING QUOTA — successful breedings logged:|n"]
    order = ["hound", "bull", "boar", "stallion", "contributor"]
    keys = [k for k in order if k in quota] + [k for k in quota if k not in order]
    for sp in keys:
        v = quota[sp]
        cur = int(v.get("current", 0)); req = int(v.get("required", 0))
        done = "|gMET|n" if cur >= req else "|rNOT MET|n"
        bar = f"{cur}/{req}"
        lines.append(f"   {_SPECIES_LABEL.get(sp, sp):<22} {bar:>8}   {done}")
    lines.append("|wstatus: " + ("|gQUOTA COMPLETE|n" if quota_met(target)
                                  else "|rINCOMPLETE — processing continues|n"))
    return "\n".join(lines)


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
