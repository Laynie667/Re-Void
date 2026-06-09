"""
commands/rocking_horse_commands.py

Commands for the rocking horse furniture.

  horsemount [facing]      — mount the horse (facing: forward/backward)
  horsedismount            — dismount
  horsestart               — start the session (operator/staff)
  horsestop                — stop the session
  horsepace <pace>         — set pace: slow/steady/fast/intense
  horseupgrade add <flag>  — add an upgrade flag to the horse
  horseupgrade remove <flag> — remove an upgrade flag
  horsestatus              — show current state and upgrades
"""

from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand


class CmdHorseMount(Command):
    """
    Mount the rocking horse in this room.

    Usage:
      horsemount [forward/backward]

    Default is forward. Backward changes the angle and message pool.
    """
    key   = "horsemount"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            return

        zone_name = getattr(room.db, "horse_zone", None)
        if not zone_name:
            caller.msg("|xThere is no rocking horse installed in this room.|n")
            return

        facing = self.args.strip().lower() or "forward"
        if facing not in ("forward", "backward"):
            facing = "forward"

        caller.db.seated_zone  = zone_name
        caller.db.horse_facing = facing
        caller_name = caller.db.rp_name or caller.name
        upgrades = list(getattr(room.db, "horse_upgrades", None) or [])

        # Mount messages
        if facing == "backward":
            msg = f"|x{caller_name} mounts the horse facing backward — hands behind them, seated and committed.|n"
        else:
            msg = f"|x{caller_name} mounts the horse — hands on the handles, settled into the seat.|n"
        room.msg_contents(msg)

        # Penetration on mount — which hole(s) the shaft finds. (Restraint is NOT
        # clamped on here any more — it engages at an arousal threshold during the
        # ride, see RockingHorseScript._check_restraint.)
        from world.rocking_horse_loader import pick_horse_msg
        from typeclasses.rocking_horse_script import rider_holes, holes_kind
        holes = [h for h in rider_holes(caller, facing, upgrades) if h]
        if holes:
            pool = {"both": "mount_both", "ass": "mount_ass", "cunt": "mount_cunt"}[holes_kind(holes)]
            entry = pick_horse_msg("upgrade", pool)
            if entry:
                room.msg_contents("|r" + entry.replace("{rider}", caller_name) + "|n")
        # Fresh ride — reset the breeding refractory clock.
        caller.db.horse_last_breed_at = 0.0

        # Milking upgrade — start attachment
        if "milking" in upgrades:
            from world.rocking_horse_loader import pick_horse_msg
            milk_msg = pick_horse_msg("upgrade", "milking_start")
            if milk_msg:
                room.msg_contents(milk_msg.replace("{rider}", caller_name))

        # Start the cycle on mount — the horse begins rocking as soon as you're seated,
        # instead of sitting dead until someone calls horsestart. (Previously the mount
        # flavour implied motion the session machinery hadn't actually started.)
        from typeclasses.rocking_horse_script import RockingHorseScript
        from evennia.utils import create
        if not RockingHorseScript.is_running(room):
            script = create.create_script(
                RockingHorseScript, obj=room, persistent=True, autostart=True)
            pace = getattr(room.db, "horse_pace", "steady") or "steady"
            from world.rocking_horse_loader import pick_horse_msg
            start_msg = pick_horse_msg(pace, "start")
            if start_msg:
                room.msg_contents(start_msg.replace("{rider}", caller_name))
            caller.msg(f"|wYou are on the horse, facing {facing} — and it begins to rock "
                       f"({pace}). |xhorsepace|w to change speed, |xhorsestop|w to still it.|n")
        else:
            caller.msg(f"|wYou are on the horse, facing {facing}. It's already rocking.|n")


