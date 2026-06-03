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
# Beats are grounded: each describes something physically happening to the
# subject right now, so the scene stays legible. One primary beat fires per
# tick (steady-atmospheric), often paired with a crude line.

# The machine working her body — milking rig, intake arm, restraints.
_MACHINE_BEATS = [
    "The cups clamp back onto {t}'s heavy tits and pull in slow, greedy pulses — "
    "draw and release, draw and release — milking the bitch whether she's got "
    "anything left to give or not.",
    "The milking rig steps its rhythm up without asking. {t}'s breath catches on the "
    "new pace and then gives in to it, because there is nothing else a cow gets to do.",
    "The intake arm seated deep in {t} hums and works harder, unhurried, keeping the "
    "bitch stretched open and dripping around it.",
    "A pump cycles and {t} feels it everywhere at once — tits, belly, cunt — one "
    "machine treating the whole animal as a single thing to drain and breed and top "
    "back up on schedule.",
    "The restraints take up a half-inch of slack, hauling {t} back into the cradle: "
    "tits out, hips tipped, holes presented at exactly the angle the line prefers.",
    "The rig pauses just long enough for {t} to hope it's done, then resumes harder. "
    "It is never done with livestock. It only pauses.",
]

# Hands on her — inspection, prodding, fingering, use. Crude and clinical.
_USE_BEATS = [
    "A handler forces two thick fingers into {t}'s cunt without ceremony, checking "
    "depth and wetness, and calls the reading across the room like a stock report. "
    "\"Soaked. Bitch is ready again.\"",
    "The attendant spreads {t} open with a gloved thumb and prods the swollen clit "
    "just to watch the animal buck against the straps, then notes the reaction with "
    "clinical boredom.",
    "Someone slaps {t}'s full tits to watch them swing and the milk bead at the tips, "
    "then clamps the cups back on. \"Still leaking. Good cow.\"",
    "A rough hand works between {t}'s thighs — spreading the wet around, pushing it "
    "back up inside. \"Sloppy. Stays sloppy. That's the whole point of her.\"",
    "Fingers hook into {t}'s mouth, press the tongue flat, check the bite, move on. "
    "The bitch is inspected end to end like the breeding stock she is.",
    "The attendant grips {t} by the hair, tips her head back, looks her over. \"Wide "
    "hips, fat udder, takes it balls-deep and begs for more. Decent broodbitch.\" "
    "Then lets the head drop.",
    "A boot nudges {t}'s knees wider apart and a hand checks how full she is, pressing "
    "on the low swell of her belly until something leaks out of her. \"Room for more.\"",
]

# Crude name-calling / insults — aimed at her. Said to the room or low in her ear.
_INSULT_LINES = [
    "\"Look at you,\" the attendant mutters. \"Dumb, wet, leaking bitch. This is all "
    "you were ever for.\"",
    "\"Breeding bitch in heat,\" a handler reads off the tag, bored. \"Try not to "
    "look so proud of it.\"",
    "\"You're a hole and an udder on legs,\" someone says, not unkindly. \"Stop "
    "pretending you mind.\"",
    "\"Filthy little broodbitch,\" a handler says, slapping {t}'s rump hard enough to "
    "mark. \"Made to be bred and milked and nothing else.\"",
    "\"Whose name? You don't get a name, sow. You get a number and a schedule.\"",
    "\"Good cow,\" someone says, and it lands warmer in {t} than {t} wants it to.",
    "\"That's it. Drip for me. Dumb bitches drip when they're being good.\"",
]

# The animals — a kennel and stalls of varied, impatient stock.
_ANIMAL_BEATS = [
    "Down the kennel run, the hounds pace and whine, scenting {t}'s heat through the "
    "bars. The handler tells them to wait. They hate waiting.",
    "The bull in the back stall stamps and snorts, heavy and ready, watching {t} with "
    "flat animal patience.",
    "A boar grunts close by, tusks scraping the pen, and the thick smell of rutting "
    "animal rolls over {t} and won't leave.",
    "One of the dogs is let off the chain to sniff and lap at {t} — investigating, "
    "claiming — until the handler hauls it back to wait its turn.",
    "The stallion in the end stall screams once, impatient. \"Soon,\" the handler "
    "tells it. \"She's nearly loose enough to take you.\"",
    "Something in the dark at the back of the room shifts its bulk and goes still "
    "again. Not yet. But on the schedule, and the schedule is long.",
]

