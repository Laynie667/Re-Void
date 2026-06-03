"""
typeclasses/plug_item.py

PlugItem — a physical insertable object that installs into an orifice zone.

When inserted:
  - Appends its description to the zone's nude desc (not a replace/override)
  - Seals the zone entrance (blocks WombRoom drainage while inserted)
  - Can be slock'd or plock'd so the target can't remove it
  - Shows in zone examination and freeform list

Installation is via the 'insert' command (commands/item_commands.py).
Removal is via 'remove' or 'unplug'.

Zone mechanics entry written on insert:
    zones[zone_name]['mechanics']['plug'] = {
        'item_dbref':  str    -- this item's dbref
        'item_name':   str    -- display name
        'desc':        str    -- default description (appended to zone nude)
        'player_desc': str    -- player-written override (appended instead of desc)
        'desc_locked': bool   -- if True, player_desc cannot be changed
        'seals_zone':  bool   -- always True for plugs
        'lock':        dict   -- slock/plock data or None
    }

The plug_item.py also carries a convenience function:
    get_plug_append(character, zone_name) -> str or ""
which is called by characters.py get_zone_display() to append the plug text.
"""

from evennia import DefaultObject


class PlugItem(DefaultObject):
    """
    An insertable item that can be placed into an orifice zone.

    Install:   insert <plug> [zone]
    Remove:    remove <plug>   /   unplug [zone]
    Describe:  itemdesc <plug> = <text>
    Lock desc: itemdesc/lock <plug>
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key                   = "plug"
        self.db.desc               = "A plain plug, snug and smooth."
        self.db.player_desc        = ""       # player-written override
        self.db.desc_locked        = False    # prevent further desc changes
        self.db.desc_lock_creator  = None     # dbref of who locked the desc
        self.db.installed_on_char  = None
        self.db.installed_on_zone  = None
        self.db.is_inserted        = False

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def get_display_name(self, looker=None, **kwargs):
        suffix = " [inserted]" if self.db.is_inserted else ""
        return f"{self.key}{suffix}"

    def get_active_desc(self) -> str:
        """Return the description that gets appended to the zone's nude desc."""
        return self.db.player_desc or self.db.desc or ""

    # ------------------------------------------------------------------
    # Insert / remove
    # ------------------------------------------------------------------

    def insert(self, character, zone_name: str) -> tuple:
        """
        Insert this plug into character's orifice zone.
        Returns (True, "") or (False, reason_str).
        """
        if self.db.is_inserted:
            return False, f"{self.key} is already inserted."

        zones = getattr(character.db, "zones", None) or {}
        if zone_name not in zones:
            return False, f"{character.db.rp_name or character.name} has no zone '{zone_name}'."

        zone_type = (zones[zone_name] or {}).get("zone_type", "surface")
        if zone_type not in ("orifice", "both"):
            return False, f"Plugs can only be inserted into orifice or both-type zones ('{zone_name}' is '{zone_type}')."

        mech = dict((zones[zone_name].get("mechanics") or {}))
        if mech.get("plug"):
            return False, f"{zone_name.replace('_', ' ')} already has something inserted."

        mech["plug"] = {
            "item_dbref":  self.dbref,
            "item_name":   self.key,
            "desc":        self.db.desc or "",
            "player_desc": self.db.player_desc or "",
            "desc_locked": self.db.desc_locked,
            "seals_zone":  True,
            "lock":        None,
        }

        zone_copy = dict(zones[zone_name])
        zone_copy["mechanics"] = mech
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone_copy
        character.db.zones = zones_copy

        self.db.installed_on_char = character
        self.db.installed_on_zone = zone_name
        self.db.is_inserted       = True
        self.location             = character

        return True, ""

    def remove(self, force: bool = False) -> tuple:
        """
        Remove this plug from its current zone.
        Returns (True, "") or (False, reason_str).
        force=True bypasses lock check (staff use).
        """
        if not self.db.is_inserted:
            return False, f"{self.key} is not currently inserted."

        character = self.db.installed_on_char
        zone_name = self.db.installed_on_zone

        if not character:
            # Clean up orphaned state
            self.db.is_inserted = False
            return True, ""

        zones = getattr(character.db, "zones", None) or {}
        if zone_name in zones:
            mech = dict((zones[zone_name].get("mechanics") or {}))
            plug_data = mech.get("plug") or {}

            if not force and plug_data.get("lock"):
                lock = plug_data["lock"]
                if lock.get("type") == "plock":
                    return False, f"{self.key} is plock'd — a key is required to remove it."
                if lock.get("type") == "slock":
                    return False, f"{self.key} is slock'd — use the code to remove it."

            mech.pop("plug", None)
            zone_copy = dict(zones[zone_name])
            zone_copy["mechanics"] = mech
            zones_copy = dict(zones)
            zones_copy[zone_name] = zone_copy
            character.db.zones = zones_copy

        self.db.installed_on_char = None
        self.db.installed_on_zone = None
        self.db.is_inserted       = False

        return True, ""

    def set_player_desc(self, desc: str, locked: bool = False,
                        creator=None) -> tuple:
        """
        Set the player-written description that appends to the zone nude.

        Args:
            desc:    New description text.
            locked:  If True, permanently lock this desc.
            creator: Character who is locking (stored for key reference).

        Returns:
            (True, "") or (False, reason)
        """
        if self.db.desc_locked:
            return False, f"The description on {self.key} has been permanently locked."

        self.db.player_desc = desc

        # Refresh mechanics entry if currently inserted
        char = self.db.installed_on_char
        zone = self.db.installed_on_zone
        if char and zone:
            zones = getattr(char.db, "zones", None) or {}
            if zone in zones:
                mech = dict((zones[zone].get("mechanics") or {}))
                if mech.get("plug"):
                    plug_data = dict(mech["plug"])
                    plug_data["player_desc"] = desc
                    mech["plug"] = plug_data
                    zone_copy = dict(zones[zone])
                    zone_copy["mechanics"] = mech
                    zones_copy = dict(zones)
                    zones_copy[zone] = zone_copy
                    char.db.zones = zones_copy

        if locked:
            self.db.desc_locked       = True
            self.db.desc_lock_creator = creator.dbref if creator else None

        return True, ""


# ---------------------------------------------------------------------------
# Module-level helper — called by characters.py get_zone_display()
# ---------------------------------------------------------------------------

def get_plug_append(character, zone_name: str) -> str:
    """
    Return the text to append to the zone's nude desc if a plug is inserted.
    Returns "" if no plug, or plug has no desc.
    """
    zones = getattr(character.db, "zones", None) or {}
    mech  = (zones.get(zone_name) or {}).get("mechanics") or {}
    plug  = mech.get("plug")
    if not plug:
        return ""
    # Prefer player_desc over default desc
    return plug.get("player_desc") or plug.get("desc") or ""
