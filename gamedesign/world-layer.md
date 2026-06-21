# The World Layer — Realms, Factions, Clock, Weather, Events, Economy, Travel

*Design-from-scratch reference. The layer **above** rooms: the world a room sits inside and
inherits from. Read the Rooms doc set (`rooms-and-roomzones.md` … `room-recipes.md`) as the layer
below this one. Companion concept: everything here composes from capabilities + recipes too
(see the architecture note, if/when written).*

> **[BUILT]** exists live · **[SPLIT]** exists but should be reorganized · **[ROADMAP]** target.

## The idea
Rooms don't float. Each belongs to a **Realm**, which is owned by a **Faction**, runs on a
shared **Clock**, sits under **Weather/Climate**, reads global **World-State** flags, is shaped by
scheduled **Events**, transacts in one **Economy** (shards), and is reachable through a **Travel**
network. **The Realm is the container** — rooms *inherit* its climate, clock, ambient palette,
scene-set, economy rules, and seizure/sanctuary scope, overriding only where they differ. Theme a
realm once; every room in it inherits.

---

## 1. Realms & Factions — the container  [BUILT, underused → ROADMAP to formalize]
**What's there (`world/realms.py`, `world/realm_state.py`):** a *realm* is a named area owned by a
*faction*; rooms carry `db.realm` (+ optional `db.faction` override). Factions have kinds
(neutral/guild/family/realm/sub), and realms can be **handed to player factions**
(`realmowner wildwood = <key>`). Per-realm **currency config** already exists (`local_currency`,
`accepts_shards`, convertibility — shards is the base). The Facility is a realm-owning faction.
**Target:** make the Realm carry the world-defaults rooms inherit —
```
Realm:
  faction:        <owning faction>          # who governs (drives seizure/economy/access)
  climate:        <weather table + season>  # regional weather (see §3)
  clock:          global | local{...}       # shared world clock, or a local one (valley)
  ambient_palette: <pool>                   # default ambient/scene tone
  scene_set:      [ ... ]                   # default SceneHost scenes
  economy:        { currency: shards, arrears_on: bool, seizable: bool }
  sanctuary:      bool                       # hard-protected (never seizable, overrides all)
```
Rooms inherit these; a room overrides locally. **This is the highest-leverage world-level move** —
it powers climate, theming, economy scope, and the seizure rules below, all at once.

## 2. The Clock  [BUILT]
`world/gametime.py`: IC time on `TIME_FACTOR` — periods (dawn/morning/afternoon/dusk/evening/
midnight), 4 seasons, a 360-day year (12×30). Rooms read `get_time_period`/`get_season`; the
`{time}` token renders it; zone `time_descs` swap prose by period.
**Moon phases [BUILT]:** `gametime.get_moon_phase()` (8 phases over one IC month — full lands
mid-month) + `is_full_moon()`, surfaced via the `{moon}` room token (like `{time}`/`{weather}`). The
lore/event hook is in place; wiring full-moon boons/heat-events is the scheduler's job (§5).
**ROADMAP:** **local clocks** — a realm/room can run its *own* day/night decoupled from global
(the underground **valley**'s glowing cycle; `DayNightMixin`).

## 3. Weather & Climate  [BUILT → ROADMAP: regionalize]
`world/weather.py` + `WeatherScript`: **one global weather** (7 states, Markov transitions,
30-min interval, broadcast lines) for the *entire world*; rooms with `has_weather=True` consume
it; `{weather}` token. Known issues: **global-only** (snowy cabin + indoor facility share one
sky), **snow is orphaned** (no transition produces it — winter must be faked), and weather is
**purely cosmetic** (drives no mechanics).
**ROADMAP:**
- **Regional climate per realm** (cabin = snow-weighted winter, facility = climate-controlled/none,
  desert = its own table) — fixes orphaned snow, kills the faked-winter problem.
- **Weather → gameplay:** a `weather:` reveal/gate condition **[BUILT for maze gates]** (`maze gate
  <name> = weather <state>`), plus (ROADMAP) ambient-pool selector, scene input, and event trigger
  (a storm spawns an event).
- **Scheduled/forecast weather** (drive a storm for a set-piece).

## 4. World State & Modes  [BUILT, underused]
`world/world_state.py` (`get_all_flags`; rooms read via `get_world_state`): global flags rooms can
react to. **ROADMAP:** use them as **world modes** that re-skin many rooms at once — `lockdown`,
`festival`, `blizzard`, `rut_live` — one flag flips the mood/availability of a whole realm. Pairs
with Events and ReactiveDesc.

## 5. Events & the Scheduler  [ROADMAP]
Generalize the facility's klaxon-events (`ev_*`, the random dispatcher) into a **world scheduler**:
time/season/moon-driven beats that touch many rooms/realms — dawn opens the market, a blizzard
rolls the cabin realm, full moon → Kakia boon, seasonal festivals on the 360-day calendar. An
`EventComponent` (room-level) + a world scheduler (realm/global-level) that flips World-State and
fires room/realm hooks.

## 6. The Economy — one wallet, shards  [BUILT (fragmented) → ROADMAP: unify]
**What's there:** **shards** is the main currency (Durgin's prices, `HousingPlot`
`TENT_PRICE`/`ROOM_PACK_PRICES`). The facility runs a *separate* ledger
(`facility_credits`/`facility_ledger`/`indentured`/`arrears_laced`). Per-realm currency rules
exist (`accepts_shards`, `local_currency`).
**ROADMAP — unify on shards:**
- **One Wallet** capability on characters/accounts holding the shard balance; the facility's
  arrears are just a **negative shard sub-ledger** (services bill shards; falling underwater =
  the arrears spiral). `facility_credits` reconciles to shards (or becomes facility-only **scrip** —
  a deliberate trap, spendable only at the facility).
