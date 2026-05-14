"""
commands/navigation_commands.py

Compass shortcut commands for player navigation.
Provides n/s/e/w/ne/nw/se/sw/u/d as aliases for traversing
exits by their common directional names.

Works by searching the current room for an exit whose name or
aliases match the direction, then traversing it exactly as if
the player had typed the full exit name.
"""

from evennia.commands.command import Command


# Mapping: shortcut key -> list of exit names/aliases to try, in order
DIRECTION_MAP = {
    "n":  ["north", "n"],
    "s":  ["south", "s"],
    "e":  ["east",  "e"],
    "w":  ["west",  "w"],
    "ne": ["northeast", "ne"],
    "nw": ["northwest", "nw"],
    "se": ["southeast", "se"],
    "sw": ["southwest", "sw"],
    "u":  ["up",   "u"],
    "d":  ["down", "d"],
}


def _traverse(caller, direction_names):
    """
    Find an exit in the caller's location matching any of the given names/aliases
    and traverse it. Returns True if an exit was found and traversed.
    """
    location = caller.location
    if not location:
        caller.msg("You have no location to move from.")
        return False

    exits = location.exits
    for exit_obj in exits:
        # Check exit key and all aliases
        names = [exit_obj.key.lower()] + [a.lower() for a in exit_obj.aliases.all()]
        for direction in direction_names:
            if direction.lower() in names:
                exit_obj.at_traverse(caller, exit_obj.destination)
                return True

    return False


def _make_direction_cmd(cmd_key, direction_names, display_name):
    """
    Factory that produces a direction Command class.
    """
    class DirectionCmd(Command):
        key = cmd_key
        locks = "cmd:all()"
        help_category = "Navigation"
        _directions = direction_names
        _display = display_name

        def func(self):
            if not _traverse(self.caller, self._directions):
                self.caller.msg(f"You can't go {self._display} from here.")

    DirectionCmd.__name__ = f"Cmd{cmd_key.upper()}"
    DirectionCmd.__qualname__ = f"Cmd{cmd_key.upper()}"
    return DirectionCmd


# Build all direction command classes
CmdN  = _make_direction_cmd("n",  ["north",     "n"],  "north")
CmdS  = _make_direction_cmd("s",  ["south",     "s"],  "south")
CmdE  = _make_direction_cmd("e",  ["east",      "e"],  "east")
CmdW  = _make_direction_cmd("w",  ["west",      "w"],  "west")
CmdNE = _make_direction_cmd("ne", ["northeast", "ne"], "northeast")
CmdNW = _make_direction_cmd("nw", ["northwest", "nw"], "northwest")
CmdSE = _make_direction_cmd("se", ["southeast", "se"], "southeast")
CmdSW = _make_direction_cmd("sw", ["southwest", "sw"], "southwest")
CmdU  = _make_direction_cmd("u",  ["up",        "u"],  "up")
CmdD  = _make_direction_cmd("d",  ["down",      "d"],  "down")


ALL_NAVIGATION_CMDS = [
    CmdN, CmdS, CmdE, CmdW,
    CmdNE, CmdNW, CmdSE, CmdSW,
    CmdU, CmdD,
]
