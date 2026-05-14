# Furniture System — Design Reference
*Planned for a future build. This document is the source of truth for implementation.*

---

## Overview

Housing rooms support purchasable furniture items that inject descriptive text into the
room description — similar to how `{zone:name}` tokens work in character descs.

Buying a piece of furniture from Durgin Ironwood (or future vendors) gives the character
a furniture token stored on their character. They then place it into any housing room they
own or have builder rights in. Placed furniture persists on the room. It can be picked
back up and moved to a different room.

---

## Data Structures

### On the character — unplaced inventory
```python
character.db.housing_furniture = [
    {
        "item_id":   "anchor_point_ceiling",   # catalogue key
        "name":      "Ceiling Anchor Point",
        "desc":      "A heavy iron ring...",   # default desc
        "custom_desc": "",                     # owner-editable override
        "room_id":   None,                     # None = in inventory
        "script":    None,                     # for tech/magic items
    },
    ...
]
```

### On the room — placed furniture
```python
room.db.furniture = [
    {
        "item_id":     "anchor_point_ceiling",
        "name":        "Ceiling Anchor Point",
        "desc":        "A heavy iron ring is bolted into the ceiling...",
        "custom_desc": "",    # owner can override desc
        "placed_by":   char_id,
        "script":      None,  # path to script class for interactive items
    },
    ...
]
```

### In the room description
Furniture descriptions append automatically after the base room desc, before
the presence/character section — same layer position as scene_stage_desc.

No token needed in the base desc. The room's `return_appearance` checks
`room.db.furniture` and appends all non-empty descs in order.

Alternatively, if the room owner wants control over placement in prose,
a `{furniture}` token can be supported in `room.db.desc` — renders the
same block at that position instead of auto-appending.

---

## Commands (planned)

```
housing furnish <item>          — place an item from inventory into this room
housing pickup <item>           — remove from room, return to inventory
housing furniture               — list all items in current room
housing inventory               — list unplaced furniture in your inventory
housing describe <item> = <text> — set a custom desc for a placed item
```

---

## Catalogue

Purchased from Durgin Ironwood (and future vendors). Prices in shards.

### Restraint & Fixings
| item_id                 | Name                    | Price | Notes                              |
|-------------------------|-------------------------|-------|------------------------------------|
| anchor_point_ceiling    | Ceiling Anchor Point    | 75    | Heavy iron ring, ceiling-mounted   |
| anchor_point_wall       | Wall Anchor Ring        | 60    | Set of two, bolted to wall         |
| anchor_point_floor      | Floor Bolt Ring         | 60    | Recessed floor ring                |
| spreader_bar_mount      | Spreader Bar Mount      | 90    | Wall-mounted horizontal bar        |
| bondage_frame_standing  | Standing Bondage Frame  | 250   | Tall A-frame, four anchor points   |
| post_single             | Restraint Post          | 120   | Single floor-to-ceiling post       |

### Furniture
| item_id                 | Name                    | Price | Notes                              |
|-------------------------|-------------------------|-------|------------------------------------|
| spanking_bench          | Spanking Bench          | 200   | Padded, adjustable angle           |
| bondage_chair           | Restraint Chair         | 220   | Wrist and ankle fixtures built in  |
| massage_table           | Padded Table            | 180   | Multi-purpose, adjustable height   |
| chaise_lounge           | Chaise Lounge           | 150   | Elegant. Also practical.           |
| bed_simple              | Simple Bed              | 100   | Frame and mattress, solid oak      |
| bed_canopy              | Canopy Bed              | 220   | Four-poster with tie points        |
| kneeling_bench          | Kneeling Bench          | 120   | Low padded bench                   |
| cage_standing           | Standing Cage           | 300   | Iron bar cage, person-height       |
| pillory                 | Pillory                 | 160   | Head-and-wrist stocks              |

### Atmosphere
| item_id                 | Name                    | Price | Notes                              |
|-------------------------|-------------------------|-------|------------------------------------|
| candle_sconce_pair      | Candle Sconces (pair)   | 50    | Wall-mounted, warm light           |
| brazier_iron            | Iron Brazier            | 80    | Floor brazier, ambient warmth      |
| privacy_screen          | Privacy Screen          | 70    | Folding room divider               |
| vanity_mirror           | Vanity Mirror           | 90    | Full-length, ornate frame          |
| rug_large               | Large Rug               | 60    | Softens the floor considerably     |
| curtain_heavy           | Heavy Curtains          | 55    | Floor-to-ceiling, blackout         |
| wardrobe_cabinet        | Wardrobe Cabinet        | 110   | Storage for clothing and gear      |

### Tech & Magical *(script-heavy — implement later)*
| item_id                 | Name                    | Price | Notes                              |
|-------------------------|-------------------------|-------|------------------------------------|
| mirror_scrying          | Scrying Mirror          | 400   | View another linked mirror         |
| orb_warming             | Warming Orb             | 150   | Heats the room; togglable          |
| lock_enchanted          | Enchanted Lock          | 300   | Keyed to owner's voice/touch       |
| collar_tracker          | Tracking Collar Display | 250   | Displays location of a linked collar |
| bell_summoning          | Summoning Bell          | 200   | Rings in a linked character's space|

---

## Tech/Magical Item Notes

These items have a `script` field pointing to a Python class that handles
targeting commands, state, and output. Pattern:

```python
room.db.furniture = [
    {
        "item_id":   "mirror_scrying",
        "script":    "world.furniture.ScryingMirrorScript",
        ...
    }
]
```

The script class handles:
- `at_look(looker, room)` — what the character sees when they examine it
- `at_interact(actor, room, args)` — called by `use <item> [args]` command
- `at_target(actor, target, room)` — called when item targets another character

A generic `use <item name>` command will dispatch to the item's script if present.
Non-scripted items just show their desc on `look at <item>`.

---

## Durgin's Shop Room

See `world/durgin_spawn.py` — `DURGIN_SHOP_DESC` constant.
The shop room is a placeholder until grid rooms are built.
Durgin is spawned with `spawn_durgin(room_dbref)`.

The shop room displays catalogue items as set dressing in its description.

---

## Future Vendors

The furniture system is vendor-agnostic. Any NPC can sell furniture items
by calling the same purchase handler with a catalogue item_id and price.
Planned future vendors:

- **The Triplets' Postal Office** — soft furnishings, decorative items
- **A magical/tech vendor** (TBD) — the scripted item catalogue
- **A black market contact** (TBD) — unlisted items, no questions asked

---

*Last updated: V.02 build*
