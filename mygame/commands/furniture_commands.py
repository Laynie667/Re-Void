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
    Install (or convert) a fluid fridge here. Bottles minted by the fluid bank route to
    the fridge in the room they were produced in (then any fridge), so stock yours where
    you milk.

    Usage:
        installfridge [name]              — create a new fridge object
        installfridge convert <object>    — make an EXISTING object (e.g. your decorative
                                            fridge) a working fridge, keeping its prose,
                                            and pull every bottle in the room into it

    Use 'convert' when the room already describes a fridge — it gains the function without
    a duplicate object, and the room's prose/`look` keep referring to the right thing.
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
        args = self.args.strip()

        # ── convert mode: upgrade an existing object into a working fridge ──
        if args.lower().startswith("convert"):
            target_name = args[len("convert"):].strip()
            if not target_name:
                caller.msg("|xUsage: installfridge convert <object>|n")
                return
            target = caller.search(target_name)
            if not target:
                return
            if target.is_typeclass(FluidFridge, exact=False):
                caller.msg(f"|x{target.key} is already a working fridge.|n")
                return
            saved_desc = target.db.desc
            saved_key = target.key
            try:
                target.swap_typeclass("typeclasses.fluid_fridge.FluidFridge",
                                      clean_attributes=False)
            except Exception as e:
                caller.msg(f"|rCouldn't convert {saved_key}: {e}|n")
                return
            # preserve the original prose/name through the swap
            if saved_desc is not None:
                target.db.desc = saved_desc
            if saved_key:
                target.key = saved_key
            # pull every bottle in the room (other fridges, loose) + orphans into it
            moved = 0
            for o in list(room.contents):
                if o is target:
                    continue
                src = ([o] if o.is_typeclass(FluidBottle, exact=False) else
                       list(o.contents) if o.is_typeclass(FluidFridge, exact=False) else [])
                for b in src:
                    if b.is_typeclass(FluidBottle, exact=False):
                        b.location = target
                        moved += 1
            for b in [x for x in FluidBottle.objects.all() if x.location is None]:
                b.location = target
                moved += 1
            caller.msg(f"|g✦ |w{target.key}|g is now a working fridge — its description is "
                       f"untouched. Moved |w{moved}|g bottle(s) into it. Delete any leftover "
                       f"fridge with |w@del <name>|g.|n")
            return

        # ── create mode: a fresh fridge object ──
        # Warn if the room already describes/holds a fridge-like object.
        existing = [o for o in room.contents
                    if any(w in (o.key or "").lower() for w in ("fridge", "cooler", "case", "freezer"))
                    and not o.is_typeclass(FluidFridge, exact=False)]
        if existing:
            caller.msg(f"|yThere's already a '{existing[0].key}' here that isn't functional. "
                       f"To make IT the working fridge (keeping its description), use:|n\n"
                       f"  |winstallfridge convert {existing[0].key}|n")
            return
        name = args or "a refrigerator"
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
        arg = self.args.strip()
        # `installhorse perfect` — the full dream rig.
        if arg.lower() == "perfect":
            room.db.horse_zone = "saddle"
            room.db.horse_pace = "steady"
            room.db.horse_upgrades = ["vibrating", "restrained", "knot", "breeding", "little"]
            caller.msg(
                "|m✦ The perfect rocking horse is installed (zone '|wsaddle|m').|n\n"
                "|x  It works you harder the faster you ride, cuffs you in like tucking you "
                "in (|wrestrained|x), breeds and fills you (|wbreeding|x), knots to hold you "
                "through it (|wknot|x), and keeps you little and helpless the whole time "
                "(|wlittle|x — caretaker voice + baby-talk + drifting conditioning).|n\n"
                "|x  horsemount → horsestart → ride. The knot won't let you down until it's "
                "done with you. (escape always frees you, instantly.)|n")
            return
        zone = (arg or "saddle").lower().replace(" ", "_")
        room.db.horse_zone = zone
        room.db.horse_pace = "steady"
        if getattr(room.db, "horse_upgrades", None) is None:
            room.db.horse_upgrades = []     # clean: a plain ride, NOT a milker
        caller.msg(f"|g✦ Rocking horse installed (zone '|w{zone}|g', plain — no milking).|n\n"
                   f"|x  horsemount → horsestart → horsestop.  Add bits with "
                   f"|whorseupgrade add breeding|x (deposit + inflate), |wlittle|x (helpless "
                   f"headspace), |winflation|x, |wrestrained|x, |wvibrating|x, |wknot|x.\n"
                   f"  Or the whole dream rig at once: |winstallhorse perfect|x.|n")


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
