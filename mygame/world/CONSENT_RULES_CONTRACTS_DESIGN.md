# Design — Consent · Relationships · Rules · Contracts (the authority stack)

Status: **blueprint, agreed-in-principle, NOT built.** This is the talk-through before any code.
Captures the design direction from the user. Build order + open questions at the bottom.

The through-line: **the consent system the user already has is the spine.** Everything else hangs
off it. We do not replace it — we extend it, and add a relationship layer it can address, a rules
layer it gates, and a contracts layer that *grants* it. And the §0 OOC floor sits under all of it,
untouched: `escape`/`force_clear`/`facilityreset` overrides every consent, lock, rule, and clause,
always, instantly.

---

## Layer 1 — RELATIONSHIPS (new; the thing consent can address)
A unit's consent/authority shouldn't only be "this exact person" or "everyone" — it should be able
to say "my owner may, my lovers may, hostile factions may not." So we need relationship TIERS.

Tiers a viewer can hold toward a target (a viewer may hold several at once):
- **self** — you, toward you.
- **owner** — holds you: facility owner (`is_owner`), your conditioning-consent holder, or an
  explicit owned-by link. The cruellest tier; Bethany lives here.
- **lover** — a mutually-set bond.
- **family** — lineage / mutually-set kin (ties the offspring/lineage system).
- **faction** — shares a faction with you (`factions.py` membership).
- **hostile** — a faction at enmity with yours (faction relations already exist).
- **all** — anyone (the catch-all / default tier).
- **<specific person>** — an explicit id, most specific.

API sketch (`world/relationships.py` or extend `world/factions.py`):
- `tiers_of(viewer, target) -> set[str]` — every tier the viewer holds toward the target.
- lover/family are **mutual opt-in** (offer/accept, like the conditioning handshake / faction invite).
- owner is derived (facility owner / consent-holder / owned-by), not self-claimed.

## Layer 2 — CONSENT / AUTHORITY MATRIX (extend the existing consent system)
The user's verb stays: **`consent <feature> allow|block <who>`** — where `<who>` is now any of:
a specific person, a relationship tier, or `all`. This is the per-feature, per-tier permission
matrix (BCX's authority module, expressed through the consent verb the user already likes).
- Store: `db.consent_matrix = {feature: {who: "allow"|"block"}}` (who = id | tier | "all").
- Resolve `may(actor, target, feature)`:
  1. most-specific wins: explicit person-id > relationship tier > `all`;
  2. at equal specificity, **block beats allow** (safety-first);
  3. default if unset = sensible per-feature default (most features default block for strangers,
     allow for self/owner).
- The CURRENT conditioning consent becomes features under this matrix
  (`condition.deepen/trigger/speech/name/body`, `rule.set`, `tf.scale`, `use`, `leash`, `dress`, …).
- Back-compat: the existing `condition/allow`, scope list, and the consent-LOCK all fold in as
  matrix state + a `locked` flag (locked = the unit can't edit the matrix themselves; an authorised
  holder or the §0 floor can). "Overall consent state that follows my system, with amendments."
- **Behaviour log / control** (user ask): `db.behaviour_log` records rule breaks + authority actions;
  a `log` view; and access to view/edit it is itself a matrix feature — someone with sufficient
  authority can LOCK a unit out of their own log (BCX behaviour-log + lockout).

## Layer 3 — RULES (new; standing obligations, gated by Layer 2, enforced by what we have)
`db.rules = [{id, name, set_by, scope_tier, condition, consequence}]`. Setting a rule requires
`may(actor, target, "rule.set")`. A curated set (NOT BCX's 70-sprawl), each with:
- **Condition** (when it applies — reuse a `meets()`-style gate): always / in <room> / owner-present
  / owner-absent / time-window (curfew) / arousal-over-N / while-a-flag.
- **Consequence** (all three are valid, per rule — user confirmed):
  - **hard block** — the action is prevented (movement/speech locks we already have);
  - **punish after** — it goes through, then `make_example`/`punish`/conditioning fires;
  - **owner-notified** — logged to the behaviour log + the setter pinged, handled in-fiction.
- Curated rule set that FITS (we own the hooks): must present/kneel on enter; may-not-leave-without-
  permission; ask-permission-to-come / announce-orgasm (ties denial subsystem); honorific / banned-
  words / designation (built); curfew/quota-by-time (ties Daily Quota); announce/count-use-aloud
  (Records/Tally); no-clothing; posture-hold.
- Bethany sets the cruellest of these on her stock; consented players set them within scope;
  a unit can self-impose (and lock, relying on someone to lift).

## Layer 4 — CONTRACTS (expand the existing `MilkingContract`; the keystone)
**Signing is consent — fully informed or otherwise.** A contract is the instrument that GRANTS the
consent-matrix entries, installs the rules, and applies the binding_effects, all at once, on sign.
This is exactly how the facility contract already works (visible + hidden clauses, `reveal_on_sign`,
a `binding_effects` payload) — we generalise it:
- A **clause** = a contract-bound rule/grant: it can grant a consent-matrix entry (allow <who> a
  feature), impose a Layer-3 rule, set a flag, or carry a `binding_effects` payload. Devious, with
  its own function — hidden clauses that grant consent the signer didn't read.
- **Player-authored contracts** — not just the facility's: any player can draft a contract with
  clauses and offer it; signing grants what it says. (The conditioning-consent handshake becomes a
  special case of "signing a small contract.")
- Expanded contract system (user has more ideas — TBD): templates, hidden/locked clauses, addenda
  the signer pre-consented to, term/quota-defined length, transfer/sale of a contract, etc.
- **§0 invariant:** no clause, signed or hidden, can gate the OOC floor. Signing grants everything
  EXCEPT the fire-exit. (The facility contract's H29 already states this in-fiction.)

---

## What does NOT fit (ruled out / care needed)
- No **hard game-over bad-ends** — soft, escapable deep states only (separate user ruling).
- No **anti-cheat / can't-escape** rules — the §0 floor is the one true override and stays loud.
- No **BCX 70-rule parity** — a tight curated set we actually have hooks for.
- BCX **item-slot curse auto-reapply** belongs to the wardrobe build (E), not the rules engine.

## Build order (proposed — confirm before each)
1. **Relationships** (Layer 1) — small, foundational; lover/family handshake + `tiers_of` + owner
   derivation + reuse faction membership/enmity.
2. **Consent matrix** (Layer 2) — fold the existing conditioning consent into `consent <feature>
   allow|block <who>` over tiers; `may()` resolver; behaviour log + lockout.
3. **Rules** (Layer 3) — the curated rule set + condition/consequence + checker hooks.
4. **Contracts** (Layer 4) — generalise `MilkingContract`; clauses grant consent / impose rules /
   carry payloads; player-authored contracts. (User has further ideas to fold in here.)

## OPEN — for the user
- The user's **contract ideas** (explicitly held back to share) — fold into Layer 4 before building it.
- Lover/family: mutual-only? can an owner FORCE a family/lineage tie (on-theme for the breeding line)?
- Default per-feature consent for strangers/`all` — block-by-default everywhere, or per-feature?
- Does a hostile-faction tier get any allows by default (non-consensual-fiction within consenting
  players), or is it purely a BLOCK target?
