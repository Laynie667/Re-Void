"""
world/relationships.py — the relationship layer (Layer 1 of the authority stack).

See world/CONSENT_RULES_CONTRACTS_DESIGN.md. This is the single spine the consent
matrix, the rules engine, and contract clauses all query via:

    tiers_of(viewer, target) -> set[str]

A viewer holds one or more TIERS toward a target:
    self / owner / lover / family / faction / hostile / all
resolved from three sources:
  - factions.py        — `faction` (shares a faction), `hostile` (factions at enmity)
  - facility ownership — `owner`
  - explicit links     — `lover` (bool) + a granular `family` role, stored per-character

Explicit links live on the character:
    db.relationships      = {other_id: {"family": <role|None>, "lover": bool,
                                         "set_by": id, "forced": bool}}
    db.relationship_offers = {from_id: {"family": <role|None>, "lover": bool}}  # pending

Semantics: `relationships[X][Y]["family"] == role` means "X is Y's <role>"
(e.g. mother). The reciprocal — what Y is to X — is auto-stored on Y, gendered by
Y's pronouns (mother → daughter/son/child). Family is role-granular for incest /
lineage play (core to Bethany); lover + family may coexist. The OOC floor
(force_clear) undoes FORCED ties; mutual player-set ties are left untouched.
"""

import time

# ── role catalogue (core set; extended kin deferred per design) ───────────────
PARENT_ROLES  = {"mother", "father", "sire", "dam", "parent"}
CHILD_ROLES   = {"daughter", "son", "get", "offspring", "child"}
SIBLING_ROLES = {"sister", "brother", "sibling"}
FAMILY_ROLES  = PARENT_ROLES | CHILD_ROLES | SIBLING_ROLES

_CLASS = {}
for _r in PARENT_ROLES:  _CLASS[_r] = "parent"
for _r in CHILD_ROLES:   _CLASS[_r] = "child"
for _r in SIBLING_ROLES: _CLASS[_r] = "sibling"
_RECIP_CLASS = {"parent": "child", "child": "parent", "sibling": "sibling"}

# ── ownership bonds (character-social.md §2): player-over-player ownership as the
# default, the same `owner` tier NPCs use. The offered spec maps to a stored flavour
# that seeds the default honorific/title; all of them mean "viewer becomes target's
# owner".
OWNER_FLAVORS = {"own": "owned", "owner": "owned", "owned": "owned",
                 "slave": "slave", "pet": "pet"}


# ── temp/perm bonds: an entry may carry `expires_at` (epoch seconds). Absent or
# None = permanent (the default). An expired entry resolves to no bond and is pruned
# lazily. When expires_at is absent, every path below behaves exactly as before. ──
def _now():
    return time.time()


def _entry_active(entry):
    """True if a relationship entry is live (no expiry, or not yet expired)."""
    exp = entry.get("expires_at") if entry else None
    return exp is None or float(exp) > _now()


# ── small helpers ─────────────────────────────────────────────────────────────
def _id(obj):
    return getattr(obj, "id", None)


def _obj(oid):
    from evennia import search_object
    res = search_object(f"#{oid}")
    return res[0] if res else None


def _rels(char):
    return dict(getattr(char.db, "relationships", None) or {})


def _offers(char):
    return dict(getattr(char.db, "relationship_offers", None) or {})


def _subj(char):
    return ((getattr(char.db, "pronouns", None) or {}).get("subject", "they") or "they").lower()


def _gendered(cls, char):
    """A role string of the given class, gendered by char's pronoun subject."""
    s = _subj(char)
    if cls == "parent":
        return "mother" if s == "she" else "father" if s == "he" else "parent"
    if cls == "child":
        return "daughter" if s == "she" else "son" if s == "he" else "child"
    return "sister" if s == "she" else "brother" if s == "he" else "sibling"


def _reciprocal(role, other):
    """The role the OTHER party holds back, gendered by the other party."""
    cls = _CLASS.get(role)
    if not cls:
        return None
    return _gendered(_RECIP_CLASS[cls], other)


def _name(char):
    return char.db.rp_name or char.key


