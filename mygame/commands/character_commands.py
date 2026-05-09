"""
commands/character_commands.py

Character-level commands for description, zones, clothing,
titles, markings, RP hooks, sheet, and consent.

All commands require an active character puppet.
"""

from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import evtable
from typeclasses.characters import (
    ZONE_DISPLAY_ORDER,
    ZONE_GROUPS,
    ZONE_TYPES,
    ZONE_VISIBILITY,
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _char(caller):
    """Get the caller's puppet character."""
    return caller.puppet if hasattr(caller, 'puppet') else caller


def _get_char(caller):
    """
    Return the character object and an error flag.
    Commands call this to ensure they have a valid character.
    """
    char = _char(caller)
    if not char:
        caller.msg("You need to be in a character to use this.")
        return None
    return char


# -------------------------------------------------------------------
# Web profile commands
# -------------------------------------------------------------------

class CmdSetPortrait(MuxCommand):
    """
    Set the portrait image shown on your public character profile page.

    Paste a direct link to an image (jpg, png, etc.) hosted anywhere
    — Discord CDN, Imgur, a personal site, etc.

    Usage:
        setportrait <url>
        setportrait/clear

    Example:
        setportrait https://i.imgur.com/abcdef.jpg
    """
    key = "setportrait"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = _get_char(self.caller)
        if not char:
            return

        if "clear" in self.switches:
            char.db.portrait_url = None
            self.caller.msg("|x[Portrait cleared.]|n")
            return

        url = self.args.strip()
        if not url:
            current = char.db.portrait_url or "|x(none set)|n"
            self.caller.msg(f"|wCurrent portrait:|n {current}")
            return

        if not (url.startswith("http://") or url.startswith("https://")):
            self.caller.msg("|xURL must start with http:// or https://|n")
            return

        char.db.portrait_url = url
        self.caller.msg(f"|x[Portrait set. It will appear on your profile page.]|n")


class CmdSetOOC(MuxCommand):
    """
    Set the OOC (out-of-character) about blurb on your public
    character profile page. Use this to tell other players about
    yourself, your roleplay preferences, contact info, etc.

    Usage:
        setooc                  — open the text editor
        setooc = <text>         — set inline
        setooc/clear            — remove your OOC blurb
        setooc/show             — preview your current blurb
    """
    key = "setooc"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = _get_char(self.caller)
        if not char:
            return

        if "clear" in self.switches:
            char.db.ooc_about = None
            self.caller.msg("|x[OOC blurb cleared.]|n")
            return

        if "show" in self.switches:
            text = char.db.ooc_about or "|x(none set)|n"
            sep = f"|w{'─' * 44}|n"
            self.caller.msg(f"\n{sep}\n|wOOC About — {char.key}|n\n{sep}\n{text}\n{sep}")
            return

        if self.args and "=" in self.args:
            text = self.args.split("=", 1)[1].strip()
            if not text:
                self.caller.msg("|xNo text provided.|n")
                return
            char.db.ooc_about = text
            self.caller.msg("|x[OOC blurb set.]|n")
            return

        # Open editor
        from world.text_editor import _enter_editor, _PENDING_SETTERS

        current = char.db.ooc_about or ""
        initial = [l for l in current.split("\n") if l] if current else []

        def _setter(c, lines):
            char.db.ooc_about = "\n".join(lines)
            c.msg(f"|x[OOC blurb saved for '{char.key}'.]|n")

        _PENDING_SETTERS[str(self.caller.dbref)] = _setter

        _enter_editor(
            self.caller,
            target_display=f"{char.key} — OOC About",
            setter_key="_room_field",
            initial_lines=initial,
            extra=None,
        )


# -------------------------------------------------------------------
# Identity commands
# -------------------------------------------------------------------

class CmdSetName(MuxCommand):
    """
    Set your character's IC/RP name.

    This is the name other players see in room listings,
    look output, and the WHO list. Different from your
    account login name.

    Usage:
        setname <name>
        setname/clear       — revert to account key

    Example:
        setname Seraphine Voss
    """
    key = "setname"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.rp_name = ""
            self.msg("RP name cleared. Using account key.")
            return

        if not self.args:
            current = char.db.rp_name or char.key
            self.msg(f"Current name: |w{current}|n")
            return

        new_name = self.args.strip()
        if len(new_name) > 60:
            self.msg("Name is too long. Keep it under 60 characters.")
            return

        char.db.rp_name = new_name
        self.msg(f"Name set to: |w{new_name}|n")


class CmdSetPronouns(MuxCommand):
    """
    Set your character's pronouns.

    Used by the emote system for third-person references.

    Usage:
        setpronouns <subject> <object> <possessive>
        setpronouns             — see current pronouns
        setpronouns/clear       — reset to they/them/their

    Examples:
        setpronouns she her her
        setpronouns he him his
        setpronouns they them their
        setpronouns xe xem xyr
    """
    key = "setpronouns"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.pronouns = {
                "subject":    "they",
                "object":     "them",
                "possessive": "their",
                "reflexive":  "themselves",
            }
            self.msg("Pronouns reset to they/them/their.")
            return

        if not self.args:
            p = char.db.pronouns or {}
            self.msg(
                f"Current pronouns:\n"
                f"  Subject:    {p.get('subject', 'they')}\n"
                f"  Object:     {p.get('object', 'them')}\n"
                f"  Possessive: {p.get('possessive', 'their')}\n"
                f"  Reflexive:  {p.get('reflexive', 'themselves')}"
            )
            return

        parts = self.args.strip().split()
        if len(parts) < 3:
            self.msg(
                "Usage: setpronouns <subject> <object> <possessive>\n"
                "Example: setpronouns she her her"
            )
            return

        subject, obj, possessive = parts[0], parts[1], parts[2]

        # Build reflexive from object
        reflexive = f"{obj}self"

        char.db.pronouns = {
            "subject":    subject,
            "object":     obj,
            "possessive": possessive,
            "reflexive":  reflexive,
        }
        self.msg(
            f"Pronouns set to "
            f"{subject}/{obj}/{possessive}/{reflexive}."
        )


class CmdSetSpecies(MuxCommand):
    """
    Set your character's species or type.

    Freeform — write whatever fits your character.

    Usage:
        setspecies <description>
        setspecies              — see current species
    """
    key = "setspecies"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if not self.args:
            current = char.db.species or "human"
            self.msg(f"Current species: |w{current}|n")
            return

        char.db.species = self.args.strip()
        self.msg(f"Species set to: |w{self.args.strip()}|n")


class CmdSetAge(MuxCommand):
    """
    Set your character's apparent age.

    Freeform description — not a number.

    Usage:
        setage <description>
        setage              — see current apparent age

    Example:
        setage mid-thirties
        setage ageless, or trying to appear so
    """
    key = "setage"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if not self.args:
            current = char.db.apparent_age or "not set"
            self.msg(f"Current apparent age: |w{current}|n")
            return

        char.db.apparent_age = self.args.strip()
        self.msg(
            f"Apparent age set to: |w{self.args.strip()}|n"
        )


# -------------------------------------------------------------------
# Description commands
# -------------------------------------------------------------------

class CmdSetDesc(MuxCommand):
    """
    Set your character's physical base description.

    This is the permanent body — what you look like
    underneath everything else. Player-written prose.
    Shown on standard look.

    Usage:
        setdesc <text>
        setdesc             — see current description
        setdesc/clear       — clear description

    Example:
        setdesc Tall and angular, with the particular
        stillness of someone who has learned to take up
        exactly as much space as they intend to.
    """
    key = "setdesc"
    aliases = ["desc"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.physical_desc = ""
            self.msg("Physical description cleared.")
            return

        if not self.args:
            current = char.db.physical_desc or "Not set."
            self.msg(
                f"Your physical description:\n\n{current}"
            )
            return

        new_desc = self.args.strip()
        if len(new_desc) > 4000:
            self.msg(
                f"Description too long ({len(new_desc)} chars). "
                f"Keep it under 4000."
            )
            return

        char.db.physical_desc = new_desc
        self.msg(
            "Physical description set.\n"
            "Type 'look me' to see how it appears."
        )


class CmdSetOutfit(MuxCommand):
    """
    Override the auto-assembled outfit layer with your
    own prose, or return to automatic assembly.

    By default the outfit layer is assembled from your
    zone states. Use this when the auto-assembly doesn't
    read naturally.

    Usage:
        setoutfit <text>    — set custom outfit description
        setoutfit           — see current outfit
        setoutfit/auto      — return to auto-assembly
        setoutfit/clear     — same as /auto

    Example:
        setoutfit A deep charcoal coat over dark trousers.
        A plain silver ring on the right hand.
    """
    key = "setoutfit"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if (
            "auto" in self.switches or
            "clear" in self.switches
        ):
            char.db.outfit_desc_override = False
            char._rebuild_outfit_desc()
            self.msg(
                "Outfit description returned to auto-assembly."
            )
            return

        if not self.args:
            override = char.db.outfit_desc_override
            current = char.db.outfit_desc or "Not set."
            mode = "custom" if override else "auto-assembled"
            self.msg(
                f"Outfit description [{mode}]:\n\n{current}"
            )
            return

        char.db.outfit_desc = self.args.strip()
        char.db.outfit_desc_override = True
        self.msg(
            "Outfit description set.\n"
            "Type 'setoutfit/auto' to return to auto-assembly."
        )


class CmdSetBodyLang(MuxCommand):
    """
    Set your character's current body language.

    Shown in look output after the outfit layer.
    Describes your current posture, position, activity.

    Usage:
        setbodylang <text>
        setbodylang             — see current body language
        setbodylang/clear       — clear body language

    Example:
        setbodylang leaning against the doorframe, arms crossed
        setbodylang seated, weight forward, elbows on the table
    """
    key = "setbodylang"
    aliases = ["bodylang"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.body_language = ""
            self.msg("Body language cleared.")
            return

        if not self.args:
            current = char.db.body_language or "Not set."
            self.msg(f"Current body language:\n\n{current}")
            return

        char.db.body_language = self.args.strip()
        self.msg("Body language set.")


class CmdSetMood(MuxCommand):
    """
    Set your character's current mood.

    The mood tell appears in parentheses at the end of
    your look output. You can set a mood word and use
    the system's tell pool, or write your own tell.

    Usage:
        setmood <word>          — set mood tag
        setmood                 — see current mood
        setmood/clear           — clear mood

    Example:
        setmood melancholy
        setmood curious
        setmood tense
    """
    key = "setmood"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.mood = ""
            char.db.mood_tell = ""
            self.msg("Mood cleared.")
            return

        if not self.args:
            mood = char.db.mood or "not set"
            tell = char.db.mood_tell or "system default"
            self.msg(
                f"Current mood: |w{mood}|n\n"
                f"Current mood tell: {tell}\n\n"
                f"Set mood tell with: setmoodtell <text>"
            )
            return

        char.db.mood = self.args.strip().lower()
        self.msg(
            f"Mood set to: |w{char.db.mood}|n\n"
            f"Set a specific tell with: "
            f"setmoodtell <text>"
        )


class CmdSetMoodTell(MuxCommand):
    """
    Set the physical tell for your character's current mood.

    The mood tell is the specific line shown in parentheses
    in your look output — the physical manifestation of
    your current emotional state.

    Usage:
        setmoodtell <text>      — set custom mood tell
        setmoodtell             — see current mood tell
        setmoodtell/clear       — clear custom tell

    Example:
        setmoodtell Something about her attention is slightly
        more focused than the situation calls for.
    """
    key = "setmoodtell"
    aliases = ["moodtell"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.mood_tell = ""
            self.msg(
                "Mood tell cleared. Will show (mood) in "
                "parentheses if mood is set."
            )
            return

        if not self.args:
            current = char.db.mood_tell or "not set"
            self.msg(f"Current mood tell:\n\n{current}")
            return

        char.db.mood_tell = self.args.strip()
        self.msg("Mood tell set.")


class CmdSetPresence(MuxCommand):
    """
    Set your character's IC presence line.

    This short line appears in room listings next to
    your name — visible without a full look command.

    Usage:
        setpresence <text>
        setpresence             — see current presence
        setpresence/clear       — clear presence line

    Example:
        setpresence watching the door
        setpresence seated at the bar, occupied
        setpresence close to the wall, very still
    """
    key = "setpresence"
    aliases = ["presence"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.ic_presence = ""
            self.msg("Presence line cleared.")
            return

        if not self.args:
            current = char.db.ic_presence or "not set"
            self.msg(f"Current presence line:\n\n{current}")
            return

        if len(self.args.strip()) > 120:
            self.msg(
                "Presence line too long. "
                "Keep it under 120 characters."
            )
            return

        char.db.ic_presence = self.args.strip()
        self.msg("Presence line set.")


class CmdSetProxTell(MuxCommand):
    """
    Set your character's proximity tell.

    Additional detail visible only when someone is
    at near or with proximity to you.

    Usage:
        setproxtell <text>
        setproxtell             — see current proximity tell
        setproxtell/clear       — clear proximity tell

    Example:
        setproxtell Up close, the shadows under her eyes
        are more visible than the distance concealed.
    """
    key = "setproxtell"
    aliases = ["proxtell"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.proximity_tell = ""
            self.msg("Proximity tell cleared.")
            return

        if not self.args:
            current = char.db.proximity_tell or "not set"
            self.msg(f"Current proximity tell:\n\n{current}")
            return

        char.db.proximity_tell = self.args.strip()
        self.msg("Proximity tell set.")


class CmdSetScent(MuxCommand):
    """
    Set your character's scent description.

    Visible only on deep examine or at with-proximity.

    Usage:
        setscent <text>
        setscent                — see current scent
        setscent/clear          — clear scent

    Example:
        setscent cedar and something colder underneath
    """
    key = "setscent"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.scent_desc = ""
            self.msg("Scent description cleared.")
            return

        if not self.args:
            current = char.db.scent_desc or "not set"
            self.msg(f"Current scent:\n\n{current}")
            return

        char.db.scent_desc = self.args.strip()
        self.msg("Scent description set.")


class CmdSetVoice(MuxCommand):
    """
    Set your character's voice description.

    Shown on examine. Also sets the quality of your
    voice that appears in say output.

    Usage:
        setvoice <text>
        setvoice                — see current voice desc
        setvoice/clear          — clear voice desc

    Example:
        setvoice low and unhurried, the kind of voice
        that doesn't raise itself
    """
    key = "setvoice"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.voice_desc = ""
            self.msg("Voice description cleared.")
            return

        if not self.args:
            current = char.db.voice_desc or "not set"
            self.msg(f"Current voice description:\n\n{current}")
            return

        char.db.voice_desc = self.args.strip()
        self.msg("Voice description set.")


class CmdSetSayVerb(MuxCommand):
    """
    Set your character's default speech verb.

    Used in say output as: [Name] [verb], "..."

    Usage:
        setsayverb <verb>
        setsayverb              — see current verb
        setsayverb/clear        — reset to 'says'

    Example:
        setsayverb murmurs
        setsayverb states
        setsayverb drawls
    """
    key = "setsayverb"
    aliases = ["sayverb"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.say_verb = "says"
            self.msg("Say verb reset to 'says'.")
            return

        if not self.args:
            current = char.db.say_verb or "says"
            self.msg(f"Current say verb: |w{current}|n")
            return

        verb = self.args.strip().lower()
        if len(verb) > 30:
            self.msg("Say verb too long.")
            return

        char.db.say_verb = verb
        self.msg(f"Say verb set to: |w{verb}|n")


class CmdSetTouch(MuxCommand):
    """
    Set your character's touch/texture description.

    Shown only with appropriate consent and at
    with-proximity. The most physically intimate
    non-intimate layer.

    Usage:
        settouch <text>
        settouch                — see current touch desc
        settouch/clear          — clear touch desc

    Example:
        settouch Warm. The particular warmth of someone
        who runs slightly hot.
    """
    key = "settouch"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.touch_desc = ""
            self.msg("Touch description cleared.")
            return

        if not self.args:
            current = char.db.touch_desc or "not set"
            self.msg(f"Current touch description:\n\n{current}")
            return

        char.db.touch_desc = self.args.strip()
        self.msg("Touch description set.")


class CmdSetBio(MuxCommand):
    """
    Set your character's public bio.

    A short IC summary shown on your character sheet.
    One or two sentences of IC framing.

    Usage:
        setbio <text>
        setbio                  — see current bio
        setbio/clear            — clear bio

    Example:
        setbio Archivist, formerly. Something else now.
    """
    key = "setbio"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.public_bio = ""
            self.msg("Bio cleared.")
            return

        if not self.args:
            current = char.db.public_bio or "not set"
            self.msg(f"Current bio:\n\n{current}")
            return

        if len(self.args.strip()) > 500:
            self.msg(
                "Bio too long. Keep it under 500 characters."
            )
            return

        char.db.public_bio = self.args.strip()
        self.msg("Bio set.")


class CmdSetIntimate(MuxCommand):
    """
    Set your character's intimate description layer.

    This is the most personal physical layer. Shown only
    with mature consent and at with-proximity.

    Usage:
        setintimate <text>
        setintimate             — see current intimate desc
        setintimate/clear       — clear intimate desc
    """
    key = "setintimate"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "clear" in self.switches:
            char.db.intimate_desc = ""
            self.msg("Intimate description cleared.")
            return

        if not self.args:
            current = char.db.intimate_desc or "not set"
            self.msg(
                f"Current intimate description:\n\n{current}\n\n"
                f"|x[Only visible with mature consent "
                f"at with-proximity]|n"
            )
            return

        char.db.intimate_desc = self.args.strip()
        self.msg(
            "Intimate description set.\n"
            "|x[Visible only with mature consent "
            "at with-proximity]|n"
        )


# -------------------------------------------------------------------
# Zone commands
# -------------------------------------------------------------------

class CmdZone(MuxCommand):
    """
    Manage your character's body zones.

    Zones are named areas of your body, each with
    their own description, visibility, and clothing state.

    Usage:
        zone list                           — list all zones
        zone show <name>                    — zone detail
        zone set <name> = <description>     — set nude desc
        zone add <name>                     — add freeform zone
        zone add <name> type=<type>         — add with type
        zone remove <name>                  — remove freeform zone
        zone rename <name> <new>            — rename zone
        zone visibility <name> <level>      — set visibility
        zone intimate <name> <on/off>       — flag as intimate
        zone order <zone> <zone> ...        — set display order
        zone ambient <name> add <line>      — add ambient line
        zone ambient <name> list            — list ambient lines
        zone ambient <name> remove <#>      — remove ambient line
        zone reset <name>                   — clear zone desc

    Zone types: surface / orifice / both / attachment
    Visibility: look / examine / deep / proximity / consent / hidden
    """
    key = "zone"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            self._zone_list(char)
            return

        # Split first word as subcommand
        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        dispatch = {
            "list":       self._zone_list,
            "show":       self._zone_show,
            "set":        self._zone_set,
            "add":        self._zone_add,
            "remove":     self._zone_remove,
            "rename":     self._zone_rename,
            "visibility": self._zone_visibility,
            "intimate":   self._zone_intimate,
            "order":      self._zone_order,
            "ambient":    self._zone_ambient,
            "reset":      self._zone_reset,
        }

        handler = dispatch.get(subcmd)
        if handler:
            handler(char, rest)
        else:
            # Treat as zone show if it looks like a zone name
            self._zone_show(char, args)

    def _zone_list(self, char, args=""):
        """Show all zones grouped and formatted."""
        zones = char._get_zones()
        lines = ["|wYour zones:|n\n"]
        sep = "|x" + "━" * 40 + "|n"

        covered_count = 0
        freeform_count = 0

        for group_name, group_zones in ZONE_GROUPS:
            # Check if any zones in this group exist
            group_has = [z for z in group_zones if z in zones]
            if not group_has:
                continue

            lines.append(f"\n|w{group_name}|n")

            for zone_name in group_zones:
                if zone_name not in zones:
                    continue

                zone = zones[zone_name]
                zone_type = zone.get("zone_type", "surface")
                visibility = zone.get("visibility", "look")
                intimate = zone.get("intimate", False)
                covered = zone.get("covered_by")
                contents = zone.get("contents", [])

                # Status indicators
                intimate_marker = "|m♦|n " if intimate else "  "
                type_tag = f"|x[{zone_type[:3]}]|n"
                vis_tag = f"|x[{visibility[:3]}]|n"

                if covered:
                    covered_count += 1
                    worn = covered.get(
                        "worn_desc",
                        covered.get("desc", "")
                    )
                    state = covered.get("state", "pristine")
                    state_tag = (
                        f" |y({state})|n"
                        if state != "pristine"
                        else ""
                    )
                    status = (
                        f"|gCOVERED|n: "
                        f"{worn[:40]}"
                        f"{'...' if len(worn) > 40 else ''}"
                        f"{state_tag}"
                    )
                elif contents:
                    status = (
                        f"|cCONTENTS|n: "
                        f"{len(contents)} item(s)"
                    )
                else:
                    nude = zone.get("nude", "")
                    if nude:
                        status = (
                            f"|xnude|n: "
                            f"{nude[:40]}"
                            f"{'...' if len(nude) > 40 else ''}"
                        )
                    else:
                        status = "|xnude — no description|n"

                lines.append(
                    f"  {intimate_marker}"
                    f"|w{zone_name:<14}|n "
                    f"{type_tag} {vis_tag}  "
                    f"{status}"
                )

        # Freeform zones
        freeform = [
            (n, z) for n, z in zones.items()
            if z.get("freeform")
        ]
        if freeform:
            lines.append(f"\n|wFREEFORM ZONES|n")
            for zone_name, zone in freeform:
                freeform_count += 1
                zone_type = zone.get("zone_type", "surface")
                visibility = zone.get("visibility", "look")
                intimate = zone.get("intimate", False)
                covered = zone.get("covered_by")
                contents = zone.get("contents", [])
                intimate_marker = "|m♦|n " if intimate else "  "

                if covered:
                    covered_count += 1
                    worn = covered.get(
                        "worn_desc",
                        covered.get("desc", "")
                    )
                    status = f"|gCOVERED|n: {worn[:40]}"
                elif contents:
                    status = (
                        f"|cCONTENTS|n: "
                        f"{len(contents)} item(s)"
                    )
                else:
                    nude = zone.get("nude", "")
                    status = (
                        f"|xnude|n: {nude[:40]}"
                        if nude
                        else "|xnude — no description|n"
                    )

                lines.append(
                    f"  {intimate_marker}"
                    f"|w{zone_name:<14}|n "
                    f"|x[{zone_type[:3]}]|n "
                    f"|x[{visibility[:3]}]|n  "
                    f"{status}"
                )

        lines.append(f"\n{sep}")
        lines.append(
            f"|x{len(zones)} zones  |  "
            f"{covered_count} covered  |  "
            f"{freeform_count} freeform|n\n"
            f"|xCommands: zone set / zone add / "
            f"zone show / zone visibility|n"
        )

        self.msg("\n".join(lines))

    def _zone_show(self, char, args):
        """Show full detail of a specific zone."""
        if not args:
            self.msg("Show which zone? Usage: zone show <name>")
            return

        zones = char._get_zones()
        zone_name = args.strip().lower().replace(" ", "_")

        # Try partial match
        if zone_name not in zones:
            matches = [
                z for z in zones
                if z.startswith(zone_name)
            ]
            if len(matches) == 1:
                zone_name = matches[0]
            elif len(matches) > 1:
                self.msg(
                    f"Multiple zones match '{zone_name}': "
                    f"{', '.join(matches)}"
                )
                return
            else:
                self.msg(
                    f"No zone named '{zone_name}'. "
                    f"Type 'zone list' to see all zones."
                )
                return

        zone = zones[zone_name]
        zone_type = zone.get("zone_type", "surface")
        visibility = zone.get("visibility", "look")
        intimate = zone.get("intimate", False)
        default = zone.get("default", False)
        consent_req = zone.get("consent_required", "casual")
        covered = zone.get("covered_by")
        contents = zone.get("contents", [])
        nude = zone.get("nude", "")
        ambient = zone.get("ambient", [])

        lines = [
            f"|wZONE: {zone_name}|n",
            f"  Type:             "
            f"{zone_type} — {ZONE_TYPES.get(zone_type, '')}",
            f"  Visibility:       "
            f"{visibility} — "
            f"{ZONE_VISIBILITY.get(visibility, '')}",
            f"  Intimate:         {'yes' if intimate else 'no'}",
            f"  Consent required: {consent_req}",
            f"  Zone type:        "
            f"{'default' if default else 'freeform'}",
            "",
        ]

        # Nude description
        lines.append("|wNude description:|n")
        if nude:
            lines.append(f"  {nude}")
        else:
            lines.append("  |x[not set]|n")
        lines.append("")

        # Surface covering
        if zone_type in ("surface", "both", "attachment"):
            lines.append("|wCurrently covered by:|n")
            if covered:
                desc = covered.get("desc", "")
                worn = covered.get("worn_desc", desc)
                examine = covered.get("examine_desc", "")
                state = covered.get("state", "pristine")
                item_ambient = covered.get("ambient", [])
                set_by = covered.get("set_by", "unknown")

                lines.append(f"  {worn}")
                if examine:
                    lines.append(
                        f"  Examine: {examine}"
                    )
                lines.append(f"  State: {state}")
                if item_ambient:
                    lines.append(
                        f"  Ambient: "
                        f"{len(item_ambient)} line(s)"
                    )
            else:
                lines.append("  |x[uncovered]|n")
            lines.append("")

        # Orifice contents
        if zone_type in ("orifice", "both"):
            lines.append("|wContents:|n")
            if contents:
                for i, item in enumerate(contents, 1):
                    desc = item.get("desc", "")
                    state = item.get("state", "inserted")
                    removable = item.get("removable_by", [])
                    lines.append(
                        f"  [{i}] {desc}"
                    )
                    lines.append(
                        f"      state: {state}"
                    )
                    if removable:
                        lines.append(
                            f"      removable by: "
                            f"{len(removable)} character(s)"
                        )
            else:
                lines.append("  |x[empty]|n")
            lines.append("")

        # Zone ambient lines
        lines.append("|wZone ambient lines:|n")
        if ambient:
            for i, line in enumerate(ambient, 1):
                lines.append(f"  {i}. {line}")
        else:
            lines.append("  |x[none set]|n")

        self.msg("\n".join(lines))

    def _zone_set(self, char, args):
        """Set nude description for a zone."""
        if "=" not in args:
            self.msg(
                "Usage: zone set <name> = <description>"
            )
            return

        zone_name, _, desc = args.partition("=")
        zone_name = zone_name.strip().lower().replace(" ", "_")
        desc = desc.strip()

        if not desc:
            self.msg("Description cannot be empty.")
            return

        zones = char._get_zones()
        if zone_name not in zones:
            self.msg(
                f"No zone named '{zone_name}'. "
                f"Type 'zone list' to see all zones."
            )
            return

        result = char.set_zone_desc(zone_name, desc)
        if result:
            self.msg(
                f"Zone |w{zone_name}|n description set."
            )
        else:
            self.msg("Could not set zone description.")

    def _zone_add(self, char, args):
        """Add a freeform zone."""
        if not args:
            self.msg(
                "Usage: zone add <name>\n"
                "       zone add <name> type=<type>\n"
                "Types: surface / orifice / both / attachment"
            )
            return

        # Parse optional type= argument
        zone_type = "surface"
        intimate = False
        visibility = "look"

        parts = args.split()
        zone_name = parts[0].lower().replace(" ", "_")

        for part in parts[1:]:
            if part.startswith("type="):
                zone_type = part[5:].lower()
                if zone_type not in ZONE_TYPES:
                    self.msg(
                        f"Unknown type '{zone_type}'. "
                        f"Valid: "
                        f"{', '.join(ZONE_TYPES.keys())}"
                    )
                    return
            elif part.startswith("visibility="):
                visibility = part[11:].lower()
                if visibility not in ZONE_VISIBILITY:
                    self.msg(
                        f"Unknown visibility '{visibility}'."
                    )
                    return
            elif part == "intimate":
                intimate = True

        # Default consent based on type
        consent = (
            "intimate"
            if (zone_type == "orifice" or intimate)
            else "casual"
        )

        result = char.add_zone(
            zone_name,
            intimate=intimate,
            visibility=visibility,
            zone_type=zone_type,
            consent_required=consent,
        )

        if result:
            self.msg(
                f"Freeform zone |w{zone_name}|n added.\n"
                f"Type: {zone_type} | "
                f"Visibility: {visibility} | "
                f"Intimate: {'yes' if intimate else 'no'}\n"
                f"Set its description with: "
                f"zone set {zone_name} = <description>"
            )
        else:
            self.msg(
                f"Zone '{zone_name}' already exists."
            )

    def _zone_remove(self, char, args):
        """Remove a freeform zone."""
        if not args:
            self.msg(
                "Usage: zone remove <name>\n"
                "Note: default zones cannot be removed."
            )
            return

        zone_name = args.strip().lower().replace(" ", "_")
        zones = char._get_zones()

        if zone_name not in zones:
            self.msg(f"No zone named '{zone_name}'.")
            return

        if zones[zone_name].get("default", False):
            self.msg(
                f"Cannot remove default zone '{zone_name}'.\n"
                "Default zones can be renamed or have their "
                "descriptions cleared."
            )
            return

        result = char.remove_zone(zone_name)
        if result:
            self.msg(f"Zone |w{zone_name}|n removed.")
        else:
            self.msg("Could not remove zone.")

    def _zone_rename(self, char, args):
        """Rename a zone."""
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            self.msg(
                "Usage: zone rename <current> <new>"
            )
            return

        old_name = parts[0].lower().replace(" ", "_")
        new_name = parts[1].lower().replace(" ", "_")

        zones = char._get_zones()

        if old_name not in zones:
            self.msg(f"No zone named '{old_name}'.")
            return

        if new_name in zones:
            self.msg(
                f"A zone named '{new_name}' already exists."
            )
            return

        # Rename by copying and deleting
        zones[new_name] = zones.pop(old_name)
        char.db.zones = zones

        # Update display order if present
        order = char.db.zone_display_order or []
        if old_name in order:
            idx = order.index(old_name)
            order[idx] = new_name
            char.db.zone_display_order = order

        char._rebuild_outfit_desc()
        self.msg(
            f"Zone renamed: |w{old_name}|n → |w{new_name}|n"
        )

    def _zone_visibility(self, char, args):
        """Set zone visibility level."""
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            levels = " / ".join(ZONE_VISIBILITY.keys())
            self.msg(
                f"Usage: zone visibility <name> <level>\n"
                f"Levels: {levels}"
            )
            return

        zone_name = parts[0].lower().replace(" ", "_")
        level = parts[1].lower()

        if level not in ZONE_VISIBILITY:
            levels = " / ".join(ZONE_VISIBILITY.keys())
            self.msg(
                f"Unknown visibility '{level}'.\n"
                f"Valid levels: {levels}"
            )
            return

        zones = char._get_zones()
        if zone_name not in zones:
            self.msg(f"No zone named '{zone_name}'.")
            return

        zones[zone_name]["visibility"] = level
        char.db.zones = zones
        self.msg(
            f"Zone |w{zone_name}|n visibility set to: "
            f"|w{level}|n\n"
            f"|x{ZONE_VISIBILITY[level]}|n"
        )

    def _zone_intimate(self, char, args):
        """Set zone intimate flag."""
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            self.msg(
                "Usage: zone intimate <name> <on/off>"
            )
            return

        zone_name = parts[0].lower().replace(" ", "_")
        setting = parts[1].lower()

        if setting not in ("on", "off"):
            self.msg("Usage: zone intimate <name> <on/off>")
            return

        zones = char._get_zones()
        if zone_name not in zones:
            self.msg(f"No zone named '{zone_name}'.")
            return

        zones[zone_name]["intimate"] = (setting == "on")
        char.db.zones = zones
        self.msg(
            f"Zone |w{zone_name}|n intimate flag: "
            f"|w{setting}|n"
        )

    def _zone_order(self, char, args):
        """Set custom zone display order."""
        if not args:
            order = char.db.zone_display_order or []
            if order:
                self.msg(
                    f"Current custom order:\n"
                    f"  {', '.join(order)}\n"
                    f"Use 'zone order/clear' to reset."
                )
            else:
                self.msg(
                    "Using default zone order.\n"
                    "Set custom order with: "
                    "zone order <zone> <zone> ..."
                )
            return

        if "clear" in self.switches:
            char.db.zone_display_order = []
            char._rebuild_outfit_desc()
            self.msg("Zone order reset to default.")
            return

        zones = char._get_zones()
        new_order = []
        unknown = []

        for zone_name in args.strip().split():
            zn = zone_name.lower().replace(" ", "_")
            if zn in zones:
                new_order.append(zn)
            else:
                unknown.append(zn)

        if unknown:
            self.msg(
                f"Unknown zones: {', '.join(unknown)}\n"
                f"Only known zones can be in the order."
            )
            return

        char.db.zone_display_order = new_order
        char._rebuild_outfit_desc()
        self.msg(
            f"Zone display order set:\n"
            f"  {', '.join(new_order)}\n"
            f"Unspecified zones follow in default order."
        )

    def _zone_ambient(self, char, args):
        """Manage zone ambient lines."""
        parts = args.strip().split(None, 2)

        if len(parts) < 2:
            self.msg(
                "Usage:\n"
                "  zone ambient <name> add <line>\n"
                "  zone ambient <name> list\n"
                "  zone ambient <name> remove <#>"
            )
            return

        zone_name = parts[0].lower().replace(" ", "_")
        subcmd = parts[1].lower()
        rest = parts[2] if len(parts) > 2 else ""

        zones = char._get_zones()
        if zone_name not in zones:
            self.msg(f"No zone named '{zone_name}'.")
            return

        zone = zones[zone_name]
        ambient = zone.get("ambient", [])

        if subcmd == "list":
            if not ambient:
                self.msg(
                    f"No ambient lines on zone "
                    f"'{zone_name}'."
                )
                return
            lines = [
                f"|wAmbient lines for {zone_name}:|n\n"
            ]
            for i, line in enumerate(ambient, 1):
                lines.append(f"  {i}. {line}")
            self.msg("\n".join(lines))

        elif subcmd == "add":
            if not rest:
                self.msg("Add what? Usage: zone ambient <name> add <line>")
                return
            ambient.append(rest.strip())
            zone["ambient"] = ambient
            char.db.zones = zones
            self.msg(
                f"Ambient line added to zone "
                f"|w{zone_name}|n (#{len(ambient)})."
            )

        elif subcmd == "remove":
            if not rest:
                self.msg(
                    "Remove which? "
                    "Usage: zone ambient <name> remove <#>"
                )
                return
            try:
                idx = int(rest.strip()) - 1
                if idx < 0 or idx >= len(ambient):
                    self.msg(
                        f"No line #{idx + 1}. "
                        f"You have {len(ambient)} lines."
                    )
                    return
                removed = ambient.pop(idx)
                zone["ambient"] = ambient
                char.db.zones = zones
                self.msg(f"Removed: {removed}")
            except ValueError:
                self.msg("Please provide a number.")

        else:
            self.msg(
                f"Unknown subcommand '{subcmd}'.\n"
                f"Use: add / list / remove"
            )

    def _zone_reset(self, char, args):
        """Clear a zone's nude description."""
        if not args:
            self.msg("Usage: zone reset <name>")
            return

        zone_name = args.strip().lower().replace(" ", "_")
        zones = char._get_zones()

        if zone_name not in zones:
            self.msg(f"No zone named '{zone_name}'.")
            return

        zones[zone_name]["nude"] = ""
        char.db.zones = zones
        self.msg(
            f"Zone |w{zone_name}|n nude description cleared."
        )


# -------------------------------------------------------------------
# Clothing commands
# -------------------------------------------------------------------

class CmdWear(MuxCommand):
    """
    Apply a freeform descriptor to a surface or attachment zone.

    The descriptor is temporary unless saved to your wardrobe.

    Usage:
        wear <zone> <description>
        wear <zone>             — see what's on this zone

    Example:
        wear neck a fitted leather collar, plain and deliberate
        wear chest a deep charcoal coat, fitted through the shoulders
        wear ears a small gold ring through the left ear

    Save to wardrobe with: wardrobe save <zone> "<name>"
    """
    key = "wear"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            self.msg(
                "Usage: wear <zone> <description>\n"
                "Example: wear neck a leather collar"
            )
            return

        parts = args.split(None, 1)
        zone_name = parts[0].lower().replace(" ", "_")

        # No description — show what's there
        if len(parts) == 1:
            zones = char._get_zones()
            if zone_name not in zones:
                self.msg(f"No zone named '{zone_name}'.")
                return
            covered = zones[zone_name].get("covered_by")
            if covered:
                worn = covered.get(
                    "worn_desc",
                    covered.get("desc", "")
                )
                self.msg(
                    f"Zone |w{zone_name}|n is covered by:\n"
                    f"  {worn}"
                )
            else:
                self.msg(
                    f"Zone |w{zone_name}|n is uncovered."
                )
            return

        descriptor = parts[1].strip()
        zones = char._get_zones()

        if zone_name not in zones:
            self.msg(
                f"No zone named '{zone_name}'.\n"
                f"Type 'zone list' to see all zones."
            )
            return

        zone = zones[zone_name]
        zone_type = zone.get("zone_type", "surface")

        if zone_type == "orifice":
            self.msg(
                f"Zone '{zone_name}' is an orifice zone.\n"
                f"Use 'insert {zone_name} <description>' instead."
            )
            return

        result = char.place_on_zone(
            zone_name,
            descriptor,
            worn_desc=descriptor,
            set_by=char.id,
        )

        if result:
            self.msg(
                f"You wear {descriptor} "
                f"[zone: {zone_name}].\n"
                f"|x[Temporary — save with: "
                f"wardrobe save {zone_name} \"<name>\"]|n"
            )
            # Room message
            name = char.db.rp_name or char.key
            char.location.msg_contents(
                f"{name} puts on {descriptor}.",
                exclude=char
            )
        else:
            self.msg("Could not apply descriptor to zone.")


class CmdRemove(MuxCommand):
    """
    Remove what's covering a zone, or extract from an orifice zone.

    Usage:
        remove <zone>               — remove surface covering
        remove <zone> here          — remove but leave in scene
        remove <zone> <#>           — remove specific orifice content
        remove <zone> all           — clear all orifice contents

    Example:
        remove neck
        remove coat here
        remove mouth 1
    """
    key = "remove"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            self.msg("Usage: remove <zone>")
            return

        parts = args.split(None, 1)
        zone_name = parts[0].lower().replace(" ", "_")
        modifier = parts[1].strip() if len(parts) > 1 else ""

        zones = char._get_zones()

        if zone_name not in zones:
            # Try to match by wardrobe name
            wardrobe = char.db.wardrobe or {}
            if args.lower() in wardrobe:
                item = wardrobe[args.lower()]
                zone_name = item.get("zone", "")
                if zone_name not in zones:
                    self.msg(
                        f"No zone '{zone_name}' found."
                    )
                    return
            else:
                self.msg(
                    f"No zone named '{zone_name}'.\n"
                    f"Type 'zone list' to see all zones."
                )
                return

        zone = zones[zone_name]
        zone_type = zone.get("zone_type", "surface")
        covered = zone.get("covered_by")
        contents = zone.get("contents", [])

        # Orifice removal
        if modifier.isdigit():
            idx = int(modifier) - 1
            if not contents:
                self.msg(
                    f"Nothing in zone '{zone_name}'."
                )
                return
            result = char.remove_from_zone(zone_name, idx)
            if result:
                self.msg(
                    f"Removed item #{int(modifier)} "
                    f"from zone |w{zone_name}|n."
                )
            return

        if modifier == "all":
            result = char.remove_from_zone(zone_name, None)
            if result:
                self.msg(
                    f"Cleared all contents from "
                    f"zone |w{zone_name}|n."
                )
            return

        # Surface removal
        if not covered:
            self.msg(
                f"Zone '{zone_name}' isn't covered."
            )
            return

        worn = covered.get(
            "worn_desc",
            covered.get("desc", "")
        )

        result = char.remove_from_zone(zone_name)

        if result:
            name = char.db.rp_name or char.key

            if modifier == "here":
                # Item stays in scene as removed_but_present
                # For now just note it in the message
                self.msg(
                    f"You remove {worn} "
                    f"[zone: {zone_name}].\n"
                    f"|x[Left in the scene nearby.]|n"
                )
                char.location.msg_contents(
                    f"{name} removes {worn}.",
                    exclude=char
                )
            else:
                self.msg(
                    f"You remove {worn} "
                    f"[zone: {zone_name}]."
                )
                char.location.msg_contents(
                    f"{name} removes {worn}.",
                    exclude=char
                )
        else:
            self.msg("Could not remove item from zone.")


class CmdInsert(MuxCommand):
    """
    Place a freeform descriptor inside an orifice zone.

    Orifice zones can hold multiple items simultaneously.
    Requires appropriate consent flags.

    Usage:
        insert <zone> <description>
        insert <zone>               — see zone contents

    Example:
        insert mouth a gag — leather-covered, buckled at the back

    Requires: mature consent
    """
    key = "insert"
    aliases = ["fill"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            self.msg(
                "Usage: insert <zone> <description>"
            )
            return

        parts = args.split(None, 1)
        zone_name = parts[0].lower().replace(" ", "_")

        # No description — show contents
        if len(parts) == 1:
            zones = char._get_zones()
            if zone_name not in zones:
                self.msg(f"No zone named '{zone_name}'.")
                return
            contents = zones[zone_name].get("contents", [])
            if contents:
                lines = [
                    f"Contents of zone |w{zone_name}|n:\n"
                ]
                for i, item in enumerate(contents, 1):
                    desc = item.get("desc", "")
                    state = item.get("state", "inserted")
                    lines.append(
                        f"  [{i}] {desc} ({state})"
                    )
                self.msg("\n".join(lines))
            else:
                self.msg(
                    f"Zone |w{zone_name}|n is empty."
                )
            return

        descriptor = parts[1].strip()
        zones = char._get_zones()

        if zone_name not in zones:
            self.msg(
                f"No zone named '{zone_name}'.\n"
                f"Type 'zone list' to see all zones."
            )
            return

        zone = zones[zone_name]
        zone_type = zone.get("zone_type", "surface")

        if zone_type == "surface":
            self.msg(
                f"Zone '{zone_name}' is a surface zone.\n"
                f"Use 'wear {zone_name} <description>' instead."
            )
            return

        # Consent check for self-insertion
        if not char.has_consent("mature"):
            self.msg(
                "Mature consent is required for this interaction.\n"
                "Enable it with: consent give mature"
            )
            return

        result = char.insert_into_zone(
            zone_name,
            descriptor,
            state="inserted",
            set_by=char.id,
            removable_by=[char.id],
        )

        if result:
            self.msg(
                f"[zone: {zone_name}] {descriptor}\n"
                f"|x[Remove with: remove {zone_name} 1]|n"
            )
        else:
            self.msg("Could not insert into zone.")


class CmdUndress(MuxCommand):
    """
    Remove all clothing from all zones simultaneously.

    Usage:
        undress             — remove everything
        undress/keep        — remove but keep in wardrobe

    Any unsaved freeform descriptors will be lost.
    """
    key = "undress"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        zones = char._get_zones()

        cleared = []
        for zone_name, zone_data in zones.items():
            if zone_data.get("covered_by"):
                zone_data["covered_by"] = None
                zone_data["state"] = "pristine"
                zone_data["state_desc"] = None
                cleared.append(zone_name)

        if cleared:
            char.db.zones = zones
            char._rebuild_outfit_desc()
            name = char.db.rp_name or char.key
            self.msg(
                f"You undress. {len(cleared)} zone(s) cleared."
            )
            char.location.msg_contents(
                f"{name} undresses.",
                exclude=char
            )
        else:
            self.msg("You aren't wearing anything.")


class CmdDress(MuxCommand):
    """
    Apply an outfit preset.

    Usage:
        dress               — apply default preset
        dress <name>        — apply named preset
        dress/list          — list saved presets

    Save a preset with: outfit save "<name>"
    """
    key = "dress"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "list" in self.switches:
            presets = char.db.outfit_presets or {}
            if not presets:
                self.msg("No outfit presets saved.")
                return
            lines = ["|wSaved outfit presets:|n\n"]
            for name, preset in presets.items():
                zone_count = len(preset)
                lines.append(
                    f"  |w{name}|n — {zone_count} zone(s)"
                )
            self.msg("\n".join(lines))
            return

        preset_name = self.args.strip() or "default"
        presets = char.db.outfit_presets or {}

        if preset_name not in presets:
            self.msg(
                f"No preset named '{preset_name}'.\n"
                f"Type 'dress/list' to see saved presets."
            )
            return

        preset = presets[preset_name]
        zones = char._get_zones()
        applied = []

        for zone_name, item_data in preset.items():
            if zone_name not in zones:
                continue
            zones[zone_name]["covered_by"] = item_data
            applied.append(zone_name)

        if applied:
            char.db.zones = zones
            char._rebuild_outfit_desc()
            name = char.db.rp_name or char.key
            self.msg(
                f"You dress in preset '{preset_name}'. "
                f"{len(applied)} zone(s) covered."
            )
            char.location.msg_contents(
                f"{name} dresses.",
                exclude=char
            )
        else:
            self.msg(
                f"Preset '{preset_name}' is empty "
                f"or zones don't exist."
            )


class CmdStraighten(MuxCommand):
    """
    Reset dishevelment on clothing.

    Usage:
        straighten              — straighten everything
        straighten <zone>       — straighten one zone

    Example:
        straighten
        straighten coat
        straighten collar
    """
    key = "straighten"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        zone_name = self.args.strip() or None

        reset = char.straighten(zone_name)

        if reset:
            name = char.db.rp_name or char.key
            if zone_name:
                self.msg(
                    f"You straighten "
                    f"{', '.join(reset)}."
                )
            else:
                self.msg(
                    f"You take a moment to set yourself "
                    f"to rights — "
                    f"{', '.join(reset)} "
                    f"reset to pristine."
                )
            char.location.msg_contents(
                f"{name} straightens their clothing.",
                exclude=char
            )
        else:
            if zone_name:
                self.msg(
                    f"Zone '{zone_name}' doesn't need "
                    f"straightening."
                )
            else:
                self.msg("Nothing needs straightening.")


# -------------------------------------------------------------------
# Wardrobe commands
# -------------------------------------------------------------------

class CmdWardrobe(MuxCommand):
    """
    Manage your character's wardrobe.

    The wardrobe stores named descriptors that can be
    applied to zones quickly. No game objects required.

    Usage:
        wardrobe                            — list wardrobe
        wardrobe save <zone> "<name>"       — save current zone desc
        wardrobe wear "<name>"              — apply saved descriptor
        wardrobe show "<name>"              — examine saved item
        wardrobe examine "<name>" <text>    — set examine desc
        wardrobe ambient "<name>" add <line>— add ambient line
        wardrobe remove "<name>"            — delete from wardrobe
    """
    key = "wardrobe"
    aliases = ["wb"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            self._wardrobe_list(char)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        dispatch = {
            "save":    self._wardrobe_save,
            "wear":    self._wardrobe_wear,
            "show":    self._wardrobe_show,
            "examine": self._wardrobe_examine,
            "ambient": self._wardrobe_ambient,
            "remove":  self._wardrobe_remove,
            "list":    lambda c, r: self._wardrobe_list(c),
        }

        handler = dispatch.get(subcmd)
        if handler:
            handler(char, rest)
        else:
            self._wardrobe_list(char)

    def _wardrobe_list(self, char):
        wardrobe = char.db.wardrobe or {}
        if not wardrobe:
            self.msg(
                "Your wardrobe is empty.\n"
                "Save a zone descriptor with: "
                "wardrobe save <zone> \"<name>\""
            )
            return

        lines = ["|wYour wardrobe:|n\n"]
        for name, item in sorted(wardrobe.items()):
            zone = item.get("zone", "unknown")
            desc = item.get("worn_desc",
                            item.get("desc", ""))
            has_examine = bool(item.get("examine_desc"))
            has_ambient = bool(item.get("ambient"))

            extras = []
            if has_examine:
                extras.append("examine")
            if has_ambient:
                extras.append("ambient")

            extra_str = (
                f" |x[{', '.join(extras)}]|n"
                if extras else ""
            )
            lines.append(
                f"  |w\"{name}\"|n [{zone}]{extra_str}\n"
                f"    {desc[:60]}"
                f"{'...' if len(desc) > 60 else ''}"
            )

        lines.append(
            f"\n|x{len(wardrobe)} item(s)|n  "
            f"Commands: wardrobe wear / wardrobe remove"
        )
        self.msg("\n".join(lines))

    def _wardrobe_save(self, char, args):
        """Save current zone covering to wardrobe."""
        # Parse: <zone> "<name>"
        import re
        match = re.match(
            r'(\S+)\s+"([^"]+)"', args.strip()
        )
        if not match:
            self.msg(
                "Usage: wardrobe save <zone> \"<name>\"\n"
                "Example: wardrobe save neck \"leather collar\""
            )
            return

        zone_name = match.group(1).lower().replace(" ", "_")
        item_name = match.group(2).lower()

        zones = char._get_zones()
        if zone_name not in zones:
            self.msg(f"No zone named '{zone_name}'.")
            return

        covered = zones[zone_name].get("covered_by")
        if not covered:
            self.msg(
                f"Zone '{zone_name}' isn't covered. "
                f"Wear something first."
            )
            return

        wardrobe = char.db.wardrobe or {}
        wardrobe[item_name] = {
            "zone":         zone_name,
            "desc":         covered.get("desc", ""),
            "worn_desc":    covered.get("worn_desc", ""),
            "examine_desc": covered.get("examine_desc", ""),
            "ambient":      covered.get("ambient", []),
            "type":         "freeform",
            "item_id":      covered.get("item_id"),
        }
        char.db.wardrobe = wardrobe

        self.msg(
            f"Saved to wardrobe as |w\"{item_name}\"|n "
            f"[zone: {zone_name}]."
        )

    def _wardrobe_wear(self, char, args):
        """Apply a saved wardrobe item to its zone."""
        import re
        match = re.match(r'"([^"]+)"', args.strip())
        item_name = (
            match.group(1).lower()
            if match
            else args.strip().lower()
        )

        wardrobe = char.db.wardrobe or {}
        if item_name not in wardrobe:
            self.msg(
                f"No wardrobe item named \"{item_name}\".\n"
                f"Type 'wardrobe' to see your wardrobe."
            )
            return

        item = wardrobe[item_name]
        zone_name = item.get("zone", "")
        zones = char._get_zones()

        if zone_name not in zones:
            self.msg(
                f"Zone '{zone_name}' no longer exists."
            )
            return

        zones[zone_name]["covered_by"] = {
            "desc":         item.get("desc", ""),
            "worn_desc":    item.get("worn_desc", ""),
            "examine_desc": item.get("examine_desc", ""),
            "ambient":      item.get("ambient", []),
            "state":        "pristine",
            "state_desc":   None,
            "state_ambient":[],
            "type":         item.get("type", "freeform"),
            "item_id":      item.get("item_id"),
            "set_by":       char.id,
        }
        char.db.zones = zones
        char._rebuild_outfit_desc()

        worn = item.get("worn_desc", item.get("desc", ""))
        name = char.db.rp_name or char.key

        self.msg(
            f"You wear {worn} [zone: {zone_name}]."
        )
        char.location.msg_contents(
            f"{name} puts on {worn}.",
            exclude=char
        )

    def _wardrobe_show(self, char, args):
        """Show full detail of a wardrobe item."""
        import re
        match = re.match(r'"([^"]+)"', args.strip())
        item_name = (
            match.group(1).lower()
            if match
            else args.strip().lower()
        )

        wardrobe = char.db.wardrobe or {}
        if item_name not in wardrobe:
            self.msg(
                f"No wardrobe item named \"{item_name}\"."
            )
            return

        item = wardrobe[item_name]
        lines = [
            f"|w\"{item_name}\"|n\n",
            f"  Zone:    {item.get('zone', 'unknown')}",
            f"  Type:    {item.get('type', 'freeform')}",
            "",
            "|wWorn description:|n",
            f"  {item.get('worn_desc', item.get('desc', 'not set'))}",
        ]

        examine = item.get("examine_desc", "")
        if examine:
            lines.extend([
                "",
                "|wExamine description:|n",
                f"  {examine}",
            ])

        ambient = item.get("ambient", [])
        if ambient:
            lines.extend([
                "",
                f"|wAmbient lines:|n ({len(ambient)} lines)",
            ])
            for i, line in enumerate(ambient, 1):
                lines.append(f"  {i}. {line}")

        self.msg("\n".join(lines))

    def _wardrobe_examine(self, char, args):
        """Set examine description for a wardrobe item."""
        import re
        match = re.match(
            r'"([^"]+)"\s+(.*)', args.strip()
        )
        if not match:
            self.msg(
                "Usage: wardrobe examine \"<name>\" <text>"
            )
            return

        item_name = match.group(1).lower()
        examine_desc = match.group(2).strip()

        wardrobe = char.db.wardrobe or {}
        if item_name not in wardrobe:
            self.msg(
                f"No wardrobe item named \"{item_name}\"."
            )
            return

        wardrobe[item_name]["examine_desc"] = examine_desc
        char.db.wardrobe = wardrobe
        self.msg(
            f"Examine description set for "
            f"|w\"{item_name}\"|n."
        )

    def _wardrobe_ambient(self, char, args):
        """Manage ambient lines for a wardrobe item."""
        import re
        match = re.match(
            r'"([^"]+)"\s+(\S+)(?:\s+(.*))?', args.strip()
        )
        if not match:
            self.msg(
                "Usage:\n"
                "  wardrobe ambient \"<name>\" add <line>\n"
                "  wardrobe ambient \"<name>\" list\n"
                "  wardrobe ambient \"<name>\" remove <#>"
            )
            return

        item_name = match.group(1).lower()
        subcmd = match.group(2).lower()
        rest = match.group(3) or ""

        wardrobe = char.db.wardrobe or {}
        if item_name not in wardrobe:
            self.msg(
                f"No wardrobe item named \"{item_name}\"."
            )
            return

        ambient = wardrobe[item_name].get("ambient", [])

        if subcmd == "list":
            if not ambient:
                self.msg(
                    f"No ambient lines for \"{item_name}\"."
                )
                return
            lines = [
                f"|wAmbient lines for \"{item_name}\":|n\n"
            ]
            for i, line in enumerate(ambient, 1):
                lines.append(f"  {i}. {line}")
            self.msg("\n".join(lines))

        elif subcmd == "add":
            if not rest:
                self.msg("Add what?")
                return
            ambient.append(rest.strip())
            wardrobe[item_name]["ambient"] = ambient
            char.db.wardrobe = wardrobe
            self.msg(
                f"Ambient line added to "
                f"|w\"{item_name}\"|n."
            )

        elif subcmd == "remove":
            try:
                idx = int(rest.strip()) - 1
                if idx < 0 or idx >= len(ambient):
                    self.msg(f"No line #{idx + 1}.")
                    return
                removed = ambient.pop(idx)
                wardrobe[item_name]["ambient"] = ambient
                char.db.wardrobe = wardrobe
                self.msg(f"Removed: {removed}")
            except ValueError:
                self.msg("Please provide a number.")

    def _wardrobe_remove(self, char, args):
        """Remove an item from the wardrobe."""
        import re
        match = re.match(r'"([^"]+)"', args.strip())
        item_name = (
            match.group(1).lower()
            if match
            else args.strip().lower()
        )

        wardrobe = char.db.wardrobe or {}
        if item_name not in wardrobe:
            self.msg(
                f"No wardrobe item named \"{item_name}\"."
            )
            return

        del wardrobe[item_name]
        char.db.wardrobe = wardrobe
        self.msg(
            f"Removed |w\"{item_name}\"|n from wardrobe."
        )


# -------------------------------------------------------------------
# Outfit preset commands
# -------------------------------------------------------------------

class CmdOutfit(MuxCommand):
    """
    Manage outfit presets.

    An outfit preset is a named collection of wardrobe
    entries applied simultaneously. One command changes
    your entire look.

    Usage:
        outfit list                     — list saved presets
        outfit save "<name>"            — save current zones as preset
        outfit wear "<name>"            — apply a preset
        outfit show "<name>"            — preview a preset
        outfit remove "<name>"          — delete a preset
    """
    key = "outfit"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args or args == "list":
            self._outfit_list(char)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        dispatch = {
            "list":   lambda c, r: self._outfit_list(c),
            "save":   self._outfit_save,
            "wear":   self._outfit_wear,
            "show":   self._outfit_show,
            "remove": self._outfit_remove,
        }

        handler = dispatch.get(subcmd)
        if handler:
            handler(char, rest)
        else:
            self.msg(
                "Usage: outfit save/wear/show/remove/list"
            )

    def _outfit_list(self, char):
        presets = char.db.outfit_presets or {}
        if not presets:
            self.msg(
                "No outfit presets saved.\n"
                "Save one with: outfit save \"<name>\""
            )
            return

        lines = ["|wSaved outfit presets:|n\n"]
        for name, preset in sorted(presets.items()):
            zone_count = len(preset)
            lines.append(
                f"  |w\"{name}\"|n — {zone_count} zone(s)"
            )
        lines.append(
            "\nApply with: outfit wear \"<name>\""
        )
        self.msg("\n".join(lines))

    def _outfit_save(self, char, args):
        import re
        match = re.match(r'"([^"]+)"', args.strip())
        name = (
            match.group(1).lower()
            if match
            else args.strip().lower()
        )

        if not name:
            self.msg(
                "Usage: outfit save \"<name>\""
            )
            return

        zones = char._get_zones()
        preset = {}

        for zone_name, zone_data in zones.items():
            covered = zone_data.get("covered_by")
            if covered:
                preset[zone_name] = dict(covered)

        # Also snapshot freeform items
        freeform = char.db.freeform_items or {}
        if freeform:
            preset["__freeform__"] = {
                k: dict(v) for k, v in freeform.items()
            }

        presets = char.db.outfit_presets or {}
        presets[name] = preset
        char.db.outfit_presets = presets
        char.db.current_outfit = name

        zone_count = sum(
            1 for k in preset if not k.startswith("__")
        )
        freeform_count = len(freeform)
        summary = f"{zone_count} zone(s)"
        if freeform_count:
            summary += f", {freeform_count} freeform item(s)"
        self.msg(
            f"Outfit |w\"{name}\"|n saved ({summary})."
        )

    def _outfit_wear(self, char, args):
        import re
        match = re.match(r'"([^"]+)"', args.strip())
        name = (
            match.group(1).lower()
            if match
            else args.strip().lower()
        )

        presets = char.db.outfit_presets or {}
        if name not in presets:
            self.msg(
                f"No preset named \"{name}\".\n"
                f"Type 'outfit list' to see saved presets."
            )
            return

        preset = presets[name]
        zones = char._get_zones()

        # First undress all zones
        for zone_name in zones:
            zones[zone_name]["covered_by"] = None

        # Apply zone coverings (skip internal keys)
        applied = []
        for zone_name, item_data in preset.items():
            if zone_name.startswith("__"):
                continue
            if zone_name in zones:
                zones[zone_name]["covered_by"] = dict(item_data)
                applied.append(zone_name)

        char.db.zones = zones
        char.db.current_outfit = name
        char._rebuild_outfit_desc()

        # Restore freeform items if saved in the preset
        saved_freeform = preset.get("__freeform__")
        if saved_freeform is not None:
            char.db.freeform_items = {
                k: dict(v) for k, v in saved_freeform.items()
            }
            freeform_count = len(saved_freeform)
        else:
            freeform_count = 0

        char_name = char.db.rp_name or char.key
        summary = f"{len(applied)} zone(s) covered"
        if freeform_count:
            summary += f", {freeform_count} freeform item(s) restored"
        self.msg(
            f"You dress in outfit |w\"{name}\"|n ({summary})."
        )
        char.location.msg_contents(
            f"{char_name} changes outfits.",
            exclude=char
        )

    def _outfit_show(self, char, args):
        import re
        match = re.match(r'"([^"]+)"', args.strip())
        name = (
            match.group(1).lower()
            if match
            else args.strip().lower()
        )

        presets = char.db.outfit_presets or {}
        if name not in presets:
            self.msg(f"No preset named \"{name}\".")
            return

        preset = presets[name]
        lines = [f"|wOutfit: \"{name}\"|n\n"]

        for zone_name, item_data in preset.items():
            worn = item_data.get(
                "worn_desc",
                item_data.get("desc", "")
            )
            lines.append(
                f"  |w{zone_name}|n: {worn}"
            )

        if not preset:
            lines.append("  |x[empty preset]|n")

        self.msg("\n".join(lines))

    def _outfit_remove(self, char, args):
        import re
        match = re.match(r'"([^"]+)"', args.strip())
        name = (
            match.group(1).lower()
            if match
            else args.strip().lower()
        )

        presets = char.db.outfit_presets or {}
        if name not in presets:
            self.msg(f"No preset named \"{name}\".")
            return

        del presets[name]
        char.db.outfit_presets = presets
        self.msg(f"Preset |w\"{name}\"|n removed.")


# -------------------------------------------------------------------
# Marking commands
# -------------------------------------------------------------------

class CmdMarking(MuxCommand):
    """
    Manage permanent markings on your character.

    Markings are tattoos, scars, piercings, and other
    permanent physical details with their own visibility
    and ambient contribution.

    Usage:
        marking list                            — list all markings
        marking add <location> = <description>  — add a marking
        marking show <#>                        — show marking detail
        marking visibility <#> <level>          — set visibility
        marking intimate <#> <on/off>           — flag as intimate
        marking ambient <#> add <line>          — add ambient line
        marking ambient <#> list                — list ambient lines
        marking ambient <#> remove <line#>      — remove ambient line
        marking remove <#>                      — remove a marking

    Example:
        marking add left wrist, inner = A small mark —
        deliberate, simple, the kind that means something.
    """
    key = "marking"
    aliases = ["markings"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args or args == "list":
            self._marking_list(char)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        dispatch = {
            "list":       lambda c, r: self._marking_list(c),
            "add":        self._marking_add,
            "show":       self._marking_show,
            "visibility": self._marking_visibility,
            "intimate":   self._marking_intimate,
            "ambient":    self._marking_ambient,
            "remove":     self._marking_remove,
        }

        handler = dispatch.get(subcmd)
        if handler:
            handler(char, rest)
        else:
            self.msg(
                "Usage: marking add/show/remove/list/visibility"
            )

    def _marking_list(self, char):
        markings = char.db.markings or []
        if not markings:
            self.msg(
                "No markings set.\n"
                "Add one with: "
                "marking add <location> = <description>"
            )
            return

        lines = ["|wYour markings:|n\n"]
        for i, marking in enumerate(markings, 1):
            name = marking.get("name", "unnamed")
            location = marking.get("location", "unknown")
            visibility = marking.get("visibility", "examine")
            intimate = marking.get("intimate", False)
            ambient_count = len(marking.get("ambient", []))

            intimate_tag = " |m♦|n" if intimate else ""
            lines.append(
                f"  [{i}] |w{name}|n{intimate_tag}\n"
                f"       Location: {location} | "
                f"Visibility: {visibility}"
                + (
                    f" | {ambient_count} ambient line(s)"
                    if ambient_count else ""
                )
            )

        self.msg("\n".join(lines))

    def _marking_add(self, char, args):
        if "=" not in args:
            self.msg(
                "Usage: marking add <location> = <description>\n"
                "Example: marking add left wrist, inner = "
                "A small deliberate mark."
            )
            return

        location, _, desc = args.partition("=")
        location = location.strip()
        desc = desc.strip()

        if not location or not desc:
            self.msg(
                "Both location and description are required."
            )
            return

        markings = char.db.markings or []
        markings.append({
            "name":             location,
            "location":         location,
            "desc":             desc,
            "visibility":       "examine",
            "intimate":         False,
            "ambient":          [],
            "consent_to_touch": "casual",
        })
        char.db.markings = markings

        self.msg(
            f"Marking added (#{len(markings)}): "
            f"|w{location}|n\n"
            f"Set visibility with: "
            f"marking visibility {len(markings)} <level>"
        )

    def _marking_show(self, char, args):
        if not args:
            self.msg("Show which marking? Usage: marking show <#>")
            return

        try:
            idx = int(args.strip()) - 1
        except ValueError:
            self.msg("Please provide a number.")
            return

        markings = char.db.markings or []
        if idx < 0 or idx >= len(markings):
            self.msg(
                f"No marking #{idx + 1}. "
                f"You have {len(markings)} markings."
            )
            return

        marking = markings[idx]
        ambient = marking.get("ambient", [])
        lines = [
            f"|wMarking #{idx + 1}:|n\n",
            f"  Location:   {marking.get('location', 'unknown')}",
            f"  Visibility: {marking.get('visibility', 'examine')}",
            f"  Intimate:   "
            f"{'yes' if marking.get('intimate') else 'no'}",
            "",
            "|wDescription:|n",
            f"  {marking.get('desc', 'not set')}",
        ]

        if ambient:
            lines.extend([
                "",
                f"|wAmbient lines:|n",
            ])
            for i, line in enumerate(ambient, 1):
                lines.append(f"  {i}. {line}")

        self.msg("\n".join(lines))

    def _marking_visibility(self, char, args):
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            levels = " / ".join(ZONE_VISIBILITY.keys())
            self.msg(
                f"Usage: marking visibility <#> <level>\n"
                f"Levels: {levels}"
            )
            return

        try:
            idx = int(parts[0]) - 1
        except ValueError:
            self.msg("Please provide a number.")
            return

        level = parts[1].lower()
        if level not in ZONE_VISIBILITY:
            self.msg(
                f"Unknown level '{level}'.\n"
                f"Valid: {', '.join(ZONE_VISIBILITY.keys())}"
            )
            return

        markings = char.db.markings or []
        if idx < 0 or idx >= len(markings):
            self.msg(f"No marking #{idx + 1}.")
            return

        markings[idx]["visibility"] = level
        char.db.markings = markings
        self.msg(
            f"Marking #{idx + 1} visibility set to "
            f"|w{level}|n."
        )

    def _marking_intimate(self, char, args):
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            self.msg(
                "Usage: marking intimate <#> <on/off>"
            )
            return

        try:
            idx = int(parts[0]) - 1
        except ValueError:
            self.msg("Please provide a number.")
            return

        setting = parts[1].lower()
        if setting not in ("on", "off"):
            self.msg("Usage: marking intimate <#> <on/off>")
            return

        markings = char.db.markings or []
        if idx < 0 or idx >= len(markings):
            self.msg(f"No marking #{idx + 1}.")
            return

        markings[idx]["intimate"] = (setting == "on")
        char.db.markings = markings
        self.msg(
            f"Marking #{idx + 1} intimate flag: "
            f"|w{setting}|n."
        )

    def _marking_ambient(self, char, args):
        parts = args.strip().split(None, 2)
        if len(parts) < 2:
            self.msg(
                "Usage:\n"
                "  marking ambient <#> add <line>\n"
                "  marking ambient <#> list\n"
                "  marking ambient <#> remove <line#>"
            )
            return

        try:
            idx = int(parts[0]) - 1
        except ValueError:
            self.msg("Please provide a marking number.")
            return

        markings = char.db.markings or []
        if idx < 0 or idx >= len(markings):
            self.msg(f"No marking #{idx + 1}.")
            return

        subcmd = parts[1].lower()
        rest = parts[2] if len(parts) > 2 else ""
        ambient = markings[idx].get("ambient", [])

        if subcmd == "list":
            if not ambient:
                self.msg(
                    f"No ambient lines on marking #{idx + 1}."
                )
                return
            lines = [
                f"|wAmbient lines for marking #{idx + 1}:|n\n"
            ]
            for i, line in enumerate(ambient, 1):
                lines.append(f"  {i}. {line}")
            self.msg("\n".join(lines))

        elif subcmd == "add":
            if not rest:
                self.msg("Add what?")
                return
            ambient.append(rest.strip())
            markings[idx]["ambient"] = ambient
            char.db.markings = markings
            self.msg(
                f"Ambient line added to marking #{idx + 1}."
            )

        elif subcmd == "remove":
            try:
                line_idx = int(rest.strip()) - 1
                if line_idx < 0 or line_idx >= len(ambient):
                    self.msg(f"No line #{line_idx + 1}.")
                    return
                removed = ambient.pop(line_idx)
                markings[idx]["ambient"] = ambient
                char.db.markings = markings
                self.msg(f"Removed: {removed}")
            except ValueError:
                self.msg("Please provide a line number.")

    def _marking_remove(self, char, args):
        if not args:
            self.msg("Usage: marking remove <#>")
            return

        try:
            idx = int(args.strip()) - 1
        except ValueError:
            self.msg("Please provide a number.")
            return

        markings = char.db.markings or []
        if idx < 0 or idx >= len(markings):
            self.msg(
                f"No marking #{idx + 1}. "
                f"You have {len(markings)} markings."
            )
            return

        removed = markings.pop(idx)
        char.db.markings = markings
        self.msg(
            f"Marking removed: "
            f"{removed.get('location', 'unknown')}"
        )


# -------------------------------------------------------------------
# Title commands
# -------------------------------------------------------------------

class CmdTitle(MuxCommand):
    """
    Manage your character's title components.

    Your title is assembled from up to five parts:
    PREFIX  LEVEL  INTERFIX  FACTION  SUFFIX

    The LEVEL component is set by your reputation tier.
    All other components are player-set.

    Usage:
        title show              — see assembled title
        title prefix <text>     — set prefix
        title prefix/clear      — clear prefix
        title interfix <text>   — set interfix
        title interfix/clear    — clear interfix
        title suffix <text>     — set suffix
        title suffix/clear      — clear suffix

    Example:
        title prefix The Calculating
        title interfix Voice of the
        title suffix of the Western Holds

        Result: The Calculating [Level] Voice of the [Faction]
                of the Western Holds
    """
    key = "title"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args or args == "show":
            title = char.get_full_title()
            name = char.db.rp_name or char.key
            self.msg(
                f"Current title assembly:\n\n"
                f"  |w{name}|n\n"
                f"  |x{title}|n\n\n"
                f"Components:\n"
                f"  Prefix:   "
                f"{char.db.title_prefix or '[not set]'}\n"
                f"  Level:    "
                f"{char.db.title_level or '[not set]'} "
                f"(reputation-driven)\n"
                f"  Interfix: "
                f"{char.db.title_interfix or '[not set]'}\n"
                f"  Faction:  "
                f"{char.db.title_faction or '[not set]'} "
                f"(faction-driven)\n"
                f"  Suffix:   "
                f"{char.db.title_suffix or '[not set]'}"
            )
            return

        parts = args.split(None, 1)
        component = parts[0].lower()
        value = parts[1].strip() if len(parts) > 1 else ""

        clearing = "clear" in self.switches

        if component == "prefix":
            if clearing:
                char.db.title_prefix = ""
                self.msg("Title prefix cleared.")
            elif value:
                char.db.title_prefix = value
                self.msg(f"Title prefix set: |w{value}|n")
            else:
                self.msg(
                    f"Current prefix: "
                    f"{char.db.title_prefix or '[not set]'}"
                )

        elif component == "interfix":
            if clearing:
                char.db.title_interfix = ""
                self.msg("Title interfix cleared.")
            elif value:
                char.db.title_interfix = value
                self.msg(f"Title interfix set: |w{value}|n")
            else:
                self.msg(
                    f"Current interfix: "
                    f"{char.db.title_interfix or '[not set]'}"
                )

        elif component == "suffix":
            if clearing:
                char.db.title_suffix = ""
                self.msg("Title suffix cleared.")
            elif value:
                char.db.title_suffix = value
                self.msg(f"Title suffix set: |w{value}|n")
            else:
                self.msg(
                    f"Current suffix: "
                    f"{char.db.title_suffix or '[not set]'}"
                )

        else:
            self.msg(
                "Usage: title prefix/interfix/suffix <text>\n"
                "Or: title show"
            )


# -------------------------------------------------------------------
# RP hooks
# -------------------------------------------------------------------

class CmdRPHook(MuxCommand):
    """
    Manage your character's RP hooks.

    RP hooks are short lines advertising available RP.
    Shown on your character sheet.

    Usage:
        rphook list                 — list current hooks
        rphook add <text>           — add a hook
        rphook remove <#>           — remove a hook by number
        rphook clear                — clear all hooks
    """
    key = "rphook"
    aliases = ["hook"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        args = self.args.strip()
        hooks = char.db.rp_hooks or []

        if not args or args == "list":
            if not hooks:
                self.msg(
                    "No RP hooks set.\n"
                    "Add one with: rphook add <text>"
                )
                return
            lines = ["|wYour RP hooks:|n\n"]
            for i, hook in enumerate(hooks, 1):
                lines.append(f"  {i}. {hook}")
            self.msg("\n".join(lines))
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if subcmd == "add":
            if not rest:
                self.msg("Add what? Usage: rphook add <text>")
                return
            if len(rest) > 200:
                self.msg(
                    "Hook too long. "
                    "Keep it under 200 characters."
                )
                return
            hooks.append(rest.strip())
            char.db.rp_hooks = hooks
            self.msg(
                f"RP hook added (#{len(hooks)}):\n"
                f"  {rest.strip()}"
            )

        elif subcmd == "remove":
            if not rest:
                self.msg(
                    "Remove which? "
                    "Usage: rphook remove <#>"
                )
                return
            try:
                idx = int(rest.strip()) - 1
                if idx < 0 or idx >= len(hooks):
                    self.msg(
                        f"No hook #{idx + 1}. "
                        f"You have {len(hooks)} hooks."
                    )
                    return
                removed = hooks.pop(idx)
                char.db.rp_hooks = hooks
                self.msg(f"Removed: {removed}")
            except ValueError:
                self.msg("Please provide a number.")

        elif subcmd == "clear":
            char.db.rp_hooks = []
            self.msg("All RP hooks cleared.")

        else:
            # Treat as add if no recognized subcommand
            hooks.append(args.strip())
            char.db.rp_hooks = hooks
            self.msg(
                f"RP hook added (#{len(hooks)})."
            )


# -------------------------------------------------------------------
# Character sheet
# -------------------------------------------------------------------

class CmdSheet(MuxCommand):
    """
    View a character sheet.

    Shows name, title, bio, reputation, RP hooks,
    consent flags, and faction.

    Usage:
        sheet               — your own sheet
        sheet <name>        — another character's sheet
    """
    key = "sheet"
    aliases = ["sc", "profile"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if self.args:
            # Look up another character
            target = char.search(
                self.args.strip(),
                location=char.location
            )
            if not target:
                return
        else:
            target = char

        self.msg(self._build_sheet(target, char))

    def _build_sheet(self, target, looker):
        from typeclasses.characters import DEFAULT_ZONE_TYPES

        is_self = target == looker
        sep = "|w" + "━" * 44 + "|n"
        thin = "|x" + "─" * 44 + "|n"

        name = target.db.rp_name or target.key
        title = target.get_full_title() if hasattr(target, 'get_full_title') else ""
        bio = target.db.public_bio or ""
        rep = target.db.reputation or 0
        tier = target.get_reputation_tier() if hasattr(target, 'get_reputation_tier') else "Unknown"
        species = target.db.species or "human"
        age = target.db.apparent_age or ""
        scene_count = target.db.scene_count or 0
        faction = target.db.title_faction or ""
        faction_rank = target.db.faction_rank or ""

        # Bio fields
        bio_fields = target.db.bio_fields or []
        bio_order = target.db.bio_field_order or []
        if bio_order:
            field_map = {f["name"].lower(): f for f in bio_fields}
            ordered_fields = []
            for fname in bio_order:
                f = field_map.get(fname.lower())
                if f:
                    ordered_fields.append(f)
            # append any fields not in order list
            ordered_names = {n.lower() for n in bio_order}
            for f in bio_fields:
                if f["name"].lower() not in ordered_names:
                    ordered_fields.append(f)
            bio_fields = ordered_fields

        # RP hooks
        hooks = target.db.rp_hooks or []

        # Zone availability — group by type
        zones = target.db.zones or {}
        zones_public = target.db.zones_public or False
        surface_zones, both_zones, attach_zones, orifice_zones, freeform_zones = [], [], [], [], []
        for zname, zdata in zones.items():
            ztype = zdata.get("zone_type") or DEFAULT_ZONE_TYPES.get(zname, "surface")
            is_default = zname in DEFAULT_ZONE_TYPES
            display = zname.replace("_", " ")
            if not is_default:
                freeform_zones.append(display)
            elif ztype == "surface":
                surface_zones.append(display)
            elif ztype == "both":
                both_zones.append(display)
            elif ztype == "attachment":
                attach_zones.append(display)
            elif ztype == "orifice":
                orifice_zones.append(display)

        # Build header
        lines = [f"\n{sep}", f"|w{name}|n"]
        if title:
            lines.append(f"|x{title}|n")
        lines.append("")

        # Bio paragraph
        if bio:
            lines.append(bio)
            lines.append("")

        # Core stats block
        stat_line = f"|xSpecies:|n  {species}"
        if age:
            stat_line += f"   |xApparent age:|n  {age}"
        lines.append(stat_line)
        lines.append(f"|xReputation:|n {rep} — {tier}")
        lines.append(f"|xScenes:|n     {scene_count}")
        if faction:
            fac_line = f"|xFaction:|n    {faction}"
            if faction_rank:
                fac_line += f"   |xRank:|n  {faction_rank}"
            lines.append(fac_line)

        # Custom bio fields
        if bio_fields:
            lines.append("")
            col = 16
            for field in bio_fields:
                fname = field.get("name", "")
                fval = field.get("value", "")
                if fname and fval:
                    lines.append(f"|x{fname + ':' :<{col}}|n {fval}")

        # RP Hooks
        if hooks:
            lines.append("")
            lines.append("|wRP Hooks:|n")
            for hook in hooks:
                lines.append(f"  * {hook}")

        # Zone availability
        lines.append("")
        lines.append(thin)
        lines.append("|xZones:|n")
        col = 12

        def _wrap_zones(zone_list, width=60):
            """Wrap a zone list into a comma-joined string."""
            return ", ".join(sorted(zone_list))

        if surface_zones:
            lines.append(f"  {'surface':<{col}}{_wrap_zones(surface_zones)}")
        if both_zones:
            lines.append(f"  {'both':<{col}}{_wrap_zones(both_zones)}")
        if attach_zones:
            lines.append(f"  {'attachment':<{col}}{_wrap_zones(attach_zones)}")
        if freeform_zones:
            lines.append(f"  {'freeform':<{col}}{_wrap_zones(freeform_zones)}")
        if orifice_zones and (is_self or zones_public):
            lines.append(f"  {'orifice':<{col}}{_wrap_zones(orifice_zones)}")
        if not (is_self or zones_public) and orifice_zones:
            lines.append(f"  |x[intimate zones hidden]|n")

        # Own sheet extras
        if is_self:
            # Consent flags
            flags = target.db.consent_flags or {}
            lines.append("")
            lines.append(thin)
            lines.append("|wConsent flags:|n")
            flag_labels = {
                "casual":      "Casual RP",
                "intimate":    "Intimate",
                "mature":      "Mature content",
                "bdsm":        "BDSM",
                "lead_follow": "Lead / follow",
                "restraint":   "Restraint",
                "plock":       "Permanent locks",
            }
            for flag, value in flags.items():
                label = flag_labels.get(flag, flag.capitalize())
                status = "|gYES|n" if value else "|rno|n"
                lines.append(f"  {label + ':':<20} {status}")

            # Contacts summary
            contacts = target.db.contacts or {}
            if contacts:
                lines.append("")
                lines.append(thin)
                lines.append("|wContacts:|n")
                for cid, cdata in contacts.items():
                    cname = cdata.get("name", f"#{cid}")
                    cstatus = cdata.get("status", "")
                    status_str = f"  |x[{cstatus}]|n" if cstatus else ""
                    lines.append(f"  |w{cname}|n{status_str}")

        lines.append(f"\n{sep}")
        return "\n".join(lines)


# -------------------------------------------------------------------
# Character consent commands
# -------------------------------------------------------------------

class CmdConsent(MuxCommand):
    """
    Manage your character's consent flags.

    Consent flags control what interactions are available to others
    with your character. Flags are global (on for everyone), but
    per-player overrides let you allow or block specific people
    regardless of the global setting.

    Usage:
        consent                             — see all flags and overrides
        consent on <type>                   — enable globally
        consent off <type>                  — disable globally
        consent allow <type|all> <name>     — allow this person (even if global is off)
        consent block <type|all> <name>     — block this person (even if global is on)
        consent unblock <type|all> <name>   — remove per-player override

    Aliases: 'give' = 'on', 'revoke' = 'off'

    Types: casual / intimate / mature / bdsm / lead_follow / restraint / plock
    """
    key = "consent"
    locks = "cmd:all()"
    help_category = "Character"

    # General consent tiers
    TIER_TYPES = [
        "casual", "intimate", "mature",
        "bdsm", "lead_follow", "restraint", "plock",
    ]
    # Specific acts (formerly perm-tier emotes)
    ACT_TYPES = [
        "undress", "blindfold", "gag", "tieup",
        "strip", "examclose", "restrain", "claimmark",
    ]
    VALID_CONSENT_TYPES = TIER_TYPES + ACT_TYPES

    CONSENT_LABELS = {
        # Tiers
        "casual":      "Casual RP",
        "intimate":    "Intimate",
        "mature":      "Mature content",
        "bdsm":        "BDSM",
        "lead_follow": "Lead / follow",
        "restraint":   "Restraint",
        "plock":       "Permanent locks",
        # Acts
        "undress":     "Undress",
        "blindfold":   "Blindfold",
        "gag":         "Gag",
        "tieup":       "Tie up",
        "strip":       "Strip",
        "examclose":   "Examine closely",
        "restrain":    "Restrain",
        "claimmark":   "Claimmark",
    }

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            self._show_consent(char)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if subcmd in ("allow", "on", "give"):
            self._allow_consent(char, rest)
        elif subcmd in ("disallow", "off", "revoke", "block"):
            self._disallow_consent(char, rest)
        elif subcmd == "unblock":
            self._unblock_consent(char, rest)
        else:
            self.msg(
                "Usage: consent allow <type|all> [name]\n"
                "       consent disallow <type|all> [name]\n"
                "       consent unblock <type|all> <name>\n"
                f"Types: {', '.join(self.VALID_CONSENT_TYPES)}, all"
            )

    def _show_consent(self, char):
        flags = char.db.consent_flags or {}
        overrides = char.db.consent_overrides or {}
        allow_map = overrides.get("allow", {})
        block_map = overrides.get("block", {})

        def flag_line(flag):
            value = flags.get(flag, False)
            label = self.CONSENT_LABELS.get(flag, flag.capitalize())
            status = "|gon|n " if value else "|roff|n"
            allowed_ids = allow_map.get(flag, set())
            blocked_ids = block_map.get(flag, set())
            extras = []
            if allowed_ids:
                extras.append(f"|g+{len(allowed_ids)} allowed|n")
            if blocked_ids:
                extras.append(f"|r-{len(blocked_ids)} blocked|n")
            extra = f"  {', '.join(extras)}" if extras else ""
            return f"  {label + ':':<22} {status}{extra}"

        lines = ["|wContent tiers:|n"]
        for flag in self.TIER_TYPES:
            lines.append(flag_line(flag))

        lines.append("")
        lines.append("|wSpecific acts:|n")
        for flag in self.ACT_TYPES:
            lines.append(flag_line(flag))

        lines.append(
            f"\n|xconsent allow <type|all>           — enable globally|n\n"
            f"|xconsent disallow <type|all>         — disable globally|n\n"
            f"|xconsent allow <type|all> <name>     — allow one person (overrides global)|n\n"
            f"|xconsent disallow <type|all> <name>  — block one person (overrides global)|n\n"
            f"|xconsent unblock <type|all> <name>   — remove personal override|n"
        )
        self.msg("\n".join(lines))

    def _allow_consent(self, char, args):
        """consent allow <type|all> [name]
        No name  → toggle global flag(s) on.
        With name → per-person allow override (works even if global is off).
        """
        import copy
        parts = args.strip().split(None, 1)
        if not parts:
            self.msg("Usage: consent allow <type|all> [name]")
            return
        consent_type = parts[0].lower()
        target_name  = parts[1] if len(parts) > 1 else None

        if consent_type != "all" and consent_type not in self.VALID_CONSENT_TYPES:
            self.msg(
                f"Unknown type '{consent_type}'.\n"
                f"Valid: {', '.join(self.VALID_CONSENT_TYPES)}, all"
            )
            return

        types = self.VALID_CONSENT_TYPES if consent_type == "all" else [consent_type]
        label = "all types" if consent_type == "all" else f"|w{consent_type}|n"

        if target_name is None:
            # Global on
            flags = char.db.consent_flags or {}
            for t in types:
                flags[t] = True
            char.db.consent_flags = flags
            self.msg(f"{label}: |gENABLED|n globally.")
        else:
            # Per-person allow
            target = char.search(target_name, location=char.location)
            if not target:
                return
            overrides = copy.deepcopy(char.db.consent_overrides or {})
            overrides.setdefault("allow", {})
            overrides.setdefault("block", {})
            for t in types:
                overrides["allow"].setdefault(t, set()).add(target.id)
                overrides["block"].get(t, set()).discard(target.id)
            char.db.consent_overrides = overrides
            tname = target.db.rp_name or target.key
            self.msg(f"{label}: |gallowed|n for {tname} (overrides global).")

    def _disallow_consent(self, char, args):
        """consent disallow <type|all> [name]
        No name  → toggle global flag(s) off.
        With name → per-person block override (works even if global is on).
        """
        import copy
        parts = args.strip().split(None, 1)
        if not parts:
            self.msg("Usage: consent disallow <type|all> [name]")
            return
        consent_type = parts[0].lower()
        target_name  = parts[1] if len(parts) > 1 else None

        if consent_type != "all" and consent_type not in self.VALID_CONSENT_TYPES:
            self.msg(
                f"Unknown type '{consent_type}'.\n"
                f"Valid: {', '.join(self.VALID_CONSENT_TYPES)}, all"
            )
            return

        types = self.VALID_CONSENT_TYPES if consent_type == "all" else [consent_type]
        label = "all types" if consent_type == "all" else f"|w{consent_type}|n"

        if target_name is None:
            # Global off
            flags = char.db.consent_flags or {}
            for t in types:
                flags[t] = False
            char.db.consent_flags = flags
            self.msg(f"{label}: |rDISABLED|n globally.")
        else:
            # Per-person block
            target = char.search(target_name, location=char.location)
            if not target:
                return
            overrides = copy.deepcopy(char.db.consent_overrides or {})
            overrides.setdefault("allow", {})
            overrides.setdefault("block", {})
            for t in types:
                overrides["block"].setdefault(t, set()).add(target.id)
                overrides["allow"].get(t, set()).discard(target.id)
            char.db.consent_overrides = overrides
            tname = target.db.rp_name or target.key
            self.msg(f"{label}: |rblocked|n for {tname} (overrides global).")

    def _unblock_consent(self, char, args):
        """consent unblock <type|all> <name> — remove override, fall back to global."""
        import copy
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            self.msg("Usage: consent unblock <type|all> <name>")
            return
        consent_type, target_name = parts[0].lower(), parts[1]
        types = (self.VALID_CONSENT_TYPES if consent_type == "all"
                 else [consent_type])
        if consent_type != "all" and consent_type not in self.VALID_CONSENT_TYPES:
            self.msg(
                f"Unknown type '{consent_type}'.\n"
                f"Valid: {', '.join(self.VALID_CONSENT_TYPES)}, all"
            )
            return
        target = char.search(target_name, location=char.location)
        if not target:
            return
        overrides = copy.deepcopy(char.db.consent_overrides or {})
        changed = False
        for t in types:
            for bucket in ("allow", "block"):
                bucket_map = overrides.get(bucket, {})
                if t in bucket_map:
                    before = len(bucket_map[t])
                    bucket_map[t].discard(target.id)
                    if len(bucket_map[t]) < before:
                        changed = True
        if changed:
            char.db.consent_overrides = overrides
        tname = target.db.rp_name or target.key
        label = "all type" if consent_type == "all" else f"|w{consent_type}|n"
        self.msg(f"{label} overrides for {tname} removed. Global flags now apply.")


# -------------------------------------------------------------------
# Block command
# -------------------------------------------------------------------

class CmdBlock(MuxCommand):
    """
    Block or unblock a character from interacting with you.

    Blocked characters cannot use interaction commands
    targeting you.

    Usage:
        block <name>        — block a character
        unblock <name>      — remove a block
        block/list          — see block list
    """
    key = "block"
    aliases = ["unblock"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller
        unblocking = self.cmdstring == "unblock"

        if "list" in self.switches:
            block_list = char.db.block_list or set()
            if not block_list:
                self.msg("Your block list is empty.")
                return
            self.msg(
                f"Blocked: {len(block_list)} character(s).\n"
                f"|x(Character IDs — use unblock <name> "
                f"while they are present to remove)|n"
            )
            return

        if not self.args:
            action = "unblock" if unblocking else "block"
            self.msg(f"Usage: {action} <name>")
            return

        target = char.search(
            self.args.strip(),
            location=char.location
        )
        if not target:
            return

        if target == char:
            self.msg("You can't block yourself.")
            return

        block_list = char.db.block_list or set()
        target_name = target.db.rp_name or target.key

        if unblocking:
            if target.id in block_list:
                block_list.discard(target.id)
                char.db.block_list = block_list
                self.msg(f"{target_name} unblocked.")
            else:
                self.msg(
                    f"{target_name} is not on your block list."
                )
        else:
            block_list.add(target.id)
            char.db.block_list = block_list
            self.msg(f"{target_name} blocked.")
