"""
commands/roomzone_commands.py

CmdRoomZone — manage spatial zones, details, and mechanic hooks on rooms.

Available to:
  - Any character with Builder permission (anywhere)
  - A housing owner in any room they own (db.housing_owner_id == caller.id)

Usage:
  roomzone                              — list all zones and details
  roomzone desc <zone> = <text>         — set zone description
  roomzone detail <zone>/<name> = <text>  — add or update a detail
  roomzone detail/rm <zone>/<name>      — remove a detail
  roomzone add <name> [in <parent>]     — add a new subzone
  roomzone rm <name>                    — remove a zone (directionals protected)
  roomzone scent <zone> = <text>        — set zone scent string
  roomzone scent/clear <zone>           — clear zone scent
  roomzone ambient <zone> + <text>      — append an ambient message to a zone
  roomzone ambient/clear <zone>         — clear all ambients for a zone
  roomzone token <zone>                 — display the {zone:name} token to copy

Zone tokens can be embedded in a room's desc with 'desc set' to render
inline.  Zones with content but no token are auto-appended below the main
description.

Subzones can be nested to any depth. Directional roots (north/south/east/
west/up/down/center) are protected and cannot be removed.
"""

from evennia import default_cmds
from evennia import CmdSet


# Protected zone names — cannot be removed
_PROTECTED_ZONES = frozenset(
    {"north", "south", "east", "west", "up", "down", "center"}
)

# Maximum subzone nesting depth (soft warning, not a hard block)
_DEPTH_WARN = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_zone(parent=None):
    """Return a fresh empty zone dict."""
    return {
        "desc":        "",
        "details":     {},
        "scent":       None,
        "ambient":     [],
        "contents":    [],
        "parent":      parent,
        "mechanics":   {},
        "scripts":     [],
        "event_hooks": {},
    }


def _get_zone_depth(zones, zone_name, _seen=None):
    """
    Return how many levels deep zone_name is (0 = root, 1 = one level in...).
    Prevents infinite loops from bad data via _seen set.
    """
    if _seen is None:
        _seen = set()
    if zone_name in _seen:
        return 0
    _seen.add(zone_name)
    zone = zones.get(zone_name)
    if not zone or not hasattr(zone, "get"):
        return 0
    parent = zone.get("parent")
    if not parent:
        return 0
    return 1 + _get_zone_depth(zones, parent, _seen)


def _build_zone_tree(zones):
    """
    Return a list of (indent_level, zone_name) tuples for display,
    sorted parent-before-child, children sorted alphabetically.
    """
    # Build parent → [children] map
    children = {}
    for name, data in zones.items():
        parent = data.get("parent") if hasattr(data, "get") else None
        if parent not in children:
            children[parent] = []
        children[parent].append(name)

    result = []

    def _walk(name, level):
        result.append((level, name))
        for child in sorted(children.get(name, [])):
            _walk(child, level + 1)

    for root in sorted(children.get(None, [])):
        _walk(root, 0)

    return result


# ---------------------------------------------------------------------------
# CmdRoomZone
# ---------------------------------------------------------------------------

