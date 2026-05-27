"""
commands/freeform_commands.py

Player-facing commands for Re:Void's freeform system.

Freeform items are purely descriptive — no real game objects.
They are stored on character.db.freeform_items and shown in
look/sheet output exactly like clothing, but without inventory.

COMMANDS
--------
  place <target> <zone> = <name>/<description>
      Place a freeform item on a character (self or other).
      The zone must exist on the target. Name is the short
      handle used in lock commands.

  unplace <target> <name>
      Remove a freeform item if it is not locked.

  slock <target> <name>
      Scene-lock an item. Returns a reference code.
      Lock releases automatically when the scene ends.

  unslock <target> <name> <code>
      Release a scene lock by providing the code.

  plock <target> <name>
      Permanently lock an item. Target must have plock consent
      toggled on. Creates a real key object in your inventory.

  unplock <target> <name>
      Release a permanent lock. You must be holding the key.
      Admins can use unplock/admin without a key.

  freeform [list] [<target>]
      List freeform items on self or another character.
  freeform save <item_name> "<wardrobe name>"
      Save a freeform item to your wardrobe.

  sound   [/pin | /clear] [<text>]
  scent   [/pin | /clear] [<text>]
  light   [/pin | /clear] [<text>]
  taste   [/pin | /clear] [<text>]
  texture [/pin | /clear] [<text>]
  temp    [/pin | /clear] [<text>]
      Set or manage a sensory layer in the current room.
      /pin  — survive scene end  /clear — remove the layer

  senses
      Show all active sensory layers in the room.
"""

import re
from evennia.commands.default.muxcommand import MuxCommand
from evennia import create_object
from world.freeform_manager import FreeformManager, SENSORY_TYPES, SENSORY_LABELS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_character(caller, target_name):
    """
    Find a character by name in the room, or return caller if 'me'/'self'.
    Returns (character, error_str). On error, character is None.
    """
    if target_name.lower() in ("me", "self", ""):
        char = caller.puppet if hasattr(caller, 'puppet') else caller
        return char, None

    room = caller.location
    if not room:
        return None, "You're not in a room."

    for obj in room.contents:
        if hasattr(obj, 'db') and obj != caller:
            name = (obj.db.rp_name or obj.key or "").lower()
            term = target_name.lower()
            if name.startswith(term) or term in name or term == obj.key.lower():
                return obj, None

    return None, f"Nobody named '{target_name}' is here."


def _char_name(character):
    return character.db.rp_name or character.key


# ---------------------------------------------------------------------------
# place
# ---------------------------------------------------------------------------

