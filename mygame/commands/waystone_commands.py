"""
commands/waystone_commands.py

Commands for the waystone / waypost travel system.

STAFF BUILDER COMMANDS  (lock: perm(Builder))
─────────────────────────────────────────────
  @waystone/hub [name=<label>]
      Create a HubWaystone in the current room.

  @waystone/portal <address> [hub=#<room>]
      Create a PortalWaystone here with the given portal label.
      hub= sets which room players return to (defaults to nearest HubWaystone).

  @waystone/list
      List all waystones and wayposts currently in the database.

  @waystone/link <portal_id> = <hub_room>
      Relink a PortalWaystone (by dbref) to a different hub room.

  @waystone/desc <waystone_id> = <text>
      Set the description on any waystone.

  @waystone/tag [hub]
      Tag the current room as 'waystone_hub' so portals/wayposts
      can find it automatically.


PLAYER COMMANDS  (on object CmdSets — available in same room as object)
────────────────────────────────────────────────────────────────────────
  waypost                — show this waypost's realm address and status
  waypost address <word> — claim a realm address for this waypost
  waypost clear          — release the realm address (deactivate)
  wayback                — return to the hub (on any portal stone or waypost)
"""

import random

from evennia.commands.default.muxcommand import MuxCommand
from evennia import CmdSet


# ---------------------------------------------------------------------------
# Teleport flavor text (return trip)
# ---------------------------------------------------------------------------

_RETURN_SELF_MSGS = [
    "The waypost pulses warmly. The runes light in sequence. The hub reshapes around you.",
    "You lay a hand on the waystone. The world folds — and you are back.",
    "A resonance answers your touch. Brief, certain. You are in the hub.",
    "The stone knows where you mean. You are there before it fully fades.",
]

_RETURN_DEPART_ROOM = [
    "{name} touches the waystone and fades back through.",
    "The waystone pulses, and {name} is gone.",
    "{name} lays a hand on the stone. A shimmer. Then they are elsewhere.",
    "A soft light, and {name} steps back through.",
]

_RETURN_HUB_ARRIVE = [
    "{name} steps back out of a waystone.",
    "A shimmer at the hub waystone — {name} has returned.",
    "{name} arrives back in the hub.",
    "The hub waystone pulses briefly as {name} comes through.",
]


# ---------------------------------------------------------------------------
# Shared return-to-hub helper
# ---------------------------------------------------------------------------

def _do_return(caller, hub_room):
    """
    Teleport caller back to hub_room with flavor messages.
    Used by both CmdWayback (portal) and CmdWayback (waypost).
    """
    name = caller.db.rp_name or caller.key

    if caller.location:
        caller.location.msg_contents(
            "|x" + random.choice(_RETURN_DEPART_ROOM).format(name=name) + "|n",
            exclude=[caller],
        )

    caller.msg("\n" + random.choice(_RETURN_SELF_MSGS))
    caller.move_to(hub_room, quiet=True)

    hub_room.msg_contents(
        "|x" + random.choice(_RETURN_HUB_ARRIVE).format(name=name) + "|n",
        exclude=[caller],
    )
    caller.msg("\n" + hub_room.return_appearance(caller))


# ---------------------------------------------------------------------------
# CmdWayback — shared by PortalWaystoneCmdSet and WaypostCmdSet
# ---------------------------------------------------------------------------

class CmdWayback(MuxCommand):
    """
    Return to the hub from a portal waystone or waypost.

    Usage:
      wayback

    Type this while in the same room as a portal waystone or a placed
    waypost to be teleported back to the hub.
    """

    key     = "wayback"
    locks   = "cmd:all()"
    help_category = "Travel"

    # Set by the CmdSet that contains this command so it knows which
    # object to look up the hub room from.
    _obj_typeclass = None

    def func(self):
        caller = self.caller

        # Navigation lock check (binding items)
        try:
            from world.binding_effects import check_navigation_allowed
            ok, reason = check_navigation_allowed(caller)
            if not ok:
                caller.msg(reason)
                return
        except Exception:
            pass

        # Find the stone/post in the current room
        hub_room = None
        for obj in caller.location.contents:
            tc = getattr(obj, "typeclass_path", "")
            if self._obj_typeclass and self._obj_typeclass in tc:
                if hasattr(obj, "get_hub_room"):
                    hub_room = obj.get_hub_room()
                    break

        if not hub_room:
            # Fallback: look for any hub stone
            try:
                from evennia import search_object
                stones = search_object(
                    None,
                    typeclass="typeclasses.waystone.HubWaystone",
                    quiet=True,
                ) or []
                if stones and stones[0].location:
                    hub_room = stones[0].location
            except Exception:
                pass

        if not hub_room:
            caller.msg("|xNo hub room found — ask a builder to set one up.|n")
            return

        if hub_room == caller.location:
            caller.msg("|xYou are already at the hub.|n")
            return

        _do_return(caller, hub_room)


