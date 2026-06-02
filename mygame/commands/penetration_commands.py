"""
commands/penetration_commands.py

Commands for shaft-zone interaction, arousal-building, and fluid deposit.

Requires:
  - Zone type 'shaft' — add with: zone add <name> type=shaft intimate
  - Zone type 'orifice' — already supported
  - Arousal system (typeclasses.arousal_script)
  - Fluid bank (typeclasses.fluid_bank)

Commands:
  penetrate <target> [<zone or #>] — initiate engagement with target's orifice zone
  thrust                           — add arousal per use while engaged
  withdraw                         — end engagement
  deposit [<target>] [<zone or #>] — deposit fluid as a degrading freeform item
  handmilk <target>                — manual breast extraction (steady-rate, high arousal)
  suck [<target>] [<zone>]         — context-sensitive oral / extraction / drink command
"""

import time
import random

from evennia.commands.default.muxcommand import MuxCommand
from evennia import Command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_shaft_zone(char):
    """Return the first zone of type 'shaft' with a body mod installed, or None."""
    zones = getattr(char.db, "zones", None) or {}
    for zname, zdata in zones.items():
        if zdata.get("zone_type") == "shaft":
            if (zdata.get("mechanics", {}) or {}).get("body_mod"):
                return zname
    return None


def _find_orifice_zones(char):
    """Return list of zone names with type 'orifice' or 'both'."""
    zones = getattr(char.db, "zones", None) or {}
    return [
        zn for zn, zd in zones.items()
        if zd.get("zone_type") in ("orifice", "both")
    ]


def _check_consent(actor, target):
    """True if target has consented to mature or bdsm interactions."""
    flags = getattr(target.db, "consent_flags", {}) or {}
    return flags.get("mature", False) or flags.get("bdsm", False)


def _resolve_zone_selection(zone_names, selection):
    """
    Resolve a zone from a list by number or name fragment.
    Returns zone name string or None.
    """
    if not zone_names:
        return None
    if selection.isdigit():
        idx = int(selection) - 1
        if 0 <= idx < len(zone_names):
            return zone_names[idx]
    key = selection.lower().replace(" ", "_")
    for zn in zone_names:
        if zn == key or zn.endswith(key) or key in zn:
            return zn
    return None


def _create_deposit_freeform(container, actor, fluid_type, fluid_flavor,
                              volume_ml, zone_name):
    """
    Place a degrading freeform item on a zone. TTL = 12 hours.
    Overwrites any existing unlocked deposit from the same actor.
    """
    from world.freeform_manager import FreeformManager
    from typeclasses.production_item import format_volume

    actor_name  = actor.db.rp_name or actor.name
    flavor_note = f", {fluid_flavor}" if fluid_flavor else ""
    item_key    = f"{actor_name.lower()}_{fluid_type}_deposit"
    item_desc   = (
        f"A deposit of {actor_name}'s {fluid_type}{flavor_note} "
        f"({format_volume(volume_ml)})."
    )

    ok, _ = FreeformManager.place_item(
        container, zone_name, item_key, item_desc,
        actor.id, display_mode="on"
    )

    if ok:
        items = container.db.freeform_items or {}
        entry = items.get(item_key)
        if entry:
            entry["ttl_hours"]  = 12.0
            entry["created_at"] = time.time()
            container.db.freeform_items = items


# ---------------------------------------------------------------------------
# CmdPenetrate
# ---------------------------------------------------------------------------

