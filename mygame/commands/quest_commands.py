"""
commands/quest_commands.py

Player-facing quest log + achievement wall, plus authoring (faction owners / builders
write their own quests and achievements). See world/QUESTS_ACHIEVEMENTS_DESIGN.md.
"""

from evennia.commands.default.muxcommand import MuxCommand


def _author_ok(caller, faction_key=None):
    """May this caller author quests/achievements? Builders/staff anywhere; a faction's
    owner for that faction."""
    if caller.is_superuser or caller.check_permstring("Builder"):
        return True
    if faction_key:
        try:
            from world.factions import is_owner
            return is_owner(caller, faction_key)
        except Exception:
            return False
    return False


class CmdQuests(MuxCommand):
    """
    Your quest log — and (with authority) authoring quests.

    Usage:
        quests                          — your active quests + what's available
        quest <id>                      — details + your progress
        quest start <id>                — take up an available quest
        quest abandon <id>              — drop an active quest

      Authoring (faction owner / builder):
        quest create <id> = <Name>; <description> [; <faction>]
        quest step <id> + <step text>           — add a step (each needs doing once)
        quest reward <id> exp <n> | ach <aid> | shards <n> | scrip <n>
        quest grant <player> = <id>             — award a completion
        quest delete <id>
    """
    key = "quests"
    aliases = ["quest"]
    locks = "cmd:all()"
    help_category = "Progression"

    def func(self):
        caller = self.caller
        import world.quests as Q
        args = (self.args or "").strip()

        if not args:
            return self._log(caller, Q)

        parts = args.split(None, 1)
        sub = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "start":
            ok, msg = Q.start_quest(caller, rest)
            caller.msg(("|g" if ok else "|x") + msg + "|n")
        elif sub == "abandon":
            Q.fail_quest(caller, rest)
            caller.msg(f"|xAbandoned {rest}.|n")
        elif sub == "create":
            self._create(caller, Q, rest)
        elif sub == "step":
            self._step(caller, Q, rest)
        elif sub == "reward":
            self._reward(caller, Q, rest)
        elif sub == "grant":
            self._grant(caller, Q, rest)
        elif sub == "delete":
            self._delete(caller, Q, rest)
        else:
            self._detail(caller, Q, args)

    # ── views ────────────────────────────────────────────────────────────────
    def _log(self, caller, Q):
        quests = getattr(caller.db, "quests", None) or {}
        active = [q for q, r in quests.items() if r.get("state") == "active"]
        avail = Q.available_quests(caller)
        lines = ["|wQUEST LOG|n"]
        if active:
            lines.append("|x── active ──|n")
            for qid in active:
                qd = Q.get_quest(qid) or {}
                lines.append(f"  |Y{qd.get('name', qid)}|n |x({qid})|n")
        if avail:
            lines.append("|x── available ──|n")
            for qid in avail:
                qd = Q.get_quest(qid) or {}
                lines.append(f"  |c{qd.get('name', qid)}|n |x({qid})|n — quest start {qid}")
        done = [q for q, r in quests.items() if r.get("state") == "done"]
        if done:
            lines.append(f"|x── completed: {len(done)} ──|n")
        if len(lines) == 1:
            lines.append("  |xNothing active or available.|n")
        caller.msg("\n".join(lines))

    def _detail(self, caller, Q, qid):
        qd = Q.get_quest(qid)
        if not qd:
            caller.msg(f"|xNo quest '{qid}'.|n")
            return
        st = Q.quest_state(caller, qid)
        prog = st.get("progress") or {}
        lines = [f"|Y{qd.get('name', qid)}|n |x({qid})|n",
                 f"  {qd.get('desc', '')}"]
        if qd.get("steps"):
            lines.append("  |x── steps ──|n")
            for s in qd["steps"]:
                have = prog.get(s["id"], 0)
                need = int(s.get("count", 1))
                mark = "|g✓|n" if have >= need else f"|x{have}/{need}|n"
                lines.append(f"   {mark} {s.get('desc', s['id'])}")
        state = st.get("state") or ("available" if Q.meets(caller, qd.get("prereq") or {}) else "locked")
        lines.append(f"  |xstatus:|n {state}")
        caller.msg("\n".join(lines))

    # ── authoring ──────────────────────────────────────────────────────────────
    def _create(self, caller, Q, rest):
        if "=" not in rest:
            caller.msg("|xUsage: quest create <id> = <Name>; <description> [; <faction>]|n")
            return
        qid, tail = [p.strip() for p in rest.split("=", 1)]
        qid = qid.lower()
        if Q.get_quest(qid):
            caller.msg(f"|xA quest '{qid}' already exists.|n")
            return
        bits = [b.strip() for b in tail.split(";")]
        name = bits[0] if bits else qid
        desc = bits[1] if len(bits) > 1 else ""
        faction = bits[2].lower() if len(bits) > 2 else None
        if not _author_ok(caller, faction):
            caller.msg("|xYou don't have the authority to author that quest.|n")
            return
        Q.create_quest(qid, {"name": name, "desc": desc, "faction": faction,
                             "repeatable": False, "hidden": False, "prereq": {},
                             "steps": [], "rewards": {},
                             "author_id": caller.id})
        caller.msg(f"|g✦ Quest '{qid}' created. Add steps with |wquest step {qid} + <text>|g "
                   f"and rewards with |wquest reward {qid} …|g.|n")

    def _step(self, caller, Q, rest):
        if "+" not in rest:
            caller.msg("|xUsage: quest step <id> + <step text>|n")
            return
        qid, text = [p.strip() for p in rest.split("+", 1)]
        qd = Q.get_quest(qid.lower())
        if not qd:
            caller.msg("|xNo such quest.|n")
            return
        if not _author_ok(caller, qd.get("faction")) and caller.id != qd.get("author_id"):
            caller.msg("|xNot your quest to edit.|n")
            return
        steps = list(qd.get("steps") or [])
        sid = f"s{len(steps) + 1}"
        steps.append({"id": sid, "desc": text, "count": 1})
        qd["steps"] = steps
        Q.create_quest(qid.lower(), qd)
        caller.msg(f"|gStep {sid} added: {text}|n")

    def _reward(self, caller, Q, rest):
        parts = rest.split()
        if len(parts) < 3:
            caller.msg("|xUsage: quest reward <id> exp <n> | ach <aid> | shards <n> | scrip <n>|n")
            return
        qid, kind, val = parts[0].lower(), parts[1].lower(), parts[2]
        qd = Q.get_quest(qid)
        if not qd:
            caller.msg("|xNo such quest.|n")
            return
        if not _author_ok(caller, qd.get("faction")) and caller.id != qd.get("author_id"):
            caller.msg("|xNot your quest to edit.|n")
            return
        rewards = dict(qd.get("rewards") or {})
        if kind == "exp":
            pool = parts[3].lower() if len(parts) > 3 else "global"
            exp = dict(rewards.get("exp") or {}); exp[pool] = int(val); rewards["exp"] = exp
        elif kind in ("ach", "achievement"):
            rewards["achievement"] = val.lower()
        elif kind in ("shards", "scrip"):
            rewards[kind] = int(val)
        else:
            caller.msg("|xReward kind: exp <n> [pool] | ach <aid> | shards <n> | scrip <n>|n")
            return
        qd["rewards"] = rewards
        Q.create_quest(qid, qd)
        caller.msg(f"|gReward set on {qid}: {kind} {val}.|n")

    def _grant(self, caller, Q, rest):
        if "=" not in rest:
            caller.msg("|xUsage: quest grant <player> = <id>|n")
            return
        who, qid = [p.strip() for p in rest.split("=", 1)]
        qd = Q.get_quest(qid.lower())
        if not qd:
            caller.msg("|xNo such quest.|n")
            return
        if not _author_ok(caller, qd.get("faction")):
            caller.msg("|xYou can't grant that quest.|n")
            return
        target = caller.search(who, global_search=True)
        if not target:
            return
        Q.complete_quest(target, qid.lower())
        caller.msg(f"|gGranted '{qid}' to {target.db.rp_name or target.key}.|n")

    def _delete(self, caller, Q, qid):
        qd = Q.get_quest(qid.lower())
        if not qd:
            caller.msg("|xNo such quest.|n")
            return
        if not _author_ok(caller, qd.get("faction")) and caller.id != qd.get("author_id"):
            caller.msg("|xNot your quest to delete.|n")
            return
        if qid.lower() in Q.QUESTS:
            caller.msg("|xBuilt-in quests can't be deleted.|n")
            return
        Q.delete_quest(qid.lower())
        caller.msg(f"|gQuest '{qid}' deleted.|n")


