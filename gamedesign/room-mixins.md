# Room Mixins & Components — the dictionary

*Design-from-scratch reference. This describes the **target** room architecture for a clean
rebuild: a thin base + composable capabilities, instead of a 1,400-line god-class with
single-inheritance types. Companion: `room-types.md` (the hierarchy), `room-recipes.md` (how
rooms get assembled), `rooms-and-roomzones.md` / `rooms-appendix.md` (the zone layer).*

> Legend — **[BUILT]**: exists in the live game (lift it as-is). **[ROADMAP]**: design target,
> build fresh. **[SPLIT]**: exists but tangled into the god-class; extract it cleanly.

## Two kinds of capability
- **Mixins** = what a room *is* and keeps for life (class-time). Stable substrate.
- **Components** = what a room can *gain or lose at runtime* (`room.add_component("maze")`).
  Toggleable, so a room can transform mid-play. (Your zone-*mechanics* already prove this model
  works — a seat is attached data, not a subclass; components extend that to whole-room
  capabilities.)

Rule of thumb: if every instance of a type always has it → mixin. If it comes and goes, or only
some instances have it → component.

---

# MIXINS (class-time capabilities)

## `ZoneMixin` — the crown jewel  [SPLIT — extract from base]
**Purpose:** named zones, each with desc/summary/details/handle/study/inscribe/scent/ambient/
mechanics/time_descs; the look/study/handle/smell/survey verbs; the `{zone:}` token render. Lives
on rooms **and** characters.
**Provides:** `db.zones`, `_render_zone_tokens`, `get_zone_detail`, the reveal/gate hook.
**Example:** *every* room and body. The Jacuzzi's `window`/`mural`/`pedestals`/`cables` zones.
**Notes:** put the **reveal/gate primitive** here so all room types (and bodies) inherit hidden
details/exits/mechanics for free. This is the one capability that's truly universal — it's the
base substrate, not an optional mixin.

## `AtmosphereMixin` — time / weather / season / ambient  [SPLIT]
**Purpose:** time-of-day, weather, season, world-state, crowd level, the ambient-line pool.
**Provides:** `get_time_period`, `get_weather`, `get_season`, `get_crowd_level`, `ensure_ambient_script`.
**Example:** the playable grid (cabin exterior, facility floor). Drives `{time}`/`{weather}`
tokens and `time_descs`.
**Notes:** *not* wanted on interiors/maze-cells — keep it off the light base. The Jacuzzi's
window ("different every hour," the aurora at night) is an Atmosphere consumer.

## `PresenceMixin` — who/what is here  [SPLIT]
**Purpose:** NPC / character / wisp presence lines, crowd flavor, object-room-desc lines.
**Provides:** `get_npc_presence_lines`, `get_character_presence_lines`, `get_wisp_presence_lines`.
**Example:** social rooms (Common Room, the Floor). **Notes:** split from the base so quiet
interiors/dream-rooms don't carry it.

## `SceneLogMixin` — memory of what happened  [SPLIT]
**Purpose:** scene logging + room history.
**Provides:** `start_logging`/`stop_logging`/`log_line`, `add_to_history`, `get_history_display`.
**Example:** RP-heavy rooms. **Notes:** optional; many utility rooms don't need it.

## `AccessMixin` — ownership / friends / lock  [BUILT — today's HousingRoom]
**Purpose:** an owner, a friends list, a lock, `can_enter`/`is_owner`/`is_friend`.
**Provides:** `housing_owner_id`, friend list, entry control; grants `roomzone` rights to the owner.
**Example:** Helena's rooms, player housing, Auria's Room (owner-gated bookshelf to the playroom).

## `MechanicsMixin` — unified fixtures + zone-mechanics  [ROADMAP — the big unify]
**Purpose:** one registry/dispatch for all interactable equipment, replacing the *two* parallel
models (zone-mechanic data vs `FacilityFurniture` objects). `mechanic_key → {behavior, display,
seated/occupancy lines}`; a **Fixture** is an optional un-gettable object that just *delegates*
to its zone-mechanic for identity/appearance.
**Provides:** `install_mechanic`, `get_fixture`, occupancy/seated/restrained dispatch (pulled out
of the god-class).
**Example:** the Jacuzzi's dildo-seats, the playroom's pommel/rocking horses + swing + pole, the
facility boards — *all* "a fixture bound to a mechanic," one code path, one teardown path, one
discovery path (`survey`).
**Notes:** the single highest-value extraction; see `rooms-and-roomzones.md` §"three layers".

## `SensoryMixin` — beyond sight  [ROADMAP]
**Purpose:** `listen` / `taste` / `feel` verbs + optional `sound`/`taste`/`feel` zone fields
(completes what `smell` started).
**Example:** the Jacuzzi (`feel` the steam/heat, `listen` to the jets), the Shower (`feel` water
temp), the pedestals' layered scent already does `smell`.

