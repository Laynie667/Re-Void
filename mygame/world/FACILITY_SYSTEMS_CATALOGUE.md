# The Facility — Systems Catalogue

A survey of **every** system that makes the facility/realm run: its purpose, key
functions, the mechanics it owns, where it overlaps others (redundancies), and where
it could improve. Companion to `FACILITY_AUDIT.md` (which tracks bugs/conflicts). For
your review. Maintained by the build loop.

Legend: **fn** = function/method · **st** = db state it owns · ⚠ = redundancy/overlap ·
→ = improvement idea.

---

## 1. Realm & world  (`world/realm_build.py`)
- **Purpose:** dig the disconnected grid realm, furnish it, gate entry/return, tear it down.
- **fn:** `build_realm` (full dig), `facility_upgrade` (in-place idempotent migration — adds
  missing rooms/exits/placards/album/office-anatomy), `teardown_realm`, `escape` (OOC floor:
  home+purge), `force_clear` (bulletproof per-attr reset), `reveal_return` (gate the way home),
  `_furnish` (zones/tokens/mechanics/furniture/NPCs/placard), `_install_mechanic`.
- **st:** `db.realm` (rooms/words/return_wp), area tags, `_REALM_TAG`.
- **Data:** `_ROOMS` (14: lobby, holding, floor, pens, conditioning, dairy, pigsty, restroom,
  showroom, **gallery**, nursery, parlour, office, deepstock), `_EXITS`, `_ROOM_ZONES`,
  `_ROOM_FURNITURE`, `_ROOM_NPCS`, `_ROOM_MECHANICS`, `_ROOM_AMBIENT`, all the NPC trigger trees.
- **Buyers' Gallery** (behind the showroom's one-way glass): tiered viewing booths (`seat` mech),
  a live **bid panel** zone, the gallery host (`_HOST_TRIGGERS`) + the buyers. Players sit, watch a
  lot worked on the showroom block through the mirror, and price her. Drives the `bid` verb
  (`facility_commands.CmdBid`): `bid <lot> [amount]` reads/raises `db.high_bid`/`high_bidder`
  off the real `_appraise` floor; an owner closes with `process <lot> buy`. The high bid carries
  *through the glass* — the lot is reposed but never told her number.
