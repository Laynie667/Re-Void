"""
world/compliance.py

Non-compliance tracking and the freedom-forfeit clause.

Defiance (e.g. reaching for the locked exit, refusing the schedule) accrues.
Once it passes the threshold a signed contract set, freedom is "forfeited":
the convenient way out locks hard and the conditioning sets permanently.

SAFETY: this only ever tightens the *convenient* exit. The genuine OOC floor —
facilityreset/force, facilityreset/purge, and the @py purge one-liner — is
never affected and always frees the character. Forfeiting freedom in-fiction
does not forfeit the real safeword.
"""

import time
import random


def register_defiance(character, amount=1, reason=""):
    """Log an act of non-compliance: punish it now, count it toward forfeiture."""
    if not character:
        return

    # Docility (set by the mind-state monitor from conditioning/suggestibility/
    # dependence) can swallow the resistance outright — the deeper she's processed,
    # the harder it is to make herself defy at all, and trying only settles her more.
    import random as _r
    doc = float(getattr(character.db, "docility", 0) or 0)
    if doc > 0 and _r.random() < min(doc, 90.0) / 100.0:
        character.db.compliance_streak = 0
        try:
            from world.conditioning import add_conditioning
            add_conditioning(character, 1.0, source="failed-defiance")
        except Exception:
            pass
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(character); add_arousal(character, 6.0)
        except Exception:
            pass
        character.msg(
            "|xYou mean to refuse — and your body doesn't. The impulse arrives and goes "
            "nowhere, smoothed flat before it reaches your hands, and the not-resisting feels, "
            "horribly, like relief. They've made defiance too much work.|n")
        return

    cur = int(getattr(character.db, "defiance", 0) or 0) + int(amount)
    character.db.defiance = cur
    character.db.compliance_streak = 0   # a slip breaks any earn-back streak

    # Every rule-break is punished immediately, clause or no clause.
    punish(character, reason=reason or "rule broken", severity=1)

    threshold = int(getattr(character.db, "compliance_threshold", 0) or 0)
    if not threshold or getattr(character.db, "freedom_forfeited", False):
        return
    if cur >= threshold:
        forfeit_freedom(character)
    else:
        character.msg(
            f"|R[non-compliance logged — {cur}/{threshold}. "
            f"the contract has a line for reaching the limit.]|n"
        )


def punish(character, reason="", severity=1):
    """Apply an immediate punishment — overstim, deeper denial, a heavier
    schedule, and sometimes a raised quota or a longer lock."""
    if not character:
        return
    room  = character.location
    cname = character.db.rp_name or character.name

    # Overstimulate and push release further away.
    try:
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(character)
        add_arousal(character, 22.0 * severity)
    except Exception:
        pass
    character.db.orgasm_denial = True
    character.db.arousal_floor = max(float(getattr(character.db, "arousal_floor", 0) or 0), 40.0)

    # Drive conditioning.
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, 6.0 * severity, source="punishment")
    except Exception:
        pass

    # Sometimes raise a breeding quota as the penalty.
    extra = ""
    quota = getattr(character.db, "breeding_quota", None)
    if quota and random.random() < 0.5:
        sp = random.choice(list(quota.keys()))
        e  = dict(quota[sp]); e["required"] = int(e.get("required", 0)) + random.randint(2, 6)
        quota[sp] = e
        character.db.breeding_quota = quota
        extra = f" The {sp} quota is raised, for the trouble."

    # If a convenient-exit lock is running, extend it.
    locked = float(getattr(character.db, "facility_reset_locked_until", 0) or 0)
    if locked and locked > time.time():
        character.db.facility_reset_locked_until = locked + 6 * 3600.0
        extra += " The clock you can't see gets longer."

    rb = f" ({reason})" if reason else ""
    character.msg(
        f"|RPunishment{rb}: the stimulation slams up, release is dragged further out "
        f"of reach, and the schedule turns heavier on you.{extra}|n"
    )
    if room:
        room.msg_contents(
            f"|R{cname} is punished — overstimmed, denied, logged. The machine doesn't "
            f"raise its voice. It just turns everything up and waits.|n",
            exclude=[character],
        )


