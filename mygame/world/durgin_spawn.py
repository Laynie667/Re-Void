"""
world/durgin_spawn.py

Spawn script for Durgin Ironwood — master carpenter, housing vendor,
and absolutely no one's idea of professional.

Run once from an in-game Python prompt or @py after the server is live:

    @py from world.durgin_spawn import spawn_durgin; spawn_durgin()

Durgin must be placed in a room manually after spawning, or pass a
room dbref to spawn_durgin(room_dbref=#XX).

Durgin is a Tier 2 Scripted NPC. He sells tents and room packs via
keyword triggers. He has... opinions on his customers' purchases.
"""

from web.housing.models import TENT_PRICE, ROOM_PACK_PRICES

WAYPOST_PRICE       = 300   # shards — one waypost, one realm address
CUSHION_PRICE       = 50    # shards — installs seating on a room zone (capacity 2)
LOTION_PRICE        = 150   # shards — 10-use lotion bottle, +0.25 perm size per use
SYRINGE_PRICE       = 200   # shards — 5-use syringe, +1.0 temp boost (escalating perm)
BREAST_MOD_PRICE    = 400   # shards — BreastItem, installs to chest zone
MILK_GLANDS_PRICE   = 300   # shards — MilkProductionItem, enables milk command on chest
PENIS_MOD_PRICE     = 400   # shards — PenisItem, installs to groin/penis zone
TESTICLE_MOD_PRICE  = 350   # shards — TesticleItem, installs to groin/testicles zone
SEMEN_GLANDS_PRICE  = 300   # shards — SemenProductionItem, enables semen production


# ---------------------------------------------------------------------------
# Durgin's dialogue data
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Shop room prose — ready to paste when the room is built
# ---------------------------------------------------------------------------

DURGIN_SHOP_NAME = "Ironwood Housing Co."

DURGIN_SHOP_DESC = """
The shop smells like sawdust, linseed oil, and the particular brand of ambition that \
doesn't feel the need to justify itself.

Shelves run floor to ceiling along three walls, displaying the Ironwood catalogue in \
physical form with the cheerful confidence of a man who stopped being embarrassed about \
his inventory somewhere around year two. A polished oak spanking bench occupies the \
centre of the floor like a showpiece — because it is one, angled just so under a warm \
overhead light, the leather padding worn smooth by the hands of satisfied customers \
testing the craftsmanship. Beside it, a standing bondage frame in dark iron holds \
itself with quiet authority, its four anchor points catching the light. A restraint \
chair sits in the corner with the dignified composure of furniture that knows its purpose \
and has made peace with it.

The walls themselves are not innocent. A row of ceiling anchor rings lines one beam, \
bolted at regular intervals with the kind of engineering precision that suggests Durgin \
takes load-bearing specifications very seriously. Below them, wall-mounted ring fixtures \
are displayed at various heights — a thoughtful range, really, accommodating for the \
full spectrum of reach. Coils of decorative rope hang from a pegboard beside brass \
wall fixtures whose function is self-evident to anyone paying the faintest attention, \
and several pairs of padded wrist cuffs are draped over a display rack with the casual \
ease of a shop that sells exactly what it sells and is very comfortable about it.

Behind a scarred wooden counter, Durgin's blueprints and commission notes are stacked \
in organised chaos. A chalkboard lists current prices in cramped, decisive handwriting \
— underlined twice, which feels like a personality trait. Below it, in smaller letters: \
ALL SALES FINAL. IRONWOOD HOUSING TAKES NO RESPONSIBILITY FOR WHAT YOU DO IN THERE. \
Beneath that, in what appears to be an afterthought: (we're proud of you though).

The whole place hums with the cheerful, unapologetic energy of commerce that has found \
its niche and absolutely refuses to leave it.
""".strip()

DURGIN_SHOP_EXAMINE_DESC = """
Closer inspection reveals that Durgin has thought of everything. The display spanking \
bench has a small engraved plaque: DEMONSTRATION MODEL — DO NOT ACTUALLY USE. \
Someone has scratched 'why not' underneath it in different handwriting. \
The ceiling anchor rings are rated for weights that suggest Durgin has very \
optimistic customers. A small printed card tucked into the pegboard reads: \
'Custom commissions available. No job too specific. No questions asked. \
No, seriously, none. We've tried.'
""".strip()

DURGIN_SHOP_ENTRY_DESC = """
The smell of sawdust and something that might be linseed oil hits you \
before you've fully crossed the threshold.
""".strip()


# ---------------------------------------------------------------------------
# Catalogue reference — for when the furniture system is built
# See design/furniture_system.md for full spec
# ---------------------------------------------------------------------------

DURGIN_CATALOGUE = {
    # Restraint & Fixings
    "anchor_point_ceiling":   {"name": "Ceiling Anchor Point",   "price": 75,  "category": "restraint"},
    "anchor_point_wall":      {"name": "Wall Anchor Ring",        "price": 60,  "category": "restraint"},
    "anchor_point_floor":     {"name": "Floor Bolt Ring",         "price": 60,  "category": "restraint"},
    "spreader_bar_mount":     {"name": "Spreader Bar Mount",      "price": 90,  "category": "restraint"},
    "bondage_frame_standing": {"name": "Standing Bondage Frame",  "price": 250, "category": "restraint"},
    "post_single":            {"name": "Restraint Post",          "price": 120, "category": "restraint"},
    # Furniture
    "spanking_bench":         {"name": "Spanking Bench",          "price": 200, "category": "furniture"},
    "bondage_chair":          {"name": "Restraint Chair",         "price": 220, "category": "furniture"},
    "massage_table":          {"name": "Padded Table",            "price": 180, "category": "furniture"},
    "chaise_lounge":          {"name": "Chaise Lounge",           "price": 150, "category": "furniture"},
    "bed_simple":             {"name": "Simple Bed",              "price": 100, "category": "furniture"},
    "bed_canopy":             {"name": "Canopy Bed",              "price": 220, "category": "furniture"},
    "kneeling_bench":         {"name": "Kneeling Bench",          "price": 120, "category": "furniture"},
    "cage_standing":          {"name": "Standing Cage",           "price": 300, "category": "furniture"},
    "pillory":                {"name": "Pillory",                 "price": 160, "category": "furniture"},
    # Atmosphere
    "candle_sconce_pair":     {"name": "Candle Sconces (pair)",   "price": 50,  "category": "atmosphere"},
    "brazier_iron":           {"name": "Iron Brazier",            "price": 80,  "category": "atmosphere"},
    "privacy_screen":         {"name": "Privacy Screen",          "price": 70,  "category": "atmosphere"},
    "vanity_mirror":          {"name": "Vanity Mirror",           "price": 90,  "category": "atmosphere"},
    "rug_large":              {"name": "Large Rug",               "price": 60,  "category": "atmosphere"},
    "curtain_heavy":          {"name": "Heavy Curtains",          "price": 55,  "category": "atmosphere"},
    "wardrobe_cabinet":       {"name": "Wardrobe Cabinet",        "price": 110, "category": "atmosphere"},
    # Tech / Magical (script-heavy — implement later)
    "mirror_scrying":         {"name": "Scrying Mirror",          "price": 400, "category": "tech", "script": "world.furniture.ScryingMirrorScript"},
    "orb_warming":            {"name": "Warming Orb",             "price": 150, "category": "tech", "script": "world.furniture.WarmingOrbScript"},
    "lock_enchanted":         {"name": "Enchanted Lock",          "price": 300, "category": "tech", "script": "world.furniture.EnchantedLockScript"},
    "collar_tracker":         {"name": "Tracking Collar Display", "price": 250, "category": "tech", "script": "world.furniture.CollarTrackerScript"},
    "bell_summoning":         {"name": "Summoning Bell",          "price": 200, "category": "tech", "script": "world.furniture.SummoningBellScript"},
}