class CmdPenetrate(MuxCommand):
    """
    Initiate engagement with a target's orifice zone using your shaft zone.

    Usage:
      penetrate <target>            — lists target's available orifice zones
      penetrate <target> <zone>     — specify by name
      penetrate <target> <number>   — specify by list number

    Requires your character to have a zone of type 'shaft' with a body mod
    installed (PenisItem). Target must have consented to mature interaction.
    Engagement is tracked on your character. Use 'thrust' to continue and
    'withdraw' to end.
    """
    key     = "penetrate"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        args   = self.args.strip()
        room   = caller.location

        shaft_zone = _find_shaft_zone(caller)
        if not shaft_zone:
            caller.msg(
                "|xYou need a shaft-type zone with a body mod installed "
                "to use this command.|n"
            )
            return

        if not args:
            caller.msg("|xUsage: penetrate <target> [<zone or number>]|n")
            return

        parts  = args.split(None, 1)
        target = caller.search(parts[0], location=room)
        if not target:
            return

        if target == caller:
            caller.msg("|xYou cannot penetrate yourself with this command.|n")
            return

        if not _check_consent(caller, target):
            tname = target.db.rp_name or target.name
            caller.msg(
                f"|x{tname} has not consented to mature interaction. "
                f"They need the 'mature' consent flag enabled.|n"
            )
            return

        orifices = _find_orifice_zones(target)
        if not orifices:
            tname = target.db.rp_name or target.name
            caller.msg(f"|x{tname} has no orifice zones available.|n")
            return

        # Resolve zone selection
        zone_name = None
        if len(parts) > 1:
            zone_name = _resolve_zone_selection(orifices, parts[1].strip())

        if zone_name is None:
            if len(orifices) == 1:
                zone_name = orifices[0]
            else:
                # Show numbered list
                tname = target.db.rp_name or target.name
                lines = [f"|w{tname}|n — available zones:"]
                for i, oz in enumerate(orifices, 1):
                    lines.append(f"  |w{i}.|n {oz.replace('_', ' ')}")
                lines.append(
                    "|xType: |wpenetrate "
                    f"{parts[0]} <number or zone name>|n"
                )
                caller.msg("\n".join(lines))
                return

        # Set engagement state — include caller's shaft zone for knot lookup
        shaft_zone = _find_shaft_zone(caller)
        caller.db.penetrating = {
            "target_dbref": target.dbref,
            "zone_name":    zone_name,
            "caller_zone":  shaft_zone,
        }

        caller_name = caller.db.rp_name or caller.name
        target_name = target.db.rp_name or target.name
        zone_disp   = zone_name.replace("_", " ")

        # Use zone handle message if the target has one for 'penetrate', else generic
        zones  = getattr(target.db, "zones", None) or {}
        zdata  = zones.get(zone_name, {})
        handles = (zdata.get("handle_details", {}) or {}).get("penetrate", [])

        if handles:
            from world.freeform_manager import _resolve_tokens
            try:
                msg = _resolve_tokens(random.choice(handles), caller, target, zone_disp)
            except Exception:
                msg = f"{caller_name} and {target_name} — {zone_disp}."
        else:
            msg = f"{caller_name} and {target_name} — {zone_disp}."

        room.msg_contents(msg)

        # Initial arousal bump for both
        from typeclasses.arousal_script import add_arousal
        add_arousal(caller, 5.0)
        add_arousal(target, 5.0)


# ---------------------------------------------------------------------------
# CmdThrust
# ---------------------------------------------------------------------------

