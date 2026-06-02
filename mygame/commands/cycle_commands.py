"""
commands/cycle_commands.py

endcycle — stop an active machine cycle.

This command is flagged bypass-restraint so it works even while
the cycle's restraint phase has the character locked.  It is the
only intended exit from an automated cycle.
"""

from evennia import Command


class CmdEndCycle(Command):
    """
    Stop an active machine cycle.

    Usage:
        endcycle

    Works even while restrained by the cycle machine.
    This is the only intended exit from an automated cycle session.
    """

    key     = "endcycle"
    locks   = "cmd:all()"   # bypass-restraint handled below
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        from typeclasses.cycle_script import CycleScript

        scripts = [s for s in caller.scripts.all() if isinstance(s, CycleScript)]
        if not scripts:
            caller.msg("|xNo active machine cycle to end.|n")
            return

        for scr in scripts:
            scr.stop()   # at_stop handles cleanup + messaging
