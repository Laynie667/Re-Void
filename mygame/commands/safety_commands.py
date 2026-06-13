"""
commands/safety_commands.py

Safety and monitoring tools for Re:Void.

--- PLAYER SAFETY SYSTEM ---

Safety commands are always available regardless of scene state,
position state, or any command set reduction. They cannot be
blocked or suppressed by any game mechanic.

When a safeword is called:
  - An OOC broadcast goes to everyone in the room
  - All active position and restraint restrictions on the caller are cleared
  - A record is added to the caller's safeword history
  - Nearby aftercare spaces are listed if available

Commands (player-facing):
    safe            -- full stop (alias: safeword)
    safe info       -- see established safewords for current scene
    safe set <word> -- set your personal safeword
    safe history    -- see your safeword use history

    yellow          -- call slow/check-in (no state changes, just signal)

--- ADMIN MONITORING ---

The watch system silently forwards everything a watched character
sees to the watching admin in real time. The watched player
receives no indication.

Commands (admin):
    watch <name>      -- begin watching
    watch/stop <name> -- stop watching
    watch/list        -- see who you're watching
    unwatch <name>    -- shorthand for watch/stop
    watching          -- list all currently watched characters
"""

import time
from evennia.commands.default.muxcommand import MuxCommand


# ===================================================================
# PLAYER SAFETY COMMANDS
# ===================================================================

class CmdSafe(MuxCommand):
    """
    Safety commands. Always available, cannot be blocked.

    'safe' with no argument calls a full stop — a safeword.
    This is the system's hard stop: all restrictions clear,
    an OOC alert goes to everyone in the room, and the moment
    is logged for your records.

    Subcommands:
      safe              -- full stop (alias: safeword)
      safe set <word>   -- set your personal safeword phrase
      safe info         -- see established safewords for this scene
      safe history      -- see your safeword use history

    Usage:
      safe
      safeword
      safe set my word
      safe info
      safe history

    See also: yellow, ooc
    """

    key = "safe"
    aliases = ["safeword"]
    locks = "cmd:all()"
    help_category = "Safety"

    def func(self):
        char = self.caller
        args = self.args.strip()

        if not args:
            # Full stop safeword
            self._call_safeword(char)
            return

        parts = args.split(None, 1)
        sub = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        dispatch = {
            "set":     self._set,
            "info":    self._info,
            "history": self._history,
        }
        fn = dispatch.get(sub)
        if fn:
            fn(char, rest)
        else:
            self.msg(
                "Usage:\n"
                "  safe                -- full stop safeword\n"
                "  safe set <phrase>   -- set your personal safeword\n"
                "  safe info           -- see scene safewords\n"
                "  safe history        -- see your use history\n"
                "  yellow              -- signal slow/check-in"
            )

    # ---------------------------------------------------------------

    def _call_safeword(self, char):
        """Execute a full safeword stop."""
        name = char.db.rp_name or char.name
        word = char.db.personal_safeword or "safeword"

        # OOC broadcast to the room
        broadcast = (
            f"\n|r[SAFEWORD — {name} has called a full stop.]|n\n"
            f"|xScene paused. All restrictions cleared. "
            f"Check in before continuing.|n\n"
        )
        if char.location:
            char.location.msg_contents(broadcast)
        else:
            self.msg(broadcast)

        # Private confirmation to caller
        self.msg(
            f"|r[Safeword called. All restrictions on you have been cleared.]|n\n"
            f"|xYou are safe. Take your time.|n"
        )

        # Clear all active restrictions
        _clear_restrictions(char)

        # Log the event
        history = char.db.safeword_history or []
        history.append({
            "time":     time.time(),
            "type":     "safeword",
            "location": char.location.key if char.location else "unknown",
        })
        char.db.safeword_history = history[-50:]  # keep last 50

        # List nearby aftercare spaces if any
        self._list_aftercare(char)

    def _set(self, char, rest):
        """Set a personal safeword phrase."""
        if not rest:
            current = char.db.personal_safeword or "(none set — defaults to 'safeword')"
            self.msg(f"|xYour safeword: |w{current}|n")
            return
        char.db.personal_safeword = rest.strip()
        self.msg(f"|xPersonal safeword set to: |w{char.db.personal_safeword}|n")

    def _info(self, char, rest):
        """Show established safewords for everyone in the current room."""
        if not char.location:
            self.msg("You need to be somewhere to check scene safewords.")
            return

        sep = f"|w{'─' * 44}|n"
        lines = [f"\n{sep}", "|wScene Safewords|n", sep]

        for obj in char.location.contents:
            if not hasattr(obj, "db") or not hasattr(obj.db, "rp_name"):
                continue
            cname = obj.db.rp_name or obj.name
            word = obj.db.personal_safeword or "|x(default: safeword)|n"
            lines.append(f"  |w{cname:<20}|n  {word}")

        lines.append(sep)
        self.msg("\n".join(lines))

    def _history(self, char, rest):
        """Show the caller's safeword use history."""
        history = char.db.safeword_history or []
        if not history:
            self.msg("|xNo safeword history on record.|n")
            return

        sep = f"|w{'─' * 44}|n"
        lines = [f"\n{sep}", "|wSafeword History|n", sep]
        for entry in reversed(history[-20:]):
            ts = _fmt_timestamp(entry.get("time", 0))
            etype = entry.get("type", "safeword")
            loc = entry.get("location", "unknown")
            marker = "|r" if etype == "safeword" else "|y"
            lines.append(f"  {marker}{etype:<10}|n  |x{ts}|n  {loc}")
        lines.append(sep)
        self.msg("\n".join(lines))

    def _list_aftercare(self, char):
        """Mention nearby aftercare spaces if any exist."""
        if not char.location:
            return
        aftercare_rooms = []
        for exit_obj in char.location.exits:
            dest = exit_obj.destination
            if dest and dest.db.is_aftercare_space:
                aftercare_rooms.append(dest.key)
        if aftercare_rooms:
            rooms = ", ".join(aftercare_rooms)
            self.msg(f"|x[Aftercare spaces nearby: {rooms}]|n")


