"""
commands/mechanic_commands.py

Commands for using mechanic items and interacting with zone mechanics.

    use <item> on/in <zone>   — install a mechanic item into a room zone (consumed)
    sit <zone>                — sit in a zone with a seat mechanic (position=seated)
    lay/lie <zone>            — lie on a zone with a lay mechanic (position=lying)
    kneel <zone>              — kneel on a zone with a kneel mechanic (position=kneeling)
    stand/rise                — get up from any position
    browse <zone>             — browse a zone's details (random pick shown)
    try on <detail>           — try on a wardrobe/zone detail (flavor emote to room)
    mirror                    — see your reflection in the nearest mirror detail
"""

import random
from evennia import Command


# ---------------------------------------------------------------------------
# Position helpers
# ---------------------------------------------------------------------------

# Maps db attribute name → position label
_POSITION_ATTRS = {
    "zone_seated_at":   "seated",
    "zone_lying_at":    "lying",
    "zone_kneeling_at": "kneeling",
}


def _get_position_attr(char):
    """
    Return (attr_name, room_id, zone_name) for char's current zone position,
    or (None, None, None) if not in any zone position.
    """
    for attr in _POSITION_ATTRS:
        val = getattr(char.db, attr, None)
        if val:
            room_id, zone_name = val
            return attr, room_id, zone_name
    return None, None, None


def _write_seat(room, zone_name, zone_data, seat_copy):
    """Write updated seat data back through a full dict copy for DB persistence."""
    zones    = room.db.zones or {}
    mech     = dict((zone_data.get("mechanics") or {}))
    mech["seat"] = seat_copy
    zc = dict(zone_data) if hasattr(zone_data, "items") else {}
    zc["mechanics"] = mech
    zs = dict(zones)
    zs[zone_name] = zc
    room.db.zones = zs


def _fuzzy_seat_zone(room, name, position=None):
    """
    Find a zone with a seat mechanic by fuzzy name.
    If position is given, only match zones whose seat.position matches.
    Returns (zone_name, zone_data, seat_dict) or (None, None, None).
    """
    zones = room.db.zones or {}
    name_clean = name.strip().lower()
    name_under = name_clean.replace(" ", "_")

    def _ok(zdata):
        if not hasattr(zdata, "get"):
            return False
        seat = (zdata.get("mechanics") or {}).get("seat")
        if not seat:
            return False
        if position and seat.get("position", "seated") != position:
            return False
        return True

    for candidate in (name_clean, name_under):
        if candidate in zones and _ok(zones[candidate]):
            zd = zones[candidate]
            return candidate, zd, zd["mechanics"]["seat"]

    for zname, zdata in zones.items():
        if not _ok(zdata):
            continue
        if name_clean in zname or name_under in zname:
            return zname, zdata, zdata["mechanics"]["seat"]

    return None, None, None


def _do_rise(char, silent=False):
    """
    Remove char from any zone position (seated / lying / kneeling).
    Called by stand/rise commands and automatically on room change or unpuppet.
    """
    attr, room_id, zone_name = _get_position_attr(char)
    if not attr:
        return

    setattr(char.db, attr, None)
    label    = zone_name
    position = _POSITION_ATTRS.get(attr, "seated")

    try:
        from evennia import search_object
        results = search_object(f"#{room_id}")
        room = results[0] if results else None
        if room:
            zones = room.db.zones or {}
            if zone_name in zones:
                zone = zones[zone_name]
                mechanics = zone.get("mechanics", {}) or {} if hasattr(zone, "get") else {}
                seat = mechanics.get("seat")
                if seat:
                    label    = seat.get("label", zone_name)
                    occupied = [e for e in seat.get("occupied", []) if e[0] != char.id]
                    sc = dict(seat)
                    sc["occupied"] = occupied
                    _write_seat(room, zone_name, zone, sc)
    except Exception:
        pass

    if not silent:
        char_name = char.db.rp_name or char.name
        if position == "lying":
            char.msg(f"|wYou get up from {label}.|n")
            if char.location:
                char.location.msg_contents(
                    f"|x{char_name} gets up from {label}.|n", exclude=char
                )
        elif position == "kneeling":
            char.msg("|wYou rise to your feet.|n")
            if char.location:
                char.location.msg_contents(
                    f"|x{char_name} rises from their knees.|n", exclude=char
                )
        else:
            char.msg(f"|wYou rise from {label}.|n")
            if char.location:
                char.location.msg_contents(
                    f"|x{char_name} rises from {label}.|n", exclude=char
                )


