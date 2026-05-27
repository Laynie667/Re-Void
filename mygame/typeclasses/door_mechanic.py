"""
typeclasses/door_mechanic.py

LockableDoor — a mechanic item that installs a lockable door on a room zone.

Usage:
    use lockable door on <zone>        — installs; item consumed
    door set <zone> = <exit name>      — link the zone to an exit (one-time setup)
    lock <zone>                        — lock the door
    unlock <zone>                      — unlock the door
    knock <zone>                       — knock; people on the other side hear it

Zone mechanics format after install:
    zone["mechanics"]["door"] = {
        "destination_id":  None,    # dbid of the room on the other side (set via 'door set')
        "locked":          False,
        "owner_ids":       [int],   # character IDs who can lock/unlock
        "lock_msg":        str,     # shown to someone who tries to pass while locked
        "knock_room_msg":  str,     # shown to people in the destination room
        "knock_caller_msg": str,    # shown to the person knocking
    }
"""

from typeclasses.mechanic_item import MechanicItem


class LockableDoor(MechanicItem):
    """
    Installs a lockable door mechanic on a room zone.

    After installing, use 'door set <zone> = <exit name>' to link the zone
    to the exit it should block. The mechanic then intercepts at_before_move
    on characters trying to use that exit while the door is locked.
    """

    mechanic_key = "door"

    def at_object_creation(self):
        super().at_object_creation()

    def install_into_zone(self, room, zone_name, installer):
        zones = room.db.zones
        if not zones:
            return False, (
                "|xThis room has no zones. Use |wroomzone add <name>|n first.|n"
            )

        if zone_name not in zones:
            return False, (
                f"|xZone '|w{zone_name}|x' not found. "
                f"Type |wroomzone list|n to see available zones.|n"
            )

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        mechanics = dict(zone.get("mechanics", {}) or {})

        if "door" in mechanics:
            return False, (
                f"|xZone '|w{zone_name}|x' already has a door mechanic installed.|n"
            )

        mechanics["door"] = {
            "destination_id":   None,
            "locked":           False,
            "owner_ids":        [installer.id],
            "lock_msg":         "The door is locked.",
            "knock_room_msg":   "There is a knock at the door.",
            "knock_caller_msg": "You knock at the door.",
        }
        zone["mechanics"] = mechanics
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        room.db.zones = zones_copy

        return True, (
            f"|wLockable door installed on zone '|w{zone_name}|w'.|n\n"
            f"|xNext: link it to an exit with "
            f"|wdoor set {zone_name} = <exit name>|n\n"
            f"Then use |wlock {zone_name}|n / |wunlock {zone_name}|n to control it.|n"
        )
