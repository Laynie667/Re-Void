"""
world/contract_clauses.py — Layer 4: clauses that GRANT consent and IMPOSE rules.

A clause on a MilkingContract may now carry a machine-readable `effect` dict. On
signing, `MilkingContract.sign()` calls `apply_clause_effect(signee, author, effect)`
for each clause — signing IS consent (fully informed or not), routed through the
REAL systems built in Layers 1-3:

  effect kinds:
    grant    — write a consent allow-override on the signee
               {"kind":"grant", "feature":"bdsm", "who":"owner"|"author"|<id>|<tier>}
    rule     — impose a Layer-3 rule on the signee
               {"kind":"rule", "name":"no_leave", "consequence":..., "params":{...},
                "condition":{...}}
    relation — force a relationship role (author → signee, e.g. author is your mother)
               {"kind":"relation", "role":"mother"}
    flag     — set a db flag on the signee
               {"kind":"flag", "flag":"perpetual_heat", "value":true}
    binding  — a binding_effects payload (merged into the contract's existing payload
               at build time; the established apply_effects path handles it)
               {"kind":"binding", "payload":{...}}

EVERY applied grant is recorded to `signee.db.contract_effects` so the §0 floor
can undo precisely what a contract added (without nuking unrelated player consent).
`revert_all` is wired into `force_clear`. Rules, forced relations, flags and binding
effects are already cleared by the existing reset paths. Nothing here gates the floor.
"""


def _record(signee, entry):
    log = list(getattr(signee.db, "contract_effects", None) or [])
    log.append(entry)
    signee.db.contract_effects = log


def _resolve_who(author, who):
    """A grant's beneficiary: a tier string stays a string; 'author'/'owner-of-record'
    resolves to the author's id; an int id stays an id."""
    if who in ("author", "<author>", "signer", "holder"):
        return getattr(author, "id", None)
    return who  # tier string (owner/lover/family/faction/hostile) or an int id


def apply_clause_effect(signee, author, effect):
    """Apply one clause's machine-readable effect to the signee. Defensive — a single
    bad clause never aborts the rest. Returns (ok, note)."""
    if not isinstance(effect, dict):
        return False, "no effect"
    kind = effect.get("kind")
    try:
        if kind == "grant":
            feature = effect["feature"]
            key = _resolve_who(author, effect.get("who", "author"))
            ov = dict(getattr(signee.db, "consent_overrides", None) or {})
            ov.setdefault("allow", {})
            ov.setdefault("block", {})
            ov["allow"].setdefault(feature, set()).add(key)
            ov["block"].get(feature, set()).discard(key)
            signee.db.consent_overrides = ov
            _record(signee, {"kind": "grant", "feature": feature, "key": key})
            return True, f"granted {feature} to {key}"

        if kind == "rule":
            from world.rules import add_rule
            rule, err = add_rule(signee, effect["name"], author,
                                 condition=effect.get("condition"),
                                 consequence=effect.get("consequence"),
                                 params=effect.get("params"))
            return (False, err) if err else (True, f"rule {effect['name']}")

        if kind == "relation":
            from world import relationships as rel
            # Signing IS the consent, so we apply the tie directly (no owner gate).
            rel._apply(author, signee, role=effect.get("role"),
                       lover=bool(effect.get("lover")), forced=True)
            return True, f"relation {effect.get('role') or ('lover' if effect.get('lover') else '?')}"

        if kind == "flag":
            setattr(signee.db, effect["flag"], effect.get("value", True))
            _record(signee, {"kind": "flag", "flag": effect["flag"]})
            return True, f"flag {effect['flag']}"

        if kind == "own":
            # Ownership is applied for the author (and co-authors) by the contract's
            # sign() via apply_ownership; nothing per-clause here.
            return True, "ownership (applied at sign)"

        if kind == "binding":
            # binding payloads are merged into the contract at build time (see
            # merge_binding); nothing to do per-clause at sign.
            return True, "binding (merged at build)"
    except Exception as e:
        return False, f"{kind} failed: {e}"
    return False, f"unknown kind {kind}"


def merge_binding(contract, payload):
    """Fold a binding_effects payload into the contract's existing one (build time)."""
    cur = dict(getattr(contract.db, "binding_effects", None) or {})
    cur.update(payload or {})
    contract.db.binding_effects = cur


def apply_ownership(signee, owners):
    """Make each of `owners` an owner of the signee (multi-owner safe). Records each
    so the §0 floor can drop it precisely. `owners` is a list of character objects."""
    from world.relationships import set_owner
    for o in owners:
        if not o:
            continue
        set_owner(o, signee, forced=True)
        _record(signee, {"kind": "own", "owner": getattr(o, "id", None)})