class CmdAchievements(MuxCommand):
    """
    The trophy wall — your earned achievements, or another's public ones.

    Usage:
        achievements [<player>]                 — show earned achievements

      Authoring (faction owner / builder):
        achievement create <id> = <Name>; <desc> [; <faction>] [; secret]
        achievement grant <player> = <id>
        achievement delete <id>
    """
    key = "achievements"
    aliases = ["achievement", "trophies"]
    locks = "cmd:all()"
    help_category = "Progression"

    def func(self):
        caller = self.caller
        import world.quests as Q
        args = (self.args or "").strip()
        parts = args.split(None, 1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "create":
            return self._create(caller, Q, rest)
        if sub == "grant":
            return self._grant(caller, Q, rest)
        if sub == "delete":
            return self._delete(caller, Q, rest)

        # view (self or another player; secret hidden for others)
        target = caller
        is_self = True
        if args:
            target = caller.search(args, global_search=True)
            if not target:
                return
            is_self = target == caller
        got = Q.achievements_of(target, include_secret=is_self)
        name = target.db.rp_name or target.key
        if not got:
            caller.msg(f"|x{name} has earned no achievements yet.|n")
            return
        lines = [f"|wTrophy wall — {name}|n"]
        for aid in got:
            a = Q.get_achievement(aid) or {}
            tag = " |x(secret)|n" if a.get("secret") else ""
            lines.append(f"  |Y✦ {a.get('name', aid)}|n — |x{a.get('desc', '')}|n{tag}")
        caller.msg("\n".join(lines))

    def _create(self, caller, Q, rest):
        if "=" not in rest:
            caller.msg("|xUsage: achievement create <id> = <Name>; <desc> [; <faction>] [; secret]|n")
            return
        aid, tail = [p.strip() for p in rest.split("=", 1)]
        aid = aid.lower()
        if Q.get_achievement(aid):
            caller.msg(f"|xAchievement '{aid}' already exists.|n")
            return
        bits = [b.strip() for b in tail.split(";")]
        name = bits[0] if bits else aid
        desc = bits[1] if len(bits) > 1 else ""
        faction = bits[2].lower() if len(bits) > 2 and bits[2] else None
        secret = any(b.lower() == "secret" for b in bits[3:]) or (len(bits) > 2 and bits[-1].lower() == "secret")
        if not _author_ok(caller, faction):
            caller.msg("|xYou don't have the authority to author that achievement.|n")
            return
        Q.create_achievement(aid, {"name": name, "desc": desc, "faction": faction,
                                   "secret": secret, "author_id": caller.id})
        caller.msg(f"|g✦ Achievement '{aid}' created"
                   f"{' (faction ' + faction + ')' if faction else ''}"
                   f"{' [secret]' if secret else ''}.|n")

    def _grant(self, caller, Q, rest):
        if "=" not in rest:
            caller.msg("|xUsage: achievement grant <player> = <id>|n")
            return
        who, aid = [p.strip() for p in rest.split("=", 1)]
        a = Q.get_achievement(aid.lower())
        if not a:
            caller.msg("|xNo such achievement.|n")
            return
        if not _author_ok(caller, a.get("faction")):
            caller.msg("|xYou can't grant that achievement.|n")
            return
        target = caller.search(who, global_search=True)
        if not target:
            return
        if Q.grant_achievement(target, aid.lower()):
            caller.msg(f"|gGranted '{aid}' to {target.db.rp_name or target.key}.|n")
        else:
            caller.msg("|xThey already have it (or it doesn't exist).|n")

    def _delete(self, caller, Q, aid):
        a = Q.get_achievement(aid.lower())
        if not a:
            caller.msg("|xNo such achievement.|n")
            return
        if not _author_ok(caller, a.get("faction")) and caller.id != a.get("author_id"):
            caller.msg("|xNot yours to delete.|n")
            return
        if aid.lower() in Q.ACHIEVEMENTS:
            caller.msg("|xBuilt-in achievements can't be deleted.|n")
            return
        Q.delete_achievement(aid.lower())
        caller.msg(f"|gAchievement '{aid}' deleted.|n")


ALL_QUEST_CMDS = [CmdQuests, CmdAchievements]
