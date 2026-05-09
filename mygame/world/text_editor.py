"""
world/text_editor.py

The universal text editor for Re:Void.

The same interface is used for all multi-line content — character
descriptions, ambient lines, room descriptions, written items, zone
descriptions, prop descriptions, extras, and more.

Players enter the editor via 'edit <target>' or by calling a description
command with no arguments. While inside, normal commands are replaced by
editor commands prefixed with ':'.

Editor commands:
    :add <text>             — add a line to the buffer
    :insert <#> <text>      — insert before line number
    :erase <#>              — remove a line
    :replace <#> <text>     — replace a line
    :show                   — preview current buffer
    :clear                  — clear all content
    :done                   — save and exit
    :cancel                 — discard and exit

Editor state survives disconnect — the buffer and target are stored
on the caller's db and restored on reconnect.

Architecture:
    EditorCmdSet    — the restricted command set loaded while editing
    CmdEditorLine   — catches all input, dispatches : commands
    CmdEdit         — the 'edit <target>' dispatcher command
    EditorTarget    — registry mapping target keys to getter/setter pairs
"""

from evennia.commands.command import Command
from evennia.commands.cmdset import CmdSet
from evennia.commands.default.muxcommand import MuxCommand


# -------------------------------------------------------------------
# Target registry
# -------------------------------------------------------------------

# Maps edit target names to (getter, setter) callables.
# getter(caller) -> list of lines (current content)
# setter(caller, lines) -> None (save the content)
#
# Populated at module level; commands can add to it.

EDITOR_TARGETS = {}

# In-memory store for setter callables that can't be pickled (e.g. closures).
# Keyed by caller dbref string. Cleared when the editor saves or cancels.
_PENDING_SETTERS = {}


def register_target(name, getter, setter):
    """
    Register an editable target.

    Args:
        name (str): Target keyword (e.g. "setdesc", "zone neck").
        getter (callable): getter(caller) -> list[str]
        setter (callable): setter(caller, lines) -> None
    """
    EDITOR_TARGETS[name.lower()] = (getter, setter)


# -------------------------------------------------------------------
# Built-in targets — character description fields
# -------------------------------------------------------------------

def _get_lines(attr, default=""):
    """Return getter that reads a db attr as a line list."""
    def getter(caller):
        val = getattr(caller.db, attr, None) or default
        if isinstance(val, list):
            return list(val)
        # Single string — split on newlines for editing
        return [line for line in str(val).split("\n") if line] if val else []
    return getter


def _set_lines(attr, join_str="\n"):
    """Return setter that writes a line list to a db attr."""
    def setter(caller, lines):
        setattr(caller.db, attr, join_str.join(lines))
    return setter


def _set_list_attr(attr):
    """Return setter that stores lines as a list (not joined)."""
    def setter(caller, lines):
        setattr(caller.db, attr, list(lines))
    return setter


# Register core character description targets
register_target("setdesc",      _get_lines("desc"),            _set_lines("desc"))
register_target("setoutfit",    _get_lines("outfit_override"), _set_lines("outfit_override"))
register_target("setbodylang",  _get_lines("body_language"),   _set_lines("body_language"))
register_target("setmoodtell",  _get_lines("mood_tell"),       _set_lines("mood_tell"))
register_target("setpresence",  _get_lines("ic_presence"),     _set_lines("ic_presence"))
register_target("setproxtell",  _get_lines("prox_tell"),       _set_lines("prox_tell"))
register_target("setscent",     _get_lines("scent"),           _set_lines("scent"))
register_target("setvoice",     _get_lines("voice"),           _set_lines("voice"))
register_target("settouch",     _get_lines("touch"),           _set_lines("touch"))
register_target("setbio",       _get_lines("bio"),             _set_lines("bio"))
register_target("setintimate",  _get_lines("intimate_desc"),   _set_lines("intimate_desc"))

# Wisp identity targets — stored on account
def _wisp_getter(attr):
    def getter(caller):
        acct = caller.account if hasattr(caller, 'account') else caller
        val = getattr(acct.db, attr, None) or ""
        if isinstance(val, list):
            return list(val)
        return [line for line in str(val).split("\n") if line] if val else []
    return getter


