"""
world/realm_build.py — builds The Facility as a real, disconnected grid realm.

Run once, as the owner, standing in the housing room that should hold the
return waypost:

    @py from world.realm_build import build_realm; build_realm(me)

What it does:
  * digs a disconnected cluster of real rooms (lobby + stations + pigsty)
  * places a HubWaystone in the lobby AND in your housing
  * an ENTRY waypost in the lobby (active) — say its word in your housing to go
  * a RETURN waypost in your housing (INACTIVE / held) — saying its word in the
    realm does nothing until the facility activates it (you've earned it)
  * basic craft-quality descriptions on every room (expanded later)
  * stores realm metadata on the owner: me.db.realm

Entry word: revealed to the owner on build (you need a way in).
Return word: held — call reveal_return(me) to activate it when requirements met.

OOC floor (always works, never gated):
    @py from world.realm_build import escape; escape(me)     # home + purge
"""

import random

# Six core rooms for the first pass; the sprawl extends from here.
_ROOMS = [
    ("lobby",        "The Facility — Intake",
     "|wA cold reception under sodium light that hums a half-tone flat.|n The air is "
     "wrong-warm and smells of milk, disinfectant, and animal. A long counter runs the "
     "far wall, a stack of intake forms weighted under a brand. There is one door in, and "
     "it has already closed behind you. A standing waystone glows faintly in the corner — "
     "the only obvious way anywhere, and it only answers to words it knows."),
    ("floor",        "The Facility — Processing Floor",
     "|wA long low hall of padded breeding stations on a slow conveyor.|n Coiled tubing and "
     "steel fixtures hang from the walls; collection bottles rack beneath each milking rig. "
     "Stock is worked here, milked and bred and dosed on a schedule that loops and does not "
     "end. The light never changes and the line never stops."),
    ("pens",         "The Facility — Breeding Pens",
     "|wStalls and a kennel run, thick with the smell of rutting animal.|n A bull stamps in "
     "one stall; a boar grunts in a low pen; a stallion screams somewhere down the row. The "
     "hounds pace their run and scent the air whenever the heat in the place shifts. Each "
     "animal is kept ready and walked to the floor when the board says it's owed."),
    ("conditioning", "The Facility — Conditioning Cell",
     "|wA dim, padded cell lit by a single band of light and a speaker grille.|n This is where "
     "the lights drop and the voice gets close. The walls eat sound. Whatever is said in here "
     "is said directly into you, and a little more of what you were is gone by the door."),
    ("dairy",        "The Facility — Dairy & Output",
     "|wA cold white room of racks and refrigerated cases.|n Bottles stand in graded rows, each "
     "labelled with a number and a date — product, shelved, inventoried. This is where what "
     "comes out of the stock is kept, and where the stock is shown what it's become: a column "
     "in a ledger, a figure that only goes up."),
    ("pigsty",       "The Facility — The Pigsty",
     "|wA filthy mud-and-slop pen at the bottom of the place, reeking and warm.|n A trough runs "
     "one wall; the floor is churned muck. This is where the lowest stock is kept on all fours "
     "to wallow, slopped and hosed and rutted and put back. It is also, the board notes, a "
     "place graded stock can be *sent* — a reminder, and a destination."),
]

# Adjacency (non-linear): which rooms connect to which.
_EXITS = {
    "lobby":        ["floor"],
    "floor":        ["lobby", "pens", "conditioning", "dairy"],
    "pens":         ["floor", "pigsty"],
    "conditioning": ["floor", "dairy"],
    "dairy":        ["floor", "pigsty"],
    "pigsty":       ["pens", "dairy"],
}

_ENTRY_WORDS  = ["downstairs", "processing", "belowstairs", "intake", "thefarm", "downbelow"]
_RETURN_WORDS = ["surfacing", "homeward", "released", "clockout", "upstairs", "iwasaperson"]


