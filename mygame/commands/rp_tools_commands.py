"""
commands/rp_tools_commands.py

Freeform RP scene and body tools for Re:Void.

Commands:
    flock <target> <zone>            -- lock a zone covering on target; gives
                                        caller a key object in their inventory
    flock <exit name>                -- flavor-lock an exit; gives caller a key
    funlock <target> <zone>          -- remove a zone flock (needs matching key)
    funlock <exit name>              -- remove an exit flock (needs matching key)
    restrain <name> <zone> = <desc>  -- apply a restraint to a zone
    unrestrain <name> <zone>         -- remove a restraint
    restraints [name]                -- list restraints on self or another

    lead <name>                      -- establish a narrative lead connection
    unlead                           -- break the lead connection (either end)

    prop create <name> = <desc>      -- spawn a temporary scene prop in the room
    prop drop <name>                 -- remove a prop you created
    prop/list                        -- list props in the current room

    detail <keyword> = <text>        -- add a lookable room detail
    detail/clear <keyword>           -- remove a room detail
    detail/list                      -- list all active room details

    stage <text>                     -- set an atmospheric overlay on the room
    stage/clear                      -- clear the stage overlay

    mark <target> <zone> = <desc>    -- apply a persistent marking to a character
    mark/remove <target> <zone> <#>  -- remove a specific marking
    mark/list <target>               -- list all markings on a character

Notes:
    - flock on a zone requires the zone to already have a covering (wear/insert first).
    - flock on an exit creates a flavor lock; traversal is blocked until unlocked.
    - restrain targeting legs / ankles / feet / thighs mechanically blocks movement.
    - restrain requires target.db.consent_flags["restraint"] == True.
    - lead requires target.db.consent_flags["lead_follow"] == True.
    - Props are cleared automatically when scene/end is called.
    - Details and stage persist until manually cleared or scene/end.
    - Markings are persistent and survive scene end and logout.
"""

import uuid as _uuid
from evennia.commands.default.muxcommand import MuxCommand
from evennia import create_object

# Zones whose restraint mechanically blocks movement
MOVEMENT_ZONES = {"legs", "ankles", "feet", "thighs"}


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _name(char):
    return char.db.rp_name or char.name


def _make_key_id():
    return _uuid.uuid4().hex[:12]


def _find_char_in_room(caller, target_name):
    """Search for a character in the caller's current room."""
    results = caller.search(
        target_name,
        location=caller.location,
        quiet=True,
    )
    if not results:
        return None
    return results[0] if isinstance(results, list) else results


def _find_exit(room, exit_name):
    """Find an exit in a room by key or alias."""
    if not room:
        return None
    name_lower = exit_name.lower()
    for exit_obj in room.exits:
        if exit_obj.key.lower() == name_lower:
            return exit_obj
        aliases = exit_obj.aliases.all() or []
        if name_lower in [a.lower() for a in aliases]:
            return exit_obj
    return None


def _find_key_in_inventory(char, key_id):
    """Return a freeform key object from char's inventory matching key_id."""
    for obj in char.contents:
        if obj.db.is_freeform_key and obj.db.key_id == key_id:
            return obj
    return None


def _create_key(caller, label, key_id, locked_on, locked_zone):
    """
    Spawn a key object in the caller's inventory.

    Args:
        caller: Character receiving the key.
        label (str): Short label for the item being locked.
        key_id (str): Unique ID matching the lock.
        locked_on (str): Name of the target the lock is on.
        locked_zone (str): Zone or exit name.

    Returns:
        The created key object.
    """
    key_name = f"small key ({label[:28]})"
    key_obj = create_object(
        "typeclasses.objects.Object",
        key=key_name,
        location=caller,
    )
    key_obj.db.is_freeform_key = True
    key_obj.db.key_id = key_id
    key_obj.db.locked_on = locked_on
    key_obj.db.locked_zone = locked_zone
    key_obj.db.desc = (
        f"A small key. It fits the lock on "
        f"{locked_on}'s {locked_zone}."
    )
    return key_obj


# -------------------------------------------------------------------
# CmdFlock
# -------------------------------------------------------------------

