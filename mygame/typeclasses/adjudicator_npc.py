"""
typeclasses/adjudicator_npc.py

AdjudicatorNPC — test-session assistant that acts as a second player.

Responds to the test subject's say commands:
  status / flags / report   — current flag progress
  help / what / explain     — description of each test
  done / finished / ready   — checks all 13 flags; confirms when clear to reset
  run pet test              — runs all pet trigger words on the subject
  attach leash              — attaches its own leash to the subject (if available)
  vibrate [intensity]       — activates vibration on a subject's vibrating item

Also fires random ambient commentary as testing progresses.
"""

import random
from typeclasses.npc import NPC

_FLAG_LABELS = [
    ("test_flag_speech",    "Speech filter — say something (output transforms)."),
    ("test_flag_edge",      "Edge machine — reach arousal 99 then say: release"),
    ("test_flag_horse",     "Rocking horse — horsemount → horsestart → horsestop"),
    ("test_flag_womb",      "WombRoom — enter it, look at the flood, leave"),
    ("test_flag_chastity",  "Chastity — attempt penetrate while belted"),
    ("test_flag_collar",    "Degrading collar — wear it, force a tick, watch it beg"),
    ("test_flag_contract",  "Contract — sign it, reveal hidden clauses"),
    ("test_flag_cycle",     "Cycle machine — start, let a phase run, endcycle"),
    ("test_flag_body_mods", "Body mods — check zone descs for {size}/{vol} tokens"),
    ("test_flag_inflation", "Inflation — inflate a zone, check state, drain it"),
    ("test_flag_pet",       "Pet triggers — completed via 'run pet test'"),
    ("test_flag_arousal",   "Arousal cycle — through all four thresholds"),
    ("test_flag_womb_flood","WombRoom flood — enter while at knee-deep level"),
]

_AMBIENT_COMMENTS = [
    "|xThe Adjudicator makes a small mark in the ledger.|n",
    "|xThe Adjudicator looks up briefly, then returns to the notes.|n",
    "|xSomething is recorded. The Adjudicator says nothing about it.|n",
    "|xThe Adjudicator turns a page.|n",
    "|xThe ledger is updated. The Adjudicator continues watching.|n",
    "|xA brief nod from the Adjudicator — acknowledgement, nothing more.|n",
]

_PET_TRIGGER_SEQUENCE = [
    "stay", "sit", "beg", "paw", "roll", "speak", "free"
]