# ---------------------------------------------------------------------------
# NPC description
# ---------------------------------------------------------------------------

DURGIN_DESC = """
A dwarf of considerable girth and questionable hygiene, Durgin Ironwood
stands behind a cluttered counter of wood samples, lock mechanisms, and
empty ale tankards. His beard is braided with what appear to be tiny
door hinges. His leather apron bears the stains of a thousand projects
and at least two breakfasts.

A hand-lettered sign above him reads: IRONWOOD HOUSING CO. — EST. RECENTLY.
COMPETITIVE PRICES. NO REFUNDS. NO JUDGEMENT. (SOME JUDGEMENT.)
"""

DURGIN_PRESENCE = (
    "Durgin Ironwood leans on the counter, eyeing you with the professional "
    "appraisal of a man who has seen exactly what people do with private rooms."
)

DURGIN_AMBIENT = [
    "Durgin polishes a lock mechanism slowly, watching you from under his brow.",
    "Durgin mutters something about 'reinforced mounting points' and marks up a blueprint.",
    "A small avalanche of sawdust cascades off the counter. Durgin doesn't notice or care.",
    "Durgin squints at you over his reading spectacles with the look of a man who has seen everything and judged none of it.",
    "Durgin takes a long pull from his tankard and sets it down with a satisfied thud. 'To good walls,' he says. 'Thick ones.'",
    "Durgin taps the counter. 'You know what I always say. Privacy isn't a luxury. It's a necessity.' He pauses. 'Especially given what some of you lot get up to.'",
    "Durgin rummages under the counter, produces a small decorative iron ring, holds it up to the light approvingly, and puts it back without comment.",
    "Durgin idly flips through a catalogue. The cover reads: RESTRAINT FIXTURES AND ANCHOR SOLUTIONS, VOL. 4. He catches you looking. 'Professional interest,' he says.",
    "Durgin runs a hand along the edge of a sample door frame. 'Oak,' he says fondly. 'Doesn't splinter. Important quality in a door that's going to take some... stress.'",
    "Durgin leans back and cracks his knuckles. 'Another happy customer left here this morning. Bought five rooms.' He shakes his head admiringly. 'Ambitious.'",
    "Durgin absently carves something into the counter with a small knife, then turns it so you can't read it.",
]

