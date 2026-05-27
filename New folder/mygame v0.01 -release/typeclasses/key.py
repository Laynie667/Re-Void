"""
typeclasses/key.py

Key objects — generated when a zone item is locked with slock or plock.

Keys are real lightweight game objects. They can be held, given, dropped,
and lost. A key holds everything needed to unlock the target zone.

For scene locks (slock): safeword or scene end releases the lock,
key is consumed.

For persistent locks (plock): only the keyholder's key releases it.
Admin can intervene for account emergencies (banned/deleted keyholder).
Safeword does NOT release persistent locks.
"""

import time
from evennia.objects.objects import DefaultObject
from .objects import ObjectParent


class Key(ObjectParent, DefaultObject):
    """
    A lock key. Holds target character, target zone, and lock type.

    Generated automatically by slock and plock commands.
    Read with 'examine key' to see what it unlocks.
    Transfer with 'give key to <name>'.
    """

    def at_object_creation(self):
        """Set all key attributes."""
        super().at_object_creation()

        # Who this key unlocks
        self.db.target_char_id = None
        # Which zone is locked (zone lock)
        self.db.target_zone = None
        # Which freeform item is locked (freeform lock)
        self.db.target_item = None
        # "zone" or "freeform"
        self.db.target_type = "zone"
        # "scene" or "persistent"
        self.db.lock_type = "scene"
        # Account/character that created the lock
        self.db.created_by_id = None
        self.db.created_by_name = None
        # Timestamp
        self.db.created_at = None

    def setup_key(self, target_char, zone_name, lock_type, creator,
                  target_type="zone", item_name=None):
        """
        Configure a newly created key.

        Args:
            target_char: Character object being locked.
            zone_name (str): Zone being locked (or zone context for freeform).
            lock_type (str): "scene" or "persistent".
            creator: Character/Account creating the lock.
            target_type (str): "zone" or "freeform".
            item_name (str): Freeform item name, if target_type == "freeform".
        """
        target_name = target_char.db.rp_name or target_char.key

        self.db.target_char_id = target_char.id
        self.db.target_type = target_type
        self.db.lock_type = lock_type
        self.db.created_by_id = creator.id
        self.db.created_by_name = (
            creator.db.rp_name
            if hasattr(creator.db, 'rp_name') and creator.db.rp_name
            else creator.key
        )
        self.db.created_at = time.time()

        if target_type == "freeform" and item_name:
            self.db.target_item = item_name.lower()
            display = item_name
            unlock_hint = f"unplock {target_name} {item_name}"
        else:
            zone_display = zone_name.replace("_", " ")
            self.db.target_zone = zone_name
            display = zone_display
            unlock_hint = f"unlock {zone_display}"

        # Set descriptive name and desc
        lock_label = "scene lock" if lock_type == "scene" else "persistent lock"
        self.key = f"a key [{target_name} / {display}]"
        self.db.desc = (
            f"A small key. It fits the lock at "
            f"|w{target_name}|n's {display}. "
            f"This is a {lock_label}."
        )
        self.db.unlock_hint = unlock_hint

    def get_lock_info(self):
        """
        Return a formatted string describing what this key unlocks.

        Returns:
            str: Formatted lock info.
        """
        from evennia import search_object
        target_id = self.db.target_char_id
        zone = (self.db.target_zone or "unknown").replace("_", " ")
        lock_type = self.db.lock_type or "scene"
        creator_name = self.db.created_by_name or "unknown"

        target_name = "unknown"
        if target_id:
            results = search_object(f"#{target_id}")
            if results:
                char = results[0]
                target_name = char.db.rp_name or char.key

        import datetime
        created_at = self.db.created_at
        if created_at:
            ts = datetime.datetime.fromtimestamp(created_at).strftime(
                "%Y-%m-%d %H:%M"
            )
        else:
            ts = "unknown"

        lock_label = (
            "|rPERSISTENT|n" if lock_type == "persistent"
            else "|ySCENE|n"
        )

        target_type = self.db.target_type or "zone"
        target_item = self.db.target_item
        unlock_hint = self.db.unlock_hint or "unlock <target>"

        if target_type == "freeform" and target_item:
            target_label = "Item"
            target_display = target_item
        else:
            target_label = "Zone"
            target_display = zone

        sep = f"|w{'─' * 44}|n"
        return (
            f"\n{sep}\n"
            f"|wKey|n\n"
            f"{sep}\n"
            f"  Target:     |w{target_name}|n\n"
            f"  {target_label}:       {target_display}\n"
            f"  Lock type:  {lock_label}\n"
            f"  Locked by:  {creator_name}\n"
            f"  Locked at:  |x{ts}|n\n"
            f"{sep}\n"
            f"|xUse '{unlock_hint}' while holding this key.|n\n"
        )

    def return_appearance(self, looker, **kwargs):
        """Override look to show lock info."""
        return self.get_lock_info()
