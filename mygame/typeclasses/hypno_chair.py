"""
typeclasses/hypno_chair.py

The Spiral Chair — Bethany's conditioning rig for the Cell. A real furniture device
(FurnitureSessionScript pattern, like the rocking horse and the little box) that runs a
staged hypnotic induction on whoever sits in it: settle → spiral → drone → deep → set.

Every stage is REAL: conditioning ticks (world.conditioning), suggestibility climbs, deep
stages seat actual installed triggers and (if she's drifting that way) regression. Mid-trance
the chair poses a CYOA choice — repeat the mantra or hold your tongue — and both answers cost
something, because that's how Bethany builds furniture.

NOT a stuck-spot, ever:
  * the session timer ALWAYS releases (`chair_release_at`, default ~420s);
  * `hypnorise` works — when she's deep the spiral drags her back once or twice
    (a struggle meter, like the box lid) and then lets go;
  * leaving the room / disconnecting auto-releases; the §0 floor clears every flag
    (all in FACILITY_FLAGS). The chair gates only its own verb, never navigation.

Build: `build_hypno_chair(room, "spiral_chair")` — installed in the Conditioning Cell by
build_realm/_furnish and by facility_upgrade. Commands: hypnosit / hypnorise (+ status).

Char state (all FACILITY_FLAGS):
    char.db.in_hypno_chair    zone name (None = not seated)
    char.db.chair_stage       0..4 induction depth this session
    char.db.chair_beats       beats this session
    char.db.chair_release_at  time.time() the timer springs her loose
    char.db.chair_struggle    progress toward surfacing on her own when deep
"""

import time
import random

from typeclasses.furniture_session import FurnitureSessionScript

_CHAIR_SESSION_S   = 420.0   # the timer that always frees her
_CHAIR_STRUGGLE_AT = 2.0     # hypnorise attempts to surface from deep
_DEEP_STAGE        = 3       # at/after this stage the spiral resists rising (gently)

# ── Stage prose — the chair speaks with Bethany's recorded voice ──────────────
# stage -> pool. Private to the sitter; the room sees a short third-person line.
_STAGE_POOLS = {
    0: [  # settle
        "The chair takes your weight like it was measured for you, because it was — the file "
        "has your numbers. The restraints don't close. They don't need to. The headrest tips "
        "your eyes to the spiral on the ceiling, and Bethany's recorded voice arrives warm by "
        "your ear: |M\"There you are, sweetheart. Sit. Watch. I had this made for you — well. "
        "For what you're becoming. Same thing now.\"|n",
        "It's comfortable. That's the first wrong thing — the Cell is never comfortable, but the "
        "chair is, deliberately, so your body files it under *safe* before your head can object. "
        "The spiral overhead begins its slow turn. |M\"No rush,\"|n murmurs Bethany's voice from "
        "the headrest, fond as a bedtime. |M\"We have your whole self to get through.\"|n",
    ],
    1: [  # spiral
        "The spiral turns and your eyes follow it, then stop following and just ride — that's "
        "the trick of it, the moment watching becomes being-carried. |M\"Good girl. Don't blink "
        "more than you must,\"|n says the warm recording. |M\"Every turn takes a little argument "
        "with it. You won't miss them. You never use the good ones on me anyway.\"|n",
        "You realise you've stopped hearing the Cell — the drone, the vents — because the spiral "
        "has a sound now, or your head's given it one, a soft falling note that goes down and "
        "down and never lands. Bethany's voice rides it: |M\"That's the way. Heavy and easy. "
        "You're so much sweeter with your thoughts taken in at the waist.\"|n",
    ],
    2: [  # drone
        "The voice has stopped being beside you and started being *in* you — under the breastbone, "
        "behind the eyes, paced exactly to your pulse because the chair is reading your pulse. "
        "|M\"Listen to how quiet you're getting,\"|n it says, delighted. |M\"I'm going to put a "
        "few things in while there's room. You'll keep them warm for me, won't you. Of course "
        "you will. You keep everything I give you.\"|n",
        "Somewhere very far up, your body is sitting in a chair. Down here there's only the turn "
        "and the warm bureaucratic murmur sorting through you like a filing drawer — keep, keep, "
        "*soften*, keep, |M\"oh, we won't be needing that one at all,\"|n — and you can't tell "
        "which of your edges just went, only that the room got simpler.",
    ],
    3: [  # deep
        "Deep now. The spiral isn't above you anymore; it's the shape your thinking makes. "
        "Bethany's voice writes on you the way a finger writes on a fogged window — effortless, "
        "and legible only from the outside. |M\"There's my open little book. Let's add a page "
        "you'll find in your mouth later and wonder how it got there.\"|n Something settles in. "
        "It fits. That's the worst part — it *fits*.",
        "You go to think your own name and the spiral lends you a different word, helpfully, the "
        "way the chair does everything — helpfully. |M\"Shh. You can have it back after,\"|n the "
        "recording soothes, and means it, mostly, probably. |M\"Though you do keep leaving it "
        "here. I think part of you wants me to hold it. I think part of you is right.\"|n",
    ],
    4: [  # set
        "And then the click — the soft, sourceless click of something being decided and closed. "
        "|M\"Set,\"|n says Bethany's voice, satisfied as a ledger balancing. |M\"You'll surface "
        "in a moment, sweetheart, and you'll feel *wonderful*, and you won't be quite sure why, "
        "and that's mine too — I keep the why. Up you come now. Good girl. My good girl.\"|n",
    ],
}

