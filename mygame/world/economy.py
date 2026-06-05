"""
The Facility's internal economy — *scrip*, the house credit.

Scrip is the only money that means anything inside these walls. It is earned by
feeding the Process — the stock earn it off their own bodies (every millilitre
drawn, every covering taken, every turn on the block), and the members in the
booths earn it by attending — and it is spent inside the house: bids on the
block must be backed by it, and tips to the floor cost it. It buys nothing
outside. Least of all freedom:

    The OOC floor (escape / force_clear / facilityreset / purge) is ALWAYS free
    and NEVER costs, checks, reserves, or is gated by a single credit. You can
    be a thousand scrip in debt and the fire-exit still opens. The economy sits
    entirely on top of the safety floor and never touches it.

State (per character, real db — no parallel store):
  - ``character.db.facility_credits``  : int balance.
  - ``character.db.facility_ledger``   : list of {when, stamp, delta, balance, reason},
                                         newest last, capped at LEDGER_CAP entries.

The cruelty of it, in Bethany's words: I keep an account in your name. It is the
most human thing left about you — a balance, a statement, a number that is yours.
And every credit in it was paid by your own body, and you will never get to spend
one on anything but more of the Process.
"""

import time

# ── Tunables (slow burn; tune live) ──────────────────────────────────────────
LEDGER_CAP     = 50          # keep the last N statement lines
STARTING_GRANT = 5000        # a member's opening float, granted once on first touch
STOCK_START    = 0           # the stock start at nothing — they earn their balance

# What a unit of the Process pays the body it's drawn from, by phase/source.
EARN = {
    "milk":      45,   # a draw on the floor
    "breed":     80,   # a covering taken in the pens
    "condition": 20,   # a session in the cell
    "display":   30,   # a turn on the block
    "show":      30,
    "nurse":     25,
    "deep":      35,
    "mark":      40,
    "punish":    10,   # the sty pays badly
    "cycle":     15,   # any other beat of the line
    "attend":    18,   # a member, watching from the booths
    "tip_yield": 0,    # set per-tip (a cut of the tip credited to the lot)
    "sale_cut":  0,    # set per-sale (a pittance of her own price)
}


# ── Core wallet ───────────────────────────────────────────────────────────────
def _is_stock(char):
    """A processed/active lot starts at nothing; everyone else gets the float."""
    try:
        return bool(getattr(char.db, "facility_active", False)
                    or getattr(char.db, "facility_signed", False))
    except Exception:
        return False


def _ensure(char):
    """Lazily seed a wallet the first time it's touched. Stock open at STOCK_START
    (they earn their balance off their bodies); members get the opening float."""
    if char is None:
        return
    if char.db.facility_credits is None:
        opening = STOCK_START if _is_stock(char) else STARTING_GRANT
        char.db.facility_credits = int(opening)
        char.db.facility_ledger = []
        if opening:
            _record(char, opening, "Opening balance — house float, credited on enrolment.")


def get_balance(char):
    """Current scrip balance (seeds the wallet on first read)."""
    _ensure(char)
    try:
        return int(char.db.facility_credits or 0)
    except Exception:
        return 0


def _record(char, delta, reason):
    """Append a ledger line with a running balance. Caps the log at LEDGER_CAP."""
    try:
        led = list(char.db.facility_ledger or [])
        led.append({
            "when":    time.time(),
            "stamp":   time.strftime("%Y-%m-%d %H:%M"),
            "delta":   int(delta),
            "balance": int(char.db.facility_credits or 0),
            "reason":  str(reason),
        })
        char.db.facility_ledger = led[-LEDGER_CAP:]
    except Exception:
        pass


def add_credits(char, amount, reason="credited"):
    """Credit scrip. Returns the new balance."""
    _ensure(char)
    amount = int(amount)
    if amount == 0:
        return get_balance(char)
    char.db.facility_credits = int(char.db.facility_credits or 0) + amount
    _record(char, amount, reason)
    return int(char.db.facility_credits)


def can_afford(char, amount):
    """Does the wallet cover this? (The OOC floor never calls this — it is free.)"""
    return get_balance(char) >= int(amount)


def spend_credits(char, amount, reason="debited"):
    """Debit scrip if affordable. Returns (ok: bool, balance: int). Never blocks an
    OOC exit — escape/force_clear/purge do not route through here."""
    _ensure(char)
    amount = int(amount)
    if amount <= 0:
        return True, get_balance(char)
    if int(char.db.facility_credits or 0) < amount:
        return False, get_balance(char)
    char.db.facility_credits = int(char.db.facility_credits) - amount
    _record(char, -amount, reason)
    return True, int(char.db.facility_credits)


def earn(char, source, amount=None, reason=None):
    """Credit the body for a unit of the Process. `source` keys EARN, or pass amount."""
    amt = int(amount) if amount is not None else int(EARN.get(source, EARN["cycle"]))
    if amt <= 0:
        return get_balance(char)
    return add_credits(char, amt, reason or _EARN_REASON.get(source, "Yield credited to account."))


# Bethany-voiced statement lines for each earn source — the payslip for her own use.
_EARN_REASON = {
    "milk":      "Yield credited — output drawn and metered on the floor.",
    "breed":     "Service rendered — covering logged, account credited.",
    "condition": "Compliance credited — session completed in the cell.",
    "display":   "Presentation credited — time turned on the block.",
    "show":      "Presentation credited — time turned on the block.",
    "nurse":     "Output credited — nursery duty logged.",
    "deep":      "Deep-stock duty credited — sub-level hours logged.",
    "mark":      "Submission credited — parlour session logged.",
    "punish":    "Reduced credit — sty hours, docked rate.",
    "cycle":     "Activity credited — processing hours logged.",
    "attend":    "Attendance credited — booth time logged, member account.",
}


# ── The statement (humiliation payslip / member account) ──────────────────────
def statement(char, n=12):
    """A formatted scrip statement: balance + the last n ledger lines, Bethany-voiced.
    For stock it reads as the payslip for her own processing; for a member, an account."""
    _ensure(char)
    bal  = get_balance(char)
    led  = list(char.db.facility_ledger or [])[-int(n):]
    stock = _is_stock(char)
    head = (f"|W╔═══ FACILITY ACCOUNT — {char.db.rp_name or char.key} ═══╗|n\n"
            f"  |xBalance:|n |w{bal:,}|n |xscrip|n")
    if stock:
        head += ("\n  |x(Every credit here was paid by your body. It spends on the Process "
                 "and nothing else — never on the door. The door is free.)|n")
    else:
        head += "\n  |x(House credit. Spends on the block and the floor; buys nothing outside.)|n"
    if not led:
        return head + "\n  |xNo movements on file.|n"
    lines = [head, "  |x── statement ──|n"]
    for e in led:
        d = int(e.get("delta", 0))
        sign = "|g+" if d >= 0 else "|r"
        lines.append(f"  {sign}{d:,}|n  |x{e.get('stamp','')}|n  {e.get('reason','')}"
                     f"  |x→ {int(e.get('balance',0)):,}|n")
    return "\n".join(lines)


def clear_wallet(char):
    """Wipe the wallet + ledger. Called by the reset path when she's purged out — the
    account dies with the rest of the facility state. (Not the OOC exit itself; this is
    bookkeeping the reset performs after the floor has already freed her.)"""
    try:
        char.db.facility_credits = None
        char.db.facility_ledger  = None
    except Exception:
        pass