class CmdWaybackPortal(CmdWayback):
    """Return to hub via a portal waystone."""
    _obj_typeclass = "typeclasses.waystone.PortalWaystone"


class CmdWaybackWaypost(CmdWayback):
    """Return to hub via a waypost."""
    _obj_typeclass = "typeclasses.waypost.Waypost"


# ---------------------------------------------------------------------------
# CmdWaypost — manage a waypost's realm address
# ---------------------------------------------------------------------------

class CmdWaypost(MuxCommand):
    """
    Manage a waypost's realm address.

    Usage:
      waypost                    — show this waypost's info
      waypost address <word>     — claim a realm address
      waypost clear              — release the realm address

    The realm address must be a single word (letters, numbers, hyphens,
    and underscores). Once set, anyone who speaks it aloud near a hub
    waystone will be teleported to the room containing this waypost.

    The waypost must be placed in a room (not in your inventory) for
    the address to be active.

    Only the owner can change or clear the address.
    """

    key           = "waypost"
    locks         = "cmd:all()"
    help_category = "Travel"

    def func(self):
        caller = self.caller
        args   = self.args.strip()

        # Find the waypost — prefer one in the room, fall back to inventory
        waypost = self._find_waypost(caller)
        if not waypost:
            caller.msg("|xNo waypost found here or in your inventory.|n")
            return

        # Check ownership
        owner_char_id    = waypost.db.owner_char_id
        owner_account_id = waypost.db.owner_account_id
        is_owner = (
            (owner_char_id    and owner_char_id    == caller.id) or
            (owner_account_id and hasattr(caller, "account") and
             caller.account and owner_account_id == caller.account.id)
        )

        # No args — show info
        if not args:
            caller.msg("\n" + waypost.return_appearance(caller))
            return

        parts  = args.split(None, 1)
        subcmd = parts[0].lower()
        rest   = parts[1] if len(parts) > 1 else ""

        if subcmd == "address":
            if not is_owner:
                caller.msg("|xOnly the owner can set this waypost's realm address.|n")
                return
            if not rest:
                caller.msg(
                    "Usage: |wwaypost address <word>|n\n"
                    "Example: |wwaypost address thornhaven|n"
                )
                return
            ok, msg = waypost.set_address(rest)
            caller.msg(msg)

        elif subcmd == "clear":
            if not is_owner:
                caller.msg("|xOnly the owner can clear this waypost's realm address.|n")
                return
            caller.msg(waypost.clear_address())

        else:
            caller.msg(
                "Unknown subcommand. Try:\n"
                "  |wwaypost|n           — show info\n"
                "  |wwaypost address <word>|n — set realm address\n"
                "  |wwaypost clear|n     — release realm address\n"
                "  |wwayback|n           — return to hub"
            )

    @staticmethod
    def _find_waypost(caller):
        """
        Find a waypost associated with caller:
        1. First, look for a waypost in the current room.
        2. Fall back to the first waypost in caller's inventory.
        """
        from typeclasses.waypost import Waypost

        # In room
        for obj in caller.location.contents:
            if isinstance(obj, Waypost):
                return obj

        # In inventory
        for obj in caller.contents:
            if isinstance(obj, Waypost):
                return obj

        return None


# ---------------------------------------------------------------------------
# CmdSets attached to the objects
# ---------------------------------------------------------------------------

class WaypostCmdSet(CmdSet):
    """CmdSet attached to a Waypost object."""

    key = "WaypostCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdWaypost())
        self.add(CmdWaybackWaypost())


class PortalWaystoneCmdSet(CmdSet):
    """CmdSet attached to a PortalWaystone object."""

    key = "PortalWaystoneCmdSet"

    def at_cmdset_creation(self):
        self.add(CmdWaybackPortal())


# ---------------------------------------------------------------------------
# CmdWaystone — staff builder command
# ---------------------------------------------------------------------------

