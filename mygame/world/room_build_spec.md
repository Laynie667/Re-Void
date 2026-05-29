# Re:Void — Room Build Specification
*Reference for converting raw room descriptions into full Evennia build scripts.*

---

## What this file is for

When Laynie pastes a raw room description (or notes/bullet points describing a room), this spec defines the output format, style, ANSI usage, zone structure, detail/handle/study conventions, mechanic suggestions, and ambient line style. Use this every time to produce consistent, high-quality build scripts.

This game is a private adult MUD. All characters are confirmed adults. Content should be explicit where the room's theme calls for it — literary in execution, not crude for its own sake. The standard is adult fiction, not shock value.

---

## Input format

Laynie typically provides one of:
- A raw prose description of the room (may include OOC notes in brackets)
- A bullet list of features, objects, and mood
- A previous room description to use as a style reference

Always expand what's given. If Laynie gives a brief description, build it out. Add history, texture, use-marks, and sensory layering. The rooms should feel inhabited and specific.

---

## Output format: the build script

Each room gets a `.txt` file in `world/` with this structure:

```
== Room Name ==
== Paste these commands in order while standing in the room ==
== Exits: <direction> to <destination> ==

-- STEP 1: Room Description --
-- STEP 2: Create zones --
-- STEP 3: Zone descriptions --
-- STEP 4: Zone details --
-- STEP 5: Zone study details --
-- STEP 6: Zone inscriptions (if any) --
-- STEP 7: Mechanic items (if any) --
-- STEP 8: Handle interactions --
-- STEP 9: Ambient lines --
-- STEP 10: State system (if applicable) --
```

---

## ANSI color conventions

| Code | Use |
|------|-----|
| `\|y` | Room name in `@desc`, warm/prominent furniture, inviting elements |
| `\|w` | Direct object names within zone descs, important nouns, panel text |
| `\|x` | Background/ambient description, secondary detail, muted presence |
| `\|m` | Intimate content, adult/sexual elements, magical or uncanny things |
| `\|c` | Cold surfaces (glass, stone, metal, ice), clinical precision |
| `\|r` | Heat, danger, urgency (scalding water, locks, warnings, blood) |
| `\|n` | **Always** reset at end of every message/description |

Rules:
- The room name at the start of `@desc` always uses `\|y` (or `\|m` for magical/uncanny rooms).
- Zone descriptions are prose — don't over-color. Color one or two key nouns per sentence, not every phrase.
- Adult content in zone descs uses `\|m`.
- `\|x` is the default tone for ambient-layer things.
- Never use `\|g` (green) or `\|b` (blue) — not part of this palette.

---

## Step 1: Room description (`@desc here`)

**Format:**
```
@desc here = |yRoom Name|n/Opening sentence establishing the space's character and mood, with |xambient detail|n and any important features named. The room's purpose should be legible within two sentences.//{zone:zone1}//{zone:zone2}//{zone:zone3}
```

Rules:
- `/` is a newline. `//` is a paragraph break (blank line).
- `{zone:name}` tokens auto-append zone descriptions when the room is looked at.
- The opening paragraph should establish: size/scale, dominant mood, 1-2 key features, and any permanent sensory detail (scent, temperature, sound).
- Do not describe every zone in the opening — the opening sets the room, zone tokens fill detail.
- Keep the main desc to 2-4 sentences. Zone tokens handle the specifics.
- Adult rooms: hint at function without spelling it out. The mural in the Jacuzzi Room is a good model — the room desc mentions "wolf-print jacuzzi" and "floor-to-ceiling glass" without front-loading the adult content.

---

## Step 2: Zone creation

```
roomzone add <name>
```

**Naming rules:**
- Lowercase, underscores for multi-word names.
- Named after the primary feature: `window`, `mural`, `cables`, `seats`, `throne`, `panel`, `bar`, `fireplace`, `bed`.
- 3–6 zones per room is typical. Fewer for sparse rooms, more for complex ones.
- Every zone that appears as `{zone:name}` in the `@desc` must be created.

---

## Step 3: Zone descriptions (`roomzone desc`)

```
roomzone desc <zone> = prose here
```

**Style:**
- 2–4 sentences. This is the "look at zone" description — what a character sees when they examine the zone in the room.
- Third-person, present tense.
- Lead with the primary visual. Follow with texture, history, or sensory detail.
- Adult zones: be explicit about function. Don't coy-describe a dildo as "a fixture." Say what it is.
- End on something that invites interaction or implies there is more to notice.

**Example (from Jacuzzi seats zone):**
```
roomzone desc seats = The tub's four toe shapes each hold |wone seat|n: contoured to receive a body correctly... Below the waterline, mounted at the center of each, is |ma wolf-cock dildo|n...
```

---

