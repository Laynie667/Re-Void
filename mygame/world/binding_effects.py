"""
world/binding_effects.py

BindingEffects — a mixin and engine for devious item effects.

Items can carry any combination of the following effect flags:

  auto_consent      bool  — sets all consent flags True on activation;
                            restores previous state on deactivation
  lock_navigation   bool  — disables waystone, jump, summon, home commands
  lock_self_remove  bool  — requires another character to remove the item;
                            the wearer's own remove command is rejected
  lock_self_cmds    bool  — prevents self-targeted emotes and self-modify
                            commands (consent changes, zone desc changes, etc.)
  pet_triggers      bool  — enables spoken trigger responses from holder
  room_bound        bool  — when True via 'stay' trigger, blocks all exits;
                            cleared by 'come/heel/free/release' or item removal

Pet trigger words (holder says them in the same room as the bound character):
  stay              bind to current room
  come / heel / here / free / release    clear room bound
  sit               set body_language to 'sitting'
  down / floor      set body_language to 'on all fours'
  beg               set body_language to 'begging' + fire emote
  roll / rollover   fire forced roll-over emote
  speak / bark      fire a bark/whimper response message
  quiet / shush     lock say for 5 minutes
  paw / shake       fire paw-raise emote
  heel              clear room_bound + set body_language to 'at heel'

Usage:
    from world.binding_effects import apply_effects, remove_effects, check_trigger

    # When item is equipped:
    apply_effects(character, item)

    # When item is removed:
    remove_effects(character, item)

    # In rp_commands.CmdSay, after broadcasting:
    check_trigger(speaker, text, room)
"""

import time

# ---------------------------------------------------------------------------
# Consent flag keys — all will be set True by auto_consent
# ---------------------------------------------------------------------------

ALL_CONSENT_FLAGS = [
    "casual", "intimate", "mature", "bdsm",
    "lead_follow", "restraint", "plock",
    "undress", "blindfold", "gag", "tieup", "strip", "examclose",
]

# ---------------------------------------------------------------------------
# Apply / remove effects
# ---------------------------------------------------------------------------

def apply_effects(character, item):
    """
    Activate all binding effects on character from item's db flags.
    Called when an item is worn or attached.
    """
    effects = _get_effects(item)
    if not effects:
        return

    # auto_consent — save previous state, set all flags True
    if effects.get("auto_consent"):
        prev = dict(character.db.consent_flags or {})
        character.db.binding_consent_backup = prev
        flags = dict(prev)
        for key in ALL_CONSENT_FLAGS:
            flags[key] = True
        character.db.consent_flags = flags
        character.msg(
            "|xAll consent flags have been opened by the binding.|n"
        )

    # lock_navigation
    if effects.get("lock_navigation"):
        character.db.navigation_locked = True
        character.msg(
            "|xYou feel the binding settle. The waystones and exits feel further away.|n"
        )

    # lock_self_cmds
    if effects.get("lock_self_cmds"):
        character.db.self_cmds_locked = True

    # pet_triggers — mark which item is the trigger source
    if effects.get("pet_triggers"):
        sources = list(character.db.pet_trigger_sources or [])
        if item.dbref not in sources:
            sources.append(item.dbref)
        character.db.pet_trigger_sources = sources


def remove_effects(character, item):
    """
    Deactivate binding effects when item is removed.
    Only clears effects if no other active binding item still sets them.
    """
    effects = _get_effects(item)
    if not effects:
        return

    # auto_consent — restore backup if no other auto_consent items active
    if effects.get("auto_consent"):
        if not _other_item_has(character, item, "auto_consent"):
            backup = character.db.binding_consent_backup or {}
            if backup:
                character.db.consent_flags = backup
                character.db.binding_consent_backup = {}
                character.msg(
                    "|xConsent flags restored to previous state.|n"
                )
            else:
                # No backup — reset to defaults
                character.db.consent_flags = {k: False for k in ALL_CONSENT_FLAGS}

    # lock_navigation
    if effects.get("lock_navigation"):
        if not _other_item_has(character, item, "lock_navigation"):
            character.db.navigation_locked = False
            character.msg("|xThe weight on the waystones lifts.|n")

    # lock_self_cmds
    if effects.get("lock_self_cmds"):
        if not _other_item_has(character, item, "lock_self_cmds"):
            character.db.self_cmds_locked = False

    # room_bound — clear on removal
    if effects.get("room_bound") or effects.get("pet_triggers"):
        character.db.room_bound = None

    # pet_triggers — remove this item from trigger sources
    if effects.get("pet_triggers"):
        sources = list(character.db.pet_trigger_sources or [])
        if item.dbref in sources:
            sources.remove(item.dbref)
        character.db.pet_trigger_sources = sources


