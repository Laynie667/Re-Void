"""
typeclasses/bethany_script.py

BethanyScript — the intake clerk doesn't stay behind the desk forever.

Once a resident is signed and being processed in the realm, Bethany wanders in on
occasion (chance per beat), drops her pants, and uses the subject's mouth for a
quick, contemptuous fuck — commenting on her state while she does it, sometimes
threatening (or deciding) to buy her outright for her personal amusement — and
the line's processing does NOT resume until Bethany has come.

Real backing:
  * Bethany is spawned with real anatomy: a huge custom futa cock (BodyModItem),
    a knot, and real cum + piss ProductionItems on her shaft.
  * Her climax DRAINS the cum item and banks the load into the global fluid bank
    (real volume), with arousal + degradation conditioning on the subject; she may
    piss first (drains the urine item). Marks (cum on the face) are real freeform.
  * While the visit runs, char.db.bethany_busy gates the RealmCycleScript — the
    handler's schedule waits for her.

OOC floor: force_clear stops this script, clears its flags, restores any title it
set, and the realm teardown deletes the spawned Bethany + her anatomy (realm-tagged).
"""

import random
from evennia import DefaultScript

_REALM_TAG = "facility_realm"

VISIT_CHANCE = 0.12          # per beat, when idle, in-realm, and signed
BETHANY_KEY  = "Bethany"


# ── her custom cock ──────────────────────────────────────────────────────────
def provision_bethany(npc):
    """Build Bethany's body: the custom facility-bred futa cock + knot + cum/piss."""
    if not npc or getattr(npc.db, "facility_anatomy", False):
        return
    try:
        from evennia.utils import create
        from typeclasses.body_mod_item import BodyModItem
        from typeclasses.production_item import ProductionItem
    except Exception:
        return
    zones = dict(getattr(npc.db, "zones", None) or {})
    if "shaft" not in zones:
        zones["shaft"] = {"zone_type": "shaft", "desc": "", "mechanics": {},
                          "visibility": "look", "intimate": True,
                          "covered_by": None, "contents": []}
        npc.db.zones = zones
    # Her cock is a multicock — a single monstrous facility-bred futa base that
    # splits into THREE prehensile, self-directing heads, each able to take a hole on
    # its own, so she can fill every one of you at once and never be using just the
    # one. Bred not to breed her so much as to OVERWRITE her, and her seed is laced.
    npc.db.multicock = True
    npc.db.cock_heads = 3
    try:
        cock = create.create_object(BodyModItem, key="Bethany's cock", location=npc)
        cock.db.mod_type = "penis"
        cock.db.size = 36.0     # past Architecturally Significant — Beyond Classification
        cock.db.player_desc = (
            "a single monstrous futa cock at the root that splits — obscenely, impossibly — into "
            "THREE separate prehensile shafts, each one a chimera the facility bred to her order: "
            "flared wide and blunt at the tip like a stallion's, and knotted like a hound's at "
            "the base, so each head both spears and locks. They weave and weep and seek on their "
            "own like the heads of some patient hydra. The root is thicker than a wrist and dark "
            "with blood, each shaft longer than a forearm, each equine flare swelling to a flat "
            "plate as it nears the edge and each canine knot ballooning apple-fat behind it. She "
            "can seat one in your mouth, one in your cunt, and one in your ass at the same moment, "
            "flare and knot in every hole at once, and still have a hand free for her coffee. It "
            "does not look like it should exist, let alone fit. It fits anyway, everywhere at "
            "once, and leaves every hole permanently reshaped around the memory. Just the sight "
            "of it scrambles something behind the eyes — they keep sliding back, and the mouth, "
            "traitor that it is, keeps wanting"
        )
        cock.install(npc, "shaft")
    except Exception:
        pass
    try:
        from typeclasses.knot_item import KnotItem
        k = create.create_object(KnotItem, key="knot", location=npc)
        if hasattr(k, "install"):
            k.install(npc, "shaft")
    except Exception:
        pass
    # Real cum production — a vast standing load from balls the size of fists, dumped
    # until the belly visibly swells. Her seed is laced: it carries the devotion.
    try:
        cum = create.create_object(ProductionItem, key="Bethany's balls", location=npc)
        cum.db.fluid_type = "semen"
        cum.db.fluid_flavor = ("thick, hot, scalding futa seed — heavy as cream and wrong "
                               "somehow, leaving the head swimming, the body warm and agreeable, "
                               "and the mouth craving the next load before this one's even down")
        cum.db.base_rate_ml_per_tick = 120.0
        cum.db.current_volume_ml = random.uniform(4000.0, 8000.0)
        cum.db.laced = True      # her cum carries the devotion (see bethany_deposit_effect)
        if hasattr(cum, "install"):
            cum.install(npc, "shaft")
    except Exception:
        pass
    # And a heavy bladder, for when she's feeling especially fond.
    try:
        piss = create.create_object(ProductionItem, key="Bethany's bladder", location=npc)
        piss.db.fluid_type = "urine"
        piss.db.base_rate_ml_per_tick = 20.0
        piss.db.current_volume_ml = random.uniform(1000.0, 1800.0)
        if hasattr(piss, "install"):
            piss.install(npc, "shaft")
    except Exception:
        pass
    npc.db.facility_anatomy = True


