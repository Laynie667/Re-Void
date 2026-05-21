"""
commands/rp_commands.py

Core RP communication commands for Re:Void.

Commands:
    say / "     -- in-character speech; uses char.db.say_verb
    pose / :    -- third-person narrative action (name + space + text)
    emote / ; @ -- freeform emote (name prepended with NO space)
    pmote       -- pronoun-substituted pose (%n %p %o %s)
    whisper     -- private message to one person in the room
    mutter      -- audible but indistinct speech
    shout       -- speech that carries to adjacent rooms
    aside       -- soft speech heard only at near/with proximity
    ooc         -- in-scene OOC comment (bracketed); no-arg = return to wisp
    tbf         -- to be felt — physical sensation pose
    spoof / sp  -- emit text to room with no attribution

Mood coloring:
    All output is tinted by the speaker's current mood color.

Output format summary:
    say Hello.            ->  Seraphine says, "Hello."
    :smiles.              ->  Seraphine smiles.
    ;'s hands shake.      ->  Seraphine's hands shake.
    pmote %n smiles.      ->  Seraphine smiles.
    whisper Ara = Hi      ->  [private] / room sees vague notice
    mutter Something...   ->  fragments shown to room
    shout Hello!          ->  current + adjacent rooms
    aside Hmm.            ->  near/with proximity only
    ooc brb a sec         ->  [OOC: Seraphine: brb a sec]
    tbf The air hums.     ->  [felt] The air hums.
    spoof The door rattles.  ->  The door rattles.
"""

from evennia.commands.default.muxcommand import MuxCommand
from commands.social_commands import MOOD_COLOR_MAP


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _name(char):
    """Return the character's RP name, falling back to their key."""
    return char.db.rp_name or char.name


def _second_person_verb(verb):
    """
    Convert a 3rd-person singular verb to its 2nd-person form for 'You ...' messages.

    Examples:
        says     → say
        murmurs  → murmur
        hisses   → hiss
        watches  → watch
        cries    → cry
        drawls   → drawl
    """
    v = verb.lower()
    if v.endswith("ies") and len(v) > 3:
        return v[:-3] + "y"                          # cries → cry
    if v.endswith(("sses", "ches", "shes", "xes", "zes")):
        return v[:-2]                                 # hisses → hiss, watches → watch
    if v.endswith("s") and not v.endswith("ss"):
        return v[:-1]                                 # says → say, murmurs → murmur
    return v                                          # already base form


def _mood_color(char):
    """Return the Evennia color code for the character's current mood."""
    mood = (char.db.mood or "").lower().strip()
    return MOOD_COLOR_MAP.get(mood, "|w")


def _ends_with_punctuation(text):
    """True if text already ends with a sentence-final mark."""
    return text.endswith((".", "!", "?", "...", "—"))


# -------------------------------------------------------------------
# Zone targeting helpers (look/examine <target> <zone>)
# -------------------------------------------------------------------

