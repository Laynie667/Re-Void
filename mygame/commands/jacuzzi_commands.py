"""
commands/jacuzzi_commands.py

Player and host commands for Helena's Log Cabin Jacuzzi.

Commands available to any player in a has_jacuzzi room:
    jets on / jets off          — start or stop the jets
    adjust jets <level>         — off / gentle / strong / full

Host-only commands (requires room.db.jacuzzi_host_id match or Builder perm):
    panel                       — show current state
    panel temp <level>          — lukewarm / warm / hot / scalding
    panel lock                  — lock the toe seats (engages DildoSeatMechanic lock)
    panel release               — release the toe seats
    panel activate              — flag dildos as active (future: vibration etc.)
    panel deactivate            — flag dildos as inactive

State is stored in room.db.jacuzzi_state as a dict.
The room must have room.db.has_jacuzzi = True to respond to any of these.

Install on the Jacuzzi room once:
    @set here/has_jacuzzi = 1
    @set here/jacuzzi_host_id = <Helena's character dbid>
    @py self.location.scripts.add("typeclasses.jacuzzi_script.JacuzziStateScript")
"""

from evennia import Command


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

_STATE_DEFAULTS = {
    "running":       False,
    "jets":          "off",       # off / gentle / strong / full
    "temp":          "hot",       # lukewarm / warm / hot / scalding
    "seats_locked":  False,
    "dildos_active": False,
}

_JETS_LEVELS = ("off", "gentle", "strong", "full")
_TEMP_LEVELS = ("lukewarm", "warm", "hot", "scalding")


def _get_state(room):
    """Lazy-init and return the full jacuzzi state dict (safe copy)."""
    raw = room.db.jacuzzi_state
    if not raw or not hasattr(raw, "items"):
        room.db.jacuzzi_state = dict(_STATE_DEFAULTS)
        return dict(_STATE_DEFAULTS)
    state = dict(_STATE_DEFAULTS)
    state.update({k: v for k, v in raw.items() if k in _STATE_DEFAULTS})
    return state


def _save_state(room, state):
    """Write state back through a full dict copy for _SaverDict persistence."""
    room.db.jacuzzi_state = dict(state)


def _set_seat_lock(room, locked):
    """
    Set seats_locked in the jacuzzi state dict AND stamp the locked flag
    directly into the 'seats' zone's mechanic dict.

    The DildoSeatMechanic lock check (_check_dildo_seat_locked in
    mechanic_commands.py) reads seat["locked"] from the zone dict,
    so both must be kept in sync.
    """
    state = _get_state(room)
    state["seats_locked"] = locked
    _save_state(room, state)

    zones = room.db.zones or {}
    if "seats" not in zones:
        return
    zone_data = zones["seats"]
    zone      = dict(zone_data) if hasattr(zone_data, "items") else {}
    mechanics = dict(zone.get("mechanics", {}) or {})
    seat      = dict(mechanics.get("seat", {}))
    seat["locked"]    = locked
    mechanics["seat"] = seat
    zone["mechanics"] = mechanics
    zones_copy = dict(zones)
    zones_copy["seats"] = zone
    room.db.zones = zones_copy


# ---------------------------------------------------------------------------
# CmdJets
# ---------------------------------------------------------------------------

class CmdJets(Command):
    """
    Turn the jacuzzi jets on or off.

    Usage:
      jets on
      jets off

    Turning jets on starts them at whatever level was last set (gentle
    if never adjusted). Turning them off stills the water entirely.
    """

    key   = "jets"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room or not room.db.has_jacuzzi:
            caller.msg("|xThere's no jacuzzi here.|n")
            return

        arg = self.args.strip().lower()
        if arg not in ("on", "off"):
            caller.msg("|xUsage: |wjets on|n or |wjets off|n")
            return

        state     = _get_state(room)
        char_name = caller.db.rp_name or caller.name

        if arg == "off":
            if not state["running"]:
                caller.msg("|xThe jacuzzi isn't running.|n")
                return
            state["running"] = False
            state["jets"]    = "off"
            _save_state(room, state)
            caller.msg(
                "|xYou ease the jet control back. The water stills gradually, "
                "the surface settling into slow rolls.|n"
            )
            room.msg_contents(
                f"|x{char_name} turns the jets off. The water loses its urgency.|n",
                exclude=caller,
            )

        else:  # on
            if state["running"]:
                caller.msg("|xThe jets are already running.|n")
                return
            if state["jets"] == "off":
                state["jets"] = "gentle"
            state["running"] = True
            _save_state(room, state)
            level = state["jets"]
            caller.msg(
                f"|xYou start the jets. The water breaks into motion — "
                f"{level} current pushing from the walls.|n"
            )
            room.msg_contents(
                f"|xThe jets start. The water surface breaks into a {level} current.|n",
                exclude=caller,
            )


