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
    ("restroom",     "The Facility — Sanitation Block",
     "|wA white-tiled wet-room of drains and troughs and holed partitions, bleach laid thin "
     "over the reek of piss and stale spend.|n One wall is a row of waist-height holes worn "
     "smooth at the rim, a kneeling-pad bolted beneath. A low frame in the centre locks a body "
     "under an open seat. A hose coils by the drains. This is where the facility's stock is put "
     "when a hole — any hole — is needed for relief, and where the staff and the other livestock "
     "come to use it."),
    ("showroom",     "The Facility — The Showroom",
     "|wA bright, carpeted sales floor with a raised, lit display block at its centre and a wall "
     "of one-way glass along one side.|n It is the only tasteful room in the place — soft "
     "lighting, a podium, a brass rail — staged like a high-end dealership, because that is what "
     "it is. Stock is brought up here to be posed, appraised, and sold: priced by yield and get "
     "and grade, bid on by buyers you cannot see behind the glass, and walked back down owned by "
     "someone new. A discreet brass plate on the block reads LOT IN VIEWING."),
]

# Adjacency (non-linear): which rooms connect to which.
_EXITS = {
    "lobby":        ["floor"],
    "floor":        ["lobby", "pens", "conditioning", "dairy", "restroom", "showroom"],
    "pens":         ["floor", "pigsty"],
    "conditioning": ["floor", "dairy"],
    "dairy":        ["floor", "pigsty"],
    "pigsty":       ["pens", "dairy", "restroom"],
    "restroom":     ["floor", "pigsty"],
    "showroom":     ["floor"],
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
            study=["Under the flat light there are no shadows to stand in and nothing looks "
                   "well — skin goes waxy, edges go clinical. It is lighting chosen to make a "
                   "body easy to inspect, not easy to like.",
                   "It never flickers off, only dips and steadies, the way a thing watching you "
                   "blinks and goes on watching."],
            ambient=["The sodium hum dips, wavers, steadies. The light never quite goes out.",
                     "Under the flat light, everything — including you — looks like inventory."]),
        "chairs": _z(
            "A row of moulded waiting chairs is bolted to the floor in front of the screen, "
            "wipe-clean and the colour of nothing, facing forward whether you want to or not.",
            summary="bolted-down waiting chairs",
            study=[
                "The front edge of every seat is worn shiny and smooth — not the wear of "
                "sitting back, but of being perched forward, knees apart, presented. Everyone "
                "who waited here was made to wait the same way.",
                "They're bolted down and angled at the screen so there's nowhere to face but "
                "the loop. You can close your eyes. You will open them again.",
                "There's a gap beneath the nearest seat where the moulding doesn't quite meet "
                "the frame, and something is tucked up into it, out of a cleaner's reach — a "
                "small dull glint you only catch from this angle. You could reach under and feel "
                "for it.",
            ],
            handle={"chairs":
                "|xYou crouch by the nearest bolted chair and work your fingers up into the "
                "seam under the seat, where the moulding doesn't quite meet the frame — and they "
                "close on something small, cold, and metal, pushed up where no cleaner ever "
                "reaches. It comes free into your palm, warm almost at once from your skin: a "
                "heavy little piercing, a captive ring, its bead worked with the facility's "
                "mark. Left here. Waiting. As if for a hand exactly your size.|n"},
            ambient=["A chair's front edge catches the light, worn to a shine by everyone made "
                     "to perch there before you."]),
        "brochures": _z(
            "A rack of glossy brochures stands by the chairs — warm photographs, soft headlines, "
            "smiling testimonials for the Residency.",
            summary="a rack of glossy brochures",
            study=[
                "Every photograph is shot from behind, or with the face turned, or cropped at "
                "the collarbone. You flip through a dozen happy residents and never once see a "
                "pair of eyes.",
                "The testimonials are signed by initial and a number of years. \"Never been more "
                "productive! — M., Resident, Year 3.\" \"I don't know who I was before. — "
                "Resident, Year 6.\" The second one is printed like it's a good thing.",
                "A pull-quote in friendly type promises *a structured daily rhythm residents "
                "come to love.* It does not say what the rhythm is, or that loving it is the "
                "point, or that it isn't optional.",
            ],
            handle={"brochures": "|xYou take a brochure off the rack. It's heavier and glossier "
                    "than it has any right to be, warm from the lamps, and it falls open to a "
                    "dog-eared page someone before you kept returning to.|n"},
            ambient=["A brochure slides from the rack and fans open on the floor to a page of "
                     "faceless, smiling residents."]),
        "poster": _z(
            "A large framed poster hangs above the rack: a soft-focus body, arms open, under "
            "three friendly words — |wYOUR BODY IS A GIFT|n.",
            summary="a framed wellness poster",
            study=[
                "Beneath the slogan, in type sized to be seen but not read from the chairs, runs "
                "a strip of clause text: *...the Gift, once given, is received in full and held "
                "in trust by the Residency for the productive lifetime of the donor...*",
                "The model's arms are open in welcome, but her wrists are turned out and held "
                "a little too wide — the pose of someone presenting, or restrained, framed to "
                "read as the first thing until you've sat with it a while.",
            ],
            ambient=["The poster's soft-lit body seems, under the flat hum, to be offering "
                     "something it has already been told it doesn't get to keep."]),
        "board": _z(
            "An illuminated |wNOW WELCOMING|n board hangs over the counter, a single number "
            "glowing in its window above a worn ticket dispenser.",
            summary="a NOW WELCOMING number board",
            study=[
                "The number in the window is enormous — five figures — and it ticks up while "
                "you watch, steadily, far faster than one room of waiting chairs could ever "
                "feed it. They are welcoming a great many people. None of them are leaving by "
                "this door.",
                "The ticket you'd pull doesn't have a number on it. It has a blank, and a line, "
                "and the word OUTPUT, the same as the form on the counter. You are not in a "
                "queue. You are an entry.",
            ],
            ambient=["The NOW WELCOMING number ticks up another digit. The chairs around you "
                     "don't empty to match it."]),
        "cooler": _z(
            "A water cooler bubbles in the corner by the chairs, paper cones stacked beside it, "
            "the only homely thing in the room.",
            summary="a bubbling water cooler",
            study=[
                "The bottle glugs and sends up a string of bubbles every so often — a warm, "
                "ordinary sound, put here on purpose, doing the work of making this feel like a "
                "place where ordinary things happen to you.",
                "The water is faintly sweet, and faintly warm, and you drink it because your "
                "mouth is dry from the hum and the waiting. Afterward the loop on the screen is "
                "a little easier to watch. You decide that's a coincidence.",
            ],
            handle={"cooler": "|xYou fill a paper cone at the cooler and drink. It's warm, and "
                    "faintly sweet, and it goes down easy — easier than water should — and a "
                    "soft, pleasant heaviness settles behind your eyes a moment later.|n"},
            ambient=["The cooler glugs and sends up a friendly string of bubbles. It is the only "
                     "kind sound in the room, and it was put here on purpose."]),
    },
    "floor": {
        "line": _z(
            "Padded breeding stations run the length of the hall on a slow conveyor, most of "
            "them empty, each fitted with restraints, a descending milking rig, and a "
            "swing-mounted intake arm. The line advances on a timer and does not stop.",
            summary="the breeding line of padded stations",
            study=[
                "Each station is cut away and angled to fold an occupant into presentation and "
                "hold her there, hands-free, at exactly working height. There is one with your "
                "number freshly chalked on the headboard. They were expecting you. They are "
                "always expecting you.",
                "The conveyor ticks forward a notch every so often, carrying whatever's strapped "
                "in from milking to breeding to dosing without ever reaching an end. This is "
                "orientation: not a tour, a turn on the line. You learn what you are by being "
                "used as it.",
                "There's no instruction posted, no schedule you can read — you're meant to learn "
                "the rhythm the way the animals did, by being put through it until it's the only "
                "thing your body remembers how to do.",
            ],
            handle={"line": "|xYou touch the nearest station's padding — wipe-clean vinyl, "
                            "still warm and faintly damp from the last thing held in it, the "
                            "restraints hanging open and unhurried, waiting to be filled.|n"},
            ambient=["Somewhere down the line a rig descends, works, and rises again, wet.",
                     "A collection bottle fills a measure higher and the gauge logs it."]),
        "rigs": _z(
            "Articulated arms of suction cups and tubing hang ready over each station, "
            "graduated bottles racked beneath, gauges logging yield.",
            summary="milking rigs and collection bottles",
            study=[
                "The bottles are labelled by number, not name. One rack is yours, or will be — "
                "an empty shelf with your figure stencilled on it, waiting to start filling.",
                "The cups are sized in a range, smallest to obscene, and they are not sized for "
                "comfort. They are sized for what you'll become, further down the schedule.",
            ],
            handle={"rigs": "|xYou lift one of the suction cups from its cradle — heavier "
                           "than it looks, the rim soft and cold, the vacuum hose behind it "
                           "twitching faintly with stored suck, eager for a nipple to seal over.|n"}),
        "cart": _z(
            "A wheeled supply cart stands within reach of the line — labelled vials in foam, "
            "needle guns, gauging rings, a brand and a tattoo kit, everything dosing and "
            "marking might want, laid out in tidy rows.",
            summary="a wheeled dosing-and-marking cart",
            study=[
                "The vials are labelled in clinical shorthand and there are more than you want "
                "to count — SWELL, YIELD, RAW-NERVE, CAPACITY, BROOD, COMPLIANCE, BIMBO, "
                "DEPENDENCE, ESTRUS, LACTATION, CUMSLUT, and one just marked SOLVENT. Most foam "
                "slots are empty, used; a great many residents have been dosed off this one cart.",
                "Each compound does a different, permanent thing — swells the flesh, opens the "
                "glands, raws the nerves, stretches what you can hold, hurries the womb, quiets "
                "the part that argues, softens the speech, builds the craving, locks the heat or "
                "the milk on for good. The handler picks one or two by whatever the schedule "
                "wants. You don't get told which, only that it's working.",
                "There's a row of prepped auto-injectors in a tray, primed and capped, the kind "
                "you press to the thigh and thumb. One has rolled loose to the cart's edge, as if "
                "set apart. As if meant. You could pick it up.",
                "The back of the cart is the marking kit: a cold-iron brand, a tattoo gun loaded "
                "for a womb-stamp, surgical milk-port valves, steel gauging rings on a sizing "
                "rod, a fertility implant in a sterile sleeve. None of it is for today. They have "
                "your file already; today is only the start of filling it.",
            ],
            handle={"cart": "|xYour hand goes to the loose auto-injector at the cart's edge "
                    "before you've quite decided to — and it fits your palm like it was molded "
                    "for it, capped, prepped, the little window showing a measure of something "
                    "warm and golden already drawn. Your thumb finds the trigger.|n"},
            ambient=["A used injector is tidied into the sharps bin. The tray is restocked "
                     "without anyone seeming to do it."]),
        "gauges": _z(
            "A bank of yield gauges and a lit processing board dominate the near wall, every "
            "station's output charted live, every resident a climbing line by number.",
            summary="yield gauges and the processing board",
            study=[
                "Your number is already on the board — a flat line at zero with a date beside it, "
                "the day you signed, waiting to start its climb. Being good, here, will be a "
                "slope. Being bad will be a flatter one, and a longer stay.",
                "The board doesn't track how you feel or what you want. It tracks millilitres and "
                "counts and grades. It is the only opinion of you the facility keeps, and it is "
                "the only one that will, eventually, be yours too.",
            ],
            ambient=["A figure on the processing board ticks upward, and a soft chime approves it.",
                     "A gauge needle swings as some station down the line gives up its measure."]),
        "drain": _z(
            "A wide grated drain sits in the centre of the sloped floor, the tiles around it "
            "worn pale, a hose coiled on a bracket nearby.",
            summary="a grated floor drain",
            study=[
                "The whole floor is pitched gently toward the drain. Whatever the line produces "
                "or spills runs to this one point and is gone, and the tiles are scrubbed pale "
                "around it from how often that's needed.",
                "It is a very practical detail, and that's the horror of it: this is a place "
                "built to be hosed down between uses, and you are one of the things between uses.",
            ],
            ambient=["Water trickles to the drain and is gone. The floor is sluiced clean on a "
                     "schedule, ready for the next mess."]),
    },
    "pens": {
        "stalls": _z(
            "Heavy stalls line the far wall — a dull-eyed breeding bull in one, a rank tusked "
            "boar in a low pen, a big-barrelled stallion stamping in the last — proven stock "
            "kept fed, kept ready, and walked out when the stockman picks one.",
            summary="stalls of breeding stock",
            study=[
                "The |gbull|n is a wall of slow muscle, sheath heavy, bred for depth — the "
                "stockman saves him for cunts trained loose enough to take him without tearing.",
                "The |gboar|n is small-eyed and tireless, blunt and rooting; the placard wired to "
                "his pen reads, in the stockman's hand, FOR THE BACK DOOR. He ruins an ass for good.",
                "The |gstallion|n stamps and screams in the end stall, flared like a fist, the one "
                "the stock is worked up to over a long, careful while. His stall has the most locks.",
                "Each stall gates onto a walkway that gates onto the breeding stocks in the middle. "
                "The geometry only runs one way, toward the frame, and the frame faces the wall.",
            ],
            handle={"stalls": "|xYou reach toward a stall and the animal inside leans into it — "
                             "huge and warm and rank, snuffling at you with flat, patient "
                             "interest, entirely uninterested in you as anything but the next "
                             "thing it'll be walked over to and put inside.|n"},
            ambient=["The bull stamps and snorts, and the sound carries through the floor.",
                     "The boar's musk thickens whenever the heat in the room shifts.",
                     "The stallion screams once, impatient, and is told to wait his turn."]),
        "kennel": _z(
            "A long kennel run takes up the near wall, a dozen heavy rangy hounds pacing the "
            "bars, noses working the air, loosed in ones and twos — or all at once — on the "
            "stockman's word.",
            summary="a kennel run of hounds",
            study=[
                "They scent heat through the bars and start to whine and jostle the moment a "
                "fresh hole is brought in. Patient and not patient at all.",
                "Hounds knot — they tie off inside and can't pull free until it goes down, so "
                "whatever they're loosed on learns to hold a load whether it wants to or not. "
                "The stockman uses them to train a hole to stay open.",
                "When the whole run goes off at once it's a churning press of them, taking turns "
                "and not waiting their turn, and there is no counting them from underneath.",
            ],
            handle={"kennel": "|xYou put your fingers near the bars and a dozen wet noses shove "
                             "at them at once, snuffling, whining, the whole run going taut with "
                             "interest — they can smell exactly what you're here to be.|n"},
            ambient=["A hound presses to the bars, snuffling, and is told to wait.",
                     "The kennel-run ripples with low whines whenever the latch-bar is touched."]),
        "stocks": _z(
            "A heavy timber breeding frame stands bolted in the centre of the floor, cut low and "
            "spread, built to lock a body bent and open at exactly the height the stock mounts — "
            "facing the wall, so there's nothing to look at but it while you're bred.",
            summary="the central breeding stocks",
            study=[
                "The frame folds you down onto forearms and knees, hips hauled up and thighs "
                "winched apart, holes presented at mounting height and your hands no use to you. "
                "It is the only thing in the room built for a person, and it is built to make her "
                "an animal's convenience.",
                "The timber is worn smooth and dark at the hip-rest and the throat-rail, polished "
                "by everyone bent here before you. The stains around the base were never fully "
                "scrubbed out. No one tried very hard.",
            ],
            handle={"stocks": "|xYou run a hand over the breeding frame — smooth worn timber, "
                             "still damp, the restraints hanging open and unhurried at ankle, "
                             "wrist, and throat, every angle of it built to hold you presented "
                             "and use-able and facing away.|n"}),
        "wallow": _z(
            "One corner of the floor is a churned pit of mud and slop, kept warm and wet, where "
            "stock is rutted face-down and left to be marked and filthy between mounts.",
            summary="a churned mud wallow",
            study=[
                "The muck is mud and water and a great deal that isn't — animal musk, spilled "
                "spend, piss the stock and the hose put there. It is kept warm on purpose. It is "
                "easier to stop minding than you'd think, and minding less is the point.",
                "There's no clean part of it and nowhere near it that stays clean. You are rutted "
                "into it face-first and you come up wearing it, and the wearing is half the mark.",
            ],
            handle={"wallow": "|xYou sink a hand into the warm reeking slop — it gives, and "
                             "clings, and doesn't let go quickly, and the stink of it is on you "
                             "now and won't come off until they decide to hose you.|n"},
            ambient=["Something settles wetly in the wallow. The reek is kept warm on purpose.",
                     "The hose drips against the wall, for marking and for the rare mercy of rinse."]),
        "scentpost": _z(
            "A scarred wooden post stands by the stocks at animal height, dark and greasy, where "
            "the stock rub and mark — and where new holes are held to be scent-marked before "
            "they're bred.",
            summary="a greasy scent-marking post",
            study=[
                "The wood is black and slick with years of rubbed-in musk, glands, and spend. "
                "The animals work themselves against it to leave their claim — and a fresh hole "
                "is held to it first, rubbed down, so the stock reads her as theirs by smell.",
                "Once you're marked at the post the animals breed you without hesitation. That's "
                "what it's for: to make you smell like something that gets bred, so you do.",
            ],
            handle={"scentpost": "|xYou touch the post and your hand comes away greasy and "
                             "reeking — musk and old spend ground into the grain, the smell of it "
                             "instantly on your skin, marking you the way it marks everything "
                             "brought near it.|n"},
            ambient=["An animal rubs the scent-post and snorts, refreshing its claim.",
                     "The post reeks across the whole floor — musk, and under it, the stock."]),
    },
    "conditioning": {
        "spiral": _z(
            "Set in the ceiling above the cradle, angled so it's the only thing to look at, a "
            "slow disc turns — a soft spiral of light winding inward, never quite arriving, "
            "pulsing in time with the voice when the voice comes.",
            summary="a slow inward-winding spiral of light",
            study=[
                "The spiral never reaches its centre; it just keeps drawing the eye inward, and "
                "inward, and the longer you watch the harder it is to remember you were ever "
                "not watching. It is the simplest tool in the room and the hardest to refuse.",
                "It pulses, you realise, on the cadence of breathing — slightly slower than "
                "yours, so that without deciding to you find your breath drifting down to match "
                "it. That's the whole trick: it breathes you, and a thing being breathed is "
                "halfway under already.",
            ],
            handle={"spiral": "|xYou look up at the spiral and can't, quite, look away — it winds "
                             "in and in and your eyes track it without permission, your breath "
                             "already slowing to its pulse, a soft heaviness pooling behind your "
                             "face before you've decided anything at all.|n"},
            ambient=["The spiral turns, winding inward, patient and bottomless.",
                     "The light pulses slow, and your breath, you notice, has matched it again."]),
        "grille": _z(
            "A speaker grille is set in the black wall at head height by the cradle — small, "
            "matte, the single source of the voice, close enough that whatever it says is said "
            "directly into you.",
            summary="a speaker grille, the source of the voice",
            study=[
                "The voice that comes from it is never loud. It doesn't need to be. It's placed "
                "exactly where a mouth would be if someone were leaning over your shoulder to "
                "murmur, and that's the effect: not broadcast, but confided, just to you.",
                "Between sessions the grille is silent, but it's the kind of silence that's "
                "clearly only a pause. You find yourself waiting for it. By the third visit, "
                "waiting for the voice is its own small surrender.",
            ],
            ambient=["The grille clicks, considers, and stays silent — for now.",
                     "From the grille, almost too soft to catch: your designation, once, like a test."]),
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
    "restroom": {
        "wall": _z(
            "One wall is a partition of waist-height holes, a dozen of them, rims worn smooth and "
            "pale, a padded kneeling-rail bolted along the base. Cocks come through from the far "
            "side — staff, stock, whoever's queued — and there is no telling whose.",
            summary="a glory-hole partition",
            study=[
                "You can't see the other side, and that's the design: the hole on the wall has "
                "no face, no name, no one to appeal to. Just the next cock through the next hole, "
                "and you on the rail, and your mouth at working height.",
                "Above each hole a small worn placard: a number, and a tally scratched beneath "
                "it. The numbers aren't holes. They're residents. The tallies are uses.",
                "The rim of each hole is stained and slick. They are used constantly. The pad "
                "under them is shaped to the dents of a great many knees.",
            ],
            handle={"wall": "|xYou kneel to the rail and a cock pushes through the hole in front "
                            "of you, already hard, already leaking, no face behind it — just "
                            "there, expectant, and the queue shifting on the far side waiting "
                            "for you to get to work.|n"},
            ambient=["A cock pushes through one of the holes, waits a beat, and withdraws — used, "
                     "or impatient.",
                     "Knuckles rap the far side of the partition. The queue is not patient."]),
        "stall": _z(
            "In the centre a low steel frame locks a body face-up beneath an open seat — a "
            "toilet built around a person, mouth and holes positioned under the gap to catch "
            "whatever the seat is used for.",
            summary="a meat-toilet frame under an open seat",
            study=[
                "The seat above is ordinary, institutional, lidless. What's underneath it isn't. "
                "The frame holds you fixed mouth-up beneath the gap, and the facility's staff and "
                "stock sit and use you as exactly what the frame makes you: the toilet.",
                "There's a placard riveted to the frame: THIS UNIT IS IN SERVICE. Below it, a "
                "use-tally, filled in by hand. The unit is you. The service is everything that "
                "comes through the seat.",
            ],
            handle={"stall": "|xYou touch the meat-toilet frame — cold steel, contoured to fold a "
                            "body face-up beneath the seat, throat and holes lined up under the "
                            "gap, restraints to keep the unit in service and still while it's "
                            "used.|n"}),
        "urinal": _z(
            "A long shallow trough is set into the wall at hip height, tiled and stained, a "
            "drain at one end — and a fixture at the other shaped to hold a face up to catch the "
            "stream, so the trough need never go to waste.",
            summary="a trough urinal with a face-fixture",
            study=[
                "It's a urinal, plainly. The only unusual fitting is the padded clamp at the "
                "head of it, angled to hold a mouth open under the lip where the stream runs — "
                "so the stock fixed there is watered by everyone who uses the trough.",
                "The tile is yellowed at the waterline and scrubbed pale above it. It is used "
                "often and rinsed rarely. You are not, the placard notes, to be rinsed until the "
                "shift ends.",
            ],
            handle={"urinal": "|xYou run a hand along the cold trough — slick, stained, reeking "
                            "of ammonia under the bleach, the head-clamp at the end hanging open "
                            "and waiting to hold a face up under the run.|n"},
            ambient=["The trough drips and trickles toward the drain. The reek of it is kept, "
                     "not cleaned.",
                     "Somewhere a cistern refills with a long hiss, and is, eventually, used."]),
        "drain": _z(
            "The whole floor pitches to a central grated drain, the tile worn pale around it, a "
            "hose coiled alongside for sluicing down the unit and the room between shifts.",
            summary="a central floor drain and sluice hose",
            study=[
                "Everything in here runs to this one point — piss, spend, rinse, all of it — and "
                "is gone. The room is built to be hosed out, and so, between uses, are you.",
                "The hose is the only thing in the block that makes anything cleaner, and it is "
                "used on the room far more often than on the unit fixed in it.",
            ],
            ambient=["Water trickles to the drain and is gone. The block is built to be sluiced.",
                     "The hose drips against the tile, coiled and waiting for the end of shift."]),
    },
    "showroom": {
        "block": _z(
            "A raised, lit display block stands at the centre of the carpet, a brass rail around "
            "it and a turntable set into the floor, angled and spotlit so whatever's posed on it "
            "is shown from every side at once.",
            summary="a lit display block with a turntable",
            study=[
                "The block rotates slowly when occupied, so the buyers behind the glass get every "
                "angle without having to move. Spread, lit, turned — a body on it isn't looked at "
                "so much as *inspected*, the way you'd walk around a car.",
                "A brass plate is bolted to the rail: LOT IN VIEWING, with a slot beneath for a "
                "card. The card has your spec on it. The card has your price on it.",
            ],
            handle={"block": "|xYou step up onto the block and the turntable takes you, slow and "
                            "smooth, into the spotlight — lit, raised, turned for the glass, every "
                            "part of you offered to eyes you can't see, posed like merchandise "
                            "because that is precisely what you are up here.|n"}),
        "card": _z(
            "A printed spec card sits in the rail's slot and on the wall display — the lot's "
            "particulars in clean sans-serif: grade, yield, get dropped, capabilities, and, in "
            "bold at the bottom, an asking price.",
            summary="the lot's spec card and price",
            study=[
                "It reads like a livestock listing because it is one: your grade, your litres, "
                "your litters, what your holes can take, all rendered as selling points. There's "
                "no line for anything you'd have called yourself. None of that priced.",
                "The asking price updates as you're worked — every litre milked, every litter "
                "dropped, every hole trained looser nudges the figure. You can watch yourself "
                "appreciate as an asset in real time. Some find that the worst part.",
            ],
            handle={"card": "|xYou pick the spec card out of the slot and read yourself the way a "
                            "buyer would — grade, yield, get, gape, and a price in bold — a whole "
                            "person rendered as a number a stranger might find reasonable.|n"}),
        "glass": _z(
            "One long wall is a sheet of one-way glass, mirror on this side, the buyers' gallery "
            "dim behind it — shapes, the red wink of a bid-button, the occasional silhouette "
            "leaning in to look closer.",
            summary="a wall of one-way buyers' glass",
            study=[
                "You can't see them; they can see all of you. The asymmetry is the product. You "
                "perform for a darkness that's appraising you and never has to show you a face or "
                "a reason.",
                "Now and then a light blinks behind the glass — a bid, raised. The number on your "
                "card ticks. Somewhere in the dark, someone has decided what you're worth to them, "
                "and it is both more and less than you'd have guessed.",
            ],
            ambient=["A bid-light winks red behind the glass, and the price on the card ticks up.",
                     "A silhouette leans close to the glass, studies the lot, and sits back."]),
        "lots": _z(
            "Other stock waits its turn along the rail — penned, tagged, graded — a row of the "
            "facility's livestock kept here for comparison and sale, each with its own card.",
            summary="other lots awaiting sale",
            study=[
                "They're posed like you, tagged like you, priced like you — and you find yourself "
                "reading their cards against your own, sizing up the competition, before you catch "
                "what you're doing and what it means that you're doing it.",
                "One's heavily pregnant and going for a premium. One's graded higher than you and "
                "knows it. The ranking is the point: stock that competes to sell is stock that's "
                "stopped trying to do anything but.",
            ],
            ambient=["A higher-graded lot is led past to the block, and the gallery stirs."]),
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
        ("the screen", "A wall-mounted screen above the waiting chairs, playing a soft pastel "
         "wellness loop on repeat — warm voices, calming colours, a jingle that gets into the "
         "back of your head and stays there. You can't quite stop watching it, and you can't "
         "quite say why."),
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
        ("Bethany", "attendant",
         "A bright, pretty receptionist behind the counter in a fitted blouse and a lanyard, "
         "her smile genuinely warm right up until you notice it doesn't reach the muscle around "
         "her eyes. She is relentlessly, professionally lovely — and when she shifts her weight "
         "the fitted skirt does nothing to hide what she's packing beneath it, heavy and "
         "unhurried, a detail she lets you catch and clearly enjoys you catching. She runs "
         "intake. She takes her time with the ones who make her work for it, and she remembers "
         "every single one — some of the stock further in carry her eyes."),
        ("a gravid resident", "resident",
         "A heavily pregnant woman sits two chairs down, hands folded on the swell of her belly, "
         "serene in a way that has nothing behind it. A laminated tag is clipped to her wrist "
         "where a name should be. She does not look at you. She is, the brochures would say, "
         "thriving — and she is what the chair you're in is for."),
        ("a collared resident", "resident",
         "Another applicant waits near the door, placid and pleasant and entirely empty-eyed, a "
         "faint pale band worn into the skin of her throat where a collar sits often enough to "
         "leave a line. She answers the clerk's glances before they're finished, already nodding. "
         "She is further along than you. She is also, unmistakably, your future, sitting with you "
         "in the same grey light."),
        ("a fresh applicant", "resident",
         "A new arrival perches on the front edge of her chair exactly the way the wear suggests, "
         "knees apart without seeming to know why, watching the screen with the soft slack face of "
         "someone the loop has already started on. She still has her name. She doesn't know that's "
         "a thing she has."),
    ],
    "floor": [
        ("the attendant", "attendant", "An attendant in a clean grey coverall working the "
         "gauges along the line with unbothered efficiency."),
        ("the handler", "attendant", "A broad handler in a rubber apron who works the bodies — "
         "strapping, adjusting, lining up whose turn is next. He looks at you the way the cart "
         "looks at you: as the next item to be set up, run, logged, and sluiced down. Ask him "
         "what you like. He answers in procedure."),
        ("worked stock", "resident", "Further down the line a resident is folded into a station, "
         "hands-free and presented, the cups working at her chest and the intake arm seated deep, "
         "her eyes half-lidded and gone somewhere else while the gauge beside her climbs. She "
         "doesn't look up. There's nothing in the look to give. That is what working looks like, "
         "and the chalked station with your number is three down from hers."),
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
    "restroom": [
        ("the custodian", "attendant", "A bored custodian in rubber gloves and an apron, "
         "clipboard in hand, who keeps the block stocked and the unit in service and ticks the "
         "use-tally without looking at it. To them you are plumbing — a fixture that needs "
         "checking, logging, and hosing down at end of shift, and nothing that needs a name."),
        ("the queue", "resident", "Beyond the partition, a shifting line of the facility's "
         "staff and stock waits its turn at the holes — shapes through frosted glass, the "
         "occasional rap of impatient knuckles, the shuffle of someone stepping up. You never "
         "see a face. That is the entire point of the wall."),
    ],
    "showroom": [
        ("the auctioneer", "attendant", "A smooth, well-dressed auctioneer with a headset and a "
         "laser pointer, working the block like a luxury salesman — because to them that's the "
         "job. They walk the buyers through your particulars in a warm, practiced patter, "
         "pointing out your features, talking your price up, never once addressing you, because "
         "the lot doesn't need to be talked to, only talked about."),
        ("the gallery", "resident", "Behind the one-way glass, the buyers: shapes in the dim, "
         "the occasional lean-in, the red wink of a bid. You never see a face — only the prices "
         "they put on you, climbing in the dark."),
        ("a premium lot", "resident", "Another of the facility's stock waits along the rail, "
         "posed and tagged and heavily pregnant, going for a premium and placid about it — what "
         "a lot looks like once it's stopped being anything but a lot."),
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
        "stocks": ("restrain", 1, "the breeding stocks",
                   "The frame folds you bent and spread at exactly mounting height and locks. You wait, presented, to be bred by whatever the stockman picks."),
        "wallow": ("seat", 4, "the wallow", "face-down in the warm muck"),
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
    "restroom": {
        "stall": ("restrain", 1, "the meat-toilet frame",
                  "The frame folds you face-up beneath the seat and locks. You are in service now; you hold still and you catch what comes."),
        "wall":  ("seat", 1, "the glory-hole rail", "kneeling at the holed wall, mouth at working height"),
        "urinal":("seat", 1, "the urinal fixture", "clamped face-up under the trough's run"),
    },
    "showroom": {
        "block": ("restrain", 1, "the display block",
                  "The block's clamps take your wrists and ankles and the turntable starts to turn. You are posed, lit, and on offer; you hold the pose because the pose is the product."),
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
    "restroom": [
        "|xA cock pushes through one of the wall-holes, waits, and withdraws. The queue shuffles forward.|n",
        "|xKnuckles rap the partition. Someone's been waiting. Someone's always waiting.|n",
        "|xThe trough trickles toward the drain. The reek of ammonia is kept, not cleaned.|n",
        "|xThe custodian ticks the use-tally without looking, and moves on.|n",
    ],
    "showroom": [
        "|xThe display block turns its slow half-revolution, and the spotlight follows.|n",
        "|xA bid-light winks red behind the glass; somewhere a number that is you goes up.|n",
        "|xThe auctioneer's patter drifts over — warm, practiced, talking up the lot to the dark.|n",
        "|xA buyer leans close to the one-way glass, studies the lot a long moment, and sits back.|n",
    ],
}

# The custodian runs the Sanitation Block. To them she is plumbing — a fixture in
# service, logged and hosed, never named.
_CUSTODIAN_TRIGGERS = {
    "restroom": ("\"Sanitation,\" the custodian says, not looking up from the clipboard. "
        "\"Wall's for relief, frame's the toilet, trough's the urinal. Whichever's needed, "
        "that's where you go. You're not here to be bred. You're here to be *used up* and "
        "rinsed.\"", "say"),
    "wall": ("\"Glory wall. You kneel, they come through, you service whatever does. No faces, "
        "no names — theirs or yours.\" A shrug. \"Staff, stock, doesn't matter. A hole on the "
        "rail doesn't get to be choosy. That's rather the comfort of it, most find.\"", "emote"),
    "toilet": ("\"The frame puts you face-up under the seat and you stay there, in service, "
        "catching what the seat's for.\" The custodian ticks a box. \"Cum, piss, the lot. A "
        "good unit doesn't spill and doesn't complain. You'll learn to swallow on schedule.\"",
        "say"),
    "urinal": ("\"Trough fixture. We clamp your face up under the run and you're watered by "
        "everyone who uses it.\" Flat. \"Hydration's a perk, really. You won't be let up to "
        "drink any other way, so. Open up when you hear the cistern.\"", "emote"),
    "piss": ("\"You'll be pissed in and pissed on, yes. Held full, too — we don't let the unit "
        "relieve itself on shift, so you ache and you hold and you learn your own bladder isn't "
        "yours either.\" A thin smile. \"Watersports, the brochure calls it. We call it Tuesday.\"",
        "emote"),
    "clean": ("\"You get hosed at end of shift. Not before. Walking around filthy and reeking "
        "between uses is the point — it tells the next user exactly what you are and that you're "
        "in service.\"", "say"),
    "leaving": ("\"Out? You're a fixture. Fixtures don't leave, they get *decommissioned*, and "
        "you're nowhere near worn out enough for that.\" The custodian caps a pen. \"Back under "
        "the seat. The queue's building.\"", "emote"),
    "help": ("\"Ask about the wall, the toilet, the urinal, the pissing, or getting clean. Or "
        "save it — units that talk get the frame, and the frame keeps your mouth otherwise "
        "occupied.\"", "say"),
}


# Bethany's conversation tree — real NPC keyword triggers (ask Bethany about X).
# Each value: (response, type). Bethany is set to a scripted tier so `ask` works.
# She never says no; she euphemises, deflects, and slides the pen closer.
_BETHANY_TRIGGERS = {
    "program": ("Oh, it's *wonderful*. The Residency is a wellness-and-productivity "
        "cooperative — structured days, full board, a real sense of purpose. Residents "
        "tell me they've never felt so useful. You're going to fit right in, I can "
        "always tell.", "say"),
    "residency": ("A cooperative! We house you, we feed you, we give you a rhythm to your "
        "days — and in return you contribute to the collective output. Everyone pulls their "
        "weight. Some of us just have more to give, and we *celebrate* that here.", "say"),
    "family": ("The family-building initiative! It's one of our proudest programs. Perfectly "
        "natural, perfectly supported. We match residents to the initiative's needs and the "
        "rest just... happens. You'd be amazed how quickly it stops feeling like a decision.",
        "say"),
    "breeding": ("We call it the family-building initiative, sweetheart — 'breeding' is such "
        "an *agricultural* word. Though.\" Her smile doesn't move. \"Though I suppose, in the "
        "end. Anyway! It's all in the paperwork.", "say"),
    "milk": ("Lactation-wellness extraction — completely standard, completely comfortable. "
        "Many residents find it the most relaxing part of the rhythm. The body so loves to be "
        "*useful*, don't you find?", "say"),
    "animals": ("Our agricultural partners! The Residency maintains a working livestock program "
        "— it's all very integrated, very natural. You'll meet them during orientation. They're "
        "ever so gentle.\" A small, private smile. \"Mostly.", "say"),
    "conditioning": ("Orientation and adjustment support! Some residents arrive with so much "
        "*noise* in them — opinions, hesitations, names they're awfully attached to. We help "
        "quiet all that down. It's a kindness, really. You'll thank us. They all do.", "say"),
    "cycle": ("A structured daily rhythm — residents *love* the structure. No more deciding, "
        "no more wondering what to do with yourself. You'll be milked and bred and settled on a "
        "lovely dependable schedule. Idle hands, and all that.", "say"),
    "pigsty": ("The wellness-recovery suite! For residents who need a little... grounding. A "
        "place to get back in touch with their basic nature. We don't send *everyone* there.\" "
        "She beams. \"Not at first.", "say"),
    "leaving": ("Oh! You'd discuss release with your placement coordinator — at a review. Once "
        "you've settled in and we've got a sense of your output. I wouldn't worry about the end "
        "before you've even begun, darling. Sign first. Everything else follows.", "say"),
    "out": ("The way out? You came in by the waystone, same as everyone. Going back out is a "
        "*privilege* — earned, reviewed, granted. By me, eventually, if you're very good. The "
        "word that works it isn't one you have yet. Sign, and we'll talk about earning it.",
        "say"),
    "waystone": ("It only answers to words it knows, and it knows the word that brought you down. "
        "The word that lifts you back up — well. That's kept somewhere safe. Somewhere that isn't "
        "you. Don't fret about it. Fretting goes in your file.", "say"),
    "noise": ("That sound? Just the rhythm of the place, sweetheart. Productive sounds. You'll "
        "stop hearing it as anything but ordinary in a day or two — that's how you'll know you're "
        "settling in nicely.", "say"),
    "smell": ("Milk and clean animals and good honest work. Wholesome, isn't it? Your nose adjusts "
        "by the second day. Everything about you adjusts, dear, given a little encouragement.",
        "say"),
    "residents": ("The other applicants? Further along than you, most of them. Content as anything. "
        "That one's expecting — *thriving*. That one's nearly graduated. Look how settled they are. "
        "That's you, in a little while. Isn't that a comfort?", "say"),
    "contract": ("Standard! Everyone signs the same one — it's just a formality, the same forms "
        "we've used for years. Front page is the friendly bit. The rest is the usual housekeeping, "
        "nothing you need trouble yourself reading. Just initial where I've marked.", "say"),
    "clauses": ("Boilerplate, all of it. Housekeeping. The interesting clauses are face-down for "
        "*tidiness*, darling, not secrecy — though I do find people read less when there's less to "
        "read, and read less still when I'm smiling. Shall we?", "say"),
    "hidden": ("Hidden? Nothing's *hidden*. It's all right there, face-down, in writing, the way "
        "everything binding always is. You agreed to be bound the moment you came down the "
        "waystone, really. The signature's just manners.", "say"),
    "you": ("Me? I'm Bethany. I run intake.\" She shifts her weight, and the fitted skirt does "
        "nothing at all, and she lets you look. \"I take *such* good care of the ones who make me "
        "work for it. Some of the stock downstairs have my eyes, you know. I do get attached.",
        "say"),
    "bethany": ("That's me! And it's the last time I'll use your name as much as you'll hear me use "
        "mine, so enjoy it. After you sign, names get a bit... optional. Yours, mostly.", "say"),
    "refuse": ("Bethany's smile does not so much as flicker. \"Of course, of course — no pressure "
        "at all.\" She makes a small, neat note, and underlines it twice. \"I'll just let Processing "
        "know you'll need a little *extra* orientation. They do so enjoy a project. Now. The pen.\"",
        "emote"),
    "no": ("\"No,\" Bethany repeats, warmly, like a word in a foreign language she finds charming. "
        "She slides the pen another inch closer. \"You'll find that one gets easier to stop saying. "
        "We help with that too.\"", "emote"),
    "help": ("You can ask me about the program, the contract, the rhythm of the day, the other "
        "residents — or about leaving, though I'll only smile at that one. Mostly you can ask me "
        "for the pen. That's the question that gets answered.", "say"),
}

# The Processing Floor handler — curt, procedural, no euphemism left in him. Where
# Bethany lied you in, he just tells you what you are now, because it no longer matters
# whether you like it. Wired the same way (scripted NPC + keyword tree).
_HANDLER_TRIGGERS = {
    "orientation": ("Handler doesn't look up from the strap he's checking. \"This is "
        "orientation. No tour. You go on the line, you get run, you learn the rhythm by "
        "doing it. Same as the animals. They learned. You'll learn.\"", "emote"),
    "station": ("\"That one's yours.\" He nods at the chalked headboard. \"Number, not name. "
        "You fold in, it holds you, the line does the rest. You don't work it. It works you.\"",
        "say"),
    "milking": ("\"Cups seal, vacuum pulls, gauge logs it. Don't matter if you're empty — "
        "schedule says milk, you get milked. Body figures it out fast once it knows there's no "
        "off switch.\"", "say"),
    "cart": ("He glances at the cart, then at you, flat. \"Dosing. Lactation primer, heat, "
        "docility, retention. We give it when the schedule calls it. Anything walks up and doses "
        "itself early —\" a shrug \"— saves me the trip. Wouldn't recommend it. Doesn't mean you "
        "won't.\"", "emote"),
    "injector": ("\"Prepped dose. Thigh, thumb the trigger, done. They're not for you to "
        "help yourself to.\" The faintest curl of his mouth. \"Funny how many do anyway. Place "
        "gets into you before the dose does.\"", "emote"),
    "dose": ("\"Whatever's drawn is drawn for a reason. You don't get told the reason. You get "
        "the dose. You'll feel it work and you'll stop minding it works — that's usually what "
        "it's for.\"", "say"),
    "board": ("\"Your number's up there. Flat line, today's date. Goes up from here if you're "
        "productive, stays flat if you fight it. Flat means you're here longer. Math's not "
        "complicated.\"", "say"),
    "drain": ("\"Floor runs to the drain. We hose between uses.\" He says it without weight, "
        "because to him it has none. \"You'll work out what that makes you. Most do, about the "
        "second time they're hosed.\"", "emote"),
    "leaving": ("\"Not my department. I run the line. Doors and words and going home, that's "
        "upstairs, that's grades, that's later. Right now you're stock on my floor and the line's "
        "ready. Let's set you up.\"", "say"),
    "stock": ("\"Her?\" He doesn't look. \"Further along. Stopped asking questions about a "
        "hundred runs back. That's not broken, that's *done*. Settled. You'll get there. "
        "Everyone on my line gets there.\"", "emote"),
    "help": ("\"Ask about the station, the line, the cart, the dose, the board. Or don't. "
        "Line doesn't need you to understand it to run you. Hold still.\"", "say"),
}

# The stockman runs the Breeding Pens — he chooses which stock breeds her, and
# when to just loose the whole pen. Curt, agricultural, no cruelty in it, which is
# its own cruelty: to him she is simply an animal being bred, nothing worth heat.
_STOCKMAN_TRIGGERS = {
    "pens": ("\"This is the breeding floor. Stock on that wall, kennel on this one, stocks in "
        "the middle for you.\" He doesn't look up from the latch he's oiling. \"You go in the "
        "frame, they come to you. Simple operation.\"", "say"),
    "stock": ("\"Bull, boar, stallion, and the kennel of hounds. All proven, all kept ready.\" "
        "A shrug. \"Which one you take's my call, not yours. Depends what your board's owed and "
        "what's rested. Some days it's the lot of them at once. Saves time.\"", "emote"),
    "choice": ("\"I pick. You don't.\" He says it without unkindness, the way you'd tell a gate "
        "it doesn't get a vote. \"I read the board, I read the stalls, I match them up. Could be "
        "the boar today, could be the whole pen. You'll find out when the latch goes.\"", "say"),
    "bull": ("\"Big lad. Slow, heavy, splits you wide and breeds deep. I save him for when your "
        "cunt's trained enough to take him without tearing. You're getting there.\"", "say"),
    "boar": ("\"Boar's for the back door, mostly. Blunt, relentless, roots in and won't quit. "
        "Ruins an ass nicely. You'll gape for good after enough of him. That's the idea.\"", "say"),
    "stallion": ("\"Stallion's the one they're all scared of. Flared like a fist. We work you up "
        "to him over a long while.\" The ghost of something. \"You'll get there too. They all do.\"",
        "say"),
    "hounds": ("\"Kennel runs hot. Loose one and the rest go off. They knot — tie in you and "
        "won't pull, so you learn to hold a load whether you like it or not. Good for training "
        "a hole to stay open.\"", "emote"),
    "all": ("\"Some days I don't pick. Throw every latch, kennel last, and let the pen have you "
        "at once.\" He finally glances at you, flat. \"Faster. You don't enjoy it less for the "
        "company, near as I can tell.\"", "emote"),
    "scent": ("\"They'll mark you. Musk, piss, rub themselves all over you till you stink of the "
        "pen.\" He nods, approving. \"Good. Means they've claimed you. A marked hole gets bred "
        "without fuss. Don't wash it off — not that you'll get the chance.\"", "say"),
    "breeding": ("\"You're bred till the board says the count's met, per species. Then the count "
        "goes up.\" He latches the gate. \"It's not personal. You're a thing that takes and "
        "drops. I keep you taking. That's the whole job.\"", "say"),
    "leaving": ("\"Out's not a pen thing. Pen things get bred.\" He jerks his chin at the stocks. "
        "\"In you go. They're ready even if you're not. Especially if you're not.\"", "emote"),
    "help": ("\"Ask about the stock, the bull, the boar, the stallion, the hounds, who I pick, "
        "or the marking. Or save your breath for the noises you'll be making. Your call.\"", "say"),
}

# The conditioning tech — soft-spoken, clinical, never raises their voice because
# the room does that for them. The actual voice from the grille. Talks about the
# work the way a dental hygienist talks about plaque.
_CONDTECH_TRIGGERS = {
    "conditioning": ("\"Orientation and adjustment,\" the tech says softly, adjusting a dial. "
        "\"We quiet the noise — the arguing, the deciding, the parts that make you unhappy here "
        "— and we leave the parts that make you useful. Most residents describe it as relief. "
        "They're not wrong. It is.\"", "say"),
    "voice": ("\"The voice is mine, mostly. Sometimes recorded, sometimes not — you won't be "
        "able to tell, and it won't matter.\" A faint smile. \"What matters is that you've "
        "started waiting for it. That's the first thing that takes. The wanting to be told.\"",
        "say"),
    "spiral": ("\"Fixation. Gives the front of your mind something to do so the back of it is "
        "open to me. Old technique. Older than the facility.\" The tech doesn't look up. \"You "
        "can resist it for a while. The cradle has nowhere else to look, though. We have time.\"",
        "say"),
    "triggers": ("\"We set handles in you — words that drop you straight back to this state, "
        "anywhere, for anyone who knows them. They don't come out when you leave. That's not "
        "cruelty, it's just how the technique works. The door doesn't close behind the things "
        "we put through it.\"", "emote"),
    "hypnosis": ("\"Call it that if you like. It's only attention, and breathing, and "
        "repetition, and a voice that never argues with you — so that after a while yours stops "
        "arguing too. There's nothing mystical in it. That's the unsettling part, isn't it. How "
        "ordinary it is to be rewritten.\"", "say"),
    "remember": ("\"You won't, mostly. We suggest forgetting, and suggestible minds forget. "
        "You'll keep the calm and lose the seams. The changes will feel like things you always "
        "thought.\" The tech makes a note. \"That's how you'll know they've held.\"", "emote"),
    "resist": ("\"Please do,\" the tech says, mild. \"Resistance is just attention pointed at "
        "me, and attention is all I need. The ones who fight go under deepest, in the end. The "
        "fighting tires out the part that fights. You'll see.\"", "say"),
    "leaving": ("\"Not my department. I only do the inside of your head. The outside — doors, "
        "words, going home — that's upstairs.\" A pause. \"Though by the time you've earned the "
        "outside, you may find the inside no longer wants it. We're thorough.\"", "emote"),
    "help": ("\"Ask about the conditioning, the voice, the spiral, the triggers, the hypnosis, "
        "or remembering. Or just lie back and watch the light. That's the same conversation, "
        "really, from where I'm sitting.\"", "say"),
}

# The dairy hand — refers to stock entirely by number; cares only about yield.
_DAIRYHAND_TRIGGERS = {
    "output": ("\"Everything that comes out of you is ours — milk, get, the data.\" The dairy "
        "hand doesn't look up from the chart. \"You're a producer. We measure producers by what "
        "they produce. That's the whole relationship.\"", "say"),
    "milk": ("\"You'll let down on the rack whether you've got it or not — the cups don't take "
        "no for an answer and neither do I.\" A glance at the gauge. \"Your numbers are coming "
        "up nicely. Post-partum especially. You make a lot when you've just dropped.\"", "emote"),
    "number": ("\"I don't use names down here. You're the figure on your shelf.\" He taps a "
        "labelled bottle. \"This is you. So's that whole row. That's more of you than the "
        "talking kind ever amounted to, if you think about it. I'd rather you didn't think.\"",
        "say"),
    "bottles": ("\"Graded by yield and date. Best stock gets the front rack.\" He shelves one. "
        "\"Being good, here, is just a quantity. You can see your own goodness stacking up. "
        "Some of them find that motivating. We like the motivated ones.\"", "say"),
    "leaving": ("\"Producers don't leave, they get *retired*, and retirement here isn't a "
        "place you'd want to get to. Back on the rack. Your shelf's not full.\"", "emote"),
    "help": ("\"Ask about your output, the milk, your number, the bottles. Or just get on the "
        "rack. The rack's the only conversation that fills a bottle.\"", "say"),
}

# The swineherd — runs the sty, treats what's kept there as exactly what it is.
_SWINEHERD_TRIGGERS = {
    "sty": ("\"Bottom of the place,\" the swineherd grunts, leaning on the hose. \"Where stock "
        "goes when it slips, or when it needs reminding what it is under all the processing. "
        "On your knees in the muck, same as the rest. You'll settle. They all settle.\"", "emote"),
    "filth": ("\"I don't clean you, I move it around. Filthy's the point — tells everyone you're "
        "sty stock.\" He spits. \"Mud, slop, piss, spunk. Not shit, we're not animals.\" A dry "
        "look. \"Well. You are. I'm not.\"", "emote"),
    "trough": ("\"You eat from it bent, hands behind you, face down. First time's the only hard "
        "time.\" He tips a bucket in. \"After that it's just dinner, and you're just the thing "
        "that eats it on its knees.\"", "say"),
    "out": ("\"Out of the sty's a privilege you earn by being good upstairs. Out of the "
        "*facility*?\" He laughs, not unkindly. \"Not a sty conversation. Eat your slop.\"",
        "emote"),
    "help": ("\"Ask about the sty, the filth, or the trough. Or root down and wait — something's "
        "always coming to use you down here, and I've got hosing to do.\"", "say"),
}

# The auctioneer — runs the Showroom. Talks about her, never to her; to them she
# is a lot with features and a price, and the whole patter is selling.
_AUCTIONEER_TRIGGERS = {
    "showroom": ("\"Welcome to viewing,\" the auctioneer says smoothly, not to you — to the "
        "glass. \"This is where the facility realises value. Every lot up here is graded, "
        "specced, and offered. You're not visiting. You're inventory being moved.\"", "say"),
    "price": ("The auctioneer taps your card without looking at you. \"Your figure? Function of "
        "grade, yield, get dropped, and what your holes take. It climbs every time you're "
        "worked. Pleasing, isn't it, watching yourself appreciate. The buyers think so.\"", "emote"),
    "sold": ("\"When the gavel falls you're walked back down owned by someone new — staff, a "
        "private party, the breeding concern, whoever bid highest.\" A smooth smile at the glass. "
        "\"Ownership's just a line in a ledger to us. To you it's everything. Funny, that.\"",
        "say"),
    "buyers": ("\"Behind the glass. You won't see them; they see all of you.\" The auctioneer "
        "gestures grandly at the mirror. \"Discretion is part of the price. A buyer likes to "
        "appraise a lot without the lot appraising back. You understand. Or you don't — doesn't "
        "matter for the sale.\"", "emote"),
    "bethany": ("\"Ah — intake's put a standing bid on you. The futa from the front desk. She "
        "does that, with the ones she takes a shine to.\" A knowing look at the glass. \"She "
        "usually wins. She has... priorities the facility likes to keep happy.\"", "say"),
    "lots": ("\"Comparison stock. We sell in a room full of other lots on purpose — a thing "
        "that can see it's being ranked tries harder to place well. You're already reading their "
        "cards against yours. That's the room working.\"", "emote"),
    "leaving": ("\"Out? You'll leave this room, certainly — on a lead, with a new owner. That's "
        "the only exit the Showroom offers.\" The gavel taps. \"Up on the block. You're next.\"",
        "emote"),
    "help": ("\"Ask about the showroom, your price, being sold, the buyers, the other lots. Or "
        "simply pose and turn and let the figure climb. The lot that sells itself fetches "
        "most.\"", "say"),
}

# Residents are ambient props — set with a flat per-key 'look' flavour.
_RESIDENT_ROLES = {"resident"}


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
        from typeclasses.npc import NPC_TIER_SCRIPTED
        from evennia.utils import create as _c
        _beasts = ("hound", "bull", "boar", "stallion")
        for nkey, role, ndesc in (_ROOM_NPCS.get(key) or []):
            cls = FacilityBeast if role in _beasts else FacilityAttendant
            n = _tag(_c.create_object(cls, key=nkey, location=room))
            n.db.rp_name = nkey
            n.db.physical_desc = ndesc
            if role in _beasts:
                n.db.facility_role = "beast"
                n.db.species = role
            elif role in _RESIDENT_ROLES:
                n.db.facility_role = "resident"   # ambient prop; won't meet your eye
            else:
                n.db.facility_role = "attendant"
            # Askable NPCs — wire their conversation trees (scripted tier).
            _tree = None
            if nkey.lower() == "bethany":
                _tree = _BETHANY_TRIGGERS
            elif nkey.lower() == "the handler":
                _tree = _HANDLER_TRIGGERS
            elif nkey.lower() == "the stockman":
                _tree = _STOCKMAN_TRIGGERS
            elif nkey.lower() == "the conditioning tech":
                _tree = _CONDTECH_TRIGGERS
            elif nkey.lower() == "the custodian":
                _tree = _CUSTODIAN_TRIGGERS
            elif nkey.lower() == "the dairy hand":
                _tree = _DAIRYHAND_TRIGGERS
            elif nkey.lower() == "the swineherd":
                _tree = _SWINEHERD_TRIGGERS
            elif nkey.lower() == "the auctioneer":
                _tree = _AUCTIONEER_TRIGGERS
            if _tree:
                n.db.npc_tier = NPC_TIER_SCRIPTED
                n.db.triggers = {
                    kw: {"response": resp, "type": ttype}
                    for kw, (resp, ttype) in _tree.items()
                }
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

    # The cursed piercing — stashed under the lobby chairs, found by `handle chairs`.
    # On contact it forces consent open and spikes suggestibility (it doesn't ask).
    # Cleaned up by force_clear (tagged facility_piercing) and the OOC floor.
    try:
        from typeclasses.piercing_item import PiercingItem
        curse = create_object(PiercingItem, key="the captive ring")
        _tag(curse)
        curse.location = None   # stashed nowhere until discovered
        curse.db.facility_piercing = True
        curse.db.slot = "center"
        curse.db.default_zone = ""
        curse.db.desc = (
            "A heavy little captive-bead ring of dull dark metal, warm out of all proportion "
            "to the cold seam it was hidden in. The bead is worked with the facility's mark. "
            "It sits in your palm with the settled patience of a thing that was left here on "
            "purpose, for a hand exactly your size — and it is already, faintly, trying to be "
            "closer to you than your palm."
        )
        curse.db.worn_desc = ("|ra heavy captive-bead ring worked with the facility's mark, "
                              "biting snug and warm and permanent-looking|n")
        curse.db.binding_effects = {
            "auto_consent": True,
            "suggestibility": 5,
            "conditioning_on_wear": 8.0,
            "arousal_floor": 40.0,
            "continuous_stimulation": 1.0,
            "install_triggers": [
                {"phrase": "be a good girl and sign", "response": "kneel", "strength": 3},
                {"phrase": "good girls don't argue", "response": "obey", "strength": 2,
                 "mantra": "good girls don't argue"},
            ],
        }
        # Wire the reveal into the chairs zone trigger.
        lobby = rooms["lobby"]
        zs = dict(getattr(lobby.db, "zones", None) or {})
        cz = dict(zs.get("chairs", {}))
        mech = dict(cz.get("mechanics", {}) or {})
        trigs = dict(mech.get("triggers", {}) or {})
        trigs["chairs"] = {
            "type": "reveal_item",
            "item_dbref": curse.dbref,
            "attr": "found_captive_ring",
            "once": True,
            "apply_on_contact": True,
            "msg_room": ("|x{actor} crouches by the bolted chairs, reaches up under the nearest "
                         "seat, and comes away with something small and metal closed in one "
                         "fist — and then goes very still.|n"),
            "msg_empty": ("|xYou feel along under the seats again, but the seam is empty now. "
                          "Whatever was waiting there has already found its hand.|n"),
        }
        mech["triggers"] = trigs
        cz["mechanics"] = mech
        zs["chairs"] = cz
        lobby.db.zones = zs
    except Exception:
        pass

    # The cursed dose — a prepped auto-injector on the Processing Floor cart, found
    # via `handle cart`. Self-dosing early (the place gets into you before the dose
    # does) facilitates the schedule: lactation primer + perpetual heat + docility.
    # Consumed on use; its installed effects are cleared by force_clear/the floor.
    try:
        from evennia import create_object as _co
        floor = rooms["floor"]
        dose = _tag(_co("typeclasses.objects.Object", key="a prepped auto-injector"))
        dose.location = None
        dose.db.desc = ("A capped auto-injector, its little window showing a measure of warm "
                        "golden fluid already drawn. Marked, in the cart's clinical shorthand: "
                        "LACT+ / HEAT / DOCILE.")
        dose.db.binding_effects = {
            "perpetual_heat": True,      # HEAT — real: HeatScript + arousal floor
            "lactation_primer": True,    # LACT+ — real: installs/boosts milk glands
            "suggestibility": 4,         # real: scales conditioning + trigger depth
            "conditioning_on_wear": 6.0, # DOCILE — real: the conditioning meter
            "arousal_floor": 45.0,
            "continuous_stimulation": 1.5,
            "milk_quota": 6,
            "install_triggers": [
                {"phrase": "settle down", "response": "kneel", "strength": 2,
                 "mantra": "good stock settles"},
            ],
        }
        zf = dict(getattr(floor.db, "zones", None) or {})
        cart = dict(zf.get("cart", {}))
        cmech = dict(cart.get("mechanics", {}) or {})
        ctrigs = dict(cmech.get("triggers", {}) or {})
        ctrigs["cart"] = {
            "type": "reveal_item",
            "item_dbref": dose.dbref,
            "attr": "used_floor_dose",
            "once": True,
            "apply_on_contact": True,
            "consume": True,
            "msg_room": ("|x{actor} lifts a prepped injector off the cart, presses it to her own "
                         "thigh, and thumbs the trigger before anyone has to tell her to.|n"),
            "msg_empty": ("|xThe tray's been restocked, but you can't make your hand reach for "
                          "another. One was enough. One is always enough to start.|n"),
        }
        cmech["triggers"] = ctrigs
        cart["mechanics"] = cmech
        zf["cart"] = cart
        floor.db.zones = zf
    except Exception:
        pass

    # Start the Intake lobby driver — Bethany, the screen, the slow squeeze.
    try:
        from typeclasses.intake_script import IntakeScript
        from evennia.utils import create as _c2
        for s in list(rooms["lobby"].scripts.all()):
            if getattr(s, "key", "") == "intake":
                s.stop()
        _c2.create_script(IntakeScript, obj=rooms["lobby"], persistent=True, autostart=True)
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
    # Capture tracked body installs before the list-clear below wipes the record,
    # so we can still delete the real objects (milk glands, womb, breast mod).
    _tracked_items = list(getattr(d, "facility_items", None) or [])
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
              "facility_zone", "facility_furniture", "intake_provocations",
              "intake_suggestibility", "intake_door_opened", "found_captive_ring"):
        try: setattr(d, k, None)
        except Exception: pass
    # -> 0
    for k in ("conditioning", "arousal_floor", "stim_per_tick", "bladder_ml", "arousal",
              "defiance", "compliance_threshold", "compliance_streak", "processing_tier",
              "facility_standing", "drug_dependence", "milk_baseline_ml",
              "suggestibility", "intake_suggestibility", "docility"):
        try: setattr(d, k, 0)
        except Exception: pass
    # drop the installed 'mind' zone entirely (the monitor object is deleted below)
    try:
        z = dict(getattr(d, "zones", None) or {})
        if "mind" in z:
            z.pop("mind", None); d.zones = z
    except Exception: pass
    # -> False / ""
    for k in ("orgasm_denial", "exhibition_active", "self_cmds_locked", "endcycle_blocked",
              "navigation_locked", "anti_clothing_active", "conditioning_permanent",
              "freedom_forfeited", "facility_signed", "facility_active", "perpetual_heat",
              "cum_craving", "lactation_locked", "body_processing_locked", "aura_dimmed",
              "bethany_busy", "bethany_owned"):
        try: setattr(d, k, False)
        except Exception: pass
    for k in ("orgasm_release_word", "required_honorific", "facility_grade", "facility_brand"):
        try: setattr(d, k, "" if "word" in k or "honorific" in k else None)
        except Exception: pass
    # consent restore — prefer the facility backup, fall back to any binding
    # backup (e.g. the cursed piercing's auto_consent), so the floor always frees her.
    backup = getattr(d, "facility_consent_backup", None)
    if backup is None:
        backup = getattr(d, "binding_consent_backup", None)
    if backup is not None:
        try:
            d.consent_flags = dict(backup)
            d.facility_consent_backup = None
            d.binding_consent_backup = None
        except Exception: pass
    # stop scripts on her
    for s in list(owner.scripts.all()):
        if getattr(s, "key", "") in ("realm_cycle", "perpetual_heat", "body_processing",
                                     "facility", "cycle_machine", "bethany_visit") or \
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
    # delete tracked body installs (milk glands, womb, breast mod) — uninstall first
    try:
        from evennia import search_object
        for dbref in _tracked_items:
            res = search_object(dbref, exact=True)
            if res:
                obj = res[0]
                for sub in list(getattr(obj, "contents", []) or []):
                    try: sub.delete()
                    except Exception: pass
                for m in ("uninstall", "remove"):
                    if hasattr(obj, m):
                        try: getattr(obj, m)()
                        except Exception: pass
                try: obj.delete()
                except Exception: pass
    except Exception: pass
    # undo the animal-sleeve state (restore hole descs, strip plug barriers)
    try:
        from world.gang_breeding import clear_animal_sleeve
        clear_animal_sleeve(owner)
    except Exception: pass
    # end any pregnancy + restore the belly desc
    try:
        from world.pregnancy import clear as _preg_clear
        _preg_clear(owner)
    except Exception: pass
    for k in ("pregnancy", "belly_desc_backup", "pregnancy_belly", "cycle_day",
              "offspring_progress", "offspring_counts", "offspring_roster",
              "facility_owner", "sale_price"):
        try: setattr(d, k, None)
        except Exception: pass
    # clear facility freeform marks
    try:
        ff = {k: v for k, v in (dict(getattr(d, "freeform_items", None) or {})).items()
              if not str(k).startswith("facility mark")}
        d.freeform_items = ff
    except Exception: pass
    try: d.factions = {}
    except Exception: pass
    owner.msg("|gForce-cleared. Speech, conditioning, triggers, marks, scripts, title, standing — all reset.|n")