# ---------------------------------------------------------------------------
# Pet trigger engine
# ---------------------------------------------------------------------------

# Map of trigger words to handler function names
_TRIGGER_MAP = {
    "stay":     "_trigger_stay",
    "come":     "_trigger_free",
    "heel":     "_trigger_heel",
    "here":     "_trigger_free",
    "free":     "_trigger_free",
    "release":  "_trigger_free",
    "sit":      "_trigger_sit",
    "down":     "_trigger_down",
    "floor":    "_trigger_down",
    "beg":      "_trigger_beg",
    "roll":     "_trigger_roll",
    "rollover": "_trigger_roll",
    "speak":    "_trigger_speak",
    "bark":     "_trigger_speak",
    "quiet":    "_trigger_quiet",
    "shush":    "_trigger_quiet",
    "paw":      "_trigger_paw",
    "shake":    "_trigger_paw",
}


def check_trigger(speaker, text: str, room, target=None):
    """
    Called from CmdSay / CmdSayTo after a character speaks in a room.
    Checks whether any pet-trigger-bound character in the room
    is bound to this speaker, and fires matching triggers.

    Args:
        speaker:  The character who spoke.
        text:     The raw spoken text (lowercased).
        room:     The current room object.
        target:   If provided (from 'sayto <target> <text>'), only fire
                  triggers for this specific character.  If None, fires
                  for all bound characters the speaker is leading.
    """
    if not room:
        return

    words = set(text.lower().split())

    from typeclasses.characters import Character
    candidates = [target] if target else list(room.contents)

    for char in candidates:
        if not isinstance(char, Character):
            continue
        if char == speaker:
            continue
        if char.location != room:
            continue

        # Is this character pet-trigger-bound?
        if not getattr(char.db, "pet_trigger_sources", None):
            continue

        # Is the speaker their holder/leader?
        leading_id = getattr(speaker.db, "leading", None)
        if leading_id != char.id:
            continue

        # Find matching trigger — first word wins
        for word in sorted(words, key=len, reverse=True):
            handler_name = _TRIGGER_MAP.get(word)
            if handler_name:
                handler = globals().get(handler_name)
                if handler:
                    handler(char, speaker, room)
                break   # one trigger per say per target


# ---------------------------------------------------------------------------
# Trigger handlers
# ---------------------------------------------------------------------------

def _trigger_stay(char, holder, room):
    char.db.room_bound = room.dbref
    cname  = char.db.rp_name or char.name
    hname  = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} goes still — held in place by {hname}'s word.|n"
    )
    char.msg("|xStay. You're not going anywhere.|n")


def _trigger_free(char, holder, room):
    char.db.room_bound = None
    cname  = char.db.rp_name or char.name
    hname  = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} is released — free to move again.|n"
    )
    char.msg("|xYou're free to move.|n")


def _trigger_heel(char, holder, room):
    char.db.room_bound = None
    char.db.body_language = "at heel"
    cname  = char.db.rp_name or char.name
    hname  = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} settles close at {hname}'s heel.|n"
    )
    char.msg("|xHeel. You settle in close.|n")


def _trigger_sit(char, holder, room):
    char.db.body_language = "sitting"
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|x{cname} sits.|n")
    char.msg("|xSit.|n")


def _trigger_down(char, holder, room):
    char.db.body_language = "on all fours"
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|x{cname} drops down — on all fours, head low.|n")
    char.msg("|xDown.|n")


def _trigger_beg(char, holder, room):
    char.db.body_language = "begging"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} rises onto their knees — hands raised, eyes up. Begging.|n"
    )
    char.msg("|xBeg.|n")


