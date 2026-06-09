"""
world/regression.py

An age-regression meter, sibling to world/conditioning.py. Hypnosis, the drugs,
the bottle, and Bethany's blanket-voice push it; at thresholds it files the adult
down into something small, soft, and dependent — vocabulary first, then grammar,
then the name, then the headspace itself.

    character.db.regression            float, 0..100+
    character.db.regression_applied    list of threshold keys already fired
    character.db.regression_permanent  bool, set once past POINT_OF_NO_RETURN
    character.db.headspace             None / "slipping" / "little" / "small"
    (the name, when taken, is backed up to facility_name_backup — the slot both
     reset paths already restore — so the floor gives the grown-up name straight back)

Design notes
------------
* Everything here is in-fiction. The OOC floor (superuser reset / force_clear /
  escape) clears ALL of it — the flags live in FACILITY_FLAGS so both reset paths
  wipe them automatically. Never gate the floor on headspace.
* It reuses the REAL systems: the speech-filter engine (baby_talk, little_talk,
  word_swap, animal_sounds), the installed-trigger engine, designation, arousal_floor,
  and forced_posture. No parallel speech/state machine.
* Like conditioning, there is no number shown to the regressed character. She feels
  small; she doesn't see a meter.
* Suggestibility (from the drugs/items) makes her slip faster — same lever
  conditioning uses, so the two systems reinforce each other.
"""

POINT_OF_NO_RETURN = 100.0


def regress(character, amount, source=None):
    """Add to the regression meter and apply any newly-crossed thresholds.
    Returns the new regression value."""
    if not character:
        return 0.0
    amt = float(amount)
    if amt > 0:
        sug = float(getattr(character.db, "suggestibility", 0) or 0)
        if sug > 0:
            amt *= 1.0 + min(sug, 20.0) * 0.03   # up to +60% at suggestibility 20
    cur = float(getattr(character.db, "regression", 0.0) or 0.0)
    new = max(0.0, cur + amt)
    character.db.regression = new
    _apply_thresholds(character, cur, new)
    return new


# (value, key, handler_name) — each fires once, the first time it's crossed.
_THRESHOLDS = [
    (15.0,  "soft",       "_reg_soft"),
    (30.0,  "vocabulary", "_reg_vocabulary"),
    (50.0,  "little",     "_reg_little"),
    (70.0,  "namegone",   "_reg_namegone"),
    (100.0, "permanent",  "_reg_permanent"),
    (140.0, "small",      "_reg_small"),
]


def _apply_thresholds(character, old_value, new_value):
    applied = list(getattr(character.db, "regression_applied", None) or [])
    for value, key, handler_name in _THRESHOLDS:
        if old_value < value <= new_value and key not in applied:
            handler = globals().get(handler_name)
            if handler:
                try:
                    handler(character)
                except Exception:
                    pass
            applied.append(key)
    character.db.regression_applied = applied


def _add_filter(character, name):
    active = list(getattr(character.db, "active_speech_filters", None) or [])
    if name not in active:
        active.append(name)
        character.db.active_speech_filters = active


def _merge_swaps(character, swaps):
    cur = dict(getattr(character.db, "word_swaps", None) or {})
    cur.update(swaps)
    character.db.word_swaps = cur


# ── Threshold handlers ─────────────────────────────────────────────────────

def _reg_soft(character):
    """First slip — the floor of the body goes warm and easy, hard to think up out of."""
    character.db.headspace = "slipping"
    existing = float(getattr(character.db, "arousal_floor", 0.0) or 0.0)
    character.db.arousal_floor = max(existing, 15.0)
    try:
        from world.binding_effects import install_trigger
        install_trigger(character, "good baby", response="blank", strength=1)
    except Exception:
        pass
    character.msg(
        "|xSomething in your shoulders comes loose that you didn't know you were holding. "
        "The room feels a size too big, the chair a little too tall, and it is so much easier "
        "to let the next thought be a small one. Just for now. Just to rest.|n"
    )


def _reg_vocabulary(character):
    """The big words stop coming first — the mouth rounds them off small."""
    _add_filter(character, "baby_talk")
    _merge_swaps(character, {"yes": "otay", "okay": "otay", "hello": "hi", "stop": "nuh-uh"})
    character.db.headspace = "slipping"
    character.msg(
        "|xYou reach for a grown-up word and a smaller, softer one is already in your mouth "
        "instead, rounder at the edges, easier to say. You hear yourself a beat late and the gap "
        "between what you meant and what came out has stopped feeling worth closing.|n"
    )