- **`EconomyComponent`** on rooms (shops, tolls) transacts against the Wallet.
- **Define the loop:** name **sources** (rewards/work/selling) vs **sinks** (housing upkeep, mods,
  waystone tolls, arrears) so money flows both ways.
- **Realm currency scope** (already half-built): a realm may run a local currency / opt out of
  shards (`accepts_shards`); convertibility is opt-in.

### 6a. Ownership-transfer primitive & the Seizure ladder  [ROADMAP]
One primitive moves ownership of **body** (`bethany_owned`/`seraphine_takes`), **housing**
(`HousingPlot.character_id` / `housing_owner_id`), **wayposts** (`owner_char_id` + `realm_address`),
and **lineage** — always **backed up** (so `force_clear`/`escape` restores it) and reversible.
The **arrears spiral** is the pressure that triggers it, in degrees:
1. **Lien** — arrears cross a line → owner gains *entry* (`AccessMixin`).
2. **Co-ownership** — joint deed; they can edit zones, set locks, invite others.
3. **Seizure** — ownership transfers (original backed up).
4. **Conversion** — re-skin: your bedroom rezoned, the owner's brand on the walls (RecordWall),
   the bed a breeding-stall, rooms rented/annexed.
**Scoping (the consent rule):** seizure is a **realm/faction power** — you can only seize property
**within your realm**. A player's sanctuary realm (Helena's Wildwood) is owned by *her* faction →
the Facility has no authority there. Plus a hard **`sanctuary` flag** nothing overrides, and
**per-asset opt-in** (the collateral clause pledges only named assets). The player always controls
what's at stake; §0 frees the *person* regardless of who holds the deed.

## 7. Travel — the waystone network  [BUILT → ROADMAP: unify & gate]
`typeclasses/waystone.py` + `waypost.py`: a **speech-word teleport network.** `HubWaystone` hears
a spoken word → teleports to the matching `PortalWaystone` (builder-placed) or `Waypost`
(player-purchased; `realm_address`, owner ids; unset address = inactive/**hidden return**). Rich
travel messaging. **ROADMAP:** unify Portal/Waypost into one `Destination`; a **learned address
book** (`travel`/`waystones` command — addresses as collectible lore); **gated/earned**
destinations (the §0 "hidden return until earned" *is* the reveal primitive); **private** wayposts
(owner/consent-gated); **tolls** (shards/arrears); fold word-travel into exits as `PortalExit`;
treat the realm **relink** as "attach this hub to the network" (the portable cabin).

## 8. Exits — the room-to-room connectors  [BUILT: vanilla → ROADMAP]
Currently a 26-line stub (default Evennia). The full exit roadmap lives in the Rooms docs
(`rooms-and-roomzones.md`/`room-mixins.md`): reveal/gate exits, exit types (Door/Hidden/Gated/
Portal/OneWay/Threshold), zone-bound exits, travel-flavor pools, the **reciprocity audit** (fixes
the real "exits don't return" bug), conditional-destination, exit-as-scene-trigger, peek/vista,
asymmetric/queued, viewer-aware. World-level tie: `PortalExit` unifies with the waystone network
(§7), and gated exits read realm climate/world-state/time.

---

## Inheritance model (how it all reaches a room)
`Realm (owned by Faction)` → sets climate, clock, ambient palette, scene-set, economy/seizure
scope → **rooms inherit, override locally**. `World-State flags` + `the Scheduler` flip realm-wide
modes/events on the Clock. `Faction control` of a realm is the live stake — when it shifts, the
realm's rooms re-skin, access re-gates, and economy/seizure rules flip (territory won/lost).

## §0 OOC floor (world-level)
Nothing at this layer may gate the floor: `escape`/`force_clear` always relocate and free the
*person*, regardless of realm, faction, debt, seizure, locked exit, or travel state. Seizure,
territory, and economy are **in-fiction and reversible** (ownership backed up, restored on reset);
the sanctuary flag and realm-scoping keep the player in control of what's ever at stake.

## What works / carry into the fresh build
- ✅ Keep: realms-owned-by-factions, `room.db.realm`, per-realm currency config, the gametime
  clock, the world-state flag store, the waystone word-network, shards as base currency.
- 🔧 Build: Realm-as-container (inheritance), regional climate, local clocks, the unified Wallet +
  arrears-as-sub-ledger, the ownership-transfer/seizure primitive with realm-scoping, the world
  scheduler + modes, the exit/waystone unification.
- ✂️ Remove: the **wisp** presence system (flagged for deletion — out of scope).
