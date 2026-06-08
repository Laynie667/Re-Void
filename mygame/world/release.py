"""
world/release.py — Manumission: the IN-FICTION escape from the Facility realm.

This is NOT the OOC safety floor. Read CONSENT_RULES_CONTRACTS_DESIGN.md → "The TWO
escapes". There are two different ways out and they must never be confused:

  • The OOC SAFETY FLOOR — `escape(me)` / `force_clear(me)` / `facilityreset|purge`
    (world/realm_build.py). The real-life fire exit for the human at the keyboard.
    FREE, ungated, instant, never bought, never revocable, NON-NEGOTIABLE (§0).
    Every function in this file reminds the player of it. Nothing here gates it.

  • MANUMISSION (this file) — how the CHARACTER gets free INSIDE the story: a release
    Bethany personally prices, dangles, honors, gouges, or revokes. It is the in-fiction
    door, and it is hers to lock. Built on top of the floor so the dread is real without
    ever cornering a real person. "Available but not abusable" — in fiction.

Mechanically, granting manumission opens the held realm return word via
`realm_build.reveal_return`; revoking it slams that word shut again. The price is paid
in real scrip (world/economy), and conditions read real devotion/standing — the cruel
joke being that the Process pushes devotion UP, so the longer she stays the dearer the
door gets, and Bethany can always just take the scrip and name a bigger number.

Bethany-side controls are called via @py (like build_realm/reveal_return):
    from world.release import offer, gouge, grant, revoke, withdraw, status
    offer(stock, scrip=8000, devotion_max=20, standing_min=40, note="...")
    grant(stock)        # honor it — the door opens
    revoke(stock)       # slam it shut again (optionally regouge=)
The player drives her side with the `release` command (status + petition + pay).
"""

from evennia import search_object

# OOC-floor reminder appended to every player-facing message in this module.
_FLOOR = ("|x(The real way out is not this and never costs anything: "
          "escape / force_clear / facilityreset are always free.)|n")


# ── state ───────────────────────────────────────────────────────────────────
def _default():
    return {
        "offered":      False,   # has Bethany named a price at all?
        "scrip":        0,       # scrip owed for the door
        "devotion_max": None,    # devotion must be AT OR BELOW this (None = ignored)
        "standing_min": None,    # standing must be AT LEAST this (None = ignored)
        "note":         "",      # Bethany's words — the dangle, in her voice
        "set_by":       None,    # dbref of who set the terms
        "paid":         False,   # has she paid the scrip toward it?
        "granted":      False,   # has Bethany honored it (door opened)?
    }


def terms(stock):
    t = dict(getattr(stock.db, "release_terms", None) or {})
    base = _default()
    base.update(t)
    return base


def _save(stock, t):
    stock.db.release_terms = t


# ── condition checks (read REAL state) ────────────────────────────────────────
def _devotion(stock):
    return int(getattr(stock.db, "bethany_devotion", 0) or 0)


def _standing(stock):
    try:
        from world.factions import get_standing
        return int(get_standing(stock))
    except Exception:
        return int(getattr(stock.db, "facility_standing", 0) or 0)


def _balance(stock):
    try:
        from world.economy import get_balance
        return int(get_balance(stock))
    except Exception:
        return 0


def _unmet(stock, t):
    """List of (label, detail) conditions not yet satisfied (scrip excluded)."""
    out = []
    dmax = t.get("devotion_max")
    if dmax is not None and _devotion(stock) > dmax:
        out.append(("devotion", f"yours is {_devotion(stock)}; she won't sign you out above {dmax} "
                                f"— you have to want it less than you do"))
    smin = t.get("standing_min")
    if smin is not None and _standing(stock) < smin:
        out.append(("standing", f"yours is {_standing(stock)}; she won't process a release under {smin}"))
    return out


