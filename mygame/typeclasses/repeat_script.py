"""
typeclasses/repeat_script.py

SimpleRepeatScript — drives /repeat variants of suck, handmilk, and thrust.

Attached to the caller character.  Fires the stored action at the configured
interval until stopped.  Auto-stops when target leaves room or action fails.

Usage (via command switches):
    suck/repeat <target> [zone]          handmilk/repeat <target> [zone]
    thrust/repeat                         (uses active penetration engagement)

    suck/stop                             handmilk/stop
    thrust/stop

Intervals:
    suck      — 60s (nursing pace)
    handmilk  — 30s (steady-rate)
    thrust    — 15s (per-use)
"""

from evennia import DefaultScript


_INTERVALS = {
    "suck":      60,
    "handmilk":  30,
    "thrust":    15,
}


class SimpleRepeatScript(DefaultScript):
    """Repeating action script for suck / handmilk / thrust."""

    def at_script_creation(self):
        self.key        = "simple_repeat"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 30

        self.db.action       = None   # "suck" | "handmilk" | "thrust"
        self.db.target_dbref = None   # dbref string of target (None = self)
        self.db.zone_name    = None   # specific zone, or None for auto-detect

    # ------------------------------------------------------------------

    def at_repeat(self):
        char = self.obj
        if not char or not hasattr(char, "db"):
            self.stop()
            return

        room = char.location
        if not room:
            self.stop()
            return

        action = self.db.action

        # Resolve target
        if self.db.target_dbref:
            from evennia import search_object
            results = search_object(self.db.target_dbref, exact=True)
            if not results:
                char.msg("|xTarget no longer available — repeat stopped.|n")
                self.stop()
                return
            target = results[0]
            if target.location != room:
                char.msg("|xTarget left the room — repeat stopped.|n")
                self.stop()
                return
        else:
            target = char

        zone = self.db.zone_name

        try:
            if action == "suck":
                from commands.penetration_commands import _repeat_suck
                if not _repeat_suck(char, target, zone, room):
                    char.msg("|xSuck repeat ended — nothing to draw.|n")
                    self.stop()

            elif action == "handmilk":
                from commands.penetration_commands import _repeat_handmilk
                if not _repeat_handmilk(char, target, zone, room):
                    char.msg("|xHandmilk repeat ended — nothing to extract.|n")
                    self.stop()

            elif action == "thrust":
                engaged = char.db.penetrating or {}
                if not engaged.get("target_dbref"):
                    char.msg("|xNot engaged — thrust repeat stopped.|n")
                    self.stop()
                    return
                from commands.penetration_commands import _repeat_thrust
                _repeat_thrust(char, engaged, room)

        except Exception:
            self.stop()

    def at_stop(self):
        char = self.obj
        if char:
            action = self.db.action or "action"
            char.msg(f"|x{action.capitalize()} repeat stopped.|n")
