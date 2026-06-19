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

## `ScaleMixin` — the room sizes itself to the viewer  [ROADMAP — pattern in the Play Pen]
**Purpose:** the room's whole presentation **scales to the looker's regression/little state** —
furniture looming, proportions ballooning — so the *same* room reads ordinary to an adult and
*gargantuan* to a regressed one. `ReactiveDesc` taken to a spatial extreme, keyed to
`regression`/`headspace`.
**Provides:** a scale selector over zone descs/details (`scale_descs`), optional reach-gating
(a little can't reach what an adult can).
**Example:** **the Play Pen** — *"the room didn't get larger. You got smaller."* Already
half-invented there; make it a capability so the nursery/play-pen/Auria's-playroom cluster all
breathe with it. A signature littlespace mechanic.

## `VistaMixin` — see a place you can't (yet) walk into  [ROADMAP — pattern in jacuzzi + Momo's]
**Purpose:** a **vista zone** renders an adjacent space, lookable but not walkable, **time/weather-
reactive**, and *optionally becomes a real exit when revealed* (the reveal/gate primitive).
**Provides:** a vista zone kind whose desc pulls from time/weather; a `reveal`-to-exit upgrade path.
**Example:** the **Jacuzzi window** (forest by day → aurora by night, "different every hour");
**Momo's open southern wall** (the meadow + brook you can see across). One capability for every
view in the game — including a window that becomes a way out.

## `PositionalMixin` — positions *within* one room  [ROADMAP — pattern in the Common Room]
**Purpose:** standing **"at" a zone** is a real, lightweight in-room position that changes your
sensory feed (scent/sound/feel), ambient, and which mechanics you can reach — without splitting
into separate rooms.
**Provides:** `move_to_zone`/`at_zone`, position-scoped sensory + reachability.
**Example:** the **Common Room** ("the smell shifts as you move"); the pedestals (sandalwood at
the window, musk at the mural, all three at the water's edge). Turns big authored set-pieces (the
Floor, the den) into explorable *space* for almost no extra rooms. Also covers **vertical**
positions — the **Barn hayloft** up its ladder, the spiral descent to the Lab — without a
separate room. Sibling of `ThresholdMixin`.

## `ThresholdMixin` — a gradient *across* the room  [ROADMAP — pattern in the cave/forest mouths]
**Purpose:** conditions change **by the step** across one space — winter→warm, daylight→dark,
outside→inside — a gradient between two states that your *position* (via `PositionalMixin`)
selects. Liminal/transition rooms.
**Provides:** a two-pole gradient (temp/light/scent/sound) interpolated by position; entry-side vs
far-side prose.
**Example:** **Mouth of the Cave** ("the world changes by the step… within three paces the winter
daylight gives out and the warm den-light takes over"); **the Forest Mouth**; Helena's door
("her scent reaches you before your eyes adjust"); the spiral descent to the Hidden Lab. A
recurring pattern across at least four built rooms — clearly wants to be one capability.

## `MirrorMixin` — reflection & witnessing  [ROADMAP — pattern in Disciplination + Auria + Princess]
**Purpose:** a surface that **reflects/multiplies the scene**, shows the looker themselves, or
frames them for others to watch. Pairs with `AudienceComponent` and `ReactiveDesc`.
**Provides:** a mirror zone that can echo occupants' states, force self-witness, or feed an
audience view.
**Example:** the **Disciplination Room** ("the room sees everything twice"); **Auria's** stage
mirror angled to catch every angle; the **Princess' beaded curtain** redistributing rose light.
Witnessing-as-mechanic — being made to watch yourself. **Variant — one-way observation:** a one-way mirror (the **Hidden Lab's** full-wall glass that *reads as wall*) lets a concealed audience watch in while the watched can't see out — a hidden `AudienceComponent`.

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
Going Under as an actual instanced mental space; private interiors. The **S.I.D.M.A.U.** is the extreme case — *"cramped by measurement, spatially wrong… the body accepts before the mind catches up"*: an instanced interior that's bigger/other inside than its shell.

## `ImmersionComponent`  [ROADMAP — pattern in jacuzzi / shower / bathing lounge / SIDMAU tank]
**Purpose:** fluid-immersion: **depth, temperature (`feel`), submersion, suspension/sensory-
deprivation**, and a **wet/marked state left on you when you leave** (see ImprintOnExit). A
seat-mechanic *inside* an immersion zone is just a submerged seat.
**Example:** the **Jacuzzi** (steam, the orifice-aware dildo-seat under the surface), the
**Shower** (set it scalding or cold), the **Bathing Lounge**, and the **S.I.D.M.A.U. float tank**
(*"the fluid does not displace so much as accommodate… no bottom to feel"* — submersion + sensory
deprivation). One component for the whole water/float family.

## `LibraryComponent`  [ROADMAP — pattern in the Entertainment Room + Hidden Lab]
**Purpose:** in-room **readable texts** — lore you can `read`, some reveal-gated — the bridge from
rooms into `loredesign/`. **Example:** the Entertainment Room's tomes and "boxes of boundless
imagination," the Hidden Lab's notes/secrets. Worldbuilding that lives in the rooms and unfolds by
attention.

## `KitComponent` — an implement rack you draw from  [ROADMAP — pattern EVERYWHERE]
**Purpose:** a zone that holds a **menu of implements** bound to the room, that you (or another)
can draw and *use* — paddles/cane/crop, graded dildos/plugs, leads/halters, lube/cuffs. One
recurring pattern that currently gets re-authored as static prose every time.
**Provides:** an implement list per zone + a `use <implement> [on <target>]` that routes to the
right mechanic/effect.
**Example:** the **Hidden Lab** shelves (whips, single-tail→cane), the **Disciplination Room**
rack + shelf, the **Barn** tack wall (graded leads/halters), **Auria's** pegboard + toy tray,
the **Princess'** chest, the post office wax-kits. Easily the most-repeated thing in your builds —
make it one component with a list.

## `MonitorComponent` — the room shows your state back  [ROADMAP — pattern in S.I.D.M.A.U.]
**Purpose:** diegetic **screens/readouts that display the occupant's live stats** — arousal,
conditioning, yield, biometrics — turning hidden numbers into in-world dread you can *see*.
**Provides:** a monitor zone whose desc renders selected live stats of whoever's hooked in.
**Example:** the **S.I.D.M.A.U.** monitors ("continuous outputs: bio…"). Pairs with the Census
(figures read aloud) and the Edge (the climbing arousal bar) — the body itemized on a screen.

---

# FEATURES / HOOKS (small, not full capabilities)

## RecordWall — an accreting mural/record  [ROADMAP — pattern in the Birthing Den + murals]
**Purpose:** a wall/mural that is **a record, not decoration**, and can **accrete** over time —
lineage handprints added as you breed, tally-marks, dated inscriptions — readable like a history.
Ties `ImprintOnExit` + inscriptions + lineage. **Example:** the **Birthing Den** lineage
handprint wall (Shadow/Whisper + the named pups — *"a record, not decoration"*); the narrative
murals (jacuzzi, Auria's, Princess') as readable, optionally-growing records.

## PortFeature — a zone that accepts fittings  [ROADMAP — pattern in S.I.D.M.A.U.]
**Purpose:** a zone with **connection ports** that accept equipment plugged into the occupant —
IV/electrode/tubing/feed lines. The "interface" half of Outfitting/Immersion. **Example:** the
S.I.D.M.A.U. circular panel ports ("some accept fittings: IV-gauge tubing, electrode…"); the
closed-loop dairy lines; the pod's feed/breed/milk lines.

## ImprintOnExit  [ROADMAP — pattern in jacuzzi (dripping), pen (muddy), pedestals (the scent)]
**Purpose:** a room/zone applies a **temporary state on the occupant when they leave** — wet,
scented, muddy, marked. "Zones that remember," but pointed at the *body* (cheaper than tracking
room wear, and hotter — you carry the room out on you). A small `at_object_leave` hook + a
timed state on the character. **Example:** leave the Jacuzzi dripping; the pen's filth on your
knees; the pedestal-musk "in the back of the throat" for an hour after.

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