class CmdPlace(MuxCommand):
    """
    Place a freeform item on a character.

    Freeform items are purely descriptive — no inventory object is created.
    They show up in look and on the character sheet in the relevant zone.

    Usage:
        place <target> <zone> = <name>/<description>
        place me neck = collar/A thin silver collar, engraved with runes
        place helena intimate = plug/A smooth obsidian plug, firmly seated
        place self wrist = cuff/A worn leather cuff buckled tight

    The 'name' is the short handle used for slock/plock/unplace commands.
    The 'description' is displayed when others look at the character.

    Placing on yourself requires no consent. Placing on another character
    is allowed freely but is recorded (they can unplace it if unlocked).

    See also: unplace, slock, plock, freeform
    """
    key = "place"
    locks = "cmd:all()"
    help_category = "Freeform"
    switch_options = ("in",)

    def func(self):
        caller = self.caller
        char = caller.puppet if hasattr(caller, 'puppet') else caller
        display_mode = "in" if "in" in self.switches else "on"

        if not self.lhs or not self.rhs:
            self.msg(
                "Usage: place <target> <zone> = <name>/<description>\n"
                "Example: place helena neck = collar/A silver collar"
            )
            return

        # Parse lhs: "<target> <zone>"
        lhs_parts = self.lhs.strip().split(None, 1)
        if len(lhs_parts) < 2:
            self.msg(
                "Specify both a target and a zone.\n"
                "Usage: place <target> <zone> = <name>/<description>"
            )
            return

        target_name = lhs_parts[0]
        zone = lhs_parts[1].lower().replace(" ", "_")

        # Parse rhs: "<name>/<description>"
        if "/" not in self.rhs:
            self.msg(
                "Separate the item name from its description with /\n"
                "Example: place helena neck = collar/A silver collar"
            )
            return

        name, _, desc = self.rhs.partition("/")
        name = name.strip().lower()
        desc = desc.strip()

        if not name or not desc:
            self.msg("Both a name and a description are required.")
            return

        if len(name) > 40:
            self.msg("Item name too long. Keep it under 40 characters.")
            return

        # Find target
        target, err = _find_character(caller, target_name)
        if err:
            # Allow placing on self by name
            if target_name.lower() in (
                char.key.lower(),
                (char.db.rp_name or "").lower()
            ):
                target = char
            else:
                self.msg(err)
                return

        ok, result = FreeformManager.place_item(
            target, zone, name, desc, char.id, display_mode=display_mode
        )
        if not ok:
            self.msg(f"|r{result}|n")
            return

        target_name_display = _char_name(target)
        char_name = _char_name(char)
        is_self = (target == char)

        mode_tag = " |x[in]|n" if display_mode == "in" else ""
        if is_self:
            self.msg(
                f"You wear |w{name}|n [{zone}]{mode_tag}: {desc}"
            )
            if char.location:
                char.location.msg_contents(
                    f"{char_name} adjusts something at their {zone.replace('_', ' ')}.",
                    exclude=char
                )
        else:
            self.msg(
                f"You place |w{name}|n on {target_name_display} [{zone}]{mode_tag}: {desc}"
            )
            target.msg(
                f"{char_name} places something at your "
                f"{zone.replace('_', ' ')}: {desc}"
            )
            if char.location:
                char.location.msg_contents(
                    f"{char_name} adjusts something at "
                    f"{target_name_display}'s {zone.replace('_', ' ')}.",
                    exclude=[char, target]
                )

            # If this was the forming companion, trigger Wren's completion reaction
            # then push the player out to the hub room after a short delay.
            if getattr(target.db, 'npc_id', None) == "forming_companion":
                from typeclasses.npc import NPC
                from evennia.utils import delay
                from evennia import search_object
                room = char.location

                # Fire Wren's farewell text
                if room:
                    for obj in room.contents:
                        if (isinstance(obj, NPC)
                                and getattr(obj.db, 'npc_id', None) == "forming_wren"):
                            obj.trigger_keyword(char, "_place_complete")
                            break

                # Find the hub exit destination — follow the room's first exit,
                # then clear the companion's freeform items for the next player.
                companion_ref = target

                def _push_to_hub(char_ref, comp_ref):
                    if not char_ref or not char_ref.location:
                        return
                    exits = [
                        o for o in char_ref.location.contents
                        if o.destination is not None
                    ]
                    if exits:
                        dest = exits[0].destination
                        char_ref.move_to(dest, quiet=False, move_type="teleport")
                    else:
                        # Fallback: try hub by dbref #2
                        hub = search_object("#2")
                        if hub:
                            char_ref.move_to(hub[0], quiet=False, move_type="teleport")
                    # Reset companion for the next visitor
                    if comp_ref:
                        comp_ref.db.freeform_items = {}

                delay(4, _push_to_hub, char, companion_ref)


# ---------------------------------------------------------------------------
# unplace
# ---------------------------------------------------------------------------

class CmdUnplace(MuxCommand):
    """
    Remove a freeform item from a character.

    The item must not be locked (slock or plock) to be removed.
    You can remove items you placed, or items on yourself.
    Admins can remove any unlocked item.

    Usage:
        unplace <target> <name>
        unplace me collar
        unplace helena cuff

    See also: place, unslock, unplock
    """
    key = "unplace"
    locks = "cmd:all()"
    help_category = "Freeform"

    def func(self):
        caller = self.caller
        char = caller.puppet if hasattr(caller, 'puppet') else caller

        args = self.args.strip().split(None, 1)
        if len(args) < 2:
            self.msg("Usage: unplace <target> <name>")
            return

        target_name, item_name = args[0], args[1].lower()

        target, err = _find_character(caller, target_name)
        if err:
            if target_name.lower() in (
                char.key.lower(),
                (char.db.rp_name or "").lower()
            ):
                target = char
            else:
                self.msg(err)
                return

        # Permission: must be placer, target themselves, or admin
        item = FreeformManager.get_item(target, item_name)
        if not item:
            self.msg(f"No freeform item named '{item_name}'.")
            return

        is_admin = caller.check_permstring("Admin")
        is_target = (target == char)
        is_placer = (item.get("placed_by") == char.id)

        if not (is_admin or is_target or is_placer):
            self.msg("You can only remove items you placed, or items on yourself.")
            return

        ok, result = FreeformManager.remove_item(target, item_name)
        if not ok:
            self.msg(f"|r{result}|n")
            return

        target_display = _char_name(target)
        char_name = _char_name(char)
        zone = result.get("zone", "unknown")

        if target == char:
            self.msg(f"You remove |w{item_name}|n from your {zone.replace('_', ' ')}.")
            if char.location:
                char.location.msg_contents(
                    f"{char_name} removes something from their {zone.replace('_', ' ')}.",
                    exclude=char
                )
        else:
            self.msg(
                f"You remove |w{item_name}|n from "
                f"{target_display}'s {zone.replace('_', ' ')}."
            )
            target.msg(
                f"{char_name} removes {item_name} from your "
                f"{zone.replace('_', ' ')}."
            )


