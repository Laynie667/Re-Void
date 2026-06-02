"""
typeclasses/production_injection_item.py

ProductionInjectionItem — injects a temporary production rate boost into an
installed ProductionItem on a character's zone.

Unlike SyringeItem (which boosts body mod size), this targets the fluid
output rate directly.  Repeated use can optionally add a small permanent
rate increment (configured per item).

Usage (via inject/prod in body_mod_commands.py CmdInject):
    inject/prod <target> [zone]
    inject/prod/self [zone]

Item variants sold by Durgin:
    Lact-O      — mild temp rate boost, 5 doses
    Lact-O-max  — aggressive temp rate boost, 3 doses, small perm increment
"""

import time
from evennia import DefaultObject


class ProductionInjectionItem(DefaultObject):
    """
    Temporary production rate booster.

    Attributes (db):
        rate_boost_ml_per_tick (float): Added to base_rate for duration.
        duration_hours (float):         How long the boost lasts.
        perm_rate_increment (float):    Permanent rate added per dose (0 = none).
        uses_remaining (int):           0 = unlimited; decrements per use.
        label (str):                    Display name in messages.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.rate_boost_ml_per_tick = 15.0
        self.db.duration_hours         = 6.0
        self.db.perm_rate_increment    = 0.0    # no perm boost by default
        self.db.uses_remaining         = 5
        self.db.label                  = "the injection"
        self.key                       = "production injection"

    # ------------------------------------------------------------------

    def inject(self, actor, target, zone_name: str) -> tuple:
        """
        Apply one dose to target's production item on zone_name.

        Returns (True, room_message) or (False, error_str).
        """
        uses = self.db.uses_remaining or 0
        if uses == 0:
            pass   # unlimited
        elif uses < 1:
            return False, f"{self.key} is empty."

        # ── Find production item on zone ──────────────────────────────
        zones = getattr(target.db, "zones", None) or {}
        if zone_name not in zones:
            return False, (
                f"{target.db.rp_name or target.name} has no zone called '{zone_name}'."
            )

        mechanics = (zones[zone_name].get("mechanics", {}) or {})
        prod_entry = mechanics.get("production")
        if not prod_entry:
            return False, (
                f"No production item installed on {target.db.rp_name or target.name}'s "
                f"{zone_name} zone."
            )

        from evennia import search_object
        from typeclasses.production_item import ProductionItem
        results = search_object(prod_entry.get("item_dbref", ""), exact=True)
        if not results or not isinstance(results[0], ProductionItem):
            return False, "The installed production item could not be found."

        prod_item = results[0]
        boost     = self.db.rate_boost_ml_per_tick or 15.0
        duration  = self.db.duration_hours         or 6.0

        # ── Apply temp rate boost (stacks) ─────────────────────────────
        current_boost  = prod_item.db.temp_rate_boost      or 0.0
        prod_item.db.temp_rate_boost      = current_boost + boost
        prod_item.db.temp_rate_expires_at = time.time() + duration * 3600

        # ── Optional permanent rate increment ──────────────────────────
        perm_inc = self.db.perm_rate_increment or 0.0
        if perm_inc > 0:
            old_base = prod_item.db.base_rate_ml_per_tick or 8.0
            prod_item.db.base_rate_ml_per_tick = old_base + perm_inc

        # ── Decrement / delete on last dose ────────────────────────────
        spent = False
        if uses > 0:
            new_uses = uses - 1
            if new_uses <= 0:
                spent = True
            else:
                self.db.uses_remaining = new_uses

        # ── Build message ──────────────────────────────────────────────
        actor_name  = actor.db.rp_name  or actor.name
        target_name = target.db.rp_name or target.name
        zone_disp   = zone_name.replace("_", " ")
        expiry_h    = int(duration)

        if actor == target:
            msg = (
                f"You administer {self.db.label} to your {zone_disp}. "
                f"(+{boost:.0f}ml/tick for ~{expiry_h}h"
            )
        else:
            msg = (
                f"{actor_name} administers {self.db.label} to "
                f"{target_name}'s {zone_disp}. "
                f"(+{boost:.0f}ml/tick for ~{expiry_h}h"
            )

        if perm_inc > 0:
            msg += f", +{perm_inc:.1f}ml/tick permanent"
        msg += ")"

        if spent:
            msg += f"\n|x[Last dose — {self.key} is spent.]|n"
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
            name += f" ({uses} dose{'s' if uses != 1 else ''} remaining)"
        return name
