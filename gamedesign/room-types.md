# Room Types — the composed hierarchy

*Design-from-scratch reference. How room *types* are assembled from the capabilities in
`room-mixins.md`. Current layout → the target composed hierarchy → the type matrix → new types →
migration. Companion: `room-mixins.md`, `room-recipes.md`, `rooms-and-roomzones.md`.*

> **[BUILT]** = exists live. **[ROADMAP]** = target for the clean rebuild.

---

## Current layout  [BUILT]
```
Room(ObjectParent, DefaultRoom)        ~1421 lines   room_type="general"   ← god-class "main"
├─ HousingRoom(Room)                    ~200 lines    room_type="housing"
│   └─ WombRoom(HousingRoom)            ~369 lines    room_type="womb"/"balls"
└─ MazeRoom(Room)                       ~272 lines    room_type="maze"
```
Single inheritance; `db.room_type` is a hand-set string that duplicates the class. Problems
(detail in `rooms-and-roomzones.md`): the base is a god-class every type inherits whole; types
are mutually exclusive → no housing-maze, no maze-interior, without a class explosion; two
sources of truth for the type.

---

## Target composed hierarchy  [ROADMAP]
A thin base + capability mixins (class-time) + components (runtime). The zone system is the
universal substrate; everything else is opt-in.
```
BaseRoom   = DefaultRoom + ZoneMixin
             └ minimal: zones + appearance + the reveal/gate primitive. For interiors,
               maze-cells, dream-rooms — anything that shouldn't carry weather/crowd.

Room       = BaseRoom + Atmosphere + Presence + SceneLog
             └ the playable grid room (today's "main"/"general"), lightened.

HousingRoom = Room + Access
MazeRoom    = BaseRoom + Maze            (light — cells don't need weather/presence)
WombRoom →
InteriorRoom = BaseRoom + Interior + Instance (+ Access)   (off Housing; keyed by interior_kind)

— and combinations that were impossible become trivial —
HousingMazeRoom = Room + Access + Maze
```
Mixins compose with multiple inheritance (Evennia already does this — `Room(ObjectParent,
DefaultRoom)`). Components attach at runtime (`room.add_component("maze")`).

### `room_type` — one source of truth  [ROADMAP]
Make it a **property derived from the class/components**, not a hand-set db string (code today
checks both `isinstance(...)` and `db.room_type ==`). Keep the **interior variant** ("womb" vs
"balls") in a *separate* `interior_kind` field — that's a sub-distinction, not the type.

---

## Type matrix  (what each type = which capabilities)  [ROADMAP]
| Type | Zone | Atmos | Presence | SceneLog | Access | + components / mixins |
|---|:--:|:--:|:--:|:--:|:--:|---|
| `BaseRoom` | ✓ | · | · | · | · | — |
| `Room` (grid) | ✓ | ✓ | ✓ | ✓ | · | (Sensory / ReactiveDesc / SceneHost as needed) |
| `HousingRoom` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `MazeRoom` | ✓ | · | · | · | · | **Maze** |
| `InteriorRoom` | ✓ | · | · | · | (✓) | **Interior + Instance** |
| `ValleyRoom` | ✓ | (✓) | ✓ | · | · | **DayNight** |
| `StageRoom` | ✓ | ✓ | ✓ | ✓ | (✓) | **Audience + Mirror** |
| `ConveyorRoom` | ✓ | ✓ | ✓ | · | · | **Conveyor** |
| `HerdRoom`/`QueueRoom` | ✓ | ✓ | ✓ | ✓ | (✓) | **(capacity/queue)** |
| `MentalRoom`/`DreamRoom` | ✓ | · | · | · | · | **Instance** (no atmos/presence) |
| `ThresholdRoom` | ✓ | (✓) | · | · | · | **Threshold + Seal (+ Vista)** |
| `ShopRoom` | ✓ | ✓ | ✓ | · | (✓) | **Economy** |
| `PlayRoom` (Play Pen) | ✓ | · | ✓ | · | (✓) | **Scale + Sensory** |
| `BathRoom` (jacuzzi/shower/tank) | ✓ | (✓) | ✓ | · | (✓) | **Immersion + Sensory (+ Mirror)** |

(✓) = optional/often. Most of these are just *recipes* over the same parts — see
`room-recipes.md`.

---

## New types worth having  [ROADMAP]
Each is a composition, not new logic:
- **`InteriorRoom`** — generalize `WombRoom` off Housing; any body-interior by `interior_kind`
  (womb/balls/stomach…), `Interior + Instance`.
- **`ValleyRoom` / `CycleRoom`** — `DayNight` (the underground glowing valley).
- **`StageRoom`** — `Audience + Mirror` (Showroom, Gala, Auria's stage).
- **`ConveyorRoom`** — `Conveyor` (the Assembly Line).
- **`HerdRoom` / `QueueRoom`** — many occupants + queue (herd-dairy, holding line, glory-wall).
- **`MentalRoom` / `DreamRoom`** — `Instance`, no atmosphere/presence (Going Under's "below").
- **`ThresholdRoom`** — `Threshold + Seal (+ Vista)` (cave/forest mouths, doorways).
- **`ShopRoom`** — `Economy` (Durgin).
- **`PlayRoom`** — `Scale` (the Play Pen and its cluster).
- **`BathRoom`** — `Immersion` (jacuzzi/shower/bathing lounge/float tank).
- **`PortableRoom`** — relocatable/waystone-aware (the "portable" cabin).

---

## Migration — don't refactor live; build the fresh copy clean  [ROADMAP]
- The live game keeps trialing on the current classes. **Do not** rip the god-class apart in
  place — risky, and unnecessary.
- For the **fresh copy**: stand up the composed hierarchy from day one. The zone system (the
  loved part) ports unchanged — it just becomes `ZoneMixin` shared by all.
- **Bridge:** `rz export` (ROADMAP) turns proven live rooms into recipes; instantiate them on the
  new hierarchy. Trial-by-error → curated rebuild, no stripping.
- Evennia note: typeclasses *can* be swapped on existing objects if you ever do want to migrate a
  live room — but treat that as optional, post-rebuild polish.

## §0 OOC floor
No composed type may produce an inescapable room: reveal/seal/maze gates **fail open**, and
`escape`/`forceclear` relocate out of any interior/instance and clear state, always.