# ── ownership derivation ──────────────────────────────────────────────────────
def _is_owner_of(viewer, target):
    """True if viewer owns target: explicit owner link, the facility owner-of-record,
    or the Facility faction's owner over facility stock (Bethany over her line)."""
    e = _rels(viewer).get(_id(target), {})
    if e.get("owner") and _entry_active(e):
        return True
    if getattr(target.db, "facility_owner", None) == _id(viewer):
        return True
    try:
        from world.factions import is_owner, FACILITY
        if getattr(target.db, "facility_active", False) and is_owner(viewer, FACILITY):
            return True
    except Exception:
        pass
    return False


# ── the resolver everything calls ─────────────────────────────────────────────
def tiers_of(viewer, target):
    """Every relationship tier `viewer` holds toward `target`."""
    tiers = set(["all"])
    if viewer is target or (_id(viewer) is not None and _id(viewer) == _id(target)):
        tiers.add("self")
    e = _rels(viewer).get(_id(target), {})
    if _entry_active(e):
        if e.get("family"):
            tiers.add("family")
        if e.get("lover"):
            tiers.add("lover")
    if _is_owner_of(viewer, target):
        tiers.add("owner")
    vf = set(getattr(viewer.db, "faction_member", None) or [])
    tf = set(getattr(target.db, "faction_member", None) or [])
    if vf & tf:
        tiers.add("faction")
    if vf and tf:
        try:
            from world.factions import relation_between
            if any(relation_between(a, b) == "enemy" for a in vf for b in tf):
                tiers.add("hostile")
        except Exception:
            pass
    return tiers


def role_toward(viewer, target):
    """The family role string viewer holds toward target (e.g. 'mother'), or None."""
    return _rels(viewer).get(_id(target), {}).get("family")


def is_lover(viewer, target):
    return bool(_rels(viewer).get(_id(target), {}).get("lover"))


# ── honorifics: who present holds a claim over you, and what you must call them ──
# Strongest claim first. Hostiles are intentionally absent — you owe an enemy no honour.
_ADDRESS_PRIORITY = ("owner", "lover", "family", "faction")


def present_superiors(target):
    """Characters in `target`'s room who hold a relationship tier OVER target, each paired
    with the address-relevant tiers they hold, ordered strongest-claim first. Read-only;
    used by the honorifics clause. Never raises — returns [] on any trouble."""
    room = getattr(target, "location", None)
    if not room:
        return []
    try:
        from typeclasses.characters import Character
    except Exception:
        Character = None
    out = []
    for obj in (getattr(room, "contents", None) or []):
        if obj is target:
            continue
        if Character is not None and not isinstance(obj, Character):
            continue
        try:
            tiers = tiers_of(obj, target) & set(_ADDRESS_PRIORITY)
        except Exception:
            tiers = set()
        if tiers:
            out.append((obj, tiers))
    out.sort(key=lambda item: min(_ADDRESS_PRIORITY.index(t) for t in item[1]))
    return out


def required_address(target, honorifics):
    """Given the clause's `honorifics` map (tier -> token; 'family' may map role -> token, or a
    plain token, with '*' as the fallback), return (token, holder_name, tier) for the
    highest-priority relationship-holder present over `target`, else None. No superior in the
    room = no requirement: you can't fail to honour someone who isn't here to hear it."""
    if not honorifics:
        return None
    for holder, tiers in present_superiors(target):
        for tier in _ADDRESS_PRIORITY:
            if tier not in tiers:
                continue
            if tier == "family":
                fam = honorifics.get("family")
                if isinstance(fam, dict):
                    token = fam.get(role_toward(holder, target)) or fam.get("*")
                else:
                    token = fam
            else:
                token = honorifics.get(tier)
            if token:
                return token, _name(holder), tier
    return None


# Relationship-tier keywords that can stand in for a person in consent overrides.
# ('all' is intentionally NOT here — the global consent flag already means "everyone".)
TIER_KEYWORDS = ("owner", "lover", "family", "faction", "hostile")


