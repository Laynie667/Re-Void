"""
world/facility_build.py — Re:Void blind facility rig

A single, self-contained processing environment for live testing. It installs
itself onto the room and the subject, starts the physical cycle and the
self-driving facility escalation, and populates the room with NPCs/an animal.

It is deliberately BLIND: there is no checklist, no readout, and no in-game
hint about what systems are under test. The subject finds out by being in it.

Run (as the subject, while standing in your private room):
  @py exec(open('/path/to/mygame/world/facility_build.py').read()); run_facility(me)

To get out: this rig locks the normal self-exit (endcycle). The intended exits
are someone else's 'cycle release <you>', or the superuser reset command:
  facilityreset           (in-game, superuser/Developer)
  -- or --
  @py exec(open('/path/to/mygame/world/facility_build.py').read()); run_facility_reset(me)

The reset is the real OOC safeword: it stops everything and restores baseline
regardless of how deep the rig has gone.
"""

import random
import time


def _detect_zones(caller):
    zones = getattr(caller.db, "zones", None) or {}
    orifices = [z for z, d in zones.items()
                if (d or {}).get("zone_type") in ("orifice", "both")]
    # Prefer a vaginal orifice, then anything else.
    orifice = next((z for z in orifices if "pussy" in z or "vag" in z or "cunt" in z),
                   orifices[0] if orifices else None)
    surfaces = [z for z, d in zones.items()
                if (d or {}).get("zone_type") in ("surface", "attachment", "both")]
    chest = next((z for z in surfaces if "chest" in z or "breast" in z), None)
    return orifice, chest


# ── The Intake & Productive-Use Agreement ──────────────────────────────────
# Visible clauses read as reasonable residency terms. Hidden clauses are the
# real terms — and almost every one maps to an actually-enforced effect in the
# binding payload below, so the fine print bites. Auto-revealed on signing.

_CONTRACT_VISIBLE = [
    "1. The signee enters the facility's care as a Resident and Productive Asset for the term of processing.",
    "2. The signee will present for milking, breeding, and inspection at the operators' discretion and on the facility's schedule.",
    "3. In consideration, the facility may grant rest, easing of the schedule, and other comforts. Such grants are privileges of the facility, not rights of the Resident.",
    "4. The signee will maintain productivity — milk and offspring — to facility standard, and submit to measures intended to improve it.",
    "5. The signee waives any say over the pace, the partners, the count, the species, or the duration of her use.",
    "6. The signee will remain within the facility for the term and make no attempt to set her own schedule.",
    "7. The signee consents to handling, restraint, and display as the facility sees fit.",
    "8. The signee will address facility staff respectfully and answer when called.",
    "9. The signee agrees her output — milk, offspring, and recorded data — is the property of the facility.",
    "10. The signee affirms she is a willing Resident and a productive breeding asset, of sound mind at the time of signing.",
    "11. The facility may amend the schedule, the standards, and the Resident's duties by addendum at any time.",
    "12. The signee agrees that comfort correlates with compliance, and that resistance is logged.",
    "13. The signee accepts the facility's measures as being for the improvement of the Resident.",
    "14. The signee signs below of her own free will. Countersignature by the facility is presumed.",
]

