"""
typeclasses/womb_room.py

WombRoom — an interior space that lives inside a character's orifice zone.

Subclasses HousingRoom so it inherits:
  - Owner (host character) tracking
  - Friend list  (residents who may enter)
  - Lock flag    (the zone IS the door — the lock is whether the zone is sealed)
  - can_enter / is_owner / is_friend helpers

Extra behaviour:
  - Installed onto a host character's orifice zone.
  - Entered via 'enter <host> [zone]' rather than a normal exit.
  - The room description is the zone's interior field (set via 'zone interior').
  - Fluid accumulates from inflation deposits and internal zone deposits.
  - Flood state appended to room desc based on accumulated volume.
  - Shaft-visible messages fire to residents when host's zone is penetrated.
  - Host can broadcast inward via 'pulse <message>'.
  - Host manages the room remotely via 'wombroom' commands without entering.

DB attributes (in addition to HousingRoom's):
    womb_host_id   (int)    — pk of the host character
    womb_zone      (str)    — zone name on the host this room is installed on
    womb_fluid_ml  (float)  — current accumulated fluid volume
    womb_capacity_ml (float) — max fluid before 'full' state
    womb_fluid_type (str)   — primary fluid type in the room
    womb_decay_rate (float) — ml drained per passive tick when unsealed
"""

from typeclasses.housing import HousingRoom


def add_fluid_from_zone(character, zone_name: str,
                        volume_ml: float, fluid_type: str = "fluid"):
    """
    Module-level helper — call whenever fluid is deposited into a character's
    orifice zone.  Silently does nothing if that zone has no WombRoom.

    Import and call from inflate_commands, penetration_commands,
    insemination_item, etc:
        from typeclasses.womb_room import add_fluid_from_zone
        add_fluid_from_zone(target, zone_name, volume_ml, fluid_type)
    """
    try:
        zones    = getattr(character.db, "zones", None) or {}
        mech     = (zones.get(zone_name) or {}).get("mechanics") or {}
        wr_entry = mech.get("womb_room")
        if not wr_entry:
            return
        dbref = wr_entry.get("room_dbref")
        if not dbref:
            return
        from evennia import search_object
        results = search_object(dbref, exact=True)
        if results and isinstance(results[0], WombRoom):
            results[0].add_fluid(volume_ml, fluid_type)
    except Exception:
        pass

# Flood state thresholds as fraction of capacity
_FLOOD_STATES = [
    (1.00, "full"),
    (0.60, "chest"),
    (0.35, "knee"),
    (0.10, "shallow"),
    (0.01, "trace"),
    (0.00, "dry"),
]

# Default capacity — overridden on install based on zone size
_DEFAULT_CAPACITY_ML = 20_000.0
_DEFAULT_DECAY_ML    = 50.0     # ml per 15-min tick when unsealed


