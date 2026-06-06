"""
commands/furniture_commands.py

Commands for animated furniture in Re:Void.

  edgestart [zone]     — start the edge machine in the current room
  edgestop             — stop the edge machine and release occupants
  stanchionstart [zone]— start the milking stanchion
  stanchionrelease     — release the current stanchion occupant
  deprive <target>     — place a character in the sensory deprivation chamber
  deprive/pulse <msg>  — send a message inward to the chamber
  deprive/release      — release the chamber occupant

All require the room to have the matching script installed.
Operator must be in the room; staff bypass zone checks.
"""

from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand


# ---------------------------------------------------------------------------
# Edge machine
# ---------------------------------------------------------------------------

class CmdEdgeStart(Command):
    """
    Start the edge machine in the current room.

    Usage:
      edgestart [zone]

    Sets arousal_denial on anyone seated in the edge machine zone.
    """
    key   = "edgestart"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            return

        zone_arg = self.args.strip()
        if zone_arg:
            room.db.edge_machine_zone = zone_arg.lower().replace(" ", "_")

        from typeclasses.furniture_scripts import EdgeMachineScript
        from evennia.utils import create

        if EdgeMachineScript.is_running(room):
            caller.msg("|xEdge machine is already running.|n")
            return

        create.create_script(EdgeMachineScript, obj=room, persistent=True, autostart=True)
        zone = getattr(room.db, "edge_machine_zone", "unset")
        caller.msg(f"|wEdge machine started on zone '{zone}'.|n")
        room.msg_contents(
            "|xThe machine hums to life. The edge is being set.|n",
            exclude=[caller],
        )


class CmdEdgeStop(Command):
    """Stop the edge machine and release all occupants."""
    key   = "edgestop"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        room = self.caller.location
        if not room:
            return
        from typeclasses.furniture_scripts import EdgeMachineScript
        if EdgeMachineScript.stop_all(room):
            self.caller.msg("|wEdge machine stopped. Occupants released.|n")
        else:
            self.caller.msg("|xNo edge machine running here.|n")


# ---------------------------------------------------------------------------
# Milking stanchion
# ---------------------------------------------------------------------------

class CmdStanchionStart(Command):
    """
    Start the milking stanchion in the current room.

    Usage:
      stanchionstart [zone]
    """
    key   = "stanchionstart"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            return

        zone_arg = self.args.strip()
        if zone_arg:
            room.db.stanchion_zone = zone_arg.lower().replace(" ", "_")

        from typeclasses.furniture_scripts import MilkingStanchionScript
        from evennia.utils import create

        if MilkingStanchionScript.is_running(room):
            caller.msg("|xMilking stanchion is already running.|n")
            return

        create.create_script(MilkingStanchionScript, obj=room, persistent=True, autostart=True)
        zone = getattr(room.db, "stanchion_zone", "unset")
        caller.msg(f"|wMilking stanchion started on zone '{zone}'.|n")
        room.msg_contents("|xThe stanchion engages, waiting for an occupant.|n", exclude=[caller])


class CmdStanchionRelease(Command):
    """Release the current stanchion occupant."""
    key   = "stanchionrelease"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        room = self.caller.location
        if not room:
            return
        from typeclasses.furniture_scripts import MilkingStanchionScript
        from typeclasses.characters import Character
        sessions = MilkingStanchionScript.find(room)
        if not sessions:
            self.caller.msg("|xNo active milking stanchion here.|n")
            return
        s = sessions[0]
        for char in room.contents:
            if isinstance(char, Character) and getattr(char.db, "stanchion_locked", False):
                if hasattr(s, "release_occupant"):
                    s.release_occupant(char)
                else:
                    char.db.stanchion_locked = False
        self.caller.msg("|wStanchion released.|n")


# ---------------------------------------------------------------------------
# Deprivation chamber
# ---------------------------------------------------------------------------

