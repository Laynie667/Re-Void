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
- **family** — lineage / kin, and **granular by role** (for incest/lineage play, which is core to
  Bethany — she breeds her own line and makes herself its origin). A relation entry stores a ROLE,
  not just the bare tier:
    `db.relationships[target_id] = {"family": "<role>", "lover": bool, "owner": bool,
                                    "set_by": id, "forced": bool}`
  Role catalogue (with reciprocals; the reciprocal is auto-set on the other party, gendered by their
  sex/pronouns):
    - parent side: **mother / father / sire / dam** (sire & dam = the breeding terms) / generic *parent*
    - child side:  **daughter / son / get / offspring** / generic *child*
    - sibling:     **sister / brother / sibling**
    - (later, optional) grandam/grandsire, aunt/uncle
  `tiers_of` collapses ANY family role → the **`family`** tier for authority checks; the role STRING
  drives flavour, the sheet/`standing` display, honorifics ("mommy", "sire"), and the lineage system.
  Default **mutual** opt-in (`relate <who> = sister`), but an **owner may FORCE** a role
  (`relate/force <who> = daughter`) — sets herself mother/sire and the reciprocal on the target, logged.
  Ageplay (the horse `little` upgrade + infantilizing conditioning) stacks with the mother/child roles
  for the mommy-and-baby register — one coherent knot, not three.
  **DECISIONS (user):** (1) **Core role set only** for v1 — mother/father/sire/dam, daughter/son/get,
  sister/brother (+ generic parent/child/sibling); extended kin (grandam, aunt, cousin…) deferred.
  (2) **lover + family CAN coexist** — `tiers_of` returns both; incest-lovers are intended.
  (3) **Manual only** — offspring do NOT auto-register as family; roles are set deliberately via
  `relate` / owner-force. (Auto-lineage from `bred_by`/`offspring_roster` kept as a future option.)
  **Cleanup:** owner-FORCED ties (`forced=True`) are undone by the OOC floor (`force_clear`); mutual
  player-set lover/family relations are NOT wiped by a facility purge (they're wider-game state).
- **faction** — shares a faction with you (`factions.py` membership).
- **hostile** — a faction at enmity with yours (faction relations already exist).
- **all** — anyone (the catch-all / default tier).
- **<specific person>** — an explicit id, most specific.

API sketch (`world/relationships.py` or extend `world/factions.py`):
- `tiers_of(viewer, target) -> set[str]` — every tier the viewer holds toward the target.
- lover/family are **mutual opt-in** (offer/accept, like the conditioning handshake / faction invite).
- owner is derived (facility owner / consent-holder / owned-by), not self-claimed.

> **Layer 2 status: BUILT (v1, as a focused EXTENSION — not a parallel matrix).** The game already
> had per-feature, per-person allow/block overrides (`db.consent_overrides = {"allow"/"block":
> {type: set(ids)}}`) consulted by `social_commands._check_consent`, `teleport_commands`, etc. v1 just
> lets those same sets ALSO hold relationship-tier strings (owner/lover/family/faction/hostile) and
> teaches the resolvers to match via `tiers_of`. New `relationships.override_decision(actor, target,
> allow, block)` returns block/allow/None (block>allow, then fall through to the global flag —
> unchanged precedence); wired into `_check_consent` + the teleport resolver. `consent allow|block|
> unblock <type> <who>` now accepts a tier keyword for `<who>` (`_resolve_who`); `consent` display
> splits tiers from person-counts.
>
> **Layer 2 v2: BUILT.** `world/consent.py` adds the single resolver `may(actor, target, feature)`
> the rest of the stack calls — it READS both stores (general overrides+flags via override_decision;
> `conditioning_consent` by/scope for `cond.*` features, plus a tier/person umbrella via a general
> `condition` feature, so `consent allow condition owner` hands an owner full conditioning). The
> consent LOCK (`consent_locked`): a unit can `consent lock` themselves (can't self-unlock), an owner
> can `consent lock|unlock <who>`, and a locked unit's self-edits are refused — §0 floor lifts it.
> Behaviour LOG + lockout: `world/consent.log_event/render_log`, the `log` command (own log; owner
> reads/locks via `log/lock`/`log/unlock`); `can_view_log` gates it. New state (`behaviour_log`,
> `consent_locked`, `log_locked_out`) cleared by both reset paths. All resolution tested standalone.

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

> **Layer 3 status: BUILT + WIRED.** Engine as below; now hooked into the live game at every event:
> `say` → `rp_commands.CmdSay` (banned_words/honorific), `enter` → `Character.at_post_move`
> (present/kneel/posture directives), `leave` → new `Character.at_pre_move` (blocks `no_leave` ONLY
> on `move_type=='traverse'` — player exit-walking; escape/force_clear/facility-drag all use 'move' and
> the param defaults to 'move', so the OOC floor can never be trapped), `orgasm` →
> `conditioning.deepen_on_climax` (ask_to_come; `compliance._grant_climax` sets a one-shot
> `rule_come_permit` so granted climaxes aren't punished). Ambient still fires each facility beat.

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
- Expanded contract system: templates, hidden/locked clauses, addenda the signer pre-consented to,
  term/quota-defined length, transfer/sale of a contract, etc.
- **NPC scenario-contracts (user direction — the marquee use of Layer 4).** A contract need not be
  paper signed at a desk; it can be a **trap that springs**: a clause whose "signing" is a CONDITION
  being met, and whose payload is a scripted scene + the consents/rules it imposes for the duration.
  Examples the user wants:
  - **The Eevee plush, Auria's room** — when the user is the only one at the cabin, the plush wakes,
    hunts her down, and makes her its bitch. (Condition: alone + at cabin + plush present → scene.)
  - **The wolf pack** (later) — pack-scene scenario-contract.
  - **Seraphine** — a contract written to her personality.
  Each = a self-contained scene module + a contract whose trigger/payload fires it; reuses the
  scene-pool / gang / conditioning machinery; cleans up on completion or via the §0 floor.
- **§0 invariant:** no clause, signed or hidden or sprung, can gate the OOC floor. Signing/triggering
  grants everything EXCEPT the fire-exit. (The facility contract's H29 already states this in-fiction.)

## The TWO escapes (user asked: can the floor be bought from Bethany?) — ruling
These are different objects. Conflating them is the trap; splitting them gives the user MORE.
- **OOC safety floor** — `escape(me)` / `force_clear(me)` / `facilityreset|purge`. The REAL-LIFE
  fire exit for the human at the keyboard. **Never bought, earned, gated, priced, or abusable** —
  "not abusable" doesn't even apply: it only ever frees the player from a state the player is in,
  against no one. It stays a free, always-available command. This is the beam; it is *because* it's
  unlocked that every in-fiction door can be locked and the dread made real. NON-NEGOTIABLE (§0).
- **In-fiction escape** — a diegetic "release" / "manumission" / contract-buyout: how the CHARACTER
  gets free *inside the story*. **This one IS gateable** — Bethany can sell it, price it obscenely,
  dangle, revoke, hide the price, write a clause that voids it. This is the "available but not
  abusable" texture the user wants, and it's hotter gated than the OOC command could ever be, because
  it adds in-fiction stakes WITHOUT ever cornering a real person. Build this on top of the floor.
  → **BUILT** (`world/release.py` + `release` command). Manumission: Bethany `offer()`s a price
  (scrip + devotion-ceiling + standing-floor), the unit `release ask`/`pay`s toward it, only her
  `grant()` opens the door (drives `reveal_return`), and `revoke()`/`gouge()` slam it shut / raise
  the price. Every message reminds: the OOC floor is separate and always free. Scrip-comfort
  (commissary) still never buys the door; manumission is the only in-fiction door, and it's hers.

---

## What does NOT fit (ruled out / care needed)
- No **hard game-over bad-ends** — soft, escapable deep states only (separate user ruling).
- No **anti-cheat / can't-escape** rules — the §0 floor is the one true override and stays loud.
- No **BCX 70-rule parity** — a tight curated set we actually have hooks for.
- BCX **item-slot curse auto-reapply** belongs to the wardrobe build (E), not the rules engine.

## Build order (proposed — confirm before each)
1. **Relationships** (Layer 1) — small, foundational; lover/family handshake + `tiers_of` + owner
   derivation + reuse faction membership/enmity.
   → **BUILT** (`world/relationships.py` + `relate` cmd). `tiers_of(viewer,target)` returns
   self/owner/lover/family/faction/hostile/all from factions + ownership + explicit links. Granular
   family with auto-gendered reciprocals; mutual offer/accept; owner-force (logged to behaviour_log);
   lover+family stack; `clear_forced` wired into the OOC floor. Flow-tested standalone. NEXT: Layer 2
   consent matrix folds the existing conditioning-consent into `consent <feature> allow|block <who>`
   over these tiers, with a `may()` resolver calling `tiers_of`.
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