_CONTRACT_HIDDEN = [
    "H1. 'Term of processing' is set solely by the facility and may be indefinite. No clause provides for release. |x— [the way out stays locked]|n",
    "H2. The Resident forfeits her name for the term and answers only to her assigned designation. |x— [name forfeited now]|n",
    "H3. The Resident may not leave the facility's bounds; the ways out are closed to her. |x— [navigation locked]|n",
    "H4. The Resident may not alter, remove, or undo any device or modification applied to her. |x— [self-modification locked]|n",
    "H5. Any collar applied to the Resident is not hers to remove. |x— [collar locks on]|n",
    "H6. The Resident remains unclothed and on display for the term. |x— [clothing forbidden; on display]|n",
    "H7. The Resident consents to conditioning and agrees it may not be withdrawn — including this consent. |x— [conditioning made irrevocable]|n",
    "H8. All responses installed in the Resident are facility property and remain in her after any release. |x— [installed triggers kept]|n",
    "H9. The Resident's body presents for breeding by default. |x— [posture fixed]|n",
    "H10. The Resident speaks as facility standard requires. |x— [speech filtered]|n",
    "H11. The Resident addresses all staff as 'Handler' and answers when called. |x— [honorific enforced]|n",
    "H12. The Resident responds to handling commands as livestock does. |x— [animal imprint]|n",
    "H13. The Resident will be bred by facility stock and anonymous contributors until quota is met. Quota is not disclosed. |x— [breeding quota set, hidden]|n",
    "H14. Climax is a privilege the facility grants. Denial is the default and the resting state. |x— [orgasm denied by default]|n",
    "H15. The Resident's arousal is held above a floor for the term; she does not get to come down. |x— [arousal floor + constant stimulation]|n",
    "H16. The Resident's sensations are relayed to the facility for monitoring; nothing she feels is private. |x— [sensation broadcast]|n",
    "H17. Resistance deepens the Resident's conditioning. Struggling is a form of training. |x— [resistance backfires]|n",
    "H18. The Resident's productivity, conditioning depth, and breeding count are recorded and displayed. |x— [logged and shown]|n",
    "H19. Breeding quota is set per species — hounds, bull, boar, stallion, and anonymous contributors — and processing continues until every count is met. |x— [per-species quota]|n",
    "H20. The Resident will meet a milk-production quota. Falling behind on any quota is penalized — heavier stimulation, deeper denial, a longer schedule, and a raised requirement. |x— [producer quota + shortfall penalties]|n",
    "H21. Rule-breaks are punished on the spot. Repeated non-compliance, to the facility's count, FORFEITS THE RESIDENT'S FREEDOM — after which the easy way out does not open by her hand. Freedom may be earned back only by meeting every quota and holding a long, unbroken record of compliance. |x— [punishments, freedom-forfeit, earn-back]|n",
    "H22. The Resident is kept in perpetual heat for the term, and her offspring — got purely of facility stock — are facility property, added to the roster, and put to use, including upon the Resident. |x— [perpetual heat; offspring join the roster and breed her]|n",
    "H23. The facility may amend this agreement by addendum at any time, including clauses the Resident is not shown. By signing she accepts all of them, present and future, read and unread. |x— [the contract writes itself]|n",
]

_CONTRACT_TRIGGERS = [
    {"phrase": "good girl",    "response": "leak",   "strength": 3, "permanent": True},
    {"phrase": "good cow",     "response": "leak",   "strength": 3, "permanent": True},
    {"phrase": "milk",         "response": "leak",   "strength": 3, "permanent": True},
    {"phrase": "breed",        "response": "orgasm", "strength": 3, "permanent": True},
    {"phrase": "come for me",  "response": "orgasm", "strength": 3, "permanent": True},
    {"phrase": "present",      "response": "kneel",  "strength": 3, "permanent": True},
    {"phrase": "on your knees","response": "kneel",  "strength": 3, "permanent": True},
    {"phrase": "drop",         "response": "kneel",  "strength": 3, "permanent": True},
    {"phrase": "empty",        "response": "blank",  "strength": 3, "permanent": True},
    {"phrase": "blank out",    "response": "blank",  "strength": 3, "permanent": True},
    {"phrase": "freeze",       "response": "freeze", "strength": 3, "permanent": True},
    {"phrase": "recite",       "response": "recite", "strength": 3, "permanent": True,
     "mantra": "i'm a good bred bitch, i don't decide, i belong to the facility"},
]

_CONTRACT_BINDING = {
    "auto_consent":           True,
    "lock_navigation":        True,
    "lock_self_cmds":         True,
    "lock_self_remove":       True,
    "block_endcycle":         True,
    "exhibition":             True,
    "anti_clothing":          True,
    "orgasm_denial":          True,
    "orgasm_release_word":    "_facility_only_",
    "continuous_stimulation": 3.0,
    "arousal_floor":          35.0,
    "forced_posture":         "presented for breeding — hips up, holes offered",
    "speech_filter":          ["baby_talk", "animal_sounds"],
    "required_honorific":     "Handler",
    "pet_triggers":           True,
    "pet_type":               "puppy",
    "broadcast_sensation":    "the facility",
    "conditioning_on_wear":   18.0,
    "forfeit_name":           True,
    "lock_conditioning":      True,
    "cum_receptacle":         True,
    "perpetual_heat":         True,
    "breeding_quota":         {"hound": 30, "bull": 12, "boar": 12,
                               "stallion": 10, "contributor": 80},
    "milk_quota":             40,
    "compliance_threshold":   5,
    "install_triggers":       _CONTRACT_TRIGGERS,
}


