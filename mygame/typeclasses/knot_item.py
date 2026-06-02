"""
typeclasses/knot_item.py

KnotItem — installs a knot mechanic on a shaft zone.

Any character can install a knot on their shaft zone regardless of species.
The knot triggers during the thrust command when arousal >= threshold,
blocking withdrawal for a configurable duration. Both parties remain engaged
during the tie and arousal continues building.

Install: use the standard 'install Knot' command on a shaft zone.

Knot state tracked on caller.db.penetrating:
  {
    ...,
    "knotted": bool,
    "knot_expires_at": float (unix timestamp),
  }

Duration modifiers:
  CaniAid  — temporary bonus (+60s for 4h), 5 doses
  CaniMax  — permanent bonus (+120s, stacks), 3 doses
  Applied via: inject/knot <target> [zone]

YAML pools (add to milking_messages.yaml or a new knot_messages.yaml):
  knot_trigger  — room-visible when knot engages
  knot_held     — private to target when they try to withdraw while tied
  knot_release  — room-visible when the tie releases naturally
"""

import time
from evennia import DefaultObject

# Arousal threshold before knot can engage
KNOT_AROUSAL_THRESHOLD = 70.0

# Per-thrust chance of knot engaging once threshold is met
KNOT_TRIGGER_CHANCE = 0.25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_knot_data(char, zone_name: str) -> dict | None:
    """Return the knot mechanics dict for a zone, or None."""
    zones = getattr(char.db, "zones", None) or {}
    return (
        zones.get(zone_name, {})
             .get("mechanics", {}) or {}
    ).get("knot")


def _set_knot_data(char, zone_name: str, knot_dict: dict):
    """Write knot mechanics dict back to the zone."""
    zones = getattr(char.db, "zones", None) or {}
    zone  = dict(zones.get(zone_name, {}))
    mech  = dict(zone.get("mechanics", {}) or {})
    mech["knot"] = knot_dict
    zone["mechanics"] = mech
    zones_copy = dict(zones)
    zones_copy[zone_name] = zone
    char.db.zones = zones_copy


def get_effective_duration(char, zone_name: str) -> float:
    """
    Return the current effective knot duration (seconds) including
    permanent and unexpired temporary bonuses.
    """
    knot = _get_knot_data(char, zone_name) or {}
    base = knot.get("base_duration", 120.0)
    perm = knot.get("perm_bonus", 0.0)

    temp       = knot.get("temp_bonus", 0.0)
    temp_exp   = knot.get("temp_expires_at", 0.0)
    temp_active = temp > 0 and time.time() < temp_exp

    return base + perm + (temp if temp_active else 0.0)


def try_trigger_knot(caller, target, shaft_zone: str, room) -> bool:
    """
    Called by CmdThrust when arousal is at threshold.
    Returns True if knot engaged.
    """
    import random

    arousal = caller.db.arousal or 0.0
    if arousal < KNOT_AROUSAL_THRESHOLD:
        return False

    engaged = caller.db.penetrating or {}
    if engaged.get("knotted"):
        return False   # already tied

    knot = _get_knot_data(caller, shaft_zone)
    if not knot:
        return False

    if random.random() > KNOT_TRIGGER_CHANCE:
        return False

    # Engage knot
    duration = get_effective_duration(caller, shaft_zone)
    engaged["knotted"]         = True
    engaged["knot_expires_at"] = time.time() + duration
    engaged["knot_zone"]       = shaft_zone
    caller.db.penetrating = engaged

    caller_name = caller.db.rp_name or caller.name
    target_name = target.db.rp_name or target.name

    # Message — [PLACEHOLDER: add pool to milking_messages.yaml under knot/trigger]
    room.msg_contents(
        f"{caller_name} and {target_name} — the knot has engaged. "
        f"Withdrawal is not immediately possible."
    )

    return True


def check_knot_release(caller) -> bool:
    """
    Check if an active knot has expired and release it if so.
    Returns True if knot released naturally.
    """
    engaged = caller.db.penetrating or {}
    if not engaged.get("knotted"):
        return False

    if time.time() >= engaged.get("knot_expires_at", 0):
        engaged["knotted"]         = False
        engaged["knot_expires_at"] = 0.0
        caller.db.penetrating = engaged
        return True

    return False


# ---------------------------------------------------------------------------
# KnotItem
# ---------------------------------------------------------------------------

