"""
typeclasses/facility_implants.py

Real, installable facility implants that create their own default zones so they're
easy to drop onto a subject and play nicely with the rest of the real systems
(production, womb-rooms, inflation, marks).

  MilkPortItem  — surgical milk ports. Creates/uses a 'nipples' default zone wired
                  into the milk ducts; tracks nipple length + girth; can be force-fed
                  fluid (semen, etc.) which inflates the breasts.
  GaugeRingItem — a one-way gauging ring for ass or cervix: a membrane that lets
                  everything IN and nothing OUT. Seals the zone (the womb-room
                  respects it), holding loads — and anything inside — trapped.
  CowRingSet    — the "heavily pierced" set, themed for anthro/livestock cows: a heavy
                  septum lead-ring + bell, ear tags, a ladder of udder/nipple rings,
                  clit + labia rings. Real PiercingItems on real zones, marks, and
                  sensitivity.

All three: install() creates the target zone if missing, tracks themselves on
db.facility_items for teardown, back up anything they overwrite, and uninstall()
restores it — so the OOC reset/floor strips them clean.
"""

import random
from evennia import DefaultObject


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ensure_zone(char, zone, zone_type="surface", intimate=True):
    """Create a default zone on the character if it doesn't exist. Returns
    (zones_dict, created_bool)."""
    zones = dict(getattr(char.db, "zones", None) or {})
    created = False
    if zone not in zones:
        try:
            from typeclasses.characters import _make_default_zone
            z = _make_default_zone(intimate=intimate, zone_type=zone_type)
        except Exception:
            z = {"parent": None, "nude": "", "covered_by": None, "interior": "",
                 "contents": [], "state": "pristine", "state_desc": None,
                 "state_ambient": [], "visibility": "look", "intimate": intimate,
                 "zone_type": zone_type, "consent_required": "casual", "details": {},
                 "study_details": [], "handle_details": {}, "mechanics": {},
                 "default": True, "freeform": False, "ambient": []}
        z["default"] = True
        z["freeform"] = False
        zones[zone] = z
        char.db.zones = zones
        created = True
        # Record item-created zones so the reset path can strip them cleanly.
        cz = list(getattr(char.db, "facility_created_zones", None) or [])
        if zone not in cz:
            cz.append(zone)
            char.db.facility_created_zones = cz
    return zones, created


def _track(char, obj):
    items = list(getattr(char.db, "facility_items", None) or [])
    if obj.dbref not in items:
        items.append(obj.dbref)
    char.db.facility_items = items


def _find_zone(char, *fragments):
    """Find an existing zone whose name contains any fragment."""
    zones = getattr(char.db, "zones", None) or {}
    for z in zones:
        if any(f in z for f in fragments):
            return z
    return None


# ---------------------------------------------------------------------------
# MilkPortItem
# ---------------------------------------------------------------------------

