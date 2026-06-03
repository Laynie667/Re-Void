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

        try:
            from world.processing import processing_tier
            lvl, tname, tstate = processing_tier(who)
            lines.append(f"  Processing tier: |Y{tname}|n  ({tstate})")
        except Exception:
            pass

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

        # Holes — gape state + trained capabilities per orifice.
        holes = getattr(d, "holes", None) or {}
        if holes:
            try:
                from world.gang_breeding import gape_word, hole_capabilities
                for zn, h in holes.items():
                    disp = zn.split("/")[-1].replace("_", " ")
                    caps = hole_capabilities(who, zn)
                    captxt = (" — trained: " + ", ".join(sorted(caps))) if caps else ""
                    lines.append(f"  {disp:<14} {gape_word(who, zn)} "
                                 f"(used {int(h.get('use',0))}x){captxt}")
            except Exception:
                pass
        pierc = getattr(d, "piercings", None) or []
        if pierc:
            lines.append(f"|wPIERCINGS:|n  {len(pierc)}")
            for p in pierc:
                lines.append(f"    • {p.get('desc', p.get('loc',''))}")
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


# ───────────────────────────────────────────────────────────────────────────
# Agency verbs — what SHE can choose to do in the facility. Submitting earns
# back freedom but breaks her deeper; struggling is defiance, punished. Both
# feed the machine. There is no move that doesn't.
# ───────────────────────────────────────────────────────────────────────────

def _fac_script(room):
    if not room:
        return None
    for s in room.scripts.all():
        if getattr(s, "key", "") == "facility":
            return s
    return None


class _FacilityVerb(Command):
    locks = "cmd:all()"
    help_category = "Interaction"

    def _ok(self):
        if not getattr(self.caller.db, "facility_active", False):
            self.caller.msg("|xThere's nothing here to do that for.|n")
            return False
        return True

    def _arouse(self, amt):
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(self.caller); add_arousal(self.caller, amt)
        except Exception:
            pass

    def _comply(self, reward=False):
        try:
            from world.compliance import register_compliance
            register_compliance(self.caller, reward=reward)
        except Exception:
            pass


class CmdPresent(_FacilityVerb):
    """
    Present yourself for use, unprompted.

    Usage: present
    """
    key = "present"

    def func(self):
        if not self._ok():
            return
        c = self.caller; room = c.location; t = c.db.rp_name or c.name
        c.db.body_language = "presented for use — hips up, holes offered"
        room.msg_contents(
            f"|y{t} presents herself without being told — hips tipped up, holes offered, "
            f"eyes down — and waits to be used.|n")
        self._comply(reward=False)
        self._arouse(5)
        c.msg("|xPresenting before you're made to is logged as good behaviour. The wanting "
              "that made you do it is logged too, in a different column.|n")


class CmdBeg(_FacilityVerb):
    """
    Beg the facility to use you.

    Usage: beg
    """
    key = "beg"

    def func(self):
        if not self._ok():
            return
        c = self.caller; room = c.location; t = c.db.rp_name or c.name
        room.msg_contents(
            f"|y{t} begs — voice climbing, hips working against nothing — to be filled, to "
            f"be bred, to be used, please, anything.|n")
        self._comply(reward=False)
        self._arouse(10)
        # The facility answers begging — it likes to reward the asking.
        fs = _fac_script(room)
        if fs:
            try:
                fs._gang(room, c, t, float(getattr(c.db, "conditioning", 0) or 0))
            except Exception:
                pass
        c.msg("|xYou asked for it out loud. That's the part they wanted. That's the part "
              "that stays with you after.|n")


class CmdThank(_FacilityVerb):
    """
    Thank the facility for what it does to you.

    Usage: thank
    """
    key = "thank"

    def func(self):
        if not self._ok():
            return
        c = self.caller; room = c.location; t = c.db.rp_name or c.name
        room.msg_contents(
            f"|y{t} thanks the facility — quiet, automatic, meaning it — for being made "
            f"useful.|n")
        self._comply(reward=True)
        try:
            from world.conditioning import add_conditioning
            add_conditioning(c, 4.0, source="gratitude")
        except Exception:
            pass
        c.msg("|xGratitude is the deepest part of the training. Every time you mean it, a "
              "little more of you agrees that this is where you belong.|n")


class CmdSubmit(_FacilityVerb):
    """
    Stop resisting. Give in to the facility completely, for now.

    Usage: submit
    """
    key = "submit"

    def func(self):
        if not self._ok():
            return
        c = self.caller; room = c.location; t = c.db.rp_name or c.name
        room.msg_contents(
            f"|y{t} goes soft and open and pliant — the fight draining out of her, her body "
            f"settling into being used as if it's all she's for.|n")
        self._comply(reward=True)
        try:
            from world.conditioning import add_conditioning
            add_conditioning(c, 8.0, source="submission")
        except Exception:
            pass
        c.msg("|xSubmitting is the fastest way through, and the fastest way down. Both at "
              "once. The way back to your freedom runs straight through giving it up.|n")


class CmdStruggle(_FacilityVerb):
    """
    Fight it. Pull against the restraints, refuse, resist.

    Usage: struggle
    """
    key = "struggle"
    aliases = ["resist"]

    def func(self):
        if not self._ok():
            return
        c = self.caller; room = c.location; t = c.db.rp_name or c.name
        room.msg_contents(
            f"|R{t} struggles — pulling against the restraints, twisting, refusing — and the "
            f"facility does not so much as pause to notice.|n")
        try:
            from world.compliance import register_defiance
            register_defiance(c, 1, reason="struggled against the line")
        except Exception:
            pass
        c.msg("|xIt's logged as non-compliance, punished, and counted toward forfeiting your "
              "freedom. The restraints don't give. Struggling only ever trained you faster.|n")


_FURNITURE_SCENE = {
    "bench": "single", "breeding": "single",
    "rack": None, "milking": None,
    "machine": "single", "fucking": "single",
    "block": "verbal", "display": "verbal",
}


class CmdMount(_FacilityVerb):
    """
    Get onto a piece of the facility's furniture and present on it.

    Usage: mount <furniture>   (e.g. mount bench, mount machine, mount block)
    """
    key = "mount"

    def func(self):
        if not self._ok():
            return
        c = self.caller; room = c.location; t = c.db.rp_name or c.name
        arg = self.args.strip().lower()
        if not arg:
            c.msg("|xMount what? (the breeding bench, the milking rack, the fucking "
                  "machine, the display block...)|n")
            return
        scene = None
        for kw, sc in _FURNITURE_SCENE.items():
            if kw in arg:
                scene = sc; matched = kw; break
        else:
            c.msg("|xThere's no such fixture here to climb onto.|n")
            return
        room.msg_contents(
            f"|y{t} climbs onto the {arg} herself and arranges into position, offering up "
            f"whatever it's built to use.|n")
        self._comply(reward=False)
        fs = _fac_script(room)
        if not fs:
            self._arouse(8)
            return
        cond = float(getattr(c.db, "conditioning", 0) or 0)
        try:
            if "rack" in arg or "milk" in arg:
                fs._start_milking(c)
                c.msg("|cThe rack's cups find you and start to pull. You climbed on for this.|n")
            else:
                getattr(fs, f"_scene_{scene or 'single'}")(room, c, t, cond, fs._orifices(c))
        except Exception:
            self._arouse(8)


ALL_FACILITY_VERBS = [CmdPresent, CmdBeg, CmdThank, CmdSubmit, CmdStruggle, CmdMount]
