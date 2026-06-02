"""
typeclasses/cycle_script.py

CycleScript — drives an automated machine cycle.

Attaches to the TARGET character.  Reads installed attachments from the
room's machine zone mechanics dict and runs phases in order.  Loops until
the target uses 'endcycle' (bypass-restraint command).

Phases (only run if the corresponding attachment is installed):
  restrain    — engages the zone's restraint mechanic
  milk        — creates a MilkingSessionScript for milk_duration seconds
  inseminate  — deposits via InseminationAttachment config
  boost       — administers an internal serum dose (perm size+rate boost)
  rest        — waits rest_duration before looping

Setup:
  The machine zone must have:
    mechanics["milking_machine"]  installed (for the cycle to start)
    mechanics["restraint"]        installed (optional — skipped if absent)
    mechanics["insemination"]     installed (optional — skipped if absent)
    cycle_mode = True             flag on the machine zone mechanics dict

Start the cycle via: the machine's start command with cycle_mode=True
  (or @py on the target)

Stop via: endcycle  (bypass-restraint, always available)

Serum doses:
  The machine has an internal serum supply — no item consumption.
  Boost defaults to: +0.10 size, +3.0 ml/tick production per cycle.
  Configure via zone mechanics: cycle_boost_size, cycle_boost_rate.
"""

import time
from evennia import DefaultScript


_PHASE_ORDER = ["restrain", "milk", "inseminate", "boost", "rest"]


