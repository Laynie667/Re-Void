"""
typeclasses/wearable_item.py

WearableItem — a physical clothing item that covers a zone.

Unlike freeform items (which are description-only), WearableItems are real
game objects that live in inventory when not worn, can be traded/given, and
write into the zone's covered_by dict when equipped.

Subclasses can set default_zone to auto-select the right zone on wear.

Wear:    wear <item> [zone]
Remove:  remove <item>
Desc:    itemdesc <item> = <text>
Lock:    itemdesc/lock <item>

DB attributes:
    desc            str    — short room-visible description
    worn_desc       str    — description shown when worn (used for covered_by.worn_desc)
    examine_desc    str    — examine-layer description
    player_desc     str    — player-written override for worn_desc
    desc_locked     bool   — lock the player_desc permanently
    default_zone    str    — default zone this item goes on (e.g. "chest", "hips")
    camouflage_desc str    — if set, applies outfit camouflage when worn
    is_worn         bool
    worn_on_char    obj
    worn_on_zone    str
"""

from evennia import DefaultObject


class WearableItem(DefaultObject):
    """
    A wearable clothing item that covers a character zone.

    Wear:   wear <item> [zone]
    Remove: remove <item>
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key                   = "garment"
        self.db.desc               = "A plain garment."
        self.db.worn_desc          = ""        # shown when worn (covered_by.worn_desc)
        self.db.examine_desc       = ""        # extra detail on deep examine
        self.db.player_desc        = ""        # player override for worn_desc
        self.db.desc_locked        = False
        self.db.desc_lock_creator  = None
        self.db.camouflage_desc    = ""        # outfit camouflage override
        self.db.default_zone       = ""        # e.g. "chest", "hips", "neck"
        self.db.is_worn            = False
        self.db.worn_on_char       = None
        self.db.worn_on_zone       = None

    def get_display_name(self, looker=None, **kwargs):
        suffix = " [worn]" if self.db.is_worn else ""
        return f"{self.key}{suffix}"

    def get_worn_desc(self) -> str:
        """Return the description shown in the zone's covered_by layer."""
        return self.db.player_desc or self.db.worn_desc or self.db.desc or ""

    # ------------------------------------------------------------------
    # Wear / remove
    # ------------------------------------------------------------------

    def wear(self, character, zone_name: str = None) -> tuple:
        """
        Cover the specified zone on character with this item.
        Returns (True, "") or (False, reason).
        """
        if self.db.is_worn:
            return False, f"{self.key} is already being worn."

        zone_name = zone_name or self.db.default_zone
        if not zone_name:
            return False, (
                f"Specify a zone: wear {self.key} <zone>\n"
                f"Available zones: " +
                ", ".join(
                    (getattr(character.db, "zones", None) or {}).keys()
                )
            )

        zones = getattr(character.db, "zones", None) or {}
        zone_name = zone_name.lower().replace(" ", "_")
        if zone_name not in zones:
            return False, f"No zone '{zone_name}' found."

        # Write covered_by
        covered = {
            "desc":         self.get_worn_desc(),
            "worn_desc":    self.get_worn_desc(),
            "examine_desc": self.db.examine_desc or "",
            "ambient":      [],
            "type":         "wearable",
            "item_id":      self.dbref,
        }

        zone_copy = dict(zones[zone_name])
        zone_copy["covered_by"] = covered
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone_copy
        character.db.zones = zones_copy

        # Apply camouflage if this item has one
        if self.db.camouflage_desc:
            character.db.outfit_camouflage = self.db.camouflage_desc

        # Rebuild outfit desc
        try:
            character._rebuild_outfit_desc()
        except Exception:
            pass

        self.db.is_worn      = True
        self.db.worn_on_char = character
        self.db.worn_on_zone = zone_name
        self.location        = character
        return True, ""

    def remove(self, force: bool = False) -> tuple:
        """Remove this item from the zone it's covering."""
        if not self.db.is_worn:
            return False, f"{self.key} is not currently worn."

        character = self.db.worn_on_char
        zone_name = self.db.worn_on_zone

        if not character:
            self.db.is_worn = False
            return True, ""

        zones = getattr(character.db, "zones", None) or {}
        if zone_name in zones:
            zone_copy = dict(zones[zone_name])
            covered = zone_copy.get("covered_by") or {}
            # Only clear if this item owns the covered_by
            if covered.get("item_id") == self.dbref:
                zone_copy["covered_by"] = None
                zones_copy = dict(zones)
                zones_copy[zone_name] = zone_copy
                character.db.zones = zones_copy

        # Clear camouflage if this item set it
        if self.db.camouflage_desc:
            current_cam = getattr(character.db, "outfit_camouflage", "")
            if current_cam == self.db.camouflage_desc:
                character.db.outfit_camouflage = ""

        try:
            character._rebuild_outfit_desc()
        except Exception:
            pass

        self.db.is_worn      = False
        self.db.worn_on_char = None
        self.db.worn_on_zone = None
        return True, ""

    def set_player_desc(self, desc: str, locked: bool = False,
                        creator=None) -> tuple:
        if self.db.desc_locked:
            return False, f"The description on {self.key} has been permanently locked."
        self.db.player_desc = desc

        # Refresh covered_by if currently worn
        char = self.db.worn_on_char
        zone = self.db.worn_on_zone
        if char and zone:
            zones = getattr(char.db, "zones", None) or {}
            if zone in zones:
                cov = dict((zones[zone].get("covered_by") or {}))
                if cov.get("item_id") == self.dbref:
                    cov["worn_desc"] = desc
                    cov["desc"]      = desc
                    zc = dict(zones[zone]); zc["covered_by"] = cov
                    zs = dict(zones); zs[zone] = zc
                    char.db.zones = zs
                    try:
                        char._rebuild_outfit_desc()
                    except Exception:
                        pass

        if locked:
            self.db.desc_locked       = True
            self.db.desc_lock_creator = creator.dbref if creator else None
        return True, ""
