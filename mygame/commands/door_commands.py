"""
commands/door_commands.py

Commands for lockable door mechanics on room zones.

    door set <zone> = <exit name>   — link the door zone to an exit (one-time setup)
    door owner <zone> add <name>    — add a character as a door owner (can lock/unlock)
    door owner <zone> remove <name> — remove a door owner
    door msg <zone> lock = <text>   — customise the locked-door message
    door msg <zone> knock = <text>  — customise the knock message
    lock <zone>                     — lock the door
    unlock <zone>                   — unlock the door
    knock <zone>                    — knock; people on the other side hear it

Zone names are matched fuzzily so 'helena door' finds 'helena_door'.
Builders and door owners can lock/unlock. Only Builders can use 'door set'.
"""

from evennia import Command, default_cmds


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fuzzy_door_zone(room, name):
    """
    Find a zone with a door mechanic by fuzzy name.
    Tries: exact, space→underscore, prefix match.
    Returns (zone_name, zone_dict) or (None, None).
    """
    zones = room.db.zones or {}
    name_clean = name.strip().lower()
    name_under = name_clean.replace(" ", "_")

    for candidate in (name_clean, name_under):
        if candidate in zones:
            z = zones[candidate]
            if hasattr(z, "get") and (z.get("mechanics") or {}).get("door"):
                return candidate, z

    # Partial match
    for zname, zdata in zones.items():
        if not hasattr(zdata, "get"):
            continue
        if not (zdata.get("mechanics") or {}).get("door"):
            continue
        if name_clean in zname or name_under in zname:
            return zname, zdata

    return None, None


def _is_door_owner(caller, door_data):
    """Return True if caller can lock/unlock this door."""
    if caller.check_permstring("Builder"):
        return True
    return caller.id in (door_data.get("owner_ids") or [])


def _save_door(room, zone_name, zone, door_data):
    """Write updated door data back through full dict copies for DB persistence."""
    mech = dict((zone.get("mechanics") or {}))
    mech["door"] = door_data
    zone_copy = dict(zone) if hasattr(zone, "items") else {}
    zone_copy["mechanics"] = mech
    zones_copy = dict(room.db.zones or {})
    zones_copy[zone_name] = zone_copy
    room.db.zones = zones_copy


# ---------------------------------------------------------------------------
# CmdDoor  (Builder-only management)
# ---------------------------------------------------------------------------

