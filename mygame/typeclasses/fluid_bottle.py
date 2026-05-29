"""
typeclasses/fluid_bottle.py

A bottle of fluid produced by the milking machine.

Attributes (db):
    producer_name (str):    RP name of the character who was milked.
    fluid_type (str):       'milk', 'semen', 'urine', or any custom string.
    fluid_flavor (str|None): Free-text flavor note, or None.
    volume_ml (float):      Volume in the bottle.
    is_empty (bool):        True once drunk/emptied.

Drink behavior:
    - Known types (milk, semen, urine): lead line uses the type name directly.
    - Custom types: lead line uses "That isn't milk..." + flavor for description.
    - Empty bottle gives a distinct message.

The bottle can be placed in fridge stock via commands/fridge system.
It is a normal inventory object — the milking machine creates it in the room
and players can pick it up, drink from it, or stock the fridge with it.
"""

from evennia import DefaultObject
from typeclasses.production_item import format_volume


_KNOWN_FLUID_TYPES = {"milk", "semen", "urine"}


def _drink_message(producer_name: str, fluid_type: str,
                   fluid_flavor: str | None, volume_ml: float) -> str:
    """
    Build the drink message for a sip from the bottle.

    Args:
        producer_name:  RP name of whoever was milked.
        fluid_type:     Fluid type string.
        fluid_flavor:   Optional flavor description.
        volume_ml:      Current volume (used to decide 'last sip' note).

    Returns:
        A string suitable for msg() to the drinker.
    """
    flavor_line = f" It tastes of {fluid_flavor}." if fluid_flavor else ""

    if fluid_type in _KNOWN_FLUID_TYPES:
        first_line = f"You take a sip from the bottle. It's {producer_name}'s {fluid_type}.{flavor_line}"
    else:
        # Custom fluid type — mystery first, then flavor
        if fluid_flavor:
            first_line = (
                f"You take a sip from the bottle. ...That isn't milk. "
                f"It tastes of {fluid_flavor}."
            )
        else:
            first_line = (
                f"You take a sip from the bottle. ...That isn't milk."
            )

    if volume_ml < 30:
        first_line += " |x(nearly empty)|n"

    return first_line


class FluidBottle(DefaultObject):
    """
    A bottle of fluids harvested by the milking machine.

    Players can drink from it (partial sips) or drain it entirely.
    The fridge system can stock it and dispense individual sips.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.producer_name  = "Unknown"
        self.db.fluid_type     = "fluid"
        self.db.fluid_flavor   = None
        self.db.volume_ml      = 0.0
        self.db.is_empty       = False
        self.db.sip_size_ml    = 30.0    # ml consumed per sip

    # ------------------------------------------------------------------
    # Drink
    # ------------------------------------------------------------------

    def do_drink(self, drinker, drain: bool = False) -> str:
        """
        Have drinker take a sip (or drain the bottle if drain=True).

        Returns the message to send to the drinker.
        """
        if self.db.is_empty or (self.db.volume_ml or 0) <= 0:
            return "The bottle is empty."

        vol  = self.db.volume_ml or 0.0
        if drain:
            consumed = vol
        else:
            consumed = min(self.db.sip_size_ml or 30.0, vol)

        self.db.volume_ml = max(0.0, vol - consumed)
        if self.db.volume_ml <= 0:
            self.db.is_empty = True

        msg = _drink_message(
            self.db.producer_name or "Unknown",
            self.db.fluid_type    or "fluid",
            self.db.fluid_flavor,
            self.db.volume_ml,
        )
        return msg

    # ------------------------------------------------------------------
    # Fridge-stock summary line
    # ------------------------------------------------------------------

    def fridge_label(self) -> str:
        """Short label for fridge listings."""
        flavor = f", {self.db.fluid_flavor}" if self.db.fluid_flavor else ""
        vol    = format_volume(self.db.volume_ml or 0.0)
        return (
            f"A bottle of {self.db.producer_name}'s "
            f"{self.db.fluid_type}{flavor} ({vol})"
        )

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def get_display_name(self, looker=None, **kwargs):
        if self.db.is_empty:
            return f"{self.key} (empty)"
        vol = format_volume(self.db.volume_ml or 0.0)
        return (
            f"{self.key} — {self.db.producer_name}'s "
            f"{self.db.fluid_type} ({vol})"
        )
