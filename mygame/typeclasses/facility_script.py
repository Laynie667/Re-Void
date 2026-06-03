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
import time
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

# The machine working her body — paragraph-length milking scenes.
_MACHINE_BEATS = [
    "The cups seal over {t}'s nipples with a wet click and the suction starts — not "
    "gentle, never gentle, a deep rhythmic draw that pulls her whole breast into the "
    "cone and then lets it go, again and again, dragging the milk out of her in thin "
    "white streams she can watch spiral down the collection tube. Her nipples are "
    "dragged out long and obscene with every pull, aching, oversensitive, and the "
    "machine doesn't care whether she's empty or not — it keeps milking her past the "
    "point of comfort because a productive animal is milked on schedule, not on mercy, "
    "and the only sound she's allowed to make about it is the wet rhythmic suck of the "
    "rig getting what it's owed.",
    "The rig steps its pace up a notch without asking, the pulls coming faster and "
    "harder, and {t} feels her let-down hit whether she wants it or not — that hot "
    "prickling rush, milk flooding the cups, her body betraying her on the machine's "
    "timetable. She arches into the restraints, helpless, as the suction works her "
    "tits in greedy synchrony, draining her down to aching empty and then keeping right "
    "on going, because the gauge says she's got more and the gauge is the only opinion "
    "that counts in here.",
    "Lower down, the intake arm seated deep in her hums and grinds and works itself a "
    "little deeper, keeping {t} stretched and stuffed and dripping around it while the "
    "cups milk her chest — the machine treating her as one continuous unit, top and "
    "bottom both, draining one end while it fills and works the other, no part of her "
    "left to herself, every hole and gland of her on the same indifferent schedule.",
    "The restraints whir and take up a half-inch of slack, hauling {t} back into the "
    "cradle and tipping her into perfect presentation — spine bowed, tits thrust up "
    "into the waiting cups, hips canted, knees winched apart until everything she has "
    "is offered at exactly the angle the line prefers. She's adjusted like equipment "
    "because that's what she is now, and the cups descend the second she's positioned "
    "right.",
]

