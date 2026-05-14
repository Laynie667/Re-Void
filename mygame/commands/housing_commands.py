"""
commands/housing_commands.py

Player housing commands for Re:Void.

Commands
--------
home        — teleport to your home room
sethome     — set your home to the current room (must be owner or friend)
grid        — return to the nearest hub room
housing     — manage your housing rooms (lock, friends, builders, dig, exits, list)
"""

from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _char_name(character):
    return (character.db.rp_name or character.key) if character else "?"


def _get_hub_room():
    """Return the first room with db.is_hub=True, or None."""
    from evennia.objects.models import ObjectDB
    for obj in ObjectDB.objects.filter(
        db_typeclass_path__contains="rooms"
    ).order_by("pk"):
        try:
            if getattr(obj.db, "is_hub", False):
                return obj
        except Exception:
            continue
    return None


def _get_all_housing_rooms(character_id):
    """Return all HousingRoom objects owned by this character."""
    from evennia.objects.models import ObjectDB
    from typeclasses.housing import HousingRoom
    owned = []
    for obj in ObjectDB.objects.filter(
        db_typeclass_path="typeclasses.housing.HousingRoom"
    ):
        try:
            room = obj.typeclass
            if room.db.housing_owner_id == character_id:
                owned.append(room)
        except Exception:
            continue
    return owned


def _is_housing_room(room):
    from typeclasses.housing import HousingRoom
    return isinstance(room, HousingRoom)


# ---------------------------------------------------------------------------
# home
# ---------------------------------------------------------------------------

class CmdHome(Command):
    """
    Teleport to your home room.

    Usage:
        home

    Your home room is the housing room you have set with 'sethome'.
    Use 'grid' to return to the hub.
    """
    key = "home"
    locks = "cmd:all()"
    help_category = "Housing"

    def func(self):
        char = self.caller
        home_id = char.db.housing_home_id

        if not home_id:
            self.msg(
                "|xYou don't have a home set.\n"
                "Purchase a tent from Durgin Ironwood to get started, "
                "then use |wsethome|n to designate your home room.|n"
            )
            return

        from evennia.objects.models import ObjectDB
        try:
            home = ObjectDB.objects.get(pk=home_id)
        except Exception:
            self.msg("|xYour home room no longer exists. Use 'sethome' to set a new one.|n")
            char.db.housing_home_id = None
            return

        if char.location == home:
            self.msg("|xYou are already home.|n")
            return

        name = _char_name(char)
        char.move_to(home, quiet=True)
        char.msg(f"|xYou step through the void and arrive home.|n")
        home.msg_contents(
            f"|x{name} arrives home.|n",
            exclude=char,
        )
        char.execute_cmd("look")


# ---------------------------------------------------------------------------
# sethome
# ---------------------------------------------------------------------------

class CmdSetHome(Command):
    """
    Set your current room as your home.

    Usage:
        sethome

    You must be the owner or a friend of this room to set it as home.
    Your home is where 'home' will take you.
    """
    key = "sethome"
    locks = "cmd:all()"
    help_category = "Housing"

    def func(self):
        char = self.caller
        room = char.location

        if not _is_housing_room(room):
            self.msg("|xYou can only set a housing room as your home.|n")
            return

        if not room.can_set_home(char):
            self.msg(
                "|xYou must be the owner or a friend of this room "
                "to set it as home.|n"
            )
            return

        char.db.housing_home_id = room.id
        self.msg(f"|w{room.key}|n is now set as your home.")


# ---------------------------------------------------------------------------
# grid
# ---------------------------------------------------------------------------

class CmdGrid(Command):
    """
    Return to the hub grid.

    Usage:
        grid

    Teleports you back to the main hub area from anywhere.
    """
    key = "grid"
    locks = "cmd:all()"
    help_category = "Housing"

    def func(self):
        char = self.caller
        hub = _get_hub_room()

        if not hub:
            self.msg("|xNo hub room found. Ask a staff member for help.|n")
            return

        if char.location == hub:
            self.msg("|xYou are already at the grid.|n")
            return

        name = _char_name(char)
        char.move_to(hub, quiet=True)
        char.msg("|xYou step through the void and emerge on the grid.|n")
        hub.msg_contents(
            f"|x{name} steps in from the void.|n",
            exclude=char,
        )
        char.execute_cmd("look")


