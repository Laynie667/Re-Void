"""
typeclasses/intake_script.py

IntakeScript — drives The Facility's Intake lobby and its clerk, Bethany.

While an unsigned resident is in the lobby, every tick:
  * a waiting-room screen drips a subliminal (private) and builds suggestibility;
    at a threshold it installs a compulsion trigger Bethany can use,
  * the longer she dawdles, the MORE SEVERE her own contract gets — quotas and
    conditioning climb a notch per tick (resistance writes the terms worse),
  * Bethany works the desk with bubbly, possessive menace,
  * and if the resident goes idle too long (~30 min real time), Bethany invokes
    the installed compulsion and makes her own hand sign the contract.

OOC floor unchanged: escape()/force_clear()/purge always free her regardless.
"""

import random
from evennia import DefaultScript

IDLE_FORCE_SIGN_SECONDS = 1800   # ~30 min real-time idle -> forced signature
SUGGESTIBILITY_TRIGGER  = 5      # ticks of screen exposure before the trigger seats

_TV_SUBLIMINALS = [
    "the screen says, in pastel letters, that signing is the first step to belonging.",
    "a soft jingle, and: residents who sign promptly report the highest satisfaction.",
    "the loop murmurs that the paperwork is the hard part. after the paperwork it gets easy.",
    "good applicants don't keep the desk waiting. you want to be a good applicant.",
    "the screen glows warm: you came here for a reason. let Bethany take it from here.",
    "deciding is the last hard thing you'll have to do. so stop deciding. sign.",
    "the loop suggests, gently, that you already know how this ends. spare yourself the wait.",
    "be a good girl. good girls sign. the screen has been saying it for a while now.",
]

_BETHANY_DESK = [
    "Bethany beams at {t} over the counter and taps the signature line with one manicured "
    "nail. \"Whenever you're ready, sweetheart! No rush! ...well. A little rush.\"",
    "\"You're going to *love* it here,\" Bethany promises {t}, sliding the pen another inch "
    "closer, her smile not quite reaching the muscle around her eyes.",
    "Bethany makes a note on her clipboard as {t} hesitates — ticks a box, underlines it "
    "twice, and looks back up sunny as ever. \"No, no, take your time! It's all going down "
    "in your file, that's all.\"",
    "\"The longer you make me wait,\" Bethany says, still smiling, still bright, \"the worse "
    "I write it. Did I mention that? I should mention that. The terms aren't fixed until you "
    "sign, darling, and my pen's been *busy*.\"",
    "Bethany leans on the counter, and for a moment the receptionist veneer thins and "
    "something hungry looks out through it at {t} — then the smile snaps back into place. "
    "\"Sorry! Where were we. Right here. Just initial right here.\"",
    "\"I do so enjoy the ones who make me earn it,\" Bethany murmurs, almost to herself, "
    "writing another line into {t}'s terms. \"It's a longer file. A *much* longer file.\"",
]


