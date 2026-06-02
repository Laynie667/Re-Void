"""
commands/womb_commands.py

WombRoom commands for Re:Void.

Player commands:
  enter <host> [zone]       — enter a host's WombRoom via their orifice zone
  leave / exit womb         — leave the WombRoom you're currently inside
  pulse <message>           — host broadcasts inward to all residents

Host management (works remotely without being inside):
  wombroom                  — show status of your installed WombRoom
  wombroom desc             — open editor for interior description
  wombroom desc = <text>    — set interior description inline
  wombroom lock             — lock the room (no new entries)
  wombroom unlock           — unlock the room
  wombroom resident add <name>    — add a resident
  wombroom resident remove <name> — remove a resident
  wombroom resident list          — list current residents
  wombroom drain            — drain all fluid from the room
  wombroom install <zone>   — install WombRoom on one of your zones
  wombroom uninstall        — uninstall and collapse the room

ALL_WOMB_CMDS exported for default_cmdsets.py.
"""

from evennia.commands.default.muxcommand import MuxCommand
from evennia import Command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_womb_room(character):
    """Return the WombRoom installed on this character's zone, or None."""
    from typeclasses.womb_room import WombRoom
    zones = getattr(character.db, "zones", None) or {}
    for zone_data in zones.values():
        mech = (zone_data or {}).get("mechanics") or {}
        wr_entry = mech.get("womb_room")
        if wr_entry:
            dbref = wr_entry.get("room_dbref")
            if dbref:
                from evennia import search_object
                results = search_object(dbref, exact=True)
                if results and isinstance(results[0], WombRoom):
                    return results[0]
    return None


def _get_womb_room_and_zone(character):
    """Return (WombRoom, zone_name) or (None, None)."""
    from typeclasses.womb_room import WombRoom
    zones = getattr(character.db, "zones", None) or {}
    for zone_name, zone_data in zones.items():
        mech = (zone_data or {}).get("mechanics") or {}
        wr_entry = mech.get("womb_room")
        if wr_entry:
            dbref = wr_entry.get("room_dbref")
            if dbref:
                from evennia import search_object
                results = search_object(dbref, exact=True)
                if results and isinstance(results[0], WombRoom):
                    return results[0], zone_name
    return None, None


# ---------------------------------------------------------------------------
# CmdEnterWomb — enter a host's WombRoom via their orifice zone
# ---------------------------------------------------------------------------

class CmdEnterWomb(Command):
    """
    Enter another character's WombRoom through their orifice zone.

    Usage:
      enter <host> [zone]

    You must be on their resident list (added via 'wombroom resident add').
    If the host has only one WombRoom, zone is optional.
    You can leave with 'leave' or 'exit'.
    """

    key     = "enter"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        args   = self.args.strip()
        room   = caller.location

        if not args:
            caller.msg("|xUsage: enter <character> [zone]|n")
            return

        parts = args.split(None, 1)
        target_name = parts[0]
        zone_query  = parts[1].strip().lower().replace(" ", "_") if len(parts) > 1 else None

        target = caller.search(target_name, location=room)
        if not target:
            return

        from typeclasses.womb_room import WombRoom
        zones = getattr(target.db, "zones", None) or {}

        # Find matching WombRoom zones
        candidates = []
        for zone_name, zone_data in zones.items():
            mech = (zone_data or {}).get("mechanics") or {}
            wr_entry = mech.get("womb_room")
            if wr_entry:
                if not zone_query or zone_name == zone_query or zone_name.endswith(zone_query):
                    candidates.append((zone_name, wr_entry.get("room_dbref")))

        if not candidates:
            target_name_disp = target.db.rp_name or target.name
            caller.msg(f"|x{target_name_disp} has no WombRoom installed{' on that zone' if zone_query else ''}.|n")
            return

        if len(candidates) > 1 and not zone_query:
            zones_list = ", ".join(zn.replace("_", " ") for zn, _ in candidates)
            caller.msg(f"|xMultiple WombRooms found. Specify a zone: {zones_list}|n")
            return

        zone_name, room_dbref = candidates[0]

        from evennia import search_object
        results = search_object(room_dbref, exact=True)
        if not results or not isinstance(results[0], WombRoom):
            caller.msg("|xThe WombRoom object could not be found. Tell a staff member.|n")
            return

        womb = results[0]

        # Access check
        if not womb.is_friend(caller) and not womb.is_staff(caller):
            if caller.id != womb.db.womb_host_id:
                target_name_disp = target.db.rp_name or target.name
                caller.msg(f"|x{target_name_disp} has not added you as a resident.|n")
                return

        # Zone sealed check (door is open if unsealed, but residents bypass lock)
        # Residents can enter regardless of seal state — the host manages this
        # via wombroom lock/unlock rather than zone seal

        # Entry messages
        from world.milking_loader import pick_womb_message
        host_name  = (target.db.rp_name or target.name)
        caller_name = caller.db.rp_name or caller.name
        zone_disp   = zone_name.replace("_", " ")

        entry_msg = pick_womb_message("entry") or f"{caller_name} enters through {host_name}'s {zone_disp}."
        entry_msg = (entry_msg
                     .replace("{actor}", caller_name)
                     .replace("{host}", host_name)
                     .replace("{zone}", zone_disp))

        # Move caller into the womb room
        caller.move_to(womb, quiet=True)
        # Message to residents already inside
        womb.msg_contents(entry_msg, exclude=[caller])
        # Message to caller
        caller.msg(entry_msg)
        # Message to outside room
        outside_msg = f"|x{caller_name} presses close to {host_name} and is gone.|n"
        if room:
            room.msg_contents(outside_msg, exclude=[caller])

        # Trigger look
        caller.execute_cmd("look")


