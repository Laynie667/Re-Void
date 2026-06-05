"""
typeclasses/waystone.py

Waystone typeclasses for the Re:Void hub/realm travel system.

HubWaystone  — placed in the hub by builders.
  Listens for spoken text via on_hear_say() (hooked by CmdSay).
  When a single word is spoken that matches a known realm address or
  portal label, teleports the speaker to that destination.

PortalWaystone — placed at a destination realm by builders.
  Paired with the hub. Say its portal_label at the hub to arrive here.
  Type 'wayback' while near it to return to the hub.

Builder setup (staff commands in waystone_commands.py):
  @waystone/hub [name=<display>]              — create hub stone in current room
  @waystone/portal <address> [hub=#<room>]    — create portal stone in current room
  @waystone/list                               — list all waystones
  @waystone/link <portal_id> = <hub_room>     — re-link a portal to a hub room
  @waystone/desc <id> = <text>                — set a waystone's description

Tag the main hub room with tag 'waystone_hub' (category 'room_type') to
help portals and wayposts find their way home automatically.
"""

import random

from evennia import DefaultObject


# ---------------------------------------------------------------------------
# Teleport flavor text
# ---------------------------------------------------------------------------

_DEPART_SELF = [
    "The waystone brightens as you speak. The air thins, folds — and you step through.",
    "A resonance answers your words. The waystone pulses once, and the world reshapes.",
    "Your voice finds the address. The space between bends obligingly.",
    "The waystone hums low, then high, then briefly not at all. You are somewhere else.",
    "The runes along the stone light in sequence. There is a moment of pressure, and then arrival.",
]

_DEPART_ROOM = [
    "{name} steps into the waystone and is gone.",
    "The waystone brightens as {name} speaks — and then {name} is elsewhere.",
    "{name} says something. The waystone answers. {name} is no longer here.",
    "A pulse of light, and {name} has gone through.",
]

_ARRIVE_ROOM = [
    "{name} steps out of a shimmer in the air.",
    "The air creases briefly, and {name} walks through.",
    "A waystone pulse announces {name}'s arrival.",
    "{name} arrives from elsewhere, looking oriented.",
]

_RETURN_SELF = [
    "The waystone accepts you without ceremony. The hub reshapes around you.",
    "You touch the stone. The runes answer. One moment here, one moment there.",
    "The waypost knows where you mean. You are in the hub before you've finished thinking it.",
    "A resonance at your fingertips, brief and certain, and then you are home.",
]


# ---------------------------------------------------------------------------
# Shared travel helper
# ---------------------------------------------------------------------------

def _do_travel(traveller, dest_room, depart_msgs=None, arrive_msgs=None,
               self_msg=None):
    """
    Move traveller to dest_room with flavor messages.

    Args:
        traveller:     The character being moved.
        dest_room:     The Room to move them to.
        depart_msgs:   List of messages shown to the room being left.
        arrive_msgs:   List of messages shown to the destination room.
        self_msg:      Message shown to the traveller.
    """
    name = traveller.db.rp_name or traveller.key

    depart_msgs  = depart_msgs  or _DEPART_ROOM
    arrive_msgs  = arrive_msgs  or _ARRIVE_ROOM
    self_msg     = self_msg     or random.choice(_DEPART_SELF)

    # Tell the current room
    if traveller.location:
        traveller.location.msg_contents(
            "|x" + random.choice(depart_msgs).format(name=name) + "|n",
            exclude=[traveller],
        )

    # Tell the traveller
    traveller.msg("\n" + self_msg)

    # Move
    traveller.move_to(dest_room, quiet=True)

    # Tell the destination room
    dest_room.msg_contents(
        "|x" + random.choice(arrive_msgs).format(name=name) + "|n",
        exclude=[traveller],
    )

    # Show the room
    traveller.msg("\n" + dest_room.return_appearance(traveller))


# ---------------------------------------------------------------------------
# HubWaystone
# ---------------------------------------------------------------------------

