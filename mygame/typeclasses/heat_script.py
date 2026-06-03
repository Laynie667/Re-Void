"""
typeclasses/heat_script.py

HeatScript — perpetual heat, enforced by the contract (the perpetual_heat
binding effect). Attaches to the CHARACTER, so it follows her anywhere, not
just inside the facility room. It holds her arousal floor up, pushes arousal,
periodically spikes into a heat wave, and flags her as in-heat so animals and
the facility treat her accordingly.

Cleared by the facility reset (which stops the script and the flag).
"""

import random
from evennia import DefaultScript

_HEAT_PRIVATE = [
    "heat rolls through you again — low, insistent, impossible to sit still under.",
    "you're slick to the thighs and it won't stop. your body wants, on its own schedule.",
    "every shift of air feels like a hand. you'd present to a draft right now and you know it.",
    "the ache settles in deep and pulses. empty reads as a problem your body wants solved.",
    "you catch yourself rocking against nothing. you don't stop. you can't, really.",
]

_HEAT_ROOM = [
    "{t} is visibly in heat — flushed, slick, hips working in tiny helpless circles against the restraints.",
    "The smell of {t}'s heat thickens, and every animal in the room turns toward it at once.",
    "{t} whines low and pushes back against nothing, presenting on instinct, past the point of pretending otherwise.",
]


class HeatScript(DefaultScript):
    """Keeps the wearer in perpetual heat."""

    def at_script_creation(self):
        self.key        = "perpetual_heat"
        self.persistent = True
        self.interval   = 150
        self.repeats    = 0

    def at_repeat(self):
        char = self.obj
        if not char or not hasattr(char, "db"):
            self.stop(); return
        if not getattr(char.db, "perpetual_heat", False):
            self.stop(); return

        char.db.arousal_floor = max(float(getattr(char.db, "arousal_floor", 0) or 0), 45.0)
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(char)
            add_arousal(char, 6.0)
        except Exception:
            pass

        if random.random() < 0.45:
            char.msg("|r  " + random.choice(_HEAT_PRIVATE) + "|n")
        room = char.location
        if room and random.random() < 0.25:
            t = char.db.rp_name or char.name
            room.msg_contents("|r" + random.choice(_HEAT_ROOM).format(t=t) + "|n",
                              exclude=[char])
