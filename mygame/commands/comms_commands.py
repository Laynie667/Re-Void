"""
commands/comms_commands.py

Cross-room communication for Re:Void.

Character-level commands (CharacterCmdSet):
    tell / t        -- private message to a character (account fallback if OOC)
    reply / r       -- reply to the last tell you received
    page            -- simultaneous tell to multiple targets
    channel / chan  -- channel management and speaking
    ws              -- speak on the Wisp State global OOC channel
    mail            -- account inbox: read, send, delete letters

Account-level commands (AccountCmdSet):
    wping           -- wisp-to-wisp private message (OOC layer only)
    channel / chan  -- channels accessible while OOC
    ws              -- Wisp State channel while OOC

Tell routing:
    1. Search for a character by rp_name / key (global)
    2. If found and puppeted  → deliver to character, show mood color
    3. If found but offline   → deliver to owning account, OOC-tagged
    4. If no character match  → search for an account by name, OOC-tagged
    5. Respects block list silently (sender gets "message not delivered")

Channels:
    Built on Evennia's ChannelDB. Any player can create a channel.
    Default channels created on first use:
        ws     -- Wisp State (global OOC, open to all)
        staff  -- Staff channel (Admin-locked)
    Speak with:  ws <message>   or   channel <alias> = <message>

Mail:
    Stored on account.db.mail_inbox as a list of dicts.
    Accessible from a character via self.caller.account.
"""

import time as _time
import uuid as _uuid
from evennia.commands.default.muxcommand import MuxCommand


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _char_name(obj):
    """Display name for a character or account."""
    if hasattr(obj, 'db') and obj.db.rp_name:
        return obj.db.rp_name
    return getattr(obj, 'key', None) or getattr(obj, 'name', str(obj))


def _mood_color(char):
    """ANSI mood color for a character, |w if none or unavailable."""
    try:
        from commands.social_commands import MOOD_COLOR_MAP
        mood = (char.db.mood or "").lower().strip()
        return MOOD_COLOR_MAP.get(mood, "|w")
    except Exception:
        return "|w"


def _find_character(name):
    """
    Search globally for a character by rp_name (preferred) or key.
    Returns the first match or None.
    """
    from evennia import search_object
    name_lower = name.lower()

    # Fast key search first
    results = search_object(
        name,
        typeclass="typeclasses.characters.Character",
        exact=False,
    )
    if results:
        return results[0]

    # Fall back to rp_name scan. NOTE: search_object(typeclass=...) with no key
    # returns [] in this Evennia (see CLAUDE.md §4) — use the typeclass manager.
    from typeclasses.characters import Character
    all_chars = Character.objects.all()
    # Exact match first
    for char in all_chars:
        rp = (char.db.rp_name or "").lower()
        if rp == name_lower:
            return char
    # Partial match
    for char in all_chars:
        rp = (char.db.rp_name or "").lower()
        if rp.startswith(name_lower):
            return char
    return None


def _find_account(name):
    """Search globally for an account by username."""
    from evennia import search_account
    results = search_account(name)
    if not results:
        return None
    return results[0] if isinstance(results, list) else results


def _is_blocked(caller_id, target):
    """Return True if target has caller_id on their block list."""
    if hasattr(target, 'db'):
        return caller_id in (target.db.block_list or set())
    return False


def _get_or_create_channel(name, alias, desc="", locks=""):
    """
    Retrieve a channel by name or alias, creating it if absent.
    Returns the ChannelDB object.
    """
    from evennia.comms.models import ChannelDB
    from evennia import create_channel

    # Try by key
    channel = ChannelDB.objects.filter(db_key__iexact=name).first()
    if channel:
        return channel
    # Try by alias tag
    for ch in ChannelDB.objects.all():
        if alias.lower() in [a.lower() for a in (ch.aliases.all() or [])]:
            return ch
    # Create
    channel = create_channel(name, aliases=[alias], desc=desc)
    if locks:
        channel.locks.add(locks)
    return channel


def _channel_by_alias(alias):
    """
    Find a channel the caller is allowed to use by alias or key.
    Returns channel or None.
    """
    from evennia.comms.models import ChannelDB
    alias_lower = alias.lower()
    # Key match
    channel = ChannelDB.objects.filter(db_key__iexact=alias_lower).first()
    if channel:
        return channel
    # Alias match
    for ch in ChannelDB.objects.all():
        if alias_lower in [a.lower() for a in (ch.aliases.all() or [])]:
            return ch
    return None


