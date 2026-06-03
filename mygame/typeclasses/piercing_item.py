"""
typeclasses/piercing_item.py

PiercingItem — a wearable piercing that goes on a specific zone.

Piercings are lightweight WearableItems that don't cover the zone
(no covered_by) but instead append their description and apply
optional mechanical effects.

Effects:
    sensitivity   float  — arousal gain multiplier on interactions with this zone
                           e.g. 0.25 = +25% arousal from suck/touch/etc. on this zone
    display       bool   — adds a persistent visible marking-style element to the zone desc
    linked        str    — dbref of a paired piercing; desc shows connection between them
    conductive    bool   — placeholder for future electric/magic stimuli response

Zone mechanics entry written on wear:
    zones[zone_name]['mechanics']['piercing_<slot>'] = {
        'item_dbref':   str
        'item_name':    str
        'desc':         str    — appended to zone nude desc
        'player_desc':  str    — player-written override
        'desc_locked':  bool
        'effect':       dict   — {sensitivity, display, linked, conductive}
        'slot':         str    — 'left', 'right', 'center', 'bar', etc.
    }

Multiple piercings per zone are supported via the slot key.
"""

from typeclasses.wearable_item import WearableItem


class PiercingItem(WearableItem):
    """
    A piercing that decorates a zone without covering it.

    Wear:   wear <piercing> [zone]
    Remove: remove <piercing>
    Desc:   itemdesc <piercing> = <text>
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key             = "piercing"
        self.db.desc         = "A simple ring."
        self.db.worn_desc    = ""        # shown appended to zone nude desc
        self.db.examine_desc = ""
        self.db.player_desc  = ""
        self.db.default_zone = ""
        self.db.slot         = "center"  # left/right/center/bar/hoop/stud
        self.db.leash_anchor = False     # ring-type piercings a leash can clip to

        # Effect flags
        self.db.effect = {
            "sensitivity": 0.0,    # bonus arousal multiplier
            "display":     False,  # show as permanent marking-like element
            "linked":      None,   # dbref of paired piercing
            "conductive":  False,  # future effect
        }

    def get_active_desc(self) -> str:
        return self.db.player_desc or self.db.worn_desc or self.db.desc or ""

    def wear(self, character, zone_name: str = None) -> tuple:
        """
        Install the piercing on the zone — appends desc, doesn't cover.
        """
        if self.db.is_worn:
            return False, f"{self.key} is already worn."

        zone_name = zone_name or self.db.default_zone
        if not zone_name:
            return False, f"Specify a zone: wear {self.key} <zone>"

        zones = getattr(character.db, "zones", None) or {}
        zone_name = zone_name.lower().replace(" ", "_")
        if zone_name not in zones:
            return False, f"No zone '{zone_name}' found."

        # Use a slot-keyed mechanics entry — supports multiple piercings per zone
        slot_key = f"piercing_{self.db.slot or 'center'}"
        mech = dict((zones[zone_name].get("mechanics") or {}))
        if mech.get(slot_key):
            return False, (
                f"There's already a {self.db.slot} piercing on "
                f"{zone_name.replace('_', ' ')}."
            )

        mech[slot_key] = {
            "item_dbref":  self.dbref,
            "item_name":   self.key,
            "desc":        self.get_active_desc(),
            "player_desc": self.db.player_desc or "",
            "desc_locked": self.db.desc_locked,
            "effect":      dict(self.db.effect or {}),
            "slot":        self.db.slot,
            "leash_anchor": bool(getattr(self.db, "leash_anchor", False)),
        }

        zone_copy = dict(zones[zone_name])
        zone_copy["mechanics"] = mech
        zones_copy = dict(zones)
        zones_copy[zone_name] = zone_copy
        character.db.zones = zones_copy

        self.db.is_worn      = True
        self.db.worn_on_char = character
        self.db.worn_on_zone = zone_name
        self.location        = character
        return True, ""

    def remove(self, force: bool = False) -> tuple:
        """Remove the piercing from its zone."""
        if not self.db.is_worn:
            return False, f"{self.key} is not currently worn."

        character = self.db.worn_on_char
        zone_name = self.db.worn_on_zone

        if not character:
            self.db.is_worn = False
            return True, ""

        slot_key = f"piercing_{self.db.slot or 'center'}"
        zones = getattr(character.db, "zones", None) or {}
        if zone_name in zones:
            mech = dict((zones[zone_name].get("mechanics") or {}))
            mech.pop(slot_key, None)
            zone_copy = dict(zones[zone_name])
            zone_copy["mechanics"] = mech
            zones_copy = dict(zones)
            zones_copy[zone_name] = zone_copy
            character.db.zones = zones_copy

        self.db.is_worn      = False
        self.db.worn_on_char = None
        self.db.worn_on_zone = None
        return True, ""


# ---------------------------------------------------------------------------
# Module-level helper — called by get_zone_display to append piercing descs
# ---------------------------------------------------------------------------

def get_piercing_appends(character, zone_name: str) -> str:
    """
    Return concatenated desc text for all piercings installed on this zone.
    Returns "" if none.
    """
    zones = getattr(character.db, "zones", None) or {}
    mech  = (zones.get(zone_name) or {}).get("mechanics") or {}
    parts = []
    for key, data in mech.items():
        if key.startswith("piercing_") and isinstance(data, dict):
            desc = data.get("player_desc") or data.get("desc") or ""
            if desc:
                parts.append(desc)
    return "  ".join(parts)