def _render_zone_target(char, target, zone_name, zone_data, deep=False):
    """
    Render a focused single-zone view for zone-targeted look/examine.

    Args:
        char:      The looking character.
        target:    The target character or NPC.
        zone_name: Canonical zone key (underscore-separated).
        zone_data: Zone dict (already flattened from _SaverDict).
        deep:      True if called from examine (shows interior on orifice zones).

    Returns:
        str: Formatted zone output, or an access-denied message.
    """
    visibility = zone_data.get("visibility", "look")
    intimate   = zone_data.get("intimate", False)
    is_self    = (char == target)

    # Hidden zones — never shown via direct targeting
    if visibility == "hidden":
        return "|xYou don't notice anything particular about that.|n"

    # Proximity-gated zones — require near/with
    if visibility == "proximity" and not is_self:
        is_near = False
        try:
            prox = getattr(target.db, "proximity", None) or {}
            for pid, plevel in prox.items():
                try:
                    if int(pid) == char.id and plevel in ("near", "with"):
                        is_near = True
                        break
                except (ValueError, TypeError):
                    pass
            if not is_near and hasattr(char, "db"):
                looker_prox = char.db.proximity or {}
                for pid, plevel in looker_prox.items():
                    try:
                        if int(pid) == target.id and plevel in ("near", "with"):
                            is_near = True
                            break
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass
        if not is_near:
            return "|xYou'd need to get closer to notice that.|n"

    # Consent-gated zones (visibility == "consent" OR intimate flag)
    if not is_self and (visibility == "consent" or intimate):
        # For full characters: use their consent system
        has_consent = False
        if hasattr(target, "_looker_has_consent"):
            has_consent = target._looker_has_consent(
                char, "intimate", zone_name=zone_name
            )
        else:
            # For NPCs without the consent method, check consent_flags
            npc_flags = getattr(target.db, "consent_flags", None) or {}
            has_consent = bool(npc_flags.get("intimate", False))
        if not has_consent:
            return "|xYou don't have consent to look there.|n"

    # Build the view
    target_name  = (target.db.rp_name if (hasattr(target.db, "rp_name")
                    and target.db.rp_name) else target.key)
    zone_display = zone_name.replace("_", " ")
    nude_desc    = (zone_data.get("nude") or "").strip()

    lines = [f"|w{target_name}|n — |x{zone_display}|n"]
    lines.append("|w" + "─" * 36 + "|n")

    if nude_desc:
        lines.append(nude_desc)
    else:
        lines.append("|xNothing particularly notable here.|n")

    # Interior desc on examine — orifice/both zones with mature consent
    if deep:
        interior  = (zone_data.get("interior") or "").strip()
        zone_type = zone_data.get("zone_type", "surface")
        if interior and zone_type in ("orifice", "both"):
            has_mature = is_self
            if not has_mature:
                if hasattr(target, "_looker_has_consent"):
                    has_mature = target._looker_has_consent(
                        char, "mature", zone_name=zone_name
                    )
                else:
                    npc_flags = getattr(target.db, "consent_flags", None) or {}
                    has_mature = bool(npc_flags.get("mature", False))
            if has_mature:
                lines.append(f"|x[interior] {interior}|n")

    return "\n".join(lines)


def _try_zone_target(char, args, deep=False):
    """
    Try to interpret args as '<target> <zone>' and render a zone view.

    Attempts splits from right to left (1-word zone first, then 2-word zone)
    to support both 'look laynie face' and 'look laynie lower back'.

    Args:
        char:  The character issuing the command.
        args:  The full argument string (already stripped of 'at ').
        deep:  True if called from examine.

    Returns:
        str or None: Rendered zone output, or None if no match found.
    """
    words = args.split()
    if len(words) < 2:
        return None

    # Try zone = last N words, target = first len-N words (N = 1, then 2)
    for zone_word_count in (1, 2):
        if zone_word_count >= len(words):
            continue
        target_str = " ".join(words[:-zone_word_count])
        zone_str   = "_".join(words[-zone_word_count:]).lower()

        target = char.search(target_str, quiet=True)
        if isinstance(target, list):
            target = target[0] if target else None
        if not target:
            continue

        # Get zones dict — Characters use _get_zones(), NPCs use db.zones
        if hasattr(target, "_get_zones"):
            zones_raw = target._get_zones()
        else:
            zones_raw = getattr(target.db, "zones", None) or {}

        if not zones_raw:
            continue

        # Find matching zone key (case-insensitive)
        matched_name = None
        zone_data    = None
        for zkey in list(zones_raw.keys()):
            if zkey.lower() == zone_str:
                matched_name = zkey
                zone_data    = zones_raw[zkey]
                break

        if not matched_name:
            continue

        # Flatten _SaverDict to plain dict
        if hasattr(zone_data, "items"):
            zone_data = {k: v for k, v in zone_data.items()}

        return _render_zone_target(char, target, matched_name, zone_data, deep=deep)

    return None


