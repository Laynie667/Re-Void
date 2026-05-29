"""
typeclasses/syringe_item.py

Syringe item — injects a significant temporary size boost into an installed
BodyModItem on a target character's zone.

Permanent escalation:
    - Each injection increments the BodyModItem's syringe_uses counter.
    - While uses <= TEMP_ONLY_THRESHOLD, injection is purely temporary.
    - Past that threshold, each injection ALSO writes a small permanent increment
      (PERM_INCREMENT_BASE) to the item's size_perm_bonus.
    - The permanent increment scales upward in tiers (PERM_TIERS) as total use
      increases, so occasional use stays cosmetic, habitual use has lasting effects.

Stacking:
    - Multiple temp boosts stack additively.
    - The expiry is reset to now + TEMP_DURATION_HOURS from the time of each injection.
    - There is no hard cap on stacking, but display_size() will show the absurd tier
      labels once the effective size gets high enough.

Usage (via commands/body_mod_commands.py CmdInject):
    inject <target> [zone]
    inject/self [zone]    — inject yourself
"""

import time
from evennia import DefaultObject


# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

TEMP_BOOST_AMOUNT    = 1.0     # size points per injection (temp)
TEMP_DURATION_HOURS  = 6.0     # hours the temp boost lasts

TEMP_ONLY_THRESHOLD  = 5       # injections before permanent effects begin

# Permanent increment tiers: (min_total_uses, perm_increment_per_injection)
PERM_TIERS = [
    (6,  0.05),   # uses 6–10:  +0.05 permanent per injection
    (11, 0.10),   # uses 11–20: +0.10 permanent per injection
    (21, 0.15),   # uses 21–35: +0.15 permanent per injection
    (36, 0.20),   # uses 36+:   +0.20 permanent per injection
]


def _perm_increment_for_use(total_uses: int) -> float:
    """Return the permanent increment size for the given total use count."""
    if total_uses <= TEMP_ONLY_THRESHOLD:
        return 0.0
    increment = 0.0
    for min_uses, inc in reversed(PERM_TIERS):
        if total_uses >= min_uses:
            increment = inc
            break
    return increment


# ---------------------------------------------------------------------------
# SyringeItem
# ---------------------------------------------------------------------------

class SyringeItem(DefaultObject):
    """
    Size-boosting syringe.

    Attributes (db):
        boost_amount (float):       Temp size boost per injection (default 1.0).
        temp_duration_hours (float): Hours the temp boost lasts (default 6).
        uses_remaining (int):        0 = unlimited; otherwise decrements.
        label (str):                 Display name used in messages.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.boost_amount         = TEMP_BOOST_AMOUNT
        self.db.temp_duration_hours  = TEMP_DURATION_HOURS
        self.db.uses_remaining       = 5      # default; override at spawn
        self.db.label                = "the syringe"
        self.key                     = "syringe"

    # ------------------------------------------------------------------
    # Core inject method
    # ------------------------------------------------------------------

    def inject(self, actor, target, zone_name: str) -> tuple:
        """
        Inject the target's zone.

        Args:
            actor:      Character performing the injection.
            target:     Character being injected.
            zone_name:  Zone name string.

        Returns:
            (True, message_for_room) on success.
            (False, error_message) on failure.
        """
        uses = self.db.uses_remaining or 0
        if uses == 0:
            pass   # unlimited
        elif uses < 1:
            return False, f"{self.key} is empty."

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
                f"There's nothing on {target.db.rp_name or target.name}'s "
                f"{zone_name} zone to inject."
            )

        # Fetch the BodyModItem
        from evennia import search_object
        results = search_object(bm_entry.get("item_dbref", ""), exact=True)
        if not results:
            return False, "The installed item could not be found."

        body_mod = results[0]
        if not hasattr(body_mod, "apply_temp_boost"):
            return False, "The installed item does not support size modification."

        old_effective = body_mod.effective_size()
        old_display   = body_mod.display_size()

        # Apply temp boost
        boost    = self.db.boost_amount or TEMP_BOOST_AMOUNT
        duration = self.db.temp_duration_hours or TEMP_DURATION_HOURS
        body_mod.apply_temp_boost(boost, duration_hours=duration)

        # Record use and calculate permanent increment
        new_total  = body_mod.record_syringe_use()
        perm_inc   = _perm_increment_for_use(new_total)
        if perm_inc > 0:
            body_mod.apply_permanent_boost(perm_inc)

        new_display = body_mod.display_size()

        # Decrement uses
        if uses > 0:
            self.db.uses_remaining = uses - 1

        # Build message
        target_name = target.db.rp_name or target.name
        actor_name  = actor.db.rp_name  or actor.name
        zone_disp   = zone_name.replace("_", " ")
        expiry_h    = int(duration)

        if actor == target:
            msg = (
                f"You inject {self.db.label} into your {zone_disp}. "
                f"({old_display} → {new_display}, "
                f"~{expiry_h}h temp boost"
            )
        else:
            msg = (
                f"{actor_name} injects {self.db.label} into "
                f"{target_name}'s {zone_disp}. "
                f"({old_display} → {new_display}, "
                f"~{expiry_h}h temp boost"
            )

        if perm_inc > 0:
            msg += f", +{perm_inc:.2f} permanent [{new_total} total uses]"
        msg += ")"

        # Escalation warnings
        if new_total == TEMP_ONLY_THRESHOLD + 1:
            msg += (
                f"\n|r[Repeated use is beginning to leave permanent changes.]|n"
            )
        elif new_total in (21, 36):
            msg += f"\n|r[The permanent effects are accelerating.]|n"

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
            name += f" ({uses} use{'s' if uses != 1 else ''} remaining)"
        return name
