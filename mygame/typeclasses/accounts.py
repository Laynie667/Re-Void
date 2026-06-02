"""
Account typeclass for Re:Void.

The Account represents the player behind the screen — their OOC identity,
wisp state, consent flags, preferences, and character roster.

Guests are disabled for this game — all players are invited members.
"""

from evennia.accounts.accounts import DefaultAccount
from evennia.utils import logger


class Account(DefaultAccount):
    """
    The Account is the OOC player entity. It exists outside the game world
    and puppets Characters to participate in it.

    When not puppeting a character, the player exists as a Wisp —
    a luminous, shapeless OOC presence that can move through the world
    invisibly (outside the Hub) or visibly (in the Hub, or when revealed).
    """

    def at_account_creation(self):
        """
        Called once when the account is first created.
        Sets all default values for wisp identity and account preferences.
        """
        super().at_account_creation()

        # ---------------------------------------------------------------
        # Wisp identity — the OOC self
        # ---------------------------------------------------------------
        self.db.wisp_mood = "uncertain"
        # None = use mood default from pool
        self.db.wisp_color = None
        # None = use system pool. Set to text to override.
        self.db.wisp_desc = None
        # small / medium / large / vast
        self.db.wisp_size = "medium"
        # None = use mood default. Set to text to override.
        self.db.wisp_movement = None
        # Persistent detail that appears regardless of mood.
        self.db.wisp_signature = None
        # Optional — what the wisp sounds like.
        self.db.wisp_sound = None
        # Player-written lines added to haunting pool.
        self.db.wisp_ambient_pool = []

        # ---------------------------------------------------------------
        # Wisp state — current runtime state
        # ---------------------------------------------------------------
        # The room the wisp is currently in when OOC.
        self.db.wisp_location = None
        # Whether haunting ambient lines are firing.
        self.db.wisp_haunt = False
        # Account IDs who can see this wisp regardless of their setting.
        self.db.wisp_revealed_to = set()
        # What this player sees: "hidden" or "visible" (all wisps).
        self.db.wisp_preference = "hidden"
        # Master visibility toggle for this wisp.
        self.db.wisp_visible = True

        # ---------------------------------------------------------------
        # Wisp display preferences
        # ---------------------------------------------------------------
        # "account" = show account name
        # "wisp_name" = show custom wisp name
        # "anonymous" = show color/mood only
        self.db.wisp_name_display = "account"
        # Used when wisp_name_display = "wisp_name"
        self.db.custom_wisp_name = None

        # ---------------------------------------------------------------
        # Tutorial tracking
        # ---------------------------------------------------------------
        self.db.tutorial_stage = 0
        self.db.tutorial_complete = False
        # Tracks which tutorial discovery moments have triggered.
        self.db.discoveries = set()

        # ---------------------------------------------------------------
        # Adult verification
        # Invitation-only game — all players are adults.
        # Field kept for records and the initial acknowledgment.
        # ---------------------------------------------------------------
        # Set to True after first-login acknowledgment.
        self.db.adult_verified = False
        # Timestamp of acknowledgment.
        self.db.adult_verified_at = None

        # ---------------------------------------------------------------
        # Consent flags
        # ---------------------------------------------------------------
        self.db.consent_flags = {
            "casual":      True,
            "intimate":    False,
            "mature":      False,
            "bdsm":        False,
            "lead_follow": False,
            "restraint":   False,
            "hardcore":    False,
        }
        # Specific per-account per-action grants.
        # Structure: {action_type: set(account_ids)}
        self.db.consent_grants = {}
        # Account IDs this player has blocked.
        self.db.block_list = set()

        # ---------------------------------------------------------------
        # Social
        # ---------------------------------------------------------------
        # Account IDs on this player's friends list.
        self.db.friends = set()
        # Whether to notify when friends log in.
        self.db.alert_on_friends = True
        # Whether to send email notifications.
        self.db.email_alerts = False

        # ---------------------------------------------------------------
        # Communication preferences
        # ---------------------------------------------------------------
        # Do not disturb — suppresses incoming tells.
        self.db.dnd = False
        # Words that get highlighted in output.
        self.db.highlight_keywords = []
        # Per-channel color overrides. {channel_name: color_code}
        self.db.channel_colors = {}
        # Types of output the player has suppressed.
        self.db.output_filters = set()
        # Player-written prompt template.
        self.db.custom_prompt = None
        # Channels the player has muted (stays subscribed, no output).
        self.db.muted_channels = set()
        # In-game mail inbox. List of dicts per comms_commands.py spec.
        self.db.mail_inbox = []

    def at_init(self):
        """Called every time the account object loads into memory."""
        super().at_init()

    def at_first_login(self, session=None, **kwargs):
        """
        Called the very first time this account logs in.
        Triggers the new player arrival sequence.
        """
        super().at_first_login(session=session, **kwargs)

    def at_post_login(self, session=None, **kwargs):
        """
        Called every time this account logs in.

        Skips Evennia's default OOC lobby entirely. Instead, places
        the wisp in the game world (START_LOCATION if no current
        location) and shows the room — so the player is immediately
        present as a navigable wisp, not stuck in a text menu.
        """
        # Announce connection to any staff/connect channel.
        self._send_to_connect_channel(f"|G{self.key} connected|n")

        saved = self.db.wisp_location

        if saved is None:
            # First-ever login — no location recorded yet.
            # Send the player to START_LOCATION (tutorial entry point).
            try:
                from django.conf import settings as django_settings
                from evennia import search_object
                start_dbref = getattr(
                    django_settings, 'START_LOCATION', '#2'
                )
                start = search_object(start_dbref, use_dbref=True)
                if start:
                    self.db.wisp_location = start[0]
            except Exception:
                pass
        else:
            # Returning player — validate that the saved room still exists.
            # If it was deleted, drop them in Limbo (#2) rather than
            # forcing them back through the tutorial start location.
            try:
                _ = saved.pk
            except Exception:
                try:
                    from evennia import search_object
                    limbo = search_object('#2', use_dbref=True)
                    self.db.wisp_location = limbo[0] if limbo else None
                except Exception:
                    self.db.wisp_location = None

        room = self.db.wisp_location
        color = self.wisp_color_code
        mood = self.wisp_mood

        self.msg(
            f"\n{color}[ wisp: {self.name} | mood: {mood} ]|n\n"
            f"|xYou drift into the world.|n"
        )

        if room:
            self.msg(self._build_wisp_room_view(room))
        else:
            self.msg(
                f"|xNo location found. "
                f"Type 'ic <name>' to enter a character.|n"
            )

        # Deliver any pending Ograms *after* the room renders.
        # The 2-second delay lets the room view (and any immediate IC puppet)
        # settle before the ogram notification appears as its own distinct message.
        try:
            from commands.ogram_commands import deliver_ograms
            from evennia.utils import delay
            delay(2, deliver_ograms, self)
        except Exception:
            pass

    def at_disconnect(self, reason=None, **kwargs):
        """
        Called when the account disconnects.
        Preserves wisp_location so the player returns to the same
        room on next login. Only clears per-session state like
        active reveal grants, which shouldn't persist across sessions.
        """
        super().at_disconnect(reason=reason, **kwargs)
        # Do NOT clear wisp_location — players should log back in
        # exactly where they logged out, just like characters do.
        self.db.wisp_revealed_to = set()

    def at_post_disconnect(self, **kwargs):
        """Called after disconnect cleanup is complete."""
        super().at_post_disconnect(**kwargs)

    def at_post_unpuppet(self, character, session=None, **kwargs):
        """
        Called on the Account after successfully unpuppeting a character.

        We suppress Evennia's default 'Account Overview' screen here —
        it's wrong for Re:Void. The CmdOOC command handles all output
        for the player (wisp transition message, state line, location).

        We keep the bookkeeping Evennia expects (_last_unpuppeted) but
        do not call super(), which is the line that sends the default screen.
        """
        # Keep track of last unpuppeted character for auto-reconnect logic.
        self.db._last_unpuppeted = character

    # -------------------------------------------------------------------
    # Wisp identity properties
    # -------------------------------------------------------------------

    @property
    def wisp_mood(self):
        """Current wisp mood. Always returns a string."""
        return self.db.wisp_mood or "uncertain"

    @property
    def wisp_color_display(self):
        """
        The wisp's current display color description.
        Returns custom color if set, otherwise mood default from pool.
        """
        if self.db.wisp_color:
            return self.db.wisp_color
        try:
            from world.pool_loader import load_pool
            pools = load_pool("wisp", "colors")
            mood_colors = pools.get("mood_colors", {})
            mood_data = mood_colors.get(self.wisp_mood, {})
            return mood_data.get("base", "pale light")
        except Exception:
            return "pale light"

    @property
    def wisp_color_code(self):
        """
        Get the ANSI color code for this wisp's current mood.
        Returns the code string e.g. '|y' for curious.
        Falls back to '|w' if mood not found.
        """
        # If player has set a custom color description we can't
        # map it to an ANSI code — return neutral white.
        if self.db.wisp_color:
            return "|w"
        try:
            from world.pool_loader import load_pool
            pools = load_pool("wisp", "colors")
            mood_colors = pools.get("mood_colors", {})
            mood_data = mood_colors.get(self.wisp_mood, {})
            return mood_data.get("code", "|w")
        except Exception:
            return "|w"

    @property
    def wisp_display_name(self):
        """
        The name shown for this wisp in room listings and WHO.
        Returns None for anonymous wisps.
        """
        pref = self.db.wisp_name_display or "account"
        if pref == "account":
            return self.name
        elif pref == "wisp_name" and self.db.custom_wisp_name:
            return self.db.custom_wisp_name
        else:
            return None

    # -------------------------------------------------------------------
    # Wisp appearance assembly
    # -------------------------------------------------------------------

    def get_wisp_appearance(self, looker=None, deep=False):
        """
        Assemble and return the wisp's full appearance string.
        Called when someone looks at this wisp.

        Args:
            looker: The character or account looking at this wisp.
            deep (bool): Whether this is a deep/close examine.

        Returns:
            str: The assembled appearance string.
        """
        import random
        from world.pool_loader import load_pool

        color = self.wisp_color_code

        # --- Base description ---
        if self.db.wisp_desc:
            base = self.db.wisp_desc
        else:
            pools = load_pool("wisp", "base")
            mood = self.wisp_mood
            mood_data = pools.get("states", {}).get(
                f"mood_{mood}",
                pools.get("states", {}).get("mood_neutral", {})
            )
            look_pool = mood_data.get("look", [])

            if look_pool:
                base = random.choice(look_pool)
            else:
                color_desc = self.wisp_color_display
                base = (
                    f"A wisp — {color_desc} light, shapeless, "
                    f"present in the way that light is present."
                )

        # --- Size modifier ---
        size = self.db.wisp_size or "medium"
        size_modifier = ""
        if size != "medium":
            try:
                size_pools = load_pool("wisp", "sizes")
                size_data = size_pools.get(size, {})
                size_modifier = size_data.get("desc_modifier", "")
            except Exception:
                pass

        # --- Signature ---
        signature = self.db.wisp_signature or ""

        # --- Sound ---
        sound = self.db.wisp_sound or ""

        # --- Assemble with color ---
        parts = [f"{color}{base}|n"]

        if size_modifier:
            parts.append(f"{color}{size_modifier}|n")

        if signature:
            parts.append(f"\n{color}{signature}|n")

        if sound and deep:
            parts.append(f"\n{color}{sound}|n")

        # --- Identity tag ---
        display_name = self.wisp_display_name
        mood = self.wisp_mood

        if display_name:
            tag = (
                f"\n\n|x[ {display_name} | OOC | "
                f"mood: {color}{mood}|n|x ]|n"
            )
        else:
            tag = f"\n\n|x[ OOC | mood: {color}{mood}|n|x ]|n"

        parts.append(tag)

        return "\n".join(parts)

    def get_wisp_presence_line(self):
        """
        Short one-line presence entry for room listings.

        Returns:
            str: Formatted presence line.
        """
        color = self.wisp_color_code
        color_desc = self.wisp_color_display
        mood = self.wisp_mood
        display_name = self.wisp_display_name

        if display_name:
            return (
                f"~ {color}{display_name}'s wisp|n "
                f"|x[ {color_desc} | OOC ]|n"
            )
        else:
            return (
                f"~ {color}a {mood} wisp|n "
                f"|x[ {color_desc} | OOC ]|n"
            )

    def get_wisp_ambient_lines(self):
        """
        Get this wisp's current ambient contribution pool.
        Combines mood-pool lines with player-written lines.
        All lines are colorized with the wisp's mood color.

        Returns:
            list: Lines available for ambient contribution.
        """
        from world.pool_loader import load_pool

        color = self.wisp_color_code
        mood = self.wisp_mood
        pools = load_pool("wisp", "base")
        mood_data = pools.get("states", {}).get(
            f"mood_{mood}", {}
        )
        system_lines = mood_data.get("ambient_contribution", [])
        personal_lines = self.db.wisp_ambient_pool or []
        combined = system_lines + personal_lines

        return [f"{color}{line}|n" for line in combined]

    def _build_wisp_room_view(self, room):
        """
        Build the room look output string for a wisp viewer.
        Used by at_post_login and CmdWispLook so both places show
        the same consistent view.

        Args:
            room: The Room object to view.

        Returns:
            str: Formatted room description for OOC/wisp viewing.
        """
        color = self.wisp_color_code
        sep = f"|x{'─' * 44}|n"
        lines = [f"\n|w{room.key}|n"]

        # Room description
        desc = room.db.desc or ""
        if desc:
            lines.append(f"\n{desc}")

        lines.append(f"\n{sep}")

        # IC characters present in the room
        try:
            from typeclasses.characters import Character
            chars = [
                obj for obj in room.contents
                if isinstance(obj, Character)
            ]
            if chars:
                lines.append("|wPresences here:|n")
                for char in chars:
                    name = (
                        char.db.rp_name
                        if hasattr(char.db, 'rp_name')
                        and char.db.rp_name
                        else char.key
                    )
                    body_lang = (
                        char.db.body_lang
                        if hasattr(char.db, 'body_lang')
                        and char.db.body_lang
                        else None
                    )
                    if body_lang:
                        lines.append(
                            f"  |w{name}|n |x— {body_lang}|n"
                        )
                    else:
                        lines.append(f"  |w{name}|n")
        except Exception:
            pass

        # Other wisps in the same room (based on viewer's wisp preference)
        try:
            from evennia import SESSION_HANDLER
            wisp_lines = []
            pref = self.db.wisp_preference or "hidden"
            for session in SESSION_HANDLER.get_sessions():
                acct = session.get_account()
                if not acct or acct == self or session.get_puppet():
                    continue
                if acct.db.wisp_location != room:
                    continue
                # Visible if: viewer prefers all wisps, or this wisp
                # has been specifically revealed to the viewer.
                if (pref == "visible" or
                        self.id in (acct.db.wisp_revealed_to or set())):
                    wisp_lines.append(
                        f"  {acct.get_wisp_presence_line()}"
                    )
            if wisp_lines:
                lines.append("|wWisps here:|n")
                lines.extend(wisp_lines)
        except Exception:
            pass

        lines.append(f"\n{sep}")

        # Exits
        exits = room.exits
        if exits:
            exit_names = [ex.key for ex in exits]
            lines.append(f"|wExits:|n  {' | '.join(exit_names)}")
        else:
            lines.append("|xNo obvious exits.|n")

        # OOC footer
        lines.append(
            f"\n|x[ OOC — mood: {color}{self.wisp_mood}|n|x ]|n"
        )

        return "\n".join(lines)

    # -------------------------------------------------------------------
    # Wisp visibility management
    # -------------------------------------------------------------------

    def reveal_to(self, target_account):
        """
        Make this wisp visible to a specific account.

        Args:
            target_account: Account object to reveal to.
        """
        revealed = self.db.wisp_revealed_to or set()
        revealed.add(target_account.id)
        self.db.wisp_revealed_to = revealed

    def conceal_from(self, target_account):
        """
        Remove revealed visibility for a specific account.

        Args:
            target_account: Account object to conceal from.
        """
        revealed = self.db.wisp_revealed_to or set()
        revealed.discard(target_account.id)
        self.db.wisp_revealed_to = revealed

    def is_visible_to(self, observer, room):
        """
        Check if this wisp is currently visible to a specific observer.

        Args:
            observer: Character object of the observer.
            room: Room object they're both in.

        Returns:
            bool: True if this wisp is visible to observer.
        """
        from world.wisp_visibility import WispVisibility
        return WispVisibility.wisp_visible_to(self, observer, room)

    # -------------------------------------------------------------------
    # Consent and access
    # -------------------------------------------------------------------

    def has_consent(self, content_type):
        """
        Check if this account has consented to a content type.

        Args:
            content_type (str): The consent category to check.

        Returns:
            bool: True if consented.
        """
        flags = self.db.consent_flags or {}
        return flags.get(content_type, False)

    def grant_consent(self, content_type, target_account=None):
        """
        Grant consent for a content type, optionally to a specific account.

        Args:
            content_type (str): The consent category.
            target_account: If provided, grants only to this account.
                            If None, grants globally.
        """
        if target_account is None:
            flags = self.db.consent_flags or {}
            flags[content_type] = True
            self.db.consent_flags = flags
        else:
            grants = self.db.consent_grants or {}
            if content_type not in grants:
                grants[content_type] = set()
            grants[content_type].add(target_account.id)
            self.db.consent_grants = grants

    def revoke_consent(self, content_type, target_account=None):
        """
        Revoke consent for a content type.

        Args:
            content_type (str): The consent category.
            target_account: If provided, revokes only for this account.
                            If None, revokes the global flag.
        """
        if target_account is None:
            flags = self.db.consent_flags or {}
            flags[content_type] = False
            self.db.consent_flags = flags
        else:
            grants = self.db.consent_grants or {}
            if content_type in grants:
                grants[content_type].discard(target_account.id)
                self.db.consent_grants = grants

    def is_blocked(self, other_account):
        """
        Check if another account is blocked by this one.

        Args:
            other_account: Account object to check.

        Returns:
            bool: True if blocked.
        """
        block_list = self.db.block_list or set()
        return other_account.id in block_list

    # -------------------------------------------------------------------
    # Account score / overview
    # -------------------------------------------------------------------

    def get_account_score(self):
        """
        Assemble and return the account score/overview string.

        Returns:
            str: Formatted account overview.
        """
        name = self.name
        mood = self.wisp_mood
        color = self.wisp_color_code
        color_desc = self.wisp_color_display
        wisp_desc_status = (
            "custom" if self.db.wisp_desc else "system pool"
        )

        # Character roster
        characters = (
            self.characters.all()
            if hasattr(self, 'characters')
            else []
        )
        char_lines = []
        for char in characters:
            char_lines.append(f"  |w{char.name}|n")
        char_display = (
            "\n".join(char_lines)
            if char_lines
            else "  [none yet]"
        )

        # Consent flags
        flags = self.db.consent_flags or {}
        consent_lines = []
        for flag, value in flags.items():
            status = "|gYES|n" if value else "|rno|n"
            consent_lines.append(
                f"  {flag.capitalize():<16}{status}"
            )
        consent_display = (
            "\n".join(consent_lines)
            if consent_lines
            else "  [none set]"
        )

        # Preferences
        dnd = "|gON|n" if self.db.dnd else "off"
        wisp_pref = self.db.wisp_preference or "hidden"
        highlights = len(self.db.highlight_keywords or [])

        sep = f"|w{'━' * 44}|n"

        output = (
            f"\n{sep}\n"
            f"|wACCOUNT:|n {name}\n"
            f"{sep}\n"
            f"\n"
            f"|wWisp|n\n"
            f"  Mood:        {color}{mood}|n\n"
            f"  Color:       {color}{color_desc}|n\n"
            f"  Description: {wisp_desc_status}\n"
            f"  Size:        {self.db.wisp_size or 'medium'}\n"
            f"  Haunt:       "
            f"{'|gon|n' if self.db.wisp_haunt else 'off'}\n"
            f"  Wisp pref:   {wisp_pref}\n"
            f"\n"
            f"|wCharacters|n\n"
            f"{char_display}\n"
            f"\n"
            f"|wConsent flags|n\n"
            f"{consent_display}\n"
            f"\n"
            f"|wPreferences|n\n"
            f"  DND:         {dnd}\n"
            f"  Highlights:  {highlights} keywords set\n"
            f"\n"
            f"{sep}\n"
        )

        return output