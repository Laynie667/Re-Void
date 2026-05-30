"""
typeclasses/fluid_fridge.py

FluidFridge — an in-room container for FluidBottle objects.

Players interact with it using standard Evennia object commands:
    put <bottle> in <fridge>    — stock the fridge
    get <bottle> from <fridge>  — retrieve a bottle
    look <fridge>               — view contents with labeled lines

The fridge renders contents using FluidBottle.fridge_label() for clean display.
No access gate — any character in the room can retrieve from it.
"""

from evennia import DefaultObject


class FluidFridge(DefaultObject):
    """
    A container for FluidBottle objects with formatted content display.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.desc = (
            "A small glass-door refrigerator, its interior cleanly lit and cold. "
            "Stock it with FluidBottle objects from the milking machine. "
            "Retrieve bottles with: |wget <bottle> from <fridge>|n"
        )

    def return_appearance(self, looker, **kwargs):
        """Show fridge contents using FluidBottle.fridge_label()."""
        from typeclasses.fluid_bottle import FluidBottle

        string = f"|w{self.get_display_name(looker)}|n\n"
        string += (self.db.desc or "") + "\n"

        bottles = []
        empties = []
        other   = []

        for obj in self.contents:
            if isinstance(obj, FluidBottle):
                if obj.db.is_empty or (obj.db.volume_ml or 0) <= 0:
                    empties.append(obj)
                else:
                    bottles.append(obj)
            else:
                other.append(obj)

        if bottles:
            string += "\n|wContents:|n\n"
            for b in bottles:
                string += f"  {b.fridge_label()}\n"
        if empties:
            count = len(empties)
            string += f"  |x{count} empty bottle{'s' if count != 1 else ''}|n\n"
        for obj in other:
            string += f"  {obj.get_display_name(looker)}\n"

        if not bottles and not empties and not other:
            string += "\n|xThe fridge is empty.|n"

        return string.strip()