class KnotItem(DefaultObject):
    """
    Installs a knot mechanic on any shaft zone.

    Usage:
      install Knot       — installs on your shaft zone (must have shaft zone set up)
      inject/knot <target> [zone]   — apply Cani-aid or Cani-max
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.base_duration      = 120.0   # 2 minutes base tie
        self.db.installed_on_char  = None
        self.db.installed_on_zone  = None
        self.key = "Knot"

    def install(self, character, zone_name: str) -> tuple:
        """Attach knot to a shaft zone. Returns (True, "") or (False, reason)."""
        zones = getattr(character.db, "zones", None) or {}
        if zone_name not in zones:
            return False, f"No zone '{zone_name}' found."

        zone_type = (zones[zone_name] or {}).get("zone_type", "")
        if zone_type != "shaft":
            return False, (
                f"The knot can only be installed on a shaft-type zone. "
                f"'{zone_name}' is type '{zone_type}'."
            )

        if _get_knot_data(character, zone_name):
            return False, f"A knot is already installed on '{zone_name}'."

        _set_knot_data(character, zone_name, {
            "base_duration":   self.db.base_duration,
            "perm_bonus":      0.0,
            "temp_bonus":      0.0,
            "temp_expires_at": 0.0,
        })

        self.db.installed_on_char = character
        self.db.installed_on_zone = zone_name
        self.location             = character

        return True, ""

    def get_display_name(self, looker=None, **kwargs):
        if self.db.installed_on_zone:
            return f"Knot [installed on {self.db.installed_on_zone}]"
        return "Knot (uninstalled)"


# ---------------------------------------------------------------------------
# CaniAid — temporary knot duration boost
# ---------------------------------------------------------------------------

class CaniAid(DefaultObject):
    """
    Temporary knot duration extension. +60 seconds for 4 hours. 5 doses.
    Applied via: inject/knot <target> [zone]
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.temp_bonus     = 60.0     # +60s
        self.db.duration_hours = 4.0
        self.db.uses_remaining = 5
        self.db.label          = "Cani-aid"
        self.key               = "Cani-aid"

    def apply(self, actor, target, zone_name: str) -> tuple:
        knot = _get_knot_data(target, zone_name)
        if not knot:
            return False, (
                f"No knot installed on "
                f"{target.db.rp_name or target.name}'s {zone_name}."
            )

        knot = dict(knot)
        knot["temp_bonus"]      = (knot.get("temp_bonus", 0.0) + self.db.temp_bonus)
        knot["temp_expires_at"] = time.time() + self.db.duration_hours * 3600
        _set_knot_data(target, zone_name, knot)

        actor_name  = actor.db.rp_name  or actor.name
        target_name = target.db.rp_name or target.name
        zone_disp   = zone_name.replace("_", " ")

        uses = self.db.uses_remaining or 0
        spent = False
        if uses > 0:
            new_uses = uses - 1
            if new_uses <= 0:
                spent = True
            else:
                self.db.uses_remaining = new_uses

        if actor == target:
            msg = (
                f"You apply {self.db.label} to your {zone_disp}. "
                f"(+{self.db.temp_bonus:.0f}s knot duration for {int(self.db.duration_hours)}h)"
            )
        else:
            msg = (
                f"{actor_name} applies {self.db.label} to "
                f"{target_name}'s {zone_disp}. "
                f"(+{self.db.temp_bonus:.0f}s for {int(self.db.duration_hours)}h)"
            )

        if spent:
            msg += f"\n|x[Last dose — {self.key} is spent.]|n"
            self.delete()

        return True, msg

    def get_display_name(self, looker=None, **kwargs):
        uses = self.db.uses_remaining
        return f"{self.key} ({uses} dose{'s' if uses != 1 else ''} remaining)"


# ---------------------------------------------------------------------------
# CaniMax — permanent knot duration increase
# ---------------------------------------------------------------------------

class CaniMax(DefaultObject):
    """
    Permanent knot duration increase. +120 seconds, stacks. 3 doses.
    Applied via: inject/knot <target> [zone]
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.perm_bonus     = 120.0    # +2 minutes permanent
        self.db.uses_remaining = 3
        self.db.label          = "Cani-max"
        self.key               = "Cani-max"

    def apply(self, actor, target, zone_name: str) -> tuple:
        knot = _get_knot_data(target, zone_name)
        if not knot:
            return False, (
                f"No knot installed on "
                f"{target.db.rp_name or target.name}'s {zone_name}."
            )

        knot = dict(knot)
        knot["perm_bonus"] = knot.get("perm_bonus", 0.0) + self.db.perm_bonus
        _set_knot_data(target, zone_name, knot)

        actor_name  = actor.db.rp_name  or actor.name
        target_name = target.db.rp_name or target.name
        zone_disp   = zone_name.replace("_", " ")

        uses = self.db.uses_remaining or 0
        spent = False
        if uses > 0:
            new_uses = uses - 1
            if new_uses <= 0:
                spent = True
            else:
                self.db.uses_remaining = new_uses

        if actor == target:
            msg = (
                f"You apply {self.db.label} to your {zone_disp}. "
                f"(+{self.db.perm_bonus:.0f}s knot duration — permanent)"
            )
        else:
            msg = (
                f"{actor_name} applies {self.db.label} to "
                f"{target_name}'s {zone_disp}. "
                f"(+{self.db.perm_bonus:.0f}s permanent)"
            )

        if spent:
            msg += f"\n|x[Last dose — {self.key} is spent.]|n"
            self.delete()

        return True, msg

    def get_display_name(self, looker=None, **kwargs):
        uses = self.db.uses_remaining
        return f"{self.key} ({uses} dose{'s' if uses != 1 else ''} remaining)"
