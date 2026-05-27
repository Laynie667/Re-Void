"""
typeclasses/seat_mechanic.py

SeatMechanic — an item that installs a seating mechanic into a room zone.

When a player uses `use <item> on <zone>`, this item writes seating data
into zone["mechanics"]["seat"] and is then consumed (deleted).

Zone mechanics format after install:
    zone["mechanics"]["seat"] = {
        "capacity":  int,           # max simultaneous sitters (default 2)
        "label":     str,           # display name e.g. "the bench"
        "occupied":  list,          # [(char_id, char_name), ...]
    }

Players then use:
    sit <zone>    — sit in the zone's seat
    stand         — stand up
"""

from typeclasses.mechanic_item import MechanicItem


class SeatMechanic(MechanicItem):
    """
    Installs a seating mechanic into a room zone.

    Attributes (set at creation or by staff/builders):
        db.capacity  (int)  — max sitters, default 2
        db.label     (str)  — what shows in room ("the rough-hewn bench")
    """

    mechanic_key = "seat"

    def at_object_creation(self):
        super().at_object_creation()
        self.db.capacity = 2
        # Label defaults to the item's key; builders can override with
        # @set obj/label = the bench
        self.db.label = self.key

    def install_into_zone(self, room, zone_name, installer):
        """Install seat mechanic data into the target zone."""
        zones = room.db.zones
        if not zones:
            return False, (
                "|xThis room has no zones set up yet. "
                "Use |wroomzone add <name>|n to create one first.|n"
            )

        if zone_name not in zones:
            return False, (
                f"|xZone '|w{zone_name}|x' not found here. "
                f"Type |wroomzone list|n to see available zones.|n"
            )

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        mechanics = dict(zone.get("mechanics", {}) or {})

        if "seat" in mechanics:
            return False, (
                f"|xZone '|w{zone_name}|x' already has a seating mechanic installed.|n"
            )

        capacity = self.db.capacity or 2
        label    = self.db.label or self.key

        mechanics["seat"] = {
            "capacity": capacity,
            "label":    label,
            "occupied": [],
        }
        zone["mechanics"] = mechanics
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        room.db.zones = zones_copy

        return True, (
            f"|wSeating installed in zone '|w{zone_name}|w'.|n\n"
            f"|x(Capacity: {capacity}. "
            f"Players can sit here with |wsit {zone_name}|x.)|n"
        )
