"""
typeclasses/characters.py

The Character typeclass represents an IC player entity in the world.
One Account can have multiple Characters.

When an Account puppets a Character, the player enters the game world.
When they unpuppet, the Character remains where it is.

The Character holds:
- The 16-layer description system
- The zone and clothing system  
- Social and relationship data
- Title assembly (PREFIX/LEVEL/INTERFIX/FACTION/SUFFIX)
- Consent and access flags
- Position and proximity state
- Scene and RP tracking
"""

import re
import random
from evennia.objects.objects import DefaultCharacter
from evennia.utils import logger
from .objects import ObjectParent

_ZONE_TOKEN_RE = re.compile(r'\{zone:([a-z_/]+)\}')


# -------------------------------------------------------------------
# Zone configuration
# -------------------------------------------------------------------

# Zone types
ZONE_TYPES = {
    "surface":    "things rest on or against this zone",
    "orifice":    "things can be placed inside this zone",
    "both":       "surface and orifice",
    "attachment": "things attach to or pierce this zone",
}

# Zone visibility levels
ZONE_VISIBILITY = {
    "look":      "visible on standard look",
    "examine":   "visible on examine",
    "deep":      "visible on examine closely only",
    "proximity": "visible at near/with proximity only",
    "consent":   "requires consent flag",
    "hidden":    "private — not visible to others",
}

# Hierarchical zone tree.
# Each entry: (name, parent, zone_type, intimate, visibility, consent_required)
# parent=None means root zone. Children inherit coverage from parents.
# Supports arbitrary depth — players extend via 'zone add parent/child/grandchild'.
DEFAULT_ZONE_TREE = [
    # ── ROOT ZONES ────────────────────────────────────────────────────
    # Wearing a root covers all its descendants.
    ("head",       None,    "surface",    False, "look",    "casual"),
    ("neck",       None,    "surface",    False, "look",    "casual"),
    ("torso",      None,    "surface",    False, "look",    "casual"),
    ("arms",       None,    "surface",    False, "look",    "casual"),
    ("groin",      None,    "surface",    True,  "hidden",  "intimate"),
    ("legs",       None,    "surface",    False, "look",    "casual"),

    # ── HEAD ──────────────────────────────────────────────────────────
    ("hair",       "head",  "surface",    False, "look",    "casual"),
    ("face",       "head",  "surface",    False, "look",    "casual"),
    ("ears",       "head",  "attachment", False, "look",    "casual"),

    # face children
    ("eyes",       "face",  "surface",    False, "look",    "casual"),
    ("lips",       "face",  "attachment", False, "look",    "casual"),
    ("mouth",      "face",  "both",       False, "look",    "casual"),

    # mouth children
    ("tongue",     "mouth", "attachment", False, "examine", "casual"),

    # ── NECK ──────────────────────────────────────────────────────────
    ("throat",     "neck",  "both",       False, "look",    "casual"),
    ("nape",       "neck",  "surface",    False, "examine", "intimate"),

    # ── TORSO ─────────────────────────────────────────────────────────
    ("shoulders",  "torso", "surface",    False, "look",    "casual"),
    ("chest",      "torso", "surface",    True,  "look",    "casual"),
    ("abdomen",    "torso", "surface",    True,  "look",    "intimate"),
    ("back",       "torso", "surface",    False, "look",    "casual"),
    ("lower_back", "back",  "surface",    True,  "examine", "intimate"),
    ("waist",      "torso", "surface",    False, "look",    "casual"),

    # ── ARMS ──────────────────────────────────────────────────────────
    ("wrists",     "arms",  "attachment", False, "look",    "casual"),
    ("hands",      "arms",  "surface",    False, "look",    "casual"),

    # ── GROIN ─────────────────────────────────────────────────────────
    # Ships empty. Players build anatomy here:
    #   zone add groin/vulva type=both intimate
    #   zone add groin/anus  type=orifice intimate
    #   etc.

    # ── LEGS ──────────────────────────────────────────────────────────
    ("hips",       "legs",  "surface",    True,  "look",    "intimate"),
    ("thighs",     "legs",  "surface",    True,  "look",    "intimate"),
    ("ankles",     "legs",  "attachment", False, "look",    "casual"),
    ("feet",       "legs",  "surface",    False, "look",    "casual"),
]

# Ordered list of root zone names — determines tree display order.
DEFAULT_ROOT_ORDER = ["head", "neck", "torso", "arms", "groin", "legs"]

# Child display order within each parent — append-order wins for unlisted.
DEFAULT_CHILD_ORDER = {
    "head":  ["hair", "face", "ears"],
    "face":  ["eyes", "lips", "mouth"],
    "mouth": ["tongue"],
    "neck":  ["throat", "nape"],
    "torso": ["shoulders", "chest", "abdomen", "back", "waist"],
    "back":  ["lower_back"],
    "arms":  ["wrists", "hands"],
    "legs":  ["hips", "thighs", "ankles", "feet"],
}

# ZONE_DISPLAY_ORDER kept for backwards compatibility — derived from tree walk.
ZONE_DISPLAY_ORDER = [
    "head", "hair", "face", "eyes", "lips", "mouth", "tongue", "ears",
    "neck", "throat", "nape",
    "torso", "shoulders", "chest", "abdomen", "back", "lower_back", "waist",
    "arms", "wrists", "hands",
    "groin",
    "legs", "hips", "thighs", "ankles", "feet",
]

# ZONE_GROUPS kept for backwards compatibility — tree display replaces this
# in zone list, but imported by character_commands.py.
ZONE_GROUPS = [
    ("HEAD",   ["head", "hair", "face", "eyes", "lips", "mouth", "tongue", "ears"]),
    ("NECK",   ["neck", "throat", "nape"]),
    ("TORSO",  ["torso", "shoulders", "chest", "abdomen", "back", "lower_back", "waist"]),
    ("ARMS",   ["arms", "wrists", "hands"]),
    ("GROIN",  ["groin"]),
    ("LEGS",   ["legs", "hips", "thighs", "ankles", "feet"]),
]

# Reputation tiers — drives level title
REPUTATION_TIERS = [
    (0,     "Unknown"),
    (100,   "Noticed"),
    (250,   "Known"),
    (500,   "Familiar"),
    (1000,  "Recognized"),
    (2000,  "Respected"),
    (3500,  "Notable"),
    (5000,  "Prominent"),
    (7500,  "Influential"),
    (10000, "Celebrated"),
]

# Consent level ordering — used for safe comparisons
CONSENT_LEVELS = ["casual", "intimate", "mature", "bdsm"]


def _make_default_zone(intimate=False, visibility="look",
                       zone_type="surface",
                       consent_required="casual",
                       parent=None):
    """
    Helper to create a fresh zone dict.

    Args:
        intimate (bool): Zone is intimate when nude.
        visibility (str): Default visibility level.
        zone_type (str): surface / orifice / both / attachment
        consent_required (str): Minimum consent for interaction.
        parent (str|None): Parent zone name, or None for root zones.
    """
    return {
        # Hierarchy
        "parent":           parent,

        # Surface layer — what's ON or AT this zone
        "nude":             "",
        "covered_by":       None,

        # Interior description — for orifice/both zones.
        # Shown only at deep examine with mature consent,
        # or when a womb-room item renders this zone as an interior space.
        "interior":         "",

        # Orifice layer — what's IN this zone
        # List of dicts: {desc, state, set_by, removable_by}
        "contents":         [],

        # State tracking
        "state":            "pristine",
        "state_desc":       None,
        "state_ambient":    [],

        # Access and visibility
        "visibility":       visibility,
        "intimate":         intimate,
        "zone_type":        zone_type,
        "consent_required": consent_required,

        # Details — keyed observations (like room zone details)
        # Set with: zone detail <zone>/<key> = <text>
        "details":          {},

        # Study pool — discovered only via careful observation
        # Set with: zone study <zone> = <observation>
        "study_details":    [],

        # Handle pool — verb-keyed interaction messages
        # Set with: zone handle/add <zone>/<verb> = <message>
        # Tokens: {actor}, {actor_s}, {actor_they}, {actor_them},
        #         {actor_their}, {target}, {target_s}, {target_they},
        #         {target_them}, {target_their}
        "handle_details":   {},

        # Mechanics — reserved for items installed onto this zone
        "mechanics":        {},

        # Metadata
        "default":          True,
        "freeform":         False,
        "ambient":          [],
    }


# -------------------------------------------------------------------
# Proximity helper — used by Character hooks and proximity_commands
# -------------------------------------------------------------------

