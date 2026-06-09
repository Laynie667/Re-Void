"""
typeclasses/rocking_horse_script.py

RockingHorseScript — drives a rocking horse session for an occupant.

Pace system mirrors the milking machine: slow / steady / fast / intense.
Upgrade flags are stored on room.db.horse_upgrades as a list of strings.

Available upgrades:
  motorized   — required for script-driven automatic pacing
  vibrating   — seat vibrates between rocks
  milking     — breast suction cups activate on mount
  restrained  — wrists + ankles lock to handles/stirrups on mount
  knot        — seat can engage a knot at arousal threshold
  inflation   — seat inflates incrementally during session

Attach to a room:
  @py from typeclasses.rocking_horse_script import RockingHorseScript
  @py from evennia.utils import create; create.create_script(RockingHorseScript, obj=here, persistent=True)
  @set here/horse_zone = <zone_name>
  @set here/horse_pace = steady
  @set here/horse_upgrades = []

Room commands: horsestart / horsestop / horsepace / horsemount / horsedismount
(see commands/rocking_horse_commands.py)
"""

import time
import random
from typeclasses.furniture_session import FurnitureSessionScript

# Arousal at/above which the frame straps the rider in (the lock-in is EARNED by
# the ride working them up, not slammed on at mount).
_RESTRAIN_THRESHOLD = 40.0
# The horse only breeds (deposits) once worked up, and then only periodically —
# a climactic event, not a per-rock thing. Threshold + refractory cooldown.
_BREED_THRESHOLD    = 65.0
_BREED_COOLDOWN_S   = 75.0
# The deposit telegraphs first: at/above _BREED_NEAR_THRESHOLD the shaft visibly winds up
# (a build-up beat) and only fires on the NEXT qualifying tick, so it's never a surprise.
_BREED_NEAR_THRESHOLD = 55.0

# Knot stages — it swells (felt), then locks (held), then softens (released) on a timer.
# Swell starts a little before the breeding telegraph so it lands as its own beat.
_KNOT_SWELL_THRESHOLD = 45.0
_KNOT_LOCK_THRESHOLD  = 80.0
_KNOT_LOCK_SECONDS    = 180.0

# Inflation seat: announce growth each step, and a one-time "full" beat at this cap (ml).
_INFLATION_FULL_ML    = 200.0

_CUNT_WORDS = ("cunt", "pussy", "vagina", "sex")
_ASS_WORDS  = ("ass", "anus", "rear", "behind")


def rider_holes(char, facing="forward", upgrades=None):
    """Which orifice zone(s) the seat works on this rider.

    Returns a list of zone names. With the 'double' upgrade and both a cunt- and
    an ass-type orifice available, returns BOTH; otherwise a single hole chosen by
    facing (forward → cunt, backward → ass), falling back to whatever orifice exists.
    """
    upgrades = upgrades or []
    zones = getattr(char.db, "zones", None) or {}
    orifices = [zn for zn, zd in zones.items()
                if (zd or {}).get("zone_type") in ("orifice", "both")]
    cunt = next((zn for zn in orifices if any(w in zn for w in _CUNT_WORDS)), None)
    ass  = next((zn for zn in orifices if any(w in zn for w in _ASS_WORDS)), None)
    if "double" in upgrades and cunt and ass:
        return [cunt, ass]
    if facing == "backward":
        return [ass or cunt or (orifices[0] if orifices else None)]
    return [cunt or ass or (orifices[0] if orifices else None)]


def holes_kind(holes):
    """Classify a hole list for message-pool selection: 'both' / 'cunt' / 'ass'."""
    if len([h for h in holes if h]) > 1:
        return "both"
    h = (holes[0] if holes else "") or ""
    return "ass" if any(w in h for w in _ASS_WORDS) else "cunt"


