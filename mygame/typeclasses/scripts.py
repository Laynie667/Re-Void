"""
Scripts

Scripts are powerful jacks-of-all-trades. They have no in-game
existence and can be used to represent persistent game systems in some
circumstances. Scripts can also have a time component that allows them
to "fire" regularly or a limited number of times.

There is generally no "tree" of Scripts inheriting from each other.
Rather, each script tends to inherit from the base Script class and
just overloads its hooks to have it perform its function.

"""

import random
from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger
from django.conf import settings


class Script(DefaultScript):
    """
    This is the base TypeClass for all Scripts. Scripts describe
    all entities/systems without a physical existence in the game world
    that require database storage (like an economic system or
    combat tracker). They can also have a timer/ticker component.

    A script type is customized by redefining some or all of its hook
    methods and variables.
    """
    pass


class AmbientScript(DefaultScript):
    """
    Attaches to a room and periodically fires atmospheric
    messages from the room's assembled ambient pool.

    The pool is assembled dynamically each time from:
    - Room's base ambient_msgs list
    - Toggle-state specific pools
    - Mood flag pools
    - Population level pools
    - Object-contributed pools
    - Character-contributed pools
    - Haunting wisp contributions

    Attach to a room with:
        room.scripts.add(AmbientScript)
    """

    def at_script_creation(self):
        self.key = "ambient_script"
        self.desc = "Room atmospheric ambient messages"
        self.interval = self._get_interval()
        self.persistent = True
        self.repeats = 0
        self.start_delay = True

    def _get_interval(self):
        """
        Get a randomized interval between fires.
        Default: 240-480 seconds (4-8 minutes)
        """
        min_interval = getattr(
            settings, 'WISP_AMBIENT_INTERVAL_MIN', 240
        )
        max_interval = getattr(
            settings, 'WISP_AMBIENT_INTERVAL_MAX', 480
        )
        return random.randint(min_interval, max_interval)

    def at_repeat(self):
        """
        Called every interval seconds.
        Picks a random line from the ambient pool and
        sends it to all characters in the room.
        """
        room = self.obj
        if not room:
            return

        # Only fire if anyone is in the room
        occupants = [
            obj for obj in room.contents
            if hasattr(obj, 'has_account') and obj.has_account
        ]
        if not occupants:
            self.interval = self._get_interval()
            return

        # Get the full ambient pool
        try:
            pool = room.get_ambient_pool()
        except AttributeError:
            return

        if not pool:
            self.interval = self._get_interval()
            return

        # Pick a random line and resolve placeholders
        line = random.choice(pool)
        line = self._resolve_placeholders(line, room)

        if line:
            room.msg_contents(f"|x{line}|n")

        # Randomize next interval so messages don't
        # fire on a predictable rhythm
        self.interval = self._get_interval()

    def _resolve_placeholders(self, text, room):
        """
        Substitute {placeholder} variables in ambient text.

        Supported placeholders:
            {name} / {Name}         — random character in room
            {occupant} / {Occupant} — character in furniture state
        """
        if "{" not in text:
            return text

        try:
            chars = [
                obj for obj in room.contents
                if hasattr(obj, 'has_account') and obj.has_account
            ]

            if chars and "{name}" in text:
                char = random.choice(chars)
                name = (
                    char.db.rp_name
                    if hasattr(char.db, 'rp_name') and char.db.rp_name
                    else char.key
                )
                text = text.replace("{name}", name)
                text = text.replace(
                    "{Name}",
                    name[0].upper() + name[1:] if name else name
                )

            # Check for furniture occupants
            for obj in room.contents:
                if (hasattr(obj, 'db') and
                        hasattr(obj.db, 'occupant_id') and
                        obj.db.occupant_id):
                    from evennia import search_object
                    occupant = search_object(obj.db.occupant_id)
                    if occupant:
                        occ_name = (
                            occupant[0].db.rp_name
                            if hasattr(occupant[0].db, 'rp_name')
                            and occupant[0].db.rp_name
                            else occupant[0].key
                        )
                        text = text.replace("{occupant}", occ_name)
                        text = text.replace(
                            "{Occupant}",
                            occ_name[0].upper() + occ_name[1:]
                            if occ_name else occ_name
                        )

        except Exception as e:
            logger.log_err(
                f"Error resolving ambient placeholders: {e}"
            )

        return text


