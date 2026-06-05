"""
commands/prefs_commands.py

Account and character preference commands for Re:Void.

Account-level commands (AccountCmdSet and CharacterCmdSet):
    prefs           -- master view of all active preferences
    dnd             -- do not disturb toggle (suppresses incoming tells)
    highlight / hl  -- keyword highlighting management
    filter          -- suppress / restore notification categories
    notify          -- friend login and email notification toggles
    friends         -- friends list management
    wispname        -- control how your wisp identity is labeled

Character-level commands (CharacterCmdSet only):
    afk             -- set / clear AFK status message
    moodcarry       -- toggle wisp mood carry-forward on login

Output filter categories:
    proximity   -- approach / withdraw notifications
    lead        -- lead tug / movement notifications
    ambient     -- room ambient tick messages
"""

from evennia.commands.default.muxcommand import MuxCommand


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _account(caller):
    """Resolve to the account object regardless of whether caller
    is a character or an account."""
    if hasattr(caller, 'account') and caller.account:
        return caller.account
    return caller


# Valid output filter categories
VALID_FILTERS = {
    "proximity": "Approach and withdraw notifications",
    "lead":      "Lead tug and movement notifications",
    "ambient":   "Room ambient tick messages",
}


# -------------------------------------------------------------------
# CmdPrefs  — master preferences view
# -------------------------------------------------------------------

class CmdPrefs(MuxCommand):
    """
    View all your active preference settings at a glance.

    Usage:
      prefs

    Shows DND, AFK, highlight keywords, output filters, notification
    settings, muted channels, mood carry, and friends list count.

    Use the individual commands to change each setting.

    See also: dnd, afk, highlight, filter, notify, friends, moodcarry
    """

    key = "prefs"
    locks = "cmd:all()"
    help_category = "Prefs"

    def func(self):
        caller = self.caller
        acct = _account(caller)
        sep = f"|w{'━' * 44}|n"

        # --- Account-level fields ---
        dnd = acct.db.dnd or False
        highlights = acct.db.highlight_keywords or []
        filters = acct.db.output_filters or set()
        alert_friends = acct.db.alert_on_friends
        if alert_friends is None:
            alert_friends = True
        muted = acct.db.muted_channels or set()
        friends = acct.db.friends or set()

        dnd_str = "|gON|n" if dnd else "off"
        hl_str = (
            f"{len(highlights)} keyword(s)"
            if highlights else "none"
        )
        filter_str = (
            ", ".join(sorted(filters)) if filters else "none"
        )
        muted_str = (
            ", ".join(sorted(muted)) if muted else "none"
        )
        af_str = "|gON|n" if alert_friends else "off"

        lines = [
            f"\n{sep}",
            f"|wPREFERENCES|n  {acct.name}",
            sep,
            f"  DND:             {dnd_str}",
            f"  Highlights:      {hl_str}",
            f"  Filters:         {filter_str}",
            f"  Muted channels:  {muted_str}",
            f"  Friend alerts:   {af_str}",
            f"  Friends:         {len(friends)} on list",
        ]

        # --- Wisp name display ---
        wisp_display = acct.db.wisp_name_display or "account"
        custom_name = acct.db.custom_wisp_name or ""
        wn_str = wisp_display
        if wisp_display == "wisp_name" and custom_name:
            wn_str = f"custom ({custom_name})"
        lines.append(f"  Wisp name:       {wn_str}")

        # --- Character-level fields (if IC) ---
        char = None
        if hasattr(caller, 'db') and hasattr(caller.db, 'wisp_mood_carry'):
            char = caller
        elif hasattr(acct, 'get_all_puppets'):
            puppets = acct.get_all_puppets()
            if puppets:
                char = puppets[0]

        if char:
            afk = char.db.afk_message or ""
            carry = char.db.wisp_mood_carry
            if carry is None:
                carry = True
            afk_str = f"|y{afk}|n" if afk else "off"
            carry_str = "|gON|n" if carry else "off"
            lines += [
                f"  AFK:             {afk_str}",
                f"  Mood carry:      {carry_str}",
            ]

        lines.append(sep)
        lines.append(
            "|xCommands: dnd / afk / highlight / filter / "
            "notify / friends / moodcarry / wispname|n"
        )

        self.msg("\n".join(lines))


# -------------------------------------------------------------------
# CmdDND  — do not disturb
# -------------------------------------------------------------------

