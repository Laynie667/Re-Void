"""
typeclasses/waypost.py

Waypost — a player-purchased item that registers a personal realm address.

Players buy wayposts from Durgin Ironwood and drop them in any room they
own. Once given a realm address (a single magic word), anyone who speaks
that word near a hub waystone is teleported to the room containing the
waypost.

Touching/activating the waypost returns the player to the hub.

Commands (from the WaypostCmdSet, available whenever the waypost is in
the room OR in the player's inventory):

  waypost                — show this waypost's current info
  waypost address <word> — claim a realm address for this waypost
  waypost clear          — release the realm address (deactivate)
  wayback                — return to the hub from this waypost
"""

import random

from evennia import DefaultObject


_RETURN_SELF_MSGS = [
    "The waypost pulses warmly. The runes light in sequence. The hub reshapes around you.",
    "You lay a hand on the post. The world folds — and you are back.",
    "A resonance answers your touch. Brief, certain. You are in the hub before it fully fades.",
    "The waypost knows where you mean. You are there before you've finished thinking it.",
]


class Waypost(DefaultObject):
    """
    A player-purchased realm-post.

    Set a realm address, drop it in a room you own, and others can say
    the address at any hub waystone to travel to your room.
    """

    def at_object_creation(self):
        self.db.realm_address    = None   # the magic word; None = inactive
        self.db.owner_account_id = None   # account ID of the purchasing player
        self.db.owner_char_id    = None   # character ID at time of purchase
        self.db.owner_name       = None   # display name for messages
        # Attach commands
        from commands.waystone_commands import WaypostCmdSet
        self.cmdset.add_default(WaypostCmdSet)

    def return_appearance(self, looker, **kwargs):
        address = self.db.realm_address
        owner   = self.db.owner_name or "unknown"
        lines   = ["|wWaypost|n  |x(Ironwood Housing Co.)|n"]
        lines.append(
            "A post of dark carved wood, engraved with flowing runes. "
            "When given a name — a realm address — it becomes a "
            "destination that the hub waystones will recognize."
        )
        if address:
            lines.append(f"\n|xRealm address:|n  |w{address}|n")
            lines.append(
                "|xActive. Say this address at any hub waystone to arrive here.|n"
            )
        else:
            lines.append(
                "\n|x[No realm address set]|n  "
                "Use |wwaypost address <word>|n to claim one."
            )
        lines.append(f"|xOwner:|n  {owner}")
        lines.append("\n|xType |wwayback|n to return to the hub.|n")
        return "\n".join(lines)

    def get_hub_room(self):
        """
        Return the hub Room for the return trip.
        Checks HubWaystone locations first, then waystone_hub tag.
        """
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

    # ------------------------------------------------------------------
    # Address management helpers (called from CmdWaypost)
    # ------------------------------------------------------------------

    def set_address(self, address):
        """Set realm address. Returns (True, msg) or (False, error_msg)."""
        import re
        addr = address.strip().lower()

        if not addr:
            return False, "An address can't be empty."

        if not re.match(r'^[a-z0-9_-]+$', addr):
            return False, (
                "Realm addresses must be a single word — letters, numbers, "
                "hyphens, and underscores only."
            )

        if len(addr) > 30:
            return False, "Realm addresses must be 30 characters or fewer."

        # Check for conflicts (skip self)
        if Waypost.address_is_taken(addr, exclude=self):
            return False, (
                f"The address '|w{addr}|n' is already registered. "
                f"Choose another."
            )

        self.db.realm_address = addr
        return True, f"Realm address set to |w{addr}|n."

    def clear_address(self):
        """Release the realm address."""
        old = self.db.realm_address
        self.db.realm_address = None
        if old:
            return f"Realm address '|w{old}|n' released. This waypost is now inactive."
        return "This waypost had no address to clear."

    @staticmethod
    def address_is_taken(address, exclude=None):
        """
        Return True if another active waypost or portal waystone uses this address.

        Args:
            address:  Normalized (lowercase) address string.
            exclude:  A Waypost to skip during the check (used when updating own address).
        """
        addr = address.strip().lower()

        try:
            # search_object(None, typeclass=...) returns [] here — use the managers,
            # or address-collision detection silently never fires.
            from typeclasses.waypost import Waypost
            from typeclasses.waystone import PortalWaystone

            # Check other wayposts
            for wp in Waypost.objects.all():
                if exclude and wp.id == exclude.id:
                    continue
                if (wp.db.realm_address or "").strip().lower() == addr:
                    return True

            # Check portal waystones
            for p in PortalWaystone.objects.all():
                if (p.db.portal_label or "").strip().lower() == addr:
                    return True

        except Exception:
            pass

        return False