def override_decision(actor, target, allow_set, block_set):
    """Resolve a stored allow/block override for `actor` toward `target`.

    The override sets (from `consent_overrides`) may hold int character ids AND
    relationship-tier strings (owner/lover/family/faction/hostile). An actor matches
    by id OR by holding a tier present in the set. Block wins over allow, matching the
    existing consent precedence. Returns 'block' / 'allow' / None (None → fall through
    to the global flag, exactly as before for id-only sets)."""
    if actor is None:
        return None
    bset = block_set or set()
    aset = allow_set or set()
    aid  = _id(actor)
    tiers = tiers_of(actor, target)
    if aid in bset or (tiers & {x for x in bset if isinstance(x, str)}):
        return "block"
    if aid in aset or (tiers & {x for x in aset if isinstance(x, str)}):
        return "allow"
    return None


# ── mutation ──────────────────────────────────────────────────────────────────
def _apply(viewer, target, role=None, lover=False, forced=False, expires_at=None):
    """Write both directions of a relation. Internal — callers gate consent/ownership.
    `expires_at` (epoch secs) marks a temp bond; None leaves the entry permanent."""
    vr = _rels(viewer)
    ve = dict(vr.get(_id(target), {}))
    if role:
        ve["family"] = role
    if lover:
        ve["lover"] = True
    ve["set_by"] = _id(viewer)
    ve["forced"] = bool(forced) or bool(ve.get("forced"))
    if expires_at is not None:
        ve["expires_at"] = float(expires_at)
    vr[_id(target)] = ve
    viewer.db.relationships = vr

    tr = _rels(target)
    te = dict(tr.get(_id(viewer), {}))
    if role:
        rec = _reciprocal(role, target)
        if rec:
            te["family"] = rec
    if lover:
        te["lover"] = True
    te["set_by"] = _id(viewer)
    te["forced"] = bool(forced) or bool(te.get("forced"))
    if expires_at is not None:
        te["expires_at"] = float(expires_at)
    tr[_id(viewer)] = te
    target.db.relationships = tr


def offer_relation(viewer, target, role=None, lover=False, owner=False,
                   flavor=None, expires_at=None):
    """Propose a mutual bond; stored pending until target accepts.

    Bonds: a family `role`, `lover`, or ownership (`owner=True`, with `flavor`
    one of owned/slave/pet). `expires_at` (epoch secs) makes it a temp bond.
    Ownership offered this way is CONSENSUAL (target must accept); the imposed
    path is `force_relation`. NPCs use the same owner tier."""
    if role and role not in FAMILY_ROLES:
        viewer.msg(f"|xUnknown family role '{role}'. Try: {', '.join(sorted(FAMILY_ROLES))}, "
                   f"lover, own, slave, or pet.|n")
        return
    offers = _offers(target)
    offers[_id(viewer)] = {"family": role, "lover": lover, "owner": bool(owner),
                           "flavor": flavor, "expires_at": expires_at}
    target.db.relationship_offers = offers
    label = (flavor or "owner") if owner else (role or ("lover" if lover else "kin"))
    span = "" if expires_at is None else " |x(temporary)|n"
    if owner:
        viewer.msg(f"|MYou offer to take {_name(target)} as your |w{label}|M{span}. "
                   f"They must |waccept|M it.|n")
        target.msg(f"|M{_name(viewer)} offers to take you as their |w{label}|M{span} — "
                   f"|wrelate/accept {_name(viewer)}|M to give yourself over, "
                   f"|wrelate/reject {_name(viewer)}|M to refuse.|n")
    else:
        viewer.msg(f"|gYou offer {_name(target)} a bond: |w{label}|g{span}. "
                   f"They must |waccept|g it.|n")
        target.msg(f"|y{_name(viewer)} offers you a bond — |w{label}|y{span}. "
                   f"|wrelate/accept {_name(viewer)}|y to take it, "
                   f"|wrelate/reject {_name(viewer)}|y to refuse.|n")


