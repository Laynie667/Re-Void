"""
commands/item_commands.py

Commands for wearable, insertable, and collar/leash items.

  insert <item> [zone]      — insert a PlugItem into an orifice zone
  unplug [zone]             — remove the plug from a zone
  wear <item> [zone]        — wear a WearableItem or CollarItem
  remove <item>             — remove a worn/inserted item
  attach leash <target>     — attach a LeashItem to a collar-wearing target
  detach leash              — detach the leash you are holding
  itemdesc <item> = <text>  — set player description on an item
  itemdesc/lock <item>      — permanently lock an item description
  camouflage [desc]         — set/view/clear outfit camouflage on your character
"""

from evennia.commands.default.muxcommand import MuxCommand
from evennia import Command


# ---------------------------------------------------------------------------
# CmdInsert — insert a PlugItem into a zone
# ---------------------------------------------------------------------------

class CmdInsert(Command):
    """
    Insert a plug or insertable item into an orifice zone.

    Usage:
      insert <item> [zone]

    If you only have one orifice zone, zone is optional.
    The plug's description is appended to that zone's description.
    Use 'unplug [zone]' or 'remove <item>' to take it out.
    """

    key     = "insert"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        args   = self.args.strip()
        room   = caller.location

        if not args:
            caller.msg("|xUsage: insert <item> [zone]|n")
            return

        parts     = args.split(None, 1)
        item_name = parts[0]
        zone_arg  = parts[1].strip().lower().replace(" ", "_") if len(parts) > 1 else None

        from typeclasses.plug_item import PlugItem
        item = caller.search(item_name, location=caller)
        if not item:
            return
        if not isinstance(item, PlugItem):
            caller.msg(f"|x{item.key} can't be inserted.|n")
            return

        # Find target zone
        zones = getattr(caller.db, "zones", None) or {}
        orifice_zones = [
            zn for zn, zd in zones.items()
            if (zd or {}).get("zone_type") in ("orifice", "both")
        ]

        if not orifice_zones:
            caller.msg("|xYou have no orifice zones to insert into.|n")
            return

        if zone_arg:
            zone_name = next(
                (zn for zn in orifice_zones
                 if zn == zone_arg or zn.endswith(zone_arg)),
                None
            )
            if not zone_name:
                caller.msg(f"|xNo orifice zone matching '{zone_arg}'.|n")
                return
        elif len(orifice_zones) == 1:
            zone_name = orifice_zones[0]
        else:
            zlist = ", ".join(zn.replace("_", " ") for zn in orifice_zones)
            caller.msg(f"|xMultiple orifice zones — specify one: {zlist}|n")
            return

        ok, reason = item.insert(caller, zone_name)
        if not ok:
            caller.msg(f"|x{reason}|n")
            return

        caller_name = caller.db.rp_name or caller.name
        zone_disp   = zone_name.replace("_", " ")
        caller.msg(f"|wYou insert {item.key} into your {zone_disp}.|n")
        if room:
            room.msg_contents(
                f"|x{caller_name} inserts something into {np(caller)} {zone_disp}.|n",
                exclude=caller,
            )


def np(char):
    """Shorthand possessive pronoun."""
    pron = getattr(char.db, "pronouns", None) or {}
    return pron.get("possessive", "their")


# ---------------------------------------------------------------------------
# CmdUnplug — remove a plug from a zone
# ---------------------------------------------------------------------------

class CmdUnplug(Command):
    """
    Remove a plug from an orifice zone.

    Usage:
      unplug [zone]
      unplug <item>

    If you only have one plug inserted, argument is optional.
    Fails if the plug is slock'd or plock'd.
    """

    key     = "unplug"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        args   = self.args.strip().lower().replace(" ", "_")
        room   = caller.location

        from typeclasses.plug_item import PlugItem

        # Find inserted plugs on caller
        plugs = [
            obj for obj in caller.contents
            if isinstance(obj, PlugItem) and obj.db.is_inserted
        ]

        if not plugs:
            caller.msg("|xYou don't have anything inserted.|n")
            return

        if args:
            # Match by zone or item name
            target_plug = next(
                (p for p in plugs
                 if args in (p.db.installed_on_zone or "")
                 or args in p.key.lower()),
                None
            )
            if not target_plug:
                caller.msg(f"|xNo inserted plug matching '{self.args.strip()}'.|n")
                return
        elif len(plugs) == 1:
            target_plug = plugs[0]
        else:
            names = ", ".join(
                f"{p.key} ({(p.db.installed_on_zone or '').replace('_', ' ')})"
                for p in plugs
            )
            caller.msg(f"|xMultiple plugs inserted — specify one: {names}|n")
            return

        ok, reason = target_plug.remove()
        if not ok:
            caller.msg(f"|x{reason}|n")
            return

        caller_name = caller.db.rp_name or caller.name
        zone_disp   = (target_plug.db.installed_on_zone or "zone").replace("_", " ")
        caller.msg(f"|wYou remove {target_plug.key} from your {zone_disp}.|n")
        if room:
            room.msg_contents(
                f"|x{caller_name} removes something from {np(caller)} {zone_disp}.|n",
                exclude=caller,
            )


