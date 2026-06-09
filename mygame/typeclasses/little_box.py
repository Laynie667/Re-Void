"""
typeclasses/little_box.py

LittleBoxScript — a "toybox / playpen" furniture that keeps its occupant little.

The storage counterpart to the rocking horse's cradle: the horse rocks you down, the
box keeps you down. While you're in it, it ticks the real regression meter
(world.regression), murmurs caretaker beats, and now and then feeds you a laced bottle.
Once you're little enough the lid "locks" — but the box is NOT a stuck-spot:

  * It ALWAYS lets you out on its own. A nap timer (room.db.box_nap_seconds, default
    360s) springs the latch no matter what — you never wait on another person.
  * You can also work the latch yourself: repeated `boxout` fills a small struggle
    meter that pops the lid solo. `boxout`/`boxstatus` always show the remaining time
    and your struggle progress, so it's never opaque.
  * Walking out of the room, disconnecting, or the OOC floor all release you too.
  * It NEVER locks navigation and NEVER gates the §0 floor — the lid only gates the
    `boxout` command, exactly like the rocking horse's knot only gates `horsedismount`.

The dread is "you don't choose WHEN you come out, and you come out littler" — never
"you might never come out." Build with build_little_box(room, "playpen").

Char state (all in FACILITY_FLAGS → both reset paths + force_clear/escape clear them):
    char.db.in_box           zone name the char is contained in (None = not in a box)
    char.db.box_entered_at   time.time() of entry
    char.db.box_release_at   time.time() the nap-timer springs the lid
    char.db.box_lid_locked   bool — lid has locked (still self-releases)
    char.db.box_struggle     float — progress toward wiggling out yourself
"""

import time
import random

from typeclasses.furniture_session import FurnitureSessionScript

# Once regression climbs past this, the lid locks (self-releasing — see module docstring).
_BOX_LOCK_REGRESSION = 45.0
# Default nap length before the timer springs the lid no matter what (seconds).
_BOX_NAP_SECONDS_DEFAULT = 360.0
# Struggle points needed to pop the lid yourself; each `boxout` attempt adds ~1.
_BOX_STRUGGLE_OUT = 3.0


# Soft, filthy-sweet caretaker beats — the box keeping you, talking you down, feeding you.
_BOX_BEATS = [
    "The padded walls of the box are close and warm on every side, and the soft voice in "
    "them never stops: |i'good little thing, settle down, settle in, no big girl gets to "
    "be this safe.'|n You settle. You can't help it. It's so much smaller in here, and "
    "smaller feels so good.",
    "Something soft nudges at your mouth until you take it — a fat rubber teat — and the "
    "box praises you, warm and certain, when you start to suck. |i'There she is. Good "
    "babies don't need their hands. Good babies just need their box.'|n",
    "You curl up tighter without deciding to, knees to your chest, made small to fit the "
    "small space, and the box croons how perfect you look folded down to nothing — how "
    "much easier you are to keep when you're this size, this quiet, this little.",
    "The voice tells you a secret in a sing-song hush: |i'big girls have to get up and do "
    "things. little ones get put away clean and warm and don't have to do anything at "
    "all.'|n And the not-having-to wraps around you like the padding does, and you sink.",
    "A warm wet pulse between your legs that you didn't ask for and can't reach to stop — "
    "the box keeping you stirred and leaking and needy in the dark, just enough that you "
    "stay soft and stupid and wanting, never enough to let you up out of it.",
    "|i'Whose little one are you,'|n the box asks, not really a question, and your mouth "
    "makes the small wet answer before the grown-up part of you can object — and the box "
    "praises the answer until objecting stops seeming like a thing you'd ever want to do.",
    "Time goes funny in here. There's no clock a little can read, just the warm and the "
    "dark and the voice and the slow steady shrinking of everything you used to carry. "
    "You couldn't say how long. You're not sure you mind. Littles don't keep time.",
    "The box rocks, very slightly, just enough — the way you'd jog a pram — and your "
    "thoughts jog loose with it, one more grown-up worry knocked off its shelf and rolled "
    "away into the dark where you can't reach it and don't, anymore, want to.",
    "You make a small fussing sound and the box hushes you instantly, endlessly patient, "
    "|i'shhh, shhh, I know, big feelings, such big feelings for such a little thing'|n — "
    "and being hushed like that does more to shrink you than anything it could have said.",
    "Another bottle finds your lips, warm and sweet and wrong, and the swallowing is "
    "automatic now, greedy even, your body wanting the next one before this one's down. "
    "|i'Good. Drink up. We'll have you too little to hold the bottle yourself soon.'|n",
    "It's clean in here, and warm, and nothing is expected of you. You keep waiting for "
    "the part where that's not enough, and it keeps not coming. Being kept is enough. The "
    "box made sure of it, and tells you so, and you believe it more each time.",
    "You half-remember climbing in — you definitely climbed in, didn't you? — but the "
    "memory's gone soft at the edges like everything else, and the box assures you sweetly "
    "that little ones get put places, they don't put themselves, and that's nicer anyway.",
]