# ── make_example: the reusable "public lesson" primitive ──────────────────────
# A graded, whole-room punishment spectacle the rest of the systems can call with one
# line (quests, resolvers, curses, quota review). severity 1 (light) .. 3 (extreme).
# Never touches the OOC floor.
_EXAMPLE_LIGHT = [
    "The floor is made to pause and watch while {t} is corrected — nothing dramatic, just a "
    "quiet, public adjustment, the kind that says this is routine, this is what you are, and "
    "everyone goes back to work having seen it.",
    "A handler taps the board and reads {t}'s shortfall aloud to the room — flat, bored, "
    "itemised — so the lesson isn't pain so much as being *itemised in front of everyone*, a "
    "line of stock that didn't make its number.",
    "{t} is stood up, turned once for the room to see, and sat back down — a small public "
    "marking, more bookkeeping than cruelty, and somehow the smallness of it is the sting.",
]
_EXAMPLE_HARD = [
    "The whole room is turned out to watch {t} taught the lesson properly — held, used as "
    "demonstration, narrated to the others as it happens so they learn the price on someone "
    "else's body. The point was never private. The point was the audience.",
    "{t} is made the example: put on display mid-correction while a handler explains, evenly, "
    "to the assembled stock exactly what this is and why, and what it costs to earn it. By the "
    "end {t} is reciting it back, because that's the part that sticks.",
    "They don't hide it. {t} is dragged to the centre of the floor and processed where everyone "
    "can see, the overhead lights brought up like a stage, the lesson landed slow and legible so "
    "no one in the room mistakes what happens to stock that steps wrong.",
]
_EXAMPLE_EXTREME = [
    "The whole house is turned out for it. {t} is made the example in front of all of it — the "
    "floor, the gallery, the buyers — broken slow and public and thorough, every stage announced, "
    "the price of whatever {t} did paid in full where not one unit can look away. They will talk "
    "about this one. That is the entire point.",
    "It is total and it is theatre. {t} is hauled up under the lights and made into the warning "
    "the whole facility gets to keep — used, marked, narrated, the lesson driven past comfort and "
    "past dignity and out the other side into something the room will flinch at remembering. The "
    "house does not raise its voice. It just makes sure everyone watches the cost.",
    "{t} becomes the lesson the house writes on a body so it doesn't have to repeat it: dragged "
    "to the centre, stripped of every comfort and every name, processed past the point of protest "
    "in front of the assembled stock — and when it's done the room understands, exactly, what the "
    "facility will spend to be obeyed.",
]


def make_example(character, severity=2, reason="", broadcast=True):
    """A public lesson — the facility turning the whole room out to watch the price of
    something. The reusable punishment primitive: a graded broadcast, the punishment
    itself, a conditioning spike, a standing setback, and a logged non-compliance count.
    severity 1 (light) .. 3 (extreme). Pass broadcast=False if the caller already narrated
    its own scene (then only the mechanical effect applies). Returns the broadcast line.
    Never touches the OOC floor — `escape`/`force_clear`/`facilityreset` always free."""
    if not character:
        return ""
    severity = max(1, min(3, int(severity)))
    room = character.location
    t = character.db.rp_name or character.name
    pool = {1: _EXAMPLE_LIGHT, 2: _EXAMPLE_HARD, 3: _EXAMPLE_EXTREME}[severity]
    line = random.choice(pool).format(t=t)
    if broadcast and room:
        room.msg_contents("|R" + line + "|n")
    # The lesson lands on the body (overstim/denial/heavier schedule, scaled).
    punish(character, reason=reason or "made an example", severity=severity)
    # And drives conditioning harder than a plain punishment — public lessons stick.
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, 8.0 * severity, source="punishment")
    except Exception:
        pass
    # And on the file — standing drops; the house remembers what it had to spend.
    try:
        from world.factions import add_standing
        add_standing(character, amount=-3.0 * severity)
    except Exception:
        pass
    # It also logs as non-compliance toward any forfeiture clause (without re-punishing —
    # punish() already fired above).
    character.db.defiance = int(getattr(character.db, "defiance", 0) or 0) + severity
    character.db.compliance_streak = 0
    return line


def quota_status(character):
    """Readable lines of what she owes before rest — breeding, milk, and arrears.
    Shape-tolerant: breeding_quota may be {sp:int} or {sp:{current,required}}; milk_quota
    is {current,required}. Returns (lines, all_met)."""
    lines = []
    all_met = True
    bq = getattr(character.db, "breeding_quota", None)
    if isinstance(bq, dict) and bq:
        counts = dict(getattr(character.db, "offspring_counts", None) or {})
        for sp, v in bq.items():
            if isinstance(v, dict):
                cur, req = int(v.get("current", 0)), int(v.get("required", 0))
            else:
                req, cur = int(v), int(counts.get(sp, 0))
            met = cur >= req
            all_met = all_met and met
            lines.append(f"  |xbreeding · {sp}:|n {cur}/{req} " + ("|g✓|n" if met else "|r…|n"))
    mq = getattr(character.db, "milk_quota", None)
    if isinstance(mq, dict) and mq:
        cur, req = int(mq.get("current", 0)), int(mq.get("required", 0))
        met = cur >= req
        all_met = all_met and met
        lines.append(f"  |xmilk:|n {cur}/{req} ml " + ("|g✓|n" if met else "|r…|n"))
    try:
        from world.economy import debt_amount
        owed = debt_amount(character)
        if owed:
            all_met = False
            lines.append(f"  |xarrears:|n |r{owed:,}|n scrip owed on the marker")
    except Exception:
        pass
    return lines, all_met


