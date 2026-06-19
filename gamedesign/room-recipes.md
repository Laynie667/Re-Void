# Room Recipes — assembling rooms from capabilities

*Design-from-scratch reference. A **recipe** is the data definition of a room: which mixins +
components it has, its config, its zones, its mechanics. Building a room becomes *"pick
capabilities, fill the recipe"* — and `rz export` (ROADMAP) turns a proven live room into one of
these so it can be re-instantiated in the clean rebuild. Companion: `room-mixins.md`.*

> **[ROADMAP]** — recipes are the target build path. Today rooms are authored with `roomzone`/
> `rz` paste-scripts (the `world/*.txt` files); a recipe is just that, lifted to a named,
> capability-aware block. The worked examples below are *your real cabin rooms* expressed as
> recipes, to show the shape.

---

## The recipe shape
```yaml
recipe: <name>
  base:       <room-type>          # which composed type (see room-types.md)
  mixins:     [ ... ]              # extra class-time capabilities, if any
  components: [ ... ]              # runtime-attachable capabilities
  area:       <realm/area>          # inherits defaults (lighting/weather/palette/scene-set)
  config:     { ...key: value... }  # per-room settings
  scenes:     [ ... ]              # SceneHostMixin: scenes that live here
  exits:      { dir: <dest/recipe>, ... }   # incl. reveal-gated exits
  zones:      { <zone>: { desc, summary, details{}, handle{}, study[], scent,
                          time_descs{}, mechanics{}, reveal{} } }
```
A recipe compiles to: instantiate the base type, attach components, set config, run the zone/
mechanic builders (i.e. the same `rz` commands today), wire exits. **One source of truth per
room**, versionable, diffable, copy-pasteable to a text editor — exactly your rebuild workflow.

---

## Worked example 1 — Jacuzzi Room  *(from `world/jacuzzi_commands.txt`)*
A bathing/use room: rich zones, an **orifice-aware dildo-seat** under the water, a window that
lives on the day/night cycle.
```yaml
recipe: cabin_jacuzzi
  base:       Room                 # full grid room (atmosphere + presence)
  mixins:     [sensory]            # feel the steam/heat, listen to the jets
  components: []
  area:       helena_cabin         # inherits winter + wolf-motif palette
  config:     { is_indoor: true, warm: true }
  scenes:     [soak]               # ROADMAP: a hosted soak/use scene
  zones:
    window:    { desc: "...floor-to-ceiling glass, the aurora at night...",
                 details: { view, glass },
                 time_descs: { day: "...mountains in winter haze...",
                               night: "...the aurora in green and violet..." } }   # AtmosphereMixin
    mural:     { desc: "...the wolf-and-maidens tilework...",
                 details: { wolf, maidens, final_panel } }
    pedestals: { desc: "...chain pedestals, ivy, candles...",
                 details: { candles }, scent: "sandalwood, then sweet, then musk" }
    cables:    { desc: "...wall cables with collar + shackles, host sets the length...",
                 details: { collar },
                 mechanics: { restrain: { anchored: true, length_set_by: host } } }   # MechanicsMixin
    water:     { desc: "the wolf-print jacuzzi, flush with the floor, steam rising",
                 feel: "blood-warm, the jets working at you",                          # SensoryMixin
                 mechanics: { seat: { seat_type: dildo, orifice_aware: true } },        # DildoSeatMechanic
                 reveal: { water/dildos: { type: action, action: sit } } }              # hidden til you SIT
```
*The payoff:* the dildos under the water are an **undescribed, survey-hidden** detail until you
`sit` — then the orifice-aware seat engages anal/vaginal by your body. The window swaps prose by
time-of-day. The cables are a restraint mechanic whose length the host controls.

---