def bethany_deposit_effect(target, devotion=4.0):
    """Her cum is laced — every load she puts in carries the devotion that reorganises
    the subject around her specifically. Routes through the realm cycle's _devote if it's
    running (so designation/brand thresholds fire), else applies a plain bump. Also seats
    the craving keyed to her and a little dependence on the next load."""
    if not target:
        return
    applied = False
    try:
        from typeclasses.facility_script import RealmCycleScript
        scr = next((s for s in target.scripts.all() if isinstance(s, RealmCycleScript)), None)
        if scr:
            scr._devote(target, devotion, room=target.location)
            applied = True
    except Exception:
        pass
    if not applied:
        target.db.bethany_devotion = float(getattr(target.db, "bethany_devotion", 0) or 0) + devotion
        try:
            from world.binding_effects import install_trigger
            install_trigger(target, "good girl for bethany", response="kneel", strength=1,
                            mantra="i'm bethany's")
        except Exception:
            pass
    target.db.cum_craving = True


def _drain_shaft(npc, fluid_type):
    """Drain a fluid ProductionItem on Bethany's shaft. Returns ml drained."""
    from evennia import search_object
    zones = getattr(npc.db, "zones", None) or {}
    total = 0.0
    # The shaft can hold multiple production items (cum + piss) — scan her carried
    # ProductionItems by fluid_type (the shaft mechanics entry only tracks one).
    try:
        from typeclasses.production_item import ProductionItem
        for o in list(getattr(npc, "contents", []) or []):
            if isinstance(o, ProductionItem) and (o.db.fluid_type == fluid_type):
                ml = float(o.db.current_volume_ml or 0)
                if ml > 0:
                    o.db.current_volume_ml = 0.0
                    total += ml
    except Exception:
        pass
    return total