# -------------------------------------------------------------------
# CmdYellow
# -------------------------------------------------------------------

class CmdYellow(MuxCommand):
    """
    Signal slow — a check-in without a full stop.

    Yellow means you need a pause or things to slow down.
    It doesn't clear restrictions or end the scene — it's a
    signal to the other participants to check in with you.

    Nothing mechanically changes. The room just sees the signal
    and knows to pause and check in before continuing.

    Usage:
      yellow

    See also: safe, safeword, ooc
    """

    key = "yellow"
    locks = "cmd:all()"
    help_category = "Safety"

    def func(self):
        char = self.caller
        name = char.db.rp_name or char.name

        broadcast = (
            f"\n|y[YELLOW — {name} is calling slow. Check in before continuing.]|n\n"
        )

        if char.location:
            char.location.msg_contents(broadcast)
        else:
            self.msg(broadcast)

        self.msg("|y[Yellow called. Others will check in with you.]|n")

        # Log the yellow signal
        history = char.db.safeword_history or []
        history.append({
            "time":     time.time(),
            "type":     "yellow",
            "location": char.location.key if char.location else "unknown",
        })
        char.db.safeword_history = history[-50:]


# -------------------------------------------------------------------
# Shared utility
# -------------------------------------------------------------------

def _clear_restrictions(char):
    """
    Clear all active position and restraint restrictions from a character.

    Called when safeword is used. Handles all known restriction fields
    defensively — if a system isn't built yet, the field just won't exist
    and nothing breaks.
    """
    # Position state — return to standing
    if hasattr(char.db, "position_state") and char.db.position_state:
        char.db.position_state = "standing"

    # Restraint state
    if hasattr(char.db, "is_restrained") and char.db.is_restrained:
        char.db.is_restrained = False

    # Lead/leash state
    if hasattr(char.db, "lead_holder") and char.db.lead_holder:
        char.db.lead_holder = None

    if hasattr(char.db, "is_leashed") and char.db.is_leashed:
        char.db.is_leashed = False

    # Furniture installation
    if hasattr(char.db, "is_installed") and char.db.is_installed:
        char.db.is_installed = False

    # Any scene-level command restrictions
    if hasattr(char.db, "command_restrictions") and char.db.command_restrictions:
        char.db.command_restrictions = []


