"""
world/quests.py — quests, achievements, and EXP (Phase 1 core).

The progression engine that makes "how far you get" a journey rather than a meter,
and the fuel for faction advance="quest"/"exp" (see world/factions.py) and any gated
room / command / shop. Data-driven like the faction registry: built-in quests and
achievements live here as defaults, and owners/players add their own via the
persistent store (faction-authored achievements, player-authored quests).

Per-character state:
  db.exp          : {pool: int}            — exp pools ("global" + per-faction key)
  db.quests       : {qid: {"state": "active|done|failed",
                           "progress": {step_id: int}, "started": ts, "completed": ts}}
  db.achievements : [aid, ...]             — earned (public unless the def is secret)

Nothing here touches the OOC floor.
"""

import time

# ── persistent store (custom quests/achievements) ─────────────────────────────
_KEY = "revoid_quests"
_MEM = {}


def _load():
    try:
        from evennia.server.models import ServerConfig
        data = ServerConfig.objects.conf(_KEY, default=None)
        return dict(data) if data else dict(_MEM)
    except Exception:
        return dict(_MEM)


def _save(data):
    _MEM.clear()
    _MEM.update(data)
    try:
        from evennia.server.models import ServerConfig
        ServerConfig.objects.conf(_KEY, value=dict(data))
    except Exception:
        pass