# ── Bethany's side ────────────────────────────────────────────────────────────
def offer(stock, scrip=0, devotion_max=None, standing_min=None, note="", by=None):
    """Bethany names (or re-names) the price of the door. Call again to change it."""
    t = terms(stock)
    t.update({
        "offered": True,
        "scrip": int(scrip or 0),
        "devotion_max": devotion_max,
        "standing_min": standing_min,
        "note": note or t.get("note", ""),
        "set_by": by.dbref if by else t.get("set_by"),
        "granted": False,
    })
    _save(stock, t)
    msg = ["|MShe slides a single sheet across the desk and taps it with one manicured nail.|n",
           f"|MManumission. A real release, on paper, out of the Process and home for good — "
           f"priced and itemised in your own hand.|n",
           f"  |xthe door:|n |w{t['scrip']:,}|n scrip"]
    if devotion_max is not None:
        msg.append(f"  |xand:|n you have to want her less — devotion at or under |w{devotion_max}|n")
    if standing_min is not None:
        msg.append(f"  |xand:|n standing at or over |w{standing_min}|n — she won't sign out a liability")
    if note:
        msg.append(f"|M\"{note}\"|n")
    msg.append("|M\"Whenever you like, sweetheart. The number's only going one way, though.\"|n")
    msg.append(_FLOOR)
    stock.msg("\n".join(msg))


def gouge(stock, add_scrip=0, devotion_max=None, standing_min=None, note=""):
    """Raise the price — the dangle made cruel. Adds to scrip, tightens conditions."""
    t = terms(stock)
    if not t["offered"]:
        return offer(stock, scrip=add_scrip, devotion_max=devotion_max,
                     standing_min=standing_min, note=note)
    t["scrip"] = int(t["scrip"]) + int(add_scrip or 0)
    if devotion_max is not None:
        t["devotion_max"] = devotion_max
    if standing_min is not None:
        t["standing_min"] = standing_min
    if note:
        t["note"] = note
    t["paid"] = False
    _save(stock, t)
    stock.msg("|MShe crosses out the figure without looking up and writes a larger one above it.|n\n"
              f"|Mthe door, today:|n |w{t['scrip']:,}|n scrip.\n"
              + (f"|M\"{note}\"|n\n" if note else "")
              + "|M\"It went up. Things do, in here. You took your time.\"|n\n" + _FLOOR)


def grant(stock, by=None, force=False):
    """Bethany honors the release — the in-fiction door opens (reveal_return)."""
    t = terms(stock)
    if not t["offered"] and not force:
        stock.msg("|xThere is no release on the table to honor.|n")
        return False
    if not t["paid"] and not force:
        stock.msg("|MShe smiles and does not pick up the pen. \"Pay it first, sweetheart.\"|n")
        return False
    t["granted"] = True
    _save(stock, t)
    try:
        from world.realm_build import reveal_return
        reveal_return(stock)
    except Exception:
        pass
    stock.msg("|MShe signs it. Both copies. Slides yours back and folds her hands.|n\n"
              "|M\"There. You're free — properly, on paper, mine no more. The word home works now; "
              "speak it at a stone whenever you're ready to go.\"|n\n"
              "|M\"...You can always stay, of course. Most do, once it's actually a choice.\"|n\n"
              + _FLOOR)
    return True


def revoke(stock, by=None, regouge=0):
    """Bethany withholds/cancels a granted release — slam the in-fiction door shut.
    Pulls the realm return word back to None so it stops working. Optionally re-prices."""
    t = terms(stock)
    # re-hide the held return word
    try:
        realm = stock.db.realm or {}
        ref = realm.get("return_wp")
        if ref:
            res = search_object(ref)
            if res:
                res[0].db.realm_address = None
        realm["active"] = False
        stock.db.realm = realm
    except Exception:
        pass
    t["granted"] = False
    t["paid"] = False
    if regouge:
        t["scrip"] = int(t["scrip"]) + int(regouge)
    _save(stock, t)
    stock.msg("|MShe takes your copy back across the desk, almost gently, and feeds it to the shredder "
              "beside her knee.|n\n"
              "|M\"Mm. No. I've reconsidered. The word stops working as of now — try it and see.\"|n\n"
              + (f"|MAnd the price for trying again is |w{t['scrip']:,}|M now.|n\n" if regouge else "")
              + "|M\"Don't look at me like that. You signed knowing I could.\"|n\n" + _FLOOR)


def withdraw(stock, by=None):
    """Bethany pulls the offer entirely — no door on the table at all."""
    t = _default()
    _save(stock, t)
    stock.msg("|MShe tucks the sheet back into your file and closes it.|n\n"
              "|M\"Let's not talk about leaving today. You're not ready, and frankly neither am I.\"|n\n"
              + _FLOOR)


