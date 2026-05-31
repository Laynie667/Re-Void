"""
typeclasses/npc.py

NPC typeclass for Re:Void.

TIERS
-----
Tier 0 — Scene Extra
    Temporary named entities created by players during scenes.
    Stored as data on room.db.scene_extras, not as real objects.
    Players puppet them via 'extra say/pose/emote' commands.
    Auto-cleaned when the scene ends via FreeformManager.end_scene().

Tier 1 — Ambient NPC
    Persistent objects that live in rooms and contribute ambient lines.
    Look/examine-able. No interaction triggers.
    Appear in room via get_room_desc_line().
    Contribute to ambient pool via get_ambient_pool().

Tier 2 — Scripted NPC
    Tier 1 + keyword trigger table + per-player state tracking.
    Can offer services. Simple branching dialogue.

Tier 3 — Interactive NPC
    Tier 2 + optional zone system + interaction flags + lore sheet.
    Services can bypass consent for builder/quest use.

NPC objects (Tier 1-3) inherit DefaultCharacter so they can be
looked at, examined, and searched like other entities.
Scene Extras (Tier 0) are stored as dicts on room.db.scene_extras.

STORAGE
-------
npc.db.npc_tier          = int (1-3)
npc.db.npc_id            = str  (YAML config id for lookup)
npc.db.rp_name           = str  (display name)
npc.db.physical_desc     = str
npc.db.outfit_desc       = str
npc.db.mood              = str  (current mood/state shown on look)
npc.db.presence          = str  (shown in room presence line)

npc.db.ambient_base      = [str, ...]
npc.db.ambient_states    = {
    "label": {
        "condition": {"key": value, ...},
        "lines": [str, ...]
    }
}
npc.db.ambient_interval  = [min_sec, max_sec]  (default [180, 360])

npc.db.triggers          = {
    "keyword": {
        "response": str | [str, ...],
        "type": "say|emote|action",
        "set_state": {key: value, ...},
        "conditions": {state_key: value, ...},
    }
}
npc.db.player_states     = {str(account_id): {key: value, ...}}

npc.db.services          = {
    "name": {
        "desc": str,
        "consent_bypass": False,
        "bypass_reason": str,
        "action": str,
    }
}
npc.db.zones             = {}  # simplified zone data (Tier 3)
npc.db.interaction_flags = {
    "mature": False,
    "consent_bypass": False,
    "bdsm": False,
}
npc.db.lore_fields       = [{"name": str, "value": str}, ...]
npc.db.npc_config        = {}  # raw YAML config, for reference

Room-level (Tier 0 extras):
room.db.scene_extras     = {
    "Name": {
        "desc": str,
        "puppet_by": char_id,  # id of character who created it
        "created": float,      # time.time()
    }
}
"""

import random
from evennia.objects.objects import DefaultCharacter
from evennia.utils import logger
from .objects import ObjectParent


# -----------------------------------------------------------------------
# NPC tier constants
# -----------------------------------------------------------------------

NPC_TIER_EXTRA       = 0   # Scene Extra (room data only, no object)
NPC_TIER_AMBIENT     = 1   # Ambient NPC
NPC_TIER_SCRIPTED    = 2   # Scripted NPC (triggers + services)
NPC_TIER_INTERACTIVE = 3   # Interactive NPC (zones + consent handling)

NPC_TIER_LABELS = {
    NPC_TIER_AMBIENT:     "Tier 1 — Ambient",
    NPC_TIER_SCRIPTED:    "Tier 2 — Scripted",
    NPC_TIER_INTERACTIVE: "Tier 3 — Interactive",
}


