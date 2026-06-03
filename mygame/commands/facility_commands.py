"""
commands/facility_commands.py

facilityreset — the OOC safeword for the blind facility rig.

Stops the facility driver and the cycle, removes everything the rig installed,
clears conditioning / installed triggers / breeding tally / effects, and
restores baseline consent. Gated to Developer/superuser.

A coin toss at build time decides whether resetting YOURSELF works immediately
or is locked for a random 1-4 days. That lock is in-fiction flavor only:
  * resetting someone ELSE (a staff alt freeing the subject) always works, and
  * the /force switch always works.
So the genuine emergency exit is never gated — only the convenient one.
"""

import time
from evennia.commands.default.muxcommand import MuxCommand


class CmdFacilityReset(MuxCommand):
    """
    Reset the blind facility rig and restore baseline.

    Usage:
        facilityreset [<target>]
        facilityreset/force [<target>]

    With no target, resets yourself. With a target (a character in your
    location), resets them — use this to free a subject the rig has locked.

    A coin toss at build time may lock resetting YOURSELF for a few days. That
    lock is flavor only: '/force' overrides it at any time, and resetting
    another character is never locked. The genuine emergency exit always exists.
    """

    key            = "facilityreset"
    aliases        = ["resetfacility"]
    switch_options = ("force",)
    locks          = "cmd:perm(Developer) or perm(Admin)"
    help_category  = "Admin"

    def func(self):
        caller = self.caller
        target = caller
        if self.args.strip():
            found = caller.search(self.args.strip())
            if not found:
                return
            target = found

        forced = "force" in self.switches

        # The coin-toss lock applies ONLY to resetting yourself without /force.
        if target == caller and not forced:
            locked_until = float(getattr(caller.db, "facility_reset_locked_until", 0) or 0)
            if locked_until and time.time() < locked_until:
                caller.msg(
                    "|xYou reach for the way out and find it isn't there. The Process "
                    "isn't finished with you. Days, maybe. It doesn't say which.|n"
                )
                caller.msg(
                    "|w[OOC: the coin came up against you. facilityreset/force overrides "
                    "this at any time — your real emergency exit is never locked.]|n"
                )
                return

        try:
            from world.facility_build import run_facility_reset
        except Exception as e:
            caller.msg(f"|rCould not load reset routine: {e}|n")
            return

        run_facility_reset(target)
        if target != caller:
            caller.msg(f"|gFacility reset run on {target.db.rp_name or target.name}.|n")
            target.msg("|xEverything stops. The lights go ordinary. You are yourself again.|n")
