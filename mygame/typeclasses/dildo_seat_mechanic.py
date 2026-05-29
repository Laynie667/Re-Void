"""
typeclasses/dildo_seat_mechanic.py

DildoSeatMechanic — a SeatMechanic variant for fixed dildo seats.

Extends SeatMechanic to stamp two extra fields into the installed seat dict:

    zone["mechanics"]["seat"]["seat_type"]  = "dildo"
    zone["mechanics"]["seat"]["locked"]     = False

These fields are consumed by mechanic_commands.py to:

  1. Serve orifice-aware sit messaging from the _DILDO_SIT_MSGS pool,
     personalised with the character's groin-parented orifice zone if one exists.

  2. Block CmdStand and at_before_move when locked == True, sending a message
     from _DILDO_LOCKED_MSGS instead of allowing the character to rise.

Panel lock/release:
  The future JacuzziStateScript (or panel command) toggles the lock by writing
  directly to the zone mechanic dict:

      zones = room.db.zones
      zone  = dict(zones["seats"])
      mech  = dict(zone.get("mechanics", {}))
      seat  = dict(mech["seat"])
      seat["locked"] = True   # or False to release
      mech["seat"]   = seat
      zone["mechanics"] = mech
      zones_copy = dict(zones)
      zones_copy["seats"] = zone
      room.db.zones = zones_copy

Attach to room once, then consume:
    @create Jacuzzi Toe Seats:typeclasses.dildo_seat_mechanic.DildoSeatMechanic
    @set Jacuzzi Toe Seats/capacity = 4
    @set Jacuzzi Toe Seats/label = the toe seats
    use Jacuzzi Toe Seats on seats
"""

from typeclasses.seat_mechanic import SeatMechanic


class DildoSeatMechanic(SeatMechanic):
    """
    Installs a dildo-seat mechanic into a room zone.

    Identical to SeatMechanic at install time, then stamps
    seat_type="dildo" and locked=False into the zone dict entry,
    which unlocks special sit/stand handling in mechanic_commands.py.
    """

    mechanic_key = "seat"

    def install_into_zone(self, room, zone_name, installer):
        """Install dildo seat mechanic data into the target zone."""
        success, msg = super().install_into_zone(room, zone_name, installer)
        if not success:
            return success, msg

        # Upgrade the freshly-written seat entry with dildo-type fields
        zones = room.db.zones
        if zones and zone_name in zones:
            zone_data = zones[zone_name]
            zone      = dict(zone_data) if hasattr(zone_data, "items") else {}
            mechanics = dict(zone.get("mechanics", {}) or {})
            seat      = dict(mechanics.get("seat", {}))
            seat["seat_type"] = "dildo"
            seat["locked"]    = False
            mechanics["seat"] = seat
            zone["mechanics"] = mechanics
            zones_copy         = dict(zones)
            zones_copy[zone_name] = zone
            room.db.zones = zones_copy

        capacity = self.db.capacity or 2
        return True, (
            f"|wDildo seat installed in zone '|w{zone_name}|w'.|n\n"
            f"|x(Capacity: {capacity}. "
            f"Players sit with |wsit {zone_name}|x. "
            f"Lock/release via the panel command or JacuzziStateScript.)|n"
        )