def _z(desc, summary="", study=None, handle=None, ambient=None, details=None,
       mechanic=None, inscribe=False):
    """Compact room-zone builder matching roomzone_commands._blank_zone schema.

    mechanic: optional spec installed as a real zone mechanic, one of:
        ("restrain", capacity, label, blocker_msg)
        ("seat",     capacity, label, position)
        ("dildo",    capacity, label, position)
        ("milk",)    — a milking machine mechanic
    """
    return {
        "desc": desc, "summary": summary,
        "details": details or {}, "handle_details": handle or {},
        "study_details": study or [], "inscribable": bool(inscribe), "inscriptions": [],
        "scent": None, "ambient": ambient or [], "contents": [], "parent": None,
        "mechanics": {}, "scripts": [], "event_hooks": {}, "bar_drinks": [],
        "games": [], "pantry": [],
        "_install": mechanic,   # consumed by _furnish, not part of the stored zone
    }


# Per-room craft: zones (desc/study/handle/ambient), furniture, and NPCs.
_ROOM_ZONES = {
    "lobby": {
        "counter": _z(
            "A long steel counter runs the far wall, scuffed and clean-scrubbed, a stack "
            "of multi-page intake forms weighted flat under a cold-iron brand.",
            summary="a long steel reception counter",
            study=[
                "The topmost form is half-filled in someone else's hand — your description, "
                "your measurements, a column already headed OUTPUT, blank, waiting.",
                "The brand holding the papers down is shaped like the facility's mark. It is "
                "not decorative. It is just the nearest thing heavy enough.",
            ],
            handle={
                "touch": "{actor} runs a hand along the counter's edge — cold, faintly tacky "
                         "with disinfectant, worn smooth by everyone processed before {target}.",
            },
            ambient=["A form slides off the stack and settles on the floor. No one picks it up."]),
        "waystone": _z(
            "A standing stone of dark mineral glows faintly in the corner, runes spiralling "
            "its surface — the only obvious way anywhere, and it only answers to words it knows.",
            summary="a faintly glowing waystone",
            study=[
                "The stone's glow pulses very slightly, like breathing, like patience.",
                "One word brought you down here. The word that lifts you back out is not cut "
                "anywhere on it, and not one you've been given.",
            ]),
        "door": _z(
            "A single heavy door is set in the near wall, seamless, no handle on this side. "
            "It closed behind you on arrival and has the settled look of something that "
            "won't open again until it's decided to.",
            summary="a sealed, handleless door",
            study=["There's no handle, no panel, no seam you can work a finger into. The "
                   "door is a statement, and the statement is no."]),
        "light": _z(
            "Sodium lamps hum a half-tone flat overhead, the light even and shadowless and "
            "the colour of old bone.",
            summary="humming sodium light",
            ambient=["The sodium hum dips, wavers, steadies. The light never quite goes out.",
                     "Under the flat light, everything — including you — looks like inventory."]),
    },
    "floor": {
        "line": _z(
            "Padded breeding stations run the length of the hall on a slow conveyor, most of "
            "them empty, each fitted with restraints, a descending milking rig, and a "
            "swing-mounted intake arm. The line advances on a timer and does not stop.",
            summary="the breeding line of padded stations",
            study=[
                "Each station is cut away and angled to fold an occupant into presentation and "
                "hold her there, hands-free, at exactly working height.",
                "The conveyor ticks forward a notch every so often, carrying whatever's strapped "
                "in from milking to breeding to dosing without ever reaching an end.",
            ],
            handle={"touch": "{actor} touches the nearest station's padding — wipe-clean vinyl, "
                             "still warm from the last thing held in it."},
            ambient=["Somewhere down the line a rig descends, works, and rises again, wet.",
                     "A collection bottle fills a measure higher and the gauge logs it."]),
        "rigs": _z(
            "Articulated arms of suction cups and tubing hang ready over each station, "
            "graduated bottles racked beneath, gauges logging yield.",
            summary="milking rigs and collection bottles",
            study=["The bottles are labelled by number, not name. One rack is yours, or will be."]),
    },
    "pens": {
        "stalls": _z(
            "Heavy stalls line the wall — a dull-eyed breeding bull in one, a rank tusked boar "
            "in a low pen, a big-barrelled stallion stamping in the last — stock kept ready and "
            "walked to the line when the board says it's owed.",
            summary="stalls of breeding stock",
            study=[
                "The animals don't pace with hunger so much as schedule. They've learned the "
                "rhythm of the place. So, the board notes, will you.",
                "Each stall has a gate that opens onto a walkway that opens onto the line. The "
                "geometry of the room only goes one direction, and it isn't out.",
            ],
            handle={"touch": "{actor} reaches toward a stall and the animal inside leans into it, "
                             "huge and warm and entirely uninterested in {target} as a person."},
            ambient=["The bull stamps and snorts, and the sound carries.",
                     "The boar's musk thickens whenever the heat in the room shifts."]),
        "kennel": _z(
            "A long kennel run takes up one wall, heavy rangy hounds pacing the bars, noses "
            "working at the air, loosed one at a time on schedule.",
            summary="a kennel run of hounds",
            study=["The hounds scent heat through the bars and whine when they catch it. They "
                   "are very patient and not patient at all."],
            ambient=["A hound presses to the bars, snuffling, and is told to wait."]),
    },
    "conditioning": {
        "cradle": _z(
            "A padded cradle-chair sits in the centre under the single band of light, "
            "restraints open and waiting, angled back so whoever's in it faces the dark and "
            "the speaker grille.",
            summary="a padded conditioning cradle",
            study=["The cradle holds you still and slightly reclined — comfortable, which is "
                   "the cruelty: comfort, and the voice, and nowhere to look but up."],
            handle={"touch": "{actor} touches the cradle's restraints — soft-lined, unhurried, "
                             "built to keep someone for a long, quiet while."}),
        "dark": _z(
            "Past the single band of light the cell goes to padded black that eats sound. The "
            "speaker grille is the only fixed point, and the voice comes from everywhere at once.",
            summary="sound-eating dark and a speaker grille",
            ambient=["The dark presses a little closer between one breath and the next.",
                     "The speaker clicks, considers, and stays silent — for now."]),
    },
    "dairy": {
        "racks": _z(
            "Refrigerated cases and steel racks hold bottles in graded rows, each labelled with "
            "a number and a date — product, shelved and inventoried.",
            summary="racks of bottled output",
            study=[
                "A whole shelf is given to one number. You don't have to be told whose. The "
                "dates run back further than seems possible for one body.",
                "The bottles are sorted by yield and grade. Being good is, here, a quantity.",
            ],
            handle={"touch": "{actor} lifts a cold bottle from the rack — heavy, full, labelled "
                             "with a number where a name should be."}),
        "ledger": _z(
            "A terminal and a chalk board hold the dairy's running totals — what each resident "
            "has produced, charted against the day they still argued.",
            summary="the output ledger",
            ambient=["A figure on the board updates itself upward. It only ever goes one way."]),
    },
    "pigsty": {
        "wallow": _z(
            "The floor is churned mud and slop, warm and reeking, deep enough to kneel in and "
            "be held — where the lowest stock is kept on all fours to wallow.",
            summary="a deep reeking mud wallow",
            study=[
                "The muck is kept warm on purpose. It is easier to stop minding it than you'd "
                "think, and minding less is the whole point of the room.",
                "There's no clean corner. There's nowhere in here that lets you stay a person "
                "who is merely visiting.",
            ],
            handle={"touch": "{actor} sinks a hand into the warm slop — it gives, and clings, "
                             "and doesn't let go quickly."},
            ambient=["Something shifts under the muck and settles. A bubble surfaces and pops."]),
        "trough": _z(
            "A long trough runs one wall, slopped twice a cycle, the only thing in here built "
            "for a mouth.",
            summary="a feeding trough",
            study=["You eat from it the way everything in here eats from it: bent, hands-free, "
                   "face down. The first time is the only hard time."]),
    },
}