class CmdFlock(MuxCommand):
    """
    Lock a zone covering or an exit with a freeform lock.

    For zones: the target's zone must already be covered (use 'wear'
    first). The lock prevents the covering from being removed until
    unlocked with the matching key, which goes into your inventory.

    For exits: places a lock on the exit. The exit cannot be traversed
    until the key holder uses 'funlock' on it.

    Usage:
      flock <name> <zone>       -- lock a zone covering on a character
      flock <exit name>         -- lock an exit in this room

    Examples:
      flock Seraphine neck      -- lock her collar in place
      flock north               -- lock the north exit

    The key produced is a physical inventory item. It can be given,
    dropped, or destroyed. Admins can always bypass locks.

    The locked state is preserved if the item is saved to wardrobe.

    See also: funlock, wear, wardrobe
    """

    key = "flock"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            self.msg(
                "Usage:\n"
                "  flock <name> <zone>   — lock a zone covering\n"
                "  flock <exit>          — lock an exit"
            )
            return

        parts = args.split(None, 1)

        if len(parts) == 2:
            self._zone_flock(caller, parts[0], parts[1])
        else:
            # One arg — try exit first, then error
            exit_obj = _find_exit(caller.location, parts[0])
            if exit_obj:
                self._exit_flock(caller, exit_obj)
            else:
                self.msg(
                    f"No exit named '{parts[0]}' here.\n"
                    f"To lock a zone: flock <name> <zone>"
                )

    def _zone_flock(self, caller, target_name, zone_name):
        target = _find_char_in_room(caller, target_name)
        if not target:
            self.msg(f"You don't see '{target_name}' here.")
            return

        zone_name = zone_name.lower().replace(" ", "_")
        zones = target._get_zones()

        if zone_name not in zones:
            self.msg(
                f"{_name(target)} has no zone named '{zone_name}'."
            )
            return

        covered = zones[zone_name].get("covered_by")
        if not covered:
            self.msg(
                f"Zone '{zone_name}' on {_name(target)} isn't covered. "
                f"Something must be worn there first."
            )
            return

        if covered.get("locked"):
            self.msg(
                f"Zone '{zone_name}' on {_name(target)} "
                f"is already locked."
            )
            return

        key_id = _make_key_id()
        covered["locked"] = True
        covered["key_id"] = key_id
        zones[zone_name]["covered_by"] = covered
        target.db.zones = zones

        worn_label = covered.get("worn_desc", covered.get("desc", zone_name))
        key_obj = _create_key(
            caller, worn_label, key_id, _name(target), zone_name
        )

        cname = _name(caller)
        tname = _name(target)

        caller.msg(
            f"You lock {tname}'s {zone_name} covering in place.\n"
            f"|x[Key: {key_obj.key} — now in your inventory]|n"
        )
        target.msg(
            f"{cname} locks your {zone_name} covering in place. "
            f"It cannot be removed without the key."
        )
        if caller.location:
            caller.location.msg_contents(
                f"|x{cname} secures something on {tname}.|n",
                exclude=[caller, target],
            )

    def _exit_flock(self, caller, exit_obj):
        if exit_obj.db.flock and exit_obj.db.flock.get("locked"):
            self.msg(f"The exit '{exit_obj.key}' is already locked.")
            return

        key_id = _make_key_id()
        exit_obj.db.flock = {
            "locked": True,
            "key_id": key_id,
        }

        key_obj = _create_key(
            caller,
            exit_obj.key,
            key_id,
            "the exit",
            exit_obj.key,
        )

        cname = _name(caller)
        caller.msg(
            f"You lock the {exit_obj.key} exit.\n"
            f"|x[Key: {key_obj.key} — now in your inventory]|n"
        )
        if caller.location:
            caller.location.msg_contents(
                f"|x{cname} locks the {exit_obj.key} exit.|n",
                exclude=[caller],
            )


# -------------------------------------------------------------------
# CmdFunlock
# -------------------------------------------------------------------

