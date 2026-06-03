"""
typeclasses/rocking_horse_script.py

RockingHorseScript — drives a rocking horse session for an occupant.

Pace system mirrors the milking machine: slow / steady / fast / intense.
Upgrade flags are stored on room.db.horse_upgrades as a list of strings.

Available upgrades:
  motorized   — required for script-driven automatic pacing
  vibrating   — seat vibrates between rocks
  milking     — breast suction cups activate on mount
  restrained  — wrists + ankles lock to handles/stirrups on mount
  knot        — seat can engage a knot at arousal threshold
  inflation   — seat inflates incrementally during session

Attach to a room:
  @py from typeclasses.rocking_horse_script import RockingHorseScript
  @py from evennia.utils import create; create.create_script(RockingHorseScript, obj=here, persistent=True)
  @set here/horse_zone = <zone_name>
  @set here/horse_pace = steady
  @set here/horse_upgrades = []

Room commands: horsestart / horsestop / horsepace / horsemount / horsedismount
(see commands/rocking_horse_commands.py)
"""

import time
import random
from evennia import DefaultScript


class RockingHorseScript(DefaultScript):
    """Drives an active rocking horse session."""

    def at_script_creation(self):
        self.key        = "rocking_horse"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 45   # recalculated per pace on start

    def at_repeat(self):
        room = self.obj
        if not room:
            return

        zone_name = getattr(room.db, "horse_zone", None)
        if not zone_name:
            return

        upgrades = list(getattr(room.db, "horse_upgrades", None) or [])
        pace     = getattr(room.db, "horse_pace", "steady") or "steady"

        from typeclasses.characters import Character
        from typeclasses.arousal_script import add_arousal
        from world.rocking_horse_loader import (
            pick_horse_msg, get_horse_config
        )

        config   = get_horse_config(pace)
        arousal_gain = config.get("arousal_per_tick", 6.0)

        for char in room.contents:
            if not isinstance(char, Character):
                continue

            # Check if rider is seated in the horse zone
            occupied = (
                getattr(char.db, "seated_zone", None) or
                getattr(char.db, "restrained_zone", None)
            )
            if occupied != zone_name:
                continue

            rider_name = char.db.rp_name or char.name

            # Running message
            msg = pick_horse_msg(pace, "running")
            if msg:
                room.msg_contents(msg.replace("{rider}", rider_name))

            # Arousal gain
            add_arousal(char, arousal_gain)

            # Upgrade effects
            if "vibrating" in upgrades:
                import random as _r
                if _r.random() < 0.50:
                    char.msg("|xThe seat pulses between rocks.|n")

            if "milking" in upgrades:
                self._tick_milking(char, room)

            if "inflation" in upgrades:
                self._tick_inflation(char, room, zone_name, upgrades)

            if "knot" in upgrades:
                self._check_knot(char, room, upgrades)

    def at_start(self):
        room = self.obj
        if not room:
            return
        pace   = getattr(room.db, "horse_pace", "steady") or "steady"
        from world.rocking_horse_loader import get_horse_config
        config = get_horse_config(pace)
        self.interval = config.get("interval_seconds", 45)

    # ------------------------------------------------------------------
    # Upgrade tick helpers
    # ------------------------------------------------------------------

    def _tick_milking(self, char, room):
        """Run a single milking tick on the rider's breast zones."""
        try:
            from typeclasses.production_item import ProductionItem
            from typeclasses.fluid_bank import GlobalFluidBank
            zones = getattr(char.db, "zones", None) or {}
            for zd in zones.values():
                entry = (zd.get("mechanics") or {}).get("production")
                if not entry:
                    continue
                from evennia import search_object
                results = search_object(entry.get("item_dbref", ""), exact=True)
                if not results or not isinstance(results[0], ProductionItem):
                    continue
                item = results[0]
                if item.db.fluid_type != "milk":
                    continue
                available = item.db.current_volume_ml or 0.0
                if available <= 0:
                    continue
                extract = min(4.0, available)
                item.db.current_volume_ml = max(0.0, available - extract)
                item.reset_fullness_notifications()
                GlobalFluidBank.get().deposit(
                    char, extract, item.db.fluid_type, item.db.fluid_flavor
                )
        except Exception:
            pass

    def _tick_inflation(self, char, room, zone_name, upgrades):
        """Incrementally inflate the seat inside the rider."""
        try:
            from typeclasses.inflation_item import add_inflation_volume
            add_inflation_volume(char, zone_name, 25.0, "seat_fill")
        except Exception:
            pass

    def _check_knot(self, char, room, upgrades):
        """Engage a knot if arousal threshold met."""
        arousal = float(char.db.arousal or 0.0)
        if arousal < 75.0:
            return
        if getattr(char.db, "horse_knotted", False):
            return
        if random.random() > 0.20:
            return
        char.db.horse_knotted         = True
        char.db.horse_knot_expires_at = time.time() + 180.0
        rider_name = char.db.rp_name or char.name
        from world.rocking_horse_loader import pick_horse_msg
        msg = pick_horse_msg("upgrade", "knot_engage") or f"The horse catches — {rider_name} is locked onto the seat."
        room.msg_contents(msg.replace("{rider}", rider_name))

    def at_stop(self):
        """Release all knots and inflation when session stops."""
        room = self.obj
        if not room:
            return
        from typeclasses.characters import Character
        zone_name = getattr(room.db, "horse_zone", None)
        for char in room.contents:
            if not isinstance(char, Character):
                continue
            char.db.horse_knotted         = False
            char.db.horse_knot_expires_at = 0.0
            if zone_name:
                try:
                    from typeclasses.inflation_item import drain_inflation
                    drain_inflation(char, zone_name)
                except Exception:
                    pass
