"""
world/pregnancy.py — real estrus, conception, gestation, and delivery.

The spine of a breeding facility: her body actually cycles, catches, swells, and
drops. This wraps the existing offspring spawner (gang_breeding._birth_offspring)
with a real pregnancy state so breeding has visible, mechanical consequence.

Flow:
  * is_fertile() — perpetual heat keeps her always in season; otherwise a real cycle.
  * on_bred(species) — a stud's deposit during a fertile window may CATCH (conceive).
  * gestation_tick() — driven each cycle beat: advances the pregnancy, swells the
    belly through stages (real zone desc + inflation), fires stage beats.
  * deliver() — at term she drops the litter (spawned via _birth_offspring, joining
    the roster), the belly resets, her milk comes in, and that species' quota is
    raised (the offspring spiral the facility runs on).

Accelerated by the BROOD accelerant and the fertility implant (accelerate()).

OOC floor: clear() restores the belly desc and wipes all pregnancy state; called by
both reset paths. Spawned get are tracked on facility_items for teardown already.
"""

import random

CYCLE_LENGTH    = 24
FERTILE_WINDOW  = (9, 15)      # cycle "days" fertile, when not in perpetual heat
BASE_TERM       = 22.0         # gestation beats at boost 0 (slow burn, but visible)
CONCEIVE_CHANCE = 0.55         # per stud-breeding while fertile and womb-free
SUPERFETATION   = 0.10         # chance a breeding adds to the litter while already gravid

_LITTER = {"hound": (3, 7), "bull": (1, 1), "boar": (4, 8),
           "stallion": (1, 1), "contributor": (1, 2), "bethany": (1, 2)}

# (min fraction of term, stage key, belly desc)
_BELLY_STAGES = [
    (0.00, "caught",   "a faint new tightness low in her belly — bred, caught, and not yet showing, "
                       "but the facility's already logged her gravid"),
    (0.20, "showing",  "a soft, unmistakable swell low in her belly — showing now, the get rooted "
                       "and growing, her body visibly given over to it"),
    (0.45, "heavy",    "a heavy, rounded pregnant belly, taut and full and obscene on her frame, "
                       "the swell of a womb doing exactly what the facility keeps it for"),
    (0.75, "full",     "a huge, full-term belly, skin drum-tight and veined, the get shifting and "
                       "kicking visibly beneath — ripe, overdue-looking, ready to drop"),
    (0.95, "labor",    "a vast, dropped, labour-heavy belly, low and clenching in waves, her body "
                       "audibly working to deliver what was put in it"),
]

_BELLY_ZONES = ["lower_belly", "belly", "abdomen", "womb", "stomach", "groin"]


def _belly_zone(target):
    zones = getattr(target.db, "zones", None) or {}
    for z in _BELLY_ZONES:
        if z in zones:
            return z
    # fall back to the vaginal orifice/womb zone if present
    for z, d in zones.items():
        if (d or {}).get("zone_type") in ("orifice", "both") and any(
                f in z for f in ("pussy", "vag", "cunt", "womb")):
            return z
    return None


def is_pregnant(target):
    return bool(getattr(target.db, "pregnancy", None))


def is_fertile(target):
    if getattr(target.db, "perpetual_heat", False):
        return True
    day = int(getattr(target.db, "cycle_day", 0) or 0)
    return FERTILE_WINDOW[0] <= day <= FERTILE_WINDOW[1]


def on_bred(target, species, generation=1, sire=None):
    """A stud has bred her. While gravid, a deposit may swell the litter; while
    fertile and empty, it may catch. `sire` names the individual stud (e.g. "Caesar")."""
    if not target:
        return
    if is_pregnant(target):
        if species in _LITTER and random.random() < SUPERFETATION:
            p = dict(target.db.pregnancy)
            p["litter"] = int(p.get("litter", 1)) + 1
            # A different stud topping her up gets recorded as a co-sire of the litter.
            if sire:
                sires = list(p.get("sires") or ([p["sire"]] if p.get("sire") else []))
                if sire not in sires:
                    sires.append(sire)
                p["sires"] = sires
            target.db.pregnancy = p
        return
    if is_fertile(target) and species in _LITTER and random.random() < CONCEIVE_CHANCE:
        conceive(target, species, generation, sire=sire)


def conceive(target, species, generation=1, sire=None):
    lo, hi = _LITTER.get(species, (1, 1))
    target.db.pregnancy = {
        "species": species, "generation": int(generation),
        "progress": 0.0, "term": BASE_TERM, "litter": random.randint(lo, hi),
        "sire": sire, "sires": ([sire] if sire else []),
    }
    _set_belly(target, 0.0)
    if target.location:
        tname = target.db.rp_name or target.name
        target.location.msg_contents(
            f"|RThe {species} catches. {tname} is bred — properly, this time, the deposit taking "
            f"root. Her chart is updated: gravid. Whatever the schedule wanted from her womb, it's "
            f"started getting.|n")


def accelerate(target, amount=5.0):
    """The brood accelerant / fertility implant hurries an active gestation along."""
    p = getattr(target.db, "pregnancy", None)
    if not p:
        return
    p = dict(p)
    p["progress"] = float(p.get("progress", 0.0)) + float(amount)
    target.db.pregnancy = p
    _set_belly(target, min(1.0, p["progress"] / p["term"]))
    if p["progress"] >= p["term"]:
        deliver(target)


