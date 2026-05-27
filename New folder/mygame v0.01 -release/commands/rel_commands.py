"""
commands/rel_commands.py

Relationship / contacts list commands for Re:Void.

The contacts list is a simple, private record of relationships.
No stages. No advancement. No shared memory. No mutual agreement.
Just a named list with a status label, a private note, and an
optional desc that person sees when they examine you.

STATUSES
--------
friend / lover / married / owner / sub / slave / blocked

'blocked' syncs with the main block_list. Adding someone as
'blocked' adds them to block_list. Removing them from contacts
removes them from block_list if their status was blocked.

STORAGE (character.db.contacts)
--------------------------------
{
    "123": {                        # str(target.id)
        "name":     "Seraphine Voss",
        "status":   "lover",
        "note":     "private note, never shown",
        "rel_desc": "what she sees when examining me",
    },
    ...
}

COMMANDS
--------
rel list                        — see contacts list (own sheet only)
rel add <name> <status>         — add or update a contact
rel remove <name>               — remove from contacts
rel note <name> = <text>        — save private note
rel note <name>                 — read your note
rel note <name>/clear           — clear note
rel desc <name> = <text>        — write what this char sees when examining you
rel desc <name>/clear           — clear it

rel_desc appears under examine, never under look or sheet.
Notes are private — never shown anywhere.
Contacts list shows on own sheet only.
"""

from evennia.commands.default.muxcommand import MuxCommand


VALID_STATUSES = (
    "friend", "lover", "married",
    "owner", "sub", "slave", "blocked",
)


def _char(caller):
    return caller.puppet if hasattr(caller, 'puppet') else caller


def _find_contact_by_name(contacts, name):
    """
    Search contacts dict by stored name (case-insensitive).
    Returns (key_str, contact_dict) or (None, None).
    """
    name_lower = name.lower()
    for key, data in contacts.items():
        if data.get("name", "").lower().startswith(name_lower):
            return key, data
    return None, None


def _find_char_in_room(caller, char, name):
    """Search room contents for a character by name."""
    room = char.location
    if not room:
        return None
    for obj in room.contents:
        if hasattr(obj, 'db') and obj != char:
            cname = (obj.db.rp_name or obj.key or "").lower()
            if cname.startswith(name.lower()) or obj.key.lower() == name.lower():
                return obj
    return None