# ── built-in registries (seed/demo; extend in-game) ──────────────────────────
# Quest def: {name, desc, faction, realm, repeatable, hidden,
#             prereq:{quests,achievements,exp,rank}, steps:[{id,desc,count}],
#             rewards:{exp:{pool:n}, shards, scrip, achievement, rank:(faction,idx)}}
QUESTS = {
    "facility_intake": {
        "name": "Intake", "faction": "facility", "realm": "facility",
        "desc": "Begin processing: sign, and take your first sessions on the floor.",
        "repeatable": False, "hidden": False, "prereq": {},
        "steps": [
            {"id": "sign",   "desc": "Sign the residency contract", "count": 1},
            {"id": "milked", "desc": "Be milked on the floor", "count": 3},
            {"id": "bred",   "desc": "Be bred in the pens", "count": 1},
        ],
        "rewards": {"exp": {"facility": 50}, "achievement": "first_day"},
        "then": "facility_breaking",
    },
    "facility_breaking": {
        "name": "Breaking In", "faction": "facility", "realm": "facility",
        "desc": "Submit to the Process — let the line have you, again and again, until "
                "resisting it stops occurring to you.",
        "repeatable": False, "hidden": False, "prereq": {"quests": ["facility_intake"]},
        "steps": [{"id": "process", "desc": "Be processed by the line", "count": 15}],
        "rewards": {"exp": {"facility": 150}, "achievement": "broken_in"},
        "then": "facility_broodmare",
    },
    "facility_broodmare": {
        "name": "Broodmare", "faction": "facility", "realm": "facility",
        "desc": "Become what you produce — bred and milked and bred again, your line the "
                "facility's reliable supply.",
        "repeatable": False, "hidden": False,
        "prereq": {"quests": ["facility_breaking"], "exp": {"facility": 300}},
        "steps": [{"id": "process", "desc": "Serve the line as a broodmare", "count": 30}],
        "rewards": {"exp": {"facility": 400}, "achievement": "broodmare"},
        "then": "facility_perfected",
    },
    "facility_perfected": {
        "name": "Perfected", "faction": "facility", "realm": "facility",
        "desc": "The terminus: past lessons, past self — finished product, racked and humming.",
        "repeatable": False, "hidden": False,
        "prereq": {"quests": ["facility_broodmare"]},
        "steps": [{"id": "process", "desc": "Be perfected on the lines", "count": 50}],
        "rewards": {"exp": {"facility": 1000}, "achievement": "perfected"},
    },
    # An optional, parallel line — completed by the permanent work happening TO you,
    # whenever it happens (early or late). Auto-enrolled by the cycle once intake's done.
    "facility_marked": {
        "name": "Marked Property", "faction": "facility", "realm": "facility",
        "desc": "Made legible as owned — branded, pierced, and tattooed where it shows.",
        "repeatable": False, "hidden": False, "prereq": {"quests": ["facility_intake"]},
        "steps": [
            {"id": "branded",  "desc": "Take a brand", "count": 1},
            {"id": "pierced",  "desc": "Take a piercing or ring", "count": 1},
            {"id": "tattooed", "desc": "Take a permanent tattoo", "count": 1},
        ],
        "rewards": {"exp": {"facility": 120}, "achievement": "marked_property"},
    },
    # ── A fork (player choice, mutually exclusive) — taking one forecloses the other.
    #    `manual` so the cycle won't auto-enrol you; you choose with `quest start`.
    "facility_favourite": {
        "name": "Bethany's Favourite", "faction": "facility", "realm": "facility",
        "desc": "Reach FOR her instead of away — earn a place at her desk, kept and owned and "
                "fond of it. (Closes the Unbroken path.)",
        "manual": True, "repeatable": False, "hidden": False,
        "prereq": {"quests": ["facility_breaking"],
                   "not_quests": ["facility_defiant"], "not_achievements": ["unbroken"]},
        "steps": [{"id": "serve", "desc": "Be kept and used in the office", "count": 8}],
        "rewards": {"exp": {"facility": 250}, "achievement": "favourite"},
    },
    "facility_defiant": {
        "name": "The Unbroken", "faction": "facility", "realm": "facility",
        "desc": "Refuse the Process the only way left — take the sty and the punishment over "
                "the comfort, and stay yourself a while longer. (Closes the Favourite path.)",
        "manual": True, "repeatable": False, "hidden": False,
        "prereq": {"quests": ["facility_breaking"],
                   "not_quests": ["facility_favourite"], "not_achievements": ["favourite"]},
        "steps": [{"id": "resist", "desc": "Take the sty rather than submit", "count": 8}],
        "rewards": {"exp": {"facility": 250}, "achievement": "unbroken"},
    },
    # ── Escape attempts (IN-FICTION ONLY). Plot it out across cycles ('plot' ticks each
    #    beat via the generic 'process'); when the plan's ready it RESOLVES as a run that
    #    usually FAILS the deeper you are, and failure is brutal. The real exit is never
    #    these — `escape`/`facilityreset` (the §0 OOC floor) always works and never fails.
    "run_waystone": {
        "name": "The Waystone Gambit", "faction": "facility", "realm": "facility",
        "desc": "Learn the word the lobby waystone answers to, and slip out the way you came in.",
        "manual": True, "repeatable": True, "hidden": False,
        "prereq": {"quests": ["facility_intake"]},
        "steps": [{"id": "process", "desc": "Watch, wait, and learn the word", "count": 4}],
        "rewards": {}, "resolve": "escape",
    },
    "run_pens": {
        "name": "Through the Pens", "faction": "facility", "realm": "facility",
        "desc": "Slip out the animals' route while the handlers are busy.",
        "manual": True, "repeatable": True, "hidden": False,
        "prereq": {"quests": ["facility_intake"]},
        "steps": [{"id": "process", "desc": "Find the gap and time the run", "count": 5}],
        "rewards": {}, "resolve": "escape",
    },
    "run_keys": {
        "name": "Bethany's Keys", "faction": "facility", "realm": "facility",
        "desc": "Lift the keys from her office while she's distracted with you — and she is never "
                "as distracted as you hope.",
        "manual": True, "repeatable": True, "hidden": False,
        "prereq": {"quests": ["facility_intake"]},
        "steps": [{"id": "process", "desc": "Get close enough, often enough, to palm them", "count": 7}],
        "rewards": {}, "resolve": "escape",
    },
    # ── The Owned capstone — opens once she's bought, collared, devoted, and branded;
    #    a little more time at the desk, and she's wholly Bethany's (a parallel terminus to
    #    the institutional 'Perfected'). Earned via the office milestones, not the grade.
    "owned_hers": {
        "name": "Wholly Hers", "faction": "facility", "realm": "facility",
        "desc": "Stop being the facility's product and become Bethany's, specifically — kept "
                "at her desk, named, marked, and reaching for her.",
        "manual": True, "repeatable": False, "hidden": False,
        "prereq": {"achievements": ["bought", "collared", "devoted", "her_mark"]},
        "steps": [{"id": "serve", "desc": "Settle into being kept", "count": 5}],
        "rewards": {"exp": {"facility": 600}, "achievement": "wholly_hers"},
    },
    # ── The Deep Stock malfunction — the one run that can ACTUALLY get you out. Only the
    #    deepest stock are wired into the lines that fault; you ride the gap when the
    #    pumps cut and the locks drop. Unlike the run_* gambits (which always end with a
    #    hand at your neck), this CAN succeed — and being loose just means being hunted.
    #    Failure here is the worst in the place. (The §0 OOC floor is never this; it's
    #    `escape`/`facilityreset`, always, and it never rolls.)
    "run_malfunction": {
        "name": "The Malfunction", "faction": "facility", "realm": "facility",
        "desc": "Down on Sub-Level P the lines fault sometimes — pumps stall, locks drop, the "
                "lights go red. Learn the rhythm of it, and the next time it happens, be ready "
                "to move. This is the one way out that the building itself can give you.",
        "manual": True, "repeatable": True, "hidden": False,
        "prereq": {"achievements": ["deep_stock"], "not_flags": ["facility_escaped"]},
        "steps": [{"id": "process", "desc": "Learn the fault, and wait for the red light", "count": 3}],
        "rewards": {}, "resolve": "escape_malfunction",
    },
    # ── The escaped meta-loop — only available once you're actually OUT (db.facility_escaped).
    #    Turn yourself back in (penitent; resumes processing), or run the rescue line and
    #    spring other stock — which pays in standing and the liberator badge if you get away
    #    with it, and is catastrophic if you don't.
    "turn_in": {
        "name": "Turn Yourself In", "faction": "facility", "realm": "facility",
        "desc": "The ache for the line doesn't leave you out here. Walk back through the lobby "
                "waystone, sit down at her desk, and ask to be put back on the board.",
        "manual": True, "repeatable": True, "hidden": False,
        "prereq": {"flags": ["facility_escaped"]},
        "steps": [{"id": "process", "desc": "Make your way back to the intake door", "count": 1}],
        "rewards": {}, "resolve": "turn_in",
    },
    "spring_stock": {
        "name": "Spring the Stock", "faction": "facility", "realm": "facility",
        "desc": "You know the gaps now — the fault timings, the pen routes, the word the "
                "waystone answers to. Slip back in while you can, and get a unit out the way "
                "you got out. If they catch you doing it, the whole house will watch what it costs.",
        "manual": True, "repeatable": True, "hidden": False,
        "prereq": {"flags": ["facility_escaped"]},
        "steps": [{"id": "process", "desc": "Get in, cut a unit loose, and get clear", "count": 4}],
        "rewards": {}, "resolve": "spring_stock",
    },
}

