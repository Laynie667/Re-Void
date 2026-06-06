# Design draft — Factions, Realms, Currency, Titles, Housing

Status: **discussion draft** from the talk-through. Nothing built yet. This captures
the agreed shape and flags the open decisions, so we lock it before code.

---

## A. The core model

Two new lightweight registries (data-driven, the way the audit recommended), plus two
stamps on rooms.

### Realms
A **realm** is a named area (a connected grid of rooms with a shared identity).
```
REALMS = {
  "void":     {name:"The Void",      faction:"void",     currencies:["shards"],            hub:<room>, housing:True},
  "facility": {name:"The Facility",  faction:"facility", currencies:["shards","scrip"],    hub:<room>, housing:False},
  "wildwood": {name:"Helena's Wood", faction:"helena",   currencies:["shards","<her cur>"],hub:<room>, housing:True},
}
```
- Each room gets `room.db.realm = "<key>"` (affiliation) and, optionally,
  `room.db.faction = "<key>"` to **override** the owner for that room (a sub-faction
  holding territory inside a realm). If unset, a room's faction = its realm's faction.
- A realm declares which **currencies** are valid inside it (always includes `shards`;
  may add a realm-local one like Facility `scrip`).

### Factions (guild / family / realm-owner / sub)
```
FACTIONS = {
  "void":     {name:"The Void",     kind:"neutral",  parent:None, colour:"|w", invite_only:False, currency:"shards", tiers:[...], leader:None},
  "facility": {name:"The Facility", kind:"realm",    parent:None, colour:"|m", invite_only:True,  currency:"scrip",  tiers:_FACILITY_TIERS, leader:"Bethany"},
  "helena":   {name:"House Helena", kind:"family",   parent:None, colour:"|c", invite_only:True,  currency:"shards", tiers:[...], leader:"Helena"},
  # sub-factions point at a parent:
  "fac_handlers": {name:"The Handlers", kind:"sub", parent:"facility", ...},
}
```
- `kind`: `neutral` (the default Void), `guild`, `family`, `realm` (owns a realm),
  `sub` (a smaller group — NPC crew or player clique — nested under a parent via `parent`).
- Standing already lives in `character.db.factions = {key:int}` and supports many — we
  generalise `factions.py` so **every** faction (not just the Facility) reads its tiers,
  title, colour, and currency from this registry. Facility becomes row 0, not a hardcode.

### The default: **The Void** (neutral) — LOCKED
- The hub and everything currently hanging off it get `realm="void"`, `faction="void"`.
- Neutral mechanically (no grades forced, no invite needed, shards-only).
- **Theme:** semi-fantasy / medieval with **void elements** threaded through. Existing
  anchors: **Durgin's shop**, the **Wayfarers' Hall**, the **post office**. More shops/places
  to come. Light custodian lore (a distant, disinterested keeper) — flavour only, expandable.

---

## B. Stamping existing rooms

You'll run a staff command **in** each space (or bulk over a realm):
```
designate realm <key>             — stamp this room's realm
designate faction <key>           — stamp this room's owning faction (override)
designate realm <key> /here-and-connected   — flood-fill across connected exits
realm claim <key>                 — mark current room as a realm's hub
```
- Bulk flood-fill (`/connected`) walks exits and stamps the whole hub cluster in one go, so
  you're not visiting 40 rooms by hand. (Stops at realm boundaries / hub waystones.)
- The **cabin** stays Void for now; when it moves to Helena's wood, you re-`designate` it
  `realm wildwood faction helena` and link it in.

---

## C. Currency — multi-currency wallet

- **Shards** = the game-wide currency (existing `typeclasses.economy`), unchanged as the
  backbone.