## Step 4: Zone details (`roomzone detail`)

```
roomzone detail <zone>/<key> = prose here
```

**Convention:**
- 2–5 details per zone.
- Key names: lowercase, underscores. Name what's being described: `wolf`, `maidens`, `collar`, `hardware`, `controls`, `surface`, `glass`, `view`.
- Details are what you find when you look at a specific element of the zone more carefully. More encyclopedic than the zone desc. Still 3rd-person present tense.
- Good detail: tells you something you couldn't have inferred from the zone desc. Adds history, specificity, or implication.
- Adult details: can be more explicit than zone descs. Full anatomical specificity is appropriate where the context calls for it.

**Difference between detail and study:**
- `detail` = what you see when you look. Can be found with `look <zone>/<key>` or `study`.
- `study` = hidden observation layer. Things you only notice if you spend time with something. Often reveals history, function, or something the room's occupant has done.

---

## Step 5: Zone study details (`roomzone study`)

```
roomzone study <zone> = single observation
```

**Convention:**
- 2–3 per zone. Each is one sentence (occasionally two).
- These are the "if you look carefully" layer. They reveal use-history, physical wear, implied narrative.
- Good study: "The collar at the end of the nearest cable has been fastened and unfastened more than the others. The clasp is smoother from use."
- Think: what evidence of use is present? What does the room reveal about what has happened here? What does a careful observer notice that a casual one wouldn't?
- Can be subtle adult content without being explicit — the implication is the point.

---

## Step 6: Zone inscriptions

```
roomzone inscribe/enable <zone>
```

- Enable on surfaces that make narrative sense to be written on: murals, walls, floors near significant locations, bedposts.
- Don't enable on functional/mechanical zones (panel, seats) or zones where inscriptions would break immersion.
- Jacuzzi: mural wall is inscribable. The seats zone is inscribable (the inside of the tub, where a character might leave a mark).

---

## Step 7: Mechanic items

Suggest mechanics based on room features. Always include `@create`, `@set`, and `use ... on <zone>`.

| Feature | Mechanic | Typeclass |
|---------|----------|-----------|
| Bench, chair, couch, floor cushion | `SeatMechanic` | `typeclasses.seat_mechanic.SeatMechanic` |
| Dildo/penetrative seat | `DildoSeatMechanic` | `typeclasses.dildo_seat_mechanic.DildoSeatMechanic` |
| Bed, exam table | `SeatMechanic` with `position = lying` | same |
| Kneeling pad, floor position | `SeatMechanic` with `position = kneeling` | same |
| Collar points, cable anchors, wall rings | `RestrainMechanic` | `typeclasses.restrain_mechanic.RestrainMechanic` |
| Lockable door between zones | `DoorMechanic` | `typeclasses.door_mechanic.DoorMechanic` |

**SeatMechanic attrs:**
```
@set <item>/capacity = <n>
@set <item>/label = <what players see, e.g. "the bench">
@set <item>/position = seated   (or: lying, kneeling)
@set <item>/allow_lap = 0       (1 for lap-sitting)
use <item> on <zone>
```

**DildoSeatMechanic attrs:**
```
@set <item>/capacity = <n>
@set <item>/label = <label>
use <item> on <zone>
```
(sit/stand messages come from the pools in `commands/mechanic_commands.py` — edit those pools, not the item)

**RestrainMechanic attrs:**
```
@set <item>/capacity = <n>
@set <item>/label = <label, e.g. "the wall rings">
@set <item>/blocker_msg = <message shown when trying to move while restrained>
use <item> on <zone>
```

**Note on `zone_label` bug:** The correct attr is `/label`, not `/zone_label`. `/zone_label` is silently ignored.

---

## Step 8: Handle interactions (`roomzone handle`)

```
roomzone handle <zone>/<key> = second-person prose here
```

**Convention:**
- Second-person present tense. "You step up to the glass and look out. The canopy spreads..."
- More experiential than a detail — this is what the character *does* and *feels*, not just what's there.
- Describe the physical interaction: what does touching/looking/handling the thing feel like? What do you notice that the zone desc and detail don't capture?
- 3–5 sentences. Can be longer for key interactive elements.
- Adult handles: can be explicit. If the handle is for a collar or a dildo seat, write what it feels like to handle it. This is where adult specificity lives most naturally — the character's direct sensory experience.
- Not every detail needs a handle, but every zone should have at least one handle for its most interactive element.

**Difference between handle and detail:**
- `detail` = third-person, observational, encyclopedic.
- `handle` = second-person, experiential, what it feels like to interact.

---

## Step 9: Ambient lines (`rambient/add`)

```
rambient/add <line>
```

