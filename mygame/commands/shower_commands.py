"""
Shower commands — Cursed Shower (Bathing Lounge annex).

Commands:
  CmdStartShower   (start shower / shower on)
  CmdStopShower    (stop shower / shower off)
  CmdAdjustTemp    (adjust temp <cold|warm|hot|scalding>)

Internals:
  _load_scenes()       — YAML loader with module-level cache
  _send_scene()        — broadcast a random scene from a phase to the room
  _get_state()         — lazy-init copy of room.db.shower_state dict
  _save_state()        — full-copy write back (avoids _SaverDict mutation issues)
  _update_mirror_fog() — syncs lounge.db.mirror_fogged via the 'out' exit
  _steam_tick()        — 60s self-rescheduling steam level tick
  _ambient_tick()      — 300-600s self-rescheduling ambient scene tick

Mimic delay chain:
  _activate_mimic() → _mimic_opening() → _mimic_rising() →
  _mimic_peak()     → _mimic_climax()  → _mimic_release() → _mimic_wrap()

Shower state (room.db.shower_state):
  running      bool   — water is on
  steam        int    — 0-3
  temp         str    — cold / warm / hot / scalding
  mimic_active bool   — mimic has taken the room
  mimic_phase  str|None
  locked       bool   — door locked by mimic; stop shower is blocked
"""

import os
import random
import yaml

from evennia import Command
from evennia.utils.utils import delay


# ---------------------------------------------------------------------------
# Scene YAML — module-level cache
# ---------------------------------------------------------------------------

_SCENES_CACHE = None
_SCENES_PATH  = os.path.join(
    os.path.dirname(__file__), "..", "world", "mimic_scenes.yaml"
)


def _load_scenes():
    global _SCENES_CACHE
    if _SCENES_CACHE is None:
        try:
            with open(_SCENES_PATH, "r", encoding="utf-8") as fh:
                _SCENES_CACHE = yaml.safe_load(fh) or {}
        except Exception:
            _SCENES_CACHE = {}
    return _SCENES_CACHE


def _send_scene(room, phase):
    """Broadcast a random scene from *phase* to everyone in the room."""
    pool = (_load_scenes().get(phase) or [])
    if not pool:
        return
    room.msg_contents(f"|m{random.choice(pool)}|n")


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

_STATE_DEFAULTS = {
    "running":      False,
    "steam":        0,
    "temp":         "warm",
    "mimic_active": False,
    "mimic_phase":  None,
    "locked":       False,
}


def _get_state(room):
    """Return a plain dict of shower state, filling any missing keys from defaults."""
    raw = room.db.shower_state
    state = dict(_STATE_DEFAULTS)
    if raw:
        state.update({k: v for k, v in raw.items()})
    return state


def _save_state(room, state):
    """Write a fresh dict copy back to room.db to sidestep _SaverDict issues."""
    room.db.shower_state = dict(state)


# ---------------------------------------------------------------------------
# Mirror fog sync
# ---------------------------------------------------------------------------

def _update_mirror_fog(shower_room):
    """
    Look for the 'out' exit on the shower room and fog the lounge mirror
    if steam >= 2.  Clears fog below that threshold.
    """
    lounge = None
    for exit_obj in shower_room.exits:
        if exit_obj.key.lower() in ("out", "lounge", "bathing lounge"):
            lounge = getattr(exit_obj, "destination", None)
            break
    if not lounge:
        return
    state = _get_state(shower_room)
    lounge.db.mirror_fogged = state["steam"] >= 2


# ---------------------------------------------------------------------------
# Steam tick — every 60s, self-rescheduling
# ---------------------------------------------------------------------------

def _steam_tick(room):
    """
    Running: +1 per tick up to 3.
    Stopped: -1 per tick down to 0.
    Reschedules itself until steam is stable.
    """
    state = _get_state(room)
    changed = False

    if state["running"] and state["steam"] < 3:
        state["steam"] += 1
        changed = True
    elif not state["running"] and state["steam"] > 0:
        state["steam"] -= 1
        changed = True

    if changed:
        _save_state(room, state)
        _update_mirror_fog(room)

    # Keep ticking if there's still work to do
    still_rising  = state["running"] and state["steam"] < 3
    still_falling = not state["running"] and state["steam"] > 0
    if still_rising or still_falling:
        delay(60, lambda: _steam_tick(room))


# ---------------------------------------------------------------------------
# Ambient tick — every 5-10 minutes, self-rescheduling
# ---------------------------------------------------------------------------

def _ambient_tick(room):
    """
    Fires a random ambient scene every 5-10 minutes.
    Suppressed while the mimic is active.
    Stops itself when the shower is off.
    """
    state = _get_state(room)
    if not state["running"]:
        return  # shower off — stop the chain

    if not state["mimic_active"]:
        _send_scene(room, "ambient")

    wait = random.randint(300, 600)
    delay(wait, lambda: _ambient_tick(room))


