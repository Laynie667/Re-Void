"""
world/binding_effects.py

BindingEffects — a mixin and engine for devious item effects.

Effect flags (any combination per item):

  auto_consent          bool    — opens all consent flags; restores on removal
  lock_navigation       bool    — disables waystones / jump / summon
  lock_self_remove      bool    — requires another character to remove the item
  lock_self_cmds        bool    — blocks self-modify commands
  pet_triggers          bool    — enables spoken trigger responses from holder
  pet_type              str     — "puppy"(default)/"kitty"/"bunny"/"pony"/"fox"
  room_bound            bool    — movement blocked (set by 'stay' trigger)
  orgasm_denial         bool    — caps arousal at 99, blocks climax; released
                                  by holder saying the configured release word
  orgasm_release_word   str     — word that lifts denial for one climax (default "come")
  continuous_stimulation float  — arousal added per passive tick (15 min) while worn
  arousal_floor         float   — arousal cannot decay below this value
  forced_posture        str     — body_language locked to this string; wearer can't change it
  exhibition            bool    — strips and prevents camouflage; all zones always visible
  anti_clothing         bool    — prevents WearableItems covering zones while active
  broadcast_sensation   str     — dbref of character who shares sensation messages
  speech_filter         list    — list of active speech filter names (see speech_filters.py)

Pet types and their trigger sets:
  puppy   stay/come/heel/sit/down/beg/roll/speak/quiet/paw/free/release
  kitty   still/here/up/down/knead/purr/hiss/pounce/quiet/nap/free/release
  bunny   freeze/hop/thump/still/groom/binky/quiet/free/release
  pony    halt/walk/trot/canter/stand/present/rest/quiet/free/release
  fox     sneak/pounce/yip/still/curl/groom/quiet/free/release
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

    # auto_consent — save the TRUE previous state once, set all flags True.
    # Non-destructive: if a backup already exists (e.g. the cursed ring opened
    # consent before the contract did), don't overwrite it with the now-open
    # state, or the reset would restore "open" instead of her real original.
    if effects.get("auto_consent"):
        if character.db.binding_consent_backup is None:
            character.db.binding_consent_backup = dict(character.db.consent_flags or {})
        flags = dict(character.db.consent_flags or {})
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

    # block_endcycle — locks out the wearer's own 'endcycle'/'cycle stop'.
    # The machine can only be ended for them by someone else's 'cycle release'.
    if effects.get("block_endcycle"):
        character.db.endcycle_blocked = True

    # orgasm_denial
    if effects.get("orgasm_denial"):
        character.db.orgasm_denial = True
        character.db.orgasm_release_word = (
            effects.get("orgasm_release_word") or "come"
        )
        character.msg(
            "|xThe binding settles into place. Release is not yours to decide.|n"
        )

    # continuous_stimulation
    stim = effects.get("continuous_stimulation", 0.0) or 0.0
    if stim > 0:
        current = float(character.db.stim_per_tick or 0.0)
        character.db.stim_per_tick = current + stim

    # arousal_floor
    floor = effects.get("arousal_floor", 0.0) or 0.0
    if floor > 0:
        existing = float(character.db.arousal_floor or 0.0)
        character.db.arousal_floor = max(existing, floor)

    # forced_posture
    posture = effects.get("forced_posture")
    if posture:
        character.db.forced_posture = posture
        character.db.body_language  = posture
        character.msg(f"|xYour posture is fixed: {posture}.|n")

    # exhibition — strip camouflage, mark as exhibited
    if effects.get("exhibition"):
        character.db.exhibition_active = True
        character.db.outfit_camouflage = ""
        character.msg(
            "|xThe binding strips your concealment. You are on display.|n"
        )

    # anti_clothing
    if effects.get("anti_clothing"):
        character.db.anti_clothing_active = True

    # broadcast_sensation
    bcast = effects.get("broadcast_sensation")
    if bcast:
        targets = list(character.db.sensation_broadcast_targets or [])
        if bcast not in targets:
            targets.append(bcast)
        character.db.sensation_broadcast_targets = targets

    # speech_filter
    filters = effects.get("speech_filter") or []
    if filters:
        active = list(character.db.active_speech_filters or [])
        for f in filters:
            if f not in active:
                active.append(f)
        character.db.active_speech_filters = active
        character.msg(
            f"|xSpeech filter active: {', '.join(filters)}.|n"
        )

    # install_triggers — conditioning baked into the item. NOTE: these are
    # written into the wearer and deliberately do NOT come off with the item.
    for t in (effects.get("install_triggers") or []):
        try:
            install_trigger(
                character, t.get("phrase", ""),
                response=t.get("response", "kneel"),
                strength=int(t.get("strength", 1)),
                permanent=bool(t.get("permanent")),
                mantra=t.get("mantra"),
            )
        except Exception:
            pass

    # conditioning_on_wear — seeds the conditioning meter the moment it's worn
    cw = float(effects.get("conditioning_on_wear", 0.0) or 0.0)
    if cw:
        try:
            from world.conditioning import add_conditioning
            add_conditioning(character, cw, source="collar")
        except Exception:
            pass

    # suggestibility — spikes BOTH the Intake counter (the screen's hook / Bethany's
    # leverage, pre-sign) AND the persistent db.suggestibility stat, which has real
    # ongoing backing: conditioning gains scale with it and installed triggers seat
    # deeper (see conditioning.add_conditioning and install_trigger).
    sug = int(effects.get("suggestibility", 0) or 0)
    if sug:
        cur = int(getattr(character.db, "intake_suggestibility", 0) or 0)
        character.db.intake_suggestibility = cur + sug
        base = float(getattr(character.db, "suggestibility", 0) or 0)
        character.db.suggestibility = base + sug
        character.msg(
            "|xSomething behind your eyes goes soft and agreeable, like a question you've "
            "stopped wanting to ask. It would be so easy to just say yes.|n"
        )

    # lactation_primer — real LACT+ backing: ensures milk glands are installed and
    # switched permanently on, and bumps their output rate (drained by _do_milk).
    if effects.get("lactation_primer"):
        character.db.lactation_locked = True
        try:
            from world.facility_build import provision_body
            provision_body(character)
        except Exception:
            pass
        try:
            from evennia import search_object
            from typeclasses.production_item import ProductionItem
            for zd in (getattr(character.db, "zones", None) or {}).values():
                pr = ((zd or {}).get("mechanics", {}) or {}).get("production")
                if pr:
                    res = search_object(pr.get("item_dbref", ""), exact=True)
                    if res and isinstance(res[0], ProductionItem):
                        cur = float(res[0].db.base_rate_ml_per_tick or 8.0)
                        res[0].db.base_rate_ml_per_tick = cur + 4.0
        except Exception:
            pass

    # forfeit_name — she answers to her designation; name restored only by reset
    if effects.get("forfeit_name"):
        if not getattr(character.db, "designation", None):
            character.db.designation = "the breeding bitch"
        if not getattr(character.db, "facility_name_backup", None):
            character.db.facility_name_backup = character.db.rp_name or character.key
        character.db.rp_name = character.db.designation

    # lock_conditioning — consent to conditioning becomes irrevocable (in-fiction)
    if effects.get("lock_conditioning"):
        character.db.conditioning_permanent = True

    # breeding_quota — a per-species ledger of required successful breedings.
    # Accepts a dict {species: required} or a bare int (-> 'contributor').
    # NOTE: stored payloads come back as Evennia _SaverDict, which is NOT a dict
    # subclass — so test for a mapping via hasattr("items"), never isinstance(dict).
    q = effects.get("breeding_quota")
    if q:
        if hasattr(q, "items"):
            character.db.breeding_quota = {
                str(sp): {"current": 0, "required": int(req)}
                for sp, req in q.items()
            }
        else:
            character.db.breeding_quota = {
                "contributor": {"current": 0, "required": int(q)}
            }

    # required_honorific — she must address staff with the given honorific
    hon = effects.get("required_honorific")
    if hon:
        character.db.required_honorific = hon

    # compliance_threshold — defiance allowed before freedom is forfeited
    ct = effects.get("compliance_threshold")
    if ct:
        character.db.compliance_threshold = int(ct)
        if getattr(character.db, "defiance", None) is None:
            character.db.defiance = 0

    # milk_quota — a producer quota (so many bottles banked)
    mq = effects.get("milk_quota")
    if mq:
        character.db.milk_quota = {"current": 0, "required": int(mq)}

    # cum_receptacle — flavour lock: kept open, kept ready, kept full
    if effects.get("cum_receptacle"):
        character.db.cum_receptacle = True

    # mark_signed — flags that a facility contract has been signed
    if effects.get("mark_signed"):
        character.db.facility_signed = True
        character.db.facility_active = True
        # She's Facility property the moment she signs — stamp the faction title
        # slot now so (faction) renders on her sheet even before she's graded.
        try:
            from world.factions import seed_facility_title
            seed_facility_title(character)
        except Exception:
            pass
        # Begin the intake quest line and tick its 'signed' step — progression starts here.
        try:
            from world.quests import start_quest, advance_quest
            start_quest(character, "facility_intake")
            advance_quest(character, "facility_intake", "sign", 1)
        except Exception:
            pass
        # Install her real body systems (milk glands, womb, arousal) so milking and
        # breeding on the Floor actually engage — the realm never did this before.
        try:
            from world.facility_build import provision_body
            provision_body(character)
        except Exception:
            pass

    # realm_cycle — start the cycle that drags her through the realm's rooms.
    if effects.get("realm_cycle"):
        try:
            from typeclasses.facility_script import RealmCycleScript
            running = any(getattr(s, "key", "") == "realm_cycle" for s in character.scripts.all())
            if not running:
                from evennia.utils import create
                create.create_script(RealmCycleScript, obj=character,
                                     persistent=True, autostart=True)
        except Exception:
            pass
        # Bethany's chance visits, on the same subject — she wanders in off the desk.
        try:
            from typeclasses.bethany_script import BethanyScript
            running = any(getattr(s, "key", "") == "bethany_visit" for s in character.scripts.all())
            if not running:
                from evennia.utils import create
                create.create_script(BethanyScript, obj=character,
                                     persistent=True, autostart=True)
        except Exception:
            pass

    # body_processing — install the contract's processing hooks in HER body, so
    # she's milked and bred on a schedule wherever she is (real enforcement).
    if effects.get("body_processing"):
        character.db.body_processing_locked = True
        try:
            from typeclasses.body_processing_script import BodyProcessingScript
            running = any(isinstance(s, BodyProcessingScript)
                          or getattr(s, "key", "") == "body_processing"
                          for s in character.scripts.all())
            if not running:
                from evennia.utils import create
                create.create_script(BodyProcessingScript, obj=character,
                                     persistent=True, autostart=True)
        except Exception:
            pass

    # perpetual_heat — keeps her permanently in heat via a self-sustaining script
    if effects.get("perpetual_heat"):
        character.db.perpetual_heat = True
        character.db.arousal_floor = max(float(getattr(character.db, "arousal_floor", 0) or 0), 45.0)
        try:
            from typeclasses.heat_script import HeatScript
            running = any(isinstance(s, HeatScript) or getattr(s, "key", "") == "perpetual_heat"
                          for s in character.scripts.all())
            if not running:
                from evennia.utils import create
                create.create_script(HeatScript, obj=character, persistent=True, autostart=True)
        except Exception:
            pass

    # pet_triggers — mark which item is the trigger source
    if effects.get("pet_triggers"):
        sources = list(character.db.pet_trigger_sources or [])
        if item.dbref not in sources:
            sources.append(item.dbref)
        character.db.pet_trigger_sources = sources
        # Store pet type on the character so trigger engine uses right map
        pet_type = effects.get("pet_type", "puppy")
        character.db.pet_type = pet_type

    # Teat-Gag clause: a word (anyone's) seats a teat that silences-and-feeds her.
    if effects.get("teat_gag"):
        cfg = effects["teat_gag"]
        gag_word   = "hush little one"
        uncork     = "words back"
        fluid      = "semen"
        if isinstance(cfg, dict):
            gag_word = cfg.get("gag_word", gag_word)
            uncork   = cfg.get("uncork_word", uncork)
            fluid    = cfg.get("fluid", fluid)
        character.db.teat_gag_fluid = fluid
        install_trigger(character, gag_word, response="gag", strength=2)
        install_trigger(character, uncork, response="ungag", strength=2)

    # Nurse-First clause: no first sentence without nursing a load first.
    if effects.get("nurse_first"):
        cfg = effects["nurse_first"]
        character.db.nurse_first = True
        character.db.nurse_first_fluid = (
            cfg.get("fluid") if isinstance(cfg, dict) else None) or "semen"


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

    # block_endcycle
    if effects.get("block_endcycle"):
        if not _other_item_has(character, item, "block_endcycle"):
            character.db.endcycle_blocked = False

    # orgasm_denial
    if effects.get("orgasm_denial"):
        if not _other_item_has(character, item, "orgasm_denial"):
            character.db.orgasm_denial       = False
            character.db.orgasm_release_word = ""
            character.msg("|xThe denial lifts.|n")

    # continuous_stimulation — subtract this item's contribution
    stim = effects.get("continuous_stimulation", 0.0) or 0.0
    if stim > 0:
        current = float(character.db.stim_per_tick or 0.0)
        character.db.stim_per_tick = max(0.0, current - stim)

    # arousal_floor — recalculate from remaining items
    if effects.get("arousal_floor"):
        new_floor = 0.0
        for obj in character.contents:
            if obj == item:
                continue
            e = _get_effects(obj)
            f = e.get("arousal_floor", 0.0) or 0.0
            if f > new_floor:
                new_floor = f
        character.db.arousal_floor = new_floor

    # forced_posture
    if effects.get("forced_posture"):
        if not _other_item_has(character, item, "forced_posture"):
            character.db.forced_posture = None

    # exhibition
    if effects.get("exhibition"):
        if not _other_item_has(character, item, "exhibition"):
            character.db.exhibition_active = False
            character.msg("|xYour concealment returns.|n")

    # anti_clothing
    if effects.get("anti_clothing"):
        if not _other_item_has(character, item, "anti_clothing"):
            character.db.anti_clothing_active = False

    # broadcast_sensation
    bcast = effects.get("broadcast_sensation")
    if bcast:
        targets = list(character.db.sensation_broadcast_targets or [])
        if bcast in targets:
            targets.remove(bcast)
        character.db.sensation_broadcast_targets = targets

    # speech_filter — remove this item's filters if no other item still sets them
    filters = effects.get("speech_filter") or []
    if filters:
        active = list(character.db.active_speech_filters or [])
        for f in filters:
            # Only remove if no other item also requests this filter
            still_needed = any(
                f in (_get_effects(obj).get("speech_filter") or [])
                for obj in character.contents
                if obj != item and _is_active(obj)
            )
            if not still_needed and f in active:
                active.remove(f)
        character.db.active_speech_filters = active

    # room_bound — clear on removal
    if effects.get("room_bound") or effects.get("pet_triggers"):
        character.db.room_bound = None

    # pet_triggers — remove this item from trigger sources
    if effects.get("pet_triggers"):
        sources = list(character.db.pet_trigger_sources or [])
        if item.dbref in sources:
            sources.remove(item.dbref)
        character.db.pet_trigger_sources = sources
        if not sources:
            character.db.pet_type = None

    # Teat-Gag — clear the gag state, the suckling filter, and the gag/ungag triggers.
    if effects.get("teat_gag"):
        character.db.teat_gagged    = False
        character.db.teat_gag_until = 0
        character.db.teat_gag_fluid = None
        active = [f for f in (getattr(character.db, "active_speech_filters", None) or [])
                  if f != "suckling"]
        character.db.active_speech_filters = active
        triggers = [t for t in (getattr(character.db, "installed_triggers", None) or [])
                    if t.get("response") not in ("gag", "ungag")]
        character.db.installed_triggers = triggers

    # Nurse-First — lift the speech gate.
    if effects.get("nurse_first"):
        character.db.nurse_first       = False
        character.db.nursed_until      = 0
        character.db.nurse_first_fluid = None


# ---------------------------------------------------------------------------
# Pet trigger engine
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Pet trigger maps — one per pet type, maps trigger word → handler name
# ---------------------------------------------------------------------------

_PET_TRIGGER_MAPS = {

    "puppy": {
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
    },

    "kitty": {
        "still":    "_trigger_stay",
        "here":     "_trigger_free",
        "free":     "_trigger_free",
        "release":  "_trigger_free",
        "up":       "_trigger_kitty_up",
        "down":     "_trigger_kitty_down",
        "knead":    "_trigger_kitty_knead",
        "purr":     "_trigger_kitty_purr",
        "hiss":     "_trigger_kitty_hiss",
        "pounce":   "_trigger_kitty_pounce",
        "quiet":    "_trigger_quiet",
        "shush":    "_trigger_quiet",
        "nap":      "_trigger_kitty_nap",
        "come":     "_trigger_free",
    },

    "bunny": {
        "freeze":   "_trigger_stay",
        "still":    "_trigger_stay",
        "hop":      "_trigger_bunny_hop",
        "thump":    "_trigger_bunny_thump",
        "groom":    "_trigger_bunny_groom",
        "binky":    "_trigger_bunny_binky",
        "quiet":    "_trigger_quiet",
        "shush":    "_trigger_quiet",
        "free":     "_trigger_free",
        "release":  "_trigger_free",
        "come":     "_trigger_free",
    },

    "pony": {
        "halt":     "_trigger_stay",
        "stand":    "_trigger_stay",
        "walk":     "_trigger_pony_walk",
        "trot":     "_trigger_pony_trot",
        "canter":   "_trigger_pony_canter",
        "present":  "_trigger_pony_present",
        "rest":     "_trigger_pony_rest",
        "quiet":    "_trigger_quiet",
        "free":     "_trigger_free",
        "release":  "_trigger_free",
        "come":     "_trigger_free",
    },

    "fox": {
        "still":    "_trigger_stay",
        "sneak":    "_trigger_fox_sneak",
        "pounce":   "_trigger_fox_pounce",
        "yip":      "_trigger_fox_yip",
        "curl":     "_trigger_fox_curl",
        "groom":    "_trigger_fox_groom",
        "quiet":    "_trigger_quiet",
        "shush":    "_trigger_quiet",
        "free":     "_trigger_free",
        "release":  "_trigger_free",
        "come":     "_trigger_free",
    },

    "piggy": {
        "wallow":   "_trigger_piggy_wallow",
        "mud":      "_trigger_piggy_wallow",
        "root":     "_trigger_piggy_root",
        "oink":     "_trigger_piggy_oink",
        "squeal":   "_trigger_piggy_squeal",
        "grunt":    "_trigger_piggy_grunt",
        "present":  "_trigger_piggy_present",
        "roll":     "_trigger_piggy_roll",
        "stay":     "_trigger_stay",
        "quiet":    "_trigger_quiet",
        "shush":    "_trigger_quiet",
        "free":     "_trigger_free",
        "come":     "_trigger_free",
        "release":  "_trigger_free",
        "clean":    "_trigger_piggy_clean",
    },
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

        # Installed (conditioned) triggers fire for ANY speaker in the room —
        # not just a holder. That is the whole point of conditioning: the
        # response no longer belongs to the person who installed it.
        _check_installed_triggers(char, speaker, room, text)

        # Is this character pet-trigger-bound?
        if not getattr(char.db, "pet_trigger_sources", None):
            continue

        # Is the speaker their holder/leader?
        leading_id = getattr(speaker.db, "leading", None)
        if leading_id != char.id:
            continue

        # Find matching trigger using pet-type-specific map
        pet_type   = getattr(char.db, "pet_type", "puppy") or "puppy"
        trigger_map = _PET_TRIGGER_MAPS.get(pet_type, _PET_TRIGGER_MAPS["puppy"])

        for word in sorted(words, key=len, reverse=True):
            handler_name = trigger_map.get(word)
            if handler_name:
                handler = globals().get(handler_name)
                if handler:
                    handler(char, speaker, room)
                break   # one trigger per say per target

        # Orgasm denial release word check
        if getattr(char.db, "orgasm_denial", False):
            release_word = (char.db.orgasm_release_word or "come").lower()
            if release_word in words:
                _trigger_orgasm_release(char, speaker, room)


# ---------------------------------------------------------------------------
# Installed triggers — conditioning / brainwashing
#
# Unlike pet triggers (which only fire for the holder), an installed trigger
# fires for ANY speaker in the room. Conditioning writes them over time. They
# live on the character as:
#     character.db.installed_triggers = [
#         {"phrase": str, "response": str, "strength": int,
#          "permanent": bool, "mantra": str (optional)}
#     ]
# ---------------------------------------------------------------------------

def install_trigger(character, phrase, response="kneel",
                    strength=1, permanent=False, mantra=None):
    """Write or reinforce an installed trigger on `character`.

    Reinforcing an existing phrase raises its strength (deeper conditioning).
    Returns the trigger entry dict.
    """
    phrase = (phrase or "").strip().lower()
    if not phrase:
        return None
    # Suggestibility makes a freshly-seated trigger bite deeper (real ongoing backing).
    sug = float(getattr(character.db, "suggestibility", 0) or 0)
    if sug > 0:
        strength = int(strength) + int(min(sug, 20.0) // 4)
    triggers = list(getattr(character.db, "installed_triggers", None) or [])
    for entry in triggers:
        if entry.get("phrase") == phrase:
            entry["strength"] = int(entry.get("strength", 0)) + int(strength)
            if response:
                entry["response"] = response
            if mantra:
                entry["mantra"] = mantra
            if permanent:
                entry["permanent"] = True
            character.db.installed_triggers = triggers
            return entry
    entry = {
        "phrase": phrase, "response": response,
        "strength": int(strength), "permanent": bool(permanent),
    }
    if mantra:
        entry["mantra"] = mantra
    triggers.append(entry)
    character.db.installed_triggers = triggers
    return entry


def _check_installed_triggers(char, speaker, room, text):
    triggers = list(getattr(char.db, "installed_triggers", None) or [])
    if not triggers:
        return
    padded = f" {(text or '').lower()} "
    # Longest phrase first so a multi-word trigger wins over a substring.
    for entry in sorted(triggers, key=lambda e: len(e.get("phrase", "")), reverse=True):
        phrase = (entry.get("phrase") or "").strip().lower()
        if phrase and f" {phrase} " in padded:
            handler = _INSTALLED_RESPONSES.get(entry.get("response", "kneel"), _inst_kneel)
            handler(char, speaker, room, entry)
            break   # one installed trigger per utterance


def _inst_kneel(char, speaker, room, entry):
    char.db.body_language = "kneeling, head bowed"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} drops — knees to the floor, head bowing — before the thought "
        f"of doing otherwise has time to arrive.|n"
    )
    char.msg("|xThe word lands somewhere underneath thought. You are already kneeling.|n")


def _inst_beg(char, speaker, room, entry):
    char.db.body_language = "begging"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} rises onto their knees — hands lifting, breath climbing into a plea "
        f"that started before any decision to make it.|n"
    )
    char.msg("|xYou hear yourself begging, and you did not choose to start.|n")


def _inst_orgasm(char, speaker, room, entry):
    try:
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(char)
        add_arousal(char, 60.0)
    except Exception:
        pass
    # Every conditioned release rewires a little more.
    try:
        from world.conditioning import deepen_on_climax
        deepen_on_climax(char)
    except Exception:
        pass
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} shudders hard — the word reaches in and pulls, and there is no "
        f"part of {cname} that gets a say in what answers.|n"
    )
    char.msg("|xThe word goes straight through you. Your body answers it on its own.|n")


def _inst_blank(char, speaker, room, entry):
    char.db.body_language = "blank, waiting"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname}'s face smooths out — present, attentive, and entirely empty. "
        f"Waiting to be told the next thing.|n"
    )
    char.msg("|xThought thins to a clean, quiet readiness. You are waiting to be instructed.|n")


def _inst_freeze(char, speaker, room, entry):
    char.db.room_bound = room.dbref
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} goes rigid — caught mid-motion, held in place by nothing but a word.|n"
    )
    char.msg("|xYou cannot move. The word holds you exactly where you are.|n")


def _inst_leak(char, speaker, room, entry):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname}'s body answers the word before anything else can — a visible flush, "
        f"a helpless clench, wetness arriving first.|n"
    )
    char.msg("|xThe word finds the place it was trained into. Your body gives you away.|n")


def _inst_recite(char, speaker, room, entry):
    mantra = entry.get("mantra") or "good girls don't decide"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f'|x{cname} recites, voice gone flat and automatic: "{mantra}."|n'
    )
    char.msg("|xThe words leave your mouth before you can examine whether you mean them.|n")


# How long the teat-gag holds before it slips free on its own (the speech filter also
# self-expires on this, so a gagged little is never left unable to be heard with no one around).
_TEAT_GAG_SECONDS = 300.0


def _nurse_feed(character, fluid="semen", source="nursing"):
    """Feed her a laced mouthful: real fluid-bank deposit + a regression drip + a little
    dependence + the craving for the next. Shared by the Teat-Gag and Nurse-First clauses.
    Returns the ml fed."""
    import random
    ml = random.uniform(60.0, 160.0)
    try:
        from typeclasses.fluid_bank import GlobalFluidBank
        GlobalFluidBank.get().deposit(character, ml, fluid, None)
    except Exception:
        pass
    try:
        from world.regression import regress
        regress(character, random.uniform(2.0, 4.0), source=source)
    except Exception:
        pass
    try:
        character.db.drug_dependence = int(getattr(character.db, "drug_dependence", 0) or 0) + 1
        character.db.cum_craving = True
    except Exception:
        pass
    return ml


def _inst_gag(char, speaker, room, entry):
    """Teat-Gag trigger: the word seats a teat in her mouth — she suckles helplessly, can't
    speak (the 'suckling' filter), and is fed while she's silenced. Anyone can say the word."""
    import time as _t
    char.db.teat_gagged    = True
    char.db.teat_gag_until = _t.time() + _TEAT_GAG_SECONDS
    active = list(getattr(char.db, "active_speech_filters", None) or [])
    if "suckling" not in active:
        active.append("suckling")
        char.db.active_speech_filters = active
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|yThe word lands and {cname}'s mouth simply opens for it — a fat teat pushed past "
        f"her lips, and she latches on before she's decided to, cheeks hollowing, suckling "
        f"helplessly. She won't get a word out around it now; she'll only nurse.|n")
    char.msg("|xThe word seats the teat in your mouth and your jaw goes soft, your tongue to "
             "work on its own. Words aren't for you right now. Suckling is. Swallowing is.|n")
    _nurse_feed(char, getattr(char.db, "teat_gag_fluid", "semen") or "semen", source="teat_gag")