class CmdFunlock(MuxCommand):
    """
    Unlock a freeform lock on a zone covering or an exit.

    You must be holding the matching key in your inventory.
    Admins and superusers can unlock without a key.
    The key is consumed when used.

    Usage:
      funlock <name> <zone>     -- unlock a zone covering
      funlock <exit name>       -- unlock an exit

    Examples:
      funlock Seraphine neck
      funlock north

    See also: flock, wear, wardrobe
    """

    key = "funlock"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            self.msg(
                "Usage:\n"
                "  funlock <name> <zone>   — unlock a zone covering\n"
                "  funlock <exit>          — unlock an exit"
            )
            return

        parts = args.split(None, 1)
        is_admin = (
            caller.is_superuser
            or caller.check_permstring("Admin")
        )

        if len(parts) == 2:
            self._zone_funlock(caller, parts[0], parts[1], is_admin)
        else:
            exit_obj = _find_exit(caller.location, parts[0])
            if exit_obj:
                self._exit_funlock(caller, exit_obj, is_admin)
            else:
                self.msg(
                    f"No exit named '{parts[0]}' here.\n"
                    f"To unlock a zone: funlock <name> <zone>"
                )

    def _zone_funlock(self, caller, target_name, zone_name, is_admin):
        target = _find_char_in_room(caller, target_name)
        if not target:
            self.msg(f"You don't see '{target_name}' here.")
            return

        zone_name = zone_name.lower().replace(" ", "_")
        zones = target._get_zones()

        if zone_name not in zones:
            self.msg(
                f"{_name(target)} has no zone named '{zone_name}'."
            )
            return

        covered = zones[zone_name].get("covered_by")
        if not covered or not covered.get("locked"):
            self.msg(
                f"Zone '{zone_name}' on {_name(target)} "
                f"isn't locked."
            )
            return

        key_id = covered.get("key_id")
        key_obj = None

        if not is_admin:
            key_obj = _find_key_in_inventory(caller, key_id)
            if not key_obj:
                self.msg(
                    f"You don't have the key for "
                    f"{_name(target)}'s '{zone_name}' lock."
                )
                return

        covered["locked"] = False
        covered.pop("key_id", None)
        zones[zone_name]["covered_by"] = covered
        target.db.zones = zones

        if key_obj:
            key_obj.delete()

        cname = _name(caller)
        tname = _name(target)

        caller.msg(f"You unlock {tname}'s {zone_name} covering.")
        if caller != target:
            target.msg(f"{cname} unlocks your {zone_name} covering.")
        if caller.location:
            caller.location.msg_contents(
                f"|x{cname} unlocks something on {tname}.|n",
                exclude=[caller, target],
            )

    def _exit_funlock(self, caller, exit_obj, is_admin):
        flock = exit_obj.db.flock or {}
        if not flock.get("locked"):
            self.msg(f"The exit '{exit_obj.key}' isn't locked.")
            return

        key_id = flock.get("key_id")
        key_obj = None

        if not is_admin:
            key_obj = _find_key_in_inventory(caller, key_id)
            if not key_obj:
                self.msg(
                    f"You don't have the key for the "
                    f"'{exit_obj.key}' lock."
                )
                return

        exit_obj.db.flock = {"locked": False}

        if key_obj:
            key_obj.delete()

        cname = _name(caller)
        caller.msg(f"You unlock the {exit_obj.key} exit.")
        if caller.location:
            caller.location.msg_contents(
                f"|x{cname} unlocks the {exit_obj.key} exit.|n",
                exclude=[caller],
            )


# -------------------------------------------------------------------
# CmdRestrain
# -------------------------------------------------------------------

class CmdRestrain(MuxCommand):
    """
    Apply a restraint to a zone on a character.

    Restraints are physical descriptors tied to a body zone. Targeting
    movement zones (legs, ankles, feet, thighs) mechanically prevents
    the restrained character from moving rooms until unrestrained.

    Requires the target to have their 'restraint' consent flag enabled.
    The target enables it with:  consent give restraint

    Usage:
      restrain <name> <zone> = <description>

    Examples:
      restrain Seraphine wrists = silk cord, wound twice and knotted
      restrain Ara ankles = leather cuffs connected by a short chain

    The restraint is visible to anyone who examines the character.
    Remove with: unrestrain <name> <zone>

    See also: unrestrain, restraints, flock, consent
    """

    key = "restrain"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller

        if not self.lhs or not self.rhs:
            self.msg(
                "Usage: restrain <name> <zone> = <description>\n"
                "Example: restrain Ara wrists = silk cord, wound twice"
            )
            return

        left_parts = self.lhs.strip().split(None, 1)
        if len(left_parts) < 2:
            self.msg(
                "Usage: restrain <name> <zone> = <description>"
            )
            return

        target_name = left_parts[0]
        zone_name = left_parts[1].lower().replace(" ", "_")
        desc = self.rhs.strip()

        if not desc:
            self.msg("Restraint description cannot be empty.")
            return

        target = _find_char_in_room(caller, target_name)
        if not target:
            self.msg(f"You don't see '{target_name}' here.")
            return

        if target == caller:
            self.msg(
                "Use 'restrain' on another character. "
                "Self-restraint isn't tracked this way."
            )
            return

        # Consent check
        consent_flags = target.db.consent_flags or {}
        if not consent_flags.get("restraint", False):
            tname = _name(target)
            self.msg(
                f"{tname} has not opened restraint content.\n"
                f"|x({tname} needs to run: consent give restraint)|n"
            )
            return

        # Warn but allow freeform zones not in the zone dict
        zones = target._get_zones()
        if zone_name not in zones:
            self.msg(
                f"|x[Note: {_name(target)} has no defined zone "
                f"'{zone_name}'. Proceeding as freeform restraint.]|n"
            )

        restraints = target.db.restraints or {}
        if zone_name in restraints:
            self.msg(
                f"Zone '{zone_name}' on {_name(target)} is already "
                f"restrained. Remove it first: "
                f"unrestrain {_name(target)} {zone_name}"
            )
            return

        blocks = zone_name in MOVEMENT_ZONES

        restraints[zone_name] = {
            "desc":            desc,
            "set_by_id":       caller.id,
            "set_by_name":     _name(caller),
            "removable_by":    [caller.id],
            "blocks_movement": blocks,
        }
        target.db.restraints = restraints

        cname = _name(caller)
        tname = _name(target)
        block_note = " |y[movement restricted]|n" if blocks else ""

        caller.msg(
            f"You restrain {tname}'s {zone_name}: {desc}{block_note}"
        )
        target.msg(
            f"{cname} restrains your {zone_name}: {desc}{block_note}"
        )
        if caller.location:
            caller.location.msg_contents(
                f"|x{cname} restrains {tname}'s {zone_name}.|n",
                exclude=[caller, target],
            )


