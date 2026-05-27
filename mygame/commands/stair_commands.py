"""
commands/stair_commands.py

Commands for managing creaking stair mechanics on room zones.

    stair set <zone> = <exit name>      — link stair zone to an exit
    stair add <zone> = #<room_dbref>    — add a listener room
    stair remove <zone> = #<room_dbref> — remove a listener room
    stair list <zone>                   — show configuration
    stair msg <zone> up = <text>        — set ascending creak message
    stair msg <zone> down = <text>      — set descending creak message

Requires Builder permission.
The at_post_move hook in characters.py fires the actual notifications.
"""

from evennia import default_cmds


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fuzzy_stair_zone(room, name):
    """Find a zone with a stair mechanic by fuzzy name."""
    zones = room.db.zones or {}
    name_clean = name.strip().lower()
    name_under = name_clean.replace(" ", "_")

    for candidate in (name_clean, name_under):
        if candidate in zones:
            z = zones[candidate]
            if hasattr(z, "get") and (z.get("mechanics") or {}).get("stair"):
                return candidate, z

    for zname, zdata in zones.items():
        if not hasattr(zdata, "get"):
            continue
        if not (zdata.get("mechanics") or {}).get("stair"):
            continue
        if name_clean in zname or name_under in zname:
            return zname, zdata

    return None, None


def _save_stair(room, zone_name, zone, stair_data):
    mech = dict((zone.get("mechanics") or {}))
    mech["stair"] = stair_data
    zone_copy = dict(zone) if hasattr(zone, "items") else {}
    zone_copy["mechanics"] = mech
    zones_copy = dict(room.db.zones or {})
    zones_copy[zone_name] = zone_copy
    room.db.zones = zones_copy


def fire_stair_creak(char, source_room, dest_room):
    """
    Called from at_post_move. Checks source and dest rooms for stair mechanics
    and fires creak notifications to listener rooms.

    Args:
        char        : the moving character
        source_room : the room they moved FROM
        dest_room   : the room they moved TO (char.location)
    """
    if not source_room or not dest_room:
        return

    # Check source room zones for a stair going TO dest
    _check_and_fire(
        char, source_room, dest_room,
        direction="ascending",
    )
    # Check dest room zones for a stair going FROM dest back to source
    # (this fires when coming DOWN the stairs)
    _check_and_fire(
        char, dest_room, source_room,
        direction="descending",
    )


def _check_and_fire(char, stair_room, other_room, direction):
    """
    Look for a stair mechanic in stair_room whose destination_id matches
    other_room. If found and direction matches, send creak to listener rooms.
    """
    zones = stair_room.db.zones or {}
    for zone_name, zone_data in zones.items():
        if not hasattr(zone_data, "get"):
            continue
        stair = (zone_data.get("mechanics") or {}).get("stair")
        if not stair:
            continue

        dest_id = stair.get("destination_id")
        # Only fire if:
        # - destination_id matches the other room (ascending: source→dest matches stair dest)
        # - OR destination_id is not set (fire on any movement through this zone's room)
        if dest_id and dest_id != other_room.id:
            continue

        # Determine messages
        if direction == "ascending":
            room_msg  = stair.get("ascending_msg",  "The stairs creak — someone is on their way up.")
            mover_msg = stair.get("mover_ascending_msg", "The stairs creak as you ascend.")
        else:
            room_msg  = stair.get("descending_msg",  "The stairs creak — someone is coming down.")
            mover_msg = stair.get("mover_descending_msg", "The stairs creak beneath your feet.")

        # Notify the mover
        char.msg(f"|x{mover_msg}|n")

        # Notify all listener rooms
        listener_ids = stair.get("listener_room_ids") or []
        from evennia import search_object
        for room_id in listener_ids:
            try:
                results = search_object(f"#{room_id}")
                if results:
                    results[0].msg_contents(f"|x{room_msg}|n")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# CmdStair
# ---------------------------------------------------------------------------

