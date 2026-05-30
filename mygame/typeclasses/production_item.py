"""
typeclasses/production_item.py

Fluid production items — zone attachments that accumulate fluid over time and
can be extracted by the milking machine or by hand.

Three concrete subclasses:
    MilkProductionItem
    SemenProductionItem
    UrineProductionItem

Custom fluid types are supported by setting fluid_type to any string.

Passive accumulation is handled by PassiveAccumulationScript, which attaches
to the item at install time and fires every 15 minutes.

Volume display thresholds:
    < 1000 ml       → "Xml"
    946+ ml         → also show "~N quart(s)"
    3785+ ml        → also show "~N gallon(s)"

Production rate scaling:
    base_rate_ml_per_tick * production_multiplier_from_body_mod_item
    Body mod item multiplier is looked up from the same zone at extract time.
    If no body mod item is installed on the zone, multiplier = 1.0.
"""

import time
from evennia import DefaultObject, DefaultScript
from evennia.utils import logger


# ---------------------------------------------------------------------------
# Volume display helper
# ---------------------------------------------------------------------------

_ML_PER_QUART  = 946.353
_ML_PER_GALLON = 3785.41


def format_volume(ml: float) -> str:
    """Return a human-readable volume string."""
    ml = max(0.0, ml)
    if ml < 1.0:
        return "trace amounts"
    parts = [f"{ml:.0f}ml"]
    if ml >= _ML_PER_GALLON:
        gallons = ml / _ML_PER_GALLON
        parts.append(f"~{gallons:.1f} gallon{'s' if gallons >= 1.99 else ''}")
    elif ml >= _ML_PER_QUART:
        quarts = ml / _ML_PER_QUART
        parts.append(f"~{quarts:.1f} quart{'s' if quarts >= 1.99 else ''}")
    return " / ".join(parts)


# ---------------------------------------------------------------------------
# Passive accumulation script
# ---------------------------------------------------------------------------

class PassiveAccumulationScript(DefaultScript):
    """
    Fires every 15 minutes and adds fluid to the owning production item.

    Stored on the production item: self.obj is the production item.
    """

    def at_script_creation(self):
        self.key      = "passive_accumulation"
        self.interval = 15 * 60   # 15 minutes in seconds
        self.persistent = True
        self.repeats  = 0         # repeat forever

    def at_repeat(self):
        item = self.obj
        if not item:
            self.stop()
            return
        if not item.db.installed_on_char:
            return   # not installed — don't accumulate
        item.tick_production()


# ---------------------------------------------------------------------------
# ProductionItem base
# ---------------------------------------------------------------------------