def _wisp_setter(attr, join_str="\n"):
    def setter(caller, lines):
        acct = caller.account if hasattr(caller, 'account') else caller
        setattr(acct.db, attr, join_str.join(lines))
    return setter


register_target("wdesc",       _wisp_getter("wisp_desc"),      _wisp_setter("wisp_desc"))
register_target("wsignature",  _wisp_getter("wisp_signature"), _wisp_setter("wisp_signature"))

# Ambient pool targets — stored as lists
def _ambient_getter(caller):
    pool = caller.db.ambient_contribution or []
    return list(pool)


def _ambient_setter(caller, lines):
    caller.db.ambient_contribution = list(lines)


register_target("ambient", _ambient_getter, _ambient_setter)

# Wisp ambient pool
def _wambient_getter(caller):
    acct = caller.account if hasattr(caller, 'account') else caller
    return list(acct.db.wisp_ambient_pool or [])


def _wambient_setter(caller, lines):
    acct = caller.account if hasattr(caller, 'account') else caller
    acct.db.wisp_ambient_pool = list(lines)


register_target("wambient", _wambient_getter, _wambient_setter)


# -------------------------------------------------------------------
# Zone targets — resolved dynamically
# -------------------------------------------------------------------

def _get_zone_target(caller, zone_name):
    """Return (getter, setter) for a zone description."""
    def getter(c):
        zones = c.db.zones or {}
        zone = zones.get(zone_name.lower(), {})
        desc = zone.get("nude_desc", "")
        return [line for line in desc.split("\n") if line] if desc else []

    def setter(c, lines):
        zones = c.db.zones or {}
        if zone_name.lower() not in zones:
            c.msg(f"|xZone '{zone_name}' not found.|n")
            return
        zones[zone_name.lower()]["nude_desc"] = "\n".join(lines)
        c.db.zones = zones

    return getter, setter


def _get_zone_ambient_target(caller, zone_name):
    """Return (getter, setter) for a zone's ambient pool."""
    def getter(c):
        zones = c.db.zones or {}
        zone = zones.get(zone_name.lower(), {})
        return list(zone.get("ambient", []))

    def setter(c, lines):
        zones = c.db.zones or {}
        if zone_name.lower() not in zones:
            c.msg(f"|xZone '{zone_name}' not found.|n")
            return
        zones[zone_name.lower()]["ambient"] = list(lines)
        c.db.zones = zones

    return getter, setter


# -------------------------------------------------------------------
# Marking targets — resolved dynamically
# -------------------------------------------------------------------

def _get_marking_target(caller, idx):
    """Return (getter, setter) for a marking description."""
    def getter(c):
        markings = c.db.markings or []
        if idx < 0 or idx >= len(markings):
            return []
        desc = markings[idx].get("desc", "")
        return [line for line in desc.split("\n") if line] if desc else []

    def setter(c, lines):
        markings = c.db.markings or []
        if idx < 0 or idx >= len(markings):
            c.msg(f"|xMarking #{idx + 1} not found.|n")
            return
        markings[idx]["desc"] = "\n".join(lines)
        c.db.markings = markings

    return getter, setter


# -------------------------------------------------------------------
# EditorCmdSet — active while editing
# -------------------------------------------------------------------

class EditorCmdSet(CmdSet):
    """
    The command set loaded onto the caller while in the editor.
    Replaces normal command access with editor-specific commands.
    """
    key = "EditorCmdSet"
    priority = 200   # higher than CharacterCmdSet (101) to override
    mergetype = "Replace"

    def at_cmdset_creation(self):
        self.add(CmdEditorLine())
        self.add(CmdEditorDone())
        self.add(CmdEditorSave())
        self.add(CmdEditorCancel())
        self.add(CmdEditorShow())
        self.add(CmdEditorHelp())


# -------------------------------------------------------------------
# Editor commands (active inside the editor)
# -------------------------------------------------------------------