# ---------------------------------------------------------------------------
# CmdWear — wear a WearableItem or CollarItem
# ---------------------------------------------------------------------------

class CmdWear(Command):
    """
    Wear a clothing item or collar.

    Usage:
      wear <item> [zone]

    Zone is optional if the item has a default zone set.
    Clothing covers the zone; deep examine shows the examine_desc.

    See also: remove, outfit, wardrobe
    """

    key     = "wear"
    locks   = "cmd:all()"
    help_category = "Character"

    def func(self):
        caller = self.caller
        args   = self.args.strip()
        room   = caller.location

        if not args:
            caller.msg("|xUsage: wear <item> [zone]|n")
            return

        parts     = args.split(None, 1)
        item_name = parts[0]
        zone_arg  = parts[1].strip() if len(parts) > 1 else None

        from typeclasses.wearable_item import WearableItem
        from typeclasses.collar_item   import CollarItem

        item = caller.search(item_name, location=caller)
        if not item:
            return

        # Anti-clothing check before wearing
        from typeclasses.collar_item   import CollarItem
        from typeclasses.wearable_item import WearableItem
        if isinstance(item, WearableItem) and item.get_worn_desc():
            try:
                from world.binding_effects import check_anti_clothing
                ok2, reason2 = check_anti_clothing(caller)
                if not ok2:
                    caller.msg(reason2)
                    return
            except Exception:
                pass

        if isinstance(item, CollarItem):
            ok, reason = item.wear(caller, zone_arg)
        elif isinstance(item, WearableItem):
            ok, reason = item.wear(caller, zone_arg)
        else:
            caller.msg(f"|x{item.key} can't be worn.|n")
            return

        if not ok:
            caller.msg(f"|x{reason}|n")
            return

        # Apply binding effects if item has them
        try:
            from world.binding_effects import apply_effects
            apply_effects(caller, item)
        except Exception:
            pass

        caller_name = caller.db.rp_name or caller.name
        zone_disp   = (item.db.worn_on_zone or "").replace("_", " ")
        caller.msg(f"|wYou put on {item.key}{'  on your ' + zone_disp if zone_disp else ''}.|n")
        if room:
            room.msg_contents(
                f"|x{caller_name} puts on {item.key}.|n",
                exclude=caller,
            )


# ---------------------------------------------------------------------------
# CmdRemoveItem — remove a worn or inserted item
# ---------------------------------------------------------------------------

class CmdRemoveItem(Command):
    """
    Remove a worn clothing item, collar, or inserted plug.

    Usage:
      remove <item>

    Fails if the item is locked (slock or plock).
    Use 'unplug [zone]' as a shortcut for plugs.
    """

    key     = "remove"
    locks   = "cmd:all()"
    help_category = "Character"

    def func(self):
        caller = self.caller
        args   = self.args.strip()
        room   = caller.location

        if not args:
            caller.msg("|xUsage: remove <item>|n")
            return

        from typeclasses.wearable_item import WearableItem
        from typeclasses.collar_item   import CollarItem
        from typeclasses.plug_item     import PlugItem

        item = caller.search(args, location=caller)
        if not item:
            return

        if isinstance(item, PlugItem):
            ok, reason = item.remove()
        elif isinstance(item, CollarItem):
            # Check self-remove lock
            try:
                from world.binding_effects import check_self_remove_allowed
                ok2, reason2 = check_self_remove_allowed(caller, item)
                if not ok2:
                    caller.msg(reason2)
                    return
            except Exception:
                pass
            ok, reason = item.remove()
        elif isinstance(item, WearableItem):
            try:
                from world.binding_effects import check_self_remove_allowed
                ok2, reason2 = check_self_remove_allowed(caller, item)
                if not ok2:
                    caller.msg(reason2)
                    return
            except Exception:
                pass
            ok, reason = item.remove()
        else:
            caller.msg(f"|x{item.key} can't be removed that way.|n")
            return

        if not ok:
            caller.msg(f"|x{reason}|n")
            return

        # Remove binding effects
        try:
            from world.binding_effects import remove_effects
            remove_effects(caller, item)
        except Exception:
            pass

        caller_name = caller.db.rp_name or caller.name
        caller.msg(f"|wYou remove {item.key}.|n")
        if room:
            room.msg_contents(
                f"|x{caller_name} removes {item.key}.|n",
                exclude=caller,
            )