def _reg_little(character):
    """Little headspace settles in — the body curls small, the wanting goes simple."""
    character.db.headspace = "little"
    character.db.forced_posture = "curled small — knees up, thumb-close, looking up to be told"
    character.db.body_language  = "little — small in the shoulders, watching for the next instruction"
    _merge_swaps(character, {"I": "me", "myself": "me", "want": "wan"})
    try:
        from world.binding_effects import install_trigger
        install_trigger(character, "be little for bethany", response="blank", strength=2,
                        mantra="m'little, m'good, m'hers")
    except Exception:
        pass
    character.msg(
        "|xIt's nicer down here. Smaller. The decisions are somebody else's and that's the best "
        "part — you don't have to be the one who knows things. You just have to be good, and "
        "be little, and wait to be told. Your body folds itself down to fit the feeling.|n"
    )


def _reg_namegone(character):
    """The name goes — too big a thing for what's left; she answers to 'little one'."""
    # Reuse the facility's name-backup slot so both reset paths already restore it.
    if not getattr(character.db, "facility_name_backup", None):
        character.db.facility_name_backup = character.db.rp_name or character.key
    if not getattr(character.db, "designation", None):
        character.db.designation = "Bethany's little one"
    character.db.rp_name = "Bethany's little one"
    _add_filter(character, "little_talk")
    _add_filter(character, "no_self_name")
    character.db.headspace = "little"
    character.msg(
        "|xSomeone uses your name and it's just a sound — too long, too grown, belonging to "
        "somebody who had to do hard things. It slides off. What's here is little, and hers, and "
        "answers to that faster and happier than the old name ever moved.|n"
    )


def _reg_permanent(character):
    """Point of no return — little sets. (Cleared only by the OOC floor.)"""
    character.db.regression_permanent = True
    try:
        from world.binding_effects import install_trigger
        for entry in list(getattr(character.db, "installed_triggers", None) or []):
            if "little" in str(entry.get("phrase", "")).lower() or entry.get("response") == "blank":
                entry["permanent"] = True
        character.db.installed_triggers = list(
            getattr(character.db, "installed_triggers", None) or [])
        install_trigger(character, "be little for bethany", response="blank", strength=3,
                        mantra="m'little, m'good, m'hers", permanent=True)
    except Exception:
        pass
    character.msg(
        "|xThere's a soft click somewhere behind your eyes, the sound of a thing being decided "
        "and then tucked in. The way down doesn't have a way back up in it anymore — not one "
        "you could find. You stopped looking for it a while ago anyway. It's warmer not to.|n"
    )


def _reg_small(character):
    """Below little — barely verbal, fully kept; words go to babble and pet-sound."""
    character.db.headspace = "small"
    _add_filter(character, "little_talk")
    _add_filter(character, "single_word")
    character.db.forced_posture = "kept small — boneless, blank, happy, waiting to be handled"
    character.msg(
        "|xThere's almost nothing to hold up now. No words worth the trouble, no day to get "
        "through, no name to answer — just warm, and held, and hers, and the small flat "
        "contentment of a thing that has everything it needs and decides none of it. Good baby. "
        "That's all that's left, and it's enough, and it's plenty.|n"
    )


# ── Hypnosis / technique entrypoints ───────────────────────────────────────

# Induction techniques — the way she walks you down. Each narrates + applies regression.
INDUCTION_TECHNIQUES = {
    "countdown": (
        "\"We're going to count down, sweetheart, and every number is a year. Ten... and "
        "you don't have to know so much. Seven... your shoulders don't fit the chair. Four... "
        "look how big my hand is. One.\" Bethany's voice does the work her cock doesn't have to. "
        "\"There she is. Hi, little one.\""),
    "bottle": (
        "She tips a warm bottle to {t}'s lips, one hand cradling the back of the skull, and "
        "watches the throat work. \"Good. Down it goes. Little ones don't argue with the bottle, "
        "and you're being so good, aren't you. So small.\" Each swallow takes another inch of the "
        "grown-up with it."),
    "blanket": (
        "Bethany wraps {t} up close, mouth at the ear, voice gone soft and slow and endless — "
        "the blanket-voice, the one that doesn't ask anything, just tells you how small you are "
        "and how safe and how hers, around and around until the words stop having edges and so "
        "do you."),
    "number": (
        "\"What number are we today?\" Bethany asks, fond, tapping {t}'s nose. She doesn't wait "
        "for an answer she knows is shrinking. \"Smaller than yesterday. We'll get you down to a "
        "nice round nothing yet — a number with no jobs in it, no name in it, just you and me and "
        "the next thing I tell you to feel.\""),
}