def _inst_ungag(char, speaker, room, entry):
    """Uncork word — pulls the teat, ends the gag early (someone else, since she can't speak)."""
    if not getattr(char.db, "teat_gagged", False):
        return
    char.db.teat_gagged    = False
    char.db.teat_gag_until = 0
    active = [f for f in (getattr(char.db, "active_speech_filters", None) or []) if f != "suckling"]
    char.db.active_speech_filters = active
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|yThe teat slips from {cname}'s mouth with a wet pop. She can shape "
                      f"words again — until the word's said over her once more.|n")
    char.msg("|xThe teat withdraws. Your mouth is your own again — until next time.|n")


_INSTALLED_RESPONSES = {
    "kneel":  _inst_kneel,
    "beg":    _inst_beg,
    "orgasm": _inst_orgasm,
    "blank":  _inst_blank,
    "obey":   _inst_blank,
    "freeze": _inst_freeze,
    "leak":   _inst_leak,
    "recite": _inst_recite,
    "gag":    _inst_gag,
    "ungag":  _inst_ungag,
}


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


# ── Kitty triggers ────────────────────────────────────────────────────────

def _trigger_kitty_up(char, holder, room):
    char.db.body_language = "perched upright"
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|x{cname} sits up — straight, alert, ears forward.|n")
    char.msg("|xUp.|n")

