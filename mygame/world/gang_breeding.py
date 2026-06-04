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
        tname = target.db.rp_name or target.name
        # Productivity ratchet + milestone brand.
        if int(entry["current"]) >= int(entry.get("required", 0)):
            if not entry.get("ratcheted"):
                # First time you reach it, meeting it IS the trigger to raise it.
                bump = random.randint(3, 6)
                entry["ratcheted"] = True
                entry["required"] = int(entry["required"]) + bump
                quota[species] = entry
                target.db.breeding_quota = quota
                if target.location:
                    target.location.msg_contents(
                        f"|mThe {species} quota is met — so the standard rises. Required "
                        f"climbs by {bump}. Meeting it was only ever the signal to move it.|n"
                    )
            elif not entry.get("branded"):
                # The raised bar is genuinely cleared — permanent brand.
                entry["branded"] = True
                quota[species] = entry
                target.db.breeding_quota = quota
                record_mark(target, f"a quota stamp seared in — {species} line, cleared",
                            prefer="ass")
                if target.location:
                    target.location.msg_contents(
                        f"|RA brand is pressed into {tname}'s skin — the {species} quota, "
                        f"cleared at last and marked. It does not come off.|n"
                    )

    # Offspring — purely the stud's line (never anonymous contributors). A stud's
    # deposit during her fertile window may catch; the pregnancy system then carries
    # it to a real gestation and delivery. (Falls back to the abstract progress
    # counter only if the pregnancy module is unavailable.)
    if species in ("hound", "bull", "boar", "stallion"):
        try:
            from world.pregnancy import on_bred
            on_bred(target, species)
        except Exception:
            _maybe_offspring(target, species)

    # Route the combined volume into the zone as cumflation (belly swell).
    total = volume_each * len(donors)
    try:
        from typeclasses.inflation_item import add_inflation_volume
        add_inflation_volume(target, zone_name, total, fluid_type)
    except Exception:
        pass

    # REAL deposit — actually place the fluid in her zone, flood any WombRoom,
    # AND broadcast the system's own message so it's visible in-game, not silent.
    try:
        from typeclasses.insemination_item import do_inseminate
        msg = do_inseminate(None, target, zone_name, {
            "source": "machine", "fluid_type": fluid_type,
            "volume_per_tick": total, "ttl_hours": 24.0,
        })
        if msg and target.location:
            target.location.msg_contents("|m" + msg + "|n")
    except Exception:
        pass

    # Stretch the hole — and past a point it stays stretched, permanently.
    add_gape(target, zone_name, random.uniform(0.6, 1.6))

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


GAPE_PERMANENT_AT = 18.0


def _markable_zone(target, prefer=None):
    """Pick a real zone to place a freeform mark on."""
    zones = getattr(target.db, "zones", None) or {}
    order = ([prefer] if prefer else []) + ["abdomen", "lower_belly", "hip", "lower_back",
             "back", "chest", "groin", "ass", "thigh"]
    for pref in order:
        if not pref:
            continue
        for zn in zones:
            if pref in zn.lower():
                return zn
    for zn, zd in zones.items():
        if (zd or {}).get("zone_type") in ("surface", "both"):
            return zn
    return next(iter(zones), None)


def record_mark(target, text, zone=None, mode="on", prefer=None):
    """Log a permanent mark BOTH on the board AND as a real freeform mark so it
    shows in the game's marks/brands commands and zone descriptions."""
    marks = list(getattr(target.db, "facility_brands", None) or [])
    marks.append(text)
    target.db.facility_brands = marks
    try:
        from world.freeform_manager import FreeformManager
        z = zone or _markable_zone(target, prefer=prefer)
        if z:
            key = f"facility mark {len(marks)}"
            FreeformManager.place_item(target, z, key, text, 0, display_mode=mode)
    except Exception:
        pass


