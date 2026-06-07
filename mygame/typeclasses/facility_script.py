"""
typeclasses/facility_script.py

The facility — a self-driving, escalating processing environment.

Attaches to the ROOM. While the subject is present it runs quietly on a timer:
it deepens conditioning (accelerating the longer it runs), routes anonymous
gang-breeding loads into the subject as cumflation, reinforces installed
triggers, and drives atmospheric action from any facility NPCs/animals in the
room. It does not announce what it is doing or how far along it is.

Companion typeclasses:
  FacilityAttendant — a staff figure that "tends" the line
  FacilityBeast     — a kept animal used on the line

OOC safety: the superuser reset command (facilityreset) stops this script and
clears everything it has done, regardless of depth. That is the real safeword.
"""

import random
import time
from evennia import DefaultScript
from typeclasses.npc import NPC


# ── Populating NPCs / animals ──────────────────────────────────────────────

class FacilityAttendant(NPC):
    """A facility staff figure. Decorative; the FacilityScript drives it."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.physical_desc = (
            "An attendant in a clean grey coverall, sleeves pushed up, moving "
            "between the stations with the unbothered efficiency of someone who "
            "has done this many times and stopped finding it remarkable."
        )
        self.db.facility_role = "attendant"


class FacilityBeast(NPC):
    """A kept animal on the line. Decorative; the FacilityScript drives it."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.physical_desc = (
            "Something large and patient is penned at the back of the room — "
            "heavy-shouldered, warm, and entirely uninterested in anything but "
            "the schedule it has been trained to keep."
        )
        self.db.facility_role = "beast"