def _proximity_clear_and_notify(char):
    """
    Clear all of char's proximity entries and notify each partner.
    Used on move and on unpuppet.
    """
    proximity = char.db.proximity or {}
    if not proximity:
        return
    char_name = char.db.rp_name or char.name
    for partner_id, level in list(proximity.items()):
        # Resolve the partner object
        try:
            from evennia import search_object
            results = search_object(f"#{partner_id}")
            if results:
                partner = results[0]
                partner.msg(f"{char_name} has moved away from you.")
        except Exception:
            pass
    char.db.proximity = {}


class Character(ObjectParent, DefaultCharacter):
    """
    The Character typeclass for Re:Void.

    Represents an IC player entity. Holds all description layers,
    zone and clothing data, social relationships, title components,
    and position/proximity state.
    """

    def at_object_creation(self):
        """
        Called once when the character is first created.
        Sets all default values.
        """
        super().at_object_creation()

        # ---------------------------------------------------------------
        # Core identity
        # ---------------------------------------------------------------
        self.db.rp_name = ""
        self.db.pronouns = {
            "subject":    "they",
            "object":     "them",
            "possessive": "their",
            "reflexive":  "themselves",
        }
        self.db.apparent_age = ""
        self.db.species = "human"

        # ---------------------------------------------------------------
        # Title system — PREFIX LEVEL INTERFIX FACTION SUFFIX
        # ---------------------------------------------------------------
        self.db.title_prefix = ""
        self.db.title_interfix = ""
        self.db.title_suffix = ""
        self.db.title_level = ""
        self.db.title_faction = ""
        self.db.titles_earned = []

        # ---------------------------------------------------------------
        # Description layers
        # ---------------------------------------------------------------

        # Layer 1 — Physical base
        self.db.physical_desc = ""

        # Layer 2 — Outfit (auto-assembled from zones)
        self.db.outfit_desc = ""
        self.db.outfit_desc_override = False

        # Layer 3 — Body language
        self.db.body_language = ""

        # Layer 4 — Mood and mood tell
        self.db.mood = ""
        self.db.mood_tell = ""

        # Layer 5 — IC presence line
        self.db.ic_presence = ""

        # Layer 6 — Proximity tell
        self.db.proximity_tell = ""

        # Layer 7 — Scent
        self.db.scent_desc = ""

        # Layer 8 — Voice
        self.db.voice_desc = ""
        self.db.say_verb = "says"

        # Layer 9 — Touch/texture
        self.db.touch_desc = ""

        # Layer 10 — Markings
        self.db.markings = []

        # Layer 13 — Public bio
        self.db.public_bio = ""

        # Layer 14 — Ambient contribution
        self.db.ambient_contribution = []

        # Layer 15 — Relationship-specific descs
        self.db.relationship_descs = {}

        # Layer 16 — Intimate layer
        self.db.intimate_desc = ""

        # ---------------------------------------------------------------
        # Zone and clothing system
        # ---------------------------------------------------------------
        self.db.zones = self._build_default_zones()

        self.db.zone_display_order = []
        # Empty = use ZONE_DISPLAY_ORDER default.
        # Player sets with: zone order [zone] [zone] ...

        self.db.wardrobe = {}
        # {name: {zone, desc, worn_desc, examine_desc,
        #         ambient, type, item_id, consent, state}}

        self.db.outfit_presets = {
            "default":   {},
            "undressed": {},
        }
        self.db.current_outfit = "undressed"
        self.db.dressed = False

        # ---------------------------------------------------------------
        # Social and reputation
        # ---------------------------------------------------------------
        self.db.reputation = 0
        self.db.relationships = {}
        self.db.faction_id = None
        self.db.faction_rank = ""
        self.db.org_memberships = []
        self.db.scene_count = 0
        self.db.rp_hooks = []

        # ---------------------------------------------------------------
        # Bio fields — player-defined key/value pairs on the sheet
        # ---------------------------------------------------------------
        # List of {"name": str, "value": str}
        self.db.bio_fields = []
        # Player-controlled display order (list of field names)
        self.db.bio_field_order = []

        # ---------------------------------------------------------------
        # Contacts / relationship system
        # ---------------------------------------------------------------
        # {str(char_id): {"name": str, "status": str,
        #                  "note": str, "rel_desc": str}}
        self.db.contacts = {}

        # ---------------------------------------------------------------
        # Zone sheet visibility
        # ---------------------------------------------------------------
        # If True, orifice zones show on public sheet
        self.db.zones_public = False

        # ---------------------------------------------------------------
        # Consent and access
        # ---------------------------------------------------------------
        self.db.consent_flags = {
            "casual":      True,
            "intimate":    False,
            "mature":      False,
            "bdsm":        False,
            "lead_follow": False,
            "restraint":   False,
            "plock":       False,   # consents to permanent freeform locks
            # Privacy / movement
            "allow_jump":   True,   # others may jump to this character's location
            "allow_summon": True,   # others may summon this character
        }
        self.db.consent_grants = {}
        # Per-zone grants: {zone_name: set(character_ids)}
        self.db.zone_consent_grants = {}
        self.db.block_list = set()
        # In-scene permission grants for perm-tier emotes
        # Structure: {emote_key: set(actor_character_ids)}
        # Populated by the 'permit' command; cleared on logout.
        self.db.perm_grants = {}
        # Admin watch list — account IDs silently monitoring this character
        self.db.watched_by = set()

        # ---------------------------------------------------------------
        # Arousal system
        # ---------------------------------------------------------------
        self.db.arousal                = 0.0    # 0–100 float
        self.db.last_arousal_activity  = 0.0    # unix timestamp of last gain
        self.db.arousal_cooldown_until = 0.0    # gain halved until this time
        self.db.penetrating            = None   # {target_dbref, zone_name} while engaged

        # Install arousal decay script immediately
        try:
            from typeclasses.arousal_script import ensure_arousal_script
            ensure_arousal_script(self)
        except Exception:
            pass

        # ---------------------------------------------------------------
        # Communication
        # ---------------------------------------------------------------
        self.db.language = "common"
        self.db.known_languages = {"common": 100}
        self.db.ooc_flag = False
        # AFK status — set by 'afk <message>', cleared by 'afk/clear'
        self.db.afk_message = None

        # ---------------------------------------------------------------
        # Position and proximity
        # ---------------------------------------------------------------
        self.db.seated_at = None
        # Zone-based positions — (room_id, zone_name) or None
        self.db.zone_seated_at   = None
        self.db.zone_lying_at    = None
        self.db.zone_kneeling_at = None
        # Zone-based restraint — (room_id, zone_name, restrainer_id) or None
        self.db.zone_restrained_at = None
        # Watching — target character id, or None
        self.db.zone_watching    = None
        # Dairy production profile
        self.db.dairy_fluid = None   # "milk", "cream", "honey", "seed", etc.
        self.db.dairy_desc  = None   # label flavor text e.g. "warm and sweet"
        self.db.dairy_on    = False  # available for milking
        # Proximity: {character_id: "near"/"with"}
        # You can be near/with multiple people simultaneously.
        self.db.proximity = {}
        self.db.currently_reaching = None
        self.db.wall_state = None

        # ---------------------------------------------------------------
        # Restraints and lead
        # ---------------------------------------------------------------
        # {zone_name: {desc, set_by_id, set_by_name,
        #              removable_by, blocks_movement}}
        self.db.restraints = {}
        # Lead connection — one leader / one follower at a time
        self.db.leading = None    # id of character being led
        self.db.led_by = None     # id of character leading this one
        self.db.lead_desc = ""    # flavor description of the lead

        # ---------------------------------------------------------------
        # Scene and RP tracking
        # ---------------------------------------------------------------
        self.db.scene_history = []
        self.db.active_scene_room = None
        self.db.pose_order_position = None

        # ---------------------------------------------------------------
        # Wisp carry-forward
        # ---------------------------------------------------------------
        self.db.wisp_mood_carry = True

    def at_init(self):
        """Called every time the character loads into memory."""
        super().at_init()

    def msg(self, text=None, from_obj=None, session=None,
            options=None, **kwargs):
        """
        Send a message to this character.
        Silently forwards a copy to any admin accounts watching them.
        """
        super().msg(
            text=text, from_obj=from_obj,
            session=session, options=options, **kwargs
        )
        watched_by = self.db.watched_by or set()
        if not watched_by or not text:
            return
        char_name = self.db.rp_name or self.name
        prefix = f"|x[{char_name}]|n "
        # Resolve text to a plain string for forwarding
        if isinstance(text, tuple):
            forward = f"{prefix}{text[0]}"
        else:
            forward = f"{prefix}{text}"
        from evennia import search_account
        for acct_id in list(watched_by):
            try:
                results = search_account(f"#{acct_id}")
                if results:
                    acct = results[0]
                    if acct.sessions.count() > 0:
                        acct.msg(forward)
            except Exception:
                pass

    def at_post_puppet(self, account=None, session=None, **kwargs):
        """
        Called just after the account puppets this character.
        Handles wisp mood carry-forward and login messaging.

        Evennia 4.x calls this hook with no arguments, so we resolve
        the account from self.account (the character's current puppeteer)
        rather than relying on the parameter.
        """
        super().at_post_puppet(**kwargs)

        # Prefer the parameter if given; fall back to self.account
        account = account or self.account

        mood = self.db.mood or ""
        location = self.location

        if account:
            # Carry wisp mood forward if flagged and no mood set
            if self.db.wisp_mood_carry and not mood:
                wisp_mood = account.wisp_mood
                if wisp_mood and wisp_mood != "uncertain":
                    self.db.mood = wisp_mood
                    mood = self.db.mood or ""

            color = account.wisp_color_code
            lines = [
                f"\n{color}The wisp gathers inward —|n\n"
                f"{color}concentrating into something "
                f"more specific.|n\n\n"
                f"|w{self.db.rp_name or self.key}|n "
                f"steps into the world.\n"
            ]

            if mood:
                lines.append(f"|x[mood: {mood}]|n")

            if location:
                lines.append(f"|xLocation: {location.key}|n")

            mail = account.db.mail_inbox or []
            unread = [m for m in mail if not m.get("read")]
            if unread:
                lines.append(
                    f"|x{len(unread)} unread letter(s) waiting.|n"
                )

            self.msg("\n".join(lines))
        else:
            # Minimal message when account context is unavailable
            self.msg(
                f"|w{self.db.rp_name or self.key}|n steps into the world."
            )

        # Show chargen checklist for fresh characters — no name or desc set yet
        is_fresh = not self.db.rp_name and not self.db.physical_desc
        if is_fresh:
            try:
                from commands.chargen import build_chargen_display
                self.msg(build_chargen_display(self))
            except Exception:
                self.msg(
                    "\n|yYour character isn't set up yet.|n "
                    "Type |wchargen|n to see what to fill in."
                )


    def at_pre_unpuppet(self, account=None, session=None, **kwargs):
        """
        Called just before the account unpuppets this character.
        Cleans up proximity and position states.
        """
        super().at_pre_unpuppet(**kwargs)

        # Clear all proximity — notify everyone we were near/with
        _proximity_clear_and_notify(self)

        if self.db.seated_at:
            try:
                from evennia import search_object
                furniture = search_object(self.db.seated_at)
                if furniture:
                    furniture = furniture[0]
                    occupants = furniture.db.occupants or []
                    if self.id in occupants:
                        occupants.remove(self.id)
                        furniture.db.occupants = occupants
            except Exception as e:
                logger.log_err(
                    f"Error clearing seated state: {e}"
                )
            self.db.seated_at = None
            self.db.body_language = ""

        # Zone-based position cleanup (seated / lying / kneeling)
        if self.db.zone_seated_at or self.db.zone_lying_at or self.db.zone_kneeling_at:
            try:
                from commands.mechanic_commands import _do_rise
                _do_rise(self, silent=True)
            except Exception:
                self.db.zone_seated_at   = None
                self.db.zone_lying_at    = None
                self.db.zone_kneeling_at = None

        # Zone restraint cleanup
        if getattr(self.db, "zone_restrained_at", None):
            try:
                from commands.restrain_commands import _do_release
                _do_release(self, silent=True)
            except Exception:
                self.db.zone_restrained_at = None

        # Watching state cleanup
        self.db.zone_watching = None

        if self.db.wall_state:
            self.db.wall_state = None

        self.db.currently_reaching = None

    def at_before_move(self, destination, move_type="move", **kwargs):
        """
        Called before this character moves to a new room.
        Blocks movement if any active restraint has blocks_movement=True.
        Blocks movement if any exit to the destination is flock-locked
        and the character doesn't hold the matching key.
        """
        # --- Door lock check ---
        if self.location and destination:
            try:
                zones = self.location.db.zones or {}
                for zone_name, zone_data in zones.items():
                    if not hasattr(zone_data, "get"):
                        continue
                    door = (zone_data.get("mechanics") or {}).get("door")
                    if not door:
                        continue
                    if not door.get("locked"):
                        continue
                    dest_id = door.get("destination_id")
                    if dest_id and destination.id == dest_id:
                        msg = door.get("lock_msg", "That door is locked.")
                        self.msg(f"|x{msg}|n")
                        return False
            except Exception:
                pass

        # --- Restraint check (freeform wardrobe restraints) ---
        restraints = self.db.restraints or {}
        for zone_name, data in restraints.items():
            if data.get("blocks_movement"):
                desc = data.get("desc", "a restraint")
                self.msg(
                    f"|xYou try to move, but {desc} holds you in place.|n"
                )
                return False

        # --- Zone restraint check (mechanic-installed restraint points) ---
        if getattr(self.db, "zone_restrained_at", None):
            val = self.db.zone_restrained_at
            blocker_msg = "|xYou are restrained and cannot move.|n"
            try:
                if self.location:
                    _, z_name, _ = val
                    zones = self.location.db.zones or {}
                    zone  = zones.get(z_name)
                    if zone and hasattr(zone, "get"):
                        r = (zone.get("mechanics") or {}).get("restrain")
                        if r:
                            blocker_msg = f"|x{r.get('blocker_msg', 'Something holds you fast.')}|n"
            except Exception:
                pass
            self.msg(blocker_msg)
            return False

        # --- Dildo seat lock check ---
        # Must run before movement is allowed; _do_rise (called at_post_move)
        # does NOT check this — it cleans up silently after moves that slip
        # through (teleports, server reloads). Only voluntary moves are blocked.
        try:
            from commands.mechanic_commands import _check_dildo_seat_locked
            locked, lock_msg = _check_dildo_seat_locked(self)
            if locked:
                self.msg(lock_msg)
                return False
        except Exception:
            pass

        # --- Exit flock check ---
        if self.location and destination:
            for exit_obj in self.location.exits:
                if exit_obj.destination == destination:
                    flock = exit_obj.db.flock or {}
                    if flock.get("locked"):
                        key_id = flock.get("key_id")
                        # Check if caller holds the key
                        has_key = any(
                            obj.db.is_freeform_key
                            and obj.db.key_id == key_id
                            for obj in self.contents
                        )
                        if not has_key:
                            self.msg(
                                f"|xThe {exit_obj.key} is locked. "
                                f"You'll need the key to pass.|n"
                            )
                            return False

        return super().at_before_move(
            destination, move_type=move_type, **kwargs
        )

    def at_post_move(self, source_location, move_type="move", **kwargs):
        """
        Called after this character successfully moves to a new room.
        Clears all proximity and notifies everyone we were near/with.
        Also notifies lead partner that we've moved.
        """
        super().at_post_move(
            source_location, move_type=move_type, **kwargs
        )
        _proximity_clear_and_notify(self)

        # Auto-rise from any zone position when leaving a room
        if self.db.zone_seated_at or self.db.zone_lying_at or self.db.zone_kneeling_at:
            try:
                from commands.mechanic_commands import _do_rise
                _do_rise(self, silent=True)
            except Exception:
                self.db.zone_seated_at   = None
                self.db.zone_lying_at    = None
                self.db.zone_kneeling_at = None

        # Clear zone restraint on room change (admin move / teleport bypass)
        if getattr(self.db, "zone_restrained_at", None):
            try:
                from commands.restrain_commands import _do_release
                _do_release(self, silent=True)
            except Exception:
                self.db.zone_restrained_at = None

        # Clear watching on room change
        self.db.zone_watching = None

        # Fire stair creak notifications if applicable
        try:
            from commands.stair_commands import fire_stair_creak
            fire_stair_creak(self, source_location, self.location)
        except Exception:
            pass

        # Notify lead partner if we moved while connected
        leading_id = self.db.leading
        led_by_id = self.db.led_by
        char_name = self.db.rp_name or self.name

        if leading_id:
            try:
                from evennia import search_object
                results = search_object(f"#{leading_id}")
                if results:
                    follower = results[0]
                    follower.msg(
                        f"|x[The lead pulls — "
                        f"{char_name} has moved.]|n"
                    )
            except Exception:
                pass

        if led_by_id:
            try:
                from evennia import search_object
                results = search_object(f"#{led_by_id}")
                if results:
                    leader = results[0]
                    leader.msg(
                        f"|x[{char_name} moves, pulling against "
                        f"your lead.]|n"
                    )
            except Exception:
                pass

    # -------------------------------------------------------------------
    # Zone system
    # -------------------------------------------------------------------

    def _get_zones(self):
        """
        Return a deep copy of the zones dict for safe modification.

        Always use this instead of `self.db.zones or {}` when you
        intend to modify zone data and save it back. Evennia may
        skip the DB write if the same object reference is reassigned,
        so deepcopy forces it to treat the value as changed.
        """
        import copy
        return copy.deepcopy(self.db.zones or {})

    def _build_default_zones(self):
        """
        Build the initial zone dict from DEFAULT_ZONE_TREE.
        Each zone gets its parent, type, consent, and visibility.

        Returns:
            dict: Full zone dict with hierarchy.
        """
        zones = {}
        for (name, parent, zone_type,
             intimate, visibility, consent) in DEFAULT_ZONE_TREE:
            zones[name] = _make_default_zone(
                intimate=intimate,
                visibility=visibility,
                zone_type=zone_type,
                consent_required=consent,
                parent=parent,
            )
        return zones

    def get_zone_order(self):
        """
        Return all zone names in depth-first tree order.

        Roots appear in DEFAULT_ROOT_ORDER. Children follow their
        parent immediately, in DEFAULT_CHILD_ORDER then alpha.
        Any custom zone_display_order is respected for roots.

        Returns:
            list: Zone names in display order.
        """
        zones = self._get_zones()

        # Build children map from zone data
        children_map = {}   # parent_name -> [child_names]
        roots = []
        for zname, zdata in zones.items():
            parent = zdata.get("parent")
            if not parent or parent not in zones:
                roots.append(zname)
            else:
                children_map.setdefault(parent, []).append(zname)

        # Sort children within each parent by preferred order then alpha
        for parent, kids in children_map.items():
            preferred = DEFAULT_CHILD_ORDER.get(parent, [])
            children_map[parent] = sorted(
                kids,
                key=lambda z: (
                    preferred.index(z)
                    if z in preferred
                    else len(preferred),
                    z
                )
            )

        # Order roots — respect custom order list if set, else DEFAULT_ROOT_ORDER
        custom_root_order = self.db.zone_display_order or []
        if custom_root_order:
            seen_r = set()
            ordered_roots = [
                z for z in custom_root_order
                if z in zones and zones[z].get("parent") is None
                and (seen_r.add(z) or True)
            ]
            for z in roots:
                if z not in seen_r:
                    ordered_roots.append(z)
                    seen_r.add(z)
        else:
            seen_r = set()
            ordered_roots = []
            for z in DEFAULT_ROOT_ORDER:
                if z in zones:
                    ordered_roots.append(z)
                    seen_r.add(z)
            for z in roots:
                if z not in seen_r:
                    ordered_roots.append(z)

        # Depth-first walk
        result = []

        def _walk(name):
            result.append(name)
            for child in children_map.get(name, []):
                _walk(child)

        for root in ordered_roots:
            _walk(root)

        return result

    def _is_covered_by_ancestor(self, zone_name, zones):
        """
        Walk the parent chain and return True if any ancestor
        has a covered_by set (i.e. is wearing something).

        This is what makes hierarchy work for rendering:
        wearing 'torso' hides 'chest', 'breast', 'nipple', etc.

        Args:
            zone_name (str): Zone to start the walk from.
            zones (dict): Current zone dict (from _get_zones()).

        Returns:
            bool: True if any ancestor is covered.
        """
        visited = set()
        current = zone_name
        while True:
            zdata = zones.get(current, {})
            parent = zdata.get("parent")
            if not parent or parent not in zones:
                return False
            if parent in visited:
                return False    # circular reference guard
            visited.add(parent)
            if zones[parent].get("covered_by"):
                return True
            current = parent

    def _zone_depth(self, zone_name, zones):
        """
        Return the depth of a zone in the tree (0 = root).
        Used for indented display.

        Args:
            zone_name (str): Zone to measure.
            zones (dict): Current zone dict.

        Returns:
            int: Depth from root.
        """
        depth = 0
        current = zone_name
        visited = set()
        while True:
            zdata = zones.get(current, {})
            parent = zdata.get("parent")
            if not parent or parent not in zones:
                return depth
            if parent in visited:
                return depth
            visited.add(parent)
            depth += 1
            current = parent

    def add_zone(self, name, intimate=False,
                 visibility="look", desc="",
                 zone_type="surface",
                 consent_required="casual",
                 parent=None):
        """
        Add a freeform zone to this character.

        Supports path syntax: 'chest/breast/nipple' will create 'nipple'
        as a child of 'breast' (which must already exist), or create
        the full path if intermediate zones are also being added.

        The 'name' argument here should already be the leaf zone name
        (path splitting is handled by _zone_add in character_commands.py).

        Args:
            name (str): Zone name (leaf only, no slashes).
            intimate (bool): Whether zone is intimate when nude.
            visibility (str): Default visibility level.
            desc (str): Initial nude description.
            zone_type (str): surface/orifice/both/attachment
            consent_required (str): Minimum consent for interaction.
            parent (str|None): Parent zone name, or None for root.

        Returns:
            bool: True if added, False if already exists.
        """
        zones = self._get_zones()
        name = name.lower().replace(" ", "_")

        if name in zones:
            return False

        zones[name] = {
            "parent":           parent,
            "nude":             desc,
            "covered_by":       None,
            "interior":         "",
            "contents":         [],
            "state":            "pristine",
            "state_desc":       None,
            "state_ambient":    [],
            "visibility":       visibility,
            "intimate":         intimate,
            "zone_type":        zone_type,
            "consent_required": consent_required,
            "default":          False,
            "freeform":         True,
            "ambient":          [],
        }
        self.db.zones = zones
        return True

    def remove_zone(self, name, cascade=False):
        """
        Remove a freeform zone. Default zones cannot be removed.

        If the zone has children, removal is blocked unless cascade=True,
        in which case all descendants are removed recursively.

        Args:
            name (str): Zone name.
            cascade (bool): If True, also remove all child zones.

        Returns:
            (bool, str|list):
                (True, [removed_names]) on success.
                (False, error_str) on failure.
        """
        zones = self._get_zones()
        name = name.lower().replace(" ", "_")

        if name not in zones:
            return False, f"No zone named '{name}'."

        if zones[name].get("default", False):
            return False, f"Cannot remove default zone '{name}'."

        # Find all descendants
        def _descendants(zname):
            kids = [
                z for z, zd in zones.items()
                if zd.get("parent") == zname
            ]
            result = list(kids)
            for k in kids:
                result.extend(_descendants(k))
            return result

        children = _descendants(name)

        if children and not cascade:
            return False, (
                f"Zone '{name}' has {len(children)} child zone(s): "
                f"{', '.join(children)}.\n"
                f"Use zone remove/cascade to remove it and all children."
            )

        # Remove the zone and all descendants
        to_remove = [name] + children
        for zname in to_remove:
            if zname in zones:
                del zones[zname]

        self.db.zones = zones

        # Clean up custom order
        order = self.db.zone_display_order or []
        changed = False
        for zname in to_remove:
            if zname in order:
                order.remove(zname)
                changed = True
        if changed:
            self.db.zone_display_order = order

        return True, to_remove

    def set_zone_desc(self, zone_name, desc):
        """
        Set the nude description for a zone.

        Args:
            zone_name (str): Zone to set.
            desc (str): Description text.

        Returns:
            bool: True if set, False if zone not found.
        """
        zones = self._get_zones()
        zone_name = zone_name.lower().replace(" ", "_")

        if zone_name not in zones:
            return False

        zones[zone_name]["nude"] = desc
        self.db.zones = zones
        return True

    def set_zone_interior(self, zone_name, desc):
        """
        Set the interior description for an orifice or both zone.

        The interior description is shown only on deep examine with
        mature consent, or when a womb-room item renders this zone
        as an enterable interior space.

        Args:
            zone_name (str): Zone to set.
            desc (str): Interior description text.

        Returns:
            bool: True if set, False if zone not found or wrong type.
        """
        zones = self._get_zones()
        zone_name = zone_name.lower().replace(" ", "_")

        if zone_name not in zones:
            return False

        zone_type = zones[zone_name].get("zone_type", "surface")
        if zone_type not in ("orifice", "both"):
            return False

        zones[zone_name]["interior"] = desc
        self.db.zones = zones
        return True

    def _expand_zone_tokens(self, zone_name: str, zone_data: dict, text: str) -> str:
        """
        Expand dynamic tokens in a zone description string at render time.

        Supported tokens
        ────────────────
        {size}      Body mod display label (cup size, length label, etc.)
        {circ}      Circumference in inches — shaft zones only
        {length}    Length in inches — shaft zones only
        {vol}       Current milk volume (breast) or per-testicle volume (testes)
        {diam}      Diameter — testes zones only
        {inflation} Current inflation state label (empty/slight/notable/full/overfull)

        Examples
        ────────
        zone set chest/left = Her breast is {size}, heavy and warm. ({vol} inside)
        zone set groin/cock = {size} and {circ} around, {length} long.
        zone set groin/balls = {size}, each one carrying {vol} — {diam} across.
        zone set groin/pussy = She is {inflation} with what was left inside her.
        """
        if not text or "{" not in text:
            return text

        mechanics = zone_data.get("mechanics") or {}

        # ── Body mod tokens ───────────────────────────────────────────────
        body_mod = mechanics.get("body_mod")
        if body_mod and any(t in text for t in
                            ("{size}", "{circ}", "{length}", "{vol}", "{diam}")):
            mod_type = body_mod.get("mod_type", "breast")
            size     = float(body_mod.get("size", 0.0))

            # Prefer live effective size from item object
            item_dbref = body_mod.get("item_dbref")
            if item_dbref:
                try:
                    from evennia import search_object
                    res = search_object(item_dbref, exact=True)
                    if res:
                        size     = res[0].effective_size()
                        mod_type = res[0].db.mod_type or mod_type
                except Exception:
                    pass

            if "{size}" in text:
                from typeclasses.body_mod_item import _DISPLAY_FUNCS, _breast_display
                fn   = _DISPLAY_FUNCS.get(mod_type, _breast_display)
                text = text.replace("{size}", fn(size))

            if "{circ}" in text or "{length}" in text:
                from typeclasses.body_mod_item import get_shaft_measurements
                circ, length = get_shaft_measurements(mod_type, size)
                text = text.replace("{circ}", circ).replace("{length}", length)

            if "{vol}" in text:
                from typeclasses.body_mod_item import (
                    get_testicle_volume_ml, format_body_volume
                )
                if mod_type == "testicle":
                    vol_str = format_body_volume(get_testicle_volume_ml(size))
                elif mod_type == "breast":
                    # Live milk volume from production item
                    prod = mechanics.get("production") or {}
                    vol_str = "empty"
                    prod_dbref = prod.get("item_dbref")
                    if prod_dbref:
                        try:
                            from evennia import search_object
                            from typeclasses.production_item import format_volume
                            res = search_object(prod_dbref, exact=True)
                            if res:
                                vol_str = format_volume(
                                    res[0].db.current_volume_ml or 0.0
                                )
                        except Exception:
                            pass
                else:
                    vol_str = ""
                text = text.replace("{vol}", vol_str)

            if "{diam}" in text:
                from typeclasses.body_mod_item import get_testicle_diam_str
                if mod_type == "testicle":
                    text = text.replace("{diam}", get_testicle_diam_str(size))
                else:
                    text = text.replace("{diam}", "")

        # ── Inflation token ───────────────────────────────────────────────
        if "{inflation}" in text:
            inflation = mechanics.get("inflation") or {}
            if inflation:
                try:
                    from typeclasses.inflation_item import get_inflation_state
                    vol = float(inflation.get("volume_ml", 0.0) or 0.0)
                    mx  = float(inflation.get("max_volume_ml", 500.0) or 500.0)
                    state = get_inflation_state(vol, mx)
                except Exception:
                    state = "empty"
            else:
                state = ""
            text = text.replace("{inflation}", state)

        return text

    def get_zone_display(self, zone_name, looker=None,
                         deep=False, proximity=False):
        """
        Get the display text for a zone, checking visibility
        and consent rules.

        For surface/attachment zones: returns covered_by or nude desc.
        For orifice zones: returns contents list.
        For both zones: returns covered_by and contents.

        Args:
            zone_name (str): Zone to display.
            looker: Character doing the looking. None for self.
            deep (bool): Whether this is a deep examine.
            proximity (bool): Whether looker is at proximity.

        Returns:
            dict: {
                "surface": str or None,
                "contents": list or None,
                "visible": bool,
            }
        """
        zones = self._get_zones()
        zone_name = zone_name.lower().replace(" ", "_")

        if zone_name not in zones:
            return {"surface": None, "contents": None,
                    "visible": False}

        zone = zones[zone_name]
        visibility = zone.get("visibility", "look")
        intimate = zone.get("intimate", False)
        zone_type = zone.get("zone_type", "surface")
        consent_req = zone.get("consent_required", "casual")

        # Check visibility level
        if visibility == "hidden":
            return {"surface": None, "contents": None,
                    "visible": False}
        if visibility == "deep" and not deep:
            return {"surface": None, "contents": None,
                    "visible": False}
        if visibility == "proximity" and not proximity:
            return {"surface": None, "contents": None,
                    "visible": False}
        if (visibility == "examine" and
                not (deep or proximity)):
            return {"surface": None, "contents": None,
                    "visible": False}

        is_self = looker == self

        # Check ancestor coverage — if a parent zone is wearing something,
        # this zone is hidden underneath and should not be shown.
        if self._is_covered_by_ancestor(zone_name, zones):
            return {"surface": None, "contents": None,
                    "visible": False}

        # Check consent for intimate zones when nude
        covered = zone.get("covered_by")
        if not covered and intimate and not is_self:
            if not self._looker_has_consent(
                looker, "intimate", zone_name=zone_name
            ):
                return {"surface": None, "contents": None,
                        "visible": False}

        # Check consent for orifice content
        # Orifice contents always require at least intimate
        contents = zone.get("contents", [])
        visible_contents = []
        if contents and not is_self:
            # Safe level comparison — avoids ValueError crash
            # if an unexpected string ends up in consent_req
            req_idx = (
                CONSENT_LEVELS.index(consent_req)
                if consent_req in CONSENT_LEVELS
                else 0
            )
            intimate_idx = CONSENT_LEVELS.index("intimate")
            required = CONSENT_LEVELS[
                max(req_idx, intimate_idx)
            ]
            if self._looker_has_consent(
                looker, required, zone_name=zone_name
            ):
                visible_contents = contents
        elif is_self:
            visible_contents = contents

        # Build surface result
        surface = None
        if zone_type in ("surface", "both", "attachment"):
            if covered:
                surface = covered.get(
                    "worn_desc",
                    covered.get("desc", "")
                )
            else:
                nude = zone.get("nude", "")
                if nude:
                    surface = self._expand_zone_tokens(zone_name, zone, nude)

        return {
            "surface":  surface,
            "contents": visible_contents,
            "visible":  True,
        }

    def _looker_has_consent(self, looker, content_type,
                            zone_name=None):
        """
        Check if a looker has consent to view content_type on
        this character.

        Two conditions must both be true:
          1. The looker has opted into this content type themselves
             (they've turned it on in their own settings).
          2. The subject (self) has made this content available —
             either globally via their own consent_flags, or via a
             specific grant to the looker in consent_grants, or via
             a per-zone grant in zone_consent_grants.

        Args:
            looker: Character doing the looking.
            content_type (str): Required consent level.
            zone_name (str): Optional zone being accessed.
                             Enables per-zone grant checks.

        Returns:
            bool: True if looker has consent.
        """
        if not looker:
            return False

        # Self always has access to their own content
        if looker == self:
            return True

        # --- Condition 1: Looker must have opted in themselves ---
        looker_account = (
            looker.account
            if hasattr(looker, 'account')
            else None
        )
        if not looker_account:
            return False

        looker_flags = looker_account.db.consent_flags or {}
        if not looker_flags.get(content_type, False):
            return False

        # --- Condition 2: Subject must have granted access ---

        # Check per-zone grant first (most specific)
        if zone_name:
            zone_grants = self.db.zone_consent_grants or {}
            granted = zone_grants.get(zone_name, set())
            if looker.id in granted:
                return True

        # Check specific per-action grant to this looker
        grants = self.db.consent_grants or {}
        if looker.id in grants.get(content_type, set()):
            return True

        # Check subject's own character-level consent flag
        # (they've globally opened this content type to anyone
        #  who has also opted in)
        char_flags = self.db.consent_flags or {}
        if char_flags.get(content_type, False):
            return True

        # Check subject's account-level consent flag
        subject_account = (
            self.account
            if hasattr(self, 'account')
            else None
        )
        if subject_account:
            acct_flags = subject_account.db.consent_flags or {}
            if acct_flags.get(content_type, False):
                return True

        return False

    def place_on_zone(self, zone_name, descriptor,
                      worn_desc=None, examine_desc=None,
                      ambient=None, set_by=None):
        """
        Place a freeform descriptor on a surface/attachment zone.
        Writes to covered_by.

        Args:
            zone_name (str): Zone to cover.
            descriptor (str): The description of what's being placed.
            worn_desc (str): Short worn description. Defaults to descriptor.
            examine_desc (str): Detailed examine description.
            ambient (list): Ambient lines for this item.
            set_by: Character ID who applied this.

        Returns:
            bool: True if placed, False if zone not found or wrong type.
        """
        zones = self._get_zones()
        zone_name = zone_name.lower().replace(" ", "_")

        if zone_name not in zones:
            return False

        zone = zones[zone_name]
        zone_type = zone.get("zone_type", "surface")

        if zone_type == "orifice":
            return False
        # Use insert_into_zone for orifice zones

        zone["covered_by"] = {
            "desc":         descriptor,
            "worn_desc":    worn_desc or descriptor,
            "examine_desc": examine_desc or "",
            "ambient":      ambient or [],
            "state":        "pristine",
            "state_desc":   None,
            "state_ambient":[],
            "type":         "freeform",
            "item_id":      None,
            "set_by":       set_by,
        }
        self.db.zones = zones
        self._rebuild_outfit_desc()
        return True

    def insert_into_zone(self, zone_name, descriptor,
                         examine_desc=None, ambient=None,
                         state="inserted", set_by=None,
                         removable_by=None):
        """
        Insert a freeform descriptor into an orifice zone.
        Appends to contents list.

        Args:
            zone_name (str): Zone to insert into.
            descriptor (str): Description of what's being inserted.
            examine_desc (str): Detailed examine description.
            ambient (list): Ambient lines.
            state (str): Current state of the insertion.
            set_by: Character ID who applied this.
            removable_by (list): Character IDs who can remove.

        Returns:
            bool: True if inserted, False if zone not found or wrong type.
        """
        zones = self._get_zones()
        zone_name = zone_name.lower().replace(" ", "_")

        if zone_name not in zones:
            return False

        zone = zones[zone_name]
        zone_type = zone.get("zone_type", "surface")

        if zone_type == "surface":
            return False
        # Use place_on_zone for surface zones

        contents = zone.get("contents", [])
        contents.append({
            "desc":         descriptor,
            "examine_desc": examine_desc or "",
            "ambient":      ambient or [],
            "state":        state,
            "set_by":       set_by,
            "removable_by": removable_by or [],
        })
        zone["contents"] = contents
        self.db.zones = zones
        return True

    def remove_from_zone(self, zone_name, index=None):
        """
        Remove the surface covering from a zone,
        or remove a specific contents item from an orifice zone.

        Args:
            zone_name (str): Zone to clear.
            index (int): For orifice zones, which item to remove.
                         None removes all contents or clears surface.

        Returns:
            bool: True if removed, False if zone not found.
        """
        zones = self._get_zones()
        zone_name = zone_name.lower().replace(" ", "_")

        if zone_name not in zones:
            return False

        zone = zones[zone_name]
        zone_type = zone.get("zone_type", "surface")

        if zone_type in ("surface", "attachment", "both"):
            if zone.get("covered_by"):
                zone["covered_by"] = None
                zone["state"] = "pristine"
                zone["state_desc"] = None
                self.db.zones = zones
                self._rebuild_outfit_desc()
                return True

        if zone_type in ("orifice", "both"):
            contents = zone.get("contents", [])
            if index is None:
                zone["contents"] = []
            elif 0 <= index < len(contents):
                contents.pop(index)
                zone["contents"] = contents
            else:
                return False
            self.db.zones = zones
            return True

        return False

    def _rebuild_outfit_desc(self):
        """
        Rebuild the outfit description from current zone states.
        Iterates zones in display order.
        Only includes surface/attachment/both zones with covered_by.
        Orifice contents do not appear in outfit layer.
        """
        if self.db.outfit_desc_override:
            return

        zones = self._get_zones()
        covered_parts = []

        for zone_name in self.get_zone_order():
            if zone_name not in zones:
                continue

            zone_data = zones[zone_name]
            zone_type = zone_data.get("zone_type", "surface")

            # Only surface/attachment/both contribute to outfit
            if zone_type == "orifice":
                continue

            # Skip zones hidden under an ancestor's clothing
            if self._is_covered_by_ancestor(zone_name, zones):
                continue

            covered = zone_data.get("covered_by")
            if not covered:
                continue

            worn_desc = covered.get(
                "worn_desc",
                covered.get("desc", "")
            )
            if not worn_desc:
                continue

            state = covered.get("state", "pristine")
            if state != "pristine":
                state_desc = covered.get("state_desc", "")
                if state_desc:
                    worn_desc = f"{worn_desc} — {state_desc}"
                else:
                    worn_desc = f"{worn_desc} ({state})"

            covered_parts.append(worn_desc)

        self.db.outfit_desc = ", ".join(covered_parts)
        self.db.dressed = bool(covered_parts)

    # -------------------------------------------------------------------
    # Title system
    # -------------------------------------------------------------------

    def get_full_title(self):
        """
        Assemble the full title from all five components.

        Returns:
            str: Full assembled title, or empty string.
        """
        parts = []

        prefix = self.db.title_prefix or ""
        level = self.db.title_level or ""
        interfix = self.db.title_interfix or ""
        faction = self.db.title_faction or ""
        suffix = self.db.title_suffix or ""

        if prefix:
            parts.append(prefix)
        if level:
            parts.append(level)
        if interfix:
            parts.append(interfix)
        if faction:
            parts.append(faction)
        if suffix:
            parts.append(suffix)

        return " ".join(parts)

    def get_reputation_tier(self):
        """
        Get the reputation tier name based on current score.

        Returns:
            str: Tier name.
        """
        rep = self.db.reputation or 0
        tier_name = "Unknown"

        for threshold, name in REPUTATION_TIERS:
            if rep >= threshold:
                tier_name = name

        self.db.title_level = tier_name
        return tier_name

    # -------------------------------------------------------------------
    # Main appearance assembly
    # -------------------------------------------------------------------

    def return_appearance(self, looker, **kwargs):
        """
        Assemble character appearance for look and examine.

        LOOK layers (always available):
          1   Name + title
          2   Species + apparent age
          3   Core description (physical_desc)
          4   Outfit summary
          5   Body language
          6   Mood tell
          7   State tells (restraints, lead)
          8   Markings — visibility-gated per marking
          9   Scent — proximity (near/with) only
          10  Intimate — proximity + mature consent

        EXAMINE additional layers (deep_examine=True):
          E1  Outfit details per zone
          E2  Proximity tell
          E3  Voice
          E4  Touch — proximity + intimate consent
          E5  Zone details (orifice zone contents)
          E6  Relationship-specific desc

        RP Hooks and bio live on the sheet, not here.

        Args:
            looker: Character doing the looking.
            deep_examine (bool): kwarg — examine command.
            proximity (bool): kwarg — explicit proximity override.

        Returns:
            str: Assembled appearance string.
        """
        deep = kwargs.get("deep_examine", False)
        is_self = looker == self

        # Zones referenced as tokens in physical_desc — these are shown
        # inline and must not appear again in the outfit layer.
        _tokenized = set(
            _ZONE_TOKEN_RE.findall(self.db.physical_desc or "")
        )
        pronouns = self.db.pronouns or {}
        _possessive = pronouns.get("possessive", "their")

        # --- Auto-detect proximity from both proximity dicts ---
        proximity = kwargs.get("proximity", False)
        if not proximity and looker and not is_self:
            prox = self.db.proximity or {}
            for pid, plevel in prox.items():
                try:
                    if int(pid) == looker.id and plevel in ("near", "with"):
                        proximity = True
                        break
                except (ValueError, TypeError):
                    pass
            if not proximity and hasattr(looker, 'db'):
                looker_prox = looker.db.proximity or {}
                for pid, plevel in looker_prox.items():
                    try:
                        if int(pid) == self.id and plevel in ("near", "with"):
                            proximity = True
                            break
                    except (ValueError, TypeError):
                        pass

        parts = []
        sep = "|w" + ("─" * 44) + "|n"

        # --- Layer 1: Name + title ---
        name = self.db.rp_name or self.key
        title = self.get_full_title()
        if title:
            parts.append(f"|w{name}|n  |x{title}|n")
        else:
            parts.append(f"|w{name}|n")
        parts.append(sep)

        # --- Layer 2: Species + apparent age ---
        species = self.db.species or ""
        age = self.db.apparent_age or ""
        if species or age:
            if species and age:
                parts.append(f"|x{species}  {age}|n")
            else:
                parts.append(f"|x{species or age}|n")
            parts.append("")

        # --- Layer 3: Core description ---
        physical = self.db.physical_desc or ""
        if physical:
            from world.freeform_manager import render_zone_tokens
            physical = render_zone_tokens(physical, self)
            parts.append(physical)

        # --- Layer 5: Body language ---
        body = self.db.body_language or ""
        if body:
            parts.append("")
            parts.append(f"|wBearing:|n {body}")

        # --- Layer 6: Mood tell ---
        mood_tell = self.db.mood_tell or ""
        mood = self.db.mood or ""
        if mood_tell:
            parts.append("")
            parts.append(f"|wMood:|n |x{mood_tell}|n")
        elif mood:
            parts.append("")
            parts.append(f"|wMood:|n |x({mood})|n")

        # --- Layer 7: State tells (restraints + lead) ---
        state_tells = []
        restraints = self.db.restraints or {}
        for zone_name, r_data in restraints.items():
            r_desc = r_data.get("desc", "")
            if r_desc:
                state_tells.append(f"|x{r_desc}|n")
        led_by_id = self.db.led_by
        if led_by_id:
            lead_desc = self.db.lead_desc or ""
            if lead_desc:
                state_tells.append(f"|x{lead_desc}|n")
            else:
                try:
                    from evennia import search_object
                    results = search_object(f"#{led_by_id}")
                    if results:
                        leader = results[0]
                        leader_name = leader.db.rp_name or leader.key
                        state_tells.append(
                            f"|xA leash connects them to {leader_name}.|n"
                        )
                except Exception:
                    pass
        if state_tells:
            parts.append("")
            parts.extend(state_tells)

        # --- Layer 8: Markings (visibility-gated per marking) ---
        markings = self.db.markings or []
        visible_markings = []
        for marking in markings:
            vis = marking.get("visibility", "examine")
            mark_intimate = marking.get("intimate", False)
            mark_visible = (
                vis == "look"
                or (vis == "examine" and deep)
                or (vis == "proximity" and proximity)
                or (vis == "deep" and deep)
            )
            if not mark_visible:
                continue
            if mark_intimate and not is_self:
                if not self._looker_has_consent(looker, "intimate"):
                    continue
            desc = marking.get("desc", "")
            if desc:
                visible_markings.append(desc)
        if visible_markings:
            parts.append("")
            for m in visible_markings:
                parts.append(f"|x{m}|n")

        # --- Layer 9: Scent (proximity only) ---
        if proximity:
            scent = self.db.scent_desc or ""
            if scent:
                parts.append("")
                parts.append(f"|xThere is something about them — {scent}.|n")

        # --- Layer 10: Intimate (proximity + mature consent) ---
        if proximity and not is_self:
            intimate_desc = self.db.intimate_desc or ""
            if intimate_desc and self._looker_has_consent(looker, "mature"):
                parts.append("")
                parts.append(intimate_desc)

        # ================================================================
        # EXAMINE-ONLY LAYERS (deep_examine=True)
        # ================================================================

        if deep:
            zones = self._get_zones()

            # --- E1: Voice ---
            voice = self.db.voice_desc or ""
            if voice:
                parts.append("")
                parts.append(f"|x{voice}|n")

            # --- E2: Outfit details per zone ---
            # Tokenized zones: show examine_desc if it differs from worn_desc
            #   (the token already showed worn_desc on look).
            # Non-tokenized zones: show "At/On/In her [zone], [examine_desc]"
            zone_lines = []
            for zone_name in self.get_zone_order():
                if zone_name not in zones:
                    continue
                # Hidden under a parent zone's clothing — skip
                if self._is_covered_by_ancestor(zone_name, zones):
                    continue
                zone_data = zones[zone_name]
                covered = zone_data.get("covered_by")
                if not covered:
                    continue
                examine = covered.get("examine_desc", "")
                worn = covered.get("worn_desc", covered.get("desc", ""))
                zone_type = zone_data.get("zone_type", "surface")
                zdisplay = zone_name.replace("_", " ")
                if zone_name in _tokenized:
                    # Only show if there's an examine_desc that adds detail
                    if examine and examine != worn:
                        zone_lines.append(
                            f"  |w{zdisplay}|n: {examine}"
                        )
                else:
                    # Non-tokenized: show with preposition
                    detail = examine or worn
                    if detail:
                        _prep = _zone_prep(zone_type).lower()
                        zone_lines.append(
                            f"  {_prep.capitalize()} {_possessive} "
                            f"{zdisplay}, {detail}"
                        )

            # Freeform items on examine
            freeform_examine = self.db.freeform_items or {}
            for _iname in sorted(freeform_examine.keys()):
                _idata = freeform_examine.get(_iname, {})
                _izone = _idata.get("zone", "?")
                _zdisplay = _izone.replace("_", " ")
                _mode = _idata.get("display_mode", "on")
                _mode_tag = " |x[in]|n" if _mode == "in" else ""
                _lock = _idata.get("lock")
                _lock_info = ""
                if _lock:
                    _ltype = _lock.get("type", "locked")
                    _lock_info = f" |r[{_ltype}]|n"
                _examine_desc = _idata.get(
                    "examine_desc", _idata.get("desc", "")
                )
                if _izone in _tokenized:
                    # Token already shows desc — just list item name + lock
                    zone_lines.append(
                        f"  |w{_zdisplay}|n: {_iname}"
                        f"{_mode_tag}{_lock_info}"
                    )
                else:
                    # Non-tokenized — show full examine desc
                    _iztype = zones.get(_izone, {}).get(
                        "zone_type", "surface"
                    )
                    _prep = _zone_prep(_iztype, mode=_mode).lower()
                    zone_lines.append(
                        f"  {_prep.capitalize()} {_possessive} "
                        f"{_zdisplay}, {_examine_desc or _iname}"
                        f"{_mode_tag}{_lock_info}"
                    )
            if zone_lines:
                parts.append("")
                parts.append(sep)
                parts.append("|xOn closer inspection:|n")
                parts.extend(zone_lines)

            # --- E3: Proximity tell ---
            if proximity:
                prox_tell = self.db.proximity_tell or ""
                if prox_tell:
                    parts.append("")
                    parts.append(prox_tell)

            # --- E4: Touch (proximity + intimate consent) --- (was E4, renumbered)
            if proximity:
                touch = self.db.touch_desc or ""
                if touch:
                    if is_self or self._looker_has_consent(looker, "intimate"):
                        parts.append("")
                        parts.append(touch)

            # --- E5: Zone contents + interior descs (orifice zones, consent-gated) ---
            orifice_lines = []
            for zone_name in self.get_zone_order():
                if zone_name not in zones:
                    continue
                zone_data = zones[zone_name]
                if zone_data.get("zone_type", "surface") not in ("orifice", "both"):
                    continue
                # Hidden under ancestor clothing — skip entirely
                if self._is_covered_by_ancestor(zone_name, zones):
                    continue
                has_consent = is_self or self._looker_has_consent(
                    looker, "intimate", zone_name=zone_name
                )
                zdisplay = zone_name.replace("_", " ")
                # Interior description — visible with mature consent at deep examine
                interior = zone_data.get("interior", "")
                if interior and (
                    is_self or self._looker_has_consent(
                        looker, "mature", zone_name=zone_name
                    )
                ):
                    orifice_lines.append(
                        f"|x[{zdisplay} — interior] {interior}|n"
                    )
                # Contents
                contents = zone_data.get("contents", [])
                if contents and has_consent:
                    for item in contents:
                        desc = item.get("desc", "")
                        if desc:
                            orifice_lines.append(
                                f"|x[{zdisplay}] {desc}|n"
                            )
            if orifice_lines:
                parts.append("")
                parts.extend(orifice_lines)

            # --- E6: Relationship-specific desc ---
            if not is_self and looker:
                contacts = self.db.contacts or {}
                contact = contacts.get(str(looker.id), {})
                rel_desc = contact.get("rel_desc", "")
                # Fall back to old relationship_descs for compatibility
                if not rel_desc:
                    rel_descs = self.db.relationship_descs or {}
                    rel_desc = rel_descs.get(str(looker.id), "")
                if rel_desc:
                    parts.append("")
                    parts.append(rel_desc)

        return "\n".join(parts)

    # -------------------------------------------------------------------
    # Ambient contribution
    # -------------------------------------------------------------------

    def get_character_ambient_lines(self):
        """
        Get all ambient lines this character contributes
        to the room's ambient pool.

        Returns:
            list: Ambient lines with character name substituted.
        """
        lines = []
        name = self.db.rp_name or self.key

        def _sub(text):
            return (
                text.replace("{name}", name)
                    .replace("{Name}", name.capitalize())
            )

        # Personal ambient pool
        for line in (self.db.ambient_contribution or []):
            lines.append(_sub(line))

        # Zone ambient lines
        zones = self._get_zones()
        for zone_name, zone_data in zones.items():
            covered = zone_data.get("covered_by")
            if covered:
                # State-specific ambient
                state = covered.get("state", "pristine")
                if state != "pristine":
                    item_desc = covered.get(
                        "worn_desc", zone_name
                    )
                    for line in covered.get(
                        "state_ambient", []
                    ):
                        lines.append(
                            _sub(line).replace(
                                "{zone_item}", item_desc
                            )
                        )

                # Item ambient lines
                for line in covered.get("ambient", []):
                    lines.append(_sub(line))

            else:
                # Nude zone ambient
                for line in zone_data.get("ambient", []):
                    lines.append(_sub(line))

            # Orifice contents ambient
            for item in zone_data.get("contents", []):
                for line in item.get("ambient", []):
                    lines.append(_sub(line))

        # Marking ambient lines
        for marking in (self.db.markings or []):
            for line in marking.get("ambient", []):
                lines.append(_sub(line))

        return lines

    # -------------------------------------------------------------------
    # Consent helpers
    # -------------------------------------------------------------------

    def has_consent(self, content_type):
        """
        Check if this character has consented to a content type.

        Args:
            content_type (str): Consent category to check.

        Returns:
            bool: True if consented.
        """
        char_flags = self.db.consent_flags or {}
        if char_flags.get(content_type, False):
            return True

        if self.account:
            acct_flags = self.account.db.consent_flags or {}
            return acct_flags.get(content_type, False)

        return False

    def grants_consent_to(self, other_char, action_type):
        """
        Check if this character grants consent to another
        for a specific action.

        Args:
            other_char: Character requesting consent.
            action_type (str): The action type.

        Returns:
            bool: True if granted.
        """
        grants = self.db.consent_grants or {}
        return other_char.id in grants.get(action_type, set())

    def grants_zone_consent_to(self, other_char, zone_name):
        """
        Check if this character has granted zone-specific
        consent to another character.

        Args:
            other_char: Character requesting access.
            zone_name (str): Zone being accessed.

        Returns:
            bool: True if granted.
        """
        zone_grants = self.db.zone_consent_grants or {}
        granted = zone_grants.get(zone_name, set())
        return other_char.id in granted

    def is_blocked(self, other_char):
        """
        Check if another character is blocked.

        Args:
            other_char: Character to check.

        Returns:
            bool: True if blocked.
        """
        return other_char.id in (self.db.block_list or set())

    # -------------------------------------------------------------------
    # Relationship helpers
    # -------------------------------------------------------------------

    def get_relationship(self, other_char):
        """Get relationship data with another character."""
        relationships = self.db.relationships or {}
        return relationships.get(str(other_char.id))

    def get_relationship_stage(self, other_char):
        """Get relationship stage with another character."""
        rel = self.get_relationship(other_char)
        if not rel:
            return "none"
        return rel.get("stage", "acquaintance")

    def add_shared_memory(self, other_char, memory_text):
        """
        Add a shared memory with another character.
        Adds to both characters' relationship records.
        """
        from evennia.utils import gametime
        memory = {
            "text":      memory_text,
            "timestamp": gametime.gametime(absolute=True),
        }

        relationships = self.db.relationships or {}
        other_id = str(other_char.id)
        if other_id not in relationships:
            relationships[other_id] = {
                "stage":              "acquaintance",
                "shared_memories":    [],
                "private_channel_id": None,
                "unlocked_emotes":    [],
                "rel_desc":           "",
            }
        relationships[other_id]["shared_memories"].append(memory)
        self.db.relationships = relationships

        other_rels = other_char.db.relationships or {}
        self_id = str(self.id)
        if self_id not in other_rels:
            other_rels[self_id] = {
                "stage":              "acquaintance",
                "shared_memories":    [],
                "private_channel_id": None,
                "unlocked_emotes":    [],
                "rel_desc":           "",
            }
        other_rels[self_id]["shared_memories"].append(memory)
        other_char.db.relationships = other_rels

    # -------------------------------------------------------------------
    # Dishevelment
    # -------------------------------------------------------------------

    def apply_dishevelment(self, zone_name,
                           state="dishevelled",
                           state_desc=None,
                           set_by="system"):
        """
        Apply a dishevelment state to a zone's surface covering.

        Returns:
            bool: True if applied.
        """
        zones = self._get_zones()
        zone_name = zone_name.lower().replace(" ", "_")

        if zone_name not in zones:
            return False

        covered = zones[zone_name].get("covered_by")
        if not covered:
            return False

        covered["state"] = state
        if state_desc:
            covered["state_desc"] = state_desc
        covered["state_set_by"] = set_by

        from evennia.utils import gametime
        covered["state_set_at"] = gametime.gametime(
            absolute=True
        )

        zones[zone_name]["covered_by"] = covered
        self.db.zones = zones
        self._rebuild_outfit_desc()
        return True

    def straighten(self, zone_name=None):
        """
        Reset dishevelment on a zone or all zones.

        Returns:
            list: Zone names that were reset.
        """
        zones = self._get_zones()
        reset = []

        def _reset(zname, zdata):
            covered = zdata.get("covered_by")
            if (covered and
                    covered.get("state", "pristine")
                    != "pristine"):
                covered["state"] = "pristine"
                covered["state_desc"] = None
                covered["state_ambient"] = []
                zdata["covered_by"] = covered
                reset.append(zname)

        if zone_name:
            zn = zone_name.lower().replace(" ", "_")
            if zn in zones:
                _reset(zn, zones[zn])
        else:
            for zn, zd in zones.items():
                _reset(zn, zd)

        if reset:
            self.db.zones = zones
            self._rebuild_outfit_desc()

        return reset

    # -------------------------------------------------------------------
    # Mood
    # -------------------------------------------------------------------

    @property
    def current_mood(self):
        """
        Get the character's current mood.
        Falls back to account wisp mood if carry is enabled.
        """
        char_mood = self.db.mood or ""
        if char_mood:
            return char_mood

        if self.db.wisp_mood_carry and self.account:
            return self.account.wisp_mood

        return ""

    # -------------------------------------------------------------------
    # Scene logging
    # -------------------------------------------------------------------

    def log_scene_participation(self, scene_title,
                                participants, duration,
                                room_name):
        """Add a scene to this character's history."""
        from evennia.utils import gametime
        history = self.db.scene_history or []

        history.append({
            "title":        scene_title,
            "participants": participants,
            "duration":     duration,
            "room":         room_name,
            "timestamp":    gametime.gametime(absolute=True),
        })

        if len(history) > 100:
            history = history[-100:]

        self.db.scene_history = history
        self.db.scene_count = (self.db.scene_count or 0) + 1

    # -------------------------------------------------------------------
    # Display helpers
    # -------------------------------------------------------------------

    def get_display_name(self, looker=None, **kwargs):
        """Return the display name for this character."""
        return self.db.rp_name or self.key

    def get_presence_line(self):
        """Get the short presence line for room listings."""
        name = self.db.rp_name or self.key
        presence = self.db.ic_presence or ""
        body = self.db.body_language or ""

        detail = presence or body
        if detail:
            return f"|w{name}|n is here. |x[{detail}]|n"
        else:
            return f"|w{name}|n is here."