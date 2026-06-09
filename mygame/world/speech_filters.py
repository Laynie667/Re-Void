"""
world/speech_filters.py

Speech filter engine for Re:Void.

Filters transform a character's spoken text before it reaches the room.
Multiple filters can be active simultaneously and stack in order.

Active filters are stored on char.db.active_speech_filters as a list of names.
Applied via binding_effects or directly by staff.

Available filters:
  third_person       — all I/me/my/mine replaced with name/pronouns
  no_names           — character names replaced with "them/they"
  single_word        — only the first word of speech survives
  honorific_required — speech blocked unless it contains the holder's honorific
  no_negatives       — words like no/don't/won't are removed or replaced
  baby_talk          — simplified vocabulary + phoneme shifts
  stutter            — configurable stutter on speech output
  whisper_only       — say is blocked; only whisper works (enforced at CmdSay level)
  cant_speak         — all speech blocked (complete silence)
  echo_holder        — speech is privately mirrored to the holder regardless of location
  third_person_coy   — speech replaced with "she/he/they says what she means" summaries
  animal_sounds      — speech replaced with appropriate pet-type vocalizations
"""

import random
import re


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def apply_speech_filters(character, text: str) -> tuple:
    """
    Apply all active speech filters to the spoken text.

    Returns:
        (filtered_text, blocked, block_reason)
        blocked=True means the speech should not go through at all.
    """
    filters = list(character.db.active_speech_filters or [])
    if not filters:
        return text, False, ""

    # Blocking filters checked first
    if "cant_speak" in filters:
        return text, True, "|xThe binding silences you completely.|n"

    if "whisper_only" in filters:
        return text, True, "|xThe binding allows only whispers. Use: whisper <target> = <text>|n"

    # Transform filters applied in order
    _FILTER_FUNCS = {
        "third_person":       _filter_third_person,
        "no_names":           _filter_no_names,
        "no_self_name":       _filter_no_self_name,
        "single_word":        _filter_single_word,
        "no_negatives":       _filter_no_negatives,
        "baby_talk":          _filter_baby_talk,
        "little_talk":        _filter_little_talk,
        "suckling":           _filter_suckling,
        "stuffed":            _filter_stuffed,
        "stutter":            _filter_stutter,
        "third_person_coy":   _filter_third_person_coy,
        "animal_sounds":      _filter_animal_sounds,
        "banned_words":       _filter_banned_words,
        "word_swap":          _filter_word_swap,
    }

    for fname in filters:
        fn = _FILTER_FUNCS.get(fname)
        if fn:
            text = fn(character, text)

    # Non-blocking side effects
    if "echo_holder" in filters:
        _side_echo_holder(character, text)

    if "echo_self" in filters:
        _side_echo_self(character, text)

    if "honorific_required" in filters:
        blocked, reason = _check_honorific(character, text)
        if blocked:
            return text, True, reason

    return text, False, ""


# ---------------------------------------------------------------------------
# Filter implementations
# ---------------------------------------------------------------------------

_FIRST_PERSON = {
    r"\bI\b":       "{name}",
    r"\bme\b":      "{obj}",
    r"\bmy\b":      "{poss}",
    r"\bmine\b":    "{poss}",
    r"\bmyself\b":  "{refl}",
    r"\bI'm\b":     "{name} is",
    r"\bI've\b":    "{name} has",
    r"\bI'll\b":    "{name} will",
    r"\bI'd\b":     "{name} would",
    r"\bI'm\b":     "{name} is",
}

def _filter_third_person(char, text: str) -> str:
    """Replace first-person pronouns with name and third-person pronouns."""
    name = char.db.rp_name or char.name
    pron = char.db.pronouns or {}
    subst = {
        "{name}": name,
        "{obj}":  pron.get("object",     "them"),
        "{poss}": pron.get("possessive",  "their"),
        "{refl}": pron.get("reflexive",   "themselves"),
    }
    for pattern, replacement in _FIRST_PERSON.items():
        rep = replacement
        for k, v in subst.items():
            rep = rep.replace(k, v)
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)
    return text


def _filter_no_names(char, text: str) -> str:
    """Replace any character names found in speech with 'them'."""
    try:
        from typeclasses.characters import Character
        room = char.location
        if not room:
            return text
        for obj in room.contents:
            if not isinstance(obj, Character) or obj == char:
                continue
            rp_name = obj.db.rp_name or obj.name
            for name_part in rp_name.split():
                if len(name_part) > 2:
                    text = re.sub(
                        rf"\b{re.escape(name_part)}\b",
                        "them",
                        text,
                        flags=re.IGNORECASE
                    )
    except Exception:
        pass
    return text


