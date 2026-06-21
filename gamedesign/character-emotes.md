# Character Emotes & the Act Framework — touch, sex, arousal

*Design-from-scratch reference. How a character **does something to a zone** — on themselves, on a
room, or on another character — and how the system turns that into **reactive, pooled prose + real
state change**. This unifies the current touch/penetration verbs, the freeform zone-emote responses,
and the arousal/breeding systems into one **typed-act framework**. Spine: `character-zones.md`
(zones are typed; acts are typed against them). Overview: `characters.md`.*

> **[BUILT]** live · **[SPLIT]** exists, reorganize · **[ROADMAP]** target.

## The idea
A free emote (`emote`/`pose`) says *what you do* but changes nothing. The game's interesting verbs
— `touch/caress/grope/kiss/lick`, `penetrate/thrust/withdraw/deposit/suck/handmilk` — already do
more: they target a **zone**, read its state, and emit a response. **Generalize all of them into one
shape:**

> **An act = `(verb, actor-part, target-zone)`**, validated by **slot-types + consent**, resolved
> into a **pooled reactive emote** *and* **real state** (use stats, fluids, arousal, marks, breeding).

Because zones are typed (`surface`/`gland`/`orifice`/`appendage` — see `character-zones.md`), the
*same* verb means the right thing in the right place automatically, and nonsense is refused before
it prints. The body spine and the act framework are the **same type system** seen from two sides:
one defines what a part *is*, the other defines what you can *do* to it.

---

## 1. Anatomy of an act  [ROADMAP — generalizes the current verbs]
```
act:
  verb:        touch | caress | grope | kiss | lick | suck | penetrate |
               thrust | withdraw | deposit | handmilk | bite | grind | ...
  actor:       <character>                # who acts
  actor_part:  <zone on actor>            # hand, mouth, cock[1..n], tail ...  (optional)
  target:      <character | self | room>  # who/what is acted on
  target_zone: <zone on target>           # mouth, breast, pussy, anus, nipples ...
  config:      { force, depth, pace, intent: tender|rough|clinical|cruel ... }
```
Resolution pipeline (every act runs the same four steps):
1. **Validate by type.** Verb declares the **target zone-type(s)** it accepts (`suck`→ gland/orifice;
   `penetrate`→ orifice; `handmilk`→ gland). The actor_part (if any) declares *its* type
   (`penetrate` needs an `appendage` actor_part). Wrong type → refused with a clear reason. (The
   `WombRoom` orifice check is the prototype; make it the universal gate.)
2. **Check consent.** The act's verb + zones map to consent keys (`consent.may(actor, target, key)`);
   intimate verbs require the intimate gate, penetrative verbs the penetration gate, etc. Denied →
   the act doesn't fire (and optionally logs to the consent log).
3. **Emit reactive prose.** Pull from the **message pool** for `(verb × target-zone-type [× state])`
   — *two-sided*: an actor line and a target line, each reading live state (see §2–3).
4. **Apply real state.** Arousal deltas on both sides, `record_use`/`hole_capabilities` updates,
   fluid bookkeeping, marks, breeding hooks — the act *does the thing*, never just narrates it
   (CLAUDE.md §2.4: "told, not done" is the enemy).

## 2. Message pools per zone × verb  [BUILT as `handle_details` → ROADMAP: extend]
**This already exists.** Each zone carries `handle_details`: a dict keyed by **verb → a *list* of
messages** (a pool), authored live by the player. The act framework **extends** that structure — it
does not invent a new one. Today's shape (real):
```
zone.handle_details:
  touch:  [ line, line, line, ... ]        # verb -> pool of lines (already a list)
  caress: [ ... ]
  lick:   [ ... ]
  kiss:   [ ... ]
```
Authored with the **real** `zone handle` command (verbs available today: touch, caress, grope,
stroke, grab, squeeze, kiss, bite, lick, taste, pull, pinch, nuzzle, hold, pet):
```
zone handle/add <zone>/<verb> = <message>     # append a line to that verb's pool
zone handle/list <zone>                        # show every verb + its pool
zone handle/rm  <zone>/<verb> <#>              # remove line N
```
Tokens in a line are the **real** ones (not `{t}`): `{actor}`, `{actor_s}`, `{actor_they}`,
`{actor_them}`, `{actor_their}`, and the matching `{target}*` set.
Keep pools **deep** (15–25+ lines per high-frequency verb) so nothing loops (CLAUDE.md §5).

**What the act framework adds [ROADMAP]:**
- **More verbs.** Extend the verb list with the penetrative/sex set (`penetrate`, `thrust`,
  `withdraw`, `deposit`, `suck`, `handmilk`, `grind`, `deepthroat`, `rim`) — same `handle_details`
  dict, more keys.
- **Per-zone-type defaults.** Ship a default pool per zone-*type* (a generic `gland`/`suck` pool any
  breast inherits) so a fresh body is never empty; a specific zone's authored pool **overrides or
  adds to** the default. (Default + custom, both player-authorable — see Q2 below.)
