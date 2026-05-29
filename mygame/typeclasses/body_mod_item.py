"""
typeclasses/body_mod_item.py

Body modification items — zone attachments that track a size float and plug
into the fluid-production and milking-machine systems.

Three concrete subclasses ship here:
    BreastItem      — cup-size scale, AA → Z → ZZ → absurd named tiers
    TesticleItem    — volume-descriptor scale, pea → grapefruit → absurd
    PenisItem       — length/girth descriptor scale

Install / uninstall via commands/body_mod_commands.py CmdInstall / CmdUninstall.

Zone mechanics dict entry written on install:
    zones[zone_name]['mechanics']['body_mod'] = {
        'item_dbref': self.dbref,
        'item_name':  self.key,
        'size':       self.db.size,
        'mod_type':   self.db.mod_type,
    }

The size float is always the authoritative value; the mechanics dict entry is a
read-only snapshot used for fast lookups (e.g. by the milking machine and sheet
renderer). It is refreshed any time size changes.
"""

from evennia import DefaultObject
from evennia.utils import logger


# ---------------------------------------------------------------------------
# Breast cup-size display table
# ---------------------------------------------------------------------------

# Integer bands → cup letter.  Fractional steps produce modifier suffixes.
_BREAST_CUP_TABLE = [
    # (min_float, label)
    (0.0,  "AA"),
    (1.0,  "A"),
    (2.0,  "B"),
    (3.0,  "C"),
    (4.0,  "D"),
    (5.0,  "DD"),
    (6.0,  "DDD"),
    (7.0,  "G"),
    (8.0,  "H"),
    (9.0,  "I"),
    (10.0, "J"),
    (11.0, "K"),
    (12.0, "L"),
    (13.0, "M"),
    (14.0, "N"),
    (15.0, "O"),
    (16.0, "P"),
    (17.0, "Q"),
    (18.0, "R"),
    (19.0, "S"),
    (20.0, "T"),
    (21.0, "U"),
    (22.0, "V"),
    (23.0, "W"),
    (24.0, "X"),
    (25.0, "Y"),
    (26.0, "Z"),
    (27.0, "ZZ"),
    (28.0, "ZZZ"),
    (29.0, "ZZZZ"),
    # Absurd named tiers begin at 30.0
    (30.0, "Monumental"),
    (32.0, "Incomprehensible"),
    (34.0, "Architecturally Significant"),
    (36.0, "Gravitationally Concerning"),
    (38.0, "Cosmologically Impractical"),
    (40.0, "Beyond Classification"),
]

# Fractional suffix modifiers (+0.25 / +0.5 / +0.75 within a band)
_FRAC_SUFFIX = {
    0.00: "",
    0.25: "+",
    0.50: "½",
    0.75: "~",   # 'approaching next size'
}


def _breast_display(size: float) -> str:
    """Return a display string for a breast cup size float."""
    size = max(0.0, round(size, 2))

    # Find the band
    label = _BREAST_CUP_TABLE[0][1]
    for min_val, band_label in reversed(_BREAST_CUP_TABLE):
        if size >= min_val:
            label = band_label
            frac = round(size - min_val, 2)
            # Only show suffix for lettered sizes, not named tiers
            if min_val < 30.0:
                suffix = _FRAC_SUFFIX.get(round(frac % 1.0, 2), "")
                return f"{label}{suffix}"
            else:
                return label
    return label


# ---------------------------------------------------------------------------
# Testicle size display table
# ---------------------------------------------------------------------------

_TESTICLE_TABLE = [
    (0.0,  "Pea-sized"),
    (1.0,  "Small"),
    (2.0,  "Average"),
    (3.0,  "Large"),
    (4.0,  "Very Large"),
    (5.0,  "Oversized"),
    (7.0,  "Grapefruit-sized"),
    (9.0,  "Melon-sized"),
    (11.0, "Cantaloupe-sized"),
    (13.0, "Watermelon-sized"),
    (15.0, "Absurdly Large"),
    (18.0, "Incomprehensibly Large"),
    (22.0, "Load-Bearing"),
    (26.0, "Structurally Significant"),
    (30.0, "Beyond Classification"),
]


def _testicle_display(size: float) -> str:
    size = max(0.0, round(size, 2))
    label = _TESTICLE_TABLE[0][1]
    for min_val, band_label in reversed(_TESTICLE_TABLE):
        if size >= min_val:
            label = band_label
            break
    frac = round(size % 1.0, 2)
    if frac >= 0.5:
        label = f"full {label}"
    return label


# ---------------------------------------------------------------------------
# Penis size display table
# ---------------------------------------------------------------------------

# Uses a 0–30+ scale; display shows length descriptor + girth modifier.
# Base 'average' is 2.0.