## Worked example 2 — Auria's Playroom  *(from `world/aurias_playroom.txt`)*
A private, **reveal-gated** dungeon/stage: many fixtures, an audience geometry, mirror.
```yaml
recipe: cabin_auria_playroom
  base:       Room
  mixins:     [reactive_desc]      # the mirror reads differently to a guest vs Auria's kept pet
  components: [audience]           # the stage + couches + pole geometry
  area:       helena_cabin
  config:     { dim: true, sound_dampened: true, temp: "maintained cool" }
  exits:
    east:     { dest: cabin_auria_room,
                reveal: { type: flag, flag: has_found_playroom } }   # hidden bookshelf passage
  zones:
    collar_wall: { desc: "mirror angled at the stage; Auria's titanium collar + shackles",
                   details: { collar }, mechanics: { restrain: { keyed: true } } }
    horses:      { desc: "pommel horse, padded cuffs, a centered twin dildo",
                   mechanics: { seat: { seat_type: dildo, twin: true, cuffs: locked } } }
    rocking_horse:{ desc: "rocking horse, fore+rear dildos, locking handlebar cuffs",
                    mechanics: { seat: { seat_type: dildo, double: true, cuffs: locked } } }
    overhead:    { desc: "ceiling bar + keyed shackles at arm-spread",
                   mechanics: { restrain: { overhead: true, keyed: true } } }
    swing:       { desc: "black sex swing, adjust points out of reach once you're in it",
                   mechanics: { seat: { seat_type: swing, self_adjust: false } } }
    stage:       { desc: "lit circular stage, chrome pole, faces the mirror",
                   mechanics: { seat: { seat_type: pole } } }
    couches:     { desc: "plush couches angled inward at the stage",
                   mechanics: { seat: { capacity: 2 } } }            # AudienceComponent seating
    accessories: { desc: "closet, spreader bar, pegboard of paddles/cane/crop, a tray of toys",
                   details: { closet, pegboard, tray } }
```
*The payoff:* the whole room is **hidden** until `has_found_playroom` is set (the bookshelf
reveal) — the gated-exit primitive. Every implement is a fixture-mechanic, one model. The couches
+ stage + pole are an `audience` component (watchers + performer). The mirror uses
`reactive_desc` to mean different things to different viewers.

---

## Worked example 3 — Shower  *(a simpler recipe, to show minimalism)*
Not every room is a set-piece. A recipe can be tiny.
```yaml
recipe: cabin_shower
  base:       Room
  mixins:     [sensory]
  area:       helena_cabin
  zones:
    stall:  { desc: "tiled stall, a wide rain-head, glass door fogged with heat",
              feel: "water you can set scalding or cold",            # SensoryMixin
              details: { rainhead, door },
              scent: "clean steam, the faint cedar of the soap" }
```
*The point:* minimalism is fine — pick only the capabilities the room needs. A shower is zones +
sensory; no maze, no audience, no atmosphere-cycle.

---

## Worked example 4 — The Play Pen  *(from `world/play_pen.txt`)* — `ScaleMixin`
A room that **sizes itself to the viewer's little/regression state**.
```yaml
recipe: cabin_play_pen
  base:       Room
  mixins:     [scale, sensory]     # ScaleMixin: the room looms when you're small
  area:       helena_cabin
  config:     { little_space: true }
  exits:
    out:      { dest: cabin_nursery }   # the wicker arch back to the nursery
  zones:
    floor:   { desc: "squishing foam underfoot",
               feel: "gives with every step, made to catch a fall",
               scale_descs: { adult: "a padded play floor",
                              little: "a vast soft plain you could lose yourself on" } }
    arch:    { desc: "the wicker arch frames the nursery",
               scale_descs: { adult: "a child's wicker arch",
                              little: "|xthe nursery beyond is gargantuan — the room didn't grow, you shrank|n" } }
```
*The payoff:* the same room reads ordinary to an adult and **gargantuan** to a regressed looker —
one room, two experiences, keyed to state. The signature littlespace mechanic.

## Worked example 5 — Mouth of the Cave  *(from `world/cave_mouth.txt`)* — `Threshold` + `Vista` + `Seal`
A **liminal** room whose conditions change *by the step*, sees both worlds, and gates the way down.
```yaml
recipe: den_cave_mouth
  base:       BaseRoom             # light — a threshold, not a full grid room
  mixins:     [threshold, sensory]
  components: [seal]               # the way deeper is reveal-gated
  exits:
    out:      { dest: den_forest_mouth }                       # back out to winter
    down:     { dest: den_birthing_den,
                reveal: { type: conditioning, min: 40 } }      # SealComponent: earn the descent
  zones:
    threshold: { desc: "the world changes by the step",
                 gradient: { entry:  { light: "thin grey winter daylight", temp: "cold" },
                             far:    { light: "warm sourceless den-light", temp: "blood-warm" } },  # ThresholdMixin
                 feel: "the cold at your back, the warm pulling you forward" }
    opening:   { desc: "the cave mouth, wide as a barn door",
                 vista: { sees: den_forest_mouth, of: "the snow-locked forest behind you" } }       # VistaMixin
```
*The payoff:* one room interpolates winter→warm across your `PositionalMixin` position; you can
*see* the forest you came from (vista); and the descent only opens once you're conditioned enough
(seal, **fails open**).

## Why recipes win for the fresh build
- **Curate by selection:** the clean copy = the set of recipes for rooms that *worked*. No
  stripping, no working-around — you just don't include the recipes you cut.
- **Diff & version:** a recipe is text; you can see exactly what a room is and changed.
- **`rz export` round-trip:** trial a room live → export → recipe → instantiate clean.
- **Consistency via `area`:** theme inheritance means a realm's rooms share a palette/lighting/
  scene-set without repeating it per room.

## §0 OOC floor
Reveal-gated exits/details and seals **fail open**; `escape`/`forceclear` always free the player
regardless of any recipe. No recipe may define an inescapable room.