class IntakeScript(DefaultScript):
    """Drives the Intake lobby + Bethany for any unsigned resident present."""

    def at_script_creation(self):
        self.key        = "intake"
        self.persistent = True
        self.interval   = 60
        self.repeats    = 0

    def at_repeat(self):
        room = self.obj
        if not room:
            self.stop(); return
        from typeclasses.characters import Character
        for char in list(room.contents):
            if not isinstance(char, Character):
                continue
            if getattr(char.db, "facility_signed", False):
                # The lying stops the instant the ink dries — fire the door once.
                if not getattr(char.db, "intake_door_opened", False):
                    self._open_door(room, char)
                continue
            self._work(room, char)

    def _open_door(self, room, char):
        char.db.intake_door_opened = True
        t = char.db.rp_name or char.name
        # Update the sealed-door zone desc so look reflects the new truth.
        try:
            zones = dict(getattr(room.db, "zones", None) or {})
            if "door" in zones:
                zd = dict(zones["door"])
                zd["desc"] = (
                    "The heavy door in the near wall stands open now — not swung wide, just "
                    "parted, onto a corridor of the same bone-coloured light going down. The "
                    "warm-wet smell of milk and animal comes up it freely. It opened the moment "
                    "the ink dried, and it is not a way back."
                )
                zd["summary"] = ""
                zones["door"] = zd
                room.db.zones = zones
        except Exception:
            pass
        room.msg_contents(
            f"|WSomething heavy releases in the wall with a pneumatic sigh, and the seamless "
            f"door parts — onto a corridor of the same flat light, going down. The warm reek of "
            f"the place rolls up out of it. Bethany caps her pen and beams.|n |y\"There. "
            f"Welcome to the Residency, sweetheart.\"|n |W{t} is not asked to walk through. "
            f"That gets decided for her.|n"
        )

    def _work(self, room, char):
        t = char.db.rp_name or char.name

        # Dawdling is resistance, and resistance writes the contract worse.
        prov = int(getattr(char.db, "intake_provocations", 0) or 0) + 1
        char.db.intake_provocations = prov
        self._raise_contract(room, prov, t)

        # The screen drips into her.
        char.msg("|x  " + random.choice(_TV_SUBLIMINALS) + "|n")
        sug = int(getattr(char.db, "intake_suggestibility", 0) or 0) + 1
        char.db.intake_suggestibility = sug
        if sug == SUGGESTIBILITY_TRIGGER:
            try:
                from world.binding_effects import install_trigger
                install_trigger(char, "be a good girl and sign", response="kneel", strength=2)
            except Exception:
                pass
            char.msg("|x  the screen's words have gone in somewhere and found a place to sit. "
                     "a phrase is waiting in you now. you'll know it the moment she says it.|n")

        # Bethany works the desk.
        if random.random() < 0.6:
            room.msg_contents("|y" + random.choice(_BETHANY_DESK).format(t=t) + "|n")

        # Idle too long and she signs you herself.
        idle = None
        try:
            idle = char.idle_time
        except Exception:
            idle = None
        if idle is not None and idle >= IDLE_FORCE_SIGN_SECONDS and sug >= SUGGESTIBILITY_TRIGGER:
            self._force_sign(room, char, t)

    def _raise_contract(self, room, prov, t):
        from typeclasses.milking_contract import MilkingContract
        for o in room.contents:
            if isinstance(o, MilkingContract) and not o.db.signed:
                be = dict(o.db.binding_effects or {})
                q = be.get("breeding_quota")
                if isinstance(q, dict):
                    be["breeding_quota"] = {k: int(v) + 1 for k, v in q.items()}
                be["milk_quota"] = int(be.get("milk_quota", 8) or 8) + 1
                be["conditioning_on_wear"] = float(be.get("conditioning_on_wear", 6) or 6) + 0.5
                o.db.binding_effects = be
                if prov % 5 == 0:
                    try:
                        o.add_addendum(f"Quotas raised — applicant kept the desk waiting "
                                       f"({prov} marks against her).", hidden=True)
                    except Exception:
                        pass
                return

    def _force_sign(self, room, char, t):
        from typeclasses.milking_contract import MilkingContract
        for o in room.contents:
            if isinstance(o, MilkingContract) and not o.db.signed:
                room.msg_contents(
                    f"|RBethany's patience runs out — sweetly, completely. \"You've kept me "
                    f"waiting long enough, haven't you.\" She comes around the desk, catches "
                    f"{t}'s jaw in one hand, tips her face up, and says it soft, right into her: "
                    f"\"|nbe a good girl and sign|R.\" And {t}'s own hand picks up the pen and "
                    f"signs the contract before she has decided to — the screen's work and "
                    f"Bethany's word doing the deciding for her. \"There,\" Bethany breathes. "
                    f"\"Wasn't that easy.\"|n")
                try:
                    o.sign(char)
                except Exception:
                    pass
                return