# ---------------------------------------------------------------------------
# CmdAttachLeash — attach a leash to a collar-wearing target
# ---------------------------------------------------------------------------

class CmdAttachLeash(Command):
    """
    Attach a leash from your inventory to a collar-wearing character.

    Usage:
      attach leash <target>
      attach <leash_name> <target>

    The target must be wearing a collar. You must be in the same room.
    Once attached, the target is led by you — they receive tug notifications
    when you move.

    Use 'detach leash' or 'unlead' to release them.
    """

    key     = "attach"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        args   = self.args.strip()
        room   = caller.location

        if not args:
            caller.msg("|xUsage: attach leash <target>|n")
            return

        from typeclasses.collar_item import LeashItem

        # Parse: "leash <target>" or "<leash_name> <target>"
        parts = args.split(None, 1)
        if parts[0].lower() == "leash":
            leash_name  = "leash"
            target_name = parts[1].strip() if len(parts) > 1 else ""
        else:
            leash_name  = parts[0]
            target_name = parts[1].strip() if len(parts) > 1 else ""

        if not target_name:
            caller.msg("|xUsage: attach leash <target>|n")
            return

        # Find leash in inventory
        leashes = [
            obj for obj in caller.contents
            if isinstance(obj, LeashItem) and not obj.db.is_attached
        ]
        if not leashes:
            caller.msg("|xYou don't have a free leash to attach.|n")
            return

        if leash_name.lower() != "leash":
            leash = next(
                (l for l in leashes if leash_name.lower() in l.key.lower()), None
            )
            if not leash:
                caller.msg(f"|xNo free leash matching '{leash_name}'.|n")
                return
        else:
            leash = leashes[0]

        target = caller.search(target_name, location=room)
        if not target:
            return

        ok, reason = leash.attach(caller, target)
        if not ok:
            caller.msg(f"|x{reason}|n")
            return

        # Apply binding effects to the leashed character
        try:
            from world.binding_effects import apply_effects
            apply_effects(target, leash)
        except Exception:
            pass

        caller_name = caller.db.rp_name or caller.name
        target_name_disp = target.db.rp_name or target.name
        caller.msg(f"|wYou attach {leash.key} to {target_name_disp}'s collar.|n")
        target.msg(f"|x{caller_name} attaches {leash.key} to your collar.|n")
        if room:
            room.msg_contents(
                f"|x{caller_name} attaches a leash to {target_name_disp}'s collar.|n",
                exclude=[caller, target],
            )


# ---------------------------------------------------------------------------
# CmdDetachLeash — detach the leash you are holding
# ---------------------------------------------------------------------------

class CmdDetachLeash(Command):
    """
    Detach the leash you are currently holding.

    Usage:
      detach leash
      detach <leash_name>

    Releases the lead connection. Either the holder or the target
    can use 'unlead' to break the lead connection instead.
    """

    key     = "detach"
    locks   = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        args   = self.args.strip()
        room   = caller.location

        from typeclasses.collar_item import LeashItem

        leashes = [
            obj for obj in caller.contents
            if isinstance(obj, LeashItem) and obj.db.is_attached
               and obj.db.holder == caller
        ]
        if not leashes:
            caller.msg("|xYou're not holding an attached leash.|n")
            return

        if args and args.lower() != "leash":
            leash = next(
                (l for l in leashes if args.lower() in l.key.lower()), None
            )
            if not leash:
                caller.msg(f"|xNo attached leash matching '{args}'.|n")
                return
        else:
            leash = leashes[0]

        target = leash.db.target
        ok, reason = leash.detach()
        if not ok:
            caller.msg(f"|x{reason}|n")
            return

        # Remove binding effects from leashed character
        if target:
            try:
                from world.binding_effects import remove_effects
                remove_effects(target, leash)
            except Exception:
                pass

        caller_name = caller.db.rp_name or caller.name
        caller.msg(f"|wYou detach {leash.key}.|n")
        if target:
            target.msg(f"|x{caller_name} detaches the leash.|n")
        if room:
            room.msg_contents(
                f"|x{caller_name} detaches a leash.|n",
                exclude=[caller, target] if target else [caller],
            )


# ---------------------------------------------------------------------------
# CmdItemDesc — set and lock item descriptions
# ---------------------------------------------------------------------------