def _trigger_kitty_down(char, holder, room):
    char.db.body_language = "low and flat"
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|x{cname} flattens down — belly low, chin to the floor.|n")
    char.msg("|xDown.|n")

def _trigger_kitty_knead(char, holder, room):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} kneads — slow rhythmic press of hands into whatever surface is nearest, eyes half-closed.|n"
    )
    char.msg("|xKnead.|n")

def _trigger_kitty_purr(char, holder, room):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} makes a low continuous sound in their throat — steady, warm, involuntary.|n"
    )
    char.msg("|xPurr.|n")

def _trigger_kitty_hiss(char, holder, room):
    cname = char.db.rp_name or char.name
    hname = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} hisses at {hname} — teeth showing, ears back, entirely serious.|n"
    )
    char.msg("|xHiss.|n")

def _trigger_kitty_pounce(char, holder, room):
    char.db.body_language = "coiled to spring"
    cname = char.db.rp_name or char.name
    hname = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} drops into a crouch and pounces toward {hname} — fast and deliberate.|n"
    )
    char.msg("|xPounce.|n")

def _trigger_kitty_nap(char, holder, room):
    char.db.body_language = "curled up asleep"
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|x{cname} curls up and closes their eyes. Napping.|n")
    char.msg("|xNap.|n")