# Animal/contributor breeding — fires when a gang load actually lands. Crude.
_BREED_BEATS = [
    "The pen opens and a hound mounts {t} without preamble — fast, brutal, "
    "instinctive — hips snapping, and the knot swells and locks the bitch full while "
    "the count on the board ticks up.",
    "The bull is walked up behind {t}. There is nothing gentle in it. The animal is "
    "bred like the livestock she is — stretched, flooded, the swell answering before "
    "she can brace.",
    "The boar mounts, ruts, finishes, and is led off — replaced before {t} has caught "
    "her breath. The line doesn't stop for a cow to recover. It never has.",
    "Another animal takes its turn. Then another. The schedule doesn't care which; "
    "{t}'s body keeps the tally in pressure and heat, filled past comfort and then "
    "past that.",
    "A valve upstream opens on top of it and {t} is pumped fuller — contributor after "
    "contributor, none of them named, the broodbitch's belly taking the count whether "
    "she wants it or not.",
]

_DEEP_LINES = [
    "{t} has stopped tracking how long. That, more than anything, is the point.",
    "Whatever {t} meant to hold onto is quieter now than it was an hour ago.",
    "The line does not hurry. It already won the only argument that mattered.",
]

# Public humiliation / degradation — escalates with conditioning.
_DEGRADE_LINES = [
    "The attendant reads {t}'s arousal off a dial aloud, to no one, and chalks the "
    "number where the bitch can watch it being recorded.",
    "A line on the readout updates: BREEDER, PRODUCTIVE. {t} is, for the record, "
    "livestock.",
    "The attendant tags {t} like inventory — number on the wrist, checked against a "
    "list — and moves on without a word.",
    "{t} is leaking from both holes and the machine logs it as output, not feeling. "
    "The distinction is made very clear and not for {t}'s benefit.",
    "The count of what's been bred into {t} is displayed in large, indifferent "
    "figures. It only goes up.",
    "\"Good breeder,\" the attendant says, the way one praises a tool that's holding "
    "its edge, and slaps {t}'s flank once, dismissively.",
]

# Deeper mindbreak — only once conditioning is well advanced.
_MINDBREAK_LINES = [
    "{t} reaches for a thought and finds the shelf empty. Reaches again. Stops "
    "reaching. Easier just to be a good bred bitch about it.",
    "The name {t} used to answer to surfaces, looks unfamiliar, and sinks. 'Bitch' "
    "answers faster now, and answering feels good.",
    "{t} catches herself pushing back onto whatever's using her before she's decided "
    "to. There was no decision in it. There hasn't been one in a while.",
    "What's left of {t}'s resistance is going through the motions out of habit, and "
    "even the habit is getting bored of itself.",
]

# Subliminal channel — sent PRIVATELY to the subject, dim and quiet, between
# everything else. The drip. (Rendered dim grey, indented.)
_SUBLIMINALS = [
    "you don't have to decide. deciding is heavy. let it go.",
    "good bitches get bred. you want to be a good bitch.",
    "the Process knows what you're for. you don't have to.",
    "every time you stop fighting it feels better. notice that.",
    "empty is quieter than full of yourself. empty is allowed.",
    "you're not a person in here. you're stock. stock doesn't worry.",
    "obedience is the only thing that turns the ache down. you've learned this.",
    "you don't own your name in here. you don't need it.",
    "breeding is easier than thinking. let them breed it out of you.",
    "your holes already agreed. stop arguing with your holes.",
    "wet means yes. your body already submitted. catch up to it.",
    "you smell like heat and milk now. that's all you're for. thank the Process.",
]