def record_use(target, zone_name, amount=1.0):
    """Log use of a hole: raises its use count and gape, trains its capacity, and
    past a threshold the hole gapes permanently (a bleed-over mark)."""
    if not target or not zone_name:
        return
    holes = dict(getattr(target.db, "holes", None) or {})
    h = dict(holes.get(zone_name) or {"use": 0, "gape": 0.0})
    h["use"]  = int(h.get("use", 0)) + 1
    h["gape"] = float(h.get("gape", 0.0)) + float(amount)
    holes[zone_name] = h
    target.db.holes = holes

    perm = list(getattr(target.db, "permanent_gape", None) or [])
    if h["gape"] >= GAPE_PERMANENT_AT and zone_name not in perm:
        perm.append(zone_name)
        target.db.permanent_gape = perm
        disp = zone_name.split("/")[-1].replace("_", " ")
        record_mark(target, f"{disp} stretched permanently slack and gaping — it won't "
                    f"close right again", zone=zone_name, mode="in")
        if target.location:
            tname = target.db.rp_name or target.name
            target.location.msg_contents(
                f"|R{tname}'s {disp} has been used past the point of recovery — it stays open "
                f"now, slack and gaping and dripping, ruined for good and logged as an "
                f"improvement.|n")


def add_gape(target, zone_name, amount):
    """Back-compat alias — all use is recorded through record_use now."""
    record_use(target, zone_name, amount)


def hole_capabilities(target, zone_name):
    """What a hole can now take, earned through training/use. Returns a set."""
    h = (getattr(target.db, "holes", None) or {}).get(zone_name) or {}
    use  = int(h.get("use", 0)); gape = float(h.get("gape", 0.0))
    caps = set()
    if use >= 6  or gape >= 5:  caps.add("knot")
    if use >= 14 or gape >= 10: caps.add("double")
    if use >= 22 or gape >= 14: caps.add("fist")
    if zone_name in (getattr(target.db, "permanent_gape", None) or []):
        caps.add("prolapse")
    return caps


def gape_word(target, zone_name):
    """A descriptor for a hole's current state, for prose."""
    h = (getattr(target.db, "holes", None) or {}).get(zone_name) or {}
    g = float(h.get("gape", 0.0))
    if zone_name in (getattr(target.db, "permanent_gape", None) or []):
        return "permanently gaping"
    if g >= 12: return "gaping"
    if g >= 6:  return "stretched loose"
    if g >= 2:  return "used and puffy"
    return "tight"


# ── Animal use: scent-marking, mucus plugs, filth, and the sleeve state ──────
# Everything here is real and cleared by the reset (marks are facility marks;
# barrier seals + rewritten zone descs are backed up and restored).

_HOLE_FRAGMENTS = {
    "pussy": ("pussy", "vag", "cunt"),
    "anus":  ("anus", "anal", "ass", "rear", "butt"),
    "mouth": ("mouth", "throat", "oral"),
}

_SLEEVE_DESC = {
    "pussy": ("a slack, animal-bred cunt — a fuck-sleeve worn loose to the shape of a beast's "
              "flared cock, lips dark and puffy and parted, the hole gaping and drooling cloudy "
              "musk-thick slick, rubbed raw and kept that way"),
    "anus":  ("a ruined, winking asshole — propped permanently open and slack, the rim a soft "
              "loose ring, slick and dripping, a hole that doesn't close anymore and isn't meant to"),
    "mouth": ("a slack, drooling fuckhole of a mouth — jaw loose, throat trained open, lips "
              "puffy and spit-shined, a sleeve that's given up fighting the stretch"),
}


def _find_hole(target, key):
    zones = getattr(target.db, "zones", None) or {}
    frags = _HOLE_FRAGMENTS.get(key, ())
    for z, d in zones.items():
        if (d or {}).get("zone_type") in ("orifice", "both") and any(f in z for f in frags):
            return z
    return None


def animal_holes(target):
    """Map of pussy/anus/mouth -> real zone name (or None)."""
    return {k: _find_hole(target, k) for k in _HOLE_FRAGMENTS}


def scent_mark(target, zone=None):
    """The animals scent-mark her — a real, persistent freeform mark (added once)."""
    if getattr(target.db, "pen_scented", False):
        return
    record_mark(target,
                "scent-marked — rubbed down with kennel-musk and stud-spunk until she reeks "
                "of the pens, so every animal in the place knows her by smell",
                zone=zone, mode="on")
    target.db.pen_scented = True


