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
            bonus = 1.5 if phase in ("breed", "condition") else 0.0
            add_conditioning(target, 1.0 + cond * 0.012 + bonus, source="facility")
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

    def _start_milking(self, target):
        """Run a REAL milking session — extracts her production into the bank."""
        try:
            from typeclasses.milking_session_script import MilkingSessionScript
            from world.milking_loader import get_speed_config
            from evennia.utils import create
            for s in target.scripts.all():
                if isinstance(s, MilkingSessionScript):
                    return   # already milking
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
            room.msg_contents(
                f"\n|w━━━━ CYCLE {cyc} · INTAKE ━━━━|n\n"
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

    def _facility_event(self, room, target, t):
        """A rare special event, with a matching mechanical bite."""
        key, text = random.choice(_EVENTS)
        room.msg_contents("\n|W★ " + text.format(t=t) + "|n")
        try:
            from world.conditioning import add_conditioning
            if key == "culling":
                add_conditioning(target, 12.0, source="event")
            elif key in ("inspection", "open_house", "restock"):
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
                marks = list(getattr(target.db, "facility_brands", None) or [])
                marks.append("a second owner's mark added beside the facility's — sold on")
                target.db.facility_brands = marks

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
        room.msg_contents(
            f"\n|W════ PROCESSING REVIEW ════|n\n"
            f"|WThe board re-grades {t}: |Y{name}|W. {state.capitalize()}.|n\n"
            f"|xThe attendant initials the form. Nobody asks {t} how she feels about the "
            f"new grade — the grade is a measurement, not an opinion, and the measurement "
            f"only goes one way.|n")
        # The graduation set-piece for this tier, witnessed by the herd.
        if lvl in _GRADUATION:
            room.msg_contents("|w" + random.choice(_GRADUATION[lvl]).format(t=t) + "|n")
        marks = list(getattr(target.db, "facility_brands", None) or [])
        marks.append(f"graded by the facility: {name}")
        target.db.facility_brands = marks
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
                room.msg_contents("|c" + random.choice(_MACHINE_BEATS).format(t=t) + "|n")
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
              "solvent", "cumslut"]
    _PROCEDURES = ["pierce", "brand", "stim_implant", "ring_fit", "milk_port",
                   "tail", "fertility_implant", "tongue", "womb_tattoo", "clit_hood"]

    def _dose(self, room, target, t):
        room.msg_contents("|G" + random.choice(_DRUG_BEATS).format(t=t) + "|n")
        for drug in random.sample(self._DRUGS, k=random.randint(1, 2)):
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

    # ── Procedures (intake phase) — surgical/permanent, with a lasting mark ──
    def _mark(self, target, text):
        marks = list(getattr(target.db, "facility_brands", None) or [])
        marks.append(text)
        target.db.facility_brands = marks

    def _procedure(self, room, target, t):
        name = random.choice(self._PROCEDURES)
        try:
            getattr(self, f"_proc_{name}")(room, target, t)
        except Exception:
            pass

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
        self._mark(target, "steel gauging rings fitted in cunt and ass, holding her permanently open")
        room.msg_contents(
            f"|GThey fit {t}'s holes with steel — a wide gauging ring worked into her cunt and "
            f"another into her ass, cranked open notch by notch and locked there, propping her "
            f"permanently gaping and slack so nothing ever has to work to get into her again. "
            f"(permanently fitted open)|n")

    def _proc_milk_port(self, room, target, t):
        self._boost_production(target, 4.0)
        self._mark(target, "surgical milk ports set under each areola — permanent")
        room.msg_contents(
            f"|GA milking port is surgically set under each of {t}'s areolae — clean valves her "
            f"body is re-plumbed around, that she'll leak from on command for the rest of the term. "
            f"(permanent — production up)|n")

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

    def _find_breeder(self, room, species):
        cands = [o for o in room.contents if getattr(o.db, "facility_role", None) == "beast"]
        match = [o for o in cands if getattr(o.db, "species", None) == species]
        pool = match or cands
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
        size = {"hound": 7.0, "bull": 13.0, "boar": 9.0, "stallion": 15.0}.get(species, 8.0)
        try:
            p = create.create_object(BodyModItem, key=f"{species} cock", location=npc)
            p.db.mod_type = "penis"; p.db.size = size
            p.install(npc, "shaft")
        except Exception:
            pass
        if species == "hound":
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
        """One real breeding of one hole: quota/offspring/deposit + real penetration."""
        n = random.randint(2, 3 + int(cond // 30))
        try:
            from world.gang_breeding import gang_inseminate
            gang_inseminate(target, zone, contributors=n, fluid_type="semen", species=species)
        except Exception:
            pass
        oral = self._is_oral(zone)
        npc = self._find_breeder(room, species)
        if npc and not oral:
            self._real_penetrate(room, npc, target, zone, species)
        if gape_mult != 1.0:
            try:
                from world.gang_breeding import add_gape
                add_gape(target, zone, random.uniform(0.6, 1.6) * (gape_mult - 1.0))
            except Exception:
                pass
        return npc, oral

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
        mq = getattr(target.db, "milk_quota", None)
        if mq and random.random() < 0.5:
            e = dict(mq); e["current"] = int(e.get("current", 0)) + 1
            target.db.milk_quota = e

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
