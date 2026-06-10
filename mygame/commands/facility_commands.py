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
import random
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
        caller.msg(build_board_text(who))


def build_board_text(who):
    """Render the live facility board for `who` as a string."""
    if not who:
        return "|xNo subject on the board.|n"
    d = who.db
    name = who.db.rp_name or who.name
    lines = ["|w" + "═" * 46 + "|n",
             f"|wFACILITY BOARD — {name}|n",
             "|w" + "═" * 46 + "|n"]

    if True:
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
        # Ownership / devotion (canonical here — board is the full dossier).
        owner = getattr(d, "facility_owner", None)
        dev = float(getattr(d, "bethany_devotion", 0) or 0)
        if owner or getattr(d, "bethany_owned", False) or dev > 0:
            lines.append(f"  Owner:          |M{owner or 'Bethany'}|n   (devotion {dev:.0f})")
        clauses = list(getattr(d, "bethany_clauses", None) or [])
        if clauses:
            lines.append(f"  Personal clauses: {', '.join(clauses)}")
        sug = float(getattr(d, "suggestibility", 0) or 0)
        doc = float(getattr(d, "docility", 0) or 0)
        if sug or doc:
            lines.append(f"  Suggestibility: {sug:.0f}    Docility: {doc:.0f}")
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

        # FORGET log — what's been redacted out of her (the dossier remembers).
        forgotten = list(getattr(d, "facility_forgotten", None) or [])
        if forgotten:
            lines.append(f"|wREDACTED (FORGET):|n  {len(forgotten)}")
            for item in forgotten[-6:]:
                lines.append(f"    • {item}")

        lines.append("|w" + "═" * 46 + "|n")
    return "\n".join(lines)


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
        # Beg-Small clause: nothing is hers by default; she begs small for relief, and the
        # begging itself is the permission. (Star-Chart relief is bought with stars instead —
        # see the `stars` command — so begging there only earns the using, not the release.)
        if getattr(c.db, "beg_small", False):
            room.msg_contents(
                f"|y{t} begs small and filthy for it — voice gone little and wet, |i'pwease, "
                f"pwease let me come, m'been so good, pwease'|n — hips bucking at nothing, "
                f"past dignity, past anything but the asking.|n")
            self._comply(reward=False)
            try:
                from world.compliance import _grant_climax
                _grant_climax(c)
            except Exception:
                self._arouse(10)
            try:
                from world.regression import regress
                regress(c, 3.0, source="beg_small")
            except Exception:
                pass
            c.msg("|xYou had to ask for it in your littlest voice, out loud, in front of "
                  "everyone. They only let you come once you've begged small enough to mean it.|n")
            return
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
        import random as _r
        room.msg_contents(
            f"|R{t} struggles — pulling against the restraints, twisting, refusing — and the "
            f"facility does not so much as pause to notice.|n")
        # Owned stock gets a different futility: she WANTS you to fight.
        if getattr(c.db, "bethany_owned", False) or float(getattr(c.db, "bethany_devotion", 0) or 0) > 0:
            c.msg("|MShe looks up from her file, delighted. \"Oh, go on — wear yourself out. "
                  "Every pull you waste on the straps is one less you've got left for me to take. "
                  "I'm in no hurry at all.\"|n")
        # register_defiance may swallow the struggle entirely if you're docile enough
        # (it prints its own beat). Otherwise it's logged + punished.
        try:
            from world.compliance import register_defiance
            register_defiance(c, 1, reason="struggled against the line")
        except Exception:
            pass
        c.msg("|x" + _r.choice([
            "The restraints don't give. Struggling only ever trained you faster.",
            "No is a sound you make in here, not a door. The room has heard it before.",
            "You fight the steel and the steel wins, the way it was built to, the way it always "
            "will. The fight was never the part that mattered — outlasting it is.",
            "The only thing your thrashing earns is a note in your file and a little more of the "
            "fight spent. There's a finite amount of it in you. They have nothing but time.",
        ]) + " |x(The one true way out is never the restraints — it's the OOC floor: escape / "
              "force_clear / purge. That door is never locked.)|n")