def accept_relation(target, viewer):
    """Target accepts viewer's pending offer."""
    offers = _offers(target)
    off = offers.pop(_id(viewer), None)
    target.db.relationship_offers = offers
    if not off:
        target.msg(f"|x{_name(viewer)} has no bond on offer to you.|n")
        return
    exp = off.get("expires_at")
    if off.get("family") or off.get("lover"):
        _apply(viewer, target, role=off.get("family"), lover=off.get("lover"),
               forced=False, expires_at=exp)
    if off.get("owner"):
        # Consensual ownership: viewer becomes target's owner (not forced).
        set_owner(viewer, target, forced=False, flavor=off.get("flavor"), expires_at=exp)
    flavor = off.get("flavor")
    label = (flavor or "owner") if off.get("owner") else \
            (off.get("family") or ("lover" if off.get("lover") else "kin"))
    span = "" if exp is None else " (for now)"
    if off.get("owner"):
        target.msg(f"|MYou give yourself over: {_name(viewer)} owns you as their {label}{span}.|n")
        viewer.msg(f"|M{_name(target)} accepted. They're your {label}{span} — on paper now.|n")
        if flavor in ("slave", "pet"):
            viewer.msg(f"|xTip: set what they call you — "
                       f"|whonorific {_name(target)} = Mistress|x.|n")
    else:
        target.msg(f"|gBond formed: {_name(viewer)} is your "
                   f"{role_toward(viewer, target) or label}{span}.|n")
        viewer.msg(f"|g{_name(target)} accepted. You are their {off.get('family') or label}{span}.|n")


def reject_relation(target, viewer):
    offers = _offers(target)
    if offers.pop(_id(viewer), None) is not None:
        target.db.relationship_offers = offers
        target.msg(f"|xYou refuse {_name(viewer)}'s offer.|n")
        viewer.msg(f"|x{_name(target)} refused the bond.|n")
    else:
        target.msg(f"|xNothing from {_name(viewer)} to refuse.|n")


def force_relation(owner, target, role):
    """An OWNER imposes a bond without consent (on-theme for the line). Family roles
    and ownership (own/slave/pet) are forceable; lover is always mutual. Forced ties
    are logged and reverted by the OOC floor (`clear_forced`)."""
    if role in OWNER_FLAVORS:
        if not _is_owner_of(owner, target):
            owner.msg(f"|xYou don't own {_name(target)}. Forced ties are an owner's privilege.|n")
            return False
        flavor = OWNER_FLAVORS[role]
        set_owner(owner, target, forced=True, flavor=flavor)
        owner.msg(f"|MYou make {_name(target)} your {flavor}, whether they like it or not. "
                  f"On paper now.|n")
        target.msg(f"|M{_name(owner)} makes it official — you're their {flavor} now.|n")
        try:
            log = list(getattr(target.db, "behaviour_log", None) or [])
            log.append({"t": "forced_owner", "by": _id(owner), "flavor": flavor})
            target.db.behaviour_log = log[-100:]
        except Exception:
            pass
        return True
    if role not in FAMILY_ROLES:
        owner.msg(f"|xCan't force '{role}'. Family roles, or own/slave/pet only.|n")
        return False
    if not _is_owner_of(owner, target):
        owner.msg(f"|xYou don't own {_name(target)}. Forced ties are an owner's privilege.|n")
        return False
    _apply(owner, target, role=role, forced=True)
    owner.msg(f"|MYou write yourself into {_name(target)}'s blood: you are their {role}, "
              f"and they are your {role_toward(target, owner)}. It is on paper now.|n")
    target.msg(f"|M{_name(owner)} makes it official, whether you like it or not — "
               f"{_name(owner)} is your {role}.|n")
    # behaviour log (Layer 2 will formalise; record now so nothing is silent)
    try:
        log = list(getattr(target.db, "behaviour_log", None) or [])
        log.append({"t": "forced_relation", "by": _id(owner), "role": role})
        target.db.behaviour_log = log[-100:]
    except Exception:
        pass
    return True


def clear_relation(a, b):
    """Remove the relation in BOTH directions between a and b."""
    ar = _rels(a); ar.pop(_id(b), None); a.db.relationships = ar
    br = _rels(b); br.pop(_id(a), None); b.db.relationships = br