def _trigger_roll(char, holder, room):
    char.db.body_language = "sprawled"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} drops and rolls — onto their back, exposed, still.|n"
    )
    char.msg("|xRoll over.|n")


def _trigger_speak(char, holder, room):
    cname = char.db.rp_name or char.name
    pron  = (char.db.pronouns or {}).get("subject", "they")
    room.msg_contents(
        f"|x{cname} makes a soft sound — high and obedient. {pron.capitalize()} spoke.|n"
    )
    char.msg("|xSpeak.|n")


def _trigger_quiet(char, holder, room):
    # Lock say for 5 minutes
    char.db.say_locked_until = time.time() + 300
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|x{cname} goes quiet.|n")
    char.msg("|xQuiet. No speaking for five minutes.|n")


def _trigger_paw(char, holder, room):
    char.db.body_language = "paw raised"
    cname  = char.db.rp_name or char.name
    hname  = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} raises one hand toward {hname} — patient, waiting.|n"
    )
    char.msg("|xPaw.|n")


# ---------------------------------------------------------------------------
# Movement block check — call from character.at_before_move
# ---------------------------------------------------------------------------

def check_movement_allowed(character, destination) -> tuple:
    """
    Returns (True, "") if movement is allowed, (False, reason) if blocked.
    Call this from character.at_before_move().
    """
    if character.db.room_bound:
        return False, "|xStay. You cannot leave.|n"
    return True, ""


# ---------------------------------------------------------------------------
# Navigation lock check — call from waystone/jump/summon commands
# ---------------------------------------------------------------------------

def check_navigation_allowed(character) -> tuple:
    """
    Returns (True, "") if navigation commands are allowed.
    Returns (False, reason) if locked by a binding item.
    """
    if getattr(character.db, "navigation_locked", False):
        return False, "|xThe binding holds you here. Waystones and shortcuts are out of reach.|n"
    return True, ""


# ---------------------------------------------------------------------------
# Self-command lock check — call from consent/zone desc commands
# ---------------------------------------------------------------------------

def check_self_cmds_allowed(character) -> tuple:
    """
    Returns (True, "") if self-modifying commands are allowed.
    Returns (False, reason) if locked.
    """
    if getattr(character.db, "self_cmds_locked", False):
        return False, "|xThe binding prevents that. Someone else has to do it for you.|n"
    return True, ""


# ---------------------------------------------------------------------------
# Say lock check — call from CmdSay
# ---------------------------------------------------------------------------

def check_say_allowed(character) -> tuple:
    """
    Returns (True, "") if speaking is allowed.
    Returns (False, reason) if quiet-locked.
    """
    until = getattr(character.db, "say_locked_until", 0) or 0
    if time.time() < until:
        remaining = int(until - time.time())
        return False, f"|xQuiet. ({remaining}s remaining)|n"
    return True, ""


# ---------------------------------------------------------------------------
# Self-remove lock check — call from CmdRemoveItem
# ---------------------------------------------------------------------------

def check_self_remove_allowed(character, item) -> tuple:
    """
    Returns (True, "") if the character may remove this item themselves.
    Returns (False, reason) if lock_self_remove is set.
    """
    effects = _get_effects(item)
    if effects.get("lock_self_remove"):
        return False, (
            f"|xThe binding on {item.key} won't let you remove it yourself. "
            f"Someone else has to take it off.|n"
        )
    return True, ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_effects(item) -> dict:
    """Return the item's binding_effects dict, or {}."""
    return getattr(item.db, "binding_effects", None) or {}


def _other_item_has(character, exclude_item, flag: str) -> bool:
    """Return True if any other worn/inserted item on character has this effect flag."""
    from typeclasses.plug_item    import PlugItem
    from typeclasses.collar_item  import CollarItem, LeashItem
    from typeclasses.wearable_item import WearableItem

    for obj in character.contents:
        if obj == exclude_item:
            continue
        is_active = (
            (isinstance(obj, PlugItem)     and obj.db.is_inserted) or
            (isinstance(obj, CollarItem)   and obj.db.is_worn)     or
            (isinstance(obj, WearableItem) and obj.db.is_worn)
        )
        if is_active:
            effects = _get_effects(obj)
            if effects.get(flag):
                return True
    return False