class CycleScript(DefaultScript):
    """Automated machine cycle driver."""

    def at_script_creation(self):
        self.key        = "cycle_machine"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 15   # check every 15s

        self.db.machine_zone    = None   # zone name where machine is installed
        self.db.phase           = "rest"
        self.db.phase_started   = 0.0
        self.db.cycle_count     = 0
        self.db.milk_session_id = None   # dbref of running MilkingSessionScript

        # Phase durations (seconds) — configurable
        self.db.phase_durations = {
            "restrain":   10,
            "milk":       300,   # 5 minutes
            "inseminate": 60,
            "boost":      30,
            "rest":       120,   # 2 minutes between cycles
        }

    # ------------------------------------------------------------------

    def at_repeat(self):
        target = self.obj
        if not target or not hasattr(target, "db"):
            self.stop()
            return

        room = target.location
        if not room:
            self.stop()
            return

        # Find the machine zone
        machine_zone = self.db.machine_zone
        if not machine_zone:
            from typeclasses.milking_machine_mechanic import MilkingMachineMechanic
            machine_zone, _ = MilkingMachineMechanic.find_in_room(room)
            if not machine_zone:
                self._end("The machine is no longer present.", room)
                return
            self.db.machine_zone = machine_zone

        zones     = room.db.zones or {}
        zone_data = zones.get(machine_zone, {})
        mechanics = zone_data.get("mechanics", {}) or {}

        # Check if phase time has elapsed
        elapsed = time.time() - (self.db.phase_started or 0.0)
        phase   = self.db.phase or "rest"
        dur     = (self.db.phase_durations or {}).get(phase, 60)

        if elapsed < dur:
            return   # still in current phase

        # Advance to next phase
        self._advance_phase(target, room, mechanics)

    def _advance_phase(self, target, room, mechanics):
        phase = self.db.phase or "rest"
        phases = self._active_phases(mechanics)

        # Move to next phase
        try:
            idx = phases.index(phase)
            next_phase = phases[(idx + 1) % len(phases)]
        except (ValueError, ZeroDivisionError):
            next_phase = "rest"

        # Wrap = new cycle
        if next_phase == phases[0]:
            self.db.cycle_count = (self.db.cycle_count or 0) + 1

        self.db.phase        = next_phase
        self.db.phase_started = time.time()
        self._run_phase(next_phase, target, room, mechanics)

    def _active_phases(self, mechanics: dict) -> list:
        """Return phases that have matching mechanics installed."""
        phases = []
        if mechanics.get("restraint"):
            phases.append("restrain")
        if mechanics.get("milking_machine"):
            phases.append("milk")
        if mechanics.get("insemination"):
            phases.append("inseminate")
        # boost always available (internal serum)
        phases.append("boost")
        phases.append("rest")
        return phases or ["rest"]

    def _run_phase(self, phase, target, room, mechanics):
        target_name = target.db.rp_name or target.name

        if phase == "restrain":
            from world.milking_loader import pick_cycle_message
            msg = pick_cycle_message("restrain") or "The machine engages — restraints lock around {target}."
            room.msg_contents(f"|x{msg.replace('{target}', target_name)}|n")

        elif phase == "milk":
            # Stop any existing milk session first
            from typeclasses.milking_session_script import MilkingSessionScript
            from evennia.utils import create
            from world.milking_loader import get_speed_config, pick_message

            for scr in list(target.scripts.all()):
                if isinstance(scr, MilkingSessionScript):
                    scr.stop()

            config = get_speed_config()
            speed  = "steady"
            start_msg = pick_message(speed, "start")
            if start_msg:
                room.msg_contents(start_msg.replace("{target}", target_name))

            script = create.create_script(
                MilkingSessionScript,
                obj=target,
                autostart=False,
                persistent=True,
            )
            script.db.speed          = speed
            script.db.operator_dbref = None
            script.db.zone_filter    = None
            script.interval          = config.get(speed, {}).get("interval_seconds", 30)
            script.start()
            self.db.milk_session_id = script.dbref

        elif phase == "inseminate":
            # Stop milk session first
            self._stop_milk(target)
            from typeclasses.insemination_item import do_inseminate
            insem_config = (mechanics.get("insemination") or {})
            # Find target's orifice zone
            target_zones = getattr(target.db, "zones", None) or {}
            orifice = next(
                (zn for zn, zd in target_zones.items()
                 if zd.get("zone_type") in ("orifice", "both")),
                None
            )
            if orifice:
                msg = do_inseminate(None, target, orifice, insem_config)
                if msg:
                    room.msg_contents(f"|x{msg}|n")

        elif phase == "boost":
            self._stop_milk(target)
            self._apply_boost(target, room, mechanics)

        elif phase == "rest":
            self._stop_milk(target)
            cycle = self.db.cycle_count or 1
            from world.milking_loader import pick_cycle_message
            msg = pick_cycle_message("rest") or "The machine enters rest phase after cycle {cycle}. It will resume shortly."
            room.msg_contents(
                f"|x{msg.replace('{target}', target_name).replace('{cycle}', str(cycle))}|n"
            )

    def _stop_milk(self, target):
        from typeclasses.milking_session_script import MilkingSessionScript
        for scr in list(target.scripts.all()):
            if isinstance(scr, MilkingSessionScript):
                scr.stop()

    def _apply_boost(self, target, room, mechanics):
        """Apply internal serum boost — permanent size and rate increment."""
        target_name = target.db.rp_name or target.name
        zones       = getattr(target.db, "zones", None) or {}
        zone_data   = room.db.zones.get(self.db.machine_zone or "", {}) if room.db.zones else {}
        mech        = zone_data.get("mechanics", {}) or {}

        size_inc = mech.get("cycle_boost_size", 0.10)
        rate_inc = mech.get("cycle_boost_rate", 3.0)

        from evennia import search_object
        from typeclasses.body_mod_item import BodyModItem
        from typeclasses.production_item import ProductionItem

        for zn, zd in zones.items():
            bm_entry = (zd.get("mechanics", {}) or {}).get("body_mod")
            if bm_entry:
                results = search_object(bm_entry.get("item_dbref", ""), exact=True)
                if results and isinstance(results[0], BodyModItem):
                    results[0].apply_permanent_boost(size_inc)
            prod_entry = (zd.get("mechanics", {}) or {}).get("production")
            if prod_entry:
                results = search_object(prod_entry.get("item_dbref", ""), exact=True)
                if results and isinstance(results[0], ProductionItem):
                    old_rate = results[0].db.base_rate_ml_per_tick or 8.0
                    results[0].db.base_rate_ml_per_tick = old_rate + rate_inc

        from world.milking_loader import pick_cycle_message
        msg = pick_cycle_message("boost") or "The machine administers a growth compound to {target}."
        room.msg_contents(
            f"|x{msg.replace('{target}', target_name)}|n"
            f"|x(+{size_inc:.2f} size, +{rate_inc:.1f}ml/tick — permanent)|n"
        )

    def _end(self, reason, room):
        if room and reason:
            room.msg_contents(f"|x{reason}|n")
        self.stop()

    def at_stop(self):
        target = self.obj
        if target:
            self._stop_milk(target)
            room = target.location
            if room:
                target_name = target.db.rp_name or target.name
                from world.milking_loader import pick_cycle_message
                msg = pick_cycle_message("end") or "The machine cycle has ended for {target}."
                room.msg_contents(
                    f"|x{msg.replace('{target}', target_name)}|n"
                )