class CmdDND(MuxCommand):
    """
    Toggle Do Not Disturb mode.

    When DND is on, incoming tells are blocked and the sender
    receives a brief notification. You can still send tells.
    Channels and pages are unaffected.

    Usage:
      dnd           -- see current status
      dnd on        -- enable
      dnd off       -- disable

    See also: prefs, filter, afk
    """

    key = "dnd"
    locks = "cmd:all()"
    help_category = "Prefs"

    def func(self):
        acct = _account(self.caller)
        current = acct.db.dnd or False

        if not self.args.strip():
            state = "|gON|n" if current else "off"
            self.msg(
                f"Do Not Disturb: {state}\n"
                "Use 'dnd on' or 'dnd off' to change."
            )
            return

        arg = self.args.strip().lower()
        if arg == "on":
            acct.db.dnd = True
            self.msg("DND |gon|n. Incoming tells are suppressed.")
        elif arg == "off":
            acct.db.dnd = False
            self.msg("DND off. You will receive tells normally.")
        else:
            self.msg("Usage: dnd on / dnd off")


# -------------------------------------------------------------------
# CmdAFK  — away from keyboard (character-level)
# -------------------------------------------------------------------

class CmdAFK(MuxCommand):
    """
    Set an away-from-keyboard message on your character.

    When you're AFK, anyone who sends you a tell receives an
    automatic reply with your message. The message also appears
    in your look description so nearby players know you're away.

    Usage:
      afk               -- see current AFK status
      afk <message>     -- set AFK with a message
      afk/clear         -- clear AFK status

    Examples:
      afk grabbing food, back in 10
      afk taking a break, check back in a bit
      afk/clear

    See also: dnd, prefs
    """

    key = "afk"
    locks = "cmd:all()"
    help_category = "Prefs"

    def func(self):
        caller = self.caller

        # Must be a character (has rp_name attribute)
        if not hasattr(caller.db, 'rp_name'):
            self.msg(
                "AFK is a character-level setting. "
                "Enter a character first with 'ic <name>'."
            )
            return

        if "clear" in self.switches:
            was = caller.db.afk_message
            caller.db.afk_message = None
            caller.db.afk_since = None
            self.msg("AFK cleared. Welcome back.")
            if was and caller.location:
                caller.location.msg_contents(
                    f"|x{caller.db.rp_name or caller.key} is back.|n", exclude=caller)
            return

        if not self.args.strip():
            current = caller.db.afk_message or ""
            if current:
                self.msg(
                    f"AFK: |y{current}|n\n"
                    "Use 'afk/clear' to remove (or just say/pose/move — it clears itself)."
                )
            else:
                self.msg(
                    "You are not AFK.\n"
                    "Use 'afk <message>' to set one."
                )
            return

        import time as _t
        caller.db.afk_message = self.args.strip()
        caller.db.afk_since = _t.time()
        self.msg(f"AFK set: |y{caller.db.afk_message}|n")
        if caller.location:
            caller.location.msg_contents(
                f"|x{caller.db.rp_name or caller.key} steps away — present, but not answering.|n",
                exclude=caller)


# -------------------------------------------------------------------
# CmdHighlight  — keyword highlighting
# -------------------------------------------------------------------

class CmdHighlight(MuxCommand):
    """
    Manage your keyword highlight list.

    Words in this list are highlighted in yellow when they appear
    in any incoming message — tells, poses, emotes, channel output.

    Usage:
      highlight                   -- list current keywords
      highlight add <word>        -- add a keyword
      highlight remove <#>        -- remove by number
      highlight clear             -- remove all keywords

    Examples:
      highlight add Seraphine
      highlight add your name
      highlight remove 2
      highlight clear

    Keywords are case-insensitive. Phrases work too.

    See also: prefs, filter
    """

    key = "highlight"
    aliases = ["hl"]
    locks = "cmd:all()"
    help_category = "Prefs"

    def func(self):
        acct = _account(self.caller)
        keywords = list(acct.db.highlight_keywords or [])
        args = self.args.strip()

        # No args — show list
        if not args:
            if not keywords:
                self.msg(
                    "No highlight keywords set.\n"
                    "Use: highlight add <word>"
                )
                return
            lines = ["|wHighlight keywords:|n\n"]
            for i, kw in enumerate(keywords, 1):
                lines.append(f"  {i}. |y{kw}|n")
            self.msg("\n".join(lines))
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "add":
            if not rest:
                self.msg("Add what? Usage: highlight add <word>")
                return
            if rest.lower() in [k.lower() for k in keywords]:
                self.msg(f"'{rest}' is already in your highlight list.")
                return
            keywords.append(rest)
            acct.db.highlight_keywords = keywords
            self.msg(f"Highlight added: |y{rest}|n")

        elif subcmd == "remove":
            if not rest:
                self.msg("Remove which? Usage: highlight remove <#>")
                return
            try:
                idx = int(rest) - 1
                if idx < 0 or idx >= len(keywords):
                    self.msg(
                        f"No item #{idx + 1}. "
                        f"You have {len(keywords)} keyword(s)."
                    )
                    return
                removed = keywords.pop(idx)
                acct.db.highlight_keywords = keywords
                self.msg(f"Removed: {removed}")
            except ValueError:
                self.msg(
                    "Please provide a number.\n"
                    "Usage: highlight remove <#>"
                )

        elif subcmd == "clear":
            acct.db.highlight_keywords = []
            self.msg("Highlight list cleared.")

        else:
            self.msg(
                "Usage:\n"
                "  highlight add <word>\n"
                "  highlight remove <#>\n"
                "  highlight clear"
            )