class CmdEditorLine(Command):
    """
    The catch-all command for editor input.

    Lines starting with ':' are editor commands.
    All other lines are treated as content to add.

    Editor commands:
        :add <text>          — add a line
        :insert <#> <text>   — insert before line #
        :erase <#>           — remove line #
        :replace <#> <text>  — replace line #
        :show                — preview buffer
        :clear               — clear buffer
        :done                — save and exit
        :cancel              — discard and exit
    """
    key = "editor_input"
    aliases = []
    locks = "cmd:all()"
    # Match everything
    arg_regex = None

    def parse(self):
        self.raw_line = self.raw_string.strip()

    def func(self):
        caller = self.caller
        raw = self.raw_line

        if not raw:
            return

        if raw.startswith(":"):
            self._handle_editor_command(raw[1:].strip())
        else:
            # Bare input — treat as :add
            self._add_line(caller, raw)

    def _handle_editor_command(self, cmd_text):
        caller = self.caller
        if not cmd_text:
            return

        parts = cmd_text.split(None, 1)
        sub = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if sub in ("add", "a"):
            if not rest:
                caller.msg("|xAdd what?|n")
                return
            self._add_line(caller, rest)

        elif sub in ("insert", "i"):
            self._insert_line(caller, rest)

        elif sub in ("erase", "e", "delete", "del"):
            self._erase_line(caller, rest)

        elif sub in ("replace", "r"):
            self._replace_line(caller, rest)

        elif sub == "show":
            self._show_buffer(caller)

        elif sub == "clear":
            caller.db._editor_buffer = []
            caller.msg("|x[Buffer cleared.]|n")

        elif sub == "save":
            self._save_only(caller)

        elif sub == "done":
            self._save_and_exit(caller)

        elif sub == "cancel":
            self._cancel(caller)

        elif sub in ("help", "?", "h"):
            self._show_help(caller)

        else:
            caller.msg(
                f"|xUnknown editor command ':{sub}'.\n"
                f"Type |w:help|n or |w:?|n to see all commands.|n"
            )

    def _add_line(self, caller, text):
        buf = caller.db._editor_buffer or []
        buf.append(text)
        caller.db._editor_buffer = buf
        caller.msg(f"|x[Line {len(buf)} added.]|n")

    def _insert_line(self, caller, rest):
        parts = rest.split(None, 1)
        if len(parts) < 2:
            caller.msg("|xUsage: :insert <#> <text>|n")
            return
        try:
            idx = int(parts[0]) - 1
        except ValueError:
            caller.msg("|xLine number must be a number.|n")
            return
        buf = caller.db._editor_buffer or []
        if idx < 0 or idx > len(buf):
            caller.msg(
                f"|xCan't insert at {idx + 1}. "
                f"Buffer has {len(buf)} lines.|n"
            )
            return
        buf.insert(idx, parts[1])
        caller.db._editor_buffer = buf
        caller.msg(f"|x[Inserted at line {idx + 1}.]|n")

    def _erase_line(self, caller, rest):
        try:
            idx = int(rest.strip()) - 1
        except ValueError:
            caller.msg("|xUsage: :erase <#>|n")
            return
        buf = caller.db._editor_buffer or []
        if idx < 0 or idx >= len(buf):
            caller.msg(
                f"|xNo line {idx + 1}. Buffer has {len(buf)} lines.|n"
            )
            return
        removed = buf.pop(idx)
        caller.db._editor_buffer = buf
        caller.msg(f"|x[Line {idx + 1} removed: {removed}]|n")

    def _replace_line(self, caller, rest):
        parts = rest.split(None, 1)
        if len(parts) < 2:
            caller.msg("|xUsage: :replace <#> <text>|n")
            return
        try:
            idx = int(parts[0]) - 1
        except ValueError:
            caller.msg("|xLine number must be a number.|n")
            return
        buf = caller.db._editor_buffer or []
        if idx < 0 or idx >= len(buf):
            caller.msg(
                f"|xNo line {idx + 1}. Buffer has {len(buf)} lines.|n"
            )
            return
        buf[idx] = parts[1]
        caller.db._editor_buffer = buf
        caller.msg(f"|x[Line {idx + 1} replaced.]|n")

    def _show_buffer(self, caller):
        buf = caller.db._editor_buffer or []
        target_key = caller.db._editor_target or "unknown"
        sep = f"|w{'─' * 44}|n"
        if not buf:
            caller.msg(
                f"\n{sep}\n|wEditing: {target_key}|n\n"
                f"{sep}\n|x(empty buffer)|n\n{sep}"
            )
            return
        lines = [
            f"\n{sep}",
            f"|wEditing: {target_key}|n",
            sep,
        ]
        for i, line in enumerate(buf, 1):
            lines.append(f"  |x{i:>2}.|n {line}")
        lines.append(sep)
        caller.msg("\n".join(lines))

    def _save_and_exit(self, caller):
        buf = caller.db._editor_buffer or []
        target_key = caller.db._editor_target or ""
        setter = caller.db._editor_setter_key or ""

        # Resolve and call the setter
        success = _apply_setter(caller, setter, target_key, buf)
        if success:
            caller.msg(
                f"|x[Saved. Exiting editor.]|n\n"
                f"|wType ':show' won't work now — "
                f"editor closed.|n"
            )
        _exit_editor(caller)

    def _cancel(self, caller):
        caller.msg("|x[Changes discarded. Exiting editor.]|n")
        _exit_editor(caller)

    def _save_only(self, caller):
        """Save the buffer without exiting the editor."""
        buf = caller.db._editor_buffer or []
        target_key = caller.db._editor_target or ""
        setter = caller.db._editor_setter_key or ""
        success = _apply_setter(caller, setter, target_key, buf)
        if success:
            caller.msg("|x[Saved. Still in editor — type :done to exit.]|n")

    def _show_help(self, caller):
        sep = f"|w{'─' * 44}|n"
        caller.msg(
            f"\n{sep}\n"
            f"|wEditor commands|n\n"
            f"{sep}\n"
            f"  |w:add <text>|n          — append a line\n"
            f"  |w:insert <#> <text>|n   — insert before line number\n"
            f"  |w:erase <#>|n           — delete a line\n"
            f"  |w:replace <#> <text>|n  — replace a line\n"
            f"  |w:show|n                — preview the buffer\n"
            f"  |w:clear|n               — erase everything\n"
            f"  |w:save|n                — save without exiting\n"
            f"  |w:done|n                — save and exit\n"
            f"  |w:cancel|n              — exit without saving\n"
            f"  |w:help|n  |w:?|n            — this help\n"
            f"{sep}\n"
            f"|wColor codes (Evennia markup):|n\n"
            f"  |r|r red|n   |g|g green|n   |b|b blue|n   |y|y yellow|n\n"
            f"  |m|m magenta|n   |c|c cyan|n   |w|w white|n   |x|x dark gray|n\n"
            f"  |n|n reset (end any color)\n"
            f"  |[500 xterm256 foreground  — |w|500|n → |500bold red|n\n"
            f"  |=a–|=z dark shades, |=A–|=Z bright shades\n"
            f"{sep}\n"
            f"|wTips:|n\n"
            f"  Typing without a ':' prefix adds a line directly.\n"
            f"  Paste multiple lines — each lands as a separate entry.\n"
            f"  Line breaks in a description are literal newlines.\n"
            f"  Use |n to reset color at the end of colored text.\n"
            f"{sep}\n"
        )


