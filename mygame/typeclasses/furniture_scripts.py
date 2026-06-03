"""
typeclasses/furniture_scripts.py

Animated furniture scripts for Re:Void.

Each script attaches to a room and drives mechanical behaviour on occupants
of a specific zone — arousal gain, forced emotes, state progression, etc.

Follows the same pattern as MilkingSessionScript and CycleScript.

Scripts in this file:
  EdgeMachineScript      — builds arousal to 99, holds there, releases on command
  MilkingStanchionScript — restrains + auto-starts a milking session
  DisplayPedestalScript  — applies exhibition effect while occupied, fires ambient
  SensoryDeprivationScript — strips ambients, blocks say, routes holder pulses

Install via:
  @py from typeclasses.furniture_scripts import EdgeMachineScript
  @py from evennia.utils import create; create.create_script(EdgeMachineScript, obj=here, persistent=True)

Then set:
  @set here/has_edge_machine = 1
  @set here/edge_machine_zone = <zone_name>
"""

import time
import random
from evennia import DefaultScript
from typeclasses.furniture_session import FurnitureSessionScript


# ---------------------------------------------------------------------------
# EdgeMachineScript
# ---------------------------------------------------------------------------

_EDGE_MSGS_PRIVATE = [
    "The machine holds you right where it wants you — at the edge, no further, not for anything. It does not lose its grip and it does not lose track.",
    "Ninety-nine, and the machine knows it, and it's not giving you that last point. The pressure doesn't ease a hair.",
    "Right there. The machine keeps you right there — the finish close enough to taste and just exactly out of reach.",
    "The edge is precise. The machine is precise. You stay pinned exactly on it, shaking.",
    "You push at the ceiling the machine's set and it doesn't budge. Neither, it turns out, do you.",
]

_EDGE_MSGS_ROOM = [
    "{name} is very still — the kind of concentrated, white-knuckle still that's being held in place by something.",
    "Something in {name}'s posture hit its limit and just stopped there, trembling.",
    "{name} breathes careful — slow, measured, working hard around something they can't quite reach.",
]

_EDGE_NEAR_MSGS = [
    "The machine's walking you toward the edge, and approach is a long way from arrival.",
    "Ninety. The machine clocks it and leans in, adjusting its pace, savoring the climb.",
    "Close. The machine keeps you close and changes the interval just to make sure you feel it.",
    "The pressure stacks up toward the ceiling the machine's set, slow, deliberate, and merciless.",
]


class EdgeMachineScript(FurnitureSessionScript):
    """
    Holds an occupant at arousal 99 — just short of climax.
    Release requires: holder says configured release word, or 'endedge' command.

    Attaches to a room. Zone set via room.db.edge_machine_zone.
    """

    furniture_key = "edge_machine"
    zone_attr     = "edge_machine_zone"
    label         = "Edge Machine"
    verbs         = [
        "edgestart [zone] / edgestop",
        "held at 99 — say the release word to finish",
    ]

    def at_script_creation(self):
        super().at_script_creation()
        self.interval = 30   # check every 30 seconds

    def at_repeat(self):
        room = self.obj
        if not room:
            return

        zone_name = getattr(room.db, "edge_machine_zone", None)
        if not zone_name:
            return

        # Auto-stop if nobody is in the machine (prevents stale scripts).
        riders = list(self.occupants(room, zone_name))
        if self.note_occupancy(bool(riders)):
            return

        from typeclasses.arousal_script import add_arousal

        for char in riders:
            # Apply arousal_denial flag — cap at 99
            char.db.orgasm_denial         = True
            char.db.orgasm_release_word   = getattr(room.db, "edge_release_word", "release")

            arousal = float(char.db.arousal or 0.0)
            cname   = char.db.rp_name or char.name

            try:
                from world.milking_loader import pick_edge_message
                _edge = pick_edge_message
            except Exception:
                _edge = None

            def _private(phase):
                if _edge:
                    msg = _edge(phase, "private")
                    if msg:
                        char.msg(msg)

            def _room_msg(phase, chance=0.30):
                if random.random() < chance and _edge:
                    msg = _edge(phase, "room")
                    if msg:
                        room.msg_contents(msg.replace("{name}", cname), exclude=[char])

            if arousal < 75:
                add_arousal(char, 8.0)
                if random.random() < 0.35:
                    _private("building")
                _room_msg("building", 0.15)
            elif arousal < 90:
                add_arousal(char, 8.0)
                if random.random() < 0.50:
                    _private("approaching")
                _room_msg("approaching", 0.25)
            elif arousal < 99:
                add_arousal(char, 3.0)
                if random.random() < 0.65:
                    _private("near")
                _room_msg("near", 0.35)
            else:
                # Held at the edge
                if random.random() < 0.60:
                    _private("held")
                _room_msg("held", 0.25)

    def at_stop(self):
        """Release all occupants' denial when machine stops."""
        room = self.obj
        if not room:
            return
        zone_name = getattr(room.db, "edge_machine_zone", None)
        from typeclasses.characters import Character
        for char in room.contents:
            if not isinstance(char, Character):
                continue
            if not char.db.orgasm_denial:
                continue
            char.db.orgasm_denial         = False
            char.db.orgasm_denial_lifted  = False
            char.db.orgasm_release_word   = ""
            char.msg("|xThe edge machine finally lets you go.|n")