def _filter_no_self_name(char, text: str) -> str:
    """She can't speak her own name — it catches and comes out as her designation.

    Targets her real name (held in facility_name_backup when forfeited), her
    current rp_name, and her base key.
    """
    names = set()
    for n in (getattr(char.db, "facility_name_backup", None),
              getattr(char.db, "rp_name", None), char.key):
        if n:
            for part in str(n).split():
                if len(part) > 2:
                    names.add(part)
    replacement = getattr(char.db, "designation", None) or "the bitch"
    for part in sorted(names, key=len, reverse=True):
        # don't rewrite the designation into itself
        if part.lower() in replacement.lower():
            continue
        text = re.sub(rf"\b{re.escape(part)}\b", replacement, text, flags=re.IGNORECASE)
    return text


def _filter_single_word(char, text: str) -> str:
    """Keep only the first word."""
    words = text.split()
    return words[0] if words else text


_NEGATIVE_WORDS = [
    r"\bno\b", r"\bnot\b", r"\bdon't\b", r"\bdont\b", r"\bwon't\b",
    r"\bwont\b", r"\bcan't\b", r"\bcant\b", r"\bnever\b", r"\brefuse\b",
    r"\bstop\b", r"\bno\b", r"\bwon't\b", r"\bwouldn't\b", r"\bcouldn't\b",
    r"\bshouldn't\b", r"\bdidn't\b", r"\bdoesn't\b", r"\bhadn't\b",
    r"\bhasn't\b", r"\bhaven't\b", r"\bisn't\b", r"\baren't\b",
]

def _filter_no_negatives(char, text: str) -> str:
    """Strip negative words from speech."""
    for pattern in _NEGATIVE_WORDS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    # Clean double spaces
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text or "..."


_BABY_REPLACEMENTS = {
    r"\bvery\b":        "weally",
    r"\breally\b":      "weally",
    r"\bplease\b":      "pweese",
    r"\bpretty\b":      "pwetty",
    r"\bsorry\b":       "sowwy",
    r"\bfriend\b":      "fwiend",
    r"\bthank\b":       "fank",
    r"\bthanks\b":      "fanks",
    r"\bwant\b":        "wan",
    r"\bcould\b":       "couwd",
    r"\bwould\b":       "wouwd",
    r"\bsleep\b":       "sweep",
    r"\bsleepy\b":      "sweepy",
    r"\blove\b":        "wuv",
    r"\bhungry\b":      "hungwy",
    r"\bdirty\b":       "diwty",
    r"\bgood\b":        "gud",
    r"\bmore\b":        "mowe",
    r"\bmy\b":          "mwy",
    r"\bthat\b":        "dat",
    r"\bthe\b":         "da",
    r"\bthis\b":        "dis",
    r"\bthink\b":       "fink",
    r"\bthere\b":       "dere",
    r"\bbroken\b":      "bwoken",
}

def _filter_baby_talk(char, text: str) -> str:
    """Apply baby-talk phoneme substitutions."""
    for pattern, replacement in _BABY_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


_LITTLE_REPLACEMENTS = {
    r"\bI\b":       "me",
    r"\bI'm\b":     "me",
    r"\bme\b":      "me",
    r"\bmy\b":      "my",
    r"\byes\b":     "otay",
    r"\byeah\b":    "otay",
    r"\bokay\b":    "otay",
    r"\bno\b":      "nuh-uh",
    r"\bhello\b":   "hi",
    r"\bwhat\b":    "wha",
    r"\bbecause\b": "cuz",
    r"\bgoing\b":   "goin'",
    r"\bnothing\b": "nuffin",
    r"\bsomething\b": "sumfin",
    r"\bmommy\b":   "mommy",
    r"\bdaddy\b":   "mommy",
}

_LITTLE_FILLERS = ["", "", "", " ...", " — m'sleepy.", " hehe.", " ...mommy?"]