# -------------------------------------------------------------------
# CmdUnrestrain
# -------------------------------------------------------------------

class CmdUnrestrain(MuxCommand):
    """
    Remove a restraint from a character's zone.

    Only the character who placed the restraint, or an admin,
    can remove it. The restrained character cannot remove their
    own restraints.

    Usage:
      unrestrain <name> <zone>

    Examples:
      unrestrain Seraphine wrists
      unrestrain Ara ankles

    See also: restrain, restraints
    """

    key = "unrestrain"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if not args:
            self.msg("Usage: unrestrain <name> <zone>")
            return

        parts = args.split(None, 1)
        if len(parts) < 2:
            self.msg("Usage: unrestrain <name> <zone>")
            return

        target_name = parts[0]
        zone_name = parts[1].lower().replace(" ", "_")

        target = _find_char_in_room(caller, target_name)
        if not target:
            self.msg(f"You don't see '{target_name}' here.")
            return

        restraints = target.db.restraints or {}
        if zone_name not in restraints:
            self.msg(
                f"{_name(target)} has no restraint on '{zone_name}'."
            )
            return

        entry = restraints[zone_name]
        is_admin = (
            caller.is_superuser
            or caller.check_permstring("Admin")
        )
        removable_by = entry.get("removable_by", [])

        if not is_admin and caller.id not in removable_by:
            self.msg(
                f"You didn't place that restraint. "
                f"Only the one who bound {_name(target)} can release it."
            )
            return

        del restraints[zone_name]
        target.db.restraints = restraints

        cname = _name(caller)
        tname = _name(target)

        caller.msg(f"You release {tname}'s {zone_name} restraint.")
        if caller != target:
            target.msg(
                f"{cname} releases your {zone_name} restraint."
            )
        if caller.location:
            caller.location.msg_contents(
                f"|x{cname} releases a restraint on {tname}.|n",
                exclude=[caller, target],
            )


# -------------------------------------------------------------------
# CmdRestraints
# -------------------------------------------------------------------

class CmdRestraints(MuxCommand):
    """
    View restraints on yourself or another character.

    Usage:
      restraints              -- see your own restraints
      restraints <name>       -- see another's (must be in room)

    See also: restrain, unrestrain
    """

    key = "restraints"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller

        if self.args.strip():
            target = _find_char_in_room(caller, self.args.strip())
            if not target:
                self.msg(
                    f"You don't see '{self.args.strip()}' here."
                )
                return
        else:
            target = caller

        restraints = target.db.restraints or {}
        tname = _name(target)
        sep = f"|w{'─' * 40}|n"

        if not restraints:
            if target == caller:
                self.msg("You have no active restraints.")
            else:
                self.msg(f"{tname} has no active restraints.")
            return

        lines = [f"\n{sep}", f"|wRestraints on {tname}|n", sep]

        for zone_name, data in sorted(restraints.items()):
            desc = data.get("desc", "")
            set_by = data.get("set_by_name", "unknown")
            blocks = data.get("blocks_movement", False)
            block_tag = " |y[movement blocked]|n" if blocks else ""
            lines.append(
                f"  |w{zone_name}|n{block_tag}\n"
                f"    {desc}\n"
                f"    |x[placed by {set_by}]|n"
            )

        lines.append(sep)
        self.msg("\n".join(lines))


# -------------------------------------------------------------------
# CmdLead
# -------------------------------------------------------------------