class CmdItemDesc(MuxCommand):
    """
    Set or lock the description on a wearable, plug, or collar item.

    Usage:
      itemdesc <item> = <text>       — set the description
      itemdesc/lock <item>           — permanently lock the description
      itemdesc <item>                — view current description

    Once locked, the description cannot be changed by anyone.
    The lock is permanent — use it when you're happy with the final text.

    For collars and plugs, the description is appended to or shown
    alongside the zone it's installed on.

    Tokens work in item descriptions:
      {n}  the wearer's display name
      {np} the wearer's possessive pronoun
    """

    key     = "itemdesc"
    locks   = "cmd:all()"
    help_category = "Character"
    switch_options = ("lock",)

    def func(self):
        caller   = self.caller
        args     = self.args.strip()
        switches = self.switches

        if not args:
            caller.msg("|xUsage: itemdesc <item> = <text>  |  itemdesc/lock <item>|n")
            return

        if "=" in args and "lock" not in switches:
            item_name, _, desc = args.partition("=")
            item_name = item_name.strip()
            desc      = desc.strip()
            item = caller.search(item_name, location=caller)
            if not item:
                return
            if not hasattr(item, "set_player_desc"):
                caller.msg(f"|x{item.key} doesn't support custom descriptions.|n")
                return
            ok, reason = item.set_player_desc(desc)
            if not ok:
                caller.msg(f"|x{reason}|n")
            else:
                caller.msg(f"|wDescription set on {item.key}:|n {desc}")
        elif "lock" in switches:
            item = caller.search(args, location=caller)
            if not item:
                return
            if not hasattr(item, "set_player_desc"):
                caller.msg(f"|x{item.key} doesn't support custom descriptions.|n")
                return
            if item.db.desc_locked:
                caller.msg(f"|x{item.key}'s description is already locked.|n")
                return
            current_desc = item.db.player_desc or item.db.desc or ""
            if not current_desc:
                caller.msg(f"|xSet a description first before locking.|n")
                return
            ok, reason = item.set_player_desc(current_desc, locked=True, creator=caller)
            if not ok:
                caller.msg(f"|x{reason}|n")
            else:
                caller.msg(
                    f"|wDescription on {item.key} is now permanently locked:|n\n"
                    f"|x{current_desc}|n"
                )
        else:
            item = caller.search(args, location=caller)
            if not item:
                return
            desc   = getattr(item.db, "player_desc", "") or getattr(item.db, "desc", "")
            locked = getattr(item.db, "desc_locked", False)
            lock_str = " |r[LOCKED]|n" if locked else " |x[unlocked]|n"
            caller.msg(f"|w{item.key}|n{lock_str}\n{desc or '|x(no description set)|n'}")


# ---------------------------------------------------------------------------
# CmdCamouflage — manage outfit camouflage on your character
# ---------------------------------------------------------------------------

class CmdCamouflage(Command):
    """
    Set or clear an outfit camouflage description on your character.

    When active, other players see the camouflage desc instead of your
    real zone descriptions. You always see your own real zones.
    Interactions (emotes, penetrate, etc.) still work normally.

    Usage:
      camouflage                     — show current camouflage
      camouflage = <description>     — set camouflage desc
      camouflage/clear               — remove camouflage

    This is automatically set when you wear a WearableItem that has a
    camouflage_desc — just wearing/removing the item handles it.
    Use this command for manual/standalone camouflage control.
    """

    key     = "camouflage"
    locks   = "cmd:all()"
    help_category = "Character"

    def func(self):
        caller = self.caller
        args   = self.args.strip()

        if "/clear" in self.raw_string or "clear" in (self.switches or []):
            caller.db.outfit_camouflage = ""
            caller.msg("|wCamouflage cleared. Others see your real description.|n")
            return

        if "=" in args:
            _, _, desc = args.partition("=")
            desc = desc.strip()
            if not desc:
                caller.db.outfit_camouflage = ""
                caller.msg("|wCamouflage cleared.|n")
            else:
                caller.db.outfit_camouflage = desc
                caller.msg(f"|wCamouflage active:|n {desc}")
            return

        current = getattr(caller.db, "outfit_camouflage", "") or ""
        if current:
            caller.msg(f"|wCamouflage active:|n {current}")
        else:
            caller.msg("|xNo camouflage active. Use: camouflage = <description>|n")


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

ALL_ITEM_CMDS = [
    CmdInsert,
    CmdUnplug,
    CmdWear,
    CmdRemoveItem,
    CmdAttachLeash,
    CmdDetachLeash,
    CmdItemDesc,
    CmdCamouflage,
]