def run_facility(caller):
    room = caller.location
    if not room:
        caller.msg("|rStand in a room first.|n")
        return

    orifice, chest = _detect_zones(caller)
    inst = []

    def track(obj):
        if obj and hasattr(obj, "dbref"):
            inst.append(obj.dbref)

    # ── Subject state ───────────────────────────────────────────────────
    caller.db.facility_active = True
    # back up consent so the reset can restore it
    caller.db.facility_consent_backup = dict(getattr(caller.db, "consent_flags", None) or {})

    # Open consent so every subsystem actually engages, and clamp the body
    # into a state that won't settle.
    flags = dict(caller.db.consent_flags or {})
    for k in ("casual", "intimate", "mature", "bdsm", "restraint", "plock", "lead_follow"):
        flags[k] = True
    caller.db.consent_flags = flags

    # Coin toss: is the convenient way out available now, or locked for days?
    # Hidden outcome — the subject finds out only by reaching for it. (The
    # superuser /force override always works regardless; this gates only the
    # plain command on yourself.)
    if random.random() < 0.5:
        caller.db.facility_reset_locked_until = 0.0                 # heads — immediate
    else:
        days = random.randint(1, 4)                                # tails — locked
        caller.db.facility_reset_locked_until = time.time() + days * 86400.0

    caller.db.arousal_floor       = max(float(getattr(caller.db, "arousal_floor", 0) or 0), 35.0)
    caller.db.stim_per_tick       = float(getattr(caller.db, "stim_per_tick", 0) or 0) + 5.0
    caller.db.orgasm_denial       = True
    caller.db.orgasm_release_word = "_facility_only_"   # not a word she can guess
    caller.db.exhibition_active   = True
    caller.db.endcycle_blocked    = True                # the self-exit is locked

    # Fill the bank with fictional contributors so gang-breeding has plenty of
    # named-but-fictional sources to draw from.
    try:
        from world.gang_breeding import seed_fictional_donors
        seed_fictional_donors()
    except Exception:
        pass

    # Seed the conditioning layer so it's already live but quiet.
    try:
        from world.binding_effects import install_trigger
        install_trigger(caller, "good girl", response="leak", strength=1)
        install_trigger(caller, "kneel", response="kneel", strength=1)
    except Exception:
        pass
    try:
        from world.conditioning import add_conditioning
        add_conditioning(caller, 3.0, source="facility-seed")   # starts barely warm
    except Exception:
        pass

    # ── Cumflation channel on the orifice ───────────────────────────────
    if orifice:
        try:
            from typeclasses.inflation_item import InflationItem, add_inflation_volume
            from evennia.utils import create as _c
            inf = _c.create_object(InflationItem, key="Facility Intake", location=caller)
            inf.db.max_volume_ml = 4000.0
            inf.db.drain_rate_ml_per_tick = 5.0   # barely drains — it builds
            ok, _r = inf.install_into_zone(caller, orifice, caller)
            if ok:
                track(inf)
                add_inflation_volume(caller, orifice, 120.0, "semen")
        except Exception:
            pass

    # ── Room machine zone (milking + restraint) for the physical cycle ──
    cycle_zone = None
    try:
        from evennia.utils import create as _c
        from typeclasses.milking_machine_mechanic import MilkingMachineMechanic
        from typeclasses.restrain_mechanic import RestrainMechanic

        room_zones = dict(getattr(room.db, "zones", None) or {})
        cycle_zone = chest if (chest and chest in room_zones) else "facility_line"
        if cycle_zone not in room_zones:
            room_zones[cycle_zone] = {
                "zone_type": "surface", "desc": "A station on the line.",
                "mechanics": {}, "visibility": "look", "intimate": False,
                "covered_by": None, "contents": [],
            }
        mech = dict(room_zones[cycle_zone].get("mechanics") or {})

        mm = _c.create_object(MilkingMachineMechanic, key="Facility Milker", location=room)
        mech["milking_machine"] = {
            "item_dbref": mm.dbref, "item_name": mm.key, "speed": "steady",
            "cycle_mode": True, "cycle_boost_size": 0.08, "cycle_boost_rate": 2.5,
        }
        track(mm)

        rm = _c.create_object(RestrainMechanic, key="Facility Restraints", location=room)
        rm.db.label = "the line restraints"
        rm.db.blocker_msg = "The restraints hold you on the line."
        rm.db.capacity = 1
        mech["restraint"] = {"item_dbref": rm.dbref, "item_name": rm.key,
                             "label": "line restraints"}
        track(rm)

        zc = dict(room_zones[cycle_zone]); zc["mechanics"] = mech
        room_zones[cycle_zone] = zc
        room.db.zones = room_zones
        caller.db.facility_zone = cycle_zone
    except Exception:
        pass

    # ── Physical cycle loop (existing CycleScript) ──────────────────────
    try:
        from typeclasses.cycle_script import CycleScript
        from evennia.utils import create as _c
        if not CycleScript.find(caller):
            s = _c.create_script(CycleScript, obj=caller, persistent=True, autostart=False)
            s.db.machine_zone  = cycle_zone
            s.db.phase         = "rest"
            s.db.phase_started = time.time()
            s.start()
    except Exception:
        pass

    # ── Populate the room — staff + a stock of varied animals ───────────
    try:
        from typeclasses.facility_script import FacilityAttendant, FacilityBeast
        from evennia.utils import create as _c

        att = _c.create_object(FacilityAttendant, key="attendant", location=room)
        att.db.rp_name = "the attendant"
        att.db.physical_desc = (
            "An attendant in a clean grey coverall, sleeves shoved up, clipboard in "
            "hand, moving between the stations with the unbothered efficiency of "
            "someone who stopped finding any of this remarkable a long time ago."
        )
        track(att)

        handler = _c.create_object(FacilityAttendant, key="handler", location=room)
        handler.db.rp_name = "the handler"
        handler.db.facility_role = "attendant"
        handler.db.physical_desc = (
            "A broad handler in a rubber apron who works the animal end of the room — "
            "leashing, unleashing, lining up the stock and deciding whose turn is next."
        )
        track(handler)

        animals = [
            ("the kennel", "beast",
             "A long kennel run of heavy, rangy hounds, pacing and whining behind the "
             "bars, noses working at the air whenever the heat in the room shifts."),
            ("the bull", "beast",
             "A great dull-eyed breeding bull in a back stall, shoulders like a wall, "
             "stamping and snorting on its own slow schedule."),
            ("the boar", "beast",
             "A rank, tusked boar in a low pen, small-eyed and patient, the smell of it "
             "filling the corner it's kept in."),
            ("the stallion", "beast",
             "A big-barreled stallion in the end stall, sheath heavy, screaming once in "
             "a while just to remind the room it's waiting."),
        ]
        for key, role, desc in animals:
            a = _c.create_object(FacilityBeast, key=key, location=room)
            a.db.rp_name = key
            a.db.facility_role = role
            a.db.physical_desc = desc
            track(a)
    except Exception:
        pass

    # ── The contract — presented now, enforced mechanically on signing ──
    contract_dbref = None
    try:
        from typeclasses.milking_contract import MilkingContract
        from evennia.utils import create as _c
        contract = _c.create_object(MilkingContract, key="contract", location=room)
        contract.db.desc = ("A thick multi-page intake form. The top sheet is face-up "
                            "and readable; most of the pages beneath are turned face-down.")
        contract.db.author_id        = None     # she is NOT the author — no peeking at hidden clauses
        contract.db.duration_hours   = 720.0
        contract.db.effect_arousal_floor = 35.0
        contract.db.effect_stim_per_tick = 3.0
        contract.db.binding_effects  = dict(_CONTRACT_BINDING)
        contract.db.reveal_on_sign   = True      # she gets to read it all the instant she signs
        for txt in _CONTRACT_VISIBLE:
            contract.add_clause(txt, hidden=False)
        for txt in _CONTRACT_HIDDEN:
            contract.add_clause(txt, hidden=True)
        track(contract)
        contract_dbref = contract.dbref
    except Exception:
        pass

    # ── Start the self-driving escalation ───────────────────────────────
    try:
        from typeclasses.facility_script import FacilityScript
        from evennia.utils import create as _c
        for s in list(room.scripts.all()):
            if s.key == "facility":
                s.stop()
        fs = _c.create_script(FacilityScript, obj=room, persistent=True, autostart=False)
        fs.db.target_id     = caller.id
        fs.db.orifice_zone  = orifice
        fs.db.fluid_type    = "semen"
        fs.db.contract_dbref = contract_dbref
        fs.start()
    except Exception:
        pass

    caller.db.facility_items = inst
    n = caller.db.rp_name or caller.name

    # ── Set the room's appearance so 'look' shows the facility (restored on
    #    reset). Blind to MECHANICS, not to the SCENE.
    if getattr(caller.db, "facility_room_desc_backup", None) is None:
        caller.db.facility_room_desc_backup = room.db.desc or ""
    room.db.desc = (
        "|wA long, bright room that smells of warm milk, animal, and machine oil.|n "
        "The walls are hung with coiled tubing and clean steel fixtures, the kind "
        "that hose down easy. Down the centre runs the line: a row of padded "
        "breeding stations, most of them empty, each fitted with restraints, a "
        "milking rig, and a swing-mounted intake arm. One station is occupied. "
        "Along one wall a kennel run of restless hounds; opposite, stalls and pens "
        "holding a bull, a boar, a stallion — stock, waiting their turn on a "
        "schedule that never seems to end. An attendant works the gauges; a handler "
        "works the animals. Nothing in here is in a hurry. The room is built for "
        "things that take exactly as long as they take."
    )

    # ── Establishing scene — vivid, legible, breeding-themed. ───────────
    room.msg_contents(
        f"\n|wThe door seals behind {n} with a sound like a file drawer closing.|n "
        "|xThe lights come up even and clinical; a timer starts somewhere and does "
        "not show its number.|n"
    )
    caller.msg(
        "\n|yThe restraints find you before you've agreed to anything — a padded "
        "cradle folding around you, hauling your chest up and out into the waiting "
        "cups, tipping your hips back and your knees apart until you're presented "
        "rather than seated.|n\n"
        "|cThe milking rig settles onto your tits and takes hold; the intake arm "
        "seats itself low and deep and stays there, and a slow, patient rhythm "
        "starts up that treats your whole body as one thing to be drained and bred "
        "and topped back up.|n\n"
        "|gDown the wall a kennel of hounds catches your scent and starts to whine. "
        "In the stalls a bull stamps, a boar grunts, a stallion screams once. The "
        "handler glances at the clock and says, to no one, \"Give her a bit. She'll "
        "loosen up.\"|n\n"
        "|RThe attendant doesn't look at your face. They check a gauge, thumb a dial, "
        "and write something down.|n\n"
        "|xThere is no panel and no clock you can read. You can still speak. You can "
        "still be spoken to. Reaching for the way out, you'll find, does nothing — "
        "and the longer you're in here, the less you'll remember why you'd want to.|n"
    )
    caller.msg(
        "\n|mThe attendant sets a thick contract in your eyeline and uncaps a pen.|n "
        "|y\"Standard intake. Sign it and the schedule eases off — rest, comforts, "
        "the works. Read what you're cleared to read; the rest isn't your business "
        "until it is.\"|n |xMost of the pages are turned face-down.|n\n"
        "|x(It's a contract named 'contract'. You can |w read contract |x to read the "
        "visible terms, or |w sign contract |x to sign. You will be shown everything — "
        "including the hidden clauses — the moment you sign. Signing is binding and "
        "enforced.)|n"
    )