class CmdDoor(default_cmds.MuxCommand):
    """
    Manage lockable door mechanics on room zones.

    Usage:
      door set <zone> = <exit name>       — link door to an exit
      door owner <zone> add <character>   — grant lock/unlock rights
      door owner <zone> remove <character>— revoke lock/unlock rights
      door msg <zone> lock = <text>       — set the locked-door message
      door msg <zone> knock = <text>      — set the knock message seen inside
      door list <zone>                    — show door mechanic settings

    Zone names are matched fuzzily (spaces and underscores both work).
    Requires Builder permission.
    """

    key = "door"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("|xYou aren't in a room.|n")
            return

        args = self.args.strip()
        if not args:
            caller.msg("|xUsage: |wdoor set/owner/msg/list <zone> ...|n")
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest   = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "set":
            self._do_set(room, rest)
        elif subcmd == "owner":
            self._do_owner(room, rest)
        elif subcmd == "msg":
            self._do_msg(room, rest)
        elif subcmd == "list":
            self._do_list(room, rest)
        else:
            caller.msg(f"|xUnknown door subcommand '{subcmd}'.|n")

    def _do_set(self, room, args):
        if "=" not in args:
            self.caller.msg("|xUsage: |wdoor set <zone> = <exit name>|n"); return

        zone_part, _, exit_name = args.partition("=")
        zone_part = zone_part.strip()
        exit_name = exit_name.strip()

        zone_name, zone = _fuzzy_door_zone(room, zone_part)
        if zone_name is None:
            self.caller.msg(f"|xNo door mechanic found for '{zone_part}'.|n"); return

        # Find exit by name/alias
        exit_obj = None
        for ex in room.exits:
            if (ex.key.lower() == exit_name.lower() or
                    exit_name.lower() in [a.lower() for a in (ex.aliases.all() or [])]):
                exit_obj = ex
                break

        if not exit_obj:
            self.caller.msg(
                f"|xNo exit named '{exit_name}' found in this room.\n"
                f"|xAvailable exits: "
                f"{', '.join(e.key for e in room.exits) or 'none'}|n"
            )
            return

        door = dict(zone.get("mechanics", {}).get("door", {}))
        door["destination_id"] = exit_obj.destination.id
        _save_door(room, zone_name, zone, door)
        self.caller.msg(
            f"|wDoor zone '|w{zone_name}|w' linked to exit "
            f"'|w{exit_obj.key}|w' → {exit_obj.destination.key}.|n\n"
            f"|xUse |wlock {zone_name}|n to lock it.|n"
        )

    def _do_owner(self, room, args):
        parts = args.split(None, 2)
        if len(parts) < 3:
            self.caller.msg(
                "|xUsage: |wdoor owner <zone> add/remove <character>|n"
            ); return

        zone_part = parts[0]
        action    = parts[1].lower()
        char_name = parts[2]

        zone_name, zone = _fuzzy_door_zone(room, zone_part)
        if zone_name is None:
            self.caller.msg(f"|xNo door mechanic for '{zone_part}'.|n"); return

        from evennia import search_object
        results = search_object(char_name, typeclass="typeclasses.characters.Character")
        if not results:
            self.caller.msg(f"|xCharacter '{char_name}' not found.|n"); return
        target = results[0]

        door = dict(zone.get("mechanics", {}).get("door", {}))
        owners = list(door.get("owner_ids") or [])

        if action == "add":
            if target.id not in owners:
                owners.append(target.id)
                door["owner_ids"] = owners
                _save_door(room, zone_name, zone, door)
                self.caller.msg(
                    f"|w{target.db.rp_name or target.name} added as door owner for '{zone_name}'.|n"
                )
            else:
                self.caller.msg(f"|xThey're already an owner.|n")
        elif action == "remove":
            if target.id in owners:
                owners.remove(target.id)
                door["owner_ids"] = owners
                _save_door(room, zone_name, zone, door)
                self.caller.msg(
                    f"|w{target.db.rp_name or target.name} removed from door owners for '{zone_name}'.|n"
                )
            else:
                self.caller.msg(f"|xThey aren't a door owner.|n")
        else:
            self.caller.msg("|xUse 'add' or 'remove'.|n")

    def _do_msg(self, room, args):
        parts = args.split(None, 1)
        if len(parts) < 2:
            self.caller.msg(
                "|xUsage: |wdoor msg <zone> lock/knock = <text>|n"
            ); return

        zone_part = parts[0]
        rest      = parts[1]

        sub_parts = rest.split(None, 1)
        msg_type  = sub_parts[0].lower() if sub_parts else ""
        if "=" not in (sub_parts[1] if len(sub_parts) > 1 else ""):
            self.caller.msg(
                "|xUsage: |wdoor msg <zone> lock = <text>|n or "
                "|wdoor msg <zone> knock = <text>|n"
            ); return

        _, _, text = rest.partition("=")
        text = text.strip()

        zone_name, zone = _fuzzy_door_zone(room, zone_part)
        if zone_name is None:
            self.caller.msg(f"|xNo door mechanic for '{zone_part}'.|n"); return

        door = dict(zone.get("mechanics", {}).get("door", {}))

        if msg_type == "lock":
            door["lock_msg"] = text
            _save_door(room, zone_name, zone, door)
            self.caller.msg(f"|wLock message updated for '{zone_name}'.|n")
        elif msg_type == "knock":
            door["knock_room_msg"] = text
            _save_door(room, zone_name, zone, door)
            self.caller.msg(f"|wKnock message updated for '{zone_name}'.|n")
        else:
            self.caller.msg("|xUse 'lock' or 'knock' as the message type.|n")

    def _do_list(self, room, args):
        zone_name, zone = _fuzzy_door_zone(room, args)
        if zone_name is None:
            self.caller.msg(f"|xNo door mechanic found for '{args}'.|n"); return

        door = zone.get("mechanics", {}).get("door", {})
        dest_id = door.get("destination_id")
        dest_str = "not set"
        if dest_id:
            from evennia import search_object
            res = search_object(f"#{dest_id}")
            dest_str = res[0].key if res else f"#{dest_id} (missing)"

        owners = door.get("owner_ids") or []
        owner_names = []
        for oid in owners:
            from evennia import search_object
            res = search_object(f"#{oid}")
            owner_names.append(
                (res[0].db.rp_name or res[0].name) if res else f"#{oid}"
            )

        lines = [
            f"|wDoor mechanic on zone '|w{zone_name}|w':|n",
            f"  Destination : {dest_str}",
            f"  Locked      : {'|ryes|n' if door.get('locked') else '|gno|n'}",
            f"  Owners      : {', '.join(owner_names) or 'none'}",
            f"  Lock msg    : {door.get('lock_msg', '')}",
            f"  Knock msg   : {door.get('knock_room_msg', '')}",
        ]
        self.caller.msg("\n".join(lines))