- **State-keyed sub-pools.** Let a verb branch on live state instead of one flat list:
  ```
  handle_details.penetrate: { shallow:[...], deep:[...], knot:[...], gape:[...] }
  ```
  so `penetrate` reads differently at first entry vs. at the knot vs. once gaped. This is where the
  prose earns its keep — specificity from real state (cycles served, brood count, hole use,
  fullness). A flat list stays valid (treated as the default sub-pool).

## 3. Two-sided / reactive emotes  [SPLIT — formalize the existing responses]
Every act emits **for both parties**, each line reading the *other* side's live state:
- **Actor line** reads the target's state ("her cunt's already slick and loose from the last load").
- **Target line** reads the actor's part + the act ("the flared head drags wide, the knot still
  outside her"), and the target's own arousal/conditioning ("she's past pretending she doesn't want
  it").
- **Room line** (optional, throttled): a third-person beat for onlookers, gated by visibility/cover
  (§5 of `character-zones.md`).
Reading real state is what makes it reactive instead of canned. Arousal tier, fullness, capability
flags, conditioning/devotion, and the `intent` config all select which line and which tone-colour
(`|y` hands/use, `|r` breeding, `|m` degradation, `|M` the Process — CLAUDE.md §5).

## 4. Concurrency & multiplicity — many parts, many holes at once  [ROADMAP — the key generalization]
A single act is one pairing; a **scene act binds several pairings into one resolved beat** so
simultaneity is first-class, not faked by spamming verbs:
```
scene_act:
  intent: rough
  pairings:
    - { verb: penetrate, actor_part: cock[1], target_zone: mouth }
    - { verb: penetrate, actor_part: cock[2], target_zone: pussy }
    - { verb: penetrate, actor_part: cock[3], target_zone: anus }
```
- **Multiple actor-parts.** An actor with N of a part (e.g. a futa whose root **splits into three
  prehensile, individually knotting/flaring shafts** — Bethany canon, `bethany_script`) indexes them
  `cock[1..3]`; each pairing validates, consent-checks, and resolves **independently**, then composes
  into one two-sided emote ("one down her throat, one in her cunt, the third working her ass open").
- **Multiple target-zones / partners.** Pairings can point at different zones on one target, or at
  **different targets** (one shaft per hole across two people) — the gangbang/multi-partner case the
  facility already implies, expressed cleanly.
- **Per-pairing capability checks.** Each pairing resolves its own `hole_capabilities`
  (knot/double/fist/gape/prolapse): can *this* hole take *this* part, flare in it, lock the knot
  behind the ring? "Two cocks in one hole" is a single target-zone with two actor-part pairings and a
  `double` capability check. Stretch/gape state updates per hole.
- **Shared context.** All pairings share one arousal pass, one fluid/breeding pass (three loads, one
  cumflation tally), and one consent envelope — so the *scene* moves the meters once, coherently,
  instead of N disjoint emotes.

This is the direct answer to "how many can you force in at once": **as many as parts × holes ×
capability allow** — the framework counts them, checks each, and narrates the whole as one beat.

## 5. The arousal system  [ROADMAP — formalize the curve]
A per-character **arousal meter** (like `conditioning` — an accelerating staged meter) that acts
read and feed:
- **Curve:** `build → edge → peak → afterglow`, with **refractory/oversensitive** after peak. Acts
  add arousal scaled by zone sensitivity, intent, capability events (knotting/flaring spikes it),
  and conditioning/devotion (the laced load — Bethany's cum carries DEVOTION, so peaks here *raise*
  conditioning, tying arousal into the long meters).
- **Gates prose & options.** Arousal tier selects message sub-pools (a teasing `caress` reads
  differently past `edge`), unlocks/locks certain acts (can't `deposit` before `peak`; oversensitive
  zones refuse more `lick`), and feeds the breeding/fluid systems.
- **Per-zone sensitivity** is a `surface`/`gland`/`orifice`/`appendage` upgrade (`character-zones.md`
  §4) — sensitized nipples or a sensitized cock contribute more per act.
- **Edging/denial** is a first-class state (held at `edge`, peak withheld) — a conditioning/devotion
  lever, not just flavour.
- **Visibility (resolved):** the meter is **private by default** — only you read your own tier;
  others infer it from your emotes/desc. **Owners see it** on those they own (Bethany/Seraphine/a
  player owner) — a cold line in the file (*"arousal: peak — denied 3×"*) the property doesn't get
  to hide. Implemented as private + an ownership-relationship override (ties to `character-social.md`
  ownership). No partner-wide visibility unless ownership grants it.

## 6. Wide sex-act coverage  [ROADMAP — what the verbs span]
The framework covers the genre (CLAUDE.md §0) by **verb × target-zone-type × capability**, not by a
giant flat command list:
- **Oral** — `suck`/`lick`/`kiss`/`deepthroat` on `mouth` (orifice) or `gland`; drinking loads =
  `deposit` into `mouth` + a swallow/fluid hook (the laced-cum DEVOTION pass).
- **Vaginal / anal** — `penetrate`/`thrust`/`withdraw`/`deposit`/`grind` on `pussy`/`anus`
  (orifice), with `knot`/`double`/`fist`/`gape`/`prolapse` capability branches.
