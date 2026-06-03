"""
typeclasses/aphrodisiac_item.py

AphrodisiacItem — a consumable that applies arousal effects.

Variants:
  personal   — affects only the user
  room       — affects everyone in the room on use
  wolf_bait  — marks the user as wolf-bait (NPC wolves react differently)

Effects when used:
  - Sets arousal_floor for duration_hours
  - Sets stim_per_tick for duration_hours
  - Fires a room or personal message
  - Applies wolf_bait flag if variant

Wolf bait marks the character in a way the wolf NPC pack can detect.
When a wolf NPC calls check_wolf_bait(character), it returns True.
The pack then queues breeding behavior on that character.
"""

import time
from evennia import DefaultObject


class AphrodisiacItem(DefaultObject):
    """
    A consumable aphrodisiac.

    Use:  use <item>   (or: consume <item>)
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key              = "aphrodisiac"
        self.db.desc          = "A small vial. Something about it smells warm."
        self.db.variant       = "personal"    # personal / room / wolf_bait
        self.db.duration_hours= 2.0
        self.db.arousal_floor = 30.0
        self.db.stim_per_tick = 5.0
        self.db.uses          = 1

    def use(self, actor) -> tuple:
        """
        Apply the aphrodisiac effects.
        Returns (True, "") or (False, reason).
        """
        uses = self.db.uses or 0
        if uses <= 0:
            return False, f"{self.key} is empty."

        room     = actor.location
        variant  = self.db.variant or "personal"
        duration = float(self.db.duration_hours or 2.0)
        floor    = float(self.db.arousal_floor   or 30.0)
        stim     = float(self.db.stim_per_tick   or 5.0)
        expires  = time.time() + duration * 3600

        targets = []
        if variant == "room" and room:
            from typeclasses.characters import Character
            targets = [obj for obj in room.contents if isinstance(obj, Character)]
        else:
            targets = [actor]

        actor_name = actor.db.rp_name or actor.name

        for char in targets:
            # Apply temporary floor + stim (store with expiry)
            char.db.arousal_floor = max(
                float(char.db.arousal_floor or 0.0), floor
            )
            char.db.stim_per_tick = float(char.db.stim_per_tick or 0.0) + stim
            # Schedule expiry via db timestamp
            expirations = list(char.db.aphrodisiac_expirations or [])
            expirations.append({
                "expires": expires,
                "floor":   floor,
                "stim":    stim,
            })
            char.db.aphrodisiac_expirations = expirations

            if char != actor:
                char.msg(
                    f"|xSomething from {actor_name} reaches you — "
                    f"warm and insistent and already working.|n"
                )

        # Wolf bait
        if variant == "wolf_bait":
            actor.db.wolf_bait         = True
            actor.db.wolf_bait_expires = expires
            actor.msg(
                "|xThe scent settles on you — heavy, animal, wrong in the best way. "
                "Anything with a nose will notice.|n"
            )
            if room:
                room.msg_contents(
                    f"|x{actor_name} smells different. Something primal just changed.|n",
                    exclude=[actor],
                )
        elif variant == "room":
            if room:
                room.msg_contents(
                    f"|x{actor_name} releases something into the air — "
                    f"a warm, insistent scent that settles over the room.|n",
                    exclude=[actor],
                )
            actor.msg("|xThe aphrodisiac disperses into the room.|n")
        else:
            actor.msg(
                "|xThe warmth of it hits almost immediately — a floor under your arousal "
                "that wasn't there a moment ago.|n"
            )

        # Consume use
        new_uses = uses - 1
        if new_uses <= 0:
            self.delete()
        else:
            self.db.uses = new_uses

        return True, ""


def check_wolf_bait(character) -> bool:
    """Return True if character is currently marked as wolf bait."""
    if not getattr(character.db, "wolf_bait", False):
        return False
    expires = getattr(character.db, "wolf_bait_expires", 0) or 0
    if time.time() > expires:
        character.db.wolf_bait         = False
        character.db.wolf_bait_expires = 0
        return False
    return True


def passive_aphrodisiac_check(character):
    """Called by passive tick — expire aphrodisiac effects."""
    expirations = list(character.db.aphrodisiac_expirations or [])
    if not expirations:
        return

    now      = time.time()
    remaining = []
    for entry in expirations:
        if now >= entry.get("expires", 0):
            # Remove this effect's contribution
            floor = float(entry.get("floor", 0.0))
            stim  = float(entry.get("stim",  0.0))
            character.db.arousal_floor = max(
                0.0,
                float(character.db.arousal_floor or 0.0) - floor
            )
            character.db.stim_per_tick = max(
                0.0,
                float(character.db.stim_per_tick or 0.0) - stim
            )
        else:
            remaining.append(entry)

    character.db.aphrodisiac_expirations = remaining