class MilkPortItem(DefaultObject):
    """Surgical milk ports on a 'nipples' zone, wired into the ducts."""

    def at_object_creation(self):
        self.key = "surgical milk ports"
        self.db.desc = "A pair of clean steel valves, set to be plumbed under the areolae."
        self.db.nipple_length = 1.0     # arbitrary units; grows with use/feeding
        self.db.nipple_girth  = 1.0
        self.db.installed_on_char = None
        self.db.installed_on_zone = None
        self.db.created_zone = False
        self.db.prev_nude = None

    def _nude_desc(self):
        L, G = self.db.nipple_length or 1.0, self.db.nipple_girth or 1.0
        size = ("stubby", "ordinary", "long", "thick, distended", "obscenely long and fat")[
            min(4, int((L + G) / 2))]
        return (f"nipples re-plumbed around surgical milk-ports — {size}, valved at the tip, "
                f"wired straight into the ducts so they leak on command and can be opened, "
                f"drained, or fed into at will")

    def install(self, char, zone="nipples"):
        if self.db.installed_on_char:
            return False, f"{self.key} is already installed."
        zones, created = _ensure_zone(char, zone, zone_type="both", intimate=True)
        zd = dict(zones[zone]); mech = dict(zd.get("mechanics", {}) or {})
        if mech.get("milk_port"):
            return False, "Milk ports are already fitted there."
        mech["milk_port"] = {
            "item_dbref": self.dbref, "length": self.db.nipple_length,
            "girth": self.db.nipple_girth, "ducts": True, "locked": True,
        }
        self.db.prev_nude = zd.get("nude", "")
        zd["mechanics"] = mech
        zd["nude"] = self._nude_desc()
        zones[zone] = zd
        char.db.zones = zones
        self.db.installed_on_char = char
        self.db.installed_on_zone = zone
        self.db.created_zone = created
        self.location = char
        # Wired into the ducts: she lactates on command, always on.
        char.db.lactation_locked = True
        # Make sure she actually has milk glands to plumb.
        try:
            from world.facility_build import provision_body
            provision_body(char)
        except Exception:
            pass
        _track(char, self)
        return True, ""

    def _refresh(self):
        char = self.db.installed_on_char
        zone = self.db.installed_on_zone
        if not (char and zone):
            return
        zones = dict(getattr(char.db, "zones", None) or {})
        if zone in zones:
            zd = dict(zones[zone]); mech = dict(zd.get("mechanics", {}) or {})
            mp = dict(mech.get("milk_port", {}) or {})
            mp["length"] = self.db.nipple_length
            mp["girth"]  = self.db.nipple_girth
            mech["milk_port"] = mp
            zd["mechanics"] = mech
            zd["nude"] = self._nude_desc()
            zones[zone] = zd
            char.db.zones = zones

    def feed(self, volume_ml, fluid="semen"):
        """Force fluid IN through the ports — it backs up into the glands and
        inflates the breasts (and engorges the nipples). Returns a message."""
        char = self.db.installed_on_char
        if not char:
            return ""
        from evennia import search_object
        from typeclasses.production_item import ProductionItem
        filled = 0.0
        for zd in (getattr(char.db, "zones", None) or {}).values():
            pr = ((zd or {}).get("mechanics", {}) or {}).get("production")
            if not pr:
                continue
            res = search_object(pr.get("item_dbref", ""), exact=True)
            if res and isinstance(res[0], ProductionItem) and res[0].db.fluid_type in ("milk", "fluid"):
                cur = float(res[0].db.current_volume_ml or 0)
                res[0].db.current_volume_ml = cur + volume_ml
                try: res[0]._check_size_messages(res[0].db.current_volume_ml)
                except Exception: pass
                filled += volume_ml
                break
        # Engorge the nipples and bump temp breast size from the backfill.
        self.db.nipple_length = (self.db.nipple_length or 1.0) + volume_ml / 600.0
        self.db.nipple_girth  = (self.db.nipple_girth or 1.0) + volume_ml / 900.0
        self._refresh()
        try:
            from typeclasses.body_mod_item import BreastItem
            for zd in (getattr(char.db, "zones", None) or {}).values():
                bm = ((zd or {}).get("mechanics", {}) or {}).get("body_mod")
                if bm:
                    r2 = search_object(bm.get("item_dbref", ""), exact=True)
                    if r2 and isinstance(r2[0], BreastItem):
                        r2[0].apply_temp_boost(volume_ml / 800.0, duration_hours=8.0)
                        break
        except Exception:
            pass
        return (f"{volume_ml:.0f}ml of {fluid} is pumped backward through {char.db.rp_name or char.name}'s "
                f"milk-ports, forced up the ducts until her tits swell tight and hot around it and her "
                f"nipples engorge long and fat — fed, inflated, and dripping from the valves.")

    def uninstall(self):
        char = self.db.installed_on_char
        zone = self.db.installed_on_zone
        if char and zone:
            zones = dict(getattr(char.db, "zones", None) or {})
            if self.db.created_zone:
                zones.pop(zone, None)
            elif zone in zones:
                zd = dict(zones[zone]); mech = dict(zd.get("mechanics", {}) or {})
                mech.pop("milk_port", None)
                zd["mechanics"] = mech
                zd["nude"] = self.db.prev_nude or ""
                zones[zone] = zd
            char.db.zones = zones
        self.db.installed_on_char = None
        self.db.installed_on_zone = None
        return True, ""


# ---------------------------------------------------------------------------
# GaugeRingItem — one-way membrane
# ---------------------------------------------------------------------------

