"""
Fireplace commands.

CmdTendFire  — stoke or bank the fire in a room with a hearth, shifting
               room.db.hearth_state between five levels.

Fire levels (ascending): banked → low → warm → bright → roaring
The room initialises to "warm" if the attribute hasn't been set yet.
"""

from evennia import Command

# ---------------------------------------------------------------------------
# Fire level data
# ---------------------------------------------------------------------------

_FIRE_LEVELS = ["banked", "low", "warm", "bright", "roaring"]

# (new_state_or_None, message_to_caller)
_STOKE = {
    "banked":  ("low",     "|yYou coax the banked coals back to life. A low flame catches and holds.|n"),
    "low":     ("warm",    "|yYou add a split log and tend the coals. The flames grow steady and warm.|n"),
    "warm":    ("bright",  "|yYou feed the fire well. The flames brighten and hearthlight reaches further into the room.|n"),
    "bright":  ("roaring", "|yYou heap wood on generously. The fire roars up, the hearth blazing full.|n"),
    "roaring": (None,      "|xThe fire is burning as high as it safely should. Let it be.|n"),
}

_BANK = {
    "banked":  (None,      "|xThe fire is already banked. There's nothing left to reduce.|n"),
    "low":     ("banked",  "|xYou spread the coals carefully. The flames die back to a low amber glow.|n"),
    "warm":    ("low",     "|xYou ease the fire back. The flames settle to a quieter, lower burn.|n"),
    "bright":  ("warm",    "|xYou pull back the fuel. The fire drops to a comfortable, steady warmth.|n"),
    "roaring": ("bright",  "|xYou bank the fire down from its peak. It settles to a bright, even burn.|n"),
}

# Room-wide messages when the level changes (seen by everyone except the person tending)
_ROOM_MSG = {
    "banked":  "|xThe hearth settles to banked coals — a faint amber glow, little heat.|n",
    "low":     "|xThe fire drops to a low, steady flicker.|n",
    "warm":    "|yThe fire rebuilds. A comfortable warmth spreads outward from the hearth.|n",
    "bright":  "|yThe fire brightens. Hearthlight reaches the far corners of the room.|n",
    "roaring": "|yThe fire roars up. The entire hearthside flushes warm and bright.|n",
}


# ---------------------------------------------------------------------------
# CmdTendFire
# ---------------------------------------------------------------------------

class CmdTendFire(Command):
    """
    Tend the fireplace — stoke it higher or bank it lower.

    Usage:
      tend fire       — stoke the fire up one level
      stoke fire      — same as tend fire
      stoke           — same
      bank fire       — reduce the fire one level
      bank            — same

    Fire levels low to high:
      banked → low → warm → bright → roaring

    The current fire level affects the hearth zone's ambient feel and
    is referenced by other room systems.
    """

    key     = "tend fire"
    aliases = ["stoke fire", "stoke", "bank fire", "bank"]
    locks   = "cmd:all()"
    help_category = "General"

    def func(self):
        caller   = self.caller
        room     = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        # Determine action
        cmd_used = self.cmdstring.lower()
        banking  = cmd_used.startswith("bank")

        # Get current state, defaulting to warm
        state = getattr(room.db, "hearth_state", None) or "warm"
        if state not in _FIRE_LEVELS:
            state = "warm"

        table = _BANK if banking else _STOKE
        new_state, msg = table.get(state, (None, "|xNothing to do here.|n"))

        caller.msg(msg)

        if new_state:
            room.db.hearth_state = new_state
            room_msg = _ROOM_MSG.get(new_state)
            if room_msg:
                room.msg_contents(room_msg, exclude=caller)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_FIREPLACE_CMDS = [CmdTendFire]