# -------------------------------------------------------------------
# CmdFilter  — output filters
# -------------------------------------------------------------------

class CmdFilter(MuxCommand):
    """
    Suppress or restore specific notification categories.

    Filtered categories are silenced — you won't see those messages.
    Useful for quieting approach pings during active scenes.

    Usage:
      filter                     -- list all categories and status
      filter add <category>      -- suppress a category
      filter remove <category>   -- restore a category

    Categories:
      proximity   -- approach and withdraw notifications
      lead        -- lead tug and movement notifications
      ambient     -- room ambient tick messages

    Examples:
      filter add proximity
      filter add ambient
      filter remove proximity
      filter

    See also: prefs, dnd
    """

    key = "filter"
    locks = "cmd:all()"
    help_category = "Prefs"

    def func(self):
        acct = _account(self.caller)
        active = set(acct.db.output_filters or set())
        args = self.args.strip()

        # No args — show all categories
        if not args:
            sep = f"|w{'─' * 40}|n"
            lines = [f"\n{sep}", "|wOutput filters|n", sep]
            for cat, desc in sorted(VALID_FILTERS.items()):
                is_on = cat in active
                status = "|ysuppressed|n" if is_on else "|gactive|n   "
                lines.append(f"  {status}  |w{cat}|n — {desc}")
            lines.append(sep)
            lines.append("|xUse 'filter add <category>' to suppress.|n")
            self.msg("\n".join(lines))
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        cat = parts[1].strip().lower() if len(parts) > 1 else ""

        if subcmd == "add":
            if not cat:
                self.msg(
                    f"Add which filter? "
                    f"Valid: {', '.join(VALID_FILTERS)}"
                )
                return
            if cat not in VALID_FILTERS:
                self.msg(
                    f"'{cat}' is not a valid filter category.\n"
                    f"Valid: {', '.join(VALID_FILTERS)}"
                )
                return
            active.add(cat)
            acct.db.output_filters = active
            self.msg(f"|w{cat}|n notifications |ysuppressed|n.")

        elif subcmd == "remove":
            if not cat:
                self.msg(
                    f"Remove which filter? "
                    f"Valid: {', '.join(VALID_FILTERS)}"
                )
                return
            if cat not in VALID_FILTERS:
                self.msg(
                    f"'{cat}' is not a valid filter category.\n"
                    f"Valid: {', '.join(VALID_FILTERS)}"
                )
                return
            active.discard(cat)
            acct.db.output_filters = active
            self.msg(f"|w{cat}|n notifications |grestored|n.")

        else:
            self.msg(
                "Usage:\n"
                "  filter add <category>\n"
                "  filter remove <category>"
            )


# -------------------------------------------------------------------
# CmdNotify  — notification toggles
# -------------------------------------------------------------------