class CmdThrust(Command):
    """
    Continue while engaged in penetration. Builds arousal for both participants.

    Usage:
      thrust

    You must be in an active penetration engagement (see: penetrate).
    Each use adds arousal to both you and your partner. When arousal reaches
    100, the climax event fires automatically.
    """
    key     = "thrust"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller  = self.caller
        engaged = caller.db.penetrating

        if not engaged:
            caller.msg("|xYou are not currently engaged. Use 'penetrate' first.|n")
            return

        target_dbref = engaged.get("target_dbref")
        zone_name    = engaged.get("zone_name", "")

        from evennia import search_object
        results = search_object(target_dbref, exact=True)
        if not results:
            caller.db.penetrating = None
            caller.msg("|xYour partner is no longer available. Engagement ended.|n")
            return

        target = results[0]
        room   = caller.location
        if not room or target.location != room:
            caller.db.penetrating = None
            caller.msg("|xYour partner has left the room. Engagement ended.|n")
            return

        caller_name = caller.db.rp_name or caller.name
        target_name = target.db.rp_name or target.name
        zone_disp   = zone_name.replace("_", " ")

        # Zone handle message if set, else generic
        zones  = getattr(target.db, "zones", None) or {}
        zdata  = zones.get(zone_name, {})
        handles = (zdata.get("handle_details", {}) or {}).get("thrust", [])

        if handles:
            from world.freeform_manager import _resolve_tokens
            try:
                msg = _resolve_tokens(random.choice(handles), caller, target, zone_disp)
            except Exception:
                msg = f"{caller_name} — {target_name}'s {zone_disp}."
        else:
            msg = f"{caller_name} — {target_name}'s {zone_disp}."

        room.msg_contents(msg)

        from typeclasses.arousal_script import add_arousal
        add_arousal(caller, 8.0)
        add_arousal(target, 5.0)

        # Try knot trigger (25% chance once arousal >= 70 and knot installed)
        caller_zone = (caller.db.penetrating or {}).get("caller_zone")
        if caller_zone:
            try:
                from typeclasses.knot_item import try_trigger_knot
                try_trigger_knot(caller, target, caller_zone, room)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# CmdWithdraw
# ---------------------------------------------------------------------------

class CmdWithdraw(Command):
    """
    End active penetration engagement.

    Usage:
      withdraw
    """
    key     = "withdraw"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller  = self.caller
        engaged = caller.db.penetrating

        if not engaged:
            caller.msg("|xYou are not currently engaged.|n")
            return

        target_dbref = engaged.get("target_dbref")
        zone_name    = engaged.get("zone_name", "")
        # Block withdrawal if knotted and tie hasn't expired
        import time as _t
        if engaged.get("knotted"):
            expires = engaged.get("knot_expires_at", 0.0)
            if _t.time() < expires:
                remaining = max(0, int(expires - _t.time()))
                caller.msg(f"|xThe knot holds — {remaining}s remaining.|n")
                return
            else:
                # Natural release — fire message then continue with withdrawal
                engaged["knotted"] = False
                engaged["knot_expires_at"] = 0.0
                caller.db.penetrating = engaged
                room = caller.location
                if room:
                    c_name = caller.db.rp_name or caller.name
                    room.msg_contents(f"|x{c_name} — the knot releases naturally.|n")

        caller.db.penetrating = None

        caller_name = caller.db.rp_name or caller.name
        zone_disp   = zone_name.replace("_", " ")
        room        = caller.location

        if room:
            from evennia import search_object
            results     = search_object(target_dbref, exact=True)
            target_name = (
                (results[0].db.rp_name or results[0].name) if results else "them"
            )
            room.msg_contents(
                f"{caller_name} withdraws from {target_name}'s {zone_disp}."
            )


# ---------------------------------------------------------------------------
# CmdDeposit
# ---------------------------------------------------------------------------