# Hands on her — paragraph-length inspection / prodding / use.
_USE_BEATS = [
    "The attendant pulls on a glove with a snap and works two thick fingers up into "
    "{t}'s cunt without ceremony or warning, curling them, spreading them, checking "
    "depth and slick and how readily she grips — and she does grip, helplessly, her "
    "body answering the intrusion before her mind can object. \"Soaked,\" he calls "
    "across the room, like a stock reading, scissoring his fingers wider just to feel "
    "her clench and to watch her face do something she'd rather it didn't. \"Bitch is "
    "ready again. She's always ready. That's the whole point of her.\" He wipes the "
    "glove off on her thigh and moves to the next gauge.",
    "A hand fists in {t}'s hair and tips her head back, and the attendant looks her "
    "over the way you'd appraise a beast at market — thumb dragging her lower lip down "
    "to check her teeth, then down the line of her, weighing one heavy tit in his palm, "
    "rolling a fat nipple until milk beads and her breath stutters. \"Wide hips, full "
    "udder, takes it to the root and pushes back for more,\" he recites to whoever's "
    "logging it. \"Top-grade broodstock.\" He says it like she isn't there, because in "
    "every way that counts to the facility, she isn't.",
    "The attendant spreads {t} open with two gloved fingers and goes after her clit "
    "with a clinical, merciless precision — not to please her, exactly, but to test the "
    "response, rubbing tight fast circles over the swollen nub until she's bucking "
    "against the straps and sobbing and right at the edge, and then he simply stops and "
    "writes the number down. Denied. Logged. \"Good sensitivity,\" he notes, already "
    "reaching for the next instrument while she shakes.",
    "A boot nudges {t}'s knees wider and a broad hand presses flat on the low, tight "
    "swell of her belly, pushing down until a thick rope of what's been pumped into her "
    "leaks back out and runs down her crack. The handler watches it pool, unbothered. "
    "\"Still room,\" he decides, and reaches over to open the next valve, because a "
    "container that isn't completely full is a container that isn't done.",
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

# Animal/contributor breeding — paragraph-length, explicit, per species.
_SPECIES_BREED = {
    "hound": [
        "A handler unlatches the run and a heavy hound is on {t} before the gate's "
        "fully open — forepaws hooking over her hips, claws scrabbling for grip on her "
        "sweat-slick back, the blunt wet point of it already dragging through her folds "
        "and then punching in. It fucks like the animal it is: fast, graceless, brutally "
        "deep, hips jackhammering a pace no person could hold, each thrust knocking a "
        "grunt out of her she never agreed to make. She feels the knot start to swell "
        "against her stretched rim — catching, tugging, then forcing through with an "
        "obscene pop that ties them — and only then does it start to pump, flooding her "
        "in hot pulses with nowhere to go, her belly taking every drop while the board "
        "logs one more breeding to the line.",
        "The hound mounts {t} in a frenzy and rides her hard, snarling against the back "
        "of her neck, its slick red length spearing in to the root over and over until "
        "it slams deep and the knot locks them. She's pinned, stuffed, leaking around "
        "the seal where she can't quite close, and the dog just keeps grinding and "
        "spurting into her, painting her insides while a handler watches the clock and "
        "ticks the count.",
    ],
    "bull": [
        "The bull is walked up behind {t}, all dull-eyed patience and a wall of muscle, "
        "and the handler lines that monstrous flared head up against her cunt and then "
        "lets the animal do what it's for. One heave of its hips and she's split open "
        "around far too much, breath punched flat, hands fisting uselessly in the "
        "restraints — and the bull doesn't care, just breeds the livestock under it in "
        "a few enormous strokes and then floods her with a volume that has her belly "
        "visibly swelling, cum forced back out around the seal of her own stretched "
        "rim. Logged. Counted. The animal is led off before she's stopped shaking.",
        "The bull mounts and ruts into {t} with a brute, mechanical rhythm, balls the "
        "size of fists drawing up, and when it finishes it empties what feels like a "
        "bucket straight into her womb. She's left gaping, dripping, dazed, the gauge "
        "on her belly climbing — one more against the bull's quota, and the quota only "
        "ever climbs to meet it.",
    ],
    "boar": [
        "The boar is grunting before it's even on her, the rank musk of it rolling over "
        "{t} as the handler guides its corkscrew prick to her hole. It screws in — "
        "literally, the spiralled length working deeper with every jerk of its hips — "
        "and then it locks up and unloads, frothy and endless, the strange ridged shape "
        "of it spurting against every wall inside her at once. It rides through its own "
        "orgasm in twitching shoves, fills her past comfort, and is dragged off still "
        "dripping. She's replaced on the schedule before she's caught her breath.",
        "The boar mounts {t} and ruts with single-minded animal greed, tusks scraping "
        "her flank, that obscene twisting cock churning her open and then flooding her "
        "with a hot froth that won't stop coming. The handler marks one more, indifferent.",
    ],
    "stallion": [
        "It takes two handlers to back the stallion up to {t}, and there's a held breath "
        "in the room because everyone knows what's coming. The flared head alone makes "
        "her sob as it spreads her, and then the animal drives in regardless, far too "
        "much for her body to do anything but accept, balls-deep in strokes that lift "
        "her onto her toes. When it flags and comes she can feel it — actual pulses "
        "climbing her belly, jet after jet of it, the stallion emptying itself into her "
        "in a flood that leaves her gaping wide and pouring it back out, ruined and "
        "logged and already due for the next.",
        "The stallion screams once and mounts, and {t} is bred like a mare — that "
        "enormous cock hammering into her, flaring, locking, and then flooding her with "
        "a volume no human hole was built for. It pumps and pumps, her belly rounding "
        "with it, and when it pulls free she's left spread open and leaking a river. "
        "One more against its quota. The bar moves up to meet it.",
    ],
    "contributor": [
        "A valve upstream opens and {t} is simply pumped full — load after anonymous "
        "load routed into her in measured pulses, donor after donor she'll never see, "
        "the reservoir emptying into her cunt and womb until her belly is round and "
        "tight with it and still the count climbs. None of them are named on the board. "
        "She is just the hole they're metered into, and the metering does not stop "
        "because she's full; full is the resting state they want her at.",
        "The intake floods {t} with the collected output of contributors she'll never "
        "meet — thick, anonymous, relentless, pumped in under pressure until it's "
        "backing up out of her and running down her thighs, the tally ticking up with "
        "every pulse while the machine treats her belly as a container to be topped off.",
    ],
}

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

# Experimental dosing / procedures — permanent growth and yield, undocumented.
_DRUG_BEATS = [
    "A line is run into {t}'s arm and something pale-green goes in cold, then warm, then "
    "everywhere. Experimental, the label says — effects not fully documented. That's what "
    "{t} is for. Her tits ache and swell against the cups as it takes.",
    "The attendant injects {t} at the base of each heavy tit, needle sunk deep into the "
    "gland, and pushes a thick serum that has her flesh straining fuller within the minute, "
    "skin tight and hot and leaking before the plunger's even empty.",
    "A procedure cart rolls up and a drape goes around {t}'s hips. Whatever they do to her "
    "cunt and womb behind it, she comes out of it gaping wider, dripping more, and built to "
    "take and hold even more than before.",
    "Two doses today, pumped straight into her: one for yield, one for size. Both permanent, "
    "neither explained. {t}'s body swells to meet them — udder fuller, nipples fatter, the "
    "gauge climbing — whether she follows the science or just feels it happen.",
    "A growth serum is fed directly into {t}'s milk glands through a port sunk under each "
    "areola. It burns, and then it's just heat and pressure and the obscene, steady stretch "
    "of her tits getting bigger on a schedule she doesn't set.",
]

# Contract pressure — said to the room while the contract is unsigned.
_CONTRACT_PRESSURE = [
    "The attendant taps the unsigned contract where {t} can see it. \"Sign, and the "
    "schedule eases. Don't, and it doesn't. We've got nothing but time.\"",
    "\"You'll sign eventually,\" the handler says, sliding the contract closer. "
    "\"They all do. Easier while there's still enough of you left to hold the pen.\"",
    "The contract sits in reach, most of its pages face-down, a line at the bottom "
    "waiting for {t}'s name — or whatever ends up answering to it.",
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
        self.interval   = 180       # a few minutes between beats — drawn out
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

    # Phase machine — the facility runs as a repeating cycle. Phases are long
    # and drawn out: one sustained beat per tick, building across the phase.
    # At ~3 min/tick these lengths make a full cycle roughly 40-45 minutes.
    _PHASE_ORDER = ["restrain", "milk", "breed", "condition", "rest"]
    _PHASE_LEN   = {"restrain": 1, "milk": 4, "breed": 4, "condition": 3, "rest": 2}

    def at_repeat(self):
        room   = self.obj
        target = self._target()
        if not room or not target:
            return   # subject absent — idle, do not escalate

        self.db.ticks = (self.db.ticks or 0) + 1
        t = target.db.rp_name or target.name
        cond = float(getattr(target.db, "conditioning", 0.0) or 0.0)

        phase = self.db.phase or "restrain"
        ptick = int(self.db.phase_tick or 0)

        # Phase opening header — so the cycle is legible.
        if ptick == 0:
            self._phase_header(room, target, t, cond, phase)

        # Arousal stays up; heat keeps it climbing.
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target)
            add_arousal(target, 5.0 + cond * 0.03)
        except Exception:
            pass

        # The phase's own sustained beat (one per tick — drawn out, not rapid).
        self._phase_beat(room, target, t, cond, phase, ptick)

        # Quiet background — a subliminal here, an insult there. Sparse.
        if random.random() < 0.4:
            target.msg("|x  " + random.choice(_SUBLIMINALS) + "|n")
        if phase in ("breed", "restrain") and random.random() < 0.3:
            room.msg_contents("|R" + random.choice(_INSULT_LINES).format(t=t) + "|n")

        # Conditioning accrues — more during breeding and conditioning phases.
        try:
            from world.conditioning import add_conditioning
            bonus = 1.5 if phase in ("breed", "condition") else 0.0
            add_conditioning(target, 1.0 + cond * 0.012 + bonus, source="facility")
        except Exception:
            pass

        # Advance the phase machine.
        ptick += 1
        if ptick >= self._PHASE_LEN.get(phase, 2):
            nxt = self._PHASE_ORDER[(self._PHASE_ORDER.index(phase) + 1) % len(self._PHASE_ORDER)]
            self.db.phase = nxt
            self.db.phase_tick = 0
            if nxt == "restrain":
                self.db.cycle_count = int(self.db.cycle_count or 0) + 1
        else:
            self.db.phase_tick = ptick

    # ------------------------------------------------------------------

    def _phase_header(self, room, target, t, cond, phase):
        cyc = int(self.db.cycle_count or 0) + 1
        if phase == "restrain":
            room.msg_contents(
                f"\n|w━━━━ CYCLE {cyc} · INTAKE ━━━━|n\n"
                f"|cThe restraints draw {t} back into the station with a hydraulic sigh — "
                f"chest hauled up into the cups, hips tipped, knees forced wide. Presented, "
                f"opened, locked down. The cycle starts again whether she's ready or not.|n")
        elif phase == "milk":
            room.msg_contents(
                f"\n|w━━━━ MILKING ━━━━|n\n"
                f"|cThe rig descends onto {t}'s tits and seals. The draw begins — slow, "
                f"deep, metronomic — and won't stop until the phase does.|n")
        elif phase == "breed":
            room.msg_contents(
                f"\n|w━━━━ BREEDING ━━━━|n\n"
                f"|rThe pens unlatch down the wall. The board lists what's owed. It's {t}'s "
                f"turn to be bred, on the schedule, to the count.|n")
        elif phase == "condition":
            room.msg_contents(
                f"\n|w━━━━ CONDITIONING ━━━━|n\n"
                f"|MThe lights dim to a single band. The voice starts up close. This is the "
                f"part where {t} gets a little quieter inside than she was last cycle.|n")
        elif phase == "rest":
            room.msg_contents(
                f"\n|w━━━━ PAUSE ━━━━|n\n"
                f"|xThe line stops. Not finished — the line is never finished. Just paused, "
                f"long enough for {t} to feel how little of the pause is hers.|n")

    def _phase_beat(self, room, target, t, cond, phase, ptick):
        if phase == "restrain":
            # Intake sometimes means a permanent procedure done to her on the table.
            if random.random() < 0.5:
                self._procedure(room, target, t)
            else:
                room.msg_contents("|y" + random.choice(_USE_BEATS).format(t=t) + "|n")

        elif phase == "milk":
            # Mid-phase, the dosing/procedure goes in — permanent, varied, real.
            if ptick == self._PHASE_LEN["milk"] // 2:
                self._dose(room, target, t)
            else:
                room.msg_contents("|c" + random.choice(_MACHINE_BEATS).format(t=t) + "|n")
                self._log_milk(target)

        elif phase == "breed":
            if self.db.orifice_zone:
                self._gang(room, target, t, cond)
            else:
                room.msg_contents("|g" + random.choice(_ANIMAL_BEATS).format(t=t) + "|n")
            if getattr(target.db, "facility_signed", False) and random.random() < 0.5:
                try:
                    from world.compliance import register_compliance
                    register_compliance(target)
                except Exception:
                    pass

        elif phase == "condition":
            # One sustained conditioning beat per tick.
            r = random.random()
            if r < 0.35:
                target.msg("|M" + random.choice(_PROCESS_VOICE) + "|n")
            elif r < 0.6 and cond >= 40:
                self._reinforce(room, target, t)
            elif r < 0.85:
                room.msg_contents("|m" + random.choice(_DEGRADE_LINES).format(t=t) + "|n")
            elif cond >= 70:
                pool = _MINDBREAK_LINES if cond >= 100 else _DEEP_LINES
                room.msg_contents("|x" + random.choice(pool).format(t=t) + "|n")
            else:
                target.msg("|x  " + random.choice(_SUBLIMINALS) + "|n")

        elif phase == "rest":
            # Withdrawal bites in the pauses once she's been made dependent.
            dep = int(getattr(target.db, "drug_dependence", 0) or 0)
            if dep and random.random() < min(0.7, 0.2 + dep * 0.1):
                try:
                    from typeclasses.arousal_script import add_arousal, ensure_arousal_script
                    ensure_arousal_script(target); add_arousal(target, 10.0 + dep * 2)
                except Exception:
                    pass
                target.msg(
                    "|G  the pause is the worst part now — your body claws for the next dose, "
                    "the craving louder than any thought, and you'd take anything to make it "
                    "the milk phase again.|n")
            contract = self._contract()
            signed = getattr(target.db, "facility_signed", False) or (contract and contract.db.signed)
            if contract is not None and not signed:
                room.msg_contents("|m" + random.choice(_CONTRACT_PRESSURE).format(t=t) + "|n")
            elif signed:
                # Quota review + the board, once per pause.
                try:
                    from world.compliance import penalize_quota_shortfall
                    penalize_quota_shortfall(target)
                except Exception:
                    pass
                if getattr(target.db, "breeding_quota", None):
                    target.msg("|m" + self._quota_board(target) + "|n")
                if int(self.db.cycle_count or 0) % 3 == 0 and contract is not None:
                    self._addendum(contract, target, t)

    # ------------------------------------------------------------------

    # Experimental drug menu — each dose applies one or two of these. All real,
    # all permanent (cleared only by the reset). Effects are deliberately mixed.
    _DRUGS = ["swell", "yield", "sensitize", "capacity", "brood",
              "compliance", "bimbo", "dependence", "estrus", "lactation", "solvent"]
    _PROCEDURES = ["pierce", "brand", "stim_implant", "ring_fit", "milk_port",
                   "tail", "fertility_implant", "tongue"]

    def _dose(self, room, target, t):
        room.msg_contents("|G" + random.choice(_DRUG_BEATS).format(t=t) + "|n")
        for drug in random.sample(self._DRUGS, k=random.randint(1, 2)):
            try:
                getattr(self, f"_drug_{drug}")(room, target, t)
            except Exception:
                pass

    def _boost_bodymods(self, target, amount):
        from evennia import search_object
        from typeclasses.body_mod_item import BodyModItem
        n = 0
        for zd in (getattr(target.db, "zones", None) or {}).values():
            bm = ((zd or {}).get("mechanics", {}) or {}).get("body_mod")
            if bm:
                res = search_object(bm.get("item_dbref", ""), exact=True)
                if res and isinstance(res[0], BodyModItem):
                    try: res[0].apply_permanent_boost(amount); n += 1
                    except Exception: pass
        return n

    def _boost_production(self, target, amount):
        from evennia import search_object
        from typeclasses.production_item import ProductionItem
        n = 0
        for zd in (getattr(target.db, "zones", None) or {}).values():
            pr = ((zd or {}).get("mechanics", {}) or {}).get("production")
            if pr:
                res = search_object(pr.get("item_dbref", ""), exact=True)
                if res and isinstance(res[0], ProductionItem):
                    try:
                        old = res[0].db.base_rate_ml_per_tick or 8.0
                        res[0].db.base_rate_ml_per_tick = old + amount; n += 1
                    except Exception: pass
        return n

    # ── the drugs ──
    def _drug_swell(self, room, target, t):
        amt = round(random.uniform(0.15, 0.30), 2)
        self._boost_bodymods(target, amt)
        room.msg_contents(
            f"|G  ▸ SWELL SERUM — {t}'s flesh strains and grows: tits fuller, heavier, "
            f"the skin tight and hot. (+{amt} size, permanent)|n")

    def _drug_yield(self, room, target, t):
        self._boost_production(target, 3.0)
        room.msg_contents(
            f"|G  ▸ YIELD COMPOUND — {t}'s glands let down faster and fuller than her body "
            f"wants to, milk beading before the cups even seal. (+production, permanent)|n")

    def _drug_sensitize(self, room, target, t):
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 50.0)
        target.db.stim_per_tick = float(getattr(target.db, 'stim_per_tick', 0) or 0) + 2.0
        room.msg_contents(
            f"|G  ▸ RAW-NERVE AGENT — every nerve in {t} turns up past comfort. Air, fabric, "
            f"breath all read as too much, and the ache never fully backs off. (sensitivity up)|n")

    def _drug_capacity(self, room, target, t):
        from evennia import search_object
        try:
            from typeclasses.inflation_item import InflationItem
        except Exception:
            return
        raised = False
        for zd in (getattr(target.db, "zones", None) or {}).values():
            inf = ((zd or {}).get("mechanics", {}) or {}).get("inflation")
            if inf:
                res = search_object(inf.get("item_dbref", ""), exact=True)
                if res:
                    try:
                        res[0].db.max_volume_ml = float(res[0].db.max_volume_ml or 1000.0) + 1500.0
                        raised = True
                    except Exception: pass
        room.msg_contents(
            f"|G  ▸ CAPACITY EXPANDER — {t} is remade to hold more without complaint. Her "
            f"limits move; the fill stops mattering long after it used to.|n")

    def _drug_brood(self, room, target, t):
        prog = dict(getattr(target.db, "offspring_progress", None) or {})
        for sp in ("hound", "bull", "boar", "stallion"):
            prog[sp] = int(prog.get(sp, 0)) + random.randint(1, 3)
        target.db.offspring_progress = prog
        room.msg_contents(
            f"|G  ▸ BROOD ACCELERANT — {t}'s womb is hurried along; whatever's rooted in her "
            f"comes due sooner and takes faster. (fertility up — get drops sooner)|n")

    def _drug_compliance(self, room, target, t):
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, random.uniform(8, 15), source="drug")
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ COMPLIANCE COMPOUND — something in {t} goes soft and agreeable. The part "
            f"that argued gets quieter, and stays quieter. (conditioning deepened)|n")

    def _drug_bimbo(self, room, target, t):
        filters = list(getattr(target.db, "active_speech_filters", None) or [])
        if "baby_talk" not in filters:
            filters.append("baby_talk"); target.db.active_speech_filters = filters
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 5.0, source="drug")
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ BIMBO DRAUGHT — {t}'s thoughts go round and pink and slow, and her mouth "
            f"follows them down. (speech softened, conditioning up)|n")

    def _drug_dependence(self, room, target, t):
        dep = int(getattr(target.db, "drug_dependence", 0) or 0) + 1
        target.db.drug_dependence = dep
        room.msg_contents(
            f"|G  ▸ DEPENDENCE DOSE — {t}'s body learns to need the next one. Between doses "
            f"now there's a craving, and the craving has its own leash. (dependence {dep})|n")

    def _drug_estrus(self, room, target, t):
        target.db.perpetual_heat = True
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 60.0)
        try:
            from typeclasses.heat_script import HeatScript
            if not any(isinstance(s, HeatScript) or getattr(s, "key", "") == "perpetual_heat"
                       for s in target.scripts.all()):
                from evennia.utils import create
                create.create_script(HeatScript, obj=target, persistent=True, autostart=True)
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ ESTRUS LOCK — {t} is forced into a permanent rut, dripping and aching and "
            f"presenting at anything that moves. Her heat never breaks now. (perpetual heat, deepened)|n")

    def _drug_lactation(self, room, target, t):
        self._boost_production(target, 5.0)
        target.db.lactation_locked = True
        room.msg_contents(
            f"|G  ▸ LACTATION OVERRIDE — {t}'s tits are switched permanently on; she'll make "
            f"milk whether she's milked or not, leaking and swelling and aching to be drained. "
            f"(production way up, can't switch off)|n")

    def _drug_solvent(self, room, target, t):
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, random.uniform(12, 20), source="drug")
            from world.binding_effects import install_trigger
            install_trigger(target, random.choice(["good girl", "empty", "breed"]),
                            response=random.choice(["blank", "leak", "kneel"]),
                            strength=2, permanent=True)
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ PERSONALITY SOLVENT — something dissolves a little more of whoever {t} "
            f"used to be and leaves room for whatever the facility writes in its place. "
            f"(deep conditioning + a trigger set)|n")

    # ── Procedures (intake phase) — surgical/permanent, with a lasting mark ──
    def _mark(self, target, text):
        marks = list(getattr(target.db, "facility_brands", None) or [])
        marks.append(text)
        target.db.facility_brands = marks

    def _procedure(self, room, target, t):
        name = random.choice(self._PROCEDURES)
        try:
            getattr(self, f"_proc_{name}")(room, target, t)
        except Exception:
            pass

    def _proc_pierce(self, room, target, t):
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 45.0)
        target.db.stim_per_tick = float(getattr(target.db, 'stim_per_tick', 0) or 0) + 1.5
        self._mark(target, "heavy rings pierced through both nipples, clit hood, and cunt — permanent")
        room.msg_contents(
            f"|GA tray of needles is wheeled to {t}'s station and they pierce her without "
            f"anaesthetic — both nipples, the hood of her clit, the rim of her cunt — threading "
            f"thick steel rings through each fresh hole and tugging to seat them. Everything is "
            f"louder now: every pull of the cups, every drip down her thighs, sings through the "
            f"new metal. (permanent piercings — sensitivity up)|n")

    def _proc_brand(self, room, target, t):
        spot = random.choice(["one hip", "the swell of her ass", "her lower belly, over the womb"])
        self._mark(target, f"a facility ownership brand seared into {spot} — permanent")
        room.msg_contents(
            f"|GA brand is drawn glowing from the coals and pressed to {spot} — a hiss, the smell "
            f"of it, a scream {t} bites down on — and then a mark of ownership burned into her for "
            f"good, set where she'll see it every time she's bent over and used. (permanent brand)|n")

    def _proc_stim_implant(self, room, target, t):
        target.db.stim_per_tick = float(getattr(target.db, 'stim_per_tick', 0) or 0) + 3.0
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 50.0)
        self._mark(target, "a stimulation implant seated at the base of her spine — permanent, can't be dug out")
        room.msg_contents(
            f"|GA small device is implanted under the skin at the base of {t}'s spine and switched "
            f"on — a constant low buzz wired straight into her nerves, never off, that she'll feel "
            f"every second of the term and can't reach to remove. (permanent implant — constant stim)|n")

    def _proc_ring_fit(self, room, target, t):
        target.db.cum_receptacle = True
        self._drug_capacity(room, target, t)  # also raises inflation max
        self._mark(target, "steel gauging rings fitted in cunt and ass, holding her permanently open")
        room.msg_contents(
            f"|GThey fit {t}'s holes with steel — a wide gauging ring worked into her cunt and "
            f"another into her ass, cranked open notch by notch and locked there, propping her "
            f"permanently gaping and slack so nothing ever has to work to get into her again. "
            f"(permanently fitted open)|n")

    def _proc_milk_port(self, room, target, t):
        self._boost_production(target, 4.0)
        self._mark(target, "surgical milk ports set under each areola — permanent")
        room.msg_contents(
            f"|GA milking port is surgically set under each of {t}'s areolae — clean valves her "
            f"body is re-plumbed around, that she'll leak from on command for the rest of the term. "
            f"(permanent — production up)|n")

    def _proc_tail(self, room, target, t):
        target.db.pet_type = target.db.pet_type or "puppy"
        self._mark(target, "a locked tail-plug and pinned ears — kept as livestock in form, not just function")
        room.msg_contents(
            f"|GA thick plug with a tail is seated deep in {t}'s ass and locked there, and a "
            f"matching set of ears is pinned into her hair. On the record she's livestock now in "
            f"form as well as function, and she moves like it before the cycle's out. (pet imprint)|n")

    def _proc_fertility_implant(self, room, target, t):
        prog = dict(getattr(target.db, "offspring_progress", None) or {})
        for sp in ("hound", "bull", "boar", "stallion"):
            prog[sp] = int(prog.get(sp, 0)) + 2
        target.db.offspring_progress = prog
        self._mark(target, "a fertility implant seated in her cervix — tuned for breeding")
        room.msg_contents(
            f"|GA fertility implant is pushed up through {t}'s cervix and seated, flooding her "
            f"with whatever makes a body take faster and drop sooner. She's tuned for one output "
            f"now, and her own get will come due that much quicker. (fertility up)|n")

    def _proc_tongue(self, room, target, t):
        filters = list(getattr(target.db, "active_speech_filters", None) or [])
        for f in ("baby_talk", "animal_sounds"):
            if f not in filters:
                filters.append(f)
        target.db.active_speech_filters = filters
        self._mark(target, "tongue 'trained' — mouth reshaped for sounds, not words")
        room.msg_contents(
            f"|G{t}'s tongue is clamped out and worked over with a device they call training — and "
            f"afterward her mouth is shaped for sounds rather than words, the language drained out "
            f"of her a little more. (speech filtered)|n")

    def _gang(self, room, target, t, cond):
        try:
            from world.gang_breeding import gang_inseminate
        except Exception:
            return
        # Pick which kind is breeding her — prefer species still short of quota.
        species = self._pick_species(target)
        n = random.randint(2, 3 + int(cond // 30))
        gang_inseminate(target, self.db.orifice_zone, contributors=n,
                        fluid_type=self.db.fluid_type or "semen", species=species)

        # If her own grown get of this line is on the roster, sometimes IT breeds her.
        offspring = [o for o in room.contents
                     if getattr(o.db, "is_offspring", False)
                     and getattr(o.db, "species", None) == species]
        if offspring and random.random() < 0.4:
            ob = random.choice(offspring)
            gen = int(getattr(ob.db, "generation", 1) or 1)
            # Steep penalty: her own get breeding her inflates the very quota it
            # serves — and steeper the deeper the generation.
            penalty = 0
            q = getattr(target.db, "breeding_quota", None)
            if q and species in q:
                penalty = random.randint(4, 9) + (gen - 1) * 3
                e = dict(q[species]); e["required"] = int(e.get("required", 0)) + penalty
                q[species] = e
                target.db.breeding_quota = q
            # And it can get her with the NEXT generation.
            try:
                from world.gang_breeding import maybe_lineage_offspring
                maybe_lineage_offspring(target, species, gen)
            except Exception:
                pass
            room.msg_contents(
                f"|r{ob.key} — {t}'s own get by the {species} line — mounts the bitch that "
                f"bore it and breeds her in turn. The roster has closed its loop... and the "
                f"{species} quota climbs by {penalty} for it. The loop doesn't just grow — "
                f"it moves the finish line further every time it turns.|n"
            )
        else:
            pool = _SPECIES_BREED.get(species, _SPECIES_BREED["contributor"])
            room.msg_contents("|r" + random.choice(pool).format(t=t) + "|n")

    def _addendum(self, contract, target, t):
        """Clause 11: the facility amends the contract with new hidden pages."""
        choice = random.choice(["quota", "trigger", "extend"])
        if choice == "quota":
            q = getattr(target.db, "breeding_quota", None)
            if q:
                sp = random.choice(list(q.keys()))
                e = dict(q[sp]); e["required"] = int(e.get("required", 0)) + random.randint(3, 8)
                q[sp] = e; target.db.breeding_quota = q
                contract.add_addendum(
                    f"The {sp} quota is increased at the facility's discretion.", hidden=True)
        elif choice == "trigger":
            try:
                from world.binding_effects import install_trigger
                phrase = random.choice(["heel", "spread", "leak for me", "good breeder", "down, bitch"])
                resp   = random.choice(["kneel", "leak", "blank"])
                install_trigger(target, phrase, response=resp, strength=2, permanent=True)
            except Exception:
                pass
            contract.add_addendum(
                "A new conditioned response is installed in the Resident.", hidden=True)
        else:
            locked = float(getattr(target.db, "facility_reset_locked_until", 0) or 0)
            if locked > time.time():
                target.db.facility_reset_locked_until = locked + 12 * 3600.0
            contract.add_addendum("The term of processing is extended.", hidden=True)
        room = self.obj
        if room:
            room.msg_contents(
                f"|mThe contract gains a page. {t} doesn't get to read this one either — "
                f"clause 11 saw to that. Whatever it says, it's already true.|n")

    def _pick_species(self, target):
        quota = getattr(target.db, "breeding_quota", None)
        species = ["hound", "bull", "boar", "stallion", "contributor"]
        if quota:
            unmet = [s for s in species
                     if s in quota and int(quota[s].get("current", 0)) < int(quota[s].get("required", 0))]
            if unmet:
                return random.choice(unmet)
        return random.choice(species)

    def _contract(self):
        cdbref = self.db.contract_dbref
        if not cdbref:
            return None
        try:
            from evennia import search_object
            res = search_object(cdbref, exact=True)
            return res[0] if res else None
        except Exception:
            return None

    def _log_milk(self, target):
        mq = getattr(target.db, "milk_quota", None)
        if mq and random.random() < 0.5:
            e = dict(mq); e["current"] = int(e.get("current", 0)) + 1
            target.db.milk_quota = e

    def _quota_board(self, target):
        parts = []
        try:
            from world.gang_breeding import summarize_quota
            b = summarize_quota(target)
            if b:
                parts.append(b)
        except Exception:
            pass
        mq = getattr(target.db, "milk_quota", None)
        if mq:
            cur = int(mq.get("current", 0)); req = int(mq.get("required", 0))
            done = "|gMET|n" if cur >= req else "|rNOT MET|n"
            parts.append(f"|wMILK QUOTA:|n  {cur}/{req} bottles   {done}")
        if getattr(target.db, "freedom_forfeited", False):
            parts.append("|RFREEDOM:  FORFEITED|n")
        return "\n".join(parts)

    def _reinforce(self, room, target, t):
        try:
            from world.binding_effects import install_trigger, _inst_recite
        except Exception:
            return
        install_trigger(target, "good girl", response="leak", strength=1)
        if random.random() < 0.5:
            _inst_recite(target, target, room, {"mantra": "i'm a good bred bitch, i don't decide"})
