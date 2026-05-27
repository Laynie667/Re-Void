"""
commands/mechanic_commands.py

Commands for using mechanic items and interacting with zone-based
mechanics (sitting, standing, etc.).

    use <item> on <zone>   — install a mechanic item into a room zone (consumed)
    use <item> in <zone>   — alias for the above
    sit <zone>             — sit in a zone that has a seat mechanic
    stand                  — stand up from wherever you're sitting
"""

from evennia import Command


# ---------------------------------------------------------------------------
# CmdUse
# ---------------------------------------------------------------------------

class CmdUse(Command):
    """
    Use an item on a zone to install its mechanic.

    Usage:
      use <item> on <zone>
      use <item> in <zone>

    The item is consumed (destroyed) on successful installation.

    Example:
      use worn cushion on center
    """

    key = "use"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            caller.msg("|xUsage: |wuse <item> on <zone>|n")
            return

        # Split on " on " or " in "
        zone_name = None
        item_name = args
        for sep in (" on ", " in "):
            if sep in args.lower():
                idx = args.lower().index(sep)
                item_name = args[:idx].strip()
                zone_name = args[idx + len(sep):].strip().lower()
                break

        # Find item in inventory
        matches = caller.search(item_name, location=caller, quiet=True)
        if not matches:
            caller.msg(f"|xYou don't have '{item_name}'.|n")
            return
        item = matches[0] if isinstance(matches, list) else matches

        # Import here to avoid circular imports
        from typeclasses.mechanic_item import MechanicItem
        if not isinstance(item, MechanicItem):
            caller.msg(
                f"|xYou're not sure how to use {item.key} that way.|n"
            )
            return

        if not zone_name:
            caller.msg(
                f"|xWhat zone do you want to use {item.key} on?\n"
                f"|xUsage: |wuse {item.key} on <zone>|n"
            )
            return

        room = caller.location
        if not room:
            caller.msg("|xYou aren't in a room.|n")
            return

        success, msg = item.install_into_zone(room, zone_name, caller)
        caller.msg(msg)

        if success:
            item.delete()


# ---------------------------------------------------------------------------
# CmdSit
# ---------------------------------------------------------------------------

class CmdSit(Command):
    """
    Sit in a zone's seat.

    Usage:
      sit <zone>

    The zone must have a seat mechanic installed. Use 'roomzone list'
    to see what zones are available in the current room.

    Example:
      sit center
    """

    key = "sit"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        zone_name = self.args.strip().lower()

        if not zone_name:
            caller.msg("|xUsage: |wsit <zone>|n")
            return

        room = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        zones = room.db.zones or {}
        if zone_name not in zones:
            caller.msg(
                f"|xThere's no zone called '{zone_name}' here.|n"
            )
            return

        zone = zones[zone_name]
        mechanics = zone.get("mechanics", {}) or {} if hasattr(zone, "get") else {}
        seat = mechanics.get("seat")

        if not seat:
            caller.msg(f"|xThere's nowhere to sit in '{zone_name}'.|n")
            return

        # Already seated here?
        if caller.db.zone_seated_at == (room.id, zone_name):
            caller.msg("|xYou're already sitting there.|n")
            return

        # Auto-stand from any other seat first
        if caller.db.zone_seated_at:
            _do_stand(caller, silent=True)

        occupied = list(seat.get("occupied", []))
        capacity = seat.get("capacity", 2)

        if len(occupied) >= capacity:
            label = seat.get("label", zone_name)
            caller.msg(
                f"|x{label.capitalize()} is full "
                f"({len(occupied)}/{capacity}).|n"
            )
            return

        # Sit down — write back through full copy to ensure DB persistence
        occupied.append((caller.id, caller.db.rp_name or caller.name))
        seat_copy = dict(seat)
        seat_copy["occupied"] = occupied
        mech_copy = dict(mechanics)
        mech_copy["seat"] = seat_copy
        zone_copy = dict(zone) if hasattr(zone, "items") else {}
        zone_copy["mechanics"] = mech_copy
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone_copy
        room.db.zones = zones_copy

        caller.db.zone_seated_at = (room.id, zone_name)

        label = seat_copy.get("label", zone_name)
        char_name = caller.db.rp_name or caller.name
        caller.msg(f"|wYou settle into {label}.|n")
        room.msg_contents(
            f"|x{char_name} settles into {label}.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# CmdStand
# ---------------------------------------------------------------------------

class CmdStand(Command):
    """
    Stand up from wherever you're sitting.

    Usage:
      stand
    """

    key = "stand"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not caller.db.zone_seated_at:
            caller.msg("|xYou aren't sitting anywhere.|n")
            return
        _do_stand(caller)


# ---------------------------------------------------------------------------
# Shared helper — also imported by characters.py for auto-stand on move
# ---------------------------------------------------------------------------

def _do_stand(char, silent=False):
    """
    Remove char from their current zone seat.

    Args:
        char   : the character object
        silent : if True, suppress stand messages (auto-stand on room change)
    """
    seated = char.db.zone_seated_at
    if not seated:
        return

    room_id, zone_name = seated
    char.db.zone_seated_at = None

    # Retrieve the label before we clear, for the message
    label = zone_name
    room = None

    try:
        from evennia import search_object
        results = search_object(f"#{room_id}")
        room = results[0] if results else None
        if room:
            zones = room.db.zones or {}
            if zone_name in zones:
                zone = zones[zone_name]
                mechanics = zone.get("mechanics", {}) or {} if hasattr(zone, "get") else {}
                seat = mechanics.get("seat")
                if seat:
                    label = seat.get("label", zone_name)
                    occupied = [
                        entry for entry in seat.get("occupied", [])
                        if entry[0] != char.id
                    ]
                    seat_copy = dict(seat)
                    seat_copy["occupied"] = occupied
                    mech_copy = dict(mechanics)
                    mech_copy["seat"] = seat_copy
                    zone_copy = dict(zone) if hasattr(zone, "items") else {}
                    zone_copy["mechanics"] = mech_copy
                    zones_copy = dict(zones)
                    zones_copy[zone_name] = zone_copy
                    room.db.zones = zones_copy
    except Exception:
        pass

    if not silent:
        char_name = char.db.rp_name or char.name
        char.msg(f"|wYou rise from {label}.|n")
        if char.location:
            char.location.msg_contents(
                f"|x{char_name} rises from {label}.|n",
                exclude=char,
            )


ALL_MECHANIC_CMDS = [CmdUse, CmdSit, CmdStand]
