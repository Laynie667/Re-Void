"""
typeclasses/maze_room.py — the combination-lock / "Lost Woods" room.

Directional moves don't lead anywhere normal: every direction is an entry into a
COMBINATION, tracked per-character. Completing one of the room's solution sequences
reveals (teleports you to) that solution's destination — the way deeper, or the way
back to the preceding room. Anything else fires a decoy line so it feels like you
moved and got turned around.

Build/configure (from `@py` or a build script):
    room = create_object("typeclasses.maze_room.MazeRoom", key="The Lost Hallway")
    room.add_solution("deeper", ["north","north","east","west"], dest=deep_room,
                      reveal="The corridor finally stops doubling back...")
    room.add_solution("back",   ["south","south"], dest=hub_room,
                      reveal="You round the corner and there's the blast door again.")
    room.db.maze_decoys = ["You head {dir}... and come out where you started.", ...]
    room.db.maze_reset_on_wrong = True   # classic Lost Woods (default)

The per-character sequence lives in `caller.ndb.maze_seq` — non-persistent, so it
resets on logout and the §0 floor never has to know it exists. Teleport-out commands
(escape/force_clear) move you straight out regardless of any solution.
"""

import random

from evennia import Command, CmdSet, search_object
from world import maze
from .rooms import Room


_DEFAULT_DECOYS = [
    "You head {dir} — and the path bends, and bends again, and spits you out exactly where you started.",
    "Three steps {dir} and the trees (or walls, or whatever they are) close ranks behind you. Same place. Same wrong light.",
    "You go {dir} with purpose. The purpose lasts about ten feet before the way doubles back on itself and deposits you here again.",
    "{dir}, you're sure of it — but the corner you turn is the corner you just left.",
    "The way {dir} looks different this time. It isn't. You're back where you began, breathing a little harder.",
]


class CmdMazeMove(Command):
    """Intercept a single directional word inside a maze room."""

    auto_help = False
    locks = "cmd:all()"

    def func(self):
        room = self.caller.location
        if not room or not hasattr(room, "maze_move"):
            self.caller.msg("You can't go that way.")
            return
        room.maze_move(self.caller, self.key)


class MazeCmdSet(CmdSet):
    """Directional movement commands for maze rooms (replaces normal exits)."""

    key = "maze_cmdset"
    priority = 2
    # Take precedence over any stray exit commands so the maze stays in control.
    mergetype = "Union"

    def at_cmdset_creation(self):
        for direction, aliases in maze.DIRECTIONS.items():
            cmd = CmdMazeMove()
            cmd.key = direction
            cmd.aliases = list(aliases)
            self.add(cmd)


class MazeRoom(Room):
    """A room whose directions are a combination lock (see module docstring)."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.room_type          = "maze"
        # name -> {"sequence": [...], "dest_dbref": "#NN", "reveal": "..."}
        self.db.maze_solutions     = {}
        self.db.maze_decoys        = list(_DEFAULT_DECOYS)
        self.db.maze_reset_on_wrong = True
        self.cmdset.add_default(MazeCmdSet, persistent=True)

    # ------------------------------------------------------------------
    # Configuration API
    # ------------------------------------------------------------------

    def add_solution(self, name, sequence, dest=None, reveal=""):
        """Register/replace a named solution. `sequence` is a list of directions
        (full names or aliases — normalised here). `dest` may be an object or dbref."""
        norm = [maze.normalize_direction(d) for d in sequence]
        norm = [d for d in norm if d]
        if not norm:
            return False
        dbref = None
        if dest is not None:
            dbref = dest if isinstance(dest, str) else getattr(dest, "dbref", None)
        sols = dict(self.db.maze_solutions or {})
        sols[name] = {"sequence": norm, "dest_dbref": dbref, "reveal": reveal}
        self.db.maze_solutions = sols
        return True

    def solution_hint(self, name):
        """Readable form of a solution's sequence (for map/hint items)."""
        sol = (self.db.maze_solutions or {}).get(name)
        if not sol:
            return None
        return maze.describe_solution(sol["sequence"])

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------

    def _solution_sequences(self):
        return {n: s["sequence"] for n, s in (self.db.maze_solutions or {}).items()}

    def maze_move(self, caller, direction):
        """Process one directional move. Either teleport (solution complete) or decoy."""
        direction = maze.normalize_direction(direction) or direction
        seq = list(getattr(caller.ndb, "maze_seq", None) or [])
        new_seq, matched = maze.evaluate_move(
            seq, direction, self._solution_sequences(),
            reset_on_wrong=bool(self.db.maze_reset_on_wrong),
        )
        caller.ndb.maze_seq = new_seq

        if matched:
            self._resolve(caller, matched)
            return

        line = maze.pick_decoy(self.db.maze_decoys or [], direction)
        if line:
            caller.msg(line)
        else:
            caller.msg(f"You go {direction}, and somehow end up back where you started.")

    def _resolve(self, caller, name):
        """A solution completed — reveal it: announce, then move the traveller."""
        sol = (self.db.maze_solutions or {}).get(name) or {}
        reveal = sol.get("reveal") or "The way opens, and you step through."
        caller.ndb.maze_seq = []
        caller.msg(f"|w{reveal}|n")

        dbref = sol.get("dest_dbref")
        if not dbref:
            return  # configured but no destination yet — prose-only reveal
        dest = search_object(dbref, exact=True)
        if not dest:
            caller.msg("|x(The way is revealed, but its destination is missing — tell a builder.)|n")
            return
        caller.move_to(dest[0], quiet=False)

    # ------------------------------------------------------------------
    # Each fresh entry restarts the combination.
    # ------------------------------------------------------------------

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        super().at_object_receive(moved_obj, source_location, **kwargs)
        try:
            if hasattr(moved_obj, "ndb"):
                moved_obj.ndb.maze_seq = []
        except Exception:
            pass