- **Realm-local currencies** (Facility `scrip`, Helena's whatever) — only spendable inside
  realms that list them. Earn/spend is gated by `room.db.realm`'s `currencies`. The governing
  faction **names** its currency, decides whether **outside currency (shards) is accepted** at
  all, and sets the **exchange rate** its shops use (per-realm config).
- **Better wallet:** one unified store + command.
  ```
  character.db.wallet = {"shards": N, "scrip": N, ...}   # shards mirrors db.shards for back-comp
  wallet            — show every balance, grouped, with which realm each is good in
  ```
  Shards keep their existing daily-cap/transfer/log machinery; realm currencies route
  through a thin per-currency adapter. (Facility scrip migrates into this transparently.)

---

## D. Membership — invite-granted, + housing

- `invite <player> to <faction>` (leader/rank/staff) → grants membership + seeds standing.
  `kick`, `leave`, `roster` round it out. Invite-only factions can't be standing-grinded
  into; neutral/open ones can.
- **Residency ≠ membership.** Someone may want to **live in a realm without joining its
  faction**. So realm **residency** is a separate grant from faction **membership** — you can be
  a resident (housing linked, allowed in) without any faction tie. Examine the existing **ogram
  realm-invite** and add a **faction-invite** alongside it (Phase 4): realm-invite grants
  residency; faction-invite grants membership/rank. Independent residents just get the former.
- **Housing connection:** a **resident** may link their **personal housing** room to the
  realm's grid — `connect housing` from a realm housing-nexus, gated on residency (not
  necessarily faction membership). Losing residency unlinks it. (Helena's wood + Void both
  `housing:True`.)

---

## E. Titles — unified, customizable slots

