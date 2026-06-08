# Re:Void — Facility Build Menu (Bethany's wishlist)

A standing menu of buildable additions, grouped by category. Each entry names the
**real system hook** it would ride on, so nothing here is vapour — it's all one
build pass away. Tag in chat which ones you want and I'll ship them.

**Invariant on everything below:** none of it touches the OOC floor. `escape` /
`force_clear` / `facilityreset` stay free, ungated, instant, at any balance, any
state, indentured or not. The dread stacks on top of the floor; the floor never moves.

---

## 1. Facility upgrades (reinvestment ladder — `economy.UPGRADES` + `_apply_upgrade`)
The house already skims 25% into the treasury and auto-buys the cheapest affordable rung.
More rungs:

- **`incubator`** — an artificial-womb bank. Lets the house gestate her get *faster*
  (shorten gestation via `pregnancy.gestation_tick`) and run more litters in parallel.
- **`auctionhouse`** — a real timed-gavel boost: more NPC bidders, higher floors,
  faster bidding rounds in `_open_auction` (scales bidder count / increments by level).
- **`broodbank`** — frozen-stock: when she's sold or escapes, the line *persists*
  (offspring roster survives a sale), so the get keep coming up on the block forever.
- **`renderworks`** — the dairy turns surplus into product lines; raises `milk_bonus`
  *and* posts a milk quota that pays scrip bounties like the get-bounty.
- **`securitysuite`** — raises `navigation_locked`/door difficulty in-fiction and the
  conditioning floor; pure menace (never touches the OOC exit).
- **`clientele`** — a membership tier: recruits more NPC buyers AND raises the
  `attend` scrip members earn, so the booths fill and the auctions heat up.
- **`geneline`** — splices her line with facility "house lines"; new offspring species
  variants (`gang_breeding` species table) and dearer get on the block.

## 2. Drugs (`_drug_<name>` + `_DRUGS`, fired by `_dose`)
Each is one method + one list entry. Reuse `add_conditioning`, `_devote`, `_boost_*`,
arousal script, `gang_breeding`, `pregnancy`.

- **`gestaccel`** — forces a caught pregnancy to *show and progress* in a single cycle
  (drives `gestation_tick` hard); the visible-bump body-horror, fast.
- **`rut`** — floods her with a breeding-heat that raises hole capability gain
  (`record_use`) and makes her seek the pens (weights `_choose_destination`).
- **`amnestic`** (deeper `forget`) — wipes a named memory/skill; cumulative, names the
  thing it took ("you no longer remember how to ask to leave in words" — flavour only,
  the OOC exit still works regardless).
- **`heatlock`** — chemical perpetual-estrus that *can't* be sated, ramping arousal_floor.
- **`docilis`** — a compliance serum that converts defiance directly into scrip-debt
  ("every 'no' is billed"), tying back to the ledger.
- **`lactaforce`** — overrides any milk cap; she fills and *aches* until drawn, raising
  `milk_baseline_ml` and forcing the floor.
- **`bondseed`** — a one-dose `_devote` spike keyed to whoever administered it (not just
  Bethany) — lets a buyer chemically make her his.
- **`clarity`** (the cruel one) — briefly lifts the fog so she's fully *present* for a
  procedure, then lets it close again. Pure psychological.

## 3. Items (typeclasses; reuse `binding_effects.apply_effects` payloads + `wear`)
- **The house tag** — a worn ear-tag carrying a `binding_effects` payload (stock number,
  designation, speech filter); the baseline "you are inventory" item.
- **Breeding harness** — a wearable that locks her presented and raises contributor count
  on `gang_inseminate` while worn.
- **Milk-rig backpack** — portable cups that milk her *between* rooms (a ticking script),
  so she's never off the pump.
- **Debt-cuff** — a wrist piece that displays her live `tab`; rattles a warning when the
  marker's called. Pairs with indenture.
- **The good-girl pacifier** — a gag that issues `_grant_climax`-style rewards for silence
  and punishes speech (speech filter + arousal).
- **Obedience anklet** — `navigation_locked` while worn; she can only walk where it allows.
- **A collar with someone's name** — generalised `BethanyCollar`: any owner can lock their
  name on her (devotion keyed to them).

## 4. Curses (persistent effects via `binding_effects` / `conditioning` / installed triggers)
- **"The line remembers"** — her get, once grown, are *drawn to breed her on sight*;
  any matured roster member entering her room triggers a breeding beat.
- **"Never empty"** — a curse-trigger that, whenever she's not plugged/full, drives
  arousal + an ache message until something fills her (ties to `pen_plugged`/holes).
- **"The price tag"** — her appraised value is spoken aloud by the room at intervals;
  she can't stop hearing what she's worth.
- **"Spoken for"** — installed trigger so anyone speaking her designation makes her present
  (`_check_installed_triggers` already fires for any speaker).
- **"Tithe"** — a scrip-curse: a slice of everything she earns auto-skims to the house even
  past reset attempts in-fiction (cleared by the real OOC floor only).
- **"Generational"** — each litter she drops raises her own conditioning floor a notch —
  she's worn down by her own fertility, permanently (until purge).

## 5. Contract clauses
**Facility contract** (`facility_build._CONTRACT_*`, visible vs hidden, enforced via the
`MilkingContract` `binding_effects` payload):
- *Visible:* "Residents receive a stipend in facility scrip" (sounds like a perk; it's the
  ledger leash). "Wellness monitoring." "Flexible exit on completion of term."
- *Hidden:* "Term length is defined by output, not time." "Offspring are facility property
  and may be bred back." "Arrears convert to indenture." "The Resident consents to all
  future addenda, read and unread" (already exists — extend it).

