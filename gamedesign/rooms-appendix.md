# Appendix — Rooms & Room-Related Content (reference)

*Companion to `rooms-and-roomzones.md`. Pure reference: the zone schema, builder verbs, player
verbs, render tokens, and the room-adjacent systems that hang off zones. **[BUILT]** unless
marked **[ROADMAP]**.*

---

## A. Zone dict schema  (`_blank_zone`, `commands/roomzone_commands.py`)
Each entry in `room.db.zones` / `character.db.zones` (key = lowercase zone name):

| field | type | what it is | player verb |
|---|---|---|---|
| `desc` | str | full zone description | `look <zone>`, `{zone:}` token |
| `summary` | str | short one-liner (token fallback before `desc`) | `{zone:}` token |
| `details` | dict name→text | inspectable nouns (no object needed) | `look`/`examine <name>` |
| `handle_details` | dict name→text | intimate emote per detail | `handle <name>` |
| `study_details` | list[str] | random observations | `study <zone>` |
| `inscribable` | bool | may players inscribe here | `inscribe` |
| `inscriptions` | list | player-written lines | shown via `study` |
| `scent` | str/None | smell text | `smell`/`sniff` |
| `ambient` | list[str] | passive room-flavor lines | (AmbientScript) |
| `time_descs` | dict period→text | time-of-day desc (dawn/day/dusk/night) | `{zone:}` token, priority 1 |
| `mechanics` | dict | installed mechanics (see C) | various |
| `parent` | str/None | parent zone name (nesting) | — |
| `contents` | list | tracked in-zone objects | — |
| `scripts` | list | attached scripts | — |
| `event_hooks` | dict | event → handler | — |
| `bar_drinks` | list[str] | drink names | `CmdPour` |
| `games` | list[str] | game names | `CmdPlay` |
| `pantry` | list[str] | food/ingredient names | `CmdCook` |

**[ROADMAP] proposed additions:** `sound`/`taste`/`feel` (senses, #4); `state_descs` &
`viewer_descs` (#2); `reveal` condition on details/handles (#3, see `gate-conditions.md`).

---

## B. Builder verbs — `roomzone` / `rz`  [BUILT]
*(Builders or the room owner. Stand in the room. `<zone>/<name>` targets a detail in a zone.)*

```
roomzone                                  — list all zones + details
roomzone desc <zone> = <text>             — set zone description
roomzone summary <zone> = <text>          — set the short one-liner
roomzone detail <zone>/<name> = <text>    — add/update a lookable detail
roomzone detail/rm <zone>/<name>          — remove a detail
roomzone handle <zone>/<name> = <text>    — set the intimate handle emote for a detail
roomzone handle/rm <zone>/<name>          — remove it
roomzone study <zone> = <text>            — append a random study observation
roomzone study/rm <zone> <idx>            — remove observation by index
roomzone study/list <zone>                — list observations
roomzone add <name> [in <parent>]         — add a (sub)zone
roomzone rm <name>                        — remove a zone (root zones protected)
roomzone scent <zone> = <text>            — set scent
roomzone scent/clear <zone>               — clear scent
roomzone ambient <zone> + <text>          — add an ambient line
roomzone ambient/clear <zone>             — clear ambients
roomzone timedesc <zone>/<period> = <text>— set time-of-day desc (period: dawn/day/dusk/night)
roomzone timedesc/rm <zone>/<period>      — remove it
roomzone timedesc/list <zone>             — list them
roomzone inscribe/enable <zone>           — allow player inscriptions
roomzone inscribe/disable <zone>          — disallow
roomzone inscribe/list <zone>             — list inscriptions
roomzone token <zone>                     — print the {zone:<name>} embed token
roomzone bar|game|pantry <zone> = <name>  — (+ /rm, /list) bar drinks / games / pantry items
```
Alias `rz` for all of the above. **[ROADMAP]** `rz export`, `rz audit`, `rz preset`, `rz copy`.

---

## C. Zone mechanics  (`zone["mechanics"]`)  [BUILT]
Installed by their own typeclasses' `install_into_zone(room, zone, installer)` (or written
directly). Known keys:

| mechanic | typeclass | what it does |
|---|---|---|
| `seat` | `SeatMechanic` | sittable; capacity; sit messaging |
| `seat` (seat_type="dildo") | `DildoSeatMechanic` | dildo-seat; **orifice-aware** sit (reads sitter's groin orifice zone → anal/vaginal); `locked` flag (e.g. jacuzzi) |
| `restrain` | `RestrainMechanic` | bind/hold; forced posture |
| `seat` (milking) / `MilkingMachineMechanic` | milking rig | draws milk; cups |
| `womb_room` | `WombRoom` (install) | an enterable interior on an orifice/both zone; fluid/flood |
| `inflation` | `InflationItem` | inflatable volume on an orifice zone; feeds a WombRoom |
| `barrier` | plug/barrier | `seals_zone` (gates a WombRoom entrance) |
| `triggers` | (data) | `set_attr` / `reveal_item` per detail — fired on `handle`. **Hidden** (not shown by `survey`). |

---

## D. Render tokens (in a room's `@desc`)  [BUILT]
- `{zone:<name>}` → `time_descs[period]` → `summary` → `desc` → "".
- `{time}` → current time period.  `{weather}` → current weather (outdoor rooms).
- Auto-append OFF: zones show only via an explicit token or `look <zone>`. Colour the
  interactable nouns as the cue.

---

## E. Player verbs (quick list)  [BUILT]
`look`/`examine <detail> [in <zone>]` · `study <zone>` · `handle <detail>` · `smell`/`sniff` ·
`inscribe` · `survey`/`scan`/`discern [<target>]` · body emotes: `touch caress grope stroke grab
squeeze kiss bite lick taste pull pinch nuzzle hold pet` (+ `/quiet /private /self`).
**[ROADMAP]** `listen` · `feel` · body-target `study`/`handle` (#1).

---

## F. Room-adjacent systems anchored on zones  [BUILT]
Freeform marks/brands/piercings (`FreeformManager.place_item` → a zone) · CYOA scenes (hosted in
rooms; `scene <name>`, `whereto`) · waystones/travel · AmbientScript (uses `ambient`) ·
weather/time (`get_time_period`, `get_weather`, `is_outdoor`) · housing ownership
(`housing_owner_id` grants `roomzone` rights) · the maze (`MazeRoom`; see `maze-gating.md`).

---

## G. Permissions
`roomzone`/`rz` and mechanics editing: **Builder** permission OR `room.db.housing_owner_id ==
caller.id` (the room's owner). Players interact (look/study/handle/etc.) freely.
