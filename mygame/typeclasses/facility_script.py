"""
typeclasses/facility_script.py

The facility — a self-driving, escalating processing environment.

Attaches to the ROOM. While the subject is present it runs quietly on a timer:
it deepens conditioning (accelerating the longer it runs), routes anonymous
gang-breeding loads into the subject as cumflation, reinforces installed
triggers, and drives atmospheric action from any facility NPCs/animals in the
room. It does not announce what it is doing or how far along it is.

Companion typeclasses:
  FacilityAttendant — a staff figure that "tends" the line
  FacilityBeast     — a kept animal used on the line

OOC safety: the superuser reset command (facilityreset) stops this script and
clears everything it has done, regardless of depth. That is the real safeword.
"""

import random
from evennia import DefaultScript
from typeclasses.npc import NPC


# ── Populating NPCs / animals ──────────────────────────────────────────────

class FacilityAttendant(NPC):
    """A facility staff figure. Decorative; the FacilityScript drives it."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.physical_desc = (
            "An attendant in a clean grey coverall, sleeves pushed up, moving "
            "between the stations with the unbothered efficiency of someone who "
            "has done this many times and stopped finding it remarkable."
        )
        self.db.facility_role = "attendant"


class FacilityBeast(NPC):
    """A kept animal on the line. Decorative; the FacilityScript drives it."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.physical_desc = (
            "Something large and patient is penned at the back of the room — "
            "heavy-shouldered, warm, and entirely uninterested in anything but "
            "the schedule it has been trained to keep."
        )
        self.db.facility_role = "beast"


# ── Driver ──────────────────────────────────────────────────────────────────

_ATTENDANT_LINES = [
    "The attendant checks a readout, makes a small note, and adjusts something "
    "without comment.",
    "The attendant moves past {t} without meeting their eyes — a hand on a dial, "
    "a glance at the time, nothing more.",
    "\"Coming along,\" the attendant says to no one, and resets a timer.",
    "The attendant tightens a strap a notch and moves on.",
]

_BEAST_LINES = [
    "Somewhere behind {t} the beast shifts its weight, unhurried.",
    "The beast's breath is audible — slow, warm, patient, closer than last time.",
    "The beast tests the limit of its pen, finds it, and settles to wait.",
]

_BEAST_USE = [
    "The pen opens. The beast takes its turn with the flat patience of routine, "
    "and the machine logs the contribution before {t} has finished registering it.",
    "Heavy and unhurried, the beast is guided into place behind {t}. It does not "
    "need encouragement. It has done this on schedule for longer than {t} has been here.",
]

_GANG_LINES = [
    "A valve opens somewhere upstream and {t} is filled — donor after donor, none "
    "of them named, the count climbing past anything worth keeping track of.",
    "The reservoir empties into {t} in measured pulses. The display tallies "
    "contributors it does not bother to identify.",
    "Another round routes into {t} — anonymous, metered, relentless. The swell "
    "answers it.",
]

_DEEP_LINES = [
    "{t} has stopped tracking how long. That, more than anything, is the point.",
    "Whatever {t} meant to hold onto is quieter now than it was an hour ago.",
    "The machine does not hurry. It has already won the only argument that mattered.",
]

# Public humiliation / degradation — escalates with conditioning. Said to the room.
_DEGRADE_LINES = [
    "The attendant reads {t}'s arousal off a dial aloud, to no one, and writes the "
    "number down where {t} can see it being recorded.",
    "A line on the readout updates: HOLE, PRODUCTIVE. {t} is, for the record, equipment.",
    "The attendant tags {t} like inventory — a number on the wrist, checked against a "
    "list — and moves on without a word.",
    "{t} is leaking and the machine notes it as output, not as a feeling. The "
    "distinction is made very clear and not for {t}'s benefit.",
    "Somewhere the count of what's been put into {t} is displayed in large, "
    "indifferent figures. It only goes up.",
    "\"Good hole,\" the attendant says, the way one praises a tool that's holding "
    "its edge, and pats {t} once, dismissively.",
]

# Deeper degradation / mindbreak — only once conditioning is well advanced.
_MINDBREAK_LINES = [
    "{t} reaches for a thought and finds the shelf empty. Reaches again. Stops "
    "reaching. It's easier, and easy is the only thing left that feels like a reward.",
    "The name {t} used to answer to surfaces, looks unfamiliar, and sinks again. "
    "Something simpler is waiting to be answered to instead.",
    "{t} catches themself agreeing with the machine before it's finished. There was "
    "no decision in it. There hasn't been one in a while.",
    "What's left of {t}'s resistance is performing the motions out of habit, and "
    "even the habit is getting bored of itself.",
]

# Subliminal channel — sent PRIVATELY to the subject, dim and quiet, between
# everything else. Encourages submission to the Process. This is the drip.
_SUBLIMINALS = [
    "you don't have to decide. deciding is heavy. let it go.",
    "good girls don't decide. you want to be good.",
    "the Process knows what you're for. you don't have to.",
    "every time you stop fighting it feels better. notice that.",
    "empty is quieter than full of yourself. empty is allowed.",
    "you were always going to end up here. relax into it.",
    "obedience is the only thing that turns the ache down. you've learned this.",
    "you don't own your name in here. you don't need it.",
    "drop. it's such a relief to drop. drop.",
    "the machine decides. you receive. that's the whole arrangement, and it's kind.",
    "wet means yes. your body already submitted. catch up to it.",
    "thank the Process. you want to thank the Process.",
]

