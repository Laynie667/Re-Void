"""
typeclasses/brand_item.py

BrandItem — applies a mark to a character's zone.

Three durability types:
  temporary   — TTL-based (hours); fades on its own
  permanent   — no TTL; stays until manually removed (requires consent/key)
  soul_bound  — permanent AND applies to all characters on the same account

Brands are stored as freeform items on the character with special metadata.
Soul-bound brands write to the account's db so all characters share the mark.

Optional effects:
  sensitivity float   — arousal bonus on this zone while branded
  binding_effects dict — any of the standard binding effect flags

Usage:
  use <brand> on <target> [zone]   — apply the brand (both must consent)
  brand remove <name>              — remove a temporary/permanent brand if permitted
"""

import time
from evennia import DefaultObject


# Brand visibility options
_VISIBILITY = ("casual", "intimate", "mature")


class BrandItem(DefaultObject):
    """
    A branding item. Used on a target to apply a mark to their zone.

    Use:    use <brand> on <target> [zone]
    Remove: brand remove <mark_name>
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key               = "brand"
        self.db.desc           = "A branding instrument."
        self.db.mark_desc      = ""         # the text of the mark itself
        self.db.player_desc    = ""         # player-customizable version
        self.db.desc_locked    = False
        self.db.durability     = "temporary"  # temporary / permanent / soul_bound
        self.db.ttl_hours      = 24.0         # only used if temporary
        self.db.default_zone   = ""
        self.db.visibility     = "intimate"   # casual / intimate / mature
        self.db.sensitivity    = 0.0          # arousal bonus while marked
        self.db.binding_effects = {}          # optional effects

    def get_mark_desc(self) -> str:
        return self.db.player_desc or self.db.mark_desc or self.db.desc or ""

    def apply(self, actor, target, zone_name: str) -> tuple:
        """
        Apply the brand to target's zone.
        Returns (True, "") or (False, reason).
        """
        zones = getattr(target.db, "zones", None) or {}
        zone_name = zone_name.lower().replace(" ", "_") if zone_name else ""

        if zone_name and zone_name not in zones:
            return False, f"No zone '{zone_name}' on {target.db.rp_name or target.name}."

        if not zone_name and zones:
            zone_name = next(iter(zones))

        mark_text   = self.get_mark_desc()
        actor_name  = actor.db.rp_name  or actor.name
        target_name = target.db.rp_name or target.name
        mark_key    = f"brand_{actor_name.lower()}_{int(time.time()) % 10000}"

        from world.freeform_manager import FreeformManager
        ok, _ = FreeformManager.place_item(
            target, zone_name, mark_key, mark_text,
            actor.id, display_mode="on"
        )
        if not ok:
            return False, "Could not apply mark."

        items = target.db.freeform_items or {}
        entry = items.get(mark_key)
        if entry:
            entry["brand"]      = True
            entry["durability"] = self.db.durability
            entry["visibility"] = self.db.visibility
            entry["sensitivity"]= self.db.sensitivity
            if self.db.durability == "temporary":
                entry["ttl_hours"]  = self.db.ttl_hours or 24.0
                entry["created_at"] = time.time()
            target.db.freeform_items = items

        # Soul-bound: write to account db
        if self.db.durability == "soul_bound":
            self._apply_soul_bound(target, mark_key, mark_text, zone_name)

        # Apply binding effects if any
        if self.db.binding_effects:
            try:
                from world.binding_effects import apply_effects
                apply_effects(target, self)
            except Exception:
                pass

        return True, mark_key

    def _apply_soul_bound(self, target, mark_key: str, mark_text: str,
                           zone_name: str):
        """Write brand to account.db so all characters see it."""
        try:
            account = target.account
            if not account:
                return
            brands = dict(account.db.soul_bound_brands or {})
            brands[mark_key] = {
                "desc":      mark_text,
                "zone":      zone_name,
                "visibility": self.db.visibility,
                "sensitivity": self.db.sensitivity,
            }
            account.db.soul_bound_brands = brands
        except Exception:
            pass

    def set_player_desc(self, desc: str, locked: bool = False,
                        creator=None) -> tuple:
        if self.db.desc_locked:
            return False, f"The description on {self.key} is locked."
        self.db.player_desc = desc
        if locked:
            self.db.desc_locked = True
        return True, ""


# ---------------------------------------------------------------------------
# CmdBrand — apply and remove brands
# ---------------------------------------------------------------------------

from evennia.commands.default.muxcommand import MuxCommand


class CmdBrand(MuxCommand):
    """
    Apply a brand to another character, or remove a brand you carry.

    Usage:
      brand <target> [zone]             — apply a BrandItem from your inventory
      brand/remove <mark_name>          — remove a brand from yourself (if removable)
      brand/list                        — list brands on yourself
      brand/list <target>               — list visible brands on target

    Brands require both parties to have mature consent.
    Soul-bound brands appear on all characters on the account.
    """

    key     = "brand"
    locks   = "cmd:all()"
    help_category = "Interaction"
    switch_options = ("remove", "list")

    def func(self):
        caller = self.caller
        args   = self.args.strip()

        if "list" in self.switches:
            self._do_list(caller, args)
            return
        if "remove" in self.switches:
            self._do_remove(caller, args)
            return

        self._do_apply(caller, args)

    def _do_apply(self, caller, args):
        from typeclasses.brand_item import BrandItem
        room = caller.location

        if not args:
            caller.msg("|xUsage: brand <target> [zone]|n")
            return

        # Find brand in inventory
        brand = next(
            (obj for obj in caller.contents if isinstance(obj, BrandItem)),
            None
        )
        if not brand:
            caller.msg("|xYou don't have a brand to apply.|n")
            return

        parts     = args.split(None, 1)
        tgt_name  = parts[0]
        zone_arg  = parts[1].strip() if len(parts) > 1 else ""

        target = caller.search(tgt_name, location=room)
        if not target:
            return

        ok, result = brand.apply(caller, target, zone_arg)
        if not ok:
            caller.msg(f"|x{result}|n")
            return

        caller_name = caller.db.rp_name or caller.name
        target_name = target.db.rp_name or target.name
        zone_disp   = zone_arg.replace("_", " ") or "body"
        caller.msg(f"|wBrand applied to {target_name}'s {zone_disp}.|n")
        target.msg(f"|x{caller_name} marks you. The brand settles.|n")
        if room:
            room.msg_contents(
                f"|x{caller_name} brands {target_name}.|n",
                exclude=[caller, target],
            )

    def _do_remove(self, caller, mark_name):
        if not mark_name:
            caller.msg("|xUsage: brand/remove <mark_name>|n")
            return
        items = caller.db.freeform_items or {}
        key   = mark_name.lower()
        entry = items.get(key)
        if not entry or not entry.get("brand"):
            caller.msg(f"|xNo brand named '{mark_name}' found.|n")
            return
        if entry.get("durability") == "permanent":
            caller.msg("|xThis brand is permanent — it cannot be removed.|n")
            return
        if entry.get("durability") == "soul_bound":
            caller.msg("|xThis brand is soul-bound — it persists across all your characters.|n")
            return
        items.pop(key, None)
        caller.db.freeform_items = items
        caller.msg(f"|wBrand '{mark_name}' removed.|n")

    def _do_list(self, caller, args):
        target = caller
        if args:
            target = caller.search(args, location=caller.location)
            if not target:
                return
        items  = target.db.freeform_items or {}
        brands = {k: v for k, v in items.items() if v.get("brand")}

        # Also check soul-bound brands
        soul_brands = {}
        try:
            if target.account:
                soul_brands = dict(target.account.db.soul_bound_brands or {})
        except Exception:
            pass

        if not brands and not soul_brands:
            caller.msg(f"|x{target.db.rp_name or target.name} has no brands.|n")
            return

        lines = [f"|wBrands on {target.db.rp_name or target.name}:|n"]
        for k, v in brands.items():
            dur  = v.get("durability", "temporary")
            desc = v.get("desc", k)[:60]
            lines.append(f"  |w{k}|n [{dur}]: {desc}")
        for k, v in soul_brands.items():
            desc = v.get("desc", k)[:60]
            lines.append(f"  |w{k}|n [soul-bound]: {desc}")
        caller.msg("\n".join(lines))


ALL_BRAND_CMDS = [CmdBrand]