## `ReactiveDescMixin` — state- & viewer-aware prose  [ROADMAP]
**Purpose:** a zone renders differently by **room state** (flooded/filthy/occupied) and **viewer
state** (a conditioned/little/owned looker sees a subliminal `|x` layer a free one doesn't).
Render priority: viewer-state → room-state → time → summary → desc (extends `time_descs`).
**Example:** the playroom mirror reading innocently to a guest and pointedly to Auria's kept pet;
the cabin valley shifting by who's looking.

## `SceneHostMixin` — bind CYOA scenes to the room  [ROADMAP]
**Purpose:** declare which scenes "live here," which auto-pose on arrival, whether `whereto`
routes here — connects rooms ↔ the scene engine instead of `scene <name>` floating globally.
**Example:** the Jacuzzi hosting a soak/use scene; a facility room owning its room-scene.

## `DayNightMixin` — independent local time/light  [ROADMAP]
**Purpose:** a room with its *own* day/night/light cycle, decoupled from realm weather.
**Provides:** a local phase ticker swapping desc-light wording + ambient.
**Example:** the cabin's underground **Yggdrasil valley** (glowing day/night though buried);
generalizes the planned `ValleyCycleScript`.

---

# COMPONENTS (runtime-attachable capabilities)

## `MazeComponent`  [BUILT as MazeRoom → ROADMAP as component]
**Purpose:** directional-combo navigation, solutions, **gates** (fail-open), decoys, debt-halls.
**Example:** the cabin forest + den passages. As a *component*, any room can gain/lose maze-ness
(a hall that only mazes when the lights drop).

## `SealComponent`  [ROADMAP — generalizes WombRoom barrier]
**Purpose:** gated/sealable **entry** on a room's thresholds, reusing the reveal/gate primitive.
**Example:** the cave mouth that won't open until a condition; a room that seals during an event.

## `InteriorComponent`  [BUILT as WombRoom → ROADMAP as component]
**Purpose:** a body-interior: fluid/flood state, `enter`, shaft-visible messaging, `interior_kind`
(womb/balls/stomach…). **Example:** the nested-passenger interiors. Pair with `InstanceComponent`.

## `EventComponent`  [ROADMAP]
**Purpose:** room-level scheduled/triggered events (on-enter, every-Nth-visit, on-a-timer) — the
facility's klaxon spectacles as a *property of rooms*. **Example:** the Floor firing the Rut.

## `EconomyComponent`  [ROADMAP]
**Purpose:** a shop/ledger node — a catalog + currency (shards/arrears). **Example:** Durgin's
shop; ties to the arrears spiral.

## `ConveyorComponent`  [ROADMAP]
**Purpose:** moves occupants station-to-station on a tick. **Example:** the Assembly Line as a room.

## `AudienceComponent`  [ROADMAP]
**Purpose:** a stage + spectators + bidding/attention model. **Example:** the Showroom, the Gala,
Auria's stage+couches+pole (the couches already "face the stage" — the geometry is authored for it).

## `InstanceComponent`  [ROADMAP — generalizes WombRoom's one-per-host]
**Purpose:** per-occupant instanced copies of a room. **Example:** trance/dream "the below" from
Going Under as an actual instanced mental space; private interiors.

---

# CROSS-CUTTING INFRASTRUCTURE (build these to make the above usable)

## Room Recipes / Capability Registry  [ROADMAP — the keystone]
Define a room as a **data recipe** (mixins + components + config + zones + mechanics) instead of a
bespoke class. Building = picking capabilities + pasting a recipe. See `room-recipes.md`.

## `rz export` — the bridge  [ROADMAP]
Walk a built room → emit every piece of prose as the exact `roomzone`/`rz` commands that placed
it (and its mechanics) → a recipe. Carries proven rooms (the jacuzzi, the playroom) into the
fresh copy intact. This is how trial-by-error feeds the clean rebuild.

## Area / Realm inheritance  [ROADMAP]
Rooms inherit defaults (lighting, weather, ambient pool, palette, scene-set) from their area/realm
(you already tag `category="realm"`), overriding locally. Theme the cabin once; every cabin room
inherits winter + the wolf-motif palette.

## Snapshot / Restore  [ROADMAP]
A room can snapshot full state (zones+mechanics+contents) and restore — one mechanism serving
**reset**, **export→recipe**, and **instancing**.

---

## §0 OOC floor (applies to every mixin/component)
Reveal/gate **fails open**; `escape`/`forceclear` relocate out of any interior and clear state;
no seal, maze, gate, or locked fixture may ever block the always-available exit.