# Backward-compatible alias (imported by characters.py)
def _do_stand(char, silent=False):
    _do_rise(char, silent=silent)


def _take_position(caller, zone_arg, position, db_attr,
                   sit_msg, room_sit_msg,
                   lap_sit_msg=None, room_lap_sit_msg=None):
    """
    Generic handler for sit / lay / kneel commands.

    sit_msg / room_sit_msg : format strings with {label} and {char_name}
    lap_sit_msg            : used when entering a lap (seated only)
    """
    room = caller.location
    if not room:
        caller.msg("|xYou aren't anywhere.|n")
        return

    zone_name, zone_data, seat = _fuzzy_seat_zone(room, zone_arg, position=position)
    if zone_name is None:
        verb_map = {
            "seated":   "sit in",
            "lying":    "lie on",
            "kneeling": "kneel in",
        }
        caller.msg(
            f"|xThere's nowhere to {verb_map.get(position, 'use')} "
            f"'{zone_arg}' here.|n"
        )
        return

    current = getattr(caller.db, db_attr, None)
    if current == (room.id, zone_name):
        pos_str = {"seated": "sitting", "lying": "lying", "kneeling": "kneeling"}.get(position, position)
        caller.msg(f"|xYou're already {pos_str} there.|n")
        return

    # Auto-rise from any other position first
    attr, _, _ = _get_position_attr(caller)
    if attr:
        _do_rise(caller, silent=True)

    occupied = list(seat.get("occupied", []))
    capacity = seat.get("capacity", 2)
    label    = seat.get("label", zone_name)
    allow_lap = seat.get("allow_lap", False)

    # Lap check (seated only)
    if position == "seated" and allow_lap and lap_sit_msg:
        seat_slots = [e for e in occupied if len(e) < 3 or e[2] in ("seat", "seated")]
        lap_slots  = [e for e in occupied if len(e) >= 3 and e[2] == "lap"]
        if len(seat_slots) == 1 and len(lap_slots) == 0:
            host_name = seat_slots[0][1]
            char_name = caller.db.rp_name or caller.name
            occupied.append((caller.id, char_name, "lap"))
            sc = dict(seat)
            sc["occupied"] = occupied
            _write_seat(room, zone_name, zone_data, sc)
            setattr(caller.db, db_attr, (room.id, zone_name))
            caller.msg(lap_sit_msg.format(label=label, host_name=host_name))
            room.msg_contents(
                room_lap_sit_msg.format(
                    char_name=char_name, label=label, host_name=host_name
                ),
                exclude=caller,
            )
            return

    if len(occupied) >= capacity:
        caller.msg(f"|x{label.capitalize()} is full ({len(occupied)}/{capacity}).|n")
        return

    char_name = caller.db.rp_name or caller.name
    slot = {"seated": "seat", "lying": "lying", "kneeling": "kneeling"}.get(position, position)
    occupied.append((caller.id, char_name, slot))
    sc = dict(seat)
    sc["occupied"] = occupied
    _write_seat(room, zone_name, zone_data, sc)
    setattr(caller.db, db_attr, (room.id, zone_name))

    caller.msg(sit_msg.format(label=label, char_name=char_name))
    room.msg_contents(
        room_sit_msg.format(char_name=char_name, label=label),
        exclude=caller,
    )


# ---------------------------------------------------------------------------
# CmdUse
# ---------------------------------------------------------------------------