DURGIN_TRIGGERS = {

    # ── Greetings ──────────────────────────────────────────────────────────
    "_arrive": {
        "response": [
            "\nDurgin looks you up and down with the practiced eye of a man "
            "who has sold private rooms long enough to make certain assumptions. "
            "'Welcome in. See anything you like?' He grins into his beard. "
            "'I mean on the price board, of course.'"
        ],
        "type": "emote",
    },

    "hello": {
        "response": [
            "Durgin leans on the counter. 'Hello yourself. First time? "
            "I can always tell first-timers — you've still got that look "
            "like you're not sure if you should be here.' "
            "He waves a hand. 'Everyone ends up here eventually. No shame in it.'",

            "'Hello!' Durgin brightens considerably. 'Come to buy some privacy? "
            "Smart. Very smart. Some things are better done behind closed doors. "
            "Or so I assume. Again — professional discretion.'",
        ],
        "type": "emote",
    },

    "hi": {
        "response": [
            "'Hi.' Durgin gives you a slow once-over. 'You look like someone "
            "who could use a room. Maybe two. No judgement. "
            "Well. Some judgement. Mostly admiration.'"
        ],
        "type": "emote",
    },

    # ── What he sells ──────────────────────────────────────────────────────
    "what": {
        "response": [
            f"'What do I sell?' Durgin spreads his hands grandly. "
            f"'Privacy. That's the honest answer. The technical answer is tents "
            f"and room packs. {TENT_PRICE} shards gets you started — one room, "
            f"walls that hold, a door that locks. What you do once that door is shut...' "
            f"He trails off with a knowing smile. 'Well. That's why the walls are thick.'"
        ],
        "type": "emote",
    },

    "sell": {
        "response": [
            f"'Rooms,' says Durgin simply. 'Private ones. Soundproofed ones. "
            f"Rooms where nobody walks in uninvited and nobody hears anything they "
            f"weren't meant to hear.' He taps his nose. "
            f"'Tent to start — {TENT_PRICE} shards. Room packs if you find yourself "
            f"needing... more space. Some people need a lot more space. "
            f"I've stopped asking why.'"
        ],
        "type": "emote",
    },

    "price": {
        "response": [
            f"Durgin slaps a laminated card on the counter and smooths it flat "
            f"with one thick hand:\n\n"
            f"  Tent (1 room)      — {TENT_PRICE} shards\n"
            f"  +1 room pack       — {ROOM_PACK_PRICES[1]} shards\n"
            f"  +5 room pack       — {ROOM_PACK_PRICES[5]} shards\n"
            f"  +10 room pack      — {ROOM_PACK_PRICES[10]} shards\n"
            f"  +20 room pack      — {ROOM_PACK_PRICES[20]} shards\n"
            f"  +25 room pack      — {ROOM_PACK_PRICES[25]} shards\n"
            f"  Waypost            — {WAYPOST_PRICE} shards\n"
            f"  Seat cushion       — {CUSHION_PRICE} shards\n"
            f"  Lotion (10 uses)   — {LOTION_PRICE} shards\n"
            f"  Syringe (5 uses)   — {SYRINGE_PRICE} shards\n"
            f"  Breast enhancement — {BREAST_MOD_PRICE} shards\n"
            f"  Milk glands          — {MILK_GLANDS_PRICE} shards\n"
            f"  Penis enhancement    — {PENIS_MOD_PRICE} shards\n"
            f"  Testicle enhancement — {TESTICLE_MOD_PRICE} shards\n"
            f"  Semen glands         — {SEMEN_GLANDS_PRICE} shards\n\n"
            f"'All rooms built to Ironwood standards. Walls are load-bearing, "
            f"anchor points are reinforced, and I don't ask questions. "
            f"The last bit is included free of charge.'"
        ],
        "type": "emote",
    },

    "prices": {
        "response": [
            f"Durgin slaps a laminated card on the counter and smooths it flat "
            f"with one thick hand:\n\n"
            f"  Tent (1 room)      — {TENT_PRICE} shards\n"
            f"  +1 room pack       — {ROOM_PACK_PRICES[1]} shards\n"
            f"  +5 room pack       — {ROOM_PACK_PRICES[5]} shards\n"
            f"  +10 room pack      — {ROOM_PACK_PRICES[10]} shards\n"
            f"  +20 room pack      — {ROOM_PACK_PRICES[20]} shards\n"
            f"  +25 room pack      — {ROOM_PACK_PRICES[25]} shards\n"
            f"  Waypost            — {WAYPOST_PRICE} shards\n"
            f"  Seat cushion       — {CUSHION_PRICE} shards\n"
            f"  Lotion (10 uses)   — {LOTION_PRICE} shards\n"
            f"  Syringe (5 uses)   — {SYRINGE_PRICE} shards\n"
            f"  Breast enhancement — {BREAST_MOD_PRICE} shards\n"
            f"  Milk glands          — {MILK_GLANDS_PRICE} shards\n"
            f"  Penis enhancement    — {PENIS_MOD_PRICE} shards\n"
            f"  Testicle enhancement — {TESTICLE_MOD_PRICE} shards\n"
            f"  Semen glands         — {SEMEN_GLANDS_PRICE} shards\n\n"
            f"'All rooms built to Ironwood standards. Walls are load-bearing, "
            f"anchor points are reinforced, and I don't ask questions. "
            f"The last bit is included free of charge.'"
        ],
        "type": "emote",
    },

    # ── Buy tent ──────────────────────────────────────────────────────────
    "tent": {
        "response": [
            f"Durgin's eyes light up with the particular warmth of a man "
            f"who loves his work. 'Ah, a tent buyer. Excellent taste.' "
            f"He leans forward. '{TENT_PRICE} shards. One room. "
            f"Yours to furnish however your heart — or whatever organ's "
            f"doing the thinking right now — desires.' "
            f"He winks, which on a dwarf is more of a full-face event. "
            f"'Say |wbuy tent|n when you're ready. I'll have it set up before "
            f"you can say \"don't tell anyone about this.\"'"
        ],
        "type": "emote",
    },

    "buy tent": {
        "response": "_HANDLE_PURCHASE_TENT",
        "type": "action",
    },

    # ── Buy room packs ─────────────────────────────────────────────────────
    "room": {
        "response": [
            f"'Need more space, do we?' Durgin grins broadly. "
            f"'I respect that. Some activities require room to breathe. "
            f"Or room to... not breathe, depending on your preferences — "
            f"not that I'd know anything about that.' "
            f"He pulls out his rate card. "
            f"'Say |wbuy 1 room|n, |wbuy 5 rooms|n, |wbuy 10 rooms|n, "
            f"|wbuy 20 rooms|n, or |wbuy 25 rooms|n. "
            f"I'll have your new space ready and waiting, "
            f"judgment-free and structurally flawless.'"
        ],
        "type": "emote",
    },

    "buy 1 room": {
        "response": "_HANDLE_PURCHASE_ROOM_1",
        "type": "action",
    },

    "buy 5 rooms": {
        "response": "_HANDLE_PURCHASE_ROOM_5",
        "type": "action",
    },

    "buy 10 rooms": {
        "response": "_HANDLE_PURCHASE_ROOM_10",
        "type": "action",
    },

    "buy 20 rooms": {
        "response": "_HANDLE_PURCHASE_ROOM_20",
        "type": "action",
    },

    "buy 25 rooms": {
        "response": "_HANDLE_PURCHASE_ROOM_25",
        "type": "action",
    },

    # ── Waypost ───────────────────────────────────────────────────────────
    "waypost": {
        "response": [
            f"Durgin reaches under the counter and sets a carved wooden post on "
            f"the surface with a solid thunk. It's small — maybe a foot tall — "
            f"dark wood worked with fine runes that catch the light in a way "
            f"that feels slightly deliberate. "
            f"'Waypost,' he says. 'You give it a name — your realm address — "
            f"and drop it in a room you own. Anyone who knows the address "
            f"can say it near a hub waystone and travel straight to you.' "
            f"He taps the runes. 'Private destinations for private people. "
            f"No map, no door, just a word.' He sets it back down. "
            f"'{WAYPOST_PRICE} shards. Say |wbuy waypost|n when you're ready.'",

            f"'Ah.' Durgin's eyes light up. 'The waypost. One of my finer products.' "
            f"He pulls one out from under the counter — a short post of dark carved "
            f"wood, its runes very subtly glowing. "
            f"'You name it — a realm address, one word, yours — and place it in a "
            f"room you own. After that, anyone who knows the word can travel to your "
            f"room from the hub waystone just by speaking it.' He sets it back. "
            f"'Privacy, accessibility, a hint of mystique. {WAYPOST_PRICE} shards. "
            f"Say |wbuy waypost|n.'",
        ],
        "type": "emote",
    },

    "buy waypost": {
        "response": "_HANDLE_PURCHASE_WAYPOST",
        "type": "action",
    },

    # ── Seat cushion ──────────────────────────────────────────────────────
    "cushion": {
        "response": [
            f"Durgin reaches under the counter and produces a flat cushion — "
            f"thick, well-stuffed, covered in practical canvas with a strap "
            f"on the back. He sets it down with a businesslike pat. "
            f"'Seat cushion. {CUSHION_PRICE} shards.' He folds his hands. "
            f"'You use it on a zone in your room — say you've got a bench, "
            f"a chair, a pile of things you're calling a throne — you drop "
            f"the cushion on it and it becomes proper seating. Capacity two. "
            f"Whoever sits, shows up in the room description as seated there.' "
            f"He taps the counter. 'It's consumed when you install it. "
            f"One cushion, one seat. Say |wbuy cushion|n when you're ready.'",

            f"'Ah.' Durgin holds up a cushion. 'One of my quieter products, "
            f"but a useful one.' He turns it over in his thick hands. "
            f"'You use this on any zone or subzone in a room you own — "
            f"|wuse cushion on <zone>|n — and that zone becomes a proper seat. "
            f"Two people can sit there at once. They show up in the room desc "
            f"when they do.' He sets it down. "
            f"'{CUSHION_PRICE} shards. It gets used up on install, "
            f"so buy one per seat. Say |wbuy cushion|n.'",
        ],
        "type": "emote",
    },

    "buy cushion": {
        "response": "_HANDLE_PURCHASE_CUSHION",
        "type": "action",
    },

    # ── Lotion ────────────────────────────────────────────────────────────
    "lotion": {
        "response": [
            f"Durgin reaches under the counter and sets a small unlabeled bottle "
            f"on the surface with a quiet click. 'Lotion,' he says, with the "
            f"professional detachment of a man who has decided not to inquire further. "
            f"'Apply it to a zone with a body mod installed — the |wlotion <zone>|n command. "
            f"Each application adds a permanent quarter-size increment. Ten uses per bottle.' "
            f"He folds his hands. 'It works. Don't ask me how. "
            f"{LOTION_PRICE} shards. Say |wbuy lotion|n when you're ready.'",

            f"'Body mod supplies.' Durgin produces a bottle with the ease of someone "
            f"who keeps a stock of everything. 'Lotion. Permanent size boost — "
            f"applies to whatever's installed on the zone you target. "
            f"Ten applications. Quarter increment each.' "
            f"He sets it down. '{LOTION_PRICE} shards. |wbuy lotion|n.'",
        ],
        "type": "emote",
    },

    "buy lotion": {
        "response": "_HANDLE_PURCHASE_LOTION",
        "type": "action",
    },

    # ── Syringe ───────────────────────────────────────────────────────────
    "syringe": {
        "response": [
            f"Durgin produces a sealed syringe from under the counter and sets it "
            f"on the surface with a crisp click. 'Temporary enhancement,' he says. "
            f"'Inject it into a zone — the |winject <target> [zone]|n command. "
            f"One full size increment, lasts six hours. Five uses.' He pauses. "
            f"'Fair warning: repeated use starts leaving permanent changes. "
            f"The first five are clean. After that...' He shrugs, which is not reassuring. "
            f"'{SYRINGE_PRICE} shards. Say |wbuy syringe|n.'",

            f"'Syringe.' Durgin holds one up briefly — sealed, clinical, clearly "
            f"not from a hardware catalogue. 'Temporary size boost. Six hours. "
            f"Five uses. Use the |winject|n command.' A pause. "
            f"'Heavy use has escalating permanent side effects, which I am required "
            f"to mention and which I personally consider a feature rather than a flaw.' "
            f"He sets it down. '{SYRINGE_PRICE} shards. Say |wbuy syringe|n.'",
        ],
        "type": "emote",
    },

    "buy syringe": {
        "response": "_HANDLE_PURCHASE_SYRINGE",
        "type": "action",
    },

    # ── Breast enhancement ────────────────────────────────────────────────
    "breast enhancement": {
        "response": [
            f"Durgin opens a drawer under the counter and produces a small padded "
            f"case, setting it down with the deliberate care of a craftsman handling "
            f"precision work. 'Breast enhancement,' he says, which is exactly what it "
            f"says on the case. 'Body mod item. Installs to your chest zone — "
            f"|winstall breast enhancement|n — and from that point it tracks size, "
            f"works with lotion and syringe, enables the milking system, and puts "
            f"a size token in your zone description.' He slides it closer. "
            f"'You'll want to set a zone description with a {{size}} token in it "
            f"once it's installed. I can't help with the writing part.' "
            f"'{BREAST_MOD_PRICE} shards. Say |wbuy breast enhancement|n.'",

            f"'Breast enhancement.' Durgin says it the way a man says 'load-bearing "
            f"anchor point' — with complete professional composure. He sets the case "
            f"on the counter. 'Installs to chest zone. Tracks size float. "
            f"Plugs into the lotion, syringe, and milking systems automatically. "
            f"Your zone desc can use the {{size}} token once it's in.' "
            f"He folds his hands. 'I don't ask what size you're starting from "
            f"and I don't ask where you're trying to get to.' "
            f"'{BREAST_MOD_PRICE} shards. |wbuy breast enhancement|n.'",
        ],
        "type": "emote",
    },

    "buy breast enhancement": {
        "response": "_HANDLE_PURCHASE_BREAST_MOD",
        "type": "action",
    },

    # ── Milk glands ───────────────────────────────────────────────────────
    "milk glands": {
        "response": [
            f"Durgin sets a second case on the counter beside the first — "
            f"slightly larger, the same padded presentation. "
            f"'Milk glands,' he says. 'Production item. Installs to chest zone alongside "
            f"a breast enhancement. Once installed, it accumulates passively over time "
            f"and the milking machine — or the |wmilk|n command — can extract it into "
            f"bottles.' He taps the case. 'You'll want the breast enhancement in first. "
            f"The production item uses the mod's size for its output multiplier.' "
            f"A pause. 'You can also set a flavor profile on it with |wsetfluid/flavor|n. "
            f"I cannot explain why that option exists. I do know it gets used.' "
            f"'{MILK_GLANDS_PRICE} shards. Say |wbuy milk glands|n.'",

            f"'Production item,' Durgin says. 'Installs to chest zone — use "
            f"|winstall milk glands|n once you have it. Starts accumulating immediately. "
            f"Extract with the milking machine or the milk command; output goes to bottles "
            f"in the room.' He gives you a very steady look. "
            f"'I recommend the breast enhancement first for best output. "
            f"That's the professional recommendation. The personal one I will keep to myself.' "
            f"'{MILK_GLANDS_PRICE} shards. |wbuy milk glands|n.'",
        ],
        "type": "emote",
    },

    "buy milk glands": {
        "response": "_HANDLE_PURCHASE_MILK_GLANDS",
        "type": "action",
    },

    # ── Penis enhancement ─────────────────────────────────────────────────
    "penis enhancement": {
        "response": [
            f"Durgin produces a padded case and sets it on the counter with the "
            f"same composed professionalism he brings to every product. "
            f"'Penis enhancement,' he says. 'Body mod item. Installs to your penis zone — "
            f"|winstall penis enhancement|n. Tracks size on a length-and-girth scale, "
            f"works with lotion and syringe, puts a {{size}} token in your zone description.' "
            f"He folds his hands. 'Starts at average. Where it ends up is between you "
            f"and the lotion. {PENIS_MOD_PRICE} shards. Say |wbuy penis enhancement|n.'",

            f"'Body mod.' Durgin opens a drawer and produces the case without ceremony. "
            f"'Penis enhancement. Same install system as the breast item — "
            f"|winstall|n command, targets your penis zone. {{size}} token shows "
            f"length-and-girth descriptor in the zone description.' "
            f"He taps the counter. 'Lotion gives permanent quarter increments. "
            f"Syringe gives a full increment for six hours, escalating permanent effects "
            f"past the fifth use.' A pause. 'I say the same thing to everyone. "
            f"Nobody stops at five.' {PENIS_MOD_PRICE} shards. |wbuy penis enhancement|n.'",
        ],
        "type": "emote",
    },

    "buy penis enhancement": {
        "response": "_HANDLE_PURCHASE_PENIS_MOD",
        "type": "action",
    },

    # ── Testicle enhancement ──────────────────────────────────────────────
    "testicle enhancement": {
        "response": [
            f"Durgin reaches under the counter and sets a small case on the surface. "
            f"'Testicle enhancement,' he says, with the flat composure of a man who "
            f"has said this sentence many times and has no feelings about it. "
            f"'Body mod item. Installs to your testicles zone. Tracks volume on a "
            f"descriptor scale — pea-sized up through load-bearing and beyond.' "
            f"He slides it forward. 'Works with lotion and syringe. Pairs with semen "
            f"glands — testicle items give a one-point-five-times multiplier on semen "
            f"production. Worth noting if that's the direction you're going.' "
            f"'{TESTICLE_MOD_PRICE} shards. Say |wbuy testicle enhancement|n.'",

            f"'Testicle enhancement.' Durgin produces the case and sets it down. "
            f"'Same system as the others. Install it on your testicles zone, "
            f"it tracks size, the {{size}} token shows the descriptor in your zone description.' "
            f"He taps the case. 'Particularly useful if you're also running semen glands — "
            f"the production multiplier scales well with this one.' "
            f"A short pause. 'I've sold a surprising number of these. "
            f"I mention this only as a data point.' "
            f"'{TESTICLE_MOD_PRICE} shards. |wbuy testicle enhancement|n.'",
        ],
        "type": "emote",
    },

    "buy testicle enhancement": {
        "response": "_HANDLE_PURCHASE_TESTICLE_MOD",
        "type": "action",
    },

    # ── Semen glands ──────────────────────────────────────────────────────
    "semen glands": {
        "response": [
            f"Durgin sets a case on the counter. 'Semen glands,' he says. "
            f"'Production item. Installs to your penis or testicles zone — "
            f"|winstall semen glands|n. Accumulates over time, extracted with "
            f"the |wmilk|n command or a milking machine, output goes to bottles.' "
            f"He pauses. 'Lower base rate than milk glands, but scales well with size. "
            f"Testicle items give a one-point-five-times multiplier on semen production "
            f"specifically. The two are designed to pair.' "
            f"He sets it flat. '{SEMEN_GLANDS_PRICE} shards. Say |wbuy semen glands|n.'",

            f"'Production item.' Durgin slides the case over. "
            f"'Installs to penis or testicles zone. Accumulates passively, "
            f"extracts with |wmilk|n or a machine, bottles up in the room.' "
            f"He folds his hands. 'Set a flavor note with |wsetfluid/flavor|n if you want "
            f"the bottles to have character. That is a feature that exists and that "
            f"I did not ask questions about when I was told to include it.' "
            f"'{SEMEN_GLANDS_PRICE} shards. |wbuy semen glands|n.'",
        ],
        "type": "emote",
    },

    "buy semen glands": {
        "response": "_HANDLE_PURCHASE_SEMEN_GLANDS",
        "type": "action",
    },

    # ── Lore / personality ────────────────────────────────────────────────
    "who are you": {
        "response": [
            "'Durgin Ironwood. Master carpenter. Purveyor of privacy. "
            "Confidant to the adventurous and the deviant alike — "
            "not that there's much difference in my experience.' "
            "He strokes his braided beard. 'I've built rooms for people "
            "who blush just asking. I've built rooms for people who didn't "
            "bother to explain and I appreciated that more.' "
            "A pause. 'My mother wanted me to build furniture. "
            "I think this is better.'"
        ],
        "type": "emote",
    },

    "name": {
        "response": [
            "'Durgin Ironwood,' he says, with a slight bow. "
            "'Master of walls, doors, and the professional silence "
            "that goes between them. There's a sign, but I don't mind "
            "being asked. Gives me a chance to introduce myself properly "
            "before things get... interesting.'"
        ],
        "type": "emote",
    },

    "bye": {
        "response": [
            "'Off you go then.' Durgin gives a broad wave. "
            "'Enjoy your room. Or rooms. Or whatever configuration you've "
            "got planned. The walls will hold. That's a Durgin Ironwood guarantee.' "
            "He pauses. 'The guarantee covers structural integrity only. "
            "Everything else is on you.'",

            "'Have fun,' says Durgin, with a grin that suggests he has "
            "a fairly specific idea of what fun looks like. "
            "'The rooms are yours. Use them well. Use them thoroughly.' "
            "He raises his tankard in salute.",
        ],
        "type": "emote",
    },

    "goodbye": {
        "response": [
            "'Come back when you need more space.' Durgin winks. "
            "'They always come back for more space.'"
        ],
        "type": "emote",
    },
}