_PENIS_LENGTH_TABLE = [
    (0.0,  "Very Small"),
    (1.0,  "Small"),
    (2.0,  "Average"),
    (3.0,  "Above Average"),
    (4.0,  "Large"),
    (5.0,  "Very Large"),
    (6.0,  "Huge"),
    (7.0,  "Massive"),
    (9.0,  "Enormous"),
    (11.0, "Immense"),
    (14.0, "Improbable"),
    (17.0, "Physically Impossible"),
    (20.0, "Architecturally Significant"),
    (24.0, "Mythological"),
    (28.0, "Beyond Classification"),
]

_PENIS_GIRTH_SUFFIX = {
    0.00: "",
    0.25: " (slender)",
    0.50: "",
    0.75: " (thick)",
}


def _penis_display(size: float) -> str:
    size = max(0.0, round(size, 2))
    label = _PENIS_LENGTH_TABLE[0][1]
    for min_val, band_label in reversed(_PENIS_LENGTH_TABLE):
        if size >= min_val:
            label = band_label
            frac = round(size - min_val, 2)
            suffix = _PENIS_GIRTH_SUFFIX.get(round(frac % 1.0, 2), "")
            return f"{label}{suffix}"
    return label


# ---------------------------------------------------------------------------
# Display dispatch
# ---------------------------------------------------------------------------

_DISPLAY_FUNCS = {
    "breast":   _breast_display,
    "testicle": _testicle_display,
    "penis":    _penis_display,
}

# Production rate multipliers per size point above base (used by production items)
_PRODUCTION_MULTIPLIERS = {
    "breast":   0.12,   # +12% base rate per size point
    "testicle": 0.10,
    "penis":    0.08,
}

# Default starting size per type
_DEFAULT_SIZE = {
    "breast":   0.0,    # AA
    "testicle": 2.0,    # Average
    "penis":    2.0,    # Average
}


# ---------------------------------------------------------------------------
# BodyModItem base class
# ---------------------------------------------------------------------------