# ---------------------------------------------------------------------------
# CmdLeaveWomb — leave the WombRoom
# ---------------------------------------------------------------------------

class CmdLeaveWomb(Command):
    """
    Leave the WombRoom you are currently inside.

    Usage:
      leave
      exit

    Returns you to the room where the host character is located.
    """

    key     = "leave"
    aliases = ["exit"]
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        room   = caller.location

        from typeclasses.womb_room import WombRoom
        if not isinstance(room, WombRoom):
            # Fall through to normal exit behaviour
            caller.msg("|xYou're not inside a WombRoom.|n")
            return

        host = room._get_host()
        if not host or not host.location:
            caller.msg("|xThe exit is unclear. Ask a staff member for help.|n")
            return

        zone_name   = room.db.womb_zone or ""
        zone_disp   = zone_name.replace("_", " ")
        caller_name = caller.db.rp_name or caller.name
        host_name   = host.db.rp_name or host.name

        from world.milking_loader import pick_womb_message
        exit_msg = pick_womb_message("exit") or f"{caller_name} passes back out through {host_name}'s {zone_disp}."
        exit_msg = (exit_msg
                    .replace("{actor}", caller_name)
                    .replace("{host}", host_name)
                    .replace("{zone}", zone_disp))

        # Message to remaining residents
        room.msg_contents(exit_msg, exclude=[caller])
        caller.msg(exit_msg)

        # Move to host's current location
        dest = host.location
        caller.move_to(dest, quiet=True)
        outside_msg = f"|x{caller_name} emerges from {host_name}.|n"
        dest.msg_contents(outside_msg, exclude=[caller])

        caller.execute_cmd("look")


# ---------------------------------------------------------------------------
# CmdPulse — host broadcasts a message inward
# ---------------------------------------------------------------------------

class CmdPulse(Command):
    """
    Broadcast a message inward to everyone currently inside your WombRoom.

    Usage:
      pulse <message>

    Only works if you have a WombRoom installed. You don't need to be inside it.
    Everyone inside hears the message with your voice wrapping around them.
    """

    key     = "pulse"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        msg    = self.args.strip()

        if not msg:
            caller.msg("|xUsage: pulse <message>|n")
            return

        womb = _get_womb_room(caller)
        if not womb:
            caller.msg("|xYou don't have a WombRoom installed.|n")
            return

        from typeclasses.characters import Character
        residents = [obj for obj in womb.contents if isinstance(obj, Character)]
        if not residents:
            caller.msg("|xThere's no one inside to hear you.|n")
            return

        host_name = caller.db.rp_name or caller.name
        from world.milking_loader import pick_womb_message
        pulse_msg = pick_womb_message("pulse") or f'{host_name}\'s voice fills the space: "{msg}"'
        pulse_msg = pulse_msg.replace("{host}", host_name).replace("{message}", msg)

        for resident in residents:
            resident.msg(pulse_msg)

        caller.msg(f"|x[Pulse sent to {len(residents)} resident(s).]|n")


