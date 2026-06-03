"""
commands/cycle_commands.py

The cycle machine — a fully automatic, endlessly looping device.

  cycle start <target> [zone]  — trap a target in the machine's cycle
  cycle stop                   — stop your own cycle (self-exit)
  cycle status [target]        — show current phase and cycle count
  cycle release <target>       — release someone else from the cycle
  endcycle                     — alias for 'cycle stop'

The cycle loops forever with no relief built in. The only ways out are:
  * the wearer using 'cycle stop' / 'endcycle' — UNLESS an item effect
    (block_endcycle) has locked that out, in which case
  * someone else (staff, an NPC, or another player) using 'cycle release'.

The cycle is persistent and survives relogs.
"""

import time
from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand


_BLOCKED_MSG = (
    "|xYou reach for the release — and the binding locks it out. The machine "
    "doesn't even slow. Someone else will have to free you.|n"
)


class CmdCycle(MuxCommand):
    """
    Operate the automatic cycle machine.

    Usage:
      cycle start <target> [zone]   start a cycle on a target
      cycle stop                    stop your own cycle (self-exit)
      cycle status [target]         show current phase and cycle count
      cycle release <target>        release someone else from the cycle

    The cycle loops endlessly with no relief. 'cycle stop' / 'endcycle' is the
    wearer's only self-exit — and an item effect can lock even that out, leaving
    'cycle release' (used by someone else) as the only way out. The cycle
    persists across relogs.
    """
    key     = "cycle"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        parts  = self.args.strip().split(None, 1)
        sub    = parts[0].lower() if parts else ""
        rest   = parts[1].strip() if len(parts) > 1 else ""

        if sub == "start":
            self._start(caller, rest)
        elif sub in ("stop", "end"):
            self._self_stop(caller)
        elif sub == "status":
            self._status(caller, rest)
        elif sub == "release":
            self._release(caller, rest)
        else:
            caller.msg(
                "|xUsage: cycle start <target> [zone] | cycle stop | "
                "cycle status [target] | cycle release <target>|n"
            )

    # ------------------------------------------------------------------

    def _start(self, caller, rest):
        room = caller.location
        if not room:
            return
        if not rest:
            caller.msg("|xUsage: cycle start <target> [zone]|n")
            return

        tparts      = rest.split(None, 1)
        target_name = tparts[0]
        zone_arg    = tparts[1].strip().lower().replace(" ", "_") if len(tparts) > 1 else None

        target = caller.search(target_name, location=room)
        if not target:
            return
        from typeclasses.characters import Character
        if not isinstance(target, Character):
            caller.msg("|xYou can only cycle a character.|n")
            return

        from typeclasses.cycle_script import CycleScript
        if CycleScript.find(target):
            caller.msg(f"|x{target.db.rp_name or target.name} is already in a cycle.|n")
            return

        zone = zone_arg
        if not zone:
            from typeclasses.milking_machine_mechanic import MilkingMachineMechanic
            zone, _ = MilkingMachineMechanic.find_in_room(room)
        if not zone:
            caller.msg("|xNo machine installed here. Specify a zone or install one first.|n")
            return

        from evennia.utils import create
        script = create.create_script(CycleScript, obj=target, persistent=True, autostart=True)
        script.db.machine_zone  = zone
        script.db.phase         = "rest"
        script.db.phase_started = time.time()

        tname = target.db.rp_name or target.name
        caller.msg(f"|wCycle started on {tname} (zone '{zone}'). It loops until ended or released.|n")
        room.msg_contents(
            f"|xThe machine closes around {tname} and begins its cycle. There is no set end to it.|n",
            exclude=[caller],
        )
        if target != caller:
            target.msg("|xThe machine takes you. It begins to cycle, and it does not intend to stop.|n")

    def _self_stop(self, caller):
        from typeclasses.cycle_script import CycleScript
        if not CycleScript.find(caller):
            caller.msg("|xYou aren't in a machine cycle.|n")
            return
        if getattr(caller.db, "endcycle_blocked", False):
            caller.msg(_BLOCKED_MSG)
            return
        CycleScript.stop_all(caller)   # at_stop handles end messaging

    def _status(self, caller, rest):
        from typeclasses.cycle_script import CycleScript
        who = caller
        if rest:
            found = caller.search(rest.strip(), location=caller.location)
            if found:
                who = found
        scripts = CycleScript.find(who)
        wname   = who.db.rp_name or who.name
        if not scripts:
            caller.msg(f"|x{wname} is not in a machine cycle.|n")
            return
        s       = scripts[0]
        phase   = getattr(s.db, "phase", "?")
        count   = getattr(s.db, "cycle_count", 0)
        blocked = " |R(self-release locked)|n" if getattr(who.db, "endcycle_blocked", False) else ""
        caller.msg(f"|w{wname}: cycle phase '{phase}', {count} cycle(s) completed.{blocked}|n")

    def _release(self, caller, rest):
        room = caller.location
        if not rest:
            caller.msg("|xUsage: cycle release <target>|n")
            return
        target = caller.search(rest.strip(), location=room)
        if not target:
            return
        from typeclasses.cycle_script import CycleScript
        if not CycleScript.find(target):
            caller.msg(f"|x{target.db.rp_name or target.name} isn't in a machine cycle.|n")
            return

        # The escape valve — deliberately bypasses block_endcycle.
        CycleScript.stop_all(target)
        tname = target.db.rp_name or target.name
        cname = caller.db.rp_name or caller.name
        caller.msg(f"|wYou release {tname} from the cycle.|n")
        if target != caller:
            target.msg(f"|x{cname} releases you from the machine. It finally lets you go.|n")
        if room:
            room.msg_contents(
                f"|x{cname} releases {tname} from the machine's cycle.|n",
                exclude=[caller, target],
            )


class CmdEndCycle(Command):
    """
    Stop your own machine cycle (self-exit).

    Usage:
        endcycle

    Works even while restrained by the cycle machine. An item effect can lock
    this out — if so, only 'cycle release' (used by someone else) will free you.
    """
    key     = "endcycle"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        from typeclasses.cycle_script import CycleScript
        if not CycleScript.find(caller):
            caller.msg("|xNo active machine cycle to end.|n")
            return
        if getattr(caller.db, "endcycle_blocked", False):
            caller.msg(_BLOCKED_MSG)
            return
        CycleScript.stop_all(caller)


ALL_CYCLE_CMDS = [CmdCycle, CmdEndCycle]