class NPC(ObjectParent, DefaultCharacter):
    """
    NPC typeclass for Re:Void.

    Covers Tier 1 (Ambient), Tier 2 (Scripted), and Tier 3 (Interactive).
    Scene Extras (Tier 0) are stored as data on rooms, not as NPC objects.

    Builders create and configure NPCs via 'npc' commands or YAML files.
    Players interact via 'ask', 'greet', and 'nservice' commands.
    NPCs appear in room descriptions and contribute ambient lines automatically.
    """

    def at_object_creation(self):
        super().at_object_creation()

        # Identity
        self.db.npc_tier = NPC_TIER_AMBIENT
        self.db.npc_id   = ""

        # Description layers
        self.db.rp_name       = self.key
        self.db.physical_desc = ""
        self.db.outfit_desc   = ""
        self.db.mood          = ""
        self.db.presence      = ""

        # Ambient system
        self.db.ambient_base     = []
        self.db.ambient_states   = {}
        self.db.ambient_interval = [180, 360]

        # Trigger system (Tier 2+)
        self.db.triggers      = {}
        self.db.player_states = {}

        # Parrot mechanic — fires on_hear_say when someone uses 'say' in room
        self.db.react_to_say    = False
        self.db.parrot_responses = []  # list of response templates: {text}, {name}

        # Services (Tier 2+)
        self.db.services = {}

        # Interactive flags (Tier 3+)
        self.db.zones             = {}
        self.db.interaction_flags = {
            "mature":         False,
            "consent_bypass": False,
            "bdsm":           False,
        }
        self.db.lore_fields = []

        # Raw YAML config reference
        self.db.npc_config = {}

        # NPCs are controlled by builders only
        self.locks.add("puppet:perm(Builder)")
        self.locks.add("delete:perm(Builder)")
        self.locks.add("get:false()")

    # -------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------

    def get_display_name(self, looker=None, **kwargs):
        """Return the NPC's display name."""
        return self.db.rp_name or self.key

    # -------------------------------------------------------------------
    # Room presence line (Layer 6 via get_object_room_desc_lines)
    # -------------------------------------------------------------------

    def get_room_desc_line(self):
        """
        Return a single presence line shown in the room description.
        Called by room.get_object_room_desc_lines() for all objects.
        """
        name = self.db.rp_name or self.key
        presence = self.db.presence or ""
        mood = self.db.mood or ""

        detail = presence or mood
        if detail:
            return f"|w{name}|n is here. |x[{detail}]|n"
        return f"|w{name}|n is here."

    # -------------------------------------------------------------------
    # Ambient pool contribution (picked up by room.get_ambient_pool)
    # -------------------------------------------------------------------

    def get_ambient_pool(self):
        """
        Return lines to contribute to the room's ambient pool.
        Called automatically by room.get_ambient_pool() for any
        object that has this method.

        Evaluates state conditions against the room's current state.
        """
        pool = list(self.db.ambient_base or [])
        room = self.location

        states = self.db.ambient_states or {}
        for label, state_def in states.items():
            condition = state_def.get("condition", {})
            lines = state_def.get("lines", [])
            if lines and self._check_ambient_condition(condition, room):
                pool.extend(lines)

        return pool

    def _check_ambient_condition(self, condition, room):
        """
        Evaluate whether a state-ambient condition is met.

        Supported condition keys:
            occupied = True/False     — is anyone (with account) in room?
            time_of_day = "morning"   — current IC time period
            room_state.<attr> = value — checks room.db attribute
        """
        if not condition:
            return True

        for key, expected in condition.items():
            if key == "occupied":
                occupants = [
                    o for o in (room.contents if room else [])
                    if hasattr(o, 'has_account') and o.has_account
                ]
                if bool(occupants) != expected:
                    return False

            elif key == "time_of_day":
                try:
                    from world.gametime import get_time_period
                    actual = get_time_period()
                except Exception:
                    actual = None
                if actual != expected:
                    return False

            elif key.startswith("room_state."):
                attr = key.split(".", 1)[1]
                actual = getattr(room.db, attr, None) if room else None
                if actual != expected:
                    return False

        return True

    # -------------------------------------------------------------------
    # Appearance
    # -------------------------------------------------------------------

    def return_appearance(self, looker, **kwargs):
        """
        Build the NPC's appearance for look/examine.
        Simpler than the full 16-layer character system.
        """
        # Accept both 'deep' and 'deep_examine' (examine command passes the latter)
        deep = kwargs.get("deep_examine", False) or kwargs.get("deep", False)
        name = self.db.rp_name or self.key
        tier = self.db.npc_tier or NPC_TIER_AMBIENT

        lines = []

        # Name
        lines.append(f"|w{name}|n")

        # Physical desc — render {zone:name} tokens before display
        physical = self.db.physical_desc or ""
        if physical:
            from world.freeform_manager import render_zone_tokens
            physical = render_zone_tokens(physical, self)
            lines.append(physical)

        # Outfit
        outfit = self.db.outfit_desc or ""
        if outfit:
            lines.append(outfit)

        # Mood/current state
        mood = self.db.mood or ""
        if mood:
            lines.append(f"|x{mood}|n")

        # Examine extras
        if deep:
            sep = "|x" + "─" * 40 + "|n"

            # Zones defined on this NPC
            # Use list(keys()) + zones.get() rather than .items() to avoid
            # _SaverDict bypassing __getitem__ and returning raw stored data.
            zones = self.db.zones or {}
            zone_keys = list(zones.keys())
            if zone_keys:
                lines.append("")
                lines.append(sep)
                lines.append("|wZones:|n")
                VIS_ORDER = ["look", "examine", "proximity", "consent"]
                for vis in VIS_ORDER:
                    zone_group = []
                    for zname in zone_keys:
                        zdata = zones.get(zname, {})
                        if (zdata.get("visibility") if zdata else None) == vis:
                            zone_group.append((zname, zdata))
                    if not zone_group:
                        continue
                    vis_label = {
                        "look":      "|x[visible on look]|n",
                        "examine":   "|x[visible on examine]|n",
                        "proximity": "|x[visible when near]|n",
                        "consent":   "|x[consent-gated]|n",
                    }.get(vis, f"|x[{vis}]|n")
                    lines.append(f"  {vis_label}")
                    for zname, zdata in zone_group:
                        zdesc = (zdata.get("nude") or "").strip()
                        zdesc_short = (zdesc[:60] + "…") if len(zdesc) > 60 else zdesc
                        lines.append(f"    |w{zname}|n — {zdesc_short}")

            # Freeform items placed on this NPC
            # Same _SaverDict caution — use list(keys()) + .get()
            freeform = self.db.freeform_items or {}
            freeform_keys = sorted(freeform.keys())
            if freeform_keys:
                lines.append("")
                lines.append(sep)
                lines.append("|xPlaced items:|n")
                for iname in freeform_keys:
                    idata = freeform.get(iname, {})
                    izone = idata.get("zone", "?").replace("_", " ")
                    idesc = idata.get("desc", "")
                    lock = idata.get("lock")
                    lock_str = ""
                    if lock:
                        lock_str = f" |r[{lock.get('type', 'locked')}]|n"
                    lines.append(f"  |w{iname}|n [{izone}]: {idesc}{lock_str}")

            if tier >= NPC_TIER_SCRIPTED:
                services = self.db.services or {}
                if services:
                    svc_names = list(services.keys())
                    lines.append(
                        f"\n|xServices available:|n "
                        + ", ".join(svc_names)
                    )
                    lines.append("|x  (Use: nservice <npc> to access)|n")

            if tier >= NPC_TIER_INTERACTIVE:
                lore = self.db.lore_fields or []
                if lore:
                    lines.append("")
                    col = 16
                    for field in lore:
                        fname = field.get("name", "")
                        fval  = field.get("value", "")
                        if fname and fval:
                            lines.append(
                                f"|x{(fname + ':'):<{col}}|n {fval}"
                            )

        return "\n".join(lines)

    def at_desc(self, looker=None, **kwargs):
        """Called on look. Delegates to return_appearance."""
        return self.return_appearance(looker, **kwargs)

    # -------------------------------------------------------------------
    # Trigger system (Tier 2+)
    # -------------------------------------------------------------------

    def trigger_keyword(self, caller, keyword):
        """
        Called when a player uses 'ask <npc> about <keyword>'
        or similar trigger-invoking commands.

        Checks conditions against per-player state, picks a response,
        updates player state if set_state is defined.

        Returns True if a trigger fired, False otherwise.
        """
        tier = self.db.npc_tier or NPC_TIER_AMBIENT
        if tier < NPC_TIER_SCRIPTED:
            return False

        triggers = self.db.triggers or {}
        keyword_lower = keyword.strip().lower()

        # Try exact match first, then best-length substring match.
        # Longest key wins so "what comes next" beats "what".
        trigger = triggers.get(keyword_lower)
        if not trigger:
            best_match = None
            best_len = -1
            for tkey, tval in triggers.items():
                if keyword_lower in tkey or tkey in keyword_lower:
                    if len(tkey) > best_len:
                        best_match = tval
                        best_len = len(tkey)
            trigger = best_match

        if not trigger:
            return False

        # Check conditions against caller's player state
        conditions = trigger.get("conditions", {})
        if conditions:
            p_state = self._get_player_state(caller)
            for ckey, cval in conditions.items():
                if p_state.get(ckey) != cval:
                    return False

        # Pick response
        response = trigger.get("response", "")
        if not isinstance(response, str):
            response = random.choice(list(response))

        if response == "READY_CHECK":
            # Delegate to the NPC's ready gate handler
            self.do_ready_check(caller)
        elif response.startswith("_HANDLE_PURCHASE_"):
            # Delegate to the NPC's purchase handler
            handler_path = self.db.purchase_handler
            if handler_path:
                try:
                    import importlib
                    module_path, func_name = handler_path.rsplit(".", 1)
                    module = importlib.import_module(module_path)
                    handler = getattr(module, func_name)
                    suffix = response[len("_HANDLE_PURCHASE_"):]
                    if suffix == "TENT":
                        purchase_type = "tent"
                    elif suffix.startswith("ROOM_"):
                        purchase_type = int(suffix[5:])
                    else:
                        purchase_type = suffix.lower()
                    handler(caller, self, purchase_type)
                except Exception as e:
                    logger.log_err(f"NPC purchase handler error: {e}")
        elif response:
            trigger_type = trigger.get("type", "say")
            npc_name = self.db.rp_name or self.key

            # Escape curly braces so Evennia's format_map doesn't
            # interpret {zone:name} tokens or any other braces as
            # Python format placeholders.
            safe = response.replace("{", "{{").replace("}", "}}")

            if trigger_type == "say":
                self.location.msg_contents(
                    f'\n|w{npc_name}|n says, "|n{safe}|n"',
                    from_obj=self
                )
            elif trigger_type in ("emote", "action"):
                # Strip leading NPC name from response if already present,
                # so we don't get "Durgin Ironwood Durgin leans on the counter"
                display = safe.strip()
                for prefix in (npc_name, npc_name.split()[0]):
                    pl = prefix.lower()
                    dl = display.lower()
                    if dl.startswith(pl + " ") or dl.startswith(pl + "'"):
                        display = display[len(prefix):].strip()
                        break
                sep = "" if display.startswith("'") else " "
                self.location.msg_contents(
                    f"\n|w{npc_name}|n{sep}{display}",
                    from_obj=self
                )
            else:
                self.location.msg_contents(
                    f"\n{safe}", from_obj=self
                )

        # Update caller's player state
        set_state = trigger.get("set_state", {})
        if set_state:
            p_state = self._get_player_state(caller)
            p_state.update(set_state)
            self._set_player_state(caller, p_state)

        return True

    def trigger_approach(self, caller):
        """Called when a player approaches this NPC."""
        return self.trigger_keyword(caller, "_approach")

    def trigger_greeting(self, caller):
        """
        Called when a player greets this NPC.
        Tries 'hello' then 'greet' triggers, then a default nod.
        """
        fired = self.trigger_keyword(caller, "hello")
        if not fired:
            fired = self.trigger_keyword(caller, "greet")
        if not fired and self.db.npc_tier >= NPC_TIER_SCRIPTED:
            npc_name = self.db.rp_name or self.key
            self.location.msg_contents(
                f"|w{npc_name}|n acknowledges you with a quiet nod.",
                from_obj=self
            )
            return True
        return fired

    def on_hear_say(self, caller, text):
        """
        Called by the say command when this NPC is in the room and
        react_to_say is True.

        For Tier 2+ NPCs, tries to match the spoken text against the
        trigger table first. If a trigger fires, returns early.

        Falls back to parrot responses for Tier 1 NPCs or when no
        trigger matched. Templates may use:
            {text} — what the caller said
            {name} — the caller's display name
        """
        # Don't react to our own speech
        if caller == self:
            return

        # Tier 2+ — try trigger keyword match first
        tier = self.db.npc_tier or NPC_TIER_AMBIENT
        if tier >= NPC_TIER_SCRIPTED:
            if self.trigger_keyword(caller, text.strip()):
                return

        responses = self.db.parrot_responses or []
        if not responses:
            return

        response = random.choice(responses)
        name = (
            caller.db.rp_name or caller.key
            if hasattr(caller, 'db') and caller.db.rp_name
            else caller.key
        )

        try:
            formatted = response.format(text=text, name=name)
        except Exception:
            formatted = response

        if self.location:
            self.location.msg_contents(formatted, from_obj=self)

    # -------------------------------------------------------------------
    # Ready gate system (Tier 2+ — forming rooms only)
    # -------------------------------------------------------------------

    def do_ready_check(self, caller):
        """
        Called when a player triggers the 'ready' keyword and the
        NPC's response is the sentinel string "READY_CHECK".

        Dispatches to a gate handler based on npc_id.
        Override or extend for new forming NPCs.
        """
        npc_id = self.db.npc_id or ""
        if npc_id == "forming_mirror":
            self._mirror_ready_check(caller)
        elif npc_id == "forming_wren":
            self._wren_ready_check(caller)
        else:
            caller.msg(
                "The moment passes. Nothing has changed yet."
            )

    def _mirror_ready_check(self, caller):
        """
        Space 4 — The Mirror gate check.
        Requires: physical_desc, ic_presence, at least one zone
        described, at least one freeform item placed, at least one
        outfit or wardrobe item saved.
        """
        missing = []

        if not getattr(caller.db, "physical_desc", ""):
            missing.append(
                "\"Not yet,\" the Mirror says. \"I cannot see your body. "
                "Use |wsetdesc|n — write what you look like. "
                "That is the first thing anyone will read about you.\""
            )

        if not getattr(caller.db, "ic_presence", ""):
            missing.append(
                "\"Almost,\" the Mirror says. \"Your presence line is empty "
                "— that is the short phrase next to your name in every room "
                "you enter. Use |wsetpresence|n. One line. "
                "How you hold yourself in a space.\""
            )

        # Check for at least one described zone
        # Note: iterate by key and use .get() rather than .values() or .items()
        # because _SaverDict.values()/.items() bypasses __getitem__ and may
        # return raw stored data that behaves differently from direct access.
        zones = caller.db.zones or {}
        has_zone_desc = any(
            (zones.get(zname, {}).get("nude") or "").strip()
            for zname in list(zones.keys())
        )
        if not has_zone_desc:
            missing.append(
                "\"There is more to do,\" the Mirror says. \"Describe at least "
                "one of your zones — use |wzone set <name> = <text>|n. "
                "The body needs some detail beneath the clothing.\""
            )

        # Check for at least one freeform item placed
        # Use list(keys()) + .get() to avoid _SaverDict iteration quirks
        freeform = caller.db.freeform_items or {}
        has_freeform = bool(list(freeform.keys()))
        if not has_freeform:
            missing.append(
                "\"You are undressed,\" the Mirror says, not unkindly. "
                "\"Or at least unwritten. Use |wplace me <zone> = <name>/<desc>|n "
                "to put something on yourself — even one piece. Even a simple one.\""
            )

        # Check for at least one outfit or wardrobe item saved
        # (exclude the built-in "default" and "undressed" preset stubs)
        outfits = caller.db.outfit_presets or {}
        real_outfits = [
            k for k in list(outfits.keys())
            if k not in ("default", "undressed")
        ]
        wardrobe = caller.db.wardrobe or {}
        if not real_outfits and not wardrobe:
            missing.append(
                "\"One more thing,\" the Mirror says. \"Save your current look "
                "— use |woutfit save \\\"<name>\\\"|n. Then |woutfit wear \\\"<name>\\\"|n "
                "to load it back. This is how you keep your outfits when you return. "
                "Do this once and I will know you understand it.\""
            )

        if missing:
            if len(missing) == 1:
                caller.msg(missing[0])
            else:
                caller.msg(
                    "\"Not quite,\" the Mirror says. \"A few things remain:\"\n\n"
                    + "\n\n".join(missing)
                    + "\n\n\"Work through them. Come back when they are done.\""
                )
            return

        # All checks pass — reveal the exit and send the pass message
        if self.location:
            self.location.msg_contents(
                """The Mirror is quiet for a moment. Then:

"Yes," it says. "That's you."

The surface holds your reflection — all of it, finally, complete — and then it does
something it has not done before: it shows you someone else's view. What you look
like from the outside. From a distance. Walking into a room.

"Go and be seen," the Mirror says.

At the far edge of the room, the wall parts — not dramatically, just opens, the way
a door does when someone has decided you may pass.

The world is through there. |wvoid|n."""
            )

    def _wren_ready_check(self, caller):
        """
        Space 5 — Wren gate check.
        Requires: at least one item placed on the companion, and at
        least one social emote used in this space.
        """
        missing = []

        # Check companion freeform — look for companion NPC in room
        companion = None
        if self.location:
            for obj in self.location.contents:
                if (hasattr(obj, 'db') and
                        getattr(obj.db, 'npc_id', '') == "forming_companion"):
                    companion = obj
                    break

        if companion is not None:
            freeform = getattr(companion.db, "freeform_items", {}) or {}
            # Check if any item was placed by this caller
            placed_by_caller = any(
                str(item.get("placed_by", "")) == str(caller.id)
                for item in freeform.values()
                if isinstance(item, dict)
            )
            if not placed_by_caller:
                missing.append(
                    "\"You have not placed anything on the companion,\" "
                    "Wren says. \"Do that first. "
                    "|wplace |ccompanion |c<zone>|n|w = |c<name>/<desc>|n.\""
                )
        else:
            # Companion not found — skip this check rather than block indefinitely
            pass

        # Check social emote usage
        if not getattr(caller.db, "forming_social_used", False):
            missing.append(
                "\"You have not used a social emote,\" Wren says. "
                "\"Type |wsocials|n, pick one, use it. "
                "That is the entire requirement.\""
            )

        if missing:
            if len(missing) == 1:
                caller.msg(missing[0])
            else:
                caller.msg(
                    "\"Two things,\" Wren says. "
                    "\"Place something on the companion. "
                    "Use a social emote. Then come back.\""
                )
            return

        # All checks pass — Wren pushes them out
        if self.location:
            self.location.msg_contents(
                """Wren sets her pen down.

"Good." She does not elaborate on what was good. She looks at you with the
expression of someone who has made a decision about you and found it acceptable.

She comes out from behind the counter.

"The world is through there." She gestures toward a section of wall that has,
until this moment, not been a door. It is, now, briefly, a door.

She moves toward you with the specific purpose of someone who intends to relocate
a problem that has been solved.""",
                from_obj=self
            )
            # Move caller through the exit
            if caller.location:
                void_exit = None
                for ex in caller.location.exits:
                    if ex.key.lower() in ("void", "out", "forward", "world"):
                        void_exit = ex
                        break
                if void_exit:
                    caller.execute_cmd("void")

    def _get_player_state(self, caller):
        """Return the caller's stored state dict (copy)."""
        states = self.db.player_states or {}
        acct_id = self._caller_id(caller)
        return dict(states.get(acct_id, {}))

    def _set_player_state(self, caller, state_dict):
        """Save caller's state dict."""
        states = dict(self.db.player_states or {})
        states[self._caller_id(caller)] = state_dict
        self.db.player_states = states

    def _caller_id(self, caller):
        """Get a stable string id for a caller (uses account id if available)."""
        if hasattr(caller, 'account') and caller.account:
            return str(caller.account.id)
        return str(caller.id)

    def get_player_state_value(self, caller, key, default=None):
        """Convenience: get a single key from caller's player state."""
        return self._get_player_state(caller).get(key, default)

    def set_player_state_value(self, caller, key, value):
        """Convenience: set a single key in caller's player state."""
        state = self._get_player_state(caller)
        state[key] = value
        self._set_player_state(caller, state)

    # -------------------------------------------------------------------
    # Service system (Tier 2+)
    # -------------------------------------------------------------------

    def list_services(self):
        """Return list of (service_name, service_dict) tuples."""
        return list((self.db.services or {}).items())

    def perform_service(self, caller, service_name):
        """
        Attempt to perform a named service for the caller.

        Returns (success: bool, message: str)
        """
        services = self.db.services or {}
        svc = services.get(service_name.lower())
        if not svc:
            return False, f"'{service_name}' is not a service I offer."

        # Emit the service action
        action = svc.get("action", "")
        npc_name = self.db.rp_name or self.key
        caller_name = (
            caller.db.rp_name or caller.key
            if hasattr(caller, 'db') else str(caller)
        )

        if action:
            resolved = action.replace("{caller}", caller_name)
            self.location.msg_contents(
                f"|w{npc_name}|n {resolved}",
                from_obj=self
            )
        else:
            desc = svc.get("desc", service_name)
            self.location.msg_contents(
                f"|w{npc_name}|n performs: {desc}",
                from_obj=self
            )

        return True, ""

    # -------------------------------------------------------------------
    # NPC sheet (for builder inspection via 'npc sheet <npc>')
    # -------------------------------------------------------------------

    def get_npc_sheet(self):
        """Return a formatted string summarizing the NPC for builders."""
        tier = self.db.npc_tier or NPC_TIER_AMBIENT
        name = self.db.rp_name or self.key
        npc_id = self.db.npc_id or f"#{self.id}"

        sep = "|w" + "─" * 50 + "|n"
        lines = [
            sep,
            f"|w{name}|n  |x{npc_id}  #{self.id}|n  "
            f"{NPC_TIER_LABELS.get(tier, f'Tier {tier}')}",
            sep,
            "",
        ]

        # Description
        if self.db.physical_desc:
            snippet = self.db.physical_desc[:75]
            ellip = "..." if len(self.db.physical_desc) > 75 else ""
            lines.append(f"|xPhysical:|n  {snippet}{ellip}")
        if self.db.outfit_desc:
            snippet = self.db.outfit_desc[:75]
            ellip = "..." if len(self.db.outfit_desc) > 75 else ""
            lines.append(f"|xOutfit:  |n  {snippet}{ellip}")
        if self.db.mood:
            lines.append(f"|xMood:    |n  {self.db.mood}")
        if self.db.presence:
            lines.append(f"|xPresence:|n  {self.db.presence}")

        # Ambient
        ambient = self.db.ambient_base or []
        states = self.db.ambient_states or {}
        lines.append("")
        lines.append(f"|wAmbient:|n  {len(ambient)} base line(s)")
        if states:
            state_summary = ", ".join(
                f"{k} ({len(v.get('lines', []))} lines)"
                for k, v in states.items()
            )
            lines.append(f"  State pools: {state_summary}")

        # Triggers (Tier 2+)
        if tier >= NPC_TIER_SCRIPTED:
            triggers = self.db.triggers or {}
            lines.append(f"|wTriggers:|n  {len(triggers)} keyword(s)")
            for kw in list(triggers.keys())[:8]:
                lines.append(f"  · {kw}")
            if len(triggers) > 8:
                lines.append(f"  · ... and {len(triggers) - 8} more")

            services = self.db.services or {}
            lines.append(f"|wServices:|n  {len(services)}")
            for sname, svc in services.items():
                bypass = " |r[consent bypass]|n" if svc.get("consent_bypass") else ""
                desc = svc.get("desc", "")[:50]
                lines.append(f"  · {sname}{bypass}: {desc}")

        # Interactive flags + lore (Tier 3+)
        if tier >= NPC_TIER_INTERACTIVE:
            flags = self.db.interaction_flags or {}
            active = [k for k, v in flags.items() if v]
            lines.append(
                f"|wFlags:|n  {', '.join(active) if active else 'none'}"
            )
            lore = self.db.lore_fields or []
            if lore:
                lines.append("|wLore fields:|n")
                for f in lore:
                    fname = f.get("name", "")
                    fval  = f.get("value", "")[:60]
                    lines.append(f"  {fname}: {fval}")

        lines.append(sep)
        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Movement override — NPCs don't wander
    # -------------------------------------------------------------------

    def at_before_move(self, destination, **kwargs):
        """NPCs don't move on their own."""
        return True

    def announce_move_from(self, destination, msg=None, **kwargs):
        """Suppress default movement messages for NPCs."""
        pass

    def announce_move_to(self, source_location, msg=None, **kwargs):
        """Suppress default movement messages for NPCs."""
        pass

    # -------------------------------------------------------------------
    # Server reload — auto-sync triggers from spawn module
    # -------------------------------------------------------------------

    def at_server_reload(self):
        """
        Re-import and apply the trigger table from the NPC's spawn module
        on every server reload, so changes to the spawn file take effect
        without manually running @py or re-spawning the NPC.

        Requires two keys set in db.npc_config:
            trigger_module  — dotted module path e.g. "world.durgin_spawn"
            trigger_var     — name of the triggers dict, e.g. "DURGIN_TRIGGERS"
        """
        config = self.db.npc_config or {}
        module_path = config.get("trigger_module")
        var_name    = config.get("trigger_var")
        if not module_path or not var_name:
            return
        try:
            import importlib
            mod      = importlib.import_module(module_path)
            # Force reload so edits since last boot are picked up
            importlib.reload(mod)
            triggers = getattr(mod, var_name, None)
            if isinstance(triggers, dict):
                self.db.triggers = triggers
        except Exception as e:
            from evennia.utils import logger
            logger.log_err(
                f"NPC {self.key} trigger auto-sync failed "
                f"({module_path}.{var_name}): {e}"
            )