class CmdWaystone(MuxCommand):
    """
    Create and manage waystones (builder command).

    Usage:
      @waystone/hub [name=<display label>]
          Create a hub waystone in the current room.

      @waystone/portal <address> [hub=#<room>]
          Create a portal waystone here with the given address label.
          Players say this address at a hub stone to arrive here.
          Optionally specify the hub room they return to.

      @waystone/list
          List all hub waystones, portal waystones, and active wayposts.

      @waystone/link <portal_dbref> = <hub_room_dbref>
          Re-link a portal waystone to a different hub room.
          Example: @waystone/link #42 = #7

      @waystone/desc <waystone_dbref> = <description>
          Set the description on any waystone.
          Example: @waystone/desc #42 = A towering pillar of dark stone...

      @waystone/tag [hub]
          Tag the current room as 'waystone_hub' so portals and
          wayposts can automatically find their way home.

    Examples:
      @waystone/hub name=The Grand Arch
      @waystone/portal thornhaven hub=#7
      @waystone/list
    """

    key            = "@waystone"
    aliases        = ["@waystones"]
    locks          = "cmd:perm(Builder)"
    help_category  = "Building"
    switch_options = ("hub", "portal", "list", "link", "desc", "tag")

    def func(self):
        caller   = self.caller
        switches = self.switches
        args     = self.args.strip()

        if not switches:
            caller.msg(self.__doc__)
            return

        sw = switches[0].lower()

        if sw == "hub":
            self._create_hub(caller, args)
        elif sw == "portal":
            self._create_portal(caller, args)
        elif sw == "list":
            self._list_all(caller)
        elif sw == "link":
            self._relink(caller, args)
        elif sw == "desc":
            self._set_desc(caller, args)
        elif sw == "tag":
            self._tag_hub(caller)
        else:
            caller.msg("Unknown switch. See |w@waystone|n help.")

    # ── /hub ────────────────────────────────────────────────────────────

    def _create_hub(self, caller, args):
        from evennia import create_object
        from typeclasses.waystone import HubWaystone

        # Parse optional name= argument
        name = "a waystone"
        if "name=" in args.lower():
            idx  = args.lower().index("name=")
            name = args[idx + 5:].strip().strip('"\'')

        room = caller.location
        if not room:
            caller.msg("You must be in a room to create a hub waystone.")
            return

        stone = create_object(
            typeclass=HubWaystone,
            key=name,
            location=room,
        )
        stone.db.display_name = name

        caller.msg(
            f"|gHub waystone created:|n #{stone.id}  '{name}'  in {room.key}\n"
            f"|xPlayers can now speak realm addresses here to travel.|n"
        )

    # ── /portal ─────────────────────────────────────────────────────────

    def _create_portal(self, caller, args):
        from evennia import create_object
        from evennia.objects.models import ObjectDB
        from typeclasses.waystone import HubWaystone, PortalWaystone
        from typeclasses.waypost import Waypost

        if not args:
            caller.msg("Usage: |w@waystone/portal <address> [hub=#<room>]|n")
            return

        # Parse "thornhaven hub=#7"
        parts  = args.split()
        label  = parts[0].lower()
        hub_id = None
        for part in parts[1:]:
            if part.lower().startswith("hub="):
                val = part[4:].lstrip("#")
                try:
                    hub_id = int(val)
                except ValueError:
                    pass

        # Check address isn't taken
        if Waypost.address_is_taken(label):
            caller.msg(
                f"|rThe address '|w{label}|r' is already in use.|n "
                f"Choose a different label."
            )
            return

        # Resolve hub room (default to first HubWaystone's location)
        hub_room = None
        if hub_id:
            try:
                hub_room = ObjectDB.objects.get(pk=hub_id)
            except Exception:
                caller.msg(f"|rRoom #{hub_id} not found.|n")
                return
        else:
            try:
                from evennia import search_object
                stones = search_object(
                    None, typeclass="typeclasses.waystone.HubWaystone", quiet=True
                ) or []
                if stones and stones[0].location:
                    hub_room = stones[0].location
            except Exception:
                pass

        room = caller.location
        stone = create_object(
            typeclass=PortalWaystone,
            key=f"a waystone [{label}]",
            location=room,
        )
        stone.db.portal_label = label
        stone.db.display_name = f"a waystone [{label}]"
        if hub_room:
            stone.db.hub_room_id = hub_room.id

        caller.msg(
            f"|gPortal waystone created:|n #{stone.id}  label='{label}'  in {room.key}\n"
            f"|xPlayers say '|w{label}|x' at the hub to arrive here.|n"
        )
        if hub_room:
            caller.msg(f"|xReturn destination: {hub_room.key} #{hub_room.id}|n")
        else:
            caller.msg(
                "|yNo hub room linked. Use |w@waystone/link|y or ensure a HubWaystone exists.|n"
            )

    # ── /list ────────────────────────────────────────────────────────────

    def _list_all(self, caller):
        from evennia import search_object
        from typeclasses.waystone import HubWaystone, PortalWaystone
        from typeclasses.waypost import Waypost

        lines = ["|wWaystone Registry|n", "|x" + "─" * 50 + "|n"]

        hubs = search_object(
            None, typeclass="typeclasses.waystone.HubWaystone", quiet=True
        ) or []
        lines.append(f"\n|wHub Waystones ({len(hubs)})|n")
        for h in hubs:
            loc = h.location.key if h.location else "nowhere"
            lines.append(f"  #{h.id:<5}  {h.db.display_name or h.key:<25}  @ {loc}")

        portals = search_object(
            None, typeclass="typeclasses.waystone.PortalWaystone", quiet=True
        ) or []
        lines.append(f"\n|wPortal Waystones ({len(portals)})|n")
        for p in portals:
            loc   = p.location.key if p.location else "nowhere"
            label = p.db.portal_label or "—"
            hub   = p.db.hub_room_id or "—"
            lines.append(
                f"  #{p.id:<5}  [{label:<15}]  @ {loc:<20}  hub #{hub}"
            )

        wayposts = search_object(
            None, typeclass="typeclasses.waypost.Waypost", quiet=True
        ) or []
        active = [
            w for w in wayposts
            if w.db.realm_address and w.location and not hasattr(w.location, "account")
        ]
        lines.append(f"\n|wPlayer Wayposts — active ({len(active)}/{len(wayposts)})|n")
        for w in wayposts:
            addr  = w.db.realm_address or "|x(no address)|n"
            owner = w.db.owner_name or "?"
            loc   = w.location.key if w.location else "nowhere"
            status = "" if (w.db.realm_address and w.location and not hasattr(w.location, "account")) else " |x[inactive]|n"
            lines.append(
                f"  #{w.id:<5}  {addr:<20}  owner: {owner:<15}  @ {loc}{status}"
            )

        if not (hubs or portals or wayposts):
            lines.append("  (none yet)")

        caller.msg("\n".join(lines))

    # ── /link ────────────────────────────────────────────────────────────

    def _relink(self, caller, args):
        from evennia.objects.models import ObjectDB
        from typeclasses.waystone import PortalWaystone

        if "=" not in args:
            caller.msg("Usage: |w@waystone/link <portal_dbref> = <hub_room_dbref>|n")
            return

        portal_str, hub_str = args.split("=", 1)
        try:
            portal_id = int(portal_str.strip().lstrip("#"))
            hub_id    = int(hub_str.strip().lstrip("#"))
        except ValueError:
            caller.msg("Provide numeric dbrefs — e.g. |w@waystone/link #42 = #7|n")
            return

        try:
            portal = ObjectDB.objects.get(pk=portal_id)
            hub    = ObjectDB.objects.get(pk=hub_id)
        except Exception as e:
            caller.msg(f"Object not found: {e}")
            return

        if not isinstance(portal.typeclass, PortalWaystone):
            caller.msg(f"#{portal_id} is not a PortalWaystone.")
            return

        portal.db.hub_room_id = hub.id
        caller.msg(
            f"|gLinked:|n portal #{portal_id} ({portal.key}) → hub room #{hub.id} ({hub.key})"
        )

    # ── /desc ────────────────────────────────────────────────────────────

    def _set_desc(self, caller, args):
        from evennia.objects.models import ObjectDB

        if "=" not in args:
            caller.msg("Usage: |w@waystone/desc <waystone_dbref> = <description>|n")
            return

        id_str, desc = args.split("=", 1)
        try:
            obj_id = int(id_str.strip().lstrip("#"))
        except ValueError:
            caller.msg("Provide a numeric dbref — e.g. |w@waystone/desc #42 = ...|n")
            return

        try:
            obj = ObjectDB.objects.get(pk=obj_id)
        except Exception:
            caller.msg(f"Object #{obj_id} not found.")
            return

        obj.db.waystone_desc = desc.strip()
        caller.msg(f"|gDescription set on #{obj_id} ({obj.key}).|n")

    # ── /tag ─────────────────────────────────────────────────────────────

    def _tag_hub(self, caller):
        room = caller.location
        if not room:
            caller.msg("You must be in a room.")
            return
        room.tags.add("waystone_hub", category="room_type")
        caller.msg(
            f"|gTagged:|n {room.key} #{room.id} as 'waystone_hub'.\n"
            f"|xPortal waystones and wayposts will return here by default.|n"
        )


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

ALL_WAYSTONE_BUILDER_CMDS = [CmdWaystone]