def mucus_plug(target, zone):
    """Cork a bred hole with a clotted plug of animal cum — a real seal the womb
    system respects (the load is held in, doesn't drain). Mark added once per zone."""
    if not zone:
        return
    zones = dict(getattr(target.db, "zones", None) or {})
    if zone in zones:
        zd = dict(zones[zone]); mech = dict(zd.get("mechanics", {}) or {})
        mech["barrier"] = {"seals_zone": True,
                           "desc": "a thick clotted plug of animal cum sealing the hole, "
                                   "holding the load in to take"}
        zd["mechanics"] = mech; zones[zone] = zd; target.db.zones = zones
    plugged = list(getattr(target.db, "pen_plugged", None) or [])
    if zone not in plugged:
        disp = zone.split("/")[-1].replace("_", " ")
        record_mark(target, f"a mucus plug of clotted animal cum corking her {disp}, the load "
                    f"held in to take", zone=zone, mode="in")
        plugged.append(zone)
        target.db.pen_plugged = plugged


def apply_filth(target):
    """Cake her in the pen's filth — mud, musk, dried piss. No feces. Added once."""
    if getattr(target.db, "pen_filth", False):
        return
    for txt in (
        "mud-caked to the thighs and elbows from being rutted face-down in the wallow",
        "matted and slick with dried animal spunk and fresh kennel-musk, head to heel",
        "piss-soaked — hosed and marked by the stock until she stinks of it, the smell "
        "rubbed into her skin and hair",
    ):
        record_mark(target, txt, mode="on")
    target.db.pen_filth = True


def _set_sleeve_desc(target, zone, desc):
    """Rewrite a hole's nude+interior desc to the sleeve, backing up the original."""
    if not zone or not desc:
        return
    zones = dict(getattr(target.db, "zones", None) or {})
    if zone not in zones:
        return
    backup = dict(getattr(target.db, "sleeve_desc_backup", None) or {})
    zd = dict(zones[zone])
    if zone not in backup:
        backup[zone] = {"nude": zd.get("nude", ""), "interior": zd.get("interior", "")}
        target.db.sleeve_desc_backup = backup
    zd["nude"] = desc
    zd["interior"] = desc
    zones[zone] = zd
    target.db.zones = zones


def make_animal_sleeve(target, holes=("pussy", "anus", "mouth"),
                       filth=True, scent=True, plug=True, broadcast=True):
    """Train her holes into permanent animal cock-sleeves: real heavy use + permanent
    gape (prolapse-capable), the zone descs rewritten to the sleeve, scent-marked,
    bred holes corked with a mucus plug, and caked in filth. Cumulative — the pens
    deepen it every visit. Returns the list of holes converted."""
    found = animal_holes(target)
    done = []
    holes_db = dict(getattr(target.db, "holes", None) or {})
    perm = list(getattr(target.db, "permanent_gape", None) or [])
    for key in holes:
        z = found.get(key)
        if not z:
            continue
        h = dict(holes_db.get(z) or {"use": 0, "gape": 0.0})
        h["use"] = max(int(h.get("use", 0)), 24)
        h["gape"] = max(float(h.get("gape", 0.0)), 16.0)
        holes_db[z] = h
        if z not in perm:
            perm.append(z)
        _set_sleeve_desc(target, z, _SLEEVE_DESC.get(key))
        if scent:
            scent_mark(target, z)
        if plug and key in ("pussy", "anus"):
            mucus_plug(target, z)
        done.append(key)
    target.db.holes = holes_db
    target.db.permanent_gape = perm
    if filth:
        apply_filth(target)
    target.db.animal_sleeve = True
    if broadcast and target.location and done:
        tname = target.db.rp_name or target.name
        target.location.msg_contents(
            f"|R{tname}'s holes have been used past the point of recovery — cunt, mouth, and "
            f"ass worn permanently slack and gaping, scent-marked, plugged, and filthy. She is "
            f"a set of animal cock-sleeves now, logged as livestock, and the record calls it an "
            f"improvement.|n")
    return done