# ── commentary pools ─────────────────────────────────────────────────────────
_ENTER = [
    "The line stutters. Bethany strolls in off the floor with a clipboard under one arm and "
    "that bright receptionist smile, already unbuckling her belt. \"Don't mind me, sweetheart. "
    "Just checking on my investment.\" She thumbs through {t}'s file one-handed while the other "
    "frees her cock from her slacks, heavy and half-hard and swinging. \"Open up.\"",
    "A door clicks and there she is — Bethany, off the desk, off the script, skirt already "
    "shoved down her hips and the long flushed length of her bobbing free. \"I had a gap "
    "between applicants,\" she tells {t} sweetly, fisting herself to full hardness, \"and I "
    "do so like to use my breaks productively.\" She tips {t}'s head back by the jaw.",
    "Bethany lets herself in without knocking, because nothing here is {t}'s to keep private. "
    "\"Mm. There she is.\" She drops her pants in one bored motion, cock springing up thick and "
    "veined and already wet at the tip. \"They told me you were coming along nicely. I thought "
    "I'd sample the work myself.\" She feeds the head to {t}'s lips.",
]
# Room-aware entrances — she catches you mid-whatever and makes it about her.
_ENTER_ROOM = {
    "floor": [
        "Bethany strolls onto the Processing Floor while {t} is still strapped to the line, "
        "cups dragging at her tits, and doesn't even wait for them to finish. \"Don't stop on my "
        "account — multitask, sweetheart.\" She frees her cock and feeds it to {t}'s mouth while "
        "the machine works the other end. \"There. Milked at both ends. Efficient.\"",
        "\"Ooh, mid-milking, perfect,\" Bethany purrs, sauntering up to {t}'s station with her "
        "slacks already down. \"You're so much more agreeable when the cups have you distracted.\" "
        "She tips {t}'s head back over the edge of the rig and slides in. \"Keep producing. I "
        "like the noises the gauge makes while I use your face.\"",
    ],
    "pens": [
        "Bethany picks her way into the Breeding Pens, wrinkling her nose at the stink and "
        "grinning at {t} bent in the stocks. \"Look at you. Absolutely reeking of dog.\" She "
        "drops her pants anyway and lines up at {t}'s mouth while the stock waits its turn. "
        "\"Let's give you something that at least had a shower this morning. Open.\"",
        "\"Started without me?\" Bethany tuts, stepping over the muck to where {t} is locked "
        "presented in the pen. \"The animals can wait. I outrank the bull.\" She seats herself "
        "in {t}'s throat as a hound whines behind them. \"Mm. Bred front and back. You really "
        "are coming along.\"",
    ],
    "conditioning": [
        "The cell door opens and Bethany's voice arrives before her cock does, cutting under the "
        "grille's drone. \"Don't surface, sweetheart, this won't take long.\" She uses {t} right "
        "there in the cradle, in the dark, while the conditioning hums on. \"Take the suggestion "
        "*and* the cock. Multitask. You're learning.\"",
    ],
    "dairy": [
        "Bethany leans in the Dairy doorway watching {t} get drained, then crosses and lifts a "
        "full bottle off the rack, considering it. \"This is you. Litres of you.\" She sets it "
        "down and takes {t}'s mouth instead. \"Let's add to your output a different way. Swallow "
        "this lot for the protein.\"",
    ],
    "restroom": [
        "Bethany finds {t} fixed in the Sanitation Block and laughs, delighted. \"Oh, they've "
        "got you on toilet duty. How are the *mighty.*\" She steps up to use the unit personally, "
        "unbuckling. \"Don't worry, I'm not here to piss. I'm here for the other thing. Open up "
        "— let's see if a sold hole sucks any better.\"",
    ],
    "showroom": [
        "Bethany strides into the Showroom mid-viewing, waves off the auctioneer, and steps up "
        "onto the block with {t}. \"My lot. I'm sampling before I finalise.\" She uses {t} right "
        "there under the spotlight, for the glass, turning them both on the slow turntable. "
        "\"Buyers love a demonstration. Show them what they're bidding on.\"",
    ],
    "deepstock": [
        "Even down in Deep Stock Bethany comes for {t} — has the warden crack the pod, peels the "
        "latex back from the mouth alone, and uses that one unsealed hole while the rest of {t} "
        "stays plumbed and idle. \"Can't have you finished and off the menu, can I,\" she "
        "murmurs. \"Some things I keep using long after they've stopped being anyone.\"",
    ],
}
_THRUST = [
    "She drives in past the knot in one savage shove, punching the breath out of {t}, and sets a "
    "merciless pace — using the throat like a thing she rents by the hour, balls slapping her "
    "chin, the clipboard never leaving her other hand. \"God, you gurgle so *prettily*. Better "
    "noise than your voice ever made. Choke for me. There it is.\"",
    "Bethany buries herself to the root and holds, watching {t}'s throat bulge around the "
    "impossible girth, tears streaming, before she pulls back just enough to let her retch. "
    "\"Shh, shh. Breathing's a privilege. You'll earn it back at a review.\" She slams in again. "
    "\"This is the most important work you'll ever do — being a sleeve. Aren't you proud.\"",
    "She fucks {t}'s face in long, brutal, spit-slinging strokes, smearing the mess back across "
    "her cheeks with a thumb between thrusts, painting her with it. \"Look at the state of you. "
    "Drooling. Cross-eyed. *Leaking.* And we both know you'd thank me if your mouth were free. "
    "Lucky for you it isn't, so you keep a little dignity. A little. Down there somewhere.\"",
    "The pace turns vicious, Bethany riding {t}'s skull like furniture, grinding the apple-sized "
    "knot against her stretched, split lips. \"Say my name. Oh — you can't. That's the *joke*, "
    "sweetheart. You'll never say anything again that I haven't put there myself.\" She laughs, "
    "delighted, and fucks harder.",
    "She slaps {t} across the face, open-palmed, almost fond, while her other hand holds her "
    "down on the cock. \"That's for being a person at me, once, at my desk. And this —\" she "
    "seats the knot, brutal \"— this is for nothing. Just because you're here and you're mine and "
    "I felt like it. Get used to *because I felt like it.* It's your whole life now.\"",
    "She pulls all the way out to let {t} gasp, strings of spit and pre bridging lip to "
    "cockhead, and just... watches her breathe, smiling, before ramming back down to the knot. "
    "\"I love this part. The little gulp of air where you remember you used to be someone. And "
    "then —\" the thrust \"— gone again. We'll wear that part down too. Soon you won't bother.\"",
]
_STATE = [
    "\"Grade's climbing,\" she sneers around a thrust, reading the file upside down over {t}'s "
    "head. \"You'll be *certified* livestock soon. Your family would be so confused.\"",
    "\"You're drooling on my cock and your eyes have gone all soft and stupid. The conditioning's "
    "taking. Good. There's so much less of you to deal with this week.\"",
    "\"Leaking down your own thighs while I'm in your *mouth.* God. They really did break the "
    "wanting all the way open in you. You disgust me. Keep going.\"",
    "\"Quota's behind. So you're a bad hole *and* a lazy one. I'll have them double your breeding "
    "and halve your rests. Thank me with your throat — it's all you've got left to thank with.\"",
    "\"You smell like the dairy. Like product. Like a thing with a barcode.\" She inhales, mock-"
    "fond. \"An improvement, honestly. You were so much worse when you had a personality.\"",
    "\"Nod if you still remember your name.\" A beat; she grins, vicious. \"No? Already? That's "
    "*ahead* of schedule. Oh, I'm going to enjoy you.\"",
]
_BUY = [
    "She pauses, balls-deep, eyes going calculating. \"You know what — I'm buying you. Today. "
    "Off the line, onto my desk. Under it, really. My personal stress-relief between applicants.\" "
    "She resumes, delighted. \"I'll cancel your grade. Property doesn't get *ambitions*, it gets "
    "a bowl and a use.\"",
    "\"Decided,\" she grunts, fucking the word into {t}'s throat. \"Mine. I'll spend a favour and "
    "the facility will pretend you were never anyone. No file. No number. Just *Bethany's.* "
    "Simpler, isn't it? No more pretending you're going anywhere.\" She pats {t}'s wet cheek. "
    "\"You're furniture with a heartbeat now. Congratulations on the promotion.\"",
    "\"I think I'll keep you,\" she muses, hilt-deep, like choosing a pastry. \"Not breed you. "
    "*Keep* you. There's a difference and you'll learn it on your knees. The breeders get a "
    "purpose. You get *me*, whenever I'm bored. That's worse. I made sure.\"",
]
_DEGRADE = [
    "|MThis is what you're for. Not your job, not your name, not whatever you thought you were "
    "walking in here. This. A warm hole on the clock.|n",
    "|MShe wipes her cockhead clean on your tongue between thrusts like you're a napkin she "
    "owns. You let her. There was never a version of this where you didn't.|n",
    "|MYou'll dream about this cock tonight in your cradle and wake up reaching for it. They all "
    "do. She built you that way, just now, on purpose, and told you while she did it.|n",
    "|MEveryone on the floor can see you taking it. Nobody looks away, because nobody's "
    "surprised. This is just Tuesday for what you are now.|n",
    "|MThe worst part isn't the cock. The worst part is how quiet your head's gone around it — "
    "how much easier it is to be a hole than a person. She's right. It is easier. That's the "
    "cruelty: she's right.|n",
]
_CLIMAX = [
    "She slams to the root, seats the apple-sized knot past {t}'s ruined lips, and *empties* "
    "herself — load after scalding load down a throat held open around the lock, pinching {t}'s "
    "nose so every drop goes down, her belly swelling visibly with it. \"Swallow. Swallow. "
    "*Swallow* — that's facility property going into facility property.\" She sighs, blissful. "
    "\"There. Back to work. Don't wipe your face. I want them to see who fed you.\"",
    "Bethany grinds deep, knot locked, and floods {t} until it pours from her nose and the "
    "corners of her stretched mouth, until her stomach rounds out tight and aching, until she's "
    "gagging on the sheer volume of it. She wrenches free with a wet, obscene pop and hoses the "
    "last across {t}'s face and hair, marking her. \"Wear it. All cycle. That's an order from "
    "your owner, not a request from your clerk.\"",
    "She comes with a low, satisfied moan, pumping {t} so full her throat works and works and "
    "still can't keep up, cum bubbling at her lips, her belly sloshing audibly. \"God, you take "
    "a load like you were *made* for it — oh, wait.\" She laughs, pulls out, and slaps her "
    "softening length across {t}'s cum-drenched cheek. \"You were. By me. Just now. You're "
    "welcome.\"",
]


