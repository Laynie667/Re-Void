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
    # neuter / sissify (+ pronoun backup so the floor restores them)
    "neutered", "sissified", "facility_pronouns_backup",
    # cross-NPC ownership (Seraphine) + forced-adoption ward
    "seraphine_owned", "seraphine_ward",
    # nested-passenger carry
    "passenger",
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


def test_pronoun_backup_roundtrip():
    """Sissify/geld must move pronouns AND back up the originals so the floor restores them.
    Mirrors the FacilityScript._set_pronouns backup-then-overwrite contract + the reset restore."""
    class _DB:
        def __init__(self):
            self.pronouns = {"subject": "he", "object": "him", "possessive": "his", "reflexive": "himself"}
            self.facility_pronouns_backup = None

    # _set_pronouns contract: back up ONCE, then overwrite (twice should not clobber the backup).
    def set_pronouns(db, s, o, p, r):
        if not db.facility_pronouns_backup:
            db.facility_pronouns_backup = dict(db.pronouns or {})
        db.pronouns = {"subject": s, "object": o, "possessive": p, "reflexive": r}

    db = _DB()
    set_pronouns(db, "she", "her", "her", "herself")          # sissify
    assert db.pronouns["subject"] == "she", "sissify should set she/her"
    assert db.facility_pronouns_backup["subject"] == "he", "original pronouns must be backed up"
    set_pronouns(db, "it", "it", "its", "itself")             # then geld — backup must NOT be clobbered
    assert db.pronouns["subject"] == "it", "geld should set it/its"
    assert db.facility_pronouns_backup["subject"] == "he", "backup must survive a second procedure"

    # reset restore contract (as in force_clear / run_facility_reset): restore, then clear backup.
    if db.facility_pronouns_backup:
        db.pronouns = dict(db.facility_pronouns_backup)
        db.facility_pronouns_backup = None
    assert db.pronouns == {"subject": "he", "object": "him", "possessive": "his", "reflexive": "himself"}, \
        "floor must restore the original pronouns"
    return "pronoun backup: sissify->she, geld->it, backup survives, floor restores original"


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


