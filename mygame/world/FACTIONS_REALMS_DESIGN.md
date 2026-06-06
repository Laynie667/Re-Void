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
  realms that list them. Earn/spend is gated by `room.db.realm`'s `currencies`.
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
- **Housing connection:** a faction member may link their **personal housing** room to the
  realm's grid — `connect housing` from a realm housing-nexus, gated on membership. Leaving
  the faction unlinks it. (Helena's wood + Void both flagged `housing:True`.)

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

### Grant / demote rules (player factions)
- You may grant or demote **any rank strictly below your own**. You cannot grant a rank
  **equal to or above** your own — so a **leader cannot create another leader**, a mid-rank
  can only move people below them.
- **Demotion** is the same gate in reverse (higher rank can demote lower).
- Factions **define their own rank names + count + advancement method** at creation
  (`faction setrank`, `faction setadvance points|rep|quest|granted`).
- Non-player factions (Facility, House Helena) advance however the faction's owner decides —
  quest-driven, financial, rep, or staff fiat — same data model, NPC/owner pulls the levers.

## F. Phasing (so we ship working increments)
1. **Foundation:** the two registries + room `realm`/`faction` stamps + `designate`/flood-fill
   + the Void default. (Everything else needs this.)
2. **Titles** unified across factions (cheap once the registry exists).
3. **Multi-currency wallet** + realm-local currency gating (Facility scrip migrates in).
4. **Membership** (invites/roster) + **housing connection**.
5. Sub-factions surfaced (NPC crews, player cliques) once 1–4 are solid.

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

## Side bug (tracked separately): mechanics cross-triggering
Symptom: the barn **ladder** fires the passage's **creaking stair**; suspected with dildo
seats / rocking horse / stairs. Hypothesis: interactions resolve by a **shared, non-unique
key or substring zone match** (`_find_detail` matches `name in dkey`), not the specific
installed instance — so same-named zones/triggers in different rooms cross-fire. Needs a
dedicated pass: dump the two rooms' zone+mechanic data, find the shared key, and switch the
resolver to instance/room-scoped matching. (See the editor `_rdesc_dynamic` fix — same class
of "global key where a scoped one was needed.")
