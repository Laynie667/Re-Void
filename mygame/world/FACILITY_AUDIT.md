# The Facility — Audit, Conflicts, Bugs & Improvements

A living review of the realm/facility systems for **your** review. Maintained by the
build loop. Severity: 🔴 bug/conflict · 🟡 risk/inconsistency · 🟢 improvement idea.
Items get struck through / moved to "Resolved" as they're fixed.

---

## 0a. Deferred / TODO (action items needing your call or a live test)

- ⏳ **OOC / wisp login-path rework** (`accounts.py` `at_post_login` + the unpuppet flow +
  `wisp_commands.py`). Phase 2 (afk) is **DONE & shipped**. Remaining — reskin "wisp"→OOC,
  cut the roaming-ghost (`wisp_location`/`wisp_visible`/`wisp_preference`), and slim the
  ~1.76k-line wisp cmdset — all touch the **login path, which can't be run-tested in the
  sandbox**, and the reskin is coupled to the roaming cut. **Land together with one live
  login test.** Plan + keep/cut triage: `world/OOC_REDESIGN_PROPOSAL.md`. KEEP regardless:
  `sheet`, `portrait`, character `mood`/say-pose colour (all character-level, unaffected).
- 🟢 **Dead code from the cmdset-collision fix** (low priority cleanup): `scene_commands.
  CmdKnock` (now unexported — superseded by the unified `door_commands.CmdKnock`) and
  `proximity_commands.CmdAside` (no longer added — RP `aside` is canonical). Both classes can
  be deleted whenever; harmless as-is.
- 🟢 **Duplicated name-helpers** (DRY): `_char_name` (5 modules), `_char` (4), `_name` (3),
  `_mood_color` (2), `_find_character` (2) are copy-pasted. → Centralise into a shared
  `commands/_helpers.py`. Low-risk but touches many files — a deliberate refactor, not a blind one.
- 🟢 **One TODO marker:** `world/build_forming.py:936` — placeholder `#2` to swap for the
  real hub dbref "once it exists." Cosmetic.

## 0. Operational note (read first)

