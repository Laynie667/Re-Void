"""
commands/bio_commands.py

Custom bio field commands for Re:Void characters.

Bio fields are player-defined key/value pairs that appear on the
character sheet between the core stats block and the RP hooks.
Players control which fields exist, what they say, and the
order they display in.

The short public bio paragraph is set with the existing 'setbio'
command in character_commands.py. Bio fields are the structured
section below it.

STORAGE
-------
character.db.bio_fields = [
    {"name": "Occupation", "value": "former archivist, current problem"},
    {"name": "Known for",  "value": "asking questions she already knows"},
]
character.db.bio_field_order = ["Occupation", "Known for", "Currently"]

COMMANDS
--------
bio                             — show your bio fields
bio list                        — alias
bio add <field name>            — add a new empty field
bio set <field name> = <text>   — set or update a field's value
bio remove <field name>         — remove a field
bio order <field> | <field> ... — set display order (pipe-separated)
bio show                        — preview bio section as it appears on sheet
"""

from evennia.commands.default.muxcommand import MuxCommand


def _char(caller):
    return caller.puppet if hasattr(caller, 'puppet') else caller


def _get_fields(char):
    return list(char.db.bio_fields or [])


def _find_field(fields, name):
    """Return (index, field_dict) or (None, None)."""
    name_lower = name.lower()
    for i, f in enumerate(fields):
        if f.get("name", "").lower() == name_lower:
            return i, f
    return None, None