# ── Bunny triggers ───────────────────────────────────────────────────────

def _trigger_bunny_hop(char, holder, room):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} hops — small quick movements, nose twitching.|n"
    )
    char.msg("|xHop.|n")

def _trigger_bunny_thump(char, holder, room):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} thumps one foot against the floor — loud, emphatic, clearly displeased.|n"
    )
    char.msg("|xThump.|n")

def _trigger_bunny_groom(char, holder, room):
    char.db.body_language = "grooming"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} grooms — small precise movements, licking and smoothing.|n"
    )
    char.msg("|xGroom.|n")

def _trigger_bunny_binky(char, holder, room):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} does a full-body binky — a sudden joyful leap and twist mid-air, landing light.|n"
    )
    char.msg("|xBinky.|n")


# ── Pony triggers ────────────────────────────────────────────────────────

def _trigger_pony_walk(char, holder, room):
    char.db.body_language = "walking in place"
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|x{cname} begins a slow, measured walk — chin up, gait even.|n")
    char.msg("|xWalk.|n")

def _trigger_pony_trot(char, holder, room):
    char.db.body_language = "trotting"
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|x{cname} moves into a trot — high-stepping, precise, rhythmic.|n")
    char.msg("|xTrot.|n")

def _trigger_pony_canter(char, holder, room):
    char.db.body_language = "cantering"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} breaks into a canter — flowing and fast, making the circuit of the room.|n"
    )
    char.msg("|xCanter.|n")

