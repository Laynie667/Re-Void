"""
typeclasses/jacuzzi_script.py

JacuzziStateScript — attaches to the Jacuzzi room (the inner room).

Handles one job:

  SERVER RESTART RECOVERY (at_start hook)
  If the server went down while the toe seats were locked, this clears
  the lock immediately on restart and broadcasts a brief reset message.
  This prevents players from being permanently stuck in a locked seat
  after an unexpected shutdown.

  The at_repeat hook is a no-op reserved for future use (e.g. ambient
  tick for a running jacuzzi, activation pulse messages, etc.).

Attach once, while standing in the Jacuzzi room:
  @py self.location.scripts.add("typeclasses.jacuzzi_script.JacuzziStateScript")

The script is persistent and survives server reloads.
"""

from evennia import DefaultScript


def _get_state(room):
    from commands.jacuzzi_commands import _get_state as _gs
    return _gs(room)


def _set_seat_lock(room, locked):
    from commands.jacuzzi_commands import _set_seat_lock as _ssl
    _ssl(room, locked)


class JacuzziStateScript(DefaultScript):
    """
    Persistent watchdog for the Jacuzzi room.
    See module docstring for details.
    """

    def at_script_creation(self):
        self.key        = "jacuzzi_state_script"
        self.desc       = "Jacuzzi state watchdog"
        self.interval   = 300      # 5-minute tick (reserved for future use)
        self.persistent = True
        self.repeats    = 0        # run forever
        self.start_delay = True

    # ------------------------------------------------------------------
    # at_start — called on every server start / reload
    # ------------------------------------------------------------------

    def at_start(self):
        """
        Recovery check: if the server died with seats locked, release them.
        A player cannot stand up to fix this themselves, so the script
        clears it automatically and notifies the room.
        """
        room = self.obj
        if not room:
            return

        state = _get_state(room)

        if state.get("seats_locked"):
            _set_seat_lock(room, False)
            room.msg_contents(
                "|xThe panel's indicators flicker once as the systems restart. "
                "The toe seat locks disengage — a soft click from each. "
                "The panel indicator is green.|n"
            )

    # ------------------------------------------------------------------
    # at_repeat — reserved
    # ------------------------------------------------------------------

    def at_repeat(self):
        """
        Reserved for future use. Candidates:
          - Ambient tick for running jacuzzi (bubbles, heat, steam)
          - Activation pulse messages when dildos_active == True
          - Periodic reminder to seated/locked players
        Currently a no-op.
        """
        pass