class CmdDeposit(MuxCommand):
    """
    Deposit fluid on a surface, on a target, or inside a zone.
    Creates a freeform item that degrades after 12 hours.

    Usage:
      deposit                        — deposit in current room
      deposit <target>               — surface deposit on target
      deposit <target> <zone or #>   — deposit in/on a specific zone

    Fluid is extracted from your installed production items (prefers non-milk
    types). All extracted fluid is deposited.

    See also: penetrate, thrust, withdraw
    """
    key     = "deposit"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        args   = self.args.strip()
        room   = caller.location

        # Find production item with stock
        from evennia import search_object
        from typeclasses.production_item import ProductionItem, format_volume

        prod_item  = None
        fluid_type = None
        flavor     = None

        zones = getattr(caller.db, "zones", None) or {}
        for zn, zd in zones.items():
            entry = (zd.get("mechanics", {}) or {}).get("production")
            if not entry:
                continue
            results = search_object(entry.get("item_dbref", ""), exact=True)
            if not results or not isinstance(results[0], ProductionItem):
                continue
            item = results[0]
            vol  = item.db.current_volume_ml or 0.0
            if vol > 0:
                ft = item.db.fluid_type or "fluid"
                # Prefer non-milk for deposit
                if ft != "milk" and prod_item is None:
                    prod_item  = item
                    fluid_type = ft
                    flavor     = item.db.fluid_flavor
                elif prod_item is None:
                    prod_item  = item
                    fluid_type = ft
                    flavor     = item.db.fluid_flavor

        if not prod_item:
            caller.msg("|xYou have nothing to deposit.|n")
            return

        extract_ml = prod_item.db.current_volume_ml or 0.0
        if extract_ml <= 0:
            caller.msg("|xNothing to deposit — stock is empty.|n")
            return

        # Extract
        prod_item.db.current_volume_ml = 0.0
        prod_item.reset_fullness_notifications()

        caller_name = caller.db.rp_name or caller.name

        # Determine target / zone
        if not args:
            # Room deposit — use first room zone
            room_zones = getattr(room.db, "zones", None) or {}
            zone_name  = next(iter(room_zones), None)
            if zone_name:
                _create_deposit_freeform(
                    room, caller, fluid_type, flavor, extract_ml, zone_name
                )
            room.msg_contents(
                f"{caller_name} deposits {format_volume(extract_ml)} of "
                f"{fluid_type} on the floor."
            )
        else:
            parts  = args.split(None, 1)
            target = caller.search(parts[0], location=room)
            if not target:
                return

            zone_name  = None
            tgt_zones  = list((getattr(target.db, "zones", None) or {}).keys())
            target_name = target.db.rp_name or target.name

            if len(parts) > 1:
                zone_name = _resolve_zone_selection(tgt_zones, parts[1].strip())
            if not zone_name and tgt_zones:
                # Default to first body zone
                zone_name = tgt_zones[0]

            if zone_name:
                _create_deposit_freeform(
                    target, caller, fluid_type, flavor, extract_ml, zone_name
                )
                zone_disp = zone_name.replace("_", " ")
                room.msg_contents(
                    f"{caller_name} deposits {format_volume(extract_ml)} of "
                    f"{fluid_type} onto {target_name}'s {zone_disp}."
                )
            else:
                caller.msg(f"|x{target_name} has no zones to deposit on.|n")
                # Restore stock on failure
                prod_item.db.current_volume_ml = extract_ml
                return

        # Route to bank as well
        try:
            from typeclasses.fluid_bank import GlobalFluidBank
            GlobalFluidBank.get().deposit(caller, extract_ml, fluid_type, flavor)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CmdSuck
# ---------------------------------------------------------------------------