class BodyModItem(DefaultObject):
    """
    Base class for body modification zone attachments.

    Attributes (stored on db):
        mod_type (str):           'breast', 'testicle', or 'penis'
        size (float):             Current size on the 0–40+ float scale.
        size_perm_bonus (float):  Permanent bonus accumulated from syringe use.
        installed_on_char (obj):  Character this item is installed on, or None.
        installed_on_zone (str):  Zone name this item is installed on, or None.
        syringe_uses (int):       Lifetime syringe injections on this item.
        temp_size_bonus (float):  Current temporary bonus (decays over time).
        temp_bonus_expires (float): Unix timestamp when temp bonus expires.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.mod_type            = "breast"
        self.db.size                = 0.0
        self.db.size_perm_bonus     = 0.0
        self.db.installed_on_char   = None
        self.db.installed_on_zone   = None
        self.db.syringe_uses        = 0
        self.db.temp_size_bonus     = 0.0
        self.db.temp_bonus_expires  = 0.0

    # ------------------------------------------------------------------
    # Effective size (base + perm bonus + unexpired temp bonus)
    # ------------------------------------------------------------------

    def effective_size(self) -> float:
        """Return current effective size, applying temp bonus if unexpired."""
        import time
        base = (self.db.size or 0.0) + (self.db.size_perm_bonus or 0.0)
        temp = self.db.temp_size_bonus or 0.0
        expires = self.db.temp_bonus_expires or 0.0
        if temp > 0 and time.time() < expires:
            return base + temp
        elif temp > 0:
            # Temp bonus has expired — clear it
            self.db.temp_size_bonus    = 0.0
            self.db.temp_bonus_expires = 0.0
        return base

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def display_size(self) -> str:
        """Return a human-readable size string for the current effective size."""
        mod_type = self.db.mod_type or "breast"
        func = _DISPLAY_FUNCS.get(mod_type, _breast_display)
        return func(self.effective_size())

    def production_multiplier(self) -> float:
        """Return the production rate multiplier based on current size."""
        mod_type = self.db.mod_type or "breast"
        per_point = _PRODUCTION_MULTIPLIERS.get(mod_type, 0.1)
        size = self.effective_size()
        return 1.0 + (size * per_point)

    # ------------------------------------------------------------------
    # Install / uninstall
    # ------------------------------------------------------------------

    def install(self, character, zone_name: str) -> tuple:
        """
        Attach this item to character's zone.

        Returns:
            (True, "") on success.
            (False, reason_str) on failure.
        """
        if self.db.installed_on_char:
            return False, f"{self.key} is already installed on {self.db.installed_on_char}."

        # Get zones dict
        zones = getattr(character.db, "zones", None) or {}
        if zone_name not in zones:
            return False, f"{character.db.rp_name or character.name} has no zone called '{zone_name}'."

        # Write into mechanics sub-dict
        zone = dict(zones[zone_name])
        mechanics = dict(zone.get("mechanics", {}) or {})
        if "body_mod" in mechanics:
            return False, f"A body mod item is already installed on the {zone_name} zone."

        mechanics["body_mod"] = {
            "item_dbref": self.dbref,
            "item_name":  self.key,
            "size":       self.effective_size(),
            "mod_type":   self.db.mod_type,
        }
        zone["mechanics"] = mechanics
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        character.db.zones = zones_copy

        # Record on the item
        self.db.installed_on_char = character
        self.db.installed_on_zone = zone_name

        # Move item from inventory to 'on' the character (keep in inventory but
        # flag as installed so it doesn't show in normal inventory listings)
        self.location = character
        self.db.is_installed = True

        return True, ""

    def uninstall(self) -> tuple:
        """
        Remove this item from its current zone.

        Returns:
            (True, "") on success.
            (False, reason) on failure.
        """
        character = self.db.installed_on_char
        zone_name = self.db.installed_on_zone

        if not character or not zone_name:
            return False, f"{self.key} is not currently installed."

        zones = getattr(character.db, "zones", None) or {}
        if zone_name in zones:
            zone = dict(zones[zone_name])
            mechanics = dict(zone.get("mechanics", {}) or {})
            mechanics.pop("body_mod", None)
            zone["mechanics"] = mechanics
            zones_copy = dict(zones)
            zones_copy[zone_name] = zone
            character.db.zones = zones_copy

        self.db.installed_on_char = None
        self.db.installed_on_zone = None
        self.db.is_installed = False

        return True, ""

    def _refresh_mechanics_entry(self):
        """Sync the mechanics snapshot with current effective size."""
        character = self.db.installed_on_char
        zone_name = self.db.installed_on_zone
        if not character or not zone_name:
            return
        zones = getattr(character.db, "zones", None) or {}
        if zone_name not in zones:
            return
        zone = dict(zones[zone_name])
        mechanics = dict(zone.get("mechanics", {}) or {})
        if "body_mod" in mechanics:
            entry = dict(mechanics["body_mod"])
            entry["size"] = self.effective_size()
            mechanics["body_mod"] = entry
            zone["mechanics"] = mechanics
            zones_copy = dict(zones)
            zones_copy[zone_name] = zone
            character.db.zones = zones_copy

    # ------------------------------------------------------------------
    # Size modification helpers (used by lotion + syringe)
    # ------------------------------------------------------------------

    def apply_permanent_boost(self, amount: float):
        """Add a permanent size increment."""
        self.db.size = (self.db.size or 0.0) + amount
        self._refresh_mechanics_entry()

    def apply_temp_boost(self, amount: float, duration_hours: float = 6.0):
        """
        Add a temporary size boost, stacking with any existing temp boost.
        Resets the expiry to now + duration_hours from the time of this call.
        """
        import time
        self.db.temp_size_bonus = (self.db.temp_size_bonus or 0.0) + amount
        self.db.temp_bonus_expires = time.time() + (duration_hours * 3600)
        self._refresh_mechanics_entry()

    def record_syringe_use(self) -> int:
        """Increment syringe use counter and return new total."""
        self.db.syringe_uses = (self.db.syringe_uses or 0) + 1
        return self.db.syringe_uses

    # ------------------------------------------------------------------
    # String representation
    # ------------------------------------------------------------------

    def get_display_name(self, looker=None, **kwargs):
        name = self.key
        if self.db.is_installed and self.db.installed_on_zone:
            name += f" [{self.display_size()} — installed on {self.db.installed_on_zone}]"
        return name


# ---------------------------------------------------------------------------
# Concrete subclasses
# ---------------------------------------------------------------------------

class BreastItem(BodyModItem):
    """
    Breast body mod item.

    Size scale: AA (0.0) → Z (26.0) → ZZ → ZZZZ → named absurd tiers (30.0+)
    Quarter steps produce suffix modifiers: AA, AA+, AA½, A~, A, A+, ...
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.mod_type = "breast"
        self.db.size     = _DEFAULT_SIZE["breast"]   # 0.0 = AA
        self.key         = "breast item"


class TesticleItem(BodyModItem):
    """
    Testicle body mod item.

    Size scale uses volume descriptors from Pea-sized (0.0) upward.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.mod_type = "testicle"
        self.db.size     = _DEFAULT_SIZE["testicle"]  # 2.0 = Average
        self.key         = "testicle item"


class PenisItem(BodyModItem):
    """
    Penis body mod item.

    Size scale uses length+girth descriptors from Very Small (0.0) upward.
    Quarter fractional steps produce slender/thick modifiers.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.mod_type = "penis"
        self.db.size     = _DEFAULT_SIZE["penis"]    # 2.0 = Average
        self.key         = "penis item"
