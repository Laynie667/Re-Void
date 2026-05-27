"""
typeclasses/stair_mechanic.py

CreakingStair — a mechanic item that installs a stair notification system
on a room zone. When a character moves through the associated exit, configurable
rooms receive a creak notification.

Usage:
    use creaking stair on staircase      — installs; item consumed
    stair set <zone> = <exit name>       — link to the exit (ascending direction)
    stair add <zone> = #<room_dbref>     — add a room to the listener list
    stair remove <zone> = #<room_dbref>  — remove a room from listeners
    stair list <zone>                    — show current config
    stair msg <zone> up = <text>         — set ascending creak message
    stair msg <zone> down = <text>       — set descending creak message

Zone mechanics format after install:
    zone["mechanics"]["stair"] = {
        "destination_id":       int,   # room at the top (set via 'stair set')
        "listener_room_ids":    list,  # room dbids that hear the creak
        "ascending_msg":        str,   # heard in listener rooms going up
        "descending_msg":       str,   # heard in listener rooms going down
        "mover_ascending_msg":  str,   # seen by the mover going up
        "mover_descending_msg": str,   # seen by the mover going down
    }
"""

from typeclasses.mechanic_item import MechanicItem


class CreakingStair(MechanicItem):
    """
    Installs a stair notification mechanic on a room zone.
    """

    mechanic_key = "stair"

    def at_object_creation(self):
        super().at_object_creation()

    def install_into_zone(self, room, zone_name, installer):
        zones = room.db.zones
        if not zones:
            return False, "|xThis room has no zones. Use |wroomzone add <name>|n first.|n"

        if zone_name not in zones:
            return False, (
                f"|xZone '|w{zone_name}|x' not found. "
                f"Type |wroomzone list|n to see available zones.|n"
            )

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        mechanics = dict(zone.get("mechanics", {}) or {})

        if "stair" in mechanics:
            return False, f"|xZone '|w{zone_name}|x' already has a stair mechanic.|n"

        mechanics["stair"] = {
            "destination_id":       None,
            "listener_room_ids":    [],
            "ascending_msg":        "The stairs creak — someone is on their way up.",
            "descending_msg":       "The stairs creak — someone is coming down.",
            "mover_ascending_msg":  "The third step announces your arrival.",
            "mover_descending_msg": "The stairs creak beneath your feet.",
        }
        zone["mechanics"] = mechanics
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        room.db.zones = zones_copy

        return True, (
            f"|wStair mechanic installed on zone '|w{zone_name}|w'.|n\n"
            f"|xNext steps:\n"
            f"  |wstair set {zone_name} = <exit name>|n   — link to an exit\n"
            f"  |wstair add {zone_name} = #<dbref>|n      — add listener rooms\n"
            f"  |wstair msg {zone_name} up = <text>|n     — customise creak message|n"
        )
