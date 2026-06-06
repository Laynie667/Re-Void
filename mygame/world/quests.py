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
}

# Achievement def: {name, desc, faction, secret}
ACHIEVEMENTS = {
    "first_day":  {"name": "First Day", "desc": "Completed intake.", "faction": "facility", "secret": False},
    "broken_in":  {"name": "Broken In", "desc": "Stopped resisting the Process.", "faction": "facility", "secret": False},
    "broodmare":  {"name": "Broodmare", "desc": "Became the line's reliable supply.", "faction": "facility", "secret": False},
    "perfected":  {"name": "Perfected Livestock", "desc": "Reached the terminus of the Process — Deep Stock opens.", "faction": "facility", "secret": False},
}


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


def available_quests(char, faction=None):
    """Quests whose prereqs are met, not already done (unless repeatable), optionally
    filtered to a faction."""
    out = []
    for qid, qdef in all_quests().items():
        if faction and qdef.get("faction") != faction:
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
    rk = req.get("rank")
    if rk:
        try:
            from world.factions import get_rank_index
            if get_rank_index(char, rk[0]) < int(rk[1]):
                return False
        except Exception:
            return False
    return True
