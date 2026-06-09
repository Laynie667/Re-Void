"""
world/star_chart.py — the Breeding Star-Chart clause's economy.

Stars are earned by the degrading sex work and are the ONLY currency that buys relief
while the chart clause is active (it sets orgasm_denial; you spend stars to be allowed
to come). A literal chart by her file: each act sticks another gold star up, and she
chases stars into worse and worse acts because the ache doesn't stop any other way.

    character.db.star_chart   {"stars": int, "earned": int, "log": [recent kinds]}
    character.db.star_chart_on  bool — the clause is active (gates award + relief)

OOC floor: both flags are in FACILITY_FLAGS → every reset path + force_clear/escape clear them.
"""

# What each act is worth in stars.
STAR_VALUES = {
    "swallow":  1,   # a load taken down the throat
    "bred":     1,   # a hole bred / a deposit taken
    "allholes": 3,   # bred in every hole at once (the seat, the gangs)
    "knot":     1,   # a knot taken to the base
    "milk":     2,   # a milk quota met
    "litter":   5,   # a litter carried to term
}

# Stars to buy one granted climax (the relief).
RELIEF_COST = 4


def _chart(character):
    return dict(getattr(character.db, "star_chart", None) or {"stars": 0, "earned": 0, "log": []})


def award_star(character, kind="bred", n=None, room=None):
    """Stick gold star(s) on her chart for an act. No-ops unless the clause is active.
    Returns the new balance."""
    if not character or not getattr(character.db, "star_chart_on", False):
        return 0
    n = int(n if n is not None else STAR_VALUES.get(kind, 1))
    c = _chart(character)
    c["stars"]  = int(c.get("stars", 0)) + n
    c["earned"] = int(c.get("earned", 0)) + n
    log = list(c.get("log") or [])
    log.append(kind)
    c["log"] = log[-20:]
    character.db.star_chart = c
    cname = character.db.rp_name or character.name
    star = "★" * min(n, 5)
    if room:
        room.msg_contents(f"|W{star} A gold star goes up on {cname}'s chart — {kind}. "
                          f"({c['stars']} saved.)|n")
    character.msg(f"|W  {star} Another gold star, for being such a good girl. You have "
                  f"{c['stars']} now — {RELIEF_COST} buys you off.|n")
    return c["stars"]


def stars_balance(character):
    return int(_chart(character).get("stars", 0))


def spend_stars(character, cost, what="relief"):
    """Spend stars if she has them. Returns True on success."""
    c = _chart(character)
    if int(c.get("stars", 0)) < cost:
        return False
    c["stars"] = int(c["stars"]) - cost
    character.db.star_chart = c
    return True


def star_status(character):
    """Read-out lines for the `stars` command."""
    c = _chart(character)
    stars = int(c.get("stars", 0))
    earned = int(c.get("earned", 0))
    lines = ["|W── YOUR STAR CHART ──|n"]
    lines.append("  " + ("★" * min(stars, 30) or "—") + f"  |w{stars}|n saved "
                 f"|x(of {earned} ever earned)|n")
    if stars >= RELIEF_COST:
        lines.append(f"|g  {RELIEF_COST} stars buys you off — |wstars spend|g to be allowed "
                     f"to come.|n")
    else:
        lines.append(f"|r  {RELIEF_COST - stars} more star(s) before you've earned relief. "
                     f"Better get to work, good girl.|n")
    lines.append("|x  stars are earned the only way that counts here: swallowing, getting "
                 "bred, taking the knot, making your milk, carrying a litter.|n")
    return lines