def clear_animal_sleeve(target):
    """Undo the sleeve state for the reset/OOC floor: restore the rewritten hole
    descs, strip the mucus-plug barriers, and clear the flags. Marks/gape are
    cleared by the caller's normal mark/permanent_gape teardown."""
    if not target:
        return
    zones = dict(getattr(target.db, "zones", None) or {})
    backup = dict(getattr(target.db, "sleeve_desc_backup", None) or {})
    touched = set(backup.keys()) | set(getattr(target.db, "pen_plugged", None) or [])
    for z in touched:
        if z not in zones:
            continue
        zd = dict(zones[z])
        if z in backup:
            zd["nude"] = backup[z].get("nude", "")
            zd["interior"] = backup[z].get("interior", "")
        mech = dict(zd.get("mechanics", {}) or {})
        mech.pop("barrier", None)
        zd["mechanics"] = mech
        zones[z] = zd
    target.db.zones = zones
    target.db.sleeve_desc_backup = None
    target.db.pen_plugged = None
    target.db.animal_sleeve = False
    target.db.pen_filth = False
    target.db.pen_scented = False


# ── Piercings ───────────────────────────────────────────────────────────────
# location -> (key, description, +stim, +floor, zone-name-fragments to find a real zone)
_PIERCINGS = {
    "nipples":   ("nipple rings", "heavy captive rings locked through both nipples", 1.5, 6.0, ("nipple", "chest")),
    "clit":      ("clit barbell", "a thick barbell driven through the clit itself", 2.5, 10.0, ("clit", "groin")),
    "clit_hood": ("hood ring", "a ring through the clit hood, tugging with every move", 1.5, 6.0, ("clit", "groin")),
    "labia":     ("labia ladder", "a locked ladder of rings down both labia", 1.0, 4.0, ("labia", "groin")),
    "septum":    ("septum ring", "a heavy septum ring — a handle, really, to lead her by", 0.4, 0.0, ("nose", "face")),
    "tongue":    ("tongue barbell", "a barbell through the tongue", 0.4, 0.0, ("tongue", "mouth")),
    "navel":     ("navel piercing", "a dangling navel piercing", 0.3, 0.0, ("navel", "abdomen")),
}


def add_piercing(target, location=None):
    """Pierce a part of her with a REAL PiercingItem worn on a real zone, plus a
    freeform mark, plus the sensitivity effect. Returns the description or None."""
    if not target:
        return None
    import random as _r
    have = [p.get("loc") for p in (getattr(target.db, "piercings", None) or [])]
    options = [k for k in _PIERCINGS if k not in have]
    location = location if location in _PIERCINGS else (_r.choice(options) if options else None)
    if not location:
        return None
    key, desc, stim, floor, frags = _PIERCINGS[location]

    # Find a real zone to wear it on.
    zones = getattr(target.db, "zones", None) or {}
    zone = None
    for frag in frags:
        for zn in zones:
            if frag in zn.lower():
                zone = zn; break
        if zone:
            break

    # Create and wear a REAL PiercingItem on that zone.
    worn = False
    if zone:
        try:
            from typeclasses.piercing_item import PiercingItem
            from evennia.utils import create
            p = create.create_object(PiercingItem, key=key, location=target)
            p.db.desc = desc
            p.db.facility_piercing = True
            ok, _r2 = p.wear(target, zone)
            worn = bool(ok)
            if not worn:
                try: p.delete()
                except Exception: pass
        except Exception:
            worn = False

    pl = list(getattr(target.db, "piercings", None) or [])
    pl.append({"loc": location, "desc": desc})
    target.db.piercings = pl
    target.db.stim_per_tick = float(getattr(target.db, "stim_per_tick", 0) or 0) + stim
    if floor:
        target.db.arousal_floor = max(float(getattr(target.db, "arousal_floor", 0) or 0), floor)
    # Freeform mark so it shows in marks/brands even if the zone wear failed.
    record_mark(target, f"pierced: {desc}", zone=zone)
    return desc


def clear_session_state(target):
    """Clear the per-session hole/use state (not the permanent marks)."""
    target.db.holes = None



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
