"""
commands/teleport_commands.py

Jump / summon / accept / decline for Re:Void.

jump    — teleport to a character or room directly
summon  — invite another character to teleport to you (requires acceptance)
accept  — accept a pending summon
decline — decline a pending summon

Consent flags (character.db.consent_flags):
    allow_jump    — others may jump to this character's location
    allow_summon  — others may summon this character

Per-player overrides in character.db.consent_overrides work the same
way as all other consent types.

Room flag:
    room.db.jump_protected = True  — blocks jumping into / summoning to this room
    (HousingRoom bypasses this for owner/friends via can_enter())

Staff always bypass both flags and room protection.
"""

import time
from evennia import Command
from evennia.utils import delay


SUMMON_TIMEOUT = 60   # seconds before a summon expires


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _char_name(character):
    return (character.db.rp_name or character.key) if character else "?"


def _check_consent(target, requester, flag):
    """
    Return True if target allows requester to perform action 'flag'.

    Checks:
      1. Per-player block override  → deny
      2. Per-player allow override  → allow
      3. Global consent_flags[flag] → use as default
    Falls back to True if the flag is missing (new characters).
    Staff (Admin+) always pass.
    """
    if requester.is_superuser or requester.check_permstring("Admin"):
        return True

    overrides  = target.db.consent_overrides or {}
    block_map  = overrides.get("block", {})
    allow_map  = overrides.get("allow", {})

    # Per-player id OR relationship-tier (owner/lover/family/faction/hostile).
    from world.relationships import override_decision
    decision = override_decision(requester, target,
                                 allow_map.get(flag, set()), block_map.get(flag, set()))
    if decision == "block":
        return False
    if decision == "allow":
        return True
    # Global flag (default True if missing)
    flags = target.db.consent_flags or {}
    return flags.get(flag, True)


def _room_allows_jump(room, mover):
    """
    Return True if mover may jump into / be summoned into room.

    HousingRooms use can_enter(); all other rooms check jump_protected.
    Staff always pass.
    """
    if mover.is_superuser or mover.check_permstring("Admin"):
        return True

    from typeclasses.housing import HousingRoom
    if isinstance(room, HousingRoom):
        return room.can_enter(mover)

    return not getattr(room.db, "jump_protected", False)


def _find_target(caller, target_str):
    """
    Resolve target_str to a character or room object.
    Supports:
      #<dbref>   — direct room or character lookup by id
      <name>     — character search via caller.search
    Returns (obj, error_str) — one will be None.
    """
    from evennia.objects.models import ObjectDB

    target_str = target_str.strip()

    if target_str.startswith("#"):
        try:
            pk = int(target_str[1:])
            obj = ObjectDB.objects.get(pk=pk).typeclass
            return obj, None
        except (ValueError, ObjectDB.DoesNotExist):
            return None, f"No object found with dbref '{target_str}'."

    # Character search — global (not limited to current room)
    results = caller.search(
        target_str,
        global_search=True,
        quiet=True,
    )
    if not results:
        return None, f"No character named '{target_str}' found."
    if isinstance(results, list):
        if len(results) > 1:
            caller.msg(
                f"Multiple matches for '{target_str}'. "
                f"Be more specific or use #dbref."
            )
            return None, None
        return results[0], None
    return results, None


# ---------------------------------------------------------------------------
# jump
# ---------------------------------------------------------------------------

class CmdJump(Command):
    """
    Jump directly to a character or room.

    Usage:
        jump <name>        — jump to a character's location
        jump #<dbref>      — jump to a room or character by dbref

    Jump is blocked if:
      - The destination room has jump_protected set (unless you are
        owner/friend of a housing room)
      - The target character has allow_jump turned off in their consent flags
      - You are blocked by that character's per-player consent override

    Staff bypass all protections.

    See also: summon, consent
    """
    key = "jump"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            self.msg("Usage: jump <name> or jump #<dbref>")
            return

        # Navigation lock check
        if not char.is_superuser and not char.check_permstring("Admin"):
            try:
                from world.binding_effects import check_navigation_allowed
                ok, reason = check_navigation_allowed(char)
                if not ok:
                    self.msg(reason)
                    return
            except Exception:
                pass

        target, err = _find_target(char, args)
        if err:
            self.msg(err)
            return
        if target is None:
            return

        from typeclasses.rooms import Room
        from typeclasses.characters import Character

        # Resolve destination room
        if isinstance(target, Room):
            dest = target
            jump_target = None      # jumping to a room, not a person
        elif isinstance(target, Character):
            if target == char:
                self.msg("|xYou can't jump to yourself.|n")
                return
            dest = target.location
            jump_target = target
        else:
            self.msg("|xThat is not a valid jump destination.|n")
            return

        if not dest:
            self.msg("|xThat character doesn't seem to be anywhere.|n")
            return

        if dest == char.location:
            self.msg("|xYou are already there.|n")
            return

        # Check character consent
        if jump_target and not _check_consent(jump_target, char, "allow_jump"):
            self.msg(
                f"|x{_char_name(jump_target)} is not allowing jumps to their location.|n"
            )
            return

        # Check room protection
        if not _room_allows_jump(dest, char):
            self.msg(
                "|xThat location is protected — you cannot jump there.|n"
            )
            return

        # Move
        name = _char_name(char)
        char.move_to(dest, quiet=True)
        char.msg(f"|xYou jump to {dest.key}.|n")
        dest.msg_contents(
            f"|x{name} arrives in a shimmer of void-light.|n",
            exclude=char,
        )
        char.execute_cmd("look")