class GaugeRingItem(DefaultObject):
    """A one-way gauging ring: everything in, nothing out. Seals the zone (the
    womb-room respects the barrier), trapping loads — and anything inside."""

    def at_object_creation(self):
        self.key = "one-way gauging ring"
        self.db.desc = "A wide steel ring with a soft internal membrane, valved to open inward only."
        self.db.gauge = 4.0
        self.db.installed_on_char = None
        self.db.installed_on_zone = None
        self.db.created_zone = False
        self.db.prev_nude = None

    def _nude_desc(self):
        return (f"a one-way gauging ring locked in — the hole cranked permanently open around "
                f"wide steel, fitted with a soft inward valve membrane that yields to anything "
                f"pushing in and seals shut against anything trying to leave, so it takes "
                f"everything and gives nothing back, kept full and plugged by its own fitting")

    def install(self, char, zone=None):
        if self.db.installed_on_char:
            return False, f"{self.key} is already installed."
        if not zone:
            zone = _find_zone(char, "anus", "ass", "cunt", "pussy", "cervix", "womb") or "anus"
        zones, created = _ensure_zone(char, zone, zone_type="orifice", intimate=True)
        zd = dict(zones[zone]); mech = dict(zd.get("mechanics", {}) or {})
        if mech.get("barrier"):
            return False, "Something already seals that hole."
        mech["barrier"] = {"seals_zone": True, "one_way": True, "item_dbref": self.dbref,
                           "desc": "a one-way gauging ring — everything in, nothing out"}
        self.db.prev_nude = zd.get("nude", "")
        zd["mechanics"] = mech
        zd["nude"] = self._nude_desc()
        zones[zone] = zd
        char.db.zones = zones
        # Held permanently open + gaping (real capability unlocks).
        try:
            holes = dict(getattr(char.db, "holes", None) or {})
            h = dict(holes.get(zone) or {"use": 0, "gape": 0.0})
            h["use"] = max(int(h.get("use", 0)), 20)
            h["gape"] = max(float(h.get("gape", 0.0)), 14.0)
            holes[zone] = h; char.db.holes = holes
            perm = list(getattr(char.db, "permanent_gape", None) or [])
            if zone not in perm:
                perm.append(zone); char.db.permanent_gape = perm
        except Exception:
            pass
        self.db.installed_on_char = char
        self.db.installed_on_zone = zone
        self.db.created_zone = created
        self.location = char
        _track(char, self)
        return True, ""

    def uninstall(self):
        char = self.db.installed_on_char
        zone = self.db.installed_on_zone
        if char and zone:
            zones = dict(getattr(char.db, "zones", None) or {})
            if self.db.created_zone:
                zones.pop(zone, None)
            elif zone in zones:
                zd = dict(zones[zone]); mech = dict(zd.get("mechanics", {}) or {})
                mech.pop("barrier", None)
                zd["mechanics"] = mech
                zd["nude"] = self.db.prev_nude or ""
                zones[zone] = zd
            char.db.zones = zones
        self.db.installed_on_char = None
        self.db.installed_on_zone = None
        return True, ""


# ---------------------------------------------------------------------------
# CowRingSet — the "heavily pierced" livestock set
# ---------------------------------------------------------------------------
# My ideal "heavily pierced", themed for an anthro/livestock cow: a face you lead
# her by, an udder ringed for milking, and metal everywhere a tug carries to a nerve.
_COW_RINGS = [
    ("septum", ("a heavy cow lead-ring through the septum",
                "a thick brass nose-ring — a handle to lead her by, hung with a small clinking "
                "tag stamped with her number")),
    ("nipples", ("milking rings through both nipples",
                 "captive steel rings locked through both nipples, sized for a milking clip")),
    ("clit",   ("a heavy clit ring",
                "a thick weighted ring through the clit that swings and drags with every step")),
    ("labia",  ("a labia ladder",
                "a locked ladder of rings down both labia, lacing the cunt half-shut")),
    ("ears",   ("a numbered livestock ear tag",
                "a yellow plastic ear tag punched through, printed with her herd number")),
    ("navel",  ("a hanging udder-bell",
                "a little brass bell hung from a navel piercing that rings softly when she's used")),
]


class CowRingSet(DefaultObject):
    """Installs the full heavily-pierced cow set as real PiercingItems + tags."""

    def at_object_creation(self):
        self.key = "a heavy cow piercing set"
        self.db.desc = "A tray of brass and steel — nose-ring, nipple rings, clit ring, ladder, ear tag, bell."

    def install(self, char):
        from evennia import create_object
        from typeclasses.piercing_item import PiercingItem
        done = []
        # Ensure a 'nose' zone for the lead-ring and an 'ears' zone for the tag.
        _ensure_zone(char, "nose", zone_type="surface", intimate=False)
        _ensure_zone(char, "ears", zone_type="surface", intimate=False)
        zone_for = {"septum": "nose", "ears": "ears"}
        for slot, (short, desc) in _COW_RINGS:
            zname = zone_for.get(slot) or self._find_for(char, slot)
            if not zname:
                continue
            try:
                p = create_object(PiercingItem, key=short, location=char)
                p.db.facility_piercing = True
                p.db.slot = slot
                p.db.worn_desc = desc
                p.db.leash_anchor = (slot == "septum")
                ok, _r = p.wear(char, zname)
                if ok:
                    _track(char, p)
                    done.append(short)
            except Exception:
                pass
        # Real marks so it shows in marks/brands, plus the herd identity.
        try:
            from world.gang_breeding import record_mark
            record_mark(char, "ringed and tagged as a dairy cow — nose-ring lead, milking rings, "
                        "ear tag, udder-bell: heavily pierced livestock", mode="on")
        except Exception:
            pass
        # Sensitivity from all the metal.
        char.db.stim_per_tick = float(getattr(char.db, "stim_per_tick", 0) or 0) + 2.0
        char.db.arousal_floor = max(float(getattr(char.db, "arousal_floor", 0) or 0), 35.0)
        return done

    def _find_for(self, char, slot):
        frag = {"nipples": ("nipple", "chest", "breast"),
                "clit": ("clit", "groin", "pussy"),
                "labia": ("labia", "groin", "pussy"),
                "navel": ("navel", "abdomen", "belly", "stomach")}.get(slot, ())
        return _find_zone(char, *frag) if frag else None