# ── the unit's side (the `release` command calls these) ───────────────────────
def status(stock):
    """Formatted status for the player. Always shows the OOC floor."""
    t = terms(stock)
    lines = ["|M" + "═" * 46 + "|n", "|MMANUMISSION — the way out, on her terms|n",
             "|M" + "═" * 46 + "|n"]
    if not t["offered"]:
        lines.append("|xThere is no release on the table. The door home is hers to price, and she "
                     "hasn't named a number. You could ask. She likes being asked.|n")
        lines.append(_FLOOR)
        lines.append("|M" + "═" * 46 + "|n")
        return "\n".join(lines)
    bal = _balance(stock)
    owe = int(t["scrip"])
    paid = t["paid"]
    lines.append(f"  |xher price:|n |w{owe:,}|n scrip" + ("  |g— paid|n" if paid else
                 f"  |x(you hold {bal:,})|n"))
    for label, detail in _unmet(stock, t):
        lines.append(f"  |R✗ {label}:|n {detail}")
    if t["devotion_max"] is not None and _devotion(stock) <= t["devotion_max"]:
        lines.append(f"  |g✓ devotion:|n {_devotion(stock)} (under {t['devotion_max']})")
    if t["standing_min"] is not None and _standing(stock) >= t["standing_min"]:
        lines.append(f"  |g✓ standing:|n {_standing(stock)} (over {t['standing_min']})")
    if t["note"]:
        lines.append(f"|M\"{t['note']}\"|n")
    if t["granted"]:
        lines.append("|gShe has signed it. The word home works — speak it at a waystone to surface.|n")
    elif paid:
        lines.append("|MPaid. Now it waits on her pen — and her pen waits on her mood.|n")
    else:
        ready = (bal >= owe) and not _unmet(stock, t)
        lines.append("|MReady to pay — |wrelease pay|M when you can stand to.|n" if ready
                     else "|xNot yet within reach. Earn it, or want her less.|n")
    lines.append(_FLOOR)
    lines.append("|M" + "═" * 46 + "|n")
    return "\n".join(lines)


def petition(stock):
    """She asks for a price to be named. Pings the dangle; Bethany sets it via @py."""
    t = terms(stock)
    if t["offered"]:
        stock.msg(status(stock))
        return
    stock.msg("|MYou ask, in so many words, what it would take to leave.|n\n"
              "|MShe doesn't laugh — that's the worst of it. She just turns to a fresh page, "
              "uncaps her pen, and starts adding. \"Let me see what you're worth to me first.\"|n\n"
              "|x(Bethany will name your price.)|n\n" + _FLOOR)


def pay(stock):
    """The unit pays the named price toward the door. Conditions must be met. Spends real scrip.
    Paying does NOT open the door — only Bethany's grant() does. That wait is the point."""
    t = terms(stock)
    if not t["offered"]:
        stock.msg("|xThere is no price on the table to pay. Ask her first — |wrelease ask|x.|n")
        return
    if t["granted"]:
        stock.msg("|gIt's already signed. The way home is open — go, if you're going.|n\n" + _FLOOR)
        return
    if t["paid"]:
        stock.msg("|MAlready paid. It waits on her pen now, not your purse.|n\n" + _FLOOR)
        return
    unmet = _unmet(stock, t)
    if unmet:
        stock.msg("|RShe won't even take the scrip until the rest is true:|n\n"
                  + "\n".join(f"  |R✗ {lbl}:|n {d}" for lbl, d in unmet) + "\n" + _FLOOR)
        return
    owe = int(t["scrip"])
    try:
        from world.economy import spend_credits
        ok, bal = spend_credits(stock, owe, "Manumission — paid toward release.")
    except Exception:
        ok, bal = False, 0
    if not ok:
        stock.msg(f"|xYou can't cover it. The door is |w{owe:,}|x and you hold |w{bal:,}|x.|n\n"
                  "|xEarn the rest off your own body like everything else in here.|n\n" + _FLOOR)
        return
    t["paid"] = True
    _save(stock, t)
    stock.msg(f"|MYou pay it — every credit, scraped out of what your own body earned on the line.|n\n"
              f"|MShe counts it without hurry, sets it aside, and says nothing about signing.|n\n"
              "|M\"Good girl. I'll have a look at the paperwork. These things take time.\"|n\n"
              "|x(It now waits on Bethany's grant. She is under no obligation, in fiction. "
              "OOC, you never are: the floor is always free.)|n\n" + _FLOOR)