def _fmt_timestamp(ts):
    """Format a unix timestamp into a short human-readable string."""
    import datetime
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "unknown"


# -------------------------------------------------------------------
# Player safety exports
# -------------------------------------------------------------------

ALL_SAFETY_CMDS = [
    CmdSafe,
    CmdYellow,
]


class CmdEscape(MuxCommand):
    """
    The §0 floor — the one door that is never locked.

    Usage:
      escape            -- leave the facility/realm entirely: home, and cleared.
      forceclear        -- the heavier hammer, if 'escape' ever misbehaves.

    This is the OOC safety exit. It ALWAYS works, from anywhere, in any state —
    no phrase, no tier, no compliance, no convincing anyone. It takes you home and
    purges every facility/realm binding on you: consent flags, navigation and
    self-command locks, conditioning, posture, speech filters, the cycle, ownership
    — all of it. Nothing in the game can gate, suppress, or delay this command.

    (The in-scene 'safe' safeword clears restraints and position for a pause; this
    is the full exit that ends the facility's hold on you completely.)

    See also: safe, yellow
    """

    key = "escape"
    aliases = ["facilityescape", "escapeme", "getmeout", "letmeout"]
    locks = "cmd:all()"
    help_category = "Safety"

    def func(self):
        char = self.caller
        try:
            from world.realm_build import escape as _escape
            _escape(char)
        except Exception:
            # Belt-and-suspenders: if the realm helper fails for any reason, still
            # run the bulletproof step-by-step clear. The floor never just fails.
            try:
                from world.realm_build import force_clear
                force_clear(char)
                char.msg("|gYou're clear. The realm lets go of you completely.|n")
            except Exception:
                try:
                    from world.facility_build import run_facility_reset
                    run_facility_reset(char, purge=True)
                    char.msg("|gYou're clear.|n")
                except Exception as e:
                    char.msg(f"|rEscape hit an error but kept trying. Tell a dev: {e}|n")


class CmdForceClear(MuxCommand):
    """
    The bulletproof §0 reset — clears ALL facility/realm state on you, step by step
    so nothing can half-fail. Use if 'escape' ever misbehaves.

    Usage:
      forceclear

    Always available, never gated. Does not move you home (use 'escape' for that);
    it simply strips every binding, flag, lock, filter, and install off you.

    See also: escape, safe
    """

    key = "forceclear"
    aliases = ["force_clear", "clearme"]
    locks = "cmd:all()"
    help_category = "Safety"

    def func(self):
        char = self.caller
        try:
            from world.realm_build import force_clear
            force_clear(char)
            char.msg("|gForce-clear complete. Every binding on you is gone.|n")
        except Exception as e:
            char.msg(f"|rForce-clear hit an error: {e}|n")


ALL_SAFETY_CMDS.append(CmdEscape)
ALL_SAFETY_CMDS.append(CmdForceClear)


# ===================================================================
# ADMIN MONITORING COMMANDS
# ===================================================================

