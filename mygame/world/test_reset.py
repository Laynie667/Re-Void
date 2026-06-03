"""
world/test_reset.py — Re:Void test session cleanup

Run AFTER all 13 test flags are complete:
  @py exec(open('/home/laynie/ReVoid/mygame/world/test_reset.py').read()); run_test_reset(me)

Or force reset (skip flag check) — only if something went wrong:
  @py exec(open('/home/laynie/ReVoid/mygame/world/test_reset.py').read()); run_test_reset(me, force=True)
"""


_FLAG_LABELS = {
    "test_flag_speech":    "Speech filter tested",
    "test_flag_edge":      "Edge machine — arousal 99 reached",
    "test_flag_horse":     "Rocking horse — full session",
    "test_flag_womb":      "WombRoom — entered and exited",
    "test_flag_chastity":  "Chastity — penetrate attempt blocked",
    "test_flag_collar":    "Degrading collar — ticked and begged",
    "test_flag_contract":  "Contract — signed and hidden revealed",
    "test_flag_cycle":     "Cycle machine — phase completed",
    "test_flag_body_mods": "Body mods — zone tokens verified",
    "test_flag_inflation": "Inflation — inflate/check/drain done",
    "test_flag_pet":       "Pet triggers — full sequence run",
    "test_flag_arousal":   "Arousal — all four thresholds passed",
    "test_flag_womb_flood":"WombRoom flood — knee-deep level seen",
}