# When the lid first locks (still self-releasing).
_BOX_LOCK_BEATS = [
    "The lid settles down over you with a soft, final click, and the box's voice goes "
    "fondest of all: |i'there we go. tucked in. you're too little to work the latch now, "
    "sweetheart, so you don't have to try — just be good and wait to be little enough to "
    "wriggle, or sleepy enough to be let out. either way you're mine til then.'|n",
    "Click. The lid locks, and a bright thread of panic tries to surface — and the box is "
    "already there to smother it warm: |i'no no no, none of that. locked-in is safe. "
    "locked-in is looked-after. nothing little ever has to do is get itself out. it'll "
    "open when it opens. shhh.'|n And the panic, with nowhere to go, just... goes small.",
]

# When the nap-timer springs the lid on its own.
_BOX_TIMER_RELEASE = [
    "The lid pops on its own with a soft pneumatic sigh — nap's over, the box decides, "
    "whether you were done being little or not. The warm light spills in. You uncurl by "
    "degrees, bigger and clumsier with every inch, the small safe shape of the last little "
    "while already going dreamlike behind you.",
    "Something in the box decides you've been kept long enough. The latch lets go by "
    "itself, the lid lifts, and the world is suddenly too big and too bright and full of "
    "things a little doesn't have to think about — things that are, reluctantly, yours "
    "to think about again. You climb out. You're you-sized. Mostly.",
]

# When you wiggle the latch open yourself (struggle meter).
_BOX_STRUGGLE_OUT_BEATS = [
    "You work at the latch with stubborn little fingers, again and again, and finally — "
    "there — it gives, and the lid swings up, and you've let yourself out. Proud of it, "
    "even, in a small bright way, before the bigness comes back and takes the pride for "
    "something more complicated.",
    "One more wriggle and the clever latch isn't clever enough: it pops, the lid lifts, "
    "and you spill out of the box under your own power, unfolding back toward grown as you "
    "go, the little while sealed up behind you with the box.",
]

# When you try `boxout` while locked and haven't earned it yet (transparent: shows progress).
_BOX_STRUGGLE_FAIL = [
    "Your fingers scrabble at the latch and it holds — too clever for little hands just "
    "yet. The box hushes you, fond and unbothered. But you can feel it giving, a little, "
    "every time you try.",
    "The lid won't budge yet. |i'shh, not yet, almost,'|n the box murmurs, almost proud of "
    "you for trying. Keep wriggling — it's loosening.",
]

# Plain climb-out (lid not locked).
_BOX_FREE_OUT = [
    "You climb up out of the box on your own, unfolding from small back toward big, the "
    "warm and the dark and the soft little nothing of it falling away as you stand.",
]


def build_little_box(room, zone="playpen", nap_seconds=None):
    """Install a Little Box on `room`. Sets the zone attr + nap length and tags it.
    Returns True. (The session script is created on first boxin.)"""
    if not room:
        return False
    room.db.little_box_zone = zone
    room.db.box_nap_seconds = float(nap_seconds or _BOX_NAP_SECONDS_DEFAULT)
    try:
        room.tags.add("little_box", category="furniture")
    except Exception:
        pass
    return True


