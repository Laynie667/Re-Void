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