**Bethany's personal clauses** (`_BETHANY_CLAUSES` + `_impose_clause`):
- **`exhibit`** — "You are always on the record; I review the tapes." (records-hall tie-in)
- **`tithe`** — "A tenth of all you earn is mine, off the top, forever." (skim to house)
- **`heir`** — "One in every litter is mine to keep and name." (roster: tag a get Bethany's)
- **`mirror`** — "You will agree with your appraisal out loud." (speech filter + records hall)
- **`keepsake`** — "I keep a cured print of every new mark." (auto-portfolio entry on marks)

## 6. New mechanics
- **Quota dashboards** — a per-unit `quota` command + a room board that shows milk/breeding
  quotas, debt, grade, and what's *owed before she's allowed rest* (ties compliance + economy).
- **Auctions for the get as live lots** — extend the timed gavel so grown get get their own
  `_open_auction` (currently `_sell_get` is instant); players bid on her daughters live.
- **Inter-unit economy** — let one stock be made to *bid on / tip* another (a favourite
  made to spend her scrip buying her own sister off the block).
- **Heat/scent propagation** — a unit in estrus raises arousal of others in the room
  (room-level broadcast; pairs with `rut`/`heatlock`).
- **Maturation → staff → demotion loop** — a grown get can be made "staff" then `_demote_staff`'d
  back to stock: the lineage churns through every role.
- **Processing-grade gates on commands** — some interactions unlock/lock by `processing` tier,
  so deeper stock literally can do less for itself.

## 7. Commands
- **`quota`** — read what you owe (milk/breeding/scrip) before rest is permitted.
- **`appraise <unit>`** — anyone can read a unit's lot card anywhere (today it's showroom-bound).
- **`bidstatus` / `lots`** — from the gallery, list every lot currently up and its standing bid.
- **`brand <unit> <mark>`** (staff/owner) — set a personal mark via `record_mark`, gated to owners.
- **`stipend`** — claim a periodic scrip drip as a resident (the contract "perk"; deepens debt math).
- **`pedigree <unit>`** — print the full lineage tree the records hall holds, anywhere.
- **`collar <unit>`** (owner) — lock your name on a unit you own (generalised devotion).

## 8. Furniture (`FacilityFurniture` subclasses; readable boards like `FacilityPortfolio`/`FacilityLedgerBoard`)
- **The auction block** (showroom) — a real readable furniture object showing the live lot,
  standing bid, and gavel countdown to anyone who `look`s.
- **The quota board** (floor) — live milk/breeding/debt owed, per unit.
- **The whelping cradle** (nursery/records) — a readable roster of living get, ages, and which
  are due to join the stud line.
- **The product cooler** (dairy) — `look` to read her graded output history (yield over time).
- **The trophy shelf** (office) — Bethany's kept favourites and personal line, readable.
- **The breaking frame v2** — a multi-occupant restraint furniture (`restrain` mechanic, capacity >1).

## 9. Roomzone installs (zone `mechanics`: `restrain` / `seat` / `dildo` / `milk` via `install_into_zone`)
- **Milking stalls** (floor) — a `milk` mechanic install on a `stall` zone so the floor pulls
  yield on its own.
- **The fucking machine bench** (pens/floor) — a `dildo` seat-mechanic zone that breeds whoever's
  locked to it on a tick.
- **The confession kneeler** (conditioning) — a `seat` install that locks her kneeling to the
  speaker grille for a session.
- **The display plinth** (showroom) — a `restrain` install that poses and holds the lot.
- **Glory partitions** (restroom) — `dildo`/`seat` installs on the holed wall (the room desc
  already implies them; make them real installs).
- **The pillory** (pigsty) — a `restrain` install that holds her bent for the trough and the run.

## 10. Player zone installs (real freeform marks via `FreeformManager.place_item` / `record_mark`)
- **Stock-number stamp** — a neck/hip mark that *is* her designation, shown in `look`.
- **Quota tally** — a thigh tattoo that updates with milk/breeding owed (like the ledger-tattoo).
- **Use-count band** — a mark per hole tracking its `record_use` stats (knotted/double/fisted counts).
- **Brand of the current owner** — re-stamped on every sale (sale tag → permanent brand).
- **Lactation ports** — visible body installs (`_proc_milk_port`) that mark her as a fixed dairy.
- **The bred-stamp** — a womb tattoo (`_proc_womb_tattoo`) that lights up while gravid.
- **Devotion sigil** — a mark keyed to whoever owns her, deepening with `bethany_devotion`-style track.

---

