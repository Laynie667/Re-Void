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
- ✅ **Dosing (`dz_*`, `scene dosing`)** — BUILT. The dose administered, the come-up, riding
  the effect; real `_dose` fires an actual drug from your pool. State-aware. In the hub.
- **Conditioning / hypno** — the Spiral Chair induction as full cinematic (settle→spiral→drone→
  deep→set→below); mantra-seating and the descent door as choices. Real triggers/regression.
- ✅ **Punishment / correction (`pn_*`, `scene correction`)** — BUILT. Confess/deny/silent →
  sentence (sty `filth` / floor `make_example` / line `punish`) → aftermath (thank=earn-back
  `gratitude` / refuse=review resets). Real punishment + earn-back. Bethany's disappointed register.
- ✅ **The Fellow arc (`fl_*`, `scene fellow`)** — BUILT. The tragic-intimate set-piece: your
  real continuity fellow (world.facility_fellow) is converted to futa at Bethany's direction
  (real `mark_fellow_futa`), dosed to a rut, and made to breed you as her mind fragments —
  real `company_use` (fellow-sired insemination + `fellow_cross_record`, lines crossed for
  good). State-aware (both-little framing). The bond is the handle AND the one mercy; §0
  floor kept lit for both of you. Branches: fear/brace/reach, watch/look-away, comfort/
  horror, take-her/hold-her, keep-her/grieve-her.
- ✅ **Seraphine's visit (`se_*`, `scene seraphine`)** — the facility↔post-office peerage; Seraphine
  as buyer; the only one Bethany opens to; the laced cum that can't own her; unbirthing carry-home.
  Real `seraphine_takes` ownership transfer. See design/seraphine_bethany.md.
- **Auction → Kept arc** — appraisal/block/gavel → Bethany buys → her evening/bed/morning →
  company (she sends for the fellow). Real ownership, laced devotion, the file.
- ✅ **The Carry (`pg_*`, `scene carry`)** — BUILT. The nested-passenger transfer: ride inside
  Seraphine, brought to Bethany; her womb (→ covered in Bethany's laced load) or her balls (→
  planted INTO Bethany). Real `world.passenger` (board/transfer/cover/eject) + the cum-effect
  rulings. §0 ejects from any host. See design/seraphine_bethany.md §7.
- **Lineage loop** — your get mature into stock and are bred back to you; each delivery raises quota.
- ✅ **The Fitting (`ft_*`, `scene fitting`)** — the most COMBINATION-aware scene: reads the full
  `_kit` (piercings / milk-port / gape-rings / latex / tail / brands / collar / clauses / body-
  states) and the prose AND the real effect change with every piece worn. A bare body gets a
  short scene; a fully-kitted one gets the works (port drained while gape filled while stim rides
  while latex sweats). New reusable `_kit(character)` + `_kit_inventory()` readers — the hook for
  item/piercing/port/state branching across ALL scenes from here.
- ✅ **The Rut (`ev_rut`, `scene rut`/frenzy/heat)** — BUILT. A marquee savor-event in the random
  dispatcher pool (now 5): the facility's seasonal frenzy — heat-dose run through the floor's air,
  pens thrown open, the whole hall dissolving into one red-lit writhing breeding-mass with no
  schedule, only rut. Real `_scene_allholes`. State-aware (preg/nugget/little), three opening
  routes (give in / ride the edge / fight toward a chosen body). §0 lit: a `the_word_rut` branch
  pulls you clean out of the frenzy at once — "the floor's frenzy can't touch the floor beneath it."