class CmdLead(MuxCommand):
    """
    Establish a narrative lead connection with another character.

    The lead is a physical or narrative link — a leash, a hand, a cord.
    When you move, your led character receives a tug notification. The
    lead persists until broken with 'unlead'. Either party can break it.

    Requires the target to have their 'lead_follow' consent flag on.
    The target enables it with:  consent give lead_follow

    Usage:
      lead <name>
      lead <name> = <flavor description>

    Examples:
      lead Seraphine
      lead Seraphine = a braided silk lead clipped to her collar

    See also: unlead, restrain, consent
    """

    key = "lead"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller

        if not self.args.strip():
            self.msg(
                "Usage: lead <name>\n"
                "       lead <name> = <flavor description>"
            )
            return

        if "=" in self.args:
            target_name, _, flavor = self.args.partition("=")
            target_name = target_name.strip()
            flavor = flavor.strip()
        else:
            target_name = self.args.strip()
            flavor = ""

        target = _find_char_in_room(caller, target_name)
        if not target:
            self.msg(f"You don't see '{target_name}' here.")
            return

        if target == caller:
            self.msg("You can't lead yourself.")
            return

        consent_flags = target.db.consent_flags or {}
        if not consent_flags.get("lead_follow", False):
            tname = _name(target)
            self.msg(
                f"{tname} has not opened lead/follow content.\n"
                f"|x({tname} needs to run: consent give lead_follow)|n"
            )
            return

        if caller.db.leading:
            self.msg(
                "You're already leading someone. "
                "Use 'unlead' to release them first."
            )
            return
        if target.db.led_by:
            self.msg(
                f"{_name(target)} is already being led by someone."
            )
            return

        caller.db.leading = target.id
        target.db.led_by = caller.id
        caller.db.lead_desc = flavor
        target.db.lead_desc = flavor

        cname = _name(caller)
        tname = _name(target)
        flavor_str = f" — {flavor}" if flavor else ""

        caller.msg(f"You take the lead with {tname}{flavor_str}.")
        target.msg(f"{cname} takes your lead{flavor_str}.")
        if caller.location:
            caller.location.msg_contents(
                f"|x{cname} takes {tname}'s lead.|n",
                exclude=[caller, target],
            )


# -------------------------------------------------------------------
# CmdUnlead
# -------------------------------------------------------------------

class CmdUnlead(MuxCommand):
    """
    Release a lead connection.

    Either the leader or the led character can break the lead.

    Usage:
      unlead

    See also: lead, restrain
    """

    key = "unlead"
    aliases = ["unleash"]
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller
        leading_id = caller.db.leading
        led_by_id = caller.db.led_by

        if not leading_id and not led_by_id:
            self.msg("You aren't in a lead connection.")
            return

        cname = _name(caller)

        if leading_id:
            # Caller is the leader — release the follower
            try:
                from evennia import search_object
                results = search_object(f"#{leading_id}")
                if results:
                    follower = results[0]
                    follower.db.led_by = None
                    follower.db.lead_desc = ""
                    follower.msg(f"{cname} releases your lead.")
                    fname = _name(follower)
                    if caller.location:
                        caller.location.msg_contents(
                            f"|x{cname} releases {fname}'s lead.|n",
                            exclude=[caller, follower],
                        )
            except Exception:
                pass
            caller.db.leading = None
            caller.db.lead_desc = ""
            self.msg("You release the lead.")

        else:
            # Caller is the follower — slip free
            try:
                from evennia import search_object
                results = search_object(f"#{led_by_id}")
                if results:
                    leader = results[0]
                    leader.db.leading = None
                    leader.db.lead_desc = ""
                    lname = _name(leader)
                    leader.msg(f"{cname} breaks free of your lead.")
                    if caller.location:
                        caller.location.msg_contents(
                            f"|x{cname} slips free of {lname}'s lead.|n",
                            exclude=[caller, leader],
                        )
            except Exception:
                pass
            caller.db.led_by = None
            caller.db.lead_desc = ""
            self.msg("You slip free of the lead.")


# -------------------------------------------------------------------
# CmdProp
# -------------------------------------------------------------------