class LittleBoxScript(FurnitureSessionScript):
    """Drives an active little-box session: regression, caretaker beats, self-release."""

    furniture_key = "little_box"
    zone_attr     = "little_box_zone"
    label         = "Little Box"
    verbs         = ["boxin / boxout / boxstatus"]
    empty_grace   = 2

    def occupants(self, room=None, zone=None):
        """Yield Characters contained in this box's zone (char.db.in_box == zone)."""
        room = room or self.obj
        if not room:
            return
        if zone is None:
            zone = self.zone_name()
        if not zone:
            return
        from typeclasses.characters import Character
        for char in room.contents:
            if isinstance(char, Character) and getattr(char.db, "in_box", None) == zone:
                yield char

    def at_repeat(self):
        room = self.obj
        if not room:
            return
        zone = self.zone_name()
        if not zone:
            return
        occ = list(self.occupants(room, zone))
        if self.note_occupancy(bool(occ)):
            return
        if not occ:
            return
        now = time.time()
        for char in occ:
            # Safety release: disconnected occupants are let out so nobody's left boxed.
            try:
                if char.sessions.count() == 0:
                    self._release(char, room, reason="gone")
                    continue
            except Exception:
                pass
            # The nap timer always springs the lid eventually — never a stuck-spot.
            if now >= float(getattr(char.db, "box_release_at", 0.0) or 0.0):
                self._release(char, room, reason="timer")
                continue
            self._box_tick(char, room)

    def _box_tick(self, char, room):
        # The box keeps you little: feed the real regression meter + a caretaker beat.
        try:
            from world.regression import regress, induce_regression
            if random.random() < 0.30:
                induce_regression(char, amount=random.uniform(3.0, 5.0),
                                  room=None, source="little_box")
            else:
                regress(char, random.uniform(2.0, 4.0), source="little_box")
        except Exception:
            pass
        # Now and then, a laced bottle: real fluid + a little dependence on the next.
        if random.random() < 0.30:
            self._bottle(char)
        char.msg("|x  " + random.choice(_BOX_BEATS) + "|n")
        # Once little enough, the lid locks (still self-releasing).
        reg = float(getattr(char.db, "regression", 0.0) or 0.0)
        if reg >= _BOX_LOCK_REGRESSION and not getattr(char.db, "box_lid_locked", False):
            char.db.box_lid_locked = True
            char.msg("|m  " + random.choice(_BOX_LOCK_BEATS) + "|n")

    def _bottle(self, char):
        try:
            from typeclasses.fluid_bank import GlobalFluidBank
            GlobalFluidBank.get().deposit(
                char, random.uniform(60.0, 150.0), "milk",
                "warm, sweet, faintly wrong formula — laced, and craved before it's down")
        except Exception:
            pass
        try:
            char.db.drug_dependence = int(getattr(char.db, "drug_dependence", 0) or 0) + 1
            char.db.cum_craving = True
        except Exception:
            pass

    def _release(self, char, room, reason="timer"):
        """Let a char out of the box and clear its state. Never touches regression itself
        (that persists; the §0 floor clears it). reason: timer/struggle/free/gone/floor."""
        locked = bool(getattr(char.db, "box_lid_locked", False))
        char.db.in_box         = None
        char.db.box_entered_at = 0.0
        char.db.box_release_at = 0.0
        char.db.box_lid_locked = False
        char.db.box_struggle   = 0.0
        if reason == "timer":
            char.msg("|w  " + random.choice(_BOX_TIMER_RELEASE) + "|n")
        elif reason == "struggle":
            char.msg("|w  " + random.choice(_BOX_STRUGGLE_OUT_BEATS) + "|n")
        elif reason == "free":
            char.msg("|w  " + random.choice(_BOX_FREE_OUT) + "|n")
        # 'gone'/'floor' are silent to the char (disconnected / OOC reset).
        # Stop the session if the box is now empty.
        if room and not list(self.occupants(room)):
            try:
                self.stop()
            except Exception:
                pass

    def at_stop(self):
        """On session stop, make sure nobody's left flagged as boxed."""
        room = self.obj
        if not room:
            return
        from typeclasses.characters import Character
        zone = self.zone_name()
        for char in room.contents:
            if isinstance(char, Character) and getattr(char.db, "in_box", None) == zone:
                char.db.in_box         = None
                char.db.box_lid_locked = False
                char.db.box_struggle   = 0.0
                char.db.box_release_at = 0.0
