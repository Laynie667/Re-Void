"""
world/build_forming.py

Build script for The Forming onboarding sequence.

USAGE
-----
From in-game (as superuser):
    @py from world.build_forming import build_all; build_all()

Or from Evennia shell:
    evennia shell
    >>> from world.build_forming import build_all
    >>> build_all()

WHAT IT DOES
------------
1. Creates five forming rooms with all descriptions, ambient lines,
   scene details, and room flags.
2. Creates void exits chaining each room to the next.
3. Spawns / updates all forming NPCs from world/npcs/forming.yaml
   and places them in their rooms.
4. Creates Wren's companion object with configured zones and freeform items.
5. Prints the dbref of each room so you can update forming.yaml if needed.

IDEMPOTENT
----------
Each room is tagged with its slot number under the 'forming_slot' category.
If a room with that tag already exists, the script updates it in place rather
than creating a duplicate. Safe to re-run after changes.
"""

import os

from evennia import create_object, search_tag, search_object
from evennia.utils import logger


ROOM_TC  = "typeclasses.rooms.Room"
EXIT_TC  = "typeclasses.exits.Exit"
NPC_TC   = "typeclasses.npc.NPC"
TAG_CAT  = "forming_slot"


# ---------------------------------------------------------------------------
# Room definitions
# ---------------------------------------------------------------------------