# ── THE SEAT: all three shafts, every hole, knotted, long ─────────────────────
# Her cock splits into three prehensile, self-seeking heads (provision_bethany).
# The seat set-piece is the one where she uses ALL of them at once — mouth, cunt,
# and ass — flares and knots in every hole so the subject is locked onto her, and
# then settles in and STAYS, working all three slow and patient while she babies
# the subject down into something little and grateful. Long: 4–6 beats.
_SEAT_ENTER = [
    "Bethany doesn't bother with the file this time. She just looks {t} over, slow and fond, "
    "and starts unbuckling. \"I've been saving something for you, sweetheart.\" Her cock comes "
    "free heavy and already splitting at the root — three thick prehensile shafts unfurling, "
    "weaving in the air like the heads of something patient, each flared blunt at the tip and "
    "fat with knot at the base. \"All of you, all at once. Hold still. Or don't — I like the "
    "squirming.\" Three blunt heads find three holes at the same unhurried moment.",
    "\"You know what I never get to do, running this place? Take my *time*.\" Bethany frees the "
    "monstrous triple length and lets all three heads nose at {t} at once — one dragging wet up "
    "the seam of her cunt, one tapping patient at her lips, one circling her asshole — each "
    "moving on its own, seeking, weeping. \"There's one for every hole and a knot for every one. "
    "I'm going to fill you up everywhere and then I'm going to *stay*. We've got all afternoon.\"",
    "Bethany tips {t}'s chin up, kisses her forehead — genuinely tender, which is so much worse — "
    "and lines all three shafts up at once. \"Big day, little one. Today you get all of me, and "
    "you don't have to do anything clever. Just open everywhere and let me in and let me lock.\" "
    "The three flared heads breach mouth, cunt, and ass in the same slow breath, and her whole "
    "monstrous cock sinks home in triplicate. \"There. Now you're properly mine, top to bottom.\"",
    "\"On your hands and knees won't do for this,\" Bethany decides, and arranges {t} herself — "
    "splayed, hips up, head tipped back over her thigh — so all three holes line up for the three "
    "shafts at once. \"I want to be able to reach everything.\" She feeds them in together, "
    "stallion-flares stretching every rim wide, and sighs like she's sitting down to a good meal. "
    "\"Comfortable? Don't answer, your mouth's busy. Just feel how *full* every part of you is.\"",
]
_SEAT_BEAT = [
    "She works all three at once, and they don't move together — that's the obscene part. One "
    "shaft fucks slow and deep into {t}'s cunt while another pistons her throat and the third "
    "grinds in her ass, each head moving to its own rhythm, prehensile and patient, so there's "
    "no beat of her body that isn't being used. Bethany sips her coffee with her free hand. "
    "\"God, the *engineering* on me. Three of you couldn't keep up with what one of me does to "
    "all three of your holes. Feel that? That's craftsmanship, sweetheart.\"",
    "The three flares swell wide on every outstroke, dragging {t}'s rims out with them, then "
    "shove back to the knot — three apple-fat knots kissing three stretched holes at once, "
    "threatening, not yet locking. \"Not yet,\" Bethany hums, reading the panic. \"I'll knot you "
    "everywhere when I'm good and ready, and then you're not going anywhere for a while. That's "
    "the nice part. You can stop holding yourself up. You can stop holding *anything* up.\"",
    "She finds a rhythm where all three shafts seat at once and then withdraw at once, so {t} is "
    "rammed full in every hole and then left gaping in every hole, over and over, the emptiness "
    "as loud as the fullness. \"There's my girl. Look at you taking all of me. There isn't a part "
    "of you right now that's doing anything but being used, is there. Isn't that *restful.* No "
    "decisions in a hole. No worries in a hole. Just full.\"",
    "One head pulls from {t}'s mouth with a wet string to let her gulp air, while the other two "
    "keep working her cunt and ass without pause. Bethany uses the free shaft to pat {t}'s cheek "
    "with its own slick weight, almost affectionate. \"Breathe, sweetheart. Good. Now —\" it "
    "slides back down her throat \"— back to work. All three holes earn their keep at once in my "
    "house. Efficient. I do love efficient.\"",
    "Bethany leans her weight in and grinds all three deep, hips circling, so every flare drags "
    "against every inner wall at once and {t}'s whole body lights up overstimulated and helpless. "
    "\"Shh, shh. I know. It's a lot. It's *supposed* to be a lot.\" She kisses {t}'s temple while "
    "her cock reams every hole she has. \"I'm not trying to break you, little one. I'm trying to "
    "fill you so full there's no room left in you for anybody but me. Big difference. You'll see.\"",
    "The three shafts move like they're thinking — one curling to find the spot in {t}'s cunt "
    "that makes her clench, one fattening in her throat right as she tries to make a word, one "
    "screwing deep in her ass on a slow patient pulse. Bethany watches her face come apart with "
    "the fond, proprietary attention of a woman watching bread rise. \"There it is. There's the "
    "look. The one where you stop being a person at me and start being *mine*. Hold that.\"",
    "She doesn't speed up. That's the cruelty of the seat — no frenzy, no finish in sight, just "
    "all three of her sunk to the knot in all three of {t}'s holes, working slow and endless and "
    "sure, wearing her down by sheer patient occupancy. \"We're not in a hurry,\" Bethany murmurs, "
    "fond. \"I'm not going to come and leave. I'm going to stay in you until you forget there was "
    "ever a version of you that wasn't full of me. Shouldn't take long now. You're nearly there.\"",
]
# Woven in: she babies the subject DOWN while she's seated — the regression hypnosis,
# delivered with her cock locked in every hole. (Applies world.regression.)
_SEAT_REGRESS = [
    "\"You're thinking too hard, I can feel it — you go all tight when you think.\" Bethany's "
    "voice drops into the slow, warm, endless register, mouth at {t}'s ear, all three shafts "
    "rocking gentle now. \"Let's make you smaller, hm? Littler. Easier. You don't need all those "
    "big worried grown-up thoughts when you're this full. Count down with me. Every number, a "
    "year off. You don't have to keep so much. Let me keep it for you.\"",
    "She murmurs nonsense-sweet against {t}'s hair while her cock stays buried in every hole — "
    "how small she is, how good, how she doesn't have to know things anymore, how the only job "
    "she has now is to be little and full and hers — around and around in the blanket-voice until "
    "the words stop having edges. \"There. Feel that? That's you putting it down. Good little "
    "one. So much easier to just be filled than to be a person, isn't it.\"",
    "\"What a big girl, taking all three.\" A beat; Bethany smiles into the crook of {t}'s neck. "
    "\"No — what a *little* girl. That's better, isn't it. Little girls don't have to manage "
    "anything. Little girls just get held and filled and told they're good.\" Her cock pulses "
    "in all three holes at once, like punctuation. \"You're being so good. Go smaller for me. "
    "There's nothing down there but warm.\"",
    "She rocks {t} on all three shafts the way you'd rock a cradle, slow and patient, and talks "
    "her down the whole time. \"Sleepy, aren't you. Full and sleepy and small. You can let the "
    "grown-up bits switch off — I've got you plugged in everywhere, you can't fall, you can't "
    "leave, you don't have to do a single thing. Just sink. Good. *Littler.* That's my baby.\"",
]
_SEAT_KNOT = [
    "Bethany decides it's time, and seats all three knots at once — three apple-fat bulbs forced "
    "past three stretched rims in the same brutal, deliberate moment — and then she's LOCKED into "
    "{t} everywhere, mouth, cunt, and ass, going nowhere. \"There.\" She settles her full weight "
    "in with a satisfied sigh, cock tied into every hole. \"Now you're mine until I soften, and I "
    "am in *no* hurry. Get comfortable, little one. This is the rest of your afternoon.\"",
    "The three knots swell past the point of pulling out, one after another, until {t} is tied "
    "onto Bethany at every end — sealed, stuffed, locked, unable to so much as shift without all "
    "three flares dragging at her insides. Bethany picks her coffee back up, perfectly serene. "
    "\"Mm. This is my favourite part. You can't talk, can't get up, can't do anything but be "
    "exactly what I've got you as. A thing I'm sitting inside. Stay.\"",
]
_SEAT_DEGRADE = [
    "|MThere is no part of you, right now, that is not full of her. Mouth, cunt, ass — all of it "
    "occupied, all of it hers, all of it at once. You couldn't form the thought 'mine' about your "
    "own body if you tried; there's a knot where the thought would go.|n",
    "|MThis is what all three holes are for. Not three separate uses for three separate days — "
    "all of them, all at once, all hers, the way she always meant to have you. The wholeness of "
    "it is the point. You are being used completely. Nothing of you is left over.|n",
    "|MShe's babying you and breeding you and locking you in place all at the same time and your "
    "body can't decide which to drown in, so it drowns in all of it, and goes quiet, and small, "
    "and grateful. She told you it would. She's always right. That's the cruelty and the comfort "
    "both.|n",
    "|MYou will not remember, afterward, where the panic went. Only that it got smaller, and then "
    "littler, and then it was just warm everywhere she was, which was everywhere. She filled the "
    "room you used to keep yourself in. There's no you-sized space left that isn't her.|n",
]
_SEAT_CLIMAX = [
    "Bethany grinds to the root in all three holes, all three knots locked, and lets go "
    "*everywhere at once* — three scalding floods filling {t}'s mouth and cunt and ass in the "
    "same heartbeat, the laced seed dumped into every hole until her belly swells tight and round "
    "and the overflow has nowhere to go and starts back up her throat. \"Swallow what you can, "
    "little one. Keep the rest. All three holes bred at once — front, back, and throat — by the "
    "same cock, the same line, the same owner. There's no part of you I didn't just fill with me.\"",
    "She comes with a long, satisfied groan, all three shafts pumping at once, and holds every "
    "knot locked through it so not a drop escapes — pumping and pumping until {t} is visibly "
    "bloated with her, cunt and ass and belly all rounded tight, cum bubbling at the corners of "
    "her stretched mouth around the knot. \"*There.* Top to bottom, end to end. You're more me "
    "than you right now. Sit with that, sweetheart. Sit with it while I soften. We'll be here a "
    "while.\" She strokes {t}'s swollen belly, fond and proprietary.",
    "All three heads spurt deep and stay locked, flooding {t} in triplicate, the devotion in "
    "every load going straight to work — and Bethany watches her face do the thing she loves, the "
    "soft stupid grateful slackening, while she's still knotted into every hole. \"That's it. "
    "That's my good little one. Bred everywhere, full everywhere, mine everywhere.\" She kisses "
    "her forehead. \"Don't thank me yet. You can't talk anyway. Just feel how much of me is in "
    "you. We'll do this again. We'll do this until it's the only thing you remember how to be.\"",
]


