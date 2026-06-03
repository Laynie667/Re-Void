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
from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand


_COND_STAGES = [
    (250, "imprinted livestock"), (200, "no self-modification"), (160, "name lost"),
    (130, "doll-state"), (100, "set (point of no return passed)"), (80, "designated"),
    (60, "triggers installed"), (40, "speech drifting"), (20, "floor raised"), (0, "warming"),
]


def _stage(cond):
    for v, label in _COND_STAGES:
        if cond >= v:
            return label
    return "warming"


class CmdBoard(Command):
    """
    Read the facility's status board for a resident.

    Usage:
        board [<resident>]

    Shows the live processing record: conditioning, heat, quotas, brands,
    freedom status, and brood. With no argument, reads your own.
    """

    key           = "board"
    aliases       = ["quota", "facilitystatus"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        who = caller
        if self.args.strip():
            found = caller.search(self.args.strip())
            if not found:
                return
            who = found

        d = who.db
        name = who.db.rp_name or who.name
        lines = ["|w" + "═" * 46 + "|n",
                 f"|wFACILITY BOARD — {name}|n",
                 "|w" + "═" * 46 + "|n"]

        cond = float(getattr(d, "conditioning", 0) or 0)
        perm = " |R[SET]|n" if getattr(d, "conditioning_permanent", False) else ""
        lines.append(f"  Conditioning:   {cond:6.0f}  ({_stage(cond)}){perm}")
        if getattr(d, "designation", None):
            lines.append(f"  Designation:    {d.designation}")
        lines.append(f"  Heat:           {'|rPERPETUAL|n' if getattr(d,'perpetual_heat',False) else 'off'}")
        if getattr(d, "lactation_locked", False):
            lines.append("  Lactation:      |rLOCKED ON|n")
        dep = int(getattr(d, "drug_dependence", 0) or 0)
        if dep:
            lines.append(f"  Drug dependence: {dep}")

        # Holes — gape state per orifice.
        gape = getattr(d, "gape", None) or {}
        if gape:
            try:
                from world.gang_breeding import gape_word
                parts = [f"{zn.split('/')[-1].replace('_',' ')}: {gape_word(who, zn)}"
                         for zn in gape]
                lines.append("  Holes:          " + " | ".join(parts))
            except Exception:
                pass
        bl = float(getattr(d, "bladder_ml", 0) or 0)
        if bl > 0:
            state = "|rBURSTING|n" if bl >= 500 else ("aching" if bl >= 350 else "filling")
            lines.append(f"  Bladder:        {bl:.0f}ml ({state})")

        # Freedom / compliance
        if getattr(d, "compliance_threshold", 0):
            if getattr(d, "freedom_forfeited", False):
                from world.compliance import EARN_BACK_STREAK
                streak = int(getattr(d, "compliance_streak", 0) or 0)
                lines.append(f"  Freedom:        |RFORFEITED|n  (earn-back streak {streak}/{EARN_BACK_STREAK})")
            else:
                lines.append(f"  Compliance:     defiance {int(getattr(d,'defiance',0) or 0)}/{int(d.compliance_threshold)}")

        # Quotas
        try:
            from world.gang_breeding import summarize_quota
            qb = summarize_quota(who)
            if qb:
                lines.append("")
                lines.append(qb)
        except Exception:
            pass
        mq = getattr(d, "milk_quota", None)
        if mq:
            cur = int(mq.get("current", 0)); req = int(mq.get("required", 0))
            done = "|gMET|n" if cur >= req else "|rNOT MET|n"
            lines.append(f"|wMILK QUOTA:|n  {cur}/{req} bottles   {done}")

        # Brood
        counts = getattr(d, "offspring_counts", None) or {}
        if counts:
            brood = ", ".join(f"{v} {k}" for k, v in counts.items())
            lines.append(f"|wBROOD:|n  {brood}")

        # Brands
        brands = getattr(d, "facility_brands", None) or []
        if getattr(d, "facility_brand", None):
            brands = [d.facility_brand] + list(brands)
        if brands:
            lines.append(f"|wBRANDS:|n  {len(brands)}")
            for b in brands:
                lines.append(f"    • {b}")

        trig = len(getattr(d, "installed_triggers", None) or [])
        if trig:
            lines.append(f"  Installed responses: {trig}")

        lines.append("|w" + "═" * 46 + "|n")
        caller.msg("\n".join(lines))


class CmdFacilityReset(MuxCommand):
    """
    Reset the blind facility rig and restore baseline.

    Usage:
        facilityreset [<target>]
        facilityreset/force [<target>]
        facilityreset/purge [<target>]

    With no target, resets yourself. With a target (a character in your
    location), resets them — use this to free a subject the rig has locked.

    A normal reset frees the subject but leaves behind a few persistent marks.
    Switches:
        /force   ignore the coin-toss time lock (emergency exit; keeps marks)
        /purge   scorched earth — clears EVERYTHING, marks included, and
                 ignores the lock. The true factory reset.

    The lock is flavor only: /force, /purge, and resetting another character
    are never locked. The genuine emergency exit always exists.
    """

    key            = "facilityreset"
    aliases        = ["resetfacility"]
    switch_options = ("force", "purge")
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

        purge  = "purge" in self.switches
        forced = "force" in self.switches or purge

        # Freedom-forfeit clause gates the PLAIN command on yourself. /force and
        # /purge always bypass — the genuine OOC exit is never gated.
        if target == caller and not forced and getattr(caller.db, "freedom_forfeited", False):
            caller.msg(
                "|RThe way out doesn't answer to you anymore. You forfeited it — there's "
                "a clause, and you signed over the page it was hiding on.|n"
            )
            caller.msg(
                "|w[OOC: in-fiction your freedom is forfeited. facilityreset/force and "
                "facilityreset/purge still work — your real exit is never gated.]|n"
            )
            return

        # The coin-toss lock applies ONLY to resetting yourself without override.
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

        run_facility_reset(target, purge=purge)
        if target != caller:
            caller.msg(f"|gFacility reset run on {target.db.rp_name or target.name}.|n")
            target.msg("|xEverything stops. The lights go ordinary. You are yourself again.|n")
