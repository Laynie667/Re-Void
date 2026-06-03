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

# Animal/contributor breeding — fires when a successful breeding lands. Per species.
_SPECIES_BREED = {
    "hound": [
        "The pen opens and a hound mounts {t} without preamble — fast, brutal, "
        "instinctive — hips snapping, and the knot swells and locks the bitch full "
        "while the board logs another successful breeding.",
        "A hound is loosed and takes {t} from behind in a frenzy, fucking fast and "
        "deep, knotting tight and emptying into her before it's dragged off and the "
        "count ticks up.",
    ],
    "bull": [
        "The bull is walked up behind {t}. There is nothing gentle in it — the animal "
        "breeds her like the livestock she is, stretched and flooded, the swell "
        "answering before she can brace. One more logged against the bull's quota.",
        "The bull mounts, enormous and dull and patient, and breeds {t} in a few "
        "heavy thrusts that leave her dripping and counted.",
    ],
    "boar": [
        "The boar mounts, ruts, and floods {t} with a hot rush, then is led off — "
        "replaced before she's caught her breath. Another against the boar's tally.",
        "The boar's corkscrew prick works into {t} and spills deep, the smell of it "
        "all over her, and the handler marks one more successful breeding.",
    ],
    "stallion": [
        "The stallion is backed up to {t} and breeds her in long brutal strokes, far "
        "too much animal for her to do anything but take it, flagging and flooding "
        "and leaving her gaping and logged.",
        "The stallion mounts with a scream, buries itself in {t}, and empties in "
        "pulses she can feel climb her belly. One more against its quota.",
    ],
    "contributor": [
        "A valve upstream opens and {t} is pumped fuller — contributor after "
        "contributor, none of them named, her belly taking the count whether she "
        "wants it or not.",
        "The reservoir empties into {t} in long measured pulses, anonymous donors "
        "logged but not identified, the contributor count climbing.",
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

    # Phase machine — the facility runs as a repeating cycle. Phases are long
    # and drawn out: one sustained beat per tick, building across the phase.
    _PHASE_ORDER = ["restrain", "milk", "breed", "condition", "rest"]
    _PHASE_LEN   = {"restrain": 3, "milk": 7, "breed": 7, "condition": 5, "rest": 3}

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
              "compliance", "bimbo", "dependence"]

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
