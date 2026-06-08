"""
commands/social_commands.py

Social emote library for Re:Void.

134 emotes across 6 consent tiers, plus the CmdPermit command.

Systems implemented:
  Consent gating     — checks target's consent_flags; soft block on fail
  Mood coloring      — emote output tinted by character's current mood
  Proximity checks   — intimate requires "near"; mature/bdsm require "with"
  State persistence  — some emotes write to char.db.body_language
  Zone dishevelment  — mature+ emotes can mark zones as disheveled
  Targetless variants— every directed emote also works without a target

Consent model:
  Players set their own consent flags using the 'consent' command.
  consent_flags covers both tiers (intimate/mature/bdsm) and specific
  acts (undress/blindfold/gag/tieup/strip/examclose/restrain/claimmark).
  Per-player overrides in consent_overrides take priority over global flags.

Tiers:
  casual   — No consent check. Public interaction.
  intimate — target.db.consent_flags["intimate"] must be True.
  mature   — target.db.consent_flags["mature"] must be True. + proximity: with.
  bdsm     — target.db.consent_flags["bdsm"] must be True. + proximity: with.
  perm     — checks consent flag by emote key (e.g. "undress", "tieup").
  solo     — No target. Self-directed only.

Registration:
  Import ALL_SOCIAL_CMDS from this module and loop-add in CharacterCmdSet.
  See commands/default_cmdsets.py.
"""

from evennia.commands.default.muxcommand import MuxCommand

# -------------------------------------------------------------------
# Mood → color map
# -------------------------------------------------------------------

MOOD_COLOR_MAP = {
    "anxious":   "|y",
    "bold":      "|r",
    "content":   "|g",
    "curious":   "|y",
    "intense":   "|R",
    "melancholy":"|B",
    "playful":   "|m",
    "restless":  "|Y",
    "reverent":  "|C",
    "serene":    "|c",
    "tender":    "|M",
    "uncertain": "|w",
}

# -------------------------------------------------------------------
# Emote table
#
# Each entry: emote_key (str) -> dict
#
# Required keys:
#   tier    -- "casual"/"intimate"/"mature"/"bdsm"/"perm"/"solo"
#   solo    -- (self_msg, room_msg)
#
# Optional keys:
#   target  -- (self_msg, room_msg, target_msg)  omit for solo-only
#   prox    -- None / "near" / "with"  required proximity to target
#   zones   -- list of zone names to dishevel on the target after use
#   persist -- (db_field, value_string) written to CALLER after use
#   perm_desc  -- human-readable description shown in permission request
#
# Format tokens:
#   {n}   caller display name
#   {t}   target display name
#   {ns}  caller subject pronoun  (they/she/he)
#   {no}  caller object pronoun   (them/her/him)
#   {np}  caller possessive       (their/her/his)
#   {nr}  caller reflexive        (themselves/herself/himself)
#   {ts}  target subject pronoun
#   {to}  target object pronoun
#   {tp}  target possessive
#   {tr}  target reflexive
# -------------------------------------------------------------------