class CmdDeprive(MuxCommand):
    """
    Manage the sensory deprivation chamber.

    Usage:
      deprive <target>       — place target in the chamber (they must be here)
      deprive/pulse <msg>    — send a message inward
      deprive/release        — release the chamber occupant
    """
    key     = "deprive"
    locks   = "cmd:all()"
    help_category = "Furniture"
    switch_options = ("pulse", "release")

    def func(self):
        caller = self.caller
        room   = caller.location
        args   = self.args.strip()

        if "pulse" in self.switches:
            self._do_pulse(caller, room, args)
            return
        if "release" in self.switches:
            self._do_release(caller, room)
            return
        self._do_deprive(caller, room, args)

    def _do_deprive(self, caller, room, target_name):
        from typeclasses.characters import Character
        if not target_name:
            caller.msg("|xUsage: deprive <target>|n")
            return
        target = caller.search(target_name, location=room)
        if not target or not isinstance(target, Character):
            return
        target.db.deprivation_locked = True
        target.db.active_speech_filters = list(
            set(target.db.active_speech_filters or []) | {"cant_speak"}
        )
        cname = caller.db.rp_name or caller.name
        tname = target.db.rp_name or target.name
        target.msg("|xThe deprivation begins. Everything outside is gone.|n")
        caller.msg(f"|w{tname} is now in deprivation.|n")
        room.msg_contents(f"|x{tname} goes silent.|n", exclude=[caller, target])

    def _do_pulse(self, caller, room, message):
        from typeclasses.characters import Character
        if not message:
            caller.msg("|xUsage: deprive/pulse <message>|n")
            return
        cname = caller.db.rp_name or caller.name
        sent = 0
        for char in room.contents:
            if isinstance(char, Character) and getattr(char.db, "deprivation_locked", False):
                char.msg(f"|xA voice reaches in from outside — close and total: {message}|n")
                sent += 1
        if sent:
            caller.msg(f"|w[Pulse sent to {sent} occupant(s)]|n")
        else:
            caller.msg("|xNo one is currently in deprivation here.|n")

    def _do_release(self, caller, room):
        from typeclasses.characters import Character
        released = 0
        for char in room.contents:
            if isinstance(char, Character) and getattr(char.db, "deprivation_locked", False):
                char.db.deprivation_locked = False
                filters = list(char.db.active_speech_filters or [])
                if "cant_speak" in filters:
                    filters.remove("cant_speak")
                char.db.active_speech_filters = filters
                char.msg("|xThe deprivation ends. The world returns.|n")
                released += 1
        if released:
            caller.msg(f"|w{released} occupant(s) released from deprivation.|n")
        else:
            caller.msg("|xNo one currently in deprivation here.|n")


# ---------------------------------------------------------------------------
# Furniture discovery
# ---------------------------------------------------------------------------

# (label, presence_attr, zone_attr|None, session_class_path|None, [verbs])
_FURNITURE_REGISTRY = [
    ("Rocking Horse", "horse_zone", "horse_zone",
     "typeclasses.rocking_horse_script.RockingHorseScript",
     ["horsemount [forward|backward] / horsedismount",
      "horsestart / horsestop / horsepace <slow|steady|fast|intense>",
      "horseupgrade add|remove <flag> / horsestatus"]),
    ("Edge Machine", "edge_machine_zone", "edge_machine_zone",
     "typeclasses.furniture_scripts.EdgeMachineScript",
     ["edgestart [zone] / edgestop",
      "held at 99 — say the release word to finish"]),
    ("Milking Stanchion", "stanchion_zone", "stanchion_zone",
     "typeclasses.furniture_scripts.MilkingStanchionScript",
     ["stanchionstart [zone] / stanchionrelease"]),
    ("Display Pedestal", "pedestal_zone", "pedestal_zone",
     "typeclasses.furniture_scripts.DisplayPedestalScript",
     ["step onto the pedestal zone to be put on display"]),
    ("Milking Machine", "machine_zone", "machine_zone", None,
     ["milk <target> [zone]"]),
    ("Jacuzzi", "has_jacuzzi", None, None,
     ["jacuzzi (see jacuzzi help for hosting/zones)"]),
    ("Shower", "has_shower", None, None,
     ["shower — step in and use it"]),
]