class CmdUse(Command):
    """
    Use an item on a zone to install its mechanic.

    Usage:
      use <item> on <zone>
      use <item> in <zone>

    The item is consumed (destroyed) on successful installation.

    Example:
      use worn cushion on bench
    """

    key = "use"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            caller.msg("|xUsage: |wuse <item> on <zone>|n")
            return

        zone_name = None
        item_name = args
        for sep in (" on ", " in "):
            if sep in args.lower():
                idx = args.lower().index(sep)
                item_name = args[:idx].strip()
                zone_name = args[idx + len(sep):].strip().lower()
                break

        matches = caller.search(item_name, location=caller, quiet=True)
        if not matches:
            caller.msg(f"|xYou don't have '{item_name}'.|n")
            return
        item = matches[0] if isinstance(matches, list) else matches

        from typeclasses.mechanic_item import MechanicItem
        if not isinstance(item, MechanicItem):
            caller.msg(f"|xYou're not sure how to use {item.key} that way.|n")
            return

        if not zone_name:
            caller.msg(
                f"|xWhat zone do you want to use {item.key} on?\n"
                f"|xUsage: |wuse {item.key} on <zone>|n"
            )
            return

        room = caller.location
        if not room:
            caller.msg("|xYou aren't in a room.|n")
            return

        success, msg = item.install_into_zone(room, zone_name, caller)
        caller.msg(msg)
        if success:
            item.delete()


# ---------------------------------------------------------------------------
# CmdSit
# ---------------------------------------------------------------------------

class CmdSit(Command):
    """
    Sit in a zone's seat.

    Usage:
      sit <zone>

    The zone must have a seat mechanic installed with position 'seated'.
    If the seat has a lap option and someone is already sitting, you'll
    settle into their lap instead.

    Example:
      sit bench
      sit chair
    """

    key = "sit"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        zone_arg = self.args.strip().lower()
        if not zone_arg:
            caller.msg("|xUsage: |wsit <zone>|n")
            return
        _take_position(
            caller, zone_arg,
            position   = "seated",
            db_attr    = "zone_seated_at",
            sit_msg         = "|wYou settle into {label}.|n",
            room_sit_msg    = "|x{char_name} settles into {label}.|n",
            lap_sit_msg     = "|wYou settle into {label}, into {host_name}'s lap.|n",
            room_lap_sit_msg= "|x{char_name} settles into {label} in {host_name}'s lap.|n",
        )


# ---------------------------------------------------------------------------
# CmdLay / CmdLie
# ---------------------------------------------------------------------------