EMOTE_TABLE = {

    # ================================================================
    # CASUAL TIER -- no consent required
    # ================================================================

    "smile": {
        "tier": "casual",
        "solo": (
            [
                "You smile quietly to yourself.",
                "You smile, just slightly.",
                "Something makes you smile.",
                "A smile crosses your face — small, genuine.",
                "You smile to yourself and don't explain it.",
            ],
            [
                "{n} smiles quietly.",
                "{n} smiles — small, private.",
                "Something makes {n} smile.",
                "A smile crosses {n}'s face.",
                "{n} smiles to {nr}self.",
            ],
        ),
        "target": (
            [
                "You smile at {t}.",
                "You give {t} a quiet smile.",
                "You catch {t}'s eye and smile.",
                "You smile at {t} — easy and unhurried.",
            ],
            [
                "{n} smiles at {t}.",
                "{n} catches {t}'s eye and smiles.",
                "{n} gives {t} a quiet smile.",
                "{n} smiles at {t} — easy, genuine.",
            ],
            [
                "{n} smiles at you.",
                "{n} catches your eye and smiles.",
                "{n} gives you a quiet smile.",
                "{n} smiles at you — easy and unhurried.",
            ],
        ),
    },
    "grin": {
        "tier": "casual",
        "solo": (
            [
                "You grin.",
                "You grin to yourself.",
                "You can't quite keep the grin off your face.",
                "A grin spreads across your face.",
            ],
            [
                "{n} grins.",
                "{n} grins to {nr}self.",
                "A grin spreads across {n}'s face.",
                "{n} can't quite keep the grin off {np} face.",
            ],
        ),
        "target": (
            [
                "You grin at {t}.",
                "You flash {t} a grin.",
                "You can't help grinning at {t}.",
                "You grin at {t} — wide and unrepentant.",
            ],
            [
                "{n} grins at {t}.",
                "{n} flashes {t} a grin.",
                "{n} grins at {t} — wide and unrepentant.",
                "{n} can't help grinning at {t}.",
            ],
            [
                "{n} grins at you.",
                "{n} flashes you a grin.",
                "{n} grins at you — wide and unrepentant.",
                "{n} can't help grinning at you.",
            ],
        ),
    },
    "laugh": {
        "tier": "casual",
        "solo": (
            ["You laugh softly.", "You laugh.", "You laugh — quiet and genuine.", "Something makes you laugh."],
            ["{n} laughs.", "{n} laughs softly.", "Something makes {n} laugh.", "{n} breaks into a laugh."],
        ),
        "target": (
            ["You laugh at something {t} said.", "You laugh at {t}.", "{t} gets a laugh out of you."],
            ["{n} laughs at something {t} said.", "{n} laughs at {t}.", "{t} gets a laugh out of {n}."],
            ["{n} laughs at something you said.", "{n} laughs at you.", "You get a laugh out of {n}."],
        ),
    },
    "chuckle": {
        "tier": "casual",
        "solo": (
            ["You chuckle under your breath.", "You chuckle to yourself.", "A low chuckle escapes you."],
            ["{n} chuckles.", "{n} chuckles under {np} breath.", "A low chuckle from {n}."],
        ),
        "target": (
            ["You chuckle at {t}.", "You chuckle at something {t} did."],
            ["{n} chuckles at {t}.", "{n} chuckles at something {t} did."],
            ["{n} chuckles at you.", "{n} chuckles at something you did."],
        ),
    },
    "snicker": {
        "tier": "casual",
        "solo": (
            ["You snicker to yourself.", "You snicker. You can't help it.", "A snicker slips out."],
            ["{n} snickers.", "{n} snickers to {nr}self.", "A snicker slips out of {n}."],
        ),
        "target": (
            ["You snicker at {t}.", "You snicker — at {t}'s expense.", "You can't help snickering at {t}."],
            ["{n} snickers at {t}.", "{n} snickers — at {t}'s expense.", "{n} can't help snickering at {t}."],
            ["{n} snickers at you.", "{n} snickers — at your expense.", "{n} can't help snickering at you."],
        ),
    },
    "giggle": {
        "tier": "casual",
        "solo": (
            ["You giggle softly.", "You giggle and don't explain it.", "A soft giggle escapes you."],
            ["{n} giggles.", "{n} giggles softly.", "A soft giggle from {n}."],
        ),
        "target": (
            ["You giggle at {t}.", "You giggle at something {t} did.", "{t} makes you giggle."],
            ["{n} giggles at {t}.", "{n} giggles at something {t} did.", "{t} makes {n} giggle."],
            ["{n} giggles at you.", "{n} giggles at something you did.", "You make {n} giggle."],
        ),
    },
    "snort": {
        "tier": "casual",
        "solo": (
            ["You snort.", "You snort — it surprises even you.", "A snort escapes you."],
            ["{n} snorts.", "A snort from {n}.", "{n} snorts unexpectedly."],
        ),
        "target": (
            ["You snort at {t}.", "You can't help snorting at {t}."],
            ["{n} snorts at {t}.", "{n} can't help snorting at {t}."],
            ["{n} snorts at you.", "{n} can't help snorting at you."],
        ),
    },
    "huff": {
        "tier": "casual",
        "solo": (
            ["You huff.", "You huff — loudly.", "An audible huff from you."],
            ["{n} huffs.", "{n} huffs — loudly.", "An audible huff from {n}."],
        ),
        "target": (
            ["You huff at {t}.", "You huff in {t}'s direction.", "You huff — aimed squarely at {t}."],
            ["{n} huffs at {t}.", "{n} huffs in {t}'s direction.", "{n} huffs — aimed squarely at {t}."],
            ["{n} huffs at you.", "{n} huffs in your direction.", "{n} huffs — aimed squarely at you."],
        ),
    },
    "sigh": {
        "tier": "casual",
        "solo": (
            ["You sigh.", "You sigh — long and slow.", "A slow sigh out of you.", "You breathe out something tired."],
            ["{n} sighs.", "{n} sighs — long and slow.", "A slow sigh from {n}.", "{n} breathes out something tired."],
        ),
        "target": (
            ["You sigh at {t}.", "You let out a sigh in {t}'s direction.", "You sigh — pointed, at {t}."],
            ["{n} sighs at {t}.", "{n} lets out a sigh in {t}'s direction.", "{n} sighs — pointed, at {t}."],
            ["{n} sighs at you.", "{n} lets out a sigh in your direction.", "{n} sighs — pointed, at you."],
        ),
    },
    "groan": {
        "tier": "casual",
        "solo": (
            ["You groan.", "You groan, low and pained.", "A groan out of you.", "You groan — not dramatically, just honestly."],
            ["{n} groans.", "{n} groans, low and pained.", "A groan from {n}.", "{n} groans — honestly."],
        ),
        "target": (
            ["You groan at {t}.", "You groan — {t}'s fault, probably.", "A groan aimed at {t}."],
            ["{n} groans at {t}.", "{n} groans — {t}'s fault, probably.", "A groan aimed at {t} from {n}."],
            ["{n} groans at you.", "{n} groans — your fault, probably.", "A groan from {n}, aimed at you."],
        ),
    },
    "pout": {
        "tier": "casual",
        "solo": (
            ["You pout.", "You pout — deliberately.", "Your lower lip comes out just slightly."],
            ["{n} pouts.", "{n} pouts — deliberately.", "{n}'s lower lip comes out just slightly."],
        ),
        "target": (
            ["You pout at {t}.", "You turn a pout on {t}.", "You give {t} the full pout."],
            ["{n} pouts at {t}.", "{n} turns a pout on {t}.", "{n} gives {t} the full pout."],
            ["{n} pouts at you.", "{n} turns a pout on you.", "{n} gives you the full pout."],
        ),
    },
    "beam": {
        "tier": "casual",
        "solo": (
            ["You beam.", "Your whole face lights up.", "You beam — you can't help it."],
            ["{n} beams.", "{n}'s whole face lights up.", "{n} beams — can't help it."],
        ),
        "target": (
            ["You beam at {t}.", "You light up when you look at {t}.", "You beam — all of it aimed at {t}."],
            ["{n} beams at {t}.", "{n} lights up when {ns} looks at {t}.", "{n} beams — all of it aimed at {t}."],
            ["{n} beams at you.", "{n} lights up when {ns} looks at you.", "{n} beams — all of it aimed at you."],
        ),
    },
    "smirk": {
        "tier": "casual",
        "solo": (
            ["You smirk.", "A smirk pulls at the corner of your mouth.", "You smirk — pleased about something."],
            ["{n} smirks.", "A smirk pulls at the corner of {n}'s mouth.", "{n} smirks — pleased about something."],
        ),
        "target": (
            ["You smirk at {t}.", "You direct a smirk at {t}.", "You look at {t} and smirk."],
            ["{n} smirks at {t}.", "{n} directs a smirk at {t}.", "{n} looks at {t} and smirks."],
            ["{n} smirks at you.", "{n} directs a smirk at you.", "{n} looks at you and smirks."],
        ),
    },
    "frown": {
        "tier": "casual",
        "solo": (
            ["You frown.", "Your brow furrows.", "A frown settles on your face.", "You frown at nothing in particular."],
            ["{n} frowns.", "{n}'s brow furrows.", "A frown settles on {n}'s face.", "{n} frowns at nothing in particular."],
        ),
        "target": (
            ["You frown at {t}.", "You turn a frown on {t}.", "Something about {t} makes you frown."],
            ["{n} frowns at {t}.", "{n} turns a frown on {t}.", "Something about {t} makes {n} frown."],
            ["{n} frowns at you.", "{n} turns a frown on you.", "Something about you makes {n} frown."],
        ),
    },
    "scowl": {
        "tier": "casual",
        "solo": (
            ["You scowl.", "You scowl at nothing.", "A scowl settles hard on your face."],
            ["{n} scowls.", "{n} scowls at nothing.", "A scowl settles hard on {n}'s face."],
        ),
        "target": (
            ["You scowl at {t}.", "You level a scowl at {t}.", "Your scowl lands on {t}."],
            ["{n} scowls at {t}.", "{n} levels a scowl at {t}.", "{n}'s scowl lands on {t}."],
            ["{n} scowls at you.", "{n} levels a scowl at you.", "{n}'s scowl lands on you."],
        ),
    },
    "whimper": {
        "tier": "casual",
        "solo": (
            ["You whimper softly.", "A soft whimper slips out.", "You whimper — small and quiet."],
            ["{n} whimpers.", "A soft whimper from {n}.", "{n} whimpers — small, quiet."],
        ),
        "target": (
            ["You whimper at {t}.", "You give {t} a small whimper.", "A whimper escapes you, aimed at {t}."],
            ["{n} whimpers at {t}.", "{n} gives {t} a small whimper.", "A whimper from {n}, aimed at {t}."],
            ["{n} whimpers at you.", "{n} gives you a small whimper.", "A whimper from {n}, aimed at you."],
        ),
    },
    "nod": {
        "tier": "casual",
        "solo": (
            ["You nod.", "You nod once.", "You nod — slow and deliberate.", "You give a small nod."],
            ["{n} nods.", "{n} nods once.", "{n} nods — slow and deliberate.", "{n} gives a small nod."],
        ),
        "target": (
            ["You nod at {t}.", "You give {t} a nod.", "You nod once in {t}'s direction."],
            ["{n} nods at {t}.", "{n} gives {t} a nod.", "{n} nods once in {t}'s direction."],
            ["{n} nods at you.", "{n} gives you a nod.", "{n} nods once in your direction."],
        ),
    },
    "shake": {
        "tier": "casual",
        "solo": (
            ["You shake your head.", "You shake your head — no.", "A slow shake of your head."],
            ["{n} shakes {np} head.", "{n} shakes {np} head — no.", "A slow shake of {n}'s head."],
        ),
        "target": (
            ["You shake your head at {t}.", "You shake your head — at {t}, specifically.", "A slow headshake aimed at {t}."],
            ["{n} shakes {np} head at {t}.", "{n} shakes {np} head — at {t}, specifically.", "A slow headshake from {n} aimed at {t}."],
            ["{n} shakes {np} head at you.", "{n} shakes {np} head — at you, specifically.", "A slow headshake from {n} aimed at you."],
        ),
    },
    "wink": {
        "tier": "casual",
        "solo": (
            ["You wink.", "You wink at no one in particular."],
            ["{n} winks.", "{n} winks at no one in particular."],
        ),
        "target": (
            ["You wink at {t}.", "You give {t} a slow wink.", "One eye closes briefly — aimed at {t}."],
            ["{n} winks at {t}.", "{n} gives {t} a slow wink.", "One of {n}'s eyes closes briefly — aimed at {t}."],
            ["{n} winks at you.", "{n} gives you a slow wink.", "One of {n}'s eyes closes briefly — aimed at you."],
        ),
    },
    "blink": {
        "tier": "casual",
        "solo": (
            ["You blink.", "You blink once.", "You blink — slow, processing something."],
            ["{n} blinks.", "{n} blinks once.", "{n} blinks — slow, processing something."],
        ),
        "target": (
            ["You blink at {t}.", "You blink at {t} — slowly.", "A long blink in {t}'s direction."],
            ["{n} blinks at {t}.", "{n} blinks at {t} — slowly.", "A long blink from {n} in {t}'s direction."],
            ["{n} blinks at you.", "{n} blinks at you — slowly.", "A long blink from {n} in your direction."],
        ),
    },
    "squint": {
        "tier": "casual",
        "solo": (
            ["You squint.", "Your eyes narrow slightly.", "You squint at nothing."],
            ["{n} squints.", "{n}'s eyes narrow slightly.", "{n} squints at nothing."],
        ),
        "target": (
            ["You squint at {t}.", "Your eyes narrow at {t}.", "You give {t} a slow squint."],
            ["{n} squints at {t}.", "{n}'s eyes narrow at {t}.", "{n} gives {t} a slow squint."],
            ["{n} squints at you.", "{n}'s eyes narrow at you.", "{n} gives you a slow squint."],
        ),
    },
    "stare": {
        "tier": "casual",
        "solo": (
            ["You stare into the middle distance.", "You stare at nothing.", "Your gaze goes somewhere far away."],
            ["{n} stares into the middle distance.", "{n} stares at nothing.", "{n}'s gaze goes somewhere far away."],
        ),
        "target": (
            ["You stare at {t}.", "You look at {t} and don't look away.", "Your eyes find {t} and stay there."],
            ["{n} stares at {t}.", "{n} looks at {t} and doesn't look away.", "{n}'s eyes find {t} and stay there."],
            ["{n} stares at you.", "{n} looks at you and doesn't look away.", "{n}'s eyes find you and stay there."],
        ),
    },
    "glance": {
        "tier": "casual",
        "solo": (
            ["You glance around.", "You glance about the room.", "Your eyes move briefly around the space."],
            ["{n} glances around.", "{n} glances about the room.", "{n}'s eyes move briefly around the space."],
        ),
        "target": (
            ["You glance at {t}.", "A quick look at {t}.", "Your eyes flick to {t} and away."],
            ["{n} glances at {t}.", "A quick look from {n} at {t}.", "{n}'s eyes flick to {t} and away."],
            ["{n} glances at you.", "A quick look from {n} at you.", "{n}'s eyes flick to you and away."],
        ),
    },
    "tilt": {
        "tier": "casual",
        "solo": (
            ["You tilt your head.", "Your head tilts slightly.", "You tilt your head — curious."],
            ["{n} tilts {np} head.", "{n}'s head tilts slightly.", "{n} tilts {np} head — curious."],
        ),
        "target": (
            ["You tilt your head at {t}.", "You tilt your head toward {t}.", "Your head tilts, looking at {t}."],
            ["{n} tilts {np} head at {t}.", "{n} tilts {np} head toward {t}.", "{n}'s head tilts, looking at {t}."],
            ["{n} tilts {np} head at you.", "{n} tilts {np} head toward you.", "{n}'s head tilts, looking at you."],
        ),
    },
    "cock": {
        "tier": "casual",
        "solo": (
            ["You cock your head.", "Your head cocks slightly to one side.", "You cock your head — weighing something."],
            ["{n} cocks {np} head.", "{n}'s head cocks slightly to one side.", "{n} cocks {np} head — weighing something."],
        ),
        "target": (
            ["You cock your head at {t}.", "Your head cocks at {t}.", "You cock your head toward {t}."],
            ["{n} cocks {np} head at {t}.", "{n}'s head cocks at {t}.", "{n} cocks {np} head toward {t}."],
            ["{n} cocks {np} head at you.", "{n}'s head cocks at you.", "{n} cocks {np} head toward you."],
        ),
    },
    "avert": {
        "tier": "casual",
        "solo": (
            ["You avert your eyes.", "Your eyes drop.", "You look away — deliberately."],
            ["{n} averts {np} eyes.", "{n}'s eyes drop.", "{n} looks away — deliberately."],
        ),
        "target": (
            ["You avert your eyes from {t}.", "You look away from {t}.", "Your eyes drop from {t}."],
            ["{n} averts {np} eyes from {t}.", "{n} looks away from {t}.", "{n}'s eyes drop from {t}."],
            ["{n} averts {np} eyes from you.", "{n} looks away from you.", "{n}'s eyes drop from you."],
        ),
    },
    "meet": {
        "tier": "casual",
        "solo": (
            ["You meet no one's eyes in particular.", "Your gaze settles somewhere neutral.", "You don't quite meet anyone's eyes."],
            ["{n} meets no one's eyes.", "{n}'s gaze settles somewhere neutral.", "{n} doesn't quite meet anyone's eyes."],
        ),
        "target": (
            ["You meet {t}'s eyes.", "You look directly at {t}.", "Your eyes find {t}'s and hold."],
            ["{n} meets {t}'s eyes.", "{n} looks directly at {t}.", "{n}'s eyes find {t}'s and hold."],
            ["{n} meets your eyes.", "{n} looks directly at you.", "{n}'s eyes find yours and hold."],
        ),
    },
    "liftchin": {
        "tier": "casual",
        "solo": (
            ["You lift your chin.", "Your chin comes up.", "You lift your chin — composed."],
            ["{n} lifts {np} chin.", "{n}'s chin comes up.", "{n} lifts {np} chin — composed."],
        ),
        "target": (
            ["You lift your chin toward {t}.", "Your chin tilts up toward {t}.", "You lift your chin in {t}'s direction."],
            ["{n} lifts {np} chin toward {t}.", "{n}'s chin tilts up toward {t}.", "{n} lifts {np} chin in {t}'s direction."],
            ["{n} lifts {np} chin toward you.", "{n}'s chin tilts up toward you.", "{n} lifts {np} chin in your direction."],
        ),
    },
    "duckhead": {
        "tier": "casual",
        "solo": (
            ["You duck your head.", "Your head dips.", "You duck your head — away from something."],
            ["{n} ducks {np} head.", "{n}'s head dips.", "{n} ducks {np} head — away from something."],
        ),
        "target": (
            ["You duck your head away from {t}.", "Your head dips away from {t}.", "You duck your head from {t}'s gaze."],
            ["{n} ducks {np} head from {t}.", "{n}'s head dips away from {t}.", "{n} ducks {np} head from {t}'s gaze."],
            ["{n} ducks {np} head away from you.", "{n}'s head dips away from you.", "{n} ducks {np} head from your gaze."],
        ),
    },
    "brow": {
        "tier": "casual",
        "solo": (
            ["You arch an eyebrow.", "One eyebrow goes up.", "Your brow lifts — skeptical."],
            ["{n} arches an eyebrow.", "One of {n}'s eyebrows goes up.", "{n}'s brow lifts — skeptical."],
        ),
        "target": (
            ["You arch an eyebrow at {t}.", "One eyebrow goes up at {t}.", "You lift a brow at {t}."],
            ["{n} arches an eyebrow at {t}.", "One of {n}'s eyebrows goes up at {t}.", "{n} lifts a brow at {t}."],
            ["{n} arches an eyebrow at you.", "One of {n}'s eyebrows goes up at you.", "{n} lifts a brow at you."],
        ),
    },
    "shrug": {
        "tier": "casual",
        "solo": (
            ["You shrug.", "Your shoulders rise and fall.", "You shrug — what can you do.", "A small shrug."],
            ["{n} shrugs.", "{n}'s shoulders rise and fall.", "{n} shrugs — what can {ns} do.", "A small shrug from {n}."],
        ),
        "target": (
            ["You shrug at {t}.", "You give {t} a shrug.", "Your shoulders rise — aimed at {t}."],
            ["{n} shrugs at {t}.", "{n} gives {t} a shrug.", "{n}'s shoulders rise — aimed at {t}."],
            ["{n} shrugs at you.", "{n} gives you a shrug.", "{n}'s shoulders rise — aimed at you."],
        ),
    },
    "stretch": {
        "tier": "casual",
        "solo": ("You stretch.", "{n} stretches."),
    },
    "yawn": {
        "tier": "casual",
        "solo": ("You yawn.", "{n} yawns."),
    },
    "fidget": {
        "tier": "casual",
        "solo": ("You fidget.", "{n} fidgets."),
    },
    "lean": {
        "tier": "casual",
        "persist": ("body_language", "leaning"),
        "solo": ("You lean against the nearest surface.", "{n} leans against the nearest surface."),
        "target": ("You lean toward {t}.", "{n} leans toward {t}.", "{n} leans toward you."),
    },
    "crossarms": {
        "tier": "casual",
        "persist": ("body_language", "arms crossed"),
        "solo": ("You cross your arms.", "{n} crosses {np} arms."),
    },
    "straighten": {
        "tier": "casual",
        "persist": ("body_language", ""),
        "solo": ("You straighten.", "{n} straightens."),
    },
    "adjust": {
        "tier": "casual",
        "solo": ("You adjust yourself.", "{n} adjusts."),
    },
    "shudder": {
        "tier": "casual",
        "solo": ("You shudder.", "{n} shudders."),
        "target": ("You shudder at {t}.", "{n} shudders at {t}.", "{n} shudders at you."),
    },
    "startle": {
        "tier": "casual",
        "solo": ("You startle.", "{n} startles."),
        "target": ("You startle at {t}.", "{n} startles at {t}.", "{n} startles at you."),
    },
    "pause": {
        "tier": "casual",
        "solo": ("You pause.", "{n} pauses."),
        "target": ("You pause, looking at {t}.", "{n} pauses, looking at {t}.", "{n} pauses, looking at you."),
    },
    "hesitate": {
        "tier": "casual",
        "solo": ("You hesitate.", "{n} hesitates."),
        "target": ("You hesitate, glancing at {t}.", "{n} hesitates, glancing at {t}.", "{n} hesitates, glancing at you."),
    },
    "flush": {
        "tier": "casual",
        "solo": ("You flush.", "{n} flushes."),
        "target": ("You flush at {t}.", "{n} flushes at {t}.", "{n} flushes at you."),
    },
    "exhale": {
        "tier": "casual",
        "solo": ("You exhale slowly.", "{n} exhales slowly."),
        "target": ("You exhale slowly, eyes on {t}.", "{n} exhales, eyes on {t}.", "{n} exhales, eyes on you."),
    },
    "bitelip": {
        "tier": "casual",
        "solo": ("You bite your lower lip.", "{n} bites {np} lower lip."),
        "target": ("You bite your lip, looking at {t}.", "{n} bites {np} lip, looking at {t}.", "{n} bites {np} lip, looking at you."),
    },
    "wave": {
        "tier": "casual",
        "solo": ("You wave.", "{n} waves."),
        "target": ("You wave at {t}.", "{n} waves at {t}.", "{n} waves at you."),
    },
    "bow": {
        "tier": "casual",
        "solo": ("You bow.", "{n} bows."),
        "target": ("You bow to {t}.", "{n} bows to {t}.", "{n} bows to you."),
    },
    "curtsy": {
        "tier": "casual",
        "solo": ("You curtsy.", "{n} curtsies."),
        "target": ("You curtsy to {t}.", "{n} curtsies to {t}.", "{n} curtsies to you."),
    },
    "clap": {
        "tier": "casual",
        "solo": ("You clap.", "{n} claps."),
        "target": ("You clap for {t}.", "{n} claps for {t}.", "{n} claps for you."),
    },
    "gesture": {
        "tier": "casual",
        "solo": ("You gesture vaguely.", "{n} gestures vaguely."),
        "target": ("You gesture toward {t}.", "{n} gestures toward {t}.", "{n} gestures toward you."),
    },
    "beckon": {
        "tier": "casual",
        "solo": ("You beckon to no one in particular.", "{n} beckons to no one."),
        "target": ("You beckon to {t}.", "{n} beckons to {t}.", "{n} beckons to you."),
    },
    "offer": {
        "tier": "casual",
        "solo": ("You extend your hand as if offering something.", "{n} extends {np} hand."),
        "target": ("You extend your hand toward {t}.", "{n} extends {np} hand toward {t}.", "{n} extends {np} hand toward you."),
    },
    "reach": {
        "tier": "casual",
        "solo": ("You reach toward something unseen.", "{n} reaches toward something unseen."),
        "target": ("You reach toward {t}.", "{n} reaches toward {t}.", "{n} reaches toward you."),
    },
    "pat": {
        "tier": "casual",
        "solo": ("You pat yourself absently.", "{n} pats {nr} absently."),
        "target": ("You pat {t} on the shoulder.", "{n} pats {t} on the shoulder.", "{n} pats you on the shoulder."),
    },
    "nudge": {
        "tier": "casual",
        "solo": ("You nudge the air beside you.", "{n} nudges the air."),
        "target": ("You nudge {t}.", "{n} nudges {t}.", "{n} nudges you."),
    },
    "tap": {
        "tier": "casual",
        "solo": ("You tap your fingers together.", "{n} taps {np} fingers together."),
        "target": ("You tap {t} on the shoulder.", "{n} taps {t} on the shoulder.", "{n} taps you on the shoulder."),
    },

    # ================================================================
    # INTIMATE TIER -- requires intimate consent + proximity: near
    # ================================================================

    "kiss": {
        "tier": "intimate",
        "prox": "near",
        "solo": (
            ["You press your lips briefly against nothing.", "You wet your lips.", "Your lips part slightly."],
            ["{n} pauses, lips parted.", "{n} wets {np} lips.", "{n}'s lips part briefly."],
        ),
        "target": (
            ["You kiss {t}.", "You lean in and kiss {t}.", "You kiss {t} — slow and deliberate.", "Your lips find {t}'s."],
            ["{n} kisses {t}.", "{n} leans in and kisses {t}.", "{n} kisses {t} — slow and deliberate.", "{n}'s lips find {t}'s."],
            ["{n} kisses you.", "{n} leans in and kisses you.", "{n} kisses you — slow and deliberate.", "{n}'s lips find yours."],
        ),
    },
    "cheek": {
        "tier": "intimate",
        "prox": "near",
        "solo": (
            ["You touch your own cheek.", "Your fingers brush your own cheek."],
            ["{n} touches {np} cheek.", "{n}'s fingers brush {np} own cheek."],
        ),
        "target": (
            ["You kiss {t} on the cheek.", "You press your lips to {t}'s cheek.", "A soft kiss to {t}'s cheek."],
            ["{n} kisses {t} on the cheek.", "{n} presses {np} lips to {t}'s cheek.", "A soft kiss from {n} to {t}'s cheek."],
            ["{n} kisses you on the cheek.", "{n} presses {np} lips to your cheek.", "A soft kiss from {n} to your cheek."],
        ),
    },
    "embrace": {
        "tier": "intimate",
        "prox": "near",
        "persist": ("body_language", "in an embrace"),
        "solo": ("You fold your arms around yourself.", "{n} folds {np} arms around {nr}."),
        "target": ("You embrace {t}.", "{n} embraces {t}.", "{n} embraces you."),
    },
    "hug": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You wrap your arms around yourself.", "{n} wraps {np} arms around {nr}."),
        "target": ("You hug {t}.", "{n} hugs {t}.", "{n} hugs you."),
    },
    "nuzzle": {
        "tier": "intimate",
        "prox": "near",
        "solo": (
            ["You nuzzle into your own shoulder.", "You press your face into your shoulder.", "You bury your nose in your own collar."],
            ["{n} nuzzles into {np} own shoulder.", "{n} presses {np} face into {np} shoulder.", "{n} buries {np} nose in {np} collar."],
        ),
        "target": (
            ["You nuzzle {t}.", "You press your nose into {t} and stay there.", "You nuzzle into {t} — warm and deliberate.", "Your nose finds {t}'s neck."],
            ["{n} nuzzles {t}.", "{n} presses {np} nose into {t} and stays there.", "{n} nuzzles into {t} — warm and deliberate.", "{n}'s nose finds {t}'s neck."],
            ["{n} nuzzles you.", "{n} presses {np} nose into you and stays there.", "{n} nuzzles into you — warm and deliberate.", "{n}'s nose finds your neck."],
        ),
    },
    "pressagainst": {
        "tier": "intimate",
        "prox": "near",
        "persist": ("body_language", "pressed close"),
        "solo": ("You press against the nearest surface.", "{n} presses against the nearest surface."),
        "target": ("You press against {t}.", "{n} presses against {t}.", "{n} presses against you."),
    },
    "resthead": {
        "tier": "intimate",
        "prox": "near",
        "persist": ("body_language", "resting against {t}"),
        "solo": ("You tilt your head as if seeking a shoulder.", "{n} tilts {np} head as if seeking a shoulder."),
        "target": ("You rest your head on {t}'s shoulder.", "{n} rests {np} head on {t}'s shoulder.", "{n} rests {np} head on your shoulder."),
    },
    "leaninto": {
        "tier": "intimate",
        "prox": "near",
        "persist": ("body_language", "leaning into {t}"),
        "solo": ("You lean into yourself.", "{n} leans into {nr}."),
        "target": ("You lean into {t}.", "{n} leans into {t}.", "{n} leans into you."),
    },
    "brushlips": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You part your lips briefly.", "{n} parts {np} lips briefly."),
        "target": ("You brush your lips against {t}'s.", "{n} brushes {np} lips against {t}'s.", "{n} brushes {np} lips against yours."),
    },
    "tracejaw": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You trace a line along your own jaw.", "{n} traces along {np} own jaw."),
        "target": ("You trace your fingertips along {t}'s jaw.", "{n} traces {np} fingertips along {t}'s jaw.", "{n} traces {np} fingertips along your jaw."),
    },
    "cupface": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You press your palms to your own face.", "{n} presses {np} palms to {np} face."),
        "target": ("You cup {t}'s face in your hands.", "{n} cups {t}'s face in {np} hands.", "{n} cups your face in {np} hands."),
    },
    "strokehair": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You run your fingers through your own hair.", "{n} runs {np} fingers through {np} hair."),
        "target": ("You stroke {t}'s hair.", "{n} strokes {t}'s hair.", "{n} strokes your hair."),
    },
    "holdhand": {
        "tier": "intimate",
        "prox": "near",
        "persist": ("body_language", "hand in hand with {t}"),
        "solo": ("You clasp your own hands.", "{n} clasps {np} own hands."),
        "target": ("You take {t}'s hand.", "{n} takes {t}'s hand.", "{n} takes your hand."),
    },
    "intertwine": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You interlace your own fingers.", "{n} interlaces {np} own fingers."),
        "target": ("You intertwine your fingers with {t}'s.", "{n} intertwines {np} fingers with {t}'s.", "{n} intertwines {np} fingers with yours."),
    },
    "squeeze": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You press your hands tightly together.", "{n} presses {np} hands together."),
        "target": ("You squeeze {t}'s hand.", "{n} squeezes {t}'s hand.", "{n} squeezes your hand."),
    },
    "murmur": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You murmur something too quiet to catch.", "{n} murmurs something too quiet to catch."),
        "target": ("You murmur something against {t}'s ear.", "{n} murmurs something against {t}'s ear.", "{n} murmurs something against your ear."),
    },
    "cradle": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You fold your arms as if cradling something.", "{n} folds {np} arms as if cradling something."),
        "target": ("You cradle {t} close.", "{n} cradles {t} close.", "{n} cradles you close."),
    },
    "pullclose": {
        "tier": "intimate",
        "prox": "near",
        "persist": ("body_language", "pulled close to {t}"),
        "solo": ("You reach for something that isn't there.", "{n} reaches for something that isn't there."),
        "target": ("You pull {t} close.", "{n} pulls {t} close.", "{n} pulls you close."),
    },

    # ================================================================
    # MATURE TIER -- requires mature consent + proximity: with
    # ================================================================

    "caress": {
        "tier": "mature",
        "prox": "with",
        "solo": ("You trail your fingers along your own arm.", "{n} trails {np} fingers along {np} arm."),
        "target": ("You caress {t}.", "{n} caresses {t}.", "{n} caresses you."),
        "zones": ["arms", "shoulders"],
    },
    "grazelneck": {
        "tier": "mature",
        "prox": "with",
        "solo": ("You trail your lips along the curve of your jaw.", "{n} trails {np} lips along {np} jaw."),
        "target": ("You graze your lips along {t}'s neck.", "{n} grazes {np} lips along {t}'s neck.", "{n} grazes {np} lips along your neck."),
        "zones": ["neck", "throat"],
    },
    "pressthroat": {
        "tier": "mature",
        "prox": "with",
        "solo": ("You press your lips to your own wrist.", "{n} presses {np} lips to {np} wrist."),
        "target": ("You press your lips to {t}'s throat.", "{n} presses {np} lips to {t}'s throat.", "{n} presses {np} lips to your throat."),
        "zones": ["throat", "neck"],
    },
    "nibble": {
        "tier": "mature",
        "prox": "with",
        "solo": (
            ["You bite softly at the air.", "Your teeth catch at nothing.", "You nip at the air."],
            ["{n} bites softly at the air.", "{n}'s teeth catch at nothing.", "{n} nips at the air."],
        ),
        "target": (
            ["You nibble at {t}.", "You catch {t} between your teeth — gentle.", "You nip at {t} softly."],
            ["{n} nibbles at {t}.", "{n} catches {t} between {np} teeth — gentle.", "{n} nips at {t} softly."],
            ["{n} nibbles at you.", "{n} catches you between {np} teeth — gentle.", "{n} nips at you softly."],
        ),
        "zones": ["lips", "neck"],
    },
    "biteneck": {
        "tier": "mature",
        "prox": "with",
        "solo": (
            ["You tilt your head back.", "Your head drops back.", "You expose your throat."],
            ["{n} tilts {np} head back.", "{n}'s head drops back.", "{n} exposes {np} throat."],
        ),
        "target": (
            ["You bite {t}'s neck.", "Your teeth find {t}'s neck and press in.", "You bite down on {t}'s neck — firm.", "You sink your teeth into the curve of {t}'s neck."],
            ["{n} bites {t}'s neck.", "{n}'s teeth find {t}'s neck and press in.", "{n} bites down on {t}'s neck — firm.", "{n} sinks {np} teeth into the curve of {t}'s neck."],
            ["{n} bites your neck.", "{n}'s teeth find your neck and press in.", "{n} bites down on your neck — firm.", "{n} sinks {np} teeth into the curve of your neck."],
        ),
        "zones": ["neck", "throat", "nape"],
    },
    "pullinlap": {
        "tier": "mature",
        "prox": "with",
        "persist": ("body_language", "in {t}'s lap"),
        "solo": ("You sink down.", "{n} sinks down."),
        "target": ("You pull {t} into your lap.", "{n} pulls {t} into {np} lap.", "{n} pulls you into {np} lap."),
        "zones": ["hips", "waist"],
    },
    "palm": {
        "tier": "mature",
        "prox": "with",
        "solo": ("You press your palm flat to your own chest.", "{n} presses {np} palm to {np} chest."),
        "target": ("You palm your hand slowly over {t}.", "{n} palms {np} hand over {t}.", "{n} palms {np} hand over you."),
        "zones": ["chest", "abdomen"],
    },
    "claim": {
        "tier": "mature",
        "prox": "with",
        "solo": ("You exhale low and slow.", "{n} exhales low and slow."),
        "target": ("You claim {t} with a slow, deliberate touch.", "{n} claims {t} with a slow, deliberate touch.", "{n} claims you with a slow, deliberate touch."),
        "zones": [],
    },
    "archinto": {
        "tier": "mature",
        "prox": "with",
        "persist": ("body_language", "arched into {t}"),
        "solo": ("You arch your back.", "{n} arches {np} back."),
        "target": ("You arch into {t}.", "{n} arches into {t}.", "{n} arches into you."),
        "zones": ["back", "lower_back"],
    },
    "shiverunder": {
        "tier": "mature",
        "prox": "with",
        "solo": (
            ["You shiver.", "A shiver runs through you.", "You shiver — can't stop it."],
            ["{n} shivers.", "A shiver runs through {n}.", "{n} shivers — can't stop it."],
        ),
        "target": (
            ["You shiver under {t}'s touch.", "You shiver when {t} touches you — a full body thing.", "{t} touches you and you shiver for it."],
            ["{n} shivers under {t}'s touch.", "{n} shivers when {t} touches {no} — a full body thing.", "{t} touches {n} and {ns} shivers for it."],
            ["{n} shivers under your touch.", "{n} shivers when you touch {no} — a full body thing.", "You touch {n} and {ns} shivers for it."],
        ),
        "zones": [],
    },
    "breatheagainst": {
        "tier": "mature",
        "prox": "with",
        "solo": ("You breathe out slowly.", "{n} breathes out slowly."),
        "target": ("You breathe against {t}'s skin.", "{n} breathes against {t}'s skin.", "{n} breathes against your skin."),
        "zones": ["neck", "nape"],
    },
    "slidehands": {
        "tier": "mature",
        "prox": "with",
        "solo": ("You run your hands down your own sides.", "{n} runs {np} hands down {np} sides."),
        "target": ("You slide your hands along {t}'s sides.", "{n} slides {np} hands along {t}'s sides.", "{n} slides {np} hands along your sides."),
        "zones": ["waist", "hips", "lower_back"],
    },
    "pressclose": {
        "tier": "mature",
        "prox": "with",
        "persist": ("body_language", "pressed against {t}"),
        "solo": ("You press yourself forward into nothing.", "{n} presses {ns}self forward."),
        "target": ("You press close against {t}.", "{n} presses close against {t}.", "{n} presses close against you."),
        "zones": ["chest", "hips"],
    },
    "tracecollar": {
        "tier": "mature",
        "prox": "with",
        "solo": ("You trace a slow line from your throat downward.", "{n} traces a slow line from {np} throat down."),
        "target": ("You trace along {t}'s collarbone.", "{n} traces along {t}'s collarbone.", "{n} traces along your collarbone."),
        "zones": ["throat", "chest", "shoulders"],
    },

    # ================================================================
    # BDSM TIER -- requires bdsm consent + proximity: with
    # ================================================================

    "collar": {
        "tier": "bdsm",
        "prox": "with",
        "solo": ("You reach up and touch your own throat.", "{n} reaches up and touches {np} throat."),
        "target": ("You collar {t}.", "{n} collars {t}.", "{n} collars you."),
        "zones": ["neck"],
    },
    "bindwrists": {
        "tier": "bdsm",
        "prox": "with",
        "solo": ("You press your wrists together.", "{n} presses {np} wrists together."),
        "target": ("You bind {t}'s wrists.", "{n} binds {t}'s wrists.", "{n} binds your wrists."),
        "zones": ["wrists", "hands"],
    },
    "leash": {
        "tier": "bdsm",
        "prox": "with",
        "solo": ("You grasp at your own collar.", "{n} grasps at {np} collar."),
        "target": ("You take {t} by the leash.", "{n} takes {t} by the leash.", "{n} takes you by the leash."),
        "zones": ["neck"],
    },
    "yieldto": {
        "tier": "bdsm",
        "prox": "with",
        "persist": ("body_language", "yielding to {t}"),
        "solo": ("You fold in on yourself with quiet submission.", "{n} folds with quiet submission."),
        "target": ("You yield to {t}.", "{n} yields to {t}.", "{n} yields to you."),
        "zones": [],
    },
    "kneel": {
        "tier": "bdsm",
        "prox": "with",
        "persist": ("body_language", "kneeling"),
        "solo": ("You kneel.", "{n} kneels."),
        "target": ("You kneel before {t}.", "{n} kneels before {t}.", "{n} kneels before you."),
        "zones": [],
    },
    "grip": {
        "tier": "bdsm",
        "prox": "with",
        "solo": ("You tighten your hands into fists.", "{n} tightens {np} hands into fists."),
        "target": ("You grip {t} firmly.", "{n} grips {t} firmly.", "{n} grips you firmly."),
        "zones": ["arms", "wrists", "hips"],
    },
    "holddown": {
        "tier": "bdsm",
        "prox": "with",
        "solo": ("You press yourself down.", "{n} presses {ns}self down."),
        "target": ("You hold {t} down.", "{n} holds {t} down.", "{n} holds you down."),
        "zones": ["shoulders", "wrists", "hips"],
    },
    "command": {
        "tier": "bdsm",
        "prox": "with",
        "solo": ("Your voice drops to something low and certain.", "{n}'s voice drops to something low and certain."),
        "target": ("You command {t} with quiet authority.", "{n} commands {t} with quiet authority.", "{n} commands you with quiet authority."),
        "zones": [],
    },
    "markbody": {
        "tier": "bdsm",
        "prox": "with",
        "solo": ("You press your fingernails into your own palm.", "{n} presses {np} fingernails into {np} palm."),
        "target": ("You mark {t}.", "{n} marks {t}.", "{n} marks you."),
        "zones": ["neck", "throat", "shoulders"],
    },
    "pin": {
        "tier": "bdsm",
        "prox": "with",
        "solo": ("You press yourself against the wall.", "{n} presses {ns}self against the wall."),
        "target": ("You pin {t}.", "{n} pins {t}.", "{n} pins you."),
        "zones": ["shoulders", "wrists"],
    },

    # ================================================================
    # PERMISSION TIER -- requires explicit consent flag by emote key
    # ================================================================

    "undress": {
        "tier": "perm",
        "prox": "with",
        "perm_desc": "undress you",
        "solo": ("You begin to undress.", "{n} begins to undress."),
        "target": ("You undress {t}.", "{n} undresses {t}.", "{n} undresses you."),
        "zones": ["chest", "shoulders", "abdomen", "waist"],
    },
    "blindfold": {
        "tier": "perm",
        "prox": "with",
        "perm_desc": "blindfold you",
        "solo": ("You cover your own eyes.", "{n} covers {np} own eyes."),
        "target": ("You blindfold {t}.", "{n} blindfolds {t}.", "{n} blindfolds you."),
        "zones": ["face", "eyes"],
    },
    "gag": {
        "tier": "perm",
        "prox": "with",
        "perm_desc": "gag you",
        "solo": ("You press your hand over your own mouth.", "{n} presses {np} hand over {np} mouth."),
        "target": ("You gag {t}.", "{n} gags {t}.", "{n} gags you."),
        "zones": ["lips", "throat"],
    },
    "tieup": {
        "tier": "perm",
        "prox": "with",
        "perm_desc": "restrain you",
        "solo": ("You cross your wrists.", "{n} crosses {np} wrists."),
        "target": ("You tie {t} up.", "{n} ties {t} up.", "{n} ties you up."),
        "zones": ["wrists", "ankles"],
    },
    "strip": {
        "tier": "perm",
        "prox": "with",
        "perm_desc": "strip you",
        "solo": ("You slip free from something at your shoulders.", "{n} slips free from {np} shoulders."),
        "target": ("You strip {t}.", "{n} strips {t}.", "{n} strips you."),
        "zones": ["chest", "hips", "legs", "back"],
    },
    "examclose": {
        "tier": "perm",
        "prox": "with",
        "perm_desc": "examine you closely",
        "solo": ("You examine your own hands closely.", "{n} examines {np} own hands closely."),
        "target": ("You examine {t} closely.", "{n} examines {t} closely.", "{n} examines you closely."),
        "zones": [],
    },
    "restrain": {
        "tier": "perm",
        "prox": "with",
        "perm_desc": "fully restrain you",
        "solo": ("You stand very still.", "{n} stands very still."),
        "target": ("You fully restrain {t}.", "{n} fully restrains {t}.", "{n} fully restrains you."),
        "zones": ["wrists", "arms", "ankles"],
    },
    "claimmark": {
        "tier": "perm",
        "prox": "with",
        "perm_desc": "leave a claim mark on you",
        "solo": ("You press your palm flat against your own chest.", "{n} presses {np} palm flat to {np} chest."),
        "target": ("You leave your claim on {t}.", "{n} leaves {np} claim on {t}.", "{n} leaves {np} claim on you."),
        "zones": ["neck", "chest", "back", "hips"],
    },

    # ================================================================
    # SOLO TIER -- no target, self-directed
    # ================================================================

    "pace": {
        "tier": "solo",
        "persist": ("body_language", "pacing"),
        "solo": ("You pace.", "{n} paces."),
    },
    "sit": {
        "tier": "solo",
        "persist": ("body_language", "seated"),
        "solo": ("You settle into a seat.", "{n} settles into a seat."),
    },
    "riseup": {
        "tier": "solo",
        "persist": ("body_language", "standing"),
        "solo": ("You rise to your feet.", "{n} rises to {np} feet."),
    },
    "curlup": {
        "tier": "solo",
        "persist": ("body_language", "curled up"),
        "solo": ("You curl up.", "{n} curls up."),
    },
    "sprawl": {
        "tier": "solo",
        "persist": ("body_language", "sprawled"),
        "solo": ("You sprawl out.", "{n} sprawls out."),
    },
    "stareup": {
        "tier": "solo",
        "solo": ("You stare up at the ceiling.", "{n} stares up at the ceiling."),
    },
    "mutter": {
        "tier": "solo",
        "solo": ("You mutter something under your breath.", "{n} mutters under {np} breath."),
    },
    "hum": {
        "tier": "solo",
        "solo": ("You hum softly to yourself.", "{n} hums softly."),
    },
    "taptemple": {
        "tier": "solo",
        "solo": ("You tap your temple slowly.", "{n} taps {np} temple."),
    },
    "tracepattern": {
        "tier": "solo",
        "solo": ("You trace an absent pattern on the nearest surface.", "{n} traces a pattern on the nearest surface."),
    },
    "hideface": {
        "tier": "solo",
        "persist": ("body_language", "face hidden"),
        "solo": ("You hide your face.", "{n} hides {np} face."),
    },
    "presshands": {
        "tier": "solo",
        "solo": ("You press your hands to your face.", "{n} presses {np} hands to {np} face."),
    },
    "tremble": {
        "tier": "solo",
        "solo": ("You tremble.", "{n} trembles."),
    },
    "brace": {
        "tier": "solo",
        "solo": ("You brace yourself.", "{n} braces {nr}."),
    },
    "closeeyes": {
        "tier": "solo",
        "persist": ("body_language", "eyes closed"),
        "solo": ("You close your eyes.", "{n} closes {np} eyes."),
    },
    "openeyes": {
        "tier": "solo",
        "persist": ("body_language", ""),
        "solo": ("You open your eyes.", "{n} opens {np} eyes."),
    },
    "sink": {
        "tier": "solo",
        "persist": ("body_language", "sunken inward"),
        "solo": ("You sink into yourself.", "{n} sinks into {nr}."),
    },
    "withdraw": {
        "tier": "solo",
        "persist": ("body_language", "withdrawn"),
        "solo": ("You withdraw slightly.", "{n} withdraws slightly."),
    },
    "drift": {
        "tier": "solo",
        "solo": ("You seem to drift for a moment.", "{n} seems to drift for a moment."),
    },
    "settle": {
        "tier": "solo",
        "solo": ("You settle.", "{n} settles."),
    },
    "flex": {
        "tier": "solo",
        "solo": ("You flex your hands.", "{n} flexes {np} hands."),
    },
    "lookaround": {
        "tier": "solo",
        "solo": ("You look around.", "{n} looks around."),
    },
    "lookup": {
        "tier": "solo",
        "solo": ("You look up.", "{n} looks up."),
    },
    "lookdown": {
        "tier": "solo",
        "solo": ("You look down.", "{n} looks down."),
    },
    "peeraround": {
        "tier": "solo",
        "solo": ("You peer around cautiously.", "{n} peers around cautiously."),
    },
    "rollshoulders": {
        "tier": "solo",
        "solo": ("You roll your shoulders.", "{n} rolls {np} shoulders."),
    },
    "crackknuckles": {
        "tier": "solo",
        "solo": ("You crack your knuckles.", "{n} cracks {np} knuckles."),
    },
    "collectself": {
        "tier": "solo",
        "solo": ("You collect yourself.", "{n} collects {nr}."),
    },
}


