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
Existing: line_remembers, never_empty. Add:
- 🔴 **"The Clock"** — every beat not spent being used raises arousal/withdrawal; idleness itself punishes.
- 🔴 **"Echo"** — anything said to her is repeated back in her own voice a beat later (speech filter),
  conditioning her own words into her.
- 🔴 **"Tally"** — a visible body tally (freeform mark) that must be "paid down" by use; grows if not.
- 🔴 **"The Pull"** — periodically drags her toward the nearest active mechanic/seat and locks her a beat.
- 🟢 **"Bloom"** — cosmetic: she scents/flushes visibly when aroused, broadcast to the room (humiliation, light).
- 🔴 **"Hollow"** — caps how full she can feel; cum/milk never satisfies, the empty-ache is permanent-on.

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
1. 🧩 **Quota loop** (#12 Daily Quota) + **make_example helper** (#14) — gives repeatable spine + a reusable punishment primitive everything else can call.
2. 🌿 **One full branch pair** (#11 Pet vs Product *or* Prize vs Cull) wired into cycle weighting — proves the lattice end to end with new content.
3. ♻️ **Relapse / Fresh File / Re-Breaking** (#12) — the progress-reset loops the user specifically asked for.
4. A themed **bundle**: pick a branch and ship its matching curse + effect + body mod + equipment + clothing + drug together (e.g. the Pet bundle, or the Dairy bundle) so each branch *feels* distinct.