def gestation_tick(target):
    """Advance the cycle or the pregnancy by one beat. Called each realm cycle tick."""
    if not target:
        return
    p = getattr(target.db, "pregnancy", None)
    if not p:
        # Not gravid — advance the estrus cycle (unless perpetual heat holds her open).
        if not getattr(target.db, "perpetual_heat", False):
            target.db.cycle_day = (int(getattr(target.db, "cycle_day", 0) or 0) + 1) % CYCLE_LENGTH
        return
    p = dict(p)
    old = float(p.get("progress", 0.0))
    term = float(p.get("term", BASE_TERM)) or BASE_TERM
    new = old + 1.0
    p["progress"] = new
    target.db.pregnancy = p
    _maybe_stage_beat(target, old / term, new / term)
    _set_belly(target, min(1.0, new / term))
    if new >= term:
        deliver(target)


def deliver(target):
    p = getattr(target.db, "pregnancy", None)
    if not p:
        return
    species = p.get("species", "contributor")
    gen     = int(p.get("generation", 1))
    litter  = int(p.get("litter", 1))
    sires   = list(p.get("sires") or ([p["sire"]] if p.get("sire") else []))
    tname   = target.db.rp_name or target.name
    if target.location:
        target.location.msg_contents(
            f"|RHer body works, and works, and delivers — {tname} drops her {species} litter on "
            f"the floor of whatever room she's in, {litter} of them, wet and squirming and "
            f"already counted.|n")
    try:
        from world.gang_breeding import _birth_offspring
        import random as _r
        for _ in range(max(1, litter)):
            # Each of the litter takes one of the recorded sires (or none, if unknown).
            sire = _r.choice(sires) if sires else None
            _birth_offspring(target, species, generation=gen, sire=sire)
    except Exception:
        pass
    # The offspring spiral: dropping a litter RAISES that species' quota.
    _raise_quota(target, species, bump=litter)
    # Her milk comes in, post-partum — the dairy's whole supply chain.
    target.db.lactation_locked = True
    _clear_belly(target, restore=True)
    target.db.pregnancy = None
    # Perpetual heat means she's fertile again immediately; otherwise reset the cycle.
    target.db.cycle_day = 0


def _raise_quota(target, species, bump=1):
    quota = getattr(target.db, "breeding_quota", None)
    if not (isinstance(quota, dict) and species in quota):
        return
    entry = dict(quota[species])
    entry["required"] = int(entry.get("required", 0)) + max(1, int(bump))
    quota[species] = entry
    target.db.breeding_quota = quota
    if target.location:
        target.location.msg_contents(
            f"|mThe {species} line drops young — so the {species} quota climbs to match. Her own "
            f"get just moved her finish line further away. It always will.|n")


def _maybe_stage_beat(target, frac_old, frac_new):
    for thresh, key, _desc in _BELLY_STAGES:
        if frac_old < thresh <= frac_new:
            beat = _STAGE_BEATS.get(key)
            if beat and target.location:
                target.location.msg_contents("|R" + random.choice(beat).format(
                    t=target.db.rp_name or target.name) + "|n")


def _stage_for(frac):
    desc = _BELLY_STAGES[0][2]
    for thresh, _key, d in _BELLY_STAGES:
        if frac >= thresh:
            desc = d
    return desc


def _set_belly(target, frac):
    """Render the pregnant belly on a real zone (nude desc), backing up the original,
    and push visible distension into the inflation channel if she has one."""
    z = _belly_zone(target)
    desc = _stage_for(frac)
    if z:
        zones = dict(getattr(target.db, "zones", None) or {})
        if z in zones:
            backup = dict(getattr(target.db, "belly_desc_backup", None) or {})
            zd = dict(zones[z])
            if z not in backup:
                backup[z] = {"nude": zd.get("nude", "")}
                target.db.belly_desc_backup = backup
            zd["nude"] = desc
            zones[z] = zd
            target.db.zones = zones
    target.db.pregnancy_belly = desc


def _clear_belly(target, restore=True):
    backup = dict(getattr(target.db, "belly_desc_backup", None) or {})
    if restore and backup:
        zones = dict(getattr(target.db, "zones", None) or {})
        for z, orig in backup.items():
            if z in zones:
                zd = dict(zones[z]); zd["nude"] = orig.get("nude", ""); zones[z] = zd
        target.db.zones = zones
    target.db.belly_desc_backup = None
    target.db.pregnancy_belly = None


def clear(target):
    """Reset/OOC-floor teardown: restore belly desc, wipe all pregnancy/cycle state."""
    if not target:
        return
    _clear_belly(target, restore=True)
    target.db.pregnancy = None
    target.db.cycle_day = 0


_STAGE_BEATS = {
    "showing": [
        "{t}'s belly has started to show — a soft new curve she can't suck in, the get rooted "
        "and growing, and the handlers note it with satisfaction and breed her anyway.",
    ],
    "heavy": [
        "{t} is heavily pregnant now, belly round and taut and in the way, and the facility "
        "adjusts the frames to fold around it — gravid stock still gets used, just braced "
        "differently.",
    ],
    "full": [
        "{t} is full-term and enormous, the get kicking visibly under drum-tight skin, and "
        "still she's milked and mounted on schedule, ripe and dropping-ready and given no rest "
        "for it.",
    ],
    "labor": [
        "{t}'s belly drops and starts to clench in long waves — labour, on the facility's clock, "
        "not hers. They log the time and keep working her through it.",
    ],
}
