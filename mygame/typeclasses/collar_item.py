"""
typeclasses/collar_item.py

CollarItem — a wearable item for the neck zone that can be locked
             and serves as an anchor for leashes.

LeashItem  — attaches to a CollarItem and wires into the existing
             lead/follow system.

Collar install:  wear <collar>   (places it on the neck zone)
Collar remove:   remove <collar>  (fails if locked without key)
Leash attach:    attach leash <target>   (or handled by LeashItem)
Leash detach:    detach leash

Zone mechanics entry written on wear:
    zones['neck']['mechanics']['collar'] = {
        'item_dbref': str,
        'item_name':  str,
        'desc':       str,     # shown in zone nude desc (appended)
        'player_desc': str,
        'desc_locked': bool,
        'lock':        dict or None,   # slock/plock
        'leash_anchor': bool,  # True — can accept a leash
    }
"""

from evennia import DefaultObject


class CollarItem(DefaultObject):
    """
    A wearable collar for the neck zone.

    Wear:    wear <collar>
    Remove:  remove <collar>
    Desc:    itemdesc <collar> = <text>
    Lock:    itemdesc/lock <collar>
    Leash:   automatically becomes a leash anchor when worn
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key                  = "collar"
        self.db.desc              = "A plain collar."
        self.db.player_desc       = ""
        self.db.desc_locked       = False
        self.db.desc_lock_creator = None
        self.db.is_worn           = False
        self.db.worn_on_char      = None
        self.db.worn_on_zone      = "neck"   # default zone; configurable

    def get_display_name(self, looker=None, **kwargs):
        suffix = " [worn]" if self.db.is_worn else ""
        return f"{self.key}{suffix}"

    def get_active_desc(self) -> str:
        return self.db.player_desc or self.db.desc or ""

    # ------------------------------------------------------------------
    # Wear / remove
    # ------------------------------------------------------------------

    def wear(self, character, zone_name: str = None) -> tuple:
        """Attach collar to character's neck (or specified) zone."""
        if self.db.is_worn:
            return False, f"{self.key} is already being worn."

        zone_name = zone_name or self.db.worn_on_zone or "neck"
        zones = getattr(character.db, "zones", None) or {}
        if zone_name not in zones:
            return False, f"{character.db.rp_name or character.name} has no zone '{zone_name}'."

        mech = dict((zones[zone_name].get("mechanics") or {}))
        if mech.get("collar"):
            return False, f"A collar is already being worn on the {zone_name.replace('_', ' ')} zone."

        mech["collar"] = {
            "item_dbref":   self.dbref,
            "item_name":    self.key,
            "desc":         self.db.desc or "",
            "player_desc":  self.db.player_desc or "",
            "desc_locked":  self.db.desc_locked,
            "lock":         None,
            "leash_anchor": True,
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
        """Remove the collar. force=True bypasses lock."""
        if not self.db.is_worn:
            return False, f"{self.key} is not currently worn."

        character = self.db.worn_on_char
        zone_name = self.db.worn_on_zone

        if not character:
            self.db.is_worn = False
            return True, ""

        zones = getattr(character.db, "zones", None) or {}
        if zone_name in zones:
            mech = dict((zones[zone_name].get("mechanics") or {}))
            collar_data = mech.get("collar") or {}

            if not force and collar_data.get("lock"):
                lock = collar_data["lock"]
                if lock.get("type") == "plock":
                    return False, f"{self.key} is plock'd — a key is required."
                if lock.get("type") == "slock":
                    return False, f"{self.key} is slock'd — use the code."

            mech.pop("collar", None)
            zone_copy = dict(zones[zone_name])
            zone_copy["mechanics"] = mech
            zones_copy = dict(zones)
            zones_copy[zone_name] = zone_copy
            character.db.zones = zones_copy

        self.db.is_worn      = False
        self.db.worn_on_char = None
        return True, ""

    def set_player_desc(self, desc: str, locked: bool = False,
                        creator=None) -> tuple:
        if self.db.desc_locked:
            return False, f"The description on {self.key} has been permanently locked."
        self.db.player_desc = desc

        # Refresh in zone mechanics if worn
        char = self.db.worn_on_char
        zone = self.db.worn_on_zone
        if char and zone:
            zones = getattr(char.db, "zones", None) or {}
            if zone in zones:
                mech = dict((zones[zone].get("mechanics") or {}))
                if mech.get("collar"):
                    cd = dict(mech["collar"])
                    cd["player_desc"] = desc
                    mech["collar"] = cd
                    zc = dict(zones[zone]); zc["mechanics"] = mech
                    zs = dict(zones); zs[zone] = zc
                    char.db.zones = zs

        if locked:
            self.db.desc_locked       = True
            self.db.desc_lock_creator = creator.dbref if creator else None
        return True, ""


# ---------------------------------------------------------------------------
# LeashItem
# ---------------------------------------------------------------------------

class LeashItem(DefaultObject):
    """
    A leash that can be attached to a collar-wearing character.

    The leash holder becomes the lead-er; the collar-wearer is led.
    Wires into the existing lead/follow system (char.db.led_by).

    Attach:  attach leash <target>
    Detach:  detach leash  (or  unlead  to use existing command)
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key               = "leash"
        self.db.desc           = "A simple leash."
        self.db.player_desc    = ""
        self.db.desc_locked    = False
        self.db.is_attached    = False
        self.db.holder         = None   # character holding the leash end
        self.db.target         = None   # character wearing the collar

    def get_display_name(self, looker=None, **kwargs):
        if self.db.is_attached:
            holder = self.db.holder
            target = self.db.target
            hn = (holder.db.rp_name or holder.name) if holder else "?"
            tn = (target.db.rp_name or target.name) if target else "?"
            return f"{self.key} [{hn} → {tn}]"
        return self.key

    def attach(self, holder, target) -> tuple:
        """
        Attach this leash from holder to target.
        Target must have a collar with leash_anchor=True.
        Wires the existing lead system.
        """
        if self.db.is_attached:
            return False, f"{self.key} is already attached."

        # Verify target has a collar
        zones = getattr(target.db, "zones", None) or {}
        has_anchor = False
        for zd in zones.values():
            collar = (zd.get("mechanics") or {}).get("collar")
            if collar and collar.get("leash_anchor"):
                has_anchor = True
                break

        if not has_anchor:
            tname = target.db.rp_name or target.name
            return False, f"{tname} is not wearing a collar with a leash anchor."

        # Wire the lead system (same as CmdLead)
        if holder.db.leading:
            return False, "You're already leading someone. Use 'unlead' first."

        holder_name = holder.db.rp_name or holder.name
        target_name = target.db.rp_name or target.name
        active_desc = self.db.player_desc or self.db.desc or "a leash"

        holder.db.leading  = target.id
        target.db.led_by   = holder.id
        target.db.lead_desc = (
            f"{target_name} is led by {holder_name} — {active_desc}"
        )

        self.db.is_attached = True
        self.db.holder      = holder
        self.db.target      = target
        self.location       = holder

        return True, ""

    def detach(self) -> tuple:
        """Detach the leash and clear lead state on both ends."""
        if not self.db.is_attached:
            return False, f"{self.key} is not currently attached."

        holder = self.db.holder
        target = self.db.target

        if holder:
            holder.db.leading = None
        if target:
            target.db.led_by   = None
            target.db.lead_desc = ""

        self.db.is_attached = False
        self.db.holder      = None
        self.db.target      = None

        return True, ""

    def set_player_desc(self, desc: str, locked: bool = False,
                        creator=None) -> tuple:
        if self.db.desc_locked:
            return False, f"The description on {self.key} has been permanently locked."
        self.db.player_desc = desc
        if locked:
            self.db.desc_locked = True
        return True, ""