# Furniture objects per room (FacilityFurniture).
_ROOM_FURNITURE = {
    "floor": [
        ("the breeding bench", "A heavy padded bench bolted to the floor, cut away to fold an "
         "occupant over it — ankle, wrist, and throat restraints, a height rail behind."),
        ("the milking rack", "An upright rack of articulated cups and tubing over graded "
         "bottles, a yield gauge logging every pull."),
        ("the fucking machine", "A piston-driven machine on a swing mount, a rack of "
         "attachments beside it, a dial that only turns one way."),
        ("the supply cart", "A wheeled cart of labelled vials, needle guns, gauging rings, "
         "brands and a tattoo kit — dosing and procedures within reach of the line."),
    ],
    "lobby": [
        ("the brand press", "A cold-iron brand on a press arm by the counter, kept at hand "
         "for marking intake the moment the forms are signed."),
    ],
    "pens": [
        ("the breeding stocks", "A timber frame at the mouth of the walkway that locks an "
         "occupant bent and spread at exactly the height the stock prefer."),
    ],
    "dairy": [
        ("the bottling station", "An automated bottling head over the racks, capping and "
         "labelling output with a number and the date, hands-free."),
    ],
    "pigsty": [
        ("the slop hose", "A coiled hose on the wall, for slopping the trough and hosing the "
         "stock — the only thing in here that ever makes anything cleaner, briefly."),
    ],
}