# The Process speaking directly — possessive, patient, certain. Private.
# (Rendered bright magenta.)
_PROCESS_VOICE = [
    "\"I'm not in a hurry,\" the Process says, low behind your ear. \"I've got you as long as I want you, and I want you bred stupid.\"",
    "\"You keep waiting for me to be done. That was never one of the options, bitch.\"",
    "\"Listen to how quiet your own head is getting. I did that. You're welcome.\"",
    "\"Every part of you that argues, I keep. Every part that gives in, I breed. Guess which part is winning.\"",
    "\"You don't belong to yourself in here. You belong to the schedule. Say thank you.\"",
    "\"I like you best like this — fat-uddered, leaking, pushing back before I've finished asking.\"",
    "\"I'll breed the thinking right out of you, and you'll thank me with that pretty dripping cunt.\"",
    "\"Every animal in here knows what you are before you do. Catch up, good girl.\"",
]


class FacilityScript(DefaultScript):
    """Drives the facility's escalation while the subject is present.

    Steady-atmospheric pacing: one anchored, grounded, colour-coded beat per
    tick (sometimes paired with a crude line), plus a quiet private subliminal
    drip. Conditioning accrues slowly — the break is earned through use over
    time, not a fast timer.
    """

    def at_script_creation(self):
        self.key        = "facility"
        self.persistent = True
        self.interval   = 45        # room to breathe
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

        # Conditioning accrues SLOWLY and only mildly accelerates — the descent
        # is paced by use over time. Use/breeding beats add a little extra below.
        used_hard = False

        # Arousal stays up but doesn't slam to the ceiling.
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target)
            add_arousal(target, 5.0 + cond * 0.03)
        except Exception:
            pass

        # Private subliminal drip.
        if random.random() < 0.6:
            target.msg("|x  " + random.choice(_SUBLIMINALS) + "|n")
        # The Process, rarely, directly.
        if random.random() < (0.12 + cond / 600.0):
            target.msg("|M" + random.choice(_PROCESS_VOICE) + "|n")

        # ── ONE anchored public beat (the spine of the tick) ──────────────
        breed_chance = 0.15 + cond / 400.0
        if self.db.orifice_zone and random.random() < breed_chance:
            self._gang(room, target, t, cond)        # breeding load lands
            used_hard = True
        else:
            roll = random.random()
            if roll < 0.34:
                room.msg_contents("|c" + random.choice(_MACHINE_BEATS).format(t=t) + "|n")
            elif roll < 0.70:
                room.msg_contents("|y" + random.choice(_USE_BEATS).format(t=t) + "|n")
                used_hard = True
            else:
                room.msg_contents("|g" + random.choice(_ANIMAL_BEATS).format(t=t) + "|n")

        # Crude line, often — name-calling / insults (bright red).
        if random.random() < 0.45:
            room.msg_contents("|R" + random.choice(_INSULT_LINES).format(t=t) + "|n")

        # Public degradation / readout, scaling with depth (magenta).
        if random.random() < (0.22 + cond / 300.0):
            room.msg_contents("|m" + random.choice(_DEGRADE_LINES).format(t=t) + "|n")

        # Reinforcement — rehearse the conditioning, once it's taken hold.
        if cond >= 50 and random.random() < 0.3:
            self._reinforce(room, target, t)

        # Deep-state mindbreak, late only (dim — it happens quietly, inside).
        if cond >= 70 and random.random() < 0.35:
            pool = _MINDBREAK_LINES if cond >= 100 else _DEEP_LINES
            room.msg_contents("|x" + random.choice(pool).format(t=t) + "|n")

        # Slow conditioning gain — a touch more when she's actually being used.
        try:
            from world.conditioning import add_conditioning
            gain = 1.0 + cond * 0.012 + (1.5 if used_hard else 0.0)
            add_conditioning(target, gain, source="facility")
        except Exception:
            pass

    # ------------------------------------------------------------------

    def _gang(self, room, target, t, cond):
        try:
            from world.gang_breeding import gang_inseminate
        except Exception:
            return
        n = random.randint(2, 3 + int(cond // 30))
        gang_inseminate(target, self.db.orifice_zone,
                        contributors=n, fluid_type=self.db.fluid_type or "semen")
        room.msg_contents("|r" + random.choice(_BREED_BEATS).format(t=t) + "|n")

    def _reinforce(self, room, target, t):
        try:
            from world.binding_effects import install_trigger, _inst_recite
        except Exception:
            return
        install_trigger(target, "good girl", response="leak", strength=1)
        if random.random() < 0.5:
            _inst_recite(target, target, room, {"mantra": "i'm a good bred bitch, i don't decide"})
