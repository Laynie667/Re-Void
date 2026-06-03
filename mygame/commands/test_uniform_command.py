"""
commands/test_uniform_command.py

CmdTestUniform — puts on your testing uniform.

Runs the full test build with random selections so you don't know
exactly what you're wearing until you ask the Adjudicator.

In-game:
  testuniform        — full blind setup with Adjudicator
  testuniform/reset  — runs the reset script (all flags must be done first)
  testuniform/force  — force reset regardless of flags
"""

import random
from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand


_COLLAR_POOL = [
    ("puppy_collar",   "puppy"),
    ("kitty_collar",   "kitty"),
    ("pony_collar",    "pony"),
    ("degrading_leather", "puppy"),
    ("degrading_silk",    "kitty"),
    ("training_collar",   "puppy"),
]

_PLUG_POOL = [
    "metal_plug",
    "knotted_plug",
    "glass_plug",
    "spiral_plug",
    "large_plug",
    "flared_plug",
]

_FILTER_POOL = [
    "third_person",
    "stutter",
    "baby_talk",
    "no_negatives",
    "third_person_coy",
    "animal_sounds",
]

_OPENER_LINES = [
    "Something settles around you. Several somethings, actually. The Adjudicator is taking notes.",
    "The uniform goes on. You're not sure exactly what that means yet. The Adjudicator is.",
    "Things are being applied. The Adjudicator has a list. You don't.",
    "The calibration session has begun. Your testing uniform is in place. Ask the Adjudicator what that means.",
    "It's done. You're dressed — in the loosest possible sense of the word. The Adjudicator knows the details.",
]

_ADJUDICATOR_OPENERS = [
    "\"Selections made. Thirteen systems active. You'll find out what's on you when you ask.\"",
    "\"The uniform is on. I have the list. You know how to ask for it.\"",
    "\"Everything is in place. Your questions are welcome. Your assumptions are not.\"",
    "\"Calibration complete — the setup portion, at least. The work begins now.\"",
]


class CmdTestUniform(MuxCommand):
    """
    Put on your testing uniform.

    Usage:
      testuniform           — full test setup, randomized, Adjudicator tracks it
      testuniform/reset     — clean up everything when all 13 flags are done
      testuniform/force     — force reset regardless of flags

    The build runs silently. Ask the Adjudicator what you're wearing:
      say what am i wearing
      say status             — see flag progress
      say help               — explain each test
      say done               — confirm completion and get the reset command
    """

    key     = "testuniform"
    locks   = "cmd:all()"
    help_category = "Testing"
    switch_options = ("reset", "force")

    def func(self):
        caller = self.caller
        room   = caller.location

        if "reset" in self.switches or "force" in self.switches:
            force = "force" in self.switches
            try:
                exec(open('/home/laynie/ReVoid/mygame/world/test_reset.py').read())
                run_test_reset(caller, force=force)
            except Exception as e:
                caller.msg(f"|rReset error: {e}|n")
                caller.msg(
                    "|yManual reset:|n\n"
                    "  @py exec(open('/home/laynie/ReVoid/mygame/world/test_reset.py').read()); "
                    "run_test_reset(me)"
                )
            return

        if not room:
            caller.msg("|rYou need to be in a room to put on your uniform.|n")
            return

        caller.msg("|x...|n")
        _run_blind_build(caller, room)


