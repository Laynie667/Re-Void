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

WAYPOST_PRICE = 300   # shards — one waypost, one realm address


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
            f"  Tent (1 room)   — {TENT_PRICE} shards\n"
            f"  +1 room pack    — {ROOM_PACK_PRICES[1]} shards\n"
            f"  +5 room pack    — {ROOM_PACK_PRICES[5]} shards\n"
            f"  +10 room pack   — {ROOM_PACK_PRICES[10]} shards\n"
            f"  +20 room pack   — {ROOM_PACK_PRICES[20]} shards\n"
            f"  +25 room pack   — {ROOM_PACK_PRICES[25]} shards\n"
            f"  Waypost         — {WAYPOST_PRICE} shards\n\n"
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
            f"  Tent (1 room)   — {TENT_PRICE} shards\n"
            f"  +1 room pack    — {ROOM_PACK_PRICES[1]} shards\n"
            f"  +5 room pack    — {ROOM_PACK_PRICES[5]} shards\n"
            f"  +10 room pack   — {ROOM_PACK_PRICES[10]} shards\n"
            f"  +20 room pack   — {ROOM_PACK_PRICES[20]} shards\n"
            f"  +25 room pack   — {ROOM_PACK_PRICES[25]} shards\n"
            f"  Waypost         — {WAYPOST_PRICE} shards\n\n"
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