# NPCs per room: (key, species_or_role, desc).
_ROOM_NPCS = {
    "lobby": [
        ("the intake clerk", "attendant", "A bored clerk in a grey coverall behind the counter, "
         "stamping forms and not looking up — the last person here who'll treat you like "
         "paperwork instead of livestock."),
    ],
    "floor": [
        ("the attendant", "attendant", "An attendant in a clean grey coverall working the "
         "gauges along the line with unbothered efficiency."),
        ("the handler", "attendant", "A broad handler in a rubber apron who works the bodies — "
         "strapping, adjusting, lining up whose turn is next."),
    ],
    "pens": [
        ("the kennel", "hound", "A run of heavy hounds, pacing and scenting the air."),
        ("the bull", "bull", "A great dull-eyed breeding bull, shoulders like a wall."),
        ("the boar", "boar", "A rank tusked boar, small-eyed and patient."),
        ("the stallion", "stallion", "A big-barrelled stallion, sheath heavy, impatient."),
        ("the stockman", "attendant", "A stockman who walks the animals to the line on schedule."),
    ],
    "conditioning": [
        ("the conditioning tech", "attendant", "A soft-spoken tech who adjusts the cradle and "
         "the levels and never raises their voice, because the room does that for them."),
    ],
    "dairy": [
        ("the dairy hand", "attendant", "A dairy hand racking bottles and chalking totals, who "
         "refers to the stock entirely by number."),
    ],
    "pigsty": [
        ("the swineherd", "attendant", "A swineherd in waders who slops the trough, hoses the "
         "wallow, and treats what's kept here exactly as what it is."),
    ],
}


# Real mechanics installed onto room zones — these make the furniture WORK.
_ROOM_MECHANICS = {
    "lobby": {
        "counter": ("restrain", 1, "the intake counter",
                    "You're bent over the counter and held there while the forms are filled in. You wait."),
    },
    "floor": {
        "line":   ("restrain", 4, "the line restraints",
                   "The station folds you into presentation and locks. You can't move until the line decides to advance."),
        "rigs":   ("milk",),
    },
    "pens": {
        "stalls": ("restrain", 1, "the breeding stocks",
                   "The stocks lock you bent and spread at exactly the height the stock prefer. You wait to be bred."),
    },
    "conditioning": {
        "cradle": ("restrain", 1, "the conditioning cradle",
                   "The cradle holds you reclined and still, facing the dark and the voice. You listen, because there's nothing else to do."),
    },
    "dairy": {
        "racks": ("milk",),
    },
    "pigsty": {
        "wallow": ("seat", 6, "the wallow", "on all fours in the muck"),
        "trough": ("seat", 4, "the trough", "bent over the trough, face down"),
    },
}