# ---------------------------------------------------------------------------
# slock
# ---------------------------------------------------------------------------

class CmdSlock(MuxCommand):
    """
    Scene-lock a freeform item.

    A scene lock prevents the item from being removed until the current
    pose order ends, or until you release it with the code.
    The lock code is shown only to you. Keep it — you'll need it to
    release the lock manually if needed.

    Locks release automatically when the scene ends.

    Usage:
        slock <target> <name>
        slock helena collar
        slock me plug

    See also: unslock, plock, place
    """
    key = "slock"
    locks = "cmd:all()"
    help_category = "Freeform"

    def func(self):
        caller = self.caller
        char = caller.puppet if hasattr(caller, 'puppet') else caller

        args = self.args.strip().split(None, 1)
        if len(args) < 2:
            self.msg("Usage: slock <target> <name>")
            return

        target_name, item_name = args[0], args[1].lower()

        target, err = _find_character(caller, target_name)
        if err:
            if target_name.lower() in (
                char.key.lower(),
                (char.db.rp_name or "").lower()
            ):
                target = char
            else:
                self.msg(err)
                return

        ok, result = FreeformManager.slock_item(target, item_name, char.id)
        if not ok:
            self.msg(f"|r{result}|n")
            return

        code = result
        target_display = _char_name(target)
        char_name = _char_name(char)
        item = FreeformManager.get_item(target, item_name)
        zone = item.get("zone", "unknown").replace("_", " ") if item else "unknown"

        self.msg(
            f"You scene-lock |w{item_name}|n on {target_display}.\n"
            f"|yLock code: {code}|n  "
            f"(Use 'unslock {target_display} {item_name} {code}' to release.)\n"
            f"The lock will release automatically when the scene ends."
        )

        if target != char:
            target.msg(
                f"{char_name} fastens something at your {zone}. "
                f"It feels secure — scene-locked."
            )

        if char.location:
            char.location.msg_contents(
                f"{char_name} secures something at "
                f"{target_display}'s {zone}.",
                exclude=[char, target] if target != char else [char]
            )


# ---------------------------------------------------------------------------
# unslock
# ---------------------------------------------------------------------------

class CmdUnslock(MuxCommand):
    """
    Release a scene lock using the lock code.

    You must provide the code that was generated when the lock was applied.
    Only the person who applied the slock (or an admin) knows the code.

    Usage:
        unslock <target> <name> <code>
        unslock helena collar SL-ABC123

    See also: slock, unplock
    """
    key = "unslock"
    locks = "cmd:all()"
    help_category = "Freeform"

    def func(self):
        caller = self.caller
        char = caller.puppet if hasattr(caller, 'puppet') else caller

        args = self.args.strip().split(None, 2)
        if len(args) < 3:
            self.msg("Usage: unslock <target> <name> <code>")
            return

        target_name, item_name, code = args[0], args[1].lower(), args[2]

        target, err = _find_character(caller, target_name)
        if err:
            if target_name.lower() in (
                char.key.lower(),
                (char.db.rp_name or "").lower()
            ):
                target = char
            else:
                self.msg(err)
                return

        # Admins can bypass code check
        if caller.check_permstring("Admin"):
            item = FreeformManager.get_item(target, item_name)
            if item and item.get("lock", {}).get("type") == "slock":
                correct = item["lock"].get("code", "")
                code = correct  # Admin override

        ok, result = FreeformManager.unslock_item(target, item_name, code)
        if not ok:
            self.msg(f"|r{result}|n")
            return

        target_display = _char_name(target)
        char_name = _char_name(char)
        zone = result.get("zone", "unknown").replace("_", " ")

        self.msg(
            f"You release the scene lock on |w{item_name}|n "
            f"({target_display}'s {zone})."
        )
        if target != char:
            target.msg(
                f"{char_name} releases the lock on your {zone}."
            )


