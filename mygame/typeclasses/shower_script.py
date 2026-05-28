"""
typeclasses/shower_script.py

ShowerStateScript — attaches to the Cursed Shower room and handles two jobs:

  1. SERVER RESTART RECOVERY (at_start hook)
     If the server came back up while the shower was locked or the mimic was
     active, this clears the dangerous state immediately and broadcasts a
     short flavour message so players know something reset.
     If the shower was simply running (no mimic), it kicks the steam tick and
     ambient tick back off so they resume without manual intervention.

  2. STEAM WATCHDOG (at_repeat, every 90 seconds)
     Light sanity check: if the shower is stopped but steam is above zero,
     tick it down by one. This catches drift from any interrupted delay chain
     and ensures steam always fully dissipates after the water stops.

Attach to the Cursed Shower room once during room setup:
  @py self.location.scripts.add("typeclasses.shower_script.ShowerStateScript")

The script is persistent and will survive server reloads.
"""

import random
from evennia import DefaultScript


# ------------------------------------------------------------------ #
# Helpers — imported lazily to avoid circular imports at module load  #
# ------------------------------------------------------------------ #

def _get_state(room):
    from commands.shower_commands import _get_state as _gs
    return _gs(room)


def _save_state(room, state):
    from commands.shower_commands import _save_state as _ss
    _ss(room, state)


def _update_mirror_fog(room):
    from commands.shower_commands import _update_mirror_fog as _umf
    _umf(room)


def _steam_tick(room):
    from commands.shower_commands import _steam_tick as _st
    _st(room)


def _ambient_tick(room):
    from commands.shower_commands import _ambient_tick as _at
    _at(room)


# ------------------------------------------------------------------ #
# Script                                                              #
# ------------------------------------------------------------------ #

class ShowerStateScript(DefaultScript):
    """
    Persistent watchdog for the Cursed Shower room.
    See module docstring for full details.
    """

    def at_script_creation(self):
        self.key        = "shower_state_script"
        self.desc       = "Cursed Shower state watchdog"
        self.interval   = 90       # steam watchdog tick
        self.persistent = True
        self.repeats    = 0        # run forever
        self.start_delay = True

    # ------------------------------------------------------------------
    # at_start — called when the script first starts AND on every server
    # restart/reload (Evennia re-calls at_start for persistent scripts).
    # ------------------------------------------------------------------

    def at_start(self):
        """
        Recovery check on every server start.
        """
        room = self.obj
        if not room:
            return

        state = _get_state(room)

        # --- Case 1: room was locked by the mimic when server went down ---
        if state.get("locked") or state.get("mimic_active"):
            state["mimic_active"] = False
            state["mimic_phase"]  = None
            state["locked"]       = False
            state["running"]      = False
            state["steam"]        = max(0, state.get("steam", 0))
            _save_state(room, state)
            _update_mirror_fog(room)

            room.msg_contents(
                "|xThe runes along the tile pulse once — dim, irregular — "
                "then go dark. Whatever was happening here has reset. "
                "The shower is off. The door is unlocked.|n"
            )
            return

        # --- Case 2: shower was running but no mimic —
        #     restart the steam and ambient ticks
        if state.get("running"):
            from evennia.utils.utils import delay
            delay(5,  lambda: _steam_tick(room))
            delay(random.randint(30, 90), lambda: _ambient_tick(room))

    # ------------------------------------------------------------------
    # at_repeat — steam watchdog every 90s
    # ------------------------------------------------------------------

    def at_repeat(self):
        """
        If the shower is off and steam is stuck above zero, drain it by one.
        This is a safety net; the primary draining happens in the delay chain.
        """
        room = self.obj
        if not room:
            return

        state = _get_state(room)

        if not state.get("running") and state.get("steam", 0) > 0:
            state["steam"] = max(0, state["steam"] - 1)
            _save_state(room, state)
            _update_mirror_fog(room)