# Room-level ambient pools (fire periodically as atmosphere).
_ROOM_AMBIENT = {
    "lobby": [
        "|xThe sodium lamps hum a half-tone flat, and the light never quite settles.|n",
        "|xThe clerk stamps another form without looking up. The stack never gets shorter.|n",
        "|xA draught carries the smell up from below — milk, animal, disinfectant — and the door stays shut.|n",
    ],
    "floor": [
        "|xDown the line a rig descends, works wetly, and rises again. The conveyor ticks one notch.|n",
        "|xA collection bottle fills a measure higher and a gauge logs the yield without comment.|n",
        "|xSomewhere a strap is cinched a notch tighter and a small, bitten-off sound follows.|n",
        "|xThe board updates a figure upward. It only ever moves the one way.|n",
    ],
    "pens": [
        "|xThe bull stamps and the sound carries through the floor.|n",
        "|xA hound presses to the bars, snuffling at the air, and is told to wait.|n",
        "|xThe boar's musk thickens whenever the heat in the place shifts.|n",
        "|xThe stallion screams once, impatient, and quiets when a handler glances at the clock.|n",
    ],
    "conditioning": [
        "|xThe dark presses a little closer between one breath and the next.|n",
        "|xThe speaker clicks, considers, and stays silent — for now.|n",
        "|xThe single band of light hums. There is nowhere to look but up into it.|n",
    ],
    "dairy": [
        "|xA figure on the board climbs itself upward. It only goes one way.|n",
        "|xThe bottling head caps and labels another, hands-free, and racks it by number.|n",
        "|xThe cold cases hum. A whole shelf is given to one number.|n",
    ],
    "pigsty": [
        "|xSomething shifts under the muck and settles. A bubble surfaces and pops.|n",
        "|xThe trough is slopped, twice a cycle, whether anything's ready for it or not.|n",
        "|xThe hose drips against the wall. The reek is kept warm on purpose.|n",
    ],
}


def _install_mechanic(room, zone_name, spec, installer):
    """Install a real mechanic into a room zone (restraint / seat / dildo / milk)."""
    if not spec:
        return
    from evennia.utils import create as _c
    kind = spec[0]
    try:
        if kind == "restrain":
            _, cap, label, blocker = (spec + (1, "the restraints", "It holds you."))[:4]
            m = _tag(_c.create_object("typeclasses.restrain_mechanic.RestrainMechanic",
                                      key=label, location=room))
            m.db.capacity = cap; m.db.label = label; m.db.blocker_msg = blocker
            m.install_into_zone(room, zone_name, installer)
        elif kind in ("seat", "dildo"):
            _, cap, label, pos = (spec + (1, "it", "seated"))[:4]
            path = ("typeclasses.dildo_seat_mechanic.DildoSeatMechanic" if kind == "dildo"
                    else "typeclasses.seat_mechanic.SeatMechanic")
            m = _tag(_c.create_object(path, key=label, location=room))
            m.db.capacity = cap; m.db.label = label; m.db.position = pos
            m.install_into_zone(room, zone_name, installer)
        elif kind == "milk":
            m = _tag(_c.create_object("typeclasses.milking_machine_mechanic.MilkingMachineMechanic",
                                      key="the milking rig", location=room))
            zones = dict(getattr(room.db, "zones", None) or {})
            zd = dict(zones.get(zone_name, {})); mech = dict(zd.get("mechanics", {}) or {})
            mech["milking_machine"] = {"item_dbref": m.dbref, "item_name": m.key,
                                       "speed": "steady", "cycle_mode": True}
            zd["mechanics"] = mech; zones[zone_name] = zd; room.db.zones = zones
    except Exception:
        pass