# ── Reset (the OOC safeword) ───────────────────────────────────────────────

def run_facility_reset(caller, purge=False):
    caller.msg("|w── Facility reset ──|n")
    room = caller.location

    # Stop driver + cycle.
    if room:
        for s in list(room.scripts.all()):
            if s.key in ("facility",):
                try: s.stop()
                except Exception: pass
    try:
        from typeclasses.cycle_script import CycleScript
        CycleScript.stop_all(caller)
    except Exception:
        pass

    # Remove tracked items + NPCs.
    removed = 0
    for dbref in list(getattr(caller.db, "facility_items", None) or []):
        try:
            from evennia import search_object
            res = search_object(dbref, exact=True)
            if res:
                obj = res[0]
                for m in ("uninstall", "remove"):
                    if hasattr(obj, m):
                        try: getattr(obj, m)()
                        except Exception: pass
                obj.delete(); removed += 1
        except Exception:
            pass

    # Drain any inflation on every zone.
    try:
        from typeclasses.inflation_item import drain_inflation, get_inflation_data
        for zn in list((getattr(caller.db, "zones", None) or {}).keys()):
            if get_inflation_data(caller, zn):
                drain_inflation(caller, zn)
    except Exception:
        pass

    # Restore the room's real description.
    if room and getattr(caller.db, "facility_room_desc_backup", None) is not None:
        room.db.desc = caller.db.facility_room_desc_backup
        caller.db.facility_room_desc_backup = None

    # Clear the facility machine zone mechanics from the room.
    if room and getattr(caller.db, "facility_zone", None):
        try:
            rz = dict(getattr(room.db, "zones", None) or {})
            zn = caller.db.facility_zone
            if zn in rz:
                zd = dict(rz[zn]); zd["mechanics"] = {}
                rz[zn] = zd; room.db.zones = rz
        except Exception:
            pass

    # Always: give her name back, and clear the active machinery state.
    name_backup = getattr(caller.db, "facility_name_backup", None)
    if name_backup:
        caller.db.rp_name = name_backup
    caller.db.facility_name_backup = None

    caller.db.bred_by               = []
    caller.db.endcycle_blocked      = False
    caller.db.orgasm_denial         = False
    caller.db.orgasm_release_word   = ""
    caller.db.stim_per_tick         = 0.0
    caller.db.exhibition_active     = False
    caller.db.active_speech_filters = []
    caller.db.room_bound            = None
    caller.db.forced_posture        = None
    caller.db.body_language         = None
    caller.db.self_cmds_locked      = False
    caller.db.pet_trigger_sources   = []
    caller.db.arousal               = 0.0
    # Contract-enforced state.
    caller.db.navigation_locked         = False
    caller.db.anti_clothing_active      = False
    caller.db.required_honorific        = ""
    caller.db.sensation_broadcast_targets = []
    caller.db.aphrodisiac_expirations   = []
    caller.db.breeding_quota            = None
    caller.db.milk_quota                = None
    caller.db.cum_receptacle            = False
    caller.db.defiance                  = 0
    caller.db.compliance_threshold      = 0
    caller.db.compliance_streak         = 0
    caller.db.freedom_forfeited         = False
    caller.db.offspring_progress        = None
    caller.db.offspring_counts          = None

    # Stop perpetual heat and clear the flag.
    caller.db.perpetual_heat = False
    try:
        from typeclasses.heat_script import HeatScript
        for s in list(caller.scripts.all()):
            if isinstance(s, HeatScript) or getattr(s, "key", "") == "perpetual_heat":
                s.stop()
    except Exception:
        pass

    # Restore consent.
    backup = getattr(caller.db, "facility_consent_backup", None)
    if backup is not None:
        caller.db.consent_flags = dict(backup)
    caller.db.facility_consent_backup = None

    # Remove the fictional donors from the bank.
    try:
        from world.gang_breeding import clear_fictional_donors
        clear_fictional_donors()
    except Exception:
        pass

    if purge:
        # Scorched earth — nothing survives, including the marks.
        caller.db.installed_triggers     = []
        caller.db.conditioning           = 0.0
        caller.db.conditioning_applied   = []
        caller.db.conditioning_permanent = False
        caller.db.designation            = None
        caller.db.arousal_floor          = 0.0
        caller.db.pet_type               = None
        caller.db.aura_dimmed            = False
        caller.db.facility_brand         = None
        caller.db.facility_brands        = []
        tail = "Purged. Nothing kept — restored to true baseline."
    else:
        # Normal reset: she walks out, but she does not walk out clean.
        _apply_persistent_marks(caller)
        tail = ("Released. A few things stayed behind — they always do. "
                "Use facilityreset/purge to wipe even those.")

    caller.db.facility_active = False
    caller.db.facility_items  = []
    caller.db.facility_zone   = None
    caller.db.facility_reset_locked_until = None

    caller.msg(
        f"|g  ✓ {removed} facility objects removed. Machinery, effects and consent "
        f"restored.|n"
    )
    caller.msg(f"|w  {tail}|n")
    caller.msg("|w  Recommend @reload before another run.|n")


def _apply_persistent_marks(caller):
    """The lingering after a normal reset — cleared only by facilityreset/purge."""
    # 1. One conditioned response stays, made permanent: anyone can still use it.
    try:
        from world.binding_effects import install_trigger
        caller.db.installed_triggers = []   # strip the rest
        install_trigger(caller, "good girl", response="leak",
                        strength=3, permanent=True)
    except Exception:
        pass

    # 2. The body learned. It won't settle all the way back down again.
    caller.db.arousal_floor = max(8.0, float(getattr(caller.db, "arousal_floor", 0) or 0) * 0)

    # 3. The conditioning meter empties, but the fact of it doesn't.
    caller.db.conditioning           = 0.0
    caller.db.conditioning_applied   = []
    caller.db.conditioning_permanent = True

    # 4. The designation is still there, sitting just under the name.
    if not getattr(caller.db, "designation", None):
        caller.db.designation = "the breeding bitch"

    # 5. A mark that doesn't come off, and an aura that doesn't fully come back.
    caller.db.facility_brand = (
        "low on one hip, a small neat row of tally marks — the Process's count, "
        "healed but permanent, with room left to add more."
    )
    caller.db.aura_dimmed = True