# ---------------------------------------------------------------------------
# MilkingStanchionScript
# ---------------------------------------------------------------------------

_STANCHION_LOCK_MSGS = [
    "The stanchion clamps shut around you — frame at the neck, bar at the hips. You're not going anywhere, and that's rather the idea.",
    "The stanchion locks you down and the milking attachments find their spots on their own. No input required from you.",
    "A heavy mechanical click and the stanchion's got you — positioned, held, and lined up to be milked whether you're ready or not.",
]

_STANCHION_RELEASE_MSGS = [
    "The stanchion lets go — the frame swinging open, the attachments drawing back. You're free, and a little unsteady.",
    "The locks pop on the stanchion and it opens up. You can move again.",
    "The stanchion releases you — frame, bar, and attachments all retracting. Done with you. For now.",
]


class MilkingStanchionScript(FurnitureSessionScript):
    """
    Restrains the occupant and auto-starts a milking session.
    Releases when milking is complete or occupant uses 'endmilk'.

    Attaches to a room. Zone set via room.db.stanchion_zone.
    """

    furniture_key = "milking_stanchion"
    zone_attr     = "stanchion_zone"
    label         = "Milking Stanchion"
    verbs         = [
        "stanchionstart [zone] / stanchionrelease",
    ]

    def at_script_creation(self):
        super().at_script_creation()
        self.interval = 10   # check every 10 seconds

    def at_repeat(self):
        room = self.obj
        if not room:
            return

        zone_name = getattr(room.db, "stanchion_zone", None)
        if not zone_name:
            return

        # Auto-stop if nobody is locked in (prevents stale scripts).
        riders = list(self.occupants(room, zone_name))
        if self.note_occupancy(bool(riders)):
            return

        from typeclasses.milking_session_script import MilkingSessionScript
        from evennia.utils import create
        from world.milking_loader import get_speed_config, pick_message

        for char in riders:
            # Check if already milking
            already_milking = any(
                isinstance(s, MilkingSessionScript)
                for s in char.scripts.all()
            )
            if already_milking:
                continue

            # Lock in and start milking
            if not getattr(char.db, "stanchion_locked", False):
                char.db.stanchion_locked = True
                char.msg(random.choice(_STANCHION_LOCK_MSGS))

            # Find production zone and start session
            zones = getattr(char.db, "zones", None) or {}
            has_prod = any(
                (zd.get("mechanics") or {}).get("production")
                for zd in zones.values()
            )
            if not has_prod:
                continue

            config = get_speed_config()
            speed  = getattr(room.db, "stanchion_speed", "steady")
            start_msg = pick_message(speed, "start") or ""
            if start_msg:
                room.msg_contents(start_msg.replace("{target}", char.db.rp_name or char.name))

            script = create.create_script(
                MilkingSessionScript, obj=char,
                autostart=False, persistent=True,
            )
            script.db.speed          = speed
            script.db.operator_dbref = None
            script.db.zone_filter    = None
            script.interval          = config.get(speed, {}).get("interval_seconds", 60)
            script.start()

    def release_occupant(self, char):
        """Explicitly release a character from the stanchion."""
        char.db.stanchion_locked = False
        room = self.obj
        if room:
            char.msg(random.choice(_STANCHION_RELEASE_MSGS))


