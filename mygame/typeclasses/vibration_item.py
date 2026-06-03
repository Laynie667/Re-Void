"""
typeclasses/vibration_item.py

VibrationItem — a PlugItem or WearableItem subclass that can vibrate.
RemoteControlItem — held by a partner; triggers vibration on the paired item.

Vibration states: off / low / medium / high / random
  - off:    no messages
  - low:    private sensation message every 5 min
  - medium: private sensation every 2 min + occasional room-visible
  - high:   private sensation every 1 min + regular room-visible
  - random: intensity and timing vary each tick

Remote control commands (on RemoteControlItem):
  vibrate <target> [intensity]   — set vibration level
  vibrate/stop <target>          — turn off
  vibrate/pulse <target>         — one-shot burst regardless of current state

Paired via: item.db.paired_remote = remote.dbref (set on wear if remote present)
"""

import time
import random

from typeclasses.plug_item import PlugItem

# Message pools per intensity
_PRIVATE_MSGS = {
    "low": [
        "A soft hum against the inside of you — brief, low, barely there.",
        "A faint vibration where the plug sits. Easy to mistake for nothing.",
        "Low and steady — the hum of it registers and fades.",
    ],
    "medium": [
        "The vibration picks up — a consistent pulse that's harder to ignore.",
        "Medium intensity, unwavering. It settles in your awareness and stays.",
        "The hum is real now. Your body is paying attention.",
    ],
    "high": [
        "High intensity — the vibration is insistent and constant and very present.",
        "The plug is working at full speed and your body has no choice but to notice.",
        "High and relentless. There is no ignoring this. It's in everything.",
    ],
    "random": [
        "An unexpected burst of vibration — gone before you fully react.",
        "The intensity shifts without warning. High, then low, then high again.",
        "Random and impossible to predict. Your body can't settle.",
    ],
}

_ROOM_MSGS = {
    "medium": [
        "{name} shifts slightly — something subtle, contained.",
        "A faint flush touches {name}'s expression.",
    ],
    "high": [
        "{name} catches a breath — something is clearly happening.",
        "{name} goes very still for a moment, jaw tight.",
        "Something crosses {name}'s face — there and gone.",
    ],
    "random": [
        "{name} twitches faintly — involuntary, brief.",
        "{name} stops mid-movement. Then continues.",
    ],
}

# Tick intervals per intensity (seconds)
_INTERVALS = {
    "low":    300,
    "medium": 120,
    "high":    60,
    "random":  90,
}


class VibratingPlugItem(PlugItem):
    """
    A plug with a built-in vibration motor.

    Vibration is controlled via a paired RemoteControlItem or by staff.
    The vibration state is stored on the plug's db and checked by the
    passive accumulation tick.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key                 = "vibrating plug"
        self.db.desc             = "A plug with a small motor inside. Currently quiet."
        self.db.vibe_state       = "off"     # off/low/medium/high/random
        self.db.vibe_last_tick   = 0.0       # unix timestamp of last message
        self.db.paired_remote    = None      # dbref of paired remote control

    def get_active_desc(self) -> str:
        state = self.db.vibe_state or "off"
        base  = self.db.player_desc or self.db.desc or ""
        if state != "off":
            return f"{base} It is vibrating — {state}."
        return base

    def set_vibe(self, state: str):
        """Set vibration state. state: off/low/medium/high/random"""
        valid = ("off", "low", "medium", "high", "random")
        self.db.vibe_state = state if state in valid else "off"
        if state == "off":
            self.db.vibe_last_tick = 0.0

    def vibe_tick(self, character):
        """
        Called by the passive tick system (via item_vibe_tick in scripts.py).
        Fires sensation messages based on current intensity and interval.
        """
        state = self.db.vibe_state or "off"
        if state == "off":
            return

        interval = _INTERVALS.get(state, 120)
        if time.time() - float(self.db.vibe_last_tick or 0.0) < interval:
            return

        self.db.vibe_last_tick = time.time()

        # Private message to wearer
        pool = _PRIVATE_MSGS.get(state, _PRIVATE_MSGS["low"])
        character.msg(random.choice(pool))

        # Arousal tick
        arousal_gain = {"low": 2.0, "medium": 5.0, "high": 9.0, "random": random.uniform(2, 9)}.get(state, 3.0)
        try:
            from typeclasses.arousal_script import add_arousal
            add_arousal(character, arousal_gain)
        except Exception:
            pass

        # Room-visible message for medium/high/random
        if state in _ROOM_MSGS and character.location:
            room_pool = _ROOM_MSGS[state]
            if random.random() < 0.40:
                cname = character.db.rp_name or character.name
                character.location.msg_contents(
                    random.choice(room_pool).format(name=cname),
                    exclude=[character],
                )


class RemoteControlItem(PlugItem.__bases__[0]):
    """
    A remote control paired with a VibratingPlugItem.

    Hold in inventory; use 'vibrate <target> [intensity]' to control.
    Must be in the same room as the target (or soul-linked for distance control).
    """

    def at_object_creation(self):
        # Don't call PlugItem's __init__ — this isn't a plug
        from evennia import DefaultObject
        DefaultObject.at_object_creation(self)
        self.key             = "remote control"
        self.db.desc         = "A small device. It controls something."
        self.db.paired_item  = None   # dbref of the vibrating item
        self.db.range_locked = True   # True = must be in same room

    def get_display_name(self, looker=None, **kwargs):
        paired = self.db.paired_item
        if paired:
            from evennia import search_object
            results = search_object(paired, exact=True)
            if results:
                return f"{self.key} [→ {results[0].key}]"
        return self.key
