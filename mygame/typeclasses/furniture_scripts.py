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


# ---------------------------------------------------------------------------
# EdgeMachineScript
# ---------------------------------------------------------------------------

_EDGE_MSGS_PRIVATE = [
    "The machine holds you exactly where it has you — right at the edge, no further. It does not lose track.",
    "You are at ninety-nine and the machine knows it and is not giving you the last point. The pressure does not ease.",
    "Right there. The machine keeps you right there. The release is present and unreachable.",
    "The edge is precise. The machine is precise. You stay exactly at it.",
    "You push against the ceiling the machine has set and it does not move. Neither do you.",
]

_EDGE_MSGS_ROOM = [
    "{name} is very still — a concentrated stillness, held in place by something specific.",
    "Something in {name}'s posture has found its limit and stopped there.",
    "{name} breathes carefully — measured, controlled, working around something.",
]

_EDGE_NEAR_MSGS = [
    "The machine is taking you toward the edge. Approach is not the same as arrival.",
    "Ninety. The machine has noted this and is adjusting its pace.",
    "Close. The machine keeps it close. The interval changes.",
    "The pressure builds toward the ceiling the machine has set.",
]


class EdgeMachineScript(DefaultScript):
    """
    Holds an occupant at arousal 99 — just short of climax.
    Release requires: holder says configured release word, or 'endedge' command.

    Attaches to a room. Zone set via room.db.edge_machine_zone.
    """

    def at_script_creation(self):
        self.key        = "edge_machine"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 30   # check every 30 seconds

    def at_repeat(self):
        room = self.obj
        if not room:
            return

        zone_name = getattr(room.db, "edge_machine_zone", None)
        if not zone_name:
            return

        # Find occupants in the zone
        from typeclasses.characters import Character
        from typeclasses.arousal_script import add_arousal

        for char in room.contents:
            if not isinstance(char, Character):
                continue

            # Check if they're seated/restrained in the target zone
            # (uses seat mechanic occupant tracking)
            occupied_zone = getattr(char.db, "seated_zone", None) or getattr(char.db, "restrained_zone", None)
            if occupied_zone != zone_name:
                continue

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
            char.msg("|xThe edge machine releases you.|n")


# ---------------------------------------------------------------------------
# MilkingStanchionScript
# ---------------------------------------------------------------------------

_STANCHION_LOCK_MSGS = [
    "The stanchion closes around you — frame at the neck, bar at the hips. You are not going anywhere.",
    "The stanchion locks you in place. The milking attachments find their positions automatically.",
    "A mechanical click as the stanchion secures. You are positioned, held, and ready to be milked.",
]

_STANCHION_RELEASE_MSGS = [
    "The stanchion releases. The frame opens and the attachments retract.",
    "The locks on the stanchion open. You are free to move.",
    "The stanchion releases you — frame, bar, and attachments all retracting.",
]


class MilkingStanchionScript(DefaultScript):
    """
    Restrains the occupant and auto-starts a milking session.
    Releases when milking is complete or occupant uses 'endmilk'.

    Attaches to a room. Zone set via room.db.stanchion_zone.
    """

    def at_script_creation(self):
        self.key        = "milking_stanchion"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 10   # check every 10 seconds

    def at_repeat(self):
        room = self.obj
        if not room:
            return

        zone_name = getattr(room.db, "stanchion_zone", None)
        if not zone_name:
            return

        from typeclasses.characters import Character
        from typeclasses.milking_session_script import MilkingSessionScript
        from evennia.utils import create
        from world.milking_loader import get_speed_config, pick_message

        for char in room.contents:
            if not isinstance(char, Character):
                continue

            occupied_zone = getattr(char.db, "seated_zone", None) or getattr(char.db, "restrained_zone", None)
            if occupied_zone != zone_name:
                continue

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
    "{name} is displayed on the pedestal — elevated, lit, every line of them visible.",
    "{name} stands on the pedestal. The room's attention organizes around them.",
    "The pedestal holds {name} above the floor level. There is nowhere to look that isn't toward them.",
]


class DisplayPedestalScript(DefaultScript):
    """
    When occupied, applies exhibition effect to the occupant and fires
    periodic room messages drawing attention to them.

    Attaches to a room. Zone set via room.db.pedestal_zone.
    """

    def at_script_creation(self):
        self.key        = "display_pedestal"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 120   # check every 2 minutes

    def at_repeat(self):
        room = self.obj
        if not room:
            return

        zone_name = getattr(room.db, "pedestal_zone", None)
        if not zone_name:
            return

        from typeclasses.characters import Character
        for char in room.contents:
            if not isinstance(char, Character):
                continue

            occupied = getattr(char.db, "seated_zone", None) or getattr(char.db, "restrained_zone", None)
            if occupied != zone_name:
                # Remove exhibition if they left
                if getattr(char.db, "on_pedestal", False):
                    char.db.on_pedestal       = False
                    char.db.exhibition_active = False
                continue

            # Apply exhibition effect
            if not getattr(char.db, "on_pedestal", False):
                char.db.on_pedestal       = True
                char.db.exhibition_active = True
                char.db.outfit_camouflage = ""
                cname = char.db.rp_name or char.name
                room.msg_contents(
                    f"|x{cname} steps onto the pedestal. The exhibition effect is immediate and total.|n"
                )

            # Periodic display message
            cname = char.db.rp_name or char.name
            room.msg_contents(random.choice(_PEDESTAL_MSGS).format(name=cname))


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