# ---------------------------------------------------------------------------
# DisplayPedestalScript
# ---------------------------------------------------------------------------

_PEDESTAL_MSGS = [
    "{name} is up on the pedestal — raised, lit, every line of them laid out for the room to look at.",
    "{name} stands on the pedestal and the whole room's attention quietly rearranges itself around them.",
    "The pedestal holds {name} up above the floor, and there's nowhere in the room to look that isn't straight at them.",
]


class DisplayPedestalScript(FurnitureSessionScript):
    """
    When occupied, applies exhibition effect to the occupant and fires
    periodic room messages drawing attention to them.

    Attaches to a room. Zone set via room.db.pedestal_zone.
    """

    furniture_key = "display_pedestal"
    zone_attr     = "pedestal_zone"
    label         = "Display Pedestal"
    verbs         = [
        "step onto the pedestal zone to be put on display",
    ]

    def at_script_creation(self):
        super().at_script_creation()
        self.interval = 120   # check every 2 minutes

    def at_repeat(self):
        room = self.obj
        if not room:
            return

        zone_name = getattr(room.db, "pedestal_zone", None)
        if not zone_name:
            return

        from typeclasses.characters import Character
        present = False
        for char in room.contents:
            if not isinstance(char, Character):
                continue

            occupied = getattr(char.db, "seated_zone", None) or getattr(char.db, "restrained_zone", None)
            if occupied != zone_name:
                # Remove exhibition if they stepped off
                if getattr(char.db, "on_pedestal", False):
                    char.db.on_pedestal       = False
                    char.db.exhibition_active = False
                continue

            present = True

            # Apply exhibition effect
            if not getattr(char.db, "on_pedestal", False):
                char.db.on_pedestal       = True
                char.db.exhibition_active = True
                char.db.outfit_camouflage = ""
                cname = char.db.rp_name or char.name
                room.msg_contents(
                    f"|x{cname} steps up onto the pedestal — and suddenly there's nowhere left on them to hide.|n"
                )

            # Periodic display message
            cname = char.db.rp_name or char.name
            room.msg_contents(random.choice(_PEDESTAL_MSGS).format(name=cname))

        # Auto-stop when the pedestal has stood empty a while.
        self.note_occupancy(present)


# ---------------------------------------------------------------------------
# SensoryDeprivationScript
# ---------------------------------------------------------------------------

class SensoryDeprivationScript(DefaultScript):
    """
    When a character is inside the sensory deprivation chamber:
      - Their ambient messages are suppressed (no rambient fires for them)
      - Their say is blocked (only holder pulses reach them)
      - Room messages from outside don't reach them

    This is a room-level script. The chamber is a separate room entirely
    (like the WombRoom pattern) with a single entrance controlled by the holder.

    The holder uses 'deprive pulse <message>' to send messages inward.
    """

    def at_script_creation(self):
        self.key        = "sensory_deprivation"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 300   # heartbeat every 5 minutes

    def at_repeat(self):
        room = self.obj
        if not room:
            return

        from typeclasses.characters import Character
        for char in room.contents:
            if not isinstance(char, Character):
                continue
            # Ensure say-lock is maintained
            if not getattr(char.db, "deprivation_locked", False):
                char.db.deprivation_locked = True
                char.db.active_speech_filters = list(
                    set(char.db.active_speech_filters or []) | {"cant_speak"}
                )
                char.msg("|xThe chamber closes around you. Nothing reaches in. Nothing gets out.|n")
