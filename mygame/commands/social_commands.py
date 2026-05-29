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
        "solo": ("You smile quietly to yourself.", "{n} smiles quietly."),
        "target": ("You smile at {t}.", "{n} smiles at {t}.", "{n} smiles at you."),
    },
    "grin": {
        "tier": "casual",
        "solo": ("You grin.", "{n} grins."),
        "target": ("You grin at {t}.", "{n} grins at {t}.", "{n} grins at you."),
    },
    "laugh": {
        "tier": "casual",
        "solo": ("You laugh softly.", "{n} laughs."),
        "target": ("You laugh at something {t} said.", "{n} laughs at something {t} said.", "{n} laughs at something you said."),
    },
    "chuckle": {
        "tier": "casual",
        "solo": ("You chuckle under your breath.", "{n} chuckles."),
        "target": ("You chuckle at {t}.", "{n} chuckles at {t}.", "{n} chuckles at you."),
    },
    "snicker": {
        "tier": "casual",
        "solo": ("You snicker to yourself.", "{n} snickers."),
        "target": ("You snicker at {t}.", "{n} snickers at {t}.", "{n} snickers at you."),
    },
    "giggle": {
        "tier": "casual",
        "solo": ("You giggle softly.", "{n} giggles."),
        "target": ("You giggle at {t}.", "{n} giggles at {t}.", "{n} giggles at you."),
    },
    "snort": {
        "tier": "casual",
        "solo": ("You snort.", "{n} snorts."),
        "target": ("You snort at {t}.", "{n} snorts at {t}.", "{n} snorts at you."),
    },
    "huff": {
        "tier": "casual",
        "solo": ("You huff.", "{n} huffs."),
        "target": ("You huff at {t}.", "{n} huffs at {t}.", "{n} huffs at you."),
    },
    "sigh": {
        "tier": "casual",
        "solo": ("You sigh.", "{n} sighs."),
        "target": ("You sigh at {t}.", "{n} sighs at {t}.", "{n} sighs at you."),
    },
    "groan": {
        "tier": "casual",
        "solo": ("You groan.", "{n} groans."),
        "target": ("You groan at {t}.", "{n} groans at {t}.", "{n} groans at you."),
    },
    "pout": {
        "tier": "casual",
        "solo": ("You pout.", "{n} pouts."),
        "target": ("You pout at {t}.", "{n} pouts at {t}.", "{n} pouts at you."),
    },
    "beam": {
        "tier": "casual",
        "solo": ("You beam.", "{n} beams."),
        "target": ("You beam at {t}.", "{n} beams at {t}.", "{n} beams at you."),
    },
    "smirk": {
        "tier": "casual",
        "solo": ("You smirk.", "{n} smirks."),
        "target": ("You smirk at {t}.", "{n} smirks at {t}.", "{n} smirks at you."),
    },
    "frown": {
        "tier": "casual",
        "solo": ("You frown.", "{n} frowns."),
        "target": ("You frown at {t}.", "{n} frowns at {t}.", "{n} frowns at you."),
    },
    "scowl": {
        "tier": "casual",
        "solo": ("You scowl.", "{n} scowls."),
        "target": ("You scowl at {t}.", "{n} scowls at {t}.", "{n} scowls at you."),
    },
    "whimper": {
        "tier": "casual",
        "solo": ("You whimper softly.", "{n} whimpers."),
        "target": ("You whimper at {t}.", "{n} whimpers at {t}.", "{n} whimpers at you."),
    },
    "nod": {
        "tier": "casual",
        "solo": ("You nod.", "{n} nods."),
        "target": ("You nod at {t}.", "{n} nods at {t}.", "{n} nods at you."),
    },
    "shake": {
        "tier": "casual",
        "solo": ("You shake your head.", "{n} shakes {np} head."),
        "target": ("You shake your head at {t}.", "{n} shakes {np} head at {t}.", "{n} shakes {np} head at you."),
    },
    "wink": {
        "tier": "casual",
        "solo": ("You wink.", "{n} winks."),
        "target": ("You wink at {t}.", "{n} winks at {t}.", "{n} winks at you."),
    },
    "blink": {
        "tier": "casual",
        "solo": ("You blink.", "{n} blinks."),
        "target": ("You blink at {t}.", "{n} blinks at {t}.", "{n} blinks at you."),
    },
    "squint": {
        "tier": "casual",
        "solo": ("You squint.", "{n} squints."),
        "target": ("You squint at {t}.", "{n} squints at {t}.", "{n} squints at you."),
    },
    "stare": {
        "tier": "casual",
        "solo": ("You stare into the middle distance.", "{n} stares into the middle distance."),
        "target": ("You stare at {t}.", "{n} stares at {t}.", "{n} stares at you."),
    },
    "glance": {
        "tier": "casual",
        "solo": ("You glance around.", "{n} glances around."),
        "target": ("You glance at {t}.", "{n} glances at {t}.", "{n} glances at you."),
    },
    "tilt": {
        "tier": "casual",
        "solo": ("You tilt your head.", "{n} tilts {np} head."),
        "target": ("You tilt your head at {t}.", "{n} tilts {np} head at {t}.", "{n} tilts {np} head at you."),
    },
    "cock": {
        "tier": "casual",
        "solo": ("You cock your head.", "{n} cocks {np} head."),
        "target": ("You cock your head at {t}.", "{n} cocks {np} head at {t}.", "{n} cocks {np} head at you."),
    },
    "avert": {
        "tier": "casual",
        "solo": ("You avert your eyes.", "{n} averts {np} eyes."),
        "target": ("You avert your eyes from {t}.", "{n} averts {np} eyes from {t}.", "{n} averts {np} eyes from you."),
    },
    "meet": {
        "tier": "casual",
        "solo": ("You meet no one's eyes in particular.", "{n} meets no one's eyes."),
        "target": ("You meet {t}'s eyes.", "{n} meets {t}'s eyes.", "{n} meets your eyes."),
    },
    "liftchin": {
        "tier": "casual",
        "solo": ("You lift your chin.", "{n} lifts {np} chin."),
        "target": ("You lift your chin toward {t}.", "{n} lifts {np} chin toward {t}.", "{n} lifts {np} chin toward you."),
    },
    "duckhead": {
        "tier": "casual",
        "solo": ("You duck your head.", "{n} ducks {np} head."),
        "target": ("You duck your head away from {t}.", "{n} ducks {np} head from {t}.", "{n} ducks {np} head away from you."),
    },
    "brow": {
        "tier": "casual",
        "solo": ("You arch an eyebrow.", "{n} arches an eyebrow."),
        "target": ("You arch an eyebrow at {t}.", "{n} arches an eyebrow at {t}.", "{n} arches an eyebrow at you."),
    },
    "shrug": {
        "tier": "casual",
        "solo": ("You shrug.", "{n} shrugs."),
        "target": ("You shrug at {t}.", "{n} shrugs at {t}.", "{n} shrugs at you."),
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
        "solo": ("You press your lips briefly against nothing.", "{n} pauses, lips parted."),
        "target": ("You kiss {t}.", "{n} kisses {t}.", "{n} kisses you."),
    },
    "cheek": {
        "tier": "intimate",
        "prox": "near",
        "solo": ("You touch your own cheek.", "{n} touches {np} cheek."),
        "target": ("You kiss {t} on the cheek.", "{n} kisses {t} on the cheek.", "{n} kisses you on the cheek."),
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
        "solo": ("You nuzzle into your own shoulder.", "{n} nuzzles into {np} own shoulder."),
        "target": ("You nuzzle {t}.", "{n} nuzzles {t}.", "{n} nuzzles you."),
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
        "solo": ("You bite softly at the air.", "{n} bites softly at the air."),
        "target": ("You nibble at {t}.", "{n} nibbles at {t}.", "{n} nibbles at you."),
        "zones": ["lips", "neck"],
    },
    "biteneck": {
        "tier": "mature",
        "prox": "with",
        "solo": ("You tilt your head back.", "{n} tilts {np} head back."),
        "target": ("You bite {t}'s neck.", "{n} bites {t}'s neck.", "{n} bites your neck."),
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
        "solo": ("You shiver.", "{n} shivers."),
        "target": ("You shiver under {t}'s touch.", "{n} shivers under {t}'s touch.", "{n} shivers under your touch."),
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
        results = char.search(
            self.args.strip(),
            location=char.location,
            quiet=True,
        )
        if not results:
            self.msg(f"You don't see '{self.args.strip()}' here.")
            return
        target = results[0] if isinstance(results, list) else results

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

    def _fire_solo(self, char, emote):
        """Fire the untargeted (solo) variant of the emote."""
        solo = emote.get("solo")
        if not solo:
            self.msg("Nothing happens.")
            return
        self_msg, room_msg = solo
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

        if actor.id in blocked:
            self.msg(
                f"You reach toward {tname}, but something holds you back. "
                f"|x({tname} has not enabled {label} with you.)|n"
            )
            return False

        if actor.id in allowed:
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
# Export list for default_cmdsets.py
#
# In CharacterCmdSet.at_cmdset_creation, do:
#
#     from commands.social_commands import ALL_SOCIAL_CMDS
#     for cmd_cls in ALL_SOCIAL_CMDS:
#         self.add(cmd_cls())
# -------------------------------------------------------------------

ALL_SOCIAL_CMDS = list(_EMOTE_CLASSES.values()) + [CmdPermit]
