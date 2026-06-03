"""
world/test_reset.py

Re:Void test reset script.
Cleans up everything installed by test_build.py.

Run in-game:
  @py exec(open('/home/laynie/ReVoid/mygame/world/test_reset.py').read()); run_test_reset(me)

All 7 test flags must be completed before this will run.
"""


def run_test_reset(caller):

    caller.msg("\n|w═══════════════════════════════════════════════|n")
    caller.msg("|wRe:Void TEST RESET — Checking flags...|n")
    caller.msg("|w═══════════════════════════════════════════════|n\n")

    # ── Check flags ───────────────────────────────────────────────────────
    flags = {
        "Speech filter tested":    getattr(caller.db, "test_flag_speech",   False),
        "Edge machine completed":  getattr(caller.db, "test_flag_edge",     False),
        "Rocking horse ridden":    getattr(caller.db, "test_flag_horse",    False),
        "WombRoom entered":        getattr(caller.db, "test_flag_womb",     False),
        "Chastity block verified": getattr(caller.db, "test_flag_chastity", False),
        "Degrading collar ticked": getattr(caller.db, "test_flag_collar",   False),
        "Contract signed":         getattr(caller.db, "test_flag_contract", False),
    }

    all_done = all(flags.values())
    missing  = [k for k, v in flags.items() if not v]

    for name, done in flags.items():
        status = "|g✓|n" if done else "|r✗|n"
        caller.msg(f"  {status} {name}")

    if not all_done:
        caller.msg(f"\n|rReset blocked — {len(missing)} flag(s) incomplete:|n")
        for m in missing:
            caller.msg(f"  |r→ {m}|n")
        caller.msg("\n|yComplete the checklist first. Set flags manually if you tested a mechanic|n")
        caller.msg("|y  but the auto-flag didn't fire — see STAFF_COMMANDS.txt for @py overrides.|n")
        return

    caller.msg("\n|gAll flags complete! Proceeding with cleanup...|n\n")

    errors = []

    def safe(label, fn):
        try:
            fn()
            caller.msg(f"  |g✓|n {label}")
        except Exception as e:
            errors.append(f"  |r✗|n {label}: {e}")

    # ── Remove installed test items ───────────────────────────────────────
    caller.msg("|w── Removing test items ──|n")
    item_dbrefs = list(getattr(caller.db, "test_items_installed", None) or [])
    removed = 0
    for dbref in item_dbrefs:
        try:
            from evennia import search_object
            results = search_object(dbref, exact=True)
            if results:
                obj = results[0]
                # Force-remove if worn/inserted
                if hasattr(obj, "remove"):
                    obj.remove(force=True)
                obj.delete()
                removed += 1
        except Exception as e:
            errors.append(f"  Could not remove {dbref}: {e}")
    caller.msg(f"  |g✓|n {removed} test items removed")

    # ── Remove any remaining test items by scanning inventory ────────────
    caller.msg("|w── Scanning inventory for leftovers ──|n")
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

    test_types = (
        PlugItem, CollarItem, LeashItem, WearableItem, ChastityItem,
        VibratingPlugItem, RemoteControlItem, BrandItem, AphrodisiacItem,
        MilkingContract, DegradingCollar, PermanentBindingCollar, PiercingItem,
    )
    leftover_removed = 0
    for obj in list(caller.contents):
        if isinstance(obj, test_types):
            try:
                if hasattr(obj, "remove"):
                    obj.remove(force=True)
                obj.delete()
                leftover_removed += 1
            except Exception:
                pass
    if leftover_removed:
        caller.msg(f"  |g✓|n {leftover_removed} additional test items cleaned up")

    # ── Clear WombRoom ────────────────────────────────────────────────────
    caller.msg("|w── WombRoom ──|n")
    safe("WombRoom uninstalled", lambda: _clear_wombroom(caller))

    # ── Remove freeform brands/marks ──────────────────────────────────────
    caller.msg("|w── Freeform marks ──|n")
    safe("Freeform test items cleared", lambda: _clear_freeform_brands(caller))

    # ── Stop furniture scripts ────────────────────────────────────────────
    caller.msg("|w── Furniture scripts ──|n")
    room = caller.location
    if room:
        safe("Edge machine stopped", lambda: _stop_script(room, "edge_machine"))
        safe("Rocking horse stopped", lambda: _stop_script(room, "rocking_horse"))
        safe("Stanchion stopped", lambda: _stop_script(room, "milking_stanchion"))
        safe("Room flags cleared", lambda: _clear_room_flags(room))

    # ── Clear all binding effects ─────────────────────────────────────────
    caller.msg("|w── Binding effects ──|n")
    safe("All binding effects cleared", lambda: _clear_effects(caller))

    # ── Clear zone mechanics installed by test ────────────────────────────
    caller.msg("|w── Zone mechanics ──|n")
    safe("Test zone mechanics cleared", lambda: _clear_zone_test_mechanics(caller))

    # ── Reset arousal ─────────────────────────────────────────────────────
    caller.msg("|w── Arousal state ──|n")
    safe("Arousal reset to 0", lambda: setattr(caller.db, "arousal", 0.0))

    # ── Clear test flags ──────────────────────────────────────────────────
    caller.msg("|w── Test flags ──|n")
    def _clear_flags():
        for flag in ["test_build_active", "test_flag_edge", "test_flag_horse",
                     "test_flag_womb", "test_flag_speech", "test_flag_chastity",
                     "test_flag_collar", "test_flag_contract", "test_items_installed"]:
            setattr(caller.db, flag, None)
    safe("Test flags cleared", _clear_flags)

    # ── Report ────────────────────────────────────────────────────────────
    if errors:
        caller.msg("\n|rErrors during cleanup:|n")
        for e in errors:
            caller.msg(e)

    caller.msg("""
|w═══════════════════════════════════════════════|n
|gTest reset complete. Character restored to baseline.|n
|w═══════════════════════════════════════════════|n

Your character is now clean. All test items, mechanics,
effects, and scripts have been removed.

A full @reload is recommended after a test run:
  evennia reload   (from the server terminal)
  or: @reload      (in-game, superuser)
""")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clear_wombroom(caller):
    from typeclasses.womb_room import WombRoom
    zones = getattr(caller.db, "zones", None) or {}
    for zone_name, zone_data in zones.items():
        mech = (zone_data or {}).get("mechanics") or {}
        wr_entry = mech.get("womb_room")
        if wr_entry:
            from evennia import search_object
            results = search_object(wr_entry.get("room_dbref", ""), exact=True)
            if results and isinstance(results[0], WombRoom):
                results[0].uninstall()
                results[0].delete()