class CmdStair(default_cmds.MuxCommand):
    """
    Manage creaking stair mechanics on room zones.

    Usage:
      stair set <zone> = <exit name>      — link the stair zone to an exit
      stair add <zone> = #<room_dbref>    — add a listener room
      stair remove <zone> = #<room_dbref> — remove a listener room
      stair list <zone>                   — show current configuration
      stair msg <zone> up = <text>        — set the ascending creak message
      stair msg <zone> down = <text>      — set the descending creak message

    Requires Builder permission.
    """

    key = "stair"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("|xYou aren't in a room.|n"); return

        args = self.args.strip()
        if not args:
            caller.msg("|xUsage: |wstair set/add/remove/list/msg <zone> ...|n"); return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest   = parts[1].strip() if len(parts) > 1 else ""

        dispatch = {
            "set":    self._do_set,
            "add":    self._do_add,
            "remove": self._do_remove,
            "list":   self._do_list,
            "msg":    self._do_msg,
        }
        handler = dispatch.get(subcmd)
        if handler is None:
            caller.msg(f"|xUnknown stair subcommand '{subcmd}'.|n"); return
        handler(room, rest)

    def _do_set(self, room, args):
        if "=" not in args:
            self.caller.msg("|xUsage: |wstair set <zone> = <exit name>|n"); return
        zone_part, _, exit_name = args.partition("=")
        zone_name, zone = _fuzzy_stair_zone(room, zone_part.strip())
        if zone_name is None:
            self.caller.msg(f"|xNo stair mechanic found for '{zone_part.strip()}'.|n"); return

        exit_obj = None
        for ex in room.exits:
            if (ex.key.lower() == exit_name.strip().lower() or
                    exit_name.strip().lower() in [a.lower() for a in (ex.aliases.all() or [])]):
                exit_obj = ex
                break

        if not exit_obj:
            self.caller.msg(
                f"|xNo exit named '{exit_name.strip()}' found.\n"
                f"Available exits: {', '.join(e.key for e in room.exits) or 'none'}|n"
            ); return

        stair = dict(zone.get("mechanics", {}).get("stair", {}))
        stair["destination_id"] = exit_obj.destination.id
        _save_stair(room, zone_name, zone, stair)
        self.caller.msg(
            f"|wStair zone '|w{zone_name}|w' linked to exit "
            f"'|w{exit_obj.key}|w' → {exit_obj.destination.key}.|n\n"
            f"|xUse |wstair add {zone_name} = #<dbref>|n to add listener rooms.|n"
        )

    def _do_add(self, room, args):
        if "=" not in args:
            self.caller.msg("|xUsage: |wstair add <zone> = #<room_dbref>|n"); return
        zone_part, _, dbref = args.partition("=")
        zone_name, zone = _fuzzy_stair_zone(room, zone_part.strip())
        if zone_name is None:
            self.caller.msg(f"|xNo stair mechanic for '{zone_part.strip()}'.|n"); return

        dbref = dbref.strip().lstrip("#")
        from evennia import search_object
        try:
            results = search_object(f"#{dbref}")
        except Exception:
            results = []
        if not results:
            self.caller.msg(f"|xRoom #{dbref} not found.|n"); return
        target_room = results[0]

        stair = dict(zone.get("mechanics", {}).get("stair", {}))
        listeners = list(stair.get("listener_room_ids") or [])
        if target_room.id in listeners:
            self.caller.msg(f"|xRoom '{target_room.key}' is already a listener.|n"); return
        listeners.append(target_room.id)
        stair["listener_room_ids"] = listeners
        _save_stair(room, zone_name, zone, stair)
        self.caller.msg(
            f"|wRoom '|w{target_room.key}|w' (#{target_room.id}) added as stair listener.|n"
        )

    def _do_remove(self, room, args):
        if "=" not in args:
            self.caller.msg("|xUsage: |wstair remove <zone> = #<room_dbref>|n"); return
        zone_part, _, dbref = args.partition("=")
        zone_name, zone = _fuzzy_stair_zone(room, zone_part.strip())
        if zone_name is None:
            self.caller.msg(f"|xNo stair mechanic for '{zone_part.strip()}'.|n"); return

        dbref = dbref.strip().lstrip("#")
        try:
            target_id = int(dbref)
        except ValueError:
            self.caller.msg(f"|xInvalid dbref '{dbref}'.|n"); return

        stair = dict(zone.get("mechanics", {}).get("stair", {}))
        listeners = list(stair.get("listener_room_ids") or [])
        if target_id not in listeners:
            self.caller.msg(f"|xRoom #{target_id} isn't in the listener list.|n"); return
        listeners.remove(target_id)
        stair["listener_room_ids"] = listeners
        _save_stair(room, zone_name, zone, stair)
        self.caller.msg(f"|wRoom #{target_id} removed from stair listeners.|n")

    def _do_list(self, room, args):
        zone_name, zone = _fuzzy_stair_zone(room, args)
        if zone_name is None:
            self.caller.msg(f"|xNo stair mechanic found for '{args}'.|n"); return

        stair = zone.get("mechanics", {}).get("stair", {})
        dest_id = stair.get("destination_id")
        dest_str = "not set"
        if dest_id:
            from evennia import search_object
            res = search_object(f"#{dest_id}")
            dest_str = f"{res[0].key} (#{dest_id})" if res else f"#{dest_id} (missing)"

        listener_ids = stair.get("listener_room_ids") or []
        listener_strs = []
        from evennia import search_object
        for rid in listener_ids:
            res = search_object(f"#{rid}")
            listener_strs.append(
                f"{res[0].key} (#{rid})" if res else f"#{rid} (missing)"
            )

        lines = [
            f"|wStair mechanic on zone '|w{zone_name}|w':|n",
            f"  Destination  : {dest_str}",
            f"  Listeners    : {', '.join(listener_strs) or 'none'}",
            f"  Ascending    : {stair.get('ascending_msg', '')}",
            f"  Descending   : {stair.get('descending_msg', '')}",
            f"  Mover (up)   : {stair.get('mover_ascending_msg', '')}",
            f"  Mover (down) : {stair.get('mover_descending_msg', '')}",
        ]
        self.caller.msg("\n".join(lines))

    def _do_msg(self, room, args):
        parts = args.split(None, 1)
        if len(parts) < 2 or "=" not in parts[1]:
            self.caller.msg(
                "|xUsage: |wstair msg <zone> up/down = <text>|n"
            ); return

        zone_part = parts[0]
        rest      = parts[1]
        dir_part, _, text = rest.partition("=")
        direction = dir_part.strip().lower()
        text      = text.strip()

        zone_name, zone = _fuzzy_stair_zone(room, zone_part)
        if zone_name is None:
            self.caller.msg(f"|xNo stair mechanic for '{zone_part}'.|n"); return

        stair = dict(zone.get("mechanics", {}).get("stair", {}))
        if direction == "up":
            stair["ascending_msg"] = text
        elif direction == "down":
            stair["descending_msg"] = text
        elif direction in ("mover_up", "moverup"):
            stair["mover_ascending_msg"] = text
        elif direction in ("mover_down", "moverdown"):
            stair["mover_descending_msg"] = text
        else:
            self.caller.msg(
                "|xUse 'up', 'down', 'mover_up', or 'mover_down' as direction.|n"
            ); return

        _save_stair(room, zone_name, zone, stair)
        self.caller.msg(f"|wStair message ({direction}) updated for '{zone_name}'.|n")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_STAIR_CMDS = [CmdStair]