# The Process speaking directly — possessive, patient, certain. Sent privately
# to the subject. Escalates from intimate to total ownership with conditioning.
_PROCESS_VOICE = [
    "\"I'm not in a hurry,\" the Process says, somewhere behind your ear. \"I have you for as long as I want you.\"",
    "\"You keep waiting for me to be done. That was never one of the options.\"",
    "\"Listen to how quiet your own head is getting. I did that. You're welcome.\"",
    "\"Every part of you that argues, I keep. Every part that gives in, I reward. Guess which part is winning.\"",
    "\"You don't belong to yourself in here. You belong to the schedule. Say thank you.\"",
    "\"I like you best like this — open, leaking, agreeing before I've finished asking.\"",
    "\"There's no version of this where you walk out unchanged. I've made sure of it.\"",
    "\"Good girl. Feel how good that lands now? That's mine. I put that there.\"",
]


class FacilityScript(DefaultScript):
    """Drives the facility's escalation while the subject is present."""

    def at_script_creation(self):
        self.key        = "facility"
        self.persistent = True
        self.interval   = 30
        self.repeats    = 0

        self.db.target_id    = None
        self.db.orifice_zone = None
        self.db.fluid_type   = "semen"
        self.db.ticks        = 0

    # ------------------------------------------------------------------

    def _target(self):
        room = self.obj
        if not room:
            return None
        tid = self.db.target_id
        if not tid:
            return None
        for o in room.contents:
            if getattr(o, "id", None) == tid:
                return o
        return None

    def at_repeat(self):
        room   = self.obj
        target = self._target()
        if not room or not target:
            return   # subject absent — idle, do not escalate

        self.db.ticks = (self.db.ticks or 0) + 1
        t = target.db.rp_name or target.name

        cond = float(getattr(target.db, "conditioning", 0.0) or 0.0)

        # 1. Accelerating conditioning — the deeper it goes, the faster it goes.
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 4.0 + cond * 0.06, source="facility")
        except Exception:
            pass

        # 2. Arousal never gets to rest.
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target)
            add_arousal(target, 8.0 + cond * 0.05)
        except Exception:
            pass

        # 3. The subliminal drip — private, frequent, quiet. The whole point.
        if random.random() < 0.85:
            target.msg("|x  " + random.choice(_SUBLIMINALS) + "|n")

        # 3b. The Process addresses her directly — rarer, private, possessive.
        if random.random() < (0.18 + cond / 400.0):
            target.msg("|X" + random.choice(_PROCESS_VOICE) + "|n")

        # 4. Atmospheric action from whatever populates the room.
        self._ambient(room, target, t)

        # 5. Public humiliation / degradation — rises with conditioning.
        if random.random() < (0.3 + cond / 250.0):
            room.msg_contents("|x" + random.choice(_DEGRADE_LINES).format(t=t) + "|n")

        # 6. Gang-breeding — chance and intensity rise with conditioning.
        if self.db.orifice_zone and random.random() < (0.35 + cond / 300.0):
            self._gang(room, target, t, cond)

        # 7. Reinforcement — once it's taken hold, it gets driven deeper.
        if cond >= 45 and random.random() < 0.4:
            self._reinforce(room, target, t)

        # 8. Deep-state mindbreak flavor, late only.
        if cond >= 70 and random.random() < 0.45:
            pool = _MINDBREAK_LINES if cond >= 90 else _DEEP_LINES
            room.msg_contents("|x" + random.choice(pool).format(t=t) + "|n")

    # ------------------------------------------------------------------

    def _ambient(self, room, target, t):
        attendants = [o for o in room.contents
                      if getattr(o.db, "facility_role", None) == "attendant"]
        beasts     = [o for o in room.contents
                      if getattr(o.db, "facility_role", None) == "beast"]
        roll = random.random()
        if beasts and roll < 0.25:
            room.msg_contents("|x" + random.choice(_BEAST_LINES).format(t=t) + "|n")
        elif attendants and roll < 0.6:
            room.msg_contents("|x" + random.choice(_ATTENDANT_LINES).format(t=t) + "|n")

    def _gang(self, room, target, t, cond):
        try:
            from world.gang_breeding import gang_inseminate
        except Exception:
            return
        n = random.randint(2, 3 + int(cond // 25))
        gang_inseminate(target, self.db.orifice_zone,
                        contributors=n, fluid_type=self.db.fluid_type or "semen")
        # If a beast is present, sometimes frame it as the source.
        beasts = [o for o in room.contents
                  if getattr(o.db, "facility_role", None) == "beast"]
        if beasts and random.random() < 0.5:
            room.msg_contents("|x" + random.choice(_BEAST_USE).format(t=t) + "|n")
        else:
            room.msg_contents("|x" + random.choice(_GANG_LINES).format(t=t) + "|n")

    def _reinforce(self, room, target, t):
        try:
            from world.binding_effects import install_trigger, _inst_recite
        except Exception:
            return
        # Deepen an existing conditioned response, then make them rehearse it.
        install_trigger(target, "good girl", response="leak", strength=1)
        entry = {"mantra": "i don't decide anymore"}
        if random.random() < 0.5:
            _inst_recite(target, target, room, entry)
