"""
typeclasses/furniture_session.py

FurnitureSessionScript — shared base for room-attached furniture session
scripts (rocking horse, edge machine, milking stanchion, display pedestal).

It exists to retire two recurring bugs:

  1. Stuck-running furniture. Each furniture used to be found one way by its
     start command (by script key) and a different way by its stop command
     (by isinstance). A persistent script whose typeclass fails to resolve
     loads as a plain DefaultScript — it keeps the key but loses the class —
     so the isinstance-based stop silently skipped it and start kept reporting
     "already running". find()/stop_all() here match by BOTH, so leaked or
     mis-typed scripts always get cleaned up.

  2. Stale scripts on empty furniture. note_occupancy() auto-stops a session
     after `empty_grace` consecutive ticks with nobody on/in the furniture,
     so a session can't outlive the rider who started it.

Subclasses set:
    furniture_key  — the script key (and the key find() matches leaked scripts by)
    zone_attr      — room.db attribute naming the active zone
    label          — human label for `showfurniture`
    verbs          — command-syntax hints for `showfurniture`
    empty_grace    — consecutive empty ticks before auto-stop (default 3)

Subclasses keep their own at_repeat; they just call

    if self.note_occupancy(bool(riders)):
        return

once per tick (and may use self.occupants() to find riders).
"""

from evennia import DefaultScript


class FurnitureSessionScript(DefaultScript):
    """Base class for room-attached furniture session scripts."""

    furniture_key = "furniture_session"
    zone_attr     = "furniture_zone"
    label         = "Furniture"
    verbs         = []
    empty_grace   = 3

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    def at_script_creation(self):
        self.key        = self.furniture_key
        self.persistent = True
        self.repeats    = 0
        self.interval   = 30
        self.db.empty_ticks = 0

    # ------------------------------------------------------------------
    # Discovery / lifecycle — one canonical way to find and stop sessions
    # ------------------------------------------------------------------
    @classmethod
    def find(cls, room):
        """Return every session of this furniture on `room`.

        Matches by class OR by key, so a persistent script whose typeclass
        failed to resolve (loads as DefaultScript, keeps the key) is still
        found and can be cleaned up.
        """
        if not room:
            return []
        return [
            s for s in room.scripts.all()
            if isinstance(s, cls) or getattr(s, "key", "") == cls.furniture_key
        ]

    @classmethod
    def is_running(cls, room):
        return bool(cls.find(room))

    @classmethod
    def stop_all(cls, room):
        """Stop every matching session on the room. Returns the count stopped."""
        scripts = cls.find(room)
        for s in scripts:
            try:
                s.stop()
            except Exception:
                pass
        return len(scripts)

    # ------------------------------------------------------------------
    # Occupant helpers
    # ------------------------------------------------------------------
    def zone_name(self):
        room = self.obj
        if not room:
            return None
        return getattr(room.db, self.zone_attr, None)

    def occupants(self, room=None, zone=None):
        """Yield Characters seated or restrained in the furniture's zone."""
        room = room or self.obj
        if not room:
            return
        if zone is None:
            zone = self.zone_name()
        if not zone:
            return
        from typeclasses.characters import Character
        for char in room.contents:
            if not isinstance(char, Character):
                continue
            occ = (getattr(char.db, "seated_zone", None)
                   or getattr(char.db, "restrained_zone", None))
            if occ == zone:
                yield char

    def note_occupancy(self, present):
        """Record whether anyone is on the furniture this tick.

        Auto-stops the session after `empty_grace` consecutive empty ticks.
        Returns True if the session just auto-stopped — callers should then
        return from at_repeat immediately.
        """
        if present:
            self.db.empty_ticks = 0
            return False
        self.db.empty_ticks = (self.db.empty_ticks or 0) + 1
        if self.db.empty_ticks >= self.empty_grace:
            self.stop()
            return True
        return False