class ProductionItem(DefaultObject):
    """
    Base class for fluid production zone attachments.

    Attributes (db):
        fluid_type (str):           e.g. 'milk', 'semen', 'urine', or custom
        fluid_flavor (str|None):    Free-text flavor description, or None
        base_rate_ml_per_tick (float): ml produced per 15-min tick at multiplier 1.0
        current_volume_ml (float):  Accumulated since last extraction
        installed_on_char (obj):    Character this item is installed on, or None
        installed_on_zone (str):    Zone name, or None
        is_installed (bool):        Install flag
        lifetime_produced_ml (float): Total ml ever produced (for records)
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.fluid_type              = "fluid"
        self.db.fluid_flavor            = None
        self.db.base_rate_ml_per_tick   = 50.0    # ml per 15-min tick; override in subclasses
        self.db.current_volume_ml       = 0.0
        self.db.installed_on_char       = None
        self.db.installed_on_zone       = None
        self.db.is_installed            = False
        self.db.lifetime_produced_ml    = 0.0
        self.db.notified_thresholds     = []      # ml values already notified this fill

    # ------------------------------------------------------------------
    # Passive tick
    # ------------------------------------------------------------------

    def tick_production(self):
        """Called by PassiveAccumulationScript every 15 minutes."""
        multiplier = self._get_body_mod_multiplier()
        amount     = (self.db.base_rate_ml_per_tick or 50.0) * multiplier
        old_vol    = self.db.current_volume_ml or 0.0
        new_vol    = old_vol + amount
        self.db.current_volume_ml    = new_vol
        self.db.lifetime_produced_ml = (self.db.lifetime_produced_ml or 0.0) + amount
        # Fire private fullness messages when crossing new thresholds
        self._check_fullness_thresholds(old_vol, new_vol)

    def _check_fullness_thresholds(self, old_vol: float, new_vol: float):
        """
        Send a private fullness message to the installed character when
        current_volume_ml crosses a new threshold for the first time this cycle.
        Thresholds are cleared on extraction (reset_fullness_notifications).
        """
        char = self.db.installed_on_char
        if not char:
            return
        try:
            from world.milking_loader import get_fullness_thresholds
        except ImportError:
            return

        notified = set(self.db.notified_thresholds or [])

        for threshold_ml, messages in get_fullness_thresholds():
            if old_vol < threshold_ml <= new_vol and threshold_ml not in notified:
                import random
                char.msg(f"|x{random.choice(messages)}|n")
                notified.add(threshold_ml)

        self.db.notified_thresholds = list(notified)

    def reset_fullness_notifications(self):
        """
        Clear the notified threshold set so messages fire again on the
        next fill cycle. Called by MilkingSessionScript after extraction.
        """
        self.db.notified_thresholds = []

    def _get_body_mod_multiplier(self) -> float:
        """
        Look up the production multiplier from a BodyModItem installed on
        the same zone as this production item.
        """
        char      = self.db.installed_on_char
        zone_name = self.db.installed_on_zone
        if not char or not zone_name:
            return 1.0
        zones = getattr(char.db, "zones", None) or {}
        zone  = zones.get(zone_name, {})
        mechanics = zone.get("mechanics", {}) or {}
        bm_entry  = mechanics.get("body_mod")
        if not bm_entry:
            return 1.0
        # Fetch the actual item and call its multiplier method
        from evennia import search_object
        results = search_object(bm_entry.get("item_dbref", ""), exact=True)
        if results:
            item = results[0]
            if hasattr(item, "production_multiplier"):
                return item.production_multiplier()
        # Fall back to the snapshot size in the mechanics entry
        size     = bm_entry.get("size", 0.0)
        per_pt   = 0.10
        return 1.0 + (size * per_pt)

    # ------------------------------------------------------------------
    # Extract
    # ------------------------------------------------------------------

    def extract(self, speed_multiplier: float = 1.0) -> float:
        """
        Extract the current volume (optionally modified by a speed multiplier).
        Returns the ml extracted and resets current_volume_ml to 0.

        speed_multiplier: additional extraction factor from the milking machine speed.
            At 1.0 (slow), full volume is extracted.
            At higher values, extra is pulled (representing 'deeper' extraction
            drawing a bit above the current accumulation).
        """
        available = (self.db.current_volume_ml or 0.0)
        # Speed multiplier above 1.0 can pull a bit extra from the next tick
        extracted = available * min(speed_multiplier, 2.0)
        self.db.current_volume_ml = max(0.0, available - extracted)
        return extracted

    # ------------------------------------------------------------------
    # Install / uninstall
    # ------------------------------------------------------------------

    def install(self, character, zone_name: str) -> tuple:
        """
        Attach to a character zone.  Returns (True, "") or (False, reason).
        """
        if self.db.installed_on_char:
            return False, f"{self.key} is already installed."

        zones = getattr(character.db, "zones", None) or {}
        if zone_name not in zones:
            return False, f"No zone '{zone_name}' on {character.db.rp_name or character.name}."

        zone      = dict(zones[zone_name])
        mechanics = dict(zone.get("mechanics", {}) or {})

        if "production" in mechanics:
            return False, f"A production item is already installed on the {zone_name} zone."

        mechanics["production"] = {
            "item_dbref":  self.dbref,
            "item_name":   self.key,
            "fluid_type":  self.db.fluid_type,
            "fluid_flavor": self.db.fluid_flavor,
        }
        zone["mechanics"] = mechanics
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        character.db.zones = zones_copy

        self.db.installed_on_char = character
        self.db.installed_on_zone = zone_name
        self.db.is_installed      = True
        self.location             = character

        # Attach the passive accumulation script
        self.scripts.add(PassiveAccumulationScript)

        return True, ""

    def uninstall(self) -> tuple:
        """Remove from current zone.  Returns (True, "") or (False, reason)."""
        character = self.db.installed_on_char
        zone_name = self.db.installed_on_zone

        if not character or not zone_name:
            return False, f"{self.key} is not currently installed."

        zones = getattr(character.db, "zones", None) or {}
        if zone_name in zones:
            zone      = dict(zones[zone_name])
            mechanics = dict(zone.get("mechanics", {}) or {})
            mechanics.pop("production", None)
            zone["mechanics"] = mechanics
            zones_copy = dict(zones)
            zones_copy[zone_name] = zone
            character.db.zones = zones_copy

        # Stop the accumulation script
        for script in self.scripts.all():
            if script.key == "passive_accumulation":
                script.stop()

        self.db.installed_on_char = None
        self.db.installed_on_zone = None
        self.db.is_installed      = False

        return True, ""

    def _refresh_mechanics_entry(self):
        """Sync the mechanics snapshot (flavor/type) after setfluid."""
        char      = self.db.installed_on_char
        zone_name = self.db.installed_on_zone
        if not char or not zone_name:
            return
        zones = getattr(char.db, "zones", None) or {}
        if zone_name not in zones:
            return
        zone      = dict(zones[zone_name])
        mechanics = dict(zone.get("mechanics", {}) or {})
        if "production" in mechanics:
            entry = dict(mechanics["production"])
            entry["fluid_type"]   = self.db.fluid_type
            entry["fluid_flavor"] = self.db.fluid_flavor
            mechanics["production"] = entry
            zone["mechanics"] = mechanics
            zones_copy = dict(zones)
            zones_copy[zone_name] = zone
            char.db.zones = zones_copy

    # ------------------------------------------------------------------
    # Volume display
    # ------------------------------------------------------------------

    def volume_display(self) -> str:
        return format_volume(self.db.current_volume_ml or 0.0)

    def get_display_name(self, looker=None, **kwargs):
        name = self.key
        if self.db.is_installed and self.db.installed_on_zone:
            vol = self.volume_display()
            name += f" [{self.db.fluid_type or 'fluid'} — {vol} — installed on {self.db.installed_on_zone}]"
        return name


# ---------------------------------------------------------------------------
# Concrete subclasses
# ---------------------------------------------------------------------------

class MilkProductionItem(ProductionItem):
    """Milk producer. Default 60ml per 15-min tick at multiplier 1.0."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.fluid_type            = "milk"
        self.db.base_rate_ml_per_tick = 60.0
        self.key                      = "milk production item"