# ---------------------------------------------------------------------------
# plock
# ---------------------------------------------------------------------------

class CmdPlock(MuxCommand):
    """
    Permanently lock a freeform item.

    A permanent lock can only be released by the keyholder (you, unless
    you give the key away), an admin, or eventually an NPC keyholder.
    The lock survives scene end, logout, and everything else.

    The target character must have permanent lock consent toggled on.
    You can check with 'freeform <name>' or ask them.
    A key object is created in your inventory.

    Usage:
        plock <target> <name>
        plock helena collar

    See also: unplock, slock, place, consent
    """
    key = "plock"
    locks = "cmd:all()"
    help_category = "Freeform"

    def func(self):
        caller = self.caller
        char = caller.puppet if hasattr(caller, 'puppet') else caller

        args = self.args.strip().split(None, 1)
        if len(args) < 2:
            self.msg("Usage: plock <target> <name>")
            return

        target_name, item_name = args[0], args[1].lower()

        target, err = _find_character(caller, target_name)
        if err:
            if target_name.lower() in (
                char.key.lower(),
                (char.db.rp_name or "").lower()
            ):
                target = char
            else:
                self.msg(err)
                return

        # Check plock consent
        if not FreeformManager.check_plock_consent(target):
            target_display = _char_name(target)
            self.msg(
                f"{target_display} has not consented to permanent locks.\n"
                f"They can toggle this with: consent plock on"
            )
            return

        # Verify item exists before creating key
        item_data = FreeformManager.get_item(target, item_name)
        if not item_data:
            self.msg(f"No freeform item named '{item_name}'.")
            return
        if item_data.get("lock"):
            ltype = item_data["lock"].get("type", "locked")
            self.msg(f"|r'{item_name}' is already {ltype}ed.|n")
            return

        # Create the key object
        target_display = _char_name(target)
        key_obj = create_object(
            "typeclasses.key.Key",
            key=f"a key",
            location=char,
        )
        key_obj.setup_key(
            target_char=target,
            zone_name=item_data.get("zone", "unknown"),
            lock_type="persistent",
            creator=char,
            target_type="freeform",
            item_name=item_name,
        )

        ok, result = FreeformManager.plock_item(target, item_name, char.id, key_obj)
        if not ok:
            # Clean up key on failure
            key_obj.delete()
            self.msg(f"|r{result}|n")
            return

        zone = item_data.get("zone", "unknown").replace("_", " ")
        char_name = _char_name(char)

        self.msg(
            f"You permanently lock |w{item_name}|n on {target_display}.\n"
            f"|rA key has been added to your inventory.|n  "
            f"('{key_obj.key}' — examine it for details.)\n"
            f"|xOnly the keyholder, an admin, or a designated NPC can release this.|n"
        )
        target.msg(
            f"{char_name} permanently locks your {zone}. "
            f"|rThis lock will not release on its own.|n"
        )
        if char.location:
            char.location.msg_contents(
                f"{char_name} locks something at "
                f"{target_display}'s {zone} with a small key.",
                exclude=[char, target] if target != char else [char]
            )


# ---------------------------------------------------------------------------
# unplock
# ---------------------------------------------------------------------------

class CmdUnplock(MuxCommand):
    """
    Release a permanent lock.

    You must be holding the key that matches this lock.
    Give the key to someone else and they become the keyholder.

    Admins can use unplock/admin to release any permanent lock
    without needing the key.

    Usage:
        unplock <target> <name>
        unplock helena collar
        unplock/admin helena collar

    See also: plock, unslock
    """
    key = "unplock"
    switch_options = ("admin",)
    locks = "cmd:all()"
    help_category = "Freeform"

    def func(self):
        caller = self.caller
        char = caller.puppet if hasattr(caller, 'puppet') else caller
        is_admin = "admin" in self.switches

        if is_admin and not caller.check_permstring("Admin"):
            self.msg("You don't have permission to use unplock/admin.")
            return

        args = self.args.strip().split(None, 1)
        if len(args) < 2:
            self.msg("Usage: unplock <target> <name>")
            return

        target_name, item_name = args[0], args[1].lower()

        target, err = _find_character(caller, target_name)
        if err:
            if target_name.lower() in (
                char.key.lower(),
                (char.db.rp_name or "").lower()
            ):
                target = char
            else:
                self.msg(err)
                return

        # Find matching key in inventory (unless admin override)
        key_obj = None
        if not is_admin:
            item_data = FreeformManager.get_item(target, item_name)
            if item_data and item_data.get("lock"):
                key_id = item_data["lock"].get("key_id")
                for obj in char.contents:
                    if hasattr(obj, 'db') and obj.id == key_id:
                        key_obj = obj
                        break

            if not key_obj:
                self.msg(
                    f"You're not holding the key for '{item_name}'.\n"
                    f"|xAn admin can use 'unplock/admin' for emergencies.|n"
                )
                return

        ok, result = FreeformManager.unplock_item(
            target, item_name, key_obj=key_obj, admin=is_admin
        )
        if not ok:
            self.msg(f"|r{result}|n")
            return

        target_display = _char_name(target)
        char_name = _char_name(char)
        zone = result.get("zone", "unknown").replace("_", " ")

        self.msg(
            f"You unlock |w{item_name}|n on {target_display}'s {zone}."
        )
        target.msg(
            f"{char_name} unlocks your {zone}."
        )

        # Consume (delete) the key after use
        if key_obj:
            self.msg(f"|xThe key crumbles as the lock releases.|n")
            key_obj.delete()