def _clear_freeform_brands(caller):
    items = dict(caller.db.freeform_items or {})
    to_remove = [k for k, v in items.items() if (v or {}).get("brand")]
    for k in to_remove:
        items.pop(k, None)
    caller.db.freeform_items = items


def _stop_script(room, key):
    for s in list(room.scripts.all()):
        if s.key == key:
            s.stop()


def _clear_room_flags(room):
    for attr in ["edge_machine_zone", "edge_release_word",
                 "horse_zone", "horse_pace", "horse_upgrades",
                 "stanchion_zone", "stanchion_speed"]:
        if hasattr(room.db, attr):
            setattr(room.db, attr, None)


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


def _clear_zone_test_mechanics(caller):
    zones = dict(getattr(caller.db, "zones", None) or {})
    changed = False
    test_keys = {"plug", "collar", "chastity", "womb_room"}
    for zone_name, zone_data in zones.items():
        if not isinstance(zone_data, dict):
            continue
        mech = dict(zone_data.get("mechanics") or {})
        removed = [k for k in mech if k in test_keys or k.startswith("piercing_")]
        if removed:
            for k in removed:
                mech.pop(k)
            zone_data = dict(zone_data)
            zone_data["mechanics"] = mech
            zones[zone_name] = zone_data
            changed = True
    if changed:
        caller.db.zones = zones
