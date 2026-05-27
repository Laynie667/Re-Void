"""
typeclasses/written_item.py

Written items — documents that exist as lightweight game objects.

Written items can be:
  - Held, given, left in rooms, attached to character zones
  - Read by anyone who has access
  - Sealed (no further editing) and unsealed by the author
  - Copied by the author (if unsealed)
  - Destroyed permanently

Types: letter, note, contract, list, journal, page, document

The content is a list of strings (one per line), edited via the
universal text editor.

Created with:
    write new "<type>"

Interacted with:
    read "<item>"           — read contents
    write seal "<item>"     — seal
    write unseal "<item>"   — unseal (author only)
    give "<item>" to <name> — transfer
    leave "<item>"          — place in room
    leave "<item>" on <zone> — attach to character zone
    take "<item>"           — pick up
    destroy "<item>"        — remove permanently
    copy "<item>"           — make a copy (author only, unsealed)
"""

import time
from evennia.objects.objects import DefaultObject
from .objects import ObjectParent


# Valid document types
VALID_TYPES = [
    "letter", "note", "contract", "list",
    "journal", "page", "document",
]


class WrittenItem(ObjectParent, DefaultObject):
    """
    A written document. Holds text content and authorship.

    Sealed items show only their cover to non-authors.
    Unsealed items display their full contents to anyone who reads them.
    """

    def at_object_creation(self):
        """Set all written item attributes."""
        super().at_object_creation()

        # Document type
        self.db.item_type = "note"
        # Content — list of strings, one per line
        self.db.content = []
        # Author character ID
        self.db.author_id = None
        # Author display name (snapshot at creation)
        self.db.author_name = None
        # Whether no further editing is allowed
        self.db.sealed = False
        # Timestamp of creation
        self.db.created_at = None
        # Title or opening line (displayed in room/zone)
        self.db.display_title = None

    def setup_item(self, item_type, author):
        """
        Configure a newly created written item.

        Args:
            item_type (str): Type from VALID_TYPES.
            author: Character creating the item.
        """
        self.db.item_type = item_type if item_type in VALID_TYPES else "note"
        self.db.author_id = author.id
        self.db.author_name = (
            author.db.rp_name
            if hasattr(author.db, 'rp_name') and author.db.rp_name
            else author.key
        )
        self.db.created_at = time.time()

        # Set key/name
        self.key = f"a {self.db.item_type}"
        self.db.desc = (
            f"A {self.db.item_type}, blank. "
            f"Written by |w{self.db.author_name}|n."
        )

    def is_author(self, char):
        """Check if a character is the author of this item."""
        return char.id == self.db.author_id

    def get_display_title(self):
        """
        Return a short display title for room/zone listings.
        Uses first line of content if no explicit title is set.
        """
        if self.db.display_title:
            return self.db.display_title
        content = self.db.content or []
        if content:
            first = content[0]
            if len(first) > 40:
                return first[:37] + "..."
            return first
        return f"a blank {self.db.item_type}"

    def get_read_output(self, reader):
        """
        Assemble the read output for this item.

        Args:
            reader: Character trying to read.

        Returns:
            str: Formatted content, or sealed message.
        """
        item_type = self.db.item_type or "note"
        author = self.db.author_name or "unknown"
        content = self.db.content or []
        sealed = self.db.sealed

        sep = f"|w{'─' * 44}|n"

        # Sealed to non-author
        if sealed and not self.is_author(reader):
            return (
                f"\n{sep}\n"
                f"|wA sealed {item_type}.|n\n"
                f"{sep}\n"
                f"  |xThe seal is intact. It has not been opened.|n\n"
                f"  Author: {author}\n"
                f"{sep}\n"
                f"|xBreak the seal with 'read/break \"{self.key}\"'.|n\n"
            )

        if not content:
            return (
                f"\n{sep}\n"
                f"|wA {item_type} by {author}|n\n"
                f"{sep}\n"
                f"  |x(blank — nothing written here)|n\n"
                f"{sep}\n"
            )

        seal_note = ""
        if sealed:
            seal_note = "  |x[sealed]|n\n"

        lines = [
            f"\n{sep}",
            f"|wA {item_type}|n  |x— by {author}|n",
            seal_note.rstrip() if seal_note else "",
            sep,
        ]
        for line in content:
            lines.append(f"  {line}")
        lines.append(sep)

        return "\n".join(l for l in lines if l is not None)

    def return_appearance(self, looker, **kwargs):
        """Override look — show read output."""
        return self.get_read_output(looker)

    def update_display_name(self):
        """
        Refresh the item's key and desc based on current content.
        Called after editing.
        """
        item_type = self.db.item_type or "note"
        author = self.db.author_name or "unknown"
        title = self.get_display_title()
        sealed_str = " [sealed]" if self.db.sealed else ""

        self.key = f"a {item_type}{sealed_str}"

        self.db.desc = (
            f"A {item_type} written by |w{author}|n. "
            f'"{title}"'
            + (f" |x[sealed]|n" if self.db.sealed else "")
        )