class CmdEditorDone(Command):
    """Save and exit the editor. Shorthand for :done."""
    key = ":done"
    locks = "cmd:all()"

    def func(self):
        buf = self.caller.db._editor_buffer or []
        target_key = self.caller.db._editor_target or ""
        setter = self.caller.db._editor_setter_key or ""
        _apply_setter(self.caller, setter, target_key, buf)
        self.msg("|x[Saved. Exiting editor.]|n")
        _exit_editor(self.caller)


class CmdEditorCancel(Command):
    """Discard changes and exit the editor. Shorthand for :cancel."""
    key = ":cancel"
    locks = "cmd:all()"

    def func(self):
        self.msg("|x[Changes discarded. Exiting editor.]|n")
        _exit_editor(self.caller)


class CmdEditorShow(Command):
    """Preview buffer. Shorthand for :show."""
    key = ":show"
    locks = "cmd:all()"

    def func(self):
        buf = self.caller.db._editor_buffer or []
        target_key = self.caller.db._editor_target or "unknown"
        sep = f"|w{'─' * 44}|n"
        if not buf:
            self.msg(
                f"\n{sep}\n|wEditing: {target_key}|n\n"
                f"{sep}\n|x(empty buffer)|n\n{sep}"
            )
            return
        lines = [f"\n{sep}", f"|wEditing: {target_key}|n", sep]
        for i, line in enumerate(buf, 1):
            lines.append(f"  |x{i:>2}.|n {line}")
        lines.append(sep)
        self.msg("\n".join(lines))