def run_test_reset(caller, force: bool = False):

    caller.msg("\n|w══════════════════════════════════════════════|n")
    caller.msg("|wRe:Void — TEST RESET|n")
    caller.msg("|w══════════════════════════════════════════════|n\n")

    # ── Flag check ────────────────────────────────────────────────────
    if not force:
        missing = [label for flag, label in _FLAG_LABELS.items()
                   if not getattr(caller.db, flag, False)]
        if missing:
            caller.msg(f"|r{len(missing)} flag(s) not yet complete:|n")
            for m in missing:
                caller.msg(f"  |r→|n {m}")
            caller.msg(
                "\n|yComplete these before resetting. "
                "Ask the Adjudicator: say status|n\n"
                "|yTo force reset anyway: run_test_reset(me, force=True)|n"
            )
            return
        caller.msg("|gAll 13 flags verified. Proceeding with cleanup.|n\n")
    else:
        caller.msg("|yForced reset — skipping flag check.|n\n")

    errors = []

    def safe(label, fn):
        try:
            fn()
            caller.msg(f"  |g✓|n {label}")
        except Exception as e:
            errors.append(f"  |r✗|n {label}: {e}")

    # ── Remove test items ──────────────────────────────────────────────
    caller.msg("|w── Removing test items ──|n")
    item_dbrefs = list(getattr(caller.db, "test_items_installed", None) or [])
    removed = 0
    for dbref in item_dbrefs:
        try:
            from evennia import search_object
            results = search_object(dbref, exact=True)
            if results:
                obj = results[0]
                if hasattr(obj, "remove"):
                    try: obj.remove(force=True)
                    except Exception: pass
                obj.delete()
                removed += 1
        except Exception:
            pass
    caller.msg(f"  |g✓|n {removed} tracked test items removed")

    # ── Scan inventory for leftovers by typeclass ──────────────────────
    caller.msg("|w── Scanning inventory ──|n")
    leftover = 0
    try:
        from typeclasses.plug_item import PlugItem
        from typeclasses.collar_item import CollarItem, LeashItem
        from typeclasses.wearable_item import WearableItem
        from typeclasses.chastity_item import ChastityItem
        from typeclasses.vibration_item import VibratingPlugItem, RemoteControlItem
        from typeclasses.brand_item import BrandItem
        from typeclasses.aphrodisiac_item import AphrodisiacItem
        from typeclasses.milking_contract import MilkingContract
        from typeclasses.degrading_collar import DegradingCollar
        from typeclasses.permanent_binding_collar import PermanentBindingCollar
        from typeclasses.piercing_item import PiercingItem
        from typeclasses.adjudicator_npc import AdjudicatorNPC
        from typeclasses.body_mod_item import BodyModItem
        from typeclasses.production_item import ProductionItem

        test_types = (
            PlugItem, CollarItem, LeashItem, WearableItem, ChastityItem,
            VibratingPlugItem, RemoteControlItem, BrandItem, AphrodisiacItem,
            MilkingContract, DegradingCollar, PermanentBindingCollar, PiercingItem,
        )
        # Remove from inventory
        for obj in list(caller.contents):
            if isinstance(obj, test_types):
                try:
                    if hasattr(obj, "remove"): obj.remove(force=True)
                    obj.delete(); leftover += 1
                except Exception: pass

        # Remove Adjudicator from room
        room = caller.location
        if room:
            for obj in list(room.contents):
                if isinstance(obj, AdjudicatorNPC):
                    try: obj.delete(); leftover += 1
                    except Exception: pass

        # Remove test body mods (installed on character zones)
        for obj in list(caller.contents):
            if isinstance(obj, (BodyModItem, ProductionItem)):
                if "Test" in (obj.key or ""):
                    try:
                        if hasattr(obj, "uninstall"): obj.uninstall()
                        obj.delete(); leftover += 1
                    except Exception: pass

        caller.msg(f"  |g✓|n {leftover} additional items cleaned up")
    except Exception as e:
        errors.append(f"  Inventory scan: {e}")

    # ── WombRoom ──────────────────────────────────────────────────────
    caller.msg("|w── WombRoom ──|n")
    safe("WombRoom uninstalled", lambda: _clear_wombroom(caller))

    # ── Freeform brands/marks ─────────────────────────────────────────
    caller.msg("|w── Freeform marks ──|n")
    safe("Temp brands removed", lambda: _clear_brands(caller))

    # ── Furniture scripts ─────────────────────────────────────────────
    caller.msg("|w── Furniture scripts ──|n")
    room = caller.location
    if room:
        for key in ("edge_machine", "rocking_horse", "milking_stanchion",
                    "display_pedestal", "sensory_deprivation"):
            safe(f"Stop {key}", lambda k=key: _stop_script(room, k))
        safe("Room test flags cleared", lambda: _clear_room_flags(room))

    # ── Cycle machine scripts on caller ───────────────────────────────
    caller.msg("|w── Cycle machine ──|n")
    safe("Cycle scripts stopped", lambda: _stop_cycles(caller))

    # ── Inflation drainage ────────────────────────────────────────────
    caller.msg("|w── Inflation ──|n")
    safe("All zone inflation drained", lambda: _drain_inflation(caller))

    # ── Zone test mechanics ───────────────────────────────────────────
    caller.msg("|w── Zone mechanics ──|n")
    safe("Test mechanics cleared from zones", lambda: _clear_zone_mechanics(caller))

    # ── Binding effects ───────────────────────────────────────────────
    caller.msg("|w── Binding effects ──|n")
    safe("All binding effects cleared", lambda: _clear_effects(caller))

    # ── Arousal ───────────────────────────────────────────────────────
    caller.msg("|w── Arousal ──|n")
    safe("Arousal reset to 0", lambda: setattr(caller.db, "arousal", 0.0))

    # ── Test flags ────────────────────────────────────────────────────
    caller.msg("|w── Test flags ──|n")
    def _clear_flags():
        for f in list(_FLAG_LABELS.keys()) + [
            "test_build_active", "test_items_installed",
            "test_flag_complete", "test_led_by_backup",
        ]:
            setattr(caller.db, f, None)
    safe("Test flags cleared", _clear_flags)

    # ── led_by cleanup ────────────────────────────────────────────────
    caller.msg("|w── Lead state ──|n")
    safe("led_by cleared", lambda: setattr(caller.db, "led_by", None))

    # ── Results ───────────────────────────────────────────────────────
    if errors:
        caller.msg("\n|rNon-fatal errors:|n")
        for e in errors: caller.msg(e)

    caller.msg("""
|w══════════════════════════════════════════════|n
|gReset complete. Character restored to baseline.|n
|w══════════════════════════════════════════════|n

Recommend a full reload before continuing:
  evennia reload   (terminal)
  @reload          (in-game superuser)
""")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clear_wombroom(caller):
    from typeclasses.womb_room import WombRoom
    zones = getattr(caller.db, "zones", None) or {}
    for zone_name, zd in zones.items():
        wr = (zd or {}).get("mechanics", {}).get("womb_room")
        if wr:
            from evennia import search_object
            results = search_object(wr.get("room_dbref", ""), exact=True)
            if results and isinstance(results[0], WombRoom):
                results[0].uninstall()
                try: results[0].delete()
                except Exception: pass