class CmdRoomZone(default_cmds.MuxCommand):
    """
    Manage spatial zones on the current room.

    Usage:
      roomzone                              — list all zones and details
      roomzone desc <zone> = <text>         — set zone description
      roomzone detail <zone>/<name> = <text>  — add or update a detail
      roomzone detail/rm <zone>/<name>      — remove a detail
      roomzone add <name> [in <parent>]     — add a new subzone
      roomzone rm <name>                    — remove a zone (roots protected)
      roomzone scent <zone> = <text>        — set zone scent
      roomzone scent/clear <zone>           — clear zone scent
      roomzone ambient <zone> + <text>      — add ambient line to a zone
      roomzone ambient/clear <zone>         — clear all ambients in a zone
      roomzone token <zone>                 — show the {zone:name} embed token

    Zones with descriptions can be embedded in the room desc using the
    token printed by 'roomzone token'. Zones with content but no embedded
    token are auto-appended below the description.

    Details are purely text — they respond to 'look <name>' and 'examine
    <name>' without needing to be physical objects. Use 'look <name> in
    <zone>' to disambiguate when the same name appears in multiple zones.
    """

    key     = "roomzone"
    aliases = ["rz"]
    locks   = "cmd:all()"  # permission check is done inside func()
    help_category = "Building"

    def _check_perm(self):
        """
        Return True if the caller may use this command here.
        False + error message if not.
        """
        caller = self.caller
        if caller.check_permstring("Builder"):
            return True
        room = caller.location
        if room and getattr(room.db, "housing_owner_id", None) == caller.id:
            return True
        caller.msg(
            "|xYou don't have permission to edit zones here. "
            "Builders and the room owner can use this command.|n"
        )
        return False

    def _get_zones(self):
        """Return the room's zone dict, initialising if missing."""
        room = self.caller.location
        if not room:
            return None, None
        zones = room.db.zones
        if zones is None:
            if hasattr(room, "_build_default_zones"):
                room.db.zones = room._build_default_zones()
            else:
                room.db.zones = {}
            zones = room.db.zones
        return room, zones

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    # All valid subcommand names (including compound ones)
    _SUBCMDS = frozenset({
        "list", "desc", "detail", "detail/rm",
        "add", "rm", "scent", "scent/clear",
        "ambient", "ambient/clear", "token",
    })

    def func(self):
        if not self._check_perm():
            return

        # Support both styles:
        #   roomzone/desc north = text   (slash-switch style)
        #   roomzone desc north = text   (space style — more natural)
        if self.switches:
            # Slash-switch: join multiple switches to handle "detail/rm"
            switch = "/".join(s.lower() for s in self.switches)
            args   = self.args.strip()
        else:
            raw = self.args.strip()
            # Try to pull a subcommand from the first word(s) of args.
            # Check two-word compounds first (e.g. "detail/rm", "scent/clear")
            # then single words.
            switch = ""
            args   = raw
            if raw:
                first, _, rest = raw.partition(" ")
                first = first.lower()
                if first in self._SUBCMDS:
                    switch = first
                    args   = rest.strip()

        # Update self.args so every handler gets the trimmed remainder
        self.args = args

        # No switch + no args → list
        if not switch and not args:
            self._do_list()
            return

        dispatch = {
            "":               self._do_list_or_error,
            "list":           self._do_list,
            "desc":           self._do_desc,
            "detail":         self._do_detail,
            "detail/rm":      self._do_detail_rm,
            "add":            self._do_add,
            "rm":             self._do_rm,
            "scent":          self._do_scent,
            "scent/clear":    self._do_scent_clear,
            "ambient":        self._do_ambient,
            "ambient/clear":  self._do_ambient_clear,
            "token":          self._do_token,
        }

        handler = dispatch.get(switch)
        if handler is None:
            self.caller.msg(
                f"|xUnknown roomzone subcommand: '{switch}'. "
                f"Type |wroomzone|n to see usage.|n"
            )
            return
        handler()

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def _do_list(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n")
            return

        if not zones:
            self.caller.msg(
                "|xThis room has no zones yet. "
                "Use |wroomzone add <name>|n to create one.|n"
            )
            return

        lines = [f"|wZones on {room.key}|n"]
        for level, zone_name in _build_zone_tree(zones):
            zone = zones.get(zone_name)
            if not hasattr(zone, "get"):
                continue
            indent  = "  " * level
            prefix  = "├─ " if level > 0 else ""
            has_desc    = bool(zone.get("desc", ""))
            has_details = bool(zone.get("details"))
            has_scent   = bool(zone.get("scent"))
            has_ambient = bool(zone.get("ambient"))
            flags = []
            if has_desc:    flags.append("|wdesc|n")
            if has_details: flags.append(f"|w{len(zone['details'])} detail(s)|n")
            if has_scent:   flags.append("|wscent|n")
            if has_ambient: flags.append(f"|w{len(zone['ambient'])} ambient|n")
            flag_str = "  |x[" + ", ".join(flags) + "]|n" if flags else ""
            lines.append(f"  {indent}{prefix}|c{zone_name}|n{flag_str}")

            # List details inline
            details = zone.get("details", {}) or {}
            for dname in sorted(details.keys()):
                lines.append(f"  {indent}    |x· {dname}|n")

        self.caller.msg("\n".join(lines))

    def _do_list_or_error(self):
        """Called when switch is empty but args present — probably a typo."""
        self.caller.msg(
            "|xUsage: |wroomzone <switch> <args>|n. "
            "Type |wroomzone|n for a list of zones."
        )

    # ------------------------------------------------------------------
    # desc
    # ------------------------------------------------------------------

    def _do_desc(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "=" not in self.args:
            self.caller.msg(
                "|xUsage: |wroomzone desc <zone> = <text>|n"
            ); return

        zone_name, _, text = self.args.partition("=")
        zone_name = zone_name.strip().lower()
        text      = text.strip()

        if zone_name not in zones:
            self.caller.msg(
                f"|xZone '{zone_name}' doesn't exist. "
                f"Use |wroomzone add {zone_name}|n to create it.|n"
            ); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        zone["desc"] = text
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wZone '{zone_name}' desc set.|n\n"
            f"|xEmbed with: |w{{zone:{zone_name}}}|n"
        )

    # ------------------------------------------------------------------
    # detail (add/update)
    # ------------------------------------------------------------------

    def _do_detail(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "=" not in self.args or "/" not in self.args.split("=")[0]:
            self.caller.msg(
                "|xUsage: |wroomzone detail <zone>/<name> = <text>|n"
            ); return

        lhs, _, text = self.args.partition("=")
        lhs  = lhs.strip()
        text = text.strip()

        if "/" not in lhs:
            self.caller.msg(
                "|xUsage: |wroomzone detail <zone>/<name> = <text>|n"
            ); return

        zone_name, _, detail_name = lhs.partition("/")
        zone_name   = zone_name.strip().lower()
        detail_name = detail_name.strip().lower()

        if zone_name not in zones:
            self.caller.msg(
                f"|xZone '{zone_name}' doesn't exist. "
                f"Use |wroomzone add {zone_name}|n first.|n"
            ); return

        if not detail_name:
            self.caller.msg("|xDetail name cannot be empty.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        details = dict(zone.get("details", {}) or {})
        details[detail_name] = text
        zone["details"] = details
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wDetail '{detail_name}' set in zone '{zone_name}'.|n\n"
            f"|xPlayers can find it with: |wlook {detail_name}|n "
            f"or |wlook {detail_name} in {zone_name}|n"
        )

    # ------------------------------------------------------------------
    # detail/rm
    # ------------------------------------------------------------------

    def _do_detail_rm(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "/" not in self.args:
            self.caller.msg(
                "|xUsage: |wroomzone detail/rm <zone>/<name>|n"
            ); return

        zone_name, _, detail_name = self.args.partition("/")
        zone_name   = zone_name.strip().lower()
        detail_name = detail_name.strip().lower()

        if zone_name not in zones:
            self.caller.msg(
                f"|xZone '{zone_name}' not found.|n"
            ); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        details = dict(zone.get("details", {}) or {})

        if detail_name not in details:
            self.caller.msg(
                f"|xNo detail '{detail_name}' in zone '{zone_name}'.|n"
            ); return

        del details[detail_name]
        zone["details"] = details
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wDetail '{detail_name}' removed from zone '{zone_name}'.|n"
        )

    # ------------------------------------------------------------------
    # add
    # ------------------------------------------------------------------

    def _do_add(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        args = self.args.strip().lower()
        parent = None

        # Parse optional 'in <parent>'
        if " in " in args:
            parts  = args.rsplit(" in ", 1)
            args   = parts[0].strip()
            parent = parts[1].strip()

        zone_name = args.replace(" ", "_")

        if not zone_name:
            self.caller.msg("|xUsage: |wroomzone add <name> [in <parent>]|n"); return

        if zone_name in zones:
            self.caller.msg(
                f"|xZone '{zone_name}' already exists.|n"
            ); return

        if parent and parent not in zones:
            self.caller.msg(
                f"|xParent zone '{parent}' doesn't exist.|n"
            ); return

        # Depth warning
        if parent:
            depth = _get_zone_depth(zones, parent) + 1
            if depth >= _DEPTH_WARN:
                self.caller.msg(
                    f"|y[Note: this zone will be {depth + 1} levels deep. "
                    f"That's fine, but deep nesting can make name lookups "
                    f"ambiguous. Consider 'look <name> in <zone>' for "
                    f"disambiguation.]|n"
                )

        zones[zone_name] = _blank_zone(parent=parent)
        room.db.zones = zones

        loc_str = f" (in '{parent}')" if parent else ""
        self.caller.msg(
            f"|wZone '{zone_name}'{loc_str} created.|n\n"
            f"|xSet its description with: "
            f"|wroomzone desc {zone_name} = <text>|n"
        )

    # ------------------------------------------------------------------
    # rm
    # ------------------------------------------------------------------

    def _do_rm(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()

        if not zone_name:
            self.caller.msg("|xUsage: |wroomzone rm <zone>|n"); return

        if zone_name in _PROTECTED_ZONES:
            self.caller.msg(
                f"|xThe '{zone_name}' zone is a directional root and "
                f"cannot be removed.|n"
            ); return

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        # Check for children
        children = [
            n for n, z in zones.items()
            if hasattr(z, "get") and z.get("parent") == zone_name
        ]
        if children:
            child_list = ", ".join(children)
            self.caller.msg(
                f"|xCannot remove '{zone_name}' — it has subzones: "
                f"{child_list}.\nRemove those first.|n"
            ); return

        del zones[zone_name]
        room.db.zones = zones
        self.caller.msg(f"|wZone '{zone_name}' removed.|n")

    # ------------------------------------------------------------------
    # scent
    # ------------------------------------------------------------------

    def _do_scent(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "=" not in self.args:
            self.caller.msg(
                "|xUsage: |wroomzone scent <zone> = <text>|n"
            ); return

        zone_name, _, text = self.args.partition("=")
        zone_name = zone_name.strip().lower()
        text      = text.strip()

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        zone["scent"] = text
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(f"|wScent set on zone '{zone_name}'.|n")

    def _do_scent_clear(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()
        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        zone["scent"] = None
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(f"|wScent cleared from zone '{zone_name}'.|n")

    # ------------------------------------------------------------------
    # ambient
    # ------------------------------------------------------------------

    def _do_ambient(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "+" not in self.args:
            self.caller.msg(
                "|xUsage: |wroomzone ambient <zone> + <text>|n"
            ); return

        zone_name, _, text = self.args.partition("+")
        zone_name = zone_name.strip().lower()
        text      = text.strip()

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        if not text:
            self.caller.msg("|xAmbient message cannot be empty.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        ambient = list(zone.get("ambient", []) or [])
        ambient.append(text)
        zone["ambient"] = ambient
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wAmbient message added to zone '{zone_name}' "
            f"({len(ambient)} total).|n"
        )

    def _do_ambient_clear(self):
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()
        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        zone["ambient"] = []
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wAll ambient messages cleared from zone '{zone_name}'.|n"
        )

    # ------------------------------------------------------------------
    # token
    # ------------------------------------------------------------------

    def _do_token(self):
        zone_name = self.args.strip().lower()
        if not zone_name:
            self.caller.msg(
                "|xUsage: |wroomzone token <zone>|n"
            ); return

        _, zones = self._get_zones()
        if zones is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        token = "{zone:" + zone_name + "}"
        self.caller.msg(
            f"|wToken for '{zone_name}':|n  |w{token}|n\n"
            f"|xPaste this into your room desc to render the zone "
            f"description inline. Zones without an embedded token "
            f"are auto-appended below the main description.|n"
        )


# ---------------------------------------------------------------------------
# CmdSet + export
# ---------------------------------------------------------------------------

class RoomZoneCmdSet(CmdSet):
    key = "RoomZoneCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdRoomZone())


ALL_ROOMZONE_CMDS = [CmdRoomZone]
