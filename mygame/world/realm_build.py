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


def build_realm(owner):
    housing = owner.location
    if not housing:
        owner.msg("|rStand in your housing room first.|n")
        return
    from evennia import create_object
    from evennia.utils import create as _c

    # Tear down a previous build if present.
    old = owner.db.realm or {}
    for dbref in (old.get("rooms") or {}).values():
        try:
            from evennia import search_object
            for r in (search_object(dbref) or []):
                for o in list(r.contents):
                    if not hasattr(o, "account"):   # don't delete characters
                        try: o.delete()
                        except Exception: pass
                r.delete()
        except Exception:
            pass

    # 1. Dig the rooms (disconnected — no exits to the main grid).
    rooms = {}
    for key, name, desc in _ROOMS:
        r = create_object("typeclasses.rooms.Room", key=name)
        r.db.desc = desc
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
            create_object(HubWaystone, key="a waystone", location=room)

    _ensure_hub(rooms["lobby"])
    _ensure_hub(housing)

    entry_word  = random.choice(_ENTRY_WORDS)
    return_word = random.choice(_RETURN_WORDS)

    # ENTRY waypost: in the lobby, active. Say its word in housing -> arrive lobby.
    entry_wp = create_object(Waypost, key="the intake waypost", location=rooms["lobby"])
    entry_wp.db.realm_address = entry_word
    entry_wp.db.owner_char_id = owner.id
    entry_wp.db.owner_name    = owner.db.rp_name or owner.key

    # RETURN waypost: in housing, INACTIVE (held). Activated only when worthy.
    return_wp = create_object(Waypost, key="a dark waypost", location=housing)
    return_wp.db.realm_address = None
    return_wp.db.owner_char_id = owner.id
    return_wp.db.owner_name    = owner.db.rp_name or owner.key

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