# keyword -> (scene_method_or_None, climb-on flavor)
_FURNITURE_SCENE = {
    "bench":    ("double",  "She folds herself over the breeding bench and reaches back to "
                            "buckle her own ankles into the stirrups — presented, locked, ready."),
    "breeding": ("double",  "She folds herself over the breeding bench and locks her own "
                            "ankles into the stirrups, hips up, holes offered."),
    "rack":     (None,      "She steps into the milking rack and fits her own tits to the "
                            "waiting cups, arms up into the cuffs, and waits for the draw."),
    "milking":  (None,      "She fits herself to the milking rack, tits to the cups, and "
                            "lets it cinch on."),
    "machine":  ("single",  "She lowers herself onto the fucking machine's primed attachment, "
                            "takes it to the base with a shudder, and reaches for the dial she "
                            "isn't allowed to turn down."),
    "fucking":  ("single",  "She seats herself on the fucking machine and braces — it only "
                            "goes one way, and she set it running herself."),
    "block":    ("verbal",  "She climbs up onto the display block under the lights, turns to "
                            "present herself to the room, and holds the pose to be looked at."),
    "display":  ("verbal",  "She mounts the display block and offers herself up to be graded, "
                            "shown, and bid on."),
    "kennel":   ("knottrain","She crawls to the kennel gate on her knees and presents through "
                            "the bars, asking for what's behind them."),
    "cart":     ("__dose",  "She bares an arm to the supply cart, offering herself for "
                            "whatever's loaded next."),
    "supply":   ("__dose",  "She presents to the supply cart for dosing."),
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
        scene = flavor = None
        for kw, (sc, fl) in _FURNITURE_SCENE.items():
            if kw in arg:
                scene, flavor = sc, fl; break
        else:
            c.msg("|xThere's no such fixture here to climb onto. (bench / rack / machine / "
                  "block / kennel / cart)|n")
            return
        room.msg_contents(f"|y{t} doesn't wait to be put there. {flavor}|n")
        self._comply(reward=False)
        fs = _fac_script(room)
        if not fs:
            self._arouse(8)
            return
        cond = float(getattr(c.db, "conditioning", 0) or 0)
        try:
            if scene is None:                       # the milking rack
                fs._start_milking(c)
                c.msg("|cThe cups find you and start to pull. You climbed on for this.|n")
            elif scene == "__dose":                 # the supply cart
                fs._dose(room, c, t)
            else:
                getattr(fs, f"_scene_{scene}")(room, c, t, cond, fs._orifices(c))
        except Exception:
            self._arouse(8)


ALL_FACILITY_VERBS = [CmdPresent, CmdBeg, CmdThank, CmdSubmit, CmdStruggle, CmdMount]


# ───────────────────────────────────────────────────────────────────────────
# Multiplayer handler — another player (or staff) can step in and actually run
# a facility subject through the real systems. The subject being facility_active
# is the opt-in; the facility has already opened her for use.
# ───────────────────────────────────────────────────────────────────────────

class CmdProcess(Command):
    """
    Handle a facility subject — run them through the line yourself.

    Usage:
      process <subject> [action]

    Actions: breed (use a hole), milk, dose (experimental drug), pierce, ring,
             neuter (geld + cage male stock — retires it from siring), sissify
             (feminize male stock into a kept sissy),
             milkport, oneway (one-way ring), cowset (heavy cow piercings),
             feed (force-feed her ports), latex (seal as a drone), grow (force
             udder growth), brand, tattoo, portfolio (mark/catalogue her in the
             parlour), condition, punish, reward, beg (make her beg), appraise,
             buy (claim her), demote (a staffer), inspect.  Default is 'breed'.

    The subject must be in the facility (it's their opt-in). Everything you do
    drives the real systems — real deposits, real milking, real conditioning.
    """
    key           = "process"
    aliases       = ["tend"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        parts = self.args.strip().split(None, 1)
        if not parts:
            caller.msg("|xUsage: process <subject> [breed|milk|dose|pierce|punish|"
                       "condition|reward|inspect]|n")
            return
        target = caller.search(parts[0])
        if not target:
            return
        action = (parts[1].strip().lower() if len(parts) > 1 else "breed")
        room = caller.location
        fs   = _fac_script(room)

        # Demote: pull a staff NPC off their post and put THEM on the line. Targets a
        # facility attendant (not the subject), so it skips the facility_active gate.
        if action in ("demote", "bust"):
            if getattr(target.db, "facility_role", None) != "attendant":
                caller.msg(f"|x{target.db.rp_name or target.name} isn't staff to demote.|n")
                return
            if fs:
                try: fs._demote_staff(room, npc=target)
                except Exception: pass
            caller.msg(f"|RYou put {target.db.rp_name or target.name} on the line. Staff one "
                       f"shift, stock the next.|n")
            return

        if not getattr(target.db, "facility_active", False):
            caller.msg(f"|x{target.db.rp_name or target.name} isn't in the facility — there's "
                       f"nothing to handle.|n")
            return
        t    = target.db.rp_name or target.name
        cn   = caller.db.rp_name or caller.name
        cond = float(getattr(target.db, "conditioning", 0) or 0)

        if action in ("breed", "fuck", "use"):
            if fs:
                try: fs._gang(room, target, t, cond)
                except Exception: pass
            # A named deposit — this load is actually the handler's, in her, on file.
            try:
                import random as _r
                from typeclasses.insemination_item import do_inseminate
                zone = None
                if fs:
                    holes = fs._holes_only(target)
                    zone = _r.choice(holes) if holes else (fs._orifices(target) or [None])[0]
                if zone:
                    do_inseminate(caller, target, zone, {
                        "source": "machine", "fluid_type": "semen",
                        "volume_per_tick": _r.uniform(80, 200), "ttl_hours": 24.0})
            except Exception:
                pass
            tally = list(getattr(target.db, "bred_by", None) or [])
            tally.append((caller.id, cn)); target.db.bred_by = tally
            room.msg_contents(f"|r{cn} takes a turn with {t}, using her the way the facility "
                              f"intends its stock to be used.|n", exclude=[target, caller])
            caller.msg(f"|rYou use {t}. The line logs your contribution.|n")
            target.msg(f"|r{cn} steps up and uses you. You're logged as bred, again.|n")

        elif action == "milk":
            if fs:
                try: fs._start_milking(target)
                except Exception: pass
            room.msg_contents(f"|c{cn} clamps the cups onto {t} and sets her milking.|n",
                              exclude=[caller])
            caller.msg(f"|cYou put {t} on the milker.|n")

        elif action in ("dose", "drug"):
            if fs:
                try: fs._dose(room, target, t)
                except Exception: pass
            caller.msg(f"|GYou dose {t}.|n")

        elif action == "pierce":
            try:
                from world.gang_breeding import add_piercing
                d = add_piercing(target)
                if d:
                    room.msg_contents(f"|G{cn} pierces {t}: {d}.|n")
                else:
                    caller.msg("|xNothing left to pierce.|n")
            except Exception:
                pass

        elif action in ("punish",):
            try:
                from world.compliance import punish
                punish(target, reason=f"handled by {cn}", severity=1)
            except Exception:
                pass
            caller.msg(f"|RYou punish {t}.|n")

        elif action in ("condition", "break"):
            try:
                from world.conditioning import add_conditioning
                add_conditioning(target, 8.0, source="handler")
            except Exception:
                pass
            room.msg_contents(f"|M{cn} works {t}'s head a while — murmuring, repeating, "
                              f"pressing it deeper — and a little more of her gives.|n",
                              exclude=[caller])
            caller.msg(f"|MYou condition {t} deeper.|n")

        elif action in ("reward", "praise"):
            try:
                from world.compliance import register_compliance
                register_compliance(target, reward=True)
            except Exception:
                pass
            room.msg_contents(f"|M{cn} praises {t} — 'good girl' — and lets her have a little "
                              f"relief for it. She'll chase it.|n", exclude=[caller])
            caller.msg(f"|MYou reward {t}.|n")

        elif action in ("inspect", "board", "check"):
            caller.execute_cmd(f"board {parts[0]}")

        elif action in ("appraise", "price", "value"):
            price = 0
            if fs:
                try: price = fs._appraise(target)
                except Exception: pass
            grade = getattr(target.db, "facility_grade", None) or "Unprocessed"
            counts = sum(int(v) for v in (getattr(target.db, "offspring_counts", None) or {}).values())
            caller.msg(f"|W{t} — lot appraisal|n\n  |xGrade:|n {grade}   |xGet dropped:|n {counts}"
                       f"   |xConditioning:|n {float(getattr(target.db,'conditioning',0) or 0):.0f}"
                       f"\n  |xAsking price:|n |w{price:,}|n")
            target.msg(f"|m{cn} walks around you, reads your card, and prices you at |w{price:,}|m "
                       f"— out loud, like you can't hear it. You hope it's enough.|n")

        elif action in ("sell", "buy", "claim", "own"):
            price = 0
            if fs:
                try: price = fs._appraise(target)
                except Exception: pass
            if not getattr(target.db, "facility_title_backup", None):
                target.db.facility_title_backup = {
                    "faction": getattr(target.db, "title_faction", "") or "",
                    "suffix":  getattr(target.db, "title_suffix", "") or ""}
            target.db.facility_owner = cn
            target.db.title_suffix = f"— {cn}'s"
            try:
                from world.gang_breeding import record_mark
                record_mark(target, f"a sale tag wired to her — SOLD to {cn} for {price:,}", mode="on")
            except Exception: pass
            room.msg_contents(f"|R{cn} buys {t} outright — {price:,}, paid, done. She's tagged "
                              f"SOLD and belongs to {cn} now.|n", exclude=[caller, target])
            caller.msg(f"|RYou buy {t}. She's yours — tagged, logged, owned.|n")
            target.msg(f"|R{cn} buys you. Over your head, while you're posed and turning, a line "
                       f"in a ledger changes and you belong to {cn} now.|n")

        elif action in ("latex", "seal", "drone"):
            if fs:
                try: fs._proc_latex(room, target, t)
                except Exception: pass
            caller.msg(f"|GYou have {t} sealed into facility latex.|n")

        elif action in ("grow", "udder", "swell"):
            if fs:
                try: fs._proc_udder(room, target, t)
                except Exception: pass
            caller.msg(f"|GYou pump {t}'s glands into a growth cycle.|n")

        elif action in ("ring", "rings"):
            if fs:
                try: fs._proc_rings(room, target, t)
                except Exception: pass
            caller.msg(f"|GYou have {t} ringed.|n")

        elif action in ("neuter", "geld", "cage"):
            if fs:
                try: fs._proc_neuter(room, target, t)
                except Exception: pass
            caller.msg(f"|GYou have {t} gelded and caged — retired from siring, kept in chastity.|n")

        elif action in ("sissify", "sissy", "feminize", "feminise"):
            if fs:
                try: fs._proc_sissify(room, target, t)
                except Exception: pass
            caller.msg(f"|GYou have {t} made over into a kept sissy.|n")

        elif action in ("brand", "mark"):
            # The marker (or a visiting owner) sets a permanent brand — the handler's
            # initial unless they're claimed, in which case the owner's.
            owner = getattr(target.db, "facility_owner", None) or cn
            initial = (owner.strip()[:1] or "?").upper()
            spot = random.choice(["one hip", "the swell of her ass",
                                                "her lower belly over the womb", "her flank"])
            try:
                from world.gang_breeding import record_mark
                record_mark(target, f"a brand seared into {spot} — a {initial}, set by {cn}, "
                            f"permanent", mode="on")
            except Exception:
                pass
            room.msg_contents(f"|R{cn} draws an iron glowing from the parlour bar and presses it "
                              f"to {t}'s {spot} — a hiss, the smell of it, a bitten-off scream — "
                              f"and leaves a {initial} burned into her for good.|n", exclude=[target])
            target.msg(f"|R{cn} brands you — a {initial}, seared into {spot}, permanent. You'll "
                       f"read it off your own skin for the rest of the term.|n")

        elif action in ("tattoo", "ink"):
            try:
                from world.gang_breeding import record_mark
                ink = random.choice([
                    "BRED · PROPERTY OF THE FACILITY across the lower belly, with a tally box",
                    "a stock number inked at the nape, under the hair",
                    f"{cn}'s name inked along the hip in a neat possessive hand",
                    "a row of breeding tallies down the inside of one thigh"])
                record_mark(target, f"a permanent tattoo — {ink}", mode="on")
            except Exception:
                pass
            room.msg_contents(f"|G{cn} sets a tattoo gun to {t} and inks her — {ink} — "
                              f"under everything she'll ever wear, for good.|n", exclude=[caller])
            caller.msg(f"|GYou ink {t}: {ink}.|n")

        elif action in ("portfolio", "photograph", "polaroid"):
            owner = getattr(target.db, "facility_owner", None) or cn
            grade = getattr(target.db, "facility_grade", None) or "stock"
            marks = len(getattr(target.db, "facility_brands", None) or [])
            summary = f"{grade}, {marks} mark(s) on record"
            try:
                from world.gang_breeding import record_mark
                record_mark(target, f"catalogued in the parlour portfolio under {owner} — "
                            f"photographed marked and owned", mode="on", prefer="back")
            except Exception:
                pass
            # Write a real entry into the readable portfolio album, if one's here.
            try:
                from typeclasses.facility_furniture import FacilityPortfolio
                album = next((o for o in room.contents if isinstance(o, FacilityPortfolio)), None)
                if album:
                    album.add_entry(owner, t, summary)
            except Exception:
                pass
            room.msg_contents(f"|x{cn} stands {t} against the portfolio wall, marked and owned, "
                              f"and photographs her — a before, an after, a page under {owner}'s "
                              f"initial that only ever gains entries.|n", exclude=[target])
            target.msg(f"|xYou're posed, marked, and photographed for {owner}'s portfolio. You "
                       f"hold the pose. The thing in the picture is you, catalogued by who owns it.|n")

        elif action in ("beg", "make beg"):
            if fs:
                try: fs._made_to_beg(room, target, t)
                except Exception: pass
            caller.msg(f"|mYou make {t} beg for it.|n")

        elif action in ("milkport", "milkports", "ports"):
            if fs:
                try: fs._proc_milk_port(room, target, t)
                except Exception: pass
            caller.msg(f"|GYou fit {t} with milk-ports.|n")

        elif action in ("oneway", "gaugering", "gaugerings", "ringopen"):
            if fs:
                try: fs._proc_oneway(room, target, t)
                except Exception: pass
            caller.msg(f"|GYou fit {t} with a one-way ring.|n")

        elif action in ("cowset", "cow", "tag"):
            if fs:
                try: fs._proc_cowset(room, target, t)
                except Exception: pass
            caller.msg(f"|GYou ring {t} out as a cow.|n")

        elif action in ("feed", "forcefeed", "pump"):
            import random as _r2
            try:
                from typeclasses.facility_implants import MilkPortItem
                port = next((o for o in target.contents if isinstance(o, MilkPortItem)
                             and o.db.installed_on_char == target), None)
                if not port:
                    fs and fs._proc_milk_port(room, target, t)
                    port = next((o for o in target.contents if isinstance(o, MilkPortItem)), None)
                if port:
                    msg = port.feed(_r2.uniform(300, 700), fluid="semen")
                    room.msg_contents(f"|r{msg}|n")
                else:
                    caller.msg(f"|x{t} has no milk-ports to feed.|n")
            except Exception:
                caller.msg(f"|x{t} has no milk-ports to feed.|n")

        else:
            caller.msg("|xUnknown action. Try: breed / milk / dose / pierce / ring / latex / "
                       "grow / condition / punish / reward / beg / appraise / buy / inspect|n")


ALL_FACILITY_VERBS.append(CmdProcess)


class CmdStanding(Command):
    """
    View your standing in The Facility (and any other faction).

    Usage:
        standing
    """
    key           = "standing"
    aliases       = ["faction", "rep"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        factions = getattr(caller.db, "factions", None) or {}
        if not factions:
            caller.msg("|xYou hold no standing with any faction.|n")
            return
        lines = ["|w" + "═" * 40 + "|n", "|wSTANDING|n", "|w" + "═" * 40 + "|n"]
        try:
            from world.factions import FACILITY, get_facility_tier, next_threshold, get_standing
        except Exception:
            FACILITY = None
        for name, val in factions.items():
            if FACILITY and name == FACILITY:
                grade, title = get_facility_tier(caller)
                nxt, nxt_name = next_threshold(caller)
                line = f"  |Y{name}|n: {int(val)}  — graded |Y{grade}|n"
                if nxt:
                    line += f"  (next: {nxt_name} at {nxt})"
                else:
                    line += "  (max grade)"
                lines.append(line)
            else:
                lines.append(f"  {name}: {int(val)}")
        lines.append("|w" + "═" * 40 + "|n")
        caller.msg("\n".join(lines))

ALL_FACILITY_VERBS.append(CmdStanding)


class CmdScrip(Command):
    """
    Read your Facility account — scrip balance and statement.

    Usage:
        scrip            — your balance and recent statement
        scrip full       — the full statement on file

    Scrip is the only money that means anything in here. Stock earn it off their
    own bodies — every draw, every covering, every turn on the block credited to
    an account in their name — and members earn it in the booths and spend it on
    the block and the floor. It buys nothing outside, and never the door: the OOC
    exit (escape / force_clear / facilityreset) is always free and costs nothing.
    """
    key           = "scrip"
    aliases       = ["wallet", "account", "ledger", "balance"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        try:
            from world.economy import statement
        except Exception:
            caller.msg("|xNo account on file.|n")
            return
        n = 25 if self.args.strip().lower() in ("full", "all", "-a") else 12
        caller.msg(statement(caller, n=n))

ALL_FACILITY_VERBS.append(CmdScrip)


class CmdBuy(Command):
    """
    The commissary — spend scrip on the only things it buys in here.

    Usage:
        buy             — the menu and your balance
        buy <thing>     — pay for it now

    Menu:
        relief   a granted climax — permission, just this once
        rest     a beat off the line, unworked
        ease     the edge and the empty-ache taken down for now
        mercy    buy off the next few trips to the sty

    Every credit you spend here your own body earned — milked, bred, shown, sold.
    It buys comfort inside the Process and nothing outside it. It does NOT buy the
    door: the OOC exit (escape / force_clear / facilityreset) is always free and
    costs nothing, at any balance — even in debt.
    """
    key           = "buy"
    aliases       = ["commissary", "comfort"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    _MENU = {
        "relief": (350, "a granted climax — permission, just this once"),
        "rest":   (250, "a beat off the line, unworked"),
        "ease":   (180, "the edge and the empty-ache taken down for now"),
        "mercy":  (300, "buy off the next few trips to the sty"),
    }

    def func(self):
        caller = self.caller
        from world.economy import get_balance, spend_credits
        if not (getattr(caller.db, "facility_active", False)
                or getattr(caller.db, "facility_signed", False)):
            caller.msg("|xThe commissary is for stock. You hold no account on the line.|n")
            return
        what = self.args.strip().lower()
        if not what:
            lines = [f"|W── COMMISSARY ──|n  |xyour scrip:|n |w{get_balance(caller):,}|n"]
            for k, (c, desc) in self._MENU.items():
                lines.append(f"  |w{k}|n |x({c:,})|n — {desc}")
            lines.append("  |x(Bought with what your body earned. None of it is the door — the "
                         "door is always free.)|n")
            caller.msg("\n".join(lines))
            return
        alias = {"cum": "relief", "climax": "relief", "orgasm": "relief", "come": "relief",
                 "pause": "rest", "sleep": "rest", "calm": "ease", "down": "ease",
                 "spare": "mercy", "skip": "mercy"}
        what = alias.get(what, what)
        if what not in self._MENU:
            caller.msg(f"|xThe commissary doesn't stock '{what}'. Try: {', '.join(self._MENU)}|n")
            return
        cost, _desc = self._MENU[what]
        ok, bal = spend_credits(caller, cost, f"Commissary — {what}.")
        if not ok:
            caller.msg(f"|x'{what}' costs |w{cost:,}|x scrip and you have |w{bal:,}|x. Earn more "
                       f"on the line.|n")
            return

        if what == "relief":
            try:
                from world.compliance import _grant_climax
                _grant_climax(caller)
            except Exception:
                caller.msg("|MPermission — just this once.|n")
            try:
                from world.economy import skim
                skim(caller, cost, "House cut — commissary relief.")
            except Exception:
                pass
            caller.msg(f"|x(— {cost:,} scrip. The orgasm your body paid for deepens the very thing "
                       f"that owns it; Bethany keeps her cut, and it goes back into the house. "
                       f"Balance |w{bal:,}|x.)|n")
        elif what == "rest":
            caller.db.line_pass = int(getattr(caller.db, "line_pass", 0) or 0) + 1
            caller.msg(f"|GYou buy a beat off the line — the handlers will pass your station once. "
                       f"(— {cost:,} scrip, balance |w{bal:,}|G.)|n")
        elif what == "ease":
            try:
                cur = float(getattr(caller.db, "arousal", 0) or 0)
                caller.db.arousal = max(0.0, cur - 45.0)
            except Exception:
                pass
            caller.msg(f"|GThe edge comes down and the empty-ache eases — bought, not granted, and "
                       f"only for now. (— {cost:,} scrip, balance |w{bal:,}|G.)|n")
        elif what == "mercy":
            caller.db.defiance = 0
            caller.db.punish_shield = max(int(getattr(caller.db, "punish_shield", 0) or 0), 3)
            caller.msg(f"|GYou buy off the sty — the next few slips won't send you down. "
                       f"(— {cost:,} scrip, balance |w{bal:,}|G.)|n")

ALL_FACILITY_VERBS.append(CmdBuy)


class CmdManumission(Command):
    """
    Manumission — the way out of the Process, on her terms.

    Usage:
        freedom         — where you stand with the door: her price and what's left
        freedom ask     — ask her to name a price (she likes being asked)
        freedom pay     — pay the named price once you can meet it

    This is the IN-FICTION door, and it is Bethany's to price, dangle, honor, or
    slam shut again on a whim. Paying it does not open it — only she does, when she
    feels like it, if she feels like it. That wait is the whole point.

    It is NOT your real way out. The real exit — escape / force_clear /
    facilityreset — is always free, instant, and costs nothing, at any balance,
    in any state, no matter what she's signed or shredded. Manumission is a story.
    The floor is not.
    """
    key           = "freedom"
    aliases       = ["manumission", "buyout"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        try:
            from world import release as rel
        except Exception:
            caller.msg("|xNo release process is available here.|n")
            return
        arg = self.args.strip().lower()
        if arg in ("ask", "petition", "beg", "request"):
            rel.petition(caller)
        elif arg in ("pay", "buy", "sign", "settle"):
            rel.pay(caller)
        else:
            caller.msg(rel.status(caller))

ALL_FACILITY_VERBS.append(CmdManumission)


class CmdManumit(MuxCommand):
    """
    Bethany's side of manumission — name, honor, gouge, or revoke a release.

    ADMIN ONLY. This is the lock that keeps the in-fiction door un-loopholable:
    a unit can ask and pay, but only this command opens it, and it never touches
    the OOC floor (escape / force_clear / facilityreset stay free regardless).

    Usage:
        manumit <target>                  — read their current release terms
        manumit/offer <target> = <scrip> [dev <N>] [stand <N>] [<note...>]
        manumit/gouge <target> = <scrip> [dev <N>] [stand <N>] [<note...>]
        manumit/grant <target>            — honor it (opens the way home)
        manumit/revoke <target> [= <add>] — slam it shut again (optionally re-price)
        manumit/withdraw <target>         — clear the offer entirely

    Examples:
        manumit/offer Laynie = 8000 dev 20 stand 40 You'll want to stay, pet.
        manumit/grant Laynie
        manumit/revoke Laynie = 5000
    """
    key            = "manumit"
    switch_options = ("offer", "gouge", "grant", "revoke", "withdraw")
    locks          = "cmd:perm(Developer) or perm(Admin)"
    help_category  = "Admin"

    @staticmethod
    def _parse_terms(rhs):
        """'8000 dev 20 stand 40 note words' -> (scrip, devotion_max, standing_min, note)."""
        toks = (rhs or "").split()
        scrip = devmax = standmin = None
        note_parts = []
        i = 0
        while i < len(toks):
            t = toks[i].lower()
            if t in ("dev", "devotion") and i + 1 < len(toks) and toks[i + 1].lstrip("<=").isdigit():
                devmax = int(toks[i + 1].lstrip("<=")); i += 2; continue
            if t in ("stand", "standing") and i + 1 < len(toks) and toks[i + 1].lstrip(">=").isdigit():
                standmin = int(toks[i + 1].lstrip(">=")); i += 2; continue
            if scrip is None and toks[i].replace(",", "").isdigit():
                scrip = int(toks[i].replace(",", "")); i += 1; continue
            note_parts.append(toks[i]); i += 1
        return scrip, devmax, standmin, " ".join(note_parts).strip()

    def func(self):
        caller = self.caller
        from world import release as rel
        name = (self.lhs or self.args or "").strip()
        if not name:
            caller.msg("|xManumit whom? See |whelp manumit|x.|n")
            return
        target = caller.search(name, global_search=True)
        if not target:
            return

        sw = self.switches
        if "offer" in sw or "gouge" in sw:
            scrip, devmax, standmin, note = self._parse_terms(self.rhs)
            if "gouge" in sw:
                rel.gouge(target, add_scrip=scrip or 0, devotion_max=devmax,
                          standing_min=standmin, note=note)
            else:
                rel.offer(target, scrip=scrip or 0, devotion_max=devmax,
                          standing_min=standmin, note=note, by=caller)
            caller.msg(f"|g[manumit] terms set on {target.key}.|n")
        elif "grant" in sw:
            ok = rel.grant(target, by=caller)
            caller.msg(f"|g[manumit] release {'GRANTED — door open' if ok else 'NOT granted (unpaid/no offer)'} "
                       f"for {target.key}.|n")
        elif "revoke" in sw:
            regouge = 0
            if self.rhs and self.rhs.strip().replace(",", "").isdigit():
                regouge = int(self.rhs.strip().replace(",", ""))
            rel.revoke(target, by=caller, regouge=regouge)
            caller.msg(f"|g[manumit] release revoked — door shut for {target.key}"
                       + (f"; re-priced +{regouge:,}." if regouge else ".") + "|n")
        elif "withdraw" in sw:
            rel.withdraw(target, by=caller)
            caller.msg(f"|g[manumit] offer withdrawn for {target.key}.|n")
        else:
            # no switch — admin read of their terms
            caller.msg(rel.status(target))

ALL_FACILITY_VERBS.append(CmdManumit)


class CmdVault(Command):
    """
    Bethany's books — the account she keeps on you, and what she's spent of it.

    Usage:
        vault        — the full statement plus Bethany's accounting

    She keeps her ledgers in her office. As stock, you only get to see them when
    she has you in there; the rest of the time the number is hers, not yours.
    """
    key           = "vault"
    aliases       = ["books"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        from world.economy import statement, totals, get_balance
        loc   = caller.location
        stock = (getattr(caller.db, "facility_active", False)
                 or getattr(caller.db, "facility_signed", False))
        in_office = bool(loc and "office" in (loc.key or "").lower())
        if stock and not in_office:
            caller.msg("|xBethany keeps her books in her office. The account is hers out here — you "
                       "only see what she's made of you when she has you at her desk.|n")
            return
        earned, spent, net = totals(caller)
        caller.msg(statement(caller, n=25))
        # The house treasury + what it has reinvested in her.
        try:
            from world.economy import house_totals, house_balance, _UP_BLURB
            h_in, h_out, h_bal = house_totals(caller)
            ups = dict(getattr(caller.db, "facility_upgrades", None) or {})
            up_lines = "\n".join(f"    |Y{k} L{lvl}|n — {_UP_BLURB.get(k, '')}"
                                 for k, lvl in ups.items()) or "    |x(none yet)|n"
            house = (f"\n|M── the house treasury ──|n\n"
                     f"  |xTaken in (skim + sales):|n |g{h_in:,}|n   |xReinvested:|n |r{h_out:,}|n"
                     f"   |xon hand:|n |w{h_bal:,}|n\n  |xupgrades bought with it:|n\n{up_lines}")
        except Exception:
            house = ""
        caller.msg(f"\n|M── Bethany's accounting ──|n\n"
                   f"  |xPaid in by your body:|n |g{earned:,}|n   |xSpent:|n |r{spent:,}|n   "
                   f"|xon the books:|n |w{get_balance(caller):,}|n{house}\n"
                   f"  |M\"Every figure in the black you made on your back, sweetheart — milked, "
                   f"bred, shown, your own get sold off the block. Every figure in the red I spent, "
                   f"on you, on more of you. The treasury you filled bought the cups that drain you "
                   f"faster and the studs that fill you fuller. I keep the books so you never wonder "
                   f"what you're worth: exactly this — and not one credit of it opens the door. The "
                   f"door was always free. This was never about the door.\"|n")

ALL_FACILITY_VERBS.append(CmdVault)


class CmdRecords(Command):
    """
    The records hall — your lineage and the polaroids the house keeps of you.

    Usage:
        records          — your get (living, grown, and sold off) and the sale wall

    Every litter you've dropped, every one grown and bred back, every one sold off
    the block — and a polaroid of each sale, filed and dated. The wall the facility
    keeps so the line is never forgotten, only added to.
    """
    key           = "records"
    aliases       = ["wall", "lineage", "portfolio"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        from evennia import search_object
        t = caller.db.rp_name or caller.key
        counts = dict(getattr(caller.db, "offspring_counts", None) or {})
        total  = sum(int(v) for v in counts.values())
        roster = list(getattr(caller.db, "offspring_roster", None) or [])
        living = grown = 0
        for ref in roster:
            o = (search_object(ref) or [None])[0]
            if not o:
                continue
            living += 1
            if getattr(o.db, "matured", False):
                grown += 1
        pol = list(getattr(caller.db, "facility_polaroids", None) or [])
        sold_get = sum(1 for p in pol if p.get("kind") == "get")

        lines = [f"|W╔═══ RECORDS — the line of {t} ═══╗|n"]
        if counts:
            by_sp = "   ".join(f"|g{sp}:|n {n}" for sp, n in counts.items())
            lines.append(f"  |xGet dropped:|n |w{total}|n   ({by_sp})")
        else:
            lines.append("  |xGet dropped:|n |w0|n — the line hasn't started. Yet.")
        lines.append(f"  |xStill on the roster:|n {living}  "
                     f"(|w{grown}|n grown and bred back to you)   |xsold off:|n {sold_get}")
        if pol:
            lines.append("  |x── the polaroid wall ──|n")
            for p in pol[-12:]:
                tag = "SOLD" if p.get("kind") == "sale" else "GET"
                lines.append(f"  |W[{tag}]|n |x{p.get('date','')}|n  {p.get('subject','')} — "
                             f"|w{int(p.get('price',0)):,}|n to {p.get('buyer','')}\n"
                             f"        |x({p.get('cap','')})|n")
        else:
            lines.append("  |xNo polaroids on file. Nothing's been sold off the block — so far.|n")
        lines.append("|W" + "═" * 38 + "|n")
        caller.msg("\n".join(lines))

ALL_FACILITY_VERBS.append(CmdRecords)


class CmdQuota(Command):
    """
    What you owe before you're allowed rest — your quotas and arrears.

    Usage:
        quota          — your breeding / milk quota and any debt on the marker
    """
    key           = "quota"
    aliases       = ["owed", "due"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        try:
            from world.compliance import quota_status
        except Exception:
            caller.msg("|xNo quota on file.|n")
            return
        lines, met = quota_status(caller)
        if not lines:
            caller.msg("|xNo quota set against you — yet. The board fills in fast.|n")
            return
        head = "|W── WHAT YOU OWE ──|n"
        foot = ("|g  All quotas met. Rest is permitted — until the board sets the next.|n" if met
                else "|r  Behind. The line does not stop for it, and rest is not yet yours.|n")
        caller.msg(head + "\n" + "\n".join(lines) + "\n" + foot)

ALL_FACILITY_VERBS.append(CmdQuota)


class CmdHeadspace(Command):
    """
    How little you've gotten — your own private read-out of the regression.

    Usage:
        headspace      — how far down you've slipped, and the way back up

    For your eyes only. The number nobody narrates to you, shown plainly because
    it's yours to see: how small you've gotten, what your mouth is doing, and —
    always — the reminder that the way back up is never locked.
    """
    key           = "headspace"
    aliases       = ["little", "howlittle"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        try:
            from world.regression import regression_status
        except Exception:
            caller.msg("|xYou feel entirely grown-up. (Regression isn't loaded.)|n")
            return
        val = float(getattr(caller.db, "regression", 0.0) or 0.0)
        if val <= 0 and not getattr(caller.db, "headspace", None):
            caller.msg("|xYou're all grown up right now — nothing's pulling you small. "
                       "|x(If something starts to, |wheadspace|x will show you how far.)|n")
            return
        caller.msg("\n".join(regression_status(caller)))

ALL_FACILITY_VERBS.append(CmdHeadspace)


class CmdState(Command):
    """
    Everything they've made of you so far — one page, for your own eyes.

    Usage:
        state          — a composed overview: your head, your body, your line, what you owe

    Pulls together the read-outs that are each their own command (|wlook mind|n, |wheadspace|n,
    |wstudbook|n, |wstars|n, |wquota|n) into a single dashboard, so you can see, all at once,
    exactly how far down the line has taken you. The way out is never on this page's terms —
    it's always yours (OOC reset / escape).
    """
    key           = "state"
    aliases       = ["status", "self"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        d = caller.db
        name = d.rp_name or caller.name
        desig = getattr(d, "designation", None)
        lines = [f"|W══ WHAT THEY'VE MADE OF {('YOU' if not desig else '').upper()} ══|n",
                 f"|w  {name}|n" + (f"  |x({desig})|n" if desig and desig != name else "")]

        # Mind — conditioning stage + docility.
        try:
            from typeclasses.mind_state_item import _stage
            cond = float(getattr(d, "conditioning", 0) or 0)
            stg = _stage(cond)
            doc = int(getattr(d, "docility", 0) or 0)
            perm = " |r(set)|n" if getattr(d, "conditioning_permanent", False) else ""
            lines.append(f"|m  mind:|n {stg}{perm}"
                         + (f", docility {doc}" if doc else "") + " |x(look mind)|n")
        except Exception:
            pass

        # Headspace — regression.
        try:
            from world.regression import regression_stage
            reg = float(getattr(d, "regression", 0) or 0)
            if reg > 0 or getattr(d, "headspace", None):
                label, _desc = regression_stage(reg)
                lines.append(f"|m  headspace:|n {label} |x(headspace)|n")
        except Exception:
            pass

        # Body — heat, engorgement, gelding/sissy, denial.
        body = []
        if getattr(d, "perpetual_heat", False):
            body.append("in perpetual heat")
        eb = int(getattr(d, "milk_engorge_beats", 0) or 0)
        if eb >= 2:
            body.append(f"|cengorged, aching to be milked ({eb})|n")
        if getattr(d, "neutered", False):
            body.append("gelded & caged")
        if getattr(d, "sissified", False):
            body.append("sissified")
        if getattr(d, "orgasm_denial", False):
            body.append("denied release")
        if getattr(d, "lactation_locked", False):
            body.append("lactating")
        if body:
            lines.append("|m  body:|n " + ", ".join(body))

        # Line — the brood, one line.
        try:
            counts = dict(getattr(d, "offspring_counts", None) or {})
            tot = sum(int(v) for v in counts.values())
            if tot:
                mg = int(getattr(d, "offspring_max_gen", 1) or 1)
                deep = f", {mg} gens deep" if mg > 1 else ""
                lines.append(f"|m  line:|n {tot} get on file{deep} |x(studbook)|n")
        except Exception:
            pass

        # Stars — if the chart's on her.
        try:
            if getattr(d, "star_chart_on", False):
                from world.star_chart import stars_balance, RELIEF_COST
                sb = stars_balance(caller)
                lines.append(f"|m  stars:|n {sb} saved |x(of {RELIEF_COST} for relief — stars)|n")
        except Exception:
            pass

        # Quota — what's owed before rest.
        try:
            from world.compliance import quota_status
            qlines, met = quota_status(caller)
            if qlines:
                lines.append("|m  owed:|n " + ("|gquota met|n" if met else "|rbehind|n")
                             + " |x(quota)|n")
        except Exception:
            pass

        # Clauses biting right now.
        clause_map = [("teat_gagged", "teat-gag"), ("nurse_first", "nurse-first"),
                      ("stuffed_mouth", "stuffed-mouth"), ("beg_small", "beg-small"),
                      ("star_chart_on", "star-chart")]
        active = [lbl for flag, lbl in clause_map if getattr(d, flag, False)]
        if active:
            lines.append("|m  clauses:|n " + ", ".join(active))

        # Standing/grade, if any.
        try:
            from world.factions import get_standing
            st = get_standing(caller)
            if st:
                lines.append(f"|m  standing:|n {st} |x(standing)|n")
        except Exception:
            pass

        lines.append("|g  and always, off this page entirely: the way out is yours — OOC reset / "
                     "escape gives you your name, your head, and your body back instantly.|n")
        caller.msg("\n".join(lines))

ALL_FACILITY_VERBS.append(CmdState)


class CmdStars(Command):
    """
    Your gold-star chart — earned the only way that counts, and spent on relief.

    Usage:
        stars          — your chart: stars saved, and what relief costs
        stars spend    — spend stars to be allowed to come (if you've earned enough)

    While the Star-Chart clause is on you, you're denied by default. Stars are earned by
    swallowing, getting bred, taking the knot, making your milk — and only stars buy you off.
    """
    key           = "stars"
    aliases       = ["chart", "starchart"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        try:
            from world.star_chart import star_status, stars_balance, spend_stars, RELIEF_COST
        except Exception:
            caller.msg("|xNo chart on you.|n")
            return
        if not getattr(caller.db, "star_chart_on", False):
            caller.msg("|xThere's no star chart on you right now.|n")
            return
        if "spend" in (self.args or "").lower():
            if stars_balance(caller) < RELIEF_COST:
                caller.msg(f"|rNot enough stars yet — you need {RELIEF_COST}. Earn them, good girl.|n")
                return
            spend_stars(caller, RELIEF_COST, "relief")
            room = caller.location
            t = caller.db.rp_name or caller.name
            if room:
                room.msg_contents(f"|W{t} cashes in {RELIEF_COST} hard-earned gold stars — and is "
                                  f"finally, gratefully, allowed to come.|n")
            try:
                from world.compliance import _grant_climax
                _grant_climax(caller)
            except Exception:
                pass
            caller.msg("|xYou spent your stars to be allowed what used to be yours for free. "
                       "That's the trade. You'll earn them all over again, gladly.|n")
            return
        caller.msg("\n".join(star_status(caller)))

ALL_FACILITY_VERBS.append(CmdStars)


class CmdStudbook(Command):
    """
    Your stud-book — every get you've dropped, read back to you by father and by line.

    Usage:
        studbook        — your brood: totals by species, by named sire, generations deep

    The facility keeps the breeding tidy. So can you: who put what in you, how many of
    each, and how deep your own line now breeds itself back through your body.
    """
    key           = "studbook"
    aliases       = ["brood", "getbook"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        try:
            from world.gang_breeding import studbook_lines
        except Exception:
            caller.msg("|xNo stud-book on you.|n")
            return
        lines = studbook_lines(caller)
        if not lines:
            caller.msg("|xNothing on your stud-book yet. The line starts the first time a stud "
                       "catches in you — and the facility is patient about that.|n")
            return
        caller.msg("\n".join(lines))

ALL_FACILITY_VERBS.append(CmdStudbook)


class CmdFacilityUpgrade(MuxCommand):
    """
    Migrate an already-built facility realm in place to the latest systems.

    Usage:
        facilityupgrade [<target>]

    Adds anything new without a teardown — keeping the resident's state and progress:
    new rooms/exits/zones/placards, the Little Box in the Nursery, Bethany's named
    personal studs, and (for a signed resident) the new hidden little-clauses. Idempotent:
    re-running only fills in what's missing. With no target, upgrades your own realm; with
    a target (a character in your location), upgrades theirs.

    All of it stays under the §0 floor — facilityreset/force/purge clears everything.
    """

    key           = "facilityupgrade"
    aliases       = ["facupgrade", "upgradefacility"]
    locks         = "cmd:perm(Developer) or perm(Admin)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        target = caller
        if self.args.strip():
            target = caller.search(self.args.strip())
            if not target:
                return
        try:
            from world.realm_build import facility_upgrade
        except Exception as e:
            caller.msg(f"|rCould not load the upgrader: {e}|n")
            return
        facility_upgrade(target)
        if target != caller:
            caller.msg(f"|gRan the facility upgrade on {target.db.rp_name or target.key}.|n")

ALL_FACILITY_VERBS.append(CmdFacilityUpgrade)


class CmdBethany(Command):
    """
    Bethany's hand on the file — move a unit's progress around (owner / staff).

    Usage:
        bethany <player> = reset           — wipe their Facility quests + EXP (back to Intake)
        bethany <player> = deepend         — throw them straight to Perfected (Deep Stock opens)
        bethany <player> = pluck <quest>   — pull them out of a specific quest
        bethany <player> = nugget [kind]   — reduce to a kept nugget (kind: stumps|paws|hooves)

    Authority: the Facility's owner (Bethany), or staff/Builder. This is in-fiction power —
    it never touches the OOC floor; the unit's own |wescape|n always works regardless.
    """
    key = "bethany"
    aliases = ["fadmin"]
    locks = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        from world.factions import is_owner
        if not (caller.is_superuser or caller.check_permstring("Builder")
                or is_owner(caller, "facility")):
            caller.msg("|xOnly the Facility's owner reaches into the files like that.|n")
            return
        if "=" not in (self.args or ""):
            caller.msg("|xUsage: bethany <player> = reset | deepend | pluck <quest>|n")
            return
        who, action = [p.strip() for p in self.args.split("=", 1)]
        target = caller.search(who, global_search=True)
        if not target:
            return
        import world.quests as Q
        tname = target.db.rp_name or target.key
        a = action.lower()

        if a == "reset":
            Q.reset_quests(target, "facility", also_exp=True)
            Q.start_quest(target, "facility_intake")
            caller.msg(f"|gReset {tname}'s Facility progress — back to Intake.|n")
            target.msg("|MBethany closes your file and opens a fresh one. \"Let's start you over, "
                       "sweetheart. From the top. I do so enjoy a second first day.\"|n")
        elif a == "deepend":
            for qid in ("facility_intake", "facility_breaking",
                        "facility_broodmare", "facility_perfected"):
                Q.complete_quest(target, qid)
            Q.grant_achievement(target, "perfected")
            Q.grant_exp(target, 1800, "facility")
            caller.msg(f"|gThrew {tname} in at the deep end — Perfected; Deep Stock is open.|n")
            target.msg("|MNo gentle descent for you. Bethany signs you straight to the bottom — "
                       "Perfected, finished, racked. \"Some of you don't need the lessons. You "
                       "just need putting away.\"|n")
        elif a.startswith("pluck"):
            bits = action.split(None, 1)
            qid = bits[1].strip().lower() if len(bits) > 1 else ""
            if not Q.get_quest(qid):
                caller.msg("|xUsage: bethany <player> = pluck <quest_id>|n")
                return
            Q.fail_quest(target, qid)
            caller.msg(f"|gPlucked {tname} out of '{qid}'.|n")
            target.msg("|MBethany reaches into your plans and simply removes one. \"No. Not that. "
                       "I decide where you're going.\"|n")
        elif a.startswith("nugget"):
            # bethany <player> = nugget [stumps|paws|hooves]
            bits = action.split(None, 1)
            app = (bits[1].strip().lower() if len(bits) > 1 else "stumps")
            if app not in ("stumps", "paws", "hooves"):
                app = "stumps"
            try:
                from typeclasses.facility_script import apply_nugget
                apply_nugget(target, appendages=app, room=target.location)
                caller.msg(f"|gReduced {tname} to a kept nugget ({app}). Her OOC escape still "
                           f"works instantly — reduction is in-fiction only.|n")
            except Exception as e:
                caller.msg(f"|xCouldn't apply: {e}|n")
        else:
            caller.msg("|xActions: reset | deepend | pluck <quest> | nugget [stumps|paws|hooves]|n")


ALL_FACILITY_VERBS.append(CmdBethany)


class CmdWordCondition(Command):
    """
    Configurable speech conditioning — ban words, or retrain words into others.

    Usage:
        wordcondition <player>                       — show what's set on them
        wordcondition <player> = ban <word>          — she can no longer say <word>
        wordcondition <player> = unban <word>        — lift a ban
        wordcondition <player> = swap <from> > <to>   — she says <to> wherever she'd say <from>
        wordcondition <player> = unswap <from>       — lift a swap
        wordcondition <player> = clear               — clear all word conditioning

    Rides the real speech-filter system (banned_words / word_swap), so it shows in her actual
    speech. Authority: the Facility's owner (Bethany) or staff/Builder. (Player-to-player
    conditioning with a consent handshake is the next build; this is the staff/owner tool.)
    In-fiction only — her own |wescape|n / |wforce_clear|n wipes all of it, instantly.
    """
    key = "wordcondition"
    aliases = ["wordlock", "wordswap"]
    locks = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        from world.factions import is_owner
        if not (caller.is_superuser or caller.check_permstring("Builder")
                or is_owner(caller, "facility")):
            caller.msg("|xOnly the Facility's owner reaches into a unit's speech like that.|n")
            return
        if "=" not in (self.args or ""):
            who = (self.args or "").strip()
            target = caller.search(who, global_search=True) if who else None
            if not target:
                caller.msg("|xUsage: wordcondition <player> = ban|unban|swap|unswap|clear ...|n")
                return
            banned = list(getattr(target.db, "banned_words", None) or [])
            swaps = dict(getattr(target.db, "word_swaps", None) or {})
            tn = target.db.rp_name or target.key
            caller.msg(f"|wWord conditioning on {tn}:|n\n"
                       f"  banned: |r{', '.join(banned) or '(none)'}|n\n"
                       f"  swaps: |y{', '.join(f'{k}->{v}' for k, v in swaps.items()) or '(none)'}|n")
            return
        who, action = [p.strip() for p in self.args.split("=", 1)]
        target = caller.search(who, global_search=True)
        if not target:
            return
        tn = target.db.rp_name or target.key
        parts = action.split(None, 1)
        verb = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        def _ensure_filter(name, on):
            flt = list(getattr(target.db, "active_speech_filters", None) or [])
            if on and name not in flt:
                flt.append(name)
            target.db.active_speech_filters = flt

        if verb == "ban" and rest:
            banned = list(getattr(target.db, "banned_words", None) or [])
            if rest.lower() not in [b.lower() for b in banned]:
                banned.append(rest)
            target.db.banned_words = banned
            _ensure_filter("banned_words", True)
            caller.msg(f"|gConditioned out: {tn} can no longer say '{rest}'.|n")
            target.msg(f"|MThe word '{rest}' is taken from you — you reach for it and it isn't there.|n")
        elif verb == "unban" and rest:
            banned = [b for b in (getattr(target.db, "banned_words", None) or [])
                      if b.lower() != rest.lower()]
            target.db.banned_words = banned
            caller.msg(f"|gLifted the ban on '{rest}' for {tn}.|n")
        elif verb == "swap" and ">" in rest:
            frm, to = [p.strip() for p in rest.split(">", 1)]
            if frm:
                swaps = dict(getattr(target.db, "word_swaps", None) or {})
                swaps[frm] = to
                target.db.word_swaps = swaps
                _ensure_filter("word_swap", True)
                caller.msg(f"|gRetrained {tn}: '{frm}' -> '{to}'.|n")
                target.msg(f"|MWhere you'd say '{frm}', now you say '{to}'. You won't notice you're doing it.|n")
        elif verb == "unswap" and rest:
            swaps = dict(getattr(target.db, "word_swaps", None) or {})
            swaps.pop(rest, None)
            target.db.word_swaps = swaps
            caller.msg(f"|gLifted the swap on '{rest}' for {tn}.|n")
        elif verb == "clear":
            target.db.banned_words = []
            target.db.word_swaps = None
            flt = [f for f in (getattr(target.db, "active_speech_filters", None) or [])
                   if f not in ("banned_words", "word_swap")]
            target.db.active_speech_filters = flt
            caller.msg(f"|gCleared all word conditioning on {tn}.|n")
        else:
            caller.msg("|xUsage: wordcondition <player> = ban <word> | unban <word> | "
                       "swap <from> > <to> | unswap <from> | clear|n")


ALL_FACILITY_VERBS.append(CmdWordCondition)


# ── Player-to-player conditioning (consent-gated) ─────────────────────────────
# Anyone can condition a CONSENTING partner, through the same real systems the facility
# uses (conditioning / installed triggers / speech filters / designation). The spine is the
# §0 floor: the target's own escape / force_clear / facilityreset wipes everything ANY
# conditioner ever did, instantly — and a target can `uncondition` to revoke + clear the
# soft bits themselves at any time. No conditioning is possible without the target's accept.
_COND_SCOPES = ("deepen", "trigger", "speech", "name", "body")
_TRIGGER_RESPONSES = ("kneel", "beg", "orgasm", "blank", "obey", "freeze", "leak", "recite")


class CmdCondition(MuxCommand):
    """
    Condition a consenting partner — brainwash, trigger, retrain speech (player-to-player).

    Usage:
        condition <player>                          — what you may do to them / your status
        condition <player> = offer [scopes]         — ask to condition them (scopes: deepen
                                                       trigger speech name; default all)
        condition/accept <conditioner>              — accept a pending offer
        condition/refuse <conditioner>              — decline a pending offer
        condition <player> = deepen                 — sink them deeper (conditioning + suggestibility)
        condition <player> = trigger <phrase> > <response>   — install a trigger word
                                                       (response: kneel beg orgasm blank freeze leak recite)
        condition <player> = ban <word>             — they can no longer say <word>
        condition <player> = swap <from> > <to>      — they say <to> wherever they'd say <from>
        condition <player> = designate <name>        — give them a designation
        condition <player> = body <track> [amount]   — reshape their body (see `transform tracks`)
        condition <player> = lock | unlock            — seal/unseal their consent (they can't self-revoke)
        condition <player> = release                 — relinquish them (clears your hold)
        condition/allow [scopes]                     — (on yourself) open to conditioning by ANYONE
        condition/allow/lock [scopes]                — open AND lock it (rely on someone to unlock)
        uncondition                                  — (on yourself) revoke consent + clear the soft conditioning

    Consent is required — nothing happens until they `condition/accept` you (or `condition/allow`
    everyone), and only within the granted scopes (deepen, trigger, speech, name, body). Consent can
    be LOCKED so the unit can't take it back themselves — then they rely on a holder to `unlock`, or
    a curse/quest can lock it. The OOC floor is theirs and absolute regardless: |wescape|n /
    |wforce_clear|n undoes ALL of it, always, no matter who did it, how deep, or whether it's locked.
    """
    key = "condition"
    aliases = ["brainwash"]
    locks = "cmd:all()"
    help_category = "Interaction"

    def _consent(self, target):
        return dict(getattr(target.db, "conditioning_consent", None) or {})

    def _scope_ok(self, caller, target, need):
        c = self._consent(target)
        # "any" = they've opened themselves to all comers (consent/allow); else must be you.
        if c.get("by") not in (caller.id, "any"):
            return False, (f"|x{target.db.rp_name or target.key} hasn't consented to be conditioned "
                           f"by you. Try: condition {target.key} = offer|n")
        if need not in (c.get("scope") or []):
            return False, f"|xThat's outside what they consented to (scope: {', '.join(c.get('scope') or [])}).|n"
        return True, ""

    def func(self):
        caller = self.caller

        # switches: accept / refuse a pending offer
        if "accept" in self.switches or "refuse" in self.switches:
            who = self.args.strip()
            target = caller.search(who, global_search=True) if who else None
            if not target:
                caller.msg("|xWhose offer? Usage: condition/accept <conditioner>|n")
                return
            pend = dict(getattr(caller.db, "pending_conditioning", None) or {})
            if pend.get("by") != target.id:
                caller.msg("|xNo pending conditioning offer from them.|n")
                return
            caller.db.pending_conditioning = None
            if "refuse" in self.switches:
                caller.msg(f"|gYou refuse {target.db.rp_name or target.key}'s offer.|n")
                target.msg(f"|x{caller.db.rp_name or caller.key} refused your conditioning offer.|n")
                return
            caller.db.conditioning_consent = {"by": target.id, "by_name": target.key,
                                              "scope": list(pend.get("scope") or _COND_SCOPES)}
            caller.msg(f"|MYou consent to be conditioned by {target.db.rp_name or target.key} "
                       f"(scope: {', '.join(pend.get('scope') or _COND_SCOPES)}). "
                       f"Your |wescape|M always undoes everything.|n")
            target.msg(f"|M{caller.db.rp_name or caller.key} accepts your conditioning. They're yours "
                       f"to work on — within scope, until they say stop.|n")
            return

        # switch: allow — open YOURSELF to conditioning by anyone (optionally lock it so you
        # can't take it back yourself — only an owner unlocks, or the §0 floor).
        #   condition/allow [scopes]            — open to all comers, can still uncondition
        #   condition/allow/lock [scopes]       — open AND locked: you rely on someone to unlock
        if "allow" in self.switches:
            scope = [s for s in (self.args or "").lower().split() if s in _COND_SCOPES] or list(_COND_SCOPES)
            locked = "lock" in self.switches
            caller.db.conditioning_consent = {"by": "any", "by_name": "anyone", "scope": scope,
                                              "locked": locked}
            caller.msg(f"|MYou open yourself to conditioning by anyone (scope: |w{', '.join(scope)}|M)"
                       + ("|M, and |rlock it|M — you can't take it back yourself now; someone has to "
                          "`condition you = unlock`. " if locked else "|M. ")
                       + "Your |wescape|M / |wfacilityreset|M still undoes everything, always.|n")
            return

        if not self.args:
            caller.msg("|xUsage: condition <player> [= offer|deepen|trigger|ban|swap|designate|release ...]|n")
            return

        # view
        if "=" not in self.args:
            target = caller.search(self.args.strip(), global_search=True)
            if not target:
                return
            c = self._consent(target)
            tn = target.db.rp_name or target.key
            if c.get("by") == caller.id:
                caller.msg(f"|w{tn} has consented to your conditioning.|n Scope: "
                           f"|g{', '.join(c.get('scope') or [])}|n.")
            else:
                caller.msg(f"|x{tn} has not consented to be conditioned by you. "
                           f"condition {target.key} = offer|n")
            return

        who, action = [p.strip() for p in self.args.split("=", 1)]
        target = caller.search(who, global_search=True)
        if not target:
            return
        if target == caller:
            caller.msg("|xCondition yourself? Use the facility for that. This is for others.|n")
            return
        tn = target.db.rp_name or target.key
        parts = action.split(None, 1)
        verb = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        # offer — request consent (target accepts with condition/accept)
        if verb == "offer":
            scope = [s for s in rest.lower().split() if s in _COND_SCOPES] or list(_COND_SCOPES)
            target.db.pending_conditioning = {"by": caller.id, "by_name": caller.key, "scope": scope}
            caller.msg(f"|gYou offer to condition {tn} (scope: {', '.join(scope)}). "
                       f"Waiting on their consent.|n")
            target.msg(f"|M{caller.db.rp_name or caller.key} offers to condition you "
                       f"(scope: |w{', '.join(scope)}|M).\n  Accept: |wcondition/accept {caller.key}|M   "
                       f"Refuse: |wcondition/refuse {caller.key}|M\n  (Your |wescape|M always undoes "
                       f"anything done to you, no matter what.)|n")
            return

        if verb == "release":
            if self._consent(target).get("by") in (caller.id, "any"):
                target.db.conditioning_consent = None
                caller.msg(f"|gYou relinquish your hold on {tn}.|n")
                target.msg(f"|x{caller.db.rp_name or caller.key} relinquishes conditioning of you. "
                           f"(What's already in stays until you clear it — `uncondition` or `escape`.)|n")
            else:
                caller.msg("|xYou don't hold them.|n")
            return

        # lock / unlock — the holder can seal their consent so the unit can't take it back
        # themselves (they rely on an owner to unlock, or on the §0 floor). Curses/quests can
        # set the same `locked` flag.
        if verb in ("lock", "unlock"):
            c = self._consent(target)
            if c.get("by") not in (caller.id, "any") or not c:
                caller.msg("|xYou don't hold their consent to lock.|n")
                return
            c["locked"] = (verb == "lock")
            target.db.conditioning_consent = c
            caller.msg(f"|g{'Locked' if verb=='lock' else 'Unlocked'} {tn}'s conditioning consent.|n")
            target.msg(f"|M{caller.db.rp_name or caller.key} "
                       + ("|rlocks|M your consent — you can't revoke it yourself now. (Your |wescape|M "
                          "still frees you, always.)" if verb == "lock"
                          else "unlocks your consent — you can `uncondition` again.") + "|n")
            return

        # everything below needs scoped consent
        scope_needed = {"deepen": "deepen", "trigger": "trigger", "ban": "speech",
                        "swap": "speech", "designate": "name", "body": "body"}.get(verb)
        if scope_needed is None:
            caller.msg("|xActions: offer | deepen | trigger <phrase> > <response> | ban <word> | "
                       "swap <from> > <to> | designate <name> | body <track> [amt] | lock | unlock | release|n")
            return
        ok, reason = self._scope_ok(caller, target, scope_needed)
        if not ok:
            caller.msg(reason)
            return

        if verb == "deepen":
            try:
                from world.conditioning import add_conditioning
                add_conditioning(target, 6.0, source="player")
            except Exception:
                pass
            target.db.suggestibility = float(getattr(target.db, "suggestibility", 0) or 0) + 2.0
            caller.msg(f"|MYou sink {tn} a little deeper.|n")
            target.msg(f"|m{caller.db.rp_name or caller.key}'s voice works at you, patient and low, "
                       f"and something in you settles further down where they're putting you.|n")
        elif verb == "trigger":
            if ">" not in rest:
                caller.msg("|xUsage: condition <player> = trigger <phrase> > <response>  "
                           f"(response: {', '.join(_TRIGGER_RESPONSES)})|n")
                return
            phrase, response = [p.strip() for p in rest.split(">", 1)]
            response = response.lower()
            if response not in _TRIGGER_RESPONSES:
                caller.msg(f"|xResponse must be one of: {', '.join(_TRIGGER_RESPONSES)}|n")
                return
            try:
                from world.binding_effects import install_trigger
                install_trigger(target, phrase, response=response, strength=2)
                caller.msg(f"|MYou seat a trigger in {tn}: \"{phrase}\" -> {response}.|n")
                target.msg(f"|m{caller.db.rp_name or caller.key} works a phrase into you until it sits "
                           f"below thinking. You won't feel it there — until someone says it.|n")
            except Exception as e:
                caller.msg(f"|xCouldn't seat it: {e}|n")
        elif verb in ("ban", "swap"):
            self._speech(caller, target, tn, verb, rest)
        elif verb == "designate":
            if not rest:
                caller.msg("|xUsage: condition <player> = designate <name>|n")
                return
            target.db.designation = rest
            caller.msg(f"|MYou designate {tn}: \"{rest}\".|n")
            target.msg(f"|m{caller.db.rp_name or caller.key} gives you a designation: \"{rest}\". "
                       f"It starts to feel more true than your name.|n")
        elif verb == "body":
            from world.transformation import apply_tf, TRACKS
            bits = rest.split()
            track = bits[0].lower() if bits else ""
            if track not in TRACKS:
                caller.msg(f"|xUsage: condition <player> = body <track> [amount]. "
                           f"Tracks: {', '.join(TRACKS)}|n")
                return
            try:
                amt = float(bits[1]) if len(bits) > 1 else 1.0
            except ValueError:
                amt = 1.0
            # Player-to-player: SCALE what they have / force production — never add a part
            # they didn't choose (allow_add=False). The facility is what adds parts.
            crossed, msg = apply_tf(target, track, amt, allow_add=False)
            room = target.location
            if crossed and room and msg:
                room.msg_contents(msg)
                caller.msg(f"|MYou push {tn}'s body along ({track} {amt:+g}).|n")
            else:
                caller.msg(msg or "|x(nothing changed)|n")

    def _speech(self, caller, target, tn, verb, rest):
        def _ensure_filter(name):
            flt = list(getattr(target.db, "active_speech_filters", None) or [])
            if name not in flt:
                flt.append(name); target.db.active_speech_filters = flt
        if verb == "ban" and rest:
            banned = list(getattr(target.db, "banned_words", None) or [])
            if rest.lower() not in [b.lower() for b in banned]:
                banned.append(rest)
            target.db.banned_words = banned
            _ensure_filter("banned_words")
            caller.msg(f"|MYou take the word '{rest}' from {tn}.|n")
            target.msg(f"|mThe word '{rest}' goes missing from your mouth — you reach and it isn't there.|n")
        elif verb == "swap" and ">" in rest:
            frm, to = [p.strip() for p in rest.split(">", 1)]
            if frm:
                swaps = dict(getattr(target.db, "word_swaps", None) or {})
                swaps[frm] = to
                target.db.word_swaps = swaps
                _ensure_filter("word_swap")
                caller.msg(f"|MYou retrain {tn}: '{frm}' -> '{to}'.|n")
                target.msg(f"|mWhere you'd say '{frm}', now '{to}' comes out instead. You stop noticing.|n")
        else:
            caller.msg("|xUsage: = ban <word>  |  = swap <from> > <to>|n")


ALL_FACILITY_VERBS.append(CmdCondition)


class CmdUncondition(Command):
    """
    Walk back conditioning done to you by another player (a soft self-clear).

    Usage:
        uncondition

    Revokes any player's consent to condition you and clears the configurable conditioning
    (banned/swapped words, designation, the echo filter). For a TOTAL wipe of everything —
    facility processing, triggers, the lot — use the OOC floor: |wescape|n / |wfacilityreset|n,
    which is always free and never gated.
    """
    key = "uncondition"
    aliases = ["unbrainwash"]
    locks = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        c = dict(getattr(caller.db, "conditioning_consent", None) or {})
        if c.get("locked"):
            caller.msg("|rYour conditioning consent is locked — you can't take it back yourself. "
                       "Someone has to `condition you = unlock`.\n|x(The OOC floor is always yours, "
                       "though: |wescape|x / |wfacilityreset|x frees you completely, no matter what.)|n")
            return
        caller.db.conditioning_consent = None
        caller.db.pending_conditioning = None
        caller.db.banned_words = []
        caller.db.word_swaps = None
        flt = [f for f in (getattr(caller.db, "active_speech_filters", None) or [])
               if f not in ("banned_words", "word_swap", "echo_self")]
        caller.db.active_speech_filters = flt
        caller.db.designation = None
        caller.msg("|gYou shake off the words and the retraining you can reach. Your speech is your "
                   "own again, and no one holds your conditioning.\n"
                   "|x(Triggers and deeper conditioning, and anything the facility did, clear with the "
                   "full floor: |wescape|x / |wfacilityreset|x.)|n")


ALL_FACILITY_VERBS.append(CmdUncondition)


class CmdBody(Command):
    """
    Read a body's current transformation — the parts the serums and the Process reshaped.

    Usage:
        body            — your own reshaped anatomy
        body <player>   — read another's (what shows to anyone who looks)
    """
    key = "body"
    aliases = ["anatomy"]
    locks = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        target = caller
        if self.args.strip():
            target = caller.search(self.args.strip(), global_search=True)
            if not target:
                return
        from world.transformation import body_summary
        lines = body_summary(target)
        tn = target.db.rp_name or target.key
        if not lines:
            caller.msg(f"|x{tn}'s body is unremarkable — nothing reshaped (yet).|n")
            return
        caller.msg(f"|w── {tn}'s body ──|n\n" + "\n".join(lines))


ALL_FACILITY_VERBS.append(CmdBody)


class CmdTransform(Command):
    """
    Reshape a unit's body (owner / staff) — push a transformation track.

    Usage:
        transform <player> = <track> [amount]
        transform tracks                         — list the tracks

    Tracks: cock, balls, breasts, lips, clit, ass, lactation, feral. Repeated doses cross
    thresholds that rewrite how the part reads (shows in `body` / `marks`); negative shrinks.
    Authority: on YOURSELF, freely — your body, your parts (the parts you want are yours to set).
    On ANOTHER, only the Facility's owner (Bethany) / staff/Builder may add or force parts; a
    consenting player can SCALE what you have with `condition <player> = body <track>`, but not
    give you parts you didn't choose. In-fiction only — |wescape|n clears all of it.
    """
    key = "transform"
    aliases = ["tf", "morph"]
    locks = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        from world.transformation import apply_tf, TRACKS
        if (self.args or "").strip().lower() == "tracks":
            caller.msg("|wTF tracks:|n " + ", ".join(TRACKS))
            return
        if "=" not in (self.args or ""):
            caller.msg("|xUsage: transform [<player> =] <track> [amount]   (no player = yourself)|n")
            return
        who, spec = [p.strip() for p in self.args.split("=", 1)]
        target = caller.search(who, global_search=True) if who else caller
        if not target:
            return
        # Your own body is yours to shape. Reshaping ANOTHER (adding/forcing parts) is facility power.
        if target != caller:
            from world.factions import is_owner
            if not (caller.is_superuser or caller.check_permstring("Builder")
                    or is_owner(caller, "facility")):
                caller.msg("|xThat's not yours to do — only the facility reshapes another unit. "
                           "(A consenting player can SCALE, not add, via `condition <them> = body`.)|n")
                return
        bits = spec.split()
        track = bits[0].lower() if bits else ""
        if track not in TRACKS:
            caller.msg(f"|xTracks: {', '.join(TRACKS)}|n")
            return
        try:
            amt = float(bits[1]) if len(bits) > 1 else 1.0
        except ValueError:
            amt = 1.0
        crossed, msg = apply_tf(target, track, amt, allow_add=True)
        room = target.location
        if room and msg:
            room.msg_contents(msg)
        tn = "yourself" if target == caller else (target.db.rp_name or target.key)
        caller.msg(f"|gReshaped {tn}: {track} {amt:+g}" + ("." if crossed else " (no new stage yet).") + "|n")


ALL_FACILITY_VERBS.append(CmdTransform)


class CmdTab(Command):
    """
    Your tab — the debt the house is carrying against you, if any.

    Usage:
        tab          — your arrears and where the marker stands
    """
    key           = "tab"
    aliases       = ["debt", "marker", "arrears"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        from world.economy import (get_balance, debt_amount, indenture_due,
                                    INDENTURE_AT, DEBT_FLOOR)
        bal  = get_balance(caller)
        owed = debt_amount(caller)
        if owed <= 0:
            caller.msg(f"|gNo marker against you. Account: |w{bal:,}|g scrip, in the black.|n")
            return
        lines = [f"|rThe house carries a marker against you: |w{owed:,}|r scrip in arrears "
                 f"(balance |w{bal:,}|r).|n"]
        if indenture_due(caller):
            lines.append("|R The marker's been called. Clear it, or — by your own choice only — "
                         "work it off on the block: |windenture|R. The door stays free regardless.|n")
        else:
            lines.append(f"|x The house will carry you to {DEBT_FLOOR:,}; it calls the marker "
                         f"at {INDENTURE_AT:,}.|n")
        caller.msg("\n".join(lines))

ALL_FACILITY_VERBS.append(CmdTab)


def _drive_quest(caller, qid):
    """Start (if needed) and run an escaped-meta quest straight to completion so its
    resolver fires now — the loose-stock actions play out on use, not on a slow cycle
    beat. Returns (ok, msg) where ok is False if it couldn't be started."""
    import world.quests as Q
    qdef = Q.get_quest(qid)
    if not qdef:
        return False, "No such action."
    if Q.quest_state(caller, qid).get("state") != "active":
        ok, msg = Q.start_quest(caller, qid)
        if not ok:
            return False, msg
    # Advance the plot to completion — fires the registered resolver via complete_quest.
    total = sum(int(s.get("count", 1)) for s in qdef.get("steps", []))
    step = (qdef.get("steps") or [{"id": "process"}])[0].get("id", "process")
    Q.advance_quest(caller, qid, step, total)
    return True, ""


class CmdTurnIn(Command):
    """
    Walk back in and put yourself on the board (only while you're loose).

    Usage:
        turnin

    After a malfunction lets you out, the ache for the line doesn't leave. This walks
    you back through the lobby and asks Bethany to take you back. (In-fiction only — the
    |wescape|n / |wfacilityreset|n OOC floor is something else entirely, and always works.)
    """
    key = "turnin"
    aliases = ["turn-in", "turnmein"]
    locks = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        if not getattr(caller.db, "facility_escaped", False):
            caller.msg("|xYou're not loose — you're already on the board. (This is for after a "
                       "malfunction run gets you out.)|n")
            return
        ok, msg = _drive_quest(caller, "turn_in")
        if not ok:
            caller.msg(f"|x{msg}|n")


ALL_FACILITY_VERBS.append(CmdTurnIn)


class CmdSpringStock(Command):
    """
    Slip back in and try to cut a unit loose (only while you're loose).

    Usage:
        springstock

    You know the gaps now — the fault timings, the pen routes, the waystone word. Going
    back in to free a unit pays in standing if you get away with it, and is catastrophic
    if you're caught: the house will make you the example. (In-fiction only — the OOC
    |wescape|n floor is never this and never rolls.)
    """
    key = "springstock"
    aliases = ["spring", "liberate", "rescue"]
    locks = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        if not getattr(caller.db, "facility_escaped", False):
            caller.msg("|xYou're inside — you can't spring stock from the board. Get loose first "
                       "(the Deep Stock malfunction), then come back for them.|n")
            return
        ok, msg = _drive_quest(caller, "spring_stock")
        if not ok:
            caller.msg(f"|x{msg}|n")


ALL_FACILITY_VERBS.append(CmdSpringStock)


def _do_indenture(caller):
    """Consensually convert a member into indentured facility stock — flags, mark,
    conditioning seed, debt cleared, and (if a realm context exists) the cycle picks
    them up. Reversible by the OOC floor like everything else."""
    from world.economy import clear_debt
    t    = caller.db.rp_name or caller.key
    room = caller.location
    caller.db.indentured      = True
    caller.db.facility_role   = "resident"
    caller.db.facility_signed = True
    caller.db.facility_active = True
    clear_debt(caller, "marker cleared — signed self over to indenture")
    try:
        from world.gang_breeding import record_mark
        record_mark(caller, f"INDENTURED — {t} signed herself over to the house to work off a "
                    f"called marker; now stock, worked and catalogued like any unit", mode="on")
    except Exception:
        pass
    try:
        from world.conditioning import add_conditioning
        add_conditioning(caller, 10.0, source="indenture")
    except Exception:
        pass
    # If she has a realm/cycle context, let the line pick her up.
    try:
        from typeclasses.facility_script import RealmCycleScript
        if getattr(caller.db, "realm", None) and not any(
                getattr(s, "key", "") == "realm_cycle" for s in caller.scripts.all()):
            from evennia.utils import create
            create.create_script(RealmCycleScript, obj=caller, key="realm_cycle")
    except Exception:
        pass
    if room:
        room.msg_contents(
            f"|R{t} signs the indenture herself — no one makes her, that's the whole horror of "
            f"it — and the registrar logs the marker CLEARED against a body signed over to the "
            f"house. The coverall comes off, a stock number goes on, and {t} is walked onto the "
            f"line she used to watch from the booths. The buyer becomes the bought, by her own "
            f"hand.|n")
    caller.msg("|MYou're stock now, by your own signature. The debt's gone; the body that paid it "
               "is the house's.|n |GThe door is still right there — |wescape|G — and always will "
               "be, indentured or not.|n")


class CmdIndenture(Command):
    """
    Work a called debt off the only way the house takes it — your body, on the block.

    Usage:
        indenture            — the terms, and whether your marker's been called
        indenture confirm    — sign yourself over as indentured stock (your choice)

    This is in-fiction servitude you CHOOSE. It never happens automatically and never
    without this command — the house cannot put you on the line over a debt; only you
    can. And it is not the door: escape / force_clear / facilityreset always free you,
    indentured or not, debt or no debt, at any moment. This is dread you opt into, on
    top of a floor that never moves.
    """
    key           = "indenture"
    aliases       = ["selfindenture"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        from world.economy import debt_amount, indenture_due
        arg  = self.args.strip().lower()
        owed = debt_amount(caller)
        if arg not in ("confirm", "yes", "sign"):
            owe_line = (f"  You owe the house |w{owed:,}|n scrip.\n" if owed
                        else "  You owe the house nothing right now — this would be wholly voluntary.\n")
            caller.msg(
                "|RINDENTURE — the terms.|n\n" + owe_line +
                "  |xSigning yourself over makes you facility stock: worked, milked, bred, "
                "catalogued and sold like any unit, your marker cleared by your body. It is a "
                "choice you make — never one made for you.|n\n"
                "  |GThe out-of-character exit is untouched: |wescape|G frees you instantly, "
                "indentured or not, at any balance.|n\n"
                "  |x→ |windenture confirm|x to sign yourself over.|n")
            return
        if getattr(caller.db, "indentured", False):
            caller.msg("|xYou're already indentured stock. The books have you.|n")
            return
        _do_indenture(caller)

ALL_FACILITY_VERBS.append(CmdIndenture)


class CmdBid(Command):
    """
    Bid on a lot from the Buyers' Gallery.

    Usage:
        bid <subject>            — read the lot's asking price and the standing bid
        bid <subject> <amount>   — enter a number; if it tops the floor it stands

    You watch through the one-way glass while she's posed, opened, and run on the
    floor below, and you put a number on her. The high bid is logged against her
    card. It does not buy her — an owner closes the sale with 'process <her> buy'
    — but it sets what she's worth tonight, out loud, where she can't hear it.
    """
    key           = "bid"
    aliases       = ["offer"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        parts  = self.args.strip().split(None, 1)
        if not parts:
            caller.msg("|xUsage: bid <subject> [amount]|n")
            return
        target = caller.search(parts[0])
        if not target:
            return
        room = caller.location
        fs   = _fac_script(room)
        cn   = caller.db.rp_name or caller.key
        t    = target.db.rp_name or target.name

        # current floor price from the real appraisal
        floor = 0
        if fs:
            try:    floor = int(fs._appraise(target) or 0)
            except Exception: floor = 0
        high  = int(getattr(target.db, "high_bid", 0) or 0)
        bidder = getattr(target.db, "high_bidder", None)
        ask   = max(floor, high)

        # ── read-only: just look at the card ──────────────────────────────
        if len(parts) == 1:
            grade  = getattr(target.db, "facility_grade", None) or "Unprocessed"
            counts = sum(int(v) for v in (getattr(target.db, "offspring_counts", None) or {}).values())
            line = (f"|W{t} — lot card|n\n  |xGrade:|n {grade}   |xGet dropped:|n {counts}"
                    f"   |xConditioning:|n {float(getattr(target.db,'conditioning',0) or 0):.0f}"
                    f"\n  |xFloor:|n |w{floor:,}|n")
            if high:
                line += f"   |xStanding bid:|n |w{high:,}|n" + (f" |x({bidder})|n" if bidder else "")
            else:
                line += "   |xNo bids yet.|n"
            caller.msg(line)
            return

        # ── place a bid ───────────────────────────────────────────────────
        raw = parts[1].strip().replace(",", "").replace("$", "")
        if not raw.lstrip("-").isdigit():
            caller.msg("|xA bid is a number. Try: bid <subject> 4000|n")
            return
        amount = int(raw)
        if amount <= 0:
            caller.msg("|xBid something real.|n")
            return
        if amount < floor:
            caller.msg(f"|x{floor:,} is the floor on this lot. Bid {floor:,} or more.|n")
            return
        if amount <= high:
            caller.msg(f"|xThe standing bid is {high:,}. You'll need to top it.|n")
            return
        # your bid has to be money you actually have — it's charged if you win the gavel
        from world.economy import get_balance
        if get_balance(caller) < amount:
            caller.msg(f"|xYou can't back {amount:,}; your account holds |w{get_balance(caller):,}|x "
                       f"scrip. Bid what you can cover — the gavel charges the winner.|n")
            return

        target.db.high_bid       = amount
        target.db.high_bidder    = cn
        target.db.high_bidder_id = caller.id
        caller.msg(f"|RYou put {amount:,} on {t} (you hold {get_balance(caller):,} scrip). It's "
                   f"the high bid — logged on her card, charged if it stands at the gavel.|n")
        room.msg_contents(f"|R{cn} bids |w{amount:,}|R on {t} — high bid, logged.|n",
                          exclude=[caller])
        # carry it through the glass: she feels the number land even if she can't hear it
        try:
            tloc = target.location
            if tloc and tloc is not room:
                tloc.msg_contents(f"|mSomewhere behind the glass a number changes; {t}'s "
                                  f"card now reads |w{amount:,}|m. She doesn't know why the "
                                  f"handlers suddenly reposition her.|n")
        except Exception:
            pass


ALL_FACILITY_VERBS.append(CmdBid)


def _showroom_lot(gallery_room, caller):
    """From the gallery, resolve the adjacent showroom and the facility subject
    posed on the block there. Returns (showroom_room, lot_character) or (None, None)."""
    if not gallery_room:
        return None, None
    try:
        from typeclasses.characters import Character
    except Exception:
        Character = None
    for ex in gallery_room.exits:
        dest = getattr(ex, "destination", None)
        if dest and "showroom" in (getattr(dest, "key", "") or "").lower():
            for obj in dest.contents:
                if obj is caller:
                    continue
                if Character and not isinstance(obj, Character):
                    continue
                if getattr(obj.db, "facility_active", False):
                    return dest, obj
            return dest, None
    return None, None


def _lot_script(target):
    """The cycle/facility script that drives this lot (lives on the character)."""
    if not target:
        return None
    for s in target.scripts.all():
        if hasattr(s, "_appraise") and hasattr(s, "_gang"):
            return s
    return None


class CmdTip(Command):
    """
    Tip the floor staff to work the lot on the block — from your booth.

    Usage:
        tip                  — show who's on the block and the menu of demands
        tip <what>           — pay the floor to do it to her, now, through the glass

    Demands: milk, breed, dose, pierce, condition, grow, ring, pose.

    You don't only watch. You name a thing and the handlers on the floor oblige
    while you sip — the real systems fire, on her, on file. She feels it land and
    never learns it came from a seat behind the mirror.
    """
    key           = "tip"
    aliases       = ["request"]
    locks         = "cmd:all()"
    help_category = "Interaction"

    _MENU = ("milk", "breed", "dose", "pierce", "condition", "grow", "ring", "pose")
    # what the floor charges to do each thing, in scrip
    _TIP_COST = {"milk": 60, "breed": 150, "dose": 90, "pierce": 120,
                 "condition": 110, "grow": 130, "ring": 120, "pose": 40}

    def func(self):
        caller = self.caller
        gallery = caller.location
        show, lot = _showroom_lot(gallery, caller)
        if not show:
            caller.msg("|xYou're not in the gallery — there's no glass to tip through.|n")
            return
        if not lot:
            caller.msg("|xThe block's empty right now. Nothing on it to tip the floor for.|n")
            return

        cn = caller.db.rp_name or caller.key
        t  = lot.db.rp_name or lot.name
        what = self.args.strip().lower()

        from world.economy import get_balance, spend_credits, add_credits

        if not what:
            menu = "  ".join(f"|w{m}|n |x({self._TIP_COST.get(m, 80):,})|n" for m in self._MENU)
            caller.msg(f"|W{t} is on the block.|n  |xYour scrip:|n |w{get_balance(caller):,}|n"
                       f"\n  |xTip the floor to:|n {menu}\n  |x(e.g. |wtip breed|x — done to her "
                       f"now, through the glass. The floor doesn't work on credit.)|n")
            return

        # normalise a few synonyms onto the menu
        alias = {"fuck": "breed", "use": "breed", "drug": "dose", "udder": "grow",
                 "rings": "ring", "present": "pose", "break": "condition"}
        what = alias.get(what, what)
        if what not in self._MENU:
            caller.msg(f"|xThe floor doesn't do '{what}'. Try: |w{', '.join(self._MENU)}|n")
            return

        # the floor takes its fee up front — no scrip, no service
        cost = self._TIP_COST.get(what, 80)
        ok, bal = spend_credits(caller, cost, f"Tip — '{what}' on lot {t}.")
        if not ok:
            caller.msg(f"|xThat costs |w{cost:,}|x scrip and you have |w{get_balance(caller):,}|x. "
                       f"The floor doesn't work on credit.|n")
            return

        fs = _lot_script(lot)
        cond = float(getattr(lot.db, "conditioning", 0) or 0)
        # what the buyers and the floor see happen; what she feels
        floor_line = None  # broadcast in the showroom (visible action)
        felt_line  = None  # to the lot herself

        if what == "milk":
            if fs:
                try: fs._start_milking(lot)
                except Exception: pass
            floor_line = (f"|cAt a tip from behind the glass, a handler walks out, clamps the "
                          f"cups onto {t} on the block, and sets her milking for the room.|n")
            felt_line  = ("|cThe cups close over you on the turntable and the pull starts — "
                          "ordered by someone you can't see, watched by faces you'll never meet.|n")
        elif what == "breed":
            if fs:
                try: fs._gang(show, lot, t, cond)
                except Exception: pass
            try:
                import random as _r
                from typeclasses.insemination_item import do_inseminate
                zone = None
                if fs:
                    holes = fs._holes_only(lot)
                    zone = _r.choice(holes) if holes else (fs._orifices(lot) or [None])[0]
                if zone:
                    do_inseminate(caller, lot, zone, {
                        "source": "machine", "fluid_type": "semen",
                        "volume_per_tick": _r.uniform(80, 200), "ttl_hours": 24.0})
            except Exception:
                pass
            floor_line = (f"|rA tip lands and a handler steps up onto the block and breeds {t} "
                          f"where she's posed — bent over the rail, lit, turned, taken for the "
                          f"booths to watch.|n")
            felt_line  = ("|rHands fold you over the rail and you're bred on the turntable, in "
                          "the light, for a room of bidders you can't see — paid for, on demand.|n")
        elif what == "dose":
            if fs:
                try: fs._dose(show, lot, t)
                except Exception: pass
            floor_line = (f"|GA buyer tips for a dose; a handler crosses the floor and puts a "
                          f"measure into {t} on the block, the room watching it take her.|n")
            felt_line  = ("|GA needle, a cup, a wet cloth over your face — and the block goes "
                          "warm and far away while strangers watch the dose do its work.|n")
        elif what == "pierce":
            try:
                from world.gang_breeding import add_piercing
                d = add_piercing(lot)
            except Exception:
                d = None
            if d:
                floor_line = (f"|GOn a tip, a handler steps up and pierces {t} on the block — "
                              f"{d} — done in the spotlight while the booths lean in.|n")
                felt_line  = (f"|GThe gun bites — {d} — set into you on the turntable, lit and "
                              f"turning, a new ring paid for by a hand you'll never see.|n")
            else:
                add_credits(caller, cost, "Tip refunded — nothing left to pierce.")
                caller.msg(f"|xNothing left on {t} to pierce. Your |w{cost:,}|x scrip is returned.|n")
                return
        elif what == "condition":
            try:
                from world.conditioning import add_conditioning
                add_conditioning(lot, 8.0, source="gallery")
            except Exception:
                pass
            floor_line = (f"|MA tip buys a session: a handler takes {t}'s head on the block — "
                          f"murmuring, repeating, pressing it deeper — and a little more of her "
                          f"gives, in front of everyone.|n")
            felt_line  = ("|MA voice at your ear on the turntable, patient and certain, presses "
                          "the same words deeper — and you feel a little more of yourself go, "
                          "watched, bought, on the block.|n")
        elif what == "grow":
            if fs:
                try: fs._proc_udder(show, lot, t)
                except Exception: pass
            floor_line = (f"|GA tip funds a growth cycle; a handler runs {t}'s glands up a stage "
                          f"on the block, swelling her for the room to see.|n")
            felt_line  = ("|GHeat blooms through your chest as the cycle drives your glands "
                          "fuller on the turntable — grown a size for an audience, on demand.|n")
        elif what == "ring":
            if fs:
                try: fs._proc_rings(show, lot, t)
                except Exception: pass
            floor_line = (f"|GA buyer tips for hardware and a handler rings {t} where she stands "
                          f"on the block, the new steel catching the spotlight.|n")
            felt_line  = ("|GCold steel is set through you on the turntable, weight added where "
                          "the booths can see it swing — bought, fitted, turned to the light.|n")
        elif what == "pose":
            lot.db.body_language = "posed on the block — turned, opened, offered to the glass"
            floor_line = (f"|WA tip, and a handler repositions {t} on the turntable — chin up, "
                          f"spread, opened to the mirror, held there for the booths.|n")
            felt_line  = ("|WHands set you into a pose on the block and leave you there — "
                          "spread, lit, turning slow, offered to a wall of glass you can't see "
                          "past — because someone behind it asked.|n")

        # log the demand on her card
        log = list(getattr(lot.db, "gallery_demands", None) or [])
        log.append((caller.id, cn, what))
        lot.db.gallery_demands = log[-40:]

        # broadcast: the floor (visible), the gallery (the buyers watching), the lot (felt)
        if floor_line:
            show.msg_contents(floor_line, exclude=[lot])
        gallery.msg_contents(f"|x{cn} tips the floor — '{what}' — and you watch it done to {t} "
                             f"through the glass.|n", exclude=[caller])
        caller.msg(f"|RYou tip the floor to {what} {t} — |w{cost:,}|R scrip, balance "
                   f"|w{bal:,}|R. It happens on the block while you watch, and she never sees "
                   f"the seat it came from.|n")
        # a cut of the buyer's tip is credited to her own account; the house skims the rest
        try:
            add_credits(lot, max(10, cost // 4),
                        f"Tip cut credited — a buyer paid {cost:,} to use you on the block.")
            from world.economy import skim
            skim(lot, cost, f"House cut — tip ('{what}') on {t}.")
        except Exception:
            pass
        if felt_line:
            lot.msg(felt_line)


ALL_FACILITY_VERBS.append(CmdTip)