class CmdHorseDismount(Command):
    """Dismount the rocking horse."""
    key   = "horsedismount"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room   = caller.location

        zone_name = getattr(room.db, "horse_zone", None) if room else None
        if not caller.db.seated_zone or caller.db.seated_zone != zone_name:
            caller.msg("|xYou are not on the horse.|n")
            return

        # Knot check
        if getattr(caller.db, "horse_knotted", False):
            expires = caller.db.horse_knot_expires_at or 0
            import time
            if time.time() < expires:
                remaining = int(expires - time.time())
                caller.msg(f"|xThe knot holds you to the seat. ({remaining}s remaining)|n")
                return
            caller.db.horse_knotted = False

        caller.db.seated_zone     = None
        caller.db.restrained_zone = None
        caller.db.horse_facing    = None
        caller.db.horse_last_breed_at = 0.0

        # 'little' upgrade teardown — remove only the baby-talk the horse itself added,
        # and only if a facility binding isn't also relying on it (don't clobber that).
        if getattr(caller.db, "horse_baby_talk", False):
            if not getattr(caller.db, "facility_active", False):
                active = list(getattr(caller.db, "active_speech_filters", None) or [])
                if "baby_talk" in active:
                    active.remove("baby_talk")
                    caller.db.active_speech_filters = active
            caller.db.horse_baby_talk = False
            caller.msg("|xYour words come back to you as you climb down — bigger again, "
                       "steadier, a little reluctant to be.|n")
        caller_name = caller.db.rp_name or caller.name
        room.msg_contents(f"|x{caller_name} dismounts the horse.|n")
        caller.msg("|wYou dismount the horse.|n")


class CmdHorseStart(Command):
    """
    Start the rocking horse session.

    Usage:
      horsestart
    """
    key   = "horsestart"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        room = self.caller.location
        if not room:
            return
        from typeclasses.rocking_horse_script import RockingHorseScript
        from evennia.utils import create

        if RockingHorseScript.is_running(room):
            self.caller.msg("|xThe horse is already running.|n")
            return

        pace   = getattr(room.db, "horse_pace", "steady") or "steady"
        script = create.create_script(
            RockingHorseScript, obj=room, persistent=True, autostart=True
        )

        from world.rocking_horse_loader import pick_horse_msg
        zone_name = getattr(room.db, "horse_zone", "horse")
        # Find any current rider
        from typeclasses.characters import Character
        for char in room.contents:
            if isinstance(char, Character) and getattr(char.db, "seated_zone", None) == zone_name:
                rider_name = char.db.rp_name or char.name
                msg = pick_horse_msg(pace, "start") or f"The horse begins — {rider_name} settles into the rhythm."
                room.msg_contents(msg.replace("{rider}", rider_name))
                break
        self.caller.msg(f"|wRocking horse started at {pace} pace.|n")
        # Fire an immediate first rock so it doesn't sit dead until the next interval.
        try:
            for char in room.contents:
                if isinstance(char, Character) and getattr(char.db, "seated_zone", None) == zone_name:
                    script.apply_rider_tick(char, room)
        except Exception:
            pass


class CmdHorseStop(Command):
    """Stop the rocking horse session."""
    key   = "horsestop"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        room = self.caller.location
        if not room:
            return
        from typeclasses.rocking_horse_script import RockingHorseScript
        if not RockingHorseScript.is_running(room):
            self.caller.msg("|xNo horse session running here.|n")
            return

        # Emit a stop message once for any current rider.
        try:
            pace = getattr(room.db, "horse_pace", "steady") or "steady"
            zone_name = getattr(room.db, "horse_zone", "horse")
            from typeclasses.characters import Character
            from world.rocking_horse_loader import pick_horse_msg
            for char in room.contents:
                if isinstance(char, Character) and getattr(char.db, "seated_zone", None) == zone_name:
                    rider_name = char.db.rp_name or char.name
                    stop_msg = pick_horse_msg(pace, "stop") or f"The horse stills under {rider_name}."
                    room.msg_contents(stop_msg.replace("{rider}", rider_name))
                    break
        except Exception:
            pass

        RockingHorseScript.stop_all(room)
        self.caller.msg("|wHorse stopped.|n")


class CmdHorsePace(Command):
    """
    Set the rocking horse pace.

    Usage:
      horsepace <slow/steady/fast/intense>
    """
    key   = "horsepace"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        pace = self.args.strip().lower()
        if pace not in ("slow", "steady", "fast", "intense"):
            self.caller.msg("|xPace must be: slow / steady / fast / intense|n")
            return
        room = self.caller.location
        if not room:
            return
        room.db.horse_pace = pace

        # Update running script interval
        from typeclasses.rocking_horse_script import RockingHorseScript
        from world.rocking_horse_loader import get_horse_config
        for s in room.scripts.all():
            if isinstance(s, RockingHorseScript):
                config = get_horse_config(pace)
                s.interval = config.get("interval_seconds", 45)
                break

        self.caller.msg(f"|wHorse pace set to {pace}.|n")
        room.msg_contents(
            f"|xThe rocking horse shifts to {pace} pace.|n",
            exclude=[self.caller],
        )