def _trigger_pony_present(char, holder, room):
    char.db.body_language = "presented"
    cname  = char.db.rp_name or char.name
    hname  = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} stops and presents — weight forward, back arched, everything on display for {hname}.|n"
    )
    char.msg("|xPresent.|n")

def _trigger_pony_rest(char, holder, room):
    char.db.body_language = "at rest"
    cname = char.db.rp_name or char.name
    room.msg_contents(f"|x{cname} comes to rest — weight settled, breathing steady, waiting.|n")
    char.msg("|xRest.|n")


# ── Fox triggers ─────────────────────────────────────────────────────────

def _trigger_fox_sneak(char, holder, room):
    char.db.body_language = "sneaking"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} drops low and begins moving — quiet, deliberate, barely visible.|n"
    )
    char.msg("|xSneak.|n")

def _trigger_fox_pounce(char, holder, room):
    cname = char.db.rp_name or char.name
    hname = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} pounces — launching fast and landing close, playful and sharp.|n"
    )
    char.msg("|xPounce.|n")

def _trigger_fox_yip(char, holder, room):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} yips — a sharp, bright sound, entirely without apology.|n"
    )
    char.msg("|xYip.|n")

def _trigger_fox_curl(char, holder, room):
    char.db.body_language = "curled up tight"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} curls up — tight and compact, tail tucked in if they have one.|n"
    )
    char.msg("|xCurl.|n")