_ROOM_LINES = [
    "|x{t} sits glazed and slack in the spiral chair, eyes tracking the slow turn overhead, lips "
    "moving now and then around words that aren't hers.|n",
    "|xThe spiral chair hums through another pass; {t} sinks visibly deeper into it, breathing "
    "in time with a recorded murmur too soft for anyone else to follow.|n",
]

_RELEASE_TIMER = [
    "The spiral slows, and slows, and stops, and the chair tips you gently upright like a "
    "hostess seeing a guest to the door. You feel rested. You feel *lovely*. Somewhere under "
    "the lovely is the suspicion of new furniture in your head, arranged while you were out — "
    "but the suspicion is small, and the lovely is large, and that ratio was the whole point.",
]
_RELEASE_STRUGGLE = [
    "You claw up through the warm — once, twice — and surface on your own, blinking hard, the "
    "spiral's afterimage still turning on everything you look at. The recording doesn't object. "
    "|M\"Of course, sweetheart,\"|n it says, unbothered, already powering down. |M\"The door was "
    "never locked. It just gets harder to want.\"|n",
]
_STRUGGLE_FAIL = [
    "You try to stand and the spiral leans on you — not hands, nothing so crude, just the warm "
    "enormous suggestion that *down* is where you live now. You sag back. But you felt it give: "
    "try again, it's loosening. (Or the session ends on its own — it always does.)",
]


def build_hypno_chair(room, zone="spiral_chair"):
    """Install the Spiral Chair on a room. The session script spawns on first sit."""
    if not room:
        return False
    room.db.hypno_chair_zone = zone
    try:
        room.tags.add("hypno_chair", category="furniture")
    except Exception:
        pass
    return True