# -------------------------------------------------------------------
# SocialEmoteCommand base class
# -------------------------------------------------------------------

class SocialEmoteCommand(MuxCommand):
    """
    Base class for all generated social emote commands.

    Subclasses set emote_key to look up their definition in EMOTE_TABLE.

    Consent model:
      For intimate/mature/bdsm emotes, we check consent on the TARGET
      via _check_consent(), which respects both global flags and
      per-player overrides (consent_overrides).
      For perm-tier emotes, we check by emote key as the consent type.
    """

    emote_key = None
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        caller = self.caller

        # Resolve character (caller may be Account puppeting a char)
        char = (
            caller.puppet
            if hasattr(caller, "puppet") and caller.puppet
            else caller
        )
        if not char:
            self.msg("You need to be playing a character to use this.")
            return

        emote = EMOTE_TABLE.get(self.emote_key)
        if not emote:
            self.msg(f"Unknown emote: {self.emote_key}")
            return

        tier = emote.get("tier", "casual")

        # No target — fire solo
        if not self.args:
            self._fire_solo(char, emote)
            return

        # Resolve target
        wanted = self.args.strip()
        results = char.search(
            wanted,
            location=char.location,
            quiet=True,
        )
        target = (results[0] if isinstance(results, list) else results) if results else None
        # Fallback: match by rp_name in the room (covers display names that aren't
        # the character's key/alias yet — see characters.sync_rpname_aliases).
        if not target and char.location:
            wl = wanted.lower()
            people = [o for o in char.location.contents
                      if o != char and hasattr(o, "db") and getattr(o.db, "rp_name", None)]
            target = next((o for o in people if (o.db.rp_name or "").lower() == wl), None) \
                or next((o for o in people if (o.db.rp_name or "").lower().startswith(wl)), None)
        if not target:
            self.msg(f"You don't see '{wanted}' here.")
            return

        # Targeting yourself falls back to solo
        if target == char:
            self._fire_solo(char, emote)
            return

        # Only characters (including NPCs) can be targeted
        from evennia.objects.objects import DefaultCharacter
        if not isinstance(target, DefaultCharacter):
            self.msg("You can only direct that at another person.")
            return

        # --- Proximity check (soft) ---
        # Emote fires regardless, but if you're not close enough a quiet
        # note is appended so the distance reads as deliberate in the scene.
        prox_req = emote.get("prox")
        _prox_note = ""
        if prox_req and not self._check_proximity(char, target, prox_req):
            tname = target.db.rp_name or target.name
            _prox_note = f" |x(across the distance between you)|n"

        # --- Consent check ---
        # intimate/mature/bdsm check by tier name;
        # perm-tier emotes each check by their own emote key.
        if tier in ("intimate", "mature", "bdsm"):
            if not self._check_consent(char, target, tier):
                return

        if tier == "perm":
            if not self._check_consent(char, target, self.emote_key):
                return

        self._fire_targeted(char, target, emote, prox_note=_prox_note)

    # ---------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------

    def _pick_from_pool(self, char, slot, default):
        """
        Pick a message string, checking char's custom pool first.

        Args:
            char:    The acting character.
            slot:    "self" | "room" | "recv"
            default: str or list[str] — the EMOTE_TABLE default.

        Custom pools stored on char.db.emote_customs:
            {emote_key: {"self": [str,...], "room": [str,...], "recv": [str,...]}}
        """
        import random
        customs = getattr(char.db, "emote_customs", None) or {}
        pool = (customs.get(self.emote_key) or {}).get(slot)
        if pool:
            return random.choice(pool)
        if isinstance(default, (list, tuple)):
            return random.choice(default)
        return default

    def _fire_solo(self, char, emote):
        """Fire the untargeted (solo) variant of the emote."""
        solo = emote.get("solo")
        if not solo:
            self.msg("Nothing happens.")
            return
        self_msg, room_msg = solo
        self_msg = self._pick_from_pool(char, "self", self_msg)
        room_msg = self._pick_from_pool(char, "room", room_msg)
        color = self._mood_color(char)
        name = char.db.rp_name or char.name
        pron = self._pronouns(char)
        self_msg = self._fmt(self_msg, name=name, pron=pron)
        room_msg = self._fmt(room_msg, name=name, pron=pron)
        self.msg(f"{color}{self_msg}|n")
        if char.location:
            char.location.msg_contents(
                f"{color}{room_msg}|n",
                exclude=char,
            )
        self._persist(char, emote, target=None)
        self._track_forming_social(char)

    def _fire_targeted(self, char, target, emote, prox_note=""):
        """Fire the targeted variant of the emote."""
        target_data = emote.get("target")
        if not target_data:
            self._fire_solo(char, emote)
            return
        t_self, t_room, t_recv = target_data
        t_self = self._pick_from_pool(char, "self", t_self)
        t_room = self._pick_from_pool(char, "room", t_room)
        t_recv = self._pick_from_pool(char, "recv", t_recv)
        color = self._mood_color(char)
        name = char.db.rp_name or char.name
        tname = target.db.rp_name or target.name
        pron = self._pronouns(char)
        tpron = self._pronouns(target)
        t_self = self._fmt(t_self, name=name, tname=tname,
                           pron=pron, tpron=tpron)
        t_room = self._fmt(t_room, name=name, tname=tname,
                           pron=pron, tpron=tpron)
        t_recv = self._fmt(t_recv, name=name, tname=tname,
                           pron=pron, tpron=tpron)
        self.msg(f"{color}{t_self}|n{prox_note}")
        target.msg(f"{color}{t_recv}|n{prox_note}")
        if char.location:
            char.location.msg_contents(
                f"{color}{t_room}|n{prox_note}",
                exclude=[char, target],
            )
        for zone_name in emote.get("zones", []):
            self._dishevel_zone(target, zone_name)
        if self.emote_key in ("restrain", "tieup"):
            self._apply_restraint_grants(char, target)
        self._persist(char, emote, target=target)
        self._track_forming_social(char)

    def _track_forming_social(self, char):
        """
        If the character is in a forming room, record that they have
        used at least one social emote. Wren's ready check reads this.
        """
        try:
            if (char.location and
                    getattr(char.location.db, 'is_forming', False)):
                char.db.forming_social_used = True
        except Exception:
            pass

    def _fmt(self, text, name="", tname="", pron=None, tpron=None):
        """Substitute format tokens in emote text."""
        pron = pron or {}
        tpron = tpron or {}
        return (
            text
            .replace("{n}",  name)
            .replace("{t}",  tname)
            .replace("{ns}", pron.get("subject",   "they"))
            .replace("{no}", pron.get("object",    "them"))
            .replace("{np}", pron.get("possessive","their"))
            .replace("{nr}", pron.get("reflexive", "themselves"))
            .replace("{ts}", tpron.get("subject",   "they"))
            .replace("{to}", tpron.get("object",    "them"))
            .replace("{tp}", tpron.get("possessive","their"))
            .replace("{tr}", tpron.get("reflexive", "themselves"))
        )

    def _pronouns(self, char):
        """Return char's pronoun dict with safe defaults."""
        defaults = {
            "subject":    "they",
            "object":     "them",
            "possessive": "their",
            "reflexive":  "themselves",
        }
        stored = char.db.pronouns or {}
        defaults.update(stored)
        return defaults

    def _mood_color(self, char):
        """Return the ANSI color code for this char's current mood."""
        mood = (char.db.mood or "").lower().strip()
        return MOOD_COLOR_MAP.get(mood, "|w")

    def _check_proximity(self, char, target, prox_req):
        """
        Return True if char is at the required proximity to target.

        Uses char.db.proximity dict: {character_id: "near"/"with"}

        prox_req "near" -- level must be "near" or "with"
        prox_req "with" -- level must be "with"
        """
        level = (char.db.proximity or {}).get(target.id, "public")
        if prox_req == "near":
            return level in ("near", "with")
        if prox_req == "with":
            return level == "with"
        return True

    def _check_consent(self, actor, target, tier):
        """
        Return True if actor may use this emote on target.

        Priority (highest wins):
          1. Per-player block override on target  → deny
          2. Per-player allow override on target  → allow
          3. Global consent flag on target

        Works for both content tiers (intimate/mature/bdsm) and
        specific acts (undress/blindfold/etc).
        """
        _TIER_LABELS = {
            "intimate": "intimate content",
            "mature":   "mature content",
            "bdsm":     "BDSM content",
        }
        label = _TIER_LABELS.get(tier, tier)

        overrides = target.db.consent_overrides or {}
        blocked = overrides.get("block", {}).get(tier, set())
        allowed = overrides.get("allow", {}).get(tier, set())

        tname = target.db.rp_name or target.name

        # Per-person id OR relationship-tier (owner/lover/family/faction/hostile).
        from world.relationships import override_decision
        decision = override_decision(actor, target, allowed, blocked)
        if decision == "block":
            self.msg(
                f"You reach toward {tname}, but something holds you back. "
                f"|x({tname} has not enabled {label} with you.)|n"
            )
            return False

        if decision == "allow":
            return True

        flags = target.db.consent_flags or {}
        if not flags.get(tier, False):
            self.msg(
                f"You reach toward {tname}, but something holds you back. "
                f"|x({tname} has not enabled {label}.)|n"
            )
            return False

        return True

    def _apply_restraint_grants(self, actor, target):
        """
        Auto-grant actor consent for common followup acts after restraint.

        Called automatically when 'restrain' or 'tieup' fires on a target.
        Writes to consent_overrides (persistent) so grants survive relog.
        Also records restrained_by on target.
        """
        import copy
        RESTRAINT_UNLOCKS = ("undress", "blindfold", "gag", "strip")
        overrides = copy.deepcopy(target.db.consent_overrides or {})
        overrides.setdefault("allow", {})
        overrides.setdefault("block", {})
        for act in RESTRAINT_UNLOCKS:
            overrides["allow"].setdefault(act, set())
            overrides["allow"][act].add(actor.id)
        target.db.consent_overrides = overrides
        target.db.restrained_by = actor.id
        tname = target.db.rp_name or target.name
        actor.msg(
            f"|x(Restraint applied — you may now undress, blindfold, gag, "
            f"or strip {tname}.)|n"
        )

    def _dishevel_zone(self, target, zone_name):
        """Mark a zone on target as disheveled."""
        zones = target.db.zones or {}
        if zone_name not in zones:
            return
        zones[zone_name]["state"] = "disheveled"
        if not zones[zone_name].get("state_desc"):
            zones[zone_name]["state_desc"] = "disheveled"
        target.db.zones = zones

    def _persist(self, char, emote, target=None):
        """Write persistent body-language state to caller's db."""
        persist = emote.get("persist")
        if not persist:
            return
        field, value = persist
        if "{t}" in value:
            if not target:
                # Template needs a target name but there is none —
                # skip the persist so we don't write a broken string.
                return
            tname = target.db.rp_name or target.name
            value = value.replace("{t}", tname)
        setattr(char.db, field, value)