def _clear_brands(caller):
    items = dict(caller.db.freeform_items or {})
    before = len(items)
    items  = {k: v for k, v in items.items() if not (v or {}).get("brand")}
    caller.db.freeform_items = items


def _stop_script(room, key):
    for s in list(room.scripts.all()):
        if s.key == key:
            s.stop()


def _clear_room_flags(room):
    for attr in ["edge_machine_zone", "edge_release_word", "horse_zone",
                 "horse_pace", "horse_upgrades", "stanchion_zone",
                 "stanchion_speed", "pedestal_zone"]:
        if hasattr(room.db, attr):
            setattr(room.db, attr, None)


def _stop_cycles(caller):
    from typeclasses.cycle_script import CycleScript
    for s in list(caller.scripts.all()):
        if isinstance(s, CycleScript):
            s.stop()


def _drain_inflation(caller):
    from typeclasses.inflation_item import drain_inflation, get_inflation_data
    zones = getattr(caller.db, "zones", None) or {}
    for zone_name in list(zones.keys()):
        if get_inflation_data(caller, zone_name):
            drain_inflation(caller, zone_name)


def _clear_zone_mechanics(caller):
    zones = dict(getattr(caller.db, "zones", None) or {})
    test_keys = {"plug", "collar", "chastity", "womb_room", "inflation"}
    changed = False
    for zn, zd in zones.items():
        if not isinstance(zd, dict): continue
        mech = dict(zd.get("mechanics") or {})
        to_remove = [k for k in mech if k in test_keys or k.startswith("piercing_")]
        if to_remove:
            for k in to_remove: mech.pop(k)
            zd = dict(zd); zd["mechanics"] = mech
            zones[zn] = zd; changed = True
    if changed:
        caller.db.zones = zones


def _clear_effects(caller):
    caller.db.orgasm_denial               = False
    caller.db.orgasm_denial_lifted        = False
    caller.db.orgasm_release_word         = ""
    caller.db.arousal_floor               = 0.0
    caller.db.stim_per_tick               = 0.0
    caller.db.navigation_locked           = False
    caller.db.forced_posture              = None
    caller.db.exhibition_active           = False
    caller.db.anti_clothing_active        = False
    caller.db.outfit_camouflage           = ""
    caller.db.active_speech_filters       = []
    caller.db.pet_trigger_sources         = []
    caller.db.pet_type                    = None
    caller.db.room_bound                  = None
    caller.db.say_locked_until            = 0
    caller.db.sensation_broadcast_targets = []
    caller.db.required_honorific          = ""
    caller.db.wolf_bait                   = False
    caller.db.wolf_bait_expires           = 0
    caller.db.aphrodisiac_expirations     = []
    caller.db.stanchion_locked            = False
    caller.db.on_pedestal                 = False
    caller.db.horse_knotted               = False
    caller.db.horse_knot_expires_at       = 0.0
    caller.db.horse_facing                = None
    caller.db.deprivation_locked          = False
    caller.db.binding_consent_backup      = {}
    caller.db.self_cmds_locked            = False
    caller.db.led_by                      = None
    # Restore default consent flags
    caller.db.consent_flags = {
        "casual":      True,
        "intimate":    False,
        "mature":      False,
        "bdsm":        False,
        "lead_follow": False,
        "restraint":   False,
        "plock":       False,
    }
