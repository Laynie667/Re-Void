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
  missing rooms/exits/placards/album/office-anatomy + the **Little Box** in the Nursery +
  **Bethany's named studs** + the new **little-clauses** on a signed resident; in-game command
  `facilityupgrade [<target>]`, perm Developer/Admin), `teardown_realm`, `escape` (OOC floor:
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

## 3b. Regression  (`world/regression.py`)
- **Purpose:** an age-regression meter, sibling to Conditioning — hypnosis/drugs/Bethany
  file the adult down into "little", then "small".
- **fn:** `regress` (suggestibility-scaled, same lever as conditioning), `_apply_thresholds`,
  `induce_regression(char, amount, technique, room)` (the hypnosis entrypoint; 4 techniques:
  countdown/bottle/blanket/number). **st:** `regression`, `regression_applied`,
  `regression_permanent`, `headspace` (slipping/little/small). 6 thresholds
  (soft→vocabulary→little→namegone→permanent→small).
- **Reuses real systems:** speech-filter engine (`baby_talk`, new `little_talk`, `word_swap`,
  `single_word`, `no_self_name`), `install_trigger`, `designation`, `arousal_floor`,
  `forced_posture`. Name loss backs up to `facility_name_backup` (so both reset paths restore it).
- **OOC floor:** all flags in `FACILITY_FLAGS` → both reset paths + force_clear/escape wipe them.
- **New speech filter:** `little_talk` (`world/speech_filters.py`) — deeper than baby_talk:
  small words + dropped grammar + first-person→"me" + fillers/whines. Stacks after baby_talk.
- **Read-out:** `regression_status`/`regression_stage`/`_reg_bar` + the `headspace` command
  (`commands/facility_commands.py`, aliases `little`/`howlittle`) — the little's own private view.
- **Composed `state` read-out** (aliases `status`/`self`): one dashboard tying together mind
  (conditioning stage/docility), headspace, body (heat/engorgement/gelded/sissy/denial/lactation),
  line (brood totals + depth), stars, owed quota, biting clauses, and standing — each line points
  at its detail command, and it always closes on the never-gated floor reminder.

## 3c. Little Box  (`typeclasses/little_box.py` + `commands/little_box_commands.py`)
- **Purpose:** "toybox/playpen" furniture that keeps its occupant little — the storage
  counterpart to the rocking-horse cradle. `LittleBoxScript(FurnitureSessionScript)`,
  `build_little_box(room, zone, nap_seconds)`; commands `boxin`/`boxout`/`boxstatus`.
- **fn:** ticks `world.regression` + caretaker `_BOX_BEATS` + a laced-bottle feed; lid LOCKS
  once regression ≥ 45. **st:** `in_box`/`box_entered_at`/`box_release_at`/`box_lid_locked`/
  `box_struggle` (all in FACILITY_FLAGS).
- **NOT a stuck-spot (by design):** ALWAYS self-releases — a nap timer (`room.db.box_nap_seconds`,
  default 360s) springs the lid; `boxout` fills a struggle meter that pops it solo; leaving the
  room, disconnecting (`sessions.count()==0`), and the OOC floor all release. The lid only gates
  the `boxout` verb (like the horse knot gates `horsedismount`) — never navigation, never the floor.
  `boxout`/`boxstatus` always show remaining time + struggle progress.

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
  realm_cycle, body_processing, perpetual_heat, pet_triggers, animal_sleeve,
  **teat_gag**, **nurse_first**.
- **Little clauses (hidden, in `_CONTRACT_BINDING`):**
  - **teat_gag** `{gag_word, uncork_word, fluid}` — installs a `gag`/`ungag` trigger pair
    (any speaker fires them). `gag` → `teat_gagged` + the `suckling` speech filter (speech
    becomes suckle-noise) + `_nurse_feed` each attempt (fluid-bank deposit + regression +
    dependence). Self-expires after `_TEAT_GAG_SECONDS` (the filter heals itself) so a gagged
    little is never left unheard; uncork word ends it early; §0 floor clears it.
  - **nurse_first** `{fluid}` — `check_say_allowed` gate: a first sentence is blocked until
    `_do_nurse_first` (kneel-and-nurse a load: deposit + regression), which opens a 90s
    speaking window; must re-nurse after. Floor clears it.
  - **stuffed_mouth** `{fluid}` — adds the `stuffed` speech filter: speech cut to a few
    cock-muffled fragments, ~40% chance the mouth is "found full" (a wet gurgle + `_nurse_feed`).
  - **beg_small** — sets `orgasm_denial`; the `beg` verb (begged small) grants one `_grant_climax`
    + a regression drip. Nothing is hers by default; she begs little for relief.
  - **star_chart** — fills from EVERY source now: Bethany (seat 3/throat 1), the rocking horse
    (breed/knot), the nugget animal beat, the gang scenes (`_gang`, per beat), and the **milk
    quota** (`_log_milk` awards once per completion, re-armed when the bar is raised). Sets
    `orgasm_denial` + `star_chart_on`; relief is bought with stars
    (`world/star_chart.py`: `award_star`/`spend_stars`/`star_status`, gated on `star_chart_on`).
    `award_star` hooked into Bethany's climax (seat=3/throat=1), the rocking-horse breeding
    deposit + knot-lock. `stars` command (`commands/facility_commands.py`) views + spends
    (RELIEF_COST=4 → a granted climax).
  - Shared helper `_nurse_feed(char, fluid, source)`. New `suckling`/`stuffed` filters in
    speech_filters. Flags (`teat_gagged`/`teat_gag_until`/`teat_gag_fluid`/`nurse_first`/
    `nursed_until`/`nurse_first_fluid`/`stuffed_mouth`/`stuffed_fluid`/`beg_small`/
    `star_chart_on`/`star_chart`) all in FACILITY_FLAGS.

## 4b. Named-sire lineage  (`world/gang_breeding.py` + `world/pregnancy.py`)
- **Purpose:** get traces to the *individual* stud, not just a species — real consequence.
- `gang_inseminate(..., sire=None)` → `on_bred(..., sire)` → `conceive` stores `sire`/`sires`
  in the pregnancy record (superfetation by a different stud records a co-sire) → `deliver`
  gives each of the litter one of the recorded sires → `_birth_offspring(..., sire)` stamps
  `o.db.sire`, names the get (`"Caesar's silver-marked pup"`), writes it into the desc + birth
  line, and tallies `target.db.offspring_by_sire` (FACILITY_FLAGS). Anonymous breeding still works.
- **Sire is supplied by:** `_breed_one` (prefers a stud actually PRESENT in the room via
  `present_stud`, else the breeder NPC), `_nugget_little_animals` (the named stud), and Bethany's
  multicock climax (sire="Bethany"). So when the stud you can see breeds you, that pup is his.

## 4c. Offspring gender (incl. futanari)  (`world/gang_breeding.py`)
- Every get rolls a sex — `offspring_sex(species)`: female / male / **futa** (the bethany line
  is always futanari). Stored `o.db.sex`; tallied `target.db.offspring_by_sex` (FACILITY_FLAGS).
  Futa get are named ("Caesar's … futa pup") and described as growing the flared/knotted cock
  they'll breed the dam with. `can_sire(obj)` = male or futa — only those breed her back
  (daughters are broodstock). `_find_breeder` and the line-remembers curse both require
  `can_sire` and record the get as the named sire of what it puts in her. Shown in `studbook`.
- **Matured get become NAMED studs** (`_mature_get` + `_name_get_stud`/`_GET_STUD_NAMES`): a
  siring get, on maturing, is named (Rex/Titus/Juno/…), flagged `is_stud`, given a stud desc, and
  added to `facility_studs` — so her own sons/futa daughters join the roster and breed her back BY
  NAME (the line-remembers curse passes their name as sire). Non-siring/gelded get file to
  broodstock instead. `present_stud` recognises a matured `is_stud` get in the room as a present
  stud (not only Bethany's FacilityAnimal studs), so scenes name the real penned child.
- **Stud-book renderer** `studbook_lines(char, brief=False)` — one source of truth for the brood
  read-out (by sex / by line / by sire / depth), reading only stored tallies + `offspring_max_gen`
  (no roster scan). Used by the `studbook` command (full) AND the Records Hall ledger board
  (`FacilityLedgerBoard`, brief — capped to the top 4 sires) so the lineage is a real in-world
  readable, not just a command.

## 4d. Neuter & sissify (male stock)  (`typeclasses/facility_script.py` + `process`)
- `_proc_neuter`: gelds + cages male stock — deletes any testicle BodyModItem, shrinks/relabels
  the penis mod to a caged clitty, sets `db.neutered` + `orgasm_denial`, real mark + conditioning.
  `can_sire` now returns False for the neutered, so the breeding system retires it from siring.
- `_proc_sissify`: feminizes into a kept sissy — backs up the name (facility_name_backup), sets a
  sissy designation/rp_name (Bambi/Candy/…), adds the new `sissy` speech filter (feminized,
  simpering), `orgasm_denial`, a presentation posture, conditioning, a `good girl`→leak trigger.
- Both are `process <unit> neuter|sissify` actions (CmdProcess) and `_proc_*` methods. Flags
  `neutered`/`sissified` in FACILITY_FLAGS; sissy name/filter cleared by the floor.

## 4e. Engorgement loop (the dairy leash)  (`typeclasses/facility_script.py`)
- Each cycle beat she ISN'T milked, `_engorgement_tick` reads her real milk ProductionItem
  volume (`_milk_volume`) and, past `_ENGORGE_ML` (300/600/850 ache→pain→leak), climbs arousal +
  an arousal-floor scaled by fullness and by `milk_engorge_beats` (how long unmilked), narrating
  from `_ENGORGE_ACHE`/`_ENGORGE_PAIN`. Past the leak threshold she lets down untouched
  (`_engorge_leak` spills real ml — wasted, not banked). The `milk` phase is RELIEF: it banks a
  little conditioning (`_ENGORGE_RELIEF`) and zeroes the counter — relief becomes the leash.
  Hooked in the main per-beat path; the nugget is maintained by its cradle so it's exempt.
  Flag `milk_engorge_beats` in FACILITY_FLAGS.

## 4f. Fellow-resident (continuity)  (`world/facility_fellow.py` + `_fellow_beat`)
- A named co-resident tracked with her own slow progression along the line: 6 stages (fresh
  intake → softening → milk-heavy → bred-round → conditioned-blank → perfected) with per-stage
  desc + beat pools. `ensure_fellow`/`advance_fellow` (chance per beat; **churns** at the end —
  sold off, a fresh intake replaces her)/`fellow_beat_line`/`fellow_churn_line`/`fellow_desc`.
- `_fellow_beat` (per cycle beat) advances her, syncs her real present NPC (`FacilityAttendant`
  on the floor, realm-tagged + tracked) to her stage, and ~30% narrates her — a recurring face a
  few rooms ahead as mirror/foreshadow, until she's sold and the cycle starts over on someone new.
  State `facility_fellow`/`facility_fellow_ref` in FACILITY_FLAGS; NPC deleted on teardown.
- **Shared scenes** (`fellow_shared` + `_fellow_scene`): when the fellow NPC is co-present in the
  resident's room, ~35% of beats run a stage-banded shared-processing scene — milked side by side,
  bred off the same stud back-to-back (real `_breed_one` on the resident), made to use each other,
  or (deep stages) she's used on you / sold to a buyer while you present beside her, told your turn
  is coming. Banks a little conditioning.
- **Futa-conversion set-piece** (`_fellow_futa_breeding` + `_FELLOW_FUTA_*` pools): once the
  fellow's a bit broken in and co-present, ~25% of shared scenes fire the unique event — Bethany
  has her surgically converted to a futa (PERMANENT: `mark_fellow_futa`, she keeps the cock),
  dosed with aphrodisiac, and set loose to aggressively breed the resident over several beats
  while her mind fragments (guilt vs rut). REAL insemination (sire = the fellow) + records the
  cross. If the resident's little, the both-littles amplifier pool fires + extra regression.
  Her NPC desc is updated to note the change.
- **Crossed lines** (`fellow_cross_record`/`fellow_cross_line`): when a shared 'breed' scene runs
  with a NAMED present stud, that stud takes both you and the fellow — recorded on
  `fellow_cross_sires` (FACILITY_FLAGS) so your broods and hers are half-siblings. Surfaced in
  `studbook` / the ledger as a "crossed lines" entry.

## 4g. Procedure breadth (`_proc_*` + `process`)
- **tonguesplit** — forks the tongue: adds the `lisp` speech filter (sibilants slur to 'th' +
  fork-flicks; ordered after sissy in `_FILTER_ORDER`), arousal floor, real mark. Distinct from
  `_proc_tongue` (babble).
- **corset** — permanent waist-training: forced_posture + body_language (cinched hourglass she
  can't slouch out of) + mark.
- **clitpump** — permanent clit enlargement into an oversensitive cocklet: arousal_floor +
  stim_per_tick + mark (distinct from `clit_hood`).
- All in `_PROCEDURES` (cycle can apply) + `process <unit> tonguesplit|corset|clitpump`. Reuse
  existing FACILITY_FLAGS (active_speech_filters/forced_posture/arousal_floor/stim_per_tick) —
  floor coverage already holds.

## 4h. CYOA choices  (`world/cyoa.py` + cycle `_pose_cyoa`/`_cyoa_tick` + `choose`/`offer` cmds)
- The facility makes her CHOOSE at branch points; every option routes through a real effect, all
  options are bad, indecision fires the facility's default (`facility_decides` on `_CYOA_TIMEOUT_S`).
  Never hard-blocks the cycle; `pending_choice` in FACILITY_FLAGS so the floor clears it.
- **Data-driven choice graph**: `@choice(id, root=)` builder registry (`_BUILDERS`/`_ROOTS`);
  `pose_named(char, id)` / `pose_random(char)` (cycle auto-poser, skips N/A builders). Options can
  **chain** via `then=<builder_id>` (resolve_choice poses the next node). Builders: beg / deal /
  hole (built from her real orifices) / slip / emphasis / **correction** (root), + `offer` &
  **bethany** (reachable). `devote` effect routes the Bethany owner-arc bump through `_devote`.
- **Option `outcome` prose**: each option can carry an `outcome` — a crude, in-voice beat shown
  privately on resolution (what the choice just did to you), separate from the mechanical effect.
- **Signature intake chain**: `intake → intake_strip → intake_first → emphasis` — a full
  multi-step opening (sign the contract → stripped/weighed/holes-inventoried inspection → first
  use before you've finished being a person → how you're spent), expansive and crude, every step
  real (devote/submit/deny_hold/pick_hole) with outcome beats.
- **`clause` node + effect**: produces a real hidden-clause addendum — `clause` effect installs it
  through the SAME `apply_effects` path the contract uses (teat_gag/nurse_first/stuffed_mouth/
  beg_small/star_chart), so it genuinely takes hold; refusing routes through auto-consent (binds
  anyway) and chains into `correction`. The clause taking hold is narrated.
- **Punishment chain** (`punished → punish_sentence → punish_after`): a CONSEQUENCE-GATED root —
  the builder returns None (pose_random skips) unless she's earned it (defiance > 0 / quota_behind /
  freedom_forfeited). Confess (banks compliance) vs deny (real `punish`, +1 infraction) → choose the
  sentence: the sty (REAL `apply_filth` + punish), the floor (public `_gang`), or the line (`punish`
  severity 2) → the aftermath: thank her and mean it (`gratitude` effect — register_compliance
  reward + conditioning; "a thank-you that you mean, that one we keep") vs silence (punished again,
  the review resets — "they're not building toward your breaking, they're building toward your
  thanking"). New effects: `punish` (compliance.punish), `filth` (apply_filth), `gratitude`.
- **Descent chain** (`descent → descent_mark → descent_break → descent_terminus`): the deeper arc —
  ask to go down → permanent parlour mark (`_procedure`) → the cell hollows her (`deepen` effect:
  real conditioning + regression) → the threshold of Deep Stock (heavy prose, real conditioning).
  Each floor a real effect with expansive crude outcome prose; the terminus keeps the §0 fire-exit
  explicitly lit in-fiction.
- **Facility spine**: `@effect("facility")` finds the running cycle script and calls a real method
  (`_gang`/`_do_milk`/`_procedure`/`_dose`/scene), so the facility's content is reachable AS choices.
  Other effects: emphasis (biases `_choose_destination`), grant_relief, deny_hold, quota_deal,
  pick_hole, go_little, submit_standing.
- Commands: `choose [<n>]` (answer/re-show), `offer` (present yourself → the offer choice graph).

## 4i. The Spiral Chair  (`typeclasses/hypno_chair.py` + `commands/hypno_chair_commands.py`)
- Bethany's hypno rig for the Conditioning Cell: `hypnosit` starts a staged induction
  (settle → spiral → drone → deep → set; her recorded voice, deep per-stage prose pools, room
  sees third-person glaze lines). Every stage REAL: `add_conditioning` scaled by depth,
  suggestibility climbs, deep stages seat actual `install_trigger`s + regression if she's drifting.
- **Mid-trance CYOA**: at stage ≥2 the chair poses the `mantra` node — "say it with her" seats the
  mantra as a REAL recite-trigger (`mantra_set` effect: install_trigger + conditioning +
  suggestibility) vs hold your tongue (deny_hold; the recording notes the trend). Crude outcome
  prose on both.
- **NOT a stuck-spot**: session timer (420s) always releases; `hypnorise` surfaces (deep trance
  resists twice via `chair_struggle`, then yields); disconnect auto-releases; all five flags
  (`in_hypno_chair`/`chair_stage`/`chair_beats`/`chair_release_at`/`chair_struggle`) in
  FACILITY_FLAGS. Installed in the Cell by `_furnish` + `facility_upgrade` (`build_hypno_chair`).

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
- **Named studs** (`world/facility_animals.py`): Bethany's personal beasts — `DEFAULT_STUDS`
  (Caesar/Duke hounds, Brutus bull, Goliath boar, Sultan stallion), `ensure_studs`/`pick_stud`/
  `add_stud`/`stud_line`. Stored on `char.db.facility_studs` (FACILITY_FLAGS). Each stud has a
  **temperament** (veteran/eager/inexorable/filthy/ruinous) driving `sire_beat(char, sire, t)` —
  a per-sire breeding-voice line (`SIRE_TEMPERAMENTS`) emitted in `_breed_one` when a named stud
  sires, so Caesar's patient mastery / Sultan's ruin / Goliath's filth read distinct. Promoted
  get-studs get a random temperament via `add_stud`. The brood is
  read back by the `studbook` command (aliases `brood`/`getbook`) — totals by species, by
  named sire (from `offspring_by_sire`), and generations deep. They are also
  spawned as **real present, examinable animals** in the Pens via `spawn_studs` (idempotent,
  realm-tagged for teardown) — `FacilityAnimal(FacilityFurniture)` (un-gettable; `get_display_desc`
  = stud desc + a per-species live idle beat). `present_stud(room, species)` lets scenes prefer
  the actual penned beast over the roster. `spawn_studs` also merges `PEN_AMBIENT` into the room.
  Wired into `_furnish` (key "pens") on fresh builds AND `facility_upgrade`. Woven into
  `_nugget_little_animals` (named-stud pool `_NUGGET_LITTLE_STUD`) and `_scene_knottrain`, both
  preferring a present stud.
- **Little-nugget animal beat** (`RealmCycleScript._nugget_beat` → `_nugget_little_animals`):
  when the kept nugget is also in little headspace (`headspace` little/small or `regression ≥ 50`),
  ~50% of use-beats run it — Bethany plays nursery-keeper while the kennel breeds the helpless
  little trunk of her: real `gang_inseminate` (hound-weighted) + `maybe_lineage_offspring` + a
  regression deepening + a star. Pool `_NUGGET_LITTLE_ANIMAL` (8). Floor still frees her instantly.
- **Visit modes** (`db.visit_mode`): `throat` (the original quick contemptuous face-fuck) and
  `seat` — the three-shaft set-piece. Seat fires ~40% when she has ≥3 holes available; runs
  4–6 beats; all three prehensile shafts work mouth/cunt/ass at once, knot-locks partway
  (`db.knotted` + a knot-lock `forced_posture` released on end), babies her down with the
  regression hypnosis (`_SEAT_REGRESS` → `world.regression.regress`), 3× per-beat
  arousal/conditioning/devotion, triple devotion + hard regression slug at climax, higher
  ownership chance. Pools: `_SEAT_ENTER/_BEAT/_REGRESS/_KNOT/_DEGRADE/_CLIMAX`. `_seat_beat`
  + `_available_holes` (reuses `gang_breeding.animal_holes`).

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