# The 'little' upgrade — the horse treats its rider as a small, helpless thing to be
# kept somewhere safe. Warm caretaker voice; helplessness delivered as comfort. The
# rocking is a cradle; the fullness is a pacifier; the regression is the point. (Feeds
# the real world.regression meter — see _tick_little.)
_LITTLE_BEATS = [
    "The horse's voice is soft and warm and close — |i'there we go, good girl, up you "
    "get'|n — and something behind your eyes goes quiet and small at being talked to "
    "like that.",
    "It rocks you the way you'd rock a fussy child: slow, deep, |ifor your own good|n. "
    "The squirming and the riding stop being different things.",
    "You reach for a grown-up thought and it slips — the warmth has it, the rhythm has "
    "it. There's just the rock, and the full, and the voice calling you good.",
    "|i'You don't have to do anything,'|n the horse murmurs into the top of your head. "
    "|i'Just be carried. Someone will come collect you.'|n And the not-having-to is the "
    "sweetest part.",
    "Your hands are put away and you can't quite remember agreeing to it. Helpless "
    "doesn't feel done to you — it feels like being |ilooked after|n, and that's worse.",
    "It tells you little things ride to be filled, sweetly, certainly, while your belly "
    "rounds out warm and heavy and your thoughts drift another inch toward nothing.",
    "You make a small sound instead of a word, and the horse praises it like you've done "
    "something clever. You do it again, just to be told again.",
    "The cradle-creak of the frame syncs up with something in your chest and the two of "
    "them rock you down together — a size smaller with every arc, a year lighter, the big "
    "heavy grown-up worries sliding off you like a coat too large to keep on.",
    "|i'Who's a sleepy little thing,'|n it croons, and you are, you really are — the seat "
    "filling you and the voice emptying you and somewhere in the middle the part of you "
    "that does sums and makes plans just... sets itself down and toddles off.",
    "You whine when the rhythm changes and the horse hushes you, patient as a nursery. "
    "|i'I know, I know. Shh. Big feelings for such a little one.'|n You believe it about "
    "yourself a little more each time it says it.",
    "There's a soother-sweetness to being this full and this small at once — nothing "
    "asked of you, nothing owed, just the rock and the stretch and the steady warm voice "
    "telling you that little ones don't have to understand, they just have to be good.",
    "Your thumb finds your mouth and you let it, because the horse said good girl when it "
    "did, and good girl is the only grade that means anything down here where you are now.",
    "The words in your head come out with their corners rounded off, small and wet and "
    "easy, and you stop reaching past them. Past them is heavy. Here is warm. Here it "
    "rocks you and calls you its baby and you let it be true.",
    "|i'There's my good little ride,'|n it says, and you glow — actually glow, helplessly, "
    "the praise landing somewhere far under the part of you that would once have been "
    "embarrassed by how much you needed it.",
    "Each arc tucks you in a little further: smaller in the shoulders, slower in the head, "
    "softer in the want. By the bottom of this one you've half-forgotten there's a version "
    "of you that stands up tall and does hard things. By the top you don't miss her.",
]