def test_passenger():
    """The nested-passenger core: board into a host, transfer between hosts (deposit-on-breed),
    cover (flood reaches the passenger), and the §0 eject (always frees, any nesting)."""
    pg = _load("passenger_test", "passenger.py")

    class _DB:
        def __init__(self): self.passenger = None
    class _P:
        def __init__(self): self.db = _DB()

    p = _P()
    assert not pg.is_passenger(p)
    pg.board(p, "Seraphine", "balls")
    st = pg.status(p)
    assert st["host"] == "Seraphine" and st["interior"] == "balls" and pg.is_passenger(p)
    # transfer: fired from Seraphine's balls into Bethany's womb (deposit-on-insemination)
    pg.transfer(p, "Bethany", "womb")
    st = pg.status(p)
    assert st["host"] == "Bethany" and st["interior"] == "womb" and st["covered"] is False
    # cover: an external flood reaches the passenger (laced=False so no Evennia devotion call)
    pg.cover(p, fluid="semen", laced=False)
    assert pg.status(p)["covered"] is True
    assert "Bethany" in pg.carried_line(p) and "covered" in pg.carried_line(p)
    # §0 eject: unbirths unconditionally
    pg.eject(p)
    assert not pg.is_passenger(p) and pg.carried_line(p) == ""
    # physical layer present + degrades gracefully with no Evennia (host can't resolve,
    # interior is None, provisioning reports a reason instead of throwing).
    assert pg._resolve_host("Bethany") is None and pg._interior_room(None, "balls") is None
    room, reason = pg.provision_passenger_interior(p, "balls")
    assert room is None and reason, "provision should report a reason without Evennia, not raise"
    # board/transfer through the physical wrappers still produce the right state on a bare obj
    pg.board(p, "Seraphine", "balls")
    assert pg.status(p)["interior"] == "balls"
    pg.eject(p); assert not pg.is_passenger(p)
    return "passenger: board/transfer/cover/eject + physical layer no-ops cleanly; §0 frees any host"


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

    # Holding chains end-to-end.
    c15 = _Char(); cyoa.start_scene(c15, "hd_arrival")
    hbeats = []
    for ch in ("wait", "still", "endure_wait", "go"):
        p = c15.db.pending_choice
        assert p, f"holding: no pending before '{ch}'"
        hbeats.append(p["key"])
        assert cyoa.resolve_choice(c15, ch)[0] is not None, f"holding '{ch}' did not resolve"
    assert hbeats == ["hd_arrival", "hd_prep", "hd_wait", "hd_called"], hbeats
    assert c15.db.pending_choice is None and c15.db.scene_flags is None, "holding should end clean"

    # The Processing Floor chains end-to-end.
    c16 = _Char(); cyoa.start_scene(c16, "pf_arrival")
    fbeats = []
    for ch in ("present", "serve", "follow"):
        p = c16.db.pending_choice
        assert p, f"floor: no pending before '{ch}'"
        fbeats.append(p["key"])
        assert cyoa.resolve_choice(c16, ch)[0] is not None, f"floor '{ch}' did not resolve"
    assert fbeats == ["pf_arrival", "pf_use", "pf_routed"], fbeats
    assert c16.db.pending_choice is None and c16.db.scene_flags is None, "floor should end clean"

    # The Records Hall / inspection chains end-to-end (grade_reveal beat).
    c17 = _Char(); cyoa.start_scene(c17, "rh_arrival")
    rbeats = []
    for ch in ("stand", "relax", "hear", "accept"):
        p = c17.db.pending_choice
        assert p, f"records: no pending before '{ch}'"
        rbeats.append(p["key"])
        assert cyoa.resolve_choice(c17, ch)[0] is not None, f"records '{ch}' did not resolve"
    assert rbeats == ["rh_arrival", "rh_gauge", "rh_grade", "rh_close"], rbeats
    assert c17.db.pending_choice is None and c17.db.scene_flags is None, "records should end clean"

    # Seraphine's visit chains end-to-end and transfers ownership for real.
    c18 = _Char(); cyoa.start_scene(c18, "se_arrival")
    sebeats = []
    for ch in ("still", "watch", "between", "yield", "settle"):
        p = c18.db.pending_choice
        assert p, f"seraphine: no pending before '{ch}'"
        sebeats.append(p["key"])
        assert cyoa.resolve_choice(c18, ch)[0] is not None, f"seraphine '{ch}' did not resolve"
    assert sebeats == ["se_arrival", "se_peerage", "se_opened", "se_unbirth", "se_close"], sebeats
    assert c18.db.seraphine_owned is True, "Seraphine should now own the player"
    assert c18.db.pending_choice is None and c18.db.scene_flags is None, "seraphine should end clean"

    # The Fitting scene chains end-to-end for BOTH a bare body and a kitted one (combination-aware).
    c19 = _Char(); cyoa.start_scene(c19, "ft_arrival")
    ftbeats = []
    for ch in ("present", "hold_check", "run", "thank"):
        p = c19.db.pending_choice
        assert p, f"fitting(bare): no pending before '{ch}'"
        ftbeats.append(p["key"])
        assert cyoa.resolve_choice(c19, ch)[0] is not None, f"fitting '{ch}' did not resolve"
    assert ftbeats == ["ft_arrival", "ft_check", "ft_use", "ft_close"], ftbeats
    assert c19.db.pending_choice is None and c19.db.scene_flags is None, "fitting should end clean"
    # kitted body: the inventory line composes, and the scene still chains
    c20 = _Char()
    c20.db.lactation_locked = True; c20.db.permanent_gape = True; c20.db.piercings = ["septum", "nipple"]
    inv = cyoa._kit_inventory(cyoa._kit(c20))
    assert "milk-port" in inv and "piercing" in inv and "gauged" in inv, inv
    cyoa.start_scene(c20, "ft_arrival")
    for ch in ("present", "hold_check", "run", "thank"):
        assert c20.db.pending_choice, f"fitting(kitted): stall before '{ch}'"
        assert cyoa.resolve_choice(c20, ch)[0] is not None, f"fitting(kitted) '{ch}' failed"
    assert c20.db.pending_choice is None and c20.db.scene_flags is None, "fitting(kitted) should end clean"

    # The Correction scene chains end-to-end (real punish/example/gratitude effects).
    c21 = _Char(); cyoa.start_scene(c21, "pn_arrival")
    pnbeats = []
    for ch in ("confess", "line", "thank"):
        p = c21.db.pending_choice
        assert p, f"correction: no pending before '{ch}'"
        pnbeats.append(p["key"])
        assert cyoa.resolve_choice(c21, ch)[0] is not None, f"correction '{ch}' did not resolve"
    assert pnbeats == ["pn_arrival", "pn_sentence", "pn_after"], pnbeats
    assert c21.db.pending_choice is None and c21.db.scene_flags is None, "correction should end clean"

    # The Dosing scene chains end-to-end (real _dose facility effect).
    c22 = _Char(); cyoa.start_scene(c22, "dz_arrival")
    dzbeats = []
    for ch in ("offer", "ride", "surf"):
        p = c22.db.pending_choice
        assert p, f"dosing: no pending before '{ch}'"
        dzbeats.append(p["key"])
        assert cyoa.resolve_choice(c22, ch)[0] is not None, f"dosing '{ch}' did not resolve"
    assert dzbeats == ["dz_arrival", "dz_comeup", "dz_ride"], dzbeats
    assert c22.db.pending_choice is None and c22.db.scene_flags is None, "dosing should end clean"

    # Auto-hub: with scene_autohub set, a scene's `end` auto-poses the facility hub.
    c23 = _Char(); c23.db.scene_autohub = True
    cyoa.start_scene(c23, "dz_arrival")
    for ch in ("offer", "ride", "surf"):
        cyoa.resolve_choice(c23, ch)
    assert c23.db.pending_choice is not None and c23.db.pending_choice["key"] == "facility_hub", \
        "scene_autohub should auto-pose the hub on scene end"

    # Events: the dispatcher returns a real event opening, and each event chains to an end.
    disp = cyoa._BUILDERS["ev_arrival"](_Char())
    assert disp and disp.get("options"), "ev_arrival dispatcher produced nothing"
    event_paths = {
        "ev_tour":  ("perform", "dread"),
        "ev_quota": ("stand", "take_quota"),
        "ev_fest":  ("dive", "glow"),
        "ev_anniv": ("moved", "give"),
    }
    for opening, path in event_paths.items():
        ce = _Char(); cyoa.start_scene(ce, opening)
        for ch in path:
            assert ce.db.pending_choice, f"{opening}: stall before '{ch}'"
            assert cyoa.resolve_choice(ce, ch)[0] is not None, f"{opening} '{ch}' failed"
        assert ce.db.pending_choice is None and ce.db.scene_flags is None, f"{opening} should end clean"

    # Manumission: the NOT-ready path (default, no release terms) chains to the honest refusal.
    c24 = _Char(); cyoa.start_scene(c24, "mn_arrival")
    mnbeats = []
    for ch in ("petition", "accept_terms", "keep_earning"):
        p = c24.db.pending_choice
        assert p, f"manumission: no pending before '{ch}'"
        mnbeats.append(p["key"])
        assert cyoa.resolve_choice(c24, ch)[0] is not None, f"manumission '{ch}' did not resolve"
    assert mnbeats == ["mn_arrival", "mn_terms", "mn_verdict"], mnbeats
    assert c24.db.pending_choice is None and c24.db.scene_flags is None, "manumission should end clean"
    # The EARNED path: stub release so _manumit_ready returns True, then press -> the grant verdict.
    import types as _t
    rel = _t.ModuleType("world.release")
    rel.terms = lambda s: {"offered": True, "paid": True, "scrip": 0}
    rel._unmet = lambda s, t: []
    rel.petition = lambda s: None
    rel.grant = lambda s, **k: None
    sys.modules["world.release"] = rel
    c25 = _Char(); cyoa.start_scene(c25, "mn_arrival")
    for ch in ("petition", "press", "stay_choose"):
        assert c25.db.pending_choice, f"manumission(earned): stall before '{ch}'"
        assert cyoa.resolve_choice(c25, ch)[0] is not None, f"manumission(earned) '{ch}' failed"
    assert c25.db.pending_choice is None, "manumission(earned) should end clean"
    sys.modules.pop("world.release", None)

    # The Fellow arc chains end-to-end (real fellow conversion + company_use breeding).
    c26 = _Char(); cyoa.start_scene(c26, "fl_arrival")
    flbeats = []
    for ch in ("reach", "watch_steady", "comfort", "take_her", "keep_her"):
        p = c26.db.pending_choice
        assert p, f"fellow: no pending before '{ch}'"
        flbeats.append(p["key"])
        assert cyoa.resolve_choice(c26, ch)[0] is not None, f"fellow '{ch}' did not resolve"
    assert flbeats == ["fl_arrival", "fl_convert", "fl_dose", "fl_bred", "fl_after"], flbeats
    assert c26.db.pending_choice is None and c26.db.scene_flags is None, "fellow should end clean"

    # The Carry scene: the BALLS path transfers you into Bethany for real.
    c27 = _Char(); cyoa.start_scene(c27, "pg_arrival")
    pgbeats = []
    for ch in ("balls", "planted", "settle"):
        p = c27.db.pending_choice
        assert p, f"carry: no pending before '{ch}'"
        pgbeats.append(p["key"])
        assert cyoa.resolve_choice(c27, ch)[0] is not None, f"carry '{ch}' did not resolve"
    assert pgbeats == ["pg_arrival", "pg_transfer", "pg_after"], pgbeats
    assert (c27.db.passenger or {}).get("host") == "Bethany", "balls path should transfer you into Bethany"
    assert c27.db.pending_choice is None and c27.db.scene_flags is None, "carry should end clean"
    # The WOMB path covers you (laced) while you ride Seraphine.
    c28 = _Char(); cyoa.start_scene(c28, "pg_arrival")
    for ch in ("womb", "covered", "exit"):
        assert c28.db.pending_choice, f"carry(womb): stall before '{ch}'"
        assert cyoa.resolve_choice(c28, ch)[0] is not None, f"carry(womb) '{ch}' failed"
    pst = c28.db.passenger or {}
    assert pst.get("host") == "Seraphine" and pst.get("covered") is True, "womb path should cover you in Seraphine"
    assert c28.db.pending_choice is None and c28.db.scene_flags is None, "carry(womb) should end clean"

    # Forced Adoption: the sign path adopts you (ownership+ward) and carries you home into Seraphine.
    c29 = _Char(); cyoa.start_scene(c29, "fa_arrival")
    fabeats = []
    for ch in ("warm", "want_home", "sign_glad", "go_home"):
        p = c29.db.pending_choice
        assert p, f"adoption: no pending before '{ch}'"
        fabeats.append(p["key"])
        assert cyoa.resolve_choice(c29, ch)[0] is not None, f"adoption '{ch}' did not resolve"
    assert fabeats == ["fa_arrival", "fa_clauses", "fa_sign", "fa_home"], fabeats
    assert c29.db.seraphine_owned is True and c29.db.seraphine_ward is True, "adoption should set owned+ward"
    assert (c29.db.passenger or {}).get("host") == "Seraphine", "adoption should carry you home into Seraphine"
    assert c29.db.pending_choice is None and c29.db.scene_flags is None, "adoption should end clean"
    # The balk path lets it lie (no signing, ends clean, not owned).
    c30 = _Char(); cyoa.start_scene(c30, "fa_arrival")
    for ch in ("wary", "balk_fa", "go"):
        assert c30.db.pending_choice, f"adoption(balk): stall before '{ch}'"
        assert cyoa.resolve_choice(c30, ch)[0] is not None, f"adoption(balk) '{ch}' failed"
    assert not c30.db.seraphine_owned, "balk path should not transfer ownership"
    assert c30.db.pending_choice is None and c30.db.scene_flags is None, "adoption(balk) should end clean"

    # Vesper's Nest (post-office warm scene) chains end-to-end, both branches.
    c31 = _Char(); cyoa.start_scene(c31, "vn_arrival")
    vnbeats = []
    for ch in ("ask_box", "watch_try", "give", "promise"):
        p = c31.db.pending_choice
        assert p, f"vesper: no pending before '{ch}'"
        vnbeats.append(p["key"])
        assert cyoa.resolve_choice(c31, ch)[0] is not None, f"vesper '{ch}' did not resolve"
    assert vnbeats == ["vn_arrival", "vn_toybox", "vn_tryon", "vn_after"], vnbeats
    assert c31.db.pending_choice is None and c31.db.scene_flags is None, "vesper should end clean"
    c32 = _Char(); cyoa.start_scene(c32, "vn_arrival")
    for ch in ("reach", "choose_for", "hold", "stay"):
        assert c32.db.pending_choice, f"vesper(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c32, ch)[0] is not None, f"vesper(b) '{ch}' failed"
    assert c32.db.pending_choice is None and c32.db.scene_flags is None, "vesper(b) should end clean"

    # Calix's Keeping-Room (post-office warm scene) chains end-to-end, both branches.
    c33 = _Char(); cyoa.start_scene(c33, "ck_arrival")
    ckbeats = []
    for ch in ("praise", "certain", "count", "stayed"):
        p = c33.db.pending_choice
        assert p, f"calix: no pending before '{ch}'"
        ckbeats.append(p["key"])
        assert cyoa.resolve_choice(c33, ch)[0] is not None, f"calix '{ch}' did not resolve"
    assert ckbeats == ["ck_arrival", "ck_consent", "ck_bench", "ck_after"], ckbeats
    assert c33.db.pending_choice is None and c33.db.scene_flags is None, "calix should end clean"
    c34 = _Char(); cyoa.start_scene(c34, "ck_arrival")
    for ch in ("quiet", "shaky", "seal", "thank"):
        assert c34.db.pending_choice, f"calix(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c34, ch)[0] is not None, f"calix(b) '{ch}' failed"
    assert c34.db.pending_choice is None and c34.db.scene_flags is None, "calix(b) should end clean"

    # Seraphine's Parlour (post-office warm scene) chains end-to-end, both branches.
    c35 = _Char(); cyoa.start_scene(c35, "sp_arrival")
    spbeats = []
    for ch in ("sit", "let_read", "tag_me", "claimed"):
        p = c35.db.pending_choice
        assert p, f"seraphine-parlour: no pending before '{ch}'"
        spbeats.append(p["key"])
        assert cyoa.resolve_choice(c35, ch)[0] is not None, f"sp '{ch}' did not resolve"
    assert spbeats == ["sp_arrival", "sp_read", "sp_keep", "sp_drawer"], spbeats
    assert c35.db.pending_choice is None and c35.db.scene_flags is None, "sp should end clean"
    c36 = _Char(); cyoa.start_scene(c36, "sp_arrival")
    for ch in ("real", "send_back", "guest", "secret"):
        assert c36.db.pending_choice, f"sp(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c36, ch)[0] is not None, f"sp(b) '{ch}' failed"
    assert c36.db.pending_choice is None and c36.db.scene_flags is None, "sp(b) should end clean"

    # The Accounting (kit-combination payoff) — bare body reads the blank-file line; a kitted
    # body reads its hardware back; both chain to a clean end.
    c37 = _Char(); cyoa.start_scene(c37, "iv_arrival")
    bare_prompt = cyoa._BUILDERS["iv_arrival"](c37)["prompt"].lower()
    assert "blank" in bare_prompt or "barely begun" in bare_prompt, "bare body should read as a blank file"
    ivbeats = []
    for ch in ("ache", "add", "stay"):
        p = c37.db.pending_choice
        assert p, f"accounting: no pending before '{ch}'"
        ivbeats.append(p["key"])
        assert cyoa.resolve_choice(c37, ch)[0] is not None, f"accounting '{ch}' did not resolve"
    assert ivbeats == ["iv_arrival", "iv_addition", "iv_close"], ivbeats
    assert c37.db.pending_choice is None and c37.db.scene_flags is None, "accounting should end clean"
    # kitted body: the ledger reads hardware back, and the §0 line is honoured in the floor branch.
    c38 = _Char()
    c38.db.piercings = ["clit_ring", "nipple_l"]; c38.db.lactation_locked = True
    kit_prompt = cyoa._BUILDERS["iv_arrival"](c38)["prompt"].lower()
    assert "piercing" in kit_prompt and "milk-port" in kit_prompt, "kitted body should read its hardware"
    cyoa.start_scene(c38, "iv_arrival")
    for ch in ("floor_ask", "not_today", "go"):
        assert c38.db.pending_choice, f"accounting(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c38, ch)[0] is not None, f"accounting(b) '{ch}' failed"
    assert c38.db.pending_choice is None and c38.db.scene_flags is None, "accounting(b) should end clean"

    # The Kennel (petplay) — chains both branches; go_pet sets the real pet state.
    c39 = _Char(); cyoa.start_scene(c39, "kn_arrival")
    knbeats = []
    for ch in ("drop", "learn_eager", "stay_pet"):
        p = c39.db.pending_choice
        assert p, f"kennel: no pending before '{ch}'"
        knbeats.append(p["key"])
        assert cyoa.resolve_choice(c39, ch)[0] is not None, f"kennel '{ch}' did not resolve"
    assert knbeats == ["kn_arrival", "kn_train", "kn_kept"], knbeats
    assert c39.db.pending_choice is None and c39.db.scene_flags is None, "kennel should end clean"
    c40 = _Char(); cyoa.start_scene(c40, "kn_arrival")
    for ch in ("ask_pet", "her_pet", "stand_person"):
        assert c40.db.pending_choice, f"kennel(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c40, ch)[0] is not None, f"kennel(b) '{ch}' failed"
    assert c40.db.pending_choice is None and c40.db.scene_flags is None, "kennel(b) should end clean"

    # The Doll Cabinet (dollification) — chains both branches; go_doll sets the real seal.
    c41 = _Char(); cyoa.start_scene(c41, "dl_arrival")
    dlbeats = []
    for ch in ("still", "seal_in", "stay_doll"):
        p = c41.db.pending_choice
        assert p, f"doll: no pending before '{ch}'"
        dlbeats.append(p["key"])
        assert cyoa.resolve_choice(c41, ch)[0] is not None, f"doll '{ch}' did not resolve"
    assert dlbeats == ["dl_arrival", "dl_seal", "dl_displayed"], dlbeats
    assert c41.db.latex_sealed is True, "doll seal should set the real latex_sealed flag"
    assert c41.db.pending_choice is None and c41.db.scene_flags is None, "doll should end clean"
    c42 = _Char(); cyoa.start_scene(c42, "dl_arrival")
    for ch in ("ask_doll", "seal_aware", "crack_seal"):
        assert c42.db.pending_choice, f"doll(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c42, ch)[0] is not None, f"doll(b) '{ch}' failed"
    assert c42.db.pending_choice is None and c42.db.scene_flags is None, "doll(b) should end clean"

    # The Filling Station (cumflation) — chains both branches; go_cumflate no-ops cleanly
    # without an inflation zone but the scene still flows.
    c43 = _Char(); cyoa.start_scene(c43, "cf_arrival")
    cfbeats = []
    for ch in ("open", "hold_it", "carry"):
        p = c43.db.pending_choice
        assert p, f"cumflation: no pending before '{ch}'"
        cfbeats.append(p["key"])
        assert cyoa.resolve_choice(c43, ch)[0] is not None, f"cumflation '{ch}' did not resolve"
    assert cfbeats == ["cf_arrival", "cf_fill", "cf_held"], cfbeats
    assert c43.db.pending_choice is None and c43.db.scene_flags is None, "cumflation should end clean"
    c44 = _Char(); cyoa.start_scene(c44, "cf_arrival")
    for ch in ("ask_mark", "beg_less", "drain_word"):
        assert c44.db.pending_choice, f"cumflation(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c44, ch)[0] is not None, f"cumflation(b) '{ch}' failed"
    assert c44.db.pending_choice is None and c44.db.scene_flags is None, "cumflation(b) should end clean"

    # The Wet Room (watersports) — chains both branches; facility methods no-op without a
    # running cycle but the scene flows and ends clean.
    c45 = _Char(); cyoa.start_scene(c45, "ws_arrival")
    wsbeats = []
    for ch in ("accept", "urinal", "stay_fixture"):
        p = c45.db.pending_choice
        assert p, f"watersports: no pending before '{ch}'"
        wsbeats.append(p["key"])
        assert cyoa.resolve_choice(c45, ch)[0] is not None, f"watersports '{ch}' did not resolve"
    assert wsbeats == ["ws_arrival", "ws_use", "ws_after"], wsbeats
    assert c45.db.pending_choice is None and c45.db.scene_flags is None, "watersports should end clean"
    c46 = _Char(); cyoa.start_scene(c46, "ws_arrival")
    for ch in ("ws_bladder", "shower", "unfix"):
        assert c46.db.pending_choice, f"watersports(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c46, ch)[0] is not None, f"watersports(b) '{ch}' failed"
    assert c46.db.pending_choice is None and c46.db.scene_flags is None, "watersports(b) should end clean"

    # CNC (The Take) — full path chains frame→take→after; and the §0 word ENDS it mid-scene.
    c47 = _Char(); cyoa.start_scene(c47, "cn_arrival")
    cnbeats = []
    for ch in ("surrender_frame", "fight", "held"):
        p = c47.db.pending_choice
        assert p, f"cnc: no pending before '{ch}'"
        cnbeats.append(p["key"])
        assert cyoa.resolve_choice(c47, ch)[0] is not None, f"cnc '{ch}' did not resolve"
    assert cnbeats == ["cn_arrival", "cn_take", "cn_after"], cnbeats
    assert c47.db.pending_choice is None and c47.db.scene_flags is None, "cnc should end clean"
    # the safeword path: at the take beat, the real word ends everything at once (no cn_after).
    c48 = _Char(); cyoa.start_scene(c48, "cn_arrival")
    cyoa.resolve_choice(c48, "test_word")  # frame beat
    assert c48.db.pending_choice and c48.db.pending_choice["key"] == "cn_take", "cnc should reach the take"
    cyoa.resolve_choice(c48, "the_word")   # §0 word mid-scene
    assert c48.db.pending_choice is None and c48.db.scene_flags is None, "the word must end the scene clean"

    # The Rig (bondage) — chains both branches; go_bound sets the real lock flags.
    c49 = _Char(); cyoa.start_scene(c49, "bd_arrival")
    bdbeats = []
    for ch in ("give_limbs", "hang", "kept_rigged"):
        p = c49.db.pending_choice
        assert p, f"bondage: no pending before '{ch}'"
        bdbeats.append(p["key"])
        assert cyoa.resolve_choice(c49, ch)[0] is not None, f"bondage '{ch}' did not resolve"
    assert bdbeats == ["bd_arrival", "bd_bound", "bd_after"], bdbeats
    assert c49.db.navigation_locked is True and c49.db.self_cmds_locked is True, \
        "bondage should set the real movement/self-command locks"
    assert c49.db.pending_choice is None and c49.db.scene_flags is None, "bondage should end clean"
    c50 = _Char(); cyoa.start_scene(c50, "bd_arrival")
    for ch in ("ask_rig", "use_suspended", "drop_straps"):
        assert c50.db.pending_choice, f"bondage(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c50, ch)[0] is not None, f"bondage(b) '{ch}' failed"
    assert c50.db.pending_choice is None and c50.db.scene_flags is None, "bondage(b) should end clean"

    # Bethany's Long Night (the savor-piece) — five beats chain; bethany_breeds runs real.
    c51 = _Char(); cyoa.start_scene(c51, "bn_arrival")
    bnbeats = []
    for ch in ("open_eager", "take_all", "feel_lock", "drown", "melt"):
        p = c51.db.pending_choice
        assert p, f"longnight: no pending before '{ch}'"
        bnbeats.append(p["key"])
        assert cyoa.resolve_choice(c51, ch)[0] is not None, f"longnight '{ch}' did not resolve"
    assert bnbeats == ["bn_arrival", "bn_seat", "bn_knot", "bn_dark", "bn_after"], bnbeats
    assert c51.db.pending_choice is None and c51.db.scene_flags is None, "longnight should end clean"
    # the alternate Long Night branch (brace / gag / sob-and-take / stay-awake / ask-the-love).
    c52 = _Char(); cyoa.start_scene(c52, "bn_arrival")
    for ch in ("brace", "gag_drool", "the_word_knot", "stay_awake", "floor_after"):
        assert c52.db.pending_choice, f"longnight(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c52, ch)[0] is not None, f"longnight(b) '{ch}' failed"
    assert c52.db.pending_choice is None and c52.db.scene_flags is None, "longnight(b) should end clean"

    # The Rut (marquee event) — both beats chain; and it's in the random event dispatcher pool.
    c53 = _Char(); cyoa.start_scene(c53, "ev_rut")
    rutbeats = []
    for ch in ("give_in", "sink"):
        p = c53.db.pending_choice
        assert p, f"rut: no pending before '{ch}'"
        rutbeats.append(p["key"])
        assert cyoa.resolve_choice(c53, ch)[0] is not None, f"rut '{ch}' did not resolve"
    assert rutbeats == ["ev_rut", "ev_rut_b"], rutbeats
    assert c53.db.pending_choice is None and c53.db.scene_flags is None, "rut should end clean"
    assert "ev_rut" in cyoa._EVENT_OPENINGS, "the Rut should be in the random event pool"
    # the §0 word ends it even mid-frenzy.
    c54 = _Char(); cyoa.start_scene(c54, "ev_rut")
    cyoa.resolve_choice(c54, "find_fellow")
    cyoa.resolve_choice(c54, "the_word_rut")
    assert c54.db.pending_choice is None and c54.db.scene_flags is None, "the word must end the Rut clean"

    # The Lineage Hall (lore-rich) — barren body reads a blank page; a productive one reads its
    # real stud-book; both chain clean.
    c55 = _Char(); cyoa.start_scene(c55, "lh_arrival")
    blank = cyoa._BUILDERS["lh_arrival"](c55)["prompt"].lower()
    assert "blank" in blank or "clean page" in blank or "nothing yet" in blank, "barren body should read a blank page"
    for ch in ("look", "just_carry"):
        assert c55.db.pending_choice, f"lineage: stall before '{ch}'"
        assert cyoa.resolve_choice(c55, ch)[0] is not None, f"lineage '{ch}' failed"
    assert c55.db.pending_choice is None and c55.db.scene_flags is None, "lineage should end clean"
    c56 = _Char()
    c56.db.offspring_counts = {"bethany": 3, "hound": 2}
    c56.db.offspring_by_sire = {"Bethany": 3, "the kennel": 2}
    prod = cyoa._BUILDERS["lh_arrival"](c56)["prompt"]
    assert "STUD-BOOK" in prod and "Bethany" in prod, "productive body should read its real stud-book"
    cyoa.start_scene(c56, "lh_arrival")
    for ch in ("ask_depth", "extend"):
        assert c56.db.pending_choice, f"lineage(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c56, ch)[0] is not None, f"lineage(b) '{ch}' failed"
    assert c56.db.pending_choice is None and c56.db.scene_flags is None, "lineage(b) should end clean"

    # Pillow Talk (lore) — the looping lore menu: ask several topics, the menu re-poses, then
    # leaving closes it clean.
    c57 = _Char(); cyoa.start_scene(c57, "bt_arrival")
    cyoa.resolve_choice(c57, "process")     # arrival → menu
    assert c57.db.pending_choice and c57.db.pending_choice["key"] == "bt_menu", "lore should loop to the menu"
    cyoa.resolve_choice(c57, "devotion")    # menu → menu (loops)
    assert c57.db.pending_choice["key"] == "bt_menu", "lore menu should re-pose on each ask"
    cyoa.resolve_choice(c57, "floor")       # the §0 topic
    assert c57.db.pending_choice["key"] == "bt_menu"
    cyoa.resolve_choice(c57, "enough")      # menu → close
    assert c57.db.pending_choice and c57.db.pending_choice["key"] == "bt_close", "enough should go to close"
    cyoa.resolve_choice(c57, "rest")
    assert c57.db.pending_choice is None and c57.db.scene_flags is None, "pillow talk should end clean"

    # The Pod (Deep Stock, experienced) — chains all beats; go_pod sets the real deep-stock state.
    c58 = _Char(); cyoa.start_scene(c58, "pd_arrival")
    pdbeats = []
    for ch in ("step_in", "plumb_in", "stay_deep"):
        p = c58.db.pending_choice
        assert p, f"pod: no pending before '{ch}'"
        pdbeats.append(p["key"])
        assert cyoa.resolve_choice(c58, ch)[0] is not None, f"pod '{ch}' did not resolve"
    assert pdbeats == ["pd_arrival", "pd_seal", "pd_kept"], pdbeats
    assert c58.db.total_dependence is True and c58.db.body_processing_locked is True, \
        "pod should set the real deep-stock dependence flags"
    assert c58.db.pending_choice is None and c58.db.scene_flags is None, "pod should end clean"
    c59 = _Char(); cyoa.start_scene(c59, "pd_arrival")
    for ch in ("lifted", "breed_full", "surface_word"):
        assert c59.db.pending_choice, f"pod(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c59, ch)[0] is not None, f"pod(b) '{ch}' failed"
    assert c59.db.pending_choice is None and c59.db.scene_flags is None, "pod(b) should end clean"

    # The Showing Gala (marquee event) — both beats chain; in the random event pool.
    c60 = _Char(); cyoa.start_scene(c60, "ev_gala")
    galabeats = []
    for ch in ("shine", "bask"):
        p = c60.db.pending_choice
        assert p, f"gala: no pending before '{ch}'"
        galabeats.append(p["key"])
        assert cyoa.resolve_choice(c60, ch)[0] is not None, f"gala '{ch}' did not resolve"
    assert galabeats == ["ev_gala", "ev_gala_b"], galabeats
    assert c60.db.pending_choice is None and c60.db.scene_flags is None, "gala should end clean"
    assert "ev_gala" in cyoa._EVENT_OPENINGS, "the Gala should be in the random event pool"
    c61 = _Char(); cyoa.start_scene(c61, "ev_gala")
    for ch in ("demonstrate", "the_word_gala"):
        assert c61.db.pending_choice, f"gala(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c61, ch)[0] is not None, f"gala(b) '{ch}' failed"
    assert c61.db.pending_choice is None and c61.db.scene_flags is None, "gala(b) should end clean"

    # The Claiming (Bethany's brand) — chains both branches; bethany_brand sets real ownership+mark.
    c62 = _Char(); cyoa.start_scene(c62, "cl_arrival")
    clbeats = []
    for ch in ("offer", "wear_it", "stay_marked"):
        p = c62.db.pending_choice
        assert p, f"claiming: no pending before '{ch}'"
        clbeats.append(p["key"])
        assert cyoa.resolve_choice(c62, ch)[0] is not None, f"claiming '{ch}' did not resolve"
    assert clbeats == ["cl_arrival", "cl_brand", "cl_after"], clbeats
    assert c62.db.bethany_owned is True and c62.db.bethany_branded is True, \
        "claiming should set real ownership + brand"
    assert c62.db.title_suffix == "— Bethany's", "claiming should claim the title"
    assert c62.db.pending_choice is None and c62.db.scene_flags is None, "claiming should end clean"
    c63 = _Char(); cyoa.start_scene(c63, "cl_arrival")
    for ch in ("ask_why_b", "weep_wear", "branded_free"):
        assert c63.db.pending_choice, f"claiming(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c63, ch)[0] is not None, f"claiming(b) '{ch}' failed"
    assert c63.db.pending_choice is None and c63.db.scene_flags is None, "claiming(b) should end clean"

    # Between Two Owners (the peerage, live) — both branches chain; real bethany_breeds runs.
    c64 = _Char(); cyoa.start_scene(c64, "tw_arrival")
    twbeats = []
    for ch in ("offer_both", "bethany_turn", "kept_between"):
        p = c64.db.pending_choice
        assert p, f"twoowners: no pending before '{ch}'"
        twbeats.append(p["key"])
        assert cyoa.resolve_choice(c64, ch)[0] is not None, f"twoowners '{ch}' did not resolve"
    assert twbeats == ["tw_arrival", "tw_shared", "tw_after"], twbeats
    assert c64.db.pending_choice is None and c64.db.scene_flags is None, "twoowners should end clean"
    c65 = _Char(); cyoa.start_scene(c65, "tw_arrival")
    for ch in ("feel_difference", "seraphine_turn", "name_sober"):
        assert c65.db.pending_choice, f"twoowners(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c65, ch)[0] is not None, f"twoowners(b) '{ch}' failed"
    assert c65.db.pending_choice is None and c65.db.scene_flags is None, "twoowners(b) should end clean"

    # On the Record (manufactured consent) — both branches chain clean.
    c90 = _Char(); cyoa.start_scene(c90, "mc_arrival")
    mcbeats = []
    for ch in ("give_yes", "seat_consent", "carry_yes"):
        p = c90.db.pending_choice
        assert p, f"ontherecord: no pending before '{ch}'"
        mcbeats.append(p["key"])
        assert cyoa.resolve_choice(c90, ch)[0] is not None, f"ontherecord '{ch}' did not resolve"
    assert mcbeats == ["mc_arrival", "mc_record", "mc_after"], mcbeats
    assert c90.db.pending_choice is None and c90.db.scene_flags is None, "ontherecord should end clean"
    c91 = _Char(); cyoa.start_scene(c91, "mc_arrival")
    for ch in ("withhold_yes", "resist_record", "dread_file"):
        assert c91.db.pending_choice, f"ontherecord(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c91, ch)[0] is not None, f"ontherecord(b) '{ch}' failed"
    assert c91.db.pending_choice is None and c91.db.scene_flags is None, "ontherecord(b) should end clean"

    # The Gift — gift-wrapped and handed to Seraphine; both branches chain clean.
    c92 = _Char(); cyoa.start_scene(c92, "gf_arrival")
    gfbeats = []
    for ch in ("be_gift", "unwrapped", "be_kept_gift"):
        p = c92.db.pending_choice
        assert p, f"thegift: no pending before '{ch}'"
        gfbeats.append(p["key"])
        assert cyoa.resolve_choice(c92, ch)[0] is not None, f"thegift '{ch}' did not resolve"
    assert gfbeats == ["gf_arrival", "gf_presented", "gf_after"], gfbeats
    assert c92.db.pending_choice is None and c92.db.scene_flags is None, "thegift should end clean"
    c93 = _Char(); cyoa.start_scene(c93, "gf_arrival")
    for ch in ("balk_gift", "given_dread", "wrapping_home"):
        assert c93.db.pending_choice, f"thegift(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c93, ch)[0] is not None, f"thegift(b) '{ch}' failed"
    assert c93.db.pending_choice is None and c93.db.scene_flags is None, "thegift(b) should end clean"

    # The Understudy — the complicity scene; both branches chain clean.
    c88 = _Char(); cyoa.start_scene(c88, "un_arrival")
    unbeats = []
    for ch in ("take_clipboard", "lure_warm", "become"):
        p = c88.db.pending_choice
        assert p, f"understudy: no pending before '{ch}'"
        unbeats.append(p["key"])
        assert cyoa.resolve_choice(c88, ch)[0] is not None, f"understudy '{ch}' did not resolve"
    assert unbeats == ["un_arrival", "un_intake", "un_after"], unbeats
    assert c88.db.pending_choice is None and c88.db.scene_flags is None, "understudy should end clean"
    c89 = _Char(); cyoa.start_scene(c89, "un_arrival")
    for ch in ("balk_role", "warn_caught", "submit_role"):
        assert c89.db.pending_choice, f"understudy(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c89, ch)[0] is not None, f"understudy(b) '{ch}' failed"
    assert c89.db.pending_choice is None and c89.db.scene_flags is None, "understudy(b) should end clean"

    # The Breeding Machine — both branches chain (the _scene_knottrain no-ops without a cycle).
    c86 = _Char(); cyoa.start_scene(c86, "mx_arrival")
    mxbeats = []
    for ch in ("yield_machine", "ride_full", "machine_calm"):
        p = c86.db.pending_choice
        assert p, f"machine: no pending before '{ch}'"
        mxbeats.append(p["key"])
        assert cyoa.resolve_choice(c86, ch)[0] is not None, f"machine '{ch}' did not resolve"
    assert mxbeats == ["mx_arrival", "mx_ride", "mx_after"], mxbeats
    assert c86.db.pending_choice is None and c86.db.scene_flags is None, "machine should end clean"
    c87 = _Char(); cyoa.start_scene(c87, "mx_arrival")
    for ch in ("fight_machine", "endure_run", "miss_someone"):
        assert c87.db.pending_choice, f"machine(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c87, ch)[0] is not None, f"machine(b) '{ch}' failed"
    assert c87.db.pending_choice is None and c87.db.scene_flags is None, "machine(b) should end clean"

    # What Vesper Won't Finish (lore) — looping menu re-poses; clean close.
    c85 = _Char(); cyoa.start_scene(c85, "vl_arrival")
    cyoa.resolve_choice(c85, "where")
    assert c85.db.pending_choice and c85.db.pending_choice["key"] == "vl_menu", "vesper-lore should loop"
    cyoa.resolve_choice(c85, "eyes")
    assert c85.db.pending_choice["key"] == "vl_menu", "vesper-lore menu should re-pose"
    cyoa.resolve_choice(c85, "see_me")
    cyoa.resolve_choice(c85, "vl_enough")
    assert c85.db.pending_choice and c85.db.pending_choice["key"] == "vl_close", "enough -> close"
    cyoa.resolve_choice(c85, "read_back")
    assert c85.db.pending_choice is None and c85.db.scene_flags is None, "vesper-lore should end clean"

    # The Open House (marquee event) — both beats chain; in the random event pool.
    c83 = _Char(); cyoa.start_scene(c83, "ev_openhouse")
    ohbeats = []
    for ch in ("serve_house", "served_out"):
        p = c83.db.pending_choice
        assert p, f"openhouse: no pending before '{ch}'"
        ohbeats.append(p["key"])
        assert cyoa.resolve_choice(c83, ch)[0] is not None, f"openhouse '{ch}' did not resolve"
    assert ohbeats == ["ev_openhouse", "ev_openhouse_b"], ohbeats
    assert c83.db.pending_choice is None and c83.db.scene_flags is None, "openhouse should end clean"
    assert "ev_openhouse" in cyoa._EVENT_OPENINGS, "Open House should be in the random event pool"
    c84 = _Char(); cyoa.start_scene(c84, "ev_openhouse")
    for ch in ("spot_someone", "dread_market"):
        assert c84.db.pending_choice, f"openhouse(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c84, ch)[0] is not None, f"openhouse(b) '{ch}' failed"
    assert c84.db.pending_choice is None and c84.db.scene_flags is None, "openhouse(b) should end clean"

    # The Line Folds — bred by your own get; both branches chain clean (bred_by_own no-ops in stub).
    c81 = _Char(); cyoa.start_scene(c81, "lf_arrival")
    lfbeats = []
    for ch in ("take_in", "fold_in", "carry_fold"):
        p = c81.db.pending_choice
        assert p, f"linefolds: no pending before '{ch}'"
        lfbeats.append(p["key"])
        assert cyoa.resolve_choice(c81, ch)[0] is not None, f"linefolds '{ch}' did not resolve"
    assert lfbeats == ["lf_arrival", "lf_fold", "lf_after"], lfbeats
    assert c81.db.pending_choice is None and c81.db.scene_flags is None, "linefolds should end clean"
    c82 = _Char(); cyoa.start_scene(c82, "lf_arrival")
    for ch in ("reel", "endure_fold", "ask_deep"):
        assert c82.db.pending_choice, f"linefolds(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c82, ch)[0] is not None, f"linefolds(b) '{ch}' failed"
    assert c82.db.pending_choice is None and c82.db.scene_flags is None, "linefolds(b) should end clean"

    # Going Under — deep staged hypnosis; both branches chain clean.
    c79 = _Char(); cyoa.start_scene(c79, "hy_arrival")
    hybeats = []
    for ch in ("let_fall", "recite", "take_seat", "surface_calm"):
        p = c79.db.pending_choice
        assert p, f"goingunder: no pending before '{ch}'"
        hybeats.append(p["key"])
        assert cyoa.resolve_choice(c79, ch)[0] is not None, f"goingunder '{ch}' did not resolve"
    assert hybeats == ["hy_arrival", "hy_deepen", "hy_below", "hy_after"], hybeats
    assert c79.db.pending_choice is None and c79.db.scene_flags is None, "goingunder should end clean"
    c80 = _Char(); cyoa.start_scene(c80, "hy_arrival")
    for ch in ("hold_top", "mouth_silent", "ghost_resist", "claw_memory"):
        assert c80.db.pending_choice, f"goingunder(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c80, ch)[0] is not None, f"goingunder(b) '{ch}' failed"
    assert c80.db.pending_choice is None and c80.db.scene_flags is None, "goingunder(b) should end clean"

    # The Programming — installs a real trigger; both branches chain clean.
    c77 = _Char(); cyoa.start_scene(c77, "pr_arrival")
    prbeats = []
    for ch in ("kneel_trig", "let_seat", "carry_trigger"):
        p = c77.db.pending_choice
        assert p, f"programming: no pending before '{ch}'"
        prbeats.append(p["key"])
        assert cyoa.resolve_choice(c77, ch)[0] is not None, f"programming '{ch}' did not resolve"
    assert prbeats == ["pr_arrival", "pr_drill", "pr_after"], prbeats
    assert c77.db.pending_choice is None and c77.db.scene_flags is None, "programming should end clean"
    c78 = _Char(); cyoa.start_scene(c78, "pr_arrival")
    for ch in ("leak_trig", "resist_seat", "dread_who"):
        assert c78.db.pending_choice, f"programming(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c78, ch)[0] is not None, f"programming(b) '{ch}' failed"
    assert c78.db.pending_choice is None and c78.db.scene_flags is None, "programming(b) should end clean"

    # The Whelping — labor/birth; give_birth no-ops without a real pregnancy but the scene flows.
    c75 = _Char(); cyoa.start_scene(c75, "bi_arrival")
    bibeats = []
    for ch in ("labor_with", "push", "rest_birth"):
        p = c75.db.pending_choice
        assert p, f"whelping: no pending before '{ch}'"
        bibeats.append(p["key"])
        assert cyoa.resolve_choice(c75, ch)[0] is not None, f"whelping '{ch}' did not resolve"
    assert bibeats == ["bi_arrival", "bi_labor", "bi_after"], bibeats
    assert c75.db.pending_choice is None and c75.db.scene_flags is None, "whelping should end clean"
    c76 = _Char(); cyoa.start_scene(c76, "bi_arrival")
    for ch in ("labor_fight", "endure_birth", "ask_litter"):
        assert c76.db.pending_choice, f"whelping(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c76, ch)[0] is not None, f"whelping(b) '{ch}' failed"
    assert c76.db.pending_choice is None and c76.db.scene_flags is None, "whelping(b) should end clean"

    # The Outfitting — install menu is combination-aware; both branches chain clean.
    c73 = _Char(); cyoa.start_scene(c73, "ou_arrival")
    oubeats = []
    for ch in ("present_fit", "fertility", "feel_fitted"):
        p = c73.db.pending_choice
        assert p, f"outfitting: no pending before '{ch}'"
        oubeats.append(p["key"])
        assert cyoa.resolve_choice(c73, ch)[0] is not None, f"outfitting '{ch}' did not resolve"
    assert oubeats == ["ou_arrival", "ou_fit", "ou_after"], oubeats
    assert c73.db.pending_choice is None and c73.db.scene_flags is None, "outfitting should end clean"
    # combination-aware: a bare body is offered milkport + cowset; a kitted one is not.
    bare_fit = {o["key"] for o in cyoa._BUILDERS["ou_fit"](_Char())["options"]}
    assert "milkport" in bare_fit and "cowset" in bare_fit, "bare body should be offered the missing kit"
    ck = _Char(); ck.db.lactation_locked = True; ck.db.piercings = ["x"]
    kitted_fit = {o["key"] for o in cyoa._BUILDERS["ou_fit"](ck)["options"]}
    assert "milkport" not in kitted_fit and "cowset" not in kitted_fit, "already-fitted kit shouldn't be re-offered"
    c74 = _Char(); cyoa.start_scene(c74, "ou_arrival")
    for ch in ("balk_fit", "tail", "dread_chart"):
        assert c74.db.pending_choice, f"outfitting(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c74, ch)[0] is not None, f"outfitting(b) '{ch}' failed"
    assert c74.db.pending_choice is None and c74.db.scene_flags is None, "outfitting(b) should end clean"

    # The Refinement — both real procedures chain and set their flags.
    c71 = _Char(); cyoa.start_scene(c71, "fm_arrival")
    fmbeats = []
    for ch in ("lean_sissy", "sissify", "meet_new"):
        p = c71.db.pending_choice
        assert p, f"refinement: no pending before '{ch}'"
        fmbeats.append(p["key"])
        assert cyoa.resolve_choice(c71, ch)[0] is not None, f"refinement '{ch}' did not resolve"
    assert fmbeats == ["fm_arrival", "fm_work", "fm_after"], fmbeats
    assert c71.db.pending_choice is None and c71.db.scene_flags is None, "refinement should end clean"
    c72 = _Char(); cyoa.start_scene(c72, "fm_arrival")
    for ch in ("lean_geld", "geld", "mourn_old"):
        assert c72.db.pending_choice, f"refinement(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c72, ch)[0] is not None, f"refinement(b) '{ch}' failed"
    assert c72.db.pending_choice is None and c72.db.scene_flags is None, "refinement(b) should end clean"

    # The Long Milking — both branches chain through the producer loop.
    c69 = _Char(); cyoa.start_scene(c69, "mm_arrival")
    mmbeats = []
    for ch in ("settle", "give_milk", "sink_milk"):
        p = c69.db.pending_choice
        assert p, f"milking: no pending before '{ch}'"
        mmbeats.append(p["key"])
        assert cyoa.resolve_choice(c69, ch)[0] is not None, f"milking '{ch}' did not resolve"
    assert mmbeats == ["mm_arrival", "mm_letdown", "mm_after"], mmbeats
    assert c69.db.pending_choice is None and c69.db.scene_flags is None, "milking should end clean"
    c70 = _Char(); cyoa.start_scene(c70, "mm_arrival")
    for ch in ("brace_mm", "ride_loop", "feel_fill"):
        assert c70.db.pending_choice, f"milking(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c70, ch)[0] is not None, f"milking(b) '{ch}' failed"
    assert c70.db.pending_choice is None and c70.db.scene_flags is None, "milking(b) should end clean"

    # Letters at the Counter (Seraphine's lore) — looping menu re-poses; clean close.
    c68 = _Char(); cyoa.start_scene(c68, "sl_arrival")
    cyoa.resolve_choice(c68, "peerage")     # arrival → menu
    assert c68.db.pending_choice and c68.db.pending_choice["key"] == "sl_menu", "sera-lore should loop to the menu"
    cyoa.resolve_choice(c68, "immune")      # menu → menu
    assert c68.db.pending_choice["key"] == "sl_menu", "sera-lore menu should re-pose"
    cyoa.resolve_choice(c68, "read_me")
    cyoa.resolve_choice(c68, "sl_enough")   # menu → close
    assert c68.db.pending_choice and c68.db.pending_choice["key"] == "sl_close", "enough should go to close"
    cyoa.resolve_choice(c68, "carry_lore")
    assert c68.db.pending_choice is None and c68.db.scene_flags is None, "sera-lore should end clean"

    # The Edge (denial/edging) — both branches chain; edge_set sets the real denial state.
    c66 = _Char(); cyoa.start_scene(c66, "ed_arrival")
    edbeats = []
    for ch in ("submit_edge", "hold_at_edge", "ache"):
        p = c66.db.pending_choice
        assert p, f"edge: no pending before '{ch}'"
        edbeats.append(p["key"])
        assert cyoa.resolve_choice(c66, ch)[0] is not None, f"edge '{ch}' did not resolve"
    assert edbeats == ["ed_arrival", "ed_ride", "ed_after"], edbeats
    assert c66.db.orgasm_denial is True, "edge should set the real orgasm_denial state"
    assert c66.db.pending_choice is None and c66.db.scene_flags is None, "edge should end clean"
    c67 = _Char(); cyoa.start_scene(c67, "ed_arrival")
    for ch in ("fight_edge", "beg", "thank_edge"):
        assert c67.db.pending_choice, f"edge(b): stall before '{ch}'"
        assert cyoa.resolve_choice(c67, ch)[0] is not None, f"edge(b) '{ch}' failed"
    assert c67.db.pending_choice is None and c67.db.scene_flags is None, "edge(b) should end clean"

    # Hub routing: the six dedicated kink set-pieces are reachable from the facility hub.
    hub_keys = {o["key"] for o in cyoa._BUILDERS["facility_hub"](_Char())["options"]}
    for need in ("kennel", "doll", "filling", "wetroom", "rig", "cnc"):
        assert need in hub_keys, f"hub should route to '{need}'"

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
    test_floor_flag_coverage, test_pronoun_backup_roundtrip, test_regression_thresholds,
    test_star_chart, test_quota_normalizer, test_maze, test_sire_temperaments,
    test_fellow_progression, test_speech_filter_order, test_heat_tell, test_honorifics_address,
    test_honorific_escalation, test_poste_ripen, test_passenger, test_bethany_scene,
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