# ---------------------------------------------------------------------------
# freeform (list / save)
# ---------------------------------------------------------------------------

class CmdFreeform(MuxCommand):
    """
    View and manage freeform items.

    Usage:
        freeform                        — list items on yourself
        freeform <target>               — list items on another character
        freeform save <name> "<label>"  — save a freeform item to your wardrobe
        freeform list                   — alias for no-arg

    Examples:
        freeform helena
        freeform save collar "silver collar"

    See also: place, unplace, slock, plock, wardrobe
    """
    key = "freeform"
    aliases = ["flist", "fl"]
    locks = "cmd:all()"
    help_category = "Freeform"

    def func(self):
        caller = self.caller
        char = caller.puppet if hasattr(caller, 'puppet') else caller
        args = self.args.strip()

        if not args or args == "list":
            self._show_items(char, char)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "save":
            self._save_item(caller, char, rest)
        elif subcmd == "list":
            self._show_items(char, char)
        else:
            # Treat as target name
            target, err = _find_character(caller, subcmd)
            if err:
                self.msg(err)
                return
            self._show_items(char, target)

    def _show_items(self, viewer, target):
        target_display = _char_name(target)
        is_self = (viewer == target)
        header = "|wYour freeform items:|n\n" if is_self else \
                 f"|wFreeform items on {target_display}:|n\n"
        body = FreeformManager.format_items(target, viewer=viewer)
        self.msg(f"{header}{body}")

    def _save_item(self, caller, char, args):
        # Parse: <item_name> "<wardrobe label>"
        match = re.match(r'(\S+)\s+"([^"]+)"', args)
        if not match:
            match = re.match(r'(\S+)\s+(\S+)', args)
        if not match:
            self.msg(
                'Usage: freeform save <item_name> "<wardrobe label>"\n'
                'Example: freeform save collar "silver collar"'
            )
            return

        item_name = match.group(1).lower()
        wardrobe_name = match.group(2).lower()

        ok, result = FreeformManager.save_to_wardrobe(char, wardrobe_name, item_name)
        if not ok:
            self.msg(f"|r{result}|n")
            return

        self.msg(
            f"Saved freeform item |w{item_name}|n to wardrobe "
            f"as |w\"{wardrobe_name}\"|n.\n"
            f"|xRetrieve it later with: wardrobe wear \"{wardrobe_name}\"|n"
        )


# ---------------------------------------------------------------------------
# Sensory commands — shared base class
# ---------------------------------------------------------------------------

class _CmdSensoryBase(MuxCommand):
    """
    Base class for sensory layer commands.
    Subclasses set `sense_type` and override key/aliases.
    """
    sense_type = None
    switch_options = ("pin", "clear")
    locks = "cmd:all()"
    help_category = "Freeform"

    def func(self):
        caller = self.caller
        char = caller.puppet if hasattr(caller, 'puppet') else caller
        room = char.location if char else caller.location

        if not room:
            self.msg("You need to be somewhere to set sensory layers.")
            return

        label = SENSORY_LABELS.get(self.sense_type, self.sense_type.capitalize())

        if "clear" in self.switches:
            ok, err = FreeformManager.clear_sensory(room, self.sense_type)
            if not ok:
                self.msg(f"|r{err}|n")
            else:
                char_name = _char_name(char)
                self.msg(f"You clear the {label.lower()} from the room.")
                room.msg_contents(
                    f"{char_name} clears the {label.lower()} from the room.",
                    exclude=char
                )
            return

        if not self.args.strip():
            # Show current
            entry = FreeformManager.get_sensory(room, self.sense_type)
            if not entry:
                self.msg(f"|xNo {label.lower()} is set here.|n")
            else:
                pinned = " |g[pinned]|n" if entry.get("pinned") else ""
                self.msg(
                    f"|w{label}|n{pinned}: {entry.get('text', '')}"
                )
            return

        text = self.args.strip()
        pinned = "pin" in self.switches

        ok, result = FreeformManager.set_sensory(
            room, self.sense_type, text, char.id, pinned=pinned
        )
        if not ok:
            self.msg(f"|r{result}|n")
            return

        char_name = _char_name(char)
        pin_note = " |g[pinned]|n" if pinned else ""
        self.msg(
            f"You set the {label.lower()}{pin_note}: {text}"
        )
        room.msg_contents(
            f"{char_name} adjusts the {label.lower()} of the room.",
            exclude=char
        )