# -------------------------------------------------------------------
# Command factory
# -------------------------------------------------------------------

_TIER_CATEGORY = {
    "casual":   "Social",
    "intimate": "Social - Intimate",
    "mature":   "Social - Mature",
    "bdsm":     "Social - BDSM",
    "perm":     "Social - Permission",
    "solo":     "Social - Solo",
}

_TIER_NOTE = {
    "casual":
        "No consent required.",
    "intimate":
        "Requires target's intimate consent flag to be on. Proximity: near.",
    "mature":
        "Requires target's mature consent flag to be on. Proximity: with. "
        "May dishevel zones.",
    "bdsm":
        "Requires target's BDSM consent flag to be on. Proximity: with.",
    "perm":
        "Requires target's consent flag for this act to be on. Use 'consent on <act>'.",
    "solo":
        "Solo only — cannot be directed at another person.",
}


def _make_emote_cmd(emote_key, emote_def):
    """Return a MuxCommand subclass for a single emote."""
    tier = emote_def.get("tier", "casual")
    solo = emote_def.get("solo", ("", ""))
    target_data = emote_def.get("target")
    help_cat = _TIER_CATEGORY.get(tier, "Social")
    tier_note = _TIER_NOTE.get(tier, "")

    if target_data:
        usage = (
            f"    {emote_key}              {solo[0]}\n"
            f"    {emote_key} <name>       {target_data[0]}"
        )
    else:
        usage = f"    {emote_key}              {solo[0]}"

    doc = (
        f"Social emote: {emote_key}\n\n"
        f"Usage:\n{usage}\n\n"
        f"{tier_note}"
    )

    return type(
        f"CmdEmote_{emote_key}",
        (SocialEmoteCommand,),
        {
            "__doc__":       doc,
            "key":           emote_key,
            "emote_key":     emote_key,
            "locks":         "cmd:all()",
            "help_category": help_cat,
        },
    )