class HubWaystone(DefaultObject):
    """
    A waystone placed in the hub room by a builder.

    Listens for 'say' via on_hear_say() (the CmdSay parrot hook).
    When a player speaks a single word matching a portal label or waypost
    realm address, teleports them to that destination.
    """

    def at_object_creation(self):
        self.db.waystone_type = "hub"
        self.db.display_name  = "a waystone"
        self.db.react_to_say  = True    # enables CmdSay's on_hear_say hook
        self.db.waystone_desc = (
            "A standing stone of dark mineral, faintly luminescent at the "
            "edges. Runes are cut into its surface in a long spiral — not "
            "decorative, functional. Something in the air near it carries "
            "the particular quality of a door that is waiting to be opened."
        )

    def return_appearance(self, looker, **kwargs):
        name = self.db.display_name or self.key
        desc = self.db.waystone_desc or ""
        lines = [f"|w{name}|n"]
        if desc:
            lines.append(desc)
        lines.append(
            "\n|xSpeak a realm address aloud to travel. "
            "The stone answers if it knows the way.|n"
        )
        return "\n".join(lines)

    def on_hear_say(self, caller, text):
        """
        Called by CmdSay when someone speaks in this room.

        Matches only if the entire spoken text is a single word (the
        realm address). Multi-word speech is ignored so casual
        conversation doesn't accidentally trigger travel.
        """
        # Normalize: strip punctuation, lowercase
        address = text.strip().lower().strip(".,!?;:'\"").strip()

        # Only match single-word addresses, max 40 chars
        if not address or " " in address or len(address) > 40:
            return

        # 1. Check portal waystones (builder-placed destinations)
        matched = self._find_portal(address)
        if matched:
            _do_travel(caller, matched.location)
            return

        # 2. Check player wayposts
        matched_post = self._find_waypost(address)
        if matched_post:
            _do_travel(caller, matched_post.location)
            return

        # No match — subtle ambient hint
        caller.msg("|xThe waystone listens. The address isn't one it knows.|n")

    @staticmethod
    def _find_portal(address):
        """Return the first PortalWaystone with matching portal_label, or None."""
        try:
            # NOTE: search_object(None, typeclass=...) returns [] in this Evennia,
            # so use the typeclass manager directly.
            from typeclasses.waystone import PortalWaystone
            for p in PortalWaystone.objects.all():
                label = (p.db.portal_label or "").strip().lower()
                if label == address and p.location:
                    return p
        except Exception:
            pass
        return None

    @staticmethod
    def _find_waypost(address):
        """
        Return the first active Waypost with matching realm_address, or None.
        A waypost is 'active' when it has an address AND is placed in a room
        (not in a character's inventory).
        """
        try:
            from typeclasses.waypost import Waypost
            from typeclasses.characters import Character
            for wp in Waypost.objects.all():
                wa = (wp.db.realm_address or "").strip().lower()
                if wa != address:
                    continue
                loc = wp.location
                # Active = placed in a room, not carried in a character's inventory.
                # (hasattr(loc,'account') was always True — every object has it —
                #  so the old check rejected every waypost.)
                if loc and not isinstance(loc, Character):
                    return wp
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# PortalWaystone
# ---------------------------------------------------------------------------

class PortalWaystone(DefaultObject):
    """
    A waystone placed at a destination realm by a builder.

    Players say its portal_label at a HubWaystone to arrive here.
    Type 'wayback' while near it to return to the hub.
    """

    def at_object_creation(self):
        self.db.waystone_type = "portal"
        self.db.portal_label  = ""      # word to speak at hub to arrive here
        self.db.hub_room_id   = None    # pk of hub room (for return trip)
        self.db.display_name  = "a waystone"
        self.db.waystone_desc = (
            "A standing stone matching the ones in the hub — same dark mineral, "
            "same spiral runes. This one faces outward, runes oriented for "
            "departure rather than arrival. Home-facing."
        )
        # Attach commands
        from commands.waystone_commands import PortalWaystoneCmdSet
        self.cmdset.add_default(PortalWaystoneCmdSet)

    def return_appearance(self, looker, **kwargs):
        name  = self.db.display_name or self.key
        desc  = self.db.waystone_desc or ""
        label = self.db.portal_label or "—"
        lines = [f"|w{name}|n  |x[{label}]|n"]
        if desc:
            lines.append(desc)
        lines.append("\n|xType |wwayback|n to return to the hub.|n")
        return "\n".join(lines)

    def get_hub_room(self):
        """
        Return the hub Room object for the return trip.

        Priority:
          1. db.hub_room_id explicitly set on this stone
          2. First HubWaystone found anywhere → its room
          3. Room tagged 'waystone_hub' (category 'room_type')
        """
        hub_id = self.db.hub_room_id
        if hub_id:
            try:
                from evennia.objects.models import ObjectDB
                return ObjectDB.objects.get(pk=int(hub_id))
            except Exception:
                pass

        try:
            # search_object(None, typeclass=...) returns [] here — use the manager.
            from typeclasses.waystone import HubWaystone
            stones = [s for s in HubWaystone.objects.all() if s.location]
            if stones:
                return stones[0].location
        except Exception:
            pass

        try:
            from evennia import search_tag
            tagged = search_tag("waystone_hub", category="room_type")
            if tagged:
                return tagged[0]
        except Exception:
            pass

        return None