def revert_all(signee):
    """OOC-floor hook: undo every consent GRANT and OWNER link a contract wrote on the
    signee (rules, forced family relations, flags and binding effects are cleared by the
    other reset paths). Returns count reverted."""
    from evennia import search_object
    from world.relationships import drop_owner
    effects = list(getattr(signee.db, "contract_effects", None) or [])
    n = 0
    ov = dict(getattr(signee.db, "consent_overrides", None) or {})
    for e in effects:
        if e.get("kind") == "grant":
            try:
                ov.get("allow", {}).get(e["feature"], set()).discard(e["key"])
                n += 1
            except Exception:
                pass
        elif e.get("kind") == "own":
            try:
                res = search_object(f"#{e['owner']}")
                if res:
                    drop_owner(res[0], signee)
                    n += 1
            except Exception:
                pass
    signee.db.consent_overrides = ov
    signee.db.contract_effects = None
    return n


# ── clause template registry (the approved-kink catalogue lands here) ─────────
# name -> {"text": visible/hidden clause text, "effect": {...}, "hidden": bool}
# Seeded with a few obviously-fine primitives as worked examples; the full catalogue
# (soft → extreme) gets added here entry-by-entry as the user approves each.
TEMPLATES = {
    # ── player ↔ player: light D/s & service ──────────────────────────────────
    "obedience": {
        "hidden": False,
        "text": "The signee agrees to obey the holder in all reasonable instruction.",
        "effect": {"kind": "grant", "feature": "lead_follow", "who": "author"},
    },
    "honorific": {
        "hidden": False,
        "text": "The signee will address the holder by their proper honorific.",
        "effect": {"kind": "rule", "name": "honorific", "consequence": "notify",
                   "params": {"honorific": "Mistress"}},
    },
    "kneel_on_enter": {
        "hidden": False,
        "text": "The signee will present and kneel whenever the holder is present.",
        "effect": {"kind": "rule", "name": "kneel_on_enter", "consequence": "notify"},
    },
    "kept_close": {
        "hidden": False,
        "text": "The signee will not leave the holder's presence without permission.",
        "effect": {"kind": "rule", "name": "no_leave", "consequence": "block",
                   "condition": {"type": "owner_present"}},
    },
    # ── intimacy & use grants ─────────────────────────────────────────────────
    "open_to_touch": {
        "hidden": False,
        "text": "The signee consents to intimate contact from the holder.",
        "effect": {"kind": "grant", "feature": "intimate", "who": "author"},
    },
    "open_to_mature": {
        "hidden": False,
        "text": "The signee consents to mature contact from the holder.",
        "effect": {"kind": "grant", "feature": "mature", "who": "author"},
    },
    "open_to_bdsm": {
        "hidden": False,
        "text": "The signee submits to the holder's BDSM use.",
        "effect": {"kind": "grant", "feature": "bdsm", "who": "author"},
    },
    "open_to_restraint": {
        "hidden": False,
        "text": "The signee consents to be restrained by the holder.",
        "effect": {"kind": "grant", "feature": "restraint", "who": "author"},
    },
    "free_use": {
        "hidden": False,
        "text": "The signee is free use to anyone sharing the holder's faction.",
        "effect": {"kind": "grant", "feature": "mature", "who": "faction"},
    },
    # ── bonds & ownership ─────────────────────────────────────────────────────
    "collar": {
        "hidden": False,
        "text": "The signee accepts the holder's collar and the holder as their owner.",
        "effect": {"kind": "own"},
    },
    "lovers": {
        "hidden": False,
        "text": "The parties bind themselves to one another as lovers.",
        "effect": {"kind": "relation", "role": None, "lover": True},
    },
    # ── control & training ────────────────────────────────────────────────────
    "training": {
        "hidden": False,
        "text": "The signee submits to the holder's conditioning.",
        "effect": {"kind": "grant", "feature": "condition", "who": "author"},
    },
    "chastity": {
        "hidden": False,
        "text": "The signee may not climax without the holder's leave.",
        "effect": {"kind": "rule", "name": "ask_to_come", "consequence": "punish"},
    },
    "exposed": {
        "hidden": False,
        "text": "The signee will remain unclothed in the holder's presence.",
        "effect": {"kind": "rule", "name": "no_clothing", "consequence": "notify",
                   "condition": {"type": "owner_present"}},
    },
    "curfew": {
        "hidden": False,
        "text": "The signee will be where they are kept during curfew hours.",
        "effect": {"kind": "rule", "name": "curfew", "consequence": "notify",
                   "params": {"hours": (22, 6)}},
    },
}


def template(name):
    return TEMPLATES.get(name)


def template_names():
    return sorted(TEMPLATES)