def _trigger_fox_groom(char, holder, room):
    char.db.body_language = "grooming"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} grooms — methodical, unbothered, licking their hands and smoothing their hair.|n"
    )
    char.msg("|xGroom.|n")


# ── Orgasm denial release ─────────────────────────────────────────────────

# ── Piggy triggers ───────────────────────────────────────────────────────

def _trigger_piggy_wallow(char, holder, room):
    char.db.body_language = "wallowing"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} drops low and moves with the complete lack of dignity that is, apparently, the point.|n"
    )
    char.msg("|xWallow.|n")

def _trigger_piggy_root(char, holder, room):
    char.db.body_language = "rooting"
    cname = char.db.rp_name or char.name
    hname = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} presses their nose to the floor and roots toward {hname}. Persistent. Unhurried.|n"
    )
    char.msg("|xRoot.|n")

def _trigger_piggy_oink(char, holder, room):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} makes the sound they have been asked to make. It comes out right on the first try.|n"
    )
    char.msg("|xOink.|n")
    from world.forced_emote import forced_emote
    forced_emote(char, "Oink.", "say")

def _trigger_piggy_squeal(char, holder, room):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} squeals — high and involuntary and entirely undignified — and does not look like they regret it.|n"
    )
    char.msg("|xSqueal.|n")