# Achievement def: {name, desc, faction, secret}
ACHIEVEMENTS = {
    "first_day":  {"name": "First Day", "desc": "Completed intake.", "faction": "facility", "secret": False},
    "broken_in":  {"name": "Broken In", "desc": "Stopped resisting the Process.", "faction": "facility", "secret": False},
    "broodmare":  {"name": "Broodmare", "desc": "Became the line's reliable supply.", "faction": "facility", "secret": False},
    "perfected":  {"name": "Perfected Livestock", "desc": "Reached the terminus of the Process — Deep Stock opens.", "faction": "facility", "secret": False},
    "bred_true":  {"name": "Bred True", "desc": "Dropped your first get — the line begins.", "faction": "facility", "secret": False},
    "kept_heir":  {"name": "Kept", "desc": "Bethany pulled one of your get to keep as her own.", "faction": "facility", "secret": False},
    "sold_off":   {"name": "Sold", "desc": "Knocked down on the block to a new owner.", "faction": "facility", "secret": False},
    "deep_stock": {"name": "Deep Stock", "desc": "Sealed into the lines on Sub-Level P.", "faction": "facility", "secret": True},
    # Finer milestones — fired from real events, early or late.
    "branded":   {"name": "Branded", "desc": "Took the iron — owned, and it shows.", "faction": "facility", "secret": False},
    "pierced":   {"name": "Ringed", "desc": "Took steel through the skin.", "faction": "facility", "secret": False},
    "tattooed":  {"name": "Inked", "desc": "Took permanent ink where it shows.", "faction": "facility", "secret": False},
    "marked_property": {"name": "Marked Property", "desc": "Branded, ringed, and inked — legible as owned.", "faction": "facility", "secret": False},
    "begged":    {"name": "Made to Beg", "desc": "Begged out loud for it.", "faction": "facility", "secret": False},
    "pigsty":    {"name": "Slopped", "desc": "Sent down to the pigsty.", "faction": "facility", "secret": False},
    "nursed":    {"name": "Wet Nurse", "desc": "Fed your own get on your own milk.", "faction": "facility", "secret": False},
    "favourite":  {"name": "Bethany's Favourite", "desc": "Reached for her, and was kept.", "faction": "facility", "secret": False},
    "unbroken":   {"name": "Unbroken", "desc": "Took the sty over the comfort, and stayed yourself.", "faction": "facility", "secret": False},
    "bolted":     {"name": "Bolted", "desc": "Made a run for it. (The in-fiction kind.)", "faction": "facility", "secret": False},
    "recaptured": {"name": "Recaptured", "desc": "Ran, was caught, and was broken for it.", "faction": "facility", "secret": False},
    # ── The Bethany 'Owned' track — being HERS, not just stock.
    "bought":     {"name": "Bought", "desc": "Bethany took you off the block as her own.", "faction": "facility", "secret": False},
    "collared":   {"name": "Collared", "desc": "Wears Bethany's collar, locked.", "faction": "facility", "secret": False},
    "devoted":    {"name": "Devoted", "desc": "Reorganised around Bethany — reaches for her.", "faction": "facility", "secret": False},
    "her_mark":   {"name": "Her Mark", "desc": "Wears Bethany's personal B — owned, specifically.", "faction": "facility", "secret": False},
    "wholly_hers":{"name": "Wholly Hers", "desc": "Bought, collared, devoted, branded, and kept — entirely Bethany's.", "faction": "facility", "secret": False},
    # ── The Deep Stock malfunction + the escaped meta-loop.
    "malfunction":{"name": "Malfunction", "desc": "A fault in the lines opened — and you took it.", "faction": "facility", "secret": True},
    "escaped":    {"name": "Escaped", "desc": "Got out of the facility (in-fiction). For now.", "faction": "facility", "secret": False},
    "penitent":   {"name": "Penitent", "desc": "Turned yourself back in.", "faction": "facility", "secret": False},
    "liberator":  {"name": "Liberator", "desc": "Sprang stock from the facility and got away with it.", "faction": "facility", "secret": False},
    "made_example":{"name": "Made an Example", "desc": "Caught springing stock — and the whole house watched the price.", "faction": "facility", "secret": False},
}