def _furnish(room, key, owner):
    """Apply craft (zones + tokens + mechanics + ambient), furniture, and NPCs."""
    # Designate the room as part of the named realm/area (ties to where/sheet).
    room.db.area = "The Facility"
    try:
        room.tags.add("the_facility", category="area")
    except Exception:
        pass
    # Zones — store a clean copy (pop the install spec) and remember mechanics.
    zones = dict(getattr(room.db, "zones", None) or {})
    to_install = []
    for zn, zd in (_ROOM_ZONES.get(key) or {}).items():
        zd = dict(zd)
        spec = zd.pop("_install", None)
        zd["summary"] = ""        # so {zone:} tokens render the full desc inline (Helena-style)
        zname = zn.replace(" ", "_")
        zones[zname] = zd
        if spec:
            to_install.append((zname, spec))
    room.db.zones = zones

    # Mechanics declared in _ROOM_MECHANICS (keeps the zone content readable).
    for zn, spec in (_ROOM_MECHANICS.get(key) or {}).items():
        to_install.append((zn.replace(" ", "_"), spec))

    # Install real mechanics into the zones.
    for zname, spec in to_install:
        _install_mechanic(room, zname, spec, owner)

    # Embed {zone:<name>} tokens so the zones render inline in the room look.
    tokens = "\n\n".join("{zone:%s}" % zn.replace(" ", "_")
                         for zn in (_ROOM_ZONES.get(key) or {}))
    if tokens:
        base = (room.db.desc or "").split("\n\n{zone:")[0]
        room.db.desc = base + "\n\n" + tokens

    # Room-level ambient lines.
    amb = _ROOM_AMBIENT.get(key)
    if amb:
        room.db.ambient_msgs = list(amb)
    # Furniture
    try:
        from typeclasses.facility_furniture import FacilityFurniture
        from evennia.utils import create as _c
        for fkey, fdesc in (_ROOM_FURNITURE.get(key) or []):
            f = _tag(_c.create_object(FacilityFurniture, key=fkey, location=room))
            f.db.desc = fdesc
    except Exception:
        pass
    # NPCs
    try:
        from typeclasses.facility_script import FacilityAttendant, FacilityBeast
        from evennia.utils import create as _c
        for nkey, role, ndesc in (_ROOM_NPCS.get(key) or []):
            cls = FacilityBeast if role in ("hound", "bull", "boar", "stallion") else FacilityAttendant
            n = _tag(_c.create_object(cls, key=nkey, location=room))
            n.db.rp_name = nkey
            n.db.physical_desc = ndesc
            n.db.facility_role = "beast" if role in ("hound", "bull", "boar", "stallion") else "attendant"
            if role in ("hound", "bull", "boar", "stallion"):
                n.db.species = role
    except Exception:
        pass


_REALM_TAG = "facility_realm"


def _tag(obj):
    try:
        obj.tags.add(_REALM_TAG, category="realm")
    except Exception:
        pass
    return obj


def teardown_realm(owner):
    """Remove ALL realm infrastructure: tagged objects + realm rooms + any
    waystone/waypost in the owner's current room (catches old untagged builds)."""
    removed = 0
    from evennia import search_object
    from evennia.utils.search import search_tag

    # 1. Everything tagged as realm (rooms, waystones, wayposts, furniture, NPCs).
    try:
        for o in list(search_tag(_REALM_TAG, category="realm") or []):
            try:
                # delete contents (NPCs/furniture) of realm rooms first
                for sub in list(getattr(o, "contents", []) or []):
                    if not sub.is_typeclass("typeclasses.characters.Character", exact=False):
                        try: sub.delete(); removed += 1
                        except Exception: pass
                o.delete(); removed += 1
            except Exception:
                pass
    except Exception:
        pass

    # 2. Realm rooms recorded in metadata (older builds, maybe untagged).
    realm = owner.db.realm or {}
    for dbref in list((realm.get("rooms") or {}).values()) + [realm.get("return_wp")]:
        if not dbref:
            continue
        for r in (search_object(dbref) or []):
            try:
                for sub in list(getattr(r, "contents", []) or []):
                    if not sub.is_typeclass("typeclasses.characters.Character", exact=False):
                        try: sub.delete(); removed += 1
                        except Exception: pass
                r.delete(); removed += 1
            except Exception:
                pass

    # 3. Scrub the owner's current room of any waystone/waypost (old untagged ones).
    room = owner.location
    if room:
        for o in list(room.contents):
            if (o.is_typeclass("typeclasses.waystone.HubWaystone", exact=False)
                    or o.is_typeclass("typeclasses.waypost.Waypost", exact=False)):
                try: o.delete(); removed += 1
                except Exception: pass

    owner.db.realm = None
    owner.msg(f"|gRealm torn down — {removed} objects removed.|n")
    return removed


