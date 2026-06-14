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
| **Holding** | a holding handler | ✅ **BUILT** (`hd_*`, 4 beats; the dread-of-waiting + first inventory) | catalogue/prep, state-aware |
| **Processing Floor** | a floor handler | ✅ **BUILT** (`pf_*`, 4 beats; processed-in-public + routing) | real `_scene_single` use; the routing hand-off |
| **Breeding Pens** | the **stockman** + named studs + animals | ✅ **BUILT** (`bp_*`, 8 beats; stud/pack/machine branches) | `_gang`/`_scene_knottrain`, lineage, quota |
| **Conditioning Cell** | Bethany (recorded voice) + Spiral Chair | ✅ **BUILT** (`cc_*`, 8 beats; sink/resist, mantra, the descent door) | real `mantra_set` trigger, `deepen` (conditioning+regression), suggestibility |
| **Dairy** | the dairy hand | ✅ **BUILT** (`dy_*`, 5 beats; the scene→cycle SEAM) | real `_do_milk` at quota; then hands off to the retained milking cycle; state-aware (little/pregnant/nugget hook) |
| **The Pigsty** | the custodian + the boar/pigs | ✅ **BUILT** (`ps_*`, 6 beats; bestiality, STATE-AWARE nugget/preg/little) | real `_gang` sty-cover, degradation |
| **Sanitation Block** | the custodian + the queue | ✅ **BUILT** (`sb_*`, 4 beats; wall/frame, state-aware) | real `_scene_bukkake` anonymous use |
| **The Showroom / Buyers' Gallery** | Bethany + bidders | ✅ **BUILT** (`sw_*`, 5 beats; state-aware; reach-for-her vs look-away gavel) | real `_appraise`, `bid_up`, `bethany_buys` ownership transfer |
| **The Nursery** | the nurse | ✅ **BUILT** (`nu_*`, 6 beats; regression/nursing/Little Box/lineage, state-aware) | real `go_little` regression, brood-aware lineage loop |
| **The Marking Parlour** | the **marker** | ✅ **BUILT** (`mp_*`, 5 beats; brand/rings/ink branches) | real `_proc_brand`/`_proc_cowset`/`_proc_womb_tattoo` |
| **Bethany's Office** | Bethany | ✅ **BUILT** (`ko_*`, 5 beats; the Kept payoff, state-aware) | real `bethany_breeds`, `file_read`, devotion |
| **Deep Stock** | Bethany + machines | ✅ **BUILT** (`ds_*`, 5 beats; the sealed terminus, §0 floor heavily lit) | real `deepen`; the never-locked door kept explicit |
| **The Records Hall** | Bethany / processor | ✅ **BUILT** (`rh_*`, 4 beats; inspection day, the real grade verdict) | real `grade_reveal` (processing_tier + appraisal off your file) |

---

## B. ENCOUNTER / SYSTEM SCENES (state- or choice-triggered, not room-locked)

- **Breeding variations (13)** *(pigsty/sanitation now demo the reusable `_state_tags` hook)* — each `_scene_*` becomes a cinematic breeding scene (single, oral,
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
- ✅ **Seraphine's visit (`se_*`, `scene seraphine`)** — the facility↔post-office peerage; Seraphine
  as buyer; the only one Bethany opens to; the laced cum that can't own her; unbirthing carry-home.
  Real `seraphine_takes` ownership transfer. See design/seraphine_bethany.md.
- **Auction → Kept arc** — appraisal/block/gavel → Bethany buys → her evening/bed/morning →
  company (she sends for the fellow). Real ownership, laced devotion, the file.
- **Lineage loop** — your get mature into stock and are bred back to you; each delivery raises quota.
- ✅ **The Fitting (`ft_*`, `scene fitting`)** — the most COMBINATION-aware scene: reads the full
  `_kit` (piercings / milk-port / gape-rings / latex / tail / brands / collar / clauses / body-
  states) and the prose AND the real effect change with every piece worn. A bare body gets a
  short scene; a fully-kitted one gets the works (port drained while gape filled while stim rides
  while latex sweats). New reusable `_kit(character)` + `_kit_inventory()` readers — the hook for
  item/piercing/port/state branching across ALL scenes from here.
- **Events (≈10)** — facility set-piece events as cinematic interrupts with choices.
- **Manumission / earn-back** — the in-fiction earned exit; the long compliance record paying off.

---

## C. THE CONNECTIVE LAYER (replaces the blind room-cycle) — ✅ BUILT (core)
- ✅ **Scene-flow hub** (`facility_hub`, `whereto`/`route`): between scenes you're routed by
  CHOICE, not a clock. State-aware menu (only what fits your standing shows; office/seraphine
  gate on ownership), each option launches a real scene; "let the board decide" routes at random.
- ✅ **`scenemode on/off`** toggle: an opt-in early-return guard on BOTH cycle `at_repeat`s
  (FacilityScript + RealmCycleScript). ON = the narrative timer-cycle stops auto-advancing /
  dragging you room to room; you drive via `scene`/`whereto`; machines, milking sessions, arousal
  and engorgement keep ticking on their own scripts. Default OFF (safe) — flip live to test.
  §0 floor untouched either way.
- TODO (polish): auto-pose `facility_hub` at a scene's close (so handoff is automatic, not a
  manual `whereto`); verify under `scenemode on` that milking still INITIATES via the Dairy scene
  (the old cycle was one initiator) — hand-test in-game.

## Build order (suggested, after Intake)
1. ✅ **Breeding Pens** (stockman + studs) — DONE. Next:
2. ✅ **Conditioning Cell** — DONE.
3. ✅ **Dairy** — DONE (the scene→cycle seam + the state-aware hook pattern).
4. ✅ **Marking Parlour** + ✅ **Sanitation/Pigsty** — DONE. Next:
5. ✅ **Showroom** + ✅ **Office/Kept** — DONE (ownership through-line complete). Next:
6. ✅ ALL 14 ROOMS BUILT (Nursery/Deep Stock/Holding/Floor/**Records** done). Remaining: **Events**, then the flow controller.