One template, all factions, all realms — **order: grade → faction → realm** (confirmed):
```
{prefix} {grade} {interfix} {faction} {suffix} {realm}
```
- **System-filled:** `grade` (= the member's current **rank title** in that faction; see §G),
  `faction` (membership), `realm` (home/current realm).
- **Player-customizable connectives:** `prefix`, `interfix`, `suffix` — free text the player
  sets, the "the"/"of"/"of" glue between slots.
- Reads as: *"**the** Footman **of** House Dorman **of** Elsewhere"* — prefix="the",
  grade="Footman", interfix="of", faction="House Dorman", suffix="of", realm="Elsewhere".
- Generalises the current Facility-only `title_faction`/`title_suffix` logic; ownership
  stamps (— Bethany's) still win where they apply.

---

## G. Ranks, rep, and advancement (per-faction)

Three distinct things, cleanly separated:
- **Rep / standing** — the numeric score per faction (`db.factions[key]`). The "grade,
  standing, rep" you mentioned are one and the same number.
- **Rank** — a *named position* in the faction hierarchy, **custom-named per faction**
  (House Dorman: Footman → Steward → Lord; Facility livestock: Intake → Breeding Stock →
  Broodmare; Facility staff: Handler → Stockman → Overseer). The rank's name fills the
  `{grade}` title slot. So `_FACILITY_TIERS` generalises into each faction's own rank table.
- **Advancement method** (set per faction):
  - `granted` — set by a higher-ranked member (see grant rules);
  - `rep` — auto-derived from rep thresholds (the Facility model);
  - `points` — a faction-internal points pool awarded for doing things, spent/accrued toward rank;
  - `quest` — flag-gated by completing faction objectives;
  - or a mix (e.g. Facility = rep+quest; a player guild = points+granted).

### Affiliation, sub-factions, and the owner (refined)
- **Affiliation is optional.** A `sub` faction *may* set `parent = <realm's main faction>`
  (an **affiliate** — e.g. the Facility's crews), or keep `parent = None` and remain
  **independent** even while operating inside a realm. Being *in* a realm ≠ being *owned by*
  its main faction. Only the realm's declared owner controls its rooms by default; other
  factions can exist there sovereignly.
- **Multiple ladders, two ways** (both supported; pick per faction):
  1. one faction with several internal **rank tracks**; or
  2. a parent faction with **affiliated sub-factions**, each effectively its own ladder.
  Recommended for the Facility: option 2 — crews as affiliated subs (Handlers, Dairy,
  Marker, Bethany's stable), which also map 1:1 to website lore/portrait pages.
- **Owner role.** Each faction has an **owner/CEO** sitting *above* the rank ladders, with
  authority to rename the faction, define its ranks, set advancement, and restructure. The
  owner's name/style is theirs to set in-game (the system supplies machinery, not fixed
  names) — e.g. Bethany names the corporate entity that runs the Facility ("…Inc", etc.).
- **Cross-faction authority (affiliates only).** A high rank / owner in a **parent** faction
  has authority over its **affiliated** children: they can grant/demote *across* affiliated
  sub-factions, including pushing someone **down into a lower affiliate** — e.g. Bethany (top
  of Handlers / Facility owner) demotes a Handler straight into the **Stock** sub-faction.
  **Independent** factions are sovereign: no external grant/demote reaches them.
- **Bethany, concretely:** owns/names the Facility faction; sits atop the **Handlers** ladder
  (so she can demote handlers); keeps her **own private faction** (her personal stable/line);
  and the demotion path Handlers→Stock is just a cross-affiliate demotion under her authority.


- You may grant or demote **any rank strictly below your own**. You cannot grant a rank
  **equal to or above** your own — so a **leader cannot create another leader**, a mid-rank
  can only move people below them.
- **Demotion** is the same gate in reverse (higher rank can demote lower).
- **Owner/top-authority override:** the one *on top of it all* (faction owner / parent owner)
  can move members up and down ladders **beyond** a sub-faction's own power — override authority
  sits above the in-faction gate. Sub-factions still self-govern internal moves; the owner can
  reach past that. The owner also **sets their own title** freely at the top.
- Factions **define their own rank names + count + advancement method** at creation
  (`faction setrank`, `faction setadvance points|rep|quest|granted`).
- Non-player factions (Facility, House Helena) advance however the faction's owner decides —
  quest-driven, financial, rep, or staff fiat — same data model, NPC/owner pulls the levers.

## F. Phasing (so we ship working increments)
1. ✅ **Foundation (DONE):** `world/realms.py` registries + room `realm`/`faction` stamps +
   `designate` flood-fill + `realmhere` + the Void default.
2. ✅ **Titles (DONE):** the existing title system already had prefix/level/interfix/faction/
   suffix slots + a player `title` command (prefix/interfix/suffix customizable). Added the
   **realm slot** (`title_realm`, rendered after suffix → grade→faction→realm), a `title realm`
   setter, and `realms.apply_realm_title(char, key)` to fill it from the registry on residency.
   *Reconcile-later note:* the `{level}` slot is driven by a **global** `db.reputation` tier,
   separate from per-faction `db.factions` standing — Phase 4 makes `{grade}` faction-rank-aware.
3. ✅ **Multi-currency wallet (DONE):** `world/wallet.py` — a view/routing layer over the
   existing stores (shards→`typeclasses.economy`, scrip→`world.economy`, others→`db.wallet`),
   so nothing migrated destructively. `balance/credit/debit/can_afford/exchange`,
   `valid_here` (realm-gated), `wallet_lines`. `wallet` command shows all currencies + where
   each is good; new `exchange` command. Per-realm config in REALMS (`local_currency`,
   `accepts_shards`, `exchange_rate`). Realm-local currency is **non-convertible by default**
   — a realm opts in by setting a rate. Logic tested. (Faction-editable currency config —
   set the name/accept/rate in-game — comes with the faction-admin commands in Phase 4/5.)
4. **Residency + Membership + Ranks** — in progress:
   - ✅ **4a (DONE): data model + generalised `factions.py`.** Registry-driven (reads
     `realms.FACTIONS`), Facility back-compat fully preserved (`add_standing`/`get_standing`/
     `get_facility_tier`/`next_threshold`/`seed_facility_title`/`FACILITY`). New layer: ranks
     (rep-derived or granted), membership (`join/leave/is_member`), residency (separate from
     membership), owner-authority `can_grant` (strictly-below-own + owner/parent-owner override),
     relations (`friends/enemies/subsidiaries`, `relation_between`). Registry gained
     `ranks`/`relations`/`owner`/`standing_key`; Facility grade ladder migrated into it. Tested.
   - ✅ **4b (DONE): `faction` command suite** — `faction` (your ties), `info`, `roster`, `invite`,
     `kick`, `promote`, `demote`, `resident`, `evict`; authority-gated (can_grant / owner override).
     Operates on per-character membership/rank/residency (persistent). Registered in cmdset.
   - ◑ **4c (started): persistent override store + realm ownership.** `world/realm_state.py` — a
     persistent (ServerConfig-backed, in-memory fallback) override layer over the code registries.
     First use: **realm ownership is reassignable in-game** — `realmowner <realm> = <faction>`
     (Builder), persists across reloads, and every room in the realm picks up the new owner
     instantly (`realms.realm_owner` consults the override). **Owner-editable rank names done:**
     `faction setrank <key> = A, B, C` (owner-only) writes a custom ladder to the store;
     `factions.ranks()` merges it over the registry, so granted factions define their own ladder
     and rep-driven ones (Facility) can be *renamed* while keeping their grade thresholds.
     **Relations done:** `faction befriend|enemy|subsidiary|unrelate <other> = <key>` (owner) writes
     to the store; `factions._rel` merges over the registry. **Currency config done:** `realmcurrency
     <realm> name=/shards=on|off/rate=N` (owner of the realm's faction) overrides per-realm currency
     policy; `realms.realm_config` merges it and the wallet reads through it.
   - ✅ **4c COMPLETE — player-created factions.** `faction create <key> = <Name>` writes a full def
     to the store (caller = owner via `owner_id`, seated at the top rank, cap 3/player); `faction
     disband` dissolves it. `realms.all_factions`/`get_faction`/`faction_key_for_name` and
     `factions._key`/`is_owner` all see store factions, so created factions work everywhere
     (designate, realmowner, setrank, relations, currency, membership). Tested.
   - **4d (next): residency invites via ograms** — examine the ogram realm-invite, add a
     faction-invite; `connect housing` gated on residency.
   - **4d: residency invites via ograms** — examine the ogram realm-invite, add a faction-invite;
     housing-link gated on residency.
5. Sub-factions surfaced (Facility crews, independent groups) once 1–4 are solid.

---

## Decisions — LOCKED
1. ✅ **Faction on rooms:** the **realm** stamp carries the controlling faction; store
   `room.db.faction` **only** when a sub-faction owns that specific room (override).
2. ✅ **The Void:** light lore, mechanically neutral; semi-fantasy/medieval + void elements
   (Durgin's, Wayfarers' Hall, post office as anchors).
3. ✅ **Title order:** `grade → faction → realm` ("the Footman of House Dorman of Elsewhere").
4. ✅ **Rank vs rep:** rep = the score; rank = named, custom, per-faction position. Player
   factions grant/demote strictly below own rank (no leader makes a leader); advancement is
   `granted|rep|points|quest` (configurable). NPC factions advance by owner's chosen method.

## Still to gather
- **Facility faction ideas** (you're bringing these) — its rank ladders (livestock grade track
  vs staff hierarchy), advancement mix, and how Bethany / sub-crews fit.
- Helena's wood specifics when the cabin moves.

---

## Side bug (RESOLVED): mechanics cross-flavour
Two separate things, neither a global-id cross-wire:
- **Stairs/ladder** — *not* a bug. The barn hayloft and the passage staircase are independent
  `stair` installs; both just inherited the same **default** creak text, so they looked linked.
  Fix is data: `stair msg <zone> up/down = <text>` to give the ladder its own voice.
- **Dildo seats "referencing the jacuzzi"** — *real* and **fixed**. `DildoSeatMechanic` was built
  jacuzzi-first; its sit/locked **message pools** (`_DILDO_SIT_MSGS`/`_DILDO_LOCKED_MSGS`) were all
  water/panel/throne flavour and were used for *every* dildo seat everywhere. Added jacuzzi-free
  `*_PLAIN` pools + an `_is_jacuzzi(room)` branch: jacuzzi rooms keep the water flavour, every other
  dildo seat (breeding bench, barn stocks, facility rig) now reads generically. Install message
  de-jacuzzi'd too. The jacuzzi *commands* were already correctly gated to `has_jacuzzi`.
