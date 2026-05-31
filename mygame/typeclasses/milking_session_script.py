"""
typeclasses/milking_session_script.py

MilkingSessionScript — drives an active milking machine session.

Attached to the target character via:
    script = create_script(MilkingSessionScript, obj=target, autostart=False)
    script.db.speed = "steady"
    script.db.operator_dbref = caller.dbref
    script.db.zone_filter = None   # or a zone name string to filter
    script.interval = config["interval_seconds"]
    script.start()

Lifecycle per tick (at_repeat):
  1. Find production items on the target (via zone mechanics dict).
  2. Extract ml_per_session_tick from each item, up to what's available.
  3. Deposit extracted fluid into existing bottles in the room (or create new).
  4. Pick a message from the appropriate pool (running / first_empty /
     running_empty) and broadcast it to the room.
  5. Update the machine state's session_output_ml counter.

Session ends when:
  - milk/stop is called (CmdMilk handles messaging then calls script.stop())
  - The machine mechanic is no longer found in the room
  - No production items found on the target

Speed is updated via set_speed(), which adjusts self.interval and restarts
the timer without losing session state.
"""

from evennia import DefaultScript


class MilkingSessionScript(DefaultScript):
    """Drives a milking machine session on its target character."""

    def at_script_creation(self):
        self.key        = "milking_session"
        self.persistent = True
        self.repeats    = 0    # run forever until stopped
        self.interval   = 30   # overwritten by CmdMilk before start()

        self.db.speed           = "steady"
        self.db.operator_dbref  = None
        self.db.zone_filter     = None   # optional zone name filter
        self.db.session_ml      = 0.0
        self.db.running_empty   = False  # True once all items are empty

    # ------------------------------------------------------------------
    # Speed control
    # ------------------------------------------------------------------

    def set_speed(self, speed: str):
        """
        Update speed and reset the interval timer.

        Evennia's DefaultScript has no restart() method — we stop/start
        manually, using ndb._restarting to signal at_stop() to skip cleanup.
        """
        from world.milking_loader import get_speed_config
        config = get_speed_config()
        if speed not in config:
            return
        self.db.speed    = speed
        self.interval    = config[speed]["interval_seconds"]
        self.ndb._restarting = True
        self.stop()
        self.ndb._restarting = False
        self.start()

    # ------------------------------------------------------------------
    # Per-tick extraction
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

        # Verify machine still exists in the room
        from typeclasses.milking_machine_mechanic import MilkingMachineMechanic
        machine_zone, state = MilkingMachineMechanic.find_in_room(room)
        if not state:
            room.msg_contents("|xThe milking machine is no longer present — session ended.|n")
            self.stop()
            return

        speed  = self.db.speed or "steady"
        target_name = target.db.rp_name or target.name

        # ── Load speed config ─────────────────────────────────────────
        from world.milking_loader import get_speed_config, pick_message
        config        = get_speed_config()
        ml_per_tick   = config.get(speed, {}).get("ml_per_session_tick", 10.0)

        # ── Find production items ─────────────────────────────────────
        from evennia import search_object
        from typeclasses.production_item import ProductionItem

        zones       = getattr(target.db, "zones", None) or {}
        zone_filter = self.db.zone_filter
        prod_items  = []

        for zn, zd in zones.items():
            if zone_filter and zn != zone_filter:
                continue
            mechanics = zd.get("mechanics", {}) or {}
            entry     = mechanics.get("production")
            if not entry:
                continue
            results = search_object(entry.get("item_dbref", ""), exact=True)
            if results and isinstance(results[0], ProductionItem):
                prod_items.append((zn, results[0]))

        if not prod_items:
            room.msg_contents(
                f"|x{target_name} has no production items — milking session ended.|n"
            )
            self.stop()
            return

        # ── Extract from each item ────────────────────────────────────
        by_type         = {}   # fluid_type → [ml, flavor]
        was_empty       = self.db.running_empty
        all_empty_now   = True

        import random
        for zn, prod in prod_items:
            available  = prod.db.current_volume_ml or 0.0
            # ±30% variance — the machine doesn't pull a perfectly constant amount
            variance   = random.uniform(0.70, 1.30)
            extract    = min(ml_per_tick * variance, available)
            if extract > 0:
                prod.db.current_volume_ml = max(0.0, available - extract)
                prod.reset_fullness_notifications()
                all_empty_now = False

                ft     = prod.db.fluid_type   or "fluid"
                flavor = prod.db.fluid_flavor
                if ft not in by_type:
                    by_type[ft] = [0.0, flavor]
                by_type[ft][0] += extract
                if by_type[ft][1] is None and flavor:
                    by_type[ft][1] = flavor

        total_ml = sum(v[0] for v in by_type.values())
        self.db.session_ml = (self.db.session_ml or 0.0) + total_ml

        # ── Deposit to bottles ────────────────────────────────────────
        if total_ml > 0:
            self._deposit_to_bottles(target, room, by_type, target_name)

        # ── Pick message pool ─────────────────────────────────────────
        if all_empty_now and not was_empty:
            pool = "first_empty"
            self.db.running_empty = True
        elif all_empty_now:
            pool = "running_empty"
        else:
            self.db.running_empty = False
            pool = "running"

        msg = pick_message(speed, pool)
        if msg:
            room.msg_contents(msg.replace("{target}", target_name))

        # ── Session tally line ────────────────────────────────────────
        if total_ml > 0:
            from typeclasses.production_item import format_volume
            room.msg_contents(
                f"|x  +{format_volume(total_ml)} this cycle — "
                f"session total: {format_volume(self.db.session_ml)}|n"
            )

        # ── Update machine state ──────────────────────────────────────
        MilkingMachineMechanic.set_state(
            room, machine_zone,
            session_output_ml=self.db.session_ml,
        )

    # ------------------------------------------------------------------
    # Bottle management
    # ------------------------------------------------------------------

    def _deposit_to_bottles(self, target, room, by_type, target_name):
        """
        Add extracted fluid to an existing bottle in the room (by producer
        and type) or create a new one if none exists.
        """
        from typeclasses.fluid_bottle import FluidBottle
        from evennia import create_object
        from typeclasses.production_item import format_volume

        for ft, (ml, flavor) in by_type.items():
            if ml <= 0:
                continue

            # Find an existing non-empty bottle for this target/type in the room
            bottle = None
            for obj in room.contents:
                if (
                    isinstance(obj, FluidBottle)
                    and not obj.db.is_empty
                    and (obj.db.volume_ml or 0) > 0
                    and obj.db.producer_name == target_name
                    and obj.db.fluid_type == ft
                ):
                    bottle = obj
                    break

            if bottle:
                bottle.db.volume_ml = (bottle.db.volume_ml or 0.0) + ml
            else:
                bottle = create_object(
                    FluidBottle,
                    key=f"bottle of {target_name}'s {ft}",
                    location=room,
                )
                bottle.db.producer_name = target_name
                bottle.db.fluid_type    = ft
                bottle.db.fluid_flavor  = flavor
                bottle.db.volume_ml     = ml
                room.msg_contents(
                    f"|xA bottle of {target_name}'s {ft} appears on the machine tray.|n"
                )

    # ------------------------------------------------------------------
    # Cleanup on stop
    # ------------------------------------------------------------------

    def at_stop(self):
        """
        Mark the machine inactive when the session fully ends.
        Skipped during set_speed() stop/start cycles (ndb._restarting=True).
        """
        if getattr(self.ndb, "_restarting", False):
            return   # just a speed change restart — don't clean up
        target = self.obj
        if not target:
            return
        room = target.location
        if not room:
            return
        from typeclasses.milking_machine_mechanic import MilkingMachineMechanic
        machine_zone, state = MilkingMachineMechanic.find_in_room(room)
        if state:
            MilkingMachineMechanic.set_state(
                room, machine_zone,
                active=False, operator=None, target=None,
            )