# ---------------------------------------------------------------------------
# CmdAdjustJets
# ---------------------------------------------------------------------------

class CmdAdjustJets(Command):
    """
    Adjust the jet intensity without stopping them entirely.

    Usage:
      adjust jets <off|gentle|strong|full>

    Setting level to 'off' is equivalent to 'jets off'.
    Setting any other level while jets are off will start them.
    """

    key   = "adjust jets"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room or not room.db.has_jacuzzi:
            caller.msg("|xThere's no jacuzzi here.|n")
            return

        arg = self.args.strip().lower()
        if not arg or arg not in _JETS_LEVELS:
            levels = " | ".join(_JETS_LEVELS)
            caller.msg(f"|xUsage: |wadjust jets <{levels}>|n")
            return

        state     = _get_state(room)
        char_name = caller.db.rp_name or caller.name
        old_level = state["jets"]

        if arg == old_level and state["running"] == (arg != "off"):
            caller.msg(f"|xThe jets are already at {arg}.|n")
            return

        state["jets"]    = arg
        state["running"] = arg != "off"
        _save_state(room, state)

        _msgs = {
            "off": (
                "|xYou bring the jets down to nothing. The water settles.|n",
                f"|x{char_name} dials the jets off. The water stills.|n",
            ),
            "gentle": (
                "|xYou ease the jets to a low, steady current. The water moves "
                "without urgency.|n",
                f"|x{char_name} adjusts the jets. The current settles to something gentle.|n",
            ),
            "strong": (
                "|xYou push the jets up. The water breaks harder against the "
                "walls now, the current continuous.|n",
                f"|x{char_name} turns the jets up. The water churns.|n",
            ),
            "full": (
                "|rYou push the jets to full. The water fills the tub with "
                "competing currents and serious heat-moving intention.|n",
                f"|x{char_name} sets the jets to full. The water moves with force.|n",
            ),
        }
        private, room_msg = _msgs[arg]
        caller.msg(private)
        room.msg_contents(room_msg, exclude=caller)


# ---------------------------------------------------------------------------
# CmdPanel
# ---------------------------------------------------------------------------