def _speak_on_channel(channel, account, char_name, message):
    """
    Format and send a message to a channel.
    auto-subscribes the account if not already connected.
    """
    if not channel.has_connection(account):
        channel.connect(account)
    key = channel.key
    formatted = f"|x[{key}]|n |w{char_name}:|n {message}"
    channel.msg(formatted, senders=[account], online=True)


# -------------------------------------------------------------------
# CmdTell
# -------------------------------------------------------------------

class CmdTell(MuxCommand):
    """
    Send a private message to another character, wherever they are.

    If the target isn't currently in a character, the message is
    routed to their account with an OOC tag so it's still received.

    Usage:
      tell <name> = <message>
      t <name> = <message>

    Examples:
      tell Ara = Are you still in the Archive?
      t Seraphine = Don't look now.

    Your mood colors your outgoing message.
    Use 'reply' or 'r' to reply without retyping the name.

    See also: reply, page, wping
    """

    key = "tell"
    aliases = ["t"]
    locks = "cmd:all()"
    help_category = "Comms"

    def func(self):
        caller = self.caller

        if not self.lhs or not self.rhs:
            self.msg(
                "Usage: tell <name> = <message>\n"
                "Example: tell Ara = Are you still there?"
            )
            return

        target_name = self.lhs.strip()
        message = self.rhs.strip()

        if not message:
            self.msg("Tell them what?")
            return

        self._send_tell(caller, target_name, message)

    def _send_tell(self, caller, target_name, message):
        cname = _char_name(caller)
        color = _mood_color(caller)

        # --- Character search ---
        target_char = _find_character(target_name)

        if target_char:
            # Block check
            if _is_blocked(caller.id, target_char):
                caller.msg("|x[Message not delivered.]|n")
                return

            tname = _char_name(target_char)

            if target_char.has_account:
                # Character is puppeted — deliver directly
                caller.msg(
                    f"|xYou tell {tname},|n "
                    f"{color}\"{message}\"|n"
                )
                target_char.msg(
                    f"{color}{cname} tells you,|n "
                    f"{color}\"{message}\"|n"
                )
                # Track for reply
                target_char.db.last_tell_from_id = caller.id
                target_char.db.last_tell_from_name = cname
                target_char.db.last_tell_is_char = True
            else:
                # Character exists but isn't puppeted — route to account
                account = target_char.db.account_owner
                if not account:
                    # Try to find the account via the character's db
                    from evennia import search_account
                    try:
                        acct_results = search_account(
                            target_char.db.account_id
                            if target_char.db.account_id
                            else target_char.key
                        )
                        account = acct_results[0] if acct_results else None
                    except Exception:
                        account = None

                if account:
                    if _is_blocked(caller.id, account):
                        caller.msg("|x[Message not delivered.]|n")
                        return
                    caller.msg(
                        f"|xYou tell {tname},|n "
                        f"{color}\"{message}\"|n "
                        f"|x[delivered OOC — not currently IC]|n"
                    )
                    account.msg(
                        f"|x[OOC tell → {tname}]|n "
                        f"|w{cname}:|n {message}"
                    )
                else:
                    caller.msg(
                        f"|x{tname} isn't reachable right now.|n"
                    )
            return

        # --- Account fallback ---
        target_acct = _find_account(target_name)
        if target_acct:
            if _is_blocked(caller.id, target_acct):
                caller.msg("|x[Message not delivered.]|n")
                return
            caller.msg(
                f"|xYou tell {target_acct.name},|n "
                f"{color}\"{message}\"|n "
                f"|x[OOC — no character found]|n"
            )
            target_acct.msg(
                f"|x[OOC tell]|n |w{cname}:|n {message}"
            )
            return

        caller.msg(
            f"No character or account named '{target_name}' found."
        )


# -------------------------------------------------------------------
# CmdReply
# -------------------------------------------------------------------