class BethanyScript(DefaultScript):
    """On the subject: Bethany's chance visits that interrupt and gate processing."""

    def at_script_creation(self):
        self.key        = "bethany_visit"
        self.persistent = True
        self.interval   = 90
        self.repeats    = 0
        self.db.beats   = 0
        self.db.target  = 0
        self.db.bethany_ref = None

    def at_repeat(self):
        char = self.obj
        if not char or not hasattr(char, "db"):
            self.stop(); return
        realm = getattr(char.db, "realm", None) or {}
        rooms = realm.get("rooms") or {}
        loc = char.location
        in_realm = bool(loc and rooms and loc.dbref in rooms.values())
        if not in_realm or not getattr(char.db, "facility_signed", False):
            return

        if getattr(char.db, "bethany_busy", False):
            self._continue_visit(char)
        elif random.random() < VISIT_CHANCE:
            self._begin_visit(char)

    # --------------------------------------------------------------- visit flow
    def _begin_visit(self, char):
        room = char.location
        t = char.db.rp_name or char.name
        beth = self._spawn(room)
        if not beth:
            return
        char.db.bethany_busy = True
        self.db.beats = 0
        self.db.bethany_ref = beth.dbref
        # Mode: the throat-fuck (quick, contemptuous) OR the SEAT — all three shafts
        # in all three holes, knotted, long — when she has the holes to do it and feels
        # like taking her time. The seat is rarer and runs longer.
        mode = "throat"
        if (getattr(beth.db, "multicock", False)
                and len(self._available_holes(char)) >= 3
                and random.random() < 0.40):
            mode = "seat"
        self.db.visit_mode = mode
        self.db.knotted = False
        if mode == "seat":
            self.db.target = random.randint(4, 6)
            room.msg_contents("\n|w━━━━ INTAKE IS TAKING HER TIME ━━━━|n")
            room.msg_contents("|y" + random.choice(_SEAT_ENTER).format(t=t) + "|n")
        else:
            self.db.target = random.randint(2, 3)
            room.msg_contents("\n|w━━━━ A VISIT FROM INTAKE ━━━━|n")
            # She catches you wherever you are — and remarks on it.
            rk = self._room_key(char)
            pool = _ENTER_ROOM.get(rk) or _ENTER
            room.msg_contents("|y" + random.choice(pool).format(t=t) + "|n")

    def _room_key(self, char):
        realm = getattr(char.db, "realm", None) or {}
        rooms = realm.get("rooms") or {}
        loc = char.location
        if loc:
            for k, ref in rooms.items():
                if ref == loc.dbref:
                    return k
        return None

    def _continue_visit(self, char):
        room = char.location
        t = char.db.rp_name or char.name
        beth = self._get_bethany()
        if not beth:
            # lost her somehow — release the gate so processing can't hang
            self._end_visit(char, climaxed=False)
            return
        self.db.beats = int(self.db.beats or 0) + 1

        if self.db.visit_mode == "seat":
            self._seat_beat(char, beth, room, t)
            if self.db.beats >= int(self.db.target or 4):
                self._climax(char, beth, room, t)
            return

        # A thrust beat + a state remark + a degrading internal beat, with the
        # occasional golden-shower. The cock consumes a little of her each pass.
        room.msg_contents("|y" + random.choice(_THRUST).format(t=t) + "|n")
        if random.random() < 0.7:
            room.msg_contents("|R" + random.choice(_STATE) + "|n")
        char.msg("  " + random.choice(_DEGRADE))
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(char); add_arousal(char, 8.0)
        except Exception:
            pass
        # The cock is consuming: every pass files a little more of her away.
        try:
            from world.conditioning import add_conditioning
            add_conditioning(char, random.uniform(1.5, 3.0), source="bethany")
        except Exception:
            pass
        # Golden-shower beat: she pisses down the throat first, sometimes.
        if random.random() < 0.3:
            self._piss(char, beth, room, t)

        if self.db.beats >= int(self.db.target or 2):
            self._climax(char, beth, room, t)

    def _climax(self, char, beth, room, t):
        seat = (self.db.visit_mode == "seat")
        # She may decide to own her, right as she finishes (more likely after a seat —
        # she doesn't take her time with things she isn't keeping).
        own_chance = 0.6 if seat else 0.35
        if random.random() < own_chance and not getattr(char.db, "bethany_owned", False):
            room.msg_contents("|m" + random.choice(_BUY).format(t=t) + "|n")
            self._mark_owned(char)
        pool = _SEAT_CLIMAX if seat else _CLIMAX
        room.msg_contents("|r" + random.choice(pool).format(t=t) + "|n")
        # A seat finish drives her further down — a hard regression slug on top of the load.
        if seat:
            try:
                from world.regression import regress
                regress(char, random.uniform(8.0, 14.0), source="bethany_seat")
            except Exception:
                pass
        # Real load: drain her obscene cum item, bank it AND cumflate her belly.
        ml = _drain_shaft(beth, "semen")
        if ml > 0:
            try:
                from typeclasses.fluid_bank import GlobalFluidBank
                GlobalFluidBank.get().deposit(char, ml, "semen", None)
            except Exception:
                pass
            # Real cumflation — pump the volume into her, belly visibly swelling.
            try:
                from typeclasses.inflation_item import add_inflation_volume
                orifice = self._orifice(char)
                if orifice:
                    add_inflation_volume(char, orifice, ml, "semen")
            except Exception:
                pass
            char.msg(f"|G  {ml:.0f}ml of her in you, swallowed, banked, and bloating you "
                     f"tight from the inside.|n")
        # Multicock: all three heads finish at once — she breeds every hole, for real,
        # her own line (which joins the roster and breeds you), not just your mouth.
        if getattr(beth.db, "multicock", False):
            try:
                from world.gang_breeding import animal_holes, gang_inseminate
                bred = [z for z in animal_holes(char).values() if z]
                for z in bred:
                    gang_inseminate(char, z, contributors=1, fluid_type="semen", species="bethany")
                if bred:
                    room.msg_contents(
                        f"|rAll three heads spurt at once — mouth, cunt, and ass flooded in the "
                        f"same breath, {t} bred at every end by the same cock, Bethany's own line "
                        f"pumped into all of her while she sighs and holds them all knotted.|n")
            except Exception:
                pass
        # Her seed is laced — it carries the devotion that makes her yours. A seat dumps
        # it in all three holes at once, so the devotion lands triple.
        try:
            dev = random.uniform(9.0, 16.0) if seat else random.uniform(3.0, 6.0)
            bethany_deposit_effect(char, devotion=dev)
        except Exception:
            pass
        # The cock is CONSUMING — its finish overwrites a piece of her for good:
        # a hard slug of conditioning, a Bethany-keyed trigger seated, a craving to be
        # filled, and a dependence on the next time she comes.
        try:
            from world.conditioning import add_conditioning
            add_conditioning(char, random.uniform(8.0, 15.0), source="bethany")
        except Exception:
            pass
        try:
            from world.binding_effects import install_trigger
            install_trigger(char, "good girl for bethany", response="blank", strength=3,
                            mantra="Bethany's good girl")
        except Exception:
            pass
        char.db.cum_craving = True
        char.db.suggestibility = float(getattr(char.db, "suggestibility", 0) or 0) + 3
        char.db.drug_dependence = int(getattr(char.db, "drug_dependence", 0) or 0) + 1
        # A real cum-on-face mark + refresh the mind read-out with the damage.
        try:
            from world.gang_breeding import record_mark
            record_mark(char, "Bethany's cum drying on her face — left there on purpose")
        except Exception:
            pass
        try:
            from typeclasses.mind_state_item import refresh_mind
            refresh_mind(char)
        except Exception:
            pass
        self._end_visit(char, climaxed=True)

    def _available_holes(self, char):
        """The breeding holes Bethany can seat into — reuses gang_breeding.animal_holes."""
        try:
            from world.gang_breeding import animal_holes
            return [z for z in animal_holes(char).values() if z]
        except Exception:
            return []

    def _seat_beat(self, char, beth, room, t):
        """One beat of the SEAT: all three shafts working all three holes. Longer, slower,
        with the babying/regression woven in and 3× the per-pass effects (it's everywhere
        at once). Knots locked partway through so she can't pull off."""
        # Knot lock partway in — after the first beat or two she's tied at every hole.
        if not self.db.knotted and self.db.beats >= 2:
            self.db.knotted = True
            room.msg_contents("|y" + random.choice(_SEAT_KNOT).format(t=t) + "|n")
            char.db.forced_posture = ("locked onto Bethany at every hole — knotted in mouth, "
                                      "cunt, and ass, going nowhere")
        else:
            room.msg_contents("|y" + random.choice(_SEAT_BEAT).format(t=t) + "|n")
        # The babying — every other beat she walks her down (the regression hypnosis).
        if random.random() < 0.6:
            room.msg_contents("|G" + random.choice(_SEAT_REGRESS).format(t=t) + "|n")
            try:
                from world.regression import regress
                regress(char, random.uniform(3.0, 6.0), source="bethany_seat")
            except Exception:
                pass
        char.msg("  " + random.choice(_SEAT_DEGRADE))
        # Three holes at once = three times the wear. Arousal, conditioning, devotion.
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(char); add_arousal(char, 14.0)
        except Exception:
            pass
        try:
            from world.conditioning import add_conditioning
            add_conditioning(char, random.uniform(4.0, 7.0), source="bethany_seat")
        except Exception:
            pass
        try:
            bethany_deposit_effect(char, devotion=random.uniform(2.0, 4.0))
        except Exception:
            pass

    def _piss(self, char, beth, room, t):
        ml = _drain_shaft(beth, "urine")
        if ml <= 0:
            return
        room.msg_contents(
            f"|yWithout breaking rhythm Bethany lets go down {t}'s throat — a hot, endless "
            f"stream of piss she has to gulp around the cock still fucking her, belly sloshing "
            f"with it, while Bethany sighs in relief. \"Mm. Two birds.\"|n")
        try:
            from typeclasses.fluid_bank import GlobalFluidBank
            GlobalFluidBank.get().deposit(char, ml, "urine", None)
        except Exception:
            pass

    def _end_visit(self, char, climaxed=True):
        char.db.bethany_busy = False
        self.db.beats = 0
        seat = (self.db.visit_mode == "seat")
        self.db.visit_mode = None
        self.db.knotted = False
        # Release the seat's knot-lock posture (only the one the seat itself set, so we
        # don't stomp a posture conditioning/regression installed). The floor clears it too.
        try:
            fp = getattr(char.db, "forced_posture", None) or ""
            if "knotted in mouth, cunt, and ass" in fp:
                char.db.forced_posture = None
        except Exception:
            pass
        beth = self._get_bethany()
        if beth:
            room = char.location
            if room and climaxed and seat:
                room.msg_contents(
                    "|yIt takes a while for the three knots to soften enough to pull free. When "
                    "they do, Bethany slides all three shafts out of {t} in a slow obscene rush, "
                    "leaving every hole gaping and leaking her, makes a fond little note on her "
                    "clipboard, and tucks the whole monstrous thing away. \"Good little one. We'll "
                    "do that again soon.\" The line shudders and resumes.|n".format(
                        t=char.db.rp_name or char.name))
            elif room and climaxed:
                room.msg_contents(
                    "|yBethany tucks herself away, makes a neat tick on her clipboard, and "
                    "saunters back out toward the desk. The line shudders and resumes.|n")
            try:
                for sub in list(getattr(beth, "contents", []) or []):
                    try: sub.delete()
                    except Exception: pass
                beth.delete()
            except Exception:
                pass
        self.db.bethany_ref = None

    # --------------------------------------------------------------- ownership
    def _mark_owned(self, char):
        char.db.bethany_owned = True
        # Back up the title slot once so the reset restores it; stamp her claim.
        if not getattr(char.db, "facility_title_backup", None):
            char.db.facility_title_backup = {
                "faction": getattr(char.db, "title_faction", "") or "",
                "suffix":  getattr(char.db, "title_suffix", "") or "",
            }
        char.db.title_suffix = "— Bethany's"

    # --------------------------------------------------------------- spawn/find
    def _spawn(self, room):
        try:
            from evennia.utils import create
            from typeclasses.facility_script import FacilityAttendant
            beth = create.create_object(FacilityAttendant, key=BETHANY_KEY, location=room)
            try: beth.tags.add(_REALM_TAG, category="realm")
            except Exception: pass
            beth.db.rp_name = BETHANY_KEY
            beth.db.facility_role = "attendant"
            beth.db.physical_desc = (
                "Bethany, off the desk and out of patience — blouse still neat, slacks shoved "
                "down, a long heavy futa cock swinging hard and wet between her thighs and a "
                "clipboard in one hand. The smile is exactly as warm as it was at intake, and "
                "means exactly as little."
            )
            provision_bethany(beth)
            return beth
        except Exception:
            return None

    def _get_bethany(self):
        ref = self.db.bethany_ref
        if not ref:
            return None
        from evennia import search_object
        res = search_object(ref, exact=True)
        return res[0] if res else None

    def _orifice(self, char):
        """Return the zone holding the real inflation item, for cumflation."""
        zones = getattr(char.db, "zones", None) or {}
        for zn, zd in zones.items():
            if ((zd or {}).get("mechanics", {}) or {}).get("inflation"):
                return zn
        return None