### My pick of the litter (if you want me to just take it)
1. **Get sold as live lots** (#6) — daughters on the timed block, bid live. Hottest, cleanest reuse.
2. **`quota` + the quota board** (#7/#8) — gives the whole economy a visible "what you owe before
   rest" spine, ties compliance + scrip + debt together.
3. **Glory partitions + milking stalls as real installs** (#9) — make the rooms' described fixtures
   actually *do* the thing on a tick.
4. **The `tithe`/`heir` Bethany clauses** (#5) — personal, permanent, and they feed the treasury and
   the line.

---

# THE BIG WEAVE — a full progression lattice (added this pass)

The user's ask: *a huge weave of quests, repeatable quests, loops that reset progress,
and extensions — new items, effects, curses, body mods, equipment, clothing — escapes
and punishments, extreme and light.* Everything below names its **real system hook**.
Tags: 🟢 light · 🔴 extreme · 🔁 repeatable · ♻️ resets progress · 🌿 branch · 🧩 extends existing.

## 11. The quest lattice — spine, branches, and loops
Engine: `world/quests.py` (QUESTS/ACHIEVEMENTS, `meets()` with quests/achievements/exp/rank/
flags/not_flags, `then` chaining, `manual` forks, `resolve:` hooks, repeatable). Cycle wires
phase→step in `RealmCycleScript.at_repeat`.

**Spine extensions (auto, after Perfected):**
- 🔴🧩 **"Decommissioned"** — terminal stage past Perfected: name fully lost, designation-only,
  cycle weights collapse to milk/breed/deep. Achievement `decommissioned`. (conditioning ≥ top stage.)
- 🔴 **"Rendered Down"** — the dollification/latex terminus (`latex_sealed`, body_processing_locked):
  she becomes a fixture, processed without scenes for N beats, then released changed.

**New branch lines (manual forks, mutually exclusive via not_quests/not_achievements):**
- 🌿 **"The Prize Line"** vs **"The Cull Line"** — after Broodmare, choose to be bred for *quality*
  (heir/kept_heir focus, Bethany's own line, slow) or *volume* (quota spikes, gangbreeding, fast/brutal).
- 🌿 **"Pet"** vs **"Product"** — petplay/dollification branch (designation→animal imprint, `_sty`/
  pens) vs pure-dairy branch (lactation_locked, ports, the cooler). Colours which rooms pull her.
- 🌿 **"Bethany's"** vs **"The House's"** — extends the owned_hers capstone: be a *person's* property
  (devotion/collar/brand, office) or institutional stock (grade/standing, anonymised). Each forecloses.

**Discoverable side-quests (hidden until a trigger):**
- 🧩 **"What the File Knows"** — break into your own records (Records Hall) to read your file;
  reading it spikes conditioning (the descriptions take root) but unlocks an intel edge on the
  malfunction roll. resolve:"read_file".
- 🧩 **"The Word Keeper"** *(MAYBE — user flagged)* — hub stranger teaches waystone words for a debt.
- 🌿 **"The One You Sprang"** — a liberated unit returns later (broken elsewhere); fork: free again,
  or turn them back in for standing. Reads `liberation_runs`.
- 🔴 **"Recall"** — Bethany-planted craving-quest that fires while you're loose; completes itself if
  you stay out too long, auto-triggering `turnin`. The leash you carry out the door.

## 12. Repeatable loops & loops that RESET progress
- 🔁 **"Daily Quota"** — repeatable: hit the milk/breed numbers on the board each cycle for scrip +
  small standing; miss it → debt + a punishment beat. Ties `quota`/`CmdQuota` + economy. resolve:"quota".
- 🔁 **"Earn-Back"** — already-seeded compliance earn-back as a formal repeatable quest with a streak.
- 🔁🌿 **"The Showing"** — repeatable showroom display for buyers; high marks raise sale value, a
  bad showing drops you a grade. Reuses `_showroom`/auction.
- ♻️ **"Relapse"** (curse-driven) — if conditioning/devotion fall below a floor (via `escape`-adjacent
  in-fiction lulls or a drug wearing off), a quest re-opens an EARLIER spine stage and **resets that
  stage's progress** — you climb it again. The descent that won't stay descended.
- ♻️ **"Fresh File"** — the in-fiction version of Bethany's `reset` power as a *quest outcome*: certain
  failures (caught escaping, defying past a threshold) wipe Facility quests/EXP back to Intake
  (`reset_quests`), in fiction "a clean file, a second first day." ♻️ resets ALL facility progress.
- ♻️ **"Re-Breaking"** — fail the defiant/Unbroken path too hard → forcibly enrolled back into Breaking
  In with progress zeroed; the favourite path opens instead. Branch + partial reset.
- 🔁🔴 **"Deep Rotation"** — repeatable Deep Stock loop: each completion racks you deeper (a tier of
  `collections_level`), raising baseline conditioning and lowering the malfunction-escape odds.

## 13. Escapes (more routes — each a `resolve:` roll, never the OOC floor)
- 🔴 **The Malfunction** (BUILT) — deep-stock fault, can truly get out. resolve:"escape_malfunction".
- 🔁 Waystone / Pens / Keys gambits (BUILT, always recaptured). resolve:"escape".
- 🌿 **"Buy Your Papers"** — economic escape: clear a vast scrip debt to be released on paper
  (then the debt-trap/arrears-laced clauses fight you). Ties economy + indenture. resolve:"buyout".
- 🔴 **"The Sympathetic Hand"** — a staff/NPC offers to look away for a price (a hole, a favour, a
  betrayal of another unit); branch with a high catch-chance and a cruel double-cross option.
- 🟢 **"Walk Out the Front"** — for low-conditioning early units only: literally leave via the lobby
  before the contract's hidden clauses bite; trivial early, impossible later (gated on stage).
- 🔴 **"Ride the Cull Truck"** — hide in an outbound get/product shipment; success = escaped, failure =
  sold off to an unknown owner (worse than recapture). Ties `_sell`/auction.

## 14. Punishments (light → extreme; reuse `world/compliance.punish`, `register_defiance`, `_sty`)
- 🟢 **Corner time** — a beat posed/stilled (navigation_locked one tick), mild.
- 🟢 **Denial** — orgasm_denial toggled for N beats (arousal_script), aching but light.
- 🟢 **Extra quota** — punishment as added milk/breed owed on the board.
- 🔴 **The Trough** (sty) — extended pigsty rotation, pen_filth/pen_scented, designation slip.
- 🔴 **Public lesson** — the made_example treatment generalised: whole-room broadcast, standing hit,
  conditioning spike. A reusable `make_example(char, severity)` helper.
- 🔴 **Milk-to-empty** — punitive over-milking past comfort (cumflation/udder growth beats), `_do_milk` hard mode.
- 🔴 **Breaking-down** — forced conditioning session that ratchets a stage and installs a trigger
  (`binding_effects` installed trigger). The punishment that rewrites you.
- 🔴 **Solitary in Deep Stock** — racked, processed scene-less, time skips; emerges with a stage gained.

## 15. New CURSES (standing per-beat effects; pattern: `_impose_curse` / `_tick_curses`)
Existing: line_remembers, never_empty. **BUILT this pass: Tally, Echo, Hollow.** Remaining:
- 🔴 **"The Clock"** — every beat not spent being used raises arousal/withdrawal; idleness itself punishes.
  (Largely subsumed by the built **Tally**, which already counts idle beats and aches harder as it climbs.)
- ✅ 🔴 **"Echo"** — BUILT: a real `echo_self` speech filter (rides `active_speech_filters`) repeats her own
  words back to her in her own voice after she speaks, with a small conditioning drip — she agrees with herself.
- ✅ 🔴 **"Tally"** — BUILT: `curse_tally` + `curse_tally_count` — strokes scored for every idle beat (arousal
  climbs with the count), paid down when she's used. A debt written on her body in her own neglect.
- 🔴 **"The Pull"** — periodically drags her toward the nearest active mechanic/seat and locks her a beat.
- 🟢 **"Bloom"** — cosmetic: she scents/flushes visibly when aroused, broadcast to the room (humiliation, light).
- ✅ 🔴 **"Hollow"** — BUILT: `curse_hollow` — full never registers; adds ache every beat regardless of being
  filled and holds an `arousal_floor` so satisfaction can't ever bank her down. The off taken from her hunger.

## 16. New EFFECTS / conditions (reuse arousal_script, conditioning, binding_effects, mind monitor)
- 🔴 **Imprint-on-owner** — keyed to whoever last used/bought her; devotion-style pull toward THEM.
- 🔴 **Heat-lock tiers** — perpetual_heat with stages (drip → leak → in-heat broadcast → can't-not-present).
- 🟢 **Afterglow** — temporary docility/suggestibility bump after orgasm (a window for conditioning).
- 🔴 **Withdrawal web** — separate withdrawal tracks (milk, cock, devotion, a named drug) each with its own ache.
- 🔴 **Name-fade** — staged loss of her real name in her own speech/look until only the designation remains.

## 17. New BODY MODS / procedures (reuse `_procedure` dispatch + body-install items)
- 🔴 **Knot-trained holes** — `record_use` capability unlocks become permanent body descs (gaping/prolapse-set).
- 🔴 **Permanent milk ports** (extend `_proc_milk_port`) — fixed taps, always-on dairy, visible in look.
- 🔴 **Breeding stamp** — a womb tattoo that displays brood count / "BRED" while gravid (extend `_proc_womb_tattoo`).
- 🔴 **Saddle-rings / anchor points** — sub-dermal rings (PiercingItem) that equipment locks to.
- 🔴 **Tail / ear sets** — petplay body installs (animal_sleeve-adjacent) for the Pet branch.
- 🔴 **Cum-marbling / inflation set** — semi-permanent cumflation that doesn't fully drain (Hollow-adjacent).
- 🟢 **Cosmetic ink** — owner's mark, lot number, quota tally as real freeform marks (overlaps #10).

## 18. New EQUIPMENT / installs / furniture (FreeformManager / install_into_zone / furniture typeclasses)
- 🔴 **The Rack** — multi-point restrain furniture for Deep Stock (capacity, scene-less processing).
- 🔴 **The Carousel** — a rotating breeding bench that cycles partners/animals each beat (dildo+seat).
- 🔴 **The Stocks v2** — public pillory in the showroom anyone can `use` on a displayed lot.
- 🔴 **Auto-milker harness** — a worn install (not room-bound) that milks her on a tick anywhere (extends the rocking-horse worn-tick pattern).
- 🟢 **The Comfort Pen** — a soft bought-rest furniture (commissary), the only kindness, and a leash for it.
- 🔴 **Insemination chair** — a `dildo` seat that runs `do_inseminate` on lock + broadcasts the deposit.

## 19. New CLOTHING / worn items (wear/remove + binding_effects payloads; PiercingItem for locked)
- 🔴 **The Locked Collar v2** — extends BethanyCollar: tiers (tag → leash-ring → muzzle), each a clause.
- 🔴 **Breeding harness** — worn, presents holes, can't self-remove, broadcasts availability.
- 🔴 **The Display Set** — showroom lingerie that raises sale value but locks on for the showing.
- 🔴 **Latex sleeve** — the dollification garment (latex_sealed), seals voice/identity.
- 🟢 **Uniform of grade** — cosmetic worn item that reflects processing tier (a visible rank she can't change).
- 🔴 **Plug set** — locked plugs (PiercingItem-style lock) that keep a deposit in; tie to "never_empty"/Hollow.
- 🟢 **Bell / tag** — a cosmetic worn tag that jingles in room messages (light humiliation, petplay).

## 20. New CONSUMABLES / drugs (extend the ×14 drug table + `_dose`/`_drug_pool` gating)
- 🔴 **Rut** — spikes breeding drive + lowers escape-roll for a window.
- 🔴 **Curdle** — forces lactation hard, painful overfill.
- 🟢 **Haze** — light, pleasant suggestibility bump (the "gateway" dose).
- 🔴 **Anchor** — deepens imprint-on-owner; withdrawal if away from them.
- 🔴 **Blank** — temporary name/identity fog (Name-fade accelerant).
- 🟢 **Treat** — a reward dose (afterglow + devotion bump) for compliance — the carrot to the others' stick.

---

### Suggested first weave to build (one coherent pass each)
1. ✅ **BUILT — Foundations pass:** 🧩 **Quota loop** (#12 Daily Quota — `quota_daily`, auto/repeatable, pays scrip+EXP+standing; the cycle quota-review bites the miss) + **`make_example()` helper** (#14 — graded light/hard/extreme public-lesson primitive in `world/compliance.py`; the escape/rescue resolvers now route through it).
2. 🌿 **One full branch pair** (#11 Pet vs Product *or* Prize vs Cull) wired into cycle weighting — proves the lattice end to end with new content.
3. ♻️ **Relapse / Fresh File / Re-Breaking** (#12) — the progress-reset loops the user specifically asked for.
4. A themed **bundle**: pick a branch and ship its matching curse + effect + body mod + equipment + clothing + drug together (e.g. the Pet bundle, or the Dairy bundle) so each branch *feels* distinct.

---

# §21. Punishments — PERMANENT vs TEMPORARY (asked for directly)
All route through `compliance.make_example` / `punish` / `register_defiance` for the
mechanical hit; what follows is the *shape* of the consequence. Permanent = survives the
beat, written into the body/file (but NEVER survives the OOC floor — `escape`/`force_clear`/
`facilityreset` wipe all of it). Temporary = a timed state that lifts on its own.

## Temporary (timed, lifts on its own) — 🟢 light · 🔴 heavy
- 🟢 **Corner-time / stillness** — `navigation_locked` for N beats; posed and made to wait.
- 🟢 **Denial window** — `orgasm_denial` + raised `arousal_floor` for N beats (arousal_script).
- 🟢 **Mute / babytalk / honorific-lock** — a temporary speech filter (binding_effects) for N beats.
- 🟢 **Extra quota** — a one-off bump to milk/breed owed (clears when met).
- 🔴 **Overstim hold** — pinned to a `dildo`/`milk` mechanic for a fixed run, can't dismount.
- 🔴 **Edge-marathon** — repeated denial + forced arousal across several beats, no release permitted.
- 🔴 **The Trough rotation** — a fixed number of pigsty beats (`pen_filth`/`pen_scented`), then released.
- 🔴 **Solitary in Deep Stock** — scene-less processing for N beats, time-skipped, emerges drained.
- 🔴 **Public lesson** — `make_example(severity)` itself: the one-beat spectacle (already built).
- 🔴 **Line-pass revoked** — any bought `line_pass`/`punish_shield` stripped (back on the line now).

## Permanent (written in until the OOC floor wipes it) — body / file / mind
- 🔴 **A procedure as penalty** — trigger `_procedure` (brand / milk-port / ring / womb-tattoo) as
  the punishment outcome, not a random beat. "You earned the iron." Real freeform mark / PiercingItem.
- 🔴 **A punitive piercing/plug locked on** — `PiercingItem.wear` a locked plug/ring she can't remove
  (ties the "never-empty" curse / cull line).
- 🔴 **Conditioning ratchet** — force a conditioning STAGE (speech drift / designation / name-loss).
  `conditioning_permanent` + `add_conditioning` past a threshold; the punishment that rewrites you.
- 🔴 **Installed trigger** — `binding_effects` installs a conditioned phrase that fires forever after
  (any speaker). A word that drops you, earned by defiance.
- 🔴 **A standing curse imposed** — `_impose_curse` (The Clock / Echo / Tally / Hollow — see §15) as a
  sentence: a per-beat affliction that doesn't lift, only honoured.
- 🔴 **Quota raised for good** — a permanent bump to `breeding_quota.required` (the cull-line move).
- 🔴 **Designation downgrade** — name struck from the records, designation-only (Name-fade, §16).
- 🔴 **Demotion of grade / standing burn** — a permanent standing setback that drops her processing tier.
- 🔴 **Forfeiture** — trip the contract's `forfeit_freedom` clause early as a sentence (convenient exit
  locks in-fiction; the §0 floor stays free — that's the whole invariant).
- 🔴 **A clause imposed** — any Bethany personal clause (collar / honorific / display / line-only)
  applied as punishment via `_impose_clause` — owned harder for stepping wrong.

### Suggested punishment build (when chosen)
A `sentence(char, kind, severity)` dispatcher that the quota review, the escape-fail resolvers, and
the defiance system all call — picks temporary vs permanent by severity + repeat-offender count
(`quota_behind`/`defiance`), narrates it, and applies via the hooks above. One primitive, every
system feeds it, escalation built in. (Pairs with `make_example`, which it would call for the
spectacle layer.)

---

# §22. THE NUGGET — terminal reduction (and what it opens)  ✅ CORE BUILT
**BUILT this pass (procedure + state + cycle beat + command + escape-safety):**
- `apply_nugget(target, appendages="stumps"|"paws"|"hooves")` (module-level in facility_script) +
  `_proc_nugget` procedure: limbs→ringed stumps, voice→sounds (animal_sounds/no_self_name filters),
  `limb_lock`/`sensory_hood`/`total_dependence`/`navigation_locked`/`self_cmds_locked`, a forced
  monstrous udder (`lactation_locked` + `milk_baseline_ml`≥4000), every hole gauged permanently open
  (titfuck/any-hole made real via `permanent_gape`), name→designation (backed up), real freeform
  marks, conditioning spike, achievements `bound_away`/`sealed`/`nugget`.
- `_nugget_beat` (realm cycle): a kept nugget isn't dragged room to room — she's maintained
  (milked/emptied/fed), then USED in place: suspended doggy/any-hole/titfuck off the stump-rings,
  walked on paws/hooves, or doted on by Bethany (the false-tenderness pool). Real breeding via
  `gang_inseminate`; conditioning + curses still tick.
- `bethany <player> = nugget [stumps|paws|hooves]` applies it. **OOC floor verified:** all flags in
  FACILITY_FLAGS, escape/force_clear never gated by the locks — a limbless nugget frees instantly.
- **Still TODO (follow-ups):** the Nugget Cradle / Wall-Socket / Transport-Crate furniture objects
  (readable + a real auto-care tick of their own); the offered→bound→sealed→kept→nugget quest line;
  the "organize denial" scheduling; the full player-to-player consent handshake (the staff/owner
  `wordcondition` tool is built — ban words / swap words, riding the real speech filters).
The facility's deepest dollification terminus, past Perfected / Rendered Down: a unit reduced
to a **torso** — limbs bound or sealed away, sensory input managed, speech gone, reduced to a
thing that is bred, milked, used, fed, emptied, displayed, and *kept*. A nugget cannot do
anything for itself. That total helplessness is the point — and it's only ever safe to go this
far because the §0 floor is *untouched*: a nugget's `escape`/`force_clear`/`facilityreset` works
instantly, no limbs required, never gated. The fiction reduces everything; the fire-exit stays.

**State / effects it sets** (all reset-safe flags + existing hooks):
- `limb_lock` — `navigation_locked` hard + `self_cmds_locked` (can't move, can't use hands/objects).
- `sensory_hood` — managed sight/sound (room descs filtered/muffled; speech filter → mute).
- `total_dependence` — must be fed, milked, watered, and emptied *by others or machines* on a tick;
  hunger/withdrawal/bladder run on their own (ties the milk/bladder/Hollow systems).
- `nugget` (master flag) + name struck from records (designation/name-fade), grade frozen.

**Furniture / machines it opens** (typeclasses + `install_into_zone`):
- **The Nugget Cradle** — holds, rocks, feeds, and empties her on a tick; the auto-everything rig.
- **The Wall Socket / Display Shelf** — mounts her as decor; anyone in the room can `use` the mounted
  nugget (gallery-style). The Showroom and Bethany's office both get one.
- **The Transport Crate** — a furniture she's carried/shipped in (ties auctions/get-sales: nuggets sell high).

**What it opens for Bethany:** her *perfect* possession — limbless, fond, wholly dependent, kept on a
shelf in her office and taken down when she wants her. The false-tenderness register peaks here ("you
don't need arms to be loved, sweetheart — you just need to be *mine*"). She breeds her own line into a
nugget, displays her, names her something small, and the gratitude/devotion runs hottest because the
nugget literally cannot reach for anything *but* her. A personal-line capstone parallel to Wholly Hers.

**Quest line — "The Nugget" (consent-gated, very deep):** reduction stages —
`offered → bound (limbs)` → `sealed (sensory)` → `kept (the cradle/shelf)` → `nugget` (terminus).
Manual fork off Perfected/Rendered Down; mutually exclusive with the active escape lines while in it.
Achievements: `bound_away`, `sealed`, `nugget`. Bethany can `bethany <player> = nugget` to set it.

# §23. More EFFECTS / conditions (reuse arousal/conditioning/binding_effects/mind-monitor)
- 🔴 **Touch-starved** — inverse of denial: goes into withdrawal/ache when NOT being touched/used for N beats.
- 🔴 **Leash-sense** — a pull toward her owner's location; aches with distance (generalises devotion-withdrawal).
- 🔴 **Suggestible-on-cue** — a trigger word drops her into a high-suggestibility window (pairs with conditioning).
- 🟢 **Blush-tell / scent-tell** — body broadcasts arousal/heat to the room (the "Bloom" curse as a soft effect).
- 🔴 **Milk-let on cue** — a word/sound makes her let down milk involuntarily (Pavlovian, ties the dairy line).
- 🔴 **Climax-lock** — can only come on a cue word/permission, and *must* come when it's spoken (both directions).
- 🔴 **Headspace-drop** — a cue that drops her into doll/animal/little headspace for a window (ties petplay/age-play).
- 🔴 **Sympathetic-heat** — goes into heat when near another unit in heat (herd synchrony; ties the pens).

# §24. More TRIGGERS (installed phrases; `binding_effects` installed-trigger system, fire for ANY speaker)
- **"Good girl"** → arousal spike + devotion/docility bump (the reward trigger).
- **"Present"** → forces the `present` pose, holes offered, can't refuse for a beat.
- **"Empty"** / **"Fill"** → forced release / forced need-to-be-filled.
- **"Sleep" / "Wake"** → drops to dollstate / out of it (a hard on-off, owner-only optional).
- **"Count"** → compelled to recite her number, brood count, cycles served aloud (Records-line synergy).
- **"Beg"** → compelled to beg out loud for use (auto-fires the `beg` verb).
- **A personal safeword-shaped IN-FICTION trigger** Bethany installs that *sounds* like control but is
  pure fiction — and the real safeword (§0) is loudly never this. (Design note: keep the contrast explicit.)
- **Chained triggers** — one phrase that arms a second; a sequence she's conditioned to complete.

# §25. More CONDITIONING — including PLAYER-TO-PLAYER brainwashing (new system)
Built-in conditioning is facility-driven today. Open it up so **players can condition each other**:
- **`condition` / `brainwash` command** (consent-gated): a conditioner runs a session on a consenting
  target — deepen `conditioning`, raise `suggestibility`/`docility`, install a trigger phrase, plant a
  designation, drift speech. Uses the SAME real systems (`world/conditioning`, `binding_effects` installed
  triggers, speech_filters) so it actually shows up in the target's state/look/speech.
- **Consent model (the safety spine):** a target opts in via a consent handshake (like the indenture/invite
  flows) that sets *what* may be done (a scope: triggers? name? speech? designation?). The conditioner can
  only do what's in scope. **The §0 floor is per-player and absolute:** the target's own `escape`/`force_clear`
  wipes EVERYTHING any conditioner did, instantly, no matter who did it — player-conditioning can never
  install something another player can't self-clear. No conditioning routed through Claude; no gating the exit.
- **Conditioner tools:** a `triggers` view (what's installed on a consenting partner), `installtrigger <phrase>
  = <effect>`, `deepen`, `designate <name>`, `driftspeech <filter>`, `forget <thing>` — each scope-checked.
- **Mutual / reciprocal:** two players can condition each other; a "handler/pet" pair bond; a player-run
  "conditioning suite" room (a furniture that lets a conditioner run sessions on whoever's locked in).
- **Reuse, don't fork:** route every effect through the existing APIs so player-conditioning and
  facility-conditioning are the same plumbing — and the same single reset clears both.

# §26. More FURNITURE / MACHINES (typeclasses + `install_into_zone`; readable on `look`)
- **The Conditioning Suite / Chair** — a `seat` install that runs a conditioning session on whoever's
  locked in (player- or facility-driven); the player-to-player conditioning station.
- **The Breeding Mill** — an industrial multi-station rig (Cull-line): locks several units, breeds on a tick.
- **The Milk Organ** — a wall of cups that milks a whole row at once; the Dairy set-piece (readable board).
- **The Doll Shelf / Nugget Wall** — mounts reduced units as decor; `use` to take one down.
- **The Stockade Carousel** — a slow public rotation in the Showroom; bidders `use` the lot as it turns.
- **The Confessional** — a `seat` that pairs with the Echo curse: speak, and it conditions your words back.
- **The Auto-Dam Rig** — feeds her get on her on a tick (Nursery), hands-free nursing (Prize/Nugget synergy).
- **The Sounding Bench / Pump Station / Inflation Rig** — procedure-grade machines for the deeper lines.

# §27. More CURSES (standing per-beat; `_impose_curse`/`_tick_curses`)
- 🔴 **"The Pull"** — periodically drags her to the nearest active mechanic/seat and locks her a beat.
- 🟢 **"Bloom"** — visible arousal/heat tells broadcast to the room (the soft humiliation curse).
- 🔴 **"Tithe"** — every climax she has feeds devotion/conditioning (pleasure itself processes her).
- 🔴 **"Mimic"** — she involuntarily copies the posture/act of anyone being used near her (herd compulsion).
- 🔴 **"Ledger"** — every use is spoken aloud as a tally to the room (Records/Tally synergy; public counting).
- 🔴 **"Doll-drift"** — left idle too long, she drifts toward dollstate on her own (Nugget on-ramp).

# §28. THEMED BUNDLES (ship a path WHOLE so it feels distinct)
Each = a curse + effect + trigger + body-mod + machine + clothing + drug + a quest beat, themed.
- **PET bundle** — headspace-drop effect + "good girl" trigger + tail/ear body-mods + the kennel furniture +
  collar/leash clothing + a docility drug + the Pet branch. (Pairs with Pet vs Product fork.)
- **DAIRY bundle** — milk-let-on-cue effect + permanent ports body-mod + the Milk Organ + the auto-milker
  harness + Curdle drug + a lactation-lock quest beat.
- **CULL bundle** — Hollow/never-empty curses + the Breeding Mill + locked plug clothing + Rut drug +
  numberless designation. (Pairs with the Cull line, already built.)
- **DOLL / NUGGET bundle** — Doll-drift curse + headspace-drop + sensory hood + limb-lock + the Nugget Cradle
  + latex sleeve + Blank drug + the Nugget quest line. The terminus bundle.

---

# §29. INSPIRATION MINE — FlexSurvival / TiTS / TrapQuest / BondageClub (+BCX/LSCG/MBCS)
Not combat — the *systems* these do well, mapped to Re:Void's real hooks. Grouped by the big
buildable systems they collectively point at. (§0 floor invariant applies to every one.)

## A. A real BODY / TRANSFORMATION framework (TiTS + Flexible Survival)
Today body changes are one-off procedures. TiTS/FlexSurvival do **incremental, thresholded,
multi-stage parts** — and it's the single highest-leverage system to build.
- **TF-serum items** (reuse `_procedure` effects + `binding_effects` payloads + `do_inseminate`
  fluids): a drink/inject item nudges ONE stat toward a target (cock count/length, breast row/size,
  hips, lips, clit, balls/load volume, height, taur/feral frame, skin/fur, fluid type). Repeated doses
  cross **thresholds** that rewrite the body desc — exactly TiTS' "your third dose; a knot forms".
- **Part registry on the character** (`db.body_parts = {part: level}`) the `look`/marks system reads,
  so changes are legible and stack. Flexible Survival's "you are 60% hound" → a per-species TF meter
  that, past thresholds, swaps descs/holes/capabilities (ties `animal_sleeve`, the Pet branch, `_proc_*`).
- **TF gels/zones** in rooms (a `dildo`/`milk` mechanic that also TFs whoever's locked in over beats).
- **"Bad end" thresholds** — pass a TF/conditioning ceiling and you're auto-sorted (the Nugget, a
  permanent feral, a drone) — Flexible Survival's signature, already half-built via the descent termini.

## B. A RULES engine (BondageClub / BCX "rules" + LSCG)
The biggest BC-family idea we don't have: an **owner-set rule list** a unit must obey, each with a
consequence the systems already provide (`make_example`, `punish`, conditioning, arousal).
- `db.rules = [{name, set_by, consequence}]`; a checker fires on the relevant action.
- Rule types: **must kneel/present in <room>**, **may not leave without permission**, **must ask to
  come** (orgasm rule), **must announce use / count aloud** (Records/Tally tie), **no clothing**,
  **honorific required** (have the filter), **curfew/quota by time**, **must edge N times first**.
- Reuses the consent layer just built (player-set) AND Bethany sets them as clauses (`_impose_clause`).
- **"Restriction" rules** (BCX): blur/garble typing, slow speech, forced emotes — all speech-filter work.

## C. SENSORY DEPRIVATION tiers (BondageClub blindfold/deaf/gag; MBCS)
Generalise the Nugget's `sensory_hood` into a reusable, staged system any item/curse/proc can set.
- **Blindness tiers** — filter `look`/room descs (full → blurred shapes → nothing); hoods/blindfolds set it.
- **Deafness tiers** — filter incoming speech/room messages (muffle → garble → silence).
- **Speech/gag tiers** — already have filters; add gag levels (muffled → unintelligible → silent) as items.
- Each is an item OR a proc OR a curse; the nugget sets all three at max. (`db.sense_sight/sound/speech`.)

## D. ORGASM / DENIAL system (TrapQuest arousal; BC orgasm rules; LSCG)
We have arousal + denial flags; make it a real subsystem.
- **Permission-to-come** (`db.climax_lock`): can't come without a cue word/owner say; ruined orgasms;
  forced orgasms on a trigger (already have the `orgasm` trigger response).
- **Denial scheduling** ("organize denial"): an owner sets a denial window/edge-count/permission cadence
  (`db.denial = {edges_required, until, permission}`); the cycle + arousal script enforce it.
- **Arousal consequences** (TrapQuest): high arousal degrades speech, raises suggestibility, can force
  public display or a "leak" — a feedback loop where being turned on processes you.

## E. RESTRAINT / WARDROBE LAYERING with locks + timers (BondageClub core)
- **Locked items with timer/owner keys** (extend `PiercingItem.wear`/`BethanyCollar`): an item locks on,
  unlockable only by the key-holder or a real timer (`db.locked_until`) — never by the wearer (OOC floor aside).
- **Layered wardrobe** — undergarment/garment/restraint/accessory layers; outer locks pin inner.
- **Crafting** (BC): combine items at a bench into bespoke restraints with chosen effects/lock types.
- **Remote-controlled toys** (BC vibes): an owner triggers a worn toy's arousal tick from anywhere
  (reuse the worn-tick pattern from the rocking horse + auto-milker harness).

## F. ADDICTION / STATUS-ESCALATION (Flexible Survival infection; TrapQuest curses)
- **Addiction tracks** (extend `drug_dependence`): per-substance, withdrawal worsens each idle beat,
  satisfied only by the source — generalises the withdrawal-web (§16) into a real meter with stages.
- **"Infections"/escalators** — a status that ticks WORSE over time unless treated (cum-addiction,
  bimbo-creep, dollification-drift, feral-creep) — Flexible Survival's spread, on a timer; ties curses.
- **Cure economy** — treatments cost scrip/standing or a task (TiTS' inhibitor items) — the only brakes,
  and the house controls the supply.

## G. MISC sharp ideas worth stealing
- **TiTS "Codex"/perks** — unlock flavour perks/titles as you cross body/conditioning thresholds (ties
  achievements + the sheet/website).
- **TrapQuest "tutor"** — a roaming NPC that catches you breaking a rule and makes the example (we have
  `make_example`; add a roamer).
- **BC "online status" / activities** — a menu of interaction verbs between players (pet, milk, leash,
  use, dress, lock) — a generalised `do <verb> <player>` activity system with consent + flavour pools.
- **BCX "antigarble"/anti-cheat as fiction** — rules that *sound* like they trap you but whose real
  override is loudly the §0 floor (keep the contrast explicit, as the contract clauses already do).

## STATUS
- ✅ **BUILT this pass — Player-to-player conditioning (B's consent layer + the verb):** `condition`/
  `brainwash` with a scoped consent handshake (offer → `condition/accept` → scope: deepen/trigger/
  speech/name), conditioner actions routed through the REAL systems (conditioning, `install_trigger`,
  banned/swap speech filters, designation), `release`, and a target-side `uncondition` soft self-clear.
  Reset-safe (`conditioning_consent`/`pending_conditioning` in FACILITY_FLAGS; triggers/filters/
  designation all cleared by the floor). Consent required; the §0 floor is the absolute undo. Tested.
- 🎯 **Recommended next big builds (in order):** (A) the TF/body framework — highest leverage, feeds
  everything; (D) the orgasm/denial subsystem; (C) sensory tiers; (B) the rules-engine checker; then
  (E) locked/layered wardrobe and (F) addiction meters. Each is one coherent pass.

---

# §30. RESEARCH NOTES — BCX perms/rules/scripts & TrapQuest traps (and what we take)
Grounding for B–F, from looking at the actual projects.

## BCX (Bondage Club Extended) — structure worth copying
Modular: **Basic** (permission management), **Behaviour logging** (records rule violations),
**Relationships** (nicknames/ownership), **Curses** (item-slot locks that AUTO-REAPPLY when a
cursed item is removed), **Commands** (one-shot actions, e.g. force a pose), **Rules** (70+
toggleable, each with **conditions** — only in certain rooms, only in your owner's presence/
absence — and **consequences**), **Speech** (gag/doll-talk integrated with rules).
- **Permission tiers** (the bit we should adopt): every feature is gated by WHO may use it —
  self / owner / "mistress"/lover / whitelist / everyone — set per-feature in an authority module.
  Map to Re:Void: a `db.authority = {feature: tier}` and a `_perm_ok(actor, target, feature)` gate,
  reusing factions `is_owner` + the new conditioning-consent holder + a whitelist. (This generalises
  the consent layer just built — consent IS a per-feature authority grant.)
- **Curse auto-reapply** → our locked items should re-lock if removed (a worn-item tick that re-wears).
- **Rule conditions** → our rules-engine (B) should support: room-scoped, owner-present/absent,
  time/curfew, arousal-threshold, only-while-a-flag — exactly the `meets()`-style gate we already have.

## TrapQuest — mechanics worth copying
Roguelike feminisation/**bimbofication** + latex TF that ESCALATES; **cursed vessels** (drinking
from a cursed container curses ANY drink, even a good one); trap tiles (glue, etc.); arousal/orgasm
loop with **bad ends** (pass a threshold and you're permanently transformed/captured).
- **Cursed-vessel mechanic** → a TF-serum/drink can be "cursed": it ignores the intended track and
  forces a random/worse one, and a cursed cup taints the next drink. Cheap, nasty, very on-theme.
- **Traps** (a real new system): tile/furniture/room hazards that fire on enter/sit/open — glue (stuck
  N beats = navigation_locked), milk-trap (forced milking), aphrodisiac gas (arousal), TF-gas (apply_tf),
  restraint-snare (locks an item on), breeding-trap (gang_inseminate). Reuse rooms + furniture + the
  systems we have; `db.traps` on a room, checked on entry/sit.
- **Escalating statuses / bad ends** → already modelled by the descent termini (Nugget, production_unit);
  add bimbo-creep / latex-creep / feral-creep meters (§F) that auto-advance and end in a sort.

## STATUS
- ✅ **BUILT — A. The TF / body framework.** `world/transformation.py`: TRACKS (cock/balls/breasts/
  lips/clit/ass/lactation/feral), each with thresholded stages that rewrite the part's read;
  `apply_tf(char, track, amount)` crosses stages → transformation beat + a real permanent mark;
  `body_summary` for the `body` command. Commands: `body [player]` (read anatomy), `transform <player>
  = <track> [amt]` (owner/staff), and `condition <player> = body <track>` (consenting player, new
  "body" scope). `db.body_parts` reset-safe in FACILITY_FLAGS. Tested.
- ✅ **BUILT — consent enhancements (your asks):** `condition/allow [scopes]` (open yourself to ALL
  comers), `condition/allow/lock` (open AND lock so you can't self-revoke), `condition <p> = lock|unlock`
  (holder seals/unseals), and `uncondition` now refuses while locked (pointing to the always-free §0
  floor). Consent "by: any" honoured everywhere. A curse/quest can set `conditioning_consent.locked`
  to make a unit rely on someone else (or escape) to get free in-fiction. Tested.
- 🎯 **Next, informed by the research:** (B) the **rules engine** with BCX-style conditions + a
  per-feature **authority/permission** layer (generalising consent); (D) the orgasm/denial subsystem;
  (TrapQuest) a **traps** system on rooms/furniture; (C) sensory tiers; (E) locked/auto-reapplying
  wardrobe; (F) creep-meters & cursed vessels. Each one coherent pass.