class CmdProp(MuxCommand):
    """
    Manage scene props in the current room.

    Props are objects placed in the room for RP dressing. By default
    they are temporary and cleared automatically when scene/end is
    called. Pin a prop to make it persist across scene resets.

    Usage:
      prop create <name> = <description>   -- spawn a temporary prop
      prop drop <name>                     -- remove one of your props
      prop/pin <name>                      -- make a prop persistent
      prop/unpin <name>                    -- return a prop to temporary
      prop/list                            -- list all props in the room

    Examples:
      prop create letter = a folded note, sealed with dark wax
      prop create candle = a half-burned candle in a brass holder
      prop/pin candle                      -- candle survives scene/end
      prop drop letter

    Props you create are tied to you. Admins can drop any prop.
    Pinned props are marked with [pinned] in the list.

    See also: detail, stage, scene
    """

    key = "prop"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            self.msg("You need to be somewhere to manage props.")
            return

        if "list" in self.switches:
            self._prop_list(caller, room)
            return

        if "pin" in self.switches:
            self._prop_pin(caller, room, self.args.strip(), persistent=True)
            return

        if "unpin" in self.switches:
            self._prop_pin(caller, room, self.args.strip(), persistent=False)
            return

        args = self.args.strip()
        if not args:
            self.msg(
                "Usage:\n"
                "  prop create <name> = <desc>\n"
                "  prop drop <name>\n"
                "  prop/pin <name>\n"
                "  prop/unpin <name>\n"
                "  prop/list"
            )
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "create":
            self._prop_create(caller, room, rest)
        elif subcmd == "drop":
            self._prop_drop(caller, room, rest)
        else:
            self.msg(
                f"Unknown subcommand '{subcmd}'.\n"
                "Use: prop create / prop drop / prop/pin / prop/list"
            )

    def _prop_create(self, caller, room, args):
        if "=" not in args:
            self.msg("Usage: prop create <name> = <description>")
            return

        prop_name, _, desc = args.partition("=")
        prop_name = prop_name.strip()
        desc = desc.strip()

        if not prop_name or not desc:
            self.msg("Both a name and description are required.")
            return

        if len(prop_name) > 60:
            self.msg("Prop name too long. Keep it under 60 characters.")
            return

        prop = create_object(
            "typeclasses.objects.Object",
            key=prop_name,
            location=room,
        )
        prop.db.desc = desc
        prop.db.is_scene_prop = True
        prop.db.prop_room_id = room.id
        prop.db.prop_owner_id = caller.id

        cname = _name(caller)
        caller.msg(f"You place {prop_name} in the scene.")
        room.msg_contents(
            f"|x{cname} places {prop_name} here.|n",
            exclude=[caller],
        )

    def _prop_drop(self, caller, room, prop_name):
        if not prop_name:
            self.msg("Drop which prop? Usage: prop drop <name>")
            return

        is_admin = (
            caller.is_superuser
            or caller.check_permstring("Admin")
        )

        target_prop = None
        name_lower = prop_name.lower()
        for obj in room.contents:
            if (
                obj.db.is_scene_prop
                and obj.key.lower() == name_lower
                and (is_admin or obj.db.prop_owner_id == caller.id)
            ):
                target_prop = obj
                break

        if not target_prop:
            self.msg(
                f"No prop named '{prop_name}' here that you can remove."
            )
            return

        cname = _name(caller)
        prop_key = target_prop.key
        target_prop.delete()
        caller.msg(f"You remove {prop_key} from the scene.")
        room.msg_contents(
            f"|x{cname} removes {prop_key} from the scene.|n",
            exclude=[caller],
        )

    def _prop_pin(self, caller, room, prop_name, persistent):
        if not prop_name:
            action = "pin" if persistent else "unpin"
            self.msg(f"Usage: prop/{action} <name>")
            return

        is_admin = (
            caller.is_superuser
            or caller.check_permstring("Admin")
        )
        name_lower = prop_name.lower()
        target_prop = None
        for obj in room.contents:
            if (
                obj.db.is_scene_prop
                and obj.key.lower() == name_lower
                and (is_admin or obj.db.prop_owner_id == caller.id)
            ):
                target_prop = obj
                break

        if not target_prop:
            self.msg(
                f"No prop named '{prop_name}' here that you can modify."
            )
            return

        target_prop.db.prop_persistent = persistent
        state = "|gpinned|n" if persistent else "|xtemporary|n"
        self.msg(
            f"{target_prop.key} is now {state}. "
            + (
                "It will survive scene/end."
                if persistent
                else "It will be cleared by scene/end."
            )
        )

    def _prop_list(self, caller, room):
        props = [obj for obj in room.contents if obj.db.is_scene_prop]

        if not props:
            self.msg("There are no scene props here.")
            return

        sep = f"|w{'─' * 40}|n"
        lines = [f"\n{sep}", "|wScene props:|n", sep]
        for prop in props:
            desc = prop.db.desc or "(no description)"
            pinned = prop.db.prop_persistent
            pin_tag = " |g[pinned]|n" if pinned else ""
            lines.append(
                f"  |w{prop.key}|n{pin_tag}\n"
                f"    {desc[:80]}{'...' if len(desc) > 80 else ''}"
            )
        lines.append(sep)
        self.msg("\n".join(lines))