# ---------------------------------------------------------------------------
# summon
# ---------------------------------------------------------------------------

class CmdSummon(Command):
    """
    Summon another character to your location.

    Usage:
        summon <name>

    Sends the target a request. They must type 'accept' or 'decline'
    within one minute. The summon fails silently if they don't respond.

    Summon is blocked if:
      - The target has allow_summon turned off in their consent flags
      - Your current room has jump_protected set (unless housing owner/friend)
      - The target is blocked from summoning in their per-player overrides

    Staff bypass all protections.

    See also: jump, consent
    """
    key = "summon"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            self.msg("Usage: summon <name>")
            return

        target, err = _find_target(char, args)
        if err:
            self.msg(err)
            return
        if target is None:
            return

        from typeclasses.characters import Character
        if not isinstance(target, Character):
            self.msg("|xYou can only summon characters.|n")
            return

        if target == char:
            self.msg("|xYou can't summon yourself.|n")
            return

        dest = char.location
        if not dest:
            self.msg("|xYou have no location to summon anyone to.|n")
            return

        # Check room allows summoning destination
        if not _room_allows_jump(dest, target):
            self.msg(
                "|xYou cannot summon someone to this location — "
                "it is protected.|n"
            )
            return

        # Check target consent
        if not _check_consent(target, char, "allow_summon"):
            self.msg(
                f"|x{_char_name(target)} is not accepting summons.|n"
            )
            return

        # Check for existing pending summon on target
        existing = target.db.pending_summon
        if existing and existing.get("expires_at", 0) > time.time():
            self.msg(
                f"|x{_char_name(target)} already has a pending summon. "
                f"Try again in a moment.|n"
            )
            return

        # Store pending summon
        expires_at = time.time() + SUMMON_TIMEOUT
        target.db.pending_summon = {
            "summoner_id": char.id,
            "room_id":     dest.id,
            "expires_at":  expires_at,
        }

        summoner_name = _char_name(char)
        target.msg(
            f"\n|w{summoner_name}|n is summoning you to |w{dest.key}|n.\n"
            f"|xType |waccept|n to go, or |wdecline|n to refuse. "
            f"(Expires in {SUMMON_TIMEOUT} seconds.)|n"
        )
        self.msg(
            f"|xSummon sent to |w{_char_name(target)}|n. "
            f"Waiting for their response...|n"
        )

        # Schedule expiry cleanup
        def _expire():
            pending = target.db.pending_summon or {}
            if pending.get("summoner_id") == char.id:
                target.db.pending_summon = None
                char.msg(
                    f"|x{_char_name(target)} did not respond — summon expired.|n"
                )

        delay(SUMMON_TIMEOUT, _expire)


# ---------------------------------------------------------------------------
# accept
# ---------------------------------------------------------------------------

class CmdAccept(Command):
    """
    Accept a pending summon.

    Usage:
        accept

    See also: decline, summon
    """
    key = "accept"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        char = self.caller
        pending = char.db.pending_summon

        if not pending or pending.get("expires_at", 0) <= time.time():
            char.db.pending_summon = None
            self.msg("|xYou have no pending summon to accept.|n")
            return

        from evennia.objects.models import ObjectDB

        summoner_id = pending.get("summoner_id")
        room_id     = pending.get("room_id")

        try:
            dest = ObjectDB.objects.get(pk=room_id).typeclass
        except Exception:
            self.msg("|xThe destination no longer exists.|n")
            char.db.pending_summon = None
            return

        # Clear pending before moving to avoid double-fire
        char.db.pending_summon = None

        # Re-check room protection at time of acceptance
        if not _room_allows_jump(dest, char):
            self.msg(
                "|xThat room is now protected — you cannot be summoned there.|n"
            )
            return

        # Resolve summoner for messaging
        summoner_name = "Someone"
        try:
            summoner = ObjectDB.objects.get(pk=summoner_id).typeclass
            summoner_name = _char_name(summoner)
            summoner.msg(
                f"|w{_char_name(char)}|n has accepted your summon."
            )
        except Exception:
            pass

        name = _char_name(char)
        char.move_to(dest, quiet=True)
        char.msg(
            f"|xYou accept {summoner_name}'s summon and arrive at |w{dest.key}|n.|n"
        )
        dest.msg_contents(
            f"|x{name} arrives, answering a summon.|n",
            exclude=char,
        )
        char.execute_cmd("look")


# ---------------------------------------------------------------------------
# decline
# ---------------------------------------------------------------------------

class CmdDecline(Command):
    """
    Decline a pending summon.

    Usage:
        decline

    See also: accept, summon
    """
    key = "decline"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        char = self.caller
        pending = char.db.pending_summon

        if not pending or pending.get("expires_at", 0) <= time.time():
            char.db.pending_summon = None
            self.msg("|xYou have no pending summon to decline.|n")
            return

        summoner_id = pending.get("summoner_id")
        char.db.pending_summon = None

        # Notify summoner
        try:
            from evennia.objects.models import ObjectDB
            summoner = ObjectDB.objects.get(pk=summoner_id).typeclass
            summoner.msg(
                f"|w{_char_name(char)}|n has declined your summon."
            )
        except Exception:
            pass

        self.msg("|xSummon declined.|n")


# ---------------------------------------------------------------------------
# Export list for default_cmdsets.py
# ---------------------------------------------------------------------------

ALL_TELEPORT_CMDS = [
    CmdJump,
    CmdSummon,
    CmdAccept,
    CmdDecline,
]