class CmdEditorSave(Command):
    """Save current buffer without exiting. Shorthand for :save."""
    key = ":save"
    locks = "cmd:all()"

    def func(self):
        caller = self.caller
        buf = caller.db._editor_buffer or []
        target_key = caller.db._editor_target or ""
        setter = caller.db._editor_setter_key or ""
        success = _apply_setter(caller, setter, target_key, buf)
        if success:
            self.msg("|x[Saved. Still in editor — type :done to exit.]|n")


class CmdEditorHelp(Command):
    """Show editor help. Shorthand for :help or :?"""
    key = ":help"
    aliases = [":?", ":h"]
    locks = "cmd:all()"

    def func(self):
        sep = f"|w{'─' * 44}|n"
        self.msg(
            f"\n{sep}\n"
            f"|wEditor commands|n\n"
            f"{sep}\n"
            f"  |w:add <text>|n          — append a line\n"
            f"  |w:insert <#> <text>|n   — insert before line number\n"
            f"  |w:erase <#>|n           — delete a line\n"
            f"  |w:replace <#> <text>|n  — replace a line\n"
            f"  |w:show|n                — preview the buffer\n"
            f"  |w:clear|n               — erase everything\n"
            f"  |w:save|n                — save without exiting\n"
            f"  |w:done|n                — save and exit\n"
            f"  |w:cancel|n              — exit without saving\n"
            f"  |w:help|n  |w:?|n            — this help\n"
            f"{sep}\n"
            f"|wColor codes (Evennia markup):|n\n"
            f"  |r|r red|n   |g|g green|n   |b|b blue|n   |y|y yellow|n\n"
            f"  |m|m magenta|n   |c|c cyan|n   |w|w white|n   |x|x dark gray|n\n"
            f"  |n (reset — end any color block)\n"
            f"  |w|500|n → xterm256 foreground code (100 shades of color)\n"
            f"  |w|[500|n → xterm256 background\n"
            f"{sep}\n"
            f"|wTips:|n\n"
            f"  Typing without ':' adds a line directly.\n"
            f"  Paste multiple lines — each arrives as a separate entry.\n"
            f"  Newlines in descriptions display as paragraph breaks.\n"
            f"  Always end colored text with |w|n|n to reset.\n"
            f"{sep}\n"
        )


# -------------------------------------------------------------------
# Editor lifecycle helpers
# -------------------------------------------------------------------

def _exit_editor(caller):
    """Remove EditorCmdSet and clear editor state."""
    try:
        caller.cmdset.remove(EditorCmdSet)
    except Exception:
        pass
    caller.db._editor_buffer = None
    caller.db._editor_target = None
    caller.db._editor_setter_key = None
    caller.db._editor_extra = None


def _enter_editor(caller, target_display, setter_key, initial_lines=None,
                  extra=None):
    """
    Enter the editor for a given target.

    Args:
        caller: Character or Account.
        target_display (str): Human-readable target name for display.
        setter_key (str): Key used to look up setter in EDITOR_TARGETS
                          or resolve dynamically.
        initial_lines (list): Pre-populate buffer with these lines.
        extra: Optional extra data (e.g. zone name, marking index).
    """
    caller.db._editor_buffer = list(initial_lines or [])
    caller.db._editor_target = target_display
    caller.db._editor_setter_key = setter_key

    # Closures can't be pickled — extract any callable setter and keep it
    # in the module-level _PENDING_SETTERS dict instead.
    if extra and callable(extra.get("setter")):
        _PENDING_SETTERS[str(caller.dbref)] = extra["setter"]
        extra = {k: v for k, v in extra.items() if k != "setter"}

    caller.db._editor_extra = extra

    caller.cmdset.add(EditorCmdSet, persistent=True)

    sep = f"|w{'─' * 44}|n"
    lines = [
        f"\n{sep}",
        f"|wEditor: {target_display}|n",
        sep,
    ]
    if initial_lines:
        for i, line in enumerate(initial_lines, 1):
            lines.append(f"  |x{i:>2}.|n {line}")
    else:
        lines.append("  |x(empty — type lines to add, or use :add)|n")

    lines.append(sep)
    lines.append(
        "|xType lines to add them. Editor commands start with ':' — "
        "type |w:help|n or |w:?|n to see all commands.|n"
    )
    caller.msg("\n".join(lines))