class CmdPanel(Command):
    """
    Interface with the silver jacuzzi control panel.
    Requires being the designated host or having Builder permissions.

    Usage:
      panel                      — show current state readout
      panel temp <level>         — set water temperature
                                   (lukewarm / warm / hot / scalding)
      panel lock                 — lock the toe seats
      panel release              — release the toe seats
      panel activate             — flag seat fixtures as active
      panel deactivate           — flag seat fixtures as inactive

    The panel is mounted flush to the rim on the throne's left side.
    The host has the key.
    """

    key   = "panel"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room or not room.db.has_jacuzzi:
            caller.msg("|xThere's no panel here.|n")
            return

        # Host / Builder check
        host_id = room.db.jacuzzi_host_id
        is_host = (
            (host_id and caller.id == int(host_id))
            or caller.check_permstring("Builders")
        )
        if not is_host:
            caller.msg(
                "|xThe panel lid is smooth under your fingers — flush, sealed, "
                "the keyhole small and specific. You don't have the key.|n"
            )
            return

        args = self.args.strip().lower()

        # ── No args: status readout ──────────────────────────────────────
        if not args:
            state = _get_state(room)
            running_str  = "|wyes|n" if state["running"] else "|xno|n"
            locked_str   = "|rLOCKED|n" if state["seats_locked"] else "|xreleased|n"
            active_str   = "|mactive|n" if state["dildos_active"] else "|xinactive|n"
            caller.msg(
                f"|w[Jacuzzi Panel]|n\n"
                f"  Running  : {running_str}\n"
                f"  Jets     : |w{state['jets']}|n\n"
                f"  Temp     : |w{state['temp']}|n\n"
                f"  Seats    : {locked_str}\n"
                f"  Fixtures : {active_str}"
            )
            return

        # ── panel temp <level> ───────────────────────────────────────────
        if args.startswith("temp"):
            level = args[4:].strip()
            if level not in _TEMP_LEVELS:
                levels = " | ".join(_TEMP_LEVELS)
                caller.msg(f"|xUsage: |wpanel temp <{levels}>|n")
                return
            state = _get_state(room)
            state["temp"] = level
            _save_state(room, state)
            _temp_msgs = {
                "lukewarm": (
                    "|xYou dial the temperature down. The water will cool to a mild warmth.|n",
                    "|xThe water temperature shifts — noticeably cooler.|n",
                ),
                "warm": (
                    "|xYou set the temperature to a comfortable warmth.|n",
                    "|xThe water temperature shifts toward something comfortable.|n",
                ),
                "hot": (
                    "|xYou bring the temperature up. The water will hold a proper heat.|n",
                    "|xThe water grows perceptibly hotter.|n",
                ),
                "scalding": (
                    "|rYou push the temperature dial to its upper range. "
                    "The water will become genuinely punishing.|n",
                    "|rThe water temperature climbs sharply.|n",
                ),
            }
            priv, pub = _temp_msgs[level]
            caller.msg(priv)
            room.msg_contents(pub, exclude=caller)
            return

        # ── panel lock ───────────────────────────────────────────────────
        if args == "lock":
            state = _get_state(room)
            if state["seats_locked"]:
                caller.msg("|xThe seats are already locked.|n")
                return
            _set_seat_lock(room, True)
            caller.msg(
                "|mYou engage the seat locks. The toe seats will not release "
                "without the panel.|n"
            )
            room.msg_contents(
                "|mSomething changes in the seat beneath you — a faint resistance "
                "that wasn't there before, deep and definite.|n",
                exclude=caller,
            )
            return

        # ── panel release ────────────────────────────────────────────────
        if args == "release":
            state = _get_state(room)
            if not state["seats_locked"]:
                caller.msg("|xThe seats are not locked.|n")
                return
            _set_seat_lock(room, False)
            caller.msg("|xYou release the seat locks.|n")
            room.msg_contents(
                "|xThe resistance in the toe seats eases. "
                "Whatever was holding you shifts and releases.|n",
                exclude=caller,
            )
            return

        # ── panel activate ───────────────────────────────────────────────
        if args == "activate":
            state = _get_state(room)
            if state["dildos_active"]:
                caller.msg("|xThe fixtures are already active.|n")
                return
            state["dildos_active"] = True
            _save_state(room, state)
            caller.msg("|mYou toggle the third switch. The fixtures respond.|n")
            room.msg_contents(
                "|mThe seat beneath you changes — something shifts in what "
                "it's doing, more present than before.|n",
                exclude=caller,
            )
            return

        # ── panel deactivate ─────────────────────────────────────────────
        if args == "deactivate":
            state = _get_state(room)
            if not state["dildos_active"]:
                caller.msg("|xThe fixtures are already inactive.|n")
                return
            state["dildos_active"] = False
            _save_state(room, state)
            caller.msg("|xYou switch the fixtures off.|n")
            room.msg_contents(
                "|xThe seat beneath you stills — back to passive.|n",
                exclude=caller,
            )
            return

        caller.msg(
            "|xUnknown panel command.\n"
            "|xOptions: |wpanel temp <level>|x, |wpanel lock|x, "
            "|wpanel release|x, |wpanel activate|x, |wpanel deactivate|n"
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_JACUZZI_CMDS = [CmdJets, CmdAdjustJets, CmdPanel]