# ── resolvers — let a quest trigger custom logic on completion (e.g. an escape roll) ──
RESOLVERS = {}


def register_resolver(name, fn):
    """Register a completion resolver; a quest with `resolve: <name>` calls fn(char, qid)
    when it completes (used for escape-attempt rolls, etc.). Registered by the system that
    owns the logic, so this module stays decoupled."""
    RESOLVERS[name] = fn


def reset_quests(char, faction=None, also_exp=False):
    """Wipe a character's quest progress (optionally only for one faction), and optionally
    the matching EXP pool. Used by Bethany's 'reset' power. Never touches the OOC floor."""
    quests = dict(getattr(char.db, "quests", None) or {})
    if faction is None:
        char.db.quests = {}
    else:
        keep = {q: r for q, r in quests.items()
                if (all_quests().get(q) or {}).get("faction") != faction}
        char.db.quests = keep
    if also_exp and faction:
        pools = dict(getattr(char.db, "exp", None) or {})
        pools.pop(faction, None)
        char.db.exp = pools


def all_quests():
    merged = dict(QUESTS)
    merged.update(_load().get("quests") or {})
    return merged


def all_achievements():
    merged = dict(ACHIEVEMENTS)
    merged.update(_load().get("achievements") or {})
    return merged


def get_quest(qid):
    return all_quests().get((qid or "").lower())


