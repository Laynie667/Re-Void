"""
typeclasses/housing.py

HousingRoom — a player-owned room typeclass for Re:Void.

Subclasses the base Room typeclass and adds:
  - Owner tracking
  - Friend list  (bypass door lock, use sethome here)
  - Builder list (dig / decorate in this space)
  - Lock flag    (blocks non-owner/non-friend entry)

Permissions are checked at entry via at_pre_object_receive.
All housing commands use the helper methods (is_owner, is_friend,
is_builder, can_enter, can_build) rather than reading db attrs directly.

Housing permissions are ROOM-LOCAL — they do not grant any global
Evennia builder permissions.
"""

from .rooms import Room


class HousingRoom(Room):
    """
    A player-owned housing room.

    Extra db attributes set at creation:
        housing_owner_id  (int)    — ObjectDB pk of the owner character
        housing_friends   (list)   — pks who can bypass lock + use sethome
        housing_builders  (list)   — pks who can dig / decorate here
        housing_locked    (bool)   — whether the room is locked to outsiders
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.housing_owner_id = None
        self.db.housing_friends  = []
        self.db.housing_builders = []
        self.db.housing_locked   = False
        self.db.room_type        = "housing"
        self.db.is_private       = True
        # Housing rooms block random jump-in by default;
        # owner/friends bypass this via can_enter() check.
        self.db.jump_protected   = True

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------

    def is_owner(self, character):
        """True if this character owns this room."""
        return (
            character is not None
            and self.db.housing_owner_id is not None
            and character.id == self.db.housing_owner_id
        )

    def is_friend(self, character):
        """True if this character is on the friend list."""
        if character is None:
            return False
        return character.id in (self.db.housing_friends or [])

    def is_builder(self, character):
        """True if this character is on the builder list."""
        if character is None:
            return False
        return character.id in (self.db.housing_builders or [])

    def is_staff(self, character):
        """True if this character has Admin or higher."""
        if character is None:
            return False
        return (
            character.is_superuser
            or character.check_permstring("Admin")
        )

    def can_enter(self, character):
        """
        True if this character may enter.
        Locked rooms only admit owners, friends, and staff.
        Unlocked rooms admit everyone.
        """
        if not self.db.housing_locked:
            return True
        return (
            self.is_owner(character)
            or self.is_friend(character)
            or self.is_staff(character)
        )

    def can_build(self, character):
        """
        True if this character may dig/decorate here.
        Owners, explicit builders, and staff may build.
        """
        return (
            self.is_owner(character)
            or self.is_builder(character)
            or self.is_staff(character)
        )

    def can_set_home(self, character):
        """
        True if this character may use sethome here.
        Owners and friends may set this as their home.
        """
        return (
            self.is_owner(character)
            or self.is_friend(character)
            or self.is_staff(character)
        )

    # ------------------------------------------------------------------
    # Friend / builder list management
    # ------------------------------------------------------------------

    def add_friend(self, character):
        friends = list(self.db.housing_friends or [])
        if character.id not in friends:
            friends.append(character.id)
            self.db.housing_friends = friends
            return True
        return False

    def remove_friend(self, character):
        friends = list(self.db.housing_friends or [])
        if character.id in friends:
            friends.remove(character.id)
            self.db.housing_friends = friends
            return True
        return False

    def add_builder(self, character):
        builders = list(self.db.housing_builders or [])
        if character.id not in builders:
            builders.append(character.id)
            self.db.housing_builders = builders
            return True
        return False

    def remove_builder(self, character):
        builders = list(self.db.housing_builders or [])
        if character.id in builders:
            builders.remove(character.id)
            self.db.housing_builders = builders
            return True
        return False

    # ------------------------------------------------------------------
    # Entry enforcement
    # ------------------------------------------------------------------

    def at_pre_object_receive(self, obj, source_location, **kwargs):
        """
        Block entry for locked housing rooms.
        Stacks with the base Room scene-lock check.
        """
        from typeclasses.characters import Character
        if isinstance(obj, Character):
            if not self.can_enter(obj):
                obj.msg(
                    "|xThe door is locked. "
                    "You have not been invited.|n"
                )
                return False
        return super().at_pre_object_receive(
            obj, source_location, **kwargs
        )

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def get_housing_status(self):
        """Return a formatted status block for the housing command."""
        from evennia.objects.models import ObjectDB

        def _name(pk):
            try:
                obj = ObjectDB.objects.get(pk=pk)
                return obj.db.rp_name or obj.key
            except Exception:
                return f"#{pk}"

        owner_name = (
            _name(self.db.housing_owner_id)
            if self.db.housing_owner_id else "none"
        )
        lock_str = "|rLocked|n" if self.db.housing_locked else "|gUnlocked|n"
        friends  = [_name(pk) for pk in (self.db.housing_friends or [])]
        builders = [_name(pk) for pk in (self.db.housing_builders or [])]

        return "\n".join([
            f"|w{self.key}|n  [{lock_str}]",
            f"  Owner:    {owner_name}",
            f"  Friends:  {', '.join(friends) or 'none'}",
            f"  Builders: {', '.join(builders) or 'none'}",
        ])
