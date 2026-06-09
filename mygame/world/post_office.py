"""
world/post_office.py — the in-game contract officiating venue (Layer 4).

A player-drafted contract isn't binding until it's OFFICIATED at the post office.
Whoever's on the desk is one of the three tiefling courier-siblings — random, or
sought out by name — and which one officiates changes the deal:

  • Calix    — the clean notary. Charges scrip. Exactly what you wrote binds,
               nothing added, absolute discretion. The safe, honest option.
  • Vesper   — genuinely neutral / undecided, siding with nothing — so they add an
               AMBIGUOUS rider whose meaning is deliberately unsettled. Free.
  • Seraphine— officiates for FREE on one condition: she gets to add a hidden
               clause of her own, written to serve her pleasure (and the facility,
               on the down-low). Decline and she charges scrip like Calix, smiling.

Officiation sets `contract.db.officiated`; a player-drafted contract's `sign()`
refuses until then. The §0 floor is never touched by any of this.
"""

import random

TRIPLETS = ("calix", "vesper", "seraphine")
OFFICIATE_FEE = 200  # scrip, for the paid notaries

# Seraphine's self-serving hidden clauses — her pleasure, her amusement, her line.
_SERAPHINE_CLAUSES = [
    {"hidden": True,
     "text": "(Seraphine's hand, in the margin:) — and the signee will warm to me, "
             "and keep warming, until reaching for me feels like their own idea.",
     "effect": {"kind": "flag", "flag": "cum_craving", "value": True}},
    {"hidden": True,
     "text": "(A crimson flourish:) — the signee remains open to me, whenever it "
             "amuses me to collect.",
     "effect": {"kind": "rule", "name": "ask_to_come", "consequence": "punish"}},
    {"hidden": True,
     "text": "(Tucked between two clean lines:) — the signee will not refuse a "
             "summons that carries my scent.",
     "effect": {"kind": "rule", "name": "no_leave", "consequence": "notify"}},
    {"hidden": True,
     "text": "(Almost too neat to notice:) — what the signee makes of themselves, "
             "they make for me to enjoy first.",
     "effect": {"kind": "grant", "feature": "intimate", "who": "all"}},
]

# Vesper's ambiguous riders — neutral, unsettled, true in more ways than one.
_VESPER_CLAUSES = [
    {"hidden": False,
     "text": "Rider (in a hand that is neither sharp nor soft): the signee shall be "
             "what they are asked to be, as the asking requires.",
     "effect": {"kind": "rule", "name": "honorific", "consequence": "notify",
                "params": {"honorific": "as addressed"}}},
    {"hidden": False,
     "text": "Rider: presence is owed where presence is due, and the due is not "
             "always named in advance.",
     "effect": {"kind": "rule", "name": "present_on_enter", "consequence": "notify"}},
    {"hidden": False,
     "text": "Rider: the signee keeps nothing back that was not, on reflection, "
             "already given.",
     "effect": {"kind": "grant", "feature": "intimate", "who": "faction"}},
]


def _scrip(char):
    try:
        from world.economy import get_balance
        return get_balance(char)
    except Exception:
        return 0


def _charge(char, amount, reason):
    try:
        from world.economy import spend_credits
        return spend_credits(char, amount, reason)
    except Exception:
        return False, 0


def officiate(contract, bringer, who=None, allow_seraphine=False):
    """Officiate a drafted contract. `bringer` is who walks it in (pays any fee).
    `who` forces a specific triplet; otherwise one is assigned at random.
    `allow_seraphine` permits Seraphine her hidden-clause fee. Returns (ok, message)."""
    if getattr(contract.db, "officiated", False):
        return False, "This contract is already officiated."
    who = (who or random.choice(TRIPLETS)).lower()
    if who not in TRIPLETS:
        return False, f"No such clerk. On the desk: {', '.join(TRIPLETS)}."

    if who == "calix":
        ok, bal = _charge(bringer, OFFICIATE_FEE, "Post office — contract officiated (Calix).")
        if not ok:
            return False, (f"Calix names the fee — |w{OFFICIATE_FEE}|n scrip — and waits. "
                           f"You can't cover it (you hold {bal}).")
        msg = ("|wCalix|n reads every line without expression, stamps the page once with "
               "the flat certainty of a man who has notarised worse, and slides it back. "
               "Exactly what you wrote. Nothing more.")

    elif who == "vesper":
        rider = random.choice(_VESPER_CLAUSES)
        contract.add_clause(rider["text"], hidden=rider.get("hidden", False), effect=rider["effect"])
        msg = ("|wVesper|n studies the contract with eyes that change colour twice, says "
               "nothing, and adds a single line in a hand that could be anyone's — a rider "
               "you'll read three times and still not be sure of. Then they stamp it. No charge.")

    else:  # seraphine
        if allow_seraphine:
            clause = random.choice(_SERAPHINE_CLAUSES)
            contract.add_clause(clause["text"], hidden=True, effect=clause["effect"])
            contract.db.reveal_on_sign = True  # she lets you find out — after
            msg = ("|wSeraphine|n smiles like she's been waiting for you to say yes, her tail "
                   "curling once. \"No charge, sweet thing.\" She writes something small and "
                   "crimson where you won't think to look, and presses her seal to it warm. "
                   "\"You'll see what it cost you eventually.\"")
        else:
            ok, bal = _charge(bringer, OFFICIATE_FEE, "Post office — contract officiated (Seraphine).")
            if not ok:
                return False, (f"Seraphine's smile doesn't waver. \"Then it's |w{OFFICIATE_FEE}|n, "
                               f"the boring way.\" You can't cover it (you hold {bal}).")
            msg = ("|wSeraphine|n pouts, charmed, takes the scrip, and stamps it clean — \"so "
                   "dull of you\" — adding nothing. This time.")

    contract.db.officiated = True
    contract.db.officiant  = who
    return True, msg