class CmdRel(MuxCommand):
    """
    Manage your contacts list.

    The contacts list is private — only you see it on your own sheet.
    Use it to track relationships, leave notes about people,
    and write what a specific person sees when they examine you.

    Usage:
        rel list                        — see your contacts
        rel add <name> <status>         — add or update contact
        rel remove <name>               — remove contact
        rel note <name> = <text>        — save a private note
        rel note <name>                 — read your note on someone
        rel note <name>/clear           — clear the note
        rel desc <name> = <text>        — what they see when examining you
        rel desc <name>/clear           — clear that desc

    Statuses:  friend / lover / married / owner / sub / slave / blocked

    'blocked' syncs with your block list. Adding someone as blocked
    also blocks them. Removing them unblocks them if they were blocked.

    rel desc: visible only to that character under examine.
    Notes: completely private — never shown anywhere.

    See also: block, sheet, examine
    """
    key = "rel"
    aliases = ["relationship", "contact", "contacts"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = _char(self.caller)
        args = self.args.strip()

        if not args or args == "list":
            self._rel_list(char)
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        dispatch = {
            "list":   lambda: self._rel_list(char),
            "add":    lambda: self._rel_add(char, rest),
            "update": lambda: self._rel_add(char, rest),
            "remove": lambda: self._rel_remove(char, rest),
            "delete": lambda: self._rel_remove(char, rest),
            "note":   lambda: self._rel_note(char, rest),
            "desc":   lambda: self._rel_desc(char, rest),
        }

        handler = dispatch.get(subcmd)
        if handler:
            handler()
        else:
            self.msg(
                "Usage: rel list / add / remove / note / desc\n"
                "Type 'help rel' for details."
            )

    # -----------------------------------------------------------------------

    def _rel_list(self, char):
        contacts = char.db.contacts or {}
        if not contacts:
            self.msg(
                "Your contacts list is empty.\n"
                "Add someone with: rel add <name> <status>"
            )
            return

        lines = ["|wContacts:|n\n"]
        status_order = {s: i for i, s in enumerate(VALID_STATUSES)}

        sorted_contacts = sorted(
            contacts.items(),
            key=lambda kv: (
                status_order.get(kv[1].get("status", ""), 99),
                kv[1].get("name", "").lower()
            )
        )

        current_status = None
        for key, data in sorted_contacts:
            name = data.get("name", f"#{key}")
            status = data.get("status", "")
            has_note = bool(data.get("note", ""))
            has_desc = bool(data.get("rel_desc", ""))

            if status != current_status:
                current_status = status
                lines.append(f"\n  |x{status.upper() if status else 'NO STATUS'}|n")

            extras = []
            if has_note:
                extras.append("|xnote|n")
            if has_desc:
                extras.append("|xdesc|n")
            extra_str = f"  |x[{', '.join(extras)}]|n" if extras else ""

            lines.append(f"    |w{name}|n{extra_str}")

        lines.append(
            f"\n|x{len(contacts)} contact(s).|n  "
            f"'rel note <name>' to read a note."
        )
        self.msg("\n".join(lines))

    def _rel_add(self, char, args):
        if not args:
            self.msg(
                "Usage: rel add <name> <status>\n"
                f"Statuses: {', '.join(VALID_STATUSES)}"
            )
            return

        parts = args.rsplit(None, 1)
        if len(parts) < 2:
            self.msg(
                "Specify both a name and a status.\n"
                f"Statuses: {', '.join(VALID_STATUSES)}"
            )
            return

        target_name = parts[0].strip()
        status = parts[1].strip().lower()

        if status not in VALID_STATUSES:
            self.msg(
                f"Unknown status '{status}'.\n"
                f"Valid statuses: {', '.join(VALID_STATUSES)}"
            )
            return

        # Try to find the character in room for their id
        target = _find_char_in_room(self.caller, char, target_name)
        contacts = char.db.contacts or {}

        if target:
            key = str(target.id)
            display_name = target.db.rp_name or target.key
        else:
            # Check if already in contacts by name
            key, existing = _find_contact_by_name(contacts, target_name)
            if key:
                display_name = existing.get("name", target_name)
            else:
                # Store by name alone — no id yet
                # Generate a placeholder key from name
                key = f"name:{target_name.lower()}"
                display_name = target_name

        if key not in contacts:
            contacts[key] = {
                "name":     display_name,
                "status":   status,
                "note":     "",
                "rel_desc": "",
            }
        else:
            old_status = contacts[key].get("status", "")
            contacts[key]["name"] = display_name
            contacts[key]["status"] = status

            # Handle block list sync for status changes
            if old_status == "blocked" and status != "blocked" and target:
                block_list = char.db.block_list or set()
                block_list.discard(target.id)
                char.db.block_list = block_list

        # Sync block list
        if status == "blocked" and target:
            block_list = char.db.block_list or set()
            block_list.add(target.id)
            char.db.block_list = block_list

        char.db.contacts = contacts
        self.msg(
            f"|w{display_name}|n added to contacts as |x{status}|n."
            + (" (block list updated)" if status == "blocked" else "")
        )

    def _rel_remove(self, char, name):
        if not name:
            self.msg("Usage: rel remove <name>")
            return

        contacts = char.db.contacts or {}
        key, data = _find_contact_by_name(contacts, name)

        if not key:
            self.msg(f"No contact named '{name}'.")
            return

        display_name = data.get("name", name)
        old_status = data.get("status", "")

        # Unblock if was blocked
        if old_status == "blocked":
            try:
                char_id = int(key)
                block_list = char.db.block_list or set()
                block_list.discard(char_id)
                char.db.block_list = block_list
            except (ValueError, TypeError):
                pass

        del contacts[key]
        char.db.contacts = contacts
        self.msg(f"|w{display_name}|n removed from contacts.")

    def _rel_note(self, char, args):
        """Read or set a private note on a contact."""
        if not args:
            self.msg(
                "Usage:\n"
                "  rel note <name> = <text>\n"
                "  rel note <name>\n"
                "  rel note <name>/clear"
            )
            return

        # Check for /clear switch
        clear = False
        if "/" in args:
            name_part, _, switch = args.partition("/")
            if switch.strip().lower() == "clear":
                args = name_part.strip()
                clear = True

        contacts = char.db.contacts or {}

        if "=" in args and not clear:
            name, _, text = args.partition("=")
            name = name.strip()
            text = text.strip()
            key, data = _find_contact_by_name(contacts, name)
            if not key:
                self.msg(f"No contact named '{name}'.")
                return
            contacts[key]["note"] = text
            char.db.contacts = contacts
            self.msg(f"Note saved for |w{data.get('name', name)}|n.")
        elif clear:
            key, data = _find_contact_by_name(contacts, args)
            if not key:
                self.msg(f"No contact named '{args}'.")
                return
            contacts[key]["note"] = ""
            char.db.contacts = contacts
            self.msg(f"Note cleared for |w{data.get('name', args)}|n.")
        else:
            # Read note
            key, data = _find_contact_by_name(contacts, args)
            if not key:
                self.msg(f"No contact named '{args}'.")
                return
            note = data.get("note", "")
            display_name = data.get("name", args)
            if note:
                self.msg(f"|wNote on {display_name}:|n\n  {note}")
            else:
                self.msg(f"No note saved for |w{display_name}|n.")

    def _rel_desc(self, char, args):
        """Set or clear the desc another person sees when examining you."""
        if not args:
            self.msg(
                "Usage:\n"
                "  rel desc <name> = <text>\n"
                "  rel desc <name>/clear"
            )
            return

        # Check for /clear switch
        clear = False
        if "/" in args:
            name_part, _, switch = args.partition("/")
            if switch.strip().lower() == "clear":
                args = name_part.strip()
                clear = True

        contacts = char.db.contacts or {}

        if "=" in args and not clear:
            name, _, text = args.partition("=")
            name = name.strip()
            text = text.strip()
            key, data = _find_contact_by_name(contacts, name)
            if not key:
                self.msg(
                    f"No contact named '{name}'.\n"
                    f"Add them first with: rel add {name} <status>"
                )
                return
            contacts[key]["rel_desc"] = text
            char.db.contacts = contacts
            display_name = data.get("name", name)
            self.msg(
                f"Relationship desc set for |w{display_name}|n.\n"
                f"|xThey will see this when they examine you.|n"
            )
        elif clear:
            key, data = _find_contact_by_name(contacts, args)
            if not key:
                self.msg(f"No contact named '{args}'.")
                return
            contacts[key]["rel_desc"] = ""
            char.db.contacts = contacts
            self.msg(
                f"Relationship desc cleared for |w{data.get('name', args)}|n."
            )
        else:
            # Show current desc
            key, data = _find_contact_by_name(contacts, args)
            if not key:
                self.msg(f"No contact named '{args}'.")
                return
            desc = data.get("rel_desc", "")
            display_name = data.get("name", args)
            if desc:
                self.msg(
                    f"|wRelationship desc for {display_name}:|n\n  {desc}"
                )
            else:
                self.msg(
                    f"No relationship desc set for |w{display_name}|n."
                )


ALL_REL_CMDS = [CmdRel]