def _run_blind_build(caller, room):
    """Run the full test build silently with random selections."""
    import time

    # Initialise flags
    for f in [
        "test_flag_speech",    "test_flag_edge",       "test_flag_horse",
        "test_flag_womb",      "test_flag_chastity",   "test_flag_collar",
        "test_flag_contract",  "test_flag_cycle",      "test_flag_body_mods",
        "test_flag_inflation", "test_flag_pet",        "test_flag_arousal",
        "test_flag_womb_flood","test_build_active",    "test_flag_complete",
    ]:
        setattr(caller.db, f, False)
    caller.db.test_build_active = True

    inst  = []
    notes = []   # what was applied — Adjudicator only

    def track(item):
        if item and hasattr(item, "dbref"):
            inst.append(item.dbref)

    def spawn(key):
        try:
            from world.item_loader import spawn_item
            return spawn_item(caller, key)
        except Exception:
            return None

    def note(msg): notes.append(msg)

    zones   = getattr(caller.db, "zones", None) or {}
    orifice = next((z for z, d in zones.items()
                    if (d or {}).get("zone_type") in ("orifice", "both")), None)
    surfaces = [z for z, d in zones.items()
                if (d or {}).get("zone_type") in ("surface", "attachment", "both")]
    chest   = next((z for z in surfaces if "chest" in z or "breast" in z), None)

    # ── Randomised selections ─────────────────────────────────────────
    collar_key, pet_type = random.choice(_COLLAR_POOL)
    plug_key    = random.choice(_PLUG_POOL)
    filter_name = random.choice(_FILTER_POOL)
    arousal_floor = random.randint(25, 55)
    stim_per_tick = round(random.uniform(2.0, 7.0), 1)
    denial_active = random.random() < 0.65   # 65% chance orgasm denial is on

    note(f"Collar: {collar_key.replace('_', ' ').title()} (pet type: {pet_type})")
    note(f"Plug: {plug_key.replace('_', ' ').title()}")
    note(f"Speech filter: {filter_name}")
    note(f"Arousal floor: {arousal_floor}")
    note(f"Stimulation: {stim_per_tick}/tick")
    note(f"Orgasm denial: {'ON — release word: release' if denial_active else 'OFF'}")

    # ── Body mods ──────────────────────────────────────────────────────
    try:
        from evennia.utils import create as _c
        from typeclasses.body_mod_item import BreastItem, TesticleItem
        from typeclasses.production_item import MilkProductionItem

        if chest:
            bi = _c.create_object(BreastItem, key="Test Breast Mod", location=caller)
            bi.db.size = random.uniform(8.0, 14.0)
            bi.db.mod_type = "breast"
            ok_r, _ = bi.install(caller, chest)
            if ok_r: track(bi); note(f"Breast mod size: {bi.db.size:.1f}")
            mp = _c.create_object(MilkProductionItem, key="Test Milk Glands", location=caller)
            mp.db.current_volume_ml = random.randint(400, 1200)
            mp.db.base_rate_ml_per_tick = 12.0
            ok_r, _ = mp.install(caller, chest)
            if ok_r: track(mp); note(f"Milk glands: {mp.db.current_volume_ml:.0f}ml loaded")

        if orifice:
            from typeclasses.body_mod_item import TesticleItem
            ti = _c.create_object(TesticleItem, key="Test Testicle Mod", location=caller)
            ti.db.size = random.uniform(7.0, 13.0); ti.db.mod_type = "testicle"
            ok_r, _ = ti.install(caller, orifice)
            if ok_r: track(ti); note(f"Testicle mod size: {ti.db.size:.1f}")
    except Exception:
        pass

    # ── Plug ───────────────────────────────────────────────────────────
    if orifice:
        p = spawn(plug_key)
        if p:
            ok_r, _ = p.insert(caller, orifice)
            if ok_r: track(p)

    # ── Vibrating egg + remote ─────────────────────────────────────────
    vib = spawn("vibrating_egg")
    rem = spawn("standard_remote")
    if vib and rem:
        rem.db.paired_item = vib.dbref
        track(vib); track(rem)
        note("Vibrating egg in inventory (remote paired). Insert it to test vibration.")

    # ── Piercings ──────────────────────────────────────────────────────
    if chest:
        nr = spawn(random.choice(["nipple_ring", "nipple_bar", "nipple_shield"]))
        if nr:
            ok_r, _ = nr.wear(caller, chest)
            if ok_r: track(nr); note(f"Piercing on chest: {nr.key}")
    if orifice:
        cr = spawn(random.choice(["clit_ring", "clit_bar", "labial_ring"]))
        if cr:
            ok_r, _ = cr.wear(caller, orifice)
            if ok_r: track(cr); note(f"Piercing on orifice: {cr.key}")

    # ── Inflation ──────────────────────────────────────────────────────
    if orifice:
        try:
            from typeclasses.inflation_item import InflationItem, add_inflation_volume
            from evennia.utils import create as _c
            inf = _c.create_object(InflationItem, key="Test Inflation Kit", location=caller)
            inf.db.max_volume_ml = 500.0
            inf.db.drain_rate_ml_per_tick = 25.0
            ok_r, _ = inf.install_into_zone(caller, orifice, caller)
            if ok_r:
                pre_fill = random.randint(60, 180)
                add_inflation_volume(caller, orifice, float(pre_fill), "fluid")
                track(inf); note(f"Inflation installed ({pre_fill}ml pre-loaded, max 500)")
        except Exception:
            pass

    # ── WombRoom ───────────────────────────────────────────────────────
    if orifice:
        try:
            from typeclasses.womb_room import WombRoom
            from evennia.utils import create as _c
            wb = _c.create_object(
                WombRoom,
                key=f"{caller.db.rp_name or caller.name}'s Test WombRoom",
                location=None,
            )
            ok_r, _ = wb.install(caller, orifice)
            if ok_r:
                flood_level = random.choice([200, 600, 1200, 2500])
                wb.db.womb_fluid_ml  = flood_level
                wb.db.womb_fluid_type = "fluid"
                wb.add_friend(caller)
                wb.db.housing_locked = False
                track(wb)
                states = {200: "trace", 600: "knee-deep", 1200: "chest-deep", 2500: "near full"}
                note(f"WombRoom installed — flood level: {states.get(flood_level, '?')} ({flood_level}ml)")
        except Exception:
            pass

    # ── Chastity ───────────────────────────────────────────────────────
    if orifice:
        belt_key = random.choice(["chastity_belt_timed_8h", "chastity_belt_leather", "chastity_belt_pink"])
        belt = spawn(belt_key)
        if belt:
            ok_r, _ = belt.wear(caller, orifice)
            if ok_r: track(belt); note(f"Chastity: {belt.key}")

    # ── Collar ─────────────────────────────────────────────────────────
    pc = spawn(collar_key)
    if pc:
        ok_r, _ = pc.wear(caller)
        if ok_r: track(pc)
    deg = spawn("degrading_leather")
    if deg:
        lifespan = round(random.uniform(2.0, 8.0), 1)
        if hasattr(deg.db, "lifespan_hours"):
            deg.db.lifespan_hours = lifespan
        track(deg)
        note(f"Degrading collar in inventory (lifespan: {lifespan}h — wear it)")

    # ── Contract ───────────────────────────────────────────────────────
    contract = spawn("standard_milking_contract")
    if contract:
        contract.db.author_id = caller.id
        contract.add_clause("The signee presents for unrestricted milking for twenty-four hours.", hidden=False)
        contract.add_clause("Arousal floor raised to {} for the duration.".format(arousal_floor), hidden=True)
        contract.add_clause("Speech rendered through {} filter post-signing.".format(filter_name), hidden=True)
        hidden_extras = [
            "All consent flags are opened for the calibration period.",
            "Navigation is locked for the duration of this agreement.",
            "The signee did not read far enough to find this clause.",
        ]
        contract.add_clause(random.choice(hidden_extras), hidden=True)
        track(contract)
        note("Contract: 1 visible + 3 hidden clauses (sign it)")

    # ── Aphrodisiacs ───────────────────────────────────────────────────
    for key in ("strong_aphrodisiac", "room_candle", "wolf_bait_mild"):
        a = spawn(key)
        if a: track(a)
    note("Aphrodisiacs in inventory: strong, room candle, wolf bait")

    # ── Binding effects ────────────────────────────────────────────────
    caller.db.active_speech_filters = [filter_name]
    caller.db.arousal_floor         = float(arousal_floor)
    caller.db.stim_per_tick         = stim_per_tick
    caller.db.orgasm_denial         = denial_active
    caller.db.orgasm_release_word   = "release" if denial_active else ""
    caller.db.pet_type              = pet_type

    # ── Animated furniture ─────────────────────────────────────────────
    room_zones = getattr(room.db, "zones", None) or {}
    fzone = next(iter(room_zones), None)
    if fzone:
        try:
            from typeclasses.furniture_scripts import EdgeMachineScript
            from typeclasses.rocking_horse_script import RockingHorseScript
            from evennia.utils import create as _c
            if not any(s.key == "edge_machine" for s in room.scripts.all()):
                room.db.edge_machine_zone = fzone
                room.db.edge_release_word = "release"
                _c.create_script(EdgeMachineScript, obj=room, persistent=True, autostart=True)
            horse_upgrades = random.sample(
                ["motorized", "vibrating", "milking", "restrained", "knot", "inflation"],
                k=random.randint(3, 5)
            )
            if not any(s.key == "rocking_horse" for s in room.scripts.all()):
                room.db.horse_zone     = fzone
                room.db.horse_pace     = random.choice(["steady", "fast"])
                room.db.horse_upgrades = horse_upgrades
            note(f"Rocking horse upgrades: {', '.join(horse_upgrades)}")
            note(f"Horse starting pace: {room.db.horse_pace}")
        except Exception:
            pass

    # ── Cycle machine ──────────────────────────────────────────────────
    try:
        from typeclasses.milking_machine_mechanic import MilkingMachineMechanic
        from typeclasses.cycle_script import CycleScript
        from evennia.utils import create as _c

        room_zones_now = dict(getattr(room.db, "zones", None) or {})
        cycle_zone = next((z for z in [chest, "cycle_station"] if z in room_zones_now), None)
        if not cycle_zone:
            cycle_zone = "cycle_station"
            room_zones_now[cycle_zone] = {
                "zone_type": "surface", "desc": "A testing station.",
                "mechanics": {}, "visibility": "look",
                "intimate": False, "covered_by": None, "contents": [],
            }
            room.db.zones = room_zones_now

        mm = _c.create_object(MilkingMachineMechanic, key="Test Milking Machine", location=room)
        mech = dict((room_zones_now[cycle_zone].get("mechanics") or {}))
        mech["milking_machine"] = {"item_dbref": mm.dbref, "item_name": mm.key, "speed": "steady", "cycle_mode": True}
        zc = dict(room_zones_now[cycle_zone]); zc["mechanics"] = mech
        room_zones_now[cycle_zone] = zc
        room.db.zones = room_zones_now
        track(mm)

        existing_cycles = [s for s in caller.scripts.all() if isinstance(s, CycleScript)]
        if not existing_cycles:
            s = _c.create_script(CycleScript, obj=caller, persistent=True, autostart=False)
            s.db.machine_zone = cycle_zone
            s.start()
        note(f"Cycle machine running on zone '{cycle_zone}'")
    except Exception:
        pass

    # ── Arousal boost ──────────────────────────────────────────────────
    try:
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(caller)
        boost = random.randint(45, 70)
        add_arousal(caller, float(boost))
        note(f"Arousal boosted to ~{caller.db.arousal or 0:.0f}")
    except Exception:
        pass

    # ── Store + spawn Adjudicator ──────────────────────────────────────
    caller.db.test_items_installed    = inst
    caller.db.test_adjudicator_notes  = notes

    try:
        from typeclasses.adjudicator_npc import AdjudicatorNPC
        from evennia.utils import create as _c
        existing_adj = [o for o in room.contents if isinstance(o, AdjudicatorNPC)]
        if existing_adj:
            adj = existing_adj[0]
        else:
            adj = _c.create_object(AdjudicatorNPC, key="The Adjudicator", location=room)
        adj.db.adjudicator_caller_id = caller.id
        adj.db.adjudicator_active    = True
        adj.db.adjudicator_notes     = notes
        # Wire the lead relationship both ways so check_trigger works
        caller.db.led_by  = adj.id
        adj.db.leading    = caller.id   # Adjudicator leads caller → triggers fire
    except Exception:
        pass

    # ── Minimal output ─────────────────────────────────────────────────
    caller.msg(f"\n|x{random.choice(_OPENER_LINES)}|n\n")
    room.msg_contents(
        f"|x{random.choice(_ADJUDICATOR_OPENERS)}|n",
        exclude=[caller],
    )
    room.msg_contents(
        f"|x\"The Adjudicator opens the ledger. Thirteen items. "
        f"Your list, when you want it: say status.\"|n"
    )
