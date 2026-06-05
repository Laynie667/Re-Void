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
        # a cut of the buyer's tip is credited to her own account — paid for her own use
        try:
            add_credits(lot, max(10, cost // 4),
                        f"Tip cut credited — a buyer paid {cost:,} to use you on the block.")
        except Exception:
            pass
        if felt_line:
            lot.msg(felt_line)


ALL_FACILITY_VERBS.append(CmdTip)
