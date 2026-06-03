"""
typeclasses/degrading_collar.py

DegradingCollar — a collar that visibly falls apart over real time.

States:  pristine → worn → frayed → cracked → broken

At each state transition:
  - The collar's worn_desc updates to a more pathetic version
  - A room-visible message fires describing the change
  - Binding effects compound (arousal_floor and continuous_stimulation
    both scale upward as the collar degrades)
  - At 'cracked', periodic forced begging emotes fire to the room
  - At 'broken', the collar snaps, releases the wearer, and leaves a
    temporary "broken collar mark" freeform item on their neck zone

DB attributes:
    state           str     — current state name
    lifespan_hours  float   — total lifespan (default 48h)
    created_at      float   — unix timestamp of when it was put on
    last_beg_at     float   — timestamp of last forced beg (cracked stage)
    base_stim       float   — starting continuous_stimulation value
    base_floor      float   — starting arousal_floor value
"""

import time
from typeclasses.collar_item import CollarItem


_STATES = ["pristine", "worn", "frayed", "cracked", "broken"]

# State thresholds as fraction of lifespan
_STATE_THRESHOLDS = {
    "worn":    0.25,
    "frayed":  0.50,
    "cracked": 0.75,
    "broken":  1.00,
}

# Per-state arousal multipliers (stacked onto base values)
_STIM_SCALE  = {"pristine": 1.0, "worn": 1.3, "frayed": 1.7, "cracked": 2.2}
_FLOOR_SCALE = {"pristine": 1.0, "worn": 1.2, "frayed": 1.5, "cracked": 2.0}

# Room-visible transition messages
_TRANSITION_MSGS = {
    "worn": (
        "The collar at {name}'s throat is starting to show wear — the leather "
        "creasing soft where it sits, like it's been gripped and pulled at."
    ),
    "frayed": (
        "The collar at {name}'s throat is fraying, edges coming apart thread by "
        "thread — and everyone can see it, and {name} can feel everyone seeing it. "
        "Their breathing's already gone uneven."
    ),
    "cracked": (
        "The collar at {name}'s throat has cracked — sitting crooked, barely "
        "holding, and the way {name} keeps touching it, squirming, flushed, "
        "tells the whole room exactly how hard it's working on them."
    ),
    "broken": (
        "The collar at {name}'s throat gives out all at once — falling away in "
        "pieces, its work done. Whatever it wound up tight inside {name} while it "
        "lasted has nowhere left to go now, and every flushed, wrecked inch of "
        "them shows it."
    ),
}

# Forced beg messages (fires at cracked stage every ~20 min)
_BEG_MSGS = [
    "{name}'s hands fly to the cracking collar, voice cracking right along with "
    "it: \"Please — please fix it, I'll be so good, I'll do anything, just "
    "don't let it come off me, please—\"",
    "The collar digs in and the words spill out of {name} before they can "
    "swallow them: \"I need it. I need it on me. Fix it, replace it, please, I "
    "can't — I can't be without it—\"",
    "{name} sinks down, thighs pressed tight together, the begging shaking loose "
    "with every breath: \"Please. Please. I can feel it slipping and it's — "
    "please, I'm begging, just put it back—\"",
    "It claws at {name} from the inside out and the plea comes out raw: \"Fix "
    "it, I'll earn it, I'll be good, I'll be so good, please don't make me feel "
    "it come off—\"",
    "{name} can't hold still, can't hold quiet, the need rolling up hot through "
    "every word: \"Replace it. Please. I'll do anything you want, anything, just "
    "keep it locked on me—\"",
    "Past shame now, {name} is reaching, pleading, pupils blown: \"It's almost "
    "gone, it's almost gone, please, I'll crawl, I'll beg, just fix it, please—\"",
    "{name}'s voice drops to something wrecked and wanting: \"I don't care how "
    "it looks. I'll get on my knees right here. Just put it back on me — and "
    "don't you dare take it off again.\"",
]