class SemenProductionItem(ProductionItem):
    """
    Semen producer.  Lower base rate; higher size-based multiplier.
    Default 15ml per 15-min tick at multiplier 1.0.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.fluid_type            = "semen"
        self.db.base_rate_ml_per_tick = 15.0
        self.key                      = "semen production item"

    def _get_body_mod_multiplier(self) -> float:
        """Prefer testicle or penis items over generic."""
        char      = self.db.installed_on_char
        zone_name = self.db.installed_on_zone
        if not char or not zone_name:
            return 1.0
        zones = getattr(char.db, "zones", None) or {}
        zone  = zones.get(zone_name, {})
        mechanics = zone.get("mechanics", {}) or {}
        bm_entry  = mechanics.get("body_mod")
        if not bm_entry:
            return 1.0
        # Testicle multiplier scales more aggressively
        from evennia import search_object
        results = search_object(bm_entry.get("item_dbref", ""), exact=True)
        if results:
            item = results[0]
            if hasattr(item, "production_multiplier"):
                mult = item.production_multiplier()
                # Testicle items give a 1.5× bonus on semen production
                if getattr(item, "db", None) and item.db.mod_type == "testicle":
                    mult *= 1.5
                return mult
        size   = bm_entry.get("size", 0.0)
        return 1.0 + (size * 0.15)


class UrineProductionItem(ProductionItem):
    """
    Urine producer.  Fastest accumulation rate by default.
    Default 120ml per 15-min tick at multiplier 1.0.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.fluid_type            = "urine"
        self.db.base_rate_ml_per_tick = 120.0
        self.key                      = "urine production item"
