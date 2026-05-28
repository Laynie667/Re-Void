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
        "desc":           "",
        "details":        {},
        "handle_details": {},   # detail_name -> intimate emote text
        "study_details":  [],   # list of random observation strings
        "inscribable":    False, # whether players can inscribe this zone
        "inscriptions":   [],   # player-written inscriptions (shown via study)
        "scent":          None,
        "ambient":        [],
        "contents":       [],
        "parent":         parent,
        "mechanics":      {},
        "scripts":        [],
        "event_hooks":    {},
        "summary":        "",    # short one-liner for main room look
        "bar_drinks":     [],   # list of drink name strings for CmdPour
        "games":          [],   # list of game name strings for CmdPlay
        "pantry":         [],   # list of food/ingredient strings for CmdCook
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
        "handle", "handle/rm",
        "study", "study/rm", "study/list",
        "inscribe/enable", "inscribe/disable", "inscribe/list",
        "bar", "bar/rm", "bar/list",
        "game", "game/rm", "game/list",
        "pantry", "pantry/rm", "pantry/list",
        "summary",
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
            "":                  self._do_list_or_error,
            "list":              self._do_list,
            "desc":              self._do_desc,
            "detail":            self._do_detail,
            "detail/rm":         self._do_detail_rm,
            "add":               self._do_add,
            "rm":                self._do_rm,
            "scent":             self._do_scent,
            "scent/clear":       self._do_scent_clear,
            "ambient":           self._do_ambient,
            "ambient/clear":     self._do_ambient_clear,
            "token":             self._do_token,
            "handle":            self._do_handle,
            "handle/rm":         self._do_handle_rm,
            "study":             self._do_study,
            "study/rm":          self._do_study_rm,
            "study/list":        self._do_study_list,
            "inscribe/enable":   self._do_inscribe_enable,
            "inscribe/disable":  self._do_inscribe_disable,
            "inscribe/list":     self._do_inscribe_list,
            "bar":               self._do_bar,
            "bar/rm":            self._do_bar_rm,
            "bar/list":          self._do_bar_list,
            "game":              self._do_game,
            "game/rm":           self._do_game_rm,
            "game/list":         self._do_game_list,
            "pantry":            self._do_pantry,
            "pantry/rm":         self._do_pantry_rm,
            "pantry/list":       self._do_pantry_list,
            "summary":           self._do_summary,
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


    # ------------------------------------------------------------------
    # handle (intimate detail interaction text)
    # ------------------------------------------------------------------

    def _do_handle(self):
        """
        roomzone handle <zone>/<detail> = <text>
        Set the intimate handle-interaction text for a detail.
        Stored in zone["handle_details"][detail_name].
        """
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "=" not in self.args or "/" not in self.args.split("=")[0]:
            self.caller.msg(
                "|xUsage: |wroomzone handle <zone>/<detail> = <text>|n"
            ); return

        lhs, _, text = self.args.partition("=")
        lhs = lhs.strip()
        text = text.strip()

        if "/" not in lhs:
            self.caller.msg(
                "|xUsage: |wroomzone handle <zone>/<detail> = <text>|n"
            ); return

        zone_name, _, detail_name = lhs.partition("/")
        zone_name   = zone_name.strip().lower()
        detail_name = detail_name.strip().lower()

        if zone_name not in zones:
            self.caller.msg(
                f"|xZone '{zone_name}' not found.|n"
            ); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        handle_details = dict(zone.get("handle_details", {}) or {})
        handle_details[detail_name] = text
        zone["handle_details"] = handle_details
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wHandle text set for '{detail_name}' in zone '{zone_name}'.|n\n"
            f"|xPlayers can trigger it with: |whandle {detail_name}|n"
        )

    def _do_handle_rm(self):
        """roomzone handle/rm <zone>/<detail>"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "/" not in self.args:
            self.caller.msg(
                "|xUsage: |wroomzone handle/rm <zone>/<detail>|n"
            ); return

        zone_name, _, detail_name = self.args.partition("/")
        zone_name   = zone_name.strip().lower()
        detail_name = detail_name.strip().lower()

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        handle_details = dict(zone.get("handle_details", {}) or {})

        if detail_name not in handle_details:
            self.caller.msg(
                f"|xNo handle text for '{detail_name}' in zone '{zone_name}'.|n"
            ); return

        del handle_details[detail_name]
        zone["handle_details"] = handle_details
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wHandle text removed for '{detail_name}' in '{zone_name}'.|n"
        )

    # ------------------------------------------------------------------
    # study (randomised observation list)
    # ------------------------------------------------------------------

    def _do_study(self):
        """
        roomzone study <zone> + <observation text>
        Append a random observation to a zone's study_details list.
        """
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "+" not in self.args:
            self.caller.msg(
                "|xUsage: |wroomzone study <zone> + <observation text>|n"
            ); return

        zone_name, _, text = self.args.partition("+")
        zone_name = zone_name.strip().lower()
        text      = text.strip()

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        if not text:
            self.caller.msg("|xObservation text cannot be empty.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        study_details = list(zone.get("study_details", []) or [])
        study_details.append(text)
        zone["study_details"] = study_details
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wStudy observation #{len(study_details)} added to zone '{zone_name}'.|n\n"
            f"|xPlayers can discover it randomly with: |wstudy {zone_name}|n"
        )

    def _do_study_rm(self):
        """roomzone study/rm <zone> <index>  (1-based)"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        parts = self.args.strip().split(None, 1)
        if len(parts) < 2:
            self.caller.msg(
                "|xUsage: |wroomzone study/rm <zone> <index>|n"
            ); return

        zone_name = parts[0].lower()
        try:
            idx = int(parts[1]) - 1
        except ValueError:
            self.caller.msg("|xIndex must be a number.|n"); return

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        study_details = list(zone.get("study_details", []) or [])

        if idx < 0 or idx >= len(study_details):
            self.caller.msg(
                f"|xIndex {idx + 1} out of range "
                f"(zone has {len(study_details)} observations).|n"
            ); return

        removed = study_details.pop(idx)
        zone["study_details"] = study_details
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wObservation #{idx + 1} removed from zone '{zone_name}'.|n\n"
            f"|x(Removed: {removed[:60]}{'...' if len(removed) > 60 else ''})|n"
        )

    def _do_study_list(self):
        """roomzone study/list <zone>"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()
        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = zones[zone_name]
        study_details = zone.get("study_details", []) or [] if hasattr(zone, "get") else []

        if not study_details:
            self.caller.msg(
                f"|xNo study observations on zone '{zone_name}' yet.\n"
                f"Add one with: |wroomzone study {zone_name} + <text>|n"
            ); return

        lines = [f"|wStudy observations for zone '{zone_name}':|n"]
        for i, obs in enumerate(study_details, 1):
            preview = obs[:80] + ("..." if len(obs) > 80 else "")
            lines.append(f"  |w{i}.|n {preview}")
        self.caller.msg("\n".join(lines))


    # ------------------------------------------------------------------
    # inscribe/enable — inscribe/disable — inscribe/list
    # ------------------------------------------------------------------

    def _do_inscribe_enable(self):
        """roomzone inscribe/enable <zone>"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()
        if not zone_name:
            self.caller.msg(
                "|xUsage: |wroomzone inscribe/enable <zone>|n"
            ); return

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        zone["inscribable"] = True
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wZone '{zone_name}' is now inscribable.\n"
            f"|xPlayers can mark it with: |winscribe {zone_name} = <text>|n"
        )

    def _do_inscribe_disable(self):
        """roomzone inscribe/disable <zone>"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()
        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        zone["inscribable"] = False
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|wZone '{zone_name}' inscribing disabled. "
            f"Existing inscriptions are preserved.|n"
        )

    def _do_inscribe_list(self):
        """roomzone inscribe/list <zone>"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()
        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = zones[zone_name]
        inscriptions = zone.get("inscriptions", []) or [] if hasattr(zone, "get") else []
        if not inscriptions:
            self.caller.msg(
                f"|xNo inscriptions on zone '{zone_name}' yet.|n"
            ); return

        lines = [f"|wInscriptions on zone '{zone_name}' ({len(inscriptions)} total):|n"]
        for i, ins in enumerate(inscriptions, 1):
            preview = ins[:90] + ("..." if len(ins) > 90 else "")
            lines.append(f"  |w{i}.|n {preview}")
        self.caller.msg("\n".join(lines))

    # ------------------------------------------------------------------
    # bar — bar/rm — bar/list
    # ------------------------------------------------------------------

    def _do_bar(self):
        """
        roomzone bar <zone> + <drink name>
        Add a drink to a zone's bar inventory.
        """
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "+" not in self.args:
            self.caller.msg(
                "|xUsage: |wroomzone bar <zone> + <drink name>|n"
            ); return

        zone_name, _, text = self.args.partition("+")
        zone_name = zone_name.strip().lower()
        text      = text.strip()

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        if not text:
            self.caller.msg("|xDrink name cannot be empty.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        bar_drinks = list(zone.get("bar_drinks", []) or [])
        bar_drinks.append(text)
        zone["bar_drinks"] = bar_drinks
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|w'{text}' added to bar on zone '{zone_name}' "
            f"({len(bar_drinks)} drinks total).|n"
        )

    def _do_bar_rm(self):
        """roomzone bar/rm <zone> <index>  (1-based)"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        parts = self.args.strip().split(None, 1)
        if len(parts) < 2:
            self.caller.msg(
                "|xUsage: |wroomzone bar/rm <zone> <index>|n"
            ); return

        zone_name = parts[0].lower()
        try:
            idx = int(parts[1]) - 1
        except ValueError:
            self.caller.msg("|xIndex must be a number.|n"); return

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        bar_drinks = list(zone.get("bar_drinks", []) or [])

        if idx < 0 or idx >= len(bar_drinks):
            self.caller.msg(
                f"|xIndex {idx + 1} out of range "
                f"(zone has {len(bar_drinks)} drinks).|n"
            ); return

        removed = bar_drinks.pop(idx)
        zone["bar_drinks"] = bar_drinks
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(f"|wRemoved '{removed}' from bar on zone '{zone_name}'.|n")

    def _do_bar_list(self):
        """roomzone bar/list <zone>"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()
        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone       = zones[zone_name]
        bar_drinks = zone.get("bar_drinks", []) or [] if hasattr(zone, "get") else []

        if not bar_drinks:
            self.caller.msg(
                f"|xNo drinks on zone '{zone_name}' yet.\n"
                f"Add one with: |wroomzone bar {zone_name} + <name>|n"
            ); return

        lines = [f"|wDrinks available on zone '{zone_name}':|n"]
        for i, d in enumerate(bar_drinks, 1):
            lines.append(f"  |w{i}.|n {d}")
        self.caller.msg("\n".join(lines))

    # ------------------------------------------------------------------
    # game — game/rm — game/list
    # ------------------------------------------------------------------

    def _do_game(self):
        """
        roomzone game <zone> + <game name>
        Add a game to a zone's game list.
        """
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        if "+" not in self.args:
            self.caller.msg(
                "|xUsage: |wroomzone game <zone> + <game name>|n"
            ); return

        zone_name, _, text = self.args.partition("+")
        zone_name = zone_name.strip().lower()
        text      = text.strip()

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        if not text:
            self.caller.msg("|xGame name cannot be empty.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        games = list(zone.get("games", []) or [])
        games.append(text)
        zone["games"] = games
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|w'{text}' added to games on zone '{zone_name}' "
            f"({len(games)} games total).|n"
        )

    def _do_game_rm(self):
        """roomzone game/rm <zone> <index>  (1-based)"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        parts = self.args.strip().split(None, 1)
        if len(parts) < 2:
            self.caller.msg(
                "|xUsage: |wroomzone game/rm <zone> <index>|n"
            ); return

        zone_name = parts[0].lower()
        try:
            idx = int(parts[1]) - 1
        except ValueError:
            self.caller.msg("|xIndex must be a number.|n"); return

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        games = list(zone.get("games", []) or [])

        if idx < 0 or idx >= len(games):
            self.caller.msg(
                f"|xIndex {idx + 1} out of range "
                f"(zone has {len(games)} games).|n"
            ); return

        removed = games.pop(idx)
        zone["games"] = games
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(f"|wRemoved '{removed}' from games on zone '{zone_name}'.|n")

    def _do_game_list(self):
        """roomzone game/list <zone>"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()
        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone  = zones[zone_name]
        games = zone.get("games", []) or [] if hasattr(zone, "get") else []

        if not games:
            self.caller.msg(
                f"|xNo games on zone '{zone_name}' yet.\n"
                f"Add one with: |wroomzone game {zone_name} + <name>|n"
            ); return

        lines = [f"|wGames on zone '{zone_name}':|n"]
        for i, g in enumerate(games, 1):
            lines.append(f"  |w{i}.|n {g}")
        self.caller.msg("\n".join(lines))

    # ------------------------------------------------------------------
    # summary
    # ------------------------------------------------------------------

    def _do_summary(self):
        """
        roomzone summary <zone> = <text>
        Set a short one-liner for a zone that shows in the main room look.

        The summary is what {zone:<name>} tokens render in the room
        description, and what auto-appends for zones without a token.
        The full desc is only shown when a player uses 'look <zone>'.

        To clear: roomzone summary <zone> =
        """
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        args = self.args.strip()
        if "=" not in args:
            self.caller.msg("|xUsage: roomzone summary <zone> = <text>|n"); return

        zone_part, _, text = args.partition("=")
        zone_name = zone_part.strip().lower()
        text      = text.strip()

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        zone["summary"] = text
        zones[zone_name] = zone
        room.db.zones = zones

        if text:
            self.caller.msg(f"|wSummary set for zone '{zone_name}':|n |x{text}|n")
        else:
            self.caller.msg(f"|xSummary cleared for zone '{zone_name}'.|n")

    # ------------------------------------------------------------------
    # pantry — pantry/rm — pantry/list
    # ------------------------------------------------------------------

    def _do_pantry(self):
        """
        roomzone pantry <zone> + <item name>
        Add a food/ingredient to a zone's pantry for CmdCook.
        """
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        args = self.args.strip()
        if "+" not in args:
            self.caller.msg(
                "|xUsage: roomzone pantry <zone> + <item name>|n"
            ); return

        zone_part, _, text = args.partition("+")
        zone_name = zone_part.strip().lower()
        text      = text.strip()

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return
        if not text:
            self.caller.msg("|xItem name cannot be empty.|n"); return

        zone   = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        pantry = list(zone.get("pantry", []) or [])
        pantry.append(text)
        zone["pantry"] = pantry
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(
            f"|w'{text}' added to pantry on zone '{zone_name}' "
            f"({len(pantry)} items total).|n"
        )

    def _do_pantry_rm(self):
        """roomzone pantry/rm <zone> <index>  (1-based)"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        args  = self.args.strip().split()
        if len(args) < 2:
            self.caller.msg("|xUsage: roomzone pantry/rm <zone> <index>|n"); return

        zone_name = args[0].lower()
        try:
            idx = int(args[1]) - 1
        except ValueError:
            self.caller.msg("|xIndex must be a number.|n"); return

        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone   = dict(zones[zone_name]) if hasattr(zones[zone_name], "items") else {}
        pantry = list(zone.get("pantry", []) or [])

        if idx < 0 or idx >= len(pantry):
            self.caller.msg(
                f"|xIndex {idx + 1} out of range "
                f"(zone has {len(pantry)} pantry items).|n"
            ); return

        removed = pantry.pop(idx)
        zone["pantry"] = pantry
        zones[zone_name] = zone
        room.db.zones = zones
        self.caller.msg(f"|wRemoved '{removed}' from pantry on zone '{zone_name}'.|n")

    def _do_pantry_list(self):
        """roomzone pantry/list <zone>"""
        room, zones = self._get_zones()
        if room is None:
            self.caller.msg("|xYou aren't in a room.|n"); return

        zone_name = self.args.strip().lower()
        if zone_name not in zones:
            self.caller.msg(f"|xZone '{zone_name}' not found.|n"); return

        zone   = zones[zone_name]
        pantry = zone.get("pantry", []) or [] if hasattr(zone, "get") else []

        if not pantry:
            self.caller.msg(
                f"|xNo pantry items on zone '{zone_name}' yet.\n"
                f"Add one with: |wroomzone pantry {zone_name} + <item>|n"
            ); return

        lines = [f"|wPantry items on zone '{zone_name}':|n"]
        for i, item in enumerate(pantry, 1):
            lines.append(f"  |w{i}.|n {item}")
        self.caller.msg("\n".join(lines))


# ---------------------------------------------------------------------------
# CmdSet + export
# ---------------------------------------------------------------------------

class RoomZoneCmdSet(CmdSet):
    key = "RoomZoneCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdRoomZone())


ALL_ROOMZONE_CMDS = [CmdRoomZone]