ROOMS = [
    # -----------------------------------------------------------------------
    # Space 1 — Before
    # -----------------------------------------------------------------------
    {
        "slot": 1,
        "key": "Before",
        "desc": (
            "There is no light here that comes from anywhere, and yet you see. "
            "The space extends\noutward in directions that don't quite have names "
            "— a grey-white expanse, even and\nvast, the particular quiet of a place "
            "that has been waiting a long time.\n\n"
            "Beneath what might be your feet, something like a floor. Above, the "
            "concept of a\nceiling without the fact of one.\n\n"
            "You are aware of yourself as a point of attention. Small. Luminous, "
            "in the way that\nthings are luminous when nothing else is competing. "
            "The air — if it is air — carries\nthe specific, difficult-to-name "
            "quality of something that has not yet begun.\n\n"
            "In the center of the space, settled as though they have been here since "
            "before you\narrived and will be here long after, is a figure made of "
            "composed stillness."
        ),
        "entry_desc": "The space receives you without ceremony.",
        "examine_desc": (
            "The closer you look, the more this place suggests itself rather than "
            "declares. The\nfloor has grain — the faint impression of something "
            "compressed over a very long time,\nmineral or light that has settled "
            "and decided to behave like stone.\n\n"
            "At one edge — and edge is perhaps too strong a word — the void seems "
            "denser. More\ndeliberate. As though it has somewhere to be.\n\n"
            "You are still here. That, apparently, counts for something."
        ),
        "ambient_msgs": [
            "Something shifts in the quality of the quiet — a pressure, like a breath held.",
            "The light here pulses, very slowly, in a rhythm that almost matches something.",
            "The grey-white deepens at one edge of the space, briefly, then returns to itself.",
            "There is a sound that might be very distant, or might be memory. It doesn't resolve.",
        ],
        "scene_details": {
            "floor": (
                "What passes for a floor has texture — grain running in a direction that doesn't\n"
                "correspond to any wall. Like wood, except older. Like ice, except without the cold.\n"
                "It holds you without declaring itself."
            ),
            "ceiling": (
                "Up, and then more up, and then the specific quality of distance that means nothing\n"
                "further applies. You could look at it for a long time and learn very little."
            ),
            "light": (
                "The light doesn't come from anything. It simply is, distributed evenly, casting no\n"
                "shadows. If you look for where it's brightest, you find yourself."
            ),
            "self": (
                "A point of light in a very still room. Your edges don't hold cleanly — they blur into\n"
                "the ambient grey-white, then reassert when you pay attention. You are here. That is,\n"
                "for now, sufficient."
            ),
            "me": (
                "A point of light in a very still room. Your edges don't hold cleanly — they blur into\n"
                "the ambient grey-white, then reassert when you pay attention. You are here. That is,\n"
                "for now, sufficient."
            ),
            "witness": (
                "They are indistinct at the edges in a way that reads as deliberate — not blurred, not\n"
                "absent, just not fully decided. Features that resolve into a general impression of\n"
                "attention. Eyes that are present. A mouth that rests near patience. The longer you\n"
                "look, the more the room seems to organize itself slightly around them, as if they are\n"
                "the fixed point and everything else — including you — is approximate."
            ),
            "figure": (
                "They are indistinct at the edges in a way that reads as deliberate — not blurred, not\n"
                "absent, just not fully decided. Features that resolve into a general impression of\n"
                "attention. Eyes that are present. A mouth that rests near patience."
            ),
        },
        "exit_key": "void",
        "exit_aliases": ["deeper", "inward", "beyond", "into the void", "further"],
        "npc_id": "forming_witness",
        "ambient_wisps": [],
    },
    # -----------------------------------------------------------------------
    # Space 2 — The Drift
    # -----------------------------------------------------------------------
    {
        "slot": 2,
        "key": "The Drift",
        "desc": (
            "The grey-white has changed. Not into something, exactly — into a place where\n"
            "something is possible.\n\n"
            "There is still no ceiling, no floor that declares itself, no walls with opinions\n"
            "about their own existence. But there is company.\n\n"
            "Other lights drift through the space at varying distances. Some are still. Some move\n"
            "with the slow deliberateness of things going somewhere without caring when they\n"
            "arrive. They are small — smaller than you expected — and each one is subtly\n"
            "particular. This one trails warmth. That one carries a faint sound at its edges, a\n"
            "frequency you almost recognize.\n\n"
            "You are one of these. This is what you look like from the outside: a point of\n"
            "attention, drifting in the same space, just as particular and just as hard to fully\n"
            "describe.\n\n"
            "Near the center, one light is more deliberate than the others. It has the quality of\n"
            "something that has been waiting, specifically, for you."
        ),
        "entry_desc": (
            "The drift receives you. Several lights take brief notice, then return to wherever\n"
            "they were going."
        ),
        "examine_desc": (
            "Each light here is different in ways that resist summary. Some have a sound at their\n"
            "edges. Some shift color when they move. Some seem larger up close than from a\n"
            "distance, and smaller again when you stop looking directly at them.\n\n"
            "You are trying to see yourself from the outside. It's difficult. You keep catching\n"
            "the edges of what you must look like — a particular quality of light, something\n"
            "distinctly yours — but the center of it keeps moving when you reach for it.\n\n"
            "That's fine. That's what this space is for."
        ),
        "ambient_msgs": [
            "A pale silver light drifts past, trailing something like a half-remembered melody.",
            "At the far edge, two lights press briefly together, then separate.",
            "Something small and very bright crosses the space too quickly to follow.",
            "The air here holds the impression of many presences, most of them elsewhere.",
            "One of the lights nearby brightens momentarily — emphasis, or acknowledgment, or just the nature of light.",
        ],
        "scene_details": {
            "others": (
                "Each one particular. This one carries warmth at its edges. That one moves with the\n"
                "specific quality of impatience. A third holds very still, watching something you\n"
                "can't see. You are one of these. The thought arrives without fanfare."
            ),
            "lights": (
                "Each one particular. This one carries warmth at its edges. That one moves with the\n"
                "specific quality of impatience. A third holds very still, watching something you\n"
                "can't see. You are one of these. The thought arrives without fanfare."
            ),
            "wisps": (
                "Each one particular. This one carries warmth at its edges. That one moves with the\n"
                "specific quality of impatience. A third holds very still, watching something you\n"
                "can't see. You are one of these. The thought arrives without fanfare."
            ),
            "lark": (
                "Warm amber, slightly larger than average, with the settled radiance of something\n"
                "that has been a light for a long time. At its edges, a faint sound — almost musical,\n"
                "almost not. It drifts without urgency, in the way of things that have stopped being\n"
                "impatient."
            ),
            "amber": (
                "Warm amber, slightly larger than average, with the settled radiance of something\n"
                "that has been a light for a long time. At its edges, a faint sound — almost musical,\n"
                "almost not. It drifts without urgency, in the way of things that have stopped being\n"
                "impatient."
            ),
            "self": (
                "You are a point of light in a space full of other points of light. From the outside —\n"
                "you understand this now — you look like this: particular, drifting, not yet fully\n"
                "decided. The color of you is whatever you've chosen, or haven't yet. The impression\n"
                "of you is yours to write. That is the only thing being asked of you here."
            ),
            "me": (
                "You are a point of light in a space full of other points of light. From the outside —\n"
                "you understand this now — you look like this: particular, drifting, not yet fully\n"
                "decided. The color of you is whatever you've chosen, or haven't yet. The impression\n"
                "of you is yours to write. That is the only thing being asked of you here."
            ),
            "sound": (
                "Some wisps carry a sound. Not music exactly — more like the memory of a frequency,\n"
                "or the suggestion of one. You could have this. It would be yours."
            ),
            "music": (
                "Some wisps carry a sound. Not music exactly — more like the memory of a frequency,\n"
                "or the suggestion of one. You could have this. It would be yours."
            ),
            "frequency": (
                "Some wisps carry a sound. Not music exactly — more like the memory of a frequency,\n"
                "or the suggestion of one. You could have this. It would be yours."
            ),
        },
        "exit_key": "void",
        "exit_aliases": ["deeper", "inward", "beyond", "into the void", "further"],
        "npc_id": "forming_lark",
        "ambient_wisps": [
            {
                "tag":      "drift_wisp_pale_silver",
                "key":      "a pale silver wisp",
                "presence": "A pale light drifts through, trailing something like music.",
            },
            {
                "tag":      "drift_wisp_warm_amber",
                "key":      "a slow amber wisp",
                "presence": "A warm amber light drifts at the edge of notice.",
            },
            {
                "tag":      "drift_wisp_bright",
                "key":      "a bright restless wisp",
                "presence": "Something small and very bright moves through without stopping.",
            },
        ],
    },
    # -----------------------------------------------------------------------
    # Space 3 — Almost
    # -----------------------------------------------------------------------
    {
        "slot": 3,
        "key": "Almost",
        "desc": (
            "The space here has more intention than the ones before it. The grey-white hasn't\n"
            "resolved into anything you'd call a room, but it's trying — there are suggestions at\n"
            "the edges of what walls might look like, if walls were interested in applying for the\n"
            "position. The floor beneath you has more conviction than it did before.\n\n"
            "There are fewer lights here. The drift has thinned. What remains is more deliberate.\n\n"
            "Leaning against what might become a wall, if the wall decided to commit, is a person.\n"
            "An actual person — not a light, not a figure of composed stillness, not an impression\n"
            "of presence. A person with a face and hands and a particular quality of existing that\n"
            "takes up space in a way you haven't encountered yet in this place.\n\n"
            "They're looking at you like they remember something."
        ),
        "entry_desc": "The almost-room settles slightly, as if your arrival gave it something to work with.",
        "examine_desc": (
            "The walls here are applying for the position without having been hired yet. There is\n"
            "a surface-ness at the edges of this space — a commitment to having edges that wasn't\n"
            "present before. It hasn't quite resolved, but it's further along than nothing.\n\n"
            "You are still light. Still wisp. But this space is making you feel the absence of a\n"
            "body more specifically than before. It isn't unpleasant. It's information."
        ),
        "ambient_msgs": [
            "At the edge of your vision, something almost resolves into a wall, then changes its mind.",
            "The air here has a different quality — heavier, somehow. More specific.",
            "Sable watches the almost-space with the expression of someone who finds it genuinely interesting after a long time.",
            "A sound at the edge of hearing — not music, not voice, just the suggestion of a world with content in it.",
        ],
        "scene_details": {
            "wall": (
                "The walls here are applying for the position without having been hired. There is a\n"
                "surface-ness at the edges — a commitment to having edges. It hasn't resolved yet.\n"
                "It's trying."
            ),
            "walls": (
                "The walls here are applying for the position without having been hired. There is a\n"
                "surface-ness at the edges — a commitment to having edges. It hasn't resolved yet.\n"
                "It's trying."
            ),
            "edges": (
                "The walls here are applying for the position without having been hired. There is a\n"
                "surface-ness at the edges — a commitment to having edges. It hasn't resolved yet.\n"
                "It's trying."
            ),
            "floor": (
                "More convincing than the one before. Whatever this place is built on, it's getting\n"
                "more serious about the concept."
            ),
            "sable": (
                "Dark-haired, unhurried, with the quality of attention that comes from spending time\n"
                "in a world where attention matters. Their face is particular — not remarkable from a\n"
                "distance, very specific up close. They're wearing something simple. Their hands are\n"
                "still. They look like someone who knows what they look like, which is its own kind\n"
                "of confidence."
            ),
            "person": (
                "Dark-haired, unhurried, with the quality of attention that comes from spending time\n"
                "in a world where attention matters. Their face is particular — not remarkable from a\n"
                "distance, very specific up close. They're wearing something simple. Their hands are\n"
                "still. They look like someone who knows what they look like, which is its own kind\n"
                "of confidence."
            ),
            "hands": (
                "Sable's hands are still. People who are comfortable in their bodies do that — keep\n"
                "their hands without needing to put them somewhere purposeful. You notice this because\n"
                "you don't have hands yet.\n\nYou will."
            ),
            "self": (
                "You are still light — still wisp — but this space is making you feel the absence of\n"
                "a body more specifically. Not as a lack. More like standing outside a room and being\n"
                "able to smell what's cooking inside."
            ),
            "me": (
                "You are still light — still wisp — but this space is making you feel the absence of\n"
                "a body more specifically. Not as a lack. More like standing outside a room and being\n"
                "able to smell what's cooking inside."
            ),
        },
        "exit_key": "void",
        "exit_aliases": ["deeper", "inward", "mirror", "the mirror", "forward"],
        "npc_id": "forming_sable",
        "ambient_wisps": [],
    },
    # -----------------------------------------------------------------------
    # Space 4 — The Mirror
    # -----------------------------------------------------------------------
    {
        "slot": 4,
        "key": "The Mirror",
        "desc": (
            "The void has made a decision here. Where before there was only the suggestion of\n"
            "edges, here there are walls — spare, pale, committed to their own existence. The\n"
            "floor is stone or something that has agreed to behave like it. The ceiling is a fact.\n\n"
            "It is, finally, a room.\n\n"
            "At the far end, taking up most of the wall: a mirror. Not polished metal, not glass\n"
            "exactly — something that reflects without being entirely passive about it. The surface\n"
            "holds your shape with particular attention, as though it is considering you as much\n"
            "as showing you.\n\n"
            "What it reflects is almost you. Not quite yet. Close."
        ),
        "entry_desc": "The Mirror notices you immediately.",
        "examine_desc": (
            "The walls here are decided. Whatever made the void thicken into a room has finished\n"
            "its work and is satisfied with the result.\n\n"
            "The Mirror itself, examined closely, has no frame. It simply begins at the floor and\n"
            "ends at the ceiling, as if it predates the room and the room was built around it.\n\n"
            "Your reflection in it shifts slightly as you look — not because you moved, but because\n"
            "the Mirror is showing you something slightly ahead of what you are. The shape of what\n"
            "you're about to be.\n\n"
            "It is, you understand, waiting."
        ),
        "ambient_msgs": [
            "The Mirror's surface ripples once, slowly, like deep water responding to something not quite on the surface.",
            "The room is very quiet. The Mirror does not mind.",
            "Your reflection holds still when you hold still, and moves when you move, but there is something in the timing that suggests it is making a choice about this.",
            "The pale walls have the quality of good listening.",
            "The Mirror catches the light you're made of and returns it differently — more organized, more deliberate.",
        ],
        "scene_details": {
            "mirror": (
                "It reflects you with specific attention. Not the passive accuracy of glass — more\n"
                "like the focused regard of something that is actively interested in what it's seeing.\n"
                "Your shape in it is real but provisional. The details are waiting for you to decide them."
            ),
            "surface": (
                "It reflects you with specific attention. Not the passive accuracy of glass — more\n"
                "like the focused regard of something that is actively interested in what it's seeing.\n"
                "Your shape in it is real but provisional. The details are waiting for you to decide them."
            ),
            "reflection": (
                "It reflects you with specific attention. Not the passive accuracy of glass — more\n"
                "like the focused regard of something that is actively interested in what it's seeing.\n"
                "Your shape in it is real but provisional. The details are waiting for you to decide them."
            ),
            "walls": (
                "Decided. Committed. This is the first room in The Forming that behaves like a room\n"
                "without apology. Something about that is both a relief and a weight — the void gave\n"
                "you nowhere to be. This place gives you somewhere. That means something."
            ),
            "room": (
                "Decided. Committed. This is the first room in The Forming that behaves like a room\n"
                "without apology. Something about that is both a relief and a weight — the void gave\n"
                "you nowhere to be. This place gives you somewhere. That means something."
            ),
            "floor": (
                "Decided. Committed. This is the first room in The Forming that behaves like a room\n"
                "without apology. Something about that is both a relief and a weight — the void gave\n"
                "you nowhere to be. This place gives you somewhere. That means something."
            ),
            "ceiling": (
                "Decided. Committed. This is the first room in The Forming that behaves like a room\n"
                "without apology. Something about that is both a relief and a weight — the void gave\n"
                "you nowhere to be. This place gives you somewhere. That means something."
            ),
            "self": (
                "You are here. The Mirror already knows that. What it doesn't know yet — what it is\n"
                "waiting for you to decide — is the rest."
            ),
            "me": (
                "You are here. The Mirror already knows that. What it doesn't know yet — what it is\n"
                "waiting for you to decide — is the rest."
            ),
        },
        "exit_key": "void",
        "exit_aliases": ["forward", "out", "world", "the world"],
        "npc_id": "forming_mirror",
        "ambient_wisps": [],
    },
    # -----------------------------------------------------------------------
    # Space 5 — The Fitting (Wren & Co.)
    # -----------------------------------------------------------------------
    {
        "slot": 5,
        "key": "The Fitting",
        "desc": (
            "The void deposits you somewhere that has made significant decisions about what it\n"
            "wants to be.\n\n"
            "The shop is narrow and precise — shelves running floor to ceiling on both sides, each\n"
            "one organized with the specificity of someone who cares deeply about category. Glass\n"
            "cases along the left wall display items arranged by size, function, and a third\n"
            "criterion you cannot immediately determine. The lighting is warm, even, and has no\n"
            "interest in flattering anyone.\n\n"
            "At the back, behind a counter that has survived more than you have, a woman is writing\n"
            "something down. She does not look up when you arrive.\n\n"
            "To the right, on a low raised platform, a figure stands very still."
        ),
        "entry_desc": (
            "Wren does not look up.\n\n"
            '"Close the door," she says. There is no door to close. She says it anyway.'
        ),
        "examine_desc": (
            "The shelves are better organized than anything you have encountered in The Forming.\n"
            "Labels in small, precise handwriting. Items arranged with the logic of someone who\n"
            "has a system and has never been persuaded to explain it.\n\n"
            "The glass cases on the left contain things that are technically describable and yet\n"
            "resist summary. All of them are labeled. All the labels are extremely specific.\n\n"
            "Wren is still writing. Whatever it is, she is going to finish it."
        ),
        "ambient_msgs": [
            "Something in the left case catches the light and holds it with unnecessary enthusiasm.",
            "Wren turns a page. She reads it. She makes a small sound of professional dissatisfaction.",
            "The companion on the platform shifts its weight by a fraction — or perhaps you only imagined this.",
            "The shop is very organized. You feel faintly judged by the organization.",
            "Wren looks up briefly, makes an assessment, returns to her work.",
        ],
        "scene_details": {
            "shelves": (
                "Organized by a system you do not fully grasp but which clearly makes sense to someone.\n"
                "The labels are clinical. The items are not. You get the sense that Wren would describe\n"
                "all of them with the same energy she uses to describe everything else: accurately,\n"
                "completely, and without ceremony."
            ),
            "items": (
                "Organized by a system you do not fully grasp but which clearly makes sense to someone.\n"
                "The labels are clinical. The items are not."
            ),
            "products": (
                "Organized by a system you do not fully grasp but which clearly makes sense to someone.\n"
                "The labels are clinical. The items are not."
            ),
            "case": (
                "The left wall's display cases contain items arranged by size, function, and a third\n"
                "category whose label you can read but whose organizing logic remains opaque. All of\n"
                "it is priced. Wren has opinions about what things are worth."
            ),
            "cases": (
                "The left wall's display cases contain items arranged by size, function, and a third\n"
                "category whose label you can read but whose organizing logic remains opaque. All of\n"
                "it is priced. Wren has opinions about what things are worth."
            ),
            "glass case": (
                "The left wall's display cases contain items arranged by size, function, and a third\n"
                "category whose label you can read but whose organizing logic remains opaque. All of\n"
                "it is priced. Wren has opinions about what things are worth."
            ),
            "counter": (
                "Old, solid, covered in paperwork that is also organized. Wren's workspace. The pen\n"
                "she is using has clearly been used for a very long time. She has not replaced it."
            ),
            "desk": (
                "Old, solid, covered in paperwork that is also organized. Wren's workspace. The pen\n"
                "she is using has clearly been used for a very long time. She has not replaced it."
            ),
            "wren": (
                "Sharp-featured, somewhere between thirty and the concept of having stopped counting,\n"
                "with the particular posture of someone who has arranged their skeleton for maximum\n"
                "efficiency over many years. Her hair is pulled back with the single-minded practicality\n"
                "of someone who solved that problem once and has not revisited it. She looks like someone\n"
                "who has been asked the same question by many different people and has answered it every time."
            ),
            "companion": (
                "The demonstration model stands on the low platform to the right — present, attentive,\n"
                "dressed in something that implies the possibility of being undressed. Its zones are\n"
                "visible at varying degrees of examination. It is, as far as you can tell, the most\n"
                "complete character description you have encountered so far in this place.\n\n"
                "It is also clearly a product."
            ),
            "model": (
                "The demonstration model stands on the low platform to the right — present, attentive,\n"
                "dressed in something that implies the possibility of being undressed."
            ),
            "figure": (
                "The demonstration model stands on the low platform to the right — present, attentive,\n"
                "dressed in something that implies the possibility of being undressed."
            ),
            "doll": (
                "The demonstration model stands on the low platform to the right — present, attentive,\n"
                "dressed in something that implies the possibility of being undressed. Its zones are\n"
                "visible at varying degrees of examination."
            ),
            "platform": (
                "A low raised dais, to the right of the entrance. The companion stands on it with the\n"
                "quality of something that has been placed with intention and is comfortable with that."
            ),
        },
        "exit_key": "void",
        "exit_aliases": ["out", "world", "forward", "the door"],
        "npc_id": "forming_wren",
        "ambient_wisps": [],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_room(slot, key):
    """
    Find an existing forming room by its slot tag, or create a new one.
    Returns (room, was_created).
    """
    results = search_tag(str(slot), category=TAG_CAT)
    if results:
        room = results[0]
        print(f"  [existing] #{room.id}  {room.key}")
        return room, False

    room = create_object(typeclass=ROOM_TC, key=key)
    room.tags.add(str(slot), category=TAG_CAT)
    print(f"  [created]  #{room.id}  {room.key}")
    return room, True


def _apply_room_data(room, data):
    """Write all descriptive attributes from data dict onto the room."""
    room.key                = data["key"]
    room.db.desc            = data["desc"]
    room.db.entry_desc      = data["entry_desc"]
    room.db.examine_desc    = data["examine_desc"]
    room.db.ambient_msgs    = list(data["ambient_msgs"])
    room.db.scene_details   = dict(data["scene_details"])
    room.db.is_forming      = True
    room.ensure_ambient_script()


def _replace_exit(exit_key, aliases, source, destination):
    """
    Remove any existing exit with the same key in source, then create a
    fresh one pointing to destination. Returns the new exit object.
    """
    for ex in list(source.exits):
        if ex.key == exit_key:
            ex.delete()
            break

    exit_obj = create_object(
        typeclass=EXIT_TC,
        key=exit_key,
        location=source,
        destination=destination,
    )
    if aliases:
        exit_obj.aliases.add(aliases)
    return exit_obj


def _spawn_ambient_wisps(room, wisp_list):
    """
    Spawn Tier-1 ambient wisp NPCs in The Drift.
    Tagged under 'forming_wisp' so they aren't duplicated on re-runs.
    """
    from typeclasses.npc import NPC_TIER_AMBIENT

    for wdata in wisp_list:
        tag     = wdata["tag"]
        results = search_tag(tag, category="forming_wisp")
        if results:
            continue  # already exists

        wisp = create_object(
            typeclass=NPC_TC,
            key=wdata["key"],
            location=room,
        )
        wisp.tags.add(tag, category="forming_wisp")
        wisp.db.npc_tier      = NPC_TIER_AMBIENT
        wisp.db.rp_name       = wdata["key"]
        wisp.db.ic_presence   = wdata["presence"]
        wisp.db.physical_desc = wdata["presence"]
        print(f"    [wisp]    {wdata['key']}  #{wisp.id}")


def _place_npc(npc_id, room):
    """
    Move an already-spawned NPC (by npc_id tag) into the given room.
    Prints a warning if the NPC doesn't exist yet.
    """
    from world.npc_loader import NPCLoader

    npc = NPCLoader.get_npc_by_id(npc_id)
    if npc is None:
        print(f"  [missing]  NPC '{npc_id}' not found — YAML spawn may have failed")
        return None

    if npc.location != room:
        npc.move_to(room, quiet=True)
        print(f"  [moved]    {npc.key}  →  #{room.id} {room.key}")
    else:
        print(f"  [present]  {npc.key}  in  #{room.id} {room.key}")
    return npc


def _build_companion(room):
    """
    Create or update Wren's demonstration companion in The Fitting.

    The companion is a Tier-1 NPC (no triggers, no ambient) with a complete
    zone layout spanning every visibility level, and three freeform items
    pre-placed to demonstrate dressing.
    """
    from world.npc_loader import NPCLoader
    from typeclasses.npc import NPC_TIER_AMBIENT

    # Find or create
    companion = NPCLoader.get_npc_by_id("forming_companion")
    if companion is None:
        companion = create_object(
            typeclass=NPC_TC,
            key="the companion",
            location=room,
        )
        companion.tags.add("forming_companion", category="npc_id")
        companion.db.npc_id = "forming_companion"
        print(f"  [created]  companion  #{companion.id}")
    else:
        if companion.location != room:
            companion.move_to(room, quiet=True)
        print(f"  [existing] companion  #{companion.id}")

    # Identity
    companion.db.npc_tier    = NPC_TIER_AMBIENT
    companion.db.rp_name     = "the companion"
    companion.key            = "the companion"

    # Descriptions
    companion.db.physical_desc = (
        "The demonstration model is built to show range. Proportions that read as "
        "intentional rather than accidental — everything placed with the awareness of "
        "being looked at. The kind of figure that makes the concept of clothing feel "
        "like a considered choice rather than a default.\n\n"
        "Its expression is attentive. Patient, in the way of things that do not "
        "experience the passage of time as loss."
    )
    companion.db.ic_presence = (
        "The companion stands very still on the platform, dressed in something that "
        "implies more than it covers."
    )
    companion.db.outfit_desc = (
        "It is dressed in something that implies the possibility of being undressed — "
        "structured fabric, close fit, the suggestion of layers."
    )

    # Consent flags — open for demonstration purposes
    companion.db.consent_flags = {
        "casual":      True,
        "intimate":    True,
        "mature":      True,
        "bdsm":        False,
        "lead_follow": False,
        "restraint":   False,
        "plock":       False,
    }

    # Disable triggers and ambients — companion is decorative
    companion.db.triggers         = {}
    companion.db.ambient_base     = []
    companion.db.react_to_say     = False
    companion.db.parrot_responses = []

    # -------------------------------------------------------------------
    # Zone layout — every visibility level demonstrated
    # -------------------------------------------------------------------
    def zone(nude, visibility, intimate=False, zone_type="surface",
             consent_required="casual", parent=None):
        return {
            "nude":             nude,
            "interior":         "",
            "covered_by":       None,
            "contents":         [],
            "ambient":          [],
            "visibility":       visibility,
            "intimate":         intimate,
            "zone_type":        zone_type,
            "consent_required": consent_required,
            "default":          True,
            "parent":           parent,
        }

    companion.db.zones = {
        # -- ROOT: head --
        "head": zone(
            "The companion's head is held with the quality of something "
            "that knows it is being looked at and is comfortable with that.",
            "look",
            parent=None,
        ),

        # -- look visibility (visible on standard look) --
        "hair": zone(
            "Dark, swept back, held in place with something minimal — "
            "a clip or cord, functional and close.",
            "look",
            parent="head",
        ),
        "face": zone(
            "Even features, arranged with the particular quality of attention "
            "that comes from being looked at often. Neither inviting nor closed — present.",
            "look",
            parent="head",
        ),

        # -- ROOT: neck --
        "neck": zone(
            "A clean line from jaw to collarbone. Unadorned at the skin, "
            "waiting for what will be placed.",
            "look",
            parent=None,
        ),

        # -- ROOT: torso --
        "torso": zone(
            "The trunk of it — proportioned for visibility, held with the "
            "awareness of a figure that has been built to be examined.",
            "look",
            parent=None,
        ),

        # -- examine visibility (visible on examine) --
        "chest": zone(
            "Where the garment begins its commitments — the surface beneath structured "
            "fabric, present and described without apology.",
            "examine",
            parent="torso",
        ),
        "waist": zone(
            "The line where the garment makes its first decision. Narrow, defined, "
            "the point around which everything else is organized.",
            "examine",
            parent="torso",
        ),
        "back": zone(
            "Bare from shoulder to mid-back where the garment begins. "
            "The line of the spine visible. Intentionally uncovered.",
            "examine",
            parent="torso",
        ),

        # -- ROOT: arms --
        "arms": zone(
            "Fine detail work visible on the inner wrist — a small marking, not "
            "immediately visible from a distance, that becomes clear on closer inspection.",
            "examine",
            parent=None,
        ),
        "hands": zone(
            "Still. The kind of still that reads as practice rather than accident — "
            "deliberate, composed, at rest.",
            "look",
            parent="arms",
        ),
        "wrists": zone(
            "The left wrist, bare at the skin beneath whatever is placed here. "
            "The attachment point for the cuff.",
            "examine",
            zone_type="attachment",
            parent="arms",
        ),

        # -- ROOT: legs --
        "legs": zone(
            "The lower half, present and proportioned. The garment covers them "
            "while implying them.",
            "look",
            parent=None,
        ),

        # -- proximity visibility (visible only at near/with) --
        "hips": zone(
            "Specific. Intentional. The garment suggests them rather than conceals — "
            "the line beneath it present and readable at close range.",
            "proximity",
            consent_required="intimate",
            parent="legs",
        ),
        "thighs": zone(
            "The garment suggests them more than it conceals. The shape beneath it "
            "is present — visible at close range, not from across the room.",
            "proximity",
            consent_required="intimate",
            parent="legs",
        ),
        "lower_back": zone(
            "A small mark here — a brand or a tattoo, old enough to have settled "
            "into the skin — visible only at close range.",
            "proximity",
            consent_required="intimate",
            parent="torso",
        ),

        # -- ROOT: groin --
        "groin": zone(
            "The companion's groin is present in its design. The garment covers it "
            "with intention — suggesting what is beneath rather than revealing.",
            "look",
            parent=None,
        ),

        # -- consent-gated intimate zones --
        "chest_intimate": zone(
            "Present. Detailed. Described for those with intimate consent — this zone "
            "exists beneath the garment and responds to what is placed on or removed from it.",
            "proximity",
            intimate=True,
            zone_type="both",
            consent_required="intimate",
            parent="torso",
        ),
        "groin_intimate": zone(
            "Fully described. Consent-gated. This zone is complete in its description "
            "and present in the companion's design — it exists to demonstrate what the "
            "consent system protects.",
            "consent",
            intimate=True,
            zone_type="both",
            consent_required="mature",
            parent="groin",
        ),
    }

    # -------------------------------------------------------------------
    # Pre-placed freeform items
    # -------------------------------------------------------------------
    companion.db.freeform_items = {
        "collar": {
            "zone":       "neck",
            "name":       "collar",
            "desc":       (
                "A slim band of dark leather, plain, buckled close against the skin. "
                "A single ring at the front."
            ),
            "placed_by":  None,
            "lock":       None,
        },
        "corset": {
            "zone":       "waist",
            "name":       "corset",
            "desc":       (
                "Black, structured, laced at the back with enough tension to be "
                "intentional. It holds the torso with opinion."
            ),
            "placed_by":  None,
            "lock":       None,
        },
        "cuff": {
            "zone":       "wrist",
            "name":       "cuff",
            "desc":       (
                "Matching leather, left wrist only. Attached. The ring on it echoes "
                "the one at the throat."
            ),
            "placed_by":  None,
            "lock":       None,
        },
    }

    return companion


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_all():
    """
    Create or update all forming rooms, exits, NPCs, and the companion.
    Print a summary table at the end.
    """
    print("\n=== Building The Forming ===\n")

    # ------------------------------------------------------------------
    # 1. Rooms
    # ------------------------------------------------------------------
    print("--- Rooms ---")
    room_objects = []
    for rdata in ROOMS:
        room, _ = _get_or_create_room(rdata["slot"], rdata["key"])
        _apply_room_data(room, rdata)
        room_objects.append(room)

    # ------------------------------------------------------------------
    # 2. Exits — chain rooms 1→2→3→4→5, then 5→hub
    # ------------------------------------------------------------------
    print("\n--- Exits ---")
    for i in range(len(ROOMS) - 1):
        rdata  = ROOMS[i]
        source = room_objects[i]
        dest   = room_objects[i + 1]
        ex     = _replace_exit(
            rdata["exit_key"],
            rdata["exit_aliases"],
            source,
            dest,
        )
        print(f"  {source.key}  →  {dest.key}  ({ex.key})")

    # Space 5 exit — goes to hub room #2 by default.
    # TODO: change '#2' to the actual hub room dbref once it exists.
    hub_results = search_object("#2")
    hub = hub_results[0] if hub_results else room_objects[0]
    ex5 = _replace_exit(
        ROOMS[-1]["exit_key"],
        ROOMS[-1]["exit_aliases"],
        room_objects[-1],
        hub,
    )
    print(f"  {room_objects[-1].key}  →  {hub.key}  (hub — update when hub exists)")

    # ------------------------------------------------------------------
    # 3. Spawn NPCs from YAML (creates them if not already present)
    # ------------------------------------------------------------------
    print("\n--- NPC Loader ---")
    try:
        from world.npc_loader import NPCLoader
        yaml_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "npcs",
            "forming.yaml",
        )
        configs = NPCLoader.load_file(yaml_path)
        if configs:
            for cfg in configs:
                npc = NPCLoader.spawn_from_config(cfg)
                if npc:
                    print(f"  [yaml]    {npc.key}  (id: {cfg.get('id', '?')})")
        else:
            print("  [warning] No NPC configs loaded from forming.yaml")
    except Exception as e:
        print(f"  [error]   YAML load failed: {e}")

    # ------------------------------------------------------------------
    # 4. Place NPCs in their rooms
    # ------------------------------------------------------------------
    print("\n--- NPC Placement ---")
    for i, rdata in enumerate(ROOMS):
        npc_id = rdata.get("npc_id")
        if npc_id:
            _place_npc(npc_id, room_objects[i])
        if rdata.get("ambient_wisps"):
            _spawn_ambient_wisps(room_objects[i], rdata["ambient_wisps"])

    # ------------------------------------------------------------------
    # 5. Companion (Space 5)
    # ------------------------------------------------------------------
    print("\n--- Companion ---")
    _build_companion(room_objects[4])

    # ------------------------------------------------------------------
    # 6. Summary table
    # ------------------------------------------------------------------
    print("\n--- Summary ---")
    print(f"  {'Slot':<5} {'Dbref':<7} {'Room':<18} {'NPC ID'}")
    print(f"  {'-'*5} {'-'*7} {'-'*18} {'-'*20}")
    for i, room in enumerate(room_objects):
        npc_id = ROOMS[i].get("npc_id", "—")
        print(f"  {i+1:<5} #{room.id:<6} {room.key:<18} {npc_id}")

    try:
        from world.npc_loader import NPCLoader as _NL
        _comp = _NL.get_npc_by_id("forming_companion")
        print(f"  Companion:  #{_comp.id if _comp else '?'}")
    except Exception:
        print("  Companion:  (lookup failed)")

    print("\n=== Done ===")
    print(
        "\nNext steps:"
        "\n  1. Update world/npcs/forming.yaml — set each NPC's 'location' field"
        "\n     to the dbref shown in the summary above (e.g. location: \"#42\")."
        "\n  2. Run build_all() again to move NPCs to their correct rooms."
        "\n  3. Once the hub room is built, update the Space 5 exit destination"
        "\n     in build_forming.py (search for 'TODO: change #2')."
    )
