"""
typeclasses/chastity_item.py

ChastityItem — a wearable that prevents penetration and deposit commands.

Two subtypes:
  ChastiyCage   — shaft/penis zone. Blocks thrust and deposit from the wearer.
  ChastityBelt  — orifice/groin zone. Blocks the zone from penetration.

Both can be timed (ttl_hours) or permanent.
Both can require a key (plock-style) or a code (slock-style) to remove.
Both support the full binding_effects system for compounding effects.

Zone mechanics entry written on wear:
    zones[zone_name]['mechanics']['chastity'] = {
        'item_dbref':   str
        'item_name':    str
        'desc':         str
        'type':         'cage' | 'belt'
        'lock':         dict or None   (slock/plock)
        'ttl_hours':    float or None  (if timed)
        'created_at':   float          (unix timestamp)
        'seals_zone':   bool           (True — blocks penetration/deposit)
    }
"""

import time
from typeclasses.wearable_item import WearableItem


class ChastityItem(WearableItem):
    """
    Base chastity item. Blocks penetration and deposit on the target zone.

    Wear:   wear <chastity item> [zone]
    Remove: remove <chastity item>  (fails if locked or timed and not expired)
    """

    chastity_type = "belt"   # override in subclasses: 'cage' or 'belt'

    def at_object_creation(self):
        super().at_object_creation()
        self.key             = "chastity device"
        self.db.desc         = "A chastity device."
        self.db.worn_desc    = "A chastity device, fitted and secured."
        self.db.chastity_type = self.chastity_type
        self.db.ttl_hours    = None    # if set, auto-releases after this many hours
        self.db.created_at   = None    # set on wear if timed

    def wear(self, character, zone_name: str = None) -> tuple:
        """Install chastity on the zone."""
        ok, reason = super().wear(character, zone_name)
        if not ok:
            return ok, reason

        zone_name = self.db.worn_on_zone
        zones = getattr(character.db, "zones", None) or {}
        if zone_name in zones:
            mech = dict((zones[zone_name].get("mechanics") or {}))
            mech["chastity"] = {
                "item_dbref":  self.dbref,
                "item_name":   self.key,
                "desc":        self.get_worn_desc(),
                "type":        self.db.chastity_type or self.chastity_type,
                "lock":        None,
                "ttl_hours":   self.db.ttl_hours,
                "created_at":  time.time() if self.db.ttl_hours else None,
                "seals_zone":  True,
            }
            zone_copy = dict(zones[zone_name])
            zone_copy["mechanics"] = mech
            zones_copy = dict(zones)
            zones_copy[zone_name] = zone_copy
            character.db.zones = zones_copy

        if self.db.ttl_hours:
            hrs = self.db.ttl_hours
            character.msg(
                f"|xThe chastity device locks in place. "
                f"It will release in {hrs:.0f} hour{'s' if hrs != 1 else ''}.|n"
            )
        return True, ""

    def remove(self, force: bool = False) -> tuple:
        """Remove chastity device, checking timed and lock status."""
        char      = self.db.worn_on_char
        zone_name = self.db.worn_on_zone

        if not self.db.is_worn:
            return False, f"{self.key} is not currently worn."

        if char and zone_name and not force:
            zones = getattr(char.db, "zones", None) or {}
            mech  = (zones.get(zone_name) or {}).get("mechanics") or {}
            ch    = mech.get("chastity") or {}

            # Timed check — still locked?
            if ch.get("ttl_hours") and ch.get("created_at"):
                elapsed = (time.time() - ch["created_at"]) / 3600.0
                if elapsed < ch["ttl_hours"]:
                    remaining = ch["ttl_hours"] - elapsed
                    hrs  = int(remaining)
                    mins = int((remaining - hrs) * 60)
                    return False, (
                        f"|xThe chastity device is still locked. "
                        f"{hrs}h {mins}m remaining.|n"
                    )

            # Key/code lock check
            if ch.get("lock"):
                lock = ch["lock"]
                if lock.get("type") == "plock":
                    return False, f"|x{self.key} is plock'd — a key is required.|n"
                if lock.get("type") == "slock":
                    return False, f"|x{self.key} is slock'd — use the code.|n"

        # Clear mechanics entry
        if char and zone_name:
            zones = getattr(char.db, "zones", None) or {}
            if zone_name in zones:
                mech = dict((zones[zone_name].get("mechanics") or {}))
                mech.pop("chastity", None)
                zc = dict(zones[zone_name]); zc["mechanics"] = mech
                zs = dict(zones); zs[zone_name] = zc
                char.db.zones = zs

        return super().remove(force=True)   # skip WearableItem's lock check, we handled it

    def get_display_name(self, looker=None, **kwargs):
        suffix = " [locked]" if self.db.is_worn else ""
        return f"{self.key}{suffix}"


class ChastiyCage(ChastityItem):
    """Chastity cage — goes on shaft zones, blocks thrust/deposit from the wearer."""
    chastity_type = "cage"

    def at_object_creation(self):
        super().at_object_creation()
        self.key          = "chastity cage"
        self.db.desc      = "A chastity cage that fits over the shaft."
        self.db.worn_desc = "A chastity cage, fitted and locked over the shaft — no access."
        self.db.default_zone = "groin"


class ChastityBelt(ChastityItem):
    """Chastity belt — goes on orifice zones, blocks penetration of the wearer."""
    chastity_type = "belt"

    def at_object_creation(self):
        super().at_object_creation()
        self.key          = "chastity belt"
        self.db.desc      = "A chastity belt, fitted around the hips."
        self.db.worn_desc = "A chastity belt fitted snugly around the hips — the front panel sealed."
        self.db.default_zone = "groin"


# ---------------------------------------------------------------------------
# Module-level helper — check if a zone is chastity-locked
# ---------------------------------------------------------------------------

def is_chastity_locked(character, zone_name: str) -> bool:
    """Return True if this zone has an active chastity mechanic."""
    zones = getattr(character.db, "zones", None) or {}
    mech  = (zones.get(zone_name) or {}).get("mechanics") or {}
    ch    = mech.get("chastity")
    if not ch:
        return False

    # Check if timed chastity has expired
    if ch.get("ttl_hours") and ch.get("created_at"):
        elapsed = (time.time() - ch["created_at"]) / 3600.0
        if elapsed >= ch["ttl_hours"]:
            return False   # expired — passive tick will clean it up
    return True


def passive_chastity_check(character):
    """
    Called by passive tick — releases expired timed chastity devices.
    """
    zones = getattr(character.db, "zones", None) or {}
    for zone_name, zone_data in zones.items():
        mech = (zone_data or {}).get("mechanics") or {}
        ch   = mech.get("chastity")
        if not ch:
            continue
        if ch.get("ttl_hours") and ch.get("created_at"):
            elapsed = (time.time() - ch["created_at"]) / 3600.0
            if elapsed >= ch["ttl_hours"]:
                # Auto-release — find the item and remove it
                from evennia import search_object
                results = search_object(ch.get("item_dbref", ""), exact=True)
                if results:
                    item = results[0]
                    item.remove(force=True)
                    character.msg(
                        f"|x{item.key} releases — the time is up.|n"
                    )
                    room = character.location
                    if room:
                        cname = character.db.rp_name or character.name
                        room.msg_contents(
                            f"|x{cname}'s chastity device releases on its timer.|n",
                            exclude=[character],
                        )