# Build the dict of generated command classes
_EMOTE_CLASSES = {
    key: _make_emote_cmd(key, defn)
    for key, defn in EMOTE_TABLE.items()
}


# -------------------------------------------------------------------
# CmdPermit — convenience alias into the consent system
# -------------------------------------------------------------------

class CmdPermit(MuxCommand):
    """
    Allow or disallow a specific person to perform an act on you.

    A convenience alias for 'consent allow/unblock'. Both commands write
    to the same consent system and persist until you change them.

    Usage:
        permit <name> <act|all>           -- allow this person
        permit/revoke <name> <act|all>    -- remove the allow
        permit/list                       -- show your current act-level overrides

    Examples:
        permit Seraphine undress
        permit Seraphine all
        permit/revoke Seraphine tieup
        permit/list

    Acts: undress, blindfold, gag, tieup, strip, examclose, restrain, claimmark
    """

    key = "permit"
    locks = "cmd:all()"
    help_category = "Social - Permission"

    PERM_EMOTES = [
        k for k, v in EMOTE_TABLE.items() if v.get("tier") == "perm"
    ]

    def func(self):
        import copy
        char = self.caller

        if "list" in self.switches:
            overrides = char.db.consent_overrides or {}
            allow_map = overrides.get("allow", {})
            block_map = overrides.get("block", {})
            lines = ["|wYour act-level overrides:|n"]
            for act in self.PERM_EMOTES:
                a_ids = allow_map.get(act, set())
                b_ids = block_map.get(act, set())
                parts = []
                if a_ids:
                    parts.append(f"|gallowed|n for {len(a_ids)}")
                if b_ids:
                    parts.append(f"|rblocked|n for {len(b_ids)}")
                if parts:
                    lines.append(f"  {act}: {', '.join(parts)}")
            if len(lines) == 1:
                self.msg("You have no act-level overrides set.")
            else:
                self.msg("\n".join(lines))
            return

        if not self.args:
            self.msg(
                "Usage:  permit <name> <act|all>\n"
                "        permit/revoke <name> <act|all>\n"
                "        permit/list\n\n"
                f"Acts: {', '.join(self.PERM_EMOTES)}"
            )
            return

        parts = self.args.strip().split(None, 1)
        if len(parts) < 2:
            self.msg("Usage: permit <name> <act|all>")
            return
        target_name, emote_arg = parts[0], parts[1].strip().lower()

        if emote_arg == "all":
            act_keys = self.PERM_EMOTES
        elif emote_arg in self.PERM_EMOTES:
            act_keys = [emote_arg]
        else:
            self.msg(
                f"'{emote_arg}' is not a valid act.\n"
                f"Valid: {', '.join(self.PERM_EMOTES)}, all"
            )
            return

        results = char.search(target_name, location=char.location, quiet=True)
        if not results:
            self.msg(f"You don't see '{target_name}' here.")
            return
        target = results[0] if isinstance(results, list) else results

        from typeclasses.characters import Character
        if not isinstance(target, Character):
            self.msg("You can only permit a character.")
            return
        if target == char:
            self.msg("You can't permit yourself.")
            return

        tname = target.db.rp_name or target.name
        char_name = char.db.rp_name or char.name
        overrides = copy.deepcopy(char.db.consent_overrides or {})
        overrides.setdefault("allow", {})
        overrides.setdefault("block", {})
        label = "all acts" if emote_arg == "all" else emote_arg

        if "revoke" in self.switches:
            for act in act_keys:
                overrides["allow"].get(act, set()).discard(target.id)
            char.db.consent_overrides = overrides
            self.msg(f"You remove {tname}'s permission for {label}.")
            target.msg(f"{char_name} has removed your permission for |w{label}|n.")
        else:
            for act in act_keys:
                overrides["allow"].setdefault(act, set()).add(target.id)
                overrides["block"].get(act, set()).discard(target.id)
            char.db.consent_overrides = overrides
            self.msg(f"You permit {tname} to {label}.")
            target.msg(f"{char_name} permits you to |w{label}|n.")