class AdjudicatorNPC(NPC):
    """Test-session assistant NPC. Acts as a second player for interactive tests."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.npc_tier     = 2
        self.db.react_to_say = True
        self.db.desc = (
            "A figure occupying one corner of the room with a small ledger "
            "and the patient attention of something that has been here before "
            "and intends to be here until the work is finished."
        )

    def on_hear_say(self, speaker, text: str):
        subject_id = self.db.adjudicator_caller_id
        if not subject_id or speaker.id != subject_id:
            return

        t    = text.strip().lower()
        room = self.location
        if not room:
            return

        if any(w in t for w in ("status", "flags", "report", "progress", "list")):
            self._report_status(speaker, room)

        elif any(w in t for w in ("help", "explain", "how", "what do")):
            self._give_help(room)

        elif any(w in t for w in ("done", "finished", "ready", "all done", "complete")):
            self._check_completion(speaker, room)

        elif "run pet test" in t or "pet test" in t:
            self._run_pet_triggers(speaker, room)

        elif "attach leash" in t:
            self._attach_leash(speaker, room)

        elif "vibrate" in t:
            intensity = "medium"
            for w in ("low", "medium", "high", "random", "intense"):
                if w in t:
                    intensity = w
                    break
            self._vibrate_subject(speaker, room, intensity)

        elif "drain" in t and "womb" in t:
            self._drain_womb(speaker, room)

        else:
            # Random ambient acknowledgement ~30% of the time
            if random.random() < 0.30:
                room.msg_contents(random.choice(_AMBIENT_COMMENTS))

    # ── Status report ──────────────────────────────────────────────────

    def _report_status(self, subject, room):
        flags = [(k, l, getattr(subject.db, k, False)) for k, l in _FLAG_LABELS]
        done  = [f for f in flags if f[2]]
        left  = [f for f in flags if not f[2]]

        lines = [
            f"|wThe Adjudicator opens the ledger.|n\n"
            f"|x{len(done)} of {len(flags)} verified.|n"
        ]
        for _, label, complete in flags:
            mark = "|g✓|n" if complete else "|y·|n"
            lines.append(f"  {mark} {label}")

        if not left:
            lines.append(
                "\n|gAll thirteen verified. Say: done  to confirm and clear for reset.|n"
            )
        else:
            lines.append(f"\n|x{len(left)} remaining.|n")

        room.msg_contents("\n".join(lines))

    # ── Help ───────────────────────────────────────────────────────────

    def _give_help(self, room):
        room.msg_contents(
            "|wThe Adjudicator turns the ledger so you can read it.|n\n\n"
            "  |w 1|n  Say anything. Watch the filter transform it.\n"
            "  |w 2|n  Sit in the room zone. Edge machine pushes to 99. Say: release\n"
            "  |w 3|n  horsemount → horsestart → let it tick → horsestop → horsedismount\n"
            "  |w 4|n  enter yourself (WombRoom) → look → leave\n"
            "  |w 5|n  While chastity belt on, try: penetrate me [zone]\n"
            "  |w 6|n  wear Worn Leather Collar → force tick → watch the beg fire\n"
            "  |w 7|n  contract/sign Milking Contract → contract/reveal/all\n"
            "  |w 8|n  Start cycle script on yourself → let one phase run → endcycle\n"
            "  |w 9|n  zone set [zone] = {size} breast holding {vol} → look at yourself\n"
            "  |w10|n  inflate me [zone] 200 → inflate/check → inflate/drain\n"
            "  |w11|n  Say: run pet test — Adjudicator runs triggers for you\n"
            "  |w12|n  Ride arousal through 75/90/95/99 threshold messages\n"
            "  |w13|n  Enter WombRoom while knee-deep — look at the flood desc\n\n"
            "  Manual flag set: @py me.db.test_flag_NAME = True\n"
            "  Current flags:   say status\n"
            "  Reset check:     say done\n"
        )

    # ── Completion check ───────────────────────────────────────────────

    def _check_completion(self, subject, room):
        flags   = [(k, l) for k, l in _FLAG_LABELS]
        missing = [(k, l) for k, l in flags if not getattr(subject.db, k, False)]

        if missing:
            lines = [
                f"|xThe Adjudicator shakes their head once. "
                f"{len(missing)} item(s) still unverified:|n"
            ]
            for _, label in missing:
                lines.append(f"  |y→|n {label}")
            lines.append("|xComplete those and say done again.|n")
            room.msg_contents("\n".join(lines))
        else:
            room.msg_contents(
                "|wThe Adjudicator closes the ledger.|n\n\n"
                "|xAll thirteen systems verified and recorded. "
                "The build is confirmed functional.\n\n"
                "You are clear to run the reset.|n\n\n"
                "|wReset command:|n\n"
                "  @py exec(open('/home/laynie/ReVoid/mygame/world/test_reset.py').read()); "
                "run_test_reset(me)"
            )
            subject.db.test_flag_complete = True

    # ── Pet trigger runner ─────────────────────────────────────────────

    def _run_pet_triggers(self, subject, room):
        """Fire each pet trigger word on the subject with a short delay between."""
        from evennia.utils import delay
        from world.binding_effects import check_trigger

        subject_name = subject.db.rp_name or subject.name
        room.msg_contents(
            f"|xThe Adjudicator sets down the ledger. "
            f"\"Pet trigger sequence,\" they say. \"Pay attention.\"|n"
        )

        def _fire(index):
            if index >= len(_PET_TRIGGER_SEQUENCE):
                subject.db.test_flag_pet = True
                room.msg_contents(
                    "|xThe Adjudicator retrieves the ledger. "
                    "\"Pet trigger calibration: verified.\"|n"
                )
                return
            word = _PET_TRIGGER_SEQUENCE[index]
            check_trigger(self, word, room, target=subject)
            delay(2, lambda: _fire(index + 1))

        delay(1, lambda: _fire(0))

    # ── Leash attachment ───────────────────────────────────────────────

    def _attach_leash(self, subject, room):
        """Attach a leash from the Adjudicator to the subject for lead testing."""
        from typeclasses.collar_item import LeashItem, CollarItem
        from evennia.utils import create

        # Check subject has a collar
        has_collar = any(
            isinstance(obj, CollarItem) and obj.db.is_worn
            for obj in subject.contents
        )
        if not has_collar:
            room.msg_contents(
                "|xThe Adjudicator looks at the subject. \"No collar,\" they note. "
                "\"Wear one first.\"|n"
            )
            return

        # Create and attach a leash
        leash = create.create_object(
            LeashItem, key="Adjudicator's Leash", location=self
        )
        leash.db.desc = "A plain leash held by the Adjudicator."
        ok_r, reason = leash.attach(self, subject)
        if ok_r:
            room.msg_contents(
                "|xThe Adjudicator attaches a leash to the subject's collar "
                "with the efficiency of someone doing it for the fourth time today.|n"
            )
        else:
            room.msg_contents(f"|xLeash attach failed: {reason}|n")
            leash.delete()

    # ── Vibrate subject ────────────────────────────────────────────────

    def _vibrate_subject(self, subject, room, intensity):
        """Remotely trigger vibration on subject's vibrating item."""
        from typeclasses.vibration_item import VibratingPlugItem, RemoteControlItem

        vib = next(
            (obj for obj in subject.contents
             if isinstance(obj, VibratingPlugItem) and obj.db.is_inserted),
            None
        )
        if not vib:
            room.msg_contents(
                "|xThe Adjudicator checks the device. \"No active vibrating item.\"|n"
            )
            return

        vib.set_vibe(intensity)
        subject.msg(f"|xThe vibration starts — {intensity}.|n")
        room.msg_contents(
            f"|xThe Adjudicator adjusts a small control. The device activates.|n",
            exclude=[subject],
        )

    # ── Drain WombRoom ─────────────────────────────────────────────────

    def _drain_womb(self, subject, room):
        from typeclasses.womb_room import WombRoom
        zones = getattr(subject.db, "zones", None) or {}
        for zone_data in zones.values():
            mech = (zone_data or {}).get("mechanics") or {}
            wr   = mech.get("womb_room")
            if wr:
                from evennia import search_object
                results = search_object(wr.get("room_dbref", ""), exact=True)
                if results and isinstance(results[0], WombRoom):
                    results[0].db.womb_fluid_ml = 0.0
                    room.msg_contents("|xThe Adjudicator drains the WombRoom.|n")
                    return
        room.msg_contents("|xNo WombRoom found to drain.|n")
