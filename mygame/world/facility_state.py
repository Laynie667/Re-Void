"""
world/facility_state.py

Single source of truth for the flat per-character db flags the facility installs,
and their reset defaults. Both reset paths — realm_build.force_clear() and
facility_build.run_facility_reset() — call apply_reset_flags() so a new flag added
HERE is cleared by both, automatically. No more "forgot to add it to one path."

This covers the flat attribute flags ONLY. Structural teardown — deleting tracked
items, restoring backed-up zone descs / name / title / consent, stopping scripts,
removing freeform marks and item-created zones — stays in each reset path, because
those steps are order-sensitive and path-specific. When you add a new flat facility
flag anywhere, add it to FACILITY_FLAGS below and you're done.
"""

# attr_name -> reset default value
FACILITY_FLAGS = {
    # --- lists -> [] ---
    "active_speech_filters": [], "installed_triggers": [], "facility_brands": [],
    "permanent_gape": [], "piercings": [], "pet_trigger_sources": [], "bred_by": [],
    "sensation_broadcast_targets": [], "aphrodisiac_expirations": [],
    "conditioning_applied": [], "facility_items": [], "facility_room_zones": [],
    "gallery_demands": [], "banned_words": [],

    # --- dicts/scalars -> None ---
    "pet_type": None, "designation": None, "facility_name_backup": None,
    "breeding_quota": None, "milk_quota": None, "holes": None, "gape": None,
    "offspring_progress": None, "offspring_counts": None, "offspring_roster": None,
    "facility_title_backup": None, "forced_posture": None, "body_language": None,
    "room_bound": None, "facility_zone": None, "facility_furniture": None,
    "intake_provocations": None, "intake_door_opened": None, "found_captive_ring": None,
    "facility_forgotten": None, "bethany_clauses": None, "facility_created_zones": None,
    "pregnancy": None, "belly_desc_backup": None, "pregnancy_belly": None,
    "sleeve_desc_backup": None, "pen_plugged": None, "facility_owner": None,
    "sale_price": None, "facility_grade": None, "facility_brand": None,
    "high_bid": None, "high_bidder": None, "high_bidder_id": None, "auction_floor": None,
    "facility_credits": None, "facility_ledger": None,
    "facility_house": None, "facility_house_ledger": None, "facility_upgrades": None,
    "facility_polaroids": None, "get_bounty": None, "word_swaps": None,
    "conditioning_consent": None, "pending_conditioning": None, "body_parts": None,
    "release_terms": None,

    # --- numbers -> 0 ---
    "conditioning": 0, "arousal_floor": 0, "stim_per_tick": 0, "bladder_ml": 0,
    "arousal": 0, "defiance": 0, "compliance_threshold": 0, "compliance_streak": 0,
    "processing_tier": 0, "facility_standing": 0, "drug_dependence": 0,
    "milk_baseline_ml": 0, "suggestibility": 0, "intake_suggestibility": 0,
    "docility": 0, "bethany_devotion": 0, "cycle_day": 0,
    "line_pass": 0, "punish_shield": 0, "liberation_runs": 0, "quota_behind": 0,
    "curse_tally_count": 0,
    "cond_bonus": 0, "milk_bonus": 0, "sale_bonus": 0, "dose_bonus": 0,
    "collections_level": 0,

    # --- booleans -> False ---
    "orgasm_denial": False, "exhibition_active": False, "self_cmds_locked": False,
    "endcycle_blocked": False, "navigation_locked": False, "anti_clothing_active": False,
    "conditioning_permanent": False, "freedom_forfeited": False, "facility_signed": False,
    "facility_active": False, "perpetual_heat": False, "cum_craving": False,
    "lactation_locked": False, "body_processing_locked": False, "aura_dimmed": False,
    "bethany_busy": False, "bethany_owned": False, "latex_sealed": False,
    "bethany_branded": False, "bethany_collar": False, "bethany_line_only": False,
    "animal_sleeve": False, "pen_filth": False, "pen_scented": False,
    "auction_open": False, "bethany_owned_get": False, "facility_escaped": False,
    "nugget": False, "limb_lock": False, "sensory_hood": False, "total_dependence": False,
    "nugget_rings": False,
    "indentured": False, "bethany_ledger_bond": False, "arrears_laced": False,
    "ledger_tattooed": False, "bethany_tithe": False, "bethany_heir": False,
    "curse_line_remembers": False, "curse_never_empty": False,
    "curse_tally": False, "curse_echo": False, "curse_hollow": False,

    # --- strings -> "" ---
    "orgasm_release_word": "", "required_honorific": "", "breeding_line": "",
    "nugget_appendages": "",
}


def apply_reset_flags(character):
    """Set every facility flat-flag on `character` to its reset default. Safe and
    idempotent; copies list defaults so they aren't shared. Returns count set."""
    if not character:
        return 0
    d = character.db
    n = 0
    for attr, default in FACILITY_FLAGS.items():
        try:
            setattr(d, attr, list(default) if isinstance(default, list) else default)
            n += 1
        except Exception:
            pass
    return n