def induce_regression(character, amount=6.0, technique=None, room=None, source="hypnosis"):
    """Run one regression induction. Narrates the technique (to the room if given), applies
    regression, and seats a little suggestibility (the deeper she goes, the easier the next).
    Returns (new_value, technique_key)."""
    if not character:
        return 0.0, None
    import random
    key = technique or random.choice(list(INDUCTION_TECHNIQUES.keys()))
    t = character.db.rp_name or character.name
    line = INDUCTION_TECHNIQUES.get(key, "")
    if line and room:
        room.msg_contents("|G" + line.format(t=t) + "|n")
    elif line:
        character.msg("|G" + line.format(t=t) + "|n")
    new = regress(character, amount, source=source)
    try:
        character.db.suggestibility = float(getattr(character.db, "suggestibility", 0) or 0) + 0.5
    except Exception:
        pass
    return new, key


# ── Read-out (for the little's own eyes — a private status command) ─────────

# (value, label, descriptor) — how deep she's slipped, told soft, not clinical.
_REG_STAGES = [
    (0.0,   "big",        "all grown up, holding everything yourself"),
    (15.0,  "drowsy",     "soft at the edges, easy to slip"),
    (30.0,  "small words","the big words won't come; everything's rounder, simpler"),
    (50.0,  "little",     "tucked down small — no decisions, just being good"),
    (70.0,  "no-name",    "too little for your own name; you answer to little one"),
    (100.0, "set",        "the way back up isn't there anymore, and you stopped looking"),
    (140.0, "smallest",   "barely a word left; warm, held, kept, and content"),
]


def regression_stage(value):
    label, desc = _REG_STAGES[0][1], _REG_STAGES[0][2]
    for thresh, lab, d in _REG_STAGES:
        if (value or 0) >= thresh:
            label, desc = lab, d
    return label, desc


def _reg_bar(value, width=20):
    cap = POINT_OF_NO_RETURN
    frac = max(0.0, min(1.0, (value or 0) / cap)) if cap else 0.0
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled)


def regression_status(character):
    """A private read-out of how little she's gotten — for her own eyes. Returns a list of
    lines (already coloured). Soft, second-person, and honest about the depth — and always
    ends on the floor: the way out is never gated."""
    val = float(getattr(character.db, "regression", 0.0) or 0.0)
    headspace = getattr(character.db, "headspace", None)
    label, desc = regression_stage(val)
    permanent = bool(getattr(character.db, "regression_permanent", False))
    filters = [f for f in (getattr(character.db, "active_speech_filters", None) or [])
               if f in ("baby_talk", "little_talk", "single_word", "no_self_name")]
    lines = ["|M── HOW LITTLE YOU'VE GOTTEN ──|n"]
    lines.append(f"|m  headspace: |w{label}|n  |x({desc})|n")
    lines.append(f"|m  depth:     |G{_reg_bar(val)}|n  |x{val:.0f}|n")
    if headspace and headspace != label:
        lines.append(f"|m  feeling:   |w{headspace}|n")
    if filters:
        pretty = {"baby_talk": "soft mouth", "little_talk": "little-talk",
                  "single_word": "one word at a time", "no_self_name": "can't say your name"}
        lines.append("|m  speech:    |x" + ", ".join(pretty.get(f, f) for f in filters) + "|n")
    if permanent:
        lines.append("|x  (in here, this has set. it feels like it won't come back up. "
                     "that feeling is part of the play.)|n")
    # The floor — never gated, always shown here so it's never out of reach.
    lines.append("|g  the way back up is always yours: OOC reset / escape gives you your "
                 "name, your words, and your grown self back instantly, every time.|n")
    return lines