def _trigger_piggy_grunt(char, holder, room):
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} grunts. Low. Satisfied. Like something that doesn't need more than this.|n"
    )
    char.msg("|xGrunt.|n")

def _trigger_piggy_present(char, holder, room):
    char.db.body_language = "presented low"
    cname  = char.db.rp_name or char.name
    hname  = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{cname} goes low and presents for {hname} — head down, hindquarters up, the offering entirely without reserve.|n"
    )
    char.msg("|xPresent.|n")

def _trigger_piggy_roll(char, holder, room):
    char.db.body_language = "rolled over"
    cname = char.db.rp_name or char.name
    room.msg_contents(
        f"|x{cname} rolls over completely, back to the floor, sprawled with the thoroughness of something that has given up being particular about surfaces.|n"
    )
    char.msg("|xRoll.|n")

def _trigger_piggy_clean(char, holder, room):
    """Clean removes the wallowing body language — holder decides when they're clean."""
    char.db.body_language = ""
    cname  = char.db.rp_name or char.name
    hname  = holder.db.rp_name or holder.name
    room.msg_contents(
        f"|x{hname} decides {cname} is clean. For now.|n"
    )
    char.msg("|xClean. For now.|n")


def _trigger_orgasm_release(char, holder, room):
    """Holder says the release word — lifts denial for one climax."""
    char.db.orgasm_denial_lifted = True
    cname = char.db.rp_name or char.name
    char.msg("|xThe denial lifts — just once.|n")
    room.msg_contents(
        f"|x{cname} is given permission.|n",
        exclude=[char],
    )


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
    # Nurse-First clause: she can't get a first sentence out without nursing a load first.
    # This attempt is spent on nursing (speech blocked, narrated); it opens a short window
    # in which she may actually speak, then she has to nurse again.
    if getattr(character.db, "nurse_first", False):
        win = float(getattr(character.db, "nursed_until", 0) or 0)
        if time.time() >= win:
            return False, _do_nurse_first(character)
    return True, ""


