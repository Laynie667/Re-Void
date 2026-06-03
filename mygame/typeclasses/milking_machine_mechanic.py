"""
typeclasses/milking_machine_mechanic.py

MilkingMachineMechanic — a room zone mechanic that harvests fluid from
characters with installed ProductionItems.

Install into a room zone via:
    @create Milking Machine:typeclasses.milking_machine_mechanic.MilkingMachineMechanic
    use Milking Machine on milking_machine

Once installed, the zone's mechanics dict contains:
    zones['milking_machine']['mechanics']['milking_machine'] = {
        'speed':   'steady',          # slow / steady / fast / intense
        'active':  False,             # currently running
        'operator': None,             # dbref of operator, or None
        'target':   None,             # dbref of current target, or None
        'session_output_ml': 0.0,     # ml produced in current session
    }

The `milk` command (commands/body_mod_commands.py CmdMilk) drives the actual
extraction loop; this typeclass just handles installation and speed constants.

Speed multipliers (applied to extract()):
    slow     → 0.75  (gentle, less output than accumulated)
    steady   → 1.0   (full accumulated volume)
    fast     → 1.35  (pulls a bit ahead of accumulation)
    intense  → 1.75  (heavy extraction, maximum output)

Output goes to FluidBottle objects created in the room, one per fluid type
found across all of the target's installed production items.
"""

from typeclasses.mechanic_item import MechanicItem


SPEED_MULTIPLIERS = {
    "slow":    0.75,
    "steady":  1.0,
    "fast":    1.35,
    "intense": 1.75,
}

SPEED_DESCRIPTIONS = {
    "slow": (
        "The machine hums low and lazy — the cups working with a slow, even "
        "pull that's in no hurry whatsoever, coaxing it up a drop at a time."
    ),
    "steady": (
        "The machine drops into a working rhythm — steady suction, even "
        "intervals, the cups grinding away like they've clocked in for a shift."
    ),
    "fast": (
        "The machine winds up — the rhythm quickening, the pull turning "
        "greedy, dragging it out faster than the body can refill between cycles."
    ),
    "intense": (
        "The machine runs flat out — deep, hammering suction that leaves the "
        "body in absolutely no doubt about exactly how much it's giving up."
    ),
}


class MilkingMachineMechanic(MechanicItem):
    """
    Installs the milking machine mechanic into a room zone.

    Once installed, the `milk` command handles all runtime operation.
    """

    mechanic_key = "milking_machine"

    def at_object_creation(self):
        super().at_object_creation()
        self.key = "Milking Machine"

    def install_into_zone(self, room, zone_name: str, installer) -> tuple:
        zones = getattr(room.db, "zones", None) or {}
        if zone_name not in zones:
            return False, f"This room has no zone called '{zone_name}'."

        zone      = dict(zones[zone_name])
        mechanics = dict(zone.get("mechanics", {}) or {})

        if "milking_machine" in mechanics:
            return False, f"A milking machine is already installed in the {zone_name} zone."

        mechanics["milking_machine"] = {
            "speed":             "steady",
            "active":            False,
            "operator":          None,
            "target":            None,
            "session_output_ml": 0.0,
        }

        zone["mechanics"] = mechanics
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        room.db.zones = zones_copy

        return (
            True,
            f"The milking machine is now installed in the {zone_name} zone.\n"
            f"Use: milk <target> [zone]    — begin milking\n"
            f"     milk/speed slow|steady|fast|intense\n"
            f"     milk/stop"
        )

    # ------------------------------------------------------------------
    # Class-level helpers used by CmdMilk
    # ------------------------------------------------------------------

    @staticmethod
    def get_state(room, zone_name: str) -> dict | None:
        """Return the milking machine state dict for a zone, or None."""
        zones = getattr(room.db, "zones", None) or {}
        zone  = zones.get(zone_name, {})
        return zone.get("mechanics", {}).get("milking_machine")

    @staticmethod
    def set_state(room, zone_name: str, **kwargs):
        """Update fields in the milking machine state dict."""
        zones = getattr(room.db, "zones", None) or {}
        if zone_name not in zones:
            return
        zone      = dict(zones[zone_name])
        mechanics = dict(zone.get("mechanics", {}) or {})
        state     = dict(mechanics.get("milking_machine", {}))
        state.update(kwargs)
        mechanics["milking_machine"] = state
        zone["mechanics"] = mechanics
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone
        room.db.zones = zones_copy

    @staticmethod
    def find_in_room(room) -> tuple:
        """
        Search room zones for an installed milking machine.

        Returns (zone_name, state_dict) or (None, None).
        """
        zones = getattr(room.db, "zones", None) or {}
        for zname, zdata in zones.items():
            mechanics = zdata.get("mechanics", {}) or {}
            state = mechanics.get("milking_machine")
            if state is not None:
                return zname, state
        return None, None