# -------------------------------------------------------------------
# CmdDetail
# -------------------------------------------------------------------

class CmdDetail(MuxCommand):
    """
    Add lookable details to the current room.

    Details are short descriptions tied to a keyword. Anyone in
    the room can 'look at <keyword>' to read them. Useful for
    props, environmental dressing, or scene flavor.

    Usage:
      detail <keyword> = <text>       -- add or update a detail
      detail/clear <keyword>          -- remove a detail
      detail/list                     -- list all active details

    Examples:
      detail mirror = A tall standing mirror in a tarnished frame.
        The glass is slightly warped.
      detail/clear mirror
      detail/list

    Keywords are case-insensitive. Details persist until cleared
    or until scene/end is called.

    See also: prop, stage, scene
    """

    key = "detail"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            self.msg("You need to be somewhere to set details.")
            return

        if "list" in self.switches:
            details = room.db.scene_details or {}
            if not details:
                self.msg("No details are set in this room.")
                return
            sep = f"|w{'─' * 40}|n"
            lines = [f"\n{sep}", "|wRoom details:|n", sep]
            for kw, text in sorted(details.items()):
                lines.append(
                    f"  |w{kw}|n\n"
                    f"    {text[:80]}{'...' if len(text) > 80 else ''}"
                )
            lines.append(sep)
            self.msg("\n".join(lines))
            return

        if "clear" in self.switches:
            if not self.args.strip():
                self.msg(
                    "Clear which detail? "
                    "Usage: detail/clear <keyword>"
                )
                return
            kw = self.args.strip().lower()
            details = room.db.scene_details or {}
            if kw not in details:
                self.msg(f"No detail named '{kw}' here.")
                return
            del details[kw]
            room.db.scene_details = details
            self.msg(f"Detail '{kw}' removed.")
            return

        if "=" not in self.args:
            self.msg(
                "Usage: detail <keyword> = <text>\n"
                "       detail/clear <keyword>\n"
                "       detail/list"
            )
            return

        kw, _, text = self.args.partition("=")
        kw = kw.strip().lower()
        text = text.strip()

        if not kw or not text:
            self.msg("Both a keyword and description are required.")
            return

        details = room.db.scene_details or {}
        details[kw] = text
        room.db.scene_details = details
        self.msg(
            f"Detail '{kw}' set.\n"
            f"|x[Others can: look at {kw}]|n"
        )


# -------------------------------------------------------------------
# CmdStage
# -------------------------------------------------------------------

class CmdStage(MuxCommand):
    """
    Set an atmospheric overlay description for the room.

    The stage text appears appended to the room description during
    the current scene. Use it to paint the scene's feeling without
    editing the permanent room description.

    Usage:
      stage <text>            -- set or replace the stage overlay
      stage/clear             -- remove the stage overlay
      stage                   -- see the current stage text

    Examples:
      stage The room smells of old smoke and something sweeter beneath
        it. The light is wrong — too still, too quiet.
      stage/clear

    See also: detail, prop, scene
    """

    key = "stage"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            self.msg("You need to be somewhere to set a stage.")
            return

        if "clear" in self.switches:
            room.db.scene_stage_desc = ""
            cname = _name(caller)
            room.msg_contents(f"|x[ {cname} clears the stage. ]|n")
            return

        if not self.args.strip():
            current = room.db.scene_stage_desc or "(not set)"
            self.msg(f"Current stage:\n\n{current}")
            return

        room.db.scene_stage_desc = self.args.strip()
        cname = _name(caller)
        room.msg_contents(f"|x[ Stage set by {cname}. ]|n")
        self.msg("Stage text set.")


# -------------------------------------------------------------------
# CmdMark
# -------------------------------------------------------------------