def _filter_little_talk(char, text: str) -> str:
    """Deeper than baby_talk: little-headspace speech — small words, dropped grammar,
    first-person collapses to 'me', the occasional filler/whine. Stacks on baby_talk
    (run after it). The §0 floor clears active_speech_filters."""
    # phoneme softening shared with baby talk first, then little-specific swaps
    text = _filter_baby_talk(char, text)
    for pattern, replacement in _LITTLE_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    # drop common grammar words so it comes out in toddler fragments
    text = re.sub(r"\b(am|are|is|was|were|the|a|an|to|of|will|would|that)\b", "",
                  text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if text and random.random() < 0.4:
        text = text + random.choice(_LITTLE_FILLERS)
    return text or "...?"


_SUCKLE_NOISES = [
    "*helpless wet suckling*", "*mmf...*", "*soft greedy sucking*", "*gulp*",
    "*whimpers around the teat*", "*nurses, cheeks hollowing*", "*needy little slurp*",
    "*suckles harder, eyes unfocusing*", "*muffled, mouth too full to shape a word*",
]

def _filter_suckling(char, text: str) -> str:
    """The Teat Gag: while gagged, speech comes out as suckling — and every attempt to talk
    pulls another laced mouthful into her (real deposit + regression). Self-expires on its own
    timer (teat_gag_until) so a gagged little is never left with no way to be heard; the uncork
    word ends it sooner, and the §0 floor clears it. Rides active_speech_filters."""
    import time as _t
    until = float(getattr(char.db, "teat_gag_until", 0) or 0)
    if until and _t.time() >= until:
        # The teat slips free on its own — clear the gag and let THIS line through ungagged.
        active = [f for f in (getattr(char.db, "active_speech_filters", None) or []) if f != "suckling"]
        char.db.active_speech_filters = active
        char.db.teat_gagged    = False
        char.db.teat_gag_until = 0
        char.msg("|xThe teat finally slips from your mouth on its own; your words are yours "
                 "again — for now.|n")
        return text
    # Still gagged: another pull feeds her, and only suckle-sounds come out.
    try:
        from world.binding_effects import _nurse_feed
        _nurse_feed(char, getattr(char.db, "teat_gag_fluid", "semen") or "semen", source="teat_gag")
    except Exception:
        pass
    return random.choice(_SUCKLE_NOISES)


_STUFFED_FILLERS = [
    " *around it*", " —mmf—", " *muffled*", " *drooling*", " *cock-stuffed*",
    " *thick and wet*",
]
_STUFFED_FULL = [
    "*gh-glk—* (mouth too full to talk)", "*muffled, throat working around it*",
    "*tries to speak; only manages a wet, stuffed gurgle*", "*mmmf—* (something's in the way)",
]

def _filter_stuffed(char, text: str) -> str:
    """The Stuffed-Mouth clause: a mouth trained to be a hole forgets sentences. Speech is
    cut to a few cock-muffled words — and now and then her mouth is simply found full
    mid-sentence (a wet gurgle + a swallowed-and-shrunk drip). Stacks with little_talk."""
    # ~40% chance her mouth is full right now — only a stuffed gurgle comes out, and she
    # swallows for it (a small laced drip + a touch littler).
    if random.random() < 0.40:
        try:
            from world.binding_effects import _nurse_feed
            _nurse_feed(char, getattr(char.db, "stuffed_fluid", "semen") or "semen", source="stuffed_mouth")
        except Exception:
            pass
        return random.choice(_STUFFED_FULL)
    # Otherwise: a few muffled words around whatever's seated, with a wet filler.
    words = text.split()
    keep = words[:random.randint(2, 3)]
    out = " ".join(keep)
    if random.random() < 0.6:
        out += random.choice(_STUFFED_FILLERS)
    return out or "*mmf*"


def _filter_stutter(char, text: str) -> str:
    """Apply a stutter effect — random word repetitions."""
    words = text.split()
    result = []
    for word in words:
        if len(word) > 1 and random.random() < 0.30:
            first_char = word[0]
            stutter_count = random.randint(1, 3)
            stutter = "- ".join([first_char] * stutter_count) + "- " + word
            result.append(stutter)
        else:
            result.append(word)
    return " ".join(result)


def _filter_third_person_coy(char, text: str) -> str:
    """Replace speech with a coy third-person summary."""
    name = char.db.rp_name or char.name
    pron = char.db.pronouns or {}
    subj = pron.get("subject", "they")
    summaries = [
        f"{name} says what {subj} means.",
        f"{name} expresses {pron.get('possessive', 'their')} thoughts indirectly.",
        f"{name} says something. It is meaningful.",
        f"{name} chooses words carefully.",
        f"{subj.capitalize()} speaks.",
    ]
    return random.choice(summaries)


_PET_VOCALIZATIONS = {
    "puppy": ["*woof*", "*bark*", "*whimper*", "*arf*", "*yip*"],
    "kitty": ["*mrrrow*", "*mew*", "*hiss*", "*purr*", "*chirp*"],
    "bunny": ["*thump*", "*squeak*", "...", "*nose twitch*"],
    "pony":  ["*nicker*", "*snort*", "*whinny*", "*huff*"],
    "fox":   ["*yip*", "*chitter*", "*bark*", "*chirp*"],
}

def _filter_animal_sounds(char, text: str) -> str:
    """Replace speech with the appropriate pet vocalization."""
    pet_type = getattr(char.db, "pet_type", "puppy") or "puppy"
    sounds   = _PET_VOCALIZATIONS.get(pet_type, _PET_VOCALIZATIONS["puppy"])
    return random.choice(sounds)


def _check_honorific(char, text: str) -> tuple:
    """Return (blocked, reason) if honorific is required but absent."""
    required = getattr(char.db, "required_honorific", "") or ""
    if not required:
        return False, ""
    if required.lower() in text.lower():
        return False, ""
    return True, (
        f"|xYou remember the correct form of address. ({required})|n"
    )


_ECHO_SELF_FRAMES = [
    "|x  …and a beat later your own voice comes back at you, flat and patient, in your own head: "
    "\"{text}\" — and it lands a little truer the second time, the way a thing does when you've "
    "said it about yourself.|n",
    "|x  The Echo returns it to you in your own voice, unhurried: \"{text}\". You hear how it sounds "
    "coming from you, and something in you files it as fact.|n",
    "|x  Your words loop back through you a moment after you let them go — \"{text}\" — repeated in "
    "your own voice until the saying and the being-true blur at the edges.|n",
    "|x  \"{text}\" — it echoes back off the inside of your skull in your own tone, and each return "
    "wears the groove a little deeper. You taught yourself that, just now. You keep teaching yourself.|n",
]


def _filter_banned_words(char, text: str) -> str:
    """Configurable conditioning: a list of words the character has been conditioned out of
    saying. Each is struck from her speech (whole-word, case-insensitive). Set per-character
    on char.db.banned_words (a list). The conditioner picks the list; the §0 floor clears it."""
    try:
        banned = list(getattr(char.db, "banned_words", None) or [])
        for w in banned:
            w = (w or "").strip()
            if not w:
                continue
            text = re.sub(rf"\b{re.escape(w)}\b", "—", text, flags=re.IGNORECASE)
    except Exception:
        pass
    return text


def _filter_word_swap(char, text: str) -> str:
    """Configurable conditioning: a mapping of words she's been retrained to say in place of
    others (e.g. 'no'->'yes', 'I'->'this unit', her own name->her designation). Set on
    char.db.word_swaps as a dict {from: to}. Whole-word, case-insensitive."""
    try:
        swaps = dict(getattr(char.db, "word_swaps", None) or {})
        for frm, to in swaps.items():
            frm = (frm or "").strip()
            if not frm:
                continue
            text = re.sub(rf"\b{re.escape(frm)}\b", str(to), text, flags=re.IGNORECASE)
    except Exception:
        pass
    return text


def _side_echo_self(char, text: str):
    """The 'Echo' curse: re-deliver the character's own spoken words back to her a beat
    after she says them, in her own voice — and let the repetition condition her own words
    into her (a small conditioning drip). She is made to agree with herself."""
    try:
        if not (text or "").strip():
            return
        import random
        frame = random.choice(_ECHO_SELF_FRAMES).format(text=text.strip())
        char.msg(frame)
        from world.conditioning import add_conditioning
        add_conditioning(char, 0.6, source="echo")
    except Exception:
        pass


def _side_echo_holder(char, text: str):
    """Mirror spoken text privately to the character's holder, wherever they are."""
    try:
        holder_id = char.db.led_by
        if not holder_id:
            return
        from evennia import search_object
        results = search_object(f"#{holder_id}", exact=True)
        if results:
            holder = results[0]
            cname  = char.db.rp_name or char.name
            holder.msg(f"|x[echo — {cname}]:|n {text}")
    except Exception:
        pass