def penalize_quota_shortfall(character):
    """Periodic review: if quotas aren't met, apply a penalty."""
    try:
        from world.gang_breeding import quota_met
    except Exception:
        return False
    breeding_done = quota_met(character)
    mq = getattr(character.db, "milk_quota", None)
    milk_done = (not mq) or int(mq.get("current", 0)) >= int(mq.get("required", 0))
    if breeding_done and milk_done:
        return False

    # Quota interest — every unmet quota compounds while you're behind.
    quota = getattr(character.db, "breeding_quota", None)
    if quota:
        for sp, v in list(quota.items()):
            cur = int(v.get("current", 0)); req = int(v.get("required", 0))
            if cur < req:
                e = dict(v); e["required"] = req + max(1, int(req * 0.08))
                quota[sp] = e
        character.db.breeding_quota = quota
    if mq:
        cur = int(mq.get("current", 0)); req = int(mq.get("required", 0))
        if cur < req:
            e = dict(mq); e["required"] = req + max(1, int(req * 0.08))
            character.db.milk_quota = e

    character.msg(
        "|R[quota review: behind. the facility does not accept 'behind' — so the "
        "targets accrue interest, and behind gets further away.]|n"
    )
    punish(character, reason="behind on quota", severity=1)
    return True


EARN_BACK_STREAK = 12   # compliant acts in a row (no slips) toward earning freedom back


def register_compliance(character, reward=True):
    """A compliant act: ease defiance, build the streak, sometimes reward — and
    check whether forfeited freedom has been earned back."""
    if not character:
        return
    cur = int(getattr(character.db, "defiance", 0) or 0)
    if cur > 0:
        character.db.defiance = cur - 1
    streak = int(getattr(character.db, "compliance_streak", 0) or 0) + 1
    character.db.compliance_streak = streak

    # Good-girl reward loop: compliance occasionally buys a brief, granted
    # climax — which deepens conditioning. The relief is the leash.
    if reward and random.random() < 0.3:
        _grant_climax(character)

    check_earn_back(character)


def _grant_climax(character):
    """Lift denial for one real release — and rewire a little for the privilege."""
    # Actually permit the climax — orgasm_denial otherwise caps her at 99.
    character.db.orgasm_denial_lifted = True
    try:
        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
        ensure_arousal_script(character)
        add_arousal(character, 80.0)
    except Exception:
        pass
    try:
        from world.conditioning import deepen_on_climax
        deepen_on_climax(character, 6.0)
    except Exception:
        pass
    character.msg(
        "|MGood girl. Permission — just this once.|n |xThe denial lifts exactly long "
        "enough to let you fall, hard and grateful, and a little deeper than before. "
        "The ease is the leash, and you take it every time.|n"
    )


def check_earn_back(character):
    """If freedom was forfeited, restore it only when every quota is met AND a
    long compliance streak is held with no slips. The hard in-fiction way out."""
    if not getattr(character.db, "freedom_forfeited", False):
        return False
    try:
        from world.gang_breeding import quota_met
    except Exception:
        return False
    mq = getattr(character.db, "milk_quota", None)
    milk_ok = (not mq) or int(mq.get("current", 0)) >= int(mq.get("required", 0))
    streak  = int(getattr(character.db, "compliance_streak", 0) or 0)
    if quota_met(character) and milk_ok and streak >= EARN_BACK_STREAK:
        character.db.freedom_forfeited = False
        character.db.facility_reset_locked_until = 0.0
        character.msg(
            "|gEvery quota met. Every test passed. Not one slip in a long, long "
            "stretch. The board flips back: FREEDOM — RESTORED. The way out will "
            "open to your hand again. Whether you still want it is your own problem "
            "now, and you're not sure of the answer.|n"
        )
        return True
    return False


def forfeit_freedom(character):
    """Invoke the forfeit-freedom clause. In-fiction only — OOC floor remains."""
    character.db.freedom_forfeited     = True
    character.db.conditioning_permanent = True
    # Lock the convenient reset effectively forever (force/purge/@py bypass it).
    character.db.facility_reset_locked_until = time.time() + 3650 * 86400.0
    try:
        from world.conditioning import add_conditioning
        add_conditioning(character, 40.0, source="forfeit")
    except Exception:
        pass
    character.msg(
        "|RClause invoked. You didn't comply, and the contract had a line ready for "
        "exactly that.|n\n"
        "|xYour freedom is logged as forfeited. The easy way out won't open for you "
        "anymore — not by your hand, not by asking nicely. You agreed to this on a "
        "page you weren't allowed to read, and it is binding now.|n"
    )
    room = character.location
    if room:
        cname = character.db.rp_name or character.name
        room.msg_contents(
            f"|RA line on the board flips red against {cname}: FREEDOM — FORFEITED. "
            f"The staff don't react. It was always one of the outcomes on the form.|n",
            exclude=[character],
        )
