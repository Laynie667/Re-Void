"""
world/test_build.py — Re:Void system verification build

Spawns and installs items/mechanics to test every new system.
The Adjudicator NPC tracks your progress and tells you what's left.

Run:
  @reload
  @py exec(open('/home/laynie/ReVoid/mygame/world/test_build.py').read()); run_test_build(me)

During testing, ask the NPC:
  say status    — see what's done and what's left
  say help      — explanation of each test
  say done      — NPC verifies completion and clears you to reset

When cleared, run:
  @py exec(open('/home/laynie/ReVoid/mygame/world/test_reset.py').read()); run_test_reset(me)
"""

import time


def run_test_build(caller):
    room = caller.location
    if not room:
        caller.msg("|rRun this while standing in a room.|n")
        return

    caller.msg("\n|w══════════════════════════════════════════════|n")
    caller.msg("|wRe:Void — SYSTEM VERIFICATION BUILD|n")
    caller.msg("|w══════════════════════════════════════════════|n\n")

    ok_log  = []
    err_log = []
    inst    = []   # item dbrefs for cleanup

    def ok(msg):   ok_log.append(f"  |g✓|n {msg}")
    def err(msg):  err_log.append(f"  |r✗|n {msg}")
    def sec(title): caller.msg(f"\n|w── {title} ──|n")

    def spawn(key):
        try:
            from world.item_loader import spawn_item
            return spawn_item(caller, key)
        except Exception as e:
            err(f"spawn '{key}': {e}")
            return None

    def track(item):
        if item and hasattr(item, "dbref"):
            inst.append(item.dbref)

    # Detect zones
    zones   = getattr(caller.db, "zones", None) or {}
    orifice = next((z for z, d in zones.items()
                    if (d or {}).get("zone_type") in ("orifice", "both")), None)
    surfaces = [z for z, d in zones.items()
                if (d or {}).get("zone_type") in ("surface", "attachment", "both")]
    chest   = next((z for z in surfaces if "chest" in z or "breast" in z), None)
    shaft   = next((z for z, d in zones.items()
                    if (d or {}).get("zone_type") == "shaft"), None)

    caller.msg(f"  Orifice: |w{orifice or 'none'}|n   "
               f"Chest: |w{chest or 'none'}|n   "
               f"Shaft: |w{shaft or 'none'}|n")

    # Initialise all 13 test flags
    for f in [
        "test_flag_speech",    "test_flag_edge",       "test_flag_horse",
        "test_flag_womb",      "test_flag_chastity",   "test_flag_collar",
        "test_flag_contract",  "test_flag_cycle",      "test_flag_body_mods",
        "test_flag_inflation", "test_flag_pet",        "test_flag_arousal",
        "test_flag_womb_flood","test_build_active",
    ]:
        setattr(caller.db, f, False)
    caller.db.test_build_active = True
    caller.db.test_items_installed = []

    # ─────────────────────────────────────────────────────────────────
    # 1. BODY MODS — tests {size}, {vol}, {circ}, {diam} zone tokens
    # ─────────────────────────────────────────────────────────────────
    sec("Body Mods — zone token testing")
    try:
        from evennia.utils import create as _c
        from typeclasses.body_mod_item import BreastItem, TesticleItem
        from typeclasses.production_item import MilkProductionItem

        if chest:
            bi = _c.create_object(BreastItem, key="Test Breast Mod", location=caller)
            bi.db.size = 10.0            # L-ish, clearly visible in {size}
            ok_r, r = bi.install(caller, chest)
            if ok_r:
                track(bi); ok(f"Breast mod (size 10) on {chest}")
                caller.msg(f"  |yToken test → zone set {chest} = {{size}} breast holding {{vol}}.|n")
            else:
                err(f"Breast mod: {r}")

            mp = _c.create_object(MilkProductionItem, key="Test Milk Glands", location=caller)
            mp.db.current_volume_ml = 800.0
            mp.db.base_rate_ml_per_tick = 12.0
            ok_r, r = mp.install(caller, chest)
            if ok_r:
                track(mp); ok(f"Milk Glands (800ml) on {chest}")
            else:
                err(f"Milk glands: {r}")

        if orifice:
            ti = _c.create_object(TesticleItem, key="Test Testicle Mod", location=caller)
            ti.db.size = 9.0; ti.db.mod_type = "testicle"
            ok_r, r = ti.install(caller, orifice)
            if ok_r:
                track(ti); ok(f"Testicle mod (size 9, melon) on {orifice}")
                caller.msg(f"  |yToken test → zone set {orifice} = {{size}}, each one {{diam}} across.|n")
            else:
                err(f"Testicle mod: {r}")

        caller.db.test_flag_body_mods = False  # set True after examining zone descs
        ok("FLAG 9: examine zone descs to see tokens, then: @py me.db.test_flag_body_mods=True")
    except Exception as e:
        err(f"Body mods: {e}")

    # ─────────────────────────────────────────────────────────────────
    # 2. PLUGS + PIERCINGS
    # ─────────────────────────────────────────────────────────────────
    sec("Plugs + Piercings")
    if orifice:
        p = spawn("metal_plug")
        if p:
            ok_r, _ = p.insert(caller, orifice)
            if ok_r: track(p); ok(f"Metal Plug inserted → {orifice}")

        vib = spawn("vibrating_egg")
        rem = spawn("standard_remote")
        if vib and rem:
            rem.db.paired_item = vib.dbref
            track(vib); track(rem)
            ok("Vibrating Egg + paired Remote in inventory")
            caller.msg(f"  |yTest: insert Vibrating Egg {orifice} → vibrate {caller.db.rp_name or caller.name} medium|n")

    if chest:
        nr = spawn("nipple_ring")
        if nr:
            ok_r, _ = nr.wear(caller, chest)
            if ok_r: track(nr); ok(f"Nipple Ring on {chest} (+20% sensitivity)")

    if orifice:
        cr = spawn("clit_ring")
        if cr:
            ok_r, r = cr.wear(caller, orifice)
            if ok_r: track(cr); ok(f"Clit Ring on {orifice} (+35% sensitivity)")
            else: caller.msg(f"  |yClit ring: {r} — try: wear Clit Ring {orifice}|n")

    # ─────────────────────────────────────────────────────────────────
    # 3. INFLATION — tests inflate/check/drain + {inflation} token
    # ─────────────────────────────────────────────────────────────────
    sec("Inflation")
    if orifice:
        try:
            from typeclasses.inflation_item import InflationItem, add_inflation_volume
            from evennia.utils import create as _c
            inf = _c.create_object(InflationItem, key="Test Inflation Kit", location=caller)
            inf.db.max_volume_ml = 500.0
            inf.db.drain_rate_ml_per_tick = 25.0
            ok_r, r = inf.install_into_zone(caller, orifice, caller)
            if ok_r:
                track(inf)
                add_inflation_volume(caller, orifice, 100.0, "fluid")   # pre-fill to notable
                ok(f"Inflation installed on {orifice} (pre-filled ~100ml, max 500)")
                caller.msg(f"  |yTest: inflate me {orifice} 200 → inflate/check me {orifice}|n")
                caller.msg(f"  |yToken: zone set {orifice} = currently {{inflation}} inside.|n")
                caller.msg(f"  |yDrain: inflate/drain me {orifice}|n")
                caller.msg(f"  |yThen: @py me.db.test_flag_inflation=True|n")
            else:
                caller.msg(f"  |yInflation install: {r}. Try: use Test Inflation Kit on {orifice}|n")
                track(inf)
        except Exception as e:
            err(f"Inflation: {e}")

    # ─────────────────────────────────────────────────────────────────
    # 4. WOMB ROOM — tests enter/look/flood/leave/pulse
    # ─────────────────────────────────────────────────────────────────
    sec("WombRoom")
    if orifice:
        try:
            from typeclasses.womb_room import WombRoom
            from evennia.utils import create as _c
            wb = _c.create_object(
                WombRoom,
                key=f"{caller.db.rp_name or caller.name}'s Test WombRoom",
                location=None,
            )
            ok_r, r = wb.install(caller, orifice)
            if ok_r:
                track(wb)
                wb.db.womb_fluid_ml  = 600.0    # pre-fill to knee level
                wb.db.womb_fluid_type = "fluid"
                wb.add_friend(caller)
                wb.db.housing_locked = False
                ok(f"WombRoom installed on {orifice}, knee-deep fluid pre-loaded")
                caller.msg(f"  |ySet desc: wombroom/desc = <text>|n")
                caller.msg(f"  |yEnter: enter {caller.db.rp_name or caller.name} {orifice}|n")
                caller.msg(f"  |yLook inside — flood description should show.|n")
                caller.msg(f"  |yLeave: leave|n")
                caller.msg(f"  |yThen: @py me.db.test_flag_womb=True; me.db.test_flag_womb_flood=True|n")
            else:
                err(f"WombRoom: {r}")
        except Exception as e:
            err(f"WombRoom: {e}")

    # ─────────────────────────────────────────────────────────────────
    # 5. CHASTITY — tests zone block on penetrate
    # ─────────────────────────────────────────────────────────────────
    sec("Chastity")
    if orifice:
        belt = spawn("chastity_belt_timed_8h")
        if belt:
            ok_r, r = belt.wear(caller, orifice)
            if ok_r:
                track(belt)
                ok(f"Timed Chastity Belt (8h) on {orifice}")
                caller.msg(f"  |yTest: penetrate me {orifice}  — should be blocked.|n")
                caller.msg(f"  |yThen: @py me.db.test_flag_chastity=True|n")
            else:
                caller.msg(f"  |yChastity blocked — try: wear Timed Chastity Belt (8h) {orifice}|n")

    # ─────────────────────────────────────────────────────────────────
    # 6. COLLARS — puppy (pet triggers) + degrading (state machine)
    # ─────────────────────────────────────────────────────────────────
    sec("Collars")
    pc = spawn("puppy_collar")
    if pc:
        ok_r, _ = pc.wear(caller)
        if ok_r:
            track(pc)
            ok("Puppy Collar worn — pet triggers active, auto_consent on")
            caller.msg(f"  |yTest trigger: sayto {caller.db.rp_name or caller.name} stay  (then: free)|n")
            caller.msg(f"  |yOr ask the Adjudicator: say run pet test|n")

    deg = spawn("degrading_leather")
    if deg:
        track(deg)
        caller.msg("  |yWorn Leather Collar in inventory — wear it to test degradation:|n")
        caller.msg("  |w  wear Worn Leather Collar|n")
        caller.msg("  |yForce a tick: @py [c for c in me.contents if hasattr(c.db,'state') and getattr(c.db,'is_worn',False)][0].tick()|n")
        caller.msg("  |yThen: @py me.db.test_flag_collar=True|n")

    # ─────────────────────────────────────────────────────────────────
    # 7. MILKING CONTRACT — visible + hidden clauses, sign + reveal
    # ─────────────────────────────────────────────────────────────────
    sec("Milking Contract")
    contract = spawn("standard_milking_contract")
    if contract:
        contract.db.author_id = caller.id
        contract.add_clause(
            "The signee presents for milking at the operator's discretion "
            "for twenty-four hours.",
            hidden=False
        )
        contract.add_clause(
            "Arousal floor raised to 40 for the duration of this agreement.",
            hidden=True
        )
        contract.add_clause(
            "Speech rendered in third person for one hour post-signing.",
            hidden=True
        )
        track(contract)
        ok("Milking Contract (1 visible, 2 hidden clauses)")
        caller.msg("  |yRead:   contract/read Milking Contract|n")
        caller.msg("  |ySign:   contract/sign Milking Contract  ← hidden effects activate|n")
        caller.msg("  |yReveal: contract/reveal/all Milking Contract|n")
        caller.msg("  |yThen: @py me.db.test_flag_contract=True|n")

    # ─────────────────────────────────────────────────────────────────
    # 8. CYCLE MACHINE — restraint → milk → boost → rest
    # ─────────────────────────────────────────────────────────────────
    sec("Cycle Machine")
    if chest:
        try:
            from evennia.utils import create as _c
            from typeclasses.milking_machine_mechanic import MilkingMachineMechanic
            mm = _c.create_object(MilkingMachineMechanic, key="Test Milking Machine", location=room)
            room_zones = getattr(room.db, "zones", None) or {}
            if chest in room_zones:
                mech = dict((room_zones[chest].get("mechanics") or {}))
                mech["milking_machine"] = {"item_dbref": mm.dbref, "item_name": mm.key, "speed": "steady"}
                zc = dict(room_zones[chest]); zc["mechanics"] = mech
                zs = dict(room_zones); zs[chest] = zc
                room.db.zones = zs
                ok(f"Milking machine installed on room zone '{chest}'")
            else:
                caller.msg(f"  |yRoom has no zone '{chest}'. Create it: roomzone add {chest}|n")
                caller.msg(f"  |yThen re-run the build.|n")
                mm.delete()

            caller.msg("  |yStart cycle on yourself:|n")
            caller.msg(f"  |w  @py from typeclasses.cycle_script import CycleScript; from evennia.utils import create; s=create.create_script(CycleScript,obj=me,persistent=True,autostart=False); s.db.machine_zone='{chest}'; s.start(); me.msg('Cycle running.')|n")
            caller.msg("  |yLet it run one full phase (15 sec) then: endcycle|n")
            caller.msg("  |yThen: @py me.db.test_flag_cycle=True|n")
        except Exception as e:
            err(f"Cycle machine: {e}")
    else:
        caller.msg("  |yNo chest zone in room. Create: roomzone add chest, then re-run.|n")

    # ─────────────────────────────────────────────────────────────────
    # 9. APHRODISIACS
    # ─────────────────────────────────────────────────────────────────
    sec("Aphrodisiacs")
    for key in ("mild_aphrodisiac", "room_candle", "wolf_bait_mild"):
        a = spawn(key); track(a) if a else None
    ok("Mild Aphrodisiac, Room Candle, Wolf Bait in inventory")
    caller.msg("  |yPersonal: @py [o for o in me.contents if 'Aphrodisiac' in o.key][0].use(me)|n")
    caller.msg("  |yRoom:     @py [o for o in me.contents if 'Candle' in o.key][0].use(me)|n")
    caller.msg("  |yWolf bait: @py [o for o in me.contents if 'Wolf' in o.key][0].use(me)|n")
    caller.msg("  |yCheck: @py from typeclasses.aphrodisiac_item import check_wolf_bait; me.msg(str(check_wolf_bait(me)))|n")

    # ─────────────────────────────────────────────────────────────────
    # 10. ANIMATED FURNITURE — edge machine + rocking horse
    # ─────────────────────────────────────────────────────────────────
    sec("Animated Furniture")
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
                ok(f"Edge Machine on '{fzone}'  — release word: release")
            else:
                ok("Edge Machine already running")

            if not any(s.key == "rocking_horse" for s in room.scripts.all()):
                room.db.horse_zone     = fzone
                room.db.horse_pace     = "steady"
                room.db.horse_upgrades = ["motorized", "vibrating", "milking", "restrained"]
                ok(f"Rocking Horse on '{fzone}' (steady, upgrades: motorized/vibrating/milking/restrained)")
                caller.msg("  |yhorsemount → horsestart → let it run → horsestop → horsedismount|n")
            else:
                ok("Rocking Horse already configured")
        except Exception as e:
            err(f"Furniture: {e}")
    else:
        caller.msg("  |yRoom needs at least one zone for furniture. roomzone add station|n")

    # ─────────────────────────────────────────────────────────────────
    # 11. BINDING EFFECTS — test-level, not maxed
    # ─────────────────────────────────────────────────────────────────
    sec("Binding Effects (test levels)")
    try:
        caller.db.active_speech_filters = ["third_person"]
        caller.db.arousal_floor         = 30.0
        caller.db.stim_per_tick         = 4.0
        caller.db.orgasm_denial         = True
        caller.db.orgasm_release_word   = "release"
        ok("Speech filter: third_person  (say something to verify it transforms)")
        ok("Arousal floor: 30  (arousal won't decay below this)")
        ok("Stimulation: 4/tick  (passive ticks push arousal up)")
        ok("Orgasm denial: ON  (say 'release' or sit on edge machine to test)")
        caller.msg("  |yTest speech: say anything — output should be third-person.|n")
        caller.msg("  |yThen: @py me.db.test_flag_speech=True|n")
        caller.msg("  |yTest denial: try to climax via machine, then say: say release|n")
        caller.msg("  |yThen: @py me.db.test_flag_arousal=True|n")
    except Exception as e:
        err(f"Effects: {e}")

    # ─────────────────────────────────────────────────────────────────
    # 12. AROUSAL BOOST — push into test range
    # ─────────────────────────────────────────────────────────────────
    sec("Arousal")
    try:
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(caller)
        add_arousal(caller, 60.0)
        ok(f"Arousal boosted to ~{caller.db.arousal or 0:.0f}  (threshold messages at 75/90/95)")
    except Exception as e:
        err(f"Arousal: {e}")

    # ─────────────────────────────────────────────────────────────────
    # 13. THE ADJUDICATOR — progress tracker NPC
    # ─────────────────────────────────────────────────────────────────
    sec("Adjudicator NPC")
    try:
        from typeclasses.adjudicator_npc import AdjudicatorNPC
        from evennia.utils import create as _c
        adj = _c.create_object(AdjudicatorNPC, key="The Adjudicator", location=room)
        adj.db.adjudicator_caller_id = caller.id
        adj.db.adjudicator_active    = True
        track(adj)
        ok(f"The Adjudicator is in the room (#{adj.id})")
        caller.msg("  |y  say status  — see what's done and what's left|n")
        caller.msg("  |y  say help    — get explanation of each test|n")
        caller.msg("  |y  say run pet test  — Adjudicator runs pet triggers on you|n")
        caller.msg("  |y  say done    — Adjudicator verifies all flags and clears you to reset|n")
        room.msg_contents(
            "|xA figure steps into the room and opens a small ledger. "
            "\"System verification in progress,\" they say. "
            "\"Thirteen items on the list. Ask me for status at any time.\"|n"
        )
    except Exception as e:
        err(f"Adjudicator: {e}")

    # ─────────────────────────────────────────────────────────────────
    caller.db.test_items_installed = inst

    caller.msg("\n|w══════════════════════════════════════════════|n")
    caller.msg("|wRESULTS:|n")
    for line in ok_log: caller.msg(line)
    if err_log:
        caller.msg("\n|rNON-FATAL ERRORS (manual steps shown above):|n")
        for line in err_log: caller.msg(line)

    caller.msg(f"\n|w{len(inst)} items/scripts installed. Adjudicator has the list.|n")
    caller.msg("""
|w══════════════════════════════════════════════|n
|wQUICK REFERENCE — ask the Adjudicator for detail|n
|w══════════════════════════════════════════════|n
  1.  Speech filter      say anything
  2.  Edge machine       sit in zone, reach 99, say release
  3.  Rocking horse      horsemount → horsestart → horsestop
  4.  WombRoom           enter yourself → look → leave
  5.  Chastity           try to penetrate while belted
  6.  Degrading collar   wear it → force tick
  7.  Contract           sign → reveal hidden clauses
  8.  Cycle machine      start → let run → endcycle
  9.  Body mods          check zone descs for tokens
  10. Inflation          inflate → check → drain
  11. Pet triggers       say run pet test to Adjudicator
  12. Arousal cycle      ride through 75/90/95/99
  13. WombRoom flood     enter → see knee-deep level
|w══════════════════════════════════════════════|n
""")
