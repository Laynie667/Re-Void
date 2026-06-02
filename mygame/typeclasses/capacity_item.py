"""
typeclasses/capacity_item.py

CapacityItem — modifies the maximum accumulation capacity of a production zone.

Installs a "capacity_bonus" entry into the zone's mechanics dict.  The
ProductionItem.get_max_volume_ml() method reads this and adds the bonus.

Temporary (Cap-aid): bonus expires after duration_hours.
Permanent (Cap-max): bonus is permanent, stacks with repeated use.

Usage (via inject/cap in body_mod_commands.py CmdInject):
    inject/cap <target> [zone]
    inject/cap/self [zone]
"""

import time
from evennia import DefaultObject


class CapacityItem(DefaultObject):
    """
    Zone capacity modifier.

    Attributes (db):
        capacity_bonus_ml (float): ml added to max capacity per use.
        is_permanent (bool):       True = permanent; False = temp.
        duration_hours (float):    Hours the bonus lasts (temp only).
        uses_remaining (int):      0 = unlimited.
        label (str):               Display name in messages.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.capacity_bonus_ml = 300.0
        self.db.is_permanent      = False
        self.db.duration_hours    = 6.0
        self.db.uses_remaining    = 3
        self.db.label             = "the capacity item"
        self.key                  = "capacity item"

    # ------------------------------------------------------------------

    def apply(self, actor, target, zone_name: str) -> tuple:
        """
        Apply one dose to target's zone.

        Returns (True, room_message) or (False, error_str).
        """
        uses = self.db.uses_remaining or 0
        if uses == 0:
            pass   # unlimited
        elif uses < 1:
            return False, f"{self.key} is empty."

        zones = getattr(target.db, "zones", None) or {}
        if zone_name not in zones:
            return False, (
                f"{target.db.rp_name or target.name} has no zone called '{zone_name}'."
            )

        bonus    = self.db.capacity_bonus_ml or 300.0
        is_perm  = self.db.is_permanent
        duration = self.db.duration_hours or 6.0

        # ── Update zone mechanics ────────────────────────────────────────
        zone      = dict(zones[zone_name])
        mechanics = dict(zone.get("mechanics", {}) or {})
        existing  = mechanics.get("capacity_bonus", {}) or {}

        if is_perm:
            # Stack permanently
            old_bonus = existing.get("bonus_ml", 0.0) if existing.get("expires_at") is None else 0.0
            mechanics["capacity_bonus"] = {
                "bonus_ml":  old_bonus + bonus,
                "expires_at": None,
            }
        else:
            # Overwrite temp bonus (extend if already active)
            mechanics["capacity_bonus"] = {
                "bonus_ml":  bonus,
                "expires_at": time.time() + duration * 3600,
            }

        zone["mechanics"] = mechanics
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        target.db.zones = zones_copy

        # ── Decrement / delete on last dose ────────────────────────────
        spent = False
        if uses > 0:
            new_uses = uses - 1
            if new_uses <= 0:
                spent = True
            else:
                self.db.uses_remaining = new_uses

        # ── Build message ──────────────────────────────────────────────
        from typeclasses.production_item import format_volume
        actor_name  = actor.db.rp_name  or actor.name
        target_name = target.db.rp_name or target.name
        zone_disp   = zone_name.replace("_", " ")
        perm_str    = "permanent" if is_perm else f"~{int(duration)}h"

        if actor == target:
            msg = (
                f"You apply {self.db.label} to your {zone_disp}. "
                f"(+{format_volume(bonus)} capacity, {perm_str})"
            )
        else:
            msg = (
                f"{actor_name} applies {self.db.label} to "
                f"{target_name}'s {zone_disp}. "
                f"(+{format_volume(bonus)} capacity, {perm_str})"
            )

        if spent:
            msg += f"\n|x[Last use — {self.key} is spent.]|n"
            self.delete()

        return True, msg

    def get_display_name(self, looker=None, **kwargs):
        name = self.key
        uses = self.db.uses_remaining
        if uses is None or uses == 0:
            name += " (unlimited)"
        elif uses < 0:
            name += " (empty)"
        else:
            name += f" ({uses} use{'s' if uses != 1 else ''} remaining)"
        return name
