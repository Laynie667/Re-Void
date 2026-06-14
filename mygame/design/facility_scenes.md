# Facility → Cinematic CYOA — conversion plan (living doc)

The facility is being converted from a timer-driven random-message cycle into **choice-driven,
stateful, cinematic scenes** on the `bx_*` model (see `world/cyoa.py`, Bethany's Intake — the
built reference). This doc is the master list of everything to convert.

## Rules (decided)
- **Everything converts to scenes** — EXCEPT genuine cycles (below), which stay loops.
- **`Continue` is a valid one-option beat.** Linear, non-branching moments still advance on the
  player's click, never a timer. (Add a `continue` option → `then` next beat.)
- **Player-paced.** A scene poses and WAITS on `choose`; `escape`/`forceclear` end it always (§0).
- **Stateful + memory.** Beats read `scene_flags` + real char state and reference earlier choices.
- **Real effects only.** Each choice routes through the real systems (breeding/conditioning/
  marks/drugs/compliance/etc.) — never narrated-only.
- **Present actors.** Every scene has a named NPC who drives it, speaks, reacts, and remembers.
- **Scene flow replaces the room-cycle.** Instead of being dragged room→room on a clock, a scene
  ends and OFFERS the next (move, submit, be taken) as choices / consequences.

## STAYS A CYCLE (not converted)
- **Milking fluid-bank loop** (`_do_milk`) — ongoing extraction for the bank.
- **Engorgement leash** (`_engorgement_tick` / `_engorge_leak`) — passive dairy pressure.
- **Device/machine loops** — milking machine, the breeding/breaking machine, rocking horse,
  Spiral Chair session timer (self-releasing furniture stays mechanical).
- **Passive body ticks** — arousal/stim decay, perpetual-heat upkeep.
*(These remain loops; scenes can START them or hand off INTO them.)*

---

## A. ROOM SCENES (one+ per facility room; the room's actor drives it)

| Room | Actor(s) | The scene | Real systems it drives |
|---|---|---|---|
| **Intake** | Bethany | ✅ **BUILT** (`bx_*`, 10 beats) | contract/clause, devote, name-forfeit, first-use |
| **Holding** | a holding handler | held & prepped before processing; the wait, the first inventory | consent open, posture, anti-clothing |
| **Processing Floor** | floor handler / Bethany | put to use on the open floor, on display; routed onward | display/exhibition, use, routing |
| **Breeding Pens** | the **stockman** + named studs + animals | ✅ **BUILT** (`bp_*`, 8 beats; stud/pack/machine branches) | `_gang`/`_scene_knottrain`, lineage, quota |
| **Conditioning Cell** | Bethany (recorded voice) + Spiral Chair | ✅ **BUILT** (`cc_*`, 8 beats; sink/resist, mantra, the descent door) | real `mantra_set` trigger, `deepen` (conditioning+regression), suggestibility |
| **Dairy** | the dairy hand | ✅ **BUILT** (`dy_*`, 5 beats; the scene→cycle SEAM) | real `_do_milk` at quota; then hands off to the retained milking cycle; state-aware (little/pregnant/nugget hook) |
| **The Pigsty** | the custodian | slopped, rutted face-down, kept filthy between uses | `apply_filth`, degradation, punishment |
| **Sanitation Block** | the custodian + the queue | made the anonymous relief-hole at the wall; the toilet frame | use, holes, golden, degradation |
| **The Showroom / Buyers' Gallery** | Bethany + bidders | the appraisal, the block, the bidding, the sale/gavel | `_appraise`, `bid_up`, `bethany_buys`, ownership transfer |
| **The Nursery** | Bethany / nurse | regression, nursing, the Little Box; your get raised here | regression, little-clauses, lineage loop |
| **The Marking Parlour** | the **marker** | branding / piercing / tattoo / the permanent work | `_proc_*` (real piercings/marks/brands) |
| **Bethany's Office** | Bethany | the kept/owned arc — her evening, her bed, her file on you | `bethany_breeds`, devotion, ownership, `file_read` |
| **Deep Stock** | (machines) + Bethany | the sealed terminus — plumbed, kept, maintained; the descent's end | descent `deepen`, the §0 floor kept lit in-fiction |
| **The Records Hall** | Bethany / processor | inspection day, gauging, the grade read aloud from your real file | `processing_tier`, `_appraise`, grade reveal |

---

## B. ENCOUNTER / SYSTEM SCENES (state- or choice-triggered, not room-locked)

- **Breeding variations (13)** — each `_scene_*` becomes a cinematic breeding scene (single, oral,
  double, all-holes, bukkake, golden, offspring-breeds-you, spitroast, suspension, knot-train,
  fist, verbal-degradation, prolapse). Stockman/studs/Bethany drive; real `_gang`/insemination.
- **Procedures (≈21)** — the Parlour/surgery scenes, each `_proc_*`: pierce, brand, stim-implant,
  ring-fit, milk-port, one-way, cow-set, tail, fertility-implant, womb-tattoo, clit-hood,
  tongue-split, corset, clit-pump, neuter, sissify, tongue, latex, udder, rings, nugget. Real mods.
- **Dosing (≈14 drugs)** — a dosing scene: the dose administered, the come-up, the effect taking;
  the choice of how you ride it. Real drug effects.
- **Conditioning / hypno** — the Spiral Chair induction as full cinematic (settle→spiral→drone→
  deep→set→below); mantra-seating and the descent door as choices. Real triggers/regression.
- **Punishment / correction** — confession vs defiance → the sentence (sty / floor / line) → the
  aftermath (thank her vs silence). Real `punish`/`make_example`/`register_defiance`.
- **The fellow-resident arc** — the futa-conversion set-piece + shared scenes; she breeds you under
  Bethany's direction. Real cross-sire lineage, conversion persists.
- **Auction → Kept arc** — appraisal/block/gavel → Bethany buys → her evening/bed/morning →
  company (she sends for the fellow). Real ownership, laced devotion, the file.
- **Lineage loop** — your get mature into stock and are bred back to you; each delivery raises quota.
- **Events (≈10)** — facility set-piece events as cinematic interrupts with choices.
- **Manumission / earn-back** — the in-fiction earned exit; the long compliance record paying off.

---

## C. THE CONNECTIVE LAYER (replaces the blind room-cycle)
- A **scene-flow controller**: a scene resolves and offers the next step as choices (be moved,
  submit to be taken, the board says you're owed elsewhere) — the dread stays, the *clock* goes.
- The old `RealmCycleScript` auto-advance is retired in favour of scene handoff (machines/milking
  still tick on their own; the narrative no longer does).

## Build order (suggested, after Intake)
1. ✅ **Breeding Pens** (stockman + studs) — DONE. Next:
2. ✅ **Conditioning Cell** — DONE.
3. ✅ **Dairy** — DONE (the scene→cycle seam + the state-aware hook pattern).
4. **Marking Parlour** (procedures) + **Sanitation/Pigsty** (degradation).
5. **Showroom → Office/Kept arc** (the ownership through-line).
6. **Nursery/lineage**, **Deep Stock**, **Records/inspection**, **Events**, then the flow controller.