class CmdReply(MuxCommand):
    """
    Reply to the last character or account that sent you a tell.

    Usage:
      reply <message>
      r <message>

    Example:
      r I'll be there in a moment.

    See also: tell, page
    """

    key = "reply"
    aliases = ["r"]
    locks = "cmd:all()"
    help_category = "Comms"

    def func(self):
        caller = self.caller

        if not self.args.strip():
            self.msg("Reply with what? Usage: reply <message>")
            return

        last_id = caller.db.last_tell_from_id
        last_name = caller.db.last_tell_from_name
        is_char = caller.db.last_tell_is_char

        if not last_id or not last_name:
            self.msg(
                "You haven't received any tells yet. "
                "Use: tell <name> = <message>"
            )
            return

        message = self.args.strip()
        cname = _char_name(caller)
        color = _mood_color(caller)

        if is_char:
            # Reply to a character
            from evennia import search_object
            results = search_object(f"#{last_id}")
            if not results:
                self.msg(
                    f"|x{last_name} is no longer reachable.|n"
                )
                return
            target = results[0]

            if _is_blocked(caller.id, target):
                self.msg("|x[Message not delivered.]|n")
                return

            caller.msg(
                f"|xYou tell {last_name},|n "
                f"{color}\"{message}\"|n"
            )
            if target.has_account:
                target.msg(
                    f"{color}{cname} tells you,|n "
                    f"{color}\"{message}\"|n"
                )
                target.db.last_tell_from_id = caller.id
                target.db.last_tell_from_name = cname
                target.db.last_tell_is_char = True
            else:
                # Fell offline — route to account
                account = None
                try:
                    acct_results = search_object(f"#{last_id}")
                    if acct_results:
                        char = acct_results[0]
                        account = char.db.account_owner
                except Exception:
                    pass
                if account:
                    account.msg(
                        f"|x[OOC tell → {last_name}]|n "
                        f"|w{cname}:|n {message}"
                    )
                else:
                    caller.msg(
                        f"|x{last_name} has gone offline.|n"
                    )
        else:
            # Reply to an account
            from evennia import search_account
            results = search_account(f"#{last_id}")
            if not results:
                self.msg(
                    f"|x{last_name} is no longer reachable.|n"
                )
                return
            target_acct = (
                results[0] if isinstance(results, list)
                else results
            )
            if _is_blocked(caller.id, target_acct):
                self.msg("|x[Message not delivered.]|n")
                return
            caller.msg(
                f"|xYou tell {last_name},|n "
                f"{color}\"{message}\"|n"
            )
            target_acct.msg(
                f"|x[OOC tell]|n |w{cname}:|n {message}"
            )


# -------------------------------------------------------------------
# CmdPage
# -------------------------------------------------------------------

class CmdPage(MuxCommand):
    """
    Send a private message to multiple characters at once.

    Each name is looked up the same way as 'tell' — character first,
    account fallback if not currently IC.

    Usage:
      page <name> <name2> ... = <message>

    Examples:
      page Ara Seraphine = heading to the Archive now
      page Rook = you still at the bar?

    See also: tell, reply
    """

    key = "page"
    aliases = ["pg"]
    locks = "cmd:all()"
    help_category = "Comms"

    def func(self):
        caller = self.caller

        if not self.lhs or not self.rhs:
            self.msg(
                "Usage: page <name> [name2 ...] = <message>\n"
                "Example: page Ara Seraphine = heading there now"
            )
            return

        names = self.lhs.strip().split()
        message = self.rhs.strip()

        if not names or not message:
            self.msg("Usage: page <name> [name2 ...] = <message>")
            return

        cname = _char_name(caller)
        color = _mood_color(caller)

        reached = []
        failed = []

        for name in names:
            target_char = _find_character(name)

            if target_char:
                if _is_blocked(caller.id, target_char):
                    failed.append(name)
                    continue
                tname = _char_name(target_char)
                if target_char.has_account:
                    target_char.msg(
                        f"{color}{cname} pages you,|n "
                        f"{color}\"{message}\"|n "
                        f"|x[also paged: "
                        f"{', '.join(n for n in names if n != name)}]|n"
                        if len(names) > 1 else
                        f"{color}{cname} pages you,|n "
                        f"{color}\"{message}\"|n"
                    )
                    target_char.db.last_tell_from_id = caller.id
                    target_char.db.last_tell_from_name = cname
                    target_char.db.last_tell_is_char = True
                    reached.append(tname)
                else:
                    # Route to account
                    account = target_char.db.account_owner
                    if account:
                        account.msg(
                            f"|x[OOC page → {tname}]|n "
                            f"|w{cname}:|n {message}"
                        )
                        reached.append(f"{tname} |x(OOC)|n")
                    else:
                        failed.append(name)
                continue

            # Account fallback
            target_acct = _find_account(name)
            if target_acct:
                if _is_blocked(caller.id, target_acct):
                    failed.append(name)
                    continue
                target_acct.msg(
                    f"|x[OOC page]|n |w{cname}:|n {message}"
                )
                reached.append(
                    f"{target_acct.name} |x(OOC)|n"
                )
            else:
                failed.append(name)

        # Confirmation to sender
        if reached:
            caller.msg(
                f"|xYou page {', '.join(reached)},|n "
                f"{color}\"{message}\"|n"
            )
        if failed:
            caller.msg(
                f"|x[Could not reach: {', '.join(failed)}]|n"
            )