class CmdMark(MuxCommand):
    """
    Apply a persistent marking to a character.

    Markings are permanent until removed — they survive scene end,
    logout, and room changes. They appear when someone examines
    the target closely.

    Usage:
      mark <name> <zone> = <description>     -- add a marking
      mark/remove <name> <zone> <#>          -- remove by number
      mark/list <name>                       -- list all markings

    Examples:
      mark Seraphine neck = a thin scar, pale and deliberate,
        running from just below the jaw to the collarbone
      mark/remove Seraphine neck 1
      mark/list Seraphine

    Only the character who placed a marking can remove it.
    Admins can remove any marking.

    See also: zone, flock, restrain
    """

    key = "mark"
    locks = "cmd:all()"
    help_category = "RP Tools"

    def func(self):
        caller = self.caller
        args = self.args.strip()

        if "list" in self.switches:
            self._mark_list(caller, args)
            return

        if "remove" in self.switches:
            self._mark_remove(caller, args)
            return

        # Add mark
        if "=" not in args:
            self.msg(
                "Usage:\n"
                "  mark <name> <zone> = <description>\n"
                "  mark/remove <name> <zone> <#>\n"
                "  mark/list <name>"
            )
            return

        left, _, desc = args.partition("=")
        left_parts = left.strip().split(None, 1)

        if len(left_parts) < 2:
            self.msg("Usage: mark <name> <zone> = <description>")
            return

        target_name = left_parts[0]
        zone_name = left_parts[1].strip().lower().replace(" ", "_")
        desc = desc.strip()

        if not desc:
            self.msg("Marking description cannot be empty.")
            return

        target = _find_char_in_room(caller, target_name)
        if not target:
            self.msg(f"You don't see '{target_name}' here.")
            return

        import time
        markings = list(target.db.markings or [])
        markings.append({
            "zone":        zone_name,
            "desc":        desc,
            "set_by_id":   caller.id,
            "set_by_name": _name(caller),
            "timestamp":   time.time(),
        })
        target.db.markings = markings

        cname = _name(caller)
        tname = _name(target)

        caller.msg(
            f"You mark {tname}'s {zone_name}: "
            f"{desc[:60]}{'...' if len(desc) > 60 else ''}"
        )
        target.msg(f"{cname} marks your {zone_name}.")
        if caller.location:
            caller.location.msg_contents(
                f"|x{cname} marks {tname}.|n",
                exclude=[caller, target],
            )

    def _mark_list(self, caller, args):
        target_name = args.strip()
        if target_name:
            target = _find_char_in_room(caller, target_name)
            if not target:
                self.msg(f"You don't see '{target_name}' here.")
                return
        else:
            target = caller

        markings = target.db.markings or []
        tname = _name(target)
        sep = f"|w{'─' * 40}|n"

        if not markings:
            self.msg(
                f"{'You have' if target == caller else tname + ' has'} "
                f"no markings."
            )
            return

        lines = [f"\n{sep}", f"|wMarkings on {tname}|n", sep]
        for i, entry in enumerate(markings, 1):
            zone = entry.get("zone", "unknown")
            desc = entry.get("desc", "")
            set_by = entry.get("set_by_name", "unknown")
            lines.append(
                f"  [{i}] |w{zone}|n — placed by {set_by}\n"
                f"       {desc}"
            )
        lines.append(sep)
        self.msg("\n".join(lines))

    def _mark_remove(self, caller, args):
        if not args:
            self.msg("Usage: mark/remove <name> <zone> <#>")
            return

        parts = args.strip().split()
        if len(parts) < 3:
            self.msg("Usage: mark/remove <name> <zone> <#>")
            return

        target_name = parts[0]
        zone_name = parts[1].lower().replace(" ", "_")
        try:
            num = int(parts[2])
        except ValueError:
            self.msg("The third argument must be a number.")
            return

        target = _find_char_in_room(caller, target_name)
        if not target:
            self.msg(f"You don't see '{target_name}' here.")
            return

        is_admin = (
            caller.is_superuser
            or caller.check_permstring("Admin")
        )

        markings = list(target.db.markings or [])
        zone_entries = [
            (i, m) for i, m in enumerate(markings)
            if m.get("zone") == zone_name
        ]

        if not zone_entries:
            self.msg(
                f"No markings on '{zone_name}' for "
                f"{_name(target)}."
            )
            return

        if num < 1 or num > len(zone_entries):
            self.msg(
                f"There are only {len(zone_entries)} marking(s) "
                f"on '{zone_name}'. Use mark/list to check."
            )
            return

        orig_idx, entry = zone_entries[num - 1]
        set_by_id = entry.get("set_by_id")

        if not is_admin and caller.id != set_by_id:
            self.msg(
                "Only the one who placed that marking can remove it."
            )
            return

        del markings[orig_idx]
        target.db.markings = markings

        cname = _name(caller)
        tname = _name(target)
        caller.msg(
            f"You remove marking #{num} from {tname}'s {zone_name}."
        )
        if caller != target:
            target.msg(
                f"{cname} removes a marking from your {zone_name}."
            )


# -------------------------------------------------------------------
# Export
# -------------------------------------------------------------------

ALL_RP_TOOLS_CMDS = [
    CmdFlock,
    CmdFunlock,
    CmdRestrain,
    CmdUnrestrain,
    CmdRestraints,
    CmdLead,
    CmdUnlead,
    CmdProp,
    CmdDetail,
    CmdStage,
    CmdMark,
]