# ---------------------------------------------------------------------------
# Mimic delay chain
# ---------------------------------------------------------------------------

def _activate_mimic(room):
    """
    Called after the initial activation delay.
    Locks the room, broadcasts activation, starts the opening phase.
    """
    state = _get_state(room)
    if not state["running"]:
        return  # shower was stopped before mimic could wake — abort

    state["mimic_active"] = True
    state["mimic_phase"]  = "activation"
    state["locked"]       = True
    _save_state(room, state)

    _send_scene(room, "activation")

    wait = random.randint(15, 25)
    delay(wait, lambda: _mimic_opening(room))


def _mimic_opening(room):
    state = _get_state(room)
    if not state["mimic_active"]:
        return

    state["mimic_phase"] = "opening"
    _save_state(room, state)

    _send_scene(room, "opening")

    count = random.randint(2, 3)
    wait  = random.randint(50, 75)
    delay(wait, lambda: _mimic_rising(room, count))


def _mimic_rising(room, remaining):
    state = _get_state(room)
    if not state["mimic_active"]:
        return

    state["mimic_phase"] = "rising"
    _save_state(room, state)

    _send_scene(room, "rising")

    remaining -= 1
    if remaining > 0:
        wait = random.randint(60, 90)
        delay(wait, lambda: _mimic_rising(room, remaining))
    else:
        count = random.randint(1, 2)
        wait  = random.randint(60, 90)
        delay(wait, lambda: _mimic_peak(room, count))


def _mimic_peak(room, remaining):
    state = _get_state(room)
    if not state["mimic_active"]:
        return

    state["mimic_phase"] = "peak"
    _save_state(room, state)

    _send_scene(room, "peak")

    remaining -= 1
    if remaining > 0:
        wait = random.randint(60, 90)
        delay(wait, lambda: _mimic_peak(room, remaining))
    else:
        wait = random.randint(60, 90)
        delay(wait, lambda: _mimic_climax(room))


def _mimic_climax(room):
    state = _get_state(room)
    if not state["mimic_active"]:
        return

    state["mimic_phase"] = "climax"
    _save_state(room, state)

    _send_scene(room, "climax")

    # Hold at climax for 60-90s before releasing
    wait = random.randint(60, 90)
    delay(wait, lambda: _mimic_release(room))


def _mimic_release(room):
    state = _get_state(room)
    if not state["mimic_active"]:
        return

    state["mimic_phase"] = "release"
    _save_state(room, state)

    _send_scene(room, "release")

    # Brief pause, then wrap up
    wait = random.randint(15, 25)
    delay(wait, lambda: _mimic_wrap(room))


def _mimic_wrap(room):
    """
    End of the mimic sequence.
    Clears the active flag, unlocks the door, turns the shower off.
    """
    state = _get_state(room)
    state["mimic_active"] = False
    state["mimic_phase"]  = None
    state["locked"]       = False
    state["running"]      = False
    _save_state(room, state)

    room.msg_contents(
        "|xThe nozzles cut out. The water stops. Steam drifts upward and thins "
        "toward the ceiling. The door handle cools beneath your palm — and a "
        "soft click, mechanical and final, as the lock releases. The shower is off.|n"
    )
    _update_mirror_fog(room)


# ---------------------------------------------------------------------------
# Temperature tables
# ---------------------------------------------------------------------------

_TEMP_LEVELS = ("cold", "warm", "hot", "scalding")

_TEMP_COLORS = {
    "cold":     "|c",
    "warm":     "|y",
    "hot":      "|y",
    "scalding": "|r",
}

_TEMP_CALLER = {
    "cold":     (
        "|cYou turn the dial down hard. The water runs cold — proper, "
        "sharp cold that hits every nerve at once.|n"
    ),
    "warm":     (
        "|yYou ease the temperature back to a comfortable warm. Steam "
        "settles to a steady drift.|n"
    ),
    "hot":      (
        "|yYou push the dial higher. The water runs properly hot now, "
        "steam thickening with it.|n"
    ),
    "scalding": (
        "|rYou crank the dial to its stop. The water goes scalding — "
        "the steam billows immediately and the room flushes with heat.|n"
    ),
}

_TEMP_ROOM = {
    "cold":     "|cThe shower drops to cold. Steam retreats. The temperature in the room falls noticeably.|n",
    "warm":     "|yThe shower eases back to a comfortable warmth. Steam levels steady.|n",
    "hot":      "|yThe shower runs hot. The steam thickens and the air grows heavy with it.|n",
    "scalding": "|rThe temperature spikes. The shower runs scalding — steam billows hard and fast.|n",
}


