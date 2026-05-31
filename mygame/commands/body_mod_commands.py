"""
commands/body_mod_commands.py

Body modification and fluid production commands.

CmdInstall      install <item> on <zone>
                install <item> on <target>'s <zone>

CmdUninstall    uninstall <item> from <zone>
                uninstall <item> from <target>'s <zone>

CmdSetFluid     setfluid <item>
                setfluid/type <item> = <fluid_type>
                setfluid/flavor <item> = <flavor text>

CmdApplyLotion  lotion [<target>'s] <zone>
                (lotion item must be in your inventory)

CmdInject       inject [<target>] [<zone>]
                inject/self [<zone>]
                (syringe must be in your inventory)

CmdMilk         milk <target> [zone]
                milk/speed slow|steady|fast|intense
                milk/stop
                milk/status

ALL_BODY_MOD_CMDS — exported list for default_cmdsets.py
"""

from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import search


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_char_in_room(caller, name):
    """Find a character in the room by partial name. Returns obj or None."""
    candidates = [
        obj for obj in caller.location.contents
        if hasattr(obj, "db") and obj != caller
        and (obj.db.rp_name or obj.name).lower().startswith(name.lower())
    ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        # Return exact match if available
        for c in candidates:
            if (c.db.rp_name or c.name).lower() == name.lower():
                return c
        return None
    # Try self
    if (caller.db.rp_name or caller.name).lower().startswith(name.lower()):
        return caller
    return None


def _find_item_in_inventory(caller, name, typeclass_path):
    """Find an installed or carried item of a given typeclass in caller's inventory."""
    for obj in caller.contents:
        if obj.__class__.__module__ + "." + obj.__class__.__name__ == typeclass_path:
            if name.lower() in (obj.db.rp_name or obj.key or "").lower() or \
               name.lower() in obj.key.lower():
                return obj
    return None


def _find_body_mod_in_inventory(caller):
    """Return all BodyModItem subclasses in caller's inventory."""
    from typeclasses.body_mod_item import BodyModItem
    return [obj for obj in caller.contents if isinstance(obj, BodyModItem)]


def _find_production_in_inventory(caller):
    """Return all ProductionItem subclasses in caller's inventory."""
    from typeclasses.production_item import ProductionItem
    return [obj for obj in caller.contents if isinstance(obj, ProductionItem)]


# ---------------------------------------------------------------------------
# CmdInstall
# ---------------------------------------------------------------------------

class CmdInstall(Command):
    """
    Install a body mod or production item onto a character zone.

    Usage:
      install <item> on <zone>                — install on your own zone
      install <item> on <target>'s <zone>     — install on another's zone
      install <item> on <target> <zone>       — alternate syntax

    The item must be in your inventory. The zone must exist on the target.
    Only one body_mod item and one production item may be installed per zone.

    Examples:
      install breast item on chest
      install milk production item on Helena's chest
    """

    key     = "install"
    locks   = "cmd:all()"
    help_category = "Body Mod"

    def func(self):
        caller = self.caller
        raw    = self.args.strip()

        if not raw or " on " not in raw.lower():
            caller.msg("|xUsage: install <item> on [<target>'s] <zone>|n")
            return

        split     = raw.lower().index(" on ")
        item_name = raw[:split].strip()
        rest      = raw[split + 4:].strip()

        # Parse target / zone from rest
        # Formats: "my chest", "Helena's chest", "Helena chest", "chest"
        target     = caller
        zone_name  = rest

        if "'s " in rest:
            tname, zone_name = rest.split("'s ", 1)
            found = _find_char_in_room(caller, tname.strip())
            if not found:
                caller.msg(f"|xCan't find '{tname}' in the room.|n")
                return
            target    = found
            zone_name = zone_name.strip()
        elif rest.startswith("my "):
            zone_name = rest[3:].strip()
        else:
            # Try to split as "<target> <zone>" — first word is target if found
            parts = rest.split(None, 1)
            if len(parts) == 2:
                maybe_target = _find_char_in_room(caller, parts[0])
                if maybe_target:
                    target    = maybe_target
                    zone_name = parts[1]

        zone_name = zone_name.replace(" ", "_").lower()

        # Find the item in inventory
        from typeclasses.body_mod_item import BodyModItem
        from typeclasses.production_item import ProductionItem

        item = None
        for obj in caller.contents:
            if item_name.lower() in obj.key.lower():
                if isinstance(obj, (BodyModItem, ProductionItem)):
                    item = obj
                    break

        if not item:
            caller.msg(
                f"|xYou don't have a body mod or production item matching '{item_name}'.|n"
            )
            return

        ok, msg = item.install(target, zone_name)
        if ok:
            target_name = target.db.rp_name or target.name
            if target == caller:
                caller.location.msg_contents(
                    f"{caller.db.rp_name or caller.name} installs {item.key} "
                    f"on their {zone_name.replace('_', ' ')}.",
                    exclude=[caller]
                )
                caller.msg(
                    f"You install {item.key} on your {zone_name.replace('_', ' ')}."
                )
            else:
                caller.location.msg_contents(
                    f"{caller.db.rp_name or caller.name} installs {item.key} "
                    f"on {target_name}'s {zone_name.replace('_', ' ')}.",
                    exclude=[caller, target]
                )
                caller.msg(
                    f"You install {item.key} on {target_name}'s "
                    f"{zone_name.replace('_', ' ')}."
                )
                target.msg(
                    f"{caller.db.rp_name or caller.name} installs {item.key} "
                    f"on your {zone_name.replace('_', ' ')}."
                )
        else:
            caller.msg(f"|x{msg}|n")


# ---------------------------------------------------------------------------
# CmdUninstall
# ---------------------------------------------------------------------------

class CmdUninstall(Command):
    """
    Remove an installed body mod or production item from a character zone.

    Usage:
      uninstall <item> from <zone>
      uninstall <item> from <target>'s <zone>

    The item can be referenced by name. You may uninstall from yourself
    or, with consent, from another character in the room.

    Examples:
      uninstall breast item from chest
      uninstall milk production item from Helena's chest
    """

    key     = "uninstall"
    locks   = "cmd:all()"
    help_category = "Body Mod"

    def func(self):
        caller = self.caller
        raw    = self.args.strip()

        if not raw or " from " not in raw.lower():
            caller.msg("|xUsage: uninstall <item> from [<target>'s] <zone>|n")
            return

        split     = raw.lower().index(" from ")
        item_name = raw[:split].strip()
        rest      = raw[split + 6:].strip()

        target    = caller
        zone_name = rest

        if "'s " in rest:
            tname, zone_name = rest.split("'s ", 1)
            found = _find_char_in_room(caller, tname.strip())
            if not found:
                caller.msg(f"|xCan't find '{tname}' in the room.|n")
                return
            target    = found
            zone_name = zone_name.strip()

        zone_name = zone_name.replace(" ", "_").lower()

        # Find installed item on the zone
        from typeclasses.body_mod_item import BodyModItem
        from typeclasses.production_item import ProductionItem

        item = None
        zones = getattr(target.db, "zones", None) or {}
        zone  = zones.get(zone_name, {})
        mechanics = zone.get("mechanics", {}) or {}

        for mkey in ("body_mod", "production"):
            entry = mechanics.get(mkey)
            if entry and item_name.lower() in entry.get("item_name", "").lower():
                from evennia import search_object
                results = search_object(entry.get("item_dbref", ""), exact=True)
                if results:
                    item = results[0]
                    break

        if not item:
            caller.msg(
                f"|xCouldn't find a matching installed item on "
                f"{target.db.rp_name or target.name}'s {zone_name}.|n"
            )
            return

        ok, msg = item.uninstall()
        if ok:
            zone_disp   = zone_name.replace("_", " ")
            target_name = target.db.rp_name or target.name
            if target == caller:
                caller.msg(f"You remove {item.key} from your {zone_disp}.")
            else:
                caller.msg(
                    f"You remove {item.key} from {target_name}'s {zone_disp}."
                )
                target.msg(
                    f"{caller.db.rp_name or caller.name} removes {item.key} "
                    f"from your {zone_disp}."
                )
        else:
            caller.msg(f"|x{msg}|n")


# ---------------------------------------------------------------------------
# CmdSetFluid
# ---------------------------------------------------------------------------

class CmdSetFluid(MuxCommand):
    """
    Set the fluid type or flavor text on a production item.

    Usage:
      setfluid/type <item> = <fluid_type>
        Sets the fluid type (e.g. milk, semen, urine, or any custom string).

      setfluid/flavor <item> = <flavor text>
        Sets the flavor description for drink messages.

      setfluid/flavor <item> =
        Clears the flavor (no flavor line in drink messages).

      setfluid <item>
        Shows current type and flavor for the item.

    The item must be in your inventory and must be a production item.

    Examples:
      setfluid/type milk production item = honey
      setfluid/flavor milk production item = sweet and faintly golden
    """

    key     = "setfluid"
    locks   = "cmd:all()"
    help_category = "Body Mod"
    switch_options = ("type", "flavor")

    def func(self):
        caller   = self.caller
        switches = self.switches
        args     = self.args.strip()

        from typeclasses.production_item import ProductionItem

        # No switches — show current state
        if not switches:
            # Find item by name
            items = [
                obj for obj in caller.contents
                if isinstance(obj, ProductionItem)
                and (not args or args.lower() in obj.key.lower())
            ]
            if not items:
                caller.msg(
                    "|xNo production items found" +
                    (f" matching '{args}'" if args else "") + ".|n"
                )
                return
            for item in items:
                caller.msg(
                    f"|w{item.key}|n\n"
                    f"  Fluid type:   {item.db.fluid_type or 'unset'}\n"
                    f"  Flavor:       {item.db.fluid_flavor or '(none)'}\n"
                    f"  Volume:       {item.volume_display()}"
                )
            return

        # Parse "item = value" or just "item"
        if "=" in args:
            item_name, _, value = args.partition("=")
            item_name = item_name.strip()
            value     = value.strip()
        else:
            item_name = args.strip()
            value     = ""

        item = None
        for obj in caller.contents:
            if isinstance(obj, ProductionItem) and item_name.lower() in obj.key.lower():
                item = obj
                break

        if not item:
            caller.msg(
                f"|xNo production item matching '{item_name}' in your inventory.|n"
            )
            return

        if "type" in switches:
            if not value:
                caller.msg("|xUsage: setfluid/type <item> = <fluid_type>|n")
                return
            old = item.db.fluid_type or "unset"
            item.db.fluid_type = value.lower()
            item._refresh_mechanics_entry()
            caller.msg(
                f"Fluid type for |w{item.key}|n changed: {old} → {item.db.fluid_type}"
            )

        elif "flavor" in switches:
            old = item.db.fluid_flavor or "(none)"
            item.db.fluid_flavor = value if value else None
            item._refresh_mechanics_entry()
            new = item.db.fluid_flavor or "(cleared)"
            caller.msg(
                f"Flavor for |w{item.key}|n: {old} → {new}"
            )


# ---------------------------------------------------------------------------
# CmdApplyLotion
# ---------------------------------------------------------------------------

class CmdApplyLotion(Command):
    """
    Apply lotion to a zone to permanently increase its installed body mod size.

    Usage:
      lotion <zone>                — apply to your own zone
      lotion <target>'s <zone>    — apply to another character's zone

    You must have a lotion item in your inventory. The target zone must have
    a body mod item installed on it — lotion has no effect on bare zones.

    Examples:
      lotion chest
      lotion Helena's chest
    """

    key     = "lotion"
    locks   = "cmd:all()"
    help_category = "Body Mod"

    def func(self):
        caller = self.caller
        args   = self.args.strip()

        if not args:
            caller.msg("|xUsage: lotion [<target>'s] <zone>|n")
            return

        # Find lotion in inventory
        from typeclasses.lotion_item import LotionItem
        lotion_items = [obj for obj in caller.contents if isinstance(obj, LotionItem)]
        if not lotion_items:
            caller.msg("|xYou don't have any lotion.|n")
            return
        lotion = lotion_items[0]   # use first available

        # Parse target / zone
        target    = caller
        zone_name = args

        if "'s " in args:
            tname, zone_name = args.split("'s ", 1)
            found = _find_char_in_room(caller, tname.strip())
            if not found:
                caller.msg(f"|xCan't find '{tname}' in the room.|n")
                return
            target    = found
            zone_name = zone_name.strip()

        zone_name = zone_name.replace(" ", "_").lower()

        ok, msg = lotion.apply(caller, target, zone_name)
        if ok:
            caller.location.msg_contents(msg, exclude=[])
        else:
            caller.msg(f"|x{msg}|n")


# ---------------------------------------------------------------------------
# CmdInject
# ---------------------------------------------------------------------------

class CmdInject(MuxCommand):
    """
    Inject a syringe into a character zone for a temporary (and with repeated use,
    increasingly permanent) size boost to the installed body mod item.

    Usage:
      inject <target> [<zone>]     — inject another character
      inject/self [<zone>]         — inject yourself

    The zone argument is optional if the target has only one installed body mod.
    You must have a syringe in your inventory.

    Temp boosts stack and last ~6 hours. After 5 total uses on an item,
    permanent effects begin to accumulate.

    Examples:
      inject Helena chest
      inject/self chest
    """

    key     = "inject"
    locks   = "cmd:all()"
    help_category = "Body Mod"
    switch_options = ("self", "serum")

    def func(self):
        caller   = self.caller
        args     = self.args.strip()
        switches = self.switches

        # ── /serum branch — permanent growth serum ────────────────────
        if "serum" in switches:
            from typeclasses.growth_serum_item import GrowthSerumItem
            serums = [obj for obj in caller.contents if isinstance(obj, GrowthSerumItem)]
            if not serums:
                caller.msg("|xYou don't have a growth serum.|n")
                return
            serum = serums[0]

            if "self" in switches:
                target   = caller
                zone_arg = args.strip()
            else:
                parts = args.split(None, 1)
                if not parts:
                    caller.msg("|xUsage: inject/serum <target> [<zone>]|n")
                    return
                found = _find_char_in_room(caller, parts[0])
                if not found:
                    caller.msg(f"|xCan't find '{parts[0]}' in the room.|n")
                    return
                target   = found
                zone_arg = parts[1].strip() if len(parts) > 1 else ""

            zone_name = zone_arg.replace(" ", "_").lower() if zone_arg else None
            if not zone_name:
                zones = getattr(target.db, "zones", None) or {}
                for zn, zd in zones.items():
                    mech = (zd.get("mechanics", {}) or {}).get("body_mod")
                    if mech:
                        zone_name = zn
                        break

            if not zone_name:
                caller.msg(
                    f"|x{target.db.rp_name or target.name} has no zones with "
                    f"an installed body mod item.|n"
                )
                return

            ok, msg = serum.administer(caller, target, zone_name)
            if ok:
                caller.location.msg_contents(msg, exclude=[])
            else:
                caller.msg(f"|x{msg}|n")
            return

        # ── Standard syringe branch ───────────────────────────────────
        from typeclasses.syringe_item import SyringeItem
        syringes = [obj for obj in caller.contents if isinstance(obj, SyringeItem)]
        if not syringes:
            caller.msg("|xYou don't have a syringe.|n")
            return
        syringe = syringes[0]

        # Parse target
        if "self" in switches:
            target   = caller
            zone_arg = args.strip()
        else:
            parts    = args.split(None, 1)
            if not parts:
                caller.msg("|xUsage: inject <target> [<zone>]|n")
                return
            found = _find_char_in_room(caller, parts[0])
            if not found:
                caller.msg(f"|xCan't find '{parts[0]}' in the room.|n")
                return
            target   = found
            zone_arg = parts[1].strip() if len(parts) > 1 else ""

        # Resolve zone
        zone_name = zone_arg.replace(" ", "_").lower() if zone_arg else None

        if not zone_name:
            zones = getattr(target.db, "zones", None) or {}
            for zn, zd in zones.items():
                mech = (zd.get("mechanics", {}) or {}).get("body_mod")
                if mech:
                    zone_name = zn
                    break

        if not zone_name:
            caller.msg(
                f"|x{target.db.rp_name or target.name} has no zones with "
                f"an installed body mod item.|n"
            )
            return

        ok, msg = syringe.inject(caller, target, zone_name)
        if ok:
            caller.location.msg_contents(msg, exclude=[])
        else:
            caller.msg(f"|x{msg}|n")


# ---------------------------------------------------------------------------
# CmdMilk
# ---------------------------------------------------------------------------

class CmdMilk(MuxCommand):
    """
    Operate the milking machine in the room.

    Usage:
      milk <target> [<zone>]              — start a milking session
      milk/speed slow|steady|fast|intense — change speed mid-session
      milk/stop                           — stop the active session
      milk/status                         — show current speed and output

    The room must have a milking machine mechanic installed.
    The target must have at least one production item installed.

    Sessions run continuously at the set speed, extracting a small amount
    per tick and broadcasting messages from the room. When the target runs
    empty the machine stays on, running dry, until stopped with milk/stop.

    Output appears as FluidBottle objects on the machine tray. Bottles for
    the same producer and fluid type accumulate across ticks.

    Speed affects both extraction rate and message tone:
      slow    — gentle, patient. 4ml/tick, 60-second intervals.
      steady  — working rhythm. 11ml/tick, 30-second intervals.
      fast    — insistent pull. 22ml/tick, 15-second intervals.
      intense — maximum draw. 38ml/tick, 10-second intervals.

    Examples:
      milk Helena
      milk/self
      milk/speed intense
      milk/stop
    """

    key     = "milk"
    locks   = "cmd:all()"
    help_category = "Body Mod"
    switch_options = ("speed", "stop", "status", "self")

    def func(self):
        caller   = self.caller
        args     = self.args.strip()
        switches = self.switches
        room     = caller.location

        from typeclasses.milking_machine_mechanic import MilkingMachineMechanic
        from typeclasses.milking_session_script import MilkingSessionScript
        from world.milking_loader import get_speed_config, pick_message

        VALID_SPEEDS = list(get_speed_config().keys())

        # Find the machine in the room
        zone_name, state = MilkingMachineMechanic.find_in_room(room)
        if not state:
            caller.msg("|xThere's no milking machine here.|n")
            return

        # ── Helper: find any running session script in room ───────────
        def _find_session():
            """
            Return (target, script) if a session is active, else (None, None).

            First tries the machine state's stored target dbref.
            Falls back to scanning everyone in the room for a
            MilkingSessionScript — handles cases where the state was
            cleared (e.g. after a speed-change restart).
            """
            # Primary: look up the stored target
            target_dbref = (state or {}).get("target")
            if target_dbref:
                from evennia import search_object
                results = search_object(target_dbref, exact=True)
                if results:
                    tgt = results[0]
                    for scr in tgt.scripts.all():
                        if isinstance(scr, MilkingSessionScript):
                            return tgt, scr

            # Fallback: scan all characters in the room
            for obj in room.contents:
                if not hasattr(obj, "scripts"):
                    continue
                for scr in obj.scripts.all():
                    if isinstance(scr, MilkingSessionScript):
                        return obj, scr

            return None, None

        # ── /stop ─────────────────────────────────────────────────────
        if "stop" in switches:
            # Stop ALL active MilkingSessionScript instances on every
            # character in the room — cleans up stale/orphaned scripts
            # regardless of machine state.
            stopped   = []
            for obj in room.contents:
                if not hasattr(obj, "scripts"):
                    continue
                for scr in list(obj.scripts.all()):
                    if isinstance(scr, MilkingSessionScript):
                        stopped.append((obj, scr.db.speed or "steady"))
                        scr.stop()

            if stopped:
                # Use the first stopped session for the stop message
                first_tgt, first_speed = stopped[0]
                tgt_name = first_tgt.db.rp_name or first_tgt.name
                stop_msg = pick_message(first_speed, "stop")
                if stop_msg:
                    room.msg_contents(stop_msg.replace("{target}", tgt_name))
            else:
                room.msg_contents("|xThe milking machine cycles down and falls quiet.|n")
                MilkingMachineMechanic.set_state(
                    room, zone_name, active=False, operator=None, target=None
                )
            return

        # ── /speed ────────────────────────────────────────────────────
        if "speed" in switches:
            speed = args.lower().strip()
            if speed not in VALID_SPEEDS:
                caller.msg(f"|xValid speeds: {', '.join(VALID_SPEEDS)}|n")
                return
            MilkingMachineMechanic.set_state(room, zone_name, speed=speed)
            tgt, script = _find_session()
            if script:
                script.set_speed(speed)
            room.msg_contents(
                f"|x{caller.db.rp_name or caller.name} adjusts the machine to {speed} speed.|n"
            )
            return

        # ── /status ───────────────────────────────────────────────────
        if "status" in switches:
            speed  = state.get("speed", "steady")
            active = state.get("active", False)
            out_ml = state.get("session_output_ml", 0.0)
            from typeclasses.production_item import format_volume
            caller.msg(
                f"|wMilking Machine|n\n"
                f"  Speed:          {speed}\n"
                f"  Active session: {'yes' if active else 'no'}\n"
                f"  Session output: {format_volume(out_ml)}"
            )
            return

        # ── Start session ─────────────────────────────────────────────
        if "self" in switches:
            target      = caller
            zone_filter = args.replace(" ", "_").lower() if args else None
        else:
            if not args:
                caller.msg("|xUsage: milk <target> [<zone>] or milk/self [<zone>]|n")
                return
            parts      = args.split(None, 1)
            found_char = None
            for obj in room.contents:
                if hasattr(obj, "db") and (
                    (obj.db.rp_name or obj.name or "").lower().startswith(parts[0].lower())
                ):
                    found_char = obj
                    break
            if not found_char:
                caller.msg(f"|xCan't find '{parts[0]}' here.|n")
                return
            target      = found_char
            zone_filter = parts[1].replace(" ", "_").lower() if len(parts) > 1 else None

        target_name = target.db.rp_name or target.name

        # Verify target has production items
        from evennia import search_object
        from typeclasses.production_item import ProductionItem
        zones      = getattr(target.db, "zones", None) or {}
        found_prod = False
        for zn, zd in zones.items():
            if zone_filter and zn != zone_filter:
                continue
            mechanics = zd.get("mechanics", {}) or {}
            entry     = mechanics.get("production")
            if entry:
                results = search_object(entry.get("item_dbref", ""), exact=True)
                if results and isinstance(results[0], ProductionItem):
                    found_prod = True
                    break

        if not found_prod:
            caller.msg(
                f"|x{target_name} has no production items installed"
                + (f" on '{zone_filter}'" if zone_filter else "") + ".|n"
            )
            return

        # Stop any existing session on this target first
        for script in target.scripts.all():
            if isinstance(script, MilkingSessionScript):
                script.stop()

        speed  = state.get("speed", "steady")
        config = get_speed_config()
        if speed not in config:
            speed = "steady"

        # Start message
        start_msg = pick_message(speed, "start")
        if start_msg:
            room.msg_contents(start_msg.replace("{target}", target_name))

        # Create and start the session script
        from evennia.utils import create
        script = create.create_script(
            MilkingSessionScript,
            obj=target,
            autostart=False,
            persistent=True,
        )
        script.db.speed          = speed
        script.db.operator_dbref = caller.dbref
        script.db.zone_filter    = zone_filter
        script.interval          = config[speed]["interval_seconds"]
        script.start()

        # Mark machine active
        MilkingMachineMechanic.set_state(
            room, zone_name,
            active=True,
            operator=caller.dbref,
            target=target.dbref,
            session_output_ml=0.0,
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_BODY_MOD_CMDS = [
    CmdInstall,
    CmdUninstall,
    CmdSetFluid,
    CmdApplyLotion,
    CmdInject,
    CmdMilk,
]