# -------------------------------------------------------------------
# CmdChannel
# -------------------------------------------------------------------

class CmdChannel(MuxCommand):
    """
    Manage and speak on channels.

    Usage:
      channel/list                      -- all channels (joined + available)
      channel/join <name>               -- subscribe to a channel
      channel/leave <name>              -- unsubscribe
      channel/create <name> = <alias>   -- create a new channel
      channel/who <name>                -- list subscribers
      channel/mute <name>               -- suppress output (stay subscribed)
      channel/unmute <name>             -- restore output
      channel/desc <name> = <text>      -- set channel description
      channel/delete <name>             -- delete (creator or admin)
      channel <alias> = <message>       -- speak on a channel

    Examples:
      channel/list
      channel/create Faction = fac
      channel/join Faction
      channel fac = anyone online?
      channel/leave Faction

    Speak shortcuts:
      ws <message>   -- Wisp State (the global OOC channel)
      <alias> <msg>  -- if you set up your own channel alias

    See also: ws, tell, wping
    """

    key = "channel"
    aliases = ["chan"]
    locks = "cmd:all()"
    help_category = "Comms"

    def func(self):
        caller = self.caller
        # Resolve account — works from char or account level
        account = (
            caller.account
            if hasattr(caller, 'account') and caller.account
            else caller
        )

        switch = self.switches[0] if self.switches else None

        # No switch + args with = → speaking shorthand
        if not switch and self.args and "=" in self.args:
            alias, _, message = self.args.partition("=")
            self._speak(account, alias.strip(), message.strip())
            return

        if not switch:
            self.msg(
                "Usage:\n"
                "  channel/list\n"
                "  channel/join <name>\n"
                "  channel/leave <name>\n"
                "  channel/create <name> = <alias>\n"
                "  channel/who <name>\n"
                "  channel/mute <name>\n"
                "  channel/unmute <name>\n"
                "  channel/desc <name> = <text>\n"
                "  channel/delete <name>\n"
                "  channel <alias> = <message>"
            )
            return

        dispatch = {
            "list":   self._list,
            "join":   self._join,
            "leave":  self._leave,
            "create": self._create,
            "who":    self._who,
            "mute":   self._mute,
            "unmute": self._unmute,
            "desc":   self._desc,
            "delete": self._delete,
        }

        fn = dispatch.get(switch)
        if fn:
            fn(caller, account)
        else:
            self.msg(
                f"Unknown switch '{switch}'.\n"
                f"Valid: {', '.join(dispatch.keys())}"
            )

    # ---------------------------------------------------------------

    def _get_account(self, caller):
        return (
            caller.account
            if hasattr(caller, 'account') and caller.account
            else caller
        )

    def _list(self, caller, account):
        from evennia.comms.models import ChannelDB
        all_channels = ChannelDB.objects.all()

        if not all_channels:
            self.msg("No channels exist yet.")
            return

        sep = f"|w{'─' * 44}|n"
        lines = [f"\n{sep}", "|wChannels|n", sep]

        for ch in sorted(all_channels, key=lambda c: c.key):
            # Skip channels caller can't see
            if not ch.access(account, "listen"):
                continue
            connected = ch.has_connection(account)
            muted = ch.key in (account.db.muted_channels or set())
            status = (
                "|g[joined]|n" if connected and not muted
                else "|y[muted]|n" if connected and muted
                else "|x[available]|n"
            )
            aliases = ", ".join(ch.aliases.all() or [])
            alias_str = f" |x({aliases})|n" if aliases else ""
            desc = ch.db.desc or ""
            sub_count = len(ch.subscriptions.all())
            lines.append(
                f"  {status} |w{ch.key}|n{alias_str} "
                f"|x[{sub_count} connected]|n"
            )
            if desc:
                lines.append(f"    {desc}")

        lines.append(sep)
        self.msg("\n".join(lines))

    def _join(self, caller, account):
        if not self.args.strip():
            self.msg("Join which channel? Usage: channel/join <name>")
            return
        ch = _channel_by_alias(self.args.strip())
        if not ch:
            self.msg(f"No channel named '{self.args.strip()}'.")
            return
        if not ch.access(account, "listen"):
            self.msg(f"You don't have access to '{ch.key}'.")
            return
        if ch.has_connection(account):
            self.msg(f"You're already on {ch.key}.")
            return
        ch.connect(account)
        aliases = ", ".join(ch.aliases.all() or [])
        alias_hint = f" Speak with: {aliases} <message>" if aliases else ""
        self.msg(f"Joined |w{ch.key}|n.{alias_hint}")

    def _leave(self, caller, account):
        if not self.args.strip():
            self.msg("Leave which channel? Usage: channel/leave <name>")
            return
        ch = _channel_by_alias(self.args.strip())
        if not ch:
            self.msg(f"No channel named '{self.args.strip()}'.")
            return
        if not ch.has_connection(account):
            self.msg(f"You're not on {ch.key}.")
            return
        ch.disconnect(account)
        self.msg(f"Left |w{ch.key}|n.")

    def _create(self, caller, account):
        if "=" not in self.args:
            self.msg(
                "Usage: channel/create <name> = <alias>\n"
                "Example: channel/create Faction = fac"
            )
            return
        name, _, alias = self.args.partition("=")
        name = name.strip()
        alias = alias.strip().lower()

        if not name or not alias:
            self.msg("Both a name and alias are required.")
            return

        if len(alias) > 10:
            self.msg("Alias must be 10 characters or fewer.")
            return

        from evennia.comms.models import ChannelDB
        if ChannelDB.objects.filter(db_key__iexact=name).exists():
            self.msg(f"A channel named '{name}' already exists.")
            return
        if _channel_by_alias(alias):
            self.msg(f"An alias '{alias}' is already in use.")
            return

        from evennia import create_channel
        ch = create_channel(
            name,
            aliases=[alias],
            desc=f"Created by {_char_name(caller)}.",
        )
        # Store creator for permission checks
        ch.db.creator_id = account.id
        ch.connect(account)

        self.msg(
            f"Channel |w{name}|n created with alias |w{alias}|n.\n"
            f"Others can join with: channel/join {name}\n"
            f"Speak with: {alias} <message>  or  "
            f"channel {alias} = <message>"
        )

    def _who(self, caller, account):
        if not self.args.strip():
            self.msg("Usage: channel/who <name>")
            return
        ch = _channel_by_alias(self.args.strip())
        if not ch:
            self.msg(f"No channel named '{self.args.strip()}'.")
            return
        if not ch.access(account, "listen"):
            self.msg(f"You don't have access to '{ch.key}'.")
            return
        subs = ch.subscriptions.all()
        if not subs:
            self.msg(f"Nobody is subscribed to {ch.key}.")
            return
        names = [s.key for s in subs]
        self.msg(
            f"|w{ch.key}|n subscribers: {', '.join(names)}"
        )

    def _mute(self, caller, account):
        if not self.args.strip():
            self.msg("Usage: channel/mute <name>")
            return
        ch = _channel_by_alias(self.args.strip())
        if not ch:
            self.msg(f"No channel named '{self.args.strip()}'.")
            return
        muted = account.db.muted_channels or set()
        muted.add(ch.key)
        account.db.muted_channels = muted
        self.msg(
            f"|w{ch.key}|n muted. You'll still appear subscribed "
            f"but won't receive messages. Use channel/unmute to restore."
        )

    def _unmute(self, caller, account):
        if not self.args.strip():
            self.msg("Usage: channel/unmute <name>")
            return
        ch = _channel_by_alias(self.args.strip())
        if not ch:
            self.msg(f"No channel named '{self.args.strip()}'.")
            return
        muted = account.db.muted_channels or set()
        muted.discard(ch.key)
        account.db.muted_channels = muted
        self.msg(f"|w{ch.key}|n unmuted.")

    def _desc(self, caller, account):
        if "=" not in self.args:
            self.msg("Usage: channel/desc <name> = <description>")
            return
        name, _, desc = self.args.partition("=")
        ch = _channel_by_alias(name.strip())
        if not ch:
            self.msg(f"No channel named '{name.strip()}'.")
            return
        is_admin = (
            account.is_superuser
            or account.check_permstring("Admin")
        )
        is_creator = ch.db.creator_id == account.id
        if not is_admin and not is_creator:
            self.msg(
                "Only the channel creator or an admin can "
                "change the description."
            )
            return
        ch.db.desc = desc.strip()
        self.msg(f"|w{ch.key}|n description updated.")

    def _delete(self, caller, account):
        if not self.args.strip():
            self.msg("Usage: channel/delete <name>")
            return
        ch = _channel_by_alias(self.args.strip())
        if not ch:
            self.msg(f"No channel named '{self.args.strip()}'.")
            return
        is_admin = (
            account.is_superuser
            or account.check_permstring("Admin")
        )
        is_creator = ch.db.creator_id == account.id
        if not is_admin and not is_creator:
            self.msg(
                "Only the channel creator or an admin can "
                "delete a channel."
            )
            return
        # Protect default channels
        if ch.key.lower() in ("ws", "staff"):
            if not is_admin:
                self.msg(
                    f"The '{ch.key}' channel is a system channel "
                    f"and cannot be deleted by players."
                )
                return
        name = ch.key
        ch.delete()
        self.msg(f"Channel |w{name}|n deleted.")

    def _speak(self, account, alias, message):
        if not message:
            self.msg("Say what on the channel?")
            return
        ch = _channel_by_alias(alias)
        if not ch:
            self.msg(f"No channel with alias '{alias}'.")
            return
        if not ch.access(account, "listen"):
            self.msg(f"You don't have access to '{ch.key}'.")
            return
        muted = account.db.muted_channels or set()
        if ch.key in muted:
            self.msg(
                f"|w{ch.key}|n is muted. Use channel/unmute first."
            )
            return
        # Resolve display name — use character name if puppeting
        puppet = None
        if hasattr(account, 'get_all_puppets'):
            puppets = account.get_all_puppets()
            if puppets:
                puppet = puppets[0]
        speaker_name = (
            _char_name(puppet) if puppet
            else account.key
        )
        _speak_on_channel(ch, account, speaker_name, message)