# ---------------------------------------------------------------------------
# housing
# ---------------------------------------------------------------------------

class CmdHousing(MuxCommand):
    """
    Manage your housing rooms.

    Usage:
        housing                         — show your housing summary
        housing list                    — list all your rooms
        housing lock                    — lock this room (owner only)
        housing unlock                  — unlock this room (owner only)
        housing friend add <name>       — add someone to the friend list
        housing friend remove <name>    — remove from friend list
        housing builder add <name>      — grant build rights in this room
        housing builder remove <name>   — revoke build rights
        housing dig <direction> = <name> — spend a room slot, create + link a room
        housing exit <direction> = <new name> — rename/realias an exit here

    Digging costs one room slot from your HousingPlot allocation.
    You must have remaining slots to dig.  Purchase more from Durgin Ironwood.

    See also: home, sethome, grid
    """
    key = "housing"
    aliases = ["house"]
    locks = "cmd:all()"
    help_category = "Housing"

    # Valid exit aliases for dig
    VALID_DIRS = {
        "north": "south", "south": "north",
        "east":  "west",  "west":  "east",
        "up":    "down",  "down":  "up",
        "in":    "out",   "out":   "in",
        "ne":    "sw",    "sw":    "ne",
        "nw":    "se",    "se":    "nw",
    }

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            self._show_summary(char)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        dispatch = {
            "list":    self._cmd_list,
            "lock":    self._cmd_lock,
            "unlock":  self._cmd_unlock,
            "friend":  self._cmd_friend,
            "builder": self._cmd_builder,
            "dig":     self._cmd_dig,
            "exit":    self._cmd_exit,
        }

        handler = dispatch.get(subcmd)
        if handler:
            handler(char, rest)
        else:
            self.msg(
                "Unknown subcommand. Try: housing list / lock / unlock / "
                "friend / builder / dig / exit"
            )

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #

    def _show_summary(self, char):
        from web.housing.models import HousingPlot
        plot = HousingPlot.get_or_none(char.id)

        if not plot:
            self.msg(
                "|xYou don't own any housing yet.\n"
                "Visit Durgin Ironwood to purchase a tent.|n"
            )
            return

        rooms = _get_all_housing_rooms(char.id)
        room = char.location
        in_housing = _is_housing_room(room) and room.is_owner(char)

        lines = [
            f"|wHousing — {_char_name(char)}|n",
            f"  Rooms: {plot.rooms_used}/{plot.rooms_total} "
            f"({plot.rooms_available} slot{'s' if plot.rooms_available != 1 else ''} available)",
        ]

        if in_housing:
            lines.append("")
            lines.append("|wCurrent room:|n")
            lines.append(room.get_housing_status())

        lines.append(
            "\n|xType |whousing list|n|x for all your rooms.|n"
        )
        self.msg("\n".join(lines))

    # ------------------------------------------------------------------ #
    # List
    # ------------------------------------------------------------------ #

    def _cmd_list(self, char, args):
        rooms = _get_all_housing_rooms(char.id)
        if not rooms:
            self.msg("|xYou own no housing rooms.|n")
            return

        home_id = char.db.housing_home_id
        lines = [f"|wYour housing rooms ({len(rooms)}):|n"]
        for room in rooms:
            lock = "|r[locked]|n" if room.db.housing_locked else "|g[open]|n"
            home = " |y[home]|n" if room.id == home_id else ""
            lines.append(f"  |w{room.key}|n #{room.id}  {lock}{home}")
        self.msg("\n".join(lines))

    # ------------------------------------------------------------------ #
    # Lock / Unlock
    # ------------------------------------------------------------------ #

    def _cmd_lock(self, char, args):
        room = char.location
        if not _is_housing_room(room):
            self.msg("|xYou must be in one of your housing rooms to lock it.|n")
            return
        if not room.is_owner(char):
            self.msg("|xOnly the room owner can lock or unlock it.|n")
            return
        if room.db.housing_locked:
            self.msg("|xThis room is already locked.|n")
            return
        room.db.housing_locked = True
        self.msg("|rRoom locked.|n Only you and your friends can enter.")
        room.msg_contents(
            "|r[This room has been locked.]|n",
            exclude=char,
        )

    def _cmd_unlock(self, char, args):
        room = char.location
        if not _is_housing_room(room):
            self.msg("|xYou must be in one of your housing rooms to unlock it.|n")
            return
        if not room.is_owner(char):
            self.msg("|xOnly the room owner can lock or unlock it.|n")
            return
        if not room.db.housing_locked:
            self.msg("|xThis room is already unlocked.|n")
            return
        room.db.housing_locked = False
        self.msg("|gRoom unlocked.|n Anyone may enter.")
        room.msg_contents(
            "|g[This room has been unlocked.]|n",
            exclude=char,
        )

    # ------------------------------------------------------------------ #
    # Friend
    # ------------------------------------------------------------------ #

    def _cmd_friend(self, char, args):
        parts = args.split(None, 1)
        if len(parts) < 2:
            self.msg(
                "Usage: housing friend add <name>\n"
                "       housing friend remove <name>"
            )
            return

        action, target_name = parts[0].lower(), parts[1]
        room = char.location

        if not _is_housing_room(room) or not room.is_owner(char):
            self.msg(
                "|xYou must be in one of your own housing rooms "
                "to manage the friend list.|n"
            )
            return

        target = char.search(target_name)
        if not target:
            return

        if action == "add":
            if room.add_friend(target):
                tname = _char_name(target)
                self.msg(f"|w{tname}|n added to the friend list.")
                target.msg(
                    f"|w{_char_name(char)}|n has added you as a friend "
                    f"to |w{room.key}|n."
                )
            else:
                self.msg("|xThey are already on the friend list.|n")

        elif action == "remove":
            if room.remove_friend(target):
                tname = _char_name(target)
                self.msg(f"|w{tname}|n removed from the friend list.")
                target.msg(
                    f"You have been removed from the friend list of "
                    f"|w{room.key}|n."
                )
            else:
                self.msg("|xThey are not on the friend list.|n")

        else:
            self.msg("Usage: housing friend add/remove <name>")

    # ------------------------------------------------------------------ #
    # Builder
    # ------------------------------------------------------------------ #

    def _cmd_builder(self, char, args):
        parts = args.split(None, 1)
        if len(parts) < 2:
            self.msg(
                "Usage: housing builder add <name>\n"
                "       housing builder remove <name>"
            )
            return

        action, target_name = parts[0].lower(), parts[1]
        room = char.location

        if not _is_housing_room(room) or not room.is_owner(char):
            self.msg(
                "|xYou must be in one of your own housing rooms "
                "to manage build rights.|n"
            )
            return

        target = char.search(target_name)
        if not target:
            return

        if action == "add":
            if room.add_builder(target):
                tname = _char_name(target)
                self.msg(f"|w{tname}|n granted build rights in this room.")
                target.msg(
                    f"|w{_char_name(char)}|n has granted you build rights "
                    f"in |w{room.key}|n."
                )
            else:
                self.msg("|xThey already have build rights here.|n")

        elif action == "remove":
            if room.remove_builder(target):
                tname = _char_name(target)
                self.msg(f"|w{tname}|n's build rights revoked.")
                target.msg(
                    f"Your build rights in |w{room.key}|n have been revoked."
                )
            else:
                self.msg("|xThey don't have build rights here.|n")

        else:
            self.msg("Usage: housing builder add/remove <name>")

    # ------------------------------------------------------------------ #
    # Dig
    # ------------------------------------------------------------------ #

    def _cmd_dig(self, char, args):
        """
        housing dig <direction> = <room name>

        Spends one room slot and creates a new HousingRoom linked in
        both directions from the current room.
        """
        from web.housing.models import HousingPlot
        from typeclasses.housing import HousingRoom
        from evennia.utils import create

        if "=" not in args:
            self.msg(
                "Usage: housing dig <direction> = <room name>\n"
                "Example: housing dig north = My Bedroom"
            )
            return

        direction, _, room_name = args.partition("=")
        direction = direction.strip().lower()
        room_name = room_name.strip()

        if not direction or not room_name:
            self.msg("Specify both a direction and a room name.")
            return

        if direction not in self.VALID_DIRS:
            self.msg(
                f"'{direction}' is not a valid direction.\n"
                f"Valid: {', '.join(sorted(self.VALID_DIRS.keys()))}"
            )
            return

        room = char.location
        if not _is_housing_room(room) or not room.can_build(char):
            self.msg(
                "|xYou must be in a housing room where you have "
                "build rights to dig.|n"
            )
            return

        # Check for existing exit in that direction
        existing = room.search(
            direction,
            typeclass="evennia.objects.objects.DefaultExit",
            location=room,
        )
        if existing:
            self.msg(
                f"|xThere is already an exit '{direction}' here.|n"
            )
            return

        # Check plot allocation
        plot = HousingPlot.get_or_none(char.id)
        if not plot:
            self.msg("|xYou don't have a housing plot. Buy a tent first.|n")
            return
        if plot.rooms_available < 1:
            self.msg(
                f"|xNo room slots remaining "
                f"({plot.rooms_used}/{plot.rooms_total} used).\n"
                f"Purchase more from Durgin Ironwood.|n"
            )
            return

        # Find the owner of the current room — new room inherits same owner
        owner_id = room.db.housing_owner_id

        # Create the new HousingRoom
        new_room = create.create_object(
            typeclass=HousingRoom,
            key=room_name,
            report_to=char,
        )
        new_room.db.housing_owner_id = owner_id
        new_room.db.housing_friends  = list(room.db.housing_friends or [])
        new_room.db.housing_builders = list(room.db.housing_builders or [])
        new_room.db.housing_locked   = room.db.housing_locked

        # Create forward exit
        return_dir = self.VALID_DIRS[direction]
        create.create_object(
            typeclass="evennia.objects.objects.DefaultExit",
            key=direction,
            location=room,
            destination=new_room,
            report_to=char,
        )
        # Create return exit
        create.create_object(
            typeclass="evennia.objects.objects.DefaultExit",
            key=return_dir,
            location=new_room,
            destination=room,
            report_to=char,
        )

        # Consume the slot
        plot.rooms_used += 1
        plot.save()

        self.msg(
            f"|gRoom created:|n |w{room_name}|n to the {direction}.\n"
            f"|x[{plot.rooms_available} slot{'s' if plot.rooms_available != 1 else ''} remaining]|n"
        )
        room.msg_contents(
            f"|x{_char_name(char)} opens up a new room to the {direction}.|n",
            exclude=char,
        )

    # ------------------------------------------------------------------ #
    # Exit rename
    # ------------------------------------------------------------------ #

    def _cmd_exit(self, char, args):
        """
        housing exit <direction> = <new name>

        Renames an exit in the current housing room.
        The exit's destination is unchanged; only the key/alias changes.
        """
        if "=" not in args:
            self.msg(
                "Usage: housing exit <direction> = <new name>\n"
                "Example: housing exit north = To the Loft"
            )
            return

        direction, _, new_name = args.partition("=")
        direction = direction.strip().lower()
        new_name  = new_name.strip()

        if not direction or not new_name:
            self.msg("Specify both a direction and a new name.")
            return

        room = char.location
        if not _is_housing_room(room) or not room.can_build(char):
            self.msg(
                "|xYou must be in a housing room where you have "
                "build rights to rename exits.|n"
            )
            return

        exit_obj = None
        for obj in room.exits:
            if obj.key.lower() == direction or direction in [
                a.lower() for a in (obj.aliases.all() or [])
            ]:
                exit_obj = obj
                break

        if not exit_obj:
            self.msg(f"|xNo exit '{direction}' found in this room.|n")
            return

        old_name = exit_obj.key
        exit_obj.key = new_name
        self.msg(
            f"Exit renamed from |w{old_name}|n to |w{new_name}|n."
        )