class CmdWatch(MuxCommand):
    """
    Silently monitor a character's incoming messages in real time.

    Everything the watched character sees, hears, receives, or is
    sent — poses, says, whispers, emotes, system messages — will
    appear on your screen prefixed with their name.

    The watched player receives no indication of any kind.

    Usage:
      watch <name>        -- start watching
      watch/stop <name>   -- stop watching
      watch/list          -- see who you're watching

    Requires Admin or Superuser.

    See also: unwatch, watching
    """

    key = "watch"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        caller = self.caller

        if "list" in self.switches:
            self._list(caller)
            return

        if "stop" in self.switches:
            self._stop(caller)
            return

        if not self.args:
            self.msg(
                "Usage: watch <name>\n"
                "       watch/stop <name>\n"
                "       watch/list"
            )
            return

        self._start(caller)

    def _start(self, caller):
        results = caller.search(self.args.strip(), quiet=True)
        if not results:
            from evennia import search_object
            results = search_object(
                self.args.strip(),
                typeclass="typeclasses.characters.Character",
            )
        if not results:
            self.msg(f"Can't find '{self.args.strip()}'.")
            return
        target = results[0] if isinstance(results, list) else results

        from typeclasses.characters import Character
        if not isinstance(target, Character):
            self.msg("You can only watch a character.")
            return

        acct = caller.account if hasattr(caller, "account") else caller
        watched_by = target.db.watched_by or set()
        watched_by.add(acct.id)
        target.db.watched_by = watched_by

        tname = target.db.rp_name or target.name
        self.msg(f"|x[watch]|n Now watching |w{tname}|n.")

    def _stop(self, caller):
        if not self.args:
            self.msg("Usage: watch/stop <name>")
            return
        results = caller.search(self.args.strip(), quiet=True)
        if not results:
            from evennia import search_object
            results = search_object(
                self.args.strip(),
                typeclass="typeclasses.characters.Character",
            )
        if not results:
            self.msg(f"Can't find '{self.args.strip()}'.")
            return
        target = results[0] if isinstance(results, list) else results

        acct = caller.account if hasattr(caller, "account") else caller
        watched_by = target.db.watched_by or set()
        watched_by.discard(acct.id)
        target.db.watched_by = watched_by

        tname = target.db.rp_name or target.name
        self.msg(f"|x[watch]|n Stopped watching |w{tname}|n.")

    def _list(self, caller):
        acct = caller.account if hasattr(caller, "account") else caller
        # search_object(typeclass=...) with no key returns [] in this Evennia
        # (CLAUDE.md §4) — use the typeclass manager so the list isn't always empty.
        from typeclasses.characters import Character
        all_chars = Character.objects.all()
        watching = [
            c for c in all_chars
            if acct.id in (c.db.watched_by or set())
        ]
        if not watching:
            self.msg("|x[watch]|n You are not watching anyone.")
            return
        names = [f"|w{c.db.rp_name or c.name}|n" for c in watching]
        self.msg(f"|x[watch]|n Currently watching: {', '.join(names)}")


class CmdUnwatch(MuxCommand):
    """
    Stop watching a character.

    Shorthand for 'watch/stop <name>'.

    Usage:
      unwatch <name>

    Requires Admin or Superuser.

    See also: watch, watching
    """

    key = "unwatch"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.msg("Usage: unwatch <name>")
            return
        caller = self.caller
        results = caller.search(self.args.strip(), quiet=True)
        if not results:
            from evennia import search_object
            results = search_object(
                self.args.strip(),
                typeclass="typeclasses.characters.Character",
            )
        if not results:
            self.msg(f"Can't find '{self.args.strip()}'.")
            return
        target = results[0] if isinstance(results, list) else results

        acct = caller.account if hasattr(caller, "account") else caller
        watched_by = target.db.watched_by or set()
        watched_by.discard(acct.id)
        target.db.watched_by = watched_by

        tname = target.db.rp_name or target.name
        self.msg(f"|x[watch]|n Stopped watching |w{tname}|n.")


class CmdWatching(MuxCommand):
    """
    List all characters you are currently watching.

    Usage:
      watching

    Requires Admin or Superuser.

    See also: watch, unwatch
    """

    key = "watching"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        caller = self.caller
        acct = caller.account if hasattr(caller, "account") else caller
        # Typeclass-manager scan (search_object(typeclass=...) returns [] here).
        from typeclasses.characters import Character
        all_chars = Character.objects.all()
        watching = [
            c for c in all_chars
            if acct.id in (c.db.watched_by or set())
        ]
        if not watching:
            self.msg("|x[watch]|n You are not watching anyone.")
            return
        names = [f"|w{c.db.rp_name or c.name}|n" for c in watching]
        self.msg(f"|x[watch]|n Watching: {', '.join(names)}")


# -------------------------------------------------------------------
# Admin safety exports
# -------------------------------------------------------------------

ALL_SAFETY_ADMIN_CMDS = [
    CmdWatch,
    CmdUnwatch,
    CmdWatching,
]