**Convention:**
- 6–8 lines per room.
- `\|x` color throughout — ambient lines are background texture, not action.
- Present tense, third-person or environmental (no "you").
- One event per line. Should feel like something happening at the edge of awareness.
- Mix categories: something moving, something settling, something scent-related, something visual (light change, reflection), something that implies the room is alive.
- Adult rooms: ambient lines can hint at the room's function without being explicit — "The water at the far toe seat shifts in a way that is slightly different from the jet pattern" rather than anything graphic.
- 15–30 words per line is the right length. Not too short (meaningless), not too long (stops feeling ambient).

**Examples from built rooms:**
```
rambient/add The cables against the wall settle with a faint sound — metal against stone, brief.
rambient/add Steam from the jacuzzi drifts far enough to reach the window glass.
rambient/add The aurora outside — if it is night — pulls a sweep of color across the upper half of the window.
rambient/add The water at the far toe seat shifts in a way that is slightly different from the jet pattern.
```

---

## Mechanic suggestion triggers

When converting a room, scan for these features and suggest the corresponding mechanic:

| Room feature | Suggest |
|-------------|---------|
| Any seating: bench, chair, cushion, floor space, throne | SeatMechanic |
| Seating with dildo/penetrative fixture | DildoSeatMechanic |
| Sleeping surface: bed, cot, mat | SeatMechanic + position=lying |
| Any kneeling surface: pad, rug, platform | SeatMechanic + position=kneeling |
| Restraint hardware: chains, cuffs, cables, rings | RestrainMechanic |
| Lockable interior door | DoorMechanic |
| Running water with steam/state effects | Custom script (see shower_script.py pattern) |
| Panel/control surface with host-only controls | has_<room> flag + CmdPanel pattern |
| Surfaces with cultural/narrative weight (murals, walls near events) | `roomzone inscribe/enable` |
| Bar, drink service | `roomzone bar <zone>` + drink list |
| Wardrobe, chest, drawer | `roomzone detail` pool with `browse` command enabled |

---

## State system pattern (for rooms with interactive mechanics)

If a room has running-state behavior (like the shower or jacuzzi), always include a Step 10 with:
1. A `has_<room>` flag on the room
2. A host ID attribute if applicable
3. A persistent DefaultScript for restart recovery
4. Commands in `commands/<room>_commands.py`, wired into `default_cmdsets.py`

See `commands/shower_commands.py` and `commands/jacuzzi_commands.py` for the established pattern.

State dict pattern:
```python
_STATE_DEFAULTS = {
    "running": False,
    "setting_a": "default",
    ...
}
```
Always `dict()` copy at every nesting level when writing back. Never mutate `_SaverDict` in place.

---

## Style notes

- **No tourist-brochure language.** "Stunning views" and "elegant furnishings" are banned. Say what makes the thing specific.
- **Evidence of use.** The best details show a room that has been lived in: worn edges, candle-drip residue, a handprint on glass, a collar smoother than the others from use. Every room should have at least 2-3 of these.
- **Sensory layering.** Rooms should have: at least one smell, at least one sound (or meaningful silence), temperature, and tactile quality for the surfaces that matter.
- **Implied narrative.** What happened here? What keeps happening here? The final panel of the Jacuzzi mural is "settled, not resigned" — that's a story. Build toward that kind of specificity.
- **Adult content calibration.** Zone descs and details can be explicit where the content is explicitly sexual. Ambient lines stay at implication. Handle interactions are the most explicitly experiential. Study observations use adult content to reveal history, not for direct titillation.
- **Sentence rhythm.** Mix sentence length. Long sentences for atmosphere, short ones for impact. "The knot holds." works because everything around it is longer.

---

## Quick reference: build command sequence

```
-- STEP 1 --
@desc here = |yName|n/desc//{zone:a}//{zone:b}

-- STEP 2 --
roomzone add a
roomzone add b

-- STEP 3 --
roomzone desc a = ...
roomzone desc b = ...

-- STEP 4 --
roomzone detail a/key1 = ...
roomzone detail a/key2 = ...
roomzone detail b/key1 = ...

-- STEP 5 --
roomzone study a = ...
roomzone study a = ...
roomzone study b = ...

-- STEP 6 (if applicable) --
roomzone inscribe/enable <zone>

-- STEP 7 (if applicable) --
@create Item Name:typeclasses.seat_mechanic.SeatMechanic
@set Item Name/capacity = 2
@set Item Name/label = the bench
use Item Name on <zone>

-- STEP 8 --
roomzone handle a/key1 = ...
roomzone handle b/key1 = ...

-- STEP 9 --
rambient/add ...   (x6-8)

-- STEP 10 (if state system needed) --
@set here/has_<room> = 1
@set here/<room>_host_id = <dbid>
@py self.location.scripts.add("typeclasses.<room>_script.<Room>StateScript")
```
