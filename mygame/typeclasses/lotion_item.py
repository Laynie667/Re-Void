"""
typeclasses/lotion_item.py

Lotion item — applies a permanent size increase to an installed BodyModItem
on a target character's zone.

Usage (via commands/body_mod_commands.py CmdApplyLotion):
    lotion <zone>                — apply to your own zone
    lotion <target>'s <zone>    — apply to another character's zone (requires consent)

Rules:
    - Only has effect if a BodyModItem is installed on the target zone.
    - Applies boost_amount (default 0.25–0.5) as a permanent size increment.
    - Lotion is a consumable: uses_remaining decrements on each application.
      Set uses_remaining = 0 for unlimited (e.g. staff-only bottles).
    - Anyone in the room can apply it (no permission gate beyond consent system).
"""

from evennia import DefaultObject


class LotionItem(DefaultObject):
    """
    Permanent size-boost consumable.

    Attributes (db):
        boost_amount (float):   Size increment per application (default 0.25).
        uses_remaining (int):   Applications left; 0 = unlimited.
        label (str):            Display name shown in apply messages.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.boost_amount    = 0.25
        self.db.uses_remaining  = 10      # default; override at spawn
        self.db.label           = "the lotion"
        self.key                = "lotion"

    # ------------------------------------------------------------------
    # Core apply method
    # ------------------------------------------------------------------

    def apply(self, actor, target, zone_name: str) -> tuple:
        """
        Apply the lotion to target's zone.

        Args:
            actor:      Character doing the applying.
            target:     Character being applied to (may be same as actor).
            zone_name:  Zone name string.

        Returns:
            (True, message) on success.
            (False, error_message) on failure.
        """
        # Unlimited uses?
        uses = self.db.uses_remaining or 0
        if uses == 1:
            # Last use — will consume after application
            pass
        elif uses == 0:
            pass  # unlimited
        elif uses < 1:
            return False, f"{self.key} is empty — there's nothing left to apply."

        # Find the body mod item on the target zone
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
                f"There's nothing on {target.db.rp_name or target.name}'s {zone_name} "
                f"for {self.key} to affect."
            )

        # Fetch the actual BodyModItem
        from evennia import search_object
        results = search_object(bm_entry.get("item_dbref", ""), exact=True)
        if not results:
            return False, "The installed item could not be found (dbref mismatch)."

        body_mod = results[0]
        if not hasattr(body_mod, "apply_permanent_boost"):
            return False, "The installed item does not support size modification."

        # Apply boost
        old_display = body_mod.display_size()
        body_mod.apply_permanent_boost(self.db.boost_amount or 0.25)
        new_display = body_mod.display_size()

        # Decrement uses
        if uses > 0:
            self.db.uses_remaining = uses - 1

        # Build result message
        target_name = target.db.rp_name or target.name
        actor_name  = actor.db.rp_name  or actor.name
        zone_disp   = zone_name.replace("_", " ")

        if actor == target:
            msg = (
                f"You work {self.db.label} into your {zone_disp}. "
                f"({old_display} → {new_display})"
            )
        else:
            msg = (
                f"{actor_name} works {self.db.label} into {target_name}'s {zone_disp}. "
                f"({old_display} → {new_display})"
            )

        uses_after = self.db.uses_remaining
        if uses_after == 1:
            msg += f" |x[{self.key}: 1 use remaining]|n"
        elif uses_after == 0 and uses != 0:
            msg += f" |x[{self.key} is now empty]|n"

        return True, msg

    def get_display_name(self, looker=None, **kwargs):
        name = self.key
        uses = self.db.uses_remaining or 0
        if uses == 0:
            name += " (unlimited)"
        else:
            name += f" ({uses} use{'s' if uses != 1 else ''} remaining)"
        return name
