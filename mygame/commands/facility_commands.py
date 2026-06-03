"""
commands/facility_commands.py

facilityreset — the OOC safeword for the blind facility rig.

Stops the facility driver and the cycle, removes everything the rig installed,
clears conditioning / installed triggers / breeding tally / effects, and
restores baseline consent. Gated to Developer/superuser so only the operator
can wipe the rig — including freeing a subject the rig has locked in.
"""

from evennia import Command


class CmdFacilityReset(Command):
    """
    Reset the blind facility rig and restore baseline.

    Usage:
        facilityreset [<target>]

    With no target, resets yourself. With a target (a character in your
    location), resets them — use this to free a subject the rig has locked.

    This is the real OOC safeword: it stops everything the facility is doing
    and restores the character to baseline regardless of how deep it has gone.
    """

    key           = "facilityreset"
    aliases       = ["resetfacility", "facility reset"]
    locks         = "cmd:perm(Developer) or perm(Admin)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        target = caller
        if self.args.strip():
            found = caller.search(self.args.strip())
            if not found:
                return
            target = found

        try:
            from world.facility_build import run_facility_reset
        except Exception as e:
            caller.msg(f"|rCould not load reset routine: {e}|n")
            return

        run_facility_reset(target)
        if target != caller:
            caller.msg(f"|gFacility reset run on {target.db.rp_name or target.name}.|n")
            target.msg("|xEverything stops. The lights go ordinary. You are yourself again.|n")