# ---------------------------------------------------------------------------
# Purchase handlers — called from NPC trigger system via action type
# ---------------------------------------------------------------------------

def handle_purchase(caller, npc, purchase_type):
    """
    Called by the NPC trigger system when a player triggers a buy action.
    purchase_type: "tent" | "waypost" | 1 | 5 | 10 | 20 | 25
    """
    from web.housing.models import HousingPlot, TENT_PRICE, ROOM_PACK_PRICES
    from web.economy.models import ShardTransaction
    from typeclasses.housing import HousingRoom
    from evennia.utils import create

    char = caller
    char_name = char.db.rp_name or char.key
    shards = char.db.shards or 0

    # ── Tent purchase ──────────────────────────────────────────────────────
    if purchase_type == "tent":
        existing = HousingPlot.get_or_none(char.id)
        if existing:
            npc.execute_cmd(
                f"say You already own a plot, {char_name}. "
                f"Don't be greedy — there are people out there with no rooms at all. "
                f"Probably."
            )
            return

        if shards < TENT_PRICE:
            npc.execute_cmd(
                f"say {char_name}, you're {TENT_PRICE - shards} shards short. "
                f"Come back when you're solvent."
            )
            return

        # Charge
        char.db.shards = shards - TENT_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=TENT_PRICE,
            reason="purchase",
            note="Tent purchase from Durgin Ironwood",
        )

        # Create the housing room
        room_name = f"{char_name}'s Tent"
        new_room = create.create_object(
            typeclass=HousingRoom,
            key=room_name,
            report_to=char,
        )
        new_room.db.housing_owner_id = char.id
        new_room.db.desc = (
            f"A modest but private space, freshly hewn from the void. "
            f"The walls feel solid — Durgin Ironwood's work always does. "
            f"What you do with it from here is entirely your business."
        )

        # Create plot
        HousingPlot.objects.create(
            character_id=char.id,
            rooms_total=1,
            rooms_used=1,
        )

        # Give the room ID to the player
        # Use dbid — Evennia's canonical pk accessor on typeclass objects
        char.db.housing_home_id = new_room.dbid

        # Durgin's response — varies by nothing, he's seen it all
        _tent_responses = [
            f"Durgin snatches the shards off the counter with practiced speed and "
            f"stamps a piece of paperwork without looking at it. "
            f"'Done. Room's yours, {char_name}. Type |whome|n to get there. "
            f"Walls are thick, door locks from the inside, and I've already "
            f"forgotten this conversation.' He taps his temple. "
            f"'Professional amnesia. It's a service I provide free of charge.'",

            f"'Lovely.' Durgin pockets the shards with the satisfaction of a man "
            f"who genuinely loves his work. 'Your tent's been carved out of the void "
            f"and it's all yours, {char_name}. Use |whome|n to get there.' "
            f"He leans on the counter. 'I've soundproofed it as best the void allows. "
            f"What I mean is — your neighbors won't hear much. "
            f"What I also mean is — have a wonderful time.'",

            f"Durgin hands over a small brass key out of pure habit, "
            f"stares at it, then puts it back under the counter. "
            f"'Void room. No physical door yet. Old habits.' "
            f"He waves a hand. 'Room's ready — type |whome|n, {char_name}. "
            f"It's private, it's yours, and the anchor points in the ceiling "
            f"are purely structural. Probably.' A pause. 'You're welcome.'",

            f"'And that,' says Durgin, pocketing the shards with a flourish, "
            f"'is what we in the trade call a wise investment.' "
            f"He fixes {char_name} with a look of genuine warmth. "
            f"'One room, all yours. Type |whome|n. Do with it what you will. "
            f"I mean that with every implication it carries.'",
        ]

        import random
        npc.location.msg_contents(random.choice(_tent_responses))
        return

    # ── Waypost purchase ───────────────────────────────────────────────────
    if purchase_type == "waypost":
        shards = char.db.shards or 0
        if shards < WAYPOST_PRICE:
            npc.execute_cmd(
                f"say {char_name}, that's {WAYPOST_PRICE} shards for a waypost. "
                f"You've got {shards}. Come back when you've got the coin."
            )
            return

        # Charge
        char.db.shards = shards - WAYPOST_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=WAYPOST_PRICE,
            reason="purchase",
            note="Waypost purchase from Durgin Ironwood",
        )

        # Create the waypost object and hand it to the player
        from typeclasses.waypost import Waypost
        waypost = create.create_object(
            typeclass=Waypost,
            key="a waypost",
            location=char,
        )
        waypost.db.owner_account_id = char.account.id if char.account else None
        waypost.db.owner_char_id    = char.id
        waypost.db.owner_name       = char_name

        _waypost_responses = [
            f"Durgin produces a waypost from under the counter, handles it briefly "
            f"with the reverence of a craftsman handing over good work, and sets it "
            f"in front of {char_name}. "
            f"'Yours now. Give it a realm address — say |wwaypost address <word>|n — "
            f"then drop it in a room you own. Anyone who knows the word can reach you "
            f"from the hub waystone.' He pockets the shards. "
            f"'One word. Your word. Guard it or share it — that's entirely your business.'",

            f"Durgin counts the shards, nods in satisfied approval, and slides a "
            f"carved waypost across the counter to {char_name}. "
            f"'It's inert until you name it,' he says. "
            f"'Type |wwaypost address <word>|n to set your realm address, "
            f"then place it — drop it — in whatever room you're calling home. "
            f"After that, anyone who speaks the address near a hub waystone "
            f"arrives right at your door.' A pause. "
            f"'Or whatever you've put in place of a door. I don't judge.'",

            f"'Here.' Durgin sets the waypost down between them with a satisfying "
            f"clunk. 'Good wood, Ironwood runes, properly keyed. "
            f"It'll take whatever address you give it.' "
            f"He meets {char_name}'s eyes. 'One word. Something you'll remember. "
            f"Use |wwaypost address <word>|n, drop it in your space, and that's your "
            f"corner of the realm — reachable by anyone who knows the name.' "
            f"He grins into his beard. 'Private, but not secret. Unless you want it secret. "
            f"In which case: don't tell anyone.'",
        ]

        import random
        npc.location.msg_contents(random.choice(_waypost_responses))
        return

    # ── Seat cushion purchase ──────────────────────────────────────────────
    if purchase_type == "cushion":
        if shards < CUSHION_PRICE:
            npc.execute_cmd(
                f"say {char_name}, a seat cushion is {CUSHION_PRICE} shards. "
                f"You've got {shards}. That's a standing problem."
            )
            return

        char.db.shards = shards - CUSHION_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=CUSHION_PRICE,
            reason="purchase",
            note="Seat cushion from Durgin Ironwood",
        )

        from typeclasses.seat_mechanic import SeatMechanic
        cushion = create.create_object(
            typeclass=SeatMechanic,
            key="a seat cushion",
            location=char,
        )
        cushion.db.capacity = 2
        cushion.db.label    = "the seat"

        _cushion_responses = [
            f"Durgin slides the cushion across the counter to {char_name} "
            f"with the no-nonsense air of a man completing a straightforward transaction. "
            f"'There you go. |wuse seat cushion on <zone>|n — whatever zone "
            f"you want to make sittable. It installs and disappears, "
            f"and after that two people can sit there.' "
            f"He glances up. 'Set the label on it first if you want "
            f"something other than \"the seat\" to show in the room desc. "
            f"|w@set seat cushion/label = <name>|n. Builders only.' "
            f"He goes back to his ledger. 'Enjoy the seating arrangement.'",

            f"Durgin pockets the shards, produces a cushion from under the counter "
            f"in one smooth motion, and holds it out to {char_name}. "
            f"'One seat cushion. Use it on a zone, it becomes seating for two, "
            f"it gets consumed. Clean transaction.' "
            f"He tilts his head. 'You can rename what shows up in the room desc '— "
            f"by default it says \"the seat\" — with |w@set seat cushion/label = <name>|n '— "
            f"'before you install it. After that it's permanent until someone "
            f"rebuilds the zone.' A pause. 'Or you buy another cushion. "
            f"Which I am always happy to sell you.'",
        ]

        import random
        npc.location.msg_contents(random.choice(_cushion_responses))
        return

    # ── Lotion purchase ────────────────────────────────────────────────────
    if purchase_type == "lotion":
        if shards < LOTION_PRICE:
            npc.execute_cmd(
                f"say {char_name}, a lotion bottle is {LOTION_PRICE} shards. "
                f"You've got {shards}. Come back when you're solvent."
            )
            return

        char.db.shards = shards - LOTION_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=LOTION_PRICE,
            reason="purchase",
            note="Lotion bottle from Durgin Ironwood",
        )

        from typeclasses.lotion_item import LotionItem
        lotion = create.create_object(
            typeclass=LotionItem,
            key="a lotion bottle",
            location=char,
        )
        lotion.db.boost_amount   = 0.25
        lotion.db.uses_remaining = 10
        lotion.db.label          = "the lotion"

        import random
        _lotion_responses = [
            f"Durgin slides the bottle across the counter to {char_name} "
            f"with the brisk efficiency of a man who has done this before. "
            f"'Apply with |wlotion <zone>|n. Ten uses. Each one's permanent.' "
            f"He goes back to his ledger. 'No refunds on changes already made. "
            f"That one's in the fine print.'",

            f"Durgin sets the bottle in {char_name}'s hand with a decisive nod. "
            f"'|wlotion <zone>|n — that's the command. Make sure you've got "
            f"a body mod installed on the zone first or it won't have anything "
            f"to work with.' A pause. 'I've never had to explain that twice "
            f"to the same customer. They figure it out.'",
        ]
        npc.location.msg_contents(random.choice(_lotion_responses))
        return

    # ── Syringe purchase ───────────────────────────────────────────────────
    if purchase_type == "syringe":
        if shards < SYRINGE_PRICE:
            npc.execute_cmd(
                f"say {char_name}, a syringe is {SYRINGE_PRICE} shards. "
                f"You've got {shards}. Not quite."
            )
            return

        char.db.shards = shards - SYRINGE_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=SYRINGE_PRICE,
            reason="purchase",
            note="Syringe from Durgin Ironwood",
        )

        from typeclasses.syringe_item import SyringeItem
        syringe = create.create_object(
            typeclass=SyringeItem,
            key="a syringe",
            location=char,
        )
        syringe.db.boost_amount        = 1.0
        syringe.db.temp_duration_hours = 6.0
        syringe.db.uses_remaining      = 5
        syringe.db.label               = "the syringe"

        import random
        _syringe_responses = [
            f"Durgin hands the syringe to {char_name} sealed and professional. "
            f"'|winject <target> [zone]|n — or |winject/self [zone]|n for yourself. "
            f"One size up, six hours. Five uses.' He meets their eyes. "
            f"'The permanent accumulation starts after the fifth use. "
            f"I mention this every time. Nobody ever stops at five.' "
            f"He goes back to his work.",

            f"Durgin counts out {char_name}'s shards, produces the syringe, "
            f"and sets it down with a precise click. 'Temporary. Six hours. "
            f"Five uses. |winject|n command.' A beat. "
            f"'The escalating permanent effects are documented in the product. "
            f"I'd say read the fine print, but there isn't any. "
            f"Consider this the fine print.' He nods once. 'Enjoy.'",
        ]
        npc.location.msg_contents(random.choice(_syringe_responses))
        return

    # ── Breast enhancement purchase ────────────────────────────────────────
    if purchase_type == "breast_mod":
        if shards < BREAST_MOD_PRICE:
            npc.execute_cmd(
                f"say {char_name}, a breast enhancement is {BREAST_MOD_PRICE} shards. "
                f"You've got {shards}. Short by {BREAST_MOD_PRICE - shards}."
            )
            return

        char.db.shards = shards - BREAST_MOD_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=BREAST_MOD_PRICE,
            reason="purchase",
            note="Breast enhancement from Durgin Ironwood",
        )

        from typeclasses.body_mod_item import BreastItem
        mod = create.create_object(
            typeclass=BreastItem,
            key="Breast Enhancement",
            location=char,
        )

        import random
        _breast_responses = [
            f"Durgin hands the case to {char_name} with the composed air of "
            f"a man who has sold a very normal product. "
            f"'|winstall Breast Enhancement|n — that puts it on your chest zone. "
            f"After that, set a zone description using the {{size}} token and it "
            f"renders dynamically.' He taps the counter. "
            f"'Lotion and syringe work on it once it's in. "
            f"Milk glands install alongside it. I've given you the whole ecosystem.' "
            f"He raises his tankard. 'Build something impressive.'",

            f"Durgin slides the case across the counter to {char_name}. "
            f"'Install command: |winstall Breast Enhancement|n. Targets your chest zone.' "
            f"He opens his ledger. 'It tracks its own size float. "
            f"Put {{size}} in your zone's nude description and it fills in automatically.' "
            f"A pause. 'I'd say good luck, but this product doesn't require luck. "
            f"It requires patience and shards, both of which you've demonstrated.'",
        ]
        npc.location.msg_contents(random.choice(_breast_responses))
        return

    # ── Milk glands purchase ───────────────────────────────────────────────
    if purchase_type == "milk_glands":
        if shards < MILK_GLANDS_PRICE:
            npc.execute_cmd(
                f"say {char_name}, milk glands are {MILK_GLANDS_PRICE} shards. "
                f"You've got {shards}. {MILK_GLANDS_PRICE - shards} short."
            )
            return

        char.db.shards = shards - MILK_GLANDS_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=MILK_GLANDS_PRICE,
            reason="purchase",
            note="Milk glands from Durgin Ironwood",
        )

        from typeclasses.production_item import MilkProductionItem
        glands = create.create_object(
            typeclass=MilkProductionItem,
            key="Milk Glands",
            location=char,
        )

        import random
        _milk_responses = [
            f"Durgin produces the case and sets it before {char_name} "
            f"with the brisk manner of a man completing a supply chain. "
            f"'|winstall Milk Glands|n — chest zone, alongside a breast enhancement. "
            f"Accumulation starts immediately. Extract with a milking machine "
            f"or the |wmilk|n command.' He pauses. "
            f"'Set a flavor profile with |wsetfluid/flavor Milk Glands = <desc>|n '— "
            f"'if you want the bottles to have a tasting note. "
            f"I ship product. What you put in the notes section is between you "
            f"and whoever reads the label.'",

            f"Durgin counts the shards and slides the case to {char_name} in one motion. "
            f"'Install command: |winstall Milk Glands|n. Chest zone. "
            f"It scales output with whatever breast enhancement you've got in.' "
            f"He leans on the counter. 'You'll want the enhancement first "
            f"if you haven't got it. The multiplier's worth it.' "
            f"A pause. 'The fridge in Helena's place holds bottles, if you "
            f"need somewhere to stock the output. Not my department, "
            f"but I do comprehensive onboarding.'",
        ]
        npc.location.msg_contents(random.choice(_milk_responses))
        return

    # ── Penis enhancement purchase ─────────────────────────────────────────
    if purchase_type == "penis_mod":
        if shards < PENIS_MOD_PRICE:
            npc.execute_cmd(
                f"say {char_name}, a penis enhancement is {PENIS_MOD_PRICE} shards. "
                f"You've got {shards}. Short by {PENIS_MOD_PRICE - shards}."
            )
            return

        char.db.shards = shards - PENIS_MOD_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=PENIS_MOD_PRICE,
            reason="purchase",
            note="Penis enhancement from Durgin Ironwood",
        )

        from typeclasses.body_mod_item import PenisItem
        mod = create.create_object(
            typeclass=PenisItem,
            key="Penis Enhancement",
            location=char,
        )

        import random
        _penis_responses = [
            f"Durgin hands the case to {char_name} with complete professional composure. "
            f"'|winstall Penis Enhancement|n — targets your penis zone. "
            f"{{size}} token in the zone description renders the length-and-girth descriptor.' "
            f"He makes a note in his ledger. 'Lotion for permanent increments, "
            f"syringe for temporary boost. Semen glands pair with it if production "
            f"is the direction you're going.' He nods once. 'Ironwood standard. Enjoy.'",

            f"Durgin pockets the shards and slides the case across the counter. "
            f"'Starts at average. Install it with |winstall Penis Enhancement|n, "
            f"put {{size}} in your zone description, and it tracks from there.' "
            f"A pause. 'I've been asked what the ceiling is. The answer is: "
            f"architecturally significant, mythological, and beyond. "
            f"I built the scale. I have no regrets.' He goes back to his ledger.",
        ]
        npc.location.msg_contents(random.choice(_penis_responses))
        return

    # ── Testicle enhancement purchase ──────────────────────────────────────
    if purchase_type == "testicle_mod":
        if shards < TESTICLE_MOD_PRICE:
            npc.execute_cmd(
                f"say {char_name}, a testicle enhancement is {TESTICLE_MOD_PRICE} shards. "
                f"You've got {shards}. Not quite."
            )
            return

        char.db.shards = shards - TESTICLE_MOD_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=TESTICLE_MOD_PRICE,
            reason="purchase",
            note="Testicle enhancement from Durgin Ironwood",
        )

        from typeclasses.body_mod_item import TesticleItem
        mod = create.create_object(
            typeclass=TesticleItem,
            key="Testicle Enhancement",
            location=char,
        )

        import random
        _testicle_responses = [
            f"Durgin produces the case and hands it to {char_name} "
            f"with a brisk nod. '|winstall Testicle Enhancement|n — "
            f"targets your testicles zone. Volume scale, pea-sized up through "
            f"load-bearing and structurally significant.' He taps the counter. "
            f"'Pairs with semen glands — the production multiplier is one-point-five "
            f"times when this is in the zone. Worth the extra shards if you're "
            f"running both.' He returns to his work.",

            f"'Starts at average,' Durgin says, sliding the case over. "
            f"'|winstall Testicle Enhancement|n on your testicles zone. "
            f"{{size}} token shows the volume descriptor.' "
            f"He pauses. 'I put \"load-bearing\" on the scale as a joke. "
            f"Then I thought about it and decided it was actually useful information. "
            f"Left it in.' He meets {char_name}'s eyes briefly. 'Lotion. Syringe. "
            f"Same as everything else. Good luck.'",
        ]
        npc.location.msg_contents(random.choice(_testicle_responses))
        return

    # ── Semen glands purchase ──────────────────────────────────────────────
    if purchase_type == "semen_glands":
        if shards < SEMEN_GLANDS_PRICE:
            npc.execute_cmd(
                f"say {char_name}, semen glands are {SEMEN_GLANDS_PRICE} shards. "
                f"You've got {shards}. {SEMEN_GLANDS_PRICE - shards} short."
            )
            return

        char.db.shards = shards - SEMEN_GLANDS_PRICE
        ShardTransaction.objects.create(
            sender_id=char.id,
            recipient_id=None,
            amount=SEMEN_GLANDS_PRICE,
            reason="purchase",
            note="Semen glands from Durgin Ironwood",
        )

        from typeclasses.production_item import SemenProductionItem
        glands = create.create_object(
            typeclass=SemenProductionItem,
            key="Semen Glands",
            location=char,
        )

        import random
        _semen_responses = [
            f"Durgin hands the case to {char_name} and wipes the counter. "
            f"'|winstall Semen Glands|n — penis or testicles zone. Accumulates "
            f"passively, extracts with |wmilk|n or a machine.' "
            f"He holds up a finger. 'Testicle enhancement in the same zone gives "
            f"a one-point-five multiplier on output. The two are designed to work together.' "
            f"He sets the case down. 'Set a flavor note with |wsetfluid/flavor Semen Glands = <desc>|n '— "
            f"'if you want the bottles to say something. I ship the product. "
            f"What goes on the label is not my department.'",

            f"'Production item,' says Durgin, completing the handoff with "
            f"professional efficiency. '|winstall|n command. Penis or testicles zone. "
            f"It accumulates. It extracts. It bottles.' "
            f"He opens his ledger. 'Lower base rate than milk glands, "
            f"but scales harder with size — especially paired with testicle enhancement. "
            f"The math works out.' A pause. 'I ran the numbers. "
            f"I didn't need to run the numbers but I did anyway. "
            f"Professional interest.' He does not elaborate.",
        ]
        npc.location.msg_contents(random.choice(_semen_responses))
        return

    # ── Room pack purchase ─────────────────────────────────────────────────
    pack_size = purchase_type
    price = ROOM_PACK_PRICES.get(pack_size)

    if price is None:
        return

    plot = HousingPlot.get_or_none(char.id)
    if not plot:
        npc.execute_cmd(
            f"say You need a tent before you can buy extra rooms, {char_name}. "
            f"Start with the basics."
        )
        return

    if shards < price:
        npc.execute_cmd(
            f"say {price} shards for {pack_size} room{'s' if pack_size > 1 else ''}, "
            f"{char_name}. You've got {shards}. "
            f"That's... not {price}."
        )
        return

    # Charge
    char.db.shards = shards - price
    ShardTransaction.objects.create(
        sender_id=char.id,
        recipient_id=None,
        amount=price,
        reason="purchase",
        note=f"+{pack_size} room pack from Durgin Ironwood",
    )

    plot.rooms_total += pack_size
    plot.save()

    _bulk_comments = {
        1: [
            f"'One more room.' Durgin doesn't look up from his ledger, "
            f"but he's smiling. 'Very sensible. Some things just need "
            f"their own dedicated space, don't they. No judgement — "
            f"in fact, considerable respect. {plot.rooms_total} rooms total. "
            f"|whousing dig|n to add it.'",

            f"Durgin pockets the shards and makes a small note. "
            f"'Smart. Keep your activities separated. Good boundaries. "
            f"Or no boundaries, depending on what the room's for.' "
            f"He grins. '{plot.rooms_total} total now — |whousing dig|n.'",
        ],
        5: [
            f"Durgin raises both eyebrows this time. That's new. "
            f"'Five rooms. You've got a vision, {char_name}. I respect a vision.' "
            f"He pockets the shards slowly, like he's savouring the moment. "
            f"'Dedicated spaces for dedicated purposes. Efficient. "
            f"You've got {plot.rooms_total} total — |whousing dig|n to build them out.' "
            f"He taps the side of his nose. 'I won't ask which room's for what. "
            f"But between you and me, I have a guess.'",

            f"'Five.' Durgin lets out a low whistle. 'Getting serious, are we. "
            f"A room for this, a room for that, a room for the things "
            f"you don't want anyone knowing about...' He waves a hand. "
            f"'The classic configuration. {plot.rooms_total} rooms total. "
            f"|whousing dig|n. I'll be here if you need more.'",
        ],
        10: [
            f"Durgin sets down his ale with a deliberate thud and gives you "
            f"his full, undivided, impressed attention. "
            f"'Ten rooms, {char_name}. Ten.' He shakes his head slowly — "
            f"not in disapproval, but in the manner of a craftsman "
            f"confronted with an ambitious commission. "
            f"'That's a whole lifestyle you're building there. "
            f"I've outfitted dungeons with fewer rooms than that.' "
            f"A significant pause. 'Not that I'm assuming anything. "
            f"{plot.rooms_total} total. |whousing dig|n. You beautiful lunatic.'",

            f"'Ten rooms.' Durgin pulls out a fresh sheet of parchment "
            f"and starts sketching something. 'You'll want to think about flow. "
            f"Where things start, where they end up, what kind of anchor points "
            f"you're going to need in the ceiling of room three...' "
            f"He catches himself. 'Professionally speaking. {plot.rooms_total} total. "
            f"|whousing dig|n. Come back if you want layout advice. "
            f"I give very discreet layout advice.'",
        ],
        20: [
            f"There is a pause while Durgin counts the shards very carefully, "
            f"as though confirming this is really happening. "
            f"'Twenty rooms,' he says, in a voice of quiet professional reverence. "
            f"'I want you to know that in thirty years of carpentry, "
            f"I have never — not once — asked a customer what they intended "
            f"to do with their space.' He meets your eyes. "
            f"'I am coming very close to breaking that rule right now.' "
            f"He doesn't. 'You've got {plot.rooms_total} total. |whousing dig|n. "
            f"I'm building you a plaque. IRONWOOD HOUSING'S MOST VALUED CLIENT. "
            f"You've earned it.'",
        ],
        25: [
            f"The shop goes quiet. "
            f"Durgin looks at the shards. Looks at {char_name}. "
            f"Looks at the shards again, as if they might tell him something. "
            f"They do not. \n"
            f"'Twenty-five rooms,' he says finally, with the soft wonder "
            f"of a man who has just witnessed something he cannot fully process. "
            f"'That is not a tent. That is not even a house. "
            f"That is a compound, {char_name}. That is an institution. "
            f"That is a legacy.' \n"
            f"He pockets the shards in complete silence, writes something "
            f"in his ledger, crosses it out, writes it again. "
            f"'I have so many questions. I will ask none of them. "
            f"{plot.rooms_total} rooms total. |whousing dig|n.' "
            f"A reverent pause. "
            f"'It has been an honour.'",
        ],
    }

    import random
    responses = _bulk_comments.get(pack_size, [f"'{pack_size} rooms added. {plot.rooms_total} total.'"])
    npc.location.msg_contents(random.choice(responses))


