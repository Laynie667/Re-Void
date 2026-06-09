"""
commands/little_box_commands.py

Commands for the Little Box furniture (see typeclasses/little_box.py).

  boxin       — climb into the box (starts the session; it keeps you little)
  boxout      — climb out; if the lid's locked, work the latch (always shows progress)
  boxstatus   — how little, lid state, time until the nap springs it, struggle progress

The box is never a stuck-spot: the nap timer always springs the lid, you can wriggle it
yourself, leaving the room or disconnecting releases you, and the OOC floor always works.
"""

import time

from evennia import Command


class CmdBoxIn(Command):
    """
    Climb into the little box.

    Usage:
        boxin

    The box keeps you while you're in it — ticking you littler, murmuring, feeding you.
    It will let you out on its own when the nap's up; you can also work the latch
    yourself with |wboxout|n. It never locks you away for good.
    """
    key   = "boxin"
    aliases = ["getin", "climbin"]
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            return
        zone = getattr(room.db, "little_box_zone", None)
        if not zone:
            caller.msg("|xThere's no little box here.|n")
            return
        if getattr(caller.db, "in_box", None):
            caller.msg("|xYou're already in the box.|n")
            return
        nap = float(getattr(room.db, "box_nap_seconds", 360.0) or 360.0)
        now = time.time()
        caller.db.in_box         = zone
        caller.db.box_entered_at = now
        caller.db.box_release_at = now + nap
        caller.db.box_lid_locked = False
        caller.db.box_struggle   = 0.0
        name = caller.db.rp_name or caller.name
        room.msg_contents(f"|x{name} climbs into the little box and folds down small inside "
                          f"it. The padded walls close warm on every side.|n")
        caller.msg("|wYou're in the box. It will let you out on its own when the nap's up — "
                   "or try |xboxout|w to climb out yourself. |xboxstatus|w to check.|n")
        # Start the session if it isn't already running.
        from typeclasses.little_box import LittleBoxScript
        from evennia.utils import create
        if not LittleBoxScript.is_running(room):
            create.create_script(LittleBoxScript, obj=room, persistent=True, autostart=True)


class CmdBoxOut(Command):
    """
    Climb out of the little box.

    Usage:
        boxout

    If the lid isn't locked you just climb out. If it's locked, this works the latch —
    repeat it to wriggle free. The nap timer will also pop the lid on its own; this and
    |wboxstatus|n always show you how long that is and how close your wriggling is.
    """
    key   = "boxout"
    aliases = ["getout", "climbout"]
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room   = caller.location
        zone = getattr(room.db, "little_box_zone", None) if room else None
        if not getattr(caller.db, "in_box", None) or caller.db.in_box != zone:
            caller.msg("|xYou're not in the box.|n")
            # Stale flag cleanup if they wandered off and it lingered.
            if getattr(caller.db, "in_box", None):
                caller.db.in_box = None
            return
        from typeclasses.little_box import LittleBoxScript
        script = next((s for s in room.scripts.all()
                       if isinstance(s, LittleBoxScript)), None)
        now = time.time()
        # Not locked → free climb-out.
        if not getattr(caller.db, "box_lid_locked", False):
            if script:
                script._release(caller, room, reason="free")
            else:
                caller.db.in_box = None
                caller.msg("|wYou climb out of the box.|n")
            name = caller.db.rp_name or caller.name
            room.msg_contents(f"|x{name} climbs out of the little box.|n", exclude=[caller])
            return
        # Locked → the nap timer may already have earned it; else work the latch.
        if now >= float(getattr(caller.db, "box_release_at", 0.0) or 0.0):
            if script:
                script._release(caller, room, reason="timer")
            return
        struggle = float(getattr(caller.db, "box_struggle", 0.0) or 0.0) + 1.0
        caller.db.box_struggle = struggle
        from typeclasses.little_box import _BOX_STRUGGLE_OUT, _BOX_STRUGGLE_FAIL, _BOX_STRUGGLE_OUT_BEATS
        import random
        if struggle >= _BOX_STRUGGLE_OUT:
            if script:
                script._release(caller, room, reason="struggle")
            else:
                caller.db.in_box = None
                caller.db.box_lid_locked = False
                caller.msg("|w  " + random.choice(_BOX_STRUGGLE_OUT_BEATS) + "|n")
            name = caller.db.rp_name or caller.name
            room.msg_contents(f"|x{name} wriggles the latch open and climbs out of the box.|n",
                              exclude=[caller])
            return
        remain = max(0, int(float(caller.db.box_release_at) - now))
        caller.msg("|x  " + random.choice(_BOX_STRUGGLE_FAIL) + "|n")
        caller.msg(f"|x  (latch: {struggle:.0f}/{_BOX_STRUGGLE_OUT:.0f} — or the nap springs "
                   f"it on its own in ~{remain}s)|n")


class CmdBoxStatus(Command):
    """How little you've gotten in the box, and exactly how you get out."""
    key   = "boxstatus"
    aliases = ["boxcheck"]
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        if not getattr(caller.db, "in_box", None):
            caller.msg("|xYou're not in a little box.|n")
            return
        now = time.time()
        remain = max(0, int(float(getattr(caller.db, "box_release_at", now) or now) - now))
        locked = getattr(caller.db, "box_lid_locked", False)
        struggle = float(getattr(caller.db, "box_struggle", 0.0) or 0.0)
        lines = ["|M── IN THE BOX ──|n"]
        try:
            from world.regression import regression_stage
            reg = float(getattr(caller.db, "regression", 0.0) or 0.0)
            label, desc = regression_stage(reg)
            lines.append(f"|m  how little: |w{label}|n |x({desc})|n")
        except Exception:
            pass
        lines.append(f"|m  lid:       |w{'LOCKED' if locked else 'open — you can climb out anytime'}|n")
        from typeclasses.little_box import _BOX_STRUGGLE_OUT
        if locked:
            lines.append(f"|m  the nap springs the lid on its own in |w~{remain}s|n")
            lines.append(f"|m  or wriggle it yourself: |w{struggle:.0f}/{_BOX_STRUGGLE_OUT:.0f}|n "
                         f"|x(keep using |wboxout|x)|n")
        lines.append("|g  always: leave the room, log off, or the OOC reset/escape lets you "
                     "out and gives your grown self back instantly.|n")
        caller.msg("\n".join(lines))


ALL_BOX_CMDS = [CmdBoxIn, CmdBoxOut, CmdBoxStatus]
