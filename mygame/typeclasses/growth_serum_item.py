"""
typeclasses/growth_serum_item.py

GrowthSerumItem — a single-use-per-dose injectable that applies a permanent
size boost to an installed BodyModItem AND permanently increases the base
production rate of any ProductionItem installed on the same zone.

Contrast with SyringeItem (temp boost, escalating perm) and LotionItem
(perm size only, no production effect). The serum does both at once,
permanently, from the first dose.

Usage (via inject/serum switch in body_mod_commands.py CmdInject):
    inject/serum <target> [zone]
    inject/serum/self [zone]

Attributes (db):
    perm_size_boost (float):      Size permanently added per dose (default 0.5).
    perm_rate_boost_ml (float):   ml/tick added permanently to ProductionItem
                                  base_rate_ml_per_tick per dose (default 15.0).
    uses_remaining (int):         0 = unlimited; otherwise decrements per dose.
    label (str):                  Display name used in messages.
"""

from evennia import DefaultObject


class GrowthSerumItem(DefaultObject):
    """
    Permanent size + production rate booster.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.perm_size_boost   = 0.5    # permanent size increment per dose
        self.db.perm_rate_boost_ml = 15.0  # ml/tick added to production rate per dose
        self.db.uses_remaining    = 3
        self.db.label             = "the growth serum"
        self.key                  = "growth serum"

    # ------------------------------------------------------------------
    # Core administer method
    # ------------------------------------------------------------------

    def administer(self, actor, target, zone_name: str) -> tuple:
        """
        Administer one dose to the target's zone.

        Applies:
          1. Permanent size boost to the BodyModItem installed on zone_name.
          2. Permanent base_rate_ml_per_tick boost to any ProductionItem
             installed on the same zone.

        Returns:
            (True, room_message_str) on success.
            (False, error_str) on failure.
        """
        uses = self.db.uses_remaining or 0
        if uses == 0:
            pass   # unlimited
        elif uses < 1:
            return False, f"{self.key} is empty."

        # ── Validate zone ─────────────────────────────────────────────
        zones = getattr(target.db, "zones", None) or {}
        if zone_name not in zones:
            return False, (
                f"{target.db.rp_name or target.name} has no zone called '{zone_name}'."
            )

        zone      = zones[zone_name]
        mechanics = zone.get("mechanics", {}) or {}
        bm_entry  = mechanics.get("body_mod")

        if not bm_entry:
            return False, (
                f"There's nothing on {target.db.rp_name or target.name}'s "
                f"{zone_name} zone to administer the serum to."
            )

        # ── Apply permanent size boost to BodyModItem ─────────────────
        from evennia import search_object
        results = search_object(bm_entry.get("item_dbref", ""), exact=True)
        if not results:
            return False, "The installed body mod item could not be found."

        body_mod  = results[0]
        if not hasattr(body_mod, "apply_permanent_boost"):
            return False, "The installed item does not support size modification."

        old_size  = body_mod.display_size()
        size_inc  = self.db.perm_size_boost or 0.5
        body_mod.apply_permanent_boost(size_inc)
        new_size  = body_mod.display_size()

        # ── Apply production rate boost if a ProductionItem is on zone ─
        from typeclasses.production_item import ProductionItem
        rate_inc       = self.db.perm_rate_boost_ml or 15.0
        prod_item_found = None

        for obj in target.contents:
            if (
                isinstance(obj, ProductionItem)
                and getattr(obj.db, "is_installed", False)
                and getattr(obj.db, "installed_on_zone", None) == zone_name
            ):
                prod_item_found = obj
                break

        if prod_item_found:
            current_rate = prod_item_found.db.base_rate_ml_per_tick or 0.0
            prod_item_found.db.base_rate_ml_per_tick = current_rate + rate_inc

        # ── Decrement uses ────────────────────────────────────────────
        if uses > 0:
            self.db.uses_remaining = uses - 1

        # ── Build message ─────────────────────────────────────────────
        target_name = target.db.rp_name or target.name
        actor_name  = actor.db.rp_name  or actor.name
        zone_disp   = zone_name.replace("_", " ")

        if actor == target:
            msg = (
                f"You administer {self.db.label} to your {zone_disp}. "
                f"({old_size} → {new_size}, +{size_inc:.2f} size — permanent"
            )
        else:
            msg = (
                f"{actor_name} administers {self.db.label} to "
                f"{target_name}'s {zone_disp}. "
                f"({old_size} → {new_size}, +{size_inc:.2f} size — permanent"
            )

        if prod_item_found:
            msg += f", +{rate_inc:.0f}ml/tick production — permanent"
        msg += ")"

        uses_after = self.db.uses_remaining
        if uses > 0 and uses_after == 0:
            msg += f"\n|x[{self.key} is now empty]|n"

        return True, msg

    def get_display_name(self, looker=None, **kwargs):
        name = self.key
        uses = self.db.uses_remaining or 0
        if uses == 0:
            name += " (unlimited)"
        else:
            name += f" ({uses} dose{'s' if uses != 1 else ''} remaining)"
        return name