class CmdSound(_CmdSensoryBase):
    """
    Set an ambient sound layer in the current room.

    Usage:
        sound <description>          — set sound (replaces existing)
        sound/pin <description>      — set and pin (survives scene end)
        sound/clear                  — remove the sound layer
        sound                        — show the current sound

    Examples:
        sound Rain hammers steadily against the shutters.
        sound/pin The deep hum of the city bleeds through the walls.
        sound/clear

    Pinned layers survive when the scene ends. Unpinned layers clear
    automatically at scene end.

    See also: scent, light, taste, texture, temp, senses
    """
    key = "sound"
    sense_type = "sound"


class CmdScent(_CmdSensoryBase):
    """
    Set an ambient scent layer in the current room.

    Usage:
        scent <description>
        scent/pin <description>
        scent/clear
        scent

    See also: sound, light, taste, texture, temp, senses
    """
    key = "scent"
    sense_type = "scent"


class CmdLight(_CmdSensoryBase):
    """
    Set the ambient light quality of the current room.

    Usage:
        light <description>
        light/pin <description>
        light/clear
        light

    See also: sound, scent, taste, texture, temp, senses
    """
    key = "light"
    sense_type = "light"


class CmdTaste(_CmdSensoryBase):
    """
    Set a taste/flavor layer in the current room.

    Usage:
        taste <description>
        taste/pin <description>
        taste/clear
        taste

    See also: sound, scent, light, texture, temp, senses
    """
    key = "taste"
    sense_type = "taste"


class CmdTexture(_CmdSensoryBase):
    """
    Set a tactile/texture layer in the current room.

    Usage:
        texture <description>
        texture/pin <description>
        texture/clear
        texture

    Examples:
        texture The floor is cold stone, slick with condensation.
        texture Silk hangings brush every surface, impossibly soft.

    See also: sound, scent, light, taste, temp, senses
    """
    key = "texture"
    sense_type = "texture"


class CmdTemp(_CmdSensoryBase):
    """
    Set the temperature quality of the current room.

    Usage:
        temp <description>
        temp/pin <description>
        temp/clear
        temp

    Examples:
        temp The room is stifling, the air barely moving.
        temp/pin A deep chill clings to every surface here.

    See also: sound, scent, light, taste, texture, senses
    """
    key = "temp"
    sense_type = "temp"


# ---------------------------------------------------------------------------
# senses — show all sensory layers in the room
# ---------------------------------------------------------------------------

class CmdSenses(MuxCommand):
    """
    Show all active sensory layers in the current room.

    Sensory layers are set with: sound, scent, light, taste, texture, temp
    Pinned layers survive scene end. Others clear automatically.

    Usage:
        senses

    See also: sound, scent, light, taste, texture, temp
    """
    key = "senses"
    aliases = ["sense"]
    locks = "cmd:all()"
    help_category = "Freeform"

    def func(self):
        caller = self.caller
        char = caller.puppet if hasattr(caller, 'puppet') else caller
        room = char.location if char else caller.location

        if not room:
            self.msg("You need to be somewhere.")
            return

        body = FreeformManager.format_sensory(room)
        self.msg(f"|wSensory layers — {room.key}:|n\n{body}")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_FREEFORM_CMDS = [
    CmdPlace,
    CmdUnplace,
    CmdSlock,
    CmdUnslock,
    CmdPlock,
    CmdUnplock,
    CmdFreeform,
    CmdSound,
    CmdScent,
    CmdLight,
    CmdTaste,
    CmdTexture,
    CmdTemp,
    CmdSenses,
]