def _apply_setter(caller, setter_key, target_display, lines):
    """
    Resolve and call the appropriate setter for the current edit target.

    Returns True on success.
    """
    key = setter_key.lower()

    # --- Static registry ---
    if key in EDITOR_TARGETS:
        _, setter = EDITOR_TARGETS[key]
        try:
            setter(caller, lines)
            return True
        except Exception as e:
            caller.msg(f"|rError saving: {e}|n")
            return False

    # --- Dynamic: zone <name> ---
    if key.startswith("zone "):
        zone_name = key[5:].strip()
        _, setter = _get_zone_target(caller, zone_name)
        setter(caller, lines)
        return True

    # --- Dynamic: ambient/zone <name> ---
    if key.startswith("ambient/zone "):
        zone_name = key[13:].strip()
        _, setter = _get_zone_ambient_target(caller, zone_name)
        setter(caller, lines)
        return True

    # --- Dynamic: marking <#> ---
    if key.startswith("marking "):
        try:
            idx = int(key[8:].strip()) - 1
        except ValueError:
            caller.msg("|xInvalid marking number.|n")
            return False
        _, setter = _get_marking_target(caller, idx)
        setter(caller, lines)
        return True

    # --- Dynamic: prop / extra / note (handled by freeform) ---
    if key.startswith("prop ") or key.startswith("extra ") or key == "note":
        extra = caller.db._editor_extra
        if extra and callable(extra.get("setter")):
            try:
                extra["setter"](caller, lines)
                return True
            except Exception as e:
                caller.msg(f"|rError saving: {e}|n")
                return False
        caller.msg("|xNo save target found for this edit.|n")
        return False

    # --- General fallback: use extra setter if one is registered ---
    # This is the path for any caller that passed extra={"setter": fn}
    # without matching a known static or dynamic key pattern above.
    extra = caller.db._editor_extra
    if extra and callable(extra.get("setter")):
        try:
            extra["setter"](caller, lines)
            return True
        except Exception as e:
            caller.msg(f"|rError saving: {e}|n")
            return False

    # --- In-memory setter fallback (closures stored before pickling) ---
    setter_fn = _PENDING_SETTERS.pop(str(caller.dbref), None)
    if setter_fn:
        try:
            setter_fn(caller, lines)
            return True
        except Exception as e:
            caller.msg(f"|rError saving: {e}|n")
            return False

    caller.msg(f"|xUnknown edit target: '{setter_key}'.|n")
    return False


# -------------------------------------------------------------------
# CmdEdit — the dispatcher command
# -------------------------------------------------------------------

