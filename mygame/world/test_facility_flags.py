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
    # neuter / sissify
    "neutered", "sissified",
    # studs / lineage / fellow
    "facility_studs", "facility_fellow", "facility_fellow_ref", "fellow_cross_sires",
    "offspring_by_sire", "offspring_by_sex", "offspring_max_gen",
    # dairy engorgement
    "milk_engorge_beats",
    # CYOA choices
    "pending_choice", "cycle_emphasis",
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


_TESTS = [
    test_floor_flag_coverage, test_regression_thresholds, test_star_chart,
    test_quota_normalizer, test_maze, test_sire_temperaments, test_fellow_progression,
    test_speech_filter_order,
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