class CmdNotify(MuxCommand):
    """
    Manage notification toggles.

    Usage:
      notify                    -- show all notification settings
      notify friends on/off     -- alert when friends come online
      notify email on/off       -- email notifications (future)

    Examples:
      notify friends on
      notify email off

    See also: friends, prefs, dnd
    """

    key = "notify"
    locks = "cmd:all()"
    help_category = "Prefs"

    def func(self):
        acct = _account(self.caller)
        args = self.args.strip()

        if not args:
            alert_friends = acct.db.alert_on_friends
            if alert_friends is None:
                alert_friends = True
            email = acct.db.email_alerts or False

            af_str = "|gON|n" if alert_friends else "off"
            em_str = "|gON|n" if email else "off"

            self.msg(
                f"|wNotification settings:|n\n"
                f"  friends  {af_str}  "
                f"|x— alert when friends log on|n\n"
                f"  email    {em_str}  "
                f"|x— email alerts (future feature)|n\n\n"
                "Use: notify <setting> on/off"
            )
            return

        parts = args.split()
        if len(parts) < 2:
            self.msg("Usage: notify <setting> on/off")
            return

        setting = parts[0].lower()
        state_str = parts[1].lower()

        if state_str not in ("on", "off"):
            self.msg("State must be 'on' or 'off'.")
            return

        state = (state_str == "on")

        if setting == "friends":
            acct.db.alert_on_friends = state
            s = "|gon|n" if state else "off"
            self.msg(f"Friend login alerts: {s}")
        elif setting == "email":
            acct.db.email_alerts = state
            s = "|gon|n" if state else "off"
            self.msg(f"Email alerts: {s}")
        else:
            self.msg(
                f"Unknown setting '{setting}'.\n"
                "Valid: friends / email"
            )


# -------------------------------------------------------------------
# CmdFriends  — friends list management
# -------------------------------------------------------------------

class CmdFriends(MuxCommand):
    """
    Manage your friends list.

    Friends are tracked by account name. When a friend comes online
    you can receive a notification (see: notify friends).

    Usage:
      friends                  -- list friends and their online status
      friends add <name>       -- add an account to your list
      friends remove <name>    -- remove from your list

    Examples:
      friends add Ara
      friends remove Seraphine
      friends

    See also: notify, wping, prefs
    """

    key = "friends"
    locks = "cmd:all()"
    help_category = "Prefs"

    def func(self):
        acct = _account(self.caller)
        args = self.args.strip()

        # No args — show list
        if not args:
            friends = set(acct.db.friends or set())
            if not friends:
                self.msg(
                    "Your friends list is empty.\n"
                    "Use: friends add <name>"
                )
                return

            from evennia import search_account
            lines = [f"|wFriends ({len(friends)}):|n\n"]
            for fid in list(friends):
                try:
                    results = search_account(f"#{fid}")
                    if results:
                        f_acct = (
                            results[0]
                            if isinstance(results, list)
                            else results
                        )
                        online = f_acct.sessions.count() > 0
                        status = "|gOnline|n " if online else "|xOffline|n"
                        lines.append(f"  {status}  {f_acct.name}")
                    else:
                        lines.append(
                            f"  |x[account unavailable #{fid}]|n"
                        )
                except Exception:
                    lines.append(f"  |x[error #{fid}]|n")
            self.msg("\n".join(lines))
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        target_name = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "add":
            if not target_name:
                self.msg("Add who? Usage: friends add <name>")
                return
            from evennia import search_account
            results = search_account(target_name)
            if not results:
                self.msg(f"No account named '{target_name}'.")
                return
            target = (
                results[0] if isinstance(results, list) else results
            )
            if target == acct:
                self.msg("You can't add yourself.")
                return
            friends = set(acct.db.friends or set())
            if target.id in friends:
                self.msg(f"{target.name} is already on your friends list.")
                return
            friends.add(target.id)
            acct.db.friends = friends
            self.msg(f"|w{target.name}|n added to friends list.")

        elif subcmd == "remove":
            if not target_name:
                self.msg("Remove who? Usage: friends remove <name>")
                return
            from evennia import search_account
            results = search_account(target_name)
            if not results:
                self.msg(f"No account named '{target_name}'.")
                return
            target = (
                results[0] if isinstance(results, list) else results
            )
            friends = set(acct.db.friends or set())
            if target.id not in friends:
                self.msg(f"{target.name} isn't on your friends list.")
                return
            friends.discard(target.id)
            acct.db.friends = friends
            self.msg(f"{target.name} removed from friends list.")

        else:
            self.msg(
                "Usage:\n"
                "  friends\n"
                "  friends add <name>\n"
                "  friends remove <name>"
            )


# -------------------------------------------------------------------
# CmdMoodCarry  — character-level
# -------------------------------------------------------------------