class CmdSuck(MuxCommand):
    """
    Context-sensitive oral / nursing / drinking command.

    Usage:
      suck <target>          — auto-detects context:
                               • target has shaft zone → arousal event for them
                               • target has breast production → slow extraction
                               • target is a drinkable container → drink from it
      suck <target> <zone>   — interact with a specific zone
      suck/self <zone>       — self-interaction

    See also: handmilk, penetrate
    """
    key     = "suck"
    locks   = "cmd:all()"
    help_category = "Interaction"
    switch_options = ("self",)

    def func(self):
        caller   = self.caller
        args     = self.args.strip()
        switches = self.switches
        room     = caller.location

        # Self-suck (own zone)
        if "self" in switches:
            self._do_self(caller, args, room)
            return

        if not args:
            caller.msg("|xUsage: suck <target> [<zone>]|n")
            return

        parts = args.split(None, 1)

        # Try as a container first
        from typeclasses.fluid_bottle import FluidBottle
        from typeclasses.fluid_fridge  import FluidFridge

        obj = caller.search(parts[0], location=room, quiet=True)
        if isinstance(obj, list):
            obj = obj[0] if obj else None

        if isinstance(obj, (FluidBottle, FluidFridge)):
            self._do_drink(caller, obj, room)
            return

        # Character target
        target = caller.search(parts[0], location=room)
        if not target:
            return

        zone_arg = parts[1].strip() if len(parts) > 1 else None
        self._do_character(caller, target, zone_arg, room)

    def _do_character(self, caller, target, zone_arg, room):
        from evennia import search_object
        from typeclasses.production_item import ProductionItem

        caller_name = caller.db.rp_name or caller.name
        target_name = target.db.rp_name or target.name

        # Check for shaft zone → arousal event
        if not zone_arg:
            shaft = _find_shaft_zone(target)
            if shaft:
                zone_disp = shaft.replace("_", " ")
                room.msg_contents(
                    f"{caller_name} — {target_name}'s {zone_disp}."
                )
                from typeclasses.arousal_script import add_arousal
                add_arousal(target, 12.0)
                add_arousal(caller, 4.0)
                return

        # Find breast production item for nursing
        zones = getattr(target.db, "zones", None) or {}
        prod_item = None
        prod_zone = None

        for zn, zd in zones.items():
            if zone_arg:
                key = zone_arg.lower().replace(" ", "_")
                if zn != key and key not in zn:
                    continue
            entry = (zd.get("mechanics", {}) or {}).get("production")
            if not entry:
                continue
            results = search_object(entry.get("item_dbref", ""), exact=True)
            if results and isinstance(results[0], ProductionItem):
                # Prefer milk type for nursing
                item = results[0]
                if item.db.fluid_type == "milk" or prod_item is None:
                    prod_item = item
                    prod_zone = zn

        if prod_item:
            available = prod_item.db.current_volume_ml or 0.0
            if available <= 0:
                caller.msg(
                    f"|x{target_name} doesn't have anything for you right now.|n"
                )
                return

            # Slow rate — 4ml
            extract = min(4.0, available)
            prod_item.db.current_volume_ml = max(0.0, available - extract)
            prod_item.reset_fullness_notifications()
            zone_disp = prod_zone.replace("_", " ")

            room.msg_contents(
                f"{caller_name} — {target_name}'s {zone_disp}."
            )
            from typeclasses.arousal_script import add_arousal
            add_arousal(caller, 3.0)
            add_arousal(target, 4.0)

            # Caller drinks the extracted fluid
            from typeclasses.fluid_bank import GlobalFluidBank
            try:
                GlobalFluidBank.get().deposit(
                    target, extract,
                    prod_item.db.fluid_type or "milk",
                    prod_item.db.fluid_flavor
                )
            except Exception:
                pass
            return

        # No matching production, generic zone interaction
        target_zones = list(zones.keys())
        if zone_arg and target_zones:
            zone_name = _resolve_zone_selection(target_zones, zone_arg)
        else:
            zone_name = target_zones[0] if target_zones else None

        if zone_name:
            zone_disp = zone_name.replace("_", " ")
            room.msg_contents(
                f"{caller_name} — {target_name}'s {zone_disp}."
            )
            from typeclasses.arousal_script import add_arousal
            add_arousal(target, 6.0)
            add_arousal(caller, 3.0)
        else:
            caller.msg("|xNothing to interact with there.|n")

    def _do_drink(self, caller, container, room):
        from typeclasses.fluid_bottle import FluidBottle
        from typeclasses.fluid_fridge  import FluidFridge
        from typeclasses.production_item import format_volume

        caller_name = caller.db.rp_name or caller.name

        if isinstance(container, FluidFridge):
            bottles = [
                o for o in container.contents
                if isinstance(o, FluidBottle) and not o.db.is_empty
            ]
            if not bottles:
                caller.msg("|xThe fridge is empty.|n")
                return
            container = bottles[0]

        if isinstance(container, FluidBottle):
            msg = container.do_drink(caller)
            caller.msg(msg)
            if room:
                room.msg_contents(
                    f"{caller_name} drinks from a bottle.",
                    exclude=[caller]
                )

    def _do_self(self, caller, zone_arg, room):
        caller_name = caller.db.rp_name or caller.name
        caller_zones = list((getattr(caller.db, "zones", None) or {}).keys())
        zone_name = None
        if zone_arg:
            zone_name = _resolve_zone_selection(caller_zones, zone_arg)
        elif caller_zones:
            zone_name = caller_zones[0]

        if zone_name:
            zone_disp = zone_name.replace("_", " ")
            room.msg_contents(
                f"{caller_name} — their own {zone_disp}."
            )
            from typeclasses.arousal_script import add_arousal
            add_arousal(caller, 5.0)
        else:
            caller.msg("|xNothing to interact with.|n")