# ---------------------------------------------------------------------------
# CmdStartShower
# ---------------------------------------------------------------------------

class CmdStartShower(Command):
    """
    Start the shower.

    Usage:
      start shower
      shower on

    The shower runs warm by default. Adjust the temperature afterward
    with |wadjust temp|n.

    The Cursed Shower has a thirty percent chance of waking up whenever
    the water starts. There is no way to know in advance.
    """

    key     = "start shower"
    aliases = ["shower on"]
    locks   = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        if not room.db.has_shower:
            caller.msg("|xThere's no shower here.|n")
            return

        state = _get_state(room)

        if state["running"]:
            caller.msg("|xThe shower is already running.|n")
            return

        state["running"] = True
        if not state["temp"]:
            state["temp"] = "warm"
        _save_state(room, state)

        c_name = caller.db.rp_name or caller.name
        temp   = state["temp"]
        color  = _TEMP_COLORS.get(temp, "|y")

        caller.msg(
            f"|yYou reach in and turn the shower on. Water rushes from all eleven "
            f"nozzles, {color}{temp}|y and immediate, and steam begins to rise.|n"
        )
        room.msg_contents(
            f"|x{c_name} turns the shower on. Water hisses from the nozzles and "
            f"steam starts to gather.|n",
            exclude=caller,
        )

        # Kick off steam and ambient ticks
        delay(60, lambda: _steam_tick(room))
        delay(random.randint(300, 600), lambda: _ambient_tick(room))

        # 30% chance — mimic wakes after a quiet 20-30s delay
        if random.random() < 0.30:
            delay(random.randint(20, 30), lambda: _activate_mimic(room))


# ---------------------------------------------------------------------------
# CmdStopShower
# ---------------------------------------------------------------------------

class CmdStopShower(Command):
    """
    Turn the shower off.

    Usage:
      stop shower
      shower off

    The shower cannot be shut off while the mimic is active and the
    room is locked.
    """

    key     = "stop shower"
    aliases = ["shower off"]
    locks   = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        if not room.db.has_shower:
            caller.msg("|xThere's no shower here.|n")
            return

        state = _get_state(room)

        if not state["running"]:
            caller.msg("|xThe shower isn't running.|n")
            return

        if state["locked"]:
            caller.msg(
                "|mThe nozzle handle doesn't respond. The door handle is warm and "
                "set in its frame. The mimic has decided how this ends. "
                "You are going to have to wait.|n"
            )
            return

        state["running"] = False
        _save_state(room, state)

        c_name = caller.db.rp_name or caller.name

        caller.msg(
            "|xYou shut the shower off. The water cuts out. Steam drifts upward "
            "and begins to thin. The room is quiet.|n"
        )
        room.msg_contents(
            f"|x{c_name} shuts the shower off. The water stops.|n",
            exclude=caller,
        )

        # Steam will drain on its own via the existing tick
        _update_mirror_fog(room)


# ---------------------------------------------------------------------------
# CmdAdjustTemp
# ---------------------------------------------------------------------------

class CmdAdjustTemp(Command):
    """
    Adjust the shower temperature.

    Usage:
      adjust temp <cold|warm|hot|scalding>

    The shower must be running. Temperature affects steam level and
    the general atmosphere of the room.

    Scalding pushes the steam level up immediately. Cold pulls it down.
    """

    key     = "adjust temp"
    aliases = ["adjust temperature", "temp"]
    locks   = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        if not room.db.has_shower:
            caller.msg("|xThere's no shower here.|n")
            return

        state = _get_state(room)

        if not state["running"]:
            caller.msg("|xThe shower isn't running. Start it first.|n")
            return

        arg = self.args.strip().lower()
        if arg not in _TEMP_LEVELS:
            opts = ", ".join(_TEMP_LEVELS)
            caller.msg(f"|xValid temperatures: {opts}|n")
            return

        if arg == state["temp"]:
            caller.msg(f"|xThe shower is already running {arg}.|n")
            return

        state["temp"] = arg
        _save_state(room, state)

        c_name = caller.db.rp_name or caller.name
        caller.msg(_TEMP_CALLER[arg])
        room.msg_contents(_TEMP_ROOM[arg], exclude=caller)

        # Scalding: bump steam up immediately if not maxed
        if arg == "scalding":
            state = _get_state(room)
            if state["steam"] < 3:
                state["steam"] = min(3, state["steam"] + 1)
                _save_state(room, state)
                _update_mirror_fog(room)

        # Cold: drop steam one level immediately
        elif arg == "cold":
            state = _get_state(room)
            if state["steam"] > 0:
                state["steam"] = max(0, state["steam"] - 1)
                _save_state(room, state)
                _update_mirror_fog(room)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_SHOWER_CMDS = [CmdStartShower, CmdStopShower, CmdAdjustTemp]