class WombRoom(HousingRoom):
    """
    An interior space installed inside a character's orifice zone.

    Access is via 'enter <host> [zone]', not normal exits.
    The host owns and manages the room remotely via wombroom commands.
    Residents (friends list) may enter when the zone is accessible.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.room_type        = "womb"
        self.db.womb_host_id     = None
        self.db.womb_zone        = None
        self.db.womb_fluid_ml    = 0.0
        self.db.womb_capacity_ml = _DEFAULT_CAPACITY_ML
        self.db.womb_fluid_type  = "fluid"
        self.db.womb_decay_rate  = _DEFAULT_DECAY_ML
        # WombRooms suppress normal exits in desc
        self.db.room_flags       = dict(self.db.room_flags or {})
        self.db.room_flags["suppress_exits"] = True
        self.db.is_private       = True
        self.db.jump_protected   = True

    # ------------------------------------------------------------------
    # Install / uninstall
    # ------------------------------------------------------------------

    def install(self, host_char, zone_name: str) -> tuple:
        """
        Attach this WombRoom to host_char's orifice zone.
        Returns (True, "") or (False, reason).
        """
        zones = getattr(host_char.db, "zones", None) or {}
        if zone_name not in zones:
            return False, f"No zone '{zone_name}' on {host_char.db.rp_name or host_char.name}."

        zone_type = (zones[zone_name] or {}).get("zone_type", "surface")
        if zone_type not in ("orifice", "both"):
            return False, (
                f"WombRoom can only be installed on an orifice or 'both' zone. "
                f"'{zone_name}' is type '{zone_type}'."
            )

        mechanics = dict((zones[zone_name].get("mechanics") or {}))
        if mechanics.get("womb_room"):
            return False, f"A WombRoom is already installed on '{zone_name}'."

        # Write mechanics entry
        mechanics["womb_room"] = {"room_dbref": self.dbref}
        zone_copy = dict(zones[zone_name])
        zone_copy["mechanics"] = mechanics
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone_copy
        host_char.db.zones = zones_copy

        # Set room attrs
        self.db.womb_host_id        = host_char.id
        self.db.womb_zone           = zone_name
        self.db.housing_owner_id    = host_char.id   # housing owner = host

        # Derive capacity from zone's inflation mechanic if present
        inf = mechanics.get("inflation") or {}
        if inf.get("max_volume_ml"):
            self.db.womb_capacity_ml = float(inf["max_volume_ml"]) * 50.0

        # Move room to a special "inside" location off limbo
        # (actual location depends on your world structure — default limbo #2)
        if not self.location:
            from evennia import search_object
            limbo = search_object("#2", exact=True)
            if limbo:
                self.location = limbo[0]

        return True, ""

    def uninstall(self) -> tuple:
        """Remove WombRoom from its host zone. Returns (True, "") or (False, reason)."""
        host = self._get_host()
        if not host:
            return False, "Host character not found."

        zone_name = self.db.womb_zone
        zones = getattr(host.db, "zones", None) or {}
        if zone_name in zones:
            zone_copy = dict(zones[zone_name])
            mech = dict(zone_copy.get("mechanics") or {})
            mech.pop("womb_room", None)
            zone_copy["mechanics"] = mech
            zones_copy = dict(zones)
            zones_copy[zone_name] = zone_copy
            host.db.zones = zones_copy

        # Evict all residents
        from typeclasses.characters import Character
        for obj in list(self.contents):
            if isinstance(obj, Character):
                host_loc = host.location
                if host_loc and host_loc != self:
                    obj.move_to(host_loc, quiet=True)
                    obj.msg("|xThe space collapses — you are expelled.|n")

        self.db.womb_host_id  = None
        self.db.womb_zone     = None
        return True, ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_host(self):
        """Return the host character object, or None."""
        host_id = self.db.womb_host_id
        if not host_id:
            return None
        from evennia import search_object
        results = search_object(f"#{host_id}", exact=True)
        return results[0] if results else None

    def get_flood_state(self) -> str:
        """Return current flood state label."""
        vol = self.db.womb_fluid_ml or 0.0
        cap = self.db.womb_capacity_ml or _DEFAULT_CAPACITY_ML
        if cap <= 0:
            return "dry"
        pct = vol / cap
        for threshold, label in _FLOOD_STATES:
            if pct >= threshold:
                return label
        return "dry"

    def get_flood_desc(self) -> str | None:
        """Return a prose line describing the current fluid state, or None if dry."""
        state = self.get_flood_state()
        if state == "dry":
            return None
        pool_key = f"flood_{state}"
        from world.milking_loader import pick_womb_message
        fluid = self.db.womb_fluid_type or "fluid"
        from typeclasses.body_mod_item import format_body_volume
        vol_str = format_body_volume(self.db.womb_fluid_ml or 0.0)
        msg = pick_womb_message(pool_key)
        if not msg:
            return None
        return msg.replace("{fluid}", fluid).replace("{volume}", vol_str)

    def is_zone_sealed(self) -> bool:
        """
        Return True if the host's zone entrance is currently sealed.
        Sealed = freeform lock on zone OR active penetration in zone
                 OR a plug/barrier item with seals_zone=True installed.
        """
        host = self._get_host()
        if not host:
            return False
        zone_name = self.db.womb_zone
        if not zone_name:
            return False

        # Check freeform lock
        freeform = getattr(host.db, "freeform_items", None) or {}
        for item_data in freeform.values():
            if (item_data or {}).get("zone") == zone_name:
                if (item_data or {}).get("lock"):
                    return True

        # Check active penetration engagement on this zone
        for char in (host.location.contents if host.location else []):
            engaged = getattr(char.db, "penetrating", None) or {}
            if (engaged.get("target_dbref") == host.dbref and
                    engaged.get("zone_name") == zone_name):
                return True

        # Check for installed plug/barrier mechanics
        zones = getattr(host.db, "zones", None) or {}
        mech = (zones.get(zone_name) or {}).get("mechanics") or {}
        if mech.get("barrier") and mech["barrier"].get("seals_zone"):
            return True

        return False

    def add_fluid(self, volume_ml: float, fluid_type: str = "fluid") -> str:
        """
        Add fluid volume to the room. Returns new flood state label.
        Respects capacity cap.
        """
        current  = float(self.db.womb_fluid_ml or 0.0)
        capacity = float(self.db.womb_capacity_ml or _DEFAULT_CAPACITY_ML)
        new_vol  = min(current + volume_ml, capacity)
        self.db.womb_fluid_ml   = new_vol
        self.db.womb_fluid_type = fluid_type
        return self.get_flood_state()

    def drain_tick(self):
        """
        Called by the passive accumulation script every 15 minutes.
        Drains fluid if the zone is not sealed.
        """
        if self.is_zone_sealed():
            return
        rate    = float(self.db.womb_decay_rate or _DEFAULT_DECAY_ML)
        current = float(self.db.womb_fluid_ml or 0.0)
        self.db.womb_fluid_ml = max(0.0, current - rate)

    def notify_shaft_visible(self, actor, shaft_zone: str):
        """
        Called when the host's zone is penetrated while residents are inside.
        Broadcasts a shaft-visible message to all residents.
        """
        from world.milking_loader import pick_womb_message
        from typeclasses.characters import Character

        residents = [obj for obj in self.contents if isinstance(obj, Character)]
        if not residents:
            return

        host = self._get_host()
        host_name  = (host.db.rp_name or host.name) if host else "the host"
        actor_name = actor.db.rp_name or actor.name
        zone_disp  = shaft_zone.replace("_", " ")

        msg = pick_womb_message("shaft_visible")
        if not msg:
            msg = "Something pushes through the wall of this space from outside."
        msg = (msg.replace("{actor}", actor_name)
                  .replace("{host}", host_name)
                  .replace("{zone}", zone_disp))

        for resident in residents:
            resident.msg(msg)

    # ------------------------------------------------------------------
    # Room description override — inject interior desc + flood state
    # ------------------------------------------------------------------

    def get_display_desc(self, looker=None, **kwargs):
        """
        Returns the room description, built from:
          1. Host's zone interior field (set via 'zone interior <zone> = <text>')
          2. Flood state prose appended if fluid present
        """
        host = self._get_host()
        zone_name = self.db.womb_zone

        # Pull interior desc from host's zone
        interior = ""
        if host and zone_name:
            zones = getattr(host.db, "zones", None) or {}
            interior = (zones.get(zone_name) or {}).get("interior", "") or ""

        if not interior:
            interior = (
                "The space is warm and close — walls that yield slightly "
                "to pressure, the air thick and still. A heartbeat is "
                "audible from somewhere in the walls."
            )

        flood_line = self.get_flood_desc()
        if flood_line:
            return f"{interior}\n\n{flood_line}"
        return interior

    # ------------------------------------------------------------------
    # Entry control — residents + host only
    # ------------------------------------------------------------------

    def at_pre_object_receive(self, obj, source_location, **kwargs):
        from typeclasses.characters import Character
        if isinstance(obj, Character):
            # Host always allowed
            if self.db.womb_host_id and obj.id == self.db.womb_host_id:
                return True
            if not self.is_friend(obj) and not self.is_staff(obj):
                obj.msg("|xYou have not been invited into this space.|n")
                return False
        return True