# -------------------------------------------------------------------
# CmdEmoteSet — player customization of emote message pools
# -------------------------------------------------------------------

class CmdEmoteSet(MuxCommand):
    """
    Customize the messages that fire when you use social emotes.

    Usage:
      emoteset                             — list emotes you have customized
      emoteset <emote>                     — show your custom variants for an emote
      emoteset <emote> <slot> add <text>   — add a variant to a slot
      emoteset <emote> <slot> clear        — remove all your custom variants for a slot
      emoteset <emote> clear               — remove all your customizations for an emote

    Slots:
      self   — what YOU see when you use the emote
      room   — what everyone else in the room sees
      recv   — what the TARGET specifically receives (targeted emotes)

    Format tokens (same as the built-in emotes):
      {n}   your display name
      {t}   your target's display name
      {ns}/{no}/{np}/{nr}   your pronouns (subject/object/possessive/reflexive)
      {ts}/{to}/{tp}/{tr}   target pronouns

    Examples:
      emoteset smile room add {n} smiles — warm and a little too wide.
      emoteset kiss recv add {n}'s lips find yours and stay there.
      emoteset nod self add You give a slow, single nod.
      emoteset smile clear

    Your custom variants are mixed into the default pool and picked randomly.
    The more variants you add, the more varied your emotes will feel.
    Use 'emoteset <emote>' with no other args to preview an emote's current pools.
    """

    key     = "emoteset"
    locks   = "cmd:all()"
    help_category = "Social"
    switch_options = ()

    _SLOTS = ("self", "room", "recv")

    def func(self):
        caller = self.caller
        char = (
            caller.puppet
            if hasattr(caller, "puppet") and caller.puppet
            else caller
        )
        args = self.args.strip()

        if not args:
            self._do_list(char)
            return

        parts = args.split(None, 1)
        emote_key = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if emote_key not in EMOTE_TABLE:
            char.msg(f"|xUnknown emote '{emote_key}'. Use 'emotes' to see the full list.|n")
            return

        # emoteset <emote> clear
        if rest == "clear":
            customs = dict(getattr(char.db, "emote_customs", None) or {})
            customs.pop(emote_key, None)
            char.db.emote_customs = customs
            char.msg(f"|wCleared all custom variants for '{emote_key}'.|n")
            return

        # emoteset <emote> — show current
        if not rest:
            self._do_show(char, emote_key)
            return

        # emoteset <emote> <slot> add <text> | <slot> clear
        slot_parts = rest.split(None, 2)
        if not slot_parts:
            char.msg("|xUsage: emoteset <emote> <slot> add <text> | <slot> clear|n")
            return

        slot = slot_parts[0].lower()
        if slot not in self._SLOTS:
            char.msg(f"|xUnknown slot '{slot}'. Use: self / room / recv|n")
            return

        subcmd = slot_parts[1].lower() if len(slot_parts) > 1 else ""
        text   = slot_parts[2] if len(slot_parts) > 2 else ""

        if subcmd == "clear":
            customs = dict(getattr(char.db, "emote_customs", None) or {})
            if emote_key in customs:
                customs[emote_key] = dict(customs[emote_key])
                customs[emote_key].pop(slot, None)
                if not customs[emote_key]:
                    customs.pop(emote_key)
            char.db.emote_customs = customs
            char.msg(f"|wCleared custom '{slot}' variants for '{emote_key}'.|n")

        elif subcmd == "add":
            if not text:
                char.msg("|xNo message text provided.|n")
                return
            customs = dict(getattr(char.db, "emote_customs", None) or {})
            customs.setdefault(emote_key, {})[slot] = (
                list(customs.get(emote_key, {}).get(slot, [])) + [text]
            )
            char.db.emote_customs = customs
            n = len(customs[emote_key][slot])
            char.msg(f"|wAdded variant #{n} to '{emote_key}' / {slot}:|n {text}")

        else:
            char.msg("|xUsage: emoteset <emote> <slot> add <text> | <slot> clear|n")

    def _do_list(self, char):
        customs = getattr(char.db, "emote_customs", None) or {}
        if not customs:
            char.msg("|xYou have no custom emote variants set. Use 'emoteset <emote> <slot> add <text>' to add some.|n")
            return
        lines = ["|wYour customized emotes:|n"]
        for key, slots in sorted(customs.items()):
            counts = ", ".join(
                f"{s}: {len(v)}" for s, v in slots.items() if v
            )
            lines.append(f"  |w{key}|n — {counts}")
        char.msg("\n".join(lines))

    def _do_show(self, char, emote_key):
        customs = (getattr(char.db, "emote_customs", None) or {}).get(emote_key, {})
        emote   = EMOTE_TABLE[emote_key]
        lines   = [f"|wEmote: {emote_key}|n  (tier: {emote.get('tier', '?')})"]
        for slot in self._SLOTS:
            pool = customs.get(slot, [])
            lines.append(f"\n  |w{slot}|n ({len(pool)} custom variant{'s' if len(pool) != 1 else ''}):")
            if pool:
                for i, v in enumerate(pool, 1):
                    lines.append(f"    |x{i}.|n {v}")
            else:
                # Show the default
                idx = {"self": 0, "room": 1, "recv": 2}[slot]
                src = emote.get("target") if slot == "recv" else emote.get("solo")
                if src and idx < len(src):
                    default = src[idx]
                    if isinstance(default, list):
                        lines.append(f"    |x(default pool — {len(default)} variant(s))|n")
                    else:
                        lines.append(f"    |x(default: {default})|n")
        char.msg("\n".join(lines))


# -------------------------------------------------------------------
# Export list for default_cmdsets.py
#
# In CharacterCmdSet.at_cmdset_creation, do:
#
#     from commands.social_commands import ALL_SOCIAL_CMDS
#     for cmd_cls in ALL_SOCIAL_CMDS:
#         self.add(cmd_cls())
# -------------------------------------------------------------------

ALL_SOCIAL_CMDS = list(_EMOTE_CLASSES.values()) + [CmdPermit, CmdEmoteSet]
