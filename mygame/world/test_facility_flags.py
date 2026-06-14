"""
world/test_facility_flags.py — standalone regression test for the recent build arc.

Runs WITHOUT Evennia: `python3 world/test_facility_flags.py` (or import and call run()).
Two jobs:

  1. §0 FLOOR GUARANTEE — assert every persistent db flag the new systems write is present in
     FACILITY_FLAGS, so escape/force_clear/facilityreset can never silently fail to clear one.
     This is the load-bearing safety check; if a future flag is added without registering it,
     this test fails loudly.
  2. PURE LOGIC — exercise the dependency-light cores (regression thresholds, star chart, quota
     normalizer, maze combination, sire temperaments, fellow progression, speech-filter order).

It deliberately covers only the pieces that load without the Evennia runtime; the live
integration paths stay in world/test_build.py / test_reset.py (run inside the game).
"""

import os
import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    """Load a module by file path in isolation (no package import side effects)."""
    path = os.path.join(_HERE, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Every persistent flag the recent systems write. Each MUST be in FACILITY_FLAGS so the OOC
# floor clears it. (Grouped by the system that introduced it.)
_NEW_FLAGS = [
    # regression
    "regression", "regression_applied", "regression_permanent", "headspace",
    # little box
    "in_box", "box_entered_at", "box_release_at", "box_lid_locked", "box_struggle",
    # little-clauses
    "teat_gagged", "teat_gag_until", "teat_gag_fluid",
    "nurse_first", "nursed_until", "nurse_first_fluid",
    "stuffed_mouth", "stuffed_fluid", "beg_small", "star_chart", "star_chart_on",
    "heat_tell", "honorifics_required", "honorific_miss_count", "honorific_miss_at",
    # neuter / sissify
    "neutered", "sissified",
    # studs / lineage / fellow
    "facility_studs", "facility_fellow", "facility_fellow_ref", "fellow_cross_sires",
    "offspring_by_sire", "offspring_by_sex", "offspring_max_gen",
    # dairy engorgement
    "milk_engorge_beats",
    # CYOA choices + scenes
    "pending_choice", "cycle_emphasis", "scene_flags",
    # spiral chair
    "in_hypno_chair", "chair_stage", "chair_beats", "chair_release_at", "chair_struggle",
    "chair_sessions",
]


def test_floor_flag_coverage():
    fs = _load("fac_state_test", "facility_state.py")
    flags = set(fs.FACILITY_FLAGS)
    missing = [k for k in _NEW_FLAGS if k not in flags]
    assert not missing, ("§0 FLOOR HOLE — these flags are written but NOT in FACILITY_FLAGS, "
                         "so the OOC floor won't clear them: " + ", ".join(missing))
    return f"floor covers all {len(_NEW_FLAGS)} new flags"


def test_regression_thresholds():
    # regression.regress only needs a stub for world.binding_effects.install_trigger.
    import sys, types
    be = types.ModuleType("world.binding_effects"); be.install_trigger = lambda *a, **k: None
    wpkg = types.ModuleType("world"); wpkg.__path__ = [_HERE]
    sys.modules.setdefault("world", wpkg); sys.modules["world.binding_effects"] = be
    rg = _load("world.regression", "regression.py")

    class D:  # minimal db
        pass

    class Ch:
        def __init__(self): self.db = D(); self.db.rp_name = "L"; self.key = "L"; self.msgs = []
        def msg(self, m): self.msgs.append(m)
    c = Ch()
    for amt in (16, 16, 22, 30, 30):
        rg.regress(c, amt, "test")
    applied = set(getattr(c.db, "regression_applied", []))
    assert {"soft", "vocabulary", "little", "namegone", "permanent"} <= applied, applied
    assert getattr(c.db, "regression_permanent", False) is True
    # name loss reused the facility backup slot (so the floor restores it)
    assert getattr(c.db, "facility_name_backup", None) == "L"
    return "regression walks soft->permanent; name backed to facility_name_backup"


def test_star_chart():
    sc = _load("star_chart_test", "star_chart.py")

    class D: pass
    class Ch:
        def __init__(self): self.db = D(); self.db.rp_name = "L"; self.name = "L"; self.msgs = []
        def msg(self, m): self.msgs.append(m)
    c = Ch()
    assert sc.award_star(c, "bred") == 0          # no-op while clause off
    c.db.star_chart_on = True
    sc.award_star(c, "allholes")                  # 3
    sc.award_star(c, "bred")                      # 1
    assert sc.stars_balance(c) == 4
    assert sc.spend_stars(c, sc.RELIEF_COST) and sc.stars_balance(c) == 0
    return "stars: off=no-op, earn 3+1, spend RELIEF_COST"


def test_quota_normalizer():
    import sys, types
    wpkg = types.ModuleType("world"); wpkg.__path__ = [_HERE]
    sys.modules.setdefault("world", wpkg)
    gb = _load("world.gang_breeding", "gang_breeding.py")
    assert gb.quota_pair(12) == (0, 12)
    assert gb.quota_pair({"current": 3, "required": 10}) == (3, 10)
    assert gb.ensure_quota_entry({"hound": 30}, "hound") == {"current": 0, "required": 30}
    return "quota_pair / ensure_quota_entry tolerate int + dict shapes"


def test_maze():
    mz = _load("maze_test", "maze.py")
    sols = {"out": ["north", "north", "east", "west"]}
    seq = []
    for d in ["north", "north", "east", "west"]:
        seq, hit = mz.evaluate_move(seq, d, sols, reset_on_wrong=True)
    assert hit == "out" and seq == []
    # a deviation resets (classic)
    seq, hit = mz.evaluate_move(["north", "north"], "west", sols, reset_on_wrong=True)
    assert hit is None
    return "maze classic combo solves; deviation resets"


def test_sire_temperaments():
    fa = _load("fac_animals_test", "facility_animals.py")

    class D: pass
    class Ch:
        def __init__(self): self.db = D()
    c = Ch(); fa.ensure_studs(c)
    assert fa.sire_beat(c, "Caesar", "L")            # veteran -> a line
    assert fa.sire_beat(c, "Bethany", "L") == ""     # Bethany skipped (own voice)
    assert fa.sire_beat(c, "Nobody", "L") == ""      # unknown skipped
    fa.add_stud(c, "Rex", "hound", "son grown to stud")
    assert any(s["name"] == "Rex" and s.get("temperament") for s in c.db.facility_studs)
    return "sire_beat by temperament; Bethany/unknown skip; get-studs get a temperament"


def test_fellow_progression():
    fa = _load("fac_fellow_test", "facility_fellow.py")

    class D: pass
    class Ch:
        def __init__(self): self.db = D(); self.db.rp_name = "L"; self.name = "L"
    c = Ch()
    churned = False
    for _ in range(50):
        ev, _f = fa.advance_fellow(c, chance=1.0)
        if ev == "churned":
            churned = True; break
    assert churned, "fellow should churn to a fresh intake at the end of the line"
    fa.mark_fellow_futa(c); assert fa.fellow_is_futa(c)
    return "fellow advances + churns; futa conversion persists"


def test_speech_filter_order():
    sf = _load("speech_test", "speech_filters.py")
    a = sf._ordered_filters(["sissy", "baby_talk", "single_word", "no_self_name"])
    b = sf._ordered_filters(["single_word", "no_self_name", "sissy", "baby_talk"])
    assert a == b, "canonical order must be add-order independent"
    assert sf._ordered_filters(["zonk", "baby_talk"]) == ["baby_talk", "zonk"]
    return "speech-filter order is add-order independent; unknowns last"


def test_heat_tell():
    """The Honest Body clause: the filter appends an arousal-tell graded off REAL arousal,
    never destroys the words, and at the edge is unmistakably more wrecked than when calm."""
    sf = _load("speech_test_ht", "speech_filters.py")

    class _Char:
        def __init__(self, arousal):
            self.db = type("_d", (), {})()
            self.db.arousal = arousal

    # heat_tell is in the canonical pipeline order (so it appends after other transforms).
    assert "heat_tell" in sf._FILTER_ORDER, "heat_tell must be registered in pipeline order"
    assert sf._ordered_filters(["heat_tell", "sissy"])[-1] == "heat_tell", \
        "heat_tell should sort to the end (it appends to whatever the pipeline produced)"

    # Original text is always preserved as a prefix (non-destructive).
    for arousal in (10.0, 45.0, 70.0, 95.0):
        out = sf._filter_heat_tell(_Char(arousal), "open the door")
        assert out.startswith("open the door"), f"heat_tell ate the words at {arousal}: {out!r}"

    # Edge tier (>=90) always tells (no silent pass) and is drawn from the edge pool.
    edge_outs = {sf._filter_heat_tell(_Char(96.0), "yes")[3:] for _ in range(40)}
    assert all(o for o in edge_outs), "edge arousal must always produce a tell"
    assert edge_outs <= set(_t for _t in sf._HEAT_TELL_EDGE), \
        "edge tells must come from the edge pool"

    # Low tier (<30) sometimes nearly hides it (returns bare text) — exercise both paths.
    low_outs = [sf._filter_heat_tell(_Char(5.0), "hello") for _ in range(80)]
    assert any(o == "hello" for o in low_outs), "low arousal should sometimes nearly hide it"
    assert any(o != "hello" for o in low_outs), "low arousal should usually still tell"
    return "heat_tell: graded by real arousal, non-destructive, edge always tells, low can hide"


def test_honorifics_address():
    """The honorifics clause: required_address returns the right token for the strongest-claim
    holder PRESENT, picks family role tokens, and requires nobody when the room is empty of
    superiors (you can't fail to honour someone who isn't here)."""
    rel = _load("rel_test", "relationships.py")

    class _DB:
        def __init__(self, **kw): self.__dict__.update(kw)
    class _Char:
        _n = 0
        def __init__(self, name, **dbkw):
            _Char._n += 1
            self.id = _Char._n
            self.key = name
            self.db = _DB(rp_name=name, **dbkw)

    honorifics = {"owner": "Owner", "lover": "love",
                  "family": {"mother": "Mommy", "*": "family"}, "faction": "ma'am"}

    target = _Char("Pet", relationships={})
    room = type("_R", (), {})()
    room.contents = [target]
    target.db.location = room
    # _Char has no .location attr; relationships reads getattr(target,'location'). Set it.
    target.location = room

    # No superiors present -> no requirement.
    assert rel.required_address(target, honorifics) is None, "empty room must not require address"

    # An explicit OWNER present -> must call them Owner.
    owner = _Char("Bethany", relationships={target.id: {"owner": True}})
    owner.location = room
    room.contents = [target, owner]
    req = rel.required_address(target, honorifics)
    assert req and req[0] == "Owner" and req[1] == "Bethany", f"owner address wrong: {req}"

    # Add a LOVER too — owner still wins (stronger claim).
    lover = _Char("Vee", relationships={target.id: {"lover": True}})
    lover.location = room
    room.contents = [target, lover, owner]
    assert rel.required_address(target, honorifics)[0] == "Owner", "owner must outrank lover"

    # Owner leaves; lover remains -> 'love'.
    room.contents = [target, lover]
    assert rel.required_address(target, honorifics)[0] == "love", "lover address wrong"

    # Family role token (a 'mother' present) -> 'Mommy'.
    mom = _Char("Dam", relationships={target.id: {"family": "mother"}})
    mom.location = room
    room.contents = [target, mom]
    assert rel.required_address(target, honorifics)[0] == "Mommy", "family role token wrong"
    return "honorifics: strongest-claim present holder picks the token; empty room requires none"


def test_honorific_escalation():
    """Missed-address ladder: 1st fumble forgiven, 2nd logs defiance (register_defiance),
    3rd is the public lesson (make_example) and resets the ladder; a stale tally resets."""
    import sys, types, time
    # Stub world.compliance so the escalation primitives are observable without Evennia.
    defiance, examples = [], []
    fake_pkg = types.ModuleType("world")
    fake_comp = types.ModuleType("world.compliance")
    fake_comp.register_defiance = lambda c, amount=1, reason="": defiance.append((amount, reason))
    fake_comp.make_example = lambda c, severity=2, reason="", broadcast=True: \
        examples.append((severity, reason, broadcast))
    sys.modules.setdefault("world", fake_pkg)
    sys.modules["world.compliance"] = fake_comp

    sf = _load("speech_test_esc", "speech_filters.py")

    class _DB:
        def __init__(self, **kw): self.__dict__.update(kw)
    class _Char:
        def __init__(self): self.db = _DB(honorific_miss_count=0, honorific_miss_at=0)

    c = _Char()
    # 1st miss: forgiven — nothing logged, tally now 1.
    assert sf._honorific_escalate(c, "Bethany") == "" and not defiance and not examples
    assert c.db.honorific_miss_count == 1, "first miss should leave tally at 1"
    # 2nd miss in-window: defiance logged, tally stays at 2 (does NOT reset — the ladder climbs).
    note2 = sf._honorific_escalate(c, "Bethany")
    assert note2 and len(defiance) == 1 and not examples, "second miss should log defiance only"
    assert "Bethany" in defiance[0][1] and c.db.honorific_miss_count == 2
    # 3rd miss in-window: the public example (severity 2, broadcast), and the ladder resets.
    note3 = sf._honorific_escalate(c, "Bethany")
    assert note3 and len(examples) == 1, "third miss should make an example"
    assert examples[0][0] == 2 and examples[0][2] is True and "Bethany" in examples[0][1]
    assert c.db.honorific_miss_count == 0, "ladder should reset after the public example"
    # A stale miss (outside the window) resets to a fresh first miss rather than escalating.
    sf._honorific_escalate(c, "Bethany")                 # tally -> 1
    c.db.honorific_miss_at = time.time() - (sf._HONORIFIC_WINDOW_S + 10)
    note4 = sf._honorific_escalate(c, "Bethany")         # stale -> fresh first miss
    assert note4 == "" and len(defiance) == 1 and len(examples) == 1, "stale tally must reset"
    return "honorific ladder: 1st forgiven, 2nd defiance, 3rd public example, stale resets"


def test_poste_ripen():
    """poste-restante ripening: age-gated (nothing fresh ripens), pops the OLDEST ripe letter,
    and the broadcast line never leaks any letter's content (the office never reads them)."""
    import sys, types, time
    ev = types.ModuleType("evennia"); ev.search_object = lambda *a, **k: []
    uu = types.ModuleType("evennia.utils")
    uu.create = types.SimpleNamespace(create_object=lambda *a, **k: None)
    ev.utils = uu
    sys.modules.setdefault("evennia", ev)
    sys.modules.setdefault("evennia.utils", uu)
    pob = _load("pob_ripen", "post_office_build.py")

    class _DB:
        def __init__(self): self.poste_letters = None
    class _Office:
        def __init__(self): self.db = _DB()

    o = _Office()
    now = time.time()
    pob.leave_poste(o, "fresh marigoldletter", author_id=1)
    o.db.poste_letters[-1]["at"] = now - 100
    assert pob.ripen_poste(o, now=now) is None and pob.poste_count(o) == 1, "fresh must not ripen"
    pob.leave_poste(o, "old marigoldletter", author_id=2);    o.db.poste_letters[-1]["at"] = now - 4 * 86400
    pob.leave_poste(o, "ancient marigoldletter", author_id=3); o.db.poste_letters[-1]["at"] = now - 9 * 86400
    line = pob.ripen_poste(o, now=now)
    assert line, "an over-age letter should ripen"
    assert pob.poste_count(o) == 2, "exactly one should have ripened out"
    texts = [e["text"] for e in o.db.poste_letters]
    assert "ancient marigoldletter" not in texts, "the OLDEST ripe letter should be the one delivered"
    assert "marigoldletter" not in line.lower(), "ripening must never leak letter content"
    return "poste ripen: age-gated, oldest-first, content never leaked"


def test_bethany_scene():
    """The choice-driven scene engine: Bethany's Intake chains through all six beats on the
    player's choices, remembers earlier choices (scene memory), references them in later beats,
    and ends clean (clears the pending choice + scene memory)."""
    import sys, types
    ev = types.ModuleType("evennia"); ev.search_object = lambda *a, **k: []
    uu = types.ModuleType("evennia.utils")
    uu.create = types.SimpleNamespace(create_object=lambda *a, **k: None)
    ev.utils = uu
    sys.modules.setdefault("evennia", ev)
    sys.modules.setdefault("evennia.utils", uu)
    cyoa = _load("cyoa_scene", "cyoa.py")

    class _DB:
        def __init__(self): self._d = {}
        def __getattr__(self, k):
            if k == "_d": raise AttributeError
            return self._d.get(k)
        def __setattr__(self, k, v):
            if k == "_d": object.__setattr__(self, k, v)
            else: self._d[k] = v
    class _Char:
        def __init__(self): self.db = _DB(); self.name = "Laynie"; self.location = None
        def msg(self, m): pass

    c = _Char()
    assert cyoa.start_scene(c, "bx_arrival"), "scene failed to start"
    beats = []
    for choice in ("bold", "honest", "present", "sign", "kneel", "take",
                   "ridden", "beg_knot", "beg_come", "thank"):
        pend = c.db.pending_choice
        assert pend, f"no pending choice before '{choice}'"
        beats.append(pend["key"])
        opt, _ = cyoa.resolve_choice(c, choice)
        assert opt is not None, f"'{choice}' did not resolve"
    assert beats == ["bx_arrival", "bx_file", "bx_strip", "bx_contract", "bx_unveil",
                     "bx_first", "bx_seat", "bx_ride", "bx_knot", "bx_close"], beats
    assert c.db.pending_choice is None, "scene should be over"
    assert c.db.scene_flags is None, "end should clear scene memory"

    # The Breeding Pens scene chains end-to-end too (pack branch, real-breed beat).
    c3 = _Char(); cyoa.start_scene(c3, "bp_arrival")
    pbeats = []
    for ch in ("present", "pack", "still", "take", "under", "beg_seed", "take_seed", "thank"):
        p = c3.db.pending_choice
        assert p, f"pens: no pending before '{ch}'"
        pbeats.append(p["key"])
        assert cyoa.resolve_choice(c3, ch)[0] is not None, f"pens '{ch}' did not resolve"
    assert pbeats == ["bp_arrival", "bp_pick", "bp_scent", "bp_mount", "bp_ride",
                      "bp_knot", "bp_breed", "bp_after"], pbeats
    assert c3.db.pending_choice is None and c3.db.scene_flags is None, "pens should end clean"

    # The Conditioning Cell scene chains end-to-end (the descent branch).
    c4 = _Char(); cyoa.start_scene(c4, "cc_arrival")
    kbeats = []
    for ch in ("sink", "breathe", "open", "say", "down", "let", "grateful"):
        p = c4.db.pending_choice
        assert p, f"cell: no pending before '{ch}'"
        kbeats.append(p["key"])
        assert cyoa.resolve_choice(c4, ch)[0] is not None, f"cell '{ch}' did not resolve"
    assert kbeats == ["cc_arrival", "cc_settle", "cc_spiral", "cc_mantra", "cc_deep",
                      "cc_descent", "cc_set"], kbeats
    assert c4.db.pending_choice is None and c4.db.scene_flags is None, "cell should end clean"

    # The Dairy scene chains end-to-end and hands off (ends) at the cycle seam.
    c5 = _Char(); cyoa.start_scene(c5, "dy_arrival")
    dbeats = []
    for ch in ("present", "hold", "letdown", "make", "thank"):
        p = c5.db.pending_choice
        assert p, f"dairy: no pending before '{ch}'"
        dbeats.append(p["key"])
        assert cyoa.resolve_choice(c5, ch)[0] is not None, f"dairy '{ch}' did not resolve"
    assert dbeats == ["dy_arrival", "dy_hook", "dy_pull", "dy_quota", "dy_handoff"], dbeats
    assert c5.db.pending_choice is None and c5.db.scene_flags is None, "dairy should end clean"

    # The Marking Parlour scene chains end-to-end (the rings/cowset branch).
    c6 = _Char(); cyoa.start_scene(c6, "mp_arrival")
    mbeats = []
    for ch in ("still", "rings", "take_it", "thank"):
        p = c6.db.pending_choice
        assert p, f"parlour: no pending before '{ch}'"
        mbeats.append(p["key"])
        assert cyoa.resolve_choice(c6, ch)[0] is not None, f"parlour '{ch}' did not resolve"
    assert mbeats == ["mp_arrival", "mp_order", "mp_work", "mp_set"], mbeats
    assert c6.db.pending_choice is None and c6.db.scene_flags is None, "parlour should end clean"

    # The Pigsty scene chains end-to-end; state hooks fire (test as a nugget).
    c7 = _Char(); c7.db.nugget = True
    cyoa.start_scene(c7, "ps_arrival")
    assert "limbless" in c7.db.pending_choice["prompt"].lower() or \
           "no arms" in c7.db.pending_choice["prompt"].lower(), "pigsty nugget hook didn't fire"
    sbeats = []
    for ch in ("walk", "sink", "still", "take", "gone", "thank"):
        p = c7.db.pending_choice
        assert p, f"pigsty: no pending before '{ch}'"
        sbeats.append(p["key"])
        assert cyoa.resolve_choice(c7, ch)[0] is not None, f"pigsty '{ch}' did not resolve"
    assert sbeats == ["ps_arrival", "ps_down", "ps_root", "ps_mount", "ps_wallow", "ps_after"], sbeats
    assert c7.db.pending_choice is None and c7.db.scene_flags is None, "pigsty should end clean"

    # The Sanitation Block scene chains end-to-end (the frame branch).
    c8 = _Char(); cyoa.start_scene(c8, "sb_arrival")
    qbeats = []
    for ch in ("frame", "serve", "thank"):
        p = c8.db.pending_choice
        assert p, f"sanitation: no pending before '{ch}'"
        qbeats.append(p["key"])
        assert cyoa.resolve_choice(c8, ch)[0] is not None, f"sanitation '{ch}' did not resolve"
    assert qbeats == ["sb_arrival", "sb_use", "sb_after"], qbeats
    assert c8.db.pending_choice is None and c8.db.scene_flags is None, "sanitation should end clean"

    # The Showroom scene chains end-to-end on both gavel outcomes.
    c9 = _Char(); cyoa.start_scene(c9, "sw_arrival")
    wbeats = []
    for ch in ("perform", "show", "drive", "her", "hers"):
        p = c9.db.pending_choice
        assert p, f"showroom: no pending before '{ch}'"
        wbeats.append(p["key"])
        assert cyoa.resolve_choice(c9, ch)[0] is not None, f"showroom '{ch}' did not resolve"
    assert wbeats == ["sw_arrival", "sw_display", "sw_bidding", "sw_gavel", "sw_bought"], wbeats
    assert c9.db.pending_choice is None and c9.db.scene_flags is None, "showroom should end clean"
    # The "look away" gavel branch (unsold/do-over) also ends clean.
    c10 = _Char(); cyoa.start_scene(c10, "sw_arrival")
    for ch in ("freeze", "endure_show", "still_bid", "dark", "ache"):
        assert c10.db.pending_choice, f"showroom-dark: stall before '{ch}'"
        assert cyoa.resolve_choice(c10, ch)[0] is not None, f"showroom-dark '{ch}' failed"
    assert c10.db.pending_choice is None and c10.db.scene_flags is None, "showroom-dark should end clean"

    # The Office/Kept scene chains end-to-end (real bethany_breeds + file_read beats).
    c11 = _Char(); cyoa.start_scene(c11, "ko_arrival")
    obeats = []
    for ch in ("lap", "melt", "open", "listen", "thank"):
        p = c11.db.pending_choice
        assert p, f"office: no pending before '{ch}'"
        obeats.append(p["key"])
        assert cyoa.resolve_choice(c11, ch)[0] is not None, f"office '{ch}' did not resolve"
    assert obeats == ["ko_arrival", "ko_evening", "ko_breed", "ko_file", "ko_close"], obeats
    assert c11.db.pending_choice is None and c11.db.scene_flags is None, "office should end clean"

    # The Nursery scene chains end-to-end (regression + lineage + Little Box).
    c12 = _Char(); cyoa.start_scene(c12, "nu_arrival")
    nbeats = []
    for ch in ("soft", "sink_little", "nurse_deep", "hold", "settle"):
        p = c12.db.pending_choice
        assert p, f"nursery: no pending before '{ch}'"
        nbeats.append(p["key"])
        assert cyoa.resolve_choice(c12, ch)[0] is not None, f"nursery '{ch}' did not resolve"
    assert nbeats == ["nu_arrival", "nu_regress", "nu_nurse", "nu_lineage", "nu_box"], nbeats
    assert c12.db.pending_choice is None and c12.db.scene_flags is None, "nursery should end clean"

    # Deep Stock: the approach branch reaches the threshold; the decline branch goes to close.
    c13 = _Char(); cyoa.start_scene(c13, "ds_arrival")
    dsbeats = []
    for ch in ("look", "touch", "approach", "linger"):
        p = c13.db.pending_choice
        assert p, f"deepstock: no pending before '{ch}'"
        dsbeats.append(p["key"])
        assert cyoa.resolve_choice(c13, ch)[0] is not None, f"deepstock '{ch}' did not resolve"
    assert dsbeats == ["ds_arrival", "ds_pod", "ds_offer", "ds_threshold"], dsbeats
    assert c13.db.pending_choice is None and c13.db.scene_flags is None, "deepstock should end clean"
    c14 = _Char(); cyoa.start_scene(c14, "ds_arrival")
    for ch in ("recoil", "pull_hand", "decline", "hold_floor"):
        assert c14.db.pending_choice, f"deepstock-decline: stall before '{ch}'"
        assert cyoa.resolve_choice(c14, ch)[0] is not None, f"deepstock-decline '{ch}' failed"
    assert c14.db.pending_choice is None and c14.db.scene_flags is None, "deepstock-decline should end clean"

    # Memory: a different path is retained and referenced by a later beat.
    c2 = _Char(); cyoa.start_scene(c2, "bx_arrival")
    cyoa.resolve_choice(c2, "meek")
    cyoa.resolve_choice(c2, "silent")
    sf = c2.db.scene_flags or {}
    assert sf.get("posture") == "meek" and sf.get("candor") == "silent", sf
    assert "nothing" in cyoa._BUILDERS["bx_strip"](c2)["prompt"].lower(), \
        "later beat did not reference the earlier silent choice"
    return "Bethany scene: 6 beats chain on choices, memory retained + referenced, ends clean"


_TESTS = [
    test_floor_flag_coverage, test_regression_thresholds, test_star_chart,
    test_quota_normalizer, test_maze, test_sire_temperaments, test_fellow_progression,
    test_speech_filter_order, test_heat_tell, test_honorifics_address,
    test_honorific_escalation, test_poste_ripen, test_bethany_scene,
]


def run():
    ok = 0
    for t in _TESTS:
        try:
            note = t()
            print(f"  ✓ {t.__name__}: {note}")
            ok += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
    print(f"\n{ok}/{len(_TESTS)} passed")
    return ok == len(_TESTS)


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