class CmdHorseUpgrade(MuxCommand):
    """
    Manage rocking horse upgrades.

    Usage:
      horseupgrade add <motorized/vibrating/milking/restrained/knot/inflation/breeding/double/little>
        (breeding = the shaft cums into you and the belly fills — deposit + inflate)
        (double   = a second shaft; if you have both holes, it takes cunt AND ass at once)
      horseupgrade remove <flag>
      horseupgrade list
    """
    key     = "horseupgrade"
    locks   = "cmd:all()"
    help_category = "Furniture"
    switch_options = ("add", "remove", "list")

    _VALID = {"motorized", "vibrating", "milking", "restrained", "knot",
              "inflation", "breeding", "double", "little"}

    def func(self):
        room = self.caller.location
        if not room:
            return
        upgrades = list(getattr(room.db, "horse_upgrades", None) or [])

        if "add" in self.switches:
            flag = self.args.strip().lower()
            if flag not in self._VALID:
                self.caller.msg(f"|xUnknown upgrade '{flag}'. Options: {', '.join(sorted(self._VALID))}|n")
                return
            if flag not in upgrades:
                upgrades.append(flag)
                room.db.horse_upgrades = upgrades
            self.caller.msg(f"|w'{flag}' upgrade added to the horse.|n")

        elif "remove" in self.switches:
            flag = self.args.strip().lower()
            if flag in upgrades:
                upgrades.remove(flag)
                room.db.horse_upgrades = upgrades
            self.caller.msg(f"|w'{flag}' upgrade removed.|n")

        else:
            if not upgrades:
                self.caller.msg("|xNo upgrades installed on the horse.|n")
                return
            self.caller.msg("|wHorse upgrades:|n " + ", ".join(upgrades))


class CmdHorseStatus(Command):
    """Show the current state of the rocking horse."""
    key   = "horsestatus"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        room = self.caller.location
        if not room:
            return
        zone    = getattr(room.db, "horse_zone", "not set")
        pace    = getattr(room.db, "horse_pace", "steady")
        upgrades = list(getattr(room.db, "horse_upgrades", None) or [])
        from typeclasses.rocking_horse_script import RockingHorseScript
        running = any(isinstance(s, RockingHorseScript) for s in room.scripts.all())
        from typeclasses.characters import Character
        riders = [
            obj.db.rp_name or obj.name
            for obj in room.contents
            if isinstance(obj, Character) and getattr(obj.db, "seated_zone", None) == zone
        ]
        self.caller.msg(
            f"|wRocking Horse|n\n"
            f"  Zone:     {zone}\n"
            f"  Pace:     {pace}\n"
            f"  Running:  {'yes' if running else 'no'}\n"
            f"  Upgrades: {', '.join(upgrades) or 'none'}\n"
            f"  Riders:   {', '.join(riders) or 'none'}"
        )


class CmdRock(Command):
    """
    Rock the horse yourself — set your own rhythm and feel it answer.

    Usage:
        rock

    You don't have to wait for it. Each rock works you the way a tick does — and the
    harder/faster you go, the more it gives back. (The horse also rocks on its own once
    started; this is you driving.)
    """
    key   = "rock"
    aliases = ["ride", "buck"]
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room = caller.location
        zone_name = getattr(room.db, "horse_zone", None) if room else None
        if not zone_name or getattr(caller.db, "seated_zone", None) != zone_name:
            caller.msg("|xYou're not on the horse. (|whorsemount|x first.)|n")
            return
        from typeclasses.rocking_horse_script import RockingHorseScript
        from evennia.utils import create
        script = next((s for s in room.scripts.all()
                       if isinstance(s, RockingHorseScript)), None)
        if not script:
            # rocking it yourself can wake a stopped horse
            script = create.create_script(RockingHorseScript, obj=room,
                                          persistent=True, autostart=True)
        # rocking yourself nudges arousal a touch extra — the harder you ride.
        try:
            from typeclasses.arousal_script import add_arousal
            add_arousal(caller, 3.0)
        except Exception:
            pass
        script.apply_rider_tick(caller, room)


ALL_HORSE_CMDS = [
    CmdHorseMount,
    CmdHorseDismount,
    CmdHorseStart,
    CmdHorseStop,
    CmdHorsePace,
    CmdHorseUpgrade,
    CmdHorseStatus,
    CmdRock,
]