class CmdLay(Command):
    """
    Lie down on a zone's surface.

    Usage:
      lay <zone>
      lie <zone>

    The zone must have a seat mechanic installed with position 'lying'.

    Example:
      lay bed
      lie bed
    """

    key  = "lay"
    aliases = ["lie"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        zone_arg = self.args.strip().lower()
        if not zone_arg:
            caller.msg("|xUsage: |wlay <zone>|n")
            return
        _take_position(
            caller, zone_arg,
            position     = "lying",
            db_attr      = "zone_lying_at",
            sit_msg      = "|wYou lie down on {label}.|n",
            room_sit_msg = "|x{char_name} lies down on {label}.|n",
        )


# ---------------------------------------------------------------------------
# CmdKneel
# ---------------------------------------------------------------------------

class CmdKneel(Command):
    """
    Kneel in a zone.

    Usage:
      kneel <zone>

    The zone must have a seat mechanic installed with position 'kneeling'.

    Example:
      kneel rug
    """

    key  = "kneel"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        zone_arg = self.args.strip().lower()
        if not zone_arg:
            caller.msg("|xUsage: |wkneel <zone>|n")
            return
        _take_position(
            caller, zone_arg,
            position     = "kneeling",
            db_attr      = "zone_kneeling_at",
            sit_msg      = "|wYou kneel on {label}.|n",
            room_sit_msg = "|x{char_name} kneels on {label}.|n",
        )


# ---------------------------------------------------------------------------
# CmdStand / CmdRise
# ---------------------------------------------------------------------------

class CmdStand(Command):
    """
    Stand up from any zone position (seated, lying, or kneeling).

    Usage:
      stand
      rise
    """

    key     = "stand"
    aliases = ["rise"]
    locks   = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        attr, _, _ = _get_position_attr(caller)
        if not attr:
            caller.msg("|xYou aren't in any position to get up from.|n")
            return
        _do_rise(caller)


# ---------------------------------------------------------------------------
# CmdBrowse
# ---------------------------------------------------------------------------

class CmdBrowse(Command):
    """
    Browse a zone's details, getting a random item description.

    Usage:
      browse <zone>

    Useful for zones like wardrobes or drawers with multiple detail entries.
    Each browse may show something different.

    Example:
      browse wardrobe
    """

    key   = "browse"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller   = self.caller
        zone_arg = self.args.strip().lower()

        if not zone_arg:
            caller.msg("|xUsage: |wbrowse <zone>|n")
            return

        room = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        zones = room.db.zones or {}
        name_under = zone_arg.replace(" ", "_")

        zone_name = None
        zone_data = None
        for candidate in (zone_arg, name_under):
            if candidate in zones:
                zone_name = candidate
                zone_data = zones[candidate]
                break
        if zone_name is None:
            for zname, zdata in zones.items():
                if zone_arg in zname or name_under in zname:
                    zone_name = zname
                    zone_data = zdata
                    break

        if zone_name is None or not hasattr(zone_data, "get"):
            caller.msg(f"|xYou don't see anywhere to browse called '{zone_arg}'.|n")
            return

        details = zone_data.get("details") or {}
        if not details:
            caller.msg(
                f"|xYou look through {zone_name} but there's nothing specific to find.|n"
            )
            return

        key, text = random.choice(list(details.items()))
        label     = zone_data.get("desc", "").split(".")[0] or zone_name
        char_name = caller.db.rp_name or caller.name

        caller.msg(f"|xYou look through {zone_name}:|n\n{text}")
        room.msg_contents(
            f"|x{char_name} looks through {zone_name}.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# CmdTryOn
# ---------------------------------------------------------------------------

class CmdTryOn(Command):
    """
    Try on something from a zone's details — a dress, a collar, anything
    described in a wardrobe or similar zone.

    Usage:
      try on <detail>
      try on <zone>/<detail>

    Shows you a private flavor description of wearing the item, and sends
    a brief emote to the room.

    Example:
      try on red dress
      try on wardrobe/dresses
    """

    key   = "try on"
    aliases = ["tryon"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller   = self.caller
        args     = self.args.strip()

        if not args:
            caller.msg("|xUsage: |wtry on <detail>|n")
            return

        room = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        # Try to find the detail across zones
        from commands.interact_commands import _find_detail_in_zones
        zone_name, dkey, dtext = _find_detail_in_zones(room, args)

        if dtext is None:
            caller.msg(f"|xYou don't see '{args}' to try on.|n")
            return

        char_name = caller.db.rp_name or caller.name

        caller.msg(
            f"|xYou hold {dkey.replace('_', ' ')} against yourself, "
            f"getting a sense of it:|n\n{dtext}"
        )
        room.msg_contents(
            f"|x{char_name} holds something from {zone_name} up, "
            f"considering it.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# CmdMirror
# ---------------------------------------------------------------------------

class CmdMirror(Command):
    """
    Look at yourself in a mirror.

    Usage:
      mirror

    Finds the nearest mirror detail in the current room's zones and
    shows your own description reflected back.

    Example:
      mirror
    """

    key   = "mirror"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        # Find a detail with 'mirror' in its key across all zones
        zones = room.db.zones or {}
        mirror_zone = None
        for zone_name, zone_data in zones.items():
            if not hasattr(zone_data, "get"):
                continue
            details = zone_data.get("details") or {}
            for dkey in details:
                if "mirror" in dkey:
                    mirror_zone = zone_name
                    break
            if mirror_zone:
                break

        if not mirror_zone:
            caller.msg("|xThere's no mirror here.|n")
            return

        desc      = caller.db.desc or caller.db.rp_desc or "(no description set)"
        char_name = caller.db.rp_name or caller.name

        caller.msg(
            f"|xThe mirror shows you:|n\n"
            f"|w{char_name}|n\n"
            f"{desc}"
        )
        room.msg_contents(
            f"|x{char_name} studies their reflection.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# CmdInscribe
# ---------------------------------------------------------------------------

class CmdInscribe(Command):
    """
    Leave a mark on an inscribable zone.

    Usage:
      inscribe <zone> = <text>

    The zone must have inscribing enabled by a Builder
    (roomzone inscribe/enable <zone>). Inscriptions are
    permanent and visible through 'study <zone>'.

    Example:
      inscribe east = The night Helena found the wolves.
    """

    key   = "inscribe"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        args = self.args.strip()
        if "=" not in args:
            caller.msg("|xUsage: |winscribe <zone> = <text>|n")
            return

        zone_arg, _, text = args.partition("=")
        zone_arg = zone_arg.strip().lower()
        text     = text.strip()

        if not zone_arg or not text:
            caller.msg("|xUsage: |winscribe <zone> = <text>|n")
            return

        zones      = room.db.zones or {}
        name_under = zone_arg.replace(" ", "_")

        zone_name = None
        zone_data = None
        for candidate in (zone_arg, name_under):
            if candidate in zones:
                zone_name = candidate
                zone_data = zones[candidate]
                break
        if zone_name is None:
            for zname, zdata in zones.items():
                if zone_arg in zname or name_under in zname:
                    zone_name = zname
                    zone_data = zdata
                    break

        if zone_name is None or not hasattr(zone_data, "get"):
            caller.msg(f"|xYou don't see '{zone_arg}' here.|n")
            return

        if not zone_data.get("inscribable"):
            caller.msg(
                f"|xThe surface here doesn't lend itself to being marked.|n"
            )
            return

        char_name    = caller.db.rp_name or caller.name
        inscriptions = list(zone_data.get("inscriptions", []) or [])
        entry        = f"|x{text}|n  — |w{char_name}|n"
        inscriptions.append(entry)

        # Write back via full dict copy
        zc = dict(zone_data)
        zc["inscriptions"] = inscriptions
        zs = dict(zones)
        zs[zone_name] = zc
        room.db.zones = zs

        caller.msg(f"|wYou add your mark to {zone_name}.|n")
        room.msg_contents(
            f"|x{char_name} takes a moment to leave something on {zone_name}.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# CmdPour
# ---------------------------------------------------------------------------

class CmdPour(Command):
    """
    Pour a drink from a zone with a bar mechanic.

    Usage:
      pour <drink>
      pour <drink> from <zone>

    The zone must have drinks configured by a Builder
    (roomzone bar <zone> + <drink name>).

    Example:
      pour bourbon
      pour beer from east
    """

    key   = "pour"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        args = self.args.strip()
        if not args:
            caller.msg("|xUsage: |wpour <drink>|n")
            return

        zone_arg  = None
        drink_arg = args
        if " from " in args.lower():
            idx       = args.lower().index(" from ")
            drink_arg = args[:idx].strip()
            zone_arg  = args[idx + 6:].strip().lower()

        drink_lower = drink_arg.lower()

        zones = room.db.zones or {}

        # Find zone with bar_drinks containing the drink
        found_zone  = None
        found_drink = None
        zone_name_f = None

        def _check_zone(zname, zdata):
            if not hasattr(zdata, "get"):
                return False, None
            drinks = zdata.get("bar_drinks") or []
            for d in drinks:
                if drink_lower in d.lower() or d.lower() in drink_lower:
                    return True, d
            return False, None

        if zone_arg:
            name_under = zone_arg.replace(" ", "_")
            for candidate in (zone_arg, name_under):
                if candidate in zones:
                    ok, d = _check_zone(candidate, zones[candidate])
                    if ok:
                        found_zone  = zones[candidate]
                        zone_name_f = candidate
                        found_drink = d
                        break
        else:
            for zname, zdata in zones.items():
                ok, d = _check_zone(zname, zdata)
                if ok:
                    found_zone  = zdata
                    zone_name_f = zname
                    found_drink = d
                    break

        if not found_drink:
            if zone_arg:
                caller.msg(f"|xThe bar doesn't have '{drink_arg}'.|n")
            else:
                caller.msg(
                    f"|xYou don't see '{drink_arg}' behind any of the bars here.|n"
                )
            return

        label     = (found_zone.get("mechanics") or {}).get("seat", {}).get("label") \
                    or zone_name_f
        char_name = caller.db.rp_name or caller.name

        caller.msg(
            f"|wYou pour {found_drink} at {label} "
            f"and settle it in front of you.|n"
        )
        room.msg_contents(
            f"|x{char_name} pours something at {label}.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# CmdWatch / CmdUnwatch
# ---------------------------------------------------------------------------

class CmdWatch(Command):
    """
    Direct your attention toward a person in the room.

    Usage:
      watch <person>

    Others will see that you're watching them. Your attention
    is visible in the room description.

    Example:
      watch Auria
    """

    key   = "watch"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        args = self.args.strip()
        if not args:
            caller.msg("|xUsage: |wwatch <person>|n")
            return

        target = caller.search(args, location=room)
        if not target:
            return

        if target == caller:
            caller.msg("|xYou're already plenty aware of yourself.|n")
            return

        char_name = caller.db.rp_name or caller.name
        tgt_name  = target.db.rp_name if hasattr(target.db, "rp_name") else target.name

        caller.db.zone_watching = target.id
        caller.msg(f"|wYou settle your attention on {tgt_name}.|n")
        target.msg(f"|x{char_name} is watching you.|n")
        room.msg_contents(
            f"|x{char_name}'s attention settles on {tgt_name}.|n",
            exclude=[caller, target],
        )


class CmdUnwatch(Command):
    """
    Stop watching whoever you're currently watching.

    Usage:
      unwatch

    Clears your current focus.
    """

    key   = "unwatch"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        watching_id = getattr(caller.db, "zone_watching", None)
        if not watching_id:
            caller.msg("|xYou aren't watching anyone in particular.|n")
            return

        char_name = caller.db.rp_name or caller.name
        tgt_name  = "them"

        # Try to get the name for the message
        if caller.location:
            for obj in caller.location.contents:
                if hasattr(obj, "id") and obj.id == watching_id:
                    tgt_name = obj.db.rp_name if hasattr(obj.db, "rp_name") else obj.name
                    break

        caller.db.zone_watching = None
        caller.msg(f"|wYou let your attention drift away from {tgt_name}.|n")
        if caller.location:
            caller.location.msg_contents(
                f"|x{char_name}'s attention moves on.|n",
                exclude=caller,
            )


# ---------------------------------------------------------------------------
# CmdPlay (stub — full card game implementations coming later)
# ---------------------------------------------------------------------------

class CmdPlay(Command):
    """
    Play a game available in this room.

    Usage:
      play <game>
      play <game> in <zone>
      play                     — list available games

    Games are configured by Builders with:
      roomzone game <zone> + <game name>

    Example:
      play cards
      play cah in center
    """

    key   = "play"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        args = self.args.strip()

        # No args — list available games
        if not args:
            zones  = room.db.zones or {}
            all_games = []
            for zname, zdata in zones.items():
                if not hasattr(zdata, "get"):
                    continue
                for g in (zdata.get("games") or []):
                    all_games.append((zname, g))
            if not all_games:
                caller.msg("|xThere are no games set up here.|n")
            else:
                lines = ["|wAvailable games:|n"]
                for zname, g in all_games:
                    lines.append(f"  |w{g}|n |x(in {zname})|n")
                caller.msg("\n".join(lines))
            return

        zone_arg = None
        game_arg = args
        if " in " in args.lower():
            idx      = args.lower().index(" in ")
            game_arg = args[:idx].strip()
            zone_arg = args[idx + 4:].strip().lower()

        game_lower = game_arg.lower()
        zones      = room.db.zones or {}

        found_zone = None
        found_game = None
        zone_name_f = None

        def _check(zname, zdata):
            if not hasattr(zdata, "get"):
                return False, None
            for g in (zdata.get("games") or []):
                if game_lower in g.lower() or g.lower() in game_lower:
                    return True, g
            return False, None

        if zone_arg:
            name_under = zone_arg.replace(" ", "_")
            for candidate in (zone_arg, name_under):
                if candidate in zones:
                    ok, g = _check(candidate, zones[candidate])
                    if ok:
                        found_zone  = zones[candidate]
                        zone_name_f = candidate
                        found_game  = g
                        break
        else:
            for zname, zdata in zones.items():
                ok, g = _check(zname, zdata)
                if ok:
                    found_zone  = zdata
                    zone_name_f = zname
                    found_game  = g
                    break

        if not found_game:
            caller.msg(
                f"|xNo game called '{game_arg}' is set up here.\n"
                f"|xType |wplay|n with no arguments to see available games.|n"
            )
            return

        char_name = caller.db.rp_name or caller.name
        caller.msg(
            f"|xFull {found_game} rules aren't implemented yet — "
            f"coming soon. For now, use posed actions to play freeform.|n"
        )
        caller.location.msg_contents(
            f"|x{char_name} moves to play {found_game}.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_MECHANIC_CMDS = [
    CmdUse, CmdSit, CmdLay, CmdKneel, CmdStand,
    CmdBrowse, CmdTryOn, CmdMirror,
    CmdInscribe, CmdPour, CmdWatch, CmdUnwatch, CmdPlay,
]