# ---------------------------------------------------------------------------
# CmdHandmilk
# ---------------------------------------------------------------------------

class CmdHandmilk(MuxCommand):
    """
    Manually extract from a target's breast production item.
    Extracts one steady-rate tick's worth. Higher arousal gain than machine.

    Usage:
      handmilk <target> [<zone>]   — milk a target manually
      handmilk/self [<zone>]       — milk yourself

    Output goes to the Global Fluid Bank (and from there to the fridge).
    See also: milk, suck
    """
    key     = "handmilk"
    locks   = "cmd:all()"
    help_category = "Body Mod"
    switch_options = ("self",)

    def func(self):
        caller   = self.caller
        args     = self.args.strip()
        switches = self.switches
        room     = caller.location

        if "self" in switches:
            target    = caller
            zone_arg  = args.strip()
        else:
            if not args:
                caller.msg("|xUsage: handmilk <target> [<zone>]|n")
                return
            parts    = args.split(None, 1)
            target   = caller.search(parts[0], location=room)
            if not target:
                return
            zone_arg = parts[1].strip() if len(parts) > 1 else None

        # Find production item
        from evennia import search_object
        from typeclasses.production_item import ProductionItem, format_volume

        zones     = getattr(target.db, "zones", None) or {}
        prod_item = None
        prod_zone = None

        for zn, zd in zones.items():
            if zone_arg:
                key = zone_arg.lower().replace(" ", "_")
                if zn != key and key not in zn:
                    continue
            entry = (zd.get("mechanics", {}) or {}).get("production")
            if not entry:
                continue
            results = search_object(entry.get("item_dbref", ""), exact=True)
            if results and isinstance(results[0], ProductionItem):
                item = results[0]
                if item.db.fluid_type == "milk" or prod_item is None:
                    prod_item = item
                    prod_zone = zn

        if not prod_item:
            tname = target.db.rp_name or target.name
            caller.msg(
                f"|x{tname} has no production items installed"
                + (f" on '{zone_arg}'" if zone_arg else "") + ".|n"
            )
            return

        available = prod_item.db.current_volume_ml or 0.0
        if available <= 0:
            tname = target.db.rp_name or target.name
            caller.msg(f"|x{tname} has nothing to give right now.|n")
            return

        # Steady-rate amount with variance
        steady_ml  = 11.0
        variance   = random.uniform(0.80, 1.20)
        extract    = min(steady_ml * variance, available)

        prod_item.db.current_volume_ml = max(0.0, available - extract)
        prod_item.reset_fullness_notifications()

        fluid_type = prod_item.db.fluid_type  or "milk"
        flavor     = prod_item.db.fluid_flavor

        caller_name = caller.db.rp_name or caller.name
        target_name = target.db.rp_name or target.name
        zone_disp   = prod_zone.replace("_", " ")

        room.msg_contents(
            f"{caller_name} milks {target_name} by hand — "
            f"{zone_disp} ({format_volume(extract)})."
        )

        # Bank deposit
        try:
            from typeclasses.fluid_bank import GlobalFluidBank
            GlobalFluidBank.get().deposit(target, extract, fluid_type, flavor)
        except Exception:
            pass

        # Higher arousal gain than machine (more intimate)
        from typeclasses.arousal_script import add_arousal
        add_arousal(target, 8.0)
        if caller != target:
            add_arousal(caller, 2.0)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_PENETRATION_CMDS = [
    CmdPenetrate,
    CmdThrust,
    CmdWithdraw,
    CmdDeposit,
    CmdSuck,
    CmdHandmilk,
]