class CmdMoodCarry(MuxCommand):
    """
    Toggle whether your wisp's mood carries forward when you log
    into a character.

    When on (the default), if your wisp is 'curious' and your
    character has no mood set, they'll begin the session as 'curious'.
    When off, your character always starts with whatever mood was
    last set directly on them.

    Usage:
      moodcarry           -- see current setting
      moodcarry on        -- enable carry-forward
      moodcarry off       -- disable carry-forward

    See also: mood (wisp), prefs
    """

    key = "moodcarry"
    locks = "cmd:all()"
    help_category = "Prefs"

    def func(self):
        caller = self.caller

        # Must be IC
        if not hasattr(caller.db, 'wisp_mood_carry'):
            self.msg(
                "Mood carry is a character-level setting. "
                "Enter a character first with 'ic <name>'."
            )
            return

        if not self.args.strip():
            current = caller.db.wisp_mood_carry
            if current is None:
                current = True
            state = "|gON|n" if current else "off"
            self.msg(
                f"Mood carry: {state}\n"
                "|xWhen on, your wisp's mood fills your character's mood "
                "on login if no character mood is set.|n"
            )
            return

        arg = self.args.strip().lower()
        if arg == "on":
            caller.db.wisp_mood_carry = True
            self.msg("Mood carry |gon|n.")
        elif arg == "off":
            caller.db.wisp_mood_carry = False
            self.msg("Mood carry off.")
        else:
            self.msg("Usage: moodcarry on / moodcarry off")


# -------------------------------------------------------------------
# CmdWispName  — wisp identity label (account-level)
# -------------------------------------------------------------------

class CmdWispName(MuxCommand):
    """
    Control how your wisp is labeled when visible to others.

    Usage:
      wispname                      -- see current setting
      wispname account              -- show your account name (default)
      wispname custom <text>        -- show a custom wisp name
      wispname anonymous            -- show no identifying name

    When 'anonymous', others can see your wisp's mood and color
    but not your account name or any custom label.

    Examples:
      wispname custom The Pale Watcher
      wispname anonymous
      wispname account

    See also: wdesc, wcolor, wisp, prefs
    """

    key = "wispname"
    locks = "cmd:all()"
    help_category = "Prefs"

    def func(self):
        acct = _account(self.caller)
        args = self.args.strip()

        if not args:
            pref = acct.db.wisp_name_display or "account"
            custom = acct.db.custom_wisp_name or ""
            detail = ""
            if pref == "wisp_name" and custom:
                detail = f" — |w{custom}|n"
            self.msg(
                f"Wisp name display: |w{pref}|n{detail}\n\n"
                "  |waccount|n    — show your account name\n"
                "  |wcustom|n <text>  — show a custom label\n"
                "  |wanonymous|n  — show no name at all"
            )
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()

        if subcmd == "account":
            acct.db.wisp_name_display = "account"
            self.msg(
                "Wisp name set to |waccount|n. "
                "Others will see your account name."
            )

        elif subcmd == "anonymous":
            acct.db.wisp_name_display = "anonymous"
            self.msg(
                "Wisp name set to |wanonymous|n. "
                "Others see only your mood and color."
            )

        elif subcmd == "custom":
            custom_text = parts[1].strip() if len(parts) > 1 else ""
            if not custom_text:
                self.msg("Usage: wispname custom <text>")
                return
            if len(custom_text) > 40:
                self.msg(
                    "Custom name must be 40 characters or fewer "
                    f"(yours is {len(custom_text)})."
                )
                return
            acct.db.custom_wisp_name = custom_text
            acct.db.wisp_name_display = "wisp_name"
            self.msg(f"Wisp name set to: |w{custom_text}|n")

        else:
            self.msg(
                "Usage:\n"
                "  wispname account\n"
                "  wispname custom <text>\n"
                "  wispname anonymous"
            )


# -------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------

# Character-level access — full set (CharacterCmdSet)
ALL_PREFS_CHAR_CMDS = [
    CmdPrefs,
    CmdDND,
    CmdAFK,
    CmdHighlight,
    CmdFilter,
    CmdNotify,
    CmdFriends,
    CmdMoodCarry,
    CmdWispName,
]

# Account-level access — OOC subset (AccountCmdSet)
# AFK and MoodCarry are character-only; excluded here
ALL_PREFS_ACCT_CMDS = [
    CmdPrefs,
    CmdDND,
    CmdHighlight,
    CmdFilter,
    CmdNotify,
    CmdFriends,
    CmdWispName,
]