class CmdShowFurniture(Command):
    """
    List the interactive furniture installed in this room.

    Usage:
      showfurniture

    Shows each installed device, the zone it uses, whether a session is
    currently running, and the commands to operate it. Furniture is attached
    to room zones; you interact with it by occupying the matching zone.
    """
    key     = "showfurniture"
    aliases = ["furniture"]
    locks   = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        room = self.caller.location
        if not room:
            return

        from evennia.utils.utils import class_from_module

        lines = []
        for label, present_attr, zone_attr, cls_path, verbs in _FURNITURE_REGISTRY:
            if not getattr(room.db, present_attr, None):
                continue

            head = f"|w{label}|n"
            zone = getattr(room.db, zone_attr, None) if zone_attr else None
            if zone:
                head += f"  |c(zone: {zone})|n"
            if cls_path:
                try:
                    cls = class_from_module(cls_path)
                    head += "  |g[running]|n" if cls.is_running(room) else "  |x[idle]|n"
                except Exception:
                    pass
            lines.append(head)
            for v in verbs:
                lines.append(f"    {v}")

        if not lines:
            self.caller.msg("|xThere's no interactive furniture installed here.|n")
            return
        self.caller.msg("|wInstalled furniture here:|n\n" + "\n".join(lines))


def _can_furnish(caller, room):
    """May this character install furniture here? Staff anywhere; players in their own
    housing (the tent/home they own, or any room they have control/edit access to)."""
    if caller.is_superuser or caller.check_permstring("Builder"):
        return True
    if getattr(caller.db, "housing_home_id", None) == getattr(room, "id", None):
        return True
    try:
        return room.access(caller, "control") or room.access(caller, "edit")
    except Exception:
        return False


class CmdInstallFridge(Command):
    """
    Install a fluid fridge here. Bottles minted by the fluid bank route to the fridge
    in the room they were produced in (then any fridge), so stock yours where you milk.

    Usage:
        installfridge [name]
    """
    key = "installfridge"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("|xYou're nowhere.|n")
            return
        if not _can_furnish(caller, room):
            caller.msg("|xYou don't have build rights here.|n")
            return
        from typeclasses.fluid_fridge import FluidFridge
        from typeclasses.fluid_bottle import FluidBottle
        from evennia.utils import create
        name = self.args.strip() or "a refrigerator"
        fridge = create.create_object(FluidFridge, key=name, location=room)
        lost = [b for b in FluidBottle.objects.all() if b.location is None]
        for b in lost:
            b.location = fridge
        extra = f" Recovered |w{len(lost)}|g orphaned bottle(s) into it." if lost else ""
        caller.msg(f"|g✦ Installed |w{name}|g (#{fridge.id}). Bottles will stock here.{extra}|n")


class CmdInstallHorse(Command):
    """
    Install a rocking horse here — a dildo ride that works you harder the faster it
    goes. Installs PLAIN (no milking, no breeding); add behaviours with `horseupgrade`.

    Usage:
        installhorse [zone-label]

    Then: horsemount → horsestart → horsepace <slow|steady|fast|intense> → horsestop.
    Upgrades: horseupgrade add <vibrating|restrained|knot|inflation|breeding|milking>.
    """
    key = "installhorse"
    locks = "cmd:all()"
    help_category = "Furniture"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("|xYou're nowhere.|n")
            return
        if not _can_furnish(caller, room):
            caller.msg("|xYou don't have build rights here.|n")
            return
        if getattr(room.db, "horse_zone", None):
            caller.msg("|xThere's already a rocking horse here (clear it with "
                       "|w@set here/horse_zone =|x).|n")
            return
        zone = (self.args.strip() or "saddle").lower().replace(" ", "_")
        room.db.horse_zone = zone
        room.db.horse_pace = "steady"
        if getattr(room.db, "horse_upgrades", None) is None:
            room.db.horse_upgrades = []     # clean: a plain ride, NOT a milker
        caller.msg(f"|g✦ Rocking horse installed (zone '|w{zone}|g', plain — no milking).|n\n"
                   f"|x  horsemount → horsestart → horsestop.  Add bits with "
                   f"|whorseupgrade add breeding|x (deposit + inflate), |winflation|x, "
                   f"|wrestrained|x, |wvibrating|x, |wknot|x.|n")


ALL_FURNITURE_CMDS = [
    CmdInstallFridge,
    CmdInstallHorse,
    CmdEdgeStart,
    CmdEdgeStop,
    CmdStanchionStart,
    CmdStanchionRelease,
    CmdDeprive,
    CmdShowFurniture,
]
