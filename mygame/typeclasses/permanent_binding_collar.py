"""
typeclasses/permanent_binding_collar.py

PermanentBindingCollar — a collar that never breaks but maintains a permanent
                         humiliation state and fires periodic forced emotes.

Unlike DegradingCollar, this one does not advance toward "broken". Instead it
locks at a chosen permanent_state (pristine/worn/frayed/cracked) and holds
there indefinitely. All compounding effects of that state remain active.

A soul_bound variant (PermanentSoulBindingCollar) applies effects to all
characters on the same account.

Additional effect: periodic_humiliation
  - On a configurable timer, fires a forced emote (pose or say) from the
    wearer drawn from the collar_variant pool.
  - Configurable interval (seconds); default 30 minutes.

DB attributes:
    collar_variant      str    — selects beg/behavior pool
    permanent_state     str    — state locked at (default "cracked")
    beg_interval        float  — seconds between forced emotes (default 1800)
    last_humil_at       float  — timestamp of last forced emote
    soul_bound          bool   — if True, effects apply account-wide
"""

import time
from typeclasses.degrading_collar import DegradingCollar, _STIM_SCALE, _FLOOR_SCALE


class PermanentBindingCollar(DegradingCollar):
    """
    A collar that never breaks.  Effects are permanent.
    Fires periodic forced emotes from the wearer on a timer.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key               = "binding collar"
        self.db.desc           = "A collar with no visible wear — or rather, wear that has become its permanent state."
        self.db.lifespan_hours = None          # never expires
        self.db.permanent_state = "cracked"   # state locked at
        self.db.beg_interval   = 1800.0       # 30 min between forced emotes
        self.db.last_humil_at  = 0.0
        self.db.soul_bound     = False

        # Default binding effects for permanent collar
        self.db.binding_effects = {
            "lock_self_remove":     True,
            "continuous_stimulation": 2.2,
            "arousal_floor":        20.0,
            "auto_consent":         True,
        }

    def wear(self, character, zone_name: str = None) -> tuple:
        ok, reason = super().wear(character, zone_name)
        if not ok:
            return ok, reason

        # Immediately advance to the permanent state
        state = self.db.permanent_state or "cracked"
        if state != "pristine":
            self._lock_to_state(character, state)

        # Soul-bound: apply to account
        if self.db.soul_bound:
            try:
                from world.soul_bound import apply_soul_bound_effects
                apply_soul_bound_effects(character.account, self)
            except Exception:
                pass

        character.msg(
            f"|xThe collar settles around your throat. "
            f"It is not going anywhere and neither are its effects.|n"
        )
        return True, ""

    def _lock_to_state(self, char, state: str):
        """Set all effects to the chosen permanent state without broadcasting."""
        stim_scale  = _STIM_SCALE.get(state, 1.0)
        floor_scale = _FLOOR_SCALE.get(state, 1.0)
        base_stim   = float(self.db.base_stim  or 1.0)
        base_floor  = float(self.db.base_floor or 10.0)

        effects = dict(self.db.binding_effects or {})
        effects["continuous_stimulation"] = base_stim * stim_scale
        effects["arousal_floor"]          = base_floor * floor_scale
        self.db.binding_effects = effects
        self.db.state           = state

        char.db.stim_per_tick = float(char.db.stim_per_tick or 0.0) + effects["continuous_stimulation"]
        char.db.arousal_floor = max(float(char.db.arousal_floor or 0.0), effects["arousal_floor"])

    # Override tick — never advance state, only fire periodic humiliation
    def tick(self):
        if not self.db.is_worn or not self.db.created_at:
            return

        char = self.db.worn_on_char
        if not char:
            return

        interval = float(self.db.beg_interval or 1800.0)
        if time.time() - float(self.db.last_humil_at or 0.0) < interval:
            return

        self.db.last_humil_at = time.time()
        self._fire_periodic_humiliation(char)

    def _fire_periodic_humiliation(self, char):
        """Fire a forced emote from the wearer on the humiliation timer."""
        self._fire_beg(char)   # reuses DegradingCollar's beg method


class PermanentSoulBindingCollar(PermanentBindingCollar):
    """
    A permanent binding collar that applies effects to all characters on
    the account, not just the one wearing it.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key           = "soul-binding collar"
        self.db.desc       = "A collar that glows cold at the edges. Its effects follow you everywhere."
        self.db.soul_bound = True
        self.db.binding_effects = {
            "lock_self_remove":       True,
            "soul_bound":             True,
            "auto_consent":           True,
            "continuous_stimulation": 2.2,
            "arousal_floor":          20.0,
            "lock_navigation":        True,
            "orgasm_denial":          True,
        }