# ---------------------------------------------------------------------------
# Spawn function — run once from @py
# ---------------------------------------------------------------------------

def spawn_durgin(room_dbref=None):
    """
    Create Durgin Ironwood in the specified room.

    Args:
        room_dbref (str, optional): e.g. "#5" or None to spawn homeless
                                    (move him manually with @tel).

    Usage (in-game):
        @py from world.durgin_spawn import spawn_durgin; spawn_durgin("#5")
    """
    from evennia.utils import create
    from typeclasses.npc import NPC

    location = None
    if room_dbref:
        from evennia.objects.models import ObjectDB
        try:
            pk = int(str(room_dbref).strip().lstrip("#"))
            location = ObjectDB.objects.get(pk=pk)
        except Exception as e:
            print(f"Could not find room '{room_dbref}': {e}")
            return None

    durgin = create.create_object(
        typeclass=NPC,
        key="Durgin Ironwood",
        location=location,
    )

    durgin.db.npc_tier    = 2   # Scripted
    durgin.db.npc_id      = "durgin_ironwood"
    durgin.db.react_to_say = True   # responds to 'say' in room
    durgin.db.rp_name     = "Durgin Ironwood"
    durgin.db.physical_desc = DURGIN_DESC.strip()
    durgin.db.presence    = DURGIN_PRESENCE
    durgin.db.ambient_base = DURGIN_AMBIENT
    durgin.db.ambient_interval = [120, 300]
    durgin.db.triggers    = DURGIN_TRIGGERS
    durgin.db.player_states = {}

    # Register purchase handler on the NPC so the trigger system can call it
    durgin.db.purchase_handler = "world.durgin_spawn.handle_purchase"

    # -------------------------------------------------------------------
    # Zones — visible on examine / zone-targeted look
    # -------------------------------------------------------------------
    def _dzone(nude, visibility="examine", zone_type="surface",
               intimate=False, consent_required="casual", parent=None):
        return {
            "nude":             nude,
            "interior":         "",
            "covered_by":       None,
            "contents":         [],
            "ambient":          [],
            "zone_type":        zone_type,
            "intimate":         intimate,
            "visibility":       visibility,
            "consent_required": consent_required,
            "default":          True,
            "parent":           parent,
        }

    durgin.db.zones = {
        # ── Head ──────────────────────────────────────────────────────
        "face": _dzone(
            "A ruddy, weathered face — the kind earned over decades of "
            "sawdust, ale, and professional opinions. Reading spectacles "
            "sit perpetually perched near the end of his broad nose, "
            "usually pushed down far enough to look over them rather than through.",
            visibility="look",
            parent="head",
        ),
        "hair": _dzone(
            "Sparse on top, what remains is a reddish-brown going grey "
            "at the temples, cropped close enough that it isn't a concern.",
            visibility="examine",
            parent="head",
        ),
        "beard": _dzone(
            "His most distinguished feature and obvious point of personal "
            "pride: a full, dense beard braided into three thick plaits, "
            "each one secured with a small iron door hinge instead of a "
            "bead. The braids are even, deliberate, and maintained with "
            "far more care than the rest of him.",
            visibility="look",
            parent="head",
        ),

        # ── Torso ─────────────────────────────────────────────────────
        "chest": _dzone(
            "Broad, solid, and largely concealed beneath the leather apron "
            "that is Durgin's default state of dress. Whatever's under the "
            "apron is a shirt of undetermined color that has seen better "
            "decades.",
            visibility="examine",
            parent="torso",
        ),
        "abdomen": _dzone(
            "Durgin is a dwarf of considerable girth, and he is entirely "
            "at peace with this. The apron does not conceal so much as "
            "organize.",
            visibility="examine",
            parent="torso",
        ),

        # ── Arms ──────────────────────────────────────────────────────
        "hands": _dzone(
            "Thick, scarred, perpetually dusted with sawdust or chalk. "
            "The knuckles are the kind that have met wood, metal, and "
            "at least one disputed door frame. He handles small mechanisms "
            "— locks, hinges, springs — with surprising precision.",
            visibility="look",
            parent="arms",
        ),

        # ── Outfit / covering ─────────────────────────────────────────
        "apron": _dzone(
            "Heavy leather, stained in layers that tell a professional "
            "biography. Dark patches of oil, lighter scars of sawdust, "
            "a faint burn mark near the left pocket. Several pockets, all "
            "full of things that rattle. A maker's stamp on the bib reads: "
            "|xIRONWOOD CO.|n, faded almost to invisibility.",
            visibility="look",
            parent=None,   # freeform outer layer, not in standard tree
        ),
    }

    # Apply shop room desc if a location was given and it has no desc yet
    if location and not (location.db.desc or "").strip():
        location.db.desc         = DURGIN_SHOP_DESC
        location.db.examine_desc = DURGIN_SHOP_EXAMINE_DESC
        location.db.entry_desc   = DURGIN_SHOP_ENTRY_DESC
        location.key             = DURGIN_SHOP_NAME
        print(f"  Shop room desc applied to {location.key}.")

    print(f"Durgin Ironwood created: #{durgin.id}")
    if location:
        print(f"  Placed in: {location.key} #{location.id}")
    else:
        print(f"  No location — move him with: @tel #{durgin.id} = #<room>")

    return durgin
