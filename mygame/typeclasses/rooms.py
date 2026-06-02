"""
Room

Rooms are the core of the world. Each room is a node in the world
graph, connected to other rooms via exits.

This Room typeclass implements the full 17-layer description system
including time-of-day, weather, atmosphere toggles, stateful object
contributions, wisp visibility, haunting ambient, scene state,
and population awareness.

"""

import random
from evennia.objects.objects import DefaultRoom
from evennia.utils import logger
from .objects import ObjectParent


class Room(ObjectParent, DefaultRoom):
    """
    The base Room typeclass for ReVoid.

    Description layers (assembled in order by return_appearance):
        1.  Base description          — permanent, owner-written
        2.  Time-of-day layer         — dawn/morning/afternoon/dusk/evening/midnight
        3.  Weather layer             — only for rooms with windows/open-air
        4.  Season layer              — tied to IC calendar
        5.  Toggle state layer        — fire/lights/curtains/music
        6.  Stateful object lines     — contributed by objects in the room
        7.  Population/crowd layer    — empty/quiet/few/busy/crowded
        8.  Mood/atmosphere flag      — intimate/tense/festive/mournful
        9.  World state layer         — global IC events
        10. Scene state layer         — scene locked, logging, content warnings
        11. Ambient pool (base)       — owner-written, fires via script
        12. Ambient pool (objects)    — contributed by active objects
        13. Ambient pool (characters) — contributed by characters present
        14. Character presence lines  — name + IC presence + body language
        15. Wisp presence lines       — visible wisps (hub or opt-in)
        16. Examine closely layer     — hidden details, room history
        17. Entry/arrival description — shown on arrival, not on look
    """

    def at_object_creation(self):
        """
        Called once when the room is first created.
        Sets all default room attributes.
        """
        super().at_object_creation()

        # ---------------------------------------------------------------
        # Core description layers
        # ---------------------------------------------------------------
        self.db.desc = ""

        self.db.time_descs = {
            "dawn":      "",
            "morning":   "",
            "afternoon": "",
            "dusk":      "",
            "evening":   "",
            "midnight":  "",
        }

        self.db.weather_descs = {
            "clear":      "",
            "overcast":   "",
            "rain":       "",
            "heavy_rain": "",
            "fog":        "",
            "storm":      "",
            "snow":       "",
        }

        self.db.has_weather = False
        self.db.has_seasons = False

        self.db.season_descs = {
            "spring": "",
            "summer": "",
            "autumn": "",
            "winter": "",
        }

        # ---------------------------------------------------------------
        # Atmosphere toggles
        # ---------------------------------------------------------------
        self.db.toggles = {
            "lights":    "bright",
            "fireplace": "unlit",
            "curtains":  "open",
            "music":     "silent",
        }

        self.db.toggle_descs = {
            "lights": {
                "bright": "",
                "dim":    "",
                "dark":   "",
            },
            "fireplace": {
                "lit":   "",
                "unlit": "",
            },
            "curtains": {
                "open":  "",
                "drawn": "",
            },
            "music": {
                "silent": "",
                "soft":   "",
                "loud":   "",
            },
        }

        # ---------------------------------------------------------------
        # Population descriptions
        # ---------------------------------------------------------------
        self.db.crowd_descs = {
            "empty":   "",
            "quiet":   "",
            "few":     "",
            "busy":    "",
            "crowded": "",
        }

        # ---------------------------------------------------------------
        # Mood / atmosphere flag
        # ---------------------------------------------------------------
        self.db.mood_flag = None
        self.db.mood_descs = {}

        # ---------------------------------------------------------------
        # World state integration
        # ---------------------------------------------------------------
        self.db.world_state_flags = []
        self.db.world_state_descs = {}

        # ---------------------------------------------------------------
        # Scene state
        # ---------------------------------------------------------------
        self.db.scene_locked = False
        self.db.scene_invite_list = []
        self.db.scene_logging = False
        self.db.scene_log = []
        self.db.scene_title = None
        self.db.scene_prompt = None
        self.db.content_warnings = []
        self.db.scene_tone = None

        # Scene dressing tools (rp_tools_commands)
        # Atmospheric overlay — shown after base desc
        self.db.scene_stage_desc = ""
        # Lookable details — {keyword: text}, checked on 'look at X'
        self.db.scene_details = {}
        # Prop tracking — list of prop object ids for scene/end cleanup
        self.db.scene_props = []

        # ---------------------------------------------------------------
        # Ambient message pools
        # ---------------------------------------------------------------
        self.db.ambient_msgs = []
        self.db.ambient_msgs_by_toggle = {}
        self.db.ambient_msgs_by_mood = {}
        self.db.ambient_msgs_by_population = {}

        # ---------------------------------------------------------------
        # Entry description
        # ---------------------------------------------------------------
        self.db.entry_desc = None

        # ---------------------------------------------------------------
        # Examine closely layer
        # ---------------------------------------------------------------
        self.db.examine_desc = None
        self.db.room_history = []

        # ---------------------------------------------------------------
        # Wisp and hub settings
        # ---------------------------------------------------------------
        self.db.wisp_always_visible = False
        self.db.is_forming = False
        self.db.is_hub = False

        # ---------------------------------------------------------------
        # Access and privacy
        # ---------------------------------------------------------------
        self.db.hide_from_who = False
        self.db.allow_teleport_in = True
        self.db.is_private = False

        # ---------------------------------------------------------------
        # Room type tags
        # ---------------------------------------------------------------
        self.db.room_type = "general"

        # ---------------------------------------------------------------
        # Room zones — spatial areas with mechanic and detail hooks.
        #
        # Each zone dict:
        #   desc        (str)   — shown inline via {zone:<name>} token,
        #                         or auto-appended if no token present
        #   details     (dict)  — name → text; inspectable via look/examine
        #   scent       (str)   — zone-local scent string
        #   ambient     (list)  — ambient lines contributed by this zone
        #   contents    (list)  — dbids of objects placed in this zone
        #   parent      (str)   — parent zone name, or None for roots
        #   mechanics   (dict)  — mechanic_id → state/config (data mechanics)
        #   scripts     (list)  — Script dbids active on this zone
        #   event_hooks (dict)  — event_name → list of handler dicts
        #                         open-ended: any string is a valid event name
        # ---------------------------------------------------------------
        self.db.zones = self._build_default_zones()

        # Start the ambient script immediately so new rooms tick from day one
        self.ensure_ambient_script()

    # -------------------------------------------------------------------
    # Room zone helpers
    # -------------------------------------------------------------------

    def _build_default_zones(self):
        """
        Return the default directional + center zone dict for a new room.
        All fields start empty so nothing renders until owners fill them in.
        """
        def _z(parent=None):
            return {
                "desc":        "",
                "details":     {},
                "scent":       None,
                "ambient":     [],
                "contents":    [],
                "parent":      parent,
                "mechanics":   {},
                "scripts":     [],
                "event_hooks": {},
            }
        return {
            "north":  _z(),
            "south":  _z(),
            "east":   _z(),
            "west":   _z(),
            "up":     _z(),
            "down":   _z(),
            "center": _z(),
        }

    # Protected zone names that cannot be removed
    _PROTECTED_ZONES = frozenset(
        {"north", "south", "east", "west", "up", "down", "center"}
    )

    def _resolve_zone_tokens(self, text):
        """
        Replace tokens in room description text.

        Handled tokens (in order):
          {time}          — current IC time period (dawn/morning/afternoon/dusk/evening/midnight)
          {weather}       — current weather state (clear/overcast/rain/heavy_rain/fog/storm/snow)
          {zone:<name>}   — zone inline description with time_descs priority:
            1. zone["time_descs"][current_period]  — time-of-day specific desc (Option C)
            2. zone["summary"]                     — short one-liner
            3. zone["desc"]                        — full description fallback
            4. ""                                  — token removed if nothing set
        """
        import re
        zones = self.db.zones or {}

        # Substitute {time} token
        if "{time}" in text:
            try:
                text = text.replace("{time}", self.get_time_period())
            except Exception:
                text = text.replace("{time}", "")

        # Substitute {weather} token
        if "{weather}" in text:
            try:
                text = text.replace("{weather}", self.get_weather())
            except Exception:
                text = text.replace("{weather}", "")

        # Zone tokens with optional time_descs support
        def _replace(match):
            zone_name = match.group(1).strip().lower()
            zone = zones.get(zone_name)
            if not zone or not hasattr(zone, "get"):
                return ""

            # Time-specific description takes priority (Option C)
            time_descs = zone.get("time_descs") or {}
            if time_descs:
                try:
                    current_time = self.get_time_period()
                    time_desc = time_descs.get(current_time, "")
                    if time_desc:
                        return time_desc
                except Exception:
                    pass

            # Fall back to summary, then full desc
            summary = zone.get("summary", "") or ""
            if summary:
                return summary
            return zone.get("desc", "") or ""

        return re.sub(r"\{zone:([^}]+)\}", _replace, text)

    def get_zone_auto_append(self, base_desc):
        """
        Auto-append is disabled. Zone descriptions only appear when a
        {zone:<name>} token is explicitly placed in the room's @desc,
        or when a player uses 'look <zone>'. ANSI colors in the main
        description are the intended cue for what's interactable.
        """
        return ""

    def get_zone_seated_lines(self):
        """
        Return display lines for any zone that currently has characters
        in a zone position (seated / lying / kneeling / in a lap).

        Returns:
            list[str] — one line per occupied zone.
        """
        zones = self.db.zones or {}
        lines = []

        for zone_name, zone_data in zones.items():
            if not hasattr(zone_data, "get"):
                continue
            mechanics = zone_data.get("mechanics", {}) or {}
            seat = mechanics.get("seat")
            if not seat:
                continue
            occupied = seat.get("occupied", [])
            if not occupied:
                continue

            label    = seat.get("label", zone_name)
            position = seat.get("position", "seated")

            # Separate seat/lap slots
            seat_entries = [e for e in occupied if len(e) < 3 or e[2] in ("seat", "seated")]
            lap_entries  = [e for e in occupied if len(e) >= 3 and e[2] == "lap"]
            lie_entries  = [e for e in occupied if len(e) >= 3 and e[2] == "lying"]
            kneel_entries= [e for e in occupied if len(e) >= 3 and e[2] == "kneeling"]

            # Seated (with optional lap riders)
            if seat_entries and position == "seated":
                host_name = seat_entries[0][1]
                if lap_entries and len(seat_entries) == 1:
                    lap_names = ", ".join(e[1] for e in lap_entries)
                    lines.append(
                        f"|x{host_name} is seated in {label} "
                        f"with {lap_names} in their lap.|n"
                    )
                else:
                    names = ", ".join(e[1] for e in seat_entries)
                    lines.append(f"|xSeated in {label}: {names}.|n")

            # Lying
            elif lie_entries or position == "lying":
                entries = lie_entries or seat_entries
                names = ", ".join(e[1] for e in entries if len(e) > 1)
                if names:
                    lines.append(f"|x{names} {'is' if ',' not in names else 'are'} lying on {label}.|n")

            # Kneeling
            elif kneel_entries or position == "kneeling":
                entries = kneel_entries or seat_entries
                names = ", ".join(e[1] for e in entries if len(e) > 1)
                if names:
                    lines.append(f"|x{names} {'is' if ',' not in names else 'are'} kneeling on {label}.|n")

        return lines

    def get_zone_restrained_lines(self):
        """
        Return display lines for zones that currently have characters restrained.

        Returns:
            list[str] — one line per zone with restrained occupants.
        """
        zones = self.db.zones or {}
        lines = []

        for zone_name, zone_data in zones.items():
            if not hasattr(zone_data, "get"):
                continue
            mechanics = zone_data.get("mechanics", {}) or {}
            restrain  = mechanics.get("restrain")
            if not restrain:
                continue
            restrained = restrain.get("restrained", [])
            if not restrained:
                continue

            label = restrain.get("label", zone_name)
            names = ", ".join(e[1] for e in restrained if len(e) > 1)
            if names:
                verb = "is" if "," not in names else "are"
                lines.append(
                    f"|m{names} {verb} secured to {label}.|n"
                )

        return lines

    def get_zone_watching_lines(self):
        """
        Return display lines for characters currently watching someone.

        Returns:
            list[str] — one line per watcher whose target is in the room.
        """
        lines = []
        contents = list(self.contents)
        id_to_name = {}
        for obj in contents:
            if hasattr(obj, "id"):
                n = obj.db.rp_name if hasattr(obj.db, "rp_name") and obj.db.rp_name else obj.name
                id_to_name[obj.id] = n

        for obj in contents:
            if not (hasattr(obj, "has_account") and obj.has_account):
                continue
            watching_id = getattr(obj.db, "zone_watching", None)
            if not watching_id:
                continue
            if watching_id not in id_to_name:
                continue    # target left the room
            watcher_name = id_to_name.get(obj.id, obj.name)
            target_name  = id_to_name[watching_id]
            lines.append(
                f"|x{watcher_name} is watching {target_name}.|n"
            )

        return lines

    def fire_zone_event(self, zone_name, event_name, **kwargs):
        """
        Fire a named event on a zone, calling all registered handlers.

        Handlers are stored as dicts in zone["event_hooks"][event_name]:
            {
                "mechanic_id": str,
                "handler":     "dotted.module.path.function",
                "priority":    int,   # higher = called first
            }

        Extra kwargs are passed through to each handler as:
            handler(room, zone_name, event_name, **kwargs)

        Args:
            zone_name  (str): The zone the event is occurring on.
            event_name (str): Any string — completely open-ended.
        """
        zones = self.db.zones or {}
        zone = zones.get(zone_name)
        if not zone or not hasattr(zone, "get"):
            return

        hooks = zone.get("event_hooks", {}) or {}
        handlers = list(hooks.get(event_name, []))
        if not handlers:
            return

        # Sort by priority descending, then call each
        handlers.sort(key=lambda h: h.get("priority", 0), reverse=True)
        for hook in handlers:
            handler_path = hook.get("handler", "")
            if not handler_path:
                continue
            try:
                import importlib
                module_path, func_name = handler_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)
                func(self, zone_name, event_name, **kwargs)
            except Exception as e:
                logger.log_err(
                    f"Zone event handler error on {self.key} "
                    f"zone={zone_name} event={event_name} "
                    f"handler={handler_path}: {e}"
                )

    def register_zone_hook(self, zone_name, event_name,
                           mechanic_id, handler_path, priority=0):
        """
        Register a mechanic event handler on a zone.

        Args:
            zone_name    (str): Zone to attach to.
            event_name   (str): Event name (any string).
            mechanic_id  (str): Mechanic identifier.
            handler_path (str): Dotted path to handler function.
            priority     (int): Call order (higher = first).
        """
        zones = self.db.zones or {}
        zone = zones.get(zone_name)
        if not zone or not hasattr(zone, "get"):
            return
        hooks = zone.get("event_hooks", {}) or {}
        handlers = list(hooks.get(event_name, []))
        # Remove any existing entry for this mechanic + event
        handlers = [
            h for h in handlers
            if h.get("mechanic_id") != mechanic_id
        ]
        handlers.append({
            "mechanic_id": mechanic_id,
            "handler":     handler_path,
            "priority":    priority,
        })
        hooks[event_name] = handlers
        zone["event_hooks"] = hooks
        zones[zone_name] = zone
        self.db.zones = zones

    def unregister_zone_hooks(self, zone_name, mechanic_id):
        """
        Remove all event hooks for a mechanic from a zone.
        """
        zones = self.db.zones or {}
        zone = zones.get(zone_name)
        if not zone or not hasattr(zone, "get"):
            return
        hooks = zone.get("event_hooks", {}) or {}
        for event_name in list(hooks.keys()):
            hooks[event_name] = [
                h for h in hooks[event_name]
                if h.get("mechanic_id") != mechanic_id
            ]
        zone["event_hooks"] = hooks
        zones[zone_name] = zone
        self.db.zones = zones

    def get_zone_detail(self, detail_key):
        """
        Search all zones for a named detail. Returns the first match.
        Checks exact match first, then prefix match.

        Args:
            detail_key (str): Detail name to look up (will be lowercased).

        Returns:
            str or None: Detail text, or None if not found.
        """
        zones = self.db.zones or {}
        key_lower = detail_key.strip().lower()
        # Exact match pass
        for zone_data in zones.values():
            if not hasattr(zone_data, "get"):
                continue
            details = zone_data.get("details", {}) or {}
            if key_lower in details:
                return details[key_lower]
        # Prefix match pass
        for zone_data in zones.values():
            if not hasattr(zone_data, "get"):
                continue
            details = zone_data.get("details", {}) or {}
            for kw, text in details.items():
                if kw.startswith(key_lower):
                    return text
        return None

    # -------------------------------------------------------------------
    # Scene lock enforcement
    # -------------------------------------------------------------------

    def at_pre_object_receive(self, obj, source_location, **kwargs):
        """
        Called before an object enters this room.
        Blocks entry if the room is scene-locked, unless:
          - the object is not a character (items, etc. pass freely)
          - the object is a superuser
          - the object has Admin permission
          - the object's id is on the invite list
        """
        from typeclasses.characters import Character
        if not isinstance(obj, Character):
            return True

        if not self.db.scene_locked:
            return True

        # Superuser and admins always pass
        if obj.is_superuser or obj.check_permstring("Admin"):
            self.msg_contents(
                f"|x[ {obj.db.rp_name or obj.name} enters quietly. ]|n"
            )
            return True

        # Invite list passes
        invite_list = self.db.scene_invite_list or []
        if obj.id in invite_list:
            return True

        # Block entry
        obj.msg(
            f"|xA scene is in progress in |w{self.key}|n|x. "
            f"Type |wknock|n if you'd like to let them know you're here.|n"
        )
        return False

    # -------------------------------------------------------------------
    # Scene logging
    # -------------------------------------------------------------------

    def append_scene_log(self, author_name, text):
        """
        Append a line to the scene log if logging is active.

        Args:
            author_name (str): Display name of the character acting.
            text (str): The raw output line as sent to the room.
        """
        if not self.db.scene_logging:
            return
        import time
        log = self.db.scene_log or []
        log.append({
            "time":   time.time(),
            "author": author_name,
            "text":   text,
        })
        self.db.scene_log = log

    # -------------------------------------------------------------------
    # Ambient script management
    # -------------------------------------------------------------------

    def ensure_ambient_script(self):
        """
        Attach the ambient script if not already present.
        Safe to call multiple times — will not duplicate.
        """
        from typeclasses.scripts import AmbientScript
        existing = self.scripts.get("ambient_script")
        if not existing:
            self.scripts.add(AmbientScript)
        elif len(existing) > 1:
            for script in list(existing)[1:]:
                script.delete()

    # -------------------------------------------------------------------
    # Description assembly helpers
    # -------------------------------------------------------------------

    def get_time_period(self):
        """Get the current IC time period."""
        try:
            from world.gametime import get_time_period
            return get_time_period()
        except (ImportError, Exception):
            return "evening"

    def get_weather(self):
        """Get the current global weather state."""
        try:
            from world.weather import get_weather
            return get_weather()
        except (ImportError, Exception):
            return "clear"

    def get_season(self):
        """Get the current IC season."""
        try:
            from world.gametime import get_season
            return get_season()
        except (ImportError, Exception):
            return "autumn"

    def get_world_state(self):
        """Get current world state flags."""
        try:
            from world.world_state import get_all_flags
            return get_all_flags()
        except (ImportError, Exception):
            return {}

    def get_crowd_level(self):
        """
        Determine crowd level based on IC characters present.

        Returns:
            str: empty / quiet / few / busy / crowded
        """
        count = len([
            obj for obj in self.contents
            if hasattr(obj, 'has_account') and obj.has_account
        ])
        if count == 0:
            return "empty"
        elif count <= 2:
            return "quiet"
        elif count <= 4:
            return "few"
        elif count <= 8:
            return "busy"
        else:
            return "crowded"

    def get_object_room_desc_lines(self):
        """
        Collect room description contributions from
        stateful objects (excludes NPCs — their presence
        lines appear in the presence section instead).

        Returns:
            list: Description lines from active objects.
        """
        lines = []
        try:
            from typeclasses.npc import NPC as _NPC
        except ImportError:
            _NPC = None
        for obj in self.contents:
            if _NPC and isinstance(obj, _NPC):
                continue
            if hasattr(obj, 'get_room_desc_line'):
                try:
                    line = obj.get_room_desc_line()
                    if line:
                        lines.append(line)
                except Exception as e:
                    logger.log_err(
                        f"Error getting room desc line "
                        f"from {obj.key}: {e}"
                    )
        return lines

    def get_npc_presence_lines(self):
        """
        Collect presence lines from NPCs in the room.
        These appear in the presence section alongside
        player character lines.

        Returns:
            list: Formatted NPC presence lines.
        """
        lines = []
        try:
            from typeclasses.npc import NPC as _NPC
        except ImportError:
            return lines
        for obj in self.contents:
            if isinstance(obj, _NPC) and hasattr(obj, 'get_room_desc_line'):
                try:
                    line = obj.get_room_desc_line()
                    if line:
                        lines.append(line)
                except Exception as e:
                    logger.log_err(
                        f"Error getting NPC presence line "
                        f"from {obj.key}: {e}"
                    )
        return lines

    def get_toggle_desc(self):
        """
        Get description modifier for current toggle states.

        Returns:
            str: Combined toggle description, or empty string.
        """
        parts = []
        toggles = self.db.toggles or {}
        toggle_descs = self.db.toggle_descs or {}

        for element, state in toggles.items():
            element_descs = toggle_descs.get(element, {})
            desc = element_descs.get(state, "")
            if desc:
                parts.append(desc)

        return "\n".join(parts)

    def get_scene_header(self):
        """
        Build the scene state header shown above the room desc.

        Returns:
            str: Scene header string, or empty string.
        """
        parts = []

        if self.db.scene_locked:
            parts.append(
                "|r[Scene in progress — invite only]|n"
            )
        if self.db.scene_title:
            parts.append(f"|w{self.db.scene_title}|n")
        if self.db.scene_prompt:
            parts.append(f"|x{self.db.scene_prompt}|n")
        if self.db.content_warnings:
            cws = ", ".join(self.db.content_warnings)
            parts.append(
                f"|y[Content warnings: {cws}]|n"
            )
        if self.db.scene_logging:
            parts.append("|x[Scene logging active]|n")
        if self.db.mood_flag:
            parts.append(f"|x[{self.db.mood_flag}]|n")

        return "\n".join(parts)

    def get_character_presence_lines(self, looker):
        """
        Build presence lines for all IC characters in the room.
        Uses character's get_presence_line() if available,
        otherwise falls back to a simple name line.

        Args:
            looker: The character doing the looking.

        Returns:
            list: Formatted presence lines.
        """
        lines = []
        for obj in self.contents:
            if obj == looker:
                continue
            if not (
                hasattr(obj, 'has_account') and obj.has_account
            ):
                continue

            # Use character's own presence line method if available
            if hasattr(obj, 'get_presence_line'):
                try:
                    line = obj.get_presence_line()
                    if line:
                        lines.append(line)
                    continue
                except Exception as e:
                    logger.log_err(
                        f"Error getting presence line "
                        f"from {obj.key}: {e}"
                    )

            # Fallback — build manually
            name = (
                obj.db.rp_name
                if hasattr(obj.db, 'rp_name') and obj.db.rp_name
                else obj.key
            )
            presence = (
                obj.db.ic_presence
                if hasattr(obj.db, 'ic_presence')
                and obj.db.ic_presence
                else ""
            )
            body = (
                obj.db.body_language
                if hasattr(obj.db, 'body_language')
                and obj.db.body_language
                else ""
            )
            detail = presence or body
            if detail:
                lines.append(
                    f"|w{name}|n is here. |x[{detail}]|n"
                )
            else:
                lines.append(f"|w{name}|n is here.")

        return lines

    def get_wisp_presence_lines(self, looker):
        """
        Build presence lines for visible wisps in the room.

        Args:
            looker: The character doing the looking.

        Returns:
            list: Formatted wisp presence lines.
        """
        lines = []
        try:
            from world.wisp_visibility import WispVisibility
            visible_wisps = WispVisibility.get_room_wisps(
                self, looker
            )
            for wisp_account in visible_wisps:
                lines.append(
                    wisp_account.get_wisp_presence_line()
                )
        except (ImportError, Exception) as e:
            logger.log_err(
                f"Error getting wisp presence lines: {e}"
            )
        return lines

    def get_ambient_pool(self):
        """
        Assemble the full ambient pool for current state.

        Returns:
            list: All available ambient lines.
        """
        pool = list(self.db.ambient_msgs or [])

        # Toggle-specific additions
        toggles = self.db.toggles or {}
        toggle_pools = self.db.ambient_msgs_by_toggle or {}
        for element, state in toggles.items():
            key = f"{element}_{state}"
            pool.extend(toggle_pools.get(key, []))

        # Mood-specific additions
        mood = self.db.mood_flag
        if mood:
            mood_pools = self.db.ambient_msgs_by_mood or {}
            pool.extend(mood_pools.get(mood, []))

        # Population-specific additions
        crowd = self.get_crowd_level()
        pop_pools = self.db.ambient_msgs_by_population or {}
        pool.extend(pop_pools.get(crowd, []))

        # Object-contributed ambient lines
        for obj in self.contents:
            if hasattr(obj, 'get_ambient_pool'):
                try:
                    obj_pool = obj.get_ambient_pool()
                    if obj_pool:
                        pool.extend(obj_pool)
                except Exception as e:
                    logger.log_err(
                        f"Error getting ambient pool "
                        f"from {obj.key}: {e}"
                    )

        # Character-contributed ambient lines
        for obj in self.contents:
            if hasattr(obj, 'has_account') and obj.has_account:
                if hasattr(obj, 'get_character_ambient_lines'):
                    try:
                        char_pool = (
                            obj.get_character_ambient_lines()
                        )
                        pool.extend(char_pool)
                    except Exception as e:
                        logger.log_err(
                            f"Error getting character "
                            f"ambient from {obj.key}: {e}"
                        )
                else:
                    char_pool = (
                        obj.db.ambient_contribution
                        if hasattr(obj.db, 'ambient_contribution')
                        else []
                    ) or []
                    pool.extend(char_pool)

        # Haunting wisp contributions
        try:
            from world.wisp_visibility import WispVisibility
            haunting_lines = WispVisibility.get_haunting_lines(
                self
            )
            pool.extend(haunting_lines)
        except (ImportError, Exception):
            pass

        return pool

    # -------------------------------------------------------------------
    # Main appearance assembly
    # -------------------------------------------------------------------

    def return_appearance(self, looker, **kwargs):
        """
        Assemble and return the full room description.
        Called by the 'look' command.

        Args:
            looker: The character or account looking at the room.

        Returns:
            str: The complete assembled room description.
        """
        parts = []

        # Leading blank line — separates room display from
        # whatever output preceded it (commands, prior text)
        parts.append("")

        # --- Scene header (above everything) ---
        scene_header = self.get_scene_header()
        if scene_header:
            parts.append(scene_header)
            parts.append("")

        # --- Room name ---
        name = self.get_display_name(looker)
        parts.append(f"|w{name}|n")
        parts.append("")

        # --- Layer 1: Base description (with zone token resolution) ---
        base = self.db.desc or ""
        if base:
            parts.append(self._resolve_zone_tokens(base))

        # --- Scene stage overlay (rp_tools: stage command) ---
        stage = self.db.scene_stage_desc or ""
        if stage:
            parts.append(stage)

        # --- Layer 2: Time of day ---
        time_period = self.get_time_period()
        time_descs = self.db.time_descs or {}
        time_line = time_descs.get(time_period, "")
        if time_line:
            parts.append(time_line)

        # --- Layer 3: Weather ---
        if self.db.has_weather:
            weather = self.get_weather()
            weather_descs = self.db.weather_descs or {}
            weather_line = weather_descs.get(weather, "")
            if weather_line:
                parts.append(weather_line)

        # --- Layer 4: Season ---
        if self.db.has_seasons:
            season = self.get_season()
            season_descs = self.db.season_descs or {}
            season_line = season_descs.get(season, "")
            if season_line:
                parts.append(season_line)

        # --- Layer 5: Toggle states ---
        toggle_desc = self.get_toggle_desc()
        if toggle_desc:
            parts.append(toggle_desc)

        # --- Layer 6: Stateful object lines ---
        object_lines = self.get_object_room_desc_lines()
        if object_lines:
            parts.append("\n".join(object_lines))

        # --- Layer 7: Population/crowd ---
        crowd = self.get_crowd_level()
        crowd_descs = self.db.crowd_descs or {}
        crowd_line = crowd_descs.get(crowd, "")
        if crowd_line:
            parts.append(crowd_line)

        # --- Layer 8: Mood/atmosphere flag ---
        mood = self.db.mood_flag
        if mood:
            mood_descs = self.db.mood_descs or {}
            mood_line = mood_descs.get(mood, "")
            if mood_line:
                parts.append(mood_line)

        # --- Layer 9: World state ---
        world_state = self.get_world_state()
        if world_state:
            state_flags = self.db.world_state_flags or []
            state_descs = self.db.world_state_descs or {}
            for flag in state_flags:
                if (world_state.get(flag) and
                        state_descs.get(flag)):
                    parts.append(state_descs[flag])

        # --- Zone auto-append (zones with desc but no inline token) ---
        zone_append = self.get_zone_auto_append(self.db.desc or "")
        if zone_append:
            parts.append(zone_append)

        # --- Zone seated characters ---
        seated_lines = self.get_zone_seated_lines()
        if seated_lines:
            parts.extend(seated_lines)

        # --- Zone restrained characters ---
        restrained_lines = self.get_zone_restrained_lines()
        if restrained_lines:
            parts.extend(restrained_lines)

        # --- Zone watching ---
        watching_lines = self.get_zone_watching_lines()
        if watching_lines:
            parts.extend(watching_lines)

        # --- Separator before presence section ---
        parts.append("")

        # --- Layer 14: NPC + character presence lines ---
        npc_lines = self.get_npc_presence_lines()
        char_lines = self.get_character_presence_lines(looker)
        all_presence = npc_lines + char_lines
        if all_presence:
            parts.extend(all_presence)
            parts.append("")

        # --- Layer 15: Wisp presence lines ---
        show_wisps = (
            self.db.wisp_always_visible
            or self.db.is_hub
            or self.db.is_forming
            or (
                hasattr(looker, 'account')
                and looker.account
                and looker.account.db.wisp_preference
                == "visible"
            )
        )
        if show_wisps:
            wisp_lines = self.get_wisp_presence_lines(looker)
            if wisp_lines:
                parts.extend(wisp_lines)
                parts.append("")

        # --- Exits ---
        exits = self.get_display_exits(looker)
        if exits:
            parts.append(exits)

        # Filter None values and join
        filtered = [p for p in parts if p is not None]
        return "\n".join(filtered)

    def get_display_exits(self, looker, **kwargs):
        """
        Format the exits for display.
        Exits are suppressed in is_forming rooms — NPCs reveal them
        verbally via their trigger dialogue.

        Returns:
            str: Formatted exits string, or empty string.
        """
        if self.db.is_forming:
            return ""

        exits = []
        for exit_obj in self.exits:
            if exit_obj.access(looker, "view"):
                exits.append(exit_obj.key)

        if not exits:
            return ""

        return f"|xExits: {', '.join(exits)}|n"

    # -------------------------------------------------------------------
    # Forming room arrival hook
    # -------------------------------------------------------------------

    def at_object_receive(self, obj, source_location, **kwargs):
        """
        Called after an object arrives in this room.
        For is_forming rooms: fires the _arrive trigger on any NPCs
        present, passing the arriving character as the caller.
        Admins and superusers are skipped so builders can move freely.
        """
        super().at_object_receive(obj, source_location, **kwargs)

        if not self.db.is_forming:
            return

        from typeclasses.characters import Character
        if not isinstance(obj, Character):
            return

        # Builders move freely — skip trigger for admins/superusers
        if obj.is_superuser or obj.check_permstring("Admin"):
            return

        from typeclasses.npc import NPC
        from evennia.utils import delay

        # Collect NPCs to trigger before the loop so we don't hold a
        # reference into room.contents across the delay boundary.
        arriving_npcs = [
            o for o in self.contents
            if o is not obj and isinstance(o, NPC)
        ]

        if not arriving_npcs:
            return

        def _fire_arrive():
            """
            Fires after the room description has rendered.
            The leading \\n on NPC speech handles visual separation.
            """
            for npc in arriving_npcs:
                try:
                    npc.trigger_keyword(obj, "_arrive")
                except Exception as e:
                    logger.log_err(
                        f"Error firing _arrive on {npc.key}: {e}"
                    )

        # Short delay lets the room look finish sending before the NPC speaks.
        delay(0.3, _fire_arrive)

    # -------------------------------------------------------------------
    # Atmosphere toggle
    # -------------------------------------------------------------------

    def toggle(self, element, actor, target_state=None):
        """
        Toggle an atmosphere element to its next state.

        Args:
            element (str): Element to toggle.
            actor: Character performing the toggle.
            target_state (str): Optional specific state to set.

        Returns:
            bool: True if successful.
        """
        progressions = {
            "lights":    ["bright", "dim", "dark"],
            "fireplace": ["unlit", "lit"],
            "curtains":  ["open", "drawn"],
            "music":     ["silent", "soft", "loud"],
        }

        if element not in progressions:
            return False

        toggles = self.db.toggles or {}
        current = toggles.get(element, progressions[element][0])
        states = progressions[element]

        if target_state and target_state in states:
            new_state = target_state
        else:
            try:
                current_idx = states.index(current)
                new_state = states[
                    (current_idx + 1) % len(states)
                ]
            except ValueError:
                new_state = states[0]

        toggles[element] = new_state
        self.db.toggles = toggles

        toggle_descs = self.db.toggle_descs or {}
        desc = toggle_descs.get(element, {}).get(new_state, "")

        if desc:
            self.msg_contents(desc)
        else:
            actor_name = (
                actor.db.rp_name
                if hasattr(actor.db, 'rp_name')
                and actor.db.rp_name
                else actor.key
            )
            self.msg_contents(
                f"{actor_name} adjusts the {element}. "
                f"|x[{element}: {new_state}]|n"
            )

        return True

    # -------------------------------------------------------------------
    # Scene management
    # -------------------------------------------------------------------

    def lock_scene(self, actor):
        """Lock the room for a private scene."""
        self.db.scene_locked = True
        self.db.scene_invite_list = [actor.id]
        actor_name = (
            actor.db.rp_name
            if hasattr(actor.db, 'rp_name')
            and actor.db.rp_name
            else actor.key
        )
        self.msg_contents(
            f"|r[Scene locked by {actor_name} "
            f"— invite only]|n"
        )

    def unlock_scene(self, actor):
        """Unlock the room."""
        self.db.scene_locked = False
        self.msg_contents("|g[Scene open]|n")

    def add_to_invite_list(self, target):
        """Add a character to the scene invite list."""
        invite_list = self.db.scene_invite_list or []
        if target.id not in invite_list:
            invite_list.append(target.id)
            self.db.scene_invite_list = invite_list

    def start_logging(self):
        """Activate scene logging."""
        self.db.scene_logging = True
        self.db.scene_log = []
        self.msg_contents("|x[Scene logging activated.]|n")

    def stop_logging(self):
        """Deactivate scene logging and return the log."""
        self.db.scene_logging = False
        log = self.db.scene_log or []
        self.msg_contents("|x[Scene logging stopped.]|n")
        return log

    def log_line(self, line):
        """Append a line to the scene log if logging is active."""
        if self.db.scene_logging:
            scene_log = self.db.scene_log or []
            scene_log.append(line)
            self.db.scene_log = scene_log

    # -------------------------------------------------------------------
    # Movement hooks
    # -------------------------------------------------------------------

    # at_object_receive is defined earlier in this class with full
    # forming-room logic. This duplicate stub has been removed.

    def at_pre_object_leave(self, leaving_object,
                            destination, **kwargs):
        """Called before an object leaves this room."""
        return super().at_pre_object_leave(
            leaving_object, destination, **kwargs
        )

    # -------------------------------------------------------------------
    # Scene detail lookup (rp_tools: detail command)
    # -------------------------------------------------------------------

    def get_detail(self, detail_key, looker=None):
        """
        Return a detail by keyword, or None if not found.

        Resolution order:
          1. scene_details (RP tool temp props — exact then prefix)
          2. Zone details  (permanent architectural details — exact then prefix)

        Called by the default 'look at <keyword>' handler in Evennia,
        and also by our custom CmdLook / CmdExamine for bare keyword lookup.

        Args:
            detail_key (str): The keyword being looked up.
            looker: The character doing the looking.

        Returns:
            str or None: Detail text, or None if not found.
        """
        key_lower = detail_key.strip().lower()

        # 1. Scene details (temporary RP props)
        details = self.db.scene_details or {}
        if key_lower in details:
            return details[key_lower]
        for kw, text in details.items():
            if kw.startswith(key_lower):
                return text

        # 2. Permanent zone details
        zone_result = self.get_zone_detail(key_lower)
        if zone_result:
            return zone_result

        return None

    # -------------------------------------------------------------------
    # Room history
    # -------------------------------------------------------------------

    def add_to_history(self, title, participants,
                       duration_minutes):
        """
        Add a scene summary to the room's history.

        Args:
            title (str): Scene title.
            participants (list): Character names.
            duration_minutes (int): Scene duration.
        """
        from evennia.utils import gametime
        history = self.db.room_history or []
        history.append({
            "title":        title,
            "participants": participants,
            "timestamp":    gametime.gametime(absolute=True),
            "duration":     duration_minutes,
        })
        if len(history) > 20:
            history = history[-20:]
        self.db.room_history = history

    def get_history_display(self):
        """
        Format the room's scene history for display.

        Returns:
            str: Formatted history string.
        """
        history = self.db.room_history or []
        if not history:
            return "No scenes have been logged in this room."

        lines = ["|wScene history for this room:|n"]
        for entry in reversed(history[-5:]):
            title = entry.get("title", "Untitled scene")
            participants = ", ".join(
                entry.get("participants", [])
            )
            duration = entry.get("duration", 0)
            lines.append(
                f"  |w{title}|n — "
                f"{participants} — "
                f"{duration} minutes"
            )

        return "\n".join(lines)