- ✅ **Events (`ev_*`, `scene events`)** — BUILT (4 to start, random dispatcher for freshness):
  the Buyer's Tour (real `_scene_single` + market interest), Quota Day (public tally; real
  `punish` on shortfall / climbing-bar), the Breeding Festival (real `_scene_bukkake` mass
  use), the Anniversary (Bethany's kept-dates; real `bethany_breeds` deepening claim). The
  freshness valve — more events drop into `_EVENT_OPENINGS` over time. In the hub.
- ✅ **Manumission (`mn_*`, `scene manumission`)** — BUILT. The IN-FICTION earned door (NOT the
  §0 floor): reads/drives the real release.py (terms / _unmet / petition / grant). Gated on
  scrip + standing + a LOW devotion cap ("you have to want it less than you do" — the wall
  Bethany works against). The two-doors contrast kept explicit throughout: her hard earned
  door vs the always-free §0 floor. Earned+press -> real grant (or earn-it-then-stay-freely).
- ✅ **The Rig / bondage (`bd_*`, `scene bondage`/rig/suspension)** — BUILT. Core-list bondage:
  strung up in the suspension rig — wrists, ankles, throat, spread and fixed — and kept helpless
  and used. Routes through a new `go_bound` effect (REAL navigation_locked + self_cmds_locked +
  forced_posture, all FACILITY_FLAGS) and the real `_scene_suspension` method. arrival → bound →
  after. State-aware (nugget needs no limb-cuffs / little / preg slung clear of the belly),
  kit-aware (pierced rings clipped into the frame; milk-port unlocks a hung-and-milked option).
  §0 lit hard: the steel is rated to hold a thrashing body all day AND to let go the instant the
  word is meant — "both at once; the only kind of rig worth trusting."
- ✅ **Bethany's Long Night (`bn_*`, `scene longnight`/night)** — BUILT. The savor-piece, the
  densest scene in the build: her triple facility-bred cock taken slow and whole over a whole
  night — the three stallion-flared heads seated one by one, the three hound-knots forced in with
  a *pop* and locked, the bulging belly, fucked past consciousness and waking still impaled and
  being bred, the laced DEVOTION load. Five beats (arrival→seat→knot→dark→after). Real
  `bethany_breeds` (holes=3 + devotion) fires at the knot and dark beats + deepen/devote.
  State-aware (preg = bred-again over the swell), kit-aware (gape takes the flares easy). §0 lit
  even here: a `the_word_knot` branch ends it instantly even knotted three ways (engine-verified
  clean) — "the knots hold against the world, never against you; the deeper I have you, the more
  carefully I hold the door." Surfaces in the hub once Bethany owns you.
- ✅ **The Take / CNC (`cn_*`, `scene cnc`/take/hunt)** — BUILT. Core-list consensual-non-consent,
  written as the scene where the §0 floor stops being mere safety and becomes the literal enabling
  beam: Bethany names BOTH lines explicitly up front — in-fiction your "no" is hers to ignore (the
  negotiated game), the OOC word is the one thing that always, instantly, un-grudgingly stops
  everything. frame → take → after. A `test_word` branch lets you prove the word stops her on a
  dime before anything begins; the `the_word` option at the take beat ENDS the scene mid-stream
  (engine-verified: clears pending + flags, no cn_after). The aftercare beat names the thesis out
  loud — "the cage is only as deep as the key is sure; the dread and the safety are married." Real
  deny_hold / facility _scene_single / devote.
- ✅ **The Wet Room / watersports (`ws_*`, `scene watersports`/wetroom/toilet/urinal)** — BUILT.
  Core-list watersports: kept as the facility's relief — urinal, drinking-station, golden-shower
  stock, bladder held full and ignored. Routes through REAL methods via the facility effect:
  `_toilet` (kind=gang — real urine to the fluid bank + bladder backing + filth marks) and
  `_scene_golden` (kind=scene), plus the real `filth` effect on close. arrival → use → after.
  State-aware (nugget perfect fixture / little wet-and-ashamed / preg still used). §0 lit hard: the
  trough holds for the facility, never against you — the word unfixes you and stands you up clean.
- ✅ **The Filling Station / cumflation (`cf_*`, `scene cumflation`/filling/pump)** — BUILT.
  Core-list cumflation: pumped/bred past full at a dedicated station to a litre-mark, then plugged
  to HOLD it — round, drum-tight, sloshing. Routes through the REAL inflation system via a new
  `go_cumflate` effect (add_inflation_volume bloats the inflatable zones the facility installs at
  intake + feeds the installed WombRoom; drained by tick AND the §0 reset, so never permanent).
  arrival → fill → held. State-aware (preg = filled over the get and faster; nugget tank; little),
  kit-aware (gape seats the plug easy; milk-port unlocks a "filled-and-milked closed loop" option).
  §0 lit hard: the plug holds for the facility but never against you — the word pops it and drains
  you free the instant you mean it.
- ✅ **The Doll Cabinet / dollification (`dl_*`, `scene doll`/dollify/cabinet)** — BUILT.
  Core-list dollification: sealed smooth into a latex/doll shell, made featureless and posable,
  kept and displayed as an OBJECT. Routes through a new `go_doll` effect (latex_sealed + optional
  sensory_hood + a posable posture — all FACILITY_FLAGS, floor-cleared). arrival → seal →
  displayed. State-aware (nugget already objectified, little a kept dolly, preg a display piece),
  kit-aware (already-sealed reads as a tighter *setting*). The seal-aware branch traps the person
  awake behind the smooth ("crueler — I like crueler"). §0 lit hard: the word splits the shell and
  stands you up a wanting person the instant you mean it — "a doll that chose to be mine."
- ✅ **The Kennel / petplay (`kn_*`, `scene kennel`/pet/puppy/petplay)** — BUILT. Core-list
  petplay: you ARE the pet (collared, crawling, named to a pet, trained, kept) — distinct from
  the Pens (bred BY animals). Routes through the REAL conditioning pet-imprint via a new `go_pet`
  effect (pet_type + pet_trigger_sources + forced_posture/body_language — all FACILITY_FLAGS, so
  the floor clears every bit). arrival → train → kept. State-aware (nugget = limbless lap-pet,
  little = already half-there, preg = bred bitch); kit-aware (already-collared reads). The
  warm-ownership branch lets you be *hers* specifically. §0 lit hard: the kept beat has Bethany
  state plainly the word stands you up a person any second, never held against you — "a pet by
  choice, not a thing I caught."
- ✅ **The Accounting (`iv_*`, `scene accounting`/inventory/stock/file)** — BUILT. The
  combination payoff: Bethany takes possessive personal stock of what she's MADE, the ledger
  GENERATED LIVE from your actual `_kit` + state (`_kit_ledger` composes every piercing / port /
  gape / brand / collar / clause + little/preg/nugget into one read-back). Distinct from Records
  (institutional grade) — this is intimate ownership. A bare body reads as a blank file with room
  to write; the addition beat reaches combination-aware for the next missing line (ring → port →
  collar → brand → "finished work"). §0 lit hard: the floor-ask branch has Bethany state plainly
  that one word wipes the whole file, instantly, never gated — "that's what makes the rest fair."

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
- ✅ **Auto-hub on close**: with `scenemode on` (sets `scene_autohub`), a scene's `end` auto-poses
  the facility hub — handoff is seamless, no manual `whereto`.
- TODO (polish): verify under `scenemode on` that milking still INITIATES via the Dairy scene
  (the old cycle was one initiator) — hand-test in-game.

## Build order (suggested, after Intake)
1. ✅ **Breeding Pens** (stockman + studs) — DONE. Next:
2. ✅ **Conditioning Cell** — DONE.
3. ✅ **Dairy** — DONE (the scene→cycle seam + the state-aware hook pattern).
4. ✅ **Marking Parlour** + ✅ **Sanitation/Pigsty** — DONE. Next:
5. ✅ **Showroom** + ✅ **Office/Kept** — DONE (ownership through-line complete). Next:
6. ✅ ALL 14 ROOMS BUILT (Nursery/Deep Stock/Holding/Floor/**Records** done). Remaining: **Events**, then the flow controller.