def set_owner(owner, target, forced=True, flavor=None, expires_at=None):
    """Mark `owner` as an owner of `target` (an explicit owner-tier link). Supports
    multi-owner — several characters may each hold this over one target. Stored on the
    owner's side; `_is_owner_of` reads it. `forced` lets the floor/contract revert it.
    `flavor` (owned/slave/pet) seeds the default honorific/title; `expires_at` makes a
    temp ownership."""
    vr = _rels(owner)
    e = dict(vr.get(_id(target), {}))
    e["owner"] = True
    e["set_by"] = _id(owner)
    e["forced"] = bool(forced) or bool(e.get("forced"))
    if flavor:
        e["flavor"] = flavor
    if expires_at is not None:
        e["expires_at"] = float(expires_at)
    vr[_id(target)] = e
    owner.db.relationships = vr


def drop_owner(owner, target):
    """Remove an owner link owner→target (used by the contract/floor revert)."""
    vr = _rels(owner)
    e = dict(vr.get(_id(target), {}))
    if e.pop("owner", None) is not None:
        if e:
            vr[_id(target)] = e
        else:
            vr.pop(_id(target), None)
        owner.db.relationships = vr


def clear_forced(char):
    """OOC-floor hook: drop every FORCED tie on char (and its reciprocal on the
    other party). Leaves mutual player-set ties intact. Returns count removed."""
    rels = _rels(char)
    removed = 0
    for oid, e in list(rels.items()):
        if e.get("forced"):
            rels.pop(oid, None)
            removed += 1
            other = _obj(oid)
            if other:
                orels = _rels(other)
                if orels.pop(_id(char), None) is not None:
                    other.db.relationships = orels
    char.db.relationships = rels
    return removed


def prune_expired(char):
    """Drop every expired temp bond on char (and its reciprocal on the other party).
    Lazy cleanup — `tiers_of`/`_is_owner_of` already ignore expired entries at read
    time, so this only tidies storage. Returns the count removed."""
    rels = _rels(char)
    removed = 0
    for oid, e in list(rels.items()):
        if not _entry_active(e):
            rels.pop(oid, None)
            removed += 1
            other = _obj(oid)
            if other:
                orels = _rels(other)
                oe = orels.get(_id(char))
                if oe is not None and not _entry_active(oe):
                    orels.pop(_id(char), None)
                    other.db.relationships = orels
    if removed:
        char.db.relationships = rels
    return removed


# ── display ───────────────────────────────────────────────────────────────────
def describe(char):
    """A readable summary of char's relationships + pending offers."""
    prune_expired(char)
    rels = _rels(char)
    lines = ["|w" + "═" * 44 + "|n", "|wRELATIONSHIPS|n", "|w" + "═" * 44 + "|n"]
    if not rels:
        lines.append("|xNo bonds on record.|n")
    for oid, e in rels.items():
        other = _obj(oid)
        oname = _name(other) if other else f"#{oid}"
        bits = []
        if e.get("family"):
            bits.append(f"|Myour {role_toward(other, char) or '?'}|n, you their |M{e['family']}|n"
                        if other else f"family: {e['family']}")
        if e.get("lover"):
            bits.append("|rlover|n")
        if e.get("owner"):
            # char owns other (this entry is char→other with owner set)
            bits.append(f"|Yyour {e.get('flavor') or 'owned'}|n")
        elif other and _is_owner_of(other, char):
            bits.append("|Yowner|n")
        tag = " |x(forced)|n" if e.get("forced") else ""
        if e.get("expires_at"):
            mins = max(0, int((float(e["expires_at"]) - _now()) / 60))
            tag += f" |x(temp, ~{mins}m left)|n"
        lines.append(f"  {oname}: " + ", ".join(bits or ["bond"]) + tag)
    offers = _offers(char)
    if offers:
        lines.append("|x── pending offers ──|n")
        for fid, off in offers.items():
            fo = _obj(fid)
            if off.get("owner"):
                what = f"to own you as their {off.get('flavor') or 'owned'}"
            else:
                what = off.get("family") or ("lover" if off.get("lover") else "kin")
            span = " |x(temp)|n" if off.get("expires_at") else ""
            lines.append(f"  {_name(fo) if fo else f'#{fid}'} offers: {what}{span}  "
                         f"|x(relate/accept · relate/reject)|n")
    lines.append("|w" + "═" * 44 + "|n")
    return "\n".join(lines)
