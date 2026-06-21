"""
typeclasses/arousal_script.py

ArousalScript — passive arousal decay attached to a character.

Arousal (0–100 float) builds from:
  - Milking session ticks
  - suck / handmilk commands
  - penetrate / thrust commands
  - Any command that calls character.add_arousal(amount)

Decay fires every 5 minutes if no arousal-gaining activity in that window.

At 100, the climax event fires automatically:
  - Extracts from all installed ProductionItems whose mod_type is genital
    ('semen', 'urine', etc.) and deposits to the GlobalFluidBank
  - Fires messages from world/milking_messages.yaml (arousal: section)
  - Resets arousal to 0
  - Applies post-climax cooldown (reduced gain for configurable period)

Install on a character with:
    script = create.create_script(ArousalScript, obj=char, persistent=True)
"""

import time
from evennia import DefaultScript


# Arousal thresholds that trigger private messages
AROUSAL_THRESHOLDS = [75.0, 90.0, 95.0]

# Post-climax window (seconds) during which arousal gain is halved
COOLDOWN_SECONDS = 600  # 10 minutes


class ArousalScript(DefaultScript):
    """Passive arousal decay and climax event handler."""

    def at_script_creation(self):
        self.key        = "arousal_decay"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 300   # 5 minutes

    # ------------------------------------------------------------------
    # Per-tick decay
    # ------------------------------------------------------------------

    def at_repeat(self):
        char = self.obj
        if not char or not hasattr(char, "db"):
            self.stop()
            return

        arousal = char.db.arousal or 0.0
        if arousal <= 0.0:
            return

        # Only decay if no arousal activity in the last interval
        last  = char.db.last_arousal_activity or 0.0
        now   = time.time()
        if now - last < self.interval:
            return

        # Arousal floor — don't decay below minimum
        floor = float(char.db.arousal_floor or 0.0)

        # Decay 3 points per tick while inactive
        new_arousal = max(floor, arousal - 3.0)
        char.db.arousal = new_arousal


# ------------------------------------------------------------------
# Module-level helpers — called by commands and session scripts
# ------------------------------------------------------------------

def add_arousal(char, amount: float):
    """
    Add arousal to a character, applying cooldown penalty if applicable.
    Checks thresholds and fires climax at 100.

    Args:
        char:   The character object.
        amount: Raw arousal amount to add.

    Returns:
        float: New arousal value.
    """
    if not hasattr(char, "db"):
        return 0.0

    # Cooldown halves gain for COOLDOWN_SECONDS after climax
    cooldown_until = char.db.arousal_cooldown_until or 0.0
    now = time.time()
    if now < cooldown_until:
        amount *= 0.5

    old_arousal = char.db.arousal or 0.0

    # Orgasm denial — the cap and the climax gate both come from the one resolver, so a
    # granted release reaches 100 and a denied one stays held at 99 (see world.arousal_rules).
    try:
        from world.arousal_rules import cap_for, may_climax, consume_release
        cap = cap_for(char)
    except Exception:
        # Fallback to the inline rule if the resolver can't load.
        denial_active = getattr(char.db, "orgasm_denial", False)
        denial_lifted = getattr(char.db, "orgasm_denial_lifted", False)
        cap = 100.0 if (not denial_active or denial_lifted) else 99.0
        may_climax = lambda c: (not denial_active or denial_lifted)
        consume_release = lambda c: setattr(c.db, "orgasm_denial_lifted", False)

    new_arousal = min(cap, old_arousal + amount)
    char.db.arousal = new_arousal
    char.db.last_arousal_activity = now

    # Threshold messages (private)
    _check_arousal_thresholds(char, old_arousal, new_arousal)

    # Climax — only if a release is permitted right now (one-shot lift is consumed here).
    if new_arousal >= 100.0 and may_climax(char):
        consume_release(char)
        _trigger_climax(char)

    return new_arousal


def _check_arousal_thresholds(char, old_val: float, new_val: float):
    """Fire private threshold messages when arousal crosses key values."""
    try:
        from world.milking_loader import pick_arousal_threshold_message
    except ImportError:
        return

    import random
    for threshold in AROUSAL_THRESHOLDS:
        if old_val < threshold <= new_val:
            msg = pick_arousal_threshold_message(threshold)
            if msg:
                char.msg(f"|x{msg}|n")


def _trigger_climax(char):
    """
    Fire the climax event:
      - Extract all genital-type production items → GlobalFluidBank
      - Broadcast climax message to room
      - Reset arousal and apply cooldown
    """
    import random

    # Extract from genital production items
    try:
        from typeclasses.production_item import ProductionItem
        from typeclasses.fluid_bank import GlobalFluidBank

        bank = GlobalFluidBank.get()
        for item in list(char.contents):
            if not isinstance(item, ProductionItem):
                continue
            if not item.db.is_installed:
                continue
            # Genital production: semen, urine (not milk)
            ft = item.db.fluid_type or ""
            if ft not in ("semen", "urine"):
                continue

            vol = item.db.current_volume_ml or 0.0
            if vol > 0:
                item.db.current_volume_ml = 0.0
                item.reset_fullness_notifications()
                bank.deposit(char, vol, ft, item.db.fluid_flavor)
    except Exception:
        pass

    # Broadcast climax message to room
    try:
        from world.milking_loader import pick_climax_message
        char_name = char.db.rp_name or char.name
        room = char.location
        if room:
            msg = pick_climax_message()
            if msg:
                room.msg_contents(
                    msg.replace("{target}", char_name)
                )
    except Exception:
        pass

    # Reset and cooldown
    char.db.arousal = 0.0
    char.db.arousal_cooldown_until = time.time() + COOLDOWN_SECONDS


def ensure_arousal_script(char):
    """
    Ensure the character has an ArousalScript installed.
    Called at character creation and at login.
    """
    from evennia.utils import create
    existing = [s for s in char.scripts.all()
                if s.key == "arousal_decay"]
    if not existing:
        create.create_script(ArousalScript, obj=char, persistent=True)


# Named arousal curve (character-emotes.md §5): build → edge → peak → afterglow.
AROUSAL_TIERS = ("build", "edge", "peak", "afterglow")


def get_arousal_tier(char):
    """Map the 0–100 arousal value to the named curve, read-only (the meter is
    unchanged). For the act framework / heat prose to select tone by tier:
      * afterglow — within the post-climax cooldown window (refractory),
      * peak      — at/near the top WITH release available,
      * edge      — high but held (denied climax), or simply past the first threshold,
      * build     — still rising.
    Fail-safe: any error → 'build'."""
    try:
        now = time.time()
        if now < float(getattr(char.db, "arousal_cooldown_until", 0) or 0):
            return "afterglow"
        a = float(getattr(char.db, "arousal", 0) or 0)
        # Is climax currently denied/capped? Then a high value is the EDGE (held on
        # the brink), not the peak.
        try:
            from world.arousal_rules import cap_for
            denied = cap_for(char) < 100.0
        except Exception:
            denied = (bool(getattr(char.db, "orgasm_denial", False))
                      and not getattr(char.db, "orgasm_denial_lifted", False))
        if a >= AROUSAL_THRESHOLDS[2]:        # >= 95
            return "edge" if denied else "peak"
        if a >= AROUSAL_THRESHOLDS[0]:        # >= 75
            return "edge"
        return "build"
    except Exception:
        return "build"

