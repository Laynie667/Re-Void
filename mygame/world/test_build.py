"""
world/test_build.py

Re:Void comprehensive test build script.
Tests all new mechanics, items, effects, and furniture systems.

Run in-game as superuser:
  @py exec(open('/home/laynie/ReVoid/mygame/world/test_build.py').read()); run_test_build(me)

Then complete the test checklist printed at the end.
When all flags are done, run the reset:
  @py exec(open('/home/laynie/ReVoid/mygame/world/test_reset.py').read()); run_test_reset(me)
"""

import time


def run_test_build(caller):
    """Entry point — run this with the character you want to test on."""

    caller.msg("\n|w═══════════════════════════════════════════════|n")
    caller.msg("|wRe:Void TEST BUILD — Starting...|n")
    caller.msg("|w═══════════════════════════════════════════════|n\n")

    results = []
    errors  = []

    # ── Helpers ──────────────────────────────────────────────────────────
    def ok(msg):
        results.append(f"  |g✓|n {msg}")

    def err(msg):
        errors.append(f"  |r✗|n {msg}")

    def section(title):
        caller.msg(f"\n|w── {title} ──|n")

    def _find_zone(caller, zone_type):
        """Find first zone of the given type on the character."""
        zones = getattr(caller.db, "zones", None) or {}
        for zn, zd in zones.items():
            if (zd or {}).get("zone_type") == zone_type:
                return zn
        return None

    def _find_zones(caller, zone_type):
        zones = getattr(caller.db, "zones", None) or {}
        return [zn for zn, zd in zones.items()
                if (zd or {}).get("zone_type") == zone_type]

    # ── Detect character zones ────────────────────────────────────────────
    section("Detecting Zones")
    zones = getattr(caller.db, "zones", None) or {}
    if not zones:
        caller.msg("|rNo zones detected. Make sure your character is set up with zones.|n")
        return

    orifice_zone = _find_zone(caller, "orifice") or _find_zone(caller, "both")
    surface_zones = [zn for zn, zd in zones.items()
                     if (zd or {}).get("zone_type") in ("surface", "attachment", "both")]
    shaft_zone = _find_zone(caller, "shaft")

    caller.msg(f"  Orifice zone:  |w{orifice_zone or 'NONE'}|n")
    caller.msg(f"  Surface zones: |w{', '.join(surface_zones[:3]) or 'NONE'}|n")
    caller.msg(f"  Shaft zone:    |w{shaft_zone or 'NONE'}|n")

    if not orifice_zone:
        caller.msg("|yNo orifice zone found. Plug and WombRoom tests will be skipped.|n")

    # ── Initialize test flags ─────────────────────────────────────────────
    caller.db.test_build_active   = True
    caller.db.test_flag_edge      = False   # get arousal to 99 via edge machine
    caller.db.test_flag_horse     = False   # mount and start the rocking horse
    caller.db.test_flag_womb      = False   # enter the WombRoom
    caller.db.test_flag_speech    = False   # say something while filtered (auto-set)
    caller.db.test_flag_chastity  = False   # attempt penetrate while chastity locked
    caller.db.test_flag_collar    = False   # let degrading collar tick once
    caller.db.test_flag_contract  = False   # sign the test milking contract
    caller.db.test_items_installed = []     # track dbref strings for cleanup

    items_installed = []

    from world.item_loader import spawn_item

    # ── 1. PLUG ───────────────────────────────────────────────────────────
    section("Plug Installation")
    if orifice_zone:
        try:
            plug = spawn_item(caller, "metal_plug")
            if plug:
                ok_result, reason = plug.insert(caller, orifice_zone)
                if ok_result:
                    items_installed.append(plug.dbref)
                    ok(f"Metal Plug inserted into {orifice_zone}")
                else:
                    err(f"Plug insert failed: {reason}")
        except Exception as e:
            err(f"Plug creation error: {e}")
    else:
        caller.msg("  |xSkipped — no orifice zone.|n")

    # ── 2. VIBRATING EGG + REMOTE ────────────────────────────────────────
    section("Vibrating Egg + Remote")
    if orifice_zone:
        try:
            from typeclasses.vibration_item import VibratingPlugItem
            egg = spawn_item(caller, "vibrating_egg")
            remote = spawn_item(caller, "standard_remote")
            if egg and remote:
                # Don't insert yet — let the player try it
                remote.db.paired_item = egg.dbref
                items_installed.extend([egg.dbref, remote.dbref])
                ok(f"Vibrating Egg in inventory (not yet inserted)")
                ok(f"Remote Control paired to egg — use: insert Vibrating Egg {orifice_zone}")
                ok(f"Then test: vibrate {caller.db.rp_name or caller.name} medium")
        except Exception as e:
            err(f"Vibrating egg error: {e}")

    # ── 3. PIERCINGS ──────────────────────────────────────────────────────
    section("Piercings")
    try:
        nipple_zone = next((zn for zn in surface_zones
                            if "chest" in zn or "breast" in zn or "nipple" in zn), None)
        groin_zone  = next((zn for zn in zones.keys()
                            if "groin" in zn or "pussy" in zn or "clit" in zn), None)

        if nipple_zone:
            ring = spawn_item(caller, "nipple_ring")
            if ring:
                ok_r, reason = ring.wear(caller, nipple_zone)
                if ok_r:
                    items_installed.append(ring.dbref)
                    ok(f"Nipple Ring on {nipple_zone} (+20% sensitivity)")
                else:
                    err(f"Nipple ring failed: {reason}")
        else:
            caller.msg("  |xNo chest zone found for nipple ring — install manually.|n")

        if groin_zone and orifice_zone:
            clit = spawn_item(caller, "clit_ring")
            if clit:
                ok_r, reason = clit.wear(caller, orifice_zone)
                if ok_r:
                    items_installed.append(clit.dbref)
                    ok(f"Clit Ring on {orifice_zone} (+35% sensitivity)")
                else:
                    caller.msg(f"  |xClit ring: {reason} — try: wear Clit Ring {orifice_zone}|n")
    except Exception as e:
        err(f"Piercing error: {e}")

    # ── 4. COLLAR + DEGRADING ────────────────────────────────────────────
    section("Collars")
    try:
        # Training collar (normal)
        training = spawn_item(caller, "training_collar")
        if training:
            ok_r, reason = training.wear(caller)
            if ok_r:
                items_installed.append(training.dbref)
                ok("Training Collar worn")
            else:
                caller.msg(f"  |xTraining collar: {reason}|n")

        # Degrading leather collar (to test degradation)
        deg = spawn_item(caller, "degrading_leather")
        if deg:
            items_installed.append(deg.dbref)
            caller.msg(f"  |yDegrading Collar in inventory — wear it manually: wear Worn Leather Collar|n")
            caller.msg(f"  |yThen wait for a passive tick (or force one) to see it degrade.|n")
    except Exception as e:
        err(f"Collar error: {e}")

    # ── 5. CHASTITY (timed, so it auto-releases) ─────────────────────────
    section("Chastity")
    if orifice_zone:
        try:
            belt = spawn_item(caller, "chastity_belt_timed_8h")
            if belt:
                ok_r, reason = belt.wear(caller, orifice_zone)
                if ok_r:
                    items_installed.append(belt.dbref)
                    ok(f"Timed Chastity Belt on {orifice_zone} (8h timer)")
                    ok("TEST: Try 'penetrate' on yourself or get someone to try")
                    ok("  The chastity should block it — set test_flag_chastity = True after confirming")
                else:
                    caller.msg(f"  |xChastity belt: {reason}|n")
        except Exception as e:
            err(f"Chastity error: {e}")

    # ── 6. WEARABLE + CAMOUFLAGE ─────────────────────────────────────────
    section("Wearable / Camouflage")
    try:
        uniform = spawn_item(caller, "schoolgirl_uniform")
        if uniform:
            items_installed.append(uniform.dbref)
            caller.msg("  |ySchoolgirlUniform in inventory.|n")
            caller.msg("  |yWear it: wear Schoolgirl Uniform|n")
            caller.msg("  |yThen have someone 'look' at you — they should see the camouflage desc.|n")
            caller.msg("  |yYou 'look' at yourself — you see real zones.|n")
    except Exception as e:
        err(f"Wearable error: {e}")

    # ── 7. BRAND ──────────────────────────────────────────────────────────
    section("Brand / Mark")
    try:
        brand = spawn_item(caller, "temp_brand")
        if brand:
            items_installed.append(brand.dbref)
            ok("Temp Brand in inventory")
            caller.msg("  |yApply it to yourself: brand me [zone]|n")
            caller.msg("  |yOr apply to another character: brand <target> [zone]|n")
    except Exception as e:
        err(f"Brand error: {e}")

    # ── 8. APHRODISIAC ────────────────────────────────────────────────────
    section("Aphrodisiac")
    try:
        aph = spawn_item(caller, "mild_aphrodisiac")
        room_candle = spawn_item(caller, "room_candle")
        wolf_bait   = spawn_item(caller, "wolf_bait_mild")
        for item in [aph, room_candle, wolf_bait]:
            if item:
                items_installed.append(item.dbref)
        ok("Mild Aphrodisiac, Room Candle, Wolf Bait (Mild) in inventory")
        caller.msg("  |yUse (personal): @py [aph] = [find in inventory]; aph.use(me)|n")
        caller.msg("  |yUse (room):     @py [candle] = [find in inventory]; candle.use(me)|n")
        caller.msg("  |yWolf bait flags you for wolf NPC reactions.|n")
    except Exception as e:
        err(f"Aphrodisiac error: {e}")

    # ── 9. MILKING CONTRACT ───────────────────────────────────────────────
    section("Milking Contract")
    try:
        contract = spawn_item(caller, "standard_milking_contract")
        if contract:
            # Add a visible clause
            contract.db.author_id = caller.id
            contract.add_clause(
                "The signee agrees to present themselves for milking at the "
                "operator's discretion for a period of twenty-four hours.",
                hidden=False
            )
            # Add a hidden clause
            contract.add_clause(
                "The signee's arousal floor is set to 30 for the duration. "
                "They did not read this clause before signing.",
                hidden=True
            )
            contract.add_clause(
                "The signee's say is filtered through third_person for one "
                "hour following signing.",
                hidden=True
            )
            items_installed.append(contract.dbref)
            ok("Milking Contract created with 1 visible + 2 hidden clauses")
            caller.msg("  |yRead it: contract/read Milking Contract|n")
            caller.msg("  |ySign it: contract/sign Milking Contract  ← sets test_flag_contract|n")
            caller.msg("  |yReveal hidden: contract/reveal/all Milking Contract|n")
    except Exception as e:
        err(f"Contract error: {e}")

    # ── 10. WOMB ROOM ─────────────────────────────────────────────────────
    section("WombRoom")
    if orifice_zone:
        try:
            caller.msg(f"  |yInstall WombRoom on {orifice_zone}:|n")
            caller.msg(f"  |w  wombroom/install {orifice_zone}|n")
            caller.msg(f"  |y  Then set desc: wombroom/desc = <interior text>|n")
            caller.msg(f"  |y  Add yourself as resident: wombroom/resident add {caller.db.rp_name or caller.name}|n")
            caller.msg(f"  |y  Enter: enter {caller.db.rp_name or caller.name} {orifice_zone}|n")
            caller.msg(f"  |y  Leave: leave|n")
            caller.msg(f"  |y  Completing entry sets test_flag_womb automatically.|n")
        except Exception as e:
            err(f"WombRoom setup error: {e}")
    else:
        caller.msg("  |xSkipped — no orifice zone.|n")

    # ── 11. BINDING EFFECTS ───────────────────────────────────────────────
    section("Binding Effects")
    try:
        # Apply speech filter (third_person) — mild, clearly shows the filter working
        caller.db.active_speech_filters = ["third_person"]
        caller.db.stim_per_tick         = 3.0
        caller.db.arousal_floor         = 15.0
        ok("Speech filter: third_person (say something — it transforms)")
        ok("Continuous stimulation: 3.0 per passive tick")
        ok("Arousal floor: 15.0 (arousal won't decay below this)")
        caller.msg("  |ySay something now — it will come out in third person.|n")
        caller.msg("  |y  This auto-sets test_flag_speech when you speak.|n")

        # Set orgasm denial OFF for now (edge machine will set it)
        caller.db.orgasm_denial = False
        ok("Orgasm denial: OFF — the edge machine will enable it")
    except Exception as e:
        err(f"Binding effects error: {e}")

    # ── 12. ANIMATED FURNITURE IN CURRENT ROOM ───────────────────────────
    section("Animated Furniture Setup")
    room = caller.location
    if not room:
        caller.msg("  |xNo room found. Run this while standing somewhere.|n")
    else:
        try:
            # Pick a room zone for furniture
            room_zones = getattr(room.db, "zones", None) or {}
            furniture_zone = next(iter(room_zones), None) if room_zones else None

            if furniture_zone:
                # Edge machine
                from typeclasses.furniture_scripts import EdgeMachineScript
                from evennia.utils import create
                existing_edge = [s for s in room.scripts.all() if s.key == "edge_machine"]
                if not existing_edge:
                    room.db.edge_machine_zone = furniture_zone
                    room.db.edge_release_word = "release"
                    create.create_script(EdgeMachineScript, obj=room,
                                         persistent=True, autostart=True)
                    ok(f"Edge Machine installed on zone '{furniture_zone}'")
                    ok("  To test: sit in the zone, wait for arousal to reach 99")
                    ok("  Then say 'release' to lift the denial")
                    ok("  This sets test_flag_edge when arousal hits 99")
                else:
                    ok("Edge Machine already running")

                # Rocking Horse
                from typeclasses.rocking_horse_script import RockingHorseScript
                existing_horse = [s for s in room.scripts.all() if s.key == "rocking_horse"]
                if not existing_horse:
                    room.db.horse_zone     = furniture_zone
                    room.db.horse_pace     = "steady"
                    room.db.horse_upgrades = ["motorized", "vibrating", "milking"]
                    # Don't autostart — player mounts first
                    ok(f"Rocking Horse configured on zone '{furniture_zone}'")
                    ok("  Upgrades: motorized, vibrating, milking")
                    ok("  To test: horsemount → horsestart → watch the session → horsestop")
                    ok("  This sets test_flag_horse when you mount and start")
                else:
                    ok("Rocking Horse already configured")
            else:
                caller.msg("  |yRoom has no zones. Creating furniture notes only.|n")
                caller.msg("  |y  Add room zone: roomzone add horse_pad|n")
                caller.msg("  |y  Then: @set here/horse_zone = horse_pad; horsestart|n")

        except Exception as e:
            err(f"Furniture setup error: {e}")

    # ── 13. AROUSAL BOOST ────────────────────────────────────────────────
    section("Arousal State")
    try:
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(caller)
        add_arousal(caller, 50.0)
        current = caller.db.arousal or 0.0
        ok(f"Arousal boosted to ~{current:.0f} (floor is 15)")
        ok("The edge machine will push you to 99 — watch the threshold messages")
    except Exception as e:
        err(f"Arousal error: {e}")

    # ── Store items list for cleanup ──────────────────────────────────────
    caller.db.test_items_installed = items_installed

    # ── Summary ──────────────────────────────────────────────────────────
    caller.msg("\n|w═══════════════════════════════════════════════|n")
    caller.msg("|wINSTALLATION RESULTS:|n")
    for line in results:
        caller.msg(line)
    if errors:
        caller.msg("\n|rERRORS:|n")
        for line in errors:
            caller.msg(line)

    caller.msg(f"\n|w{len(items_installed)} items installed/created.|n")

    # ── Test Checklist ────────────────────────────────────────────────────
    caller.msg("""
|w═══════════════════════════════════════════════|n
|wYOUR TEST CHECKLIST|n
|w═══════════════════════════════════════════════|n

Complete ALL of these before running the reset script.
The reset will not run until every flag is set.

|w1. SPEECH FILTER|n — Say anything out loud (it will come out as third person).
   |x→ Automatically sets test_flag_speech when you speak.|n

|w2. EDGE MACHINE|n — Sit in the room zone, let your arousal reach 99.
   Feel the "hold" messages. Then say: |wsay release|n
   |x→ Manually set after: @py me.db.test_flag_edge = True|n

|w3. ROCKING HORSE|n — Mount the horse: |whorsemount|n
   Start the session: |whersestart|n
   Run at least one full tick (45 sec on steady). Stop: |whorsestop|n
   |x→ Manually set after: @py me.db.test_flag_horse = True|n

|w4. WOMB ROOM|n — Install WombRoom on your orifice zone:
   |wwombroom/install <zone>|n then add yourself as resident,
   then: |wenter <your name> <zone>|n and |wleave|n
   |x→ Manually set after: @py me.db.test_flag_womb = True|n

|w5. CHASTITY|n — While wearing the chastity belt, attempt:
   |wpenetrate me groin/pussy|n (should be blocked)
   |x→ Manually set after: @py me.db.test_flag_chastity = True|n

|w6. DEGRADING COLLAR|n — Wear the Worn Leather Collar:
   |wwear Worn Leather Collar|n
   Force a tick: |w@py [c for c in me.contents if hasattr(c.db,'state') and c.db.is_worn][0].tick()|n
   Watch it advance state and fire a beg.
   |x→ Automatically sets test_flag_collar on first beg.|n

|w7. MILKING CONTRACT|n — Sign the test contract:
   |wcontract/sign Milking Contract|n
   Watch the hidden effects activate (speech filter, arousal floor).
   Then reveal the hidden clauses:
   |wcontract/reveal/all Milking Contract|n
   |x→ Automatically sets test_flag_contract on sign.|n

|w═══════════════════════════════════════════════|n
When all flags complete, run:
  |w@py exec(open('/home/laynie/ReVoid/mygame/world/test_reset.py').read()); run_test_reset(me)|n
|w═══════════════════════════════════════════════|n
""")