def _mutter_fragment(text):
    """
    Return a partial version of 'text' for use in mutter output.
    Shows the first third of words plus a trailing fragment.
    """
    words = text.split()
    if len(words) <= 2:
        return "..."
    visible = max(1, len(words) // 3)
    fragment = " ".join(words[:visible])
    if len(words) > visible + 1:
        fragment += " ... " + words[-1]
    return fragment



# -------------------------------------------------------------------
# CmdSay
# -------------------------------------------------------------------

class CmdSay(MuxCommand):
    """
    Speak in character.

    Uses your character's say verb (set with 'setsayverb').
    Default verb is 'says'. Mood colors your speech.

    Usage:
      say <message>
      "<message>

    Examples:
      say Hello, is anyone there?
      "I don't think so.

    The opening quote is added automatically — don't include it.

    See also: whisper, mutter, shout, aside, pose, setsayverb
    """

    key = "say"
    aliases = ['"']
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg('Say what? Usage: say <message>  or  "<message>')
            return

        # Strip any explicit quotes the player typed themselves
        text = self.args.strip().strip('"').strip("'")
        if not text:
            self.msg("Say what?")
            return

        name = _name(char)
        color = _mood_color(char)
        verb = char.db.say_verb or "says"
        verb_2nd = _second_person_verb(verb)

        room_msg = f'{color}{name} {verb}, "{text}"|n'

        self.msg(f'{color}You {verb_2nd}, "{text}"|n')
        if char.location:
            char.location.msg_contents(room_msg, exclude=char)
            char.location.append_scene_log(name, room_msg)

            # Parrot mechanic — call on_hear_say on NPCs that want it
            for obj in char.location.contents:
                if (hasattr(obj, 'on_hear_say') and
                        getattr(obj.db, 'react_to_say', False)):
                    try:
                        obj.on_hear_say(char, text)
                    except Exception:
                        pass


# -------------------------------------------------------------------
# CmdPose
# -------------------------------------------------------------------

class CmdPose(MuxCommand):
    """
    Perform a third-person narrative action.

    Your name is prepended with a space before your text.
    Everyone in the room — including you — sees the full pose.

    Usage:
      pose <action>
      :<action>

    Examples:
      pose settles into the nearest chair.
      :turns toward the door, listening.

    Mood colors your pose.

    See also: emote, pmote, say, spoof
    """

    key = "pose"
    aliases = [":"]
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg("Pose what? Usage: pose <action>  or  :<action>")
            return

        text = self.args.strip()
        name = _name(char)
        color = _mood_color(char)

        # Add a period if the pose doesn't end with punctuation
        if not _ends_with_punctuation(text):
            text += "."

        msg = f"{color}{name} {text}|n"

        if char.location:
            char.location.msg_contents(msg)
            char.location.append_scene_log(name, msg)
        else:
            self.msg(msg)


# -------------------------------------------------------------------
# CmdEmote
# -------------------------------------------------------------------

class CmdEmote(MuxCommand):
    """
    Freeform emote — your name is prepended with NO space.

    Use this when your name needs to flow directly into the text,
    such as possessives or mid-name constructions.

    Usage:
      emote <text>
      ;<text>
      @<text>

    Examples:
      ;'s gaze drifts toward the window.
        -> Seraphine's gaze drifts toward the window.

      ; turns away, shoulders tight.
        -> Seraphine turns away, shoulders tight.

    Note the space (or lack of it) after the semicolon — that
    controls whether it reads as a possessive or an action.

    Mood colors your emote.

    See also: pose, say, spoof, pmote
    """

    key = "emote"
    aliases = [";", "@"]
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg(
                "Emote what? Usage: emote <text>  or  ;<text>\n"
                "Example: ;'s hands tremble.  ->  Seraphine's hands tremble."
            )
            return

        # No strip on leading whitespace — player controls the spacing
        text = self.args
        name = _name(char)
        color = _mood_color(char)

        if not _ends_with_punctuation(text.rstrip()):
            text = text.rstrip() + "."

        msg = f"{color}{name}{text}|n"

        if char.location:
            char.location.msg_contents(msg)
            char.location.append_scene_log(name, msg)
        else:
            self.msg(msg)


# -------------------------------------------------------------------
# CmdPmote
# -------------------------------------------------------------------

class CmdPmote(MuxCommand):
    """
    Send a private pose to one person in the room.

    The target sees your name and the pose text. The room sees nothing.
    Use for quiet physical moments between two characters that aren't
    meant to be part of the public scene.

    Usage:
      pmote <name> = <text>

    Examples:
      pmote Ara = reaches out and briefly touches your hand.
        -> Ara sees:  Witch reaches out and briefly touches your hand.
        -> Room sees: nothing
        -> You see:   [private -> Ara] reaches out and briefly touches your hand.

    Mood colors what the target receives.

    See also: pose, whisper, aside
    """

    key = "pmote"
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.lhs or not self.rhs:
            self.msg(
                "Usage: pmote <name> = <text>\n"
                "Example: pmote Ara = glances toward you briefly."
            )
            return

        results = char.search(
            self.lhs.strip(),
            location=char.location,
            quiet=True,
        )
        if not results:
            self.msg(f"You don't see '{self.lhs.strip()}' here.")
            return
        target = results[0] if isinstance(results, list) else results

        if target == char:
            self.msg("You can't private-pose at yourself.")
            return

        name = _name(char)
        tname = _name(target)
        color = _mood_color(char)
        text = self.rhs.strip()

        if not text:
            self.msg("Pose what?")
            return

        if not _ends_with_punctuation(text):
            text += "."

        # Caller confirmation
        self.msg(f"|x[private -> {tname}]|n {color}{name} {text}|n")

        # Target receives the full pose
        target.msg(f"{color}{name} {text}|n")

        # Log privately — neither version goes to room
        if char.location:
            char.location.append_scene_log(
                name, f"[private -> {tname}] {name} {text}"
            )


# -------------------------------------------------------------------
# CmdWhisper
# -------------------------------------------------------------------

class CmdWhisper(MuxCommand):
    """
    Whisper a private message to someone in the same room.

    The room sees only that you whispered — not what you said.
    The target receives your full message.

    Usage:
      whisper <name> = <message>

    Examples:
      whisper Ara = Are you all right?
      whisper Seraphine = Don't look now, but—

    Mood colors what the target receives.

    See also: say, aside, mutter
    """

    key = "whisper"
    aliases = ["wh"]
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.lhs or not self.rhs:
            self.msg(
                "Usage: whisper <name> = <message>\n"
                "Example: whisper Ara = Are you all right?"
            )
            return

        # Find target in the room
        results = char.search(
            self.lhs.strip(),
            location=char.location,
            quiet=True,
        )
        if not results:
            self.msg(f"You don't see '{self.lhs.strip()}' here.")
            return
        target = results[0] if isinstance(results, list) else results

        if target == char:
            self.msg("You whisper to yourself. Old habit.")
            return

        name = _name(char)
        tname = _name(target)
        color = _mood_color(char)
        text = self.rhs.strip()

        if not text:
            self.msg("Whisper what?")
            return

        # Caller confirmation
        self.msg(f'{color}You whisper to {tname}, "{text}"|n')

        # Target receives the full message
        target.msg(f'{color}{name} whispers to you, "{text}"|n')

        # Room sees only the act
        if char.location:
            char.location.msg_contents(
                f"|x{name} leans toward {tname} and says something quietly.|n",
                exclude=[char, target],
            )


# -------------------------------------------------------------------
# CmdMutter
# -------------------------------------------------------------------

class CmdMutter(MuxCommand):
    """
    Speak audibly but indistinctly.

    The room hears that you said something and catches fragments —
    but not the full content. Use for half-heard remarks, things
    said under your breath, or thoughts spoken aloud.

    Usage:
      mutter <text>

    Examples:
      mutter I can't believe this.
        -> Room: Seraphine mutters something — "I can't ... this."
        -> You:  You mutter, "I can't believe this."

    See also: say, whisper, aside
    """

    key = "mutter"
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg("Mutter what? Usage: mutter <text>")
            return

        text = self.args.strip()
        name = _name(char)
        color = _mood_color(char)
        fragment = _mutter_fragment(text)

        self.msg(f'{color}You mutter, "{text}"|n')
        if char.location:
            room_msg = f'{color}{name} mutters something — "{fragment}"|n'
            char.location.msg_contents(room_msg, exclude=char)
            char.location.append_scene_log(name, room_msg)


# -------------------------------------------------------------------
# CmdShout
# -------------------------------------------------------------------

class CmdShout(MuxCommand):
    """
    Shout loudly enough to be heard in adjacent rooms.

    Everyone in your room hears the full shout. Anyone in directly
    connected rooms hears a muffled version with the words but no
    speaker identity.

    Usage:
      shout <text>

    Examples:
      shout Is anyone out there?

    See also: say, mutter, aside
    """

    key = "shout"
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg("Shout what? Usage: shout <text>")
            return

        text = self.args.strip()
        name = _name(char)
        color = _mood_color(char)

        if not _ends_with_punctuation(text):
            text += "!"

        # Current room: full message
        self.msg(f'{color}You shout, "{text}"|n')
        if char.location:
            room_msg = f'{color}{name} shouts, "{text}"|n'
            char.location.msg_contents(room_msg, exclude=char)
            char.location.append_scene_log(name, room_msg)

            # Adjacent rooms: muffled version without identity
            for exit_obj in char.location.exits:
                dest = exit_obj.destination
                if dest and dest != char.location:
                    dest.msg_contents(
                        f'|xA voice carries from nearby — "{text}"|n'
                    )


# -------------------------------------------------------------------
# CmdAside
# -------------------------------------------------------------------

class CmdAside(MuxCommand):
    """
    Draw someone aside for a hushed private exchange.

    Pulls a specific character into a quiet conversation. The room
    sees the gesture — two people stepping aside to speak — but
    cannot make out the words. Only the two of you hear the content.

    Wisps in the room always see the full exchange, since they
    observe the scene from outside it.

    Usage:
      aside <name> = <text>

    Examples:
      aside Seraphine = Don't look now — he followed us.
      aside Mira = The door was open when I arrived.

    See also: whisper, say, mutter, tell
    """

    key = "aside"
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if "=" not in (self.args or ""):
            self.msg(
                "Usage: aside <name> = <text>\n"
                "Example: aside Seraphine = Don't look now."
            )
            return

        target_str, _, text = self.args.partition("=")
        target_str = target_str.strip()
        text = text.strip()

        if not target_str or not text:
            self.msg("Usage: aside <name> = <text>")
            return

        # Find the target in the room
        target = char.search(
            target_str,
            location=char.location,
            quiet=True,
        )
        if not target:
            self.msg(f"|xYou don't see '{target_str}' here.|n")
            return
        if isinstance(target, list):
            if not target:
                self.msg(f"|xYou don't see '{target_str}' here.|n")
                return
            target = target[0]

        if target == char:
            self.msg("|xYou can't draw yourself aside.|n")
            return

        name = _name(char)
        target_name = _name(target)
        color = _mood_color(char)

        # --- Caller sees ---
        self.msg(
            f'{color}[aside → {target_name}] "{text}"|n'
        )

        # --- Target sees ---
        target.msg(
            f'{color}[aside ← {name}] "{text}"|n'
        )

        # --- Room sees (gesture, no content) ---
        room_msg = (
            f"|x{name} draws {target_name} aside, "
            f"speaking in low tones.|n"
        )

        if char.location:
            from world.wisp_visibility import WispVisibility

            # Message to other characters in the room (gesture, no content)
            for obj in char.location.contents:
                if obj in (char, target):
                    continue
                if not hasattr(obj, "msg"):
                    continue
                obj.msg(room_msg)

            # Wisps observe the full exchange — they're OOC
            # Wisps are Account objects tracked separately, not in contents
            wisp_msg = (
                f"|x[aside] {name} → {target_name}: "
                f'"{text}"|n'
            )
            room_wisps = WispVisibility.get_room_wisps(char.location)
            for wisp_acct in room_wisps:
                wisp_acct.msg(wisp_msg)

            # Log the full exchange to the scene log
            char.location.append_scene_log(
                name,
                f'[aside → {target_name}] "{text}"'
            )


# -------------------------------------------------------------------
# CmdOOC
# -------------------------------------------------------------------

class CmdOOC(MuxCommand):
    """
    Make an out-of-character comment visible to everyone in the scene.

    OOC comments appear bracketed and in grey, clearly separated
    from IC content. Use for pauses, clarifications, or quick
    check-ins without leaving the scene.

    If called without text, returns you to your wisp (same as
    typing 'ooc' as a wisp command).

    Usage:
      ooc <comment>     -- make an OOC comment in the scene
      ooc               -- return to wisp state

    Examples:
      ooc brb one minute
      ooc Is it okay if we skip ahead here?

    See also: safeword, yellow
    """

    key = "ooc"
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.args:
            # No text — return to wisp state (same logic as wisp CmdOOC)
            account = self.account
            session = self.session

            puppet = account.get_puppet(session)
            if not puppet:
                self.msg("You are already in wisp state.")
                return

            char_location = puppet.location
            char_name = puppet.key

            account.unpuppet_object(session)
            account.db.wisp_location = char_location

            color = account.wisp_color_code
            mood = account.wisp_mood

            self.msg(
                f"\n{char_name} steps back —\n"
                f"the character releasing into the wisp,\n"
                f"the specificity relaxing into something\n"
                f"more luminous and less defined.\n\n"
                f"{color}[Wisp state: {account.name} | "
                f"mood: {mood}]|n\n"
                f"|xYour character remains in "
                f"{char_location.key if char_location else 'their last location'}.|n\n"
                f"Type '|wic {char_name}|n' to return."
            )
            return

        text = self.args.strip()
        name = _name(char)

        msg = f"|x[OOC: |w{name}|n|x: {text}]|n"

        if char.location:
            char.location.msg_contents(msg)
            char.location.append_scene_log(name, f"[OOC: {name}: {text}]")
        else:
            self.msg(msg)


# -------------------------------------------------------------------
# CmdTBF
# -------------------------------------------------------------------

class CmdTBF(MuxCommand):
    """
    To be felt — a physical sensation pose.

    TBF lines describe a tactile, sensory, or environmental detail
    that others in the scene can choose to receive. Use for warmth,
    pressure, proximity, scent — sensation rather than action.

    The output is tagged [felt] to distinguish it from action poses.

    Usage:
      tbf <text>

    Examples:
      tbf The warmth of the fire settles over everyone nearby.
      tbf A faint perfume lingers as she passes.
      tbf The air shifts — something has changed.

    See also: pose, emote, spoof
    """

    key = "tbf"
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg(
                "Usage: tbf <sensation>\n"
                "Example: tbf The warmth of the fire settles close."
            )
            return

        text = self.args.strip()
        name = _name(char)
        color = _mood_color(char)

        if not _ends_with_punctuation(text):
            text += "."

        msg = f"|x[felt]|n {color}{text}|n"

        if char.location:
            char.location.msg_contents(msg)
            char.location.append_scene_log(name, msg)
        else:
            self.msg(msg)


# -------------------------------------------------------------------
# CmdSpoof
# -------------------------------------------------------------------

class CmdSpoof(MuxCommand):
    """
    Emit text to the room with no attribution.

    The text appears exactly as you write it — no name, no prefix.
    Use for scene dressing, ambient narration, or collaborative
    storytelling moments that don't belong to any one character.

    Usage:
      spoof <text>
      sp <text>

    Examples:
      spoof The candle gutters and nearly goes out.
      spoof A low sound drifts in from somewhere beyond the walls.

    See also: pose, emote, tbf
    """

    key = "spoof"
    aliases = ["sp"]
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg(
                "Spoof what? Usage: spoof <text>\n"
                "Example: spoof The candle gutters."
            )
            return

        text = self.args.strip()

        if char.location:
            char.location.msg_contents(text)
        else:
            self.msg(text)


# -------------------------------------------------------------------
# CmdLook
# -------------------------------------------------------------------

class CmdLook(MuxCommand):
    """
    Look at a character, object, the room, or a specific zone.

    Usage:
      look
      look <character/object>
      look <character> <zone>
      look/deep <character>

    'look' with no target shows the current room.
    'look <name>' shows a standard view of that person or thing.
    'look <name> <zone>' zooms in on a specific body zone — for example,
    'look laynie face' or 'look durgin beard'.
    'look/deep <name>' shows a detailed examination.

    Proximity layers (scent, proximity tell, touch, intimate desc)
    are shown automatically when you are near or with the target.

    See also: approach, withdraw, examine
    """

    key = "look"
    aliases = ["l"]
    locks = "cmd:all()"
    help_category = "RP"
    # /deep switch triggers deep examine
    switch_options = ("deep",)

    def func(self):
        char = self.caller
        deep = "deep" in self.switches

        if not self.args:
            # No target — look at the room
            if char.location:
                char.msg(char.location.return_appearance(char))
            else:
                char.msg("|xYou are in the void.|n")
            return

        # Strip optional "at " preposition so "look at lark" == "look lark"
        args = self.args.strip()
        if args.lower().startswith("at "):
            args = args[3:].strip()

        # Find the target
        target = char.search(args, quiet=True)
        if isinstance(target, list):
            target = target[0] if target else None

        if not target:
            # Try zone targeting: 'look <target> <zone>'
            zone_output = _try_zone_target(char, args, deep=deep)
            if zone_output is not None:
                char.msg("\n" + zone_output)
                return

            # Fallback: check caller's own freeform items
            freeform = char.db.freeform_items or {}
            query = args.lower().replace("-", " ").replace(" ", "")
            match = None
            for iname, idata in freeform.items():
                normalized = iname.lower().replace("-", " ").replace(" ", "")
                if query == normalized or query in normalized or normalized in query:
                    match = (iname, idata)
                    break
            if match:
                iname, idata = match
                idesc = idata.get("desc", "")
                izone = idata.get("zone", "?").replace("_", " ")
                lock = idata.get("lock")
                lock_str = ""
                if lock:
                    lock_str = f" |r[{lock.get('type', 'locked')}]|n"
                char.msg(
                    f"\n|w{iname}|n {lock_str}\n"
                    f"|x{izone}|n\n\n"
                    f"{idesc}"
                )
                return
            char.msg(f"|xYou don't see '{args}' here.|n")
            return

        char.msg("\n" + target.return_appearance(char, deep_examine=deep))


# -------------------------------------------------------------------
# CmdExamine — alias to look/deep
# -------------------------------------------------------------------

class CmdExamine(MuxCommand):
    """
    Examine a character, object, or specific zone closely.

    Equivalent to 'look/deep' — reveals voice, detailed markings,
    intimate zones, and RP hooks when set.

    Usage:
      examine <character/object>
      examine <character> <zone>
      ex <character/object>

    'examine <name> <zone>' zooms in on a specific body zone — for example,
    'examine laynie chest' or 'examine companion lower back'.

    Proximity layers are shown automatically if you are near or with
    the target.

    See also: look, approach
    """

    key = "examine"
    aliases = ["ex"]
    locks = "cmd:all()"
    help_category = "RP"

    def func(self):
        char = self.caller

        if not self.args:
            char.msg(
                "Examine what?\n"
                "Usage: examine <character/object>"
            )
            return

        args = self.args.strip()
        if args.lower().startswith("at "):
            args = args[3:].strip()

        target = char.search(args, quiet=True)
        if isinstance(target, list):
            target = target[0] if target else None

        if not target:
            # Try zone targeting: 'examine <target> <zone>'
            zone_output = _try_zone_target(char, args, deep=True)
            if zone_output is not None:
                char.msg("\n" + zone_output)
                return

            # Fallback: check caller's own freeform items
            freeform = char.db.freeform_items or {}
            query = args.lower().replace("-", " ").replace(" ", "")
            match = None
            for iname, idata in freeform.items():
                normalized = iname.lower().replace("-", " ").replace(" ", "")
                if query == normalized or query in normalized or normalized in query:
                    match = (iname, idata)
                    break
            if match:
                iname, idata = match
                idesc = idata.get("desc", "")
                izone = idata.get("zone", "?").replace("_", " ")
                lock = idata.get("lock")
                lock_str = ""
                if lock:
                    lock_str = f" |r[{lock.get('type', 'locked')}]|n"
                char.msg(
                    f"\n|w{iname}|n{lock_str}\n"
                    f"|x{izone}|n\n\n"
                    f"{idesc}"
                )
                return
            char.msg(f"|xYou don't see '{args}' here.|n")
            return

        char.msg("\n" + target.return_appearance(char, deep_examine=True))


# -------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------

ALL_RP_CMDS = [
    CmdSay,
    CmdPose,
    CmdEmote,
    CmdPmote,
    CmdWhisper,
    CmdMutter,
    CmdShout,
    CmdAside,
    CmdOOC,
    CmdTBF,
    CmdSpoof,
    CmdLook,
    CmdExamine,
]