class SceneTimeoutScript(DefaultScript):
    """
    Attaches to a scene-locked room and auto-unlocks
    it if no activity has occurred within the timeout period.

    Attach to a room with:
        room.scripts.add(SceneTimeoutScript)
    """

    def at_script_creation(self):
        self.key = "scene_timeout_script"
        self.desc = "Auto-unlock idle scene rooms"
        self.interval = 300
        self.persistent = True
        self.repeats = 0
        self.start_delay = True

        self.db.last_activity = None
        self.db.timeout_minutes = 30

    def at_repeat(self):
        """
        Check if the scene room has been idle too long.
        """
        room = self.obj
        if not room or not room.db.scene_locked:
            return

        from evennia.utils import gametime
        now = gametime.gametime(absolute=True)
        last = self.db.last_activity

        if last is None:
            self.db.last_activity = now
            return

        timeout_seconds = self.db.timeout_minutes * 60
        if (now - last) > timeout_seconds:
            room.db.scene_locked = False
            room.msg_contents(
                "|y[Scene lock released — no activity "
                f"for {self.db.timeout_minutes} minutes.]|n"
            )
            self.delete()

    def register_activity(self):
        """Call this when activity occurs in the room."""
        from evennia.utils import gametime
        self.db.last_activity = gametime.gametime(absolute=True)


class HousingExpiryScript(DefaultScript):
    """
    Monitors housing rooms and handles expiry/eviction.
    Placeholder — full implementation when housing system is built.
    """

    def at_script_creation(self):
        self.key = "housing_expiry_script"
        self.desc = "Housing expiry monitor"
        self.interval = 86400
        self.persistent = True
        self.repeats = 0

    def at_repeat(self):
        pass

class PassiveAccumulationScript(DefaultScript):
    """
    Global 15-minute tick script.

    Runs every 900 seconds and processes all online characters:
      1. FreeformManager.cleanup_expired_freeform(char) — TTL item removal
      2. inflation tick_drain on every inflation zone
      3. WombRoom drain_tick on any installed WombRoom
      4. Size-ambient messages (breast + testes) for oversized characters

    Attach once to the global Limbo room (#2) at server start.
    There should be exactly one of these running at any time.

    To install (run once as superuser):
        @py from typeclasses.scripts import PassiveAccumulationScript; \
             from evennia.utils import create; \
             from evennia import search_object; \
             limbo = search_object("#2")[0]; \
             create.create_script(PassiveAccumulationScript, obj=limbo, \
                                  persistent=True, autostart=True)
    """

    def at_script_creation(self):
        self.key        = "passive_accumulation"
        self.desc       = "Global 15-min passive tick (freeform TTL, inflation drain, womb drain)"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 900   # 15 minutes

    def at_repeat(self):
        """Process every online character."""
        try:
            from typeclasses.characters import Character
            seen = set()
            for char in Character.objects.all():
                try:
                    if char.sessions.count() == 0:
                        continue
                    if char.id in seen:
                        continue
                    seen.add(char.id)
                    self._process_char(char)
                except Exception:
                    pass
        except Exception as e:
            logger.log_err(f"PassiveAccumulationScript error: {e}")

    def _process_char(self, char):
        # 1. Freeform TTL cleanup
        try:
            from world.freeform_manager import FreeformManager
            FreeformManager.cleanup_expired_freeform(char)
        except Exception:
            pass

        zones = getattr(char.db, "zones", None) or {}

        for zone_name, zone_data in zones.items():
            mech = (zone_data or {}).get("mechanics") or {}

            # 2. Inflation passive drain
            if mech.get("inflation"):
                try:
                    from typeclasses.inflation_item import tick_drain
                    tick_drain(char, zone_name)
                except Exception:
                    pass

            # 3. WombRoom drain tick
            wr_entry = mech.get("womb_room")
            if wr_entry:
                try:
                    from evennia import search_object
                    from typeclasses.womb_room import WombRoom
                    results = search_object(
                        wr_entry.get("room_dbref", ""), exact=True
                    )
                    if results and isinstance(results[0], WombRoom):
                        results[0].drain_tick()
                except Exception:
                    pass

            # 4. Size-ambient messages — breast and testes
            bm = mech.get("body_mod")
            if bm:
                try:
                    self._check_size_ambient(char, bm)
                except Exception:
                    pass

    def _check_size_ambient(self, char, bm_entry: dict):
        """Fire a size-ambient message if the character is oversized."""
        import random
        mod_type = bm_entry.get("mod_type", "breast")
        size     = float(bm_entry.get("size", 0.0))

        if mod_type in ("breast",):
            from world.milking_loader import get_size_ambient_tiers
            tiers = get_size_ambient_tiers()
        elif mod_type == "testicle":
            from world.milking_loader import get_testes_ambient_tiers
            tiers = get_testes_ambient_tiers()
        else:
            return

        # Find the highest matching tier
        for min_size, messages in tiers:
            if size >= min_size:
                if random.random() < 0.30:   # 30% chance per tick
                    char.msg(random.choice(messages))
                break


def ensure_passive_script():
    """
    Ensure exactly one PassiveAccumulationScript is running on Limbo.
    Call from server startup or manually as a superuser.
    """
    from evennia import search_object
    from evennia.utils import create

    limbo_results = search_object("#2", exact=True)
    if not limbo_results:
        return

    limbo = limbo_results[0]
    existing = [s for s in limbo.scripts.all()
                if s.key == "passive_accumulation"]
    if not existing:
        create.create_script(
            PassiveAccumulationScript,
            obj=limbo,
            persistent=True,
            autostart=True,
        )