def get_achievement(aid):
    return all_achievements().get((aid or "").lower())


# ── authoring (custom quests / achievements persisted) ────────────────────────
def create_quest(qid, data):
    d = _load(); q = dict(d.get("quests") or {})
    q[(qid or "").lower()] = dict(data); d["quests"] = q; _save(d)
    return q[(qid or "").lower()]


def delete_quest(qid):
    d = _load(); q = dict(d.get("quests") or {}); q.pop((qid or "").lower(), None)
    d["quests"] = q; _save(d)


def create_achievement(aid, data):
    d = _load(); a = dict(d.get("achievements") or {})
    a[(aid or "").lower()] = dict(data); d["achievements"] = a; _save(d)
    return a[(aid or "").lower()]


def delete_achievement(aid):
    d = _load(); a = dict(d.get("achievements") or {}); a.pop((aid or "").lower(), None)
    d["achievements"] = a; _save(d)


# ── EXP ───────────────────────────────────────────────────────────────────────
def get_exp(char, pool="global"):
    try:
        return int((char.db.exp or {}).get(pool, 0))
    except Exception:
        return 0


def grant_exp(char, amount, pool="global"):
    amount = int(amount)
    pools = dict(getattr(char.db, "exp", None) or {})
    pools[pool] = int(pools.get(pool, 0)) + amount
    char.db.exp = pools
    return pools[pool]


# ── achievements ──────────────────────────────────────────────────────────────
def has_achievement(char, aid):
    return (aid or "").lower() in (getattr(char.db, "achievements", None) or [])


def achievements_of(char, include_secret=True):
    got = list(getattr(char.db, "achievements", None) or [])
    if include_secret:
        return got
    return [a for a in got if not (get_achievement(a) or {}).get("secret")]


def grant_achievement(char, aid, announce=True):
    aid = (aid or "").lower()
    if not aid or has_achievement(char, aid):
        return False
    got = list(getattr(char.db, "achievements", None) or [])
    got.append(aid)
    char.db.achievements = got
    if announce:
        a = get_achievement(aid) or {}
        char.msg(f"|Y✦ Achievement unlocked: {a.get('name', aid)}|n — "
                 f"|x{a.get('desc', '')}|n")
    return True


def revoke_achievement(char, aid):
    aid = (aid or "").lower()
    got = list(getattr(char.db, "achievements", None) or [])
    if aid in got:
        got.remove(aid)
        char.db.achievements = got
        return True
    return False


# ── quests ────────────────────────────────────────────────────────────────────
def quest_state(char, qid):
    return dict((getattr(char.db, "quests", None) or {}).get((qid or "").lower(), {}))


def _set_quest(char, qid, rec):
    q = dict(getattr(char.db, "quests", None) or {})
    q[(qid or "").lower()] = rec
    char.db.quests = q


def available_quests(char, faction=None, auto_only=False):
    """Quests whose prereqs are met, not already done (unless repeatable), optionally
    filtered to a faction. With auto_only=True, skip `manual` quests — those are
    player-chosen fork points the cycle should NOT auto-enrol you into."""
    out = []
    for qid, qdef in all_quests().items():
        if faction and qdef.get("faction") != faction:
            continue
        if auto_only and qdef.get("manual"):
            continue
        st = quest_state(char, qid).get("state")
        if st == "active":
            continue
        if st == "done" and not qdef.get("repeatable"):
            continue
        if not meets(char, qdef.get("prereq") or {}):
            continue
        out.append(qid)
    return out


def start_quest(char, qid):
    qid = (qid or "").lower()
    qdef = get_quest(qid)
    if not qdef:
        return False, "No such quest."
    st = quest_state(char, qid)
    if st.get("state") == "active":
        return False, "Already on that quest."
    if st.get("state") == "done" and not qdef.get("repeatable"):
        return False, "You've already completed that."
    if not meets(char, qdef.get("prereq") or {}):
        return False, "You don't meet the requirements for that yet."
    _set_quest(char, qid, {"state": "active", "progress": {}, "started": time.time()})
    return True, f"Quest started: {qdef.get('name', qid)}."