# ---------------------------------------------------------------------------
# CmdLock
# ---------------------------------------------------------------------------

class CmdLock(Command):
    """
    Lock a door in the current room.

    Usage:
      lock <zone>

    You must be a Builder or listed as a door owner to lock.
    Zone names are matched fuzzily — 'lock helena door' works.
    """

    key = "lock"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("|xYou aren't in a room.|n"); return

        zone_name, zone = _fuzzy_door_zone(room, self.args)
        if zone_name is None:
            caller.msg(
                f"|xNo lockable door matching '{self.args.strip()}' found here.|n"
            ); return

        door = dict(zone.get("mechanics", {}).get("door", {}))

        if not _is_door_owner(caller, door):
            caller.msg("|xYou don't have the right to lock that door.|n"); return

        if door.get("locked"):
            caller.msg("|xThat door is already locked.|n"); return

        door["locked"] = True
        _save_door(room, zone_name, zone, door)

        char_name = caller.db.rp_name or caller.name
        caller.msg(f"|wYou lock the door.|n")
        room.msg_contents(
            f"|x{char_name} locks the door.|n", exclude=caller
        )


# ---------------------------------------------------------------------------
# CmdUnlock
# ---------------------------------------------------------------------------

class CmdUnlock(Command):
    """
    Unlock a door in the current room.

    Usage:
      unlock <zone>

    You must be a Builder or listed as a door owner to unlock.
    Zone names are matched fuzzily — 'unlock helena door' works.
    """

    key = "unlock"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("|xYou aren't in a room.|n"); return

        zone_name, zone = _fuzzy_door_zone(room, self.args)
        if zone_name is None:
            caller.msg(
                f"|xNo lockable door matching '{self.args.strip()}' found here.|n"
            ); return

        door = dict(zone.get("mechanics", {}).get("door", {}))

        if not _is_door_owner(caller, door):
            caller.msg("|xYou don't have the right to unlock that door.|n"); return

        if not door.get("locked"):
            caller.msg("|xThat door isn't locked.|n"); return

        door["locked"] = False
        _save_door(room, zone_name, zone, door)

        char_name = caller.db.rp_name or caller.name
        caller.msg(f"|wYou unlock the door.|n")
        room.msg_contents(
            f"|x{char_name} unlocks the door.|n", exclude=caller
        )


# ---------------------------------------------------------------------------
# CmdKnock
# ---------------------------------------------------------------------------

class CmdKnock(Command):
    """
    Knock on a door. People on the other side will hear it.

    Usage:
      knock <zone>
      knock helena door
      knock auria
    """

    key = "knock"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("|xYou aren't in a room.|n"); return

        zone_name, zone = _fuzzy_door_zone(room, self.args)
        if zone_name is None:
            caller.msg(
                f"|xNo door found matching '{self.args.strip()}' here.|n"
            ); return

        door = zone.get("mechanics", {}).get("door", {})
        dest_id = door.get("destination_id")
        knock_room_msg   = door.get("knock_room_msg",   "There is a knock at the door.")
        knock_caller_msg = door.get("knock_caller_msg", "You knock at the door.")

        caller.msg(f"|w{knock_caller_msg}|n")
        room.msg_contents(
            f"|x{caller.db.rp_name or caller.name} knocks on the door.|n",
            exclude=caller,
        )

        if dest_id:
            from evennia import search_object
            results = search_object(f"#{dest_id}")
            if results:
                dest_room = results[0]
                dest_room.msg_contents(f"|x{knock_room_msg}|n")
        else:
            caller.msg(
                "|x(The door hasn't been linked to a room yet — "
                "a Builder needs to run 'door set'.)|n"
            )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_DOOR_CMDS = [CmdDoor, CmdLock, CmdUnlock, CmdKnock]