def build_realm(owner):
    housing = owner.location
    if not housing:
        owner.msg("|rStand in your housing room first.|n")
        return
    from evennia import create_object
    from evennia.utils import create as _c

    # Clean slate.
    teardown_realm(owner)

    # 1. Dig the rooms (disconnected — no exits to the main grid).
    rooms = {}
    for key, name, desc in _ROOMS:
        r = create_object("typeclasses.rooms.Room", key=name)
        r.db.desc = desc
        _tag(r)
        _furnish(r, key, owner)   # zones, furniture, NPCs (tagged inside)
        rooms[key] = r

    # 2. Exits between realm rooms (one-way feel kept by naming, but walkable).
    for src, dests in _EXITS.items():
        for dst in dests:
            try:
                create_object("typeclasses.exits.Exit",
                              key=rooms[dst].key.split("— ")[-1].lower(),
                              location=rooms[src], destination=rooms[dst])
            except Exception:
                pass

    # 3. Navigation. A waystone listens in the lobby AND in housing.
    from typeclasses.waystone import HubWaystone
    from typeclasses.waypost import Waypost

    def _ensure_hub(room):
        if not any(o.is_typeclass("typeclasses.waystone.HubWaystone", exact=False)
                   for o in room.contents):
            _tag(create_object(HubWaystone, key="a waystone", location=room))

    _ensure_hub(rooms["lobby"])
    _ensure_hub(housing)

    entry_word  = random.choice(_ENTRY_WORDS)
    return_word = random.choice(_RETURN_WORDS)

    # ENTRY waypost: in the lobby, active. Say its word in housing -> arrive lobby.
    entry_wp = _tag(create_object(Waypost, key="the intake waypost", location=rooms["lobby"]))
    entry_wp.db.realm_address = entry_word
    entry_wp.db.owner_char_id = owner.id
    entry_wp.db.owner_name    = owner.db.rp_name or owner.key

    # RETURN waypost: in housing, INACTIVE (held). Activated only when worthy.
    return_wp = _tag(create_object(Waypost, key="a dark waypost", location=housing))
    return_wp.db.realm_address = None
    return_wp.db.owner_char_id = owner.id
    return_wp.db.owner_name    = owner.db.rp_name or owner.key

    # The contract — placed on the lobby counter. Signing it starts the cycle.
    try:
        from world.facility_build import (_CONTRACT_VISIBLE, _CONTRACT_HIDDEN,
                                          _CONTRACT_BINDING)
        from typeclasses.milking_contract import MilkingContract
        c = _tag(create_object(MilkingContract, key="contract", location=rooms["lobby"]))
        c.db.desc = ("A thick multi-page intake form on the counter, top sheet face-up, "
                     "the rest turned face-down.")
        c.db.author_id        = None
        c.db.duration_hours   = 720.0
        c.db.effect_arousal_floor = 35.0
        c.db.effect_stim_per_tick = 3.0
        c.db.binding_effects  = dict(_CONTRACT_BINDING)
        c.db.reveal_on_sign   = True
        for txt in _CONTRACT_VISIBLE:
            c.add_clause(txt, hidden=False)
        for txt in _CONTRACT_HIDDEN:
            c.add_clause(txt, hidden=True)
    except Exception:
        pass

    # 4. Store realm metadata (return_word held here, not revealed to her).
    owner.db.realm = {
        "rooms":       {k: v.dbref for k, v in rooms.items()},
        "housing":     housing.dbref,
        "entry_word":  entry_word,
        "return_word": return_word,
        "return_wp":   return_wp.dbref,
        "active":      False,
    }

    owner.msg(
        "\n|wThe Facility realm is built.|n\n"
        f"|xA waystone now stands in your housing. Speak the word |w{entry_word}|x here and it "
        "will take you down into Intake. There is a waystone in the lobby too — but the word "
        "that brings you home is not one you have been given. It will not work until the "
        "facility decides you've earned it.|n\n"
        "|x(OOC floor, always: @py from world.realm_build import escape; escape(me))|n"
    )


def reveal_return(owner):
    """Activate the held return word — call when she's met the requirements."""
    realm = owner.db.realm or {}
    word  = realm.get("return_word")
    ref   = realm.get("return_wp")
    if not word or not ref:
        owner.msg("|xNo realm return to activate.|n")
        return
    from evennia import search_object
    res = search_object(ref)
    if res:
        res[0].db.realm_address = word
        realm["active"] = True
        owner.db.realm = realm
        owner.msg(f"|gThe way home opens. The word is |w{word}|g. Speak it at a waystone to "
                  f"surface — if you still want to.|n")