class HypnoChairScript(FurnitureSessionScript):
    """Drives an active spiral-chair session: staged induction, real conditioning, the
    mid-trance mantra choice, and guaranteed self-release."""

    furniture_key = "hypno_chair"
    zone_attr     = "hypno_chair_zone"
    label         = "Spiral Chair"
    verbs         = ["hypnosit / hypnorise"]
    empty_grace   = 2

    def at_script_creation(self):
        super().at_script_creation()
        self.interval = 45

    def occupants(self, room=None, zone=None):
        room = room or self.obj
        if not room:
            return
        if zone is None:
            zone = self.zone_name()
        if not zone:
            return
        from typeclasses.characters import Character
        for char in room.contents:
            if isinstance(char, Character) and getattr(char.db, "in_hypno_chair", None) == zone:
                yield char

    def at_repeat(self):
        room = self.obj
        if not room:
            return
        zone = self.zone_name()
        occ = list(self.occupants(room, zone))
        if self.note_occupancy(bool(occ)):
            return
        now = time.time()
        for char in occ:
            try:
                if char.sessions.count() == 0:
                    self.release(char, room, reason="gone")
                    continue
            except Exception:
                pass
            if now >= float(getattr(char.db, "chair_release_at", 0.0) or 0.0):
                self.release(char, room, reason="timer")
                continue
            self._trance_beat(char, room)

    def _trance_beat(self, char, room):
        """One beat of the induction: stage prose + the real effects of that depth."""
        stage = int(getattr(char.db, "chair_stage", 0) or 0)
        beats = int(getattr(char.db, "chair_beats", 0) or 0) + 1
        char.db.chair_beats = beats
        # advance a stage every other beat, capped at 'set'
        if beats % 2 == 0 and stage < 4:
            stage += 1
            char.db.chair_stage = stage
        char.msg("|x  " + random.choice(_STAGE_POOLS.get(stage, _STAGE_POOLS[0])) + "|n")
        if room and random.random() < 0.4:
            t = char.db.rp_name or char.name
            room.msg_contents(random.choice(_ROOM_LINES).format(t=t), exclude=[char])
        # Real effects scale with depth.
        try:
            from world.conditioning import add_conditioning
            add_conditioning(char, 1.5 + stage * 1.2, source="spiral_chair")
        except Exception:
            pass
        try:
            char.db.suggestibility = float(getattr(char.db, "suggestibility", 0) or 0) + 0.4
        except Exception:
            pass
        if stage >= _DEEP_STAGE:
            # deep stages seat real work: a trigger, or (if she's slipping) regression
            if random.random() < 0.4:
                try:
                    from world.binding_effects import install_trigger
                    phrase, resp = random.choice([
                        ("good girl", "leak"), ("empty", "blank"), ("spiral down", "blank"),
                        ("settle", "kneel"),
                    ])
                    install_trigger(char, phrase, response=resp, strength=1)
                except Exception:
                    pass
            if getattr(char.db, "headspace", None) or random.random() < 0.25:
                try:
                    from world.regression import regress
                    regress(char, random.uniform(2.0, 4.0), source="spiral_chair")
                except Exception:
                    pass
        # Mid-trance, the chair poses the mantra choice (CYOA) if nothing's pending.
        if stage >= 2 and random.random() < 0.35:
            try:
                from world import cyoa
                if not cyoa.has_pending(char):
                    cyoa.pose_named(char, "mantra", room=room)
            except Exception:
                pass

    def release(self, char, room, reason="timer"):
        """Free the sitter and clear session state. Always available; floor-safe."""
        char.db.in_hypno_chair  = None
        char.db.chair_stage     = 0
        char.db.chair_beats     = 0
        char.db.chair_release_at = 0.0
        char.db.chair_struggle  = 0.0
        if reason == "timer":
            char.msg("|w  " + random.choice(_RELEASE_TIMER) + "|n")
        elif reason == "struggle":
            char.msg("|w  " + random.choice(_RELEASE_STRUGGLE) + "|n")
        if room and not list(self.occupants(room)):
            try:
                self.stop()
            except Exception:
                pass

    def at_stop(self):
        room = self.obj
        if not room:
            return
        from typeclasses.characters import Character
        zone = self.zone_name()
        for char in room.contents:
            if isinstance(char, Character) and getattr(char.db, "in_hypno_chair", None) == zone:
                char.db.in_hypno_chair = None
                char.db.chair_stage = 0
                char.db.chair_struggle = 0.0
                char.db.chair_release_at = 0.0
