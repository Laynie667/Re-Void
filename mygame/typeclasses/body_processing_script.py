"""
typeclasses/body_processing_script.py

BodyProcessingScript — the contract's hooks installed in HER, not a room.

Once a facility contract is signed, this runs on the character and processes the
body on a schedule regardless of location: it milks her production zones (real
drain + bank), breeds her orifice zones (real do_inseminate deposit), and keeps
her aroused. It's the enforcement that follows her out of any room — the body
is the facility now.

Started by the binding effect 'body_processing' (apply_effects); stopped and
cleared by the facility reset.
"""

import random
from evennia import DefaultScript


class BodyProcessingScript(DefaultScript):
    """Contract-enforced processing of the body itself, anywhere."""

    def at_script_creation(self):
        self.key        = "body_processing"
        self.persistent = True
        self.interval   = 150
        self.repeats    = 0

    def at_repeat(self):
        char = self.obj
        if not char or not hasattr(char, "db"):
            self.stop(); return
        # Runs while the contract is in force (signed) or permanently locked in.
        if not (getattr(char.db, "facility_signed", False)
                or getattr(char.db, "body_processing_locked", False)):
            self.stop(); return

        room = char.location
        t = char.db.rp_name or char.name

        # Arousal never rests.
        try:
            from typeclasses.arousal_script import add_arousal, ensure_arousal_script
            ensure_arousal_script(char); add_arousal(char, 6.0)
        except Exception:
            pass

        action = random.random()

        # 1. Milk the production zones, wherever she is.
        if action < 0.5:
            self._milk(char, room, t)
        # 2. Breed an orifice zone (real deposit) on schedule.
        else:
            self._breed(char, room, t)

    def _milk(self, char, room, t):
        try:
            from evennia import search_object
            from typeclasses.production_item import ProductionItem
        except Exception:
            return
        total = 0.0; by_type = {}
        for zd in (getattr(char.db, "zones", None) or {}).values():
            entry = ((zd or {}).get("mechanics", {}) or {}).get("production")
            if not entry:
                continue
            res = search_object(entry.get("item_dbref", ""), exact=True)
            if not (res and isinstance(res[0], ProductionItem)):
                continue
            prod = res[0]
            avail = float(prod.db.current_volume_ml or 0)
            ext = min(random.uniform(25, 60), avail)
            if ext > 0:
                prod.db.current_volume_ml = max(0.0, avail - ext)
                try: prod.reset_fullness_notifications()
                except Exception: pass
                ft = prod.db.fluid_type or "milk"
                by_type[ft] = by_type.get(ft, 0.0) + ext; total += ext
        if total <= 0:
            return
        try:
            from typeclasses.fluid_bank import GlobalFluidBank
            bank = GlobalFluidBank.get()
            for ft, ml in by_type.items():
                bank.deposit(char, ml, ft, None)
        except Exception:
            pass
        msg = (f"|cThe contract's hooks in {t}'s glands draw down on schedule — {total:.0f}ml "
               f"milked out of her wherever she stands, ache and let-down arriving whether the "
               f"moment suits her or not, and banked against her number.|n")
        if room:
            room.msg_contents(msg)
        else:
            char.msg(msg)

    def _breed(self, char, room, t):
        # Find an orifice zone by name.
        orifices = [zn for zn in (getattr(char.db, "zones", None) or {})
                    if any(k in zn.lower() for k in ("pussy", "cunt", "vagina", "anus", "asshole"))]
        if not orifices:
            return
        zone = random.choice(orifices)
        try:
            from world.gang_breeding import gang_inseminate
            gang_inseminate(char, zone, contributors=random.randint(1, 3),
                            fluid_type="semen", species="contributor")
        except Exception:
            return
        disp = zone.split("/")[-1].replace("_", " ")
        msg = (f"|mThe breeding hook the contract set in {t} fires on its timer — her {disp} "
               f"filled where she stands, no station, no animal, no warning, just the schedule "
               f"reaching into her body and using it.|n")
        if room:
            room.msg_contents(msg)
        else:
            char.msg(msg)