def escape(owner):
    """OOC floor — always works. Home + purge, regardless of realm state."""
    realm = owner.db.realm or {}
    from evennia import search_object
    res = search_object(realm.get("housing", "")) if realm.get("housing") else None
    if res:
        owner.move_to(res[0], quiet=True)
    try:
        from world.facility_build import run_facility_reset
        run_facility_reset(owner, purge=True)
    except Exception:
        pass
    owner.msg("|gYou're home, and clear. The realm lets go of you completely.|n")


def force_clear(owner):
    """Bulletproof reset — clears ALL facility/realm state on the character,
    step by step so nothing half-fails. Use if run_facility_reset misbehaves."""
    d = owner.db
    # restore name + title FIRST (before clearing their backups)
    if getattr(d, "facility_name_backup", None):
        try: d.rp_name = d.facility_name_backup
        except Exception: pass
    tb = getattr(d, "facility_title_backup", None) or {}
    try:
        d.title_faction = tb.get("faction", "")
        d.title_suffix  = tb.get("suffix", "")
    except Exception: pass
    # lists -> []
    for k in ("active_speech_filters", "installed_triggers", "facility_brands",
              "permanent_gape", "piercings", "pet_trigger_sources", "bred_by",
              "sensation_broadcast_targets", "aphrodisiac_expirations",
              "conditioning_applied", "facility_items", "facility_room_zones"):
        try: setattr(d, k, [])
        except Exception: pass
    # -> None
    for k in ("pet_type", "designation", "facility_name_backup", "breeding_quota",
              "milk_quota", "holes", "gape", "offspring_progress", "offspring_counts",
              "facility_title_backup", "forced_posture", "body_language", "room_bound",
              "facility_zone", "facility_furniture"):
        try: setattr(d, k, None)
        except Exception: pass
    # -> 0
    for k in ("conditioning", "arousal_floor", "stim_per_tick", "bladder_ml", "arousal",
              "defiance", "compliance_threshold", "compliance_streak", "processing_tier",
              "facility_standing", "drug_dependence", "milk_baseline_ml"):
        try: setattr(d, k, 0)
        except Exception: pass
    # -> False / ""
    for k in ("orgasm_denial", "exhibition_active", "self_cmds_locked", "endcycle_blocked",
              "navigation_locked", "anti_clothing_active", "conditioning_permanent",
              "freedom_forfeited", "facility_signed", "facility_active", "perpetual_heat",
              "cum_craving", "lactation_locked", "body_processing_locked", "aura_dimmed"):
        try: setattr(d, k, False)
        except Exception: pass
    for k in ("orgasm_release_word", "required_honorific", "facility_grade", "facility_brand"):
        try: setattr(d, k, "" if "word" in k or "honorific" in k else None)
        except Exception: pass
    # consent restore
    backup = getattr(d, "facility_consent_backup", None)
    if backup is not None:
        try: d.consent_flags = dict(backup); d.facility_consent_backup = None
        except Exception: pass
    # stop scripts on her
    for s in list(owner.scripts.all()):
        if getattr(s, "key", "") in ("realm_cycle", "perpetual_heat", "body_processing",
                                     "facility", "cycle_machine") or \
           s.is_typeclass("typeclasses.milking_session_script.MilkingSessionScript", exact=False):
            try: s.stop()
            except Exception: pass
    # remove worn facility piercings
    try:
        from typeclasses.piercing_item import PiercingItem
        for o in list(owner.contents):
            if isinstance(o, PiercingItem) and getattr(o.db, "facility_piercing", False):
                try: o.delete()
                except Exception: pass
    except Exception: pass
    # clear facility freeform marks
    try:
        ff = {k: v for k, v in (dict(getattr(d, "freeform_items", None) or {})).items()
              if not str(k).startswith("facility mark")}
        d.freeform_items = ff
    except Exception: pass
    owner.msg("|gForce-cleared. Speech, conditioning, triggers, marks, scripts, title — all reset.|n")