- **Gallery `tip` (`facility_commands.CmdTip`):** the gallery isn't only passive. `tip` /
  `tip <what>` (milk/breed/dose/pierce/condition/grow/ring/pose) resolves the adjacent showroom +
  the facility-active lot on the block (`_showroom_lot`), finds her cycle script (`_lot_script`),
  and fires the **same real systems** `process` uses (`_start_milking`/`_gang`+`do_inseminate`/
  `_dose`/`add_piercing`/`add_conditioning`/`_proc_udder`/`_proc_rings`) on her, broadcasting to
  the showroom (visible), the gallery (buyers watching through glass), and the lot (felt, source
  hidden). Demands logged to `db.gallery_demands` (reset-spec'd). CNC-on-demand by an audience she
  can't see — and every effect routes through a real subsystem, nothing faked.
- **Gallery ↔ cycle integration (`_showroom`/`_sell`/`_gallery_of`):** the gallery is now live
  *inside the real cycle*, not just on demand. When a lot hits her **display** phase, `_showroom`
  poses her on the block (`body_language`), and `_gallery_of(room)` cues the adjacent gallery —
  buyers seated behind the glass get an "open for viewing" line with her floor price + any standing
  bid + the `bid`/`tip` prompt. A live buyer present raises the gavel chance (+0.25). At the gavel,
  `_sell` now honours a **player's standing `high_bid`** — the high bidder actually *wins* her at
  their price (beating Bethany's standing bid), the gallery's told, and the auction state is cleared.
  Player bids/tips have real consequence in the cycle now.
- **NPC clientele bidding (`_npc_bidding` + `_NPC_BIDDERS`/`_NPC_BID_LINES`/`_NPC_OUTBID_PC`):**
  "both, layered" audience — the booths are never empty. On a display visit a round of NPC buyers
  (a breeding concern, a kennel syndicate, the dairy interest, Bethany herself, …) bid the lot up
  on their own, climbing `high_bid` and narrating into the gallery; an NPC can **top a live player's
  standing bid** (they must re-`bid` to hold her), and Bethany bids 1.6× hard on ones she's claimed.
  Gavel logic is fair to a present player: if the live buyer holds the top bid the hammer drops
  (0.85) and they win; if they're present but outbid/idle it eases off (0.15) to give them ticks to
  act; empty house resolves the NPC auction at 0.30. Bethany winning via the bid path sets
  `bethany_owned`. Net: a self-running auction players can jump into and win.
- **Live timed gavel (`_open_auction`/`_auction_step`/`_auction_gavel` + `_GAVEL_COUNTDOWN`):** a
  display now *opens* a real ~80s bidding window (via `evennia.utils.delay`) instead of resolving
  instantly — staged NPC rounds at 20/40/58/70s climb the price with a "going once / going twice"
  countdown into the room + gallery, then `_auction_gavel` at 80s auto-resolves to the standing high
  bidder (player or NPC) or passes the lot in if nobody bid. A watching player can `bid`/`tip` the
  whole window to steal her at the wire. **Defensive:** falls back to the instant gavel if `delay`
  isn't importable; every callback re-checks `auction_open`/`facility_active`/ownership and that she
  hasn't been dragged off the block (auction lapses if so), all wrapped in try/except.
  **OOC-floor-safe:** `auction_open`/`auction_floor` are in the reset spec, so a purge mid-auction
  makes the pending gavel a silent no-op. Cycle interval is 180s, so the 80s window fits one visit.
  → *Needs a live test* (delay timing + reload behaviour can't be verified in-sandbox).
- **The economy — scrip (`world/economy.py` + `scrip` command):** the house currency, finally giving
  the block real weight. State lives on real db: `db.facility_credits` (int) + `db.facility_ledger`
  (capped list of {when, stamp, delta, balance, reason}). API: `get_balance`, `add_credits`,
  `spend_credits` (returns (ok, balance), never blocks anything but a purchase), `can_afford`, `earn`
  (per-source EARN table), `statement` (Bethany-voiced payslip/account), `clear_wallet`. **Stock open
  at 0 and earn scrip off their own bodies** — `at_repeat` credits `earn(char, phase)` every beat
  (milk 45 / breed 80 / condition 20 / display 30 / punish 10 / …), itemised on a statement she can
  read but (this pass) can't spend; **members open at a 5000 float** and earn `attend` scrip when
  present in the gallery as a lot opens. **Spending is wired into the block:** `tip` now charges a
  per-demand fee (`_TIP_COST`, 40–150) up front — refunded if the action no-ops (nothing to pierce) —
  and credits the lot a ¼ cut ("paid for her own use"); `bid` requires `can_afford` and stamps
  `high_bidder_id`, and `_sell` **charges the winning player** their bid at the gavel (house carries
  any shortfall) while crediting the lot a pittance `sale_cut` of her own price. **OOC-floor-sacred:**
  `spend_credits`/`can_afford` are never on the escape path — the door is free at any balance, even in
  debt; the module docstring states this as an invariant. Wallet keys (`facility_credits`/
  `facility_ledger`/`high_bidder_id`) are in the reset spec, so a purge wipes the account with the
  rest.
- **The commissary — her spend-sink (`buy`/`commissary` command):** closes the stock side of the
  economy. She spends the scrip her own body earned on the only things it buys *inside* the Process,
  each routed through a real system: **relief** (350 → `compliance._grant_climax`, a granted climax
  that deepens conditioning — the leash she pays for), **rest** (250 → `db.line_pass`, consumed in
  `at_repeat` to skip a beat off the line), **ease** (180 → drops `db.arousal`), **mercy** (300 →
  clears defiance + sets `db.punish_shield`, consumed in `_choose_destination` to buy off the next
  few sty trips). Stock-only; the help + every line repeats that none of it buys the door — the OOC
  exit is always free, even in debt.
- **Selling the get (`_sell_get`/`_appraise_get` + `_GET_SALE`):** the lineage cashed out. ~40% of
  showroom visits the lot on the block is one of her **matured get** (a real `FacilityScion` from
  `offspring_roster`), not her — appraised off generation/species + dam's grade, bid up by the house,
  sold to an NPC buyer (or Bethany), then **a breeder's cut is credited to the dam** (paid for her
  own child) and logged as a real `record_mark`; the get is pulled from the bred-back roster and
  `delete()`d (sold away). She's made to watch. Incest breeds them, commerce disperses them, she's
  paid for both.
- **The office books (`vault`/`books` command):** Bethany's accounting. Shows the full statement +
  `economy.totals` (paid in / spent / on the books) and a Bethany-voiced reckoning of what she spent
  the stock's own earnings on ("on you, on more of you"). Office-gated for stock (the number is hers
  out on the line) — closes by reminding her not one credit opens the door.
- **The house treasury + reinvestment (`economy.house_*`/`skim`/`UPGRADES`/`_try_reinvest`):** the
  skims are real money now. A per-instance treasury (`db.facility_house` + `db.facility_house_ledger`,
  anchored on the resident) takes a `HOUSE_CUT` (25%) of every sale, get-sale, tip, and commissary
  relief. The house doesn't hoard it — `_try_reinvest` (fired on every sale + each office visit)
  auto-buys the cheapest affordable item off the `UPGRADES` ladder (studs/cups/line/suite/bounty/
  showroom/pharmacy; each owned level dearer than the last) and `_apply_upgrade` applies a **real
  live effect**: studs → `breeding_quota` +1/species; line → cycle `interval` ×0.85 (floor 60s) via
  `restart`; suite → `cond_bonus` (deeper conditioning in `at_repeat`); cups → `milk_bonus` (yield
  scrip on milk beats); showroom → `sale_bonus` (price ×(1+0.15·L) in `_appraise`); bounty →
  `get_bounty`. The burn she funds accelerates the burn against her. Logic tested standalone.
- **Bounties on the get (`get_bounty` + `_pay_get_bounty`):** the `bounty` upgrade posts a standing
  bounty; `_mature_get` pays it out of the treasury into her account on every maturation — she's paid
  for producing the line that breeds her, funded by the house she filled.
- **Polaroids on every sale (`_file_polaroid` + `_POLAROID_CAPS`):** parlour-style — each sale of her
  or her get files a dated polaroid (cold catalogue captions: shot from behind, face turned, cropped)
  to `db.facility_polaroids`.
- **The records hall (`records`/`wall`/`lineage` command):** renders her line — get dropped by
  species, how many on the roster / grown and bred back / sold off — plus the polaroid wall, dated.
  A readable "hall" without grid surgery. `vault` now also shows the **treasury** (taken in /
  reinvested / on hand) and the **upgrades bought with it**, in Bethany's voice.
- **Debt + consensual indenture (`economy` debt API + `tab`/`indenture` commands):** members can now
  run **negative**. `spend_credits(..., allow_debt=True)` carries a marker down to `DEBT_FLOOR`
  (-8000); the gavel uses it — win a lot you can't cover and the house carries the difference as real
  arrears. `in_debt`/`debt_amount`/`indenture_due` (called at `INDENTURE_AT` -2500)/`clear_debt`. The
  `tab` command reads your arrears; `indenture`/`indenture confirm` lets a player **consensually** sign
  themselves over as stock (`_do_indenture`: role flip, real `record_mark`, conditioning seed, debt
  cleared, cycle started if a realm context exists). **Consent floor for third parties:** indenture
  *never* happens automatically and *never* without the player's own `confirm` — the house cannot put
  anyone on the line over a debt; only they can. And it is never the OOC door: `escape`/`force_clear`
  free an indentured member instantly at any balance. `indentured` is in the reset spec.
- **The Records Hall (new realm room `records` in `realm_build.py`):** a 14th room — lineage wall,
  the open ledger, and a tall **appraisal mirror with a cataloguing stool** (a real `seat` zone
  mechanic install). Data-driven, so `build_realm` *and* `facility_upgrade` create it + its exits
  (`floor`/`nursery`/`office`) automatically, with a registrar NPC and a readable
  **`FacilityLedgerBoard`** furniture object (renders the looker's own live account/statement/debt +
  lineage). Cycle phase `_records_hall` (wired into dispatch, `_choose_destination` — weighted up by
  a line on file or a debt — and `_REALM_SEQUENCE`): she's sat at the mirror, read her own valuation/
  account aloud, the lineage advanced, the books reinvested, and conditioned by *knowing her number*.
- **The ledger-tattoo (player zone install, `_ledger_tattoo`):** a real freeform mark on her hip that
  displays her running total (get dropped + current valuation), inked once and refreshed in place
  each records visit — the body kept as its own legible account.
- **New contract clause `ledger` (Bethany):** "Your account is mine; what you owe me, you owe with
  your body." Enforced: sets `bethany_ledger_bond`, seeds a standing debt marker (`allow_debt`), inks
  the ledger-tattoo.
- **New drug `arrears`:** laces being used with debt-relief — she reads being worked as *paying
  down* a balance that only ever climbs. Pairs with the hall and the clause.
- **Two new upgrades on the ladder:** `archive` (richer get-bounty + standing) and `collections`
  (markers called harder — `collections_level`), both honored in `_apply_upgrade`.
  → *Backlog (deliberately next):* a live shakedown of the new room/mechanics/indenture on the running
  engine; auto-starting an indentured member's *own* cycle when there's no realm context; the records
  hall's NPC dialogue tree; a true shared house-account object.
- **Real room installs (data-driven, `_ROOM_ZONES` mechanic specs):** the rooms now *do* what they
  describe. Floor: `milkstall` (real `milk` machine install) + `matingbench` (`dildo` cycle); pens:
  `machine` breaking-saddle (`dildo`); restroom: the glory-hole `wall` is a real `dildo` install.
  `facility_upgrade` step 1a **merges new zones + installs into existing rooms**, so older realms get
  them too.
- **Quota spine (`compliance.quota_status` + `quota` command + `FacilityQuotaBoard`):** what she owes
  before rest — breeding/milk quotas + arrears, shape-tolerant (handles both breeding_quota shapes).
  A `quota` command and a live floor board that reads the looker's own owed.
- **Two curses (`_impose_curse`/`_tick_curses`):** laid in during deep conditioning, honored every
  beat. `line_remembers` (a matured get sharing her room breeds its dam unprompted — the incest loop
  self-driving) and `never_empty` (any unfilled beat spikes ache + arousal until she's filled).
- **Two Bethany clauses:** `tithe` (a tenth of every earn skimmed to the house, honored in the earn
  hook) and `heir` (one get per litter pulled and kept by Bethany — honored in `_mature_get`, skipped
  by both sale paths).
- **Live get-auctions (`_post_get_lot`/`_get_bid_step`/`_get_gavel`):** a grown get goes up as a
  *live timed lot* players can `bid` and steal at the wire (isolated trio, reuses `_npc_bidding`/
  `_GAVEL_COUNTDOWN`/the gallery bid path); the dam is credited her cut + made to watch, the house
  skims, a polaroid's filed, the get removed from the roster and deleted (sold away). `_showroom`
  posts live when a gallery is present, else the instant `_sell_get`.
  → *Backlog:* fix the two-shape `breeding_quota` conflict (see AUDIT); live test of installs +
  get-auction; the deferred `_drug`/item/furniture menu in `FACILITY_IDEAS.md`.
- ⚠ **Two reset paths:** `force_clear` here and `run_facility_reset` in `facility_build.py`
  must be kept in lockstep — every new persistent attr has to be added to both. Real
  maintenance burden and the single biggest source of "forgot to clear X" risk.
  → Extract a single `FACILITY_STATE` spec (attr → default) both paths consume.

## 1b. Manumission — the IN-FICTION escape  (`world/release.py` + `release` cmd)
- **Purpose:** the diegetic door out of the Process, distinct from the OOC floor. Bethany's to
  price, dangle, honor, gouge, and revoke. The "available but not abusable" texture, in fiction only.
- **fn (Bethany, via the `manumit` ADMIN command — `cmd:perm(Developer) or perm(Admin)`, so players
  can't loophole it):** `offer(stock, scrip, devotion_max, standing_min, note, by)` names/edits the
  price; `gouge(add_scrip, …)` raises it; `grant(stock)` honors it → drives `realm_build.reveal_return`
  (opens the held return word); `revoke(stock, regouge=)` slams it shut (pulls the return-wp
  `realm_address` back to None) + can re-price; `withdraw` clears the offer. Command:
  `manumit[/offer|/gouge|/grant|/revoke|/withdraw] <target> [= <scrip> dev N stand N note…]`.
- **fn (unit, via the `freedom` cmd — keyed `freedom`, NOT `release`, which the restraint system owns):**
  `status` (price + met/unmet conditions), `petition` (`freedom ask`), `pay` (`freedom pay` — spends
  REAL scrip via `economy.spend_credits`; conditions must be met; paying does NOT open the door, only
  Bethany's `grant` does — the wait is the point).
- **st:** `db.release_terms` {offered, scrip, devotion_max, standing_min, note, set_by, paid, granted}.
  Reads real `bethany_devotion` / faction `get_standing` / scrip balance. Cleared by BOTH reset
  paths (`release_terms` added to `facility_state` defaults + `force_clear`'s None-list) — a purge
  wipes any pending/granted release with everything else.
- **§0:** every message reprints the floor reminder; nothing here gates `escape`/`force_clear`/purge.
  Commissary scrip still never buys the door (unchanged); manumission is the only in-fiction door.

## 2. The cycle  (`typeclasses/facility_script.py` · `RealmCycleScript`)
- **Purpose:** the phase machine that drags her room-to-room and runs each room's scene.
- **fn:** `at_repeat` (drive), `_choose_destination` (handler-weighted next room),
  `_drag` (relocate + narrate), `_mature_get` (lineage), and the phase scenes: `_do_milk`,
  `_dose`, `_procedure`, `_pen_breed`, `_hypno`, `_dairy`, `_toilet`, `_sty`, `_showroom`,
  `_office`, `_deepstock`, `_nurse`, `_parlour`, plus `_grow_udder`, `_made_to_beg`,
  `_devote`, `_impose_clause`, `_sell`, `_demote_staff`, `_facility_event`.
- **st:** `phase_index`, `orifice_zone`.
- **Phases:** milk / breed / condition / display / toilet / punish / show / owned / mark /
  deep / nurse. **NPCs:** `FacilityAttendant`, `FacilityBeast`, `FacilityScion`.
- → `_choose_destination` weights are inline magic numbers; a small table would be tunable.
- → The base `FacilityScript` (single-room rig) and `RealmCycleScript` share huge pools —
  fine, but the single-room path is now largely superseded by the realm. ⚠ possible to retire.

## 3. Conditioning  (`world/conditioning.py`)
- **Purpose:** the brokenness meter + staged threshold effects.
- **fn:** `add_conditioning` (suggestibility-scaled), `deepen_on_climax`, `_apply_thresholds`,
  `get/_refresh` stage. **st:** `conditioning`, `conditioning_applied`. 9 thresholds
  (floor→speech→trigger→designation→name→permanent→doll→identity→lockself→imprint).

## 4. Binding effects  (`world/binding_effects.py`)
- **Purpose:** the central effect engine items/contracts/collars fire.
- **fn:** `apply_effects` / `remove_effects` (~30 effect keys), `install_trigger` +
  `_check_installed_triggers` + the `_inst_*` response handlers (kneel/beg/orgasm/blank/
  obey/freeze/leak/recite), `passive_tick` (stim + posture, ridden by the milk-gland script),
  `check_say_allowed`/`check_trigger`/`check_navigation_allowed`/`check_anti_clothing`.
- **Effect keys:** auto_consent, lock_navigation/self_cmds/self_remove, block_endcycle,
  orgasm_denial, continuous_stimulation, arousal_floor, forced_posture, exhibition,
  anti_clothing, broadcast_sensation, speech_filter, install_triggers, conditioning_on_wear,
  suggestibility, lactation_primer, forfeit_name, lock_conditioning, breeding_quota,
  required_honorific, compliance_threshold, milk_quota, cum_receptacle, mark_signed,
  realm_cycle, body_processing, perpetual_heat, pet_triggers, animal_sleeve.

## 5. Breeding, holes, marks  (`world/gang_breeding.py`)
- **fn:** `gang_inseminate` (deposit + quota + lineage), `record_use`/`add_gape`/
  `hole_capabilities`/`gape_word` (hole training), `record_mark` (freeform + board),
  `add_piercing` (real `PiercingItem`), `make_animal_sleeve`/`scent_mark`/`mucus_plug`/
  `apply_filth`/`clear_animal_sleeve`, `_birth_offspring` (spawns get; `FacilityScion` for
  the bethany line), `animal_holes`, quota helpers.
- ⚠ **Marks stored twice:** `db.facility_brands` (legacy strings) *and* real freeform items
  (`FreeformManager`). `record_mark` writes both; `board` reads facility_brands, `marks`
  reads freeform. → Pick freeform as canonical; keep facility_brands as a thin cache or drop.
- ⚠ **`offspring_progress` (legacy abstract counter)** coexists with the real pregnancy
  system; `_maybe_offspring` is now a fallback, and the BROOD drug still bumps the old
  counter. → Retire `offspring_progress`/`_maybe_offspring` once pregnancy is confirmed stable.

## 6. Pregnancy & lineage  (`world/pregnancy.py`)
- **fn:** `is_fertile`/`is_pregnant`, `on_bred`, `conceive`, `accelerate`, `gestation_tick`
  (belly stages), `deliver` (litter via `_birth_offspring` + quota raise + lactation), `clear`.
- **st:** `pregnancy`, `cycle_day`, `belly_desc_backup`, `pregnancy_belly`. Litter sizes per
  species incl. `bethany`. ⚠ belly desc backup is its own dict (see §13 zone-backup overlap).

## 7. Compliance & punishment  (`world/compliance.py`)
- **fn:** `register_defiance` (docility-suppressed), `punish`, `register_compliance` +
  `_grant_climax` (the relief leash), `check_earn_back`, `forfeit_freedom`,
  `penalize_quota_shortfall`. **st:** defiance, compliance_streak, freedom_forfeited,
  compliance_threshold.

## 8. Factions / grade / title  (`world/factions.py`)
- **fn:** `add_standing`, `get_facility_tier`, `_apply_facility_title` (ownership-wins),
  `seed_facility_title`. **st:** `db.factions`, title slots, `facility_grade`,
  `facility_owner`. 6 grade tiers. ⚠ title suffix written by grade/sale/ownership — resolved
  by the ownership-wins rule.

## 9. The mind  (`typeclasses/mind_state_item.py`)
- **fn:** `render` (the read-out), `compute_docility`, `tick` (withdrawal/craving/drift),
  `refresh`, `find_mind_item`. Installed on a real `mind` zone.
- ⚠ **State-view overlap** with the `board` command and `FacilityBoard` furniture. Now
  intentional/tiered: `board` = staff dossier (canonical, full), mind zone = in-world body
  read-out (`look <her> mind`), board furniture = the wall rendering of `board`. Documented,
  not accidental — but worth keeping deliberately in sync.

## 10. Body systems  (engaged, not owned by the facility)
- **Production** (`production_item.py`, milk glands), **WombRoom** (flood/seal/meat-toilet),
  **Inflation** (cumflation/capacity), **BodyMod** (breast/penis size, `_grow_udder`),
  **arousal_script** (floor + climax), **heat_script** (perpetual heat), **GlobalFluidBank**.
  Installed by `facility_build.provision_body` on signing; tracked on `db.facility_items`.

## 11. Facility implants  (`typeclasses/facility_implants.py`)
- `MilkPortItem` (nipple zone + duct + force-feed inflation), `GaugeRingItem` (one-way
  membrane), `CowRingSet` (heavy cow piercings), `BethanyCollar` (owned collar). Each creates
  its own default zone where needed; tracked for teardown; item-created zones in
  `db.facility_created_zones`.

## 12. Bethany  (`typeclasses/bethany_script.py`)
- **fn:** `provision_bethany` (multicock + cum/piss production), `BethanyScript` (chance
  visits, room-aware, gates the cycle via `bethany_busy`, climax deposits + breeds every hole
  + `bethany_deposit_effect` laced devotion), `_spawn`/`_mark_owned`. Office Bethany is a
  static NPC; visit Bethany is spawned/despawned. ⚠ possible to have 2–3 Bethanys in one room
  momentarily (see AUDIT).

## 13. Intake  (`typeclasses/intake_script.py`)
- The lobby driver: the screen subliminal squeeze, dawdle-worsens-contract, suggestibility
  trigger, idle forced-sign, the door opening on signing.

## 14. Commands  (`commands/facility_commands.py`)
- `board`/`quota` (the dossier — now canonical), `process` (the witness/staff verb: ~25
  actions), `facilityreset` (`/force`,`/purge` — the OOC floor command), `standing`, and the
  agency verbs `present`/`beg`/`thank`/`submit`/`struggle`/`mount`. **Furniture:**
  `FacilityFurniture`/`FacilityBoard`/`FacilityPortfolio`.

## 15. Content data (deep pools)
- **Drugs (14):** swell, yield, sensitize, capacity, brood, compliance, bimbo, dependence,
  estrus, lactation, solvent, cumslut, forget, devotion.
- **Procedures (15):** pierce, brand, stim_implant, ring_fit, milk_port, tail, fertility_
  implant, tongue, womb_tattoo, clit_hood, latex, udder, rings, cowset, oneway.
- **Events (10):** inspection, open_house, culling, audit, buyer, restock, breeding_demo,
  conditioning_broadcast, hose_drill, milking_parade.
- **Contract:** 14 visible + 29 hidden clauses (`facility_build`) + Bethany's 6 personal
  clauses. **Scene pools:** dozens, 3–6 variants each, brace-scanned safe.

---

## Cross-system redundancies (catalogued)
1. ⚠→✅ **Two reset paths** (`force_clear` / `run_facility_reset`) — **mitigated.** New
   `world/facility_state.py` (`FACILITY_FLAGS`, 86 flat flags, + `apply_reset_flags()`) is the
   single source of truth; both paths now call it (after consuming the name/title backups), so
   a new flag added to the spec is cleared by both automatically. The old per-attr loops remain
   as belt-and-suspenders and can be trimmed later. Also addresses redundancy #6. *(§1)*
2. ⚠ **Marks stored twice** (`facility_brands` strings + freeform items). *(§5)*
3. ⚠ **`offspring_progress` legacy** vs the real pregnancy system. *(§5/§6)*
4. ⚠ **Three state-views** (`board` / mind zone / board furniture) — now tiered & deliberate. *(§9)*
5. ⚠ **Zone-desc backups per-system** (sleeve / belly / item `prev_nude`) — different zones
   today, but three mechanisms doing one job. *(§6/§11)*
6. ⚠ **~60 flat `db.*` flags** — no namespace; ties into reset-sync risk. *(§1)*
7. ⚠ **Single-room `FacilityScript`** largely superseded by the realm cycle. *(§2)*

## Improvement backlog (by payoff)
- ✅ **DONE — unify the two reset paths** behind one spec (`world/facility_state.py`). Kills
  redundancies 1 & 6 and the "forgot to clear X" class. *Next on this thread:* retire the now-
  redundant per-attr clear loops in both paths (safe once the spec is confirmed live), then
  retire `offspring_progress` (3).
- **Medium:** make freeform the canonical mark store, `facility_brands` a derived cache (2).
  Unify zone-desc backups behind one helper (5).
- **Low / polish:** dedupe Bethany NPCs (AUDIT); table-drive `_choose_destination` weights;
  per-NPC `rp_name` aliasing; retire the single-room rig if unused (7).

---

# PART B — the wider game (non-facility systems)

A survey of the ~45 command modules + core typeclasses outside the facility, grouped by
area, with overlap/improvement notes. (Inventoried by size + module purpose.)

## B1. Character & identity
- `character_commands.py` (4.4k lines — the biggest module: name/desc/outfit/wardrobe/mood/
  voice/scent/title/sheet/consent/block, wear/remove/insert), `chargen.py`, `bio_commands.py`,
  `prefs_commands.py`. → The size of `character_commands` suggests it could be split by concern
  (appearance vs outfit vs identity vs consent) for maintainability.

## B2. Roleplay & speech
- `rp_commands.py` (say/pose/emote/look/whisper/mutter/aside/ooc/shout + consent-gated speech),
  `social_commands.py` (the directed social/intimate emote table), `scene_commands.py`,
  `rp_tools_commands.py`, `comms_commands.py` (tell/page/reply/channels), `proximity_commands.py`
  (approach/withdraw/beside/aside/prox). ⚠ **`aside` collision** (rp vs proximity — see AUDIT
  §1d). ⚠ speech verbs also exist in `wisp_commands.py` for the wisp state (intentional split).

## B3. Zones, body & intimacy
- `roomzone_commands.py` + `zone_interact_commands.py` + `interact_commands.py` (zone look/
  study/handle), `freeform_commands.py` (freeform marks/placement), `body_mod_commands.py`
  (breast/penis/testicle mods), `penetration_commands.py`, `womb_commands.py`,
  `inflate_commands.py`, `restrain_commands.py`, `mechanic_commands.py` (install zone mechanics),
  `shower_commands.py` (cursed shower), `dairy_commands.py`. → Several overlap the facility's
  installs; the facility reuses these real systems (good — not redundant).

## B4. World, navigation & housing
- `housing_commands.py`, `door_commands.py`, `stair_commands.py`, `teleport_commands.py`,
  `waystone_commands.py` (+ the realm's waystone/waypost). ⚠ **`knock` collision** (door vs
  scene — see AUDIT §1d). ✅ waystone/waypost no-key bugs fixed (AUDIT §1c).

## B5. NPCs, furniture, props, minigames
- `npc_commands.py` (ask/greet/nservice/triggers — the system the facility NPCs use),
  `furniture_commands.py`, `rocking_horse_commands.py`, `jacuzzi_commands.py`,
  `cah_commands.py` (cards-against-humanity minigame), `cooking_commands.py`,
  `economy_commands.py`, `item_commands.py`, `ogram_commands.py`, `rel_commands.py`
  (relationships), `safety_commands.py` (watch/block — `watch/list` bug fixed, AUDIT §1b),
  `cycle_commands.py` (the endcycle/struggle verbs).

## B6. Core typeclasses (non-facility)
- `characters.py` (zones, appearance layers, rp_name→alias sync — added this loop),
  `rooms.py` (15-layer appearance incl. wisps), `npc.py` (tiered NPC + triggers),
  `objects.py`, `exits.py`, `scripts.py` (PassiveAccumulationScript — drives production +
  the facility passive_tick), plus the body items (`production_item`, `womb_room`,
  `inflation_item`, `body_mod_item`, `piercing_item`, `wearable_item`, `collar_item`,
  `arousal_script`, `heat_script`, `fluid_bank`).

## B7. Non-facility improvement notes
- → **Split `character_commands.py`** (4.4k lines) along concern lines.
- → **Resolve the two cmdset collisions** (`aside`, `knock`) — ✅ done (AUDIT §1d); two now-
  dead classes left to delete whenever (AUDIT §0a).
- → **Centralise duplicated name-helpers** — `_char_name`/`_char`/`_name`/`_mood_color`/
  `_find_character` are copy-pasted across 2–5 modules each. One `commands/_helpers.py` would
  DRY them. (AUDIT §0a)
- → **Per-NPC `rp_name` alias** (the PC fix applied to NPCs) so `ask`/targeting is robust.
- → Many `except Exception as e:` where `e` is only logged — fine, but a project-wide
  logging convention would make failures easier to trace.
- ✅ No-key `search_object`, `hasattr`-account, bare `except:`, mutable defaults, stray-brace
  `.format`, unguarded `[0]`/`int()` — all swept clean game-wide (see AUDIT).
- ✅ **`print()` audit:** all 56 are in `world/` build/migration/loader scripts (run via `@py`
  by staff, where console output is intended) — **none in live command/typeclass paths.** Not
  a bug. (Could route through Evennia's logger for consistency, but low value.)

*Loop pass 13: created this catalogue; made `board` the canonical full dossier.*
*Loop pass 14: extended the catalogue to the wider game (Part B — ~45 command modules + core
typeclasses, grouped by area); flagged two real `CharacterCmdSet` key collisions (`aside`,
`knock`) for your decision (AUDIT §1d).*