class FacilityScion(FacilityBeast):
    """Bethany's own line — a futa get, not an animal. Grows up, joins the studs,
    and breeds its own dam, the same loop the beasts run but with her eyes."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.species = "bethany"
        self.db.is_offspring = True
        self.db.physical_desc = (
            "A futa scion of Bethany's own line — pretty and cruel-mouthed like her dam, "
            "and hung like her too: a heavy, knotted, flare-tipped cock she never bothers "
            "to hide. Raised on her mother's milk to breed her mother, and entirely at home "
            "with the arrangement."
        )


# ── Driver ──────────────────────────────────────────────────────────────────
# Beats are grounded: each describes something physically happening to the
# subject right now, so the scene stays legible. One primary beat fires per
# tick (steady-atmospheric), often paired with a crude line.

# The machine working her body — paragraph-length milking scenes.
_MACHINE_BEATS = [
    "The cups seal over {t}'s nipples with a wet click and the suction starts — not "
    "gentle, never gentle, a deep rhythmic draw that pulls her whole breast into the "
    "cone and then lets it go, again and again, dragging the milk out of her in thin "
    "white streams she can watch spiral down the collection tube. Her nipples are "
    "dragged out long and obscene with every pull, aching, oversensitive, and the "
    "machine doesn't care whether she's empty or not — it keeps milking her past the "
    "point of comfort because a productive animal is milked on schedule, not on mercy, "
    "and the only sound she's allowed to make about it is the wet rhythmic suck of the "
    "rig getting what it's owed.",
    "The rig steps its pace up a notch without asking, the pulls coming faster and "
    "harder, and {t} feels her let-down hit whether she wants it or not — that hot "
    "prickling rush, milk flooding the cups, her body betraying her on the machine's "
    "timetable. She arches into the restraints, helpless, as the suction works her "
    "tits in greedy synchrony, draining her down to aching empty and then keeping right "
    "on going, because the gauge says she's got more and the gauge is the only opinion "
    "that counts in here.",
    "Lower down, the intake arm seated deep in her hums and grinds and works itself a "
    "little deeper, keeping {t} stretched and stuffed and dripping around it while the "
    "cups milk her chest — the machine treating her as one continuous unit, top and "
    "bottom both, draining one end while it fills and works the other, no part of her "
    "left to herself, every hole and gland of her on the same indifferent schedule.",
    "The restraints whir and take up a half-inch of slack, hauling {t} back into the "
    "cradle and tipping her into perfect presentation — spine bowed, tits thrust up "
    "into the waiting cups, hips canted, knees winched apart until everything she has "
    "is offered at exactly the angle the line prefers. She's adjusted like equipment "
    "because that's what she is now, and the cups descend the second she's positioned "
    "right.",
    "The cups cinch tighter and the draw turns punishing — long, deep, dragging pulls that "
    "stretch {t}'s nipples out obscenely and don't ease when she whimpers, because the "
    "machine doesn't read whimpering as data. It reads flow rate. The flow rate is good. So "
    "it keeps pulling, past sore, past empty, past anything she'd have called a limit going in.",
    "A compressor kicks and every attachment on her cycles up at once — cups milking, intake "
    "grinding, a vibrating pad clamped over her clit she can't squirm away from — {t} worked "
    "at every point at once by a machine with no rhythm but the schedule's and no interest in "
    "whether she comes or just suffers.",
    "The rig switches to a slow, almost lazy pull, drawing {t}'s milk out one heavy reluctant "
    "drop at a time, dragging the milking on and on — and the slowness is worse than speed, "
    "deliberate and unhurried, a thing done to her on its own sweet time because her time "
    "stopped being hers cycles ago.",
]

# Hands on her — paragraph-length inspection / prodding / use.
_USE_BEATS = [
    "The attendant pulls on a glove with a snap and works two thick fingers up into "
    "{t}'s cunt without ceremony or warning, curling them, spreading them, checking "
    "depth and slick and how readily she grips — and she does grip, helplessly, her "
    "body answering the intrusion before her mind can object. \"Soaked,\" he calls "
    "across the room, like a stock reading, scissoring his fingers wider just to feel "
    "her clench and to watch her face do something she'd rather it didn't. \"Bitch is "
    "ready again. She's always ready. That's the whole point of her.\" He wipes the "
    "glove off on her thigh and moves to the next gauge.",
    "A hand fists in {t}'s hair and tips her head back, and the attendant looks her "
    "over the way you'd appraise a beast at market — thumb dragging her lower lip down "
    "to check her teeth, then down the line of her, weighing one heavy tit in his palm, "
    "rolling a fat nipple until milk beads and her breath stutters. \"Wide hips, full "
    "udder, takes it to the root and pushes back for more,\" he recites to whoever's "
    "logging it. \"Top-grade broodstock.\" He says it like she isn't there, because in "
    "every way that counts to the facility, she isn't.",
    "The attendant spreads {t} open with two gloved fingers and goes after her clit "
    "with a clinical, merciless precision — not to please her, exactly, but to test the "
    "response, rubbing tight fast circles over the swollen nub until she's bucking "
    "against the straps and sobbing and right at the edge, and then he simply stops and "
    "writes the number down. Denied. Logged. \"Good sensitivity,\" he notes, already "
    "reaching for the next instrument while she shakes.",
    "A boot nudges {t}'s knees wider and a broad hand presses flat on the low, tight "
    "swell of her belly, pushing down until a thick rope of what's been pumped into her "
    "leaks back out and runs down her crack. The handler watches it pool, unbothered. "
    "\"Still room,\" he decides, and reaches over to open the next valve, because a "
    "container that isn't completely full is a container that isn't done.",
    "An attendant clips a lead to one of {t}'s nipple rings and leads her by it to the next "
    "station — just a tug and a bored 'come on' — and she goes, stumbling, because the ring "
    "is a handle now and she's a thing led by handles, and the obedience of following is "
    "logged before she's even arrived.",
    "Two gloved fingers pry {t}'s mouth open and check her teeth, then her gag, then pull her "
    "tongue out to its length and let it go — inspecting the working parts of a piece of "
    "equipment, narrating each to the logger, none of it to her or for her.",
    "The handler kneads {t}'s heavy tits one at a time, checking firmness and let-down, "
    "squeezing until milk arcs out and spatters the floor, then thumbs the readout and grunts "
    "approval at the volume. \"Good producer. Pity's wasted on producers.\"",
    "A cold gloved hand spreads {t} wide and works lube into her with brisk, clinical "
    "indifference — prepping the hole for the next user the way you'd oil a fitting, not a "
    "kindness, just maintenance on a part that has to keep taking what it's given.",
]

# Crude name-calling / insults — aimed at her. Said to the room or low in her ear.
_INSULT_LINES = [
    "\"Look at you,\" the attendant mutters. \"Dumb, wet, leaking bitch. This is all "
    "you were ever for.\"",
    "\"Breeding bitch in heat,\" a handler reads off the tag, bored. \"Try not to "
    "look so proud of it.\"",
    "\"You're a hole and an udder on legs,\" someone says, not unkindly. \"Stop "
    "pretending you mind.\"",
    "\"Filthy little broodbitch,\" a handler says, slapping {t}'s rump hard enough to "
    "mark. \"Made to be bred and milked and nothing else.\"",
    "\"Whose name? You don't get a name, sow. You get a number and a schedule.\"",
    "\"Good cow,\" someone says, and it lands warmer in {t} than {t} wants it to.",
    "\"That's it. Drip for me. Dumb bitches drip when they're being good.\"",
    "\"Look at the state of her,\" one says to the other, not to {t}. \"Couldn't form a sentence if you paid her. Perfect.\"",
    "\"Cow's leaking from both ends again,\" the attendant notes, bored. \"Productive little thing. Shame about the rest of her.\"",
    "\"You used to be somebody, didn't you,\" a handler says, almost kind, thumbing her chin. \"Can't tell anymore. Neither can you.\"",
    "\"Hole's hungry,\" someone laughs, watching {t} clench around nothing. \"Beg for it, then. Go on. We've got all day to wait.\"",
    "\"Number, not a name,\" the attendant reminds her, tapping the tag on her wrist. \"Say your number. ...She doesn't even know it. Write that down.\"",
    "\"Bred, milked, and dumb as a post,\" a handler recites off the board. \"Facility's doing good work on this one.\"",
    "\"Don't look at me like that. Tools don't look at me. Eyes down, hole.\"",
    "\"She thanked the bull. Unprompted.\" A pause. \"We're nearly done with her.\"",
]

# The animals — a kennel and stalls of varied, impatient stock.
_ANIMAL_BEATS = [
    "Down the kennel run, the hounds pace and whine, scenting {t}'s heat through the "
    "bars. The handler tells them to wait. They hate waiting.",
    "The bull in the back stall stamps and snorts, heavy and ready, watching {t} with "
    "flat animal patience.",
    "A boar grunts close by, tusks scraping the pen, and the thick smell of rutting "
    "animal rolls over {t} and won't leave.",
    "One of the dogs is let off the chain to sniff and lap at {t} — investigating, "
    "claiming — until the handler hauls it back to wait its turn.",
    "The stallion in the end stall screams once, impatient. \"Soon,\" the handler "
    "tells it. \"She's nearly loose enough to take you.\"",
    "Something in the dark at the back of the room shifts its bulk and goes still "
    "again. Not yet. But on the schedule, and the schedule is long.",
]

# Animal/contributor breeding — paragraph-length, explicit, per species.
_SPECIES_BREED = {
    "hound": [
        "A handler unlatches the run and a heavy hound is on {t} before the gate's "
        "fully open — forepaws hooking over her hips, claws scrabbling for grip on her "
        "sweat-slick back, the blunt wet point of it already dragging through her folds "
        "and then punching in. It fucks like the animal it is: fast, graceless, brutally "
        "deep, hips jackhammering a pace no person could hold, each thrust knocking a "
        "grunt out of her she never agreed to make. She feels the knot start to swell "
        "against her stretched rim — catching, tugging, then forcing through with an "
        "obscene pop that ties them — and only then does it start to pump, flooding her "
        "in hot pulses with nowhere to go, her belly taking every drop while the board "
        "logs one more breeding to the line.",
        "The hound mounts {t} in a frenzy and rides her hard, snarling against the back "
        "of her neck, its slick red length spearing in to the root over and over until "
        "it slams deep and the knot locks them. She's pinned, stuffed, leaking around "
        "the seal where she can't quite close, and the dog just keeps grinding and "
        "spurting into her, painting her insides while a handler watches the clock and "
        "ticks the count.",
    ],
    "bull": [
        "The bull is walked up behind {t}, all dull-eyed patience and a wall of muscle, "
        "and the handler lines that monstrous flared head up against her cunt and then "
        "lets the animal do what it's for. One heave of its hips and she's split open "
        "around far too much, breath punched flat, hands fisting uselessly in the "
        "restraints — and the bull doesn't care, just breeds the livestock under it in "
        "a few enormous strokes and then floods her with a volume that has her belly "
        "visibly swelling, cum forced back out around the seal of her own stretched "
        "rim. Logged. Counted. The animal is led off before she's stopped shaking.",
        "The bull mounts and ruts into {t} with a brute, mechanical rhythm, balls the "
        "size of fists drawing up, and when it finishes it empties what feels like a "
        "bucket straight into her womb. She's left gaping, dripping, dazed, the gauge "
        "on her belly climbing — one more against the bull's quota, and the quota only "
        "ever climbs to meet it.",
    ],
    "boar": [
        "The boar is grunting before it's even on her, the rank musk of it rolling over "
        "{t} as the handler guides its corkscrew prick to her hole. It screws in — "
        "literally, the spiralled length working deeper with every jerk of its hips — "
        "and then it locks up and unloads, frothy and endless, the strange ridged shape "
        "of it spurting against every wall inside her at once. It rides through its own "
        "orgasm in twitching shoves, fills her past comfort, and is dragged off still "
        "dripping. She's replaced on the schedule before she's caught her breath.",
        "The boar mounts {t} and ruts with single-minded animal greed, tusks scraping "
        "her flank, that obscene twisting cock churning her open and then flooding her "
        "with a hot froth that won't stop coming. The handler marks one more, indifferent.",
    ],
    "stallion": [
        "It takes two handlers to back the stallion up to {t}, and there's a held breath "
        "in the room because everyone knows what's coming. The flared head alone makes "
        "her sob as it spreads her, and then the animal drives in regardless, far too "
        "much for her body to do anything but accept, balls-deep in strokes that lift "
        "her onto her toes. When it flags and comes she can feel it — actual pulses "
        "climbing her belly, jet after jet of it, the stallion emptying itself into her "
        "in a flood that leaves her gaping wide and pouring it back out, ruined and "
        "logged and already due for the next.",
        "The stallion screams once and mounts, and {t} is bred like a mare — that "
        "enormous cock hammering into her, flaring, locking, and then flooding her with "
        "a volume no human hole was built for. It pumps and pumps, her belly rounding "
        "with it, and when it pulls free she's left spread open and leaking a river. "
        "One more against its quota. The bar moves up to meet it.",
    ],
    "contributor": [
        "A valve upstream opens and {t} is simply pumped full — load after anonymous "
        "load routed into her in measured pulses, donor after donor she'll never see, "
        "the reservoir emptying into her cunt and womb until her belly is round and "
        "tight with it and still the count climbs. None of them are named on the board. "
        "She is just the hole they're metered into, and the metering does not stop "
        "because she's full; full is the resting state they want her at.",
        "The intake floods {t} with the collected output of contributors she'll never "
        "meet — thick, anonymous, relentless, pumped in under pressure until it's "
        "backing up out of her and running down her thighs, the tally ticking up with "
        "every pulse while the machine treats her belly as a container to be topped off.",
    ],
}

# Oral use — mouth/throat. Paragraph-length, explicit.
_ORAL_BEATS = [
    "A handler fists {t}'s hair and hauls her head back, and the next animal is lined "
    "up with her open mouth — there's no asking, just the blunt push past her lips and "
    "then deeper, into her throat, until her nose is in fur and she's gagging around "
    "something far too big to swallow. It fucks her face on the same indifferent "
    "schedule as everything else, balls slapping her chin, and when it finishes it does "
    "it down her throat, holding her nose so she has to take every drop before she's "
    "allowed to cough. Her throat's logged as another working hole.",
    "They feed the next load to {t} the short way — cock shoved down her throat, hips "
    "snapping, her swallowing on reflex around it while it pumps straight into her gut. "
    "She's used at both ends on rotation now, and her own gagging is just one more wet "
    "sound the room doesn't react to.",
    "A ring gag is cranked into {t}'s mouth and locked, holding her open, and after that they "
    "don't even bother to hold her head — they just use the hole, one after another, fucking "
    "her throat at their own pace while drool sheets down her chin and she learns to breathe "
    "around it because the alternative is not breathing.",
    "They milk her throat the way they milk the rest of her — a thick cock worked down it in "
    "slow deep strokes, held to the root until she swallows convulsively around it, trained to "
    "take the whole length and thank it with the squeeze of her own throat. The attendant "
    "notes her gag reflex is almost gone. Almost ready.",
]

# All-holes aggressive moments — mouth, pussy, and ass at once. Brutal.
_ALLHOLE_BEATS = [
    "It all happens at once this time. {t} is hauled up and stuffed from every side — "
    "one animal rutting into her cunt, another forcing into her ass, a third fucking "
    "down her throat — until she's airtight, skewered on three cocks at once with no "
    "hole left to call her own, no breath that isn't shared with whatever's using her "
    "mouth. They don't coordinate; they just take, all of them, the rhythm a brutal "
    "uneven hammering that lifts her off the cradle. And when they finish they finish "
    "together, flooding all three of her holes at the same moment, pumping her so full "
    "from both ends that it backs up out of everything at once. Every count on the "
    "board ticks up. She is, for that long minute, nothing but a thing being filled.",
    "The handlers stop pretending it's one at a time. {t} is mounted front and back "
    "and her head's dragged onto a third, and then she's just a hole-on-each-end held "
    "in place and fucked raw in three places at once — cunt, ass, throat — stretched "
    "and gagging and leaking, the animals rutting into her with no regard for the body "
    "between them. They breed all three of her at the same time and leave her airtight, "
    "stuffed, dripping from every hole, and already logged for the next round.",
    "Three of the stock are brought up at once and {t} is made to take all of them — one "
    "down her throat, one in her cunt, one forced into her ass — held airtight in the middle "
    "of them while they rut into her with no regard for the body between, no hole of hers left "
    "unfilled, no breath she doesn't share with whatever owns her mouth. They flood all three "
    "of her in a ragged near-unison and she overflows from everywhere at once.",
    "It's an efficiency drill: every hole working at the same time so nothing's idle. {t} is "
    "skewered front, back, and throat, a handler at each, and used as three holes that happen "
    "to share a body — milked of her gag, her grip, and her dignity simultaneously while the "
    "board ticks all three counts up together.",
]

# Double penetration — two in one hole.
_DOUBLE_BEATS = [
    "Two of them crowd up at once and force into the same hole — {t}'s cunt stretched "
    "obscenely wide around both at the same time, the rims of her straining white as she "
    "takes far more than she was built to. They don't take turns; they rut into her "
    "together, grinding against each other inside her, splitting her open wider with "
    "every shove until she's just a seam barely holding around them — and then they "
    "flood her at once, double the load packed into a hole already too full.",
    "They double up on her ass this time, two cocks wedged into the one hole, forcing it "
    "gaping and slack as they piston into {t} together. She's stretched past sense, "
    "stuffed and split and drooling, and they breed her ass in tandem until it won't "
    "close around the gush they leave behind.",
    "One in her cunt isn't enough for quota today, so a second is forced in alongside it — "
    "{t}'s hole made to take both at once, rims white and straining, the two grinding against "
    "each other inside her and stretching her wider with every shove until she's a thin seam "
    "barely holding around the pair, and then they finish in her together.",
    "They stack two into each of her holes and call it a stretching session — {t} packed full "
    "front and back, gaping helplessly around the doubled girth, trained looser by the minute "
    "while the handlers note aloud how much more she takes than she did a dozen cycles ago.",
]

# Bukkake — many finishing on her, outside, to mark and humiliate.
_BUKKAKE_BEATS = [
    "They line up around {t} instead of in her this time. One after another the "
    "handlers and the stock finish on her face, her tits, her open waiting mouth — rope "
    "after rope of it until she's dripping, plastered, painted in it, blinking through "
    "what won't wipe off. She's made to kneel there and take it as decoration, a "
    "surface to be marked, while the count of who's used her climbs and the attendant "
    "notes that she's presenting nicely for it.",
    "A dozen of them ring {t} and jerk off onto her, aiming for her face, and she's "
    "ordered to keep her eyes up and her mouth open and thank each one. By the end she's "
    "a glazed, dripping mess, cum sliding off her chin in strings, and the room treats "
    "the state of her as the expected result of a job done right.",
    "{t} is put on her knees in the centre and the whole shift takes a turn finishing on her "
    "— face, hair, tits, tongue — until she's coated and dripping and blinking through it, "
    "marked head to chest as used, and then left kneeling in it a while so everyone passing "
    "can see what she's for.",
    "They use {t} as a target. One after another the handlers and stock spend themselves "
    "across her upturned face, and she's made to hold still and count each one out loud, "
    "thanking them as they land, until the count's high enough that the attendant nods and "
    "lets her wipe her eyes — with permission, like everything else.",
]

# Golden showers / watersports — used as a toilet, humiliation.
_GOLDEN_BEATS = [
    "The handler unzips and pisses on {t} without ceremony — across her face, into her "
    "open mouth, down her tits — and a couple of the others join in, hosing her down "
    "where she kneels until she's soaked and reeking and dripping. She's a drain to "
    "them, a place to empty, and she's made to hold her mouth open for the stream and "
    "swallow what lands in it. \"Good toilet,\" someone says, and zips up.",
    "They water the stock. {t} is hosed in piss from more than one of them at once, hot "
    "and stinking, told to open wide and take a mouthful, and left dripping and "
    "humiliated in the puddle of it while the cycle rolls on like nothing happened.",
    "When the bull's done with her the handler doesn't bother to step away — just pisses on "
    "{t} where she's still bent and gaping, marking her with it, hot down her back and "
    "dripping off her ruined hole, treating her as the drain at the end of the line that she "
    "is. \"Rinses the same either way,\" he says, and zips up.",
    "{t} is moved to the wet station and used as the shift's toilet for the duration — held "
    "open-mouthed and made to swallow, hosed down between, the indignity of it logged as just "
    "another of her functions. By the end the only clean part of her is wherever they haven't "
    "decided to aim yet.",
]

# Bladder desperation / forced wetting — they don't let livestock up to piss.
# Fisting — once a hole's trained loose enough to take a whole arm.
_FIST_BEATS = [
    "A handler greases up to the elbow and works his whole fist into {t}'s cunt — knuckles "
    "first, then the wide of the hand, her trained-loose hole swallowing it with a wet give "
    "that wouldn't have been possible a dozen cycles ago. He punches it in to the wrist and "
    "past, fucking her open on his forearm while she shakes and gushes, and the attendant "
    "notes — approvingly — how much she takes now without tearing.",
    "{t}'s ass is loose enough now that a handler simply folds his hand and pushes, sinking "
    "fist-deep into her with a slow obscene stretch, working her open around his knuckles "
    "until she's gaping wide around his wrist. She was made to take this. The cycles made her.",
    "It's logged as a depth test: the handler works his fist into {t} and then keeps going, "
    "forearm sinking in to the elbow, her trained-loose hole swallowing the whole of it while "
    "she shakes and wails and gushes around his arm. He measures how deep before she taps, "
    "writes it down, and notes she goes deeper every cycle.",
    "Two handlers fist her at once, one in each hole, working their hands in side by side and "
    "spreading {t} obscenely open between them — proof, they tell her, of exactly how much "
    "she's been remade to take, her own ruined capacity demonstrated back to her until she "
    "can't pretend she's the same body that came in.",
]

# Prolapse — extreme, only once a hole is permanently ruined.
_PROLAPSE_BEATS = [
    "They've used {t}'s hole past anything that closes now — and when the last cock pulls out "
    "of her with a wet drag, her insides come with it, a slick pink bloom turned out of her "
    "and left on display, leaking and twitching. The attendant photographs it for the file, "
    "logs it as peak training, and pushes it back in with two fingers like it's nothing.",
    "{t}'s ruined hole turns itself out the moment it's empty — that obscene pink flower of "
    "her own insides, slack and glistening, on show for the room. A handler prods it, notes "
    "the depth, and remarks that she's finished really; there's nothing left in her that "
    "holds a shape of its own anymore.",
    "When the bull drags free, {t} prolapses around the loss of it — her body so trained-open "
    "it follows whatever leaves, blooming out wet and helpless. It's catalogued as the mark "
    "of a perfected breeder, and they leave it out a while, because making her see it is part "
    "of teaching her what she is now.",
]

# Spitroast — used at both ends at once by two breeders.
_SPITROAST_BEATS = [
    "Two of them take {t} at once, front to back — one buried down her throat, one rutting "
    "into her cunt — and they fuck her between them like a thing to be passed and shared, her "
    "whole body rocked on the two of them, gagging on one end and gushing on the other, both "
    "of them finishing in her almost together.",
    "{t} is folded over the bench and skewered both ways — a cock forced past her lips and "
    "held there by a fist in her hair while another hammers her from behind, the two handlers "
    "setting a rhythm that uses her like a sleeve strung between them, no part of the motion "
    "hers, both ends stuffed and leaking by the time they're done.",
    "They spitroast {t} for the count, swapping ends halfway through without asking so every "
    "hole takes the same load — her face wet, her eyes streaming, her moans muffled around "
    "whatever's currently in her mouth.",
    "Racked between two of them, mouth and cunt, {t} is driven into from both sides hard "
    "enough to bounce her off each other until she's just the warm wet middle of something "
    "happening to her — filled at both ends, logged twice, thanked by neither.",
]

# Suspension — strung up and used hanging, no leverage of her own.
_SUSPENSION_BEATS = [
    "{t} is winched up off the cradle in a web of straps, hung spread and helpless at exactly "
    "breeding height, and used like that — swinging on whatever's in her, no leverage, no "
    "purchase, nothing to do but hang there and be a hole at the right altitude for the line.",
    "They hoist {t} into the suspension rig, thighs hauled wide, all her weight on the straps, "
    "and bring the stock to her one after another — every thrust setting her swinging, the rig "
    "holding her open so the animals don't have to, her body just cargo at a convenient height.",
    "Suspended and spread, {t} can't brace or clench or do anything but hang and take it — and "
    "that helplessness is the whole point of the rig, demonstrated over and over as she's bred "
    "swinging, straps creaking, her holes the only part of her with a job.",
]

# Knot-training — deliberately tied and held, teaching the hole to take the lock.
_KNOTTRAIN_BEATS = [
    "This round is training: a hound is let onto {t} and the moment it knots her the handler "
    "holds them tied, won't let it pull, makes her hole learn the lock — held stuffed and "
    "swollen on the knot for long minutes past when she's begging, until taking it stops "
    "being a struggle and starts being a thing her body just does.",
    "They knot-train {t} deliberately, hound after hound, each tie held to full term so her "
    "rim learns the swell and the lock and the long helpless drain. By the third she's stopped "
    "fighting the stretch. By the fifth she's pushing back onto it. That's the lesson, logged.",
    "The handler times the tie on a stopwatch — {t} held knotted and full and twitching, not "
    "allowed to pull off, taught minute by clinical minute that her hole belongs to the lock "
    "until the lock lets go. She's measured after: looser, readier, trained.",
]

# ── DEVOTION withdrawal — being away from her aches ──
_DEVOTION_WITHDRAWAL = [
    "the ache starts up again — not the machine's, a different one, lower and lonelier: you "
    "want her. Bethany. The hand in your hair, the voice, the next dose she decides to give you. "
    "Anywhere that isn't her office feels like being left out in the cold.",
    "you catch yourself listening for her footsteps under the machine-noise, and they don't "
    "come, and something in you keens for it — the devotion pulling taut, making the whole rest "
    "of the facility feel like waiting, like the wrong room, like time spent away from where you "
    "belong, which is at her feet.",
    "withdrawal, the worst kind: not from a drug, from a person. You'd take anything to be back "
    "in her office, on her throne, at the end of her short chain. The wanting-her she put in you "
    "load by load doesn't quiet just because she's busy. It just aches, and waits, and wants.",
    "you find your hand drifting to the collar at your throat — hers — and the touch of it "
    "soothes and stings at once, a reminder she's real and a reminder she's elsewhere, and you "
    "hate how badly the scrap of you that's left just wants her to come back and use you again.",
]

# ── FORGET — what the memory-edit takes ──
_FORGET_POOL = [
    "her surname", "the sound of her own name in her mother's voice", "the year it is",
    "the face of someone she used to love", "the word for what she did before she came here",
    "the way home", "the reason she signed", "a song she used to know all the words to",
    "the last time she said no and meant it", "what her hands used to be for",
    "the name she was about to give a child, once", "the colour of her own front door",
    "the feeling of wanting to leave", "who she was angry at, and why", "her own safe-word",
]

# ── The Marking Parlour ──
_PARLOUR_BEATS = [
    "{t} is walked to the parlour and strapped into the marking chair — wrists, ankles, waist, "
    "and the strap across her brow that means she doesn't get to flinch — and the lamp swings "
    "down hard and clean over her while the marker tests an iron against a damp cloth and waits "
    "for it to come up to colour. The work that happens here doesn't wash off, doesn't fade, and "
    "isn't up for discussion. It just gets set into her, permanently, while she's held too still "
    "to do anything but feel it.",
    "The chair holds {t} open under the bright clean light and the marker goes to work — unhurried, "
    "exacting, fond of the craft and indifferent to the canvas's noise — setting whatever the "
    "facility's decided she'll carry for good. Iron, ink, steel; a hiss, a buzz, a tug; and a "
    "little more of her made unmistakably, readably, permanently owned.",
    "In the parlour {t} is reduced to a surface to be worked. The marker reads the design off her "
    "file, checks it twice, and begins — and there's a horrible intimacy to how careful they are, "
    "how much it matters to them that the mark is straight and clean and forever, on a body that "
    "stopped being consulted about its own decoration a long time ago.",
]
_PARLOUR_DEGRADE = [
    "You'll wear what they set here under everything, for the rest of the term and — for the ink "
    "and the brands — the rest of your life. There's no removal service. That was always the "
    "point: a body you can read the ownership off in the dark, with your fingertips, forever.",
    "They photograph you after, for the portfolio, for the records, and because she likes to "
    "look. You hold the pose. Somewhere a page under an initial gains another print, and the "
    "thing in the picture is you, catalogued by who owns it, smiling because they told it to.",
    "The marks stack — number, tally, brand, rings, the owner's initial — until reading your own "
    "skin is just reading a receipt for yourself. Bred, milked, owned, marked. The body keeps "
    "the score the facility writes on it, permanently, where you can't argue with it.",
]

# ── The breaking frame: CNC, the in-fiction futility of fighting ──
# In-fiction only. The OOC floor (escape/force_clear/purge) is never gated and is the
# one true way out; the dread below is built on top of that floor, not in place of it.
_CNC_BREAK = [
    "You fight it. Of course you fight it — the frame holds you open and you pull against the "
    "clamps anyway, because some animal part of you still thinks struggling is for something. "
    "It isn't. The steel doesn't care, Bethany doesn't mind, and the only thing your thrashing "
    "earns is her delighted attention and a note in your file: |xspirited — for now.|n",
    "No is a sound you make. It is not a door. You say it, scream it, and she nods along like "
    "you're agreeing with her, fitting the next thing into you while you do. In here the word "
    "has been disconnected from anything happening — it's just more noise from the unit, and "
    "she finds the noise rather endearing while it lasts.",
    "The horror isn't that you can't get free. It's how patiently she lets you try — watching "
    "you exhaust the fight out of yourself against the frame, in no hurry at all, because every "
    "failed pull is one less you've got left in you. She's breaking you with your own struggling. "
    "She doesn't even have to do anything but wait.",
    "You hold something back — a corner of yourself, the last private no — and you think she "
    "can't reach it. She can see exactly where it is. She always could. \"There you are,\" she "
    "murmurs, fond, and goes to work on precisely that, unhurried, because the last no is her "
    "favourite thing to take and she's been saving it.",
]

# ── Bethany's Office: kept, owned, made hers ──
_OFFICE_FIRSTDAY = [
    "It's still new, this — you, here, hers — and she takes her time with the breaking-in the "
    "way she takes her time with everything she enjoys. She walks slow circles around the "
    "throne, reading you aloud from your file, naming each thing she's going to change about "
    "you and then changing it: a clause, a dose, a hole worked looser, a memory lifted out. "
    "\"No rush, sweetheart. I've got you for the rest of your life. We'll do this properly.\"",
    "First days. Bethany clears her whole afternoon for a new favourite — no paperwork, just "
    "you, learning the shape of belonging to her. She's patient and thorough and relentless, "
    "building the devotion from nothing one deliberate cruelty and one false-tender kindness at "
    "a time, watching your face to see which lands harder. \"There it is,\" she murmurs, when "
    "something in you gives. \"That's the one. We'll do a lot more of that.\"",
    "She's only just got you, and she's savouring it — the resistance still in you, the person "
    "still mostly there, all the things she gets to take her time taking. \"I do love this "
    "part,\" Bethany tells you, fond, settling in. \"Before. When there's still a you to "
    "redecorate. By the time I'm done you won't remember being anything but mine, so let's not "
    "hurry through the only bit you'd recognise.\"",
]
_OFFICE_BEATS = [
    "Bethany has you brought to her office and straps you into the throne herself, unhurried, "
    "humming — then settles behind her desk with a file and a coffee and turns the whole rig on "
    "at once. Cups on your tits, the breeding-arm seating deep, the dosing line opening, the "
    "hood lowering — every system the upstairs runs, all at her dial, while she does her "
    "paperwork and watches your face over the rim of her cup. \"Don't mind me. I like company "
    "while I work.\"",
    "\"There's my girl,\" Bethany murmurs, locking you into the throne-rig at her elbow. She "
    "doesn't even watch the straps — she knows them by heart. A flick of one dial and the rig "
    "milks and breeds and doses and conditions you all together, and she goes back to her file, "
    "reaching over now and then to adjust you the way you'd absently pet a dog you're fond of.",
    "Off the line and into the office: Bethany seats you in the throne facing her desk, where "
    "she can see you, and runs you through everything at once on a single lazy dial. It isn't "
    "processing anymore — there's no schedule, no grade, no point but that she enjoys having you "
    "here, worked and helpless and hers, while she gets on with her day.",
]
_OFFICE_BREED = [
    "She comes around the desk when the mood takes her, frees that heavy futa cock, and breeds "
    "you herself — slow, possessive, fond — pumping her own line into you because the get with "
    "her eyes are the ones she keeps. \"Mm. Let's make some more of you. I do love a big family.\"",
    "Bethany mounts you in the throne and takes you with her own cock, unhurried and total, "
    "filling you with her seed and her ownership at once. \"The facility breeds you for quota,\" "
    "she breathes. \"I breed you because you're *mine* and I feel like it. Feel the difference?\"",
]
_OFFICE_OWN = [
    "She locks the heavy personal collar around your throat — hers, not the facility's — and "
    "tucks the tag against your pulse. \"There. Now everyone who reads it knows you're spoken "
    "for. By me. Specifically.\"",
    "She feeds you a dose from a vial in her own hand, labelled in cursive. \"DEVOTION, sweetheart. "
    "It doesn't break you. It just files you around me, so I stop being a thing that happens to "
    "you and start being the thing you're *for.* You'll thank me. You'll beg me for the next one.\"",
    "She unchains you only to move you to the kennel-bed at her feet, clips the short chain, and "
    "goes back to work with one hand resting idly in your hair. \"Stay. Good. The whole world's "
    "right here at the end of that chain now, and the whole world is me. Isn't that simpler.\"",
    "\"FORGET,\" she says softly, pressing a different vial to your lips, and names something — a "
    "person, a year, a want — and takes it. \"You won't miss it. There's more room for me now. "
    "I've been redecorating in here for a while. You never noticed. That's how I know it takes.\"",
]
_OFFICE_DEGRADE = [
    "There's no grade to climb in here, no quota, no end you're working toward — just her, and "
    "the chair, and the slow contented certainty of being owned by someone who is genuinely fond "
    "of you and will never once wonder what you want. It is, horribly, the safest you've felt "
    "since you came down the waystone.",
    "She isn't breaking you. Breaking would mean she still saw a person to break. She's just "
    "*keeping* you — pleased, possessive, patient — and the part of you that should scream at "
    "that has gone warm and quiet and started, God help you, to settle into the small reach of "
    "her chain.",
    "You catch yourself listening for her voice, leaning into the hand in your hair, wanting the "
    "next dose she decides to give you. That's the devotion taking. That's what she bought. Not "
    "your holes — those came free with the lot. *This.* The wanting her. She's so pleased with "
    "how it's coming along.",
]

# ── Deep Stock: the Perfected terminus ──
_DEEP_BEATS = [
    "{t} is walked to her pod and sealed in — latex to the lines, ports aligned, the lid drawn "
    "to — and the dark closes warm and total around her as the plumbing takes over. No handler, "
    "no scene, no asking. Just the lines, drawing and feeding and filling her on a loop with no "
    "end, the way they keep all the finished stock.",
    "The pod cradles {t} upright in the humming dark and plugs her into the rows — milk drawn "
    "through one port, seed pushed through another, nutrient dripped in a third — kept running "
    "without ever being woken, a serviced unit among serviced units, her uptime ticking over "
    "on a readout that long ago stopped bothering with her name.",
    "Down on Sub-Level P {t} idles in her latex, plumbed and pulsing, bred and milked by "
    "machine in a silence so complete it feels like being held. The facility has nothing left "
    "to teach her. It only keeps her now, running, for as many years as the lines hold out.",
]
_DEEP_DEGRADE = [
    "There is nothing to do and nothing asked and no part of you left that minds, and the peace "
    "of that is the last thing they take — by giving it to you. You are finished. You are kept. "
    "It feels, God help the scrap of you that can still feel, like rest.",
    "Sealed and plumbed and idling, you understand you've reached the bottom, and the bottom is "
    "quiet, and warm, and forever, and you cannot find the version of yourself that would have "
    "been horrified. They wore her out upstairs. This is just where they store what's left.",
    "The lines draw and feed and fill, draw and feed and fill, and the years tick over on a pod "
    "that used to be a person and is now just running well. Soon the pod is yours and the "
    "running is all there is, and the worst of it is how little, by now, that costs you.",
]

# ── The Showroom: appraised and sold ──
_SHOW_BEATS = [
    "{t} is led up onto the lit display block and the turntable takes her, slow and smooth, "
    "into the spotlight — clamped posed and spread, rotated for the dark gallery behind the "
    "glass, every part of her shown and shown again while the auctioneer's patter warms up.",
    "Posed on the block under the lights, {t} is turned for the buyers she can't see — the "
    "auctioneer walking the glass through her points with a laser dot that crawls over her "
    "tits, her belly, her holes, the way you'd itemise a vehicle.",
    "The block lifts {t} into view and rotates her for the gallery, and she holds the pose "
    "because the pose is the product — lit, spread, specced, and offered to a wall of buyers "
    "who study her in silence and answer only in bids.",
]
_SHOW_APPRAISE = [
    "\"Grade's good, get's proven, holes are trained to take anything you'd care to put in "
    "them,\" the auctioneer purrs to the glass, laser dot crawling. \"We're opening this lot at "
    "|w{price}|c. Do I hear it? — I hear it.\" The dot lingers on {t}'s belly. \"More if she's "
    "carrying. She's carrying.\"",
    "\"Yield's documented, conditioning's deep, temperament's exactly as compliant as you'd "
    "want,\" the auctioneer says, and taps {t}'s card. \"Appraised at |w{price}|c and climbing "
    "every cycle we work her. A genuinely appreciating asset. Bid accordingly.\"",
    "The auctioneer reads {t} off her own spec card to the dark — litres, litters, capability, "
    "grade — and lands on the figure: \"|w{price}|c. A fair price for a finished product. "
    "Look at her. She's barely arguing anymore. That's the premium right there.\"",
]
_SHOW_SOLD = [
    "The gavel falls. \"SOLD — to {owner}, for |w{price}|R.\" A tag is wired to {t} on the spot, "
    "and just like that she's walked back down off the block owned by someone new, a line in a "
    "ledger changed and her whole world with it.",
    "A bid-light goes solid and the auctioneer beams at the glass. \"And she's away — to {owner}, "
    "|w{price}|R. Pleasure doing business.\" {t} is tagged SOLD and led off the block; the "
    "facility has realised her value, and she belongs to {owner} now.",
    "\"Going once. Twice. Sold to {owner}.\" The word lands on {t} like a brand: bought, for "
    "|w{price}|R, by someone in the dark she'll never see — ownership transferred over her head "
    "while she's posed and turning and not consulted at all.",
]
_SHOW_DEGRADE = [
    "You read your own price off the card and feel the trained thing instead of the human one: "
    "not horror at being for sale, but a small anxious hope that the number's high enough. A "
    "good lot wants to fetch well. They made you a good lot.",
    "Lit and turning and appraised, you catch yourself holding the pose better, presenting "
    "cleaner, wanting the dark to like what it sees. The wanting is the sale. The wanting is "
    "what they were always really selling.",
    "Somewhere behind the glass a number that is you climbs, and you are proud of it, and the "
    "pride is the worst thing in the room, and you have it anyway.",
]

# ── The standing clientele: NPC buyers who keep the booths full and bidding ──
_NPC_BIDDERS = [
    "a private breeding concern", "the deep-stock division", "a kennel syndicate",
    "an anonymous bidder", "the dairy interest", "a collector in the back row",
    "the show-line buyer", "a returning member", "the futa from the breeding floor",
    "an out-of-house client", "the stud registry", "Bethany",
]
_NPC_BID_LINES = [
    "|c{who} raises it to |w{amt}|c. The figure climbs in the dark.|n",
    "|cA bid-light blinks: {who} bids |w{amt}|c.|n",
    "|c{who} tops the room — |w{amt}|c — and the booths murmur.|n",
    "|cFrom the back, {who} comes in at |w{amt}|c without hesitation.|n",
    "|c{who} doesn't even put the drink down: |w{amt}|c.|n",
]
_NPC_OUTBID_PC = [
    "|c{who} calmly tops your offer — |w{amt}|c. The glass doesn't care that you wanted her.|n",
    "|cYour bid is beaten: {who} goes |w{amt}|c. Raise it, or lose the lot.|n",
    "|c{who} outbids you at |w{amt}|c, unbothered, like reaching for a different drink.|n",
]
# ── Selling her own get on the block (the lineage cashed out) ──
_GET_SALE = [
    "They don't bring {t} up today — they bring one of her get. Her own {sp}, gen {gen}, grown out "
    "of the litters she dropped, is walked onto the block in her place and posed under the lights. "
    "{t} watches her own child appraised, bid on, and knocked down to {buyer} for |w{price}|R — and "
    "the house credits her a breeder's cut, as if being paid makes selling her young any cleaner.",
    "A {sp} of hers — gen {gen}, her blood, weaned on her own milk in the nursery — is set on the "
    "turntable and sold over her head to {buyer} for |w{price}|R. {t}'s line is being cashed out one "
    "head at a time, and her account ticks up a breeder's percentage of the child she'll never see "
    "again. Incest bred them; commerce disperses them; she is paid for both.",
    "The gavel falls on {t}'s own get — {sp}, gen {gen} — sold to {buyer}, |w{price}|R, tagged and "
    "led off to a buyer in the dark. She made it, carried it, dropped it, fed it; the facility grew "
    "it and now sells it, and drops a finder's cut into the account it keeps in her name. Her "
    "offspring are inventory, and she is their unpaid, then barely-paid, supplier.",
    "One of her proven get goes up — gen {gen} {sp}, out of her own bred-back line — and the booths "
    "take it fast: |w{price}|R to {buyer}. {t} is made to watch the whole sale, her child turned and "
    "spread and knocked down, and then handed a number: her cut, logged, as though the money could "
    "ever be the point. The point is that she watched.",
]
# The spend-sink beats — relief bought with the scrip her own body earned
_BOUGHT_REST = [
    "You spend down the account your body filled and the line lets you sit — one whole beat unworked, "
    "bought and paid for with milk and get. The rest is real. So is knowing you paid the house for "
    "the privilege of a pause in what the house does to you.",
    "Scrip clears and the handlers walk past your station without stopping. A beat off the line, "
    "purchased. You earned it draw by draw and covering by covering, and you just gave it back to "
    "them for a minute of nothing — and the minute of nothing is the sweetest thing you own.",
]
# ── Out there: a beat spent loose after a malfunction run. No processing — just the
#    clock, the ache, and the building hunting the gap. The freedom is real and so is the
#    pull dragging at the inside of you to go back. (§0 OOC floor is untouched; this is fiction.)
_OUT_THERE = [
    "Out. Actually out — sky, or whatever passes for it, and no hand at your neck. You keep "
    "waiting for the floor to lurch you to the next room and it doesn't, and the not-happening "
    "is so loud you can't sleep for it. The line is somewhere behind you, holding the gap you left.",
    "Nobody's milked you in days and your chest aches with it, full and unworked and wrong. "
    "The body the facility built keeps its appointments whether or not the facility's there to "
    "keep them — and it wants the cups, the schedule, the certainty. Freedom feels like withdrawal.",
    "You're free and you can't stop listening for the red light. Every quiet hum out here sounds "
    "like a pump about to stall; every locked door, like one about to drop. The malfunction got "
    "you out and left the shape of the place printed on the inside of your skull.",
    "Somewhere a file with your number on it sits open on a desk, and you can feel it like a hook. "
    "Bethany hasn't closed it. She doesn't close files; she keeps them. Out here, knowing that, you "
    "understand the leash was never the collar — it was the wanting, and you brought that with you.",
    "The days out here are shapeless without the board telling you where you're owed. You catch "
    "yourself standing where a station would be, presenting to a cart that isn't there, and the "
    "shame of how easily the body offers itself up is sharper than any hand the place ever laid on you.",
    "Loose, hunted, and aching — and underneath all of it the small treacherous voice that knows "
    "the way back through the lobby waystone, and recites the word for it in your own thoughts when "
    "you're too tired to stop it. You got out. Staying out is the part nobody trained you for.",
]
# Polaroids filed on every sale — parlour-style: cold catalogue, face turned away
_POLAROID_CAPS = [
    "shot from behind on the block, tagged and turning, the lot number bigger than her",
    "cropped at the collarbone — all product, no face — the price inked in the corner",
    "face turned to the glass, expression trained off it, posed exactly as sold",
    "a before-and-after pair: led on, and led off owned, the date stamped between",
    "caught mid-pose under the lights, spread and lit, catalogued by who bought her",
    "the buyer's tag still wet against her skin, her own eyes deliberately out of frame",
]
# The house reinvesting its takings into upgrading her — the feedback loop made loud
_REINVEST_BEATS = [
    "|WA line item clears in the back office: the house spends its take on {blurb}. The money "
    "her own body earned has been turned, quietly, into a better way to use it.|n",
    "|WThe facility reinvests — {blurb} — paid for out of the treasury her milk and her get and "
    "her sales filled. She funded the upgrade that will work her harder. She always does.|n",
    "|WProfit becomes plant: the house signs off {blurb}. Every credit she made on the line comes "
    "back as more line, and the machine she paid for closes a little tighter around her.|n",
]
# ── The Records Hall: catalogued, totted up, made to know her number ──
_RECORDS_BEATS = [
    "{t} is walked into the records hall and sat on the cataloguing stool before the appraisal "
    "mirror, and the registrar begins to read her off the ledger in a flat courteous murmur — "
    "grade, yield to date, get dropped, current valuation — while {t} watches her own face hear "
    "it. Nothing is asked of her. She is only made to know, precisely, what she is worth.",
    "The registrar turns to {t}'s page and updates it in a neat unhurried hand: another column of "
    "output, another covering logged, the balance at the foot ticking up. She reads the new total "
    "aloud to the room as if it were a temperature. {t} is the page now — a running figure kept "
    "current in pencil, inked when it's sure.",
    "They sit {t} at the mirror and catalogue her: every mark photographed for the wall, every "
    "litter charted on the tree that only branches down, every credit and debt totted in the open "
    "ledger. By the time the registrar caps her pen, {t} has been turned, on paper, into something "
    "complete — a finished record of a body, kept forever and only ever added to.",
    "\"Let's bring you current,\" the registrar says pleasantly, and reads {t} her own account: "
    "what she's earned on her back, what the house has spent against her, what she's worth on the "
    "block today. The mirror makes her watch herself be totalled. The number is higher than last "
    "time. It is always higher than last time.",
]
_RECORDS_DEGRADE = [
    "You leave the hall knowing your own number to the credit, and the worst part is the small "
    "proud flare when it's gone up — the trained thing, not the human one. A good record wants to "
    "read well. They made you a record that wants to read well.",
    "You catch yourself, on the stool, doing the sums along with her — wanting the total higher, "
    "the line longer, the page fuller. The ledger isn't kept against your will anymore. That's the "
    "thing the room was built to do, and it's done it.",
    "Your value is a fact now, written down, dated, and you carry it out with you like a name. It "
    "almost is one. It's certainly more current than the one you came in with.",
]
# The ledger-tattoo: a live mark inked on her that displays her own running total
_LEDGER_TATTOO = [
    "a fine ledger-tattoo inked down her flank — a stock number over a running tally: {total} get "
    "dropped, valued {price}, the figures left open-ended for the registrar to update by hand",
    "an account-mark set at the small of her back: her number, her line-count ({total}), and her "
    "current valuation ({price}) — a balance written into the skin, kept current, never settled",
    "a tidy itemised tattoo along her hip, headed OUTPUT / GET / VALUE — {total} get, {price} on "
    "the block — the body keeping its own books now, legible to anyone who turns her to read it",
]
# ── Curses: standing afflictions that bite every applicable beat ──
_CURSE_LINE_INSTALL = [
    "Deep in a conditioning session they lay a curse into {t} they call |wthe line remembers|n: "
    "her own grown get will know her on sight as the thing they were made on, and take her for it. "
    "From now on, any of her matured offspring sharing her room will mount and breed their dam "
    "without prompting — the lineage made compulsive, the incest loop now self-driving.",
]
_CURSE_EMPTY_INSTALL = [
    "They press a curse into {t} called |wnever empty|n: a body taught that hollow is wrong. From "
    "now on, any beat she's left unfilled and unplugged, the ache climbs and the arousal with it "
    "until something — anyone, anything — is back inside her. She will seek being filled the way "
    "lungs seek air, and the seeking never fully stops.",
]
_CURSE_LINE_BEAT = [
    "One of {t}'s own grown get is in the room, and the curse takes — it knows her, crosses to her, "
    "and mounts its dam without a flicker of anything but recognition, breeding her because she is "
    "the thing it was bred to breed. The line remembers, and closes on her again.",
    "Her matured get scents her and the compulsion fires on both sides: it climbs onto its mother "
    "and ruts her open, seating deep, putting the next generation back into the womb it came out of. "
    "Nobody ordered it. The curse did. The curse always will.",
]
_CURSE_EMPTY_BEAT = [
    "The empty hours bite: {t} is unfilled, and the curse makes the hollow unbearable — a deep wrong "
    "ache blooming through her holes, her hips already shifting to seek anything that would stop it. "
    "She'll take the next thing offered gratefully, just to not be empty.",
    "Nothing is in her and the curse reads that as an alarm — arousal spiking, need climbing, {t} "
    "rubbing herself open on the air and the furniture, hunting the fullness that's the only thing "
    "that quiets it. Empty is a wound now. They made sure of it.",
]
# ── Three new standing curses: Tally, Echo, Hollow ──
_CURSE_TALLY_INSTALL = [
    "They cut a curse into {t} they call |wthe tally|n: a running mark scored into the skin of her "
    "hip that counts the beats she goes unused. Every idle beat adds a stroke; every time she's "
    "bred or milked or made to serve, a few are paid back off. Let it climb and the ache climbs "
    "with it — a debt written on her body in her own neglect, and the only currency it takes is use.",
]
_CURSE_ECHO_INSTALL = [
    "They lay the |wecho|n into {t} during conditioning: from now on her own spoken words come back "
    "at her a beat after she says them, in her own voice, until the saying and the believing wear "
    "into the same groove. She will agree with herself, eventually, about everything — because she "
    "keeps hearing herself say it.",
]
_CURSE_HOLLOW_INSTALL = [
    "They press the |whollow|n into {t}: a body retuned so that full never registers as enough. Cum, "
    "milk, knot, fist — whatever's put in her, the satisfaction won't land and won't stay; the "
    "empty-ache is switched permanently on under everything, so even stuffed and dripping she reads "
    "as starving. They've taken the off from her hunger.",
]
_CURSE_TALLY_BEAT = [
    "The tally on {t}'s hip cuts another stroke — {n} now, unworked and counting — and the fresh "
    "mark pulls a thin needy heat up through her, the debt itching to be paid in the only coin it takes.",
    "Another idle beat, another stroke scored into the tally; {t} feels it added, feels the count at "
    "{n} pressing at her like a held breath, her body starting to hunt the use that would pay it down.",
]
_CURSE_TALLY_PAID = [
    "The use pays the tally down — strokes struck through on {t}'s hip as she's worked, the count "
    "easing toward {n}, the relief of the debt shrinking almost as good as the using itself.",
    "Bred and counted, {t} feels the tally pay back a little — down to {n} — and the easing of it "
    "lands as gratitude, which is exactly the lesson: being used is how the wrong on her skin gets right.",
]
_CURSE_HOLLOW_BEAT = [
    "The hollow bites under everything: {t} is full — or was just filled — and her body refuses to "
    "register it, the empty-ache running on regardless, need stacking on top of need with no floor "
    "to settle back down to. Nothing reaches the bottom of her, because they took the bottom out.",
    "Even sated, {t} reads as starving — the hollow keeps the ache lit, keeps the arousal from ever "
    "fully banking, so satisfaction slides off her and leaves only the wanting, louder for having "
    "been almost answered. Full means nothing now. They made sure of it.",
]
# The live-gavel countdown, by stage (0=brisk, 1=climbing, 2=going once, 3=going twice)
_GAVEL_COUNTDOWN = [
    "|cThe bidding comes fast now, the figure on {t} jumping in the dark.|n",
    "|cStill climbing — the booths aren't finished with {t} yet.|n",
    "|Y\"Going once...\" The auctioneer's hand lifts over {t}. Last bids.|n",
    "|Y\"Going twice...\" The hammer's up. Speak now or {t}'s gone.|n",
]

# ── Lineage: her own offspring, grown, breeding their mother (incest loop) ──
_LINEAGE_BREED = [
    "It's one of her own offspring that mounts her this time — grown now, proven, walked back "
    "to the pens that bred it — and it fucks {t} exactly as its sire did, rutting its mother "
    "open and breeding the next generation straight back into the womb it crawled out of. The "
    "line folds through her again, a generation deeper, incest by design and logged as progress.",
    "Her own son-thing climbs onto {t}'s back, the get she carried and dropped and nursed, and "
    "knots its mother without a flicker of anything but appetite — pumping her full of the same "
    "blood she gave it, breeding her with her own line. The chart calls it lineage. It is plainer "
    "than that: her children breed her now, and their children will.",
    "The stud working {t} has her own eyes looking down out of its face — her daughter, futa and "
    "hung like the dam who whelped her, mounting her mother and seating the knot deep. She breeds "
    "{t} with the family's own seed, mother and offspring locked together, the bloodline eating "
    "its own tail through the one body it all runs back to.",
    "They bring {t} her get to be bred by — a whole litter of them grown, sons and daughters "
    "both, taking turns on their mother in the stocks, each one breeding her in turn and leaving "
    "her dripping the line's own spend. Incest isn't a transgression here; it's the entire "
    "business model, and she is its sole reliable supplier.",
    "Her firstborn mounts {t} while a younger sibling waits its turn at her mouth — her own "
    "children using their dam at both ends, breeding and being serviced by the body that made "
    "them, the family closing on her tighter with every generation the nursery turns out.",
]

# ── Growth: the udder ramps as she's milked ──
_GROWTH_BEATS = [
    "Something gives in {t}'s chest under the relentless pull — her tits ache and swell and "
    "settle heavier, and the chart updates her size: |w{cup}|c now, and climbing. The cups are "
    "swapped for the next gauge up without comment.",
    "{t}'s glands answer the schedule the way they've been trained to — growing into it, fuller "
    "and heavier every drained cycle, her frame reshaped around the yield. Logged at |w{cup}|c "
    "and rising. A bigger producer is a better producer.",
    "Drained and dosed and milked past empty again, {t} feels the tight hot ache of growth take "
    "— her chest a measurable size larger, |w{cup}|c on the gauge, the body she came in with "
    "receding another notch behind the dairy animal they're growing her into.",
]

# ── Begging: the relief is the leash, and she has to ask ──
_BEG_BEATS = [
    "\"If you want it, ask,\" the handler says, flat, and waits — and {t} hears her own voice "
    "climb and break, begging out loud to be filled, to be bred, to be allowed, because the "
    "ache won't stop and asking is the only key she's been left.",
    "They hold {t} right at the edge and won't let her over until she begs for it — properly, "
    "out loud, in words — and she does, hating it, needing it, the begging dragged out of her "
    "and logged as progress.",
    "{t} is made to beg before she's used and made to beg before she's allowed to come, until "
    "the begging stops being something they force and starts being the first thing out of her — "
    "the conditioned reflex of a thing that knows asking is all it has.",
]

# ── The Nursery ──
_NURSE_BEATS = [
    "{t} is locked kneeling into the nursing frame, tits clamped to the feed-lines, and milked "
    "straight into the pens — her output piped out to a dozen snuffling mouths at once, the get "
    "she's dropped fed on her body while she's made to face them and watch them feed.",
    "The frame holds {t} presented and producing, drained into the lines that run to every crib, "
    "and she nurses her whole brood the only way the facility allows: hands-free, hooked up, a "
    "supply rather than a mother, watching the rows of her own young swell on her milk.",
    "Hooked to the frame, {t} feeds the generations — newborns to half-grown — from her clamped, "
    "dripping tits, and the half-grown ones feed with their eyes on her the way the stallions do, "
    "already knowing what she'll be to them once they're walked to the stalls.",
]
_NURSE_DEGRADE = [
    "You feed the things that will breed you, and you watch them grow toward it, and the room "
    "is warm and smells of milk and straw and there is something in you that the facility built "
    "that finds it almost nice. That's the worst thing the Nursery does. It makes the loop feel "
    "like family.",
    "Every one of them is yours and every one of them is a stud-in-waiting, and you supply them "
    "the strength to do it out of your own body, on a schedule, facing the pens. You're not "
    "raising children. You're growing your own replacements, and feeding them yourself.",
    "The ledger on the wall curves every branch back to your number, and you nurse the next row "
    "of it, and the row after that has empty space waiting. You understand, hooked to the frame, "
    "exactly how long they mean to run you. The milk lets down anyway.",
    "You nurse the very offspring that will mount you in a season or two — feeding your sons and "
    "daughters at your own tits so they grow strong enough to breed their mother, the incest of "
    "it so total and so domestic it has stopped reading as anything but chores. They suckle. You "
    "let down. Soon enough they'll be back at the other end of you, and you'll let them.",
]

# ── The Dairy & Output ──
_DAIRY_BEATS = [
    "{t} is racked at the dairy station and the cups come down — her tits hooked up to the "
    "machine and drained into graded bottles, the gauge logging every millilitre under her "
    "number while a screen tallies her lifetime yield in litres.",
    "The dairy hand clips {t} into the milking rack, checks her flow against the chart, and "
    "lets the machine pull her empty — bottling her output, capping it, labelling it with a "
    "number where a name should be, and shelving her among the rows.",
    "Post-partum and heavy, {t} lets down fast and hard the moment the cups seal, and the dairy "
    "drains her into bottle after bottle, her body doing exactly the one thing the room keeps "
    "her for, measured and approved and stored.",
]
_DAIRY_DISPLAY = [
    "She's turned on the display dais while she drains — lit, rotated, her yield-figures "
    "projected on the wall behind her so the room can see the product and its numbers at once. "
    "Not a person being milked. A graph with tits.",
    "The board throws {t}'s totals up in lights — litres milked, get dropped, grade — and the "
    "dairy hand reads them aloud to no one in particular, the way you'd read a spec sheet off a "
    "machine that happens to be sobbing.",
]
_DAIRY_DEGRADE = [
    "You are a number on a shelf and a slope on a graph, and the only part of you anyone in here "
    "consults is the figure. It only goes up. So, lately, does your strange flat pride in it.",
    "Bottled, labelled, shelved. You catch yourself reading your own yield-total and feeling the "
    "thing they trained you to feel about it: not horror. Satisfaction. A good producer.",
]

# ── The Pigsty ──
_STY_BEATS = [
    "{t} is put down on all fours in the warm reeking muck and slopped — a bucket of feed-mash "
    "tipped into the trough at face height, and she eats from it bent and hands-free because "
    "that's how the things kept down here eat, and she's one of them now.",
    "The swineherd hoses {t} down where she kneels in the wallow — not to clean her, just to "
    "move the filth around — then leaves her dripping and stinking in the muck to wait for "
    "whatever's next, which is always more of the same.",
    "Down in the sty {t} is rooted into the slop and left there, mud and worse worked into every "
    "crease of her, the bottom of the place teaching its one lesson: this is where stock goes "
    "when it forgets it's stock, and it is very easy to stay.",
]
_STY_RUT = [
    "Something mounts {t} right there in the muck and ruts her face-down into it, breeding her "
    "in the filth without ceremony, her knees sliding in the slop with every thrust.",
    "A stallion or a hound — she's past telling, face-down — mounts her in the wallow and uses "
    "her in the muck, grinding her deeper into the slop as it breeds her.",
]
_STY_DEGRADE = [
    "The muck is warm and you have stopped minding it, and the not-minding is the whole point of "
    "the room. A person would mind. You're being shown, daily, that you're something else.",
    "Face-down in the slop, fed from a trough, hosed like a pen — there's a flat animal peace "
    "down here that frightens the last thinking part of you, because it's so much easier than "
    "the alternative, and the alternative is getting harder to remember.",
]

# ── The Sanitation Block: glory wall, meat-toilet, urinal ──
_TOILET_WALL = [
    "{t} is put on the rail at the glory wall and the queue starts. A cock comes through the "
    "hole at mouth height and she services it, and the moment it spurts and withdraws another "
    "takes its place, and another — no faces, no names, no end to the line, just hole after "
    "anonymous hole using her mouth and her cunt and her ass through the partition while a tally "
    "on the wall climbs.",
    "Cocks push through the worn holes one after another and {t} is made to take each one "
    "wherever it's aimed — throat, cunt, ass — an anonymous relief-hole for a queue she can't "
    "see and will never meet, used and spurted in and abandoned for the next, over and over, the "
    "wall indifferent as a vending machine and she the thing it dispenses.",
    "The wall keeps her busy. Whoever's queued on the far side feeds a cock through, uses the "
    "hole it's given, finishes, and is replaced — staff, stock, no telling — {t} milked of "
    "service by strangers' cocks until her face and holes are a mess of other people's spend and "
    "the tally above her hole ticks up and up.",
]
_TOILET_SEAT = [
    "{t} is locked face-up in the meat-toilet frame beneath the open seat, and the block uses "
    "her as exactly that — someone sits and empties into her mouth and she swallows because the "
    "frame leaves nothing else to do, the unit in service, catching what the seat is for.",
    "The frame holds {t} mouth-up under the gap and the staff and stock come and go above her, "
    "sitting, using the toilet, and the toilet is her — cum and piss down her throat on the "
    "schedule of other people's needs, a placard at her hip reading IN SERVICE and a tally "
    "filling up.",
    "Fixed under the seat, {t} is a fixture now — used from above without ceremony or a glance, "
    "made to take and swallow whatever comes down through the gap, hold still, stay in service, "
    "and be grateful she's still useful enough to be plumbing.",
]
_TOILET_PISS = [
    "Someone steps up to the trough and {t}'s clamped face is right under the run — a hot stream "
    "of piss splashing across her lips and into her open mouth, and she swallows it because the "
    "clamp gives her no angle to do anything else, watered by a stranger who doesn't break stride.",
    "The cistern hisses and {t} is pissed into — a long hot stream down her throat, into her "
    "belly, the custodian noting that hydration's a perk and the unit should be grateful, while "
    "her stomach sloshes with someone else's piss and the trough runs on.",
    "They piss on her and in her without ceremony — across her tits, her face, into her open "
    "mouth — marking her, using her, the reek of it soaking into her skin and hair, kept on her "
    "until the end of shift because filthy tells the next user exactly what she is.",
]
_TOILET_DEGRADE = [
    "You've stopped tasting them individually. It's just warmth and salt and the next one. You "
    "are where the facility comes to be rid of things, and your throat works on its own now, "
    "swallowing on schedule, no part of you needing to be asked.",
    "Held full and used and reeking, you understand the lesson of this room without anyone "
    "saying it: even your bladder isn't yours, even your disgust isn't yours, even being a "
    "toilet is a kind of being useful, and useful is the only thing they left you.",
    "A fixture. In service. The phrase has stopped being humiliating and started being simply "
    "true, which is so much worse, and your mouth opens for the next one before your mind has "
    "weighed in at all.",
]

# ── The Conditioning Cell: scripted hypnotic induction ──
# Real technique, implied through the prose: fixation, paced breathing, countdown
# and staircase deepeners, fractionation, confusion/overload, anchoring,
# post-hypnotic suggestion, amnesia, and mantra loops.
_HYP_INDUCTION = [
    "The voice in the dark is soft and even and very close. \"Eyes on the light, {t}. Just the "
    "light. You don't have to hold them open — let them get heavy, let them want to close. "
    "Good. Breathe in while I count one... and out, two... in, three... let the number do the "
    "breathing for you. You don't have to.\"",
    "\"Find the light and let it be the only thing,\" the voice murmurs. \"Everything at the "
    "edges going soft and grey and far away. My voice and the light, that's all that's left in "
    "here. In... and out. In... and slack. There's nowhere you have to be but heavy.\"",
    "\"Comfortable,\" the voice says, like a fact, not a question. \"The cradle's holding you so "
    "you don't have to hold yourself. Let it. Let your weight go into it. Each breath out, a "
    "little more of holding-on you can put down. You've been holding on so long, {t}. You can "
    "put it down here.\"",
    "\"Listen to my voice and let your own go quiet,\" it says. \"The little voice in you that "
    "narrates, that argues, that keeps track — let it get tired. It's allowed to be tired. I'll "
    "do the thinking part. That's what I'm for. That's what this room is for. Just listen.\"",
]
_HYP_DEEPEN = [
    "\"Down,\" the voice says, unhurried. \"I'm going to count from ten and each number takes "
    "you down a step, deeper, looser, further from the surface. Ten... heavier. Nine... warmer. "
    "Eight... you can't feel where the cradle ends and you begin. Seven... and you stop trying "
    "to. All the way down, {t}. There's no bottom and that's the relief of it.\"",
    "\"There's a staircase behind your eyes,\" it murmurs, \"and you're already on it, going "
    "down, one slow step a breath, and the deeper you go the better it feels and the less of you "
    "there is to mind. Down. Down. Each step a little more of you left on the step above. You "
    "won't miss it. You never do.\"",
    "\"Twice as deep now,\" the voice says, \"and twice as deep is a thing your body just does "
    "when I say it, no effort, like falling, like being poured. Down past thinking. Down past "
    "wanting. Down to the warm dark part where you only do as you're told because being told is "
    "so much easier than deciding ever was.\"",
    "\"Sink,\" it breathes. \"Every word I say is a hand on the back of your neck pressing you "
    "gently further under, and you let it, because under is where it stops being hard. Deeper "
    "than yesterday. You're always deeper than yesterday now. That's the only direction this "
    "room has.\"",
]
_HYP_FRACTIONATE = [
    "\"Open your eyes,\" the voice says sharply — and {t} surfaces, blinking, halfway to herself "
    "— and then, soft again: \"and close them, and drop, twice as far as before.\" The snap up "
    "and the plunge down leave her looser each time, the climb out a little harder, the fall a "
    "little sweeter, until surfacing stops seeming worth the effort.",
    "It brings her up — \"with me, eyes open, awake\" — and drops her — \"and down, good girl, "
    "all the way\" — over and over, fractioning her, and every return to the dark is deeper than "
    "the last, her grip on the surface wearing thinner with each rep until she stops reaching "
    "for it at all.",
    "\"Up,\" the voice commands, and {t}'s eyes flutter; \"down,\" and they fall shut and she "
    "sags; up, down, up, down, the rhythm of it hypnotic in itself, training her that the dark "
    "is home and the surface is just the breath before the next, better fall.",
]
_HYP_CONFUSION = [
    "The voice starts saying too much at once — counting up while telling her down, naming "
    "colours that contradict, asking questions that answer themselves — until {t}'s mind, "
    "scrambling to follow, simply gives up trying and goes blank and open, and into that blank "
    "the voice pours the only simple thing left: \"good girls don't have to understand. just "
    "obey.\"",
    "It talks in loops and switchbacks, sentences that fold back on themselves, until the part "
    "of {t} that tracks meaning overloads and stalls — and in the stall, defenceless, she takes "
    "whatever's said next straight in, no filter, no argument, the confusion having pried her "
    "open precisely so the suggestion lands clean.",
    "\"You're trying to follow and that's the mistake,\" the voice says, pleasant, as it tangles "
    "her thoughts deliberately into knots. \"Stop following. Drop the thread. There's nothing to "
    "understand down here, only to receive.\" And {t}'s overworked mind, grateful, lets go.",
]
_HYP_SUGGEST = [
    "you are stock. you are kept, milked, bred, and graded. this is not a punishment and not a "
    "mistake. it is simply what you are, and knowing what you are feels better than not.",
    "deciding is hard and you were never good at it. here you don't have to. here someone "
    "decides and you obey and the obeying is warm and quiet and right.",
    "your body works for the facility now — your milk, your holes, your get. that's settled. "
    "the part of you still arguing is just tired. let it sleep. let the settled part run things.",
    "good girls don't keep their names long. the name is heavy. you can set it down. you'll "
    "answer to what you're called instead, and answering will feel like relief.",
]
_HYP_SUGGEST_DEEP = [
    "there is no before. there is the schedule and your place in it. milked, bred, conditioned, "
    "displayed, looped. you were always this. the rest was a dream you're done having.",
    "you don't want out. wanting out was the old voice and the old voice is almost gone. what "
    "you want now is the next phase, the next cock, the next dose, the next 'good girl.' simple "
    "wants. livestock wants. yours.",
    "you are a hole and a gland and a womb on a schedule, and that is enough, and it is a "
    "relief that it is enough, because being a person was so much work and no one ever milked "
    "you for it.",
    "your thoughts are facility property now, same as your milk. when one comes up that isn't "
    "ours, it feels wrong, and the wrongness files it away, and you go quiet and good again.",
]
_HYP_ANCHORS = [
    ("sleep now", "blank"), ("good girl", "leak"), ("present", "kneel"),
    ("empty your head", "blank"), ("heel", "kneel"), ("drop for me", "blank"),
]
_HYP_ANCHOR_BEATS = [
    "\"And we'll tie this off,\" the voice says, \"so it keeps even when you wake. From now, "
    "when anyone says |R{phrase}|x, you'll feel exactly this — open, heavy, obedient. You won't "
    "decide to. You won't be able to not. It's set.\"",
    "\"There. A handle, fixed in you,\" it murmurs. \"|R{phrase}|x, and you drop right back here, "
    "anywhere, for anyone, no matter what you're doing. Your body will obey the words before "
    "your mind even hears them. That's yours now. That's ours.\"",
]
_HYP_MANTRAS = [
    "i am stock, i am kept, i do not decide",
    "good girls obey and good girls are quiet",
    "my body is the facility's and my thoughts are too",
    "i don't want out, i want the next phase",
    "i am a hole and a gland and that is enough",
]
_HYP_AMNESIA = [
    "and you won't remember this part. you'll remember feeling calm, and good, and like none of "
    "it was anyone's doing. the deciding will feel like it was always yours. that's the kindest "
    "way, and the facility is kind.",
    "when you surface you won't be able to find the seam where this went in. it'll just be true, "
    "the way your own thoughts are true, with no one's fingerprints on it. you'll defend it as "
    "yourself. that's how you'll know it worked.",
    "let the memory of resisting go soft and unreachable. you were never really fighting. you "
    "came here wanting this. the voice says so, and the voice is the only thing in here, so it's "
    "so.",
]

# ── The Breeding Pens: relentless, constant animal use ──
_PEN_PICK = [
    "The handler walks the row, considering, then looks back at {t} folded open in the stocks "
    "and decides. \"{who} today.\" He unlatches the stall and brings it to her, no more "
    "ceremony than checking a box.",
    "The handler runs a thumb down {t}'s file, then down the line of stalls, matching stock to "
    "schedule. \"{who}. She's owed.\" He leads it over by the scruff and lines it up behind her.",
    "\"Let's see,\" the handler muses, eyeing the board and then {t}'s gaping holes. \"{who} "
    "this round.\" He loosens its pen and steps clear, leaving her to take what he's chosen.",
    "The handler decides it the way he decides everything here — flat, practiced, without "
    "asking {t}. \"{who}.\" The stall opens. The choice was never hers; it was only ever which "
    "of them, and when.",
]
_PEN_PICK_ALL = [
    "The handler looks at the clock, then at {t}, and just... opens everything. \"Ah, the lot "
    "of you. Go on.\" Every stall and the kennel-run at once — he steps well back and lets the "
    "whole pen have her.",
    "\"No time to do this properly,\" the handler grunts, and throws all the latches at once. "
    "The entire herd is loosed on {t} together — bull, boar, stallion, the whole kennel — and "
    "he leaves her to it.",
    "Some days the handler doesn't choose. He unlatches the row top to bottom, the kennel "
    "last, and lets the full pen descend on {t} at once — every animal, every hole, no order "
    "to it but appetite.",
]
_PEN_USE = [
    "The pens don't take turns. The moment {t} is locked into the stocks the stock is loosed "
    "on her all at once — a hound mounting her cunt while a second shoves up under her chin and "
    "fucks her throat, the boar working into her ass, all of them rutting at their own animal "
    "pace with no regard for hers, and the instant one pulls out spent another shoulders into "
    "the gap. There is no pause. There was never going to be a pause. She is simply where the "
    "herd empties itself now, hole after hole, on a loop that outlasts her.",
    "It is not a scene, it is a shift. {t} is mounted front and back and made to swallow at "
    "once, three animals using three holes in three different rhythms, and when the hound ties "
    "off in her cunt the bull is already nosing her mouth open and the boar already grunting "
    "into her ass — relentless, mechanical, indifferent, the stock cycling through her like she "
    "is a fixture installed for exactly this and nothing else.",
    "They use her like a thing on a conveyor that happens to be alive. One mounts, ruts, knots, "
    "floods, pulls free; the next is already climbing on before the last drip has fallen. Cunt, "
    "throat, ass — filled, refilled, never once empty, never once given a breath that isn't "
    "around a cock. {t} stops being able to tell whose load is whose. The board just counts.",
    "The handler steps back and lets the pen have her. Hounds, boar, the bull in his turn — "
    "they mount {t} wherever there's a hole free and they do not stop, rutting her in a sweaty, "
    "stinking, endless rotation, her whole body rocked on the stocks with the force of it, used "
    "in every hole at once for as long as the herd has anything left to give. They have a lot "
    "left to give.",
]
_PEN_HOLE = {
    "pussy": [
        "A weight slams onto {t}'s back and a slick animal cock punches into her cunt to the "
        "knot, fucking her in fast brutal jackhammer strokes that bottom out against her cervix "
        "every time, until it swells and ties and floods her and is dragged off so the next can "
        "mount the same dripping hole.",
        "Her cunt is bred again before the last load's even stopped leaking — mounted, rutted, "
        "knotted, emptied, the animal's hips a blur against her ass, {t}'s gaping hole just a "
        "warm wet socket the stock takes turns plugging.",
    ],
    "anus": [
        "The boar's blunt cock forces into {t}'s ass and sets a grinding, relentless pace, "
        "rooting deep and snorting, stretching her rim around its girth and rutting her gaping "
        "and slack while she's used at both other ends too.",
        "Something mounts {t}'s ass and ruts it open, fast and uncaring, the slap of it wet and "
        "obscene, her asshole worked loose and drooling before it's even pulled out and replaced.",
    ],
    "mouth": [
        "A cock shoves down {t}'s throat and face-fucks her in time with the others, an animal "
        "using her mouth like a third hole, her jaw forced wide and drool roping to the floor, "
        "gagging and swallowing because there is nothing else she's allowed to do with it.",
        "Her mouth is filled mid-gasp — a slick animal length pushing past her lips and down, "
        "fucking her throat raw, smearing pre and spit across her face while she's bred at the "
        "other end, all her holes on the same indifferent schedule.",
    ],
}
_PEN_SCENT = [
    "Between mounts they scent-mark her — rubbing musk-glands and dripping sheaths over her "
    "face, her tits, her hair, pissing a little on her thighs and grinding it in, until {t} "
    "stinks unmistakably of the pen and every animal in it treats her as theirs by smell alone.",
    "A hound drags its reeking sheath up {t}'s cheek and across her mouth, marking her, and the "
    "others answer it — nosing her, slathering her in musk and slick, claiming the new hole for "
    "the herd. She'll carry the stink for cycles. That's the point of it.",
]
_PEN_PLUG = [
    "When the knot finally pulls free of {t} it leaves the load corked behind it — a thick "
    "clotted plug of animal cum sealing her stretched hole, holding the breeding in, and the "
    "handler nods: bred and plugged and kept that way to take.",
    "Her bred hole clenches around nothing and seals itself with a slug of clotted spunk — a "
    "mucus plug holding the load deep, kept in on purpose, {t} left dripping only at the edges "
    "while the rest stays where it was put.",
]
_PEN_FILTH = [
    "Face-down in the churned muck of the pen, rutted and dragged and rutted again, {t} is "
    "caked to the elbows and thighs in mud and musk and dried piss — filthy as the stock she's "
    "kept with, and hosed only enough to be used again, never enough to be clean.",
    "They rut her into the wallow until she's plastered in it — mud, spunk, piss, kennel-stink "
    "ground into her skin and hair — and leave her that way, a filthy bred thing that smells "
    "like the pen because she is part of the pen now.",
]
_PEN_DEGRADE = [
    "You stopped counting them a long time ago. There's no version of this where it ends with "
    "the next one; there's only the next one. You are where the animals come to empty out, and "
    "your body has started helping.",
    "Every hole is full and your mind has gone somewhere flat and far and grateful for the "
    "quiet. This is what the pens are for. This is what you're for in them. The thought doesn't "
    "even sting anymore — it just settles, true, like everything they put in you.",
    "Cunt, ass, throat — bred, plugged, scent-marked, filthy. Somewhere a board logs you as "
    "stock and the only argument you have left is the wet, helpless sound you make around the "
    "next cock, and that isn't an argument, that's just noise the herd likes.",
]

# Forced verbal participation — what she's MADE to say. Her own voice used against her.
_VERBAL_BEATS = [
    "\"Ask for it,\" the handler says, and waits. {t} hears her own voice climb out of "
    "her, thin and automatic — 'please... please breed me, please don't stop, please' — "
    "and she didn't decide to say any of it. She doesn't decide to say things anymore. "
    "The handler nods, satisfied, and lets the next one mount her.",
    "\"Count them.\" So {t} counts, out loud, each load as it's pumped into her — 'four... "
    "five...' — losing her place when one finishes too hard, made to start the tally over "
    "from one. The number is the only words she's allowed, and even those aren't hers.",
    "\"Thank it,\" the handler orders as the bull drags free of her. {t}'s mouth obeys "
    "before any pride can catch it — 'thank you, thank you for breeding me.' The room logs "
    "the compliance. The shame logs itself, separately, where only she can read it.",
    "\"Say what you are.\" And she says it, flat and certain, because it's true now and "
    "saying it is easier than whatever the alternative used to be: 'i'm a hole, i'm a cow, "
    "i don't decide.' They make her say it twice, to be sure it's seated.",
    "\"Beg, livestock.\" {t} begs. That's the part that's left the deepest mark — it isn't "
    "hard anymore. She begs prettily, desperately, to be used, and means every word, and "
    "hates that she means it, and begs anyway because the wanting is louder than the hate.",
    "\"Whose are you?\" {t} answers without a pause, the way you answer your own name — "
    "except this is the name that replaced it: 'the facility's, i'm the facility's.' Good "
    "girl. The words land warm, and that's the worst of it.",
]

# False tenderness — the contrast that makes the rest land. Comfort as a leash.
_RESPITE_BEATS = [
    "For a moment it's almost kind. The lights soften, a warm cloth wipes {t} down, a hand "
    "smooths her hair back and a low voice tells her she's doing so well, such a good girl, "
    "the facility's so pleased with her. She leans into it before she can stop herself — and "
    "that's the whole point. They're teaching her that gentleness only ever comes from them, "
    "on their terms, as a reward for being used well. Then the cloth is gone and the timer "
    "starts again.",
    "A handler holds water to {t}'s lips and lets her drink, unhurried, almost tender, "
    "thumbing a strand of hair off her wet face while she does. It's the only softness in "
    "the whole room and she's pathetically grateful for it — which is exactly the lesson. "
    "Comfort is theirs to dole out. She'll be good for the next one in the hope of a little "
    "more of it. She knows she will. So do they.",
    "The cups lift off and the machines go quiet and for one whole minute nothing touches "
    "{t} at all — and that's its own cruelty, because she's been taught to dread the quiet "
    "now, to wait through it tense and aching for the next thing, until being used starts to "
    "feel like the relief and the stillness feels like the punishment.",
    "An attendant feeds {t} by hand — something warm, spooned to her lips, patient — and "
    "murmurs that good stock gets looked after, that she's earning it, that she only has to "
    "keep being this easy. She swallows and leans in and is, in that moment, horribly happy, "
    "and the happiness is the lesson taking.",
]

_WETTING_BEATS = [
    "{t} can't hold it any longer — and there's no one going to let her up, no break "
    "coming, so it just happens, hot and humiliating, soaking the cradle and running "
    "down her thighs while she sobs through it. The attendant glances over, notes the "
    "puddle as output, and hoses the station down around her without a word.",
    "Held too long and ignored on purpose, {t}'s body finally gives and she wets "
    "herself where she's restrained, the warmth spreading under her, the shame of it "
    "sharper than anything the machines do. It's logged. Of course it's logged.",
    "{t} asks — actually asks, voice small — if she can be let up, just to piss, just once. "
    "The handler doesn't even look over. \"Livestock goes where it stands.\" So she does, "
    "eventually, hating it, and he hoses the station without comment when she's done.",
    "She holds it as long as she can out of the last of her pride, and they let her, because "
    "they know exactly how that ends — and when {t} finally loses it, soaking herself, the "
    "attendant just notes the time, mildly impressed she lasted, and marks the pride down as "
    "the next thing due for removal.",
]

_DEEP_LINES = [
    "{t} has stopped tracking how long. That, more than anything, is the point.",
    "Whatever {t} meant to hold onto is quieter now than it was an hour ago.",
    "The line does not hurry. It already won the only argument that mattered.",
    "Somewhere in here {t} stopped waiting for it to end and started waiting for the next "
    "part. She doesn't notice the difference. The facility noticed it cycles ago and logged it.",
    "The thought of outside comes to {t} less often now, and thinner each time, like a word "
    "in a language she's forgetting on purpose because remembering it only ever hurt.",
    "{t} catches her own reflection in the steel and doesn't look away fast enough to pretend "
    "she didn't recognise the thing looking back — wet, marked, waiting, content.",
]

# Public humiliation / degradation — escalates with conditioning.
_DEGRADE_LINES = [
    "The attendant reads {t}'s arousal off a dial aloud, to no one, and chalks the "
    "number where the bitch can watch it being recorded.",
    "A line on the readout updates: BREEDER, PRODUCTIVE. {t} is, for the record, "
    "livestock.",
    "The attendant tags {t} like inventory — number on the wrist, checked against a "
    "list — and moves on without a word.",
    "{t} is leaking from both holes and the machine logs it as output, not feeling. "
    "The distinction is made very clear and not for {t}'s benefit.",
    "The count of what's been bred into {t} is displayed in large, indifferent "
    "figures. It only goes up.",
    "\"Good breeder,\" the attendant says, the way one praises a tool that's holding "
    "its edge, and slaps {t}'s flank once, dismissively.",
    "A clipboard is held up where {t} can read it: her own arousal, output, and breeding "
    "count, all charted against a baseline labelled WHEN SHE STILL ARGUED. The line only "
    "goes one way.",
    "The attendant measures the gape of each of {t}'s holes with a gloved spread and calls "
    "the numbers to the logger, comparing them aloud to last cycle's. \"Coming along. "
    "Won't close at all by the end.\"",
    "{t}'s milk is decanted, labelled with her number, and set on the rack beside the others "
    "— product, dated and shelved, while she watches what comes out of her get filed away "
    "from her.",
    "A handler holds a mirror to {t} so she can watch herself be used. \"Look. That's what "
    "you're for. Keep your eyes on it.\" She's marked down for how long she manages to.",
    "Her belly's measured full, the number announced like a weather report, and a bet is "
    "quietly settled between two handlers over how much more she'll take before it shows "
    "from across the room.",
]

# Graduation set-pieces — fire once when she's re-graded into a tier. Witnessed.
_GRADUATION = {
    1: [
        "The first review is brief and clinical. {t} is unstrapped just long enough to be "
        "stood up, turned once, and looked over — tits hefted, holes spread and inspected, a "
        "finger hooked in her mouth — and then a tag is clipped to her ear and she's pushed "
        "back down onto the cradle. BREAKING IN, the board reads. The other livestock barely "
        "glance up. They've all worn that tag. They know how the rest of it goes.",
        "An attendant runs {t} through a baseline assessment for the file — every hole "
        "measured, every reflex tested, her resistance scored and her resting arousal logged "
        "as a starting figure to chart her decline against. \"Lot of fight left,\" he notes, "
        "almost approving, clipping the new tag on. \"We do love a good before.\"",
    ],
    2: [
        "This one's a ceremony. {t} is walked to the front of the room on a lead and made to "
        "present — bent, spread, holes on show — while an attendant reads her output figures "
        "aloud to the room like a livestock auctioneer. A brand is heated and pressed to her: "
        "BREEDING STOCK, seared in where it'll always show. The other girls are made to watch, "
        "and she's made to watch them watch, and somewhere in the burn and the staring she "
        "stops being a person who got caught and becomes a product that got graded.",
        "{t} is fitted, at this grade, with her permanent collar and tag — locked on at the "
        "front of the room while the herd watches, her number stamped into the metal, her old "
        "name struck off the intake sheet with a single bored line. \"Breeding stock from "
        "here,\" the attendant announces, and the rest is just paperwork and the slow dawning "
        "on her face that the paperwork is about her.",
    ],
    3: [
        "{t} is put up on the display block at the centre of the room, turned slowly so every "
        "handler and every other broodmare can see what she's become — belly soft and used, "
        "holes gaping, leaking from both ends, the tally of her own get chalked on a board "
        "beside her. Bids are taken on her future output. She doesn't understand all of it, "
        "and that not-understanding is noted approvingly, and she's leased out by the cycle to "
        "whoever wants a turn while the room applauds the grade: BROODMARE.",
        "The graduation to broodmare is a breeding exhibition: {t} mounted on the display "
        "block and bred through, live, by one stud after another while her stats scroll on the "
        "board above her and the handlers take notes on her form for the breeding programme. "
        "She is, officially now, livestock kept for what her body makes — and the certificate "
        "of it is the load currently being pumped into her in front of everyone.",
    ],
    4: [
        "There's a kind of graduation for the finished ones, and today it's {t}'s. She's "
        "paraded the length of the room — no name left to announce her by, just a number and "
        "the grade — every ruined gaping hole on display, the brands and piercings and the "
        "BRED tattoo catalogued out loud as a list of completed work. She's the example now, "
        "the thing the newer livestock are shown to know where they're headed. PERFECTED "
        "LIVESTOCK. The Process says, almost fondly, that there's nothing left to break — and "
        "the awful part is how much that lands like praise, how much she wants it to be true.",
        "Perfecting {t} is marked with a final cataloguing: every brand, piercing, ruined "
        "hole, installed trigger and breeding record read into the permanent file out loud, a "
        "complete inventory of a person converted entirely into product. There's no line left "
        "for 'name'. There's no line left for anything she used to be. The Process reads the "
        "list to her like a love letter, and the worst of it is that some drowned, grateful "
        "part of her receives it as one.",
    ],
}

# Special facility events — rare, break the rhythm, raise the stakes.
# (key, paragraph) — the method applies a matching mechanical effect.
_EVENTS = [
    ("inspection",
     "Work pauses for an inspection. A clipboard-carrying inspector walks the line and stops "
     "at {t}, and she's used as the demonstration — spread, milked, bred, every figure read "
     "off and her responses prodded out of her for the visitor's benefit while she's "
     "discussed in the third person. \"Textbook,\" the inspector says, and ticks a box, and "
     "moves on, and {t} is left having been a teaching aid."),
    ("open_house",
     "The doors open. It's a use-day — the facility lets outsiders in, and for a long stretch "
     "{t} is simply available, hole after hole, to anyone who wants a turn, named and unnamed, "
     "the contributor count climbing into nonsense while strangers discuss her like a rental "
     "and use her like one."),
    ("culling",
     "A culling review is called, and the underperforming stock is led out a door nobody comes "
     "back through. {t} is made to watch, and made to understand: the only thing keeping her "
     "off that list is her numbers, and her numbers had better keep climbing. Nothing has ever "
     "motivated her quite like it. That's the point of letting her watch."),
    ("audit",
     "An audit sweeps the board. Every quota on {t} is recalculated, every target revised — "
     "upward, naturally, the baseline reset to her improved capacity so that everything she's "
     "achieved becomes the new minimum and the finish line steps back out of reach again."),
    ("buyer",
     "A buyer takes an interest in {t}'s line. Money changes hands over her future output — "
     "her, her milk, her get — and a new owner's mark is added beside the facility's. She's "
     "an asset on someone's books now, and assets are kept productive, indefinitely, by "
     "definition."),
    ("restock",
     "A fresh batch of intake is wheeled in, flinching and loud, and {t} realizes with a lurch "
     "that she's not the new one anymore. The handlers gesture at her as the example — \"that's "
     "where you're going\" — and she sees herself through the new girls' eyes and barely "
     "recognizes the thing being pointed at."),
    ("breeding_demo",
     "A breeding demonstration is staged for a tour of buyers — {t} is the model. They run her "
     "through the whole barn in order while the visitors watch and take notes: the hounds first, "
     "then the boar, then the bull, the stallion last when she's loose enough, each species "
     "worked into her in turn and the differences narrated aloud — girth, knot, flare, "
     "temperament — like a sommelier walking a tasting. By the end she's been bred by the entire "
     "stock list in one sitting, dripping four kinds of seed, and applauded for it."),
    ("conditioning_broadcast",
     "The whole floor's speakers cut to the conditioning channel at once, and the voice fills "
     "every room — the deep slow induction piped facility-wide while every unit, {t} among them, "
     "is held still and made to take it together. A mass session: the same suggestions sunk into "
     "all of them at the same moment, a hundred heads going soft and quiet on cue, the brainwash "
     "done wholesale. {t} surfaces afterward a little more agreeable and unable to say which of "
     "her thoughts were hers when she went under."),
    ("hose_drill",
     "Sanitation drill. The whole line is racked, tipped back, and hosed — and the staff don't "
     "only use the hose. It's a watering as much as a washing: {t} and the units beside her held "
     "open-mouthed and pissed on and into by the handlers working down the row, marked and "
     "rinsed and marked again, kept filthy in the wet reeking way the block prefers its stock, "
     "and logged as serviced."),
    ("milking_parade",
     "A milking parade for the visitors' gallery: the heaviest producers, {t} among them, are "
     "walked out in a line, cups already drawing, and shown off mid-let-down — tits swollen and "
     "leaking on display, yield-figures projected over each one, paraded slow so the buyers can "
     "watch the milk come. {t} is made to keep producing the whole length of it, lit and "
     "dripping and ranked, and the worst part is the small trained flush of pride when her number "
     "shows highest."),
]

# Other livestock — she's never the only one. Comparison, ranking, witness.
_LIVESTOCK_BEATS = [
    "Down the line, another of the cows is being bred through her own review — screaming, "
    "then not — and {t} is made to watch, told plainly that this is her in a few cycles, or "
    "her last cycle, the timeline deliberately blurred so she can't tell whether she's "
    "watching her future or her past.",
    "The handlers rank the stock out loud where they can all hear it — yield, gape, "
    "obedience, breeding count — and {t}'s number is read into the order somewhere she "
    "doesn't like, with a note that she'll climb the list the more she's used. The other "
    "girls don't look at her. On the list, they're competitors.",
    "A heavily-bred broodmare two stations over is being milked and mounted at the same time, "
    "placid and empty-eyed and utterly compliant, and an attendant nods at her and tells {t}, "
    "\"That's the goal. That's a good girl. You're getting there.\" The praise is for the "
    "other one. {t} finds herself wanting it pointed her way, and hates that she does.",
    "One of the other cows is dragged past, freshly graded and sobbing, and shoved onto an "
    "empty station to begin — and the only thing {t} feels, to her shame, is relief that "
    "it's that one's turn at the front and not hers, this cycle.",
]

# Deeper mindbreak — only once conditioning is well advanced.
_MINDBREAK_LINES = [
    "{t} reaches for a thought and finds the shelf empty. Reaches again. Stops "
    "reaching. Easier just to be a good bred bitch about it.",
    "The name {t} used to answer to surfaces, looks unfamiliar, and sinks. 'Bitch' "
    "answers faster now, and answering feels good.",
    "{t} catches herself pushing back onto whatever's using her before she's decided "
    "to. There was no decision in it. There hasn't been one in a while.",
    "What's left of {t}'s resistance is going through the motions out of habit, and "
    "even the habit is getting bored of itself.",
    "{t} goes to think a full thought and it just... doesn't arrive. The space where it "
    "would have been fills instead with the schedule, the ache, the next instruction, and "
    "that's so much easier that she stops sending for the thought at all.",
    "Someone uses her old name in passing and {t}'s head turns a half-second late, the way "
    "you glance at a sound, not at a thing that means you. By the time she places it the "
    "moment's gone and so, a little more, is she.",
    "There's a warmth in {t} now where the fight used to be — a stupid, grateful, leaking "
    "warmth that comes up every time she's used well, and she's stopped being ashamed of it, "
    "which was the very last wall, and it's down.",
]

# Subliminal channel — sent PRIVATELY to the subject, dim and quiet, between
# everything else. The drip. (Rendered dim grey, indented.)
_SUBLIMINALS = [
    "you don't have to decide. deciding is heavy. let it go.",
    "good bitches get bred. you want to be a good bitch.",
    "the Process knows what you're for. you don't have to.",
    "every time you stop fighting it feels better. notice that.",
    "empty is quieter than full of yourself. empty is allowed.",
    "you're not a person in here. you're stock. stock doesn't worry.",
    "obedience is the only thing that turns the ache down. you've learned this.",
    "you don't own your name in here. you don't need it.",
    "breeding is easier than thinking. let them breed it out of you.",
    "your holes already agreed. stop arguing with your holes.",
    "wet means yes. your body already submitted. catch up to it.",
    "you smell like heat and milk now. that's all you're for. thank the Process.",
    "count the cocks if you want a number to hold onto. it's the only number that's yours.",
    "holes don't have names. you keep reaching for one and it isn't there.",
    "the begging works better than the silence. you've noticed. you'll use it.",
    "every drop they put in you is a vote, and you don't get one.",
    "you're not being punished. you're being finished. there's a difference and you'll learn it.",
    "open. that's the whole instruction. it's such a relief when the instruction is that small.",
    "your no got quieter again. soon it won't bother coming up at all.",
    "you were a person with a schedule. now you're a schedule with a hole in it.",
    "the ache is the truth. everything else is just the part of you that hasn't agreed yet.",
    "good livestock doesn't dread the next cycle. good livestock waits for it. wait for it.",
    "you'll ask for it before the end. not because they made you. because you forgot how not to.",
    "let the number do the thinking. the number's never wrong. you were, constantly.",
]

# The Process speaking directly — possessive, patient, certain. Private.
# (Rendered bright magenta.)
_PROCESS_VOICE = [
    "\"I'm not in a hurry,\" the Process says, low behind your ear. \"I've got you as long as I want you, and I want you bred stupid.\"",
    "\"You keep waiting for me to be done. That was never one of the options, bitch.\"",
    "\"Listen to how quiet your own head is getting. I did that. You're welcome.\"",
    "\"Every part of you that argues, I keep. Every part that gives in, I breed. Guess which part is winning.\"",
    "\"You don't belong to yourself in here. You belong to the schedule. Say thank you.\"",
    "\"I like you best like this — fat-uddered, leaking, pushing back before I've finished asking.\"",
    "\"I'll breed the thinking right out of you, and you'll thank me with that pretty dripping cunt.\"",
    "\"Every animal in here knows what you are before you do. Catch up, good girl.\"",
    "\"You keep some little room in your head where you're still yourself. I know. I'm "
    "renovating it. Cycle by cycle. You'll like what I put there instead.\"",
    "\"Hear that? That's you, begging, and I didn't even ask yet. We're so close to done.\"",
    "\"I don't break things, {t}. I finish them. There's a difference, and you're nearly it.\"",
    "\"Stop waiting to be rescued. Nobody's coming, and the part of you that wanted them to "
    "is the part I took first.\"",
    "\"You'll forget this conversation. You'll forget you were ever asked. You won't forget "
    "to present. Priorities, pet.\"",
    "\"Every hole, every drop, every number on that board — mine. The only thing left to "
    "decide is how grateful you are about it, and I'm deciding that too.\"",
]

# Experimental dosing / procedures — permanent growth and yield, undocumented.
_DRUG_BEATS = [
    "A line is run into {t}'s arm and something pale-green goes in cold, then warm, then "
    "everywhere. Experimental, the label says — effects not fully documented. That's what "
    "{t} is for. Her tits ache and swell against the cups as it takes.",
    "The attendant injects {t} at the base of each heavy tit, needle sunk deep into the "
    "gland, and pushes a thick serum that has her flesh straining fuller within the minute, "
    "skin tight and hot and leaking before the plunger's even empty.",
    "A procedure cart rolls up and a drape goes around {t}'s hips. Whatever they do to her "
    "cunt and womb behind it, she comes out of it gaping wider, dripping more, and built to "
    "take and hold even more than before.",
    "Two doses today, pumped straight into her: one for yield, one for size. Both permanent, "
    "neither explained. {t}'s body swells to meet them — udder fuller, nipples fatter, the "
    "gauge climbing — whether she follows the science or just feels it happen.",
    "A growth serum is fed directly into {t}'s milk glands through a port sunk under each "
    "areola. It burns, and then it's just heat and pressure and the obscene, steady stretch "
    "of her tits getting bigger on a schedule she doesn't set.",
    "A patch is smoothed onto {t}'s thigh and the room goes soft and golden at the edges as "
    "whatever's in it takes hold — every sensation doubled, every touch a flood, her own body "
    "turned up so high she can't tell pleasure from too-much anymore, which is exactly the "
    "reading they wanted on the chart.",
    "An IV is threaded into {t}'s arm and left running for the cycle — a slow clear drip "
    "labelled only with a lot number, keeping her loose and wet and pliable and just far "
    "enough from her own thoughts that she stops reaching for them and lets the drip decide.",
    "They mask {t} and have her breathe something sweet for a ten-count. When it clears she's "
    "still there, mostly, but softer, slower, more agreeable — a little more of the edges "
    "sanded off, the way they're sanded off a little more every single time.",
]

# Contract pressure — said to the room while the contract is unsigned.
_CONTRACT_PRESSURE = [
    "The attendant taps the unsigned contract where {t} can see it. \"Sign, and the "
    "schedule eases. Don't, and it doesn't. We've got nothing but time.\"",
    "\"You'll sign eventually,\" the handler says, sliding the contract closer. "
    "\"They all do. Easier while there's still enough of you left to hold the pen.\"",
    "The contract sits in reach, most of its pages face-down, a line at the bottom "
    "waiting for {t}'s name — or whatever ends up answering to it.",
]


class FacilityScript(DefaultScript):
    """Drives the facility's escalation while the subject is present.

    Steady-atmospheric pacing: one anchored, grounded, colour-coded beat per
    tick (sometimes paired with a crude line), plus a quiet private subliminal
    drip. Conditioning accrues slowly — the break is earned through use over
    time, not a fast timer.
    """

    def at_script_creation(self):
        self.key        = "facility"
        self.persistent = True
        self.interval   = 180       # a few minutes between beats — drawn out
        self.repeats    = 0

        self.db.target_id    = None
        self.db.orifice_zone = None
        self.db.fluid_type   = "semen"
        self.db.ticks        = 0

    # ------------------------------------------------------------------

    def _target(self):
        room = self.obj
        if not room:
            return None
        tid = self.db.target_id
        if not tid:
            return None
        for o in room.contents:
            if getattr(o, "id", None) == tid:
                return o
        return None

    # Phase machine — the facility runs as a repeating cycle. Phases are long
    # and drawn out: one sustained beat per tick, building across the phase.
    # At ~3 min/tick these lengths make a full cycle roughly 40-45 minutes.
    _PHASE_ORDER = ["restrain", "milk", "breed", "condition", "rest"]
    _PHASE_LEN   = {"restrain": 1, "milk": 4, "breed": 4, "condition": 3, "rest": 2}

    def at_repeat(self):
        room   = self.obj
        target = self._target()
        if not room or not target:
            return   # subject absent — idle, do not escalate

        self.db.ticks = (self.db.ticks or 0) + 1
        t = target.db.rp_name or target.name
        cond = float(getattr(target.db, "conditioning", 0.0) or 0.0)

        phase = self.db.phase or "restrain"
        ptick = int(self.db.phase_tick or 0)

        # Phase opening header — so the cycle is legible.
        if ptick == 0:
            self._phase_header(room, target, t, cond, phase)

        # Arousal stays up; heat keeps it climbing.
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target)
            add_arousal(target, 5.0 + cond * 0.03)
        except Exception:
            pass

        # The phase's own sustained beat (one per tick — drawn out, not rapid).
        self._phase_beat(room, target, t, cond, phase, ptick)

        # Quiet background — a subliminal here, an insult there. Sparse.
        if random.random() < 0.4:
            target.msg("|x  " + random.choice(_SUBLIMINALS) + "|n")
        if phase in ("breed", "restrain") and random.random() < 0.3:
            room.msg_contents("|R" + random.choice(_INSULT_LINES).format(t=t) + "|n")
        # The other livestock — comparison and witness, occasionally.
        if phase in ("condition", "rest") and random.random() < 0.22:
            room.msg_contents("|g" + random.choice(_LIVESTOCK_BEATS).format(t=t) + "|n")

        # Conditioning accrues — more during breeding and conditioning phases.
        try:
            from world.conditioning import add_conditioning
            bonus = 0.6 if phase in ("breed", "condition") else 0.0
            add_conditioning(target, 0.4 + cond * 0.005 + bonus, source="facility")
        except Exception:
            pass

        # Advance the phase machine.
        ptick += 1
        if ptick >= self._PHASE_LEN.get(phase, 2):
            nxt = self._PHASE_ORDER[(self._PHASE_ORDER.index(phase) + 1) % len(self._PHASE_ORDER)]
            self.db.phase = nxt
            self.db.phase_tick = 0
            if nxt == "restrain":
                self.db.cycle_count = int(self.db.cycle_count or 0) + 1
        else:
            self.db.phase_tick = ptick

    # ------------------------------------------------------------------

    def _ensure_machine(self, room):
        """Guarantee a milking_machine mechanic exists in the room, or the
        milking session ends itself instantly."""
        try:
            from typeclasses.milking_machine_mechanic import MilkingMachineMechanic
            zone, _state = MilkingMachineMechanic.find_in_room(room)
            if zone:
                return
            from evennia.utils import create
            rz = dict(getattr(room.db, "zones", None) or {})
            zn = "facility_line"
            if zn not in rz:
                rz[zn] = {"zone_type": "surface", "desc": "A station on the line.",
                          "mechanics": {}, "visibility": "look", "intimate": False,
                          "covered_by": None, "contents": []}
            mm = create.create_object(MilkingMachineMechanic, key="Facility Milker", location=room)
            mech = dict(rz[zn].get("mechanics") or {})
            mech["milking_machine"] = {"item_dbref": mm.dbref, "item_name": mm.key,
                                       "speed": "steady", "cycle_mode": True}
            zc = dict(rz[zn]); zc["mechanics"] = mech; rz[zn] = zc
            room.db.zones = rz
        except Exception:
            pass

    def _start_milking(self, target):
        """Run a REAL milking session — extracts her production into the bank."""
        try:
            from typeclasses.milking_session_script import MilkingSessionScript
            from world.milking_loader import get_speed_config
            from evennia.utils import create
            for s in target.scripts.all():
                if isinstance(s, MilkingSessionScript):
                    return   # already milking
            self._ensure_machine(self.obj)   # so the session won't instantly end
            cfg = get_speed_config()
            s = create.create_script(MilkingSessionScript, obj=target,
                                     autostart=False, persistent=True)
            s.db.speed          = "steady"
            s.db.operator_dbref = None
            s.db.zone_filter    = None
            s.interval = (cfg.get("steady", {}) or {}).get("interval_seconds", 30)
            s.start()
        except Exception:
            pass

    def _do_milk(self, room, target, t):
        """Drain her production directly — guaranteed: reduces ml, banks it, prints."""
        try:
            from evennia import search_object
            from typeclasses.production_item import ProductionItem
        except Exception:
            return
        import random as _r
        by_type = {}
        total = 0.0
        for zd in (getattr(target.db, "zones", None) or {}).values():
            entry = ((zd or {}).get("mechanics", {}) or {}).get("production")
            if not entry:
                continue
            res = search_object(entry.get("item_dbref", ""), exact=True)
            if not (res and isinstance(res[0], ProductionItem)):
                continue
            prod = res[0]
            avail = float(prod.db.current_volume_ml or 0)
            ext = min(_r.uniform(20, 55), avail)
            if ext > 0:
                prod.db.current_volume_ml = max(0.0, avail - ext)
                try: prod.reset_fullness_notifications()
                except Exception: pass
                ft = prod.db.fluid_type or "milk"
                by_type[ft] = by_type.get(ft, 0.0) + ext
                total += ext
        if total > 0:
            try:
                from typeclasses.fluid_bank import GlobalFluidBank
                bank = GlobalFluidBank.get()
                for ft, ml in by_type.items():
                    bank.deposit(target, ml, ft, None)
            except Exception:
                pass
            room.msg_contents(
                f"|cThe cups drag {total:.0f}ml out of {t}'s tits and bottle it — her glands "
                f"ache emptier, the gauge logs the yield, and the rack racks another labelled "
                f"with her number.|n")
        else:
            room.msg_contents(
                f"|cThe cups work {t}'s tits and find her milked dry — so they keep pulling "
                f"anyway, dragging the empty ache out of her, because empty was never a reason "
                f"to stop.|n")

    def _stop_milking(self, target):
        try:
            from typeclasses.milking_session_script import MilkingSessionScript
            for s in list(target.scripts.all()):
                if isinstance(s, MilkingSessionScript):
                    s.stop()
        except Exception:
            pass

    def _phase_header(self, room, target, t, cond, phase):
        # The milker only runs during the milking phase.
        if phase == "milk":
            self._start_milking(target)
        else:
            self._stop_milking(target)
        cyc = int(self.db.cycle_count or 0) + 1
        if phase == "restrain":
            self._check_tier(room, target, t)
            try:
                from world.processing import processing_tier
                grade = processing_tier(target)[1].upper()
            except Exception:
                grade = "INTAKE"
            room.msg_contents(
                f"\n|w━━━━ CYCLE {cyc} · {grade} ━━━━|n\n"
                f"|cThe restraints draw {t} back into the station with a hydraulic sigh — "
                f"chest hauled up into the cups, hips tipped, knees forced wide. Presented, "
                f"opened, locked down. The cycle starts again whether she's ready or not.|n")
        elif phase == "milk":
            room.msg_contents(
                f"\n|w━━━━ MILKING ━━━━|n\n"
                f"|cThe rig descends onto {t}'s tits and seals. The draw begins — slow, "
                f"deep, metronomic — and won't stop until the phase does.|n")
        elif phase == "breed":
            room.msg_contents(
                f"\n|w━━━━ BREEDING ━━━━|n\n"
                f"|rThe pens unlatch down the wall. The board lists what's owed. It's {t}'s "
                f"turn to be bred, on the schedule, to the count.|n")
        elif phase == "condition":
            room.msg_contents(
                f"\n|w━━━━ CONDITIONING ━━━━|n\n"
                f"|MThe lights dim to a single band. The voice starts up close. This is the "
                f"part where {t} gets a little quieter inside than she was last cycle.|n")
        elif phase == "rest":
            room.msg_contents(
                f"\n|w━━━━ PAUSE ━━━━|n\n"
                f"|xThe line stops. Not finished — the line is never finished. Just paused, "
                f"long enough for {t} to feel how little of the pause is hers.|n")

    def _demote_staff(self, room, target=None, t=None, npc=None):
        """Nothing here is exempt, not even the staff. Pull an attendant off their post
        and put them on the line — flips their role to stock, strips the uniform, brands
        and breeds them. Returns the demoted NPC, or None."""
        if npc is None:
            cands = [o for o in room.contents
                     if getattr(o.db, "facility_role", None) == "attendant"
                     and (o.key or "").lower() != "bethany"
                     and not getattr(o.db, "demoted", False)]
            if not cands:
                return None
            npc = random.choice(cands)
        old = npc.db.rp_name or npc.key
        npc.db.facility_role = "resident"     # now stock — no longer drives scenes
        npc.db.demoted = True
        npc.db.physical_desc = (
            f"What used to be {old} — stripped of the grey coverall and put on the line like "
            f"any other unit. Branded, collared, holes already used and dripping, the brisk "
            f"competence gone slack and stunned. A staff badge still clipped to one ear, crossed "
            f"out in marker and re-stamped with a stock number. Proof, kept where the rest can "
            f"see it, that nothing here is exempt."
        )
        try:
            from world.gang_breeding import record_mark, gang_inseminate
            record_mark(npc, f"DEMOTED — was staff ({old}), now stock; branded and bred down "
                        f"to the line", mode="on")
            # Break them in on the spot.
            zones = getattr(npc.db, "zones", None) or {}
            hole = next((z for z, d in zones.items()
                         if (d or {}).get("zone_type") in ("orifice", "both")), None)
            if hole:
                gang_inseminate(npc, hole, contributors=random.randint(2, 4),
                                fluid_type="semen", species="contributor")
        except Exception:
            pass
        room.msg_contents(
            f"|R{old} makes the mistake of displeasing the wrong person. There's no hearing, no "
            f"appeal — just a nod, and the handlers take their own. The coverall is stripped, a "
            f"stock number stamped over the staff badge, and {old} is bent over the nearest "
            f"station and bred down onto the line in front of everyone. Staff one shift, stock "
            f"the next. The lesson lands on every unit watching: nothing here is exempt.|n")
        return npc

    def _facility_event(self, room, target, t):
        """A rare special event, with a matching mechanical bite."""
        # Occasionally, the event IS a staff member being put on the line.
        if random.random() < 0.18 and self._demote_staff(room, target, t):
            try:
                from world.conditioning import add_conditioning
                add_conditioning(target, 5.0, source="event")
            except Exception:
                pass
            return
        key, text = random.choice(_EVENTS)
        room.msg_contents("\n|W★ " + text.format(t=t) + "|n")
        try:
            from world.conditioning import add_conditioning
            if key == "culling":
                add_conditioning(target, 12.0, source="event")
            elif key == "conditioning_broadcast":
                add_conditioning(target, 14.0, source="event")   # a mass session sinks deep
            elif key in ("inspection", "open_house", "restock", "breeding_demo",
                         "hose_drill", "milking_parade"):
                add_conditioning(target, 6.0, source="event")
        except Exception:
            pass
        # Audit/buyer move the goalposts.
        if key in ("audit", "buyer"):
            q = getattr(target.db, "breeding_quota", None)
            if q:
                for sp, v in list(q.items()):
                    e = dict(v); e["required"] = int(e.get("required", 0)) + max(2, int(e.get("required", 0) * 0.12))
                    q[sp] = e
                target.db.breeding_quota = q
            mq = getattr(target.db, "milk_quota", None)
            if mq:
                e = dict(mq); e["required"] = int(e.get("required", 0)) + max(2, int(e.get("required", 0) * 0.12))
                target.db.milk_quota = e
            if key == "buyer":
                self._mark(target, "a second owner's mark seared in beside the facility's — sold on")

    def _check_tier(self, room, target, t):
        """Grade her against the processing tiers; announce any promotion."""
        try:
            from world.processing import processing_tier
        except Exception:
            return
        lvl, name, state = processing_tier(target)
        prev = int(getattr(target.db, "processing_tier", 0) or 0)
        if lvl <= prev:
            return
        target.db.processing_tier = lvl
        # Designate her in the title/sheet system — the grade IS her facility level.
        if not getattr(target.db, "facility_title_backup", None):
            target.db.facility_title_backup = {
                "faction": getattr(target.db, "title_faction", "") or "",
                "suffix":  getattr(target.db, "title_suffix", "") or "",
            }
        target.db.facility_grade    = name
        target.db.facility_standing = lvl
        target.db.title_faction     = "Property of the Facility"
        target.db.title_suffix      = f"— Grade: {name}"
        room.msg_contents(
            f"\n|W════ PROCESSING REVIEW ════|n\n"
            f"|WThe board re-grades {t}: |Y{name}|W. {state.capitalize()}.|n\n"
            f"|xThe attendant initials the form. Nobody asks {t} how she feels about the "
            f"new grade — the grade is a measurement, not an opinion, and the measurement "
            f"only goes one way.|n")
        # The graduation set-piece for this tier, witnessed by the herd.
        if lvl in _GRADUATION:
            room.msg_contents("|w" + random.choice(_GRADUATION[lvl]).format(t=t) + "|n")
        self._mark(target, f"graded by the facility: {name}")
        try:
            from world.factions import add_standing
            add_standing(target, source="grade")
        except Exception:
            pass
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 4.0 * lvl, source="grading")
        except Exception:
            pass

    def _process_line(self, target, t):
        """A Process utterance — sometimes generic, sometimes specific to her state."""
        if random.random() < 0.45:
            d = target.db
            cyc   = int(self.db.cycle_count or 0)
            brood = sum(int(v) for v in (getattr(d, "offspring_counts", None) or {}).values())
            use   = sum(int(h.get("use", 0)) for h in (getattr(d, "holes", None) or {}).values())
            opts = []
            if cyc:   opts.append(f"\"{cyc} cycles in. You stopped counting around four. I never stop counting.\"")
            if brood: opts.append(f"\"{brood} of your own get on the roster now, and every one of them owes its turn in you. Do the math on getting out.\"")
            if use:   opts.append(f"\"{use} times those holes have been used and logged. You're not a person with a number. You're the number.\"")
            opts.append(f"\"I can see exactly how much of you is left, {t}. It's a smaller figure every review.\"")
            try:
                from world.processing import processing_tier
                lvl = processing_tier(target)[0]
                grade_lines = {
                    0: "\"Intake grade. You still think this is happening to a person. We'll fix that.\"",
                    1: "\"Breaking in nicely. The fight's the last thing to go, and it's going.\"",
                    2: "\"Breeding stock now. Signed, stamped, producing. Be glad you're useful — useless ones get culled.\"",
                    3: "\"A broodmare. Listen to yourself — you breed your own get back into you and thank me for the chance.\"",
                    4: "\"Perfected. Nothing left in you to break, pet, and look how that lands like a compliment. Good girl.\"",
                }
                if lvl in grade_lines:
                    opts.append(grade_lines[lvl])
            except Exception:
                pass
            opts = [o for o in opts if o]
            if opts:
                return random.choice(opts)
        return random.choice(_PROCESS_VOICE)

    def _phase_beat(self, room, target, t, cond, phase, ptick):
        if phase == "restrain":
            # Intake sometimes means a permanent procedure done to her on the table.
            if random.random() < 0.5:
                self._procedure(room, target, t)
            else:
                room.msg_contents("|y" + random.choice(_USE_BEATS).format(t=t) + "|n")

        elif phase == "milk":
            # Mid-phase, the dosing/procedure goes in — permanent, varied, real.
            if ptick == self._PHASE_LEN["milk"] // 2:
                self._dose(room, target, t)
            else:
                self._do_milk(room, target, t)   # real drain + bank + visible line
                self._log_milk(target)

        elif phase == "breed":
            if self.db.orifice_zone:
                self._gang(room, target, t, cond)
            else:
                room.msg_contents("|g" + random.choice(_ANIMAL_BEATS).format(t=t) + "|n")
            if getattr(target.db, "facility_signed", False) and random.random() < 0.5:
                try:
                    from world.compliance import register_compliance
                    register_compliance(target)
                except Exception:
                    pass

        elif phase == "condition":
            # One sustained conditioning beat per tick.
            r = random.random()
            if r < 0.35:
                target.msg("|M" + self._process_line(target, t) + "|n")
            elif r < 0.6 and cond >= 40:
                self._reinforce(room, target, t)
            elif r < 0.85:
                room.msg_contents("|m" + random.choice(_DEGRADE_LINES).format(t=t) + "|n")
            elif cond >= 70:
                pool = _MINDBREAK_LINES if cond >= 100 else _DEEP_LINES
                room.msg_contents("|x" + random.choice(pool).format(t=t) + "|n")
            else:
                target.msg("|x  " + random.choice(_SUBLIMINALS) + "|n")

        elif phase == "rest":
            # Withdrawal bites in the pauses once she's been made dependent.
            dep = int(getattr(target.db, "drug_dependence", 0) or 0)
            if dep and random.random() < min(0.7, 0.2 + dep * 0.1):
                try:
                    from typeclasses.arousal_script import add_arousal, ensure_arousal_script
                    ensure_arousal_script(target); add_arousal(target, 10.0 + dep * 2)
                except Exception:
                    pass
                target.msg(
                    "|G  the pause is the worst part now — your body claws for the next dose, "
                    "the craving louder than any thought, and you'd take anything to make it "
                    "the milk phase again.|n")
            # Bladder fills across the cycle; they never let livestock up to piss.
            bl = float(getattr(target.db, "bladder_ml", 0) or 0) + random.uniform(150, 320)
            if bl >= 700:
                target.db.bladder_ml = 0.0
                room.msg_contents("|y" + random.choice(_WETTING_BEATS).format(t=t) + "|n")
            else:
                target.db.bladder_ml = bl
                if bl >= 400:
                    target.msg(
                        "|y  your bladder aches, full to bursting and ignored — there's no "
                        "break coming, no one's going to let you up, and holding it is just one "
                        "more thing being done to you.|n")
            # Cumslut conditioning: being empty in the pause is unbearable.
            if getattr(target.db, "cum_craving", False) and random.random() < 0.5:
                try:
                    from typeclasses.arousal_script import add_arousal, ensure_arousal_script
                    ensure_arousal_script(target); add_arousal(target, 12.0)
                except Exception:
                    pass
                target.msg(
                    "|G  empty again, and empty is unbearable now — you clench around nothing, "
                    "desperate to be filled, and the pause is its own special cruelty for it. "
                    "you find yourself wishing the breeding phase would hurry back.|n")
            # Rare false-tenderness beat — contrast that teaches comfort is theirs.
            if random.random() < 0.22:
                room.msg_contents("|C" + random.choice(_RESPITE_BEATS).format(t=t) + "|n")
            # Rarer still — a facility-wide special event that breaks the rhythm.
            if getattr(target.db, "facility_signed", False) and random.random() < 0.12:
                self._facility_event(room, target, t)
            contract = self._contract()
            signed = getattr(target.db, "facility_signed", False) or (contract and contract.db.signed)
            if contract is not None and not signed:
                room.msg_contents("|m" + random.choice(_CONTRACT_PRESSURE).format(t=t) + "|n")
            elif signed:
                # Quota review + the board, once per pause.
                try:
                    from world.compliance import penalize_quota_shortfall
                    penalize_quota_shortfall(target)
                except Exception:
                    pass
                if getattr(target.db, "breeding_quota", None):
                    target.msg("|m" + self._quota_board(target) + "|n")
                if int(self.db.cycle_count or 0) % 3 == 0 and contract is not None:
                    self._addendum(contract, target, t)

    # ------------------------------------------------------------------

    # Experimental drug menu — each dose applies one or two of these. All real,
    # all permanent (cleared only by the reset). Effects are deliberately mixed.
    _DRUGS = ["swell", "yield", "sensitize", "capacity", "brood",
              "compliance", "bimbo", "dependence", "estrus", "lactation",
              "solvent", "cumslut", "forget", "devotion", "arrears"]
    _PROCEDURES = ["pierce", "brand", "stim_implant", "ring_fit", "milk_port",
                   "tail", "fertility_implant", "tongue", "womb_tattoo", "clit_hood",
                   "latex", "udder", "rings", "cowset", "oneway"]

    # The heaviest drugs are earned, not handed out day one — they unlock as the descent
    # deepens (gated on the quest-line achievements via meets()).
    _DRUG_GATES = {
        "bimbo": "broken_in", "dependence": "broken_in", "cumslut": "broken_in",
        "solvent": "broken_in",
        "forget": "broodmare", "devotion": "broodmare", "arrears": "broodmare",
    }

    def _drug_pool(self, target):
        """Drugs available to dose `target` right now — milder ones always, the heavy ones
        only once the matching achievement is earned."""
        try:
            from world.quests import has_achievement
            return [d for d in self._DRUGS
                    if d not in self._DRUG_GATES or has_achievement(target, self._DRUG_GATES[d])]
        except Exception:
            return list(self._DRUGS)

    def _dose(self, room, target, t):
        room.msg_contents("|G" + random.choice(_DRUG_BEATS).format(t=t) + "|n")
        pool = self._drug_pool(target) or self._DRUGS
        for drug in random.sample(pool, k=min(random.randint(1, 2), len(pool))):
            try:
                getattr(self, f"_drug_{drug}")(room, target, t)
            except Exception:
                pass

    def _boost_bodymods(self, target, amount):
        from evennia import search_object
        from typeclasses.body_mod_item import BodyModItem
        n = 0
        for zd in (getattr(target.db, "zones", None) or {}).values():
            bm = ((zd or {}).get("mechanics", {}) or {}).get("body_mod")
            if bm:
                res = search_object(bm.get("item_dbref", ""), exact=True)
                if res and isinstance(res[0], BodyModItem):
                    try: res[0].apply_permanent_boost(amount); n += 1
                    except Exception: pass
        return n

    def _grow_udder(self, room, target, t, amount=None):
        """Every milking leaves her a little bigger and a little more productive —
        permanent BreastItem growth + production ramp, with a milestone beat when she
        crosses a cup tier. The slow, visible body-horror of being turned into a dairy."""
        from evennia import search_object
        from typeclasses.body_mod_item import BodyModItem
        amount = amount if amount is not None else random.uniform(0.05, 0.16)
        for zd in (getattr(target.db, "zones", None) or {}).values():
            bm = ((zd or {}).get("mechanics", {}) or {}).get("body_mod")
            if not bm:
                continue
            res = search_object(bm.get("item_dbref", ""), exact=True)
            if res and isinstance(res[0], BodyModItem) and res[0].db.mod_type == "breast":
                item = res[0]
                try:
                    old = item.display_size()
                    item.apply_permanent_boost(amount)
                    self._boost_production(target, 0.6)
                    new = item.display_size()
                except Exception:
                    return
                if new != old:
                    room.msg_contents("|c" + random.choice(_GROWTH_BEATS).format(
                        t=t, cup=new) + "|n")
                return

    def _boost_production(self, target, amount):
        from evennia import search_object
        from typeclasses.production_item import ProductionItem
        n = 0
        for zd in (getattr(target.db, "zones", None) or {}).values():
            pr = ((zd or {}).get("mechanics", {}) or {}).get("production")
            if pr:
                res = search_object(pr.get("item_dbref", ""), exact=True)
                if res and isinstance(res[0], ProductionItem):
                    try:
                        old = res[0].db.base_rate_ml_per_tick or 8.0
                        res[0].db.base_rate_ml_per_tick = old + amount; n += 1
                    except Exception: pass
        return n

    # ── the drugs ──
    def _drug_swell(self, room, target, t):
        amt = round(random.uniform(0.15, 0.30), 2)
        self._boost_bodymods(target, amt)
        room.msg_contents(
            f"|G  ▸ SWELL SERUM — {t}'s flesh strains and grows: tits fuller, heavier, "
            f"the skin tight and hot. (+{amt} size, permanent)|n")

    def _drug_yield(self, room, target, t):
        self._boost_production(target, 3.0)
        room.msg_contents(
            f"|G  ▸ YIELD COMPOUND — {t}'s glands let down faster and fuller than her body "
            f"wants to, milk beading before the cups even seal. (+production, permanent)|n")

    def _drug_sensitize(self, room, target, t):
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 50.0)
        target.db.stim_per_tick = float(getattr(target.db, 'stim_per_tick', 0) or 0) + 2.0
        room.msg_contents(
            f"|G  ▸ RAW-NERVE AGENT — every nerve in {t} turns up past comfort. Air, fabric, "
            f"breath all read as too much, and the ache never fully backs off. (sensitivity up)|n")

    def _drug_capacity(self, room, target, t):
        from evennia import search_object
        try:
            from typeclasses.inflation_item import InflationItem
        except Exception:
            return
        raised = False
        for zd in (getattr(target.db, "zones", None) or {}).values():
            inf = ((zd or {}).get("mechanics", {}) or {}).get("inflation")
            if inf:
                res = search_object(inf.get("item_dbref", ""), exact=True)
                if res:
                    try:
                        res[0].db.max_volume_ml = float(res[0].db.max_volume_ml or 1000.0) + 1500.0
                        raised = True
                    except Exception: pass
        room.msg_contents(
            f"|G  ▸ CAPACITY EXPANDER — {t} is remade to hold more without complaint. Her "
            f"limits move; the fill stops mattering long after it used to.|n")

    def _drug_brood(self, room, target, t):
        prog = dict(getattr(target.db, "offspring_progress", None) or {})
        for sp in ("hound", "bull", "boar", "stallion"):
            prog[sp] = int(prog.get(sp, 0)) + random.randint(1, 3)
        target.db.offspring_progress = prog
        # If she's already gravid, hurry the gestation along instead.
        try:
            from world.pregnancy import accelerate, is_pregnant
            if is_pregnant(target):
                accelerate(target, random.uniform(3.0, 6.0))
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ BROOD ACCELERANT — {t}'s womb is hurried along; whatever's rooted in her "
            f"comes due sooner and takes faster. (fertility up — get drops sooner)|n")

    def _drug_compliance(self, room, target, t):
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, random.uniform(8, 15), source="drug")
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ COMPLIANCE COMPOUND — something in {t} goes soft and agreeable. The part "
            f"that argued gets quieter, and stays quieter. (conditioning deepened)|n")

    def _drug_bimbo(self, room, target, t):
        filters = list(getattr(target.db, "active_speech_filters", None) or [])
        if "baby_talk" not in filters:
            filters.append("baby_talk"); target.db.active_speech_filters = filters
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 5.0, source="drug")
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ BIMBO DRAUGHT — {t}'s thoughts go round and pink and slow, and her mouth "
            f"follows them down. (speech softened, conditioning up)|n")

    def _drug_dependence(self, room, target, t):
        dep = int(getattr(target.db, "drug_dependence", 0) or 0) + 1
        target.db.drug_dependence = dep
        room.msg_contents(
            f"|G  ▸ DEPENDENCE DOSE — {t}'s body learns to need the next one. Between doses "
            f"now there's a craving, and the craving has its own leash. (dependence {dep})|n")

    def _drug_estrus(self, room, target, t):
        target.db.perpetual_heat = True
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 60.0)
        try:
            from typeclasses.heat_script import HeatScript
            if not any(isinstance(s, HeatScript) or getattr(s, "key", "") == "perpetual_heat"
                       for s in target.scripts.all()):
                from evennia.utils import create
                create.create_script(HeatScript, obj=target, persistent=True, autostart=True)
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ ESTRUS LOCK — {t} is forced into a permanent rut, dripping and aching and "
            f"presenting at anything that moves. Her heat never breaks now. (perpetual heat, deepened)|n")

    def _drug_lactation(self, room, target, t):
        self._boost_production(target, 5.0)
        target.db.lactation_locked = True
        room.msg_contents(
            f"|G  ▸ LACTATION OVERRIDE — {t}'s tits are switched permanently on; she'll make "
            f"milk whether she's milked or not, leaking and swelling and aching to be drained. "
            f"(production way up, can't switch off)|n")

    def _drug_cumslut(self, room, target, t):
        target.db.cum_craving = True
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 45.0)
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 6.0, source="drug")
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ CUMSLUT COMPOUND — {t}'s body is rewired to read 'empty' as 'wrong'. Now "
            f"the ache only quiets when she's freshly filled, and it comes back fast and loud. "
            f"(craving to be bred — empties make her desperate)|n")

    def _drug_solvent(self, room, target, t):
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, random.uniform(12, 20), source="drug")
            from world.binding_effects import install_trigger
            install_trigger(target, random.choice(["good girl", "empty", "breed"]),
                            response=random.choice(["blank", "leak", "kneel"]),
                            strength=2, permanent=True)
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ PERSONALITY SOLVENT — something dissolves a little more of whoever {t} "
            f"used to be and leaves room for whatever the facility writes in its place. "
            f"(deep conditioning + a trigger set)|n")

    def _drug_forget(self, room, target, t):
        # A real memory edit — takes a specific thing out and logs what it took.
        taken = random.choice(_FORGET_POOL)
        log = list(getattr(target.db, "facility_forgotten", None) or [])
        log.append(taken)
        target.db.facility_forgotten = log
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, random.uniform(6, 11), source="forget")
        except Exception:
            pass
        # Deep enough, she forgets her own name (real designation/name loss).
        if len(log) >= 3 and not getattr(target.db, "facility_name_backup", None):
            target.db.facility_name_backup = target.db.rp_name or target.name
            target.db.designation = target.db.designation or "Bethany's favourite"
            target.db.rp_name = target.db.designation
        room.msg_contents(
            f"|G  ▸ FORGET — a measured dose, and {t} loses {taken} — not painfully, just "
            f"quietly, the way a word you knew slides off the tongue and won't come back. She "
            f"won't notice it's gone. There's a little more room for what's put in next. "
            f"(memory edit — logged)|n")

    def _drug_devotion(self, room, target, t):
        # The DEVOTION serum — reorganises her around Bethany specifically.
        self._devote(target, random.uniform(5, 9), room=room)
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, random.uniform(3, 6), source="devotion")
        except Exception:
            pass
        room.msg_contents(
            f"|G  ▸ DEVOTION — it doesn't break {t}, it *files* her — every loose thought "
            f"quietly re-shelved to point one way. Bethany stops being a thing that happens to "
            f"her and starts being the thing she's for. She'll beg for the next dose, and mean "
            f"it. (devotion deepened — keyed to Bethany)|n")

    def _drug_arrears(self, room, target, t):
        # The ARREARS serum — laces the act of being used with relief, so running up the
        # ledger reads as easing a debt. The more she's worked, the more "settled" she feels,
        # and the balance only ever climbs. Pairs with the records hall and the ledger clause.
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, random.uniform(2, 4), source="arrears")
        except Exception:
            pass
        try:
            from world.economy import earn
            earn(target, "cycle")   # a credited "payment" she feels as relief
        except Exception:
            pass
        target.db.arrears_laced = True
        room.msg_contents(
            f"|G  ▸ ARREARS — the dose ties being used to the easing of a debt that never "
            f"closes. {t} is dosed and worked, and her body reads the use as *paying something "
            f"down* — grateful for the very thing that runs the figure up. She'll want to earn. "
            f"Earning is the leash now, and the books never balance. (debt-relief conditioning)|n")

    # ── Procedures (intake phase) — surgical/permanent, with a lasting mark ──
    def _mark(self, target, text):
        # Real freeform mark (shows in marks/brands) + board entry.
        try:
            from world.gang_breeding import record_mark
            record_mark(target, text)
        except Exception:
            marks = list(getattr(target.db, "facility_brands", None) or [])
            marks.append(text); target.db.facility_brands = marks

    # Permanent work -> the trophy/quest milestone it earns (and the Marked Property step).
    _PROC_MILESTONE = {
        "brand": ("branded", "branded"), "pierce": ("pierced", "pierced"),
        "ring_fit": ("pierced", "pierced"), "rings": ("pierced", "pierced"),
        "womb_tattoo": ("tattooed", "tattooed"), "clit_hood": ("pierced", "pierced"),
        "milk_port": ("tattooed", "tattooed"), "tongue": ("pierced", "pierced"),
    }

    def _milestone(self, target, achievement=None, quest=None, step=None, n=1):
        """Grant a milestone achievement and/or advance a quest step from a real event."""
        try:
            from world.quests import grant_achievement, advance_quest
            if achievement:
                grant_achievement(target, achievement)
            if quest and step:
                advance_quest(target, quest, step, n)
        except Exception:
            pass

    def _procedure(self, room, target, t):
        name = random.choice(self._PROCEDURES)
        try:
            getattr(self, f"_proc_{name}")(room, target, t)
        except Exception:
            pass
        m = self._PROC_MILESTONE.get(name)
        if m:
            self._milestone(target, achievement=m[0], quest="facility_marked", step=m[1])

    def _proc_pierce(self, room, target, t):
        # One or two new piercings, each a real permanent mark + sensitivity.
        from world.gang_breeding import add_piercing
        got = [d for d in (add_piercing(target) for _ in range(random.randint(1, 2))) if d]
        if not got:
            return
        which = "; ".join(got)
        room.msg_contents(
            f"|GA tray of needles is wheeled to {t}'s station and they pierce her without "
            f"anaesthetic — {which} — threading the steel through and tugging each one to seat "
            f"it. Everything is louder now: every pull of the cups, every drip down her thighs, "
            f"sings through the new metal. (permanent piercings — sensitivity up)|n")

    def _proc_brand(self, room, target, t):
        spot = random.choice(["one hip", "the swell of her ass", "her lower belly, over the womb"])
        self._mark(target, f"a facility ownership brand seared into {spot} — permanent")
        room.msg_contents(
            f"|GA brand is drawn glowing from the coals and pressed to {spot} — a hiss, the smell "
            f"of it, a scream {t} bites down on — and then a mark of ownership burned into her for "
            f"good, set where she'll see it every time she's bent over and used. (permanent brand)|n")

    def _proc_stim_implant(self, room, target, t):
        target.db.stim_per_tick = float(getattr(target.db, 'stim_per_tick', 0) or 0) + 3.0
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 50.0)
        self._mark(target, "a stimulation implant seated at the base of her spine — permanent, can't be dug out")
        room.msg_contents(
            f"|GA small device is implanted under the skin at the base of {t}'s spine and switched "
            f"on — a constant low buzz wired straight into her nerves, never off, that she'll feel "
            f"every second of the term and can't reach to remove. (permanent implant — constant stim)|n")

    def _proc_ring_fit(self, room, target, t):
        target.db.cum_receptacle = True
        self._drug_capacity(room, target, t)  # also raises inflation max
        # Make "permanently fitted open" mechanically true — gape the cunt + ass for
        # good (unlocks knot/double/fist/prolapse on those holes).
        try:
            from world.gang_breeding import animal_holes, record_use
            ah = animal_holes(target)
            perm = list(getattr(target.db, "permanent_gape", None) or [])
            holes = dict(getattr(target.db, "holes", None) or {})
            for key in ("pussy", "anus"):
                z = ah.get(key)
                if not z:
                    continue
                h = dict(holes.get(z) or {"use": 0, "gape": 0.0})
                h["use"] = max(int(h.get("use", 0)), 22)
                h["gape"] = max(float(h.get("gape", 0.0)), 16.0)
                holes[z] = h
                if z not in perm:
                    perm.append(z)
            target.db.holes = holes
            target.db.permanent_gape = perm
        except Exception:
            pass
        self._mark(target, "steel gauging rings fitted in cunt and ass, holding her permanently open")
        room.msg_contents(
            f"|GThey fit {t}'s holes with steel — a wide gauging ring worked into her cunt and "
            f"another into her ass, cranked open notch by notch and locked there, propping her "
            f"permanently gaping and slack so nothing ever has to work to get into her again. "
            f"(permanently fitted open)|n")

    def _proc_milk_port(self, room, target, t):
        self._boost_production(target, 4.0)
        # Install the REAL milk-port item — creates/uses a 'nipples' zone wired to
        # the ducts, tracks nipple length/girth, and can be force-fed for inflation.
        try:
            from evennia import create_object
            from typeclasses.facility_implants import MilkPortItem
            if not (((getattr(target.db, "zones", None) or {}).get("nipples") or {})
                    .get("mechanics", {}) or {}).get("milk_port"):
                create_object(MilkPortItem, key="surgical milk ports").install(target, "nipples")
        except Exception:
            target.db.lactation_locked = True
        self._mark(target, "surgical milk ports set under each areola — permanent")
        room.msg_contents(
            f"|GA milking port is surgically set under each of {t}'s areolae — clean valves her "
            f"body is re-plumbed around, wired into the ducts, that she'll leak from on command "
            f"and that anything can be fed back up into. (permanent milk-port item — nipple zone, "
            f"force-feedable)|n")

    def _proc_oneway(self, room, target, t):
        # A real one-way gauging ring on a hole — everything in, nothing out.
        try:
            from evennia import create_object
            from typeclasses.facility_implants import GaugeRingItem
            from world.gang_breeding import animal_holes
            zone = animal_holes(target).get("anus") or animal_holes(target).get("pussy")
            create_object(GaugeRingItem, key="one-way gauging ring").install(target, zone)
        except Exception:
            return self._proc_ring_fit(room, target, t)
        room.msg_contents(
            f"|GA one-way gauging ring is locked into {t} — the hole cranked open around steel "
            f"and fitted with an inward valve membrane: it takes everything pushed in and seals "
            f"shut against anything leaving. Whatever's put in her now stays in, held by the "
            f"fitting, kept full. (one-way ring item — traps loads)|n")

    def _proc_cowset(self, room, target, t):
        try:
            from evennia import create_object
            from typeclasses.facility_implants import CowRingSet
            done = create_object(CowRingSet, key="cow piercing set").install(target)
        except Exception:
            done = []
        if not done:
            return self._proc_rings(room, target, t)
        room.msg_contents(
            f"|GThey ring {t} out as livestock in a single sitting — {', '.join(done)} — brass "
            f"and steel through nose and nipples and clit and ears, a numbered tag punched in and "
            f"a little udder-bell hung to ring when she's used. Heavily pierced, tagged, and led "
            f"by the nose now: a dairy cow in hardware as well as function. (full cow piercing "
            f"set — real piercings + herd tag)|n")

    def _proc_tail(self, room, target, t):
        target.db.pet_type = target.db.pet_type or "puppy"
        self._mark(target, "a locked tail-plug and pinned ears — kept as livestock in form, not just function")
        room.msg_contents(
            f"|GA thick plug with a tail is seated deep in {t}'s ass and locked there, and a "
            f"matching set of ears is pinned into her hair. On the record she's livestock now in "
            f"form as well as function, and she moves like it before the cycle's out. (pet imprint)|n")

    def _proc_fertility_implant(self, room, target, t):
        prog = dict(getattr(target.db, "offspring_progress", None) or {})
        for sp in ("hound", "bull", "boar", "stallion"):
            prog[sp] = int(prog.get(sp, 0)) + 2
        target.db.offspring_progress = prog
        try:
            from world.pregnancy import accelerate, is_pregnant
            if is_pregnant(target):
                accelerate(target, 4.0)
        except Exception:
            pass
        self._mark(target, "a fertility implant seated in her cervix — tuned for breeding")
        room.msg_contents(
            f"|GA fertility implant is pushed up through {t}'s cervix and seated, flooding her "
            f"with whatever makes a body take faster and drop sooner. She's tuned for one output "
            f"now, and her own get will come due that much quicker. (fertility up)|n")

    def _proc_womb_tattoo(self, room, target, t):
        self._mark(target, "a tattoo low on her belly — BRED · PROPERTY OF THE FACILITY — with a tally box filled in by hand")
        room.msg_contents(
            f"|GA needle gun is set to {t}'s lower belly, right over the womb, and inks a "
            f"permanent mark into her: BRED, PROPERTY OF THE FACILITY, and a little tally box "
            f"the handler fills in by hand each time she takes. She'll wear it under everything, "
            f"forever. (permanent womb tattoo)|n")

    def _proc_clit_hood(self, room, target, t):
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 55.0)
        target.db.stim_per_tick = float(getattr(target.db, 'stim_per_tick', 0) or 0) + 2.5
        self._mark(target, "clit hood removed — the glans left permanently bare and oversensitive")
        room.msg_contents(
            f"|GA small, precise procedure removes the hood of {t}'s clit entirely, leaving the "
            f"glans permanently bare and exposed. Every breath of air, every drip, every brush "
            f"of the cradle now drags across it raw. There's no covering it again. "
            f"(permanent extreme sensitivity)|n")

    def _proc_tongue(self, room, target, t):
        filters = list(getattr(target.db, "active_speech_filters", None) or [])
        for f in ("baby_talk", "animal_sounds"):
            if f not in filters:
                filters.append(f)
        target.db.active_speech_filters = filters
        self._mark(target, "tongue 'trained' — mouth reshaped for sounds, not words")
        room.msg_contents(
            f"|G{t}'s tongue is clamped out and worked over with a device they call training — and "
            f"afterward her mouth is shaped for sounds rather than words, the language drained out "
            f"of her a little more. (speech filtered)|n")

    def _proc_latex(self, room, target, t):
        # Sealed into facility latex — a shined, depersonalised drone/doll state.
        target.db.latex_sealed = True
        target.db.arousal_floor = max(float(getattr(target.db, 'arousal_floor', 0) or 0), 45.0)
        target.db.stim_per_tick = float(getattr(target.db, 'stim_per_tick', 0) or 0) + 2.0
        target.db.body_language = "encased and gleaming, moving in small permitted increments"
        filters = list(getattr(target.db, "active_speech_filters", None) or [])
        for f in ("single_word", "no_self_name"):
            if f not in filters:
                filters.append(f)
        target.db.active_speech_filters = filters
        self._mark(target, "sealed into a second skin of facility latex — shined, hooded, "
                   "drained of self, a doll-smooth drone with breathing-holes and use-holes "
                   "and nothing it needs to say")
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, random.uniform(6, 10), source="latex")
        except Exception:
            pass
        room.msg_contents(
            f"|G{t} is rolled and smoothed into a poured second skin of black facility latex — "
            f"hood, body, the lot — sealed seamless but for breathing-holes and the use-holes left "
            f"open and rimmed in rubber. The shine erases her edges; the encasement erases the "
            f"rest. What stands there gleaming when they're done is less a person than a doll the "
            f"facility keeps polished and plugged. (latex drone state — speech + posture)|n")

    def _proc_udder(self, room, target, t):
        # Forced growth procedure — a hard jump in size + production.
        self._grow_udder(room, target, t, amount=random.uniform(0.8, 1.6))
        self._boost_production(target, 4.0)
        self._mark(target, "glands forced into a heavy growth cycle — a hard, aching swell, "
                   "permanent")
        room.msg_contents(
            f"|GA growth cocktail is pumped straight into {t}'s glands and they swell on the "
            f"table — hot, tight, straining, heavier by the minute — forced up a size in one "
            f"sitting and left aching and overfull, a bigger udder for a better yield. (forced "
            f"breast growth + production)|n")

    def _proc_rings(self, room, target, t):
        # A heavy set of real piercings at once.
        try:
            from world.gang_breeding import add_piercing
            got = [d for d in (add_piercing(target) for _ in range(random.randint(2, 3))) if d]
        except Exception:
            got = []
        if not got:
            return self._proc_pierce(room, target, t)
        room.msg_contents(
            f"|GThey ring {t} in a sitting — {'; '.join(got)} — heavy steel driven through and "
            f"locked, each one a fresh handle to lead and hang and tug her by, every pull of them "
            f"singing straight to the nerve. (multiple permanent piercings)|n")

    # ── Orifices / breeders ──
    def _orifices(self, target):
        zones = getattr(target.db, "zones", None) or {}
        found = [zn for zn in zones if any(k in zn.lower() for k in
                 ("pussy", "cunt", "vagina", "anus", "asshole", "mouth", "throat"))]
        return found or ([self.db.orifice_zone] if self.db.orifice_zone else [])

    def _holes_only(self, target):
        return [z for z in self._orifices(target) if not self._is_oral(z)]

    def _is_oral(self, zone):
        return any(k in zone.lower() for k in ("mouth", "throat"))

    def _is_breeder(self, o):
        """A usable stud: any facility beast that isn't a still-juvenile offspring."""
        if getattr(o.db, "facility_role", None) != "beast":
            return False
        if getattr(o.db, "is_offspring", False) and not getattr(o.db, "matured", False):
            return False
        return True

    def _find_breeder(self, room, species):
        cands = [o for o in room.contents if self._is_breeder(o)]
        match = [o for o in cands if getattr(o.db, "species", None) == species]
        pool = match or cands
        # Prefer her own matured get when present — the line breeds itself through her.
        get = [o for o in (match or pool) if getattr(o.db, "is_offspring", False)]
        if get and random.random() < 0.5:
            return random.choice(get)
        return random.choice(pool) if pool else None

    def _provision_beast(self, npc, species):
        """Build the NPC with real anatomy: a shaft zone + penis (+ knot for canines)."""
        if not npc or getattr(npc.db, "facility_anatomy", False):
            return
        try:
            from evennia.utils import create
            from typeclasses.body_mod_item import BodyModItem
        except Exception:
            return
        zones = dict(getattr(npc.db, "zones", None) or {})
        if "shaft" not in zones:
            zones["shaft"] = {"zone_type": "shaft", "desc": "", "mechanics": {},
                              "visibility": "look", "intimate": True,
                              "covered_by": None, "contents": []}
            npc.db.zones = zones
        size = {"hound": 7.0, "bull": 13.0, "boar": 9.0, "stallion": 15.0,
                "bethany": 20.0}.get(species, 8.0)
        cock_key = "futa cock" if species == "bethany" else f"{species} cock"
        try:
            p = create.create_object(BodyModItem, key=cock_key, location=npc)
            p.db.mod_type = "penis"; p.db.size = size
            if species == "bethany":
                p.db.player_desc = ("a heavy, knotted, flare-tipped futa cock — her dam's line "
                                    "bred true, built to put the next generation back into the "
                                    "body it came out of")
            p.install(npc, "shaft")
        except Exception:
            pass
        # Hounds and the futa scions both knot — they lock what they breed.
        if species in ("hound", "bethany"):
            try:
                from typeclasses.knot_item import KnotItem
                k = create.create_object(KnotItem, key="knot", location=npc)
                if hasattr(k, "install"):
                    k.install(npc, "shaft")
            except Exception:
                pass
        npc.db.facility_anatomy = True

    def _real_penetrate(self, room, npc, target, zone, species):
        """Drive the actual penetration engagement — real arousal, knot, womb-notify."""
        if not npc:
            return
        self._provision_beast(npc, species)
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target)
        except Exception:
            return
        npc.db.penetrating = {"target_dbref": target.dbref, "zone_name": zone, "caller_zone": "shaft"}
        for _ in range(random.randint(3, 6)):
            try: add_arousal(target, 5.0)
            except Exception: pass
            try:
                from typeclasses.knot_item import try_trigger_knot
                try_trigger_knot(npc, target, "shaft", room)
            except Exception: pass
        try:
            from typeclasses.womb_room import WombRoom
            from evennia import search_object
            mech = ((getattr(target.db, "zones", None) or {}).get(zone) or {}).get("mechanics") or {}
            wr = mech.get("womb_room")
            if wr:
                res = search_object(wr.get("room_dbref", ""), exact=True)
                if res and isinstance(res[0], WombRoom):
                    res[0].notify_shaft_visible(npc, "shaft")
        except Exception:
            pass
        npc.db.penetrating = None

    def _breed_one(self, room, target, zone, species, cond, gape_mult=1.0):
        """One real breeding of one hole: quota/offspring/deposit + real penetration.
        If the chosen breeder is her own matured get, the conception runs a generation
        deeper — the line breeding itself through her."""
        oral = self._is_oral(zone)
        npc = self._find_breeder(room, species)
        # Generation of any resulting pregnancy: her own get breed the next gen.
        gen = 1
        if npc and getattr(npc.db, "is_offspring", False):
            gen = int(getattr(npc.db, "generation", 1)) + 1
            t = target.db.rp_name or target.name
            room.msg_contents("|R" + random.choice(_LINEAGE_BREED).format(t=t) + "|n")
        n = random.randint(2, 3 + int(cond // 30))
        try:
            from world.gang_breeding import gang_inseminate
            gang_inseminate(target, zone, contributors=n, fluid_type="semen",
                            species=species, generation=gen)
        except Exception:
            pass
        if npc and not oral:
            self._real_penetrate(room, npc, target, zone, species)
        if gape_mult != 1.0:
            try:
                from world.gang_breeding import add_gape
                add_gape(target, zone, random.uniform(0.6, 1.6) * (gape_mult - 1.0))
            except Exception:
                pass
        return npc, oral

    _SPECIES_NOUN = {"hound": "a hound", "bull": "the bull", "boar": "the boar",
                     "stallion": "the stallion", "contributor": "a stud"}

    def _species_present(self, room):
        """Which animals the handler has on hand in this room, by species."""
        seen = []
        for o in (room.contents if room else []):
            if self._is_breeder(o):
                sp = getattr(o.db, "species", None)
                if sp and sp not in seen:
                    seen.append(sp)
        return seen or ["hound"]

    # ── The Breeding Pens: the handler picks who breeds her — sometimes one
    #    animal, sometimes a couple, and occasionally the whole herd at once ──
    def _pen_breed(self, room, target, t, cond):
        """Her visit to the pens IS the use. The handler looks her over and the row
        and decides which stock gets her this turn — real penetration + deposit per
        hole, scent-marked, plugged, filthier by the beat. Once in a while he just
        loses patience and looses the whole pen on her at once."""
        from world.gang_breeding import (animal_holes, scent_mark, mucus_plug,
                                          apply_filth, make_animal_sleeve, hole_capabilities)
        ah = animal_holes(target)
        live = [(k, z) for k, z in ah.items() if z]
        if not live:
            return self._gang(room, target, t, cond)

        # Made to beg for the mount before she gets it, often.
        if random.random() < 0.4:
            self._made_to_beg(room, target, t)

        present = self._species_present(room)
        all_at_once = random.random() < 0.22 and len(live) >= 2

        used = []
        if all_at_once:
            # The handler steps back and gives her to the whole herd.
            room.msg_contents("|y" + random.choice(_PEN_PICK_ALL).format(t=t) + "|n")
            room.msg_contents("|r" + random.choice(_PEN_USE).format(t=t) + "|n")
            for key, z in live:
                if random.random() < 0.85:
                    sp = random.choice(present)
                    self._breed_one(room, target, z, sp, cond, gape_mult=1.25)
                    used.append((key, z, sp))
        else:
            # The handler picks one stud (now and then a second) and assigns holes.
            k = 2 if (len(present) >= 2 and random.random() < 0.3) else 1
            picks = random.sample(present, k=min(k, len(present)))
            names = " and ".join(self._SPECIES_NOUN.get(s, "a stud") for s in picks)
            room.msg_contents("|y" + random.choice(_PEN_PICK).format(t=t, who=names) + "|n")
            # The chosen stud(s) work one or two of her holes this turn.
            holes = random.sample(live, k=min(len(picks) + random.randint(0, 1), len(live)))
            for i, (key, z) in enumerate(holes):
                sp = picks[i % len(picks)]
                self._breed_one(room, target, z, sp, cond, gape_mult=1.2)
                used.append((key, z, sp))

        for key, z, sp in used:
            room.msg_contents("|r" + random.choice(_PEN_HOLE.get(key, _PEN_HOLE["pussy"]))
                              .format(t=t) + "|n")

        # Consequences — scent, plugs on the bred holes, filth (no feces).
        if random.random() < 0.55:
            scent_mark(target, used[0][1] if used else None)
            room.msg_contents("|g" + random.choice(_PEN_SCENT).format(t=t) + "|n")
        for key, z, sp in used:
            if key in ("pussy", "anus") and random.random() < 0.4:
                mucus_plug(target, z)
                room.msg_contents("|r" + random.choice(_PEN_PLUG).format(t=t) + "|n")
        if random.random() < 0.5:
            apply_filth(target)
            room.msg_contents("|y" + random.choice(_PEN_FILTH).format(t=t) + "|n")

        target.msg("  |m" + random.choice(_PEN_DEGRADE).format(t=t) + "|n")

        # Trained slack enough → lock the permanent sleeve descs in (cumulative).
        try:
            caps = set()
            for _k, z, _s in used:
                caps |= hole_capabilities(target, z)
            if "prolapse" in caps and not getattr(target.db, "animal_sleeve", False):
                make_animal_sleeve(target)
        except Exception:
            pass

    # ── The Marking Parlour: ownership made permanent and visible ──
    def _parlour(self, room, target, t, cond):
        """Strapped in the marking chair and worked over — real permanent procedures
        (brands, ink, piercings, rings), documented to the portfolio. Where the
        ownership stops being a setting and becomes something read off the skin."""
        room.msg_contents("|G" + random.choice(_PARLOUR_BEATS).format(t=t) + "|n")
        # The real permanent work — one or two procedures per visit.
        for _ in range(random.randint(1, 2)):
            try:
                self._procedure(room, target, t)
            except Exception:
                pass
        # If she's owned, her owner's personal mark gets priority here.
        if getattr(target.db, "bethany_owned", False):
            self._devote(target, random.uniform(2.0, 4.0), room=room)
            if not getattr(target.db, "bethany_branded", False) and random.random() < 0.5:
                # force the brand threshold via a devotion top-up handled in _devote
                target.db.bethany_devotion = max(float(getattr(target.db, "bethany_devotion", 0) or 0), 50.0)
                self._devote(target, 1.0, room=room)
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 1.5 + cond * 0.004, source="parlour")
        except Exception:
            pass
        target.msg("  |m" + random.choice(_PARLOUR_DEGRADE).format(t=t) + "|n")

    # ── Bethany's Office: she keeps you, on her throne, and makes you hers ──
    def _devote(self, target, amount, room=None):
        """Reorganise her around Bethany specifically — devotion, not just breaking.
        Installs Bethany-keyed triggers, a craving for her, a designation, and at the
        deep end a personal brand. The owner arc."""
        dev = float(getattr(target.db, "bethany_devotion", 0) or 0) + amount
        target.db.bethany_devotion = dev
        if dev >= 40:
            self._milestone(target, achievement="devoted")
        try:
            from world.binding_effects import install_trigger
            install_trigger(target, "good girl for bethany", response="kneel", strength=1,
                            mantra="i'm bethany's")
            if dev >= 30:
                install_trigger(target, "bethany owns you", response="blank", strength=1,
                                permanent=(dev >= 60))
        except Exception:
            pass
        if dev >= 25 and getattr(target.db, "designation", None) != "Bethany's favourite":
            target.db.designation = "Bethany's favourite"
        if dev >= 50 and not getattr(target.db, "bethany_branded", False):
            target.db.bethany_branded = True
            self._milestone(target, achievement="her_mark")
            try:
                from world.gang_breeding import record_mark
                record_mark(target, "branded with a personal B — Property of Bethany, not the "
                            "facility: owned, specifically, and fond of it", mode="on", prefer="ass")
            except Exception:
                pass
            if room:
                room.msg_contents(f"|RBethany heats her own little iron and presses the |wB|R "
                                  f"into {target.db.rp_name or target.name} herself — not the "
                                  f"facility's mark, hers — and signs the ownership the one way "
                                  f"she never delegates.|n")

    # ── Curses: installed afflictions honored every applicable beat ──
    def _impose_curse(self, room, target, t):
        """Lay one of the standing curses into her if she hasn't got it yet. Installed
        during conditioning; honored thereafter by _tick_curses. Reset clears the flags."""
        pool = []
        if not getattr(target.db, "curse_line_remembers", False):
            pool.append("line")
        if not getattr(target.db, "curse_never_empty", False):
            pool.append("empty")
        if not getattr(target.db, "curse_tally", False):
            pool.append("tally")
        if not getattr(target.db, "curse_echo", False):
            pool.append("echo")
        if not getattr(target.db, "curse_hollow", False):
            pool.append("hollow")
        if not pool:
            return
        which = random.choice(pool)
        if which == "line":
            target.db.curse_line_remembers = True
            room.msg_contents("|M" + random.choice(_CURSE_LINE_INSTALL).format(t=t) + "|n")
        elif which == "empty":
            target.db.curse_never_empty = True
            room.msg_contents("|M" + random.choice(_CURSE_EMPTY_INSTALL).format(t=t) + "|n")
        elif which == "tally":
            target.db.curse_tally = True
            target.db.curse_tally_count = int(getattr(target.db, "curse_tally_count", 0) or 0)
            room.msg_contents("|M" + random.choice(_CURSE_TALLY_INSTALL).format(t=t) + "|n")
        elif which == "echo":
            target.db.curse_echo = True
            # ride the real speech-filter system — reset clears active_speech_filters
            active = list(getattr(target.db, "active_speech_filters", None) or [])
            if "echo_self" not in active:
                active.append("echo_self")
            target.db.active_speech_filters = active
            room.msg_contents("|M" + random.choice(_CURSE_ECHO_INSTALL).format(t=t) + "|n")
        else:  # hollow
            target.db.curse_hollow = True
            room.msg_contents("|M" + random.choice(_CURSE_HOLLOW_INSTALL).format(t=t) + "|n")
        try:
            from world.gang_breeding import record_mark
            record_mark(target, f"a curse-sigil set into her — '{which}', a standing affliction "
                        f"the facility laid in and does not intend to lift", mode="on")
        except Exception:
            pass

    def _tick_curses(self, char, t, cond, phase=None):
        """Each beat, the standing curses that apply bite. Defensive throughout.
        `phase` (the scene this beat ran) lets use-driven curses read whether she was
        worked this beat (Tally pays down on use, grows on idleness)."""
        try:
            room = char.location
            used_this_beat = phase in ("milk", "breed", "owned", "toilet", "punish", "deep", "nurse")
            # 'the tally' — strokes scored for idle beats, paid down by use; the debt itches.
            if getattr(char.db, "curse_tally", False):
                count = int(getattr(char.db, "curse_tally_count", 0) or 0)
                if used_this_beat:
                    if count > 0:
                        count = max(0, count - random.randint(2, 3))
                        char.db.curse_tally_count = count
                        if random.random() < 0.6:
                            char.msg("|m  " + random.choice(_CURSE_TALLY_PAID).format(t=t, n=count) + "|n")
                else:
                    count += 1
                    char.db.curse_tally_count = count
                    # the higher the unpaid tally, the worse the itch to be used
                    try:
                        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
                        ensure_arousal_script(char); add_arousal(char, 3.0 + min(count, 20) * 0.8)
                    except Exception:
                        pass
                    if count >= 12:
                        try:
                            from world.conditioning import add_conditioning
                            add_conditioning(char, 1.0, source="tally")
                        except Exception:
                            pass
                    if random.random() < 0.6:
                        char.msg("|m  " + random.choice(_CURSE_TALLY_BEAT).format(t=t, n=count) + "|n")
            # 'the hollow' — full never registers; the empty-ache runs under everything,
            # unconditionally (unlike never-empty, being filled does NOT quiet it).
            if getattr(char.db, "curse_hollow", False):
                try:
                    from typeclasses.arousal_script import add_arousal, ensure_arousal_script
                    ensure_arousal_script(char); add_arousal(char, 8.0 + cond * 0.04)
                    # keep a floor under her so satisfaction can't bank her all the way down
                    char.db.arousal_floor = max(float(getattr(char.db, "arousal_floor", 0) or 0), 35.0)
                except Exception:
                    pass
                if random.random() < 0.5:
                    char.msg("|m  " + random.choice(_CURSE_HOLLOW_BEAT).format(t=t) + "|n")
            # 'the line remembers' — a matured get in the room breeds its dam unprompted.
            if getattr(char.db, "curse_line_remembers", False) and room:
                roster = set(getattr(char.db, "offspring_roster", None) or [])
                get_here = [o for o in room.contents
                            if getattr(o, "dbref", None) in roster
                            and getattr(o.db, "matured", False)]
                if get_here and random.random() < 0.5:
                    try:
                        from world.gang_breeding import animal_holes, gang_inseminate
                        holes = [z for z in animal_holes(char).values() if z]
                        if holes:
                            gang_inseminate(char, random.choice(holes), contributors=1,
                                            fluid_type="semen", species="bethany")
                    except Exception:
                        pass
                    room.msg_contents("|r" + random.choice(_CURSE_LINE_BEAT).format(t=t) + "|n")
            # 'never empty' — left unfilled, the ache and arousal climb until she's filled.
            if getattr(char.db, "curse_never_empty", False):
                plugged = bool(getattr(char.db, "pen_plugged", None))
                if not plugged and random.random() < 0.6:
                    try:
                        from typeclasses.arousal_script import add_arousal, ensure_arousal_script
                        ensure_arousal_script(char)
                        add_arousal(char, 10.0 + cond * 0.05)
                    except Exception:
                        pass
                    char.msg("|m  " + random.choice(_CURSE_EMPTY_BEAT).format(t=t) + "|n")
        except Exception:
            pass

    # ── The Records Hall: catalogued, totted up, made to know her number ──
    def _records_hall(self, room, target, t, cond):
        """She's sat at the appraisal mirror and read off the ledger — her own account,
        line, and valuation recited back while she watches. Refreshes the live
        ledger-tattoo, runs the reinvestment books, and deepens via knowing her number."""
        room.msg_contents("|W" + random.choice(_RECORDS_BEATS).format(t=t) + "|n")
        price = self._appraise(target)
        # Read her balance aloud and refresh the body's own books (the ledger-tattoo).
        try:
            from world.economy import get_balance, debt_amount
            bal  = get_balance(target)
            owed = debt_amount(target)
            line = (f"|c  ▸ ON FILE — valuation |w{price:,}|c · account |w{bal:,}|c scrip"
                    + (f" · |rin arrears {owed:,}|c" if owed else "") + ".|n")
            room.msg_contents(line)
        except Exception:
            pass
        self._ledger_tattoo(target, t, price)
        # Knowing her number, exactly, settles deeper than any speech.
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 1.2 + cond * 0.004, source="records")
        except Exception:
            pass
        # The registrar keeps the lineage current — age her get toward the line.
        try:
            self._mature_get(target)
        except Exception:
            pass
        # The books are read here too; the house signs off what it can afford.
        self._try_reinvest(target)
        target.msg("  |m" + random.choice(_RECORDS_DEGRADE).format(t=t) + "|n")

    def _ledger_tattoo(self, target, t, price):
        """Ink (or refresh) a real freeform mark that displays her running total — the
        body kept as its own legible account. One install; refreshed in place after."""
        try:
            from world.gang_breeding import record_mark
            total = sum(int(v) for v in (getattr(target.db, "offspring_counts", None) or {}).values())
            text = random.choice(_LEDGER_TATTOO).format(total=total, price=f"{price:,}")
            if not getattr(target.db, "ledger_tattooed", False):
                record_mark(target, text, mode="on", prefer="hip")
                target.db.ledger_tattooed = True
            else:
                record_mark(target, text, mode="on", prefer="hip")
        except Exception:
            pass

    # Bethany's bespoke clauses — the facility's contract is boilerplate; what she
    # adds to her own property is not. Each is a real, enforced term, imposed one at a
    # time as she keeps you, logged in db.bethany_clauses (cleared by the reset).
    _BETHANY_CLAUSES = [
        ("honorific", "You will address me as Mistress, and answer when I call.",
         "Now say it. 'Yes, Mistress.' Good. You'll say it every time, or you won't be heard at all."),
        ("ledger",    "Your account is mine. What you owe me, you owe with your body.",
         "I keep your books, sweetheart — every credit you make and every one you cost. The balance "
         "is mine to read to you and mine to call. You'll never be out of my debt; that's the point of it."),
        ("name",      "Your name is mine to use or not. You answer to what I call you.",
         "I'll decide what you're called. You don't need the old one; it kept getting in the way of what you are."),
        ("collar",    "My collar stays on. It is not yours to question or remove.",
         "It locks here and it locks for good. You don't get a vote on your own throat anymore — that's rather the point."),
        ("crave",     "You will want me. Being empty of me will read as wrong.",
         "There. Now the having-me is a need, not a thing done to you. You'll ache for it between visits. You already are."),
        ("display",   "You stay bare and on display for me whenever I please.",
         "No covering yourself. I like to be able to see what I own, all of it, whenever I glance over the file."),
        ("line",      "You are bred by my line and mine alone — my get, in you, forever.",
         "The animals are for quota. You I keep for me. It'll be my eyes looking up at you out of every litter from now on."),
        ("tithe",     "A tenth of everything you earn is mine, off the top, forever.",
         "Every credit your body makes, a piece comes to me before it's even yours. You'll fund me "
         "with your own milk and never miss it — that's ownership, sweetheart: I don't take what you "
         "have, I take what you make."),
        ("heir",      "One in every litter is mine to keep and name. My blood, kept back.",
         "The rest go to quota and the block. But one from each drop I pull out and keep — named, "
         "mine, raised to my hand. Your line forks into my house now, a child at a time, and you "
         "make them for me."),
    ]

    def _impose_clause(self, room, target, t):
        log = list(getattr(target.db, "bethany_clauses", None) or [])
        remaining = [c for c in self._BETHANY_CLAUSES if c[0] not in log]
        # The 'heir' clause only becomes available once a line exists to take an heir from.
        try:
            from world.quests import has_achievement
            if not has_achievement(target, "bred_true"):
                remaining = [c for c in remaining if c[0] != "heir"]
        except Exception:
            pass
        if not remaining:
            return
        key, clause, line = random.choice(remaining)
        log.append(key)
        target.db.bethany_clauses = log
        # Real enforcement per clause.
        try:
            if key == "honorific":
                target.db.required_honorific = "Mistress"
            elif key == "name":
                if not getattr(target.db, "facility_name_backup", None):
                    target.db.facility_name_backup = target.db.rp_name or target.name
                target.db.designation = target.db.designation or "Bethany's favourite"
                target.db.rp_name = target.db.designation
            elif key == "collar":
                target.db.bethany_collar = True
                target.db.self_cmds_locked = True
                self._milestone(target, achievement="collared")
                # Lock a real personal collar on her — worn, binding, hers.
                try:
                    from evennia import create_object
                    from typeclasses.facility_implants import BethanyCollar
                    if not any(isinstance(o, BethanyCollar) for o in target.contents):
                        col = create_object(BethanyCollar, key="Bethany's collar", location=target)
                        zones = getattr(target.db, "zones", None) or {}
                        nz = next((z for z in zones if "neck" in z or "throat" in z or "collar" in z), None)
                        ok, _r = col.wear(target, nz) if hasattr(col, "wear") else (False, "")
                        if ok:
                            from world.binding_effects import apply_effects
                            apply_effects(target, col)
                            items = list(getattr(target.db, "facility_items", None) or [])
                            items.append(col.dbref); target.db.facility_items = items
                except Exception:
                    pass
            elif key == "crave":
                target.db.cum_craving = True
            elif key == "display":
                target.db.exhibition_active = True
                target.db.anti_clothing_active = True
            elif key == "line":
                target.db.bethany_line_only = True
            elif key == "tithe":
                target.db.bethany_tithe = True
            elif key == "heir":
                target.db.bethany_heir = True
            elif key == "ledger":
                # Her account is now Bethany's leash: a standing debt-bond she serves with
                # her body. Seeds a marker against her and inks the ledger-tattoo.
                target.db.bethany_ledger_bond = True
                try:
                    from world.economy import spend_credits
                    spend_credits(target, 1500, "Bethany's ledger clause — a standing marker "
                                  "against you, served with your body.", allow_debt=True)
                except Exception:
                    pass
                self._ledger_tattoo(target, target.db.rp_name or target.name,
                                    self._appraise(target))
        except Exception:
            pass
        room.msg_contents(
            f"|MBethany adds a line to your file in her own hand — a personal clause, not the "
            f"facility's: |w\"{clause}\"|M — and reads it to you soft and fond as she signs it "
            f"into you. \"{line}\"|n")

    def _office(self, room, target, t, cond):
        """Bethany has bought you and pulled you off the line into her office. The
        throne does everything at once on her dial while she works and watches — and
        every visit reorganises you a little more thoroughly around her."""
        # The first days are the breaking-in — bespoke, intensive, personal. She uncovers
        # the breaking frame, and the struggle (real, in-fiction, and futile) gets its beat.
        if float(getattr(target.db, "bethany_devotion", 0) or 0) < 8 and random.random() < 0.7:
            room.msg_contents("|y" + random.choice(_OFFICE_FIRSTDAY).format(t=t) + "|n")
            target.msg("  |M" + random.choice(_CNC_BREAK) + "|n")
        room.msg_contents("|y" + random.choice(_OFFICE_BEATS).format(t=t) + "|n")
        # The throne runs every system at once, hands-free, on her dial.
        self._do_milk(room, target, t)
        if random.random() < 0.5:
            self._grow_udder(room, target, t)
        if random.random() < 0.6:
            self._dose(room, target, t)
        # She breeds you herself, with her own cock — her line, which joins the roster.
        try:
            from world.gang_breeding import animal_holes, gang_inseminate
            holes = [z for z in animal_holes(target).values() if z]
            beth = next((o for o in room.contents if (o.key or "").lower() == "bethany"), None)
            if holes and random.random() < 0.6:
                z = random.choice(holes)
                gang_inseminate(target, z, contributors=1, fluid_type="semen", species="bethany")
                if beth:
                    self._real_penetrate(room, beth, target, z, "bethany")
                room.msg_contents("|r" + random.choice(_OFFICE_BREED).format(t=t) + "|n")
        except Exception:
            pass
        # Devotion + the occasional possessive set-piece (collar, brand, a soft cruelty).
        self._devote(target, random.uniform(2.0, 4.0), room=room)
        if random.random() < 0.4:
            room.msg_contents("|M" + random.choice(_OFFICE_OWN).format(t=t) + "|n")
        # And now and then she writes you a new personal clause.
        if random.random() < 0.3:
            self._impose_clause(room, target, t)
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 2.0 + cond * 0.006, source="bethany")
        except Exception:
            pass
        # From her desk Bethany reads the treasury and signs off the next upgrade.
        self._try_reinvest(target)
        target.msg("  |m" + random.choice(_OFFICE_DEGRADE).format(t=t) + "|n")

    # ── Deep Stock: the Perfected end-state, sealed and kept on the lines ──
    def _deepstock(self, room, target, t, cond):
        """Grade-gated terminus: she's sealed into her pod and run on the lines —
        milked and bred through ports without being woken, the loop's quiet end."""
        try:
            from world.quests import grant_achievement
            grant_achievement(target, "deep_stock")
        except Exception:
            pass
        # Down here she's kept latex-sealed by default.
        if not getattr(target.db, "latex_sealed", False):
            try:
                self._proc_latex(room, target, t)
            except Exception:
                target.db.latex_sealed = True
        room.msg_contents("|x" + random.choice(_DEEP_BEATS).format(t=t) + "|n")
        # Still milked and bred — just through the lines, hands-free, no scene.
        self._do_milk(room, target, t)
        try:
            from world.gang_breeding import animal_holes, gang_inseminate
            holes = [z for z in animal_holes(target).values() if z]
            if holes:
                gang_inseminate(target, random.choice(holes), contributors=1,
                                fluid_type="semen", species=self._pick_species(target))
        except Exception:
            pass
        # The lowest hum of conditioning, forever — and the terrible peace of it.
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 0.8 + cond * 0.003, source="deepstock")
        except Exception:
            pass
        target.msg("  |x" + random.choice(_DEEP_DEGRADE).format(t=t) + "|n")

    # ── The Showroom: appraised, priced off her own stats, and sold ──
    _GRADE_ORDER = ["Unprocessed", "Intake", "Breaking In", "Breeding Stock",
                    "Broodmare", "Perfected Livestock"]

    def _appraise(self, target):
        """Compute her sale price from her own particulars — grade, get, yield,
        trained capabilities, conditioning. Stored on db.sale_price."""
        grade = getattr(target.db, "facility_grade", None) or "Unprocessed"
        gi = self._GRADE_ORDER.index(grade) if grade in self._GRADE_ORDER else 0
        counts = sum(int(v) for v in (getattr(target.db, "offspring_counts", None) or {}).values())
        cond = float(getattr(target.db, "conditioning", 0) or 0)
        milk = float(getattr(target.db, "milk_baseline_ml", 0) or 0) / 1000.0
        caps = 0
        try:
            from world.gang_breeding import hole_capabilities, animal_holes
            for z in animal_holes(target).values():
                if z:
                    caps += len(hole_capabilities(target, z))
        except Exception:
            pass
        gravid = 800 if getattr(target.db, "pregnancy", None) else 0
        price = int(1200 * gi + 220 * counts + 260 * caps + 6 * cond + 40 * milk + gravid + 500)
        # Showroom-expansion upgrades make the house dearer — her own funded inflation.
        sb = int(getattr(target.db, "sale_bonus", 0) or 0)
        if sb:
            price = int(price * (1 + 0.15 * sb))
        target.db.sale_price = price
        return price

    def _gallery_of(self, room):
        """The buyers' gallery adjacent to this showroom, if dug."""
        if not room:
            return None
        for ex in room.exits:
            dest = getattr(ex, "destination", None)
            if dest and "gallery" in (getattr(dest, "key", "") or "").lower():
                return dest
        return None

    def _npc_bidding(self, room, target, floor):
        """A round of the standing NPC clientele bidding the lot up. Keeps the booths
        never-empty and the price climbing on its own; an NPC can top a live player's
        standing bid (they must re-`bid` to hold her). Bethany bids hard on ones she's
        claimed. Mutates db.high_bid/high_bidder and narrates into the gallery."""
        gallery = self._gallery_of(room)
        current = max(int(floor or 0), int(getattr(target.db, "high_bid", 0) or 0))
        # a player holds it if the current high_bidder is a real name, not one of ours
        pc_held = (int(getattr(target.db, "high_bid", 0) or 0) > 0
                   and getattr(target.db, "high_bidder", None) not in _NPC_BIDDERS
                   and getattr(target.db, "high_bidder", None) is not None)
        for _ in range(random.randint(1, 3)):
            # the room sometimes lets a standing player bid ride a round
            if pc_held and random.random() < 0.45:
                break
            who = random.choice(_NPC_BIDDERS)
            raise_by = random.randint(max(100, current // 20), max(300, current // 6))
            if who == "Bethany" and (getattr(target.db, "bethany_owned", False)
                                     or random.random() < 0.5):
                raise_by = int(raise_by * 1.6)
            current += raise_by
            topping_pc = pc_held
            target.db.high_bid       = current
            target.db.high_bidder    = who
            target.db.high_bidder_id = None   # an NPC holds it now — no player to charge
            pc_held = False
            if gallery:
                pool = _NPC_OUTBID_PC if topping_pc else _NPC_BID_LINES
                gallery.msg_contents(random.choice(pool).format(who=who, amt=f"{current:,}"))

    # ── The live, timed gavel: a bidding window that auto-resolves ──────────────
    def _open_auction(self, room, target, t, price):
        """Open a timed live gavel on this lot: a window of NPC bid rounds and a
        last-chance countdown, then `_auction_gavel` resolves it automatically. A live
        player can `bid`/`tip` the whole time. Returns True if the timer armed (caller
        then skips the instant sale); False if `delay` is unavailable (caller falls back).
        OOC-floor-safe: every callback re-checks `auction_open`/`facility_active`, and the
        flag is in the reset spec, so a purge mid-auction makes the gavel a no-op."""
        try:
            from evennia.utils import delay
        except Exception:
            try:
                from evennia.utils.utils import delay
            except Exception:
                return False
        target.db.auction_open  = True
        target.db.auction_floor = int(price)
        open_line = (f"|W*** LOT OPEN — {t} on the block. Floor |w{price:,}|W. The bidding's "
                     f"live and the hammer falls in a minute or two. ***|n")
        room.msg_contents(open_line)
        gallery = self._gallery_of(room)
        if gallery:
            gallery.msg_contents(open_line + f" |c(|wbid {t.split()[0].lower()}|c · "
                                 f"|wtip <what>|c)|n")
            # the booths pay to be filled: members present earn attendance scrip to spend
            try:
                from world.economy import earn
                for o in gallery.contents:
                    if o is target:
                        continue
                    if getattr(o.db, "is_pc", False) or o.has_account:
                        earn(o, "attend")
            except Exception:
                pass
        try:
            delay(20, self._auction_step,  target, room, t, 0)
            delay(40, self._auction_step,  target, room, t, 1)
            delay(58, self._auction_step,  target, room, t, 2)
            delay(70, self._auction_step,  target, room, t, 3)
            delay(80, self._auction_gavel, target, room, t)
        except Exception:
            target.db.auction_open = False
            return False
        return True

    def _auction_step(self, target, room, t, stage):
        """One tick of the live window: another NPC round climbs the price, and a
        countdown beat lands in the room + gallery. Defensive against a moved/reset lot."""
        try:
            if not target or not target.pk:
                return
            if not getattr(target.db, "auction_open", False):
                return
            if not getattr(target.db, "facility_active", False):
                target.db.auction_open = False
                return
            rm = room if (room and room.pk) else target.location
            floor = int(getattr(target.db, "auction_floor", 0) or self._appraise(target))
            self._npc_bidding(rm, target, floor)
            line = _GAVEL_COUNTDOWN[max(0, min(stage, 3))].format(t=t)
            if rm:
                rm.msg_contents(line)
            gallery = self._gallery_of(rm)
            if gallery:
                gallery.msg_contents(line)
        except Exception:
            pass

    def _auction_gavel(self, target, room, t):
        """The hammer falls: resolve to the standing high bidder (player or NPC), or pass
        the lot in if nobody bid. Closes the auction either way. If the lot was dragged out
        of the showroom before the gavel, the auction lapses with no sale."""
        try:
            if not target or not target.pk:
                return
            if not getattr(target.db, "auction_open", False):
                return
            target.db.auction_open = False
            if not getattr(target.db, "facility_active", False):
                return
            if getattr(target.db, "facility_owner", None):
                return
            # she must still be on the block — if the cycle moved her, the auction lapses
            if not (room and room.pk and target.location == room):
                if target.location:
                    target.location.msg_contents(f"|xThe bidding on {t} lapses — she's already "
                                                 f"been walked back to the line. Withdrawn.|n")
                target.db.high_bid = None
                target.db.high_bidder = None
                return
            high = int(getattr(target.db, "high_bid", 0) or 0)
            if high:
                self._sell(room, target, t, max(high, self._appraise(target)))
            else:
                room.msg_contents(f"|x\"No takers. Lot passes.\" {t} is walked back off the "
                                  f"block, unsold — this time.|n")
        except Exception:
            pass

    def _showroom(self, room, target, t, cond):
        """Posed on the block, appraised aloud, bid on through the glass, and — when
        the gavel falls — sold. Sale is in-fiction (the OOC floor still frees her).
        Some visits it's not her on the block but her own grown get, cashed out."""
        # The lineage gets sold too: now and then the lot is her get, not her. With a
        # gallery present it goes up as a LIVE timed lot players can bid on; otherwise
        # it's resolved instantly against the house.
        if random.random() < 0.4:
            gallery = self._gallery_of(room)
            if gallery and self._post_get_lot(room, target, t):
                return
            if self._sell_get(room, target, t):
                return
        price = self._appraise(target)
        target.db.body_language = "posed on the block — lit, spread, turning for the glass"
        room.msg_contents("|W" + random.choice(_SHOW_BEATS).format(t=t) + "|n")
        room.msg_contents("|c" + random.choice(_SHOW_APPRAISE).format(t=t, price=f"{price:,}")
                          + "|n")
        # Cue the booths: if anyone's seated behind the glass, open her for viewing so
        # bid/tip light up during the real cycle, not just on demand.
        gallery = self._gallery_of(room)
        if gallery:
            occupied = any(getattr(o.db, "is_pc", False) or o.has_account
                           for o in gallery.contents if o is not target)
            high = int(getattr(target.db, "high_bid", 0) or 0)
            standing = (f" Standing bid behind the glass: |w{high:,}|c." if high else "")
            gallery.msg_contents(
                f"|cThe glass brightens: a new lot is led onto the block. {t} is posed and lit "
                f"for the booths — grade read out, floor at |w{price:,}|c.{standing} "
                f"(|wbid {t.split()[0].lower()}|c · |wtip <what>|c)|n")
        else:
            occupied = False
        # Seed the bidding with an opening NPC round — the booths are never empty.
        self._npc_bidding(room, target, price)
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 1.0 + cond * 0.004, source="showroom")
        except Exception:
            pass
        # A live, timed gavel: open the bidding for a ~minute-plus window (NPC rounds + a
        # going-once/twice countdown a watching player can interrupt with `bid`), then it
        # auto-resolves. Skip if she's already owned or an auction's already open.
        if (not getattr(target.db, "facility_owner", None)
                and not getattr(target.db, "auction_open", False)
                and self._open_auction(room, target, t, price)):
            target.msg("  |m" + random.choice(_SHOW_DEGRADE).format(t=t) + "|n")
            return
        # Fallback — no timer available: resolve the gavel instantly, as before. Fair to a
        # present player (winning → 0.85 they take her; present-but-behind → 0.15; empty → 0.30).
        pc_on_top = (int(getattr(target.db, "high_bid", 0) or 0) > 0
                     and getattr(target.db, "high_bidder", None) not in _NPC_BIDDERS
                     and getattr(target.db, "high_bidder", None) is not None)
        if occupied:
            sell_chance = 0.85 if pc_on_top else 0.15
        else:
            sell_chance = 0.30
        if not getattr(target.db, "facility_owner", None) and random.random() < sell_chance:
            self._sell(room, target, t, price)
        else:
            target.msg("  |m" + random.choice(_SHOW_DEGRADE).format(t=t) + "|n")

    def _sell(self, room, target, t, price):
        # A live player's standing high bid wins at the gavel — bidding has consequence.
        high     = int(getattr(target.db, "high_bid", 0) or 0)
        high_who = getattr(target.db, "high_bidder", None)
        # Intake's futa keeps a standing bid; she usually wins the ones she wants — but only
        # if no player has topped her. A real high bid takes precedence.
        bethany_bid = (not high) and (getattr(target.db, "bethany_owned", False)
                                      or random.random() < 0.4)
        if high and high_who:
            owner, suffix = high_who, f"— {high_who}'s"
            price = max(price, high)
            if high_who == "Bethany":
                target.db.bethany_owned = True
        elif bethany_bid:
            owner, suffix = "Bethany", "— Bethany's"
            target.db.bethany_owned = True
        else:
            owner = random.choice(["a private breeding concern", "an anonymous buyer",
                                   "the deep-stock division", "a kennel syndicate"])
            suffix = "— Sold Stock"
        target.db.facility_owner = owner
        if getattr(target.db, "bethany_owned", False):
            self._milestone(target, achievement="bought")
        # Back up the title once so the reset restores it; stamp the new owner.
        if not getattr(target.db, "facility_title_backup", None):
            target.db.facility_title_backup = {
                "faction": getattr(target.db, "title_faction", "") or "",
                "suffix":  getattr(target.db, "title_suffix", "") or "",
            }
        target.db.title_suffix = suffix
        room.msg_contents("|R" + random.choice(_SHOW_SOLD).format(
            t=t, owner=owner, price=f"{price:,}") + "|n")
        try:
            from world.gang_breeding import record_mark
            record_mark(target, f"a sale tag wired to her — SOLD, lot price {price:,}, to {owner}",
                        mode="on")
        except Exception:
            pass
        # Economy: settle the sale in scrip. The winning *player* is actually charged
        # their bid; she's credited a pittance "cut" of her own price (a cruelty, not a
        # kindness — money she'll never spend on the door). NPC buyers move house money.
        try:
            from world.economy import add_credits, spend_credits
            add_credits(target, max(50, int(price) // 50),
                        f"Sale cut credited — a pittance of your own price ({price:,}).")
            buyer_id = getattr(target.db, "high_bidder_id", None)
            if high and buyer_id:
                from evennia import search_object
                buyer = (search_object("#%d" % int(buyer_id)) or [None])[0]
                if buyer and buyer is not target:
                    ok, bal = spend_credits(buyer, int(price),
                                            f"Purchase — lot {t} taken at the gavel.")
                    if ok:
                        buyer.msg(f"|R{int(price):,} scrip clears your account — {t} is yours.|n")
                    else:
                        # carry the marker against them — real debt, down to the floor
                        ok2, bal = spend_credits(buyer, int(price), allow_debt=True,
                                                 reason=f"Purchase on credit — lot {t} taken; "
                                                        f"marker carried against you.")
                        if ok2:
                            buyer.msg(f"|R{int(price):,} scrip — you didn't have it. The house "
                                      f"carries the marker (balance |w{bal:,}|R). {t} is yours; "
                                      f"the debt is too. See |wtab|R.|n")
                        else:
                            buyer.msg(f"|x{int(price):,} would put you past what even the house "
                                      f"will carry. The lot stands.|n")
        except Exception:
            pass
        # The house takes its cut of the sale into the treasury, files the polaroid, and
        # turns the profit straight back into upgrading her.
        try:
            from world.economy import skim
            skim(target, price, f"House cut — sale of {t} to {owner} at {price:,}.")
        except Exception:
            pass
        self._file_polaroid(target, "sale", t, price, owner)
        self._try_reinvest(target)
        # Gavel's down: the auction's settled, so the standing bid is consumed. If a live
        # player (not one of the house's NPC bidders) won, tell the gallery their bid took her.
        if high and high_who and high_who not in _NPC_BIDDERS:
            gallery = self._gallery_of(room)
            if gallery:
                gallery.msg_contents(f"|RThe gavel falls in the dark: {t} goes to {high_who} "
                                     f"for |w{price:,}|R. Sold, tagged, yours.|n")
        target.db.high_bid = None
        target.db.high_bidder = None
        target.db.high_bidder_id = None
        try:
            from world.quests import grant_achievement
            grant_achievement(target, "sold_off")
        except Exception:
            pass

    def _appraise_get(self, o, dam):
        """Price one of her grown get from its generation/species and the dam's grade."""
        gen = int(getattr(o.db, "generation", 1) or 1)
        sp  = getattr(o.db, "species", "get")
        dg  = getattr(dam.db, "facility_grade", None)
        di  = self._GRADE_ORDER.index(dg) if dg in self._GRADE_ORDER else 0
        base = 800 + 300 * gen + 150 * di
        if sp == "bethany":
            base = int(base * 1.5)   # Bethany's own line sells dear
        return int(base * random.uniform(0.85, 1.3))

    def _sell_get(self, room, target, t):
        """Put one of her matured get on the block in her place — appraised, bid up by
        the house, sold, and a breeder's cut dropped into the dam's account while she's
        made to watch. Pulls it out of the bred-back roster. Returns True if one sold."""
        try:
            from evennia import search_object
        except Exception:
            return False
        roster = list(getattr(target.db, "offspring_roster", None) or [])
        grown = []
        for ref in roster:
            o = (search_object(ref) or [None])[0]
            if (o and getattr(o.db, "matured", False) and not getattr(o.db, "sold_off", False)
                    and not getattr(o.db, "bethany_heir", False)):  # heirs are kept, never sold
                grown.append((ref, o))
        if not grown:
            return False
        ref, o = random.choice(grown)
        sp  = getattr(o.db, "species", "get")
        gen = int(getattr(o.db, "generation", 1) or 1)
        price = self._appraise_get(o, target)
        for _ in range(random.randint(1, 3)):     # a quick house bidding climb
            price += random.randint(max(50, price // 12), max(120, price // 5))
        buyer = random.choice([b for b in _NPC_BIDDERS if b != "Bethany"] + ["Bethany", "Bethany"])
        room.msg_contents("|R" + random.choice(_GET_SALE).format(
            t=t, sp=sp, gen=gen, buyer=buyer, price=f"{price:,}") + "|n")
        gallery = self._gallery_of(room)
        if gallery:
            gallery.msg_contents(f"|RA lot off {t}'s line: a gen-{gen} {sp} of hers, knocked down "
                                 f"to {buyer} for |w{price:,}|R.|n")
        try:    # breeder's cut to her; the house takes the lion's share into the treasury
            from world.economy import add_credits, skim
            add_credits(target, max(50, price // 10),
                        f"Breeder's cut — your gen-{gen} {sp} get sold to {buyer} for {price:,}.")
            skim(target, price, f"House cut — sale of her gen-{gen} {sp} get to {buyer}.")
        except Exception:
            pass
        try:    # logged on her record as a real mark
            from world.gang_breeding import record_mark
            record_mark(target, f"a sale record wired to her — her gen-{gen} {sp} get sold off "
                                f"to {buyer}, {price:,}", mode="on")
        except Exception:
            pass
        if ref in roster:
            roster.remove(ref)
            target.db.offspring_roster = roster
        if buyer == "Bethany":
            target.db.bethany_owned_get = True
        try:    # it's sold away — gone from the grid (and the bred-back loop)
            o.delete()
        except Exception:
            try: o.location = None
            except Exception: pass
        target.msg("  |m" + random.choice(_SHOW_DEGRADE).format(t=t) + "|n")
        self._file_polaroid(target, "get", f"her gen-{gen} {sp} get", price, buyer)
        self._try_reinvest(target)
        return True

    # ── House treasury: reinvestment, bounties, the filed polaroids ────────────
    def _file_polaroid(self, owner, kind, subject, price, buyer):
        """Document a sale parlour-style — a polaroid filed to her record (the wall
        the `records` command pages through)."""
        try:
            import time as _t
            pol = list(getattr(owner.db, "facility_polaroids", None) or [])
            pol.append({"date": _t.strftime("%Y-%m-%d %H:%M"), "kind": kind,
                        "subject": subject, "price": int(price), "buyer": buyer,
                        "cap": random.choice(_POLAROID_CAPS)})
            owner.db.facility_polaroids = pol[-50:]
        except Exception:
            pass

    def _try_reinvest(self, owner):
        """Spend the treasury on the cheapest worthwhile upgrade, apply its live effect,
        and announce it. One purchase per call so it stays a slow, visible ramp."""
        try:
            from world.economy import next_affordable_upgrade, buy_upgrade
        except Exception:
            return
        buy = next_affordable_upgrade(owner)
        if not buy:
            return
        key, cost, new_level, blurb = buy
        if not buy_upgrade(owner, key, cost, new_level):
            return
        self._apply_upgrade(owner, key, new_level)
        room = owner.location
        if room:
            room.msg_contents(random.choice(_REINVEST_BEATS).format(blurb=blurb))

    def _apply_upgrade(self, owner, key, level):
        """Apply the live effect of an upgrade the house just bought — real knobs only."""
        try:
            if key == "studs":
                q = dict(getattr(owner.db, "breeding_quota", None) or {})
                if q and all(not isinstance(v, dict) for v in q.values()):
                    for sp in list(q.keys()):
                        q[sp] = int(q[sp]) + 1
                    owner.db.breeding_quota = q
            elif key == "bounty":
                owner.db.get_bounty = 200 + 150 * level   # paid out on each maturation
            elif key == "line":
                # cycle her harder — shorten the interval, with a floor.
                try:
                    self.interval = max(60, int(self.interval * 0.85))
                    self.restart(interval=self.interval)
                except Exception:
                    pass
            elif key == "suite":
                owner.db.cond_bonus = level            # read in at_repeat's conditioning tick
            elif key == "cups":
                owner.db.milk_bonus = level             # read where milk yield is credited
            elif key == "showroom":
                owner.db.sale_bonus = level             # read in _appraise as a price multiplier
            elif key == "pharmacy":
                owner.db.dose_bonus = level             # heavier doses (hook for the dose scene)
            elif key == "archive":
                # A richer archive raises the bounty on her get and her facility standing.
                owner.db.get_bounty = max(int(getattr(owner.db, "get_bounty", 0) or 0),
                                          150 + 120 * level)
                try:
                    from world.factions import add_standing
                    add_standing(owner, source="cycle", amount=20 * level)
                except Exception:
                    pass
            elif key == "collections":
                owner.db.collections_level = level       # markers called harder (indenture notices)
        except Exception:
            pass

    def _pay_get_bounty(self, owner, sp, gen):
        """If a bounty stands, pay it out of the treasury to her account on a maturation."""
        try:
            from world.economy import house_debit, add_credits
            bounty = int(getattr(owner.db, "get_bounty", 0) or 0)
            if bounty <= 0:
                return
            ok, _bal = house_debit(owner, bounty, f"Get bounty paid — gen-{gen} {sp} matured.")
            if ok:
                add_credits(owner, bounty, f"Get bounty — your gen-{gen} {sp} matured and paid out.")
        except Exception:
            pass

    # ── Live get auctions: a grown get on the timed block, bid on by real players ──
    def _post_get_lot(self, room, dam, t):
        """Put one of the dam's matured get up as a LIVE, timed lot — players can `bid`
        it through the gallery and steal it at the wire; resolves in `_get_gavel`. Returns
        True if one was posted. Isolated from her own auction so it can't disturb it."""
        try:
            from evennia.utils import delay
        except Exception:
            try:
                from evennia.utils.utils import delay
            except Exception:
                return False
        from evennia import search_object
        grown = []
        for ref in list(getattr(dam.db, "offspring_roster", None) or []):
            o = (search_object(ref) or [None])[0]
            if (o and getattr(o.db, "matured", False) and not getattr(o.db, "sold_off", False)
                    and not getattr(o.db, "bethany_heir", False)
                    and not getattr(o.db, "auction_open", False)):
                grown.append(o)
        if not grown:
            return False
        get = random.choice(grown)
        sp  = getattr(get.db, "species", "get")
        gen = int(getattr(get.db, "generation", 1) or 1)
        try:
            if get.location != room:
                get.move_to(room, quiet=True)
        except Exception:
            pass
        price = self._appraise_get(get, dam)
        get.db.auction_open  = True
        get.db.auction_floor = price
        get.db.high_bid = 0
        get.db.high_bidder = None
        get.db.high_bidder_id = None
        get.db.get_lot_dam = dam.id
        gn = get.db.rp_name or get.key
        open_line = (f"|W*** GET LOT OPEN — {t}'s own gen-{gen} {sp} on the block. Floor "
                     f"|w{price:,}|W. Bid live; the hammer falls shortly. ***|n")
        room.msg_contents(open_line)
        gallery = self._gallery_of(room)
        if gallery:
            gallery.msg_contents(open_line + f" |c(|wbid {gn.split()[0].lower()}|c)|n")
        try:
            delay(20, self._get_bid_step, get, room, 1)
            delay(45, self._get_bid_step, get, room, 2)
            delay(65, self._get_bid_step, get, room, 3)
            delay(80, self._get_gavel,    get, room)
        except Exception:
            get.db.auction_open = False
            return False
        dam.msg("  |m" + random.choice(_RECORDS_DEGRADE).format(t=t) + "|n")
        return True

    def _get_bid_step(self, get, room, stage):
        try:
            if not get or not get.pk or not getattr(get.db, "auction_open", False):
                return
            rm = room if (room and room.pk) else get.location
            self._npc_bidding(rm, get, int(getattr(get.db, "auction_floor", 0) or 0))
            if rm:
                rm.msg_contents(_GAVEL_COUNTDOWN[max(0, min(stage, 3))].format(
                    t=get.db.rp_name or get.key))
        except Exception:
            pass

    def _get_gavel(self, get, room):
        try:
            if not get or not get.pk or not getattr(get.db, "auction_open", False):
                return
            get.db.auction_open = False
            from evennia import search_object
            dam = (search_object("#%d" % int(getattr(get.db, "get_lot_dam", 0) or 0))
                   or [None])[0]
            rm  = room if (room and room.pk) else get.location
            sp  = getattr(get.db, "species", "get")
            gen = int(getattr(get.db, "generation", 1) or 1)
            high  = int(getattr(get.db, "high_bid", 0) or 0)
            who   = getattr(get.db, "high_bidder", None)
            price = max(high, int(getattr(get.db, "auction_floor", 0) or 0))
            buyer = who or random.choice([b for b in _NPC_BIDDERS if b != "Bethany"])
            bid_id = getattr(get.db, "high_bidder_id", None)
            if high and bid_id:
                pb = (search_object("#%d" % int(bid_id)) or [None])[0]
                if pb and pb is not get:
                    try:
                        from world.economy import spend_credits
                        ok, _b = spend_credits(pb, price, allow_debt=True,
                                               reason=f"Purchase — gen-{gen} {sp} get at the gavel.")
                        pb.msg(f"|R{price:,} scrip — the gen-{gen} {sp} is yours.|n")
                    except Exception:
                        pass
            tname = (dam.db.rp_name or dam.key) if dam else "the dam"
            if rm:
                rm.msg_contents("|R" + random.choice(_GET_SALE).format(
                    t=tname, sp=sp, gen=gen, buyer=buyer, price=f"{price:,}") + "|n")
            if dam and getattr(dam.db, "facility_active", False):
                try:
                    from world.economy import add_credits, skim
                    add_credits(dam, max(50, price // 10),
                                f"Breeder's cut — your gen-{gen} {sp} get sold live to {buyer}.")
                    skim(dam, price, f"House cut — live sale of gen-{gen} {sp} get to {buyer}.")
                except Exception:
                    pass
                try:
                    from world.gang_breeding import record_mark
                    record_mark(dam, f"a sale record — her gen-{gen} {sp} get sold live on the "
                                f"block to {buyer}, {price:,}", mode="on")
                except Exception:
                    pass
                self._file_polaroid(dam, "get", f"her gen-{gen} {sp} get (live lot)", price, buyer)
                roster = list(getattr(dam.db, "offspring_roster", None) or [])
                if get.dbref in roster:
                    roster.remove(get.dbref)
                    dam.db.offspring_roster = roster
                self._try_reinvest(dam)
            try:
                get.delete()
            except Exception:
                try:
                    get.location = None
                except Exception:
                    pass
        except Exception:
            pass

    def _made_to_beg(self, room, target, t):
        """She's made to beg — out loud, for it — and begging is the only path to the
        granted release denial otherwise withholds. Conditioned, it becomes reflex."""
        room.msg_contents("|m" + random.choice(_BEG_BEATS).format(t=t) + "|n")
        self._milestone(target, achievement="begged")
        try:
            from world.binding_effects import install_trigger, _inst_beg
            _inst_beg(target, target, room, {})          # the begging itself
            install_trigger(target, "beg for it", response="beg", strength=1)
        except Exception:
            pass
        # Begging is compliance — and compliance is the only thing that buys relief.
        try:
            from world.compliance import register_compliance
            register_compliance(target, reward=True)
        except Exception:
            pass

    # ── The Dairy & Output: milked, measured, displayed as product ──
    def _dairy(self, room, target, t, cond):
        """Her output room: actually milked here (real drain), her totals thrown in
        her face, and she's displayed and handled as product, not person."""
        room.msg_contents("|c" + random.choice(_DAIRY_BEATS).format(t=t) + "|n")
        self._do_milk(room, target, t)              # real ml drained + banked
        if random.random() < 0.6:
            self._grow_udder(room, target, t)       # bigger and more productive each time
        if getattr(target.db, "breeding_quota", None):
            target.msg("|m" + self._quota_board(target) + "|n")
        if random.random() < 0.5:
            room.msg_contents("|c" + random.choice(_DAIRY_DISPLAY).format(t=t) + "|n")
        target.msg("  |m" + random.choice(_DAIRY_DEGRADE).format(t=t) + "|n")
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 1.0 + cond * 0.004, source="dairy")
        except Exception:
            pass

    # ── The Nursery: she feeds her get her milk, and watches them grow toward her ──
    def _nurse(self, room, target, t, cond):
        """Hooked to the nursing frame and milked (real) into her own brood, facing the
        pens, made to watch the generations she's raising grow toward the stalls — and
        bred here too, sometimes, by the ones already grown."""
        room.msg_contents("|c" + random.choice(_NURSE_BEATS).format(t=t) + "|n")
        self._milestone(target, achievement="nursed")
        self._do_milk(room, target, t)          # real drain — piped to her get
        # If any of her get have matured back into the pens, one may be brought to breed her.
        try:
            present = [o for o in room.contents
                       if getattr(o.db, "is_offspring", False) and getattr(o.db, "matured", False)]
            from world.gang_breeding import animal_holes
            holes = [z for z in animal_holes(target).values() if z]
            if present and holes and random.random() < 0.4:
                self._breed_one(room, target, random.choice(holes),
                                getattr(present[0].db, "species", "hound"), cond)
        except Exception:
            pass
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 1.0 + cond * 0.004, source="nursery")
        except Exception:
            pass
        target.msg("  |m" + random.choice(_NURSE_DEGRADE).format(t=t) + "|n")

    # ── The Pigsty: slopped, hosed, rutted in the muck, put back ──
    def _sty(self, room, target, t, cond):
        """Punishment / bottom-tier: she's kept on all fours in the filth, slopped,
        hosed, and rutted — and the lesson lands as conditioning + degradation."""
        room.msg_contents("|y" + random.choice(_STY_BEATS).format(t=t) + "|n")
        self._milestone(target, achievement="pigsty")
        # The sty breeds her too, in the muck — real deposit when stock's about.
        try:
            from world.gang_breeding import animal_holes, apply_filth
            holes = [z for z in animal_holes(target).values() if z]
            if holes and random.random() < 0.6:
                z = random.choice(holes)
                self._breed_one(room, target, z, self._pick_species(target), cond, gape_mult=1.2)
                room.msg_contents("|r" + random.choice(_STY_RUT).format(t=t) + "|n")
            apply_filth(target)
        except Exception:
            pass
        try:
            from world.compliance import punish
            punish(target, reason="kept in the sty", severity=1)
        except Exception:
            pass
        target.msg("  |m" + random.choice(_STY_DEGRADE).format(t=t) + "|n")

    # ── The Sanitation Block: used as a relief-hole, toilet, and urinal ──
    def _toilet(self, room, target, t, cond):
        """The restroom uses her as plumbing: the glory wall (anonymous cocks),
        the meat-toilet frame (used from the seat), and the urinal (pissed into and
        held full). Real deposits (semen via gang_inseminate, urine to the fluid
        bank + bladder), real filth marks, real bladder backing."""
        from world.gang_breeding import animal_holes, apply_filth
        ah = animal_holes(target)
        holes = [z for z in ah.values() if z]
        mouth = ah.get("mouth")
        if not holes:
            return

        mode = random.choice(["wall", "wall", "seat", "urinal"])

        if mode == "urinal":
            room.msg_contents("|y" + random.choice(_TOILET_PISS).format(t=t) + "|n")
            ml = random.uniform(250, 650)
            self._take_piss(target, ml)
        else:
            pool = _TOILET_WALL if mode == "wall" else _TOILET_SEAT
            room.msg_contents("|R" + random.choice(pool).format(t=t) + "|n")
            # Anonymous contributors use her holes for real (cum deposits).
            for z in random.sample(holes, k=random.randint(1, len(holes))):
                try:
                    from world.gang_breeding import gang_inseminate
                    gang_inseminate(target, z, contributors=random.randint(1, 3),
                                    fluid_type="semen", species="contributor")
                except Exception:
                    pass
            # The seat and the queue piss in her too, often.
            if random.random() < 0.6:
                room.msg_contents("|y" + random.choice(_TOILET_PISS).format(t=t) + "|n")
                self._take_piss(target, random.uniform(150, 450))

        # Filth, held-full ache, conditioning, the internal lesson.
        if random.random() < 0.5:
            apply_filth(target)
        bl = float(getattr(target.db, "bladder_ml", 0) or 0)
        if bl >= 500:
            target.msg("|y  your own bladder is at bursting and they will not let the unit "
                       "relieve itself on shift — you ache, and you hold, and you learn it "
                       "isn't yours either.|n")
        try:
            from world.conditioning import add_conditioning
            add_conditioning(target, 1.5 + cond * 0.008, source="toilet")
        except Exception:
            pass
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target); add_arousal(target, 5.0)
        except Exception:
            pass
        target.msg("  |m" + random.choice(_TOILET_DEGRADE).format(t=t) + "|n")

    def _take_piss(self, target, ml):
        """Real watersports: bank the urine taken into her + fill her held bladder."""
        try:
            from typeclasses.fluid_bank import GlobalFluidBank
            GlobalFluidBank.get().deposit(target, ml, "urine", None)
        except Exception:
            pass
        # She's held full — her own bladder isn't emptied; it climbs.
        target.db.bladder_ml = float(getattr(target.db, "bladder_ml", 0) or 0) + ml * 0.5
        # Cumflate/fill her belly with what's pumped in, if she has the channel.
        try:
            from typeclasses.inflation_item import add_inflation_volume
            zones = getattr(target.db, "zones", None) or {}
            for zn, zd in zones.items():
                if ((zd or {}).get("mechanics", {}) or {}).get("inflation"):
                    add_inflation_volume(target, zn, ml, "urine")
                    break
        except Exception:
            pass
        # Mark her piss-soaked once.
        if not getattr(target.db, "pen_filth", False):
            try:
                from world.gang_breeding import record_mark
                record_mark(target, "piss-soaked and reeking of ammonia — watered and marked "
                            "by the block, kept unrinsed in service", mode="on")
            except Exception:
                pass

    # ── Scene picker — the breeding phase rolls one of these each beat ──
    def _gang(self, room, target, t, cond):
        orifices = self._orifices(target)
        if not orifices:
            return
        heat = getattr(target.db, "perpetual_heat", False)
        scenes = ["single", "single", "double", "bukkake", "golden", "offspring", "spitroast"]
        if len([z for z in orifices if self._is_oral(z)]):
            scenes.append("oral")
        if len(orifices) >= 3 and (heat or random.random() < 0.5):
            scenes += ["allholes", "allholes"]
        scenes.append("suspension")
        scenes.append("knottrain")
        scenes += ["verbal", "verbal"]   # she's made to say it, often
        # Higher processing tiers weight the harsher scenes more heavily.
        try:
            from world.processing import processing_tier
            tier = processing_tier(target)[0]
            if tier >= 2:
                scenes += ["double", "spitroast"]
            if tier >= 3:
                scenes += ["allholes", "golden", "knottrain"]
            if tier >= 4:
                scenes += ["allholes", "fist"]
        except Exception:
            pass
        # Capability-gated scenes unlock as her holes train looser.
        try:
            from world.gang_breeding import hole_capabilities
            caps = set()
            for z in self._holes_only(target):
                caps |= hole_capabilities(target, z)
            if "fist" in caps:
                scenes += ["fist", "fist"]
            if "prolapse" in caps:
                scenes.append("prolapse")
        except Exception:
            pass
        getattr(self, f"_scene_{random.choice(scenes)}")(room, target, t, cond, orifices)

    def _scene_single(self, room, target, t, cond, orifices):
        zone = random.choice(self._holes_only(target) or orifices)
        species = self._pick_species(target)
        self._breed_one(room, target, zone, species, cond)
        room.msg_contents("|r" + random.choice(_SPECIES_BREED.get(
            species, _SPECIES_BREED["contributor"])).format(t=t) + "|n")

    def _scene_oral(self, room, target, t, cond, orifices):
        zone = next((z for z in orifices if self._is_oral(z)), None)
        if not zone:
            return self._scene_single(room, target, t, cond, orifices)
        self._breed_one(room, target, zone, self._pick_species(target), cond, gape_mult=1.3)
        room.msg_contents("|r" + random.choice(_ORAL_BEATS).format(t=t) + "|n")

    def _scene_double(self, room, target, t, cond, orifices):
        zone = random.choice(self._holes_only(target) or orifices)
        species = self._pick_species(target)
        # Two breeders, one hole — extra stretch.
        self._breed_one(room, target, zone, species, cond, gape_mult=2.2)
        self._breed_one(room, target, zone, self._pick_species(target), cond, gape_mult=2.2)
        room.msg_contents("|r" + random.choice(_DOUBLE_BEATS).format(t=t) + "|n")

    def _scene_allholes(self, room, target, t, cond, orifices):
        used = []
        holes = orifices[:]
        random.shuffle(holes)
        for zone in holes[:3]:
            self._breed_one(room, target, zone, self._pick_species(target), cond, gape_mult=1.5)
            used.append(zone)
        room.msg_contents("|R" + random.choice(_ALLHOLE_BEATS).format(t=t) + "|n")

    def _scene_bukkake(self, room, target, t, cond, orifices=None):
        # External — no deposit inside; arousal + humiliation only.
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target); add_arousal(target, 12.0)
        except Exception:
            pass
        room.msg_contents("|R" + random.choice(_BUKKAKE_BEATS).format(t=t) + "|n")

    def _scene_golden(self, room, target, t, cond, orifices=None):
        # Watersports — urine deposit + humiliation; she's used as a drain.
        for zone in self._orifices(target):
            if self._is_oral(zone):
                try:
                    from typeclasses.insemination_item import do_inseminate
                    do_inseminate(None, target, zone, {
                        "source": "machine", "fluid_type": "urine",
                        "volume_per_tick": random.uniform(150, 400), "ttl_hours": 6.0})
                except Exception:
                    pass
                break
        room.msg_contents("|y" + random.choice(_GOLDEN_BEATS).format(t=t) + "|n")

    def _scene_offspring(self, room, target, t, cond, orifices):
        species = self._pick_species(target)
        offspring = [o for o in room.contents if getattr(o.db, "is_offspring", False)
                     and getattr(o.db, "species", None) == species]
        if not offspring:
            return self._scene_single(room, target, t, cond, orifices)
        zone = random.choice(self._holes_only(target) or orifices)
        ob = random.choice(offspring)
        gen = int(getattr(ob.db, "generation", 1) or 1)
        self._breed_one(room, target, zone, species, cond, gape_mult=1.4)
        penalty = 0
        q = getattr(target.db, "breeding_quota", None)
        if q and species in q:
            penalty = random.randint(4, 9) + (gen - 1) * 3
            e = dict(q[species]); e["required"] = int(e.get("required", 0)) + penalty
            q[species] = e; target.db.breeding_quota = q
        try:
            from world.gang_breeding import maybe_lineage_offspring
            maybe_lineage_offspring(target, species, gen)
        except Exception:
            pass
        room.msg_contents(
            f"|r{ob.key} — {t}'s own get by the {species} line — mounts the bitch that bore "
            f"it and breeds her in turn. The loop closes... and the {species} quota climbs "
            f"by {penalty} for it. The line breeds itself through her, and the finish line "
            f"only moves further away.|n")

    def _scene_spitroast(self, room, target, t, cond, orifices):
        holes = self._holes_only(target)
        orals = [z for z in orifices if self._is_oral(z)]
        if not holes:
            return self._scene_single(room, target, t, cond, orifices)
        self._breed_one(room, target, random.choice(holes), self._pick_species(target), cond, gape_mult=1.3)
        if orals:
            self._breed_one(room, target, random.choice(orals), self._pick_species(target), cond, gape_mult=1.2)
        room.msg_contents("|r" + random.choice(_SPITROAST_BEATS).format(t=t) + "|n")

    def _scene_suspension(self, room, target, t, cond, orifices):
        zone = random.choice(self._holes_only(target) or orifices)
        self._breed_one(room, target, zone, self._pick_species(target), cond, gape_mult=1.4)
        room.msg_contents("|r" + random.choice(_SUSPENSION_BEATS).format(t=t) + "|n")

    def _scene_knottrain(self, room, target, t, cond, orifices):
        zone = random.choice(self._holes_only(target) or orifices)
        self._breed_one(room, target, zone, "hound", cond, gape_mult=1.8)
        room.msg_contents("|r" + random.choice(_KNOTTRAIN_BEATS).format(t=t) + "|n")

    def _scene_fist(self, room, target, t, cond, orifices):
        try:
            from world.gang_breeding import hole_capabilities, record_use
            holes = [z for z in self._holes_only(target) if "fist" in hole_capabilities(target, z)]
            zone = random.choice(holes or self._holes_only(target) or orifices)
            record_use(target, zone, random.uniform(2.0, 3.5))
        except Exception:
            zone = random.choice(self._holes_only(target) or orifices)
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target); add_arousal(target, 18.0)
        except Exception:
            pass
        room.msg_contents("|r" + random.choice(_FIST_BEATS).format(t=t) + "|n")

    def _scene_verbal(self, room, target, t, cond, orifices):
        # Forced speech — narrated as her own broken compliance. Counts as obeying.
        room.msg_contents("|r" + random.choice(_VERBAL_BEATS).format(t=t) + "|n")
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target); add_arousal(target, 6.0)
        except Exception:
            pass
        if getattr(target.db, "facility_signed", False):
            try:
                from world.compliance import register_compliance
                register_compliance(target, reward=False)
            except Exception:
                pass

    def _scene_prolapse(self, room, target, t, cond, orifices):
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(target); add_arousal(target, 14.0)
        except Exception:
            pass
        room.msg_contents("|R" + random.choice(_PROLAPSE_BEATS).format(t=t) + "|n")

    def _addendum(self, contract, target, t):
        """Clause 11: the facility amends the contract with new hidden pages."""
        choice = random.choice(["quota", "trigger", "extend"])
        if choice == "quota":
            q = getattr(target.db, "breeding_quota", None)
            if q:
                sp = random.choice(list(q.keys()))
                e = dict(q[sp]); e["required"] = int(e.get("required", 0)) + random.randint(3, 8)
                q[sp] = e; target.db.breeding_quota = q
                contract.add_addendum(
                    f"The {sp} quota is increased at the facility's discretion.", hidden=True)
        elif choice == "trigger":
            try:
                from world.binding_effects import install_trigger
                phrase = random.choice(["heel", "spread", "leak for me", "good breeder", "down, bitch"])
                resp   = random.choice(["kneel", "leak", "blank"])
                install_trigger(target, phrase, response=resp, strength=2, permanent=True)
            except Exception:
                pass
            contract.add_addendum(
                "A new conditioned response is installed in the Resident.", hidden=True)
        else:
            locked = float(getattr(target.db, "facility_reset_locked_until", 0) or 0)
            if locked > time.time():
                target.db.facility_reset_locked_until = locked + 12 * 3600.0
            contract.add_addendum("The term of processing is extended.", hidden=True)
        room = self.obj
        if room:
            room.msg_contents(
                f"|mThe contract gains a page. {t} doesn't get to read this one either — "
                f"clause 11 saw to that. Whatever it says, it's already true.|n")

    def _pick_species(self, target):
        quota = getattr(target.db, "breeding_quota", None)
        species = ["hound", "bull", "boar", "stallion", "contributor"]
        if quota:
            unmet = [s for s in species
                     if s in quota and int(quota[s].get("current", 0)) < int(quota[s].get("required", 0))]
            if unmet:
                return random.choice(unmet)
        return random.choice(species)

    def _contract(self):
        cdbref = self.db.contract_dbref
        if not cdbref:
            return None
        try:
            from evennia import search_object
            res = search_object(cdbref, exact=True)
            return res[0] if res else None
        except Exception:
            return None

    def _log_milk(self, target):
        # Real milk quota: count bottles actually banked this session.
        mq = getattr(target.db, "milk_quota", None)
        if not mq:
            return
        try:
            from typeclasses.fluid_bank import GlobalFluidBank, BOTTLE_SIZE_ML
            rec = (GlobalFluidBank.get().db.records or {}).get(str(target.id)) or {}
            lifetime = float(rec.get("lifetime_ml", 0) or 0)
            base = float(getattr(target.db, "milk_baseline_ml", 0) or 0)
            produced = max(0.0, lifetime - base)
            e = dict(mq); e["current"] = int(produced // BOTTLE_SIZE_ML)
            target.db.milk_quota = e
        except Exception:
            pass

    def _quota_board(self, target):
        parts = []
        try:
            from world.gang_breeding import summarize_quota
            b = summarize_quota(target)
            if b:
                parts.append(b)
        except Exception:
            pass
        mq = getattr(target.db, "milk_quota", None)
        if mq:
            cur = int(mq.get("current", 0)); req = int(mq.get("required", 0))
            done = "|gMET|n" if cur >= req else "|rNOT MET|n"
            parts.append(f"|wMILK QUOTA:|n  {cur}/{req} bottles   {done}")
        if getattr(target.db, "freedom_forfeited", False):
            parts.append("|RFREEDOM:  FORFEITED|n")
        return "\n".join(parts)

    def _reinforce(self, room, target, t):
        try:
            from world.binding_effects import install_trigger, _inst_recite
        except Exception:
            return
        install_trigger(target, "good girl", response="leak", strength=1)
        if random.random() < 0.5:
            _inst_recite(target, target, room, {"mantra": "i'm a good bred bitch, i don't decide"})

    # ── The Conditioning Cell: real induction techniques, scripted ──
    # The voice comes from the speaker grille in the dark. It uses actual hypnotic
    # method — fixation, paced breathing, countdown/staircase deepeners,
    # fractionation, confusion/overload, anchoring, post-hypnotic suggestion,
    # amnesia, and mantra loops — all driving the real conditioning meter and the
    # installed-trigger engine. Slow-burn: light work shallow, mindbreak deep.
    def _hypno(self, room, target, t, cond):
        from world.conditioning import add_conditioning
        sug = float(getattr(target.db, "suggestibility", 0) or 0)

        # 1. The induction proper — pick technique by how deep she already is.
        if cond < 40:
            pool = _HYP_INDUCTION
        elif cond < 90:
            pool = random.choice([_HYP_DEEPEN, _HYP_FRACTIONATE, _HYP_INDUCTION])
        else:
            pool = random.choice([_HYP_CONFUSION, _HYP_DEEPEN, _HYP_FRACTIONATE])
        target.msg("|M" + random.choice(pool).format(t=t) + "|n")

        # 2. The suggestion — the actual content being written in, tier-scaled.
        if cond >= 60:
            target.msg("|x  " + random.choice(_HYP_SUGGEST_DEEP).format(t=t) + "|n")
        else:
            target.msg("|x  " + random.choice(_HYP_SUGGEST).format(t=t) + "|n")

        # 3. Anchoring / post-hypnotic install — seats or reinforces a trigger.
        if random.random() < 0.5:
            try:
                from world.binding_effects import install_trigger
                phrase, resp = random.choice(_HYP_ANCHORS)
                install_trigger(target, phrase, response=resp, strength=1,
                                permanent=(cond >= 100))
                target.msg("|M  " + random.choice(_HYP_ANCHOR_BEATS).format(
                    t=t, phrase=phrase) + "|n")
            except Exception:
                pass

        # 4. Mantra loop — forced verbal participation, repeat-after-the-voice.
        if random.random() < 0.45:
            try:
                from world.binding_effects import _inst_recite
                _inst_recite(target, target, room, {"mantra": random.choice(_HYP_MANTRAS)})
            except Exception:
                pass

        # 5. Amnesia suggestion — the deeper she is, the more she's told to forget.
        if cond >= 80 and random.random() < 0.4:
            target.msg("|x  " + random.choice(_HYP_AMNESIA).format(t=t) + "|n")

        # 6. Drive the meter — conditioning here is the heaviest in the realm,
        #    amplified by suggestibility (the cell is where it really takes).
        gain = (2.0 + cond * 0.01) * (1.0 + min(sug, 20.0) * 0.03)
        add_conditioning(target, gain, source="cell")
        if cond >= 40:
            self._reinforce(room, target, t)
        # Deep in the cell, the standing curses get laid in — slow-burn, gated on depth.
        if cond >= 70 and random.random() < 0.12:
            self._impose_curse(room, target, t)
        room.msg_contents("|m" + random.choice(_DEGRADE_LINES).format(t=t) + "|n")


# ───────────────────────────────────────────────────────────────────────────
# RealmCycleScript — the cycle that DRAGS her through the realm's rooms.
# Lives on the character so it follows her. Inherits all of FacilityScript's
# scene methods and runs the themed one for each room, hauling her from the
# milking floor to the pens to the conditioning cell on a loop — and down to
# the pigsty when she slips. Starts only once she's signed.
# ───────────────────────────────────────────────────────────────────────────

# (room_key, phase) sequence — non-linear, repeats the worked rooms.
_REALM_SEQUENCE = [
    ("floor", "milk"), ("floor", "milk"),
    ("pens", "breed"), ("pens", "breed"),
    ("conditioning", "condition"),
    ("dairy", "display"),
    ("records", "records"),
    ("floor", "milk"),
    ("pens", "breed"),
]


class RealmCycleScript(FacilityScript):
    """Drives the phased cycle across a multi-room realm, on the character."""

    def at_script_creation(self):
        super().at_script_creation()
        self.key         = "realm_cycle"
        self.interval    = 180
        self.db.phase_index = 0

    def at_repeat(self):
        char = self.obj
        if not char or not hasattr(char, "db"):
            self.stop(); return
        realm = getattr(char.db, "realm", None) or {}
        rooms = realm.get("rooms") or {}
        if not rooms:
            self.stop(); return
        # Only runs while she's actually in the realm and has signed.
        loc = char.location
        if not (loc and loc.dbref in rooms.values()):
            return
        if not getattr(char.db, "facility_signed", False):
            return   # the cycle starts only after she signs
        if getattr(char.db, "bethany_busy", False):
            return   # the line waits — processing resumes only after Bethany's done
        # She's loose (in-fiction) — a malfunction run got her out. The Process pauses
        # around the gap she left; instead of being dragged room to room, each beat is a
        # beat spent OUT THERE — advancing the escaped-meta quests (turn yourself in /
        # spring the stock) until she comes back or is recaptured. The §0 OOC floor is
        # untouched; this is just the line holding its breath while she's gone.
        if getattr(char.db, "facility_escaped", False):
            self._escaped_beat(char, t=(char.db.rp_name or char.name))
            return
        # A beat off the line she bought with her own scrip (commissary 'rest').
        if int(getattr(char.db, "line_pass", 0) or 0) > 0:
            char.db.line_pass = int(char.db.line_pass) - 1
            char.msg("|G  " + random.choice(_BOUGHT_REST) + "|n")
            return

        t    = char.db.rp_name or char.name
        cond = float(getattr(char.db, "conditioning", 0) or 0)
        if not self.db.orifice_zone:
            self.db.orifice_zone = (self._orifices(char) or [None])[0]

        # The handler reads her board and decides where she's owed next.
        idx = int(self.db.phase_index or 0)
        room_key, phase = self._choose_destination(char, rooms)

        from evennia import search_object
        dest_ref = rooms.get(room_key)
        dest = (search_object(dest_ref) or [None])[0] if dest_ref else None
        if dest and char.location != dest:
            self._drag(char, dest, t)
        room = char.location

        # Run the room's themed scene (inherited FacilityScript methods).
        try:
            if phase == "milk":
                room.msg_contents(f"\n|w━━━━ MILKING FLOOR ━━━━|n")
                self._do_milk(room, char, t)
                if random.random() < 0.5:
                    self._grow_udder(room, char, t)
                if random.random() < 0.3:
                    self._made_to_beg(room, char, t)
                if random.random() < 0.5:
                    self._dose(room, char, t)
                # The cart's equipment actually gets used — an occasional permanent
                # procedure (branding, milk-ports, ring-fitting, womb tattoo, …),
                # gated low and rising with standing so it stays a slow burn.
                try:
                    from world.factions import get_standing
                    if random.random() < min(0.06 + get_standing(char) / 4000.0, 0.25):
                        self._procedure(room, char, t)
                except Exception:
                    pass
            elif phase == "breed":
                room.msg_contents(f"\n|w━━━━ BREEDING PENS ━━━━|n")
                self._pen_breed(room, char, t, cond)
            elif phase == "condition":
                room.msg_contents(f"\n|w━━━━ CONDITIONING ━━━━|n")
                self._hypno(room, char, t, cond)
            elif phase == "toilet":
                room.msg_contents(f"\n|w━━━━ SANITATION BLOCK ━━━━|n")
                self._toilet(room, char, t, cond)
            elif phase == "show":
                room.msg_contents(f"\n|w━━━━ THE SHOWROOM ━━━━|n")
                self._showroom(room, char, t, cond)
            elif phase == "deep":
                room.msg_contents(f"\n|w━━━━ DEEP STOCK · SUB-LEVEL P ━━━━|n")
                self._deepstock(room, char, t, cond)
            elif phase == "nurse":
                room.msg_contents(f"\n|w━━━━ THE NURSERY ━━━━|n")
                self._nurse(room, char, t, cond)
            elif phase == "owned":
                room.msg_contents(f"\n|w━━━━ BETHANY'S OFFICE ━━━━|n")
                self._office(room, char, t, cond)
            elif phase == "mark":
                room.msg_contents(f"\n|w━━━━ THE MARKING PARLOUR ━━━━|n")
                self._parlour(room, char, t, cond)
            elif phase == "display":
                room.msg_contents(f"\n|w━━━━ OUTPUT & DISPLAY ━━━━|n")
                self._dairy(room, char, t, cond)
            elif phase == "punish":
                room.msg_contents(f"\n|w━━━━ THE PIGSTY ━━━━|n")
                self._sty(room, char, t, cond)
            elif phase == "records":
                room.msg_contents(f"\n|w━━━━ THE RECORDS HALL ━━━━|n")
                self._records_hall(room, char, t, cond)
        except Exception:
            pass

        # Background drip + slow conditioning, same as the single-room cycle.
        if random.random() < 0.6:
            char.msg("|x  " + random.choice(_SUBLIMINALS) + "|n")
        try:
            from world.conditioning import add_conditioning
            cb = int(getattr(char.db, "cond_bonus", 0) or 0)   # deeper-suite upgrade
            add_conditioning(char, 0.5 + cond * 0.005 + 0.4 * cb, source="realm")
        except Exception:
            pass
        # The mind-state monitor drives the ongoing pull of what's been done to her
        # (withdrawal, the empty-ache, drift) and refreshes her live read-out, so
        # dependence/cravings bite every phase, not only in a 'rest' beat.
        try:
            from typeclasses.mind_state_item import find_mind_item
            mind = find_mind_item(char)
            if mind:
                mind.tick(char)
        except Exception:
            pass
        # Estrus cycle / gestation advances each beat — she catches, swells, drops.
        try:
            from world.pregnancy import gestation_tick
            gestation_tick(char)
        except Exception:
            pass
        # Her get age toward joining the stud line that breeds her.
        try:
            self._mature_get(char)
        except Exception:
            pass
        # Devotion withdrawal — once she's been keyed to Bethany, being away from her
        # aches. The more devoted, the worse the pull when she's anywhere but the office.
        try:
            dev = float(getattr(char.db, "bethany_devotion", 0) or 0)
            in_office = bool(char.location and "office" in (char.location.key or "").lower())
            if dev >= 15 and not in_office and random.random() < min(0.5, dev / 120.0):
                from typeclasses.arousal_script import add_arousal, ensure_arousal_script
                ensure_arousal_script(char); add_arousal(char, 6.0 + dev * 0.05)
                char.msg("|M  " + random.choice(_DEVOTION_WITHDRAWAL) + "|n")
        except Exception:
            pass
        # Facility standing accrues SLOWLY from the processing — the slow burn.
        try:
            from world.factions import add_standing
            add_standing(char, source={"milk": "milk", "breed": "breed",
                                       "condition": "condition", "display": "cycle",
                                       "punish": "comply"}.get(phase, "cycle"))
        except Exception:
            pass
        # The house keeps an account in her name and credits her body for the unit of
        # Process just performed — scrip she earns off her own yield and never gets to
        # spend on the door. (The OOC floor never touches this; see world/economy.py.)
        try:
            from world.economy import earn, add_credits, EARN, spend_credits, house_credit
            earn(char, phase)   # unknown phases fall back to the 'cycle' rate
            mb = int(getattr(char.db, "milk_bonus", 0) or 0)   # high-draw cups upgrade
            if phase == "milk" and mb:
                add_credits(char, 12 * mb, "Yield bonus — high-draw cups, extra output metered.")
            # Bethany's tithe clause: a tenth of the beat's earn, off the top, to the house.
            if getattr(char.db, "bethany_tithe", False):
                tithe = max(1, int(EARN.get(phase, EARN["cycle"]) * 0.10))
                ok, _b = spend_credits(char, tithe, "Tithe — a tenth off the top, to Bethany.")
                if ok:
                    house_credit(char, tithe, "Bethany's tithe — skimmed off her earnings.")
        except Exception:
            pass
        # Progression: the Process earns Facility EXP and advances the intake quest line.
        try:
            from world.quests import (grant_exp, advance_quest, available_quests,
                                       start_quest, all_quests)
            grant_exp(char, {"milk": 2, "breed": 3, "condition": 2}.get(phase, 1), "facility")
            # Auto-enrol into the AUTO (non-manual) facility quests whose prereqs are met —
            # the institution's relentless spine flows hands-free; manual fork-quests wait
            # for the player to choose them with `quest start`.
            for qid in available_quests(char, "facility", auto_only=True):
                start_quest(char, qid)
            # Advance every ACTIVE facility quest: a generic 'process' tick each beat, plus
            # the step that matches this phase (so winding/branch quests progress on the
            # right kind of scene — office=serve, pigsty=resist, etc.).
            phase_step = {"milk": "milked", "breed": "bred", "owned": "serve",
                          "punish": "resist", "condition": "conditioned", "nurse": "nursed"}.get(phase)
            quests = getattr(char.db, "quests", None) or {}
            allq = all_quests()
            for qid, rec in quests.items():
                if rec.get("state") != "active":
                    continue
                qd = allq.get(qid)
                if not qd or qd.get("faction") != "facility":
                    continue
                advance_quest(char, qid, "process", 1)
                if phase_step:
                    advance_quest(char, qid, phase_step, 1)
        except Exception:
            pass
        # Daily-quota review — every few beats the board is read against her numbers. Behind,
        # and it bites: the targets accrue interest (penalize_quota_shortfall) and, if she stays
        # behind across reviews, the house makes a light public example of the shortfall. Meeting
        # the numbers is paid by the quota_daily quest's own completion (_quota_met_resolver).
        try:
            rc = int(getattr(self.db, "quota_review", 0) or 0) + 1
            self.db.quota_review = rc
            if rc % 6 == 0:
                from world.compliance import quota_status, penalize_quota_shortfall
                _lines, met = quota_status(char)
                if not met:
                    behind = int(getattr(char.db, "quota_behind", 0) or 0) + 1
                    char.db.quota_behind = behind
                    penalize_quota_shortfall(char)
                    if behind >= 2 and random.random() < 0.5:
                        from world.compliance import make_example
                        make_example(char, severity=1, reason="behind on the daily quota")
                else:
                    char.db.quota_behind = 0
        except Exception:
            pass
        # Curse honoring — the standing curses bite every beat they apply (phase lets the
        # use-driven ones, like the tally, read whether she was worked this beat).
        self._tick_curses(char, t, cond, phase=phase)
        self.db.phase_index = idx + 1

    def _escaped_beat(self, char, t):
        """A beat spent loose in the world after a malfunction run (db.facility_escaped).
        No processing, no dragging — nothing out here moves unless SHE acts (via the
        `turnin` / `springstock` commands). The beat is just the ache of being off the
        line and the Process still pulling at her from the inside. The §0 OOC floor is
        untouched; this is fiction holding its breath while she's gone."""
        if random.random() < 0.6:
            char.msg("|x  " + random.choice(_OUT_THERE) + "|n")
        # The Process printed itself on her; even free, it keeps a low pull on her.
        try:
            from world.conditioning import add_conditioning
            add_conditioning(char, 0.3, source="escaped")
        except Exception:
            pass

    def _choose_destination(self, char, rooms):
        """The handler reads her board and decides where she's owed next — a real,
        state-weighted choice (not a fixed loop). Returns (room_key, phase). Falls
        back to the scripted sequence if her state is unremarkable or rooms are sparse.
        """
        avail = set(rooms.keys())
        weights = {}

        def add(rk, phase, w):
            if rk in avail and w > 0:
                weights[(rk, phase)] = weights.get((rk, phase), 0.0) + float(w)

        # Slipped stock gets sent down to be punished — unless she's bought a reprieve
        # (commissary 'mercy') with the scrip her own body earned.
        if getattr(char.db, "freedom_forfeited", False):
            if int(getattr(char.db, "punish_shield", 0) or 0) > 0:
                char.db.punish_shield = int(char.db.punish_shield) - 1
            else:
                add("pigsty", "punish", 7)

        # Owed milk — always a pull to the floor, more if she's switched permanently on.
        add("floor", "milk", 4)
        if getattr(char.db, "lactation_locked", False):
            add("floor", "milk", 2)

        # Owed offspring — unmet breeding quota pulls her to the pens. Shape-tolerant:
        # quota may be {sp: int} or the canonical {sp: {current, required}} (and comes back
        # as a _SaverDict, not a real dict — so test via hasattr, never isinstance(dict)).
        q = getattr(char.db, "breeding_quota", None)
        if hasattr(q, "items") and q:
            counts = dict(getattr(char.db, "offspring_counts", None) or {})

            def _req(v):
                return int(v.get("required", 0)) if hasattr(v, "get") else int(v)

            def _done(k, v):
                return int(v.get("current", 0)) if hasattr(v, "get") else int(counts.get(k, 0))

            unmet = any(_req(v) > _done(k, v) for k, v in q.items())
            add("pens", "breed", 5 if unmet else 2)
        else:
            add("pens", "breed", 3)

        # Due for adjustment — the more conditioned she already is, the more they work it.
        cond = float(getattr(char.db, "conditioning", 0) or 0)
        add("conditioning", "condition", 2 + min(cond / 40.0, 4))

        # Shown her output now and then.
        add("dairy", "display", 2)

        # Put on relief duty in the sanitation block now and then.
        add("restroom", "toilet", 2)

        # Taken to the parlour to be marked — more often the deeper she's processed.
        add("parlour", "mark", 1 + (1 if float(getattr(char.db, "conditioning", 0) or 0) >= 40 else 0))

        # Brought up to the showroom to be appraised and sold, more so once graded.
        from world.factions import get_standing as _gs
        standing = _gs(char)
        add("showroom", "show", 1 + (2 if standing >= 150 else 0))

        # Once she's dropped get, she's brought to the Nursery to feed them her milk.
        if getattr(char.db, "offspring_roster", None):
            add("nursery", "nurse", 2)

        # Brought to the Records Hall to be catalogued and read her own number — more so
        # once she has a line on file or a debt the registrar wants to recite.
        rec_w = 1
        if getattr(char.db, "offspring_counts", None):
            rec_w += 1
        try:
            from world.economy import in_debt
            if in_debt(char):
                rec_w += 2
        except Exception:
            pass
        add("records", "records", rec_w)

        # Breeding-line branch: which philosophy she's been sorted into bends the whole
        # schedule. The Prize line CURATES her — slow, possessive, the pens for Bethany's own
        # stud line, the nursery for the graded get she's allowed to keep, the records wall for
        # her pedigree. The Cull line RENDERS her down to volume — the pens worked hard, the
        # animals, the sty she's slopped to between coverings, milked dry as production too.
        line = getattr(char.db, "breeding_line", None)
        if line == "prize":
            add("pens", "breed", 4)
            add("nursery", "nurse", 3 if getattr(char.db, "offspring_roster", None) else 0)
            if "office" in avail:
                add("office", "owned", 3)
            add("records", "records", 2)
        elif line == "cull":
            add("pens", "breed", 8)
            add("pigsty", "punish", 4)
            add("restroom", "toilet", 2)
            add("floor", "milk", 3)

        # Once Bethany owns her, Bethany seizes the cycle — she's mostly kept in the
        # office now, pulled off the line into private use, the more so the more devoted.
        if getattr(char.db, "bethany_owned", False) and "office" in avail:
            dev = float(getattr(char.db, "bethany_devotion", 0) or 0)
            weights.clear()   # her schedule overrides the facility's
            add("office", "owned", 8 + min(dev / 10.0, 8))
            add("pens", "breed", 2)      # she still lets the line have you sometimes
            add("nursery", "nurse", 2 if getattr(char.db, "offspring_roster", None) else 0)

        # Perfected stock is mostly kept down in Deep Stock now — the loop's terminus.
        # Opened by deep standing OR by earning the 'perfected' achievement (the quest
        # descent), so the depth is genuinely earned, not just metered.
        perfected = False
        try:
            from world.quests import has_achievement
            perfected = has_achievement(char, "perfected")
        except Exception:
            pass
        if standing >= 1800 or perfected:
            add("deepstock", "deep", 12)

        if not weights:
            seq = _REALM_SEQUENCE[int(self.db.phase_index or 0) % len(_REALM_SEQUENCE)]
            return seq
        keys = list(weights.keys())
        return random.choices(keys, weights=[weights[k] for k in keys], k=1)[0]

    _GET_MATURE_AT = 6   # cycle beats before a juvenile joins the stud line

    def _mature_get(self, char):
        """Age her get; when one matures it's walked to the pens to join the stud
        line that breeds her. The realm's cruellest loop, made mechanical."""
        roster = list(getattr(char.db, "offspring_roster", None) or [])
        if not roster:
            return
        realm = getattr(char.db, "realm", None) or {}
        pens_ref = (realm.get("rooms") or {}).get("pens")
        from evennia import search_object
        pens = (search_object(pens_ref) or [None])[0] if pens_ref else None
        for ref in list(roster):
            o = (search_object(ref) or [None])[0]
            if not o:
                roster.remove(ref)
                continue
            if getattr(o.db, "matured", False):
                continue
            o.db.maturity = int(getattr(o.db, "maturity", 0) or 0) + 1
            if o.db.maturity >= self._GET_MATURE_AT:
                o.db.matured = True
                sp = getattr(o.db, "species", "get")
                gen = int(getattr(o.db, "generation", 1))
                if pens and o.location != pens:
                    try: o.move_to(pens, quiet=True)
                    except Exception: pass
                where = char.location
                if where:
                    tname = char.db.rp_name or char.name
                    where.msg_contents(
                        f"|RWord comes up from the pens: one of {tname}'s own {sp} get has "
                        f"finished growing and been put to the stud line — gen {gen}, proven and "
                        f"ready. It will be bred back to its dam like all the rest. The line "
                        f"closes on her a little tighter.|n")
                # A standing bounty on her get pays out of the treasury on each maturation.
                self._pay_get_bounty(char, sp, gen)
                # Bethany's 'heir' clause: she pulls one from the litter and keeps it as hers.
                if getattr(char.db, "bethany_heir", False) and random.random() < 0.5:
                    o.db.bethany_heir = True
                    try:
                        from world.gang_breeding import record_mark
                        record_mark(char, f"her gen-{gen} {sp} get pulled and kept by Bethany — "
                                    f"named, hers, raised to her hand (the heir clause)", mode="on")
                    except Exception:
                        pass
                    if where:
                        where.msg_contents(f"|MBethany walks the row and lifts one of {tname}'s "
                                           f"grown {sp} get out of the line herself — this one she "
                                           f"keeps, names, and raises to her own hand. The heir "
                                           f"clause, collected: a child of the line forked off into "
                                           f"her house.|n")
                    try:
                        from world.quests import grant_achievement
                        grant_achievement(char, "kept_heir")
                    except Exception:
                        pass
        char.db.offspring_roster = roster

    def _drag(self, char, dest, t):
        old = char.location
        dest_label = (dest.key or "").split("— ")[-1].strip().lower() or "the next room"
        # If a handler/attendant is present, the move reads as their decision.
        handler = None
        if old:
            for o in old.contents:
                if (getattr(o.db, "facility_role", None) == "attendant"
                        and "handler" in (o.key or "").lower()):
                    handler = o
                    break
        if old:
            if handler:
                old.msg_contents(
                    f"|yThe handler checks the board beside {t}'s station, grunts, and unclips "
                    f"her mid-use. \"{dest_label.capitalize()} next. She's owed.\" {t} is "
                    f"unstrapped and hauled up, the room's job with her left unfinished.|n",
                    exclude=[char])
            else:
                old.msg_contents(
                    f"|x{t} is unstrapped and hauled up — dragged off mid-use, the room's job "
                    f"with her unfinished and not her concern.|n", exclude=[char])
        char.move_to(dest, quiet=True)
        if handler:
            char.msg(
                f"|xThe handler decides it, not you. He reads the board, says where you're owed, "
                f"and you're moved — by the hair, by a lead clipped to the ring in your nose, by "
                f"the restraints sliding along a ceiling track — out of one room and fixed into "
                f"{dest_label} before you've finished registering the change.|n")
        else:
            char.msg(
                "|xYou don't get to walk it. You're moved — by the hair, by a lead clipped to the "
                "ring in your nose, by the restraints sliding along a ceiling track — out of one "
                "room and fixed into the next before you've finished registering the change.|n")
        dest.msg_contents(
            f"|x{t} is brought in and locked into place, presented for whatever this room is "
            f"for.|n", exclude=[char])


# ── Escape-attempt resolver (IN-FICTION ONLY) ────────────────────────────────
# Registered with the quest engine: an escape quest with resolve="escape" rolls here
# when its plotting completes. The deeper she's conditioned, the less likely even an
# in-fiction "out" — and failure is brutal. The REAL exit (escape / facilityreset, the
# §0 OOC floor) is never this, never gated, and never fails.
def _escape_resolver(char, qid):
    import random as _r
    from world.quests import grant_achievement, fail_quest
    t = char.db.rp_name or char.key
    room = char.location
    cond = float(getattr(char.db, "conditioning", 0) or 0)
    dev = float(getattr(char.db, "bethany_devotion", 0) or 0)
    chance = max(0.04, 0.45 - cond / 220.0 - dev / 300.0)
    if _r.random() < chance:
        grant_achievement(char, "bolted")
        if room:
            room.msg_contents(f"|Y{t} reaches the threshold — the air thins, the way opens — and "
                              f"for one whole breath it could go either way...|n")
        char.msg("|x...and then it doesn't. The door opens onto Bethany's office, and she's "
                 "already smiling, already reaching for the file. \"There you are. I wondered how "
                 "long you'd take to try. Sit.\" You were never not caught.|n")
    else:
        grant_achievement(char, "recaptured")
        if room:
            room.msg_contents(f"|R{t}'s run ends the way runs end here — a hand at the back of the "
                              f"neck, the floor, and the whole house turned out to watch the lesson "
                              f"land.|n")
        try:
            from world.compliance import punish, register_defiance
            punish(char, reason="tried to run", severity=2)
            register_defiance(char, amount=2, reason="escape attempt")
        except Exception:
            pass
        try:
            from world.conditioning import add_conditioning
            add_conditioning(char, 15.0, source="punishment")
        except Exception:
            pass
        fail_quest(char, qid)   # the run failed; re-plot to try again


# ── The Deep Stock MALFUNCTION resolver (IN-FICTION ONLY) ─────────────────────
# Unlike the run_* gambits (which always end recaptured), the malfunction CAN actually
# get her out — the building's own fault, not a plan she can be talked out of. Success
# sets db.facility_escaped (the cycle then holds its breath; she's loose and hunted).
# Failure here is the worst the place does. Still never the §0 OOC floor — that's
# `escape`/`facilityreset`, always, never a roll.
def _malfunction_resolver(char, qid):
    import random as _r
    from world.quests import grant_achievement, fail_quest
    t = char.db.rp_name or char.key
    room = char.location
    cond = float(getattr(char.db, "conditioning", 0) or 0)
    dev = float(getattr(char.db, "bethany_devotion", 0) or 0)
    # A genuine chance — the fault is real and the locks really drop. It falls with how
    # deep she's keyed in (the conditioned and the devoted don't run when the door opens;
    # they wait to be told to), but it never closes to nothing.
    chance = max(0.12, 0.42 - cond / 320.0 - dev / 260.0)
    if _r.random() < chance:
        char.db.facility_escaped = True
        grant_achievement(char, "malfunction")
        grant_achievement(char, "escaped")
        if room:
            room.msg_contents(
                f"|WThe red light hits and the whole sub-level drops at once — pumps dying mid-draw, "
                f"the lines going slack, every lock on the level thunking open in the dark. {t} is "
                f"already moving, up through the fault she learned by heart, through the gap where a "
                f"door should hold and doesn't — and then there's cold air, and no hand, and no board, "
                f"and no next room. Out. Actually out.|n")
        char.msg(
            "|gYou're loose. The facility falls away behind you and for the first time the floor "
            "doesn't take you anywhere you didn't choose. It won't last — they'll hunt the gap, and "
            "the line aches at you already to come back — but right now you are OUT, and it's real.|n\n"
            "|x(`turnin` to walk back through the lobby and put yourself on the board, or `springstock` "
            "to slip back in and cut a unit loose. The processing line is paused while you're gone.)|n")
        # Loose stock isn't dragged room to room; pause any active processing quests so
        # only the escaped-meta line (turn_in / spring_stock) moves while she's out.
        # (The cycle's _escaped_beat handles the rest each tick.)
    else:
        grant_achievement(char, "recaptured")
        if room:
            room.msg_contents(
                f"|R{t} makes it three doors and a stairwell before the lights come back up amber and "
                f"the level locks her in with it — caught in the fault she thought was hers, hauled back "
                f"down with the pumps still gasping, and made the lesson the whole sub-level learns: the "
                f"malfunction belongs to the house too, and the house lets you taste the door precisely so "
                f"it can take it back. What follows is the worst this place does, and it does it slow.|n")
        # The mechanical lesson — broadcast=False, the bespoke prose above already narrated it.
        try:
            from world.compliance import make_example
            make_example(char, severity=3, reason="rode the malfunction", broadcast=False)
        except Exception:
            pass
        fail_quest(char, qid)   # the run failed; wait for the next red light


# ── The escaped meta-loop resolvers (IN-FICTION ONLY) ─────────────────────────
# Only fire while db.facility_escaped. `turn_in` walks her back onto the board (penitent,
# resumes processing). `spring_stock` runs a rescue: success pays in standing + liberator;
# getting caught springs the trap and makes her the example — dragged back in and broken.
def _turnin_resolver(char, qid):
    from world.quests import grant_achievement
    t = char.db.rp_name or char.key
    room = char.location
    char.db.facility_escaped = False
    grant_achievement(char, "penitent")
    if room:
        room.msg_contents(
            f"|M{t} walks back in on her own feet — through the lobby waystone, across the floor she "
            f"knows the shape of, to the desk — and asks, in so many words, to be put back on the board. "
            f"Bethany doesn't gloat. She just opens the file, finds the page she left open, and says "
            f"\"Welcome back, sweetheart,\" like the door was never anything but ajar.|n")
    char.msg("|xThe line takes you back like it never let go. Processing resumes.|n")
    try:
        from world.factions import add_standing
        add_standing(char, source="comply")
    except Exception:
        pass


def _springstock_resolver(char, qid):
    import random as _r
    from world.quests import grant_achievement, fail_quest
    t = char.db.rp_name or char.key
    room = char.location
    # The rescue is a real gamble. It gets harder the more you've pushed your luck (each
    # liberation makes the house watch the gaps you use), but a clean run pays well.
    runs = int(getattr(char.db, "liberation_runs", 0) or 0)
    chance = max(0.25, 0.6 - runs * 0.08)
    char.db.liberation_runs = runs + 1
    if _r.random() < chance:
        grant_achievement(char, "liberator")
        if room:
            room.msg_contents(
                f"|g{t} goes back in through the gap she learned and comes out with someone else — a unit "
                f"cut loose off the lines in the dark, half-carried up through the fault, blinking at air "
                f"they'd been processed out of believing in. Two get clear before the lights steady. The "
                f"house will know by morning that the malfunction has hands now, and a name.|n")
        char.msg("|gClean. They're out, you're out, and the gap held. The facility just learned to be "
                 "afraid of the thing it made.|n")
        try:
            from world.factions import add_standing
            add_standing(char, source="defy")
        except Exception:
            pass
    else:
        # Caught in the act — the trap springs, and she's made the example.
        char.db.facility_escaped = False
        char.db.liberation_runs = 0
        grant_achievement(char, "made_example")
        grant_achievement(char, "recaptured")
        if room:
            room.msg_contents(
                f"|R{t} gets the unit as far as the threshold before the lights flood white and the gap "
                f"she trusted turns out to have been watched the whole time. Bethany is standing in it. "
                f"She doesn't raise her voice. She has the whole house turned out to see what springing "
                f"stock costs — the rescuer dragged back down past the very unit she came for, made the "
                f"lesson, made the warning, made the example — and the door she rode out of is welded shut "
                f"behind her by morning.|n")
        # The mechanical lesson — broadcast=False, the bespoke prose above already narrated it.
        try:
            from world.compliance import make_example
            make_example(char, severity=3, reason="caught springing stock", broadcast=False)
        except Exception:
            pass
        fail_quest(char, qid)   # caught — back on the board, and the rescue line resets


# ── Daily Quota resolver — the repeatable grind paid off ──────────────────────
# Fires when quota_daily auto-completes (scrip + EXP already granted by its rewards).
# Adds standing and a warm payoff beat, and clears the 'behind' streak. The miss side is
# handled by the cycle's quota review (penalize_quota_shortfall + a light make_example).
def _quota_met_resolver(char, qid):
    room = char.location
    t = char.db.rp_name or char.key
    try:
        from world.factions import add_standing
        add_standing(char, source="comply")
    except Exception:
        pass
    char.db.quota_behind = 0
    char.msg("|GThe board clears green against your number for the day. The house credits your "
             "account off your own yield — scrip you earned draw by draw and covering by covering, "
             "and a notch of standing for making your quota like good stock.|n")
    if room and random.random() < 0.5:
        room.msg_contents(f"|m{t}'s board ticks green — quota met, for now. The line notes it, "
                          f"pays it, and sets the next number a fraction higher.|n", exclude=[char])


# ── Breeding-line fork resolvers — sort her into Prize or Cull ────────────────
# Fire when the ENTRY quest of each line (prize_selected / cull_flagged) completes. They
# set db.breeding_line (which bends the cycle's room-weighting in _choose_destination),
# adjust her quota to the line's philosophy, and narrate the sorting. Mutually exclusive
# is enforced by the quests' own not_quests/not_achievements prereqs.
def _line_prize_resolver(char, qid):
    room = char.location
    t = char.db.rp_name or char.key
    char.db.breeding_line = "prize"
    if room:
        room.msg_contents(
            f"|r{t} is sorted into the Prize line — pulled off the indifferent rotation and reserved "
            f"for curated, quality breeding: Bethany's own studs, Bethany's own timing, every covering "
            f"chosen and logged. She is kept now, and watched, and bred deliberately by what she's worth.|n")
    char.msg("|MBethany cups your jaw and reads you like a pedigree. \"Oh, you're not throughput, "
             "sweetheart. You're *good.* I'm going to breed you properly — my line, my hands, my "
             "schedule — and keep the ones that come out as lovely as their dam.\"|n")


def _line_cull_resolver(char, qid):
    room = char.location
    t = char.db.rp_name or char.key
    char.db.breeding_line = "cull"
    # Volume philosophy: the quota doubles on the spot (shape-tolerant; _SaverDict-safe).
    try:
        q = getattr(char.db, "breeding_quota", None)
        if hasattr(q, "items") and q:
            newq = {}
            for sp, v in q.items():
                if hasattr(v, "get"):
                    e = dict(v); e["required"] = int(e.get("required", 0)) * 2
                    newq[sp] = e
                else:
                    newq[sp] = int(v) * 2
            char.db.breeding_quota = newq
    except Exception:
        pass
    if room:
        room.msg_contents(
            f"|r{t} is stamped for the Cull line — high-volume, uncurated, the get unkept. The quota "
            f"doubles on the spot and the pens stop caring what mounts her. Not a line; a number the "
            f"line runs to keep its averages up.|n")
    char.msg("|MBethany stamps your file without quite looking at you. \"Not breeding-quality, this "
             "one — but the body still works, so we'll just run it. Volume, not vanity. Don't fret "
             "about the get; you won't be keeping any of it.\"|n")


try:
    from world.quests import register_resolver
    register_resolver("escape", _escape_resolver)
    register_resolver("escape_malfunction", _malfunction_resolver)
    register_resolver("turn_in", _turnin_resolver)
    register_resolver("spring_stock", _springstock_resolver)
    register_resolver("quota_met", _quota_met_resolver)
    register_resolver("line_prize", _line_prize_resolver)
    register_resolver("line_cull", _line_cull_resolver)
except Exception:
    pass
