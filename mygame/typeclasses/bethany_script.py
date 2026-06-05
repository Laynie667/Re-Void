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
    # An all-powerful, consuming facility-bred futa cock — monstrous, impossible,
    # built not to breed her but to overwrite her. (mod_type 'penis' for mechanical
    # compatibility; everything else is its own thing.)
    try:
        cock = create.create_object(BodyModItem, key="Bethany's cock", location=npc)
        cock.db.mod_type = "penis"
        cock.db.size = 32.0     # monumental — past anything the body should take
        cock.db.player_desc = (
            "a monstrous, all-consuming futa cock — far past anything the line keeps, "
            "longer than a forearm and thicker than a wrist, dark with blood and slick "
            "to the root, the flared head the size of a fist and weeping clear strings "
            "before she's even touched anyone. A heavy knot the size of an apple swells "
            "at the base. It does not look like it should fit anywhere on a person. That "
            "is the point: it is made to fit anyway, to take whatever it's put in and "
            "leave it permanently reshaped around the memory of it. Just the sight of it "
            "scrambles something — the eye keeps sliding back, the mouth keeps wanting"
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
    # Real cum production — an obscene standing load she dumps until the belly swells.
    try:
        cum = create.create_object(ProductionItem, key="Bethany's balls", location=npc)
        cum.db.fluid_type = "semen"
        cum.db.fluid_flavor = ("thick, hot, scalding facility seed — heavy as cream and "
                               "wrong somehow, leaving the head swimming and the mouth craving more")
        cum.db.base_rate_ml_per_tick = 80.0
        cum.db.current_volume_ml = random.uniform(2500.0, 4500.0)
        if hasattr(cum, "install"):
            cum.install(npc, "shaft")
    except Exception:
        pass
    # And a heavy bladder, for when she's feeling especially fond.
    try:
        piss = create.create_object(ProductionItem, key="Bethany's bladder", location=npc)
        piss.db.fluid_type = "urine"
        piss.db.base_rate_ml_per_tick = 15.0
        piss.db.current_volume_ml = random.uniform(700.0, 1400.0)
        if hasattr(piss, "install"):
            piss.install(npc, "shaft")
    except Exception:
        pass
    npc.db.facility_anatomy = True


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
        self.db.target = random.randint(2, 3)
        self.db.bethany_ref = beth.dbref
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
        # She may decide to own her, right as she finishes.
        if random.random() < 0.35 and not getattr(char.db, "bethany_owned", False):
            room.msg_contents("|m" + random.choice(_BUY).format(t=t) + "|n")
            self._mark_owned(char)
        room.msg_contents("|r" + random.choice(_CLIMAX).format(t=t) + "|n")
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
        beth = self._get_bethany()
        if beth:
            room = char.location
            if room and climaxed:
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
