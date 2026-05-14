"""
web/housing/models.py

Tracks housing plot allocations for Re:Void characters.

Each character that has purchased a tent gets one HousingPlot row.
rooms_total  = total room slots purchased (tent = 1, packs add more)
rooms_used   = rooms actually dug / created so far

The HousingRoom typeclass (typeclasses/housing.py) stores the actual
room data (owner, friends, builders, lock state) on each room object.
This model is purely for the allocation ledger.
"""

from django.db import models


# ---------------------------------------------------------------------------
# Pricing constants — single source of truth used by commands + Durgin
# ---------------------------------------------------------------------------

TENT_PRICE = 50          # base tent (1 room slot)

ROOM_PACK_PRICES = {
    1:  200,
    5:  900,
    10: 1_700,
    20: 3_200,
    25: 3_750,
}


class HousingPlot(models.Model):
    """
    One row per character that owns housing.

    character_id  — ObjectDB pk of the owning character
    rooms_total   — total room slots purchased
    rooms_used    — slots consumed by dug rooms
    """
    character_id = models.IntegerField(
        unique=True,
        db_index=True,
        help_text="ObjectDB pk of the owning character.",
    )
    rooms_total = models.IntegerField(
        default=1,
        help_text="Total room slots purchased (tent gives 1, packs add more).",
    )
    rooms_used = models.IntegerField(
        default=1,
        help_text="Room slots consumed by created rooms.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["character_id"]

    def __str__(self):
        return (
            f"Plot #{self.character_id}: "
            f"{self.rooms_used}/{self.rooms_total} rooms used"
        )

    @property
    def rooms_available(self):
        """Slots left to dig."""
        return max(0, self.rooms_total - self.rooms_used)

    @classmethod
    def get_or_none(cls, character_id):
        """Return the plot for this character, or None."""
        try:
            return cls.objects.get(character_id=character_id)
        except cls.DoesNotExist:
            return None