# ---------------------------------------------------------------------------
# CmdWombRoom — host management command
# ---------------------------------------------------------------------------

class CmdWombRoom(MuxCommand):
    """
    Manage your WombRoom. Works from anywhere — you don't need to be inside.

    Usage:
      wombroom                         — show status
      wombroom install <zone>          — install on one of your zones
      wombroom uninstall               — remove and collapse the room
      wombroom desc                    — open editor for interior desc
      wombroom desc = <text>           — set interior desc inline
      wombroom lock                    — lock (no new entries)
      wombroom unlock                  — unlock
      wombroom resident add <name>     — add a resident
      wombroom resident remove <name>  — remove a resident
      wombroom resident list           — list current residents
      wombroom drain                   — drain all fluid

    The interior description is the same as: zone interior <zone> = <text>
    Either command sets it — wombroom desc is just a shortcut.
    """

    key     = "wombroom"
    locks   = "cmd:all()"
    help_category = "Housing"
    switch_options = ("install", "uninstall", "desc", "lock", "unlock",
                      "resident", "drain")

    def func(self):
        caller   = self.caller
        args     = self.args.strip()
        switches = self.switches

        if "install" in switches:
            self._do_install(caller, args)
        elif "uninstall" in switches:
            self._do_uninstall(caller)
        elif "desc" in switches:
            self._do_desc(caller, args)
        elif "lock" in switches:
            self._do_lock(caller, True)
        elif "unlock" in switches:
            self._do_lock(caller, False)
        elif "resident" in switches:
            self._do_resident(caller, args)
        elif "drain" in switches:
            self._do_drain(caller)
        else:
            self._do_status(caller)

    # -- Status --------------------------------------------------------

    def _do_status(self, caller):
        womb, zone_name = _get_womb_room_and_zone(caller)
        if not womb:
            caller.msg(
                "|xYou don't have a WombRoom installed.\n"
                "Usage: wombroom/install <zone>|n"
            )
            return

        from evennia.objects.models import ObjectDB
        def _name(pk):
            try:
                return ObjectDB.objects.get(pk=pk).db.rp_name or ObjectDB.objects.get(pk=pk).key
            except Exception:
                return f"#{pk}"

        from typeclasses.characters import Character
        residents_inside = [obj for obj in womb.contents if isinstance(obj, Character)]
        res_ids = womb.db.housing_friends or []

        from typeclasses.body_mod_item import format_body_volume
        vol = format_body_volume(womb.db.womb_fluid_ml or 0.0)
        cap = format_body_volume(womb.db.womb_capacity_ml or 20_000.0)
        state = womb.get_flood_state()
        locked = "|rLocked|n" if womb.db.housing_locked else "|gUnlocked|n"
        sealed = "|gSealed|n" if womb.is_zone_sealed() else "|xOpen|n"

        caller.msg(
            f"|wWombRoom|n — {womb.key}  [{locked}]  [Entrance: {sealed}]\n"
            f"  Zone:      {zone_name.replace('_', ' ')}\n"
            f"  Fluid:     {vol} / {cap}  ({state})\n"
            f"  Inside:    {len(residents_inside)} character(s)\n"
            f"  Residents: {', '.join(_name(pk) for pk in res_ids) or 'none'}\n"
            f"\n  Use |wwombroom/desc|n to set the interior description."
        )

    # -- Install -------------------------------------------------------

    def _do_install(self, caller, args):
        if not args:
            caller.msg("|xUsage: wombroom/install <zone>|n")
            return

        existing, _ = _get_womb_room_and_zone(caller)
        if existing:
            caller.msg("|xYou already have a WombRoom installed. Use wombroom/uninstall first.|n")
            return

        zone_name = args.lower().replace(" ", "_")
        from typeclasses.womb_room import WombRoom
        from evennia.utils import create

        womb = create.create_object(
            WombRoom,
            key=f"{caller.db.rp_name or caller.name}'s WombRoom",
            location=None,
        )
        ok, reason = womb.install(caller, zone_name)
        if not ok:
            womb.delete()
            caller.msg(f"|x{reason}|n")
            return

        caller.msg(
            f"|wWombRoom installed on {zone_name.replace('_', ' ')}.|n\n"
            f"  Set the interior description: |wwombroom/desc = <text>|n\n"
            f"  Add residents: |wwombroom/resident add <name>|n"
        )

    # -- Uninstall -----------------------------------------------------

    def _do_uninstall(self, caller):
        womb, _ = _get_womb_room_and_zone(caller)
        if not womb:
            caller.msg("|xYou don't have a WombRoom installed.|n")
            return
        ok, reason = womb.uninstall()
        if not ok:
            caller.msg(f"|x{reason}|n")
            return
        womb.delete()
        caller.msg("|xWombRoom uninstalled and removed.|n")

    # -- Desc ----------------------------------------------------------

    def _do_desc(self, caller, args):
        womb, zone_name = _get_womb_room_and_zone(caller)
        if not womb:
            caller.msg("|xYou don't have a WombRoom installed.|n")
            return

        if "=" in args:
            _, _, desc = args.partition("=")
            desc = desc.strip()
            if not desc:
                caller.msg("|xDescription cannot be empty.|n")
                return
            # Set via zone interior
            ok = caller.set_zone_interior(zone_name, desc)
            if ok:
                caller.msg("|wWombRoom interior description updated.|n")
            else:
                caller.msg("|xCould not set description.|n")
        else:
            # Open multi-line editor
            zones = getattr(caller.db, "zones", None) or {}
            current = (zones.get(zone_name) or {}).get("interior", "") or ""
            from world.text_editor import TextEditor

            def _save(caller, buffer, **kwargs):
                caller.set_zone_interior(kwargs["zone_name"], "\n".join(buffer))
                caller.msg("|wWombRoom interior description saved.|n")

            editor = TextEditor(
                caller,
                loadfunc=lambda caller, **kwargs: current.splitlines(),
                savefunc=_save,
                key=f"wombroom interior — {zone_name}",
                persistent=True,
                extra={"zone_name": zone_name},
            )
            caller.ndb._editor = editor
            editor.load()

    # -- Lock / Unlock -------------------------------------------------

    def _do_lock(self, caller, lock_state: bool):
        womb, _ = _get_womb_room_and_zone(caller)
        if not womb:
            caller.msg("|xYou don't have a WombRoom installed.|n")
            return
        womb.db.housing_locked = lock_state
        state = "|rLocked|n" if lock_state else "|gUnlocked|n"
        caller.msg(f"|wWombRoom is now {state}.|n")

    # -- Residents -----------------------------------------------------

    def _do_resident(self, caller, args):
        womb, _ = _get_womb_room_and_zone(caller)
        if not womb:
            caller.msg("|xYou don't have a WombRoom installed.|n")
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower() if parts else "list"
        name   = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "list":
            from evennia.objects.models import ObjectDB
            res_ids = womb.db.housing_friends or []
            if not res_ids:
                caller.msg("|xNo residents added yet.|n")
                return
            names = []
            for pk in res_ids:
                try:
                    obj = ObjectDB.objects.get(pk=pk)
                    names.append(obj.db.rp_name or obj.key)
                except Exception:
                    names.append(f"#{pk}")
            caller.msg("|wResidents:|n " + ", ".join(names))

        elif subcmd == "add":
            if not name:
                caller.msg("|xUsage: wombroom/resident add <name>|n")
                return
            target = caller.search(name, global_search=True)
            if not target:
                return
            if womb.add_friend(target):
                caller.msg(f"|w{target.db.rp_name or target.name} added as a resident.|n")
            else:
                caller.msg(f"|x{target.db.rp_name or target.name} is already a resident.|n")

        elif subcmd == "remove":
            if not name:
                caller.msg("|xUsage: wombroom/resident remove <name>|n")
                return
            target = caller.search(name, global_search=True)
            if not target:
                return
            if womb.remove_friend(target):
                caller.msg(f"|w{target.db.rp_name or target.name} removed from residents.|n")
            else:
                caller.msg(f"|x{target.db.rp_name or target.name} is not a resident.|n")

        else:
            caller.msg("|xUsage: wombroom/resident list | add <name> | remove <name>|n")

    # -- Drain ---------------------------------------------------------

    def _do_drain(self, caller):
        womb, _ = _get_womb_room_and_zone(caller)
        if not womb:
            caller.msg("|xYou don't have a WombRoom installed.|n")
            return
        womb.db.womb_fluid_ml   = 0.0
        womb.db.womb_fluid_type = "fluid"
        caller.msg("|xWombRoom drained.|n")


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

ALL_WOMB_CMDS = [
    CmdEnterWomb,
    CmdLeaveWomb,
    CmdPulse,
    CmdWombRoom,
]
