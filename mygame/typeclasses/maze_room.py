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

# Shown when a solution is walked correctly but its body-gate isn't satisfied yet:
# the way recognises you, and refuses anyway.
_DEFAULT_GATE_DENIALS = [
    "You walk the way out — you KNOW it's the way out, your feet are certain — and the corridor "
    "lets you get one step from the door before it folds gently closed and sets you back at the "
    "start. Not yet, the halls seem to say. You're not done yet.",
    "The path opens. For one bright second you can see the way back. Then something in you comes "
    "up short — a quota unmet, a depth not reached — and the opening seals over like water, and "
    "you're standing where you began, no closer, kept.",
    "Right combination. Wrong you. The door knows the difference, and it isn't satisfied with "
    "what you are yet. The way loops you back to start, patient, certain you'll be enough "
    "eventually. She built it to wait. She built you to get there.",
]

# Shown when the breeding-debt halls take their toll on a wrong turn.
_DEFAULT_DEBT_MSGS = [
    "You take a wrong turn and something takes you — bent over against the wall of the corridor, "
    "bred fast and deep before you're spat back to the start, dripping, more lost than before.",
    "The hall doesn't just loop you. It mounts you first — a quick, brutal rut in the dark of the "
    "wrong passage, a load pumped into you, and THEN the corner doubles back to where you began.",
    "Lost again — but not before the corridor collects its toll, filling you where you stand and "
    "leaving you to stagger on stuffed and leaking. Getting lost in here has a price, and you pay "
    "it in your holes.",
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
        self.db.maze_gate_denials  = list(_DEFAULT_GATE_DENIALS)
        # Breeding-debt halls (opt-in): per-move chance a wrong turn breeds you.
        self.db.maze_breeding_debt = 0.0
        self.db.maze_debt_species  = "contributor"
        self.db.maze_debt_msgs     = list(_DEFAULT_DEBT_MSGS)
        self.cmdset.add_default(MazeCmdSet, persistent=True)

    # ------------------------------------------------------------------
    # Configuration API
    # ------------------------------------------------------------------

    def add_solution(self, name, sequence, dest=None, reveal="", gate=None):
        """Register/replace a named solution. `sequence` is a list of directions
        (full names or aliases — normalised here). `dest` may be an object or dbref.
        `gate` (optional) makes the exit refuse to open until a body condition is met
        — a dict {"type": "conditioning"|"regression"|"devotion"|"standing"|"quota",
        "min": <number>}. quota needs no min. Preserves an existing gate if gate is None."""
        norm = [maze.normalize_direction(d) for d in sequence]
        norm = [d for d in norm if d]
        if not norm:
            return False
        dbref = None
        if dest is not None:
            dbref = dest if isinstance(dest, str) else getattr(dest, "dbref", None)
        sols = dict(self.db.maze_solutions or {})
        prev = sols.get(name) or {}
        sols[name] = {
            "sequence": norm, "dest_dbref": dbref, "reveal": reveal,
            "gate": gate if gate is not None else prev.get("gate"),
        }
        self.db.maze_solutions = sols
        return True

    def set_gate(self, name, gate):
        """Set/clear the body-gate on an existing solution. gate=None removes it."""
        sols = dict(self.db.maze_solutions or {})
        if name not in sols:
            return False
        sols[name] = dict(sols[name]); sols[name]["gate"] = gate
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
            if self._gate_ok(caller, matched):
                self._resolve(caller, matched)
            else:
                # The way recognises you — but the halls won't let you out yet.
                caller.ndb.maze_seq = []
                caller.msg("|x" + self._gate_denial(matched) + "|n")
            return

        line = maze.pick_decoy(self.db.maze_decoys or [], direction)
        if line:
            caller.msg(line)
        else:
            caller.msg(f"You go {direction}, and somehow end up back where you started.")
        # Breeding-debt halls: every wrong turn can cost you a deposit before it loops
        # you back, so getting lost IS the breeding. Opt-in per room.
        self._maybe_breeding_debt(caller, direction)

    # ------------------------------------------------------------------
    # Body gates — the halls make you earn your way out
    # ------------------------------------------------------------------

    def _gate_ok(self, caller, name):
        """True if `name`'s gate (if any) is satisfied by the traveller's body state."""
        sol = (self.db.maze_solutions or {}).get(name) or {}
        gate = sol.get("gate")
        if not gate:
            return True
        try:
            gtype = (gate.get("type") or "").lower()
            gmin = float(gate.get("min", 0) or 0)
            db = caller.db
            if gtype == "conditioning":
                return float(getattr(db, "conditioning", 0) or 0) >= gmin
            if gtype == "regression":
                return float(getattr(db, "regression", 0) or 0) >= gmin
            if gtype == "devotion":
                return float(getattr(db, "bethany_devotion", 0) or 0) >= gmin
            if gtype == "standing":
                return float(getattr(db, "facility_standing", 0) or 0) >= gmin
            if gtype == "quota":
                from world.gang_breeding import quota_met
                return bool(quota_met(caller))
        except Exception:
            return True   # never trap her on a broken gate — fail open
        return True

    def _gate_denial(self, name):
        sol = (self.db.maze_solutions or {}).get(name) or {}
        custom = sol.get("gate_denial")
        if custom:
            return custom
        pool = self.db.maze_gate_denials or _DEFAULT_GATE_DENIALS
        return random.choice(list(pool))

    def _maybe_breeding_debt(self, caller, direction):
        """If this room charges a breeding toll, a wrong turn may breed you before it
        loops you back. Reuses the real gang_breeding deposit. Opt-in: db.maze_breeding_debt
        is the per-move chance (0..1); 0/None = off."""
        chance = float(self.db.maze_breeding_debt or 0)
        if chance <= 0 or random.random() >= chance:
            return
        try:
            from world.gang_breeding import animal_holes, gang_inseminate
            holes = [z for z in animal_holes(caller).values() if z]
            if not holes:
                return
            zone = random.choice(holes)
            species = self.db.maze_debt_species or "contributor"
            gang_inseminate(caller, zone, contributors=1, fluid_type="semen", species=species)
            line = random.choice(list(self.db.maze_debt_msgs or _DEFAULT_DEBT_MSGS))
            caller.msg("|r" + line + "|n")
        except Exception:
            pass

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
