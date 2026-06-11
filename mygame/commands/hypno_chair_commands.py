"""
commands/hypno_chair_commands.py

Verbs for the Spiral Chair (typeclasses/hypno_chair.py).

  hypnosit    — settle into the chair; the induction starts on its own
  hypnorise   — surface and stand; deep trance resists once or twice, then yields,
                and the session timer ALWAYS frees you regardless

Never a stuck-spot: timer / struggle / leaving / disconnect / the §0 floor all release.
"""

import time

from evennia import Command


class CmdHypnoSit(Command):
    """
    Settle into the spiral chair.

    Usage:
        hypnosit

    The chair was made for you — Bethany had your measurements off the file. The induction
    runs itself: the spiral, her recorded voice, the slow staged sinking. It will tip you
    back out on its own when the session ends; |whypnorise|n surfaces you sooner (the deep
    stages resist, briefly, and then let go — the door is never locked, it just gets harder
    to want).
    """
    key   = "hypnosit"
    aliases = ["sitspiral", "spiralsit"]
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            return
        zone = getattr(room.db, "hypno_chair_zone", None)
        if not zone:
            caller.msg("|xThere's no spiral chair here.|n")
            return
        if getattr(caller.db, "in_hypno_chair", None):
            caller.msg("|xYou're already in the chair. Watch the spiral.|n")
            return
        caller.db.in_hypno_chair  = zone
        caller.db.chair_stage     = 0
        caller.db.chair_beats     = 0
        caller.db.chair_release_at = time.time() + 420.0
        caller.db.chair_struggle  = 0.0
        name = caller.db.rp_name or caller.name
        room.msg_contents(f"|x{name} settles into the spiral chair. The headrest tips, the "
                          f"spiral overhead begins its slow turn, and a warm recorded voice "
                          f"starts up too low for anyone else to follow.|n", exclude=[caller])
        caller.msg("|wYou sit. The chair takes you like it was measured for you — it was. "
                   "The session ends on its own; |xhypnorise|w surfaces you sooner.|n")
        from typeclasses.hypno_chair import HypnoChairScript
        from evennia.utils import create
        if not HypnoChairScript.is_running(room):
            create.create_script(HypnoChairScript, obj=room, persistent=True, autostart=True)


class CmdHypnoRise(Command):
    """
    Surface from the spiral chair.

    Usage:
        hypnorise

    Shallow trance: you just stand. Deep trance: the spiral leans on you once or twice —
    keep trying, it yields — and the session timer always frees you regardless.
    """
    key   = "hypnorise"
    aliases = ["risespiral", "surface"]
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room = caller.location
        zone = getattr(room.db, "hypno_chair_zone", None) if room else None
        if not getattr(caller.db, "in_hypno_chair", None) or caller.db.in_hypno_chair != zone:
            caller.msg("|xYou're not in the spiral chair.|n")
            if getattr(caller.db, "in_hypno_chair", None):
                caller.db.in_hypno_chair = None   # stale-flag cleanup
            return
        from typeclasses.hypno_chair import HypnoChairScript, _DEEP_STAGE, _CHAIR_STRUGGLE_AT, _STRUGGLE_FAIL
        import random as _r
        script = next((s for s in room.scripts.all() if isinstance(s, HypnoChairScript)), None)
        stage = int(getattr(caller.db, "chair_stage", 0) or 0)
        now = time.time()
        deep = stage >= _DEEP_STAGE and now < float(getattr(caller.db, "chair_release_at", 0) or 0)
        if deep:
            struggle = float(getattr(caller.db, "chair_struggle", 0) or 0) + 1.0
            caller.db.chair_struggle = struggle
            if struggle < _CHAIR_STRUGGLE_AT:
                remain = max(0, int(float(caller.db.chair_release_at) - now))
                caller.msg("|x  " + _r.choice(_STRUGGLE_FAIL) + "|n")
                caller.msg(f"|x  (surfacing: {struggle:.0f}/{_CHAIR_STRUGGLE_AT:.0f} — or the "
                           f"session ends itself in ~{remain}s)|n")
                return
            if script:
                script.release(caller, room, reason="struggle")
            else:
                caller.db.in_hypno_chair = None
                caller.db.chair_stage = 0
            return
        # shallow — just stand up
        if script:
            script.release(caller, room, reason="struggle")
        else:
            caller.db.in_hypno_chair = None
            caller.db.chair_stage = 0
        name = caller.db.rp_name or caller.name
        if room:
            room.msg_contents(f"|x{name} rises from the spiral chair, blinking the turn out of "
                              f"her eyes.|n", exclude=[caller])


ALL_HYPNO_CMDS = [CmdHypnoSit, CmdHypnoRise]