# -------------------------------------------------------------------
# CmdWS  (Wisp State — dedicated shortcut for the global OOC channel)
# -------------------------------------------------------------------

class CmdWS(MuxCommand):
    """
    Speak on the Wisp State channel — the global OOC channel.

    Usage:
      ws <message>

    Example:
      ws Anyone up for a scene in the Archive tonight?

    Wisp State is the out-of-character global channel. It's available
    from both character and wisp (account) mode.

    See also: channel, wping, tell
    """

    key = "ws"
    locks = "cmd:all()"
    help_category = "Comms"

    def func(self):
        caller = self.caller

        if not self.args.strip():
            self.msg("Say what? Usage: ws <message>")
            return

        account = (
            caller.account
            if hasattr(caller, 'account') and caller.account
            else caller
        )

        # Get or create the WS channel
        ch = _get_or_create_channel(
            "WS",
            "ws",
            desc="Wisp State — global out-of-character channel.",
            locks="control:perm(Admin);listen:all();send:all()",
        )

        # Resolve speaker name
        puppet = None
        if hasattr(account, 'get_all_puppets'):
            puppets = account.get_all_puppets()
            if puppets:
                puppet = puppets[0]
        speaker_name = (
            _char_name(puppet) if puppet
            else account.key
        )

        muted = account.db.muted_channels or set()
        if ch.key in muted:
            self.msg(
                "WS is muted. Use channel/unmute ws to restore."
            )
            return

        _speak_on_channel(ch, account, speaker_name, self.args.strip())