class CmdEdit(MuxCommand):
    """
    Open the text editor for a description field or content target.

    Usage:
        edit <target>
        edit zone <name>
        edit ambient/zone <name>
        edit marking <#>
        edit prop "<name>"
        edit extra "<handle>"
        edit wdesc
        edit wambient
        edit rambient    (builder — room ambient)
        edit rdesc       (builder — room base description)

    Any description command called with no arguments also opens
    the editor automatically.

    Editor commands:
        :add <text>          — add a line
        :insert <#> <text>   — insert before line #
        :erase <#>           — remove a line
        :replace <#> <text>  — replace a line
        :show                — preview buffer
        :clear               — clear buffer
        :done                — save and exit
        :cancel              — discard and exit

    Your buffer survives disconnect — if you get cut off mid-edit,
    it will be waiting when you return.
    """

    key = "edit"
    locks = "cmd:all()"
    help_category = "Description"

    def func(self):
        caller = self.caller

        # Already in editor?
        if caller.db._editor_target is not None:
            caller.msg(
                "|xYou are already in the editor. "
                "Type ':done' to save or ':cancel' to exit.|n"
            )
            return

        if not self.args:
            caller.msg(
                "Usage: edit <target>\n"
                "Examples: edit setdesc / edit zone neck / "
                "edit ambient / edit wdesc"
            )
            return

        target_str = self.args.strip().lower()

        # Resolve getter
        getter, setter_key, display = self._resolve_target(
            caller, target_str
        )
        if getter is None:
            return

        # Get current content
        try:
            current_lines = getter(caller)
        except Exception as e:
            caller.msg(f"|rError loading content: {e}|n")
            return

        _enter_editor(caller, display, setter_key, current_lines)

    def _resolve_target(self, caller, target_str):
        """
        Resolve a target string to (getter, setter_key, display).
        Returns (None, None, None) and messages caller on failure.
        """
        # Static registry
        if target_str in EDITOR_TARGETS:
            getter, _ = EDITOR_TARGETS[target_str]
            return getter, target_str, target_str

        # zone <name>
        if target_str.startswith("zone "):
            zone_name = target_str[5:].strip()
            if not zone_name:
                caller.msg("|xUsage: edit zone <name>|n")
                return None, None, None
            zones = caller.db.zones or {}
            if zone_name.lower() not in zones:
                caller.msg(
                    f"|xNo zone '{zone_name}'. "
                    f"Use 'zone list' to see your zones.|n"
                )
                return None, None, None
            getter, _ = _get_zone_target(caller, zone_name)
            return getter, target_str, f"zone: {zone_name}"

        # ambient/zone <name>
        if target_str.startswith("ambient/zone "):
            zone_name = target_str[13:].strip()
            getter, _ = _get_zone_ambient_target(caller, zone_name)
            return getter, target_str, f"zone ambient: {zone_name}"

        # marking <#>
        if target_str.startswith("marking "):
            try:
                idx = int(target_str[8:].strip()) - 1
            except ValueError:
                caller.msg("|xUsage: edit marking <#>|n")
                return None, None, None
            getter, _ = _get_marking_target(caller, idx)
            return getter, target_str, f"marking #{idx + 1}"

        # room targets — need builder perm
        if target_str in ("rdesc", "rentry", "rexamine", "rambient"):
            if not (caller.is_superuser or
                    caller.check_permstring("Builder")):
                caller.msg(
                    "|xYou need Builder permission to edit room content.|n"
                )
                return None, None, None
            room = caller.location
            if not room:
                caller.msg("|xYou need to be in a room.|n")
                return None, None, None

            if target_str == "rdesc":
                def getter(c):
                    v = room.db.desc or ""
                    return [l for l in v.split("\n") if l]
                def setter(c, lines):
                    room.db.desc = "\n".join(lines)
                EDITOR_TARGETS["_rdesc_dynamic"] = (getter, setter)
                return getter, "_rdesc_dynamic", f"room desc: {room.key}"

            if target_str == "rentry":
                def getter(c):
                    v = room.db.entry_desc or ""
                    return [l for l in v.split("\n") if l]
                def setter(c, lines):
                    room.db.entry_desc = "\n".join(lines)
                EDITOR_TARGETS["_rentry_dynamic"] = (getter, setter)
                return getter, "_rentry_dynamic", f"room entry: {room.key}"

            if target_str == "rexamine":
                def getter(c):
                    v = room.db.examine_desc or ""
                    return [l for l in v.split("\n") if l]
                def setter(c, lines):
                    room.db.examine_desc = "\n".join(lines)
                EDITOR_TARGETS["_rexamine_dynamic"] = (getter, setter)
                return getter, "_rexamine_dynamic", f"room examine: {room.key}"

            if target_str == "rambient":
                def getter(c):
                    return list(room.db.ambient_msgs or [])
                def setter(c, lines):
                    room.db.ambient_msgs = list(lines)
                EDITOR_TARGETS["_rambient_dynamic"] = (getter, setter)
                return getter, "_rambient_dynamic", f"room ambient: {room.key}"

        # prop / extra — handled via freeform; just open with empty getter
        if target_str.startswith('prop "') or target_str.startswith("prop '"):
            caller.msg(
                "|xUse 'prop ambient' commands or "
                "the freeform system to edit props.|n"
            )
            return None, None, None

        caller.msg(
            f"|xUnknown edit target: '{target_str}'.\n"
            f"Try: setdesc, setbio, setbodylang, setmoodtell, "
            f"setpresence, setscent, setvoice, settouch, setintimate, "
            f"zone <name>, ambient, wdesc, wambient, marking <#>, "
            f"rdesc, rentry, rexamine, rambient|n"
        )
        return None, None, None
