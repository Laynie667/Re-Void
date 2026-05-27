"""
commands/chargen.py

Character setup for Re:Void.

No gating — players can enter the world at any time regardless of
what they've filled in. This is a reference tool, not a locked flow.

CmdChargen shows a checklist of core and optional character fields,
with the command to use for each unset field.

The checklist is also shown automatically on first puppet if the
character has no name or description yet.

Commands:
    chargen         -- show the setup checklist
    chargen/clear   -- reset a field back to empty (staff use)
"""

from evennia.commands.default.muxcommand import MuxCommand


# -------------------------------------------------------------------
# Checklist builder
# Called by CmdChargen and by the first-puppet hook in characters.py
# -------------------------------------------------------------------

def build_chargen_display(char):
    """
    Assemble and return the full chargen checklist string for a character.

    Args:
        char: Character object.

    Returns:
        str: Formatted checklist ready to send via msg().
    """
    sep = f"|w{'━' * 48}|n"

    def _row(label, value, cmd, optional=False):
        """Format one checklist row."""
        if value:
            status = "|g✓|n"
            display = (
                value if len(value) <= 32
                else value[:29] + "..."
            )
        else:
            status = "|x·|n" if optional else "|y!|n"
            display = "|x(not set)|n"

        opt_tag = " |x[optional]|n" if optional and not value else ""
        return (
            f"  {status} |w{label:<14}|n "
            f"{display:<34} |x{cmd}|n{opt_tag}"
        )

    # Pronouns display
    pron = char.db.pronouns or {}
    pron_display = (
        f"{pron.get('subject','they')}/"
        f"{pron.get('object','them')}/"
        f"{pron.get('possessive','their')}"
        if pron else None
    )
    # Treat default they/them as "set" since it's valid
    if pron_display == "they/them/their":
        pron_set = pron_display
    else:
        pron_set = pron_display if pron else None

    # RP hooks count
    hooks = char.db.rp_hooks or []
    hooks_display = f"{len(hooks)} set" if hooks else None

    lines = [
        f"\n{sep}",
        f"|wCHARACTER SETUP|n  |x— type 'chargen' anytime to return here|n",
        sep,
        "",
        "|wCore|n  |x(these shape how others see you)|n",
        _row("Name",        char.db.rp_name,      "setname <name>"),
        _row("Pronouns",    pron_set,              "setpronouns <s> <o> <p>"),
        _row("Description", char.db.physical_desc, "setdesc <text>"),
        "",
        "|wIdentity|n",
        _row("Species",     char.db.species if char.db.species != "human"
                            else None,             "setspecies <text>",  optional=True),
        _row("Age",         char.db.apparent_age,  "setage <text>",      optional=True),
        _row("Bio",         char.db.public_bio,    "setbio <text>",      optional=True),
        "",
        "|wPresence|n  |x(sensory layers others notice)|n",
        _row("IC Presence", char.db.ic_presence,   "setpresence <text>", optional=True),
        _row("Voice",       char.db.voice_desc,    "setvoice <text>",    optional=True),
        _row("Scent",       char.db.scent_desc,    "setscent <text>",    optional=True),
        _row("Mood",        char.db.mood,          "setmood <text>",     optional=True),
        _row("Body lang.",  char.db.body_language, "setbodylang <text>", optional=True),
        "",
        "|wRP Hooks|n  |x(what draws others to scene with you)|n",
        _row("Hooks",       hooks_display,         "rphook/add <text>",  optional=True),
        "",
        sep,
        "|x|w!|n|x = recommended  · = optional  ✓ = set|n",
        sep,
    ]

    return "\n".join(lines)


# -------------------------------------------------------------------
# CmdChargen
# -------------------------------------------------------------------

class CmdChargen(MuxCommand):
    """
    View your character setup checklist.

    Shows which fields are set, which are missing, and what command
    to use for each. Nothing is locked — you can enter the world
    whenever you're ready.

    Fields marked |y!|n are recommended. Fields marked |x·|n are optional.

    Usage:
      chargen             -- show the checklist
      chargen/done        -- print a confirmation and clear the prompt

    Core fields:
      setname <name>              your IC/RP display name
      setpronouns <s> <o> <p>     e.g. setpronouns she her her
      setdesc <text>              your physical appearance

    Identity fields:
      setspecies <text>           e.g. human, fae, construct
      setage <text>               apparent age — text, not a number
      setbio <text>               public background blurb

    Presence fields:
      setpresence <text>          the IC line that appears in room listings
      setvoice <text>             what your voice sounds like
      setscent <text>             your scent layer
      setmood <text>              current IC mood
      setbodylang <text>          current body language

    RP hooks:
      rphook/add <text>           add a hook others can use to engage you

    See also: sheet, setname, setdesc, setpronouns
    """

    key = "chargen"
    aliases = ["setup"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "done" in self.switches:
            name = char.db.rp_name or char.name
            self.msg(
                f"\n|w{name}|n steps into the world.\n\n"
                f"|xYou can return to this checklist anytime with |wchargen|n|x.\n"
                f"When you're ready to meet others, just start playing.|n"
            )
            return

        self.msg(build_chargen_display(char))
