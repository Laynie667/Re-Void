"""
typeclasses/restrain_mechanic.py

RestrainMechanic — a mechanic item that installs a restraint point on a zone.

When installed, adds:
    zone["mechanics"]["restrain"] = {
        "capacity":       int,   # max characters that can be restrained
        "label":          str,   # display label ("the cables", "the cuffs", etc.)
        "restrained":     [],    # list of (char_id, char_name, restrainer_id)
        "blocker_msg":    str,   # message shown when restrained char tries to move
        "restrainer_ids": [],    # ids of characters authorised to use this point
    }

Usage (in-game):
    @create Table Cables:typeclasses.restrain_mechanic.RestrainMechanic
    @set Table Cables/label    = the cables
    @set Table Cables/capacity = 4
    @set Table Cables/blocker_msg = The cables hold you exactly where you are.
    use Table Cables on center
"""

from typeclasses.mechanic_item import MechanicItem


class RestrainMechanic(MechanicItem):
    """
    A mechanic item that installs a restraint anchor point on a zone.

    Attributes (set with @set before use):
        label       (str)  — display name for the restraint ("the cables")
        capacity    (int)  — how many characters can be restrained at once
        blocker_msg (str)  — message shown when the restrained character tries to leave
    """

    mechanic_key = "restrain"

    def at_object_creation(self):
        super().at_object_creation()
        self.db.capacity    = 1
        self.db.label       = "the restraints"
        self.db.blocker_msg = "Something holds you fast."

    def install_into_zone(self, room, zone_name, installer):
        """
        Install this mechanic into the named zone.

        Returns (success: bool, message: str).
        On success, the item is consumed by CmdUse.
        """
        zones = room.db.zones or {}
        zone_name = zone_name.strip().lower()

        if zone_name not in zones:
            return False, f"|xZone '{zone_name}' not found.|n"

        zone = zones[zone_name]
        if not hasattr(zone, "get"):
            return False, f"|xZone '{zone_name}' is malformed.|n"

        mechanics = dict(zone.get("mechanics", {}) or {})
        if "restrain" in mechanics:
            return False, (
                f"|xZone '{zone_name}' already has a restraint mechanic installed. "
                f"Remove it first if you need to reconfigure.|n"
            )

        capacity    = int(self.db.capacity or 1)
        label       = str(self.db.label or "the restraints")
        blocker_msg = str(self.db.blocker_msg or "Something holds you fast.")

        mechanics["restrain"] = {
            "capacity":       capacity,
            "label":          label,
            "restrained":     [],
            "blocker_msg":    blocker_msg,
            "restrainer_ids": [installer.id],
        }

        # Write back via full dict copy for _SaverDict persistence
        zc = dict(zone)
        zc["mechanics"] = mechanics
        zs = dict(zones)
        zs[zone_name] = zc
        room.db.zones = zs

        return True, (
            f"|wRestraint mechanic installed on zone '{zone_name}'.|n\n"
            f"|xLabel: {label} | Capacity: {capacity}|n"
        )