# -------------------------------------------------------------------
# CmdMail
# -------------------------------------------------------------------

class CmdMail(MuxCommand):
    """
    Send and receive letters through the in-game mail system.

    Mail is account-level — it reaches you regardless of which
    character you're playing or whether you're online.

    Usage:
      mail                          -- show inbox (same as mail/inbox)
      mail/inbox                    -- list all mail
      mail/unread                   -- list unread mail only
      mail/read <#>                 -- read a specific message
      mail/send <name> = <subject> / <body>   -- send a letter
      mail/delete <#>               -- delete a message

    Examples:
      mail/send Ara = Scene invite / Hey, free for a scene tonight?
        Thinking Archive or the Threshold.
      mail/read 1
      mail/delete 3

    See also: tell, page, wping
    """

    key = "mail"
    locks = "cmd:all()"
    help_category = "Comms"

    def func(self):
        caller = self.caller
        account = (
            caller.account
            if hasattr(caller, 'account') and caller.account
            else caller
        )

        switch = self.switches[0] if self.switches else "inbox"

        dispatch = {
            "inbox":  self._inbox,
            "unread": self._unread,
            "read":   self._read,
            "send":   self._send,
            "delete": self._delete,
        }

        fn = dispatch.get(switch)
        if fn:
            fn(account)
        else:
            self.msg(
                f"Unknown switch '{switch}'.\n"
                "Valid: inbox / unread / read / send / delete"
            )

    def _get_inbox(self, account):
        return list(account.db.mail_inbox or [])

    def _inbox(self, account):
        inbox = self._get_inbox(account)
        if not inbox:
            self.msg("Your inbox is empty.")
            return

        sep = f"|w{'─' * 44}|n"
        lines = [f"\n{sep}", "|wInbox|n", sep]
        for i, letter in enumerate(inbox, 1):
            read = letter.get("read", False)
            read_tag = " " if read else "|y●|n "
            from_name = letter.get("from_name", "unknown")
            subject = letter.get("subject", "(no subject)")
            ts = letter.get("timestamp", 0)
            import datetime
            date = datetime.datetime.fromtimestamp(ts).strftime(
                "%b %d"
            ) if ts else "?"
            lines.append(
                f"  [{i:>2}] {read_tag}|w{subject}|n  "
                f"|xfrom {from_name}  {date}|n"
            )
        unread = sum(1 for l in inbox if not l.get("read"))
        lines.append(sep)
        lines.append(
            f"|x{len(inbox)} message(s), {unread} unread.|n"
        )
        self.msg("\n".join(lines))

    def _unread(self, account):
        inbox = self._get_inbox(account)
        unread = [l for l in inbox if not l.get("read")]
        if not unread:
            self.msg("No unread messages.")
            return
        sep = f"|w{'─' * 44}|n"
        lines = [f"\n{sep}", "|wUnread Mail|n", sep]
        all_idx = {id(l): i + 1 for i, l in enumerate(inbox)}
        for letter in unread:
            idx = all_idx.get(id(letter), "?")
            from_name = letter.get("from_name", "unknown")
            subject = letter.get("subject", "(no subject)")
            lines.append(
                f"  [{idx:>2}] |y●|n |w{subject}|n  "
                f"|xfrom {from_name}|n"
            )
        lines.append(sep)
        self.msg("\n".join(lines))

    def _read(self, account):
        args = self.args.strip()
        if not args:
            self.msg("Read which message? Usage: mail/read <#>")
            return
        try:
            idx = int(args) - 1
        except ValueError:
            self.msg("Please provide a message number.")
            return

        inbox = self._get_inbox(account)
        if idx < 0 or idx >= len(inbox):
            self.msg(
                f"No message #{idx + 1}. "
                f"You have {len(inbox)} message(s)."
            )
            return

        letter = inbox[idx]
        from_name = letter.get("from_name", "unknown")
        subject = letter.get("subject", "(no subject)")
        body = letter.get("body", "")
        ts = letter.get("timestamp", 0)
        import datetime
        date = datetime.datetime.fromtimestamp(ts).strftime(
            "%Y-%m-%d %H:%M"
        ) if ts else "unknown"

        sep = f"|w{'─' * 44}|n"
        self.msg(
            f"\n{sep}\n"
            f"|wFrom:|n   {from_name}\n"
            f"|wSubject:|n {subject}\n"
            f"|wDate:|n   {date}\n"
            f"{sep}\n"
            f"{body}\n"
            f"{sep}"
        )

        # Mark as read
        inbox[idx]["read"] = True
        account.db.mail_inbox = inbox

    def _send(self, account):
        if not self.lhs or not self.rhs:
            self.msg(
                "Usage: mail/send <name> = <subject> / <body>\n"
                "Example: mail/send Ara = Scene invite / "
                "Are you free tonight?"
            )
            return

        target_name = self.lhs.strip()
        rest = self.rhs.strip()

        if "/" in rest:
            subject, _, body = rest.partition("/")
            subject = subject.strip()
            body = body.strip()
        else:
            subject = rest
            body = ""

        # Find target account
        target_acct = None

        # Try character first → get account
        target_char = _find_character(target_name)
        if target_char:
            target_acct = (
                target_char.account
                if hasattr(target_char, 'account')
                and target_char.account
                else None
            )
            if not target_acct:
                target_acct = target_char.db.account_owner

        if not target_acct:
            target_acct = _find_account(target_name)

        if not target_acct:
            self.msg(
                f"No character or account named '{target_name}' found."
            )
            return

        # Determine sender name
        sender_name = account.key
        puppets = (
            account.get_all_puppets()
            if hasattr(account, 'get_all_puppets')
            else []
        )
        if puppets:
            sender_name = _char_name(puppets[0])

        inbox = list(target_acct.db.mail_inbox or [])
        inbox.append({
            "id":              _uuid.uuid4().hex[:12],
            "from_name":       sender_name,
            "from_account_id": account.id,
            "subject":         subject or "(no subject)",
            "body":            body,
            "timestamp":       _time.time(),
            "read":            False,
        })
        target_acct.db.mail_inbox = inbox

        self.msg(
            f"Letter sent to |w{target_acct.key}|n.\n"
            f"|xSubject: {subject or '(no subject)'}|n"
        )

        # Notify if online
        if target_acct.sessions.count() > 0:
            target_acct.msg(
                f"|x[New mail from {sender_name}: "
                f"{subject or '(no subject)'}]|n"
            )

    def _delete(self, account):
        args = self.args.strip()
        if not args:
            self.msg("Delete which message? Usage: mail/delete <#>")
            return
        try:
            idx = int(args) - 1
        except ValueError:
            self.msg("Please provide a message number.")
            return

        inbox = self._get_inbox(account)
        if idx < 0 or idx >= len(inbox):
            self.msg(
                f"No message #{idx + 1}. "
                f"You have {len(inbox)} message(s)."
            )
            return

        subject = inbox[idx].get("subject", "(no subject)")
        del inbox[idx]
        account.db.mail_inbox = inbox
        self.msg(f"Deleted: |w{subject}|n")