class RockingHorseScript(FurnitureSessionScript):
    """Drives an active rocking horse session."""

    furniture_key = "rocking_horse"
    zone_attr     = "horse_zone"
    label         = "Rocking Horse"
    verbs         = [
        "horsemount [forward|backward] / horsedismount",
        "horsestart / horsestop / horsepace <slow|steady|fast|intense>",
        "horseupgrade add|remove <flag> / horsestatus",
    ]

    def at_repeat(self):
        room = self.obj
        if not room:
            return

        zone_name = getattr(room.db, "horse_zone", None)
        if not zone_name:
            return

        # Auto-stop the session if nobody is riding (prevents stale scripts).
        riders = list(self.occupants(room, zone_name))
        if self.note_occupancy(bool(riders)):
            return
        if not riders:
            return

        upgrades = list(getattr(room.db, "horse_upgrades", None) or [])
        pace     = getattr(room.db, "horse_pace", "steady") or "steady"

        from typeclasses.arousal_script import add_arousal
        from world.rocking_horse_loader import (
            pick_horse_msg, get_horse_config
        )

        config   = get_horse_config(pace)
        arousal_gain = config.get("arousal_per_tick", 6.0)

        for char in riders:
            self.apply_rider_tick(char, room, upgrades, pace, arousal_gain)

    def apply_rider_tick(self, char, room, upgrades=None, pace=None, arousal_gain=None):
        """One rock's worth of effects on a rider — shared by the auto-rhythm (at_repeat)
        and the manual `rock` command, so rocking it yourself does exactly what waiting does."""
        from typeclasses.arousal_script import add_arousal
        from world.rocking_horse_loader import pick_horse_msg, get_horse_config
        if upgrades is None:
            upgrades = list(getattr(room.db, "horse_upgrades", None) or [])
        if pace is None:
            pace = getattr(room.db, "horse_pace", "steady") or "steady"
        if arousal_gain is None:
            arousal_gain = get_horse_config(pace).get("arousal_per_tick", 6.0)
        rider_name = char.db.rp_name or char.name

        msg = pick_horse_msg(pace, "running")
        if msg:
            room.msg_contents(msg.replace("{rider}", rider_name))

        add_arousal(char, arousal_gain)
        # The build-up: announce the rider climbing into a new arousal band, so the ride
        # reads as an escalating scene rather than a flat loop. (Fires on upward crossings.)
        self._arousal_beat(char, room, rider_name)

        if "restrained" in upgrades:
            self._check_restraint(char, room)
        if "vibrating" in upgrades:
            if random.random() < 0.50:
                char.msg("|xThe seat buzzes hard between rocks, a relentless little pulse "
                         "right where it's buried, never quite letting the edge off.|n")
        if "milking" in upgrades:
            self._tick_milking(char, room)
        if "inflation" in upgrades:
            zone_name = getattr(room.db, "horse_zone", None)
            self._tick_inflation(char, room, zone_name, upgrades)
        if "knot" in upgrades:
            self._check_knot(char, room, upgrades)
        if "breeding" in upgrades:
            self._tick_breeding(char, room, upgrades)
        if "little" in upgrades:
            self._tick_little(char, room)

    # Arousal bands for the build-up beats (low -> high). Crossing UP narrates a beat.
    _AROUSAL_BANDS = [(75.0, "edge"), (55.0, "rising"), (30.0, "building"), (0.0, "warming")]
    _BAND_ORDER    = ["warming", "building", "rising", "edge"]

    def _arousal_beat(self, char, room, rider_name):
        """Narrate the rider crossing UP into a new arousal band — the scene's build-up."""
        arousal = float(char.db.arousal or 0.0)
        band = next(name for thr, name in self._AROUSAL_BANDS if arousal >= thr)
        prev = getattr(char.db, "horse_arousal_band", None)
        if band == prev:
            return
        char.db.horse_arousal_band = band
        climbing = (prev is None
                    or self._BAND_ORDER.index(band) > self._BAND_ORDER.index(prev))
        if not climbing:
            return
        from world.rocking_horse_loader import pick_horse_msg
        line = pick_horse_msg("arousal", band)
        if line:
            room.msg_contents("|r" + line.replace("{rider}", rider_name) + "|n")

    def _check_restraint(self, char, room):
        """Strap the rider in once the ride has worked them past the threshold — NOT
        on mount. Engages once; sets restrained_zone so occupancy/flavor hold."""
        if getattr(char.db, "restrained_zone", None):
            # Already strapped in — an occasional reminder so the state stays present.
            if random.random() < 0.25:
                rider_name = char.db.rp_name or char.name
                from world.rocking_horse_loader import pick_horse_msg
                msg = (pick_horse_msg("upgrade", "restrain_reminder")
                       or "{rider} pulls at the straps; they don't give.")
                room.msg_contents("|x" + msg.replace("{rider}", rider_name) + "|n")
            return
        if float(char.db.arousal or 0.0) < _RESTRAIN_THRESHOLD:
            return
        zone_name = getattr(room.db, "horse_zone", None)
        char.db.restrained_zone = zone_name
        rider_name = char.db.rp_name or char.name
        from world.rocking_horse_loader import pick_horse_msg
        msg = (pick_horse_msg("upgrade", "restrain_threshold")
               or "The restraints draw shut around {rider} now that the ride has them.")
        room.msg_contents(msg.replace("{rider}", rider_name))

    def at_start(self):
        room = self.obj
        if not room:
            return
        pace   = getattr(room.db, "horse_pace", "steady") or "steady"
        from world.rocking_horse_loader import get_horse_config
        config = get_horse_config(pace)
        self.interval = config.get("interval_seconds", 45)

    # ------------------------------------------------------------------
    # Upgrade tick helpers
    # ------------------------------------------------------------------

    def _tick_milking(self, char, room):
        """Run a single milking tick on the rider's breast zones."""
        try:
            from typeclasses.production_item import ProductionItem
            from typeclasses.fluid_bank import GlobalFluidBank
            zones = getattr(char.db, "zones", None) or {}
            for zd in zones.values():
                entry = (zd.get("mechanics") or {}).get("production")
                if not entry:
                    continue
                from evennia import search_object
                results = search_object(entry.get("item_dbref", ""), exact=True)
                if not results or not isinstance(results[0], ProductionItem):
                    continue
                item = results[0]
                if item.db.fluid_type != "milk":
                    continue
                available = item.db.current_volume_ml or 0.0
                if available <= 0:
                    continue
                extract = min(4.0, available)
                item.db.current_volume_ml = max(0.0, available - extract)
                item.reset_fullness_notifications()
                GlobalFluidBank.get().deposit(
                    char, extract, item.db.fluid_type, item.db.fluid_flavor
                )
        except Exception:
            pass

    def _rider_orifice(self, char):
        """The orifice the seat is working — prefer cunt/ass over mouth; any orifice else."""
        zones = getattr(char.db, "zones", None) or {}
        pref = ("cunt", "pussy", "vagina", "sex", "ass", "anus", "hole")
        for zn, zd in zones.items():
            if (zd or {}).get("zone_type") in ("orifice", "both") and any(w in zn for w in pref):
                return zn
        for zn, zd in zones.items():
            if (zd or {}).get("zone_type") in ("orifice", "both"):
                return zn
        return None

    def _tick_little(self, char, room):
        """The 'little'/helpless headspace. Feeds the REAL regression meter
        (world.regression) — the speech-drift, name-loss and little-talk are owned there
        and cleared by the OOC floor — so the cradle actually walks the rider down over a
        session instead of just flavour-texting it. Occasionally runs a full induction
        (the horse's caretaker voice) for a bigger step; otherwise a small steady drift."""
        try:
            from world.regression import regress, induce_regression
            if random.random() < 0.25:
                # The horse does a proper induction beat in its nursery-voice.
                induce_regression(char, amount=random.uniform(2.0, 4.0),
                                   room=room, source="rocking_horse")
            else:
                regress(char, random.uniform(1.0, 2.5), source="rocking_horse")
        except Exception:
            # Fallback if regression isn't available: the old light baby-talk drift.
            try:
                if not getattr(char.db, "horse_baby_talk", False):
                    active = list(getattr(char.db, "active_speech_filters", None) or [])
                    if "baby_talk" not in active:
                        active.append("baby_talk")
                        char.db.active_speech_filters = active
                        char.db.horse_baby_talk = True
            except Exception:
                pass
        try:
            from typeclasses.arousal_script import add_arousal
            add_arousal(char, 3.0)
        except Exception:
            pass
        char.msg("|x  " + random.choice(_LITTLE_BEATS) + "|n")

    def _tick_breeding(self, char, room, upgrades=None):
        """Breeding upgrade: the shaft(s) breed the rider — a CLIMACTIC deposit, not a
        per-rock one. Gated behind an arousal threshold and a refractory cooldown so it
        reads as the horse cumming when the ride peaks, then building back up to do it
        again. Real fluid deposit (inflation/pregnancy/womb systems pick it up), but the
        room message is the horse's own hot pool — not the clinical machine line."""
        try:
            import random as _r
            from typeclasses.insemination_item import do_inseminate
            from world.rocking_horse_loader import pick_horse_msg
            from typeclasses.production_item import format_volume

            arousal = float(char.db.arousal or 0.0)
            now  = time.time()
            last = float(getattr(char.db, "horse_last_breed_at", 0.0) or 0.0)
            rider_name = char.db.rp_name or char.name

            # Refractory window: narrate the afterglow / the shaft thickening up again,
            # so the cooldown reads as recovery rather than dead air.
            if now - last < _BREED_COOLDOWN_S and last > 0:
                if random.random() < 0.5:
                    msg = (pick_horse_msg("upgrade", "breed_after")
                           or "The horse rocks {rider} through the afterglow, the load sitting deep.")
                    room.msg_contents("|x" + msg.replace("{rider}", rider_name) + "|n")
                return

            # Build-up beat: once worked up but not yet at the deposit threshold, the shaft
            # visibly winds up — and we DON'T fire the load until the next qualifying tick,
            # so being bred is always telegraphed, never a surprise.
            if arousal < _BREED_THRESHOLD:
                if arousal >= _BREED_NEAR_THRESHOLD and not getattr(char.db, "horse_breed_warned", False):
                    char.db.horse_breed_warned = True
                    msg = (pick_horse_msg("upgrade", "breed_near")
                           or "The shaft swells and jerks inside {rider} — the horse is close.")
                    room.msg_contents("|r" + msg.replace("{rider}", rider_name) + "|n")
                return
            # At/over threshold: only go off if it warned first (guarantees a build-up beat).
            if not getattr(char.db, "horse_breed_warned", False):
                char.db.horse_breed_warned = True
                msg = (pick_horse_msg("upgrade", "breed_near")
                       or "The shaft swells and jerks inside {rider} — the horse is about to go off.")
                room.msg_contents("|r" + msg.replace("{rider}", rider_name) + "|n")
                return

            upgrades = upgrades if upgrades is not None else \
                list(getattr(room.db, "horse_upgrades", None) or [])
            facing = getattr(char.db, "horse_facing", "forward") or "forward"
            holes  = [h for h in rider_holes(char, facing, upgrades) if h]
            if not holes:
                return

            char.db.horse_last_breed_at = now
            char.db.horse_breed_warned  = False
            total = _r.uniform(90.0, 180.0)
            per   = total / len(holes)
            for zone in holes:
                # Deposit silently — we broadcast the horse's own message below.
                do_inseminate(None, char, zone, {
                    "source": "machine", "fluid_type": "semen",
                    "volume_per_tick": per, "ttl_hours": 12.0,
                })

            rider_name = char.db.rp_name or char.name
            kind = holes_kind(holes)
            pool = "breeding_both" if kind == "both" else "breeding_deposit"
            zone_disp = (" and ".join(h.replace("_", " ") for h in holes)
                         if kind == "both" else holes[0].replace("_", " "))
            msg = (pick_horse_msg("upgrade", pool)
                   or "The horse breeds {rider} — {volume} pumped deep into their {zone}.")
            room.msg_contents(
                msg.replace("{rider}", rider_name)
                   .replace("{volume}", format_volume(total))
                   .replace("{zone}", zone_disp)
            )
        except Exception:
            pass

    def _tick_inflation(self, char, room, zone_name, upgrades):
        """Incrementally inflate the seat inside the rider — and SAY so. Each step narrates
        the swelling; crossing the cap fires a one-time 'full' beat."""
        try:
            from typeclasses.inflation_item import add_inflation_volume
            add_inflation_volume(char, zone_name, 25.0, "seat_fill")
        except Exception:
            pass
        rider_name = char.db.rp_name or char.name
        fill = float(getattr(char.db, "horse_seat_fill", 0.0) or 0.0) + 25.0
        char.db.horse_seat_fill = fill
        from world.rocking_horse_loader import pick_horse_msg
        if fill >= _INFLATION_FULL_ML:
            if not getattr(char.db, "horse_seat_full_said", False):
                char.db.horse_seat_full_said = True
                msg = (pick_horse_msg("upgrade", "inflation_full")
                       or pick_horse_msg("upgrade", "inflation_peak")
                       or "The seat is packed full inside {rider}, swollen to capacity.")
                room.msg_contents("|R" + msg.replace("{rider}", rider_name) + "|n")
        elif random.random() < 0.6:
            msg = (pick_horse_msg("upgrade", "inflation_fill")
                   or "The seat swells bigger inside {rider}, stretching them wider.")
            room.msg_contents("|r" + msg.replace("{rider}", rider_name) + "|n")

    def _check_knot(self, char, room, upgrades):
        """Staged knot you can feel coming and going:
            stage 0 -> 1 (swelling) at _KNOT_SWELL_THRESHOLD,
            stage 1 -> 2 (locked)   at _KNOT_LOCK_THRESHOLD,
            stage 2 -> 0 (softens/releases) once the lock timer expires.
        Every transition is announced, so the rider always knows whether it's inflating
        or deflating and whether they're held."""
        arousal    = float(char.db.arousal or 0.0)
        stage      = int(getattr(char.db, "horse_knot_stage", 0) or 0)
        rider_name = char.db.rp_name or char.name
        from world.rocking_horse_loader import pick_horse_msg

        def say(pool, fallback):
            room.msg_contents("|r" + (pick_horse_msg("upgrade", pool) or fallback)
                              .replace("{rider}", rider_name) + "|n")

        if stage == 2 and getattr(char.db, "horse_knotted", False):
            # Locked — release when the timer runs out, else an occasional held-fast reminder.
            if time.time() >= float(getattr(char.db, "horse_knot_expires_at", 0.0) or 0.0):
                char.db.horse_knotted   = False
                char.db.horse_knot_stage = 0
                char.db.horse_knot_expires_at = 0.0
                say("knot_soften", "The knot softens and lets {rider} loose.")
            elif random.random() < 0.30:
                room.msg_contents(f"|x{rider_name} shifts and the knot holds them fast, "
                                  f"sealed onto the seat, going nowhere yet.|n")
            return
        if stage == 0 and arousal >= _KNOT_SWELL_THRESHOLD:
            char.db.horse_knot_stage = 1
            say("knot_swell", "The knot at the base of the seat begins to swell inside {rider}.")
            return
        if stage == 1 and arousal >= _KNOT_LOCK_THRESHOLD:
            char.db.horse_knot_stage      = 2
            char.db.horse_knotted         = True
            char.db.horse_knot_expires_at = time.time() + _KNOT_LOCK_SECONDS
            say("knot_engage", "The knot swells past pulling-out and locks {rider} onto the seat.")

    def at_stop(self):
        """Release all knots and inflation when session stops."""
        room = self.obj
        if not room:
            return
        from typeclasses.characters import Character
        zone_name = getattr(room.db, "horse_zone", None)
        for char in room.contents:
            if not isinstance(char, Character):
                continue
            char.db.horse_knotted         = False
            char.db.horse_knot_expires_at = 0.0
            char.db.horse_knot_stage      = 0
            char.db.horse_last_breed_at   = 0.0
            char.db.horse_breed_warned    = False
            char.db.horse_arousal_band    = None
            char.db.horse_seat_fill       = 0.0
            char.db.horse_seat_full_said  = False
            if zone_name:
                try:
                    from typeclasses.inflation_item import drain_inflation
                    drain_inflation(char, zone_name)
                except Exception:
                    pass