- 🟡→✅ **Getting new rooms without losing state.** Previously you had to `teardown_realm`
  + `build_realm` (losing nothing on the *character*, but rebuilding the whole realm). **Now
  there's `facility_upgrade(owner)`** — `@py from world.realm_build import facility_upgrade;
  facility_upgrade(me)` — which adds *only the missing* rooms/exits/staff-placards/office
  anatomy into your existing realm in place, idempotently. Full rebuild is still available
  but no longer required to see new work.
- 🟡 **The rp_name → alias fix only applies on next login** for already-puppeted
  characters (`at_post_puppet`). If page/tell/emote still can't find someone mid-session,
  they should relog once (or `setname <same name>`).

## 0b. Recent passes (build log, newest first)

- 🟢 **The works, batch 1: quota spine, real installs, curses, clauses, live get-auctions.**
  **Real room installs (data-driven):** floor gains automated `milkstall` (milk mechanic) + a
  `matingbench` (dildo); pens gains a `machine` breaking-saddle (dildo); restroom's glory-hole `wall`
  is now a real `dildo` install. `facility_upgrade` gained a **zone-merge step (1a)** so existing
  realms pick these up, not just fresh builds. **Quota spine:** `compliance.quota_status` (shape-
  tolerant — handles both breeding_quota shapes, milk, arrears; tested), the `quota` command, and a
  `FacilityQuotaBoard` furniture on the floor (built + migrated). **Two curses:** `_impose_curse`
  (laid in during deep conditioning) + `_tick_curses` honored every beat — `line_remembers` (a matured
  get in the room breeds its dam unprompted) and `never_empty` (unfilled beats spike ache + arousal).
  **Two Bethany clauses:** `tithe` (10% of every earn skimmed to the house, honored in the earn hook)
  and `heir` (one get per litter pulled and kept by Bethany; honored in `_mature_get`, skipped by
  `_sell_get`). **Live get-auctions:** `_post_get_lot`/`_get_bid_step`/`_get_gavel` — an isolated
  timed trio that puts a grown get on the block as a live lot players can `bid` and steal at the wire;
  `_showroom` posts live when a gallery's present, else the instant `_sell_get`. All new flags in the
  reset spec. Compile + brace-scan clean; quota shape-tolerance tested. ⏳ **Needs a live test** (the
  new installs, the get-auction delay/charge path, curse honoring on a running cycle).
- ⚠ **CONFLICT (catalogued): two `breeding_quota` shapes.** `binding_effects`/`compliance`/
  `gang_breeding.quota_met` use `{species: {current, required}}`; `facility_script._choose_destination`
  reads `{species: int}` (does `int(v)` on the value, which would raise on a dict). They don't crash
  today because the realm path seeds the int shape, but `quota_met` returns False against the int
  shape and `_choose_destination` would error on the dict shape. `quota_status` is written to tolerate
  both. **Fix owed:** pick one shape (recommend `{sp:{current,required}}`) and adapt
  `_choose_destination` + the seeders. Not yet done — flagged for a dedicated pass.


- 🟢 **The Records Hall & The Ledger (big themed pass).** Built #1 + #2 plus a connected bundle.
  **Records Hall:** a real 14th realm room (`records` in `realm_build.py`) — lineage wall, open
  ledger, appraisal mirror + cataloguing stool (real `seat` mechanic install); data-driven so both
  `build_realm` and `facility_upgrade` create it, its exits, the registrar NPC, and a readable
  `FacilityLedgerBoard` (shows the looker's own live account). Cycle phase `_records_hall` wired into
  dispatch + `_choose_destination` (weighted by line/debt) + `_REALM_SEQUENCE`. **Debt + consensual
  indenture:** `spend_credits(allow_debt=True)` carries markers to `DEBT_FLOOR`; the gavel pushes
  unaffordable wins into real arrears; `tab` + `indenture`/`indenture confirm` commands; `_do_indenture`
  flips a *consenting* player to stock (mark, conditioning, debt cleared, cycle if realm present).
  **Consent floor honored:** indenture is opt-in only, never automatic, never on a third party without
  their `confirm`; `escape`/`force_clear` free an indentured member at any balance. Plus: **ledger-
  tattoo** player-zone install (`_ledger_tattoo`), **`ledger` Bethany clause**, **`arrears` drug**,
  two new upgrades (`archive`/`collections`). All new flags in the reset spec. Compile + brace-scan
  clean; debt/indenture math + upgrade ladder tested standalone. ⏳ **Needs a live test** (new room
  build/upgrade/teardown, the seat install, the ledger board render, the indenture conversion +
  cycle-start) — can't run Evennia in-sandbox. **Follow-ups:** indentured member's own cycle when no
  realm; registrar dialogue tree; shared house-account object.
- 🟢 **House treasury, reinvestment, bounties, polaroids, records hall.** The skims became real
  money. A per-instance treasury (`db.facility_house`) takes a 25% `HOUSE_CUT` of every sale/get-sale/
  tip/relief, and `_try_reinvest` (on each sale + office visit) auto-buys off the `UPGRADES` ladder
  with **real honored effects**: studs→quota+1, line→cycle interval ×0.85 (restart), suite→cond_bonus,
  cups→milk_bonus, showroom→sale_bonus (in `_appraise`), bounty→`get_bounty` (paid out in
  `_mature_get`). Sales file parlour-style **polaroids** (`_file_polaroid`); new `records`/`wall`
  command pages the lineage + polaroid wall; `vault` extended to show treasury + upgrades. Feedback
  loop: her productivity funds the machine that works her harder. **OOC floor verified:** all new
  keys (`facility_house`/`_ledger`/`facility_upgrades`/`facility_polaroids`/`get_bounty`/`*_bonus`)
  added to the reset spec; treasury/skim never touch the escape path; door free at any balance.
  Compile + brace-scan clean; treasury skim + reinvest ladder + totals tested standalone. ⏳ **Next
  (deliberately deferred):** debt + **consensual** indenture — a member going negative may walk
  *themselves* onto the block, but third-party players are NEVER auto-converted (the OOC consent floor
  covers other accounts, not just the owner); plus a live test of reinvest/bounty/gavel-charge.
- 🟢 **Economy built out — commissary, get-sale, office books (all three).** Closed every open side
  of the scrip loop in one pass. **(1) Commissary (`buy`):** stock spend the scrip their body earned
  on relief (real `_grant_climax`), rest (`line_pass`, honored in `at_repeat`), ease (drops arousal),
  mercy (`punish_shield`, honored in `_choose_destination` to buy off the sty) — every path routed
  through a real system, every line repeating the door is still free. **(2) Selling the get
  (`_sell_get`):** ~40% of showroom visits put one of her matured `FacilityScion` get on the block
  instead of her — appraised, house-bid, sold, a breeder's cut credited to the dam, logged as a real
  mark, pulled from the bred-back roster and deleted (sold away). **(3) Office books (`vault`):**
  Bethany's accounting — full statement + `totals()` + her reckoning of what she spent the stock's
  earnings on; office-gated for stock. **OOC floor verified:** new flags (`line_pass`/`punish_shield`/
  `bethany_owned_get`) added to the reset spec; the commissary never touches the escape path; the door
  is free at any balance, and every surface says so. Compile + brace-scan clean; economy logic
  (earn/spend-gate/totals) tested standalone. ⏳ **Backlog:** live test of get-sale + gavel charge
  (need real objects); a real house-account object so Bethany's skim lands somewhere.
- 🟢 **The economy — scrip + ledger (`world/economy.py`).** The block finally has money under it.
  A real wallet (`db.facility_credits`) + statement (`db.facility_ledger`) on every character, with
  a clean API (`get_balance`/`add_credits`/`spend_credits`/`can_afford`/`earn`/`statement`). Stock
  open at 0 and **earn scrip off their own bodies** each cycle beat (the cruel payslip — `at_repeat`
  → `earn(char, phase)`); members open at a 5000 float and earn `attend` scrip watching a lot open.
  Spending wired in: `tip` charges a per-demand fee (refunded on no-op, ¼ credited to the lot), `bid`
  requires affordability and the **gavel charges the winning player** (`_sell` via `high_bidder_id`),
  crediting the lot a pittance cut of her own price. New `scrip`/`wallet`/`ledger` command (auto-
  registered via `ALL_FACILITY_VERBS`). **OOC floor verified:** `spend_credits`/`can_afford` are
  never on the escape path — the door is free at any balance, in debt or not (stated as a module
  invariant); wallet keys added to the reset spec so a purge wipes the account. Standalone logic
  test passed (seed/earn/spend/overspend-block/statement/clear). ⏳ **Backlog:** stock spend-sink
  (buy relief via `compliance.py`) to close her side of the loop; selling the get; live test of the
  gavel charge.
- 🟢 **Live timed gavel.** A display now opens a real ~80s bidding window (`evennia.utils.delay`)
  instead of resolving in one tick: staged NPC rounds climb the price (20/40/58/70s) with a
  going-once/going-twice countdown, then `_auction_gavel` at 80s auto-resolves to the high bidder
  (player or NPC) or passes the lot in. A watching player can `bid`/`tip` the whole window and steal
  her at the wire. Defensive throughout — falls back to the instant gavel if `delay` won't import,
  every callback re-checks `auction_open`/`facility_active`/ownership + that she's still on the block
  (lapses if the cycle moved her), all in try/except. **OOC floor verified:** `auction_open`/
  `auction_floor` added to the reset spec (both paths call `apply_reset_flags`), so a purge
  mid-auction makes the pending gavel a no-op — the fire-exit is untouched. ⏳ **Needs a live test**
  (delay timing, multi-player bidding into a live window, reload mid-auction) — can't be run in-sandbox.
- 🟢 **NPC clientele bid the block (both-layered audience).** `_npc_bidding` fills the booths with
  a standing NPC clientele that bids the lot up on its own during a display visit — climbing
  `high_bid`, narrating into the gallery, and able to **top a live player's standing bid** (Bethany
  bids hard on hers). Gavel logic made fair to a present player: holds-top → 0.85 (wins), present
  but outbid/idle → 0.15 (more ticks to act), empty house → 0.30. Bethany winning via the bid path
  now sets `bethany_owned`; the player-won gallery announce is gated to non-NPC winners. Per the
  user's "both, layered" call. Compile + brace-scan clean. *Design note:* an NPC can outbid and take
  a lot a player wanted — intended auction tension; the player always has the OOC floor and can
  re-bid while she's on the block.
- 🟢 **Gallery wired into the live cycle.** `_showroom` now poses the lot on the block and cues the
  adjacent gallery (`_gallery_of`) — seated buyers get an open-for-viewing line (floor price +
  standing bid + bid/tip prompt), and a live buyer in the booths raises the gavel chance. `_sell`
  now lets a player's standing `high_bid` **win** at the gavel (beats Bethany's standing bid, at the
  bid price), announces it to the gallery, and clears the auction state. Result: `bid`/`tip` are no
  longer on-demand-only — they fire and matter during real cycles. Compile clean. *Confirmed:* the
  user's call is "opt-in IS the gate" — no per-lot remote-handling toggle; the OOC floor remains the
  sole true exit, untouched by any of this.
- 🟢 **Gallery `tip` — interactive viewing.** The booths can now *direct*, not just price.
  `tip <what>` (milk/breed/dose/pierce/condition/grow/ring/pose) from the gallery resolves the
  showroom + the lot on the block, finds her cycle script, and fires the **same real systems**
  `process` uses on her — broadcast to the floor (visible), the gallery (buyers watching), and the
  lot herself (felt, source hidden). Demands logged to `db.gallery_demands` (added to reset spec).
  Host trigger tree + booth/panel handles updated to surface it. CNC-on-demand by an unseen
  audience; nothing faked — every branch routes through a real subsystem. Compile + brace-scan clean.
  *Watch-item:* `tip` reaches across a room boundary to fire effects on a player who didn't type the
  command — that's intended (she's facility-active = opted in, and posed in the showroom to be shown),
  but it's the first verb that does so. If we ever want a per-lot "no remote handling" toggle, this is
  where it'd hook. The OOC floor is unaffected — `escape`/`force_clear`/purge still end everything.
- 🟢 **Buyers' Gallery + `bid`.** New room behind the showroom glass (tiered viewing booths
  `seat` mech, bid-panel zone, the host + buyers NPCs) and a real multiplayer hook: `bid <lot>
  [amount]` (`facility_commands.CmdBid`) reads/raises `db.high_bid`/`high_bidder` off the live
  `_appraise` floor; owners still close with `process <lot> buy`. Both new flags added to the
  `FACILITY_STATE` spec (cleared by both reset paths). The high bid carries through the glass to
  the lot's room as a reposition she's never told the number behind. Compile + brace-scan clean.
  *Note:* `_appraise` is the single source of price truth — gallery, `process appraise`, and `bid`
  all read it, so price stays consistent across the three surfaces.

---

## 1. Conflicts

- 🟡→✅ **Title-suffix stomping.** The faction grade, the sale, and Bethany's ownership all
  wrote `db.title_suffix` and overwrote each other live (a grade tick could replace "—
  Bethany's"). **Fixed:** `_apply_facility_title` now applies an **ownership-wins** rule —
  if `bethany_owned`/`facility_owner` is set, the grade keeps the faction slot but won't
  overwrite an owner suffix.
- 🟡 **Installed-trigger phrases overlap staff dialogue.** `_check_installed_triggers`
  fires for ANY speaker, and some NPC trees contain words that are also common trigger
  phrases ("good girl", "present", "heel"). `ask`-ing a staffer could incidentally fire
  the player's drop. This is *mostly intentional* (the staff weaponise her conditioning),
  but worth a deliberate decision — maybe NPC `say` from trees shouldn't auto-fire, only
  free-typed speech. *Fix idea:* a `from_trigger_safe` flag on NPC trigger output.
- 🟢 **Zone-desc backups are per-system.** `sleeve_desc_backup`, `belly_desc_backup`, and
  the latex/milk-port nude rewrites each back up independently. They target *different*
  zones today (pussy/anus/mouth vs belly vs nipples), so no live conflict — but if two
  ever target the same zone, restore order would matter. *Fix idea:* one unified
  `db.facility_zone_backup` keyed by zone, written through a single helper.

## 1d. Command-key collisions (NON-facility) — RESOLVED (per user direction)

Two verbs were defined twice and both landed in `CharacterCmdSet`, so one silently shadowed
the other. Resolved on the user's call:
- 🟡→✅ **`knock`** — the door-zone knock was beating the exit-knock, but the user wants
  exit-knock (knock → notify the room beyond, for locked/owned grid rooms). **Merged** into
  one canonical `door_commands.CmdKnock`: `knock <door>` does the built-door zone; bare `knock`
  notifies any destination that's scene-locked / owned / traverse-locked. Removed
  `scene_commands.CmdKnock` from `ALL_SCENE_CMDS` (de-shadowed; class kept for the scene/invite
  flow).
- 🟡→✅ **`aside`** — user notes proximity is "a bit unnecessary," so the RP `aside`
  (`rp_commands.CmdAside`) is canonical. Dropped `proximity_commands.CmdAside` from the
  `CharacterCmdSet` add so the RP one is no longer shadowed.
- ✅ **Everything else dup'd** (say/pose/emote/look/whisper/mutter/ooc/shout) is the clean
  **wisp ↔ character** split — different cmdsets, intentional state-gating, no collision.

**Room-lock answers + features (user Q&A):**
- On a *normal grid room*, `scene/lock` (any room, anyone present) is the working lock —
  it blocks non-invited entry via the room's scene gate; `housing lock` is housing-only.
  Unlock requires being *in* the room (no remote unlock by design).
- ✅ **Resident re-admit via `knock`** — a `housing_residents`/owner who locks their room and
  steps out is added back to the scene invite list when they `knock`, so they get back in
  (the compromise instead of remote-unlock).
- ✅ **`home/tent` switch** — goes to a room you actually OWN (your housing plot), even if
  your `sethome` is a grid room, so builders/residents with a grid home can still reach their
  housing to work on it.

**User design notes (for future work, not yet actioned):**
- *Wisp/OOC layer* "has barely worked as intended" — `wisp` is flavour for being OOC and is a
  candidate for a **redesign/re-envisioning** of the whole OOC-presence concept.
- *Proximity commands* are "a bit unnecessary" — a candidate for slimming/removal.

## 1c. ENTIRE-game sweep (waystone / waypost travel infra)

Four real bugs, all the documented Evennia gotchas, in core travel code:
- 🔴→✅ **Staff waystone registry showed nothing.** `waystone_commands._list_all` scanned
  hubs/portals/wayposts via `search_object(None, typeclass=…)` (→ `[]`), so the whole
  registry always printed `(0)`. **Fixed:** uses the typeclass managers.
- 🔴→✅ **Wayposts always read `[inactive]`.** Same command used `not hasattr(w.location,
  "account")` to mean "is in a room" — but `hasattr(_, "account")` is **always True**
  (rooms included), so the test was always False and every waypost showed inactive.
  **Fixed:** `isinstance(loc, Character)` check.
- 🟡→✅ **Return-hub lookup degraded.** `waypost._get_hub_room` and `waystone.py`'s hub
  resolver both scanned `search_object(None, …HubWaystone)` (→ `[]`), surviving only on a
  `waystone_hub` *tag* fallback — so an untagged hub broke the return trip. **Fixed:**
  `HubWaystone.objects.all()`.
- 🟡→✅ **Address-collision detection disabled.** `waypost._address_in_use` scanned with the
  same no-key trap → always returned False → two wayposts could silently share an address
  (travel ambiguity). **Fixed:** managers.
- 🟡→✅ **Two more fallback hub scans** (`waystone_commands` travel + return paths, lines
  ~146/447) hit the same no-key trap. **Fixed.** ✅ **The no-key `search_object(None, …)`
  gotcha is now fully swept from the entire codebase** — every remaining textual match is an
  explanatory comment or this audit doc, not a live call. All `hasattr(_,"account")` sites
  reviewed: only the two waystone ones were the dangerous (no-truthiness) form; the rest
  guard with `and …account` and are safe.

## 1b. Codebase-wide sweep (beyond the facility)

- 🔴→✅ **`watch/list` always empty (2 sites).** `safety_commands.py` `CmdWatch._list`
  and the admin watch-list both scanned `search_object(typeclass="…Character")` with no
  key — the same `[]` gotcha — so the watch list always reported "not watching anyone."
  **Fixed:** both now use `Character.objects.all()`.
- 🟢 **By-name searches now resolve display names for free.** `economy_commands`,
  `ogram_commands`, `wisp_commands`, `scripts.py` search by `name`+typeclass (the *working*
  pattern) — and since `rp_name` is now registered as an alias (login sync), those resolve
  a character's display name too. No change needed; noted as a dependency on the alias fix.
- ✅ **Whole `mygame/{typeclasses,commands,world}` tree compiles clean** (py_compile sweep).
- ✅ **Hygiene scan clean:** zero bare `except:` across the tree (consistent
  `except Exception:`); no stray-brace `.format` strings; no remaining no-key
  `search_object`; all `hasattr(_,"account")` sites guarded. The known fault classes
  are closed.
- 🟡 **Remaining gotcha audit:** all other `search_object(...)` calls reviewed pass a key
  positional (waystone/waypost/womb dbref lookups, char-by-name) — none hit the no-key `[]`
  trap. The waystone/waypost ones were already corrected to `.objects.all()` in earlier work.
- ✅ **Stray-brace `.format()` crash class ruled out.** AST-scanned all ten pool/scene files
  for any `{…}` token in a string that's later `.format(t=t)`-ed; the only hit is the
  intentional `{zone:%s}` (`%`-format) template. No pool string can throw `KeyError`/
  `ValueError` at runtime. Each multi-token pool (`{who}`/`{price}`/`{owner}`/`{cup}`/
  `{phrase}`) is only ever `.format`-ed by a caller that supplies those keys.

## 1e. Freeform items — comb-over (user-reported: "stuck / unremovable")

The handles existed (`flist` showed them) but were undiscoverable from the zones, there was
no bulk clear, and `undress` mishandled locks. Fixed:
- 🔴→✅ **`undress` wiped ALL freeform — including LOCKED items.** It did
  `char.db.freeform_items = {}`, so a slock/plock'd item (chastity belt, gag) came off by
  undressing. **Fixed:** undress now uses `FreeformManager.remove_all_unlocked()` — clears
  unlocked, **keeps locked**, and reports both.
- 🟢→✅ **Names weren't visible from the zone view.** `look <self> <zone>` showed only the
  description, so you couldn't know the handle to `unplace`. **Fixed:** the self zone-view now
  lists `[items here: <name> …]` with a removal hint.
- 🟢→✅ **No bulk clear.** **Added `unplace/all [target] [zone]`** — removes every unlocked
  item at once (reports any locked ones it skipped). The escape hatch for "stuck" piles.
- ✅ `unplace me <name>` already handled **multi-word names** (`facility mark 1`) and `me`
  — confirmed working; the problem was purely discoverability + the undress lock bug.
- ℹ **Note:** facility marks re-apply each cycle by design (they're the processing); manual
  `unplace` clears them, but the active realm re-marks. Permanent removal is the OOC floor —
  `escape` / `force_clear` / `/purge` — which wipes all facility freeform.

## 2. Bugs

- 🔴→✅ **Office Bethany had no anatomy.** `provision_bethany` was only called for the
  *spawned* visit-Bethany, so the static office Bethany showed no cock on `look` and her
  office breeding never engaged a real penetrator. **Fixed this pass** (provision on
  furnish + `_office` now penetrates with the room's Bethany).
- 🟡 **Duplicate Bethany NPCs.** Intake Bethany + office Bethany are two persistent NPCs,
  and a visit spawns a third transient one. In a room with two, `ask Bethany` / targeting
  multimatches. *Fix idea:* the roaming visit should reuse a single canonical Bethany
  (move her in) rather than spawn, or tag the office/intake ones distinctly.
- 🟡→✅ **`bethany`-line get spawn as `FacilityBeast`.** **Fixed:** new `FacilityScion`
  typeclass (futa get, knotted flare-tipped cock) is used for `species == "bethany"`, and
  `_provision_beast` now gives scions a real futa cock + knot — so her own line breeds her
  back as futa, not animals.
- 🟡 **Demoting a key staffer removes a cycle voice.** `_demote_staff` can demote the
  handler/stockman; the demoted NPC keeps its trigger tree (so `ask` still works) but
  `_drag`'s handler-attribution and `_choose_destination`'s flavour lose their actor.
  Low impact; *fix idea:* protect role-critical NPCs, or respawn a replacement.

## 3. Improvements — character mechanics

- 🟢 **rp_name aliases for NPCs too.** Players will `process the handler` / `kiss bethany`;
  NPC keys already mostly match display names, but syncing `rp_name` → alias on facility
  NPCs (like we now do for PCs) would make every target robust.
- 🟢 **Namespace the facility state.** There are ~60 `db.*` flags now. A single
  `db.facility = {...}` dict (with helpers) would make teardown a one-liner and reduce the
  risk of a new attribute being forgotten in a reset path. Big refactor; high payoff.
- 🟢→✅ **A `forgotten` readout.** **Done:** the mind monitor now shows the FORGET log
  (last 5 redacted items), plus owner/devotion/personal-clauses and the lineage (offspring
  counts + the incest-loop note). `look <her> mind` reads the whole damage now.
- 🟢→✅ **Gape/capability surfaced.** **Done:** the monitor now prints a trained-holes line
  per hole (gape word + what it can take: knot/double/fist/prolapse).

## 4. Improvements — room / world mechanics

- 🟢 **Zone-token budget on big rooms.** `_furnish` tokenises *every* zone into the room
  desc, so rooms with many zones (Office, Pens) produce a long `look`. Consider a curated
  "featured zones" subset for the inline render, leaving the rest to `look <zone>`.
- 🟢 **Ambient cadence.** Room `ambient_msgs` exist but I haven't confirmed a driver fires
  them on a timer in the realm rooms (vs only the cycle beats). Worth verifying an ambient
  ticker runs so empty-room atmosphere lands between cycle phases.
- 🟢→✅ **Witness discoverability.** **Done:** every realm room now gets a "staff handling
  placard" (FacilityFurniture) listing the full `process <unit> <action>` verb set
  (incl. appraise/buy/demote) in-fiction, so visiting players learn how to use the stock.
- 🟢 **Exit flavour.** Realm exits are auto-named from room keys; bespoke exit names/descs
  ("DOWN — Sub-Level P", a sealed hatch) would sell the geography.

## 5. OOC floor — verification checklist (keep current)

Every persistent thing the facility installs must be undone by `force_clear` / `escape` /
`run_facility_reset(purge)`. Confirmed-covered: conditioning, suggestibility, docility,
dependence, cravings, perpetual heat, lactation lock, speech filters, installed triggers,
designation/name, title slots (+ ownership/grade), consent (facility + binding backups),
piercings (facility-tagged), freeform marks, body installs (glands/womb/breast/inflation/
mind monitor + item-created zones), animal-sleeve descs + barriers, pregnancy/belly/cycle,
offspring roster + spawned get, sale/owner, latex, bethany devotion/brand, FORGET log,
realm scripts (realm_cycle/heat/bethany_visit/milking), the escaped meta-loop flags
(`facility_escaped`/`liberation_runs`) + the daily-quota streak (`quota_behind`), all in
`FACILITY_FLAGS` → cleared by every reset path. **When adding ANY new persistent state, add
it here and to all three reset paths.**

**Escaped meta-loop OOC-floor verification:** the Deep Stock malfunction escape, `turnin`, and
`springstock` are pure in-fiction quest resolvers (rolls); none touch `escape`/`force_clear`/
`/purge`, which always work and clear `facility_escaped` along with everything else. The
malfunction is the *building's* way out (rollable, recapturable); the §0 floor is the player's
(never a roll, never gated).

---

*Loop pass 1: office-Bethany anatomy fix, FORGET + DEVOTION drugs + the devotion-withdrawal
ache, the flared+knotted multicock, employees-as-stock (`demote`).*
*Loop pass 2: title-suffix ownership-wins fix, `FacilityScion` (futa get), and Bethany's
bespoke personal clauses (honorific/name/collar/crave/display/line — each a real enforced
term, imposed one at a time in the office, logged + reset-safe).*
*Loop pass 3 (autonomous): in-fiction `process`-verb signage in every room (witness
discoverability), and the office "first-day" breaking-in prose for a new favourite.*
*Loop pass 4: codebase-wide bug sweep — fixed `watch/list` always-empty (2 sites, same
`search_object` gotcha); full tree compiles clean. Added hidden contract clauses H25–H29
(lineage, sale/ownership, FORGET/DEVOTION, Deep Stock, and H29 — the OOC floor named
in-fiction as the one true clause).*
*Loop pass 5: incest lineage prose deepened (her own offspring breed their mother — sons &
daughters, the bloodline folded through her); mind-monitor read-out expanded to show
owner/devotion/clauses, lineage + incest-loop, trained holes/capabilities, and the FORGET
log (two improvement items resolved).*
*Loop pass 6: bug-hunt — AST-ruled-out the stray-brace `.format()` crash class across all
pool files. Content: the office "breaking frame" machine + CNC futility prose (`_CNC_BREAK`)
on the first-day breaking — in-fiction helplessness layered on top of the never-gated OOC
floor (the dread is built on the floor, not in place of it).*
*Loop pass 7: ENTIRE-game bug-hunt — fixed 4 real waystone/waypost travel bugs (registry
empty, wayposts always inactive, return-hub degraded, address-collision detection disabled
— all the no-key `search_object` / `hasattr(...,"account")` gotchas). Content: deepened the
`struggle` verb with CNC futility (owner-aware) + an explicit in-line OOC-floor reminder.*
*Loop pass 8: swept the last two no-key hub scans — the `search_object(None,…)` gotcha is
now GONE from the whole codebase; all `hasattr(…,"account")` sites verified safe. Content:
`BethanyCollar` — the personal "collar" clause now locks a real worn item on her (her B-tag,
honorific + craving + open-consent binding, lock_self_remove), tracked for teardown.*
*Loop pass 9: `facility_upgrade(owner)` — in-place idempotent realm migration (adds missing
rooms/exits/placards/office-anatomy without teardown; resolves the operational re-build
note). Content (my pick, across the board): four new special events — breeding_demo (the
whole barn in order: hounds→boar→bull→stallion), conditioning_broadcast (facility-wide mass
hypnosis), hose_drill (watersports/sanitation), milking_parade (exhibition).*
*Loop pass 10: Room 12 — the Marking Parlour (my pick): a dedicated marking studio (chair/
rack/portfolio zones, the marker NPC, a `mark` cycle phase that runs the real permanent
procedures + the owner's B-brand). Hygiene scan clean (zero bare `except:` tree-wide).*
*Loop pass 11: `process <her> brand|tattoo|portfolio` — a visiting owner can now mark and
catalogue stock in the parlour (real freeform marks; owner's initial on the brand). Bug-
sweep: `search_object(...)[0]`/unguarded `int(self.args)` crash classes — clean (the one
`[0]` hit is inside a docstring). Major fault classes remain closed.*
*Loop pass 12: `FacilityPortfolio` — the parlour now has a real, readable portfolio album
(`look the portfolio album`) that renders the owner-grouped catalogue; `process <her>
portfolio` writes a live entry to it. Auto-added by `facility_upgrade`. Bug-sweep: zero
mutable default args tree-wide; the 44 `except Exception as e:` are lint-smell only.*