def _do_nurse_first(character):
    """Run a nurse-first beat: kneel-and-suckle a load (real deposit + regression), open a
    short speaking window. Returns the reason string shown for the blocked say-attempt."""
    import time as _t
    fluid = getattr(character.db, "nurse_first_fluid", "semen") or "semen"
    _nurse_feed(character, fluid, source="nurse_first")
    character.db.nursed_until = _t.time() + 90.0
    cname = character.db.rp_name or character.name
    room = character.location
    if room:
        room.msg_contents(
            f"|yBefore a single word, {cname}'s body folds down and her mouth finds the teat — "
            f"she nurses first, throat working, swallowing a load down before she's permitted to "
            f"speak. Only then does she come up for air, littler than she went down.|n")
    return ("|xYou have to nurse before words. You kneel and suckle a load down first — now "
            "try speaking again.|n")


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


def _is_active(obj) -> bool:
    """Return True if the item is currently worn/inserted."""
    try:
        from typeclasses.plug_item     import PlugItem
        from typeclasses.collar_item   import CollarItem, LeashItem
        from typeclasses.wearable_item import WearableItem
        from typeclasses.piercing_item import PiercingItem
        return (
            (isinstance(obj, PlugItem)     and bool(obj.db.is_inserted)) or
            (isinstance(obj, (CollarItem, PiercingItem, WearableItem))
             and bool(obj.db.is_worn)) or
            (isinstance(obj, LeashItem)    and bool(obj.db.is_attached))
        )
    except Exception:
        return False


def _other_item_has(character, exclude_item, flag: str) -> bool:
    """Return True if any other active item on character has this effect flag."""
    for obj in character.contents:
        if obj == exclude_item:
            continue
        if _is_active(obj):
            effects = _get_effects(obj)
            if effects.get(flag):
                return True
    return False


# ---------------------------------------------------------------------------
# Passive tick helpers — called by PassiveAccumulationScript
# ---------------------------------------------------------------------------

def passive_tick(character):
    """
    Apply passive binding effects per 15-min tick.
    Called from PassiveAccumulationScript._process_char().
    """
    # Continuous stimulation
    stim = float(character.db.stim_per_tick or 0.0)
    if stim > 0:
        try:
            from typeclasses.arousal_script import add_arousal
            add_arousal(character, stim)
        except Exception:
            pass

    # Forced posture enforcement
    posture = character.db.forced_posture
    if posture and character.db.body_language != posture:
        character.db.body_language = posture


# ---------------------------------------------------------------------------
# Anti-clothing check — called from WearableItem.wear()
# ---------------------------------------------------------------------------

def check_anti_clothing(character) -> tuple:
    """Returns (True, "") if clothing is allowed, (False, reason) if locked."""
    if getattr(character.db, "anti_clothing_active", False):
        return False, "|xThe binding prevents you from covering yourself.|n"
    return True, ""


# ---------------------------------------------------------------------------
# Exhibition check — used by return_appearance to bypass camouflage
# ---------------------------------------------------------------------------

def is_exhibition_active(character) -> bool:
    """Return True if exhibition effect is stripping camouflage."""
    return bool(getattr(character.db, "exhibition_active", False))
