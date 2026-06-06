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


# The 'little' upgrade — the horse treats its rider as a small, helpless thing to be
# kept somewhere safe. Warm caretaker voice; helplessness delivered as comfort.
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

        if "vibrating" in upgrades:
            if random.random() < 0.50:
                char.msg("|xThe seat pulses between rocks.|n")
        if "milking" in upgrades:
            self._tick_milking(char, room)
        if "inflation" in upgrades:
            zone_name = getattr(room.db, "horse_zone", None)
            self._tick_inflation(char, room, zone_name, upgrades)
        if "knot" in upgrades:
            self._check_knot(char, room, upgrades)
        if "breeding" in upgrades:
            self._tick_breeding(char, room)
        if "little" in upgrades:
            self._tick_little(char, room)

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
        """The 'little'/helpless headspace: a caretaker voice, drifting conditioning, and
        a baby-talk speech filter applied once (cleanly removed on dismount)."""
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
            from world.conditioning import add_conditioning
            add_conditioning(char, 1.0, source="rocking_horse")
        except Exception:
            pass
        try:
            from typeclasses.arousal_script import add_arousal
            add_arousal(char, 3.0)
        except Exception:
            pass
        char.msg("|x  " + random.choice(_LITTLE_BEATS) + "|n")

    def _tick_breeding(self, char, room):
        """Breeding upgrade: the dildos cum into the seated rider and the belly fills —
        a real fluid deposit (which the inflation/pregnancy systems pick up). Optional;
        this is what makes the horse *deposit and inflate* rather than just ride."""
        try:
            import random as _r
            from typeclasses.insemination_item import do_inseminate
            zone = self._rider_orifice(char)
            if not zone:
                return
            msg = do_inseminate(None, char, zone, {
                "source": "machine", "fluid_type": "semen",
                "volume_per_tick": _r.uniform(60.0, 160.0), "ttl_hours": 12.0,
            })
            if msg:
                room.msg_contents(msg)
        except Exception:
            pass

    def _tick_inflation(self, char, room, zone_name, upgrades):
        """Incrementally inflate the seat inside the rider."""
        try:
            from typeclasses.inflation_item import add_inflation_volume
            add_inflation_volume(char, zone_name, 25.0, "seat_fill")
        except Exception:
            pass

    def _check_knot(self, char, room, upgrades):
        """Engage a knot if arousal threshold met."""
        arousal = float(char.db.arousal or 0.0)
        if arousal < 75.0:
            return
        if getattr(char.db, "horse_knotted", False):
            return
        if random.random() > 0.20:
            return
        char.db.horse_knotted         = True
        char.db.horse_knot_expires_at = time.time() + 180.0
        rider_name = char.db.rp_name or char.name
        from world.rocking_horse_loader import pick_horse_msg
        msg = pick_horse_msg("upgrade", "knot_engage") or f"The horse catches — {rider_name} is locked onto the seat."
        room.msg_contents(msg.replace("{rider}", rider_name))

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
            if zone_name:
                try:
                    from typeclasses.inflation_item import drain_inflation
                    drain_inflation(char, zone_name)
                except Exception:
                    pass