# -------------------------------------------------------------------
# CmdWping  (Account-level — wisp-to-wisp private message)
# -------------------------------------------------------------------

class CmdWping(MuxCommand):
    """
    Send a private OOC message to another wisp (account).

    This is the OOC equivalent of 'tell' — it reaches the player
    directly, not through their character. Available in both wisp
    state and while playing a character.

    Usage:
      wping <name> = <message>

    Examples:
      wping Ara = hey, ready to start that scene?
      wping Seraphine = logging on in 10

    See also: tell, page, ws
    """

    key = "wping"
    locks = "cmd:all()"
    help_category = "Comms"

    def func(self):
        caller = self.caller
        # caller may be account or character
        account = (
            caller.account
            if hasattr(caller, 'account') and caller.account
            else caller
        )

        if not self.lhs or not self.rhs:
            self.msg(
                "Usage: wping <name> = <message>\n"
                "Example: wping Ara = heading on now"
            )
            return

        target_name = self.lhs.strip()
        message = self.rhs.strip()

        if not message:
            self.msg("Ping with what message?")
            return

        # Find target account
        target_acct = _find_account(target_name)
        if not target_acct:
            # Try via character name
            target_char = _find_character(target_name)
            if target_char:
                target_acct = (
                    target_char.account
                    if hasattr(target_char, 'account')
                    and target_char.account
                    else target_char.db.account_owner
                )

        if not target_acct:
            self.msg(
                f"No account or character named '{target_name}' found."
            )
            return

        if target_acct == account:
            self.msg("You ping yourself. Nothing happens.")
            return

        sender_name = account.key
        # Use wisp color if available
        try:
            color = account.wisp_color_code
        except Exception:
            color = "|w"

        account.msg(
            f"|x[wping → {target_acct.key}]|n "
            f"{color}{message}|n"
        )
        target_acct.msg(
            f"|x[wping from {sender_name}]|n "
            f"{color}{message}|n"
        )


# -------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------

# Goes in CharacterCmdSet
ALL_COMMS_CMDS = [
    CmdTell,
    CmdReply,
    CmdPage,
    CmdChannel,
    CmdWS,
    CmdMail,
]

# Goes in AccountCmdSet (OOC access to channels + wisp ping)
ALL_COMMS_ACCT_CMDS = [
    CmdWping,
    CmdChannel,
    CmdWS,
]