class CmdBio(MuxCommand):
    """
    Manage custom bio fields on your character sheet.

    Bio fields are player-defined lines that appear on your sheet
    under the core stats. Use them for occupation, background,
    current mood, or anything you want visible on your public profile.

    Usage:
        bio                             — list your bio fields
        bio list                        — same
        bio add <field name>            — create a new field
        bio set <field name> = <value>  — set a field's content
        bio remove <field name>         — remove a field
        bio order <name> | <name> | ... — set display order
        bio show                        — preview bio section

    Examples:
        bio add Occupation
        bio set Occupation = former archivist, current problem
        bio add Known for
        bio set Known for = asking questions she already knows the answer to
        bio order Occupation | Known for | Currently
        bio show

    See also: sheet, setbio, rphook
    """
    key = "bio"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = _char(self.caller)
        args = self.args.strip()

        if not args or args == "list":
            self._bio_list(char)
            return

        # Check for set syntax: "set <name> = <value>" or "<name> = <value>"
        if "=" in args and not args.lower().startswith("order"):
            # Could be "set Name = value" or just "Name = value"
            if args.lower().startswith("set "):
                rest = args[4:].strip()
            else:
                rest = args
            self._bio_set(char, rest)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        dispatch = {
            "list":   lambda: self._bio_list(char),
            "add":    lambda: self._bio_add(char, rest),
            "set":    lambda: self._bio_set(char, rest),
            "remove": lambda: self._bio_remove(char, rest),
            "delete": lambda: self._bio_remove(char, rest),
            "order":  lambda: self._bio_order(char, rest),
            "show":   lambda: self._bio_show(char),
        }

        handler = dispatch.get(subcmd)
        if handler:
            handler()
        else:
            # Treat as field name — show it
            fields = _get_fields(char)
            idx, field = _find_field(fields, args)
            if field:
                self.msg(
                    f"|w{field['name']}:|n "
                    f"{field.get('value', '|x(not set)|n')}"
                )
            else:
                self.msg(
                    f"Unknown subcommand '{subcmd}'.\n"
                    "Usage: bio add/set/remove/order/show/list"
                )

    def _bio_list(self, char):
        fields = _get_fields(char)
        order = char.db.bio_field_order or []

        if not fields:
            self.msg(
                "You have no bio fields.\n"
                "Add one with: bio add <field name>"
            )
            return

        # Sort by order preference
        field_map = {f["name"].lower(): f for f in fields}
        seen = set()
        ordered = []
        for name in order:
            f = field_map.get(name.lower())
            if f:
                ordered.append(f)
                seen.add(f["name"].lower())
        for f in fields:
            if f["name"].lower() not in seen:
                ordered.append(f)

        lines = ["|wYour bio fields:|n\n"]
        for i, f in enumerate(ordered, 1):
            name = f.get("name", "")
            value = f.get("value", "")
            value_str = value[:60] + "..." if len(value) > 60 else value
            val_display = value_str if value_str else "|x(not set)|n"
            lines.append(f"  {i}. |w{name}|n: {val_display}")

        lines.append(
            f"\n|x{len(fields)} field(s).|n  "
            f"Set with: bio set <name> = <value>"
        )
        if order:
            lines.append(f"|xDisplay order: {' | '.join(order)}|n")
        self.msg("\n".join(lines))

    def _bio_add(self, char, name):
        if not name:
            self.msg("Usage: bio add <field name>")
            return
        if len(name) > 40:
            self.msg("Field name too long. Keep it under 40 characters.")
            return

        fields = _get_fields(char)
        idx, existing = _find_field(fields, name)
        if existing:
            self.msg(
                f"A field named '{name}' already exists.\n"
                f"Update it with: bio set {name} = <value>"
            )
            return

        fields.append({"name": name, "value": ""})
        char.db.bio_fields = fields
        self.msg(
            f"Bio field |w'{name}'|n added.\n"
            f"Set its content with: bio set {name} = <text>"
        )

    def _bio_set(self, char, args):
        if "=" not in args:
            self.msg(
                "Usage: bio set <field name> = <value>\n"
                "Example: bio set Occupation = former archivist"
            )
            return

        name, _, value = args.partition("=")
        name = name.strip()
        value = value.strip()

        if not name:
            self.msg("Specify a field name.")
            return

        fields = _get_fields(char)
        idx, field = _find_field(fields, name)

        if field is None:
            # Auto-create if it doesn't exist
            fields.append({"name": name, "value": value})
            char.db.bio_fields = fields
            self.msg(
                f"Bio field |w'{name}'|n created and set:\n"
                f"  {value}"
            )
        else:
            fields[idx]["value"] = value
            char.db.bio_fields = fields
            self.msg(
                f"Bio field |w'{name}'|n updated:\n"
                f"  {value}"
            )

    def _bio_remove(self, char, name):
        if not name:
            self.msg("Usage: bio remove <field name>")
            return

        fields = _get_fields(char)
        idx, field = _find_field(fields, name)

        if field is None:
            self.msg(f"No bio field named '{name}'.")
            return

        removed_name = field["name"]
        fields.pop(idx)
        char.db.bio_fields = fields

        # Also remove from order list
        order = list(char.db.bio_field_order or [])
        order = [n for n in order if n.lower() != removed_name.lower()]
        char.db.bio_field_order = order

        self.msg(f"Bio field |w'{removed_name}'|n removed.")

    def _bio_order(self, char, args):
        if not args:
            self.msg(
                "Usage: bio order <name> | <name> | <name>\n"
                "Example: bio order Occupation | Known for | Currently"
            )
            return

        # Split by pipe
        parts = [p.strip() for p in args.split("|") if p.strip()]
        if not parts:
            self.msg("Provide field names separated by |")
            return

        fields = _get_fields(char)
        field_names_lower = {f["name"].lower() for f in fields}

        valid = []
        unknown = []
        for part in parts:
            if part.lower() in field_names_lower:
                valid.append(part)
            else:
                unknown.append(part)

        if unknown:
            self.msg(
                f"Unknown field(s): {', '.join(unknown)}\n"
                f"Add them first with: bio add <name>"
            )
            return

        char.db.bio_field_order = valid
        self.msg(
            f"Bio field order set:\n"
            f"  {' | '.join(valid)}"
        )

    def _bio_show(self, char):
        """Preview the bio section as it appears on the sheet."""
        bio = char.db.public_bio or ""
        fields = _get_fields(char)
        order = char.db.bio_field_order or []

        # Sort by order
        field_map = {f["name"].lower(): f for f in fields}
        seen = set()
        ordered = []
        for name in order:
            f = field_map.get(name.lower())
            if f:
                ordered.append(f)
                seen.add(f["name"].lower())
        for f in fields:
            if f["name"].lower() not in seen:
                ordered.append(f)

        lines = ["|wBio preview:|n\n"]
        if bio:
            lines.append(bio)
            lines.append("")

        if ordered:
            col = 16
            for f in ordered:
                name = f.get("name", "")
                value = f.get("value", "")
                if name:
                    val_display = value if value else "|x(not set)|n"
                    lines.append(f"|x{name + ':':<{col}}|n {val_display}")

        if not bio and not ordered:
            lines.append("|x(nothing set — use setbio and bio add)|n")

        self.msg("\n".join(lines))


ALL_BIO_CMDS = [CmdBio]