class DegradingCollar(CollarItem):
    """
    A collar that visibly degrades over real time and releases when it breaks.

    The wearer cannot remove it (lock_self_remove is always True).
    Effects compound as it wears down.
    When it breaks it leaves a mark and deletes itself.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.key              = "degrading collar"
        self.db.desc          = "A collar that won't last. You can tell just looking at it."
        self.db.worn_desc     = "A collar sits around the throat — pristine for now."
        self.db.state          = "pristine"
        self.db.lifespan_hours = 48.0
        self.db.created_at     = None
        self.db.last_beg_at    = 0.0
        self.db.base_stim      = 1.0    # continuous_stimulation per tick at pristine
        self.db.base_floor     = 10.0   # arousal_floor at pristine
        self.db.collar_variant = "leather_puppy"  # selects beg pool variant

        # Always self-remove locked
        self.db.binding_effects = {
            "lock_self_remove": True,
            "continuous_stimulation": 1.0,
            "arousal_floor": 10.0,
        }

    def wear(self, character, zone_name: str = None) -> tuple:
        ok, reason = super().wear(character, zone_name)
        if not ok:
            return ok, reason
        self.db.created_at  = time.time()
        self.db.state       = "pristine"
        self.db.last_beg_at = 0.0
        character.msg(
            "|xA collar settles around your throat. It looks fine — for now.|n"
        )
        return True, ""

    def get_display_name(self, looker=None, **kwargs):
        state = self.db.state or "pristine"
        suffix = f" [{state}]" if self.db.is_worn else ""
        return f"{self.key}{suffix}"

    # ------------------------------------------------------------------
    # State machine — called by passive tick
    # ------------------------------------------------------------------

    def tick(self):
        """
        Called every 15 minutes by PassiveAccumulationScript.
        Checks for state transitions and forced emotes.
        """
        if not self.db.is_worn or not self.db.created_at:
            return

        char = self.db.worn_on_char
        if not char:
            return

        lifespan = float(self.db.lifespan_hours or 48.0) * 3600
        elapsed  = time.time() - float(self.db.created_at)
        frac     = elapsed / lifespan if lifespan > 0 else 1.0

        current_state = self.db.state or "pristine"

        # Check for state advance
        new_state = current_state
        for state, threshold in sorted(_STATE_THRESHOLDS.items(),
                                        key=lambda x: x[1]):
            if frac >= threshold and _STATES.index(state) > _STATES.index(current_state):
                new_state = state
                break

        if new_state != current_state:
            self._advance_state(char, current_state, new_state)

        # Forced beg at cracked stage (every 20 min)
        if self.db.state == "cracked":
            last_beg = float(self.db.last_beg_at or 0.0)
            if time.time() - last_beg > 1200:
                self._fire_beg(char)
                self.db.last_beg_at = time.time()

    def _advance_state(self, char, old_state: str, new_state: str):
        """Handle a state transition."""
        import random
        self.db.state = new_state
        cname = char.db.rp_name or char.name

        # Fire transition message to room
        msg_template = _TRANSITION_MSGS.get(new_state, "")
        if msg_template and char.location:
            char.location.msg_contents(
                f"|x{msg_template.format(name=cname)}|n"
            )

        if new_state == "broken":
            self._break(char, cname)
            return

        # Scale up compounding effects
        stim_scale  = _STIM_SCALE.get(new_state, 1.0)
        floor_scale = _FLOOR_SCALE.get(new_state, 1.0)
        base_stim   = float(self.db.base_stim  or 1.0)
        base_floor  = float(self.db.base_floor or 10.0)

        new_stim  = base_stim  * stim_scale
        new_floor = base_floor * floor_scale

        # Update binding_effects and the character's live values
        effects = dict(self.db.binding_effects or {})
        old_stim  = effects.get("continuous_stimulation", 0.0) or 0.0
        old_floor = effects.get("arousal_floor", 0.0) or 0.0

        effects["continuous_stimulation"] = new_stim
        effects["arousal_floor"]          = new_floor
        self.db.binding_effects = effects

        # Patch the character's live stim and floor
        char.db.stim_per_tick = max(
            float(char.db.stim_per_tick or 0.0) - old_stim + new_stim,
            0.0
        )
        char.db.arousal_floor = max(
            float(char.db.arousal_floor or 0.0),
            new_floor
        )

        # Update worn desc
        _STATE_DESCS = {
            "worn":    "A collar sits at the throat — it's been worn, the surface creased and soft in the wrong places.",
            "frayed":  "A fraying collar clings to the throat — edges coming apart, material thinning.",
            "cracked": "A cracked collar sits crooked at the throat. It won't hold together much longer.",
        }
        self.db.worn_desc = _STATE_DESCS.get(new_state, self.db.worn_desc)

    def _fire_beg(self, char):
        """Fire a forced begging message — as the character, in their voice."""
        import random
        from world.forced_emote import forced_emote
        from world.variant_loader import pick_collar_beg

        holder = self._get_holder(char)
        holder_name = (holder.db.rp_name or holder.name) if holder else "them"
        collar_variant = getattr(self.db, "collar_variant", "leather_puppy")

        # Alternate say and pose
        use_say = random.random() < 0.5
        msg_type = "say" if use_say else "pose"
        msg = pick_collar_beg(collar_variant, msg_type)

        if not msg:
            msg = _BEG_MSGS[random.randint(0, len(_BEG_MSGS)-1)].format(name=char.db.rp_name or char.name)
            forced_emote(char, msg, "pose")
            return

        msg = msg.replace("{holder}", holder_name).replace("{name}", char.db.rp_name or char.name)
        emote_type = "say" if use_say else "pose"
        forced_emote(char, msg, emote_type)

    def _get_holder(self, char):
        """Return the character currently leading this character, if any."""
        led_by_id = getattr(char.db, "led_by", None)
        if not led_by_id:
            return None
        try:
            from evennia import search_object
            results = search_object(f"#{led_by_id}", exact=True)
            return results[0] if results else None
        except Exception:
            return None

    def _break(self, char, cname: str):
        """The collar breaks — release the wearer and leave a mark."""
        room = char.location

        if room:
            room.msg_contents(
                f"|x{_TRANSITION_MSGS['broken'].format(name=cname)}|n"
            )

        # Clear compounding effects
        try:
            from world.binding_effects import remove_effects
            remove_effects(char, self)
        except Exception:
            pass

        # Place a "broken collar mark" freeform item (24h TTL)
        try:
            from world.freeform_manager import FreeformManager
            zone = self.db.worn_on_zone or "neck"
            FreeformManager.place_item(
                char, zone,
                "broken collar",
                "The remnants of a collar that didn't last — "
                "a worn line at the throat where it sat.",
                0,
                display_mode="on",
            )
            items = char.db.freeform_items or {}
            entry = items.get("broken collar")
            if entry:
                entry["ttl_hours"]  = 24.0
                entry["created_at"] = time.time()
                char.db.freeform_items = items
        except Exception:
            pass

        # Clear zone mechanics
        zone_name = self.db.worn_on_zone
        if zone_name:
            zones = getattr(char.db, "zones", None) or {}
            if zone_name in zones:
                mech = dict((zones[zone_name].get("mechanics") or {}))
                mech.pop("collar", None)
                zc = dict(zones[zone_name]); zc["mechanics"] = mech
                zs = dict(zones); zs[zone_name] = zc
                char.db.zones = zs

        self.db.is_worn      = False
        self.db.worn_on_char = None
        self.db.worn_on_zone = None
        self.delete()