def advance_quest(char, qid, step_id, n=1):
    """Add progress to a quest step; auto-completes when every step's count is met.
    Safe to call from scene hooks even if the quest isn't active (no-op then)."""
    qid = (qid or "").lower()
    qdef = get_quest(qid)
    st = quest_state(char, qid)
    if not qdef or st.get("state") != "active":
        return False
    prog = dict(st.get("progress") or {})
    prog[step_id] = int(prog.get(step_id, 0)) + int(n)
    st["progress"] = prog
    _set_quest(char, qid, st)
    # auto-complete?
    done = all(prog.get(s["id"], 0) >= int(s.get("count", 1)) for s in qdef.get("steps", []))
    if done:
        complete_quest(char, qid)
    return True


def complete_quest(char, qid):
    qid = (qid or "").lower()
    qdef = get_quest(qid)
    if not qdef:
        return False
    st = quest_state(char, qid)
    st["state"] = "done"
    st["completed"] = time.time()
    _set_quest(char, qid, st)
    char.msg(f"|G✦ Quest complete: {qdef.get('name', qid)}|n")
    _grant_rewards(char, qdef.get("rewards") or {})
    # Custom resolver (e.g. an escape attempt rolls here — and may flip this to 'failed').
    res = qdef.get("resolve")
    if res and res in RESOLVERS:
        try:
            RESOLVERS[res](char, qid)
        except Exception:
            pass
    # Chain: auto-start the next quest in the line, if its prereqs are now met.
    nxt = qdef.get("then")
    if nxt and get_quest(nxt):
        ok, _m = start_quest(char, nxt)
        if ok:
            char.msg(f"|x  …and the next stage opens: |Y{get_quest(nxt).get('name', nxt)}|x.|n")
    return True


def fail_quest(char, qid):
    qid = (qid or "").lower()
    st = quest_state(char, qid)
    if st:
        st["state"] = "failed"
        _set_quest(char, qid, st)
    return True


def _grant_rewards(char, rewards):
    for pool, amt in (rewards.get("exp") or {}).items():
        grant_exp(char, amt, pool)
    if rewards.get("achievement"):
        grant_achievement(char, rewards["achievement"])
    # currency rewards route through the multi-currency wallet
    for cur in ("shards", "scrip"):
        if rewards.get(cur):
            try:
                from world.wallet import credit
                credit(char, cur, int(rewards[cur]), reason="quest reward")
            except Exception:
                pass
    rk = rewards.get("rank")
    if rk:
        try:
            from world.factions import set_rank
            set_rank(char, rk[0], int(rk[1]))
        except Exception:
            pass


# ── the universal gate ────────────────────────────────────────────────────────
def meets(char, req):
    """Does `char` satisfy a requirement dict? Used to gate anything — rooms, commands,
    shops, faction rank advancement. req keys (all optional):
        quests:[qid...]  achievements:[aid...]  exp:{pool:n}  rank:(faction_key, index)
    """
    if not req:
        return True
    for qid in req.get("quests", []):
        if quest_state(char, qid).get("state") != "done":
            return False
    for aid in req.get("achievements", []):
        if not has_achievement(char, aid):
            return False
    for pool, n in (req.get("exp") or {}).items():
        if get_exp(char, pool) < int(n):
            return False
    # Exclusions — the heart of a winding, mutually-exclusive web: a path can require
    # that you HAVEN'T taken another (achievement earned / quest completed forecloses it).
    for aid in req.get("not_achievements", []):
        if has_achievement(char, aid):
            return False
    for qid in req.get("not_quests", []):
        if quest_state(char, qid).get("state") in ("active", "done"):
            return False
    # Live-state flags — gate on a current character db flag being set/unset (e.g.
    # `facility_escaped`: the escaped-meta quests only open while you're actually loose,
    # and the malfunction run only while you're not). Lets a winding line read live state,
    # not just permanent badges.
    for flag in req.get("flags", []):
        if not getattr(char.db, flag, False):
            return False
    for flag in req.get("not_flags", []):
        if getattr(char.db, flag, False):
            return False
    rk = req.get("rank")
    if rk:
        try:
            from world.factions import get_rank_index
            if get_rank_index(char, rk[0]) < int(rk[1]):
                return False
        except Exception:
            return False
    return True