- **Rimming** — `lick`/`kiss` on `anus` (orifice, non-penetrative sub-case).
- **Breeding** — `deposit` routes through the real `gang_inseminate`/`do_inseminate` +
  pregnancy/lineage/quota systems (CLAUDE.md §3 gang-breeding); the emote **broadcasts the real
  deposit message** (CLAUDE.md §2.4), never a silent one.
- **Lactation/milking** — `suck`/`handmilk` on `breast`/`nipples` (gland) → the milking mechanic +
  production state.
- **Cumflation** — repeated/high-volume `deposit` (Bethany's 4–8 L) accrues a belly/fullness state
  on the target's `belly` zone, with its own descs/look impact.
- **Multi-partner / multi-cock** — the concurrency model (§4): gangbangs, three-holes-at-once, a
  hand still free for her coffee. (*Multiple parts into a **single** hole — two cocks in one ass —
  is the `double` capability sub-case; noted but **not a current priority**.*)
- **Kissing / tenderness** — `kiss` carries the false-tenderness register (`|M`/warm intent) — the
  contrast beat (CLAUDE.md §7) is a tone/intent selection, same machinery.

## Commands (shape, not final)
- **Acting:** `<verb> <target> [zone]` / `<verb> <target>'s <zone> [with <my-part>]` — single act.
  `<verb> <target> with cock1` (or `all`) — index/select actor-parts for concurrency.
  `arousal`/`mood` shows your curve (own meter; owners see those they own — see §7); `consent`/
  `limits` gates it.
- **Authoring pools (real, exists today):** `zone handle/add <zone>/<verb> = <message>` appends a
  line; `zone handle/list <zone>` shows pools; `zone handle/rm <zone>/<verb> <#>` removes one. Same
  for rooms via `roomzone`. Both **default (type-level) and custom (per-zone) pools are
  player-authored** through this command — there is no separate `acts` key; pools live in
  `handle_details`.

## Real subsystems this builds on / replaces
- **Builds on:** the touch/zone verbs (`CmdZoneInteract`: touch/caress/grope/kiss/lick + `CmdSmell`),
  the penetration verbs (`penetrate/thrust/withdraw/deposit/suck/handmilk`), the existing
  **`handle_details` verb→pool** structure + its `zone handle/add|list|rm` authoring command (the
  per-`(verb,zone)` pool *already exists* — this extends it), `record_use`/`hole_capabilities`/
  `gang_inseminate`/`do_inseminate` (CLAUDE.md §3), the milking mechanic, `consent.may`, the
  `study_details` list-pool pattern, `conditioning` (the accelerating-meter model for arousal),
  `bethany_script` three-cock anatomy.
- **Generalizes:** all intimate verbs into one typed-act pipeline (validate-by-type → consent →
  pooled two-sided emote → real state), with concurrency/multiplicity built in.
- **Extends (not replaces):** `handle_details` gains the sex verbs, state-keyed sub-pools, two-sided
  lines, and type-level defaults; one-target verbs gain the optional scene-act concurrency binder.

## §0 OOC floor
Acts are **consent-gated before they fire** (step 2), and `escape`/`force_clear` always end the
scene and free the **person** from any trap mid-act, regardless of how many pairings are live (the
concurrency model never creates an unbreakable hold — the floor relocates and clears scene state
unconditionally). Arousal/use/breeding state set by acts is normal reversible character state. No
act, capability, or concurrency may gate the self-service exit. **Hardcore mode** (see
`characters.md` §0 / `character-consent.md`) only ever opts out of *item teardown*, never out of
freeing the person from a trap.

## What to carry into the fresh build
- ✅ The typed-act pipeline (verb × actor-part × target-zone → validate/consent/pooled-emote/state);
  per-`(verb,zone)` message pools; two-sided reactive emotes; the arousal curve; concurrency &
  multiplicity as first-class (many parts → many holes, per-pairing capability checks, one shared
  context); routing breeding/milking/fluids through the real systems with real broadcasts.
- 🔧 Build the arousal meter + per-zone sensitivity upgrades; convert single-line zone responses to
  pools; build the scene-act binder for simultaneity; wire `deposit`→`gang_inseminate` broadcast.
- ✂️ Retire one-line-only zone responses and one-target-only verb assumptions.

## Resolved decisions
- **Pool authoring:** **player-authored, both default and custom**, through the *existing* real
  command — `zone handle/add <zone>/<verb> = <message>` (no invented `acts` key; pools are
  `handle_details`). Type-level defaults seed a fresh body; per-zone pools override/extend.
- **Arousal visibility:** **private by default + owner-visible** (see §5). No partner-wide read.
- **Multi-part into one hole** (two cocks, one ass): the `double` capability sub-case — **noted, not
  a current priority** (§6). Concurrency across *different* holes/partners is the live feature (§4).

## Open questions
- **Concurrency syntax:** explicit scene-act builder vs. a natural multi-target parser
  (`fuck her mouth and cunt and ass`)? The builder is unambiguous; the parser reads better. (Low
  priority — single acts cover the common case.)
