"""
commands/scene_commands.py

Scene management for Re:Void.

A scene is a structured RP session in a room. Any participant can
manage it — no ownership, no gating. Admins and superusers bypass
scene locks entirely (handled in rooms.py at_pre_object_receive).

Commands:
    scene/start [title]     mark scene active, optionally title it
    scene/end               save to room history, reset state
    scene/lock              close room to new arrivals
    scene/unlock            open room again
    scene/log               toggle scene logging on/off
    scene/title <text>      set or rename the scene title
    scene/prompt <text>     set a scene prompt shown above the room desc
    scene/prompt/clear      clear the scene prompt
    scene/warn <text>       add a content warning
    scene/warn/clear        clear all content warnings
    scene/tone <text>       set the scene tone tag
    scene/status            show current scene state
    scene/read              read the current scene log
    scene/history           list past saved scenes for this room
    scene/invite <name>     add someone to the invite list (bypass lock)
    scene/uninvite <name>   remove from invite list

    knock                   from outside a locked room, notify those inside

    po                      see current pose order queue
    po join                 join the pose order queue
    po leave                leave pose order
    po skip                 skip your turn (moves you to the back)
    po next                 advance the queue to the next person
    po reset                clear and rebuild the queue
    po add <name>           add someone to the queue
    po remove <name>        remove someone from the queue
"""

import time
import datetime
from evennia.commands.default.muxcommand import MuxCommand


def _fmt_duration(seconds):
    """Format a duration in seconds into a human-readable string."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def _fmt_timestamp(ts):
    """Format a unix timestamp into a short readable date."""
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "unknown"


def _char_name(char):
    """Return the character's RP display name."""
    return char.db.rp_name or char.name


# -------------------------------------------------------------------
# CmdScene
# -------------------------------------------------------------------

class CmdScene(MuxCommand):
    """
    Manage the current scene in this room.

    Usage:
      scene/start [title]       -- open a scene, optionally name it
      scene/end                 -- close and save to room history
      scene/lock                -- close room to new arrivals
      scene/unlock              -- open room again
      scene/log                 -- toggle scene logging
      scene/title <text>        -- set or rename the scene title
      scene/prompt <text>       -- set a prompt shown above room desc
      scene/prompt/clear        -- clear the scene prompt
      scene/warn <text>         -- add a content warning
      scene/warn/clear          -- clear all content warnings
      scene/tone <text>         -- set scene tone (e.g. tender, tense)
      scene/status              -- show current state
      scene/read                -- read the current scene log
      scene/history             -- list past scenes saved in this room
      scene/invite <name>       -- add someone to bypass the lock
      scene/uninvite <name>     -- remove from invite list

    No scene needs to be started before locking or logging — those
    work independently. 'start' and 'end' are bookmarks.

    See also: knock, po, pose, say, spoof
    """

    key = "scene"
    locks = "cmd:all()"
    help_category = "Scene"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            self.msg("You need to be somewhere to manage a scene.")
            return

        switch = self.switches[0] if self.switches else "status"

        dispatch = {
            "start":    self._start,
            "end":      self._end,
            "lock":     self._lock,
            "unlock":   self._unlock,
            "log":      self._log,
            "title":    self._title,
            "prompt":   self._prompt,
            "warn":     self._warn,
            "tone":     self._tone,
            "status":   self._status,
            "read":     self._read,
            "history":  self._history,
            "invite":   self._invite,
            "uninvite": self._uninvite,
        }

        fn = dispatch.get(switch)
        if fn:
            fn(caller, room)
        else:
            self.msg(
                f"Unknown switch: {switch}\n"
                f"Valid: {', '.join(dispatch.keys())}"
            )

    # ---------------------------------------------------------------

    def _start(self, caller, room):
        room.db.scene_active = True
        room.db.scene_started_at = time.time()
        if self.args:
            room.db.scene_title = self.args.strip()
        title = room.db.scene_title or "untitled"
        room.msg_contents(
            f"|w[ Scene started: {title} ]|n",
        )

    def _end(self, caller, room):
        title = room.db.scene_title or "untitled"
        started = room.db.scene_started_at or time.time()
        duration = time.time() - started
        log = list(room.db.scene_log or [])

        # Save to room history
        history = room.db.room_history or []
        history.append({
            "title":     title,
            "started":   started,
            "ended":     time.time(),
            "duration":  duration,
            "log":       log,
            "warnings":  list(room.db.content_warnings or []),
            "tone":      room.db.scene_tone,
        })
        # Keep last 20 scenes
        room.db.room_history = history[-20:]

        # Delete temporary scene props (skip pinned ones)
        prop_count = 0
        for obj in list(room.contents):
            if (
                getattr(obj.db, "is_scene_prop", False)
                and not getattr(obj.db, "prop_persistent", False)
            ):
                obj.delete()
                prop_count += 1

        # Freeform cleanup: release slocks, clear unpinned sensory layers
        try:
            from world.freeform_manager import FreeformManager
            FreeformManager.end_scene(room)
        except Exception:
            pass

        # Reset scene state
        room.db.scene_active = False
        room.db.scene_started_at = None
        room.db.scene_log = []
        room.db.scene_title = None
        room.db.scene_prompt = None
        room.db.scene_tone = None
        room.db.content_warnings = []
        room.db.scene_locked = False
        room.db.scene_logging = False
        room.db.scene_invite_list = []
        room.db.scene_stage_desc = ""
        room.db.scene_details = {}
        room.db.scene_props = []
        room.db.pose_order = []

        prop_note = (
            f" {prop_count} prop(s) cleared."
            if prop_count else ""
        )
        room.msg_contents(
            f"|w[ Scene ended: {title} — {_fmt_duration(duration)} ]|n"
            f"\n|xSaved to room history. ({len(log)} lines logged)."
            f"{prop_note}|n"
        )

    def _lock(self, caller, room):
        room.db.scene_locked = True
        room.msg_contents("|x[ This room is now closed to new arrivals. ]|n")

    def _unlock(self, caller, room):
        room.db.scene_locked = False
        room.msg_contents("|x[ This room is now open. ]|n")

    def _log(self, caller, room):
        current = room.db.scene_logging or False
        room.db.scene_logging = not current
        if room.db.scene_logging:
            room.msg_contents("|x[ Scene logging ON. ]|n")
        else:
            room.msg_contents("|x[ Scene logging OFF. ]|n")

    def _title(self, caller, room):
        if not self.args:
            current = room.db.scene_title or "(none)"
            self.msg(f"Current scene title: |w{current}|n")
            return
        room.db.scene_title = self.args.strip()
        room.msg_contents(
            f"|x[ Scene title set: |w{room.db.scene_title}|n|x ]|n"
        )

    def _prompt(self, caller, room):
        """
        Set or clear the scene prompt.

        The prompt appears above the room description when set.
        Use it to give the current scene context, a shared goal,
        or a mood note that everyone in the room can see.

        Usage:
          scene/prompt <text>    -- set the prompt
          scene/prompt/clear     -- clear the prompt
          scene/prompt           -- see current prompt
        """
        if "clear" in self.switches:
            room.db.scene_prompt = None
            room.msg_contents("|x[ Scene prompt cleared. ]|n")
            return
        if not self.args:
            current = room.db.scene_prompt or "(none)"
            self.msg(f"Scene prompt: {current}")
            return
        room.db.scene_prompt = self.args.strip()
        room.msg_contents(
            f"|x[ Scene prompt: |w{room.db.scene_prompt}|n|x ]|n"
        )

    def _warn(self, caller, room):
        if "clear" in self.switches:
            room.db.content_warnings = []
            room.msg_contents("|x[ Content warnings cleared. ]|n")
            return
        if not self.args:
            warnings = room.db.content_warnings or []
            if warnings:
                self.msg(f"Current warnings: {', '.join(warnings)}")
            else:
                self.msg("No content warnings set.")
            return
        warnings = room.db.content_warnings or []
        tag = self.args.strip().lower()
        if tag not in warnings:
            warnings.append(tag)
            room.db.content_warnings = warnings
        room.msg_contents(
            f"|x[ Content warning added: |y{tag}|n|x ]|n"
        )

    def _tone(self, caller, room):
        if not self.args:
            current = room.db.scene_tone or "(none)"
            self.msg(f"Current tone: |w{current}|n")
            return
        room.db.scene_tone = self.args.strip().lower()
        room.msg_contents(
            f"|x[ Scene tone: |w{room.db.scene_tone}|n|x ]|n"
        )

    def _status(self, caller, room):
        sep = f"|w{'━' * 44}|n"
        title = room.db.scene_title or "(untitled)"
        active = room.db.scene_active or False
        locked = room.db.scene_locked or False
        logging = room.db.scene_logging or False
        log_count = len(room.db.scene_log or [])
        warnings = room.db.content_warnings or []
        tone = room.db.scene_tone or "(none)"
        prompt = room.db.scene_prompt or "(none)"
        invite_list = room.db.scene_invite_list or []
        pose_order = room.db.pose_order or []

        if active and room.db.scene_started_at:
            duration = _fmt_duration(time.time() - room.db.scene_started_at)
            active_str = f"|gYes|n — {duration}"
        elif active:
            active_str = "|gYes|n"
        else:
            active_str = "|xNo|n"

        lock_str = "|rLocked|n" if locked else "|gOpen|n"
        log_str = f"|gOn|n ({log_count} lines)" if logging else "|xOff|n"
        warn_str = ", ".join(f"|y{w}|n" for w in warnings) or "(none)"

        invite_names = []
        if invite_list:
            from evennia import search_object
            for cid in invite_list:
                try:
                    r = search_object(f"#{cid}")
                    if r:
                        invite_names.append(r[0].db.rp_name or r[0].name)
                except Exception:
                    pass
        invite_str = ", ".join(invite_names) or "(none)"

        po_names = _resolve_pose_order_names(room)
        po_str = " → ".join(po_names) if po_names else "(none)"

        self.msg(
            f"\n{sep}\n"
            f"|wSCENE STATUS|n  {room.key}\n"
            f"{sep}\n"
            f"  Title:      {title}\n"
            f"  Active:     {active_str}\n"
            f"  Lock:       {lock_str}\n"
            f"  Logging:    {log_str}\n"
            f"  Tone:       {tone}\n"
            f"  Warnings:   {warn_str}\n"
            f"  Prompt:     {prompt}\n"
            f"  Pose order: {po_str}\n"
            f"  Invites:    {invite_str}\n"
            f"{sep}"
        )

    def _read(self, caller, room):
        log = room.db.scene_log or []
        if not log:
            self.msg("The scene log is empty.")
            return
        sep = f"|w{'─' * 44}|n"
        title = room.db.scene_title or "Scene Log"
        lines = [
            f"\n{sep}",
            f"|w{title}|n",
            sep,
        ]
        for entry in log:
            ts = _fmt_timestamp(entry.get("time", 0))
            lines.append(f"|x[{ts}]|n {entry.get('text', '')}")
        lines.append(sep)
        self.msg("\n".join(lines))

    def _history(self, caller, room):
        history = room.db.room_history or []
        if not history:
            self.msg("No scenes have been saved for this room.")
            return
        sep = f"|w{'─' * 44}|n"
        lines = [f"\n{sep}", f"|wScene History|n  {room.key}", sep]
        for i, entry in enumerate(reversed(history), 1):
            title = entry.get("title", "untitled")
            started = _fmt_timestamp(entry.get("started", 0))
            duration = _fmt_duration(entry.get("duration", 0))
            log_count = len(entry.get("log", []))
            lines.append(
                f"  |w{i:>2}.|n {title:<28} "
                f"|x{started}  {duration}  {log_count} lines|n"
            )
        lines.append(sep)
        self.msg("\n".join(lines))

    def _invite(self, caller, room):
        if not self.args:
            self.msg("Invite whom? Usage: scene/invite <name>")
            return
        results = caller.search(
            self.args.strip(),
            quiet=True,
        )
        if not results:
            self.msg(f"Can't find '{self.args.strip()}'.")
            return
        target = results[0] if isinstance(results, list) else results
        invite_list = room.db.scene_invite_list or []
        if target.id not in invite_list:
            invite_list.append(target.id)
            room.db.scene_invite_list = invite_list
        tname = target.db.rp_name or target.name
        self.msg(f"{tname} added to the invite list.")
        target.msg(
            f"|xYou've been invited into |w{room.key}|n|x. "
            f"Head there to enter.|n"
        )

    def _uninvite(self, caller, room):
        if not self.args:
            self.msg("Uninvite whom? Usage: scene/uninvite <name>")
            return
        results = caller.search(self.args.strip(), quiet=True)
        if not results:
            self.msg(f"Can't find '{self.args.strip()}'.")
            return
        target = results[0] if isinstance(results, list) else results
        invite_list = room.db.scene_invite_list or []
        if target.id in invite_list:
            invite_list.remove(target.id)
            room.db.scene_invite_list = invite_list
        tname = target.db.rp_name or target.name
        self.msg(f"{tname} removed from the invite list.")


# -------------------------------------------------------------------
# CmdKnock
# -------------------------------------------------------------------

class CmdKnock(MuxCommand):
    """
    Let people in a locked room know you're waiting outside.

    If you're outside a locked room and want to enter, knock.
    Everyone inside will hear it. One of them can then use
    scene/invite <your name> to let you in.

    Usage:
      knock

    The command checks all exits from your current room and sends
    a notification to any locked destination rooms it finds.

    See also: scene/invite, scene/lock, scene/unlock
    """

    key = "knock"
    locks = "cmd:all()"
    help_category = "Scene"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            self.msg("You're not anywhere.")
            return

        name = caller.db.rp_name or caller.name
        notified = []

        for exit_obj in room.exits:
            destination = exit_obj.destination
            if destination and destination.db.scene_locked:
                destination.msg_contents(
                    f"|x[ Someone knocks — {name} is waiting outside. ]|n"
                )
                notified.append(destination.key)

        if notified:
            rooms_str = ", ".join(notified)
            self.msg(
                f"You knock. Those inside |w{rooms_str}|n will hear you."
            )
        else:
            self.msg(
                "There's no locked scene nearby to knock on."
            )


# -------------------------------------------------------------------
# Pose Order utilities
# -------------------------------------------------------------------

def _resolve_pose_order_names(room):
    """
    Return a list of display names for the current pose order queue.

    Reads room.db.pose_order (a list of character IDs) and resolves
    each to a name. IDs whose characters are no longer in the room
    are silently skipped.
    """
    from evennia import search_object
    order = room.db.pose_order or []
    names = []
    for cid in order:
        try:
            results = search_object(f"#{cid}")
            if results:
                char = results[0]
                names.append(char.db.rp_name or char.name)
        except Exception:
            pass
    return names


def _find_char_in_room(caller, name_str):
    """
    Find a character in the caller's current room by name string.
    Returns the object or None.
    """
    results = caller.search(
        name_str,
        location=caller.location,
        quiet=True,
    )
    if not results:
        return None
    return results[0] if isinstance(results, list) else results


# -------------------------------------------------------------------
# CmdPO — Pose Order
# -------------------------------------------------------------------

class CmdPO(MuxCommand):
    """
    Manage the pose order queue for the current scene.

    Pose order is a turn list — it keeps track of whose turn it is
    to pose. The person at the top of the queue is 'up'. When they
    pose, the queue advances to the next person.

    The queue is stored on the room. Anyone in the scene can join
    or see it. Anyone can advance the queue with 'po next' — there's
    no scene runner gating.

    Usage:
      po              -- show current queue
      po join         -- add yourself to the queue
      po leave        -- remove yourself from the queue
      po skip         -- skip your turn (moves you to the back)
      po next         -- advance to the next person in queue
      po reset        -- clear the queue entirely
      po add <name>   -- add someone else to the queue
      po remove <name>-- remove someone else from the queue

    Examples:
      po join
      po
        -> 1. Seraphine (up)   2. Ara   3. Mireille
      po next
        -> Queue advances: Ara is now up.

    See also: scene, pose
    """

    key = "po"
    locks = "cmd:all()"
    help_category = "Scene"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            self.msg("You need to be in a room to use pose order.")
            return

        args = self.args.strip().lower()
        parts = args.split(None, 1)
        sub = parts[0] if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if not sub:
            self._show(caller, room)
            return

        dispatch = {
            "join":   self._join,
            "leave":  self._leave,
            "skip":   self._skip,
            "next":   self._next,
            "reset":  self._reset,
            "add":    self._add,
            "remove": self._remove,
        }

        fn = dispatch.get(sub)
        if fn:
            fn(caller, room, rest)
        else:
            self.msg(
                "Usage: po [join|leave|skip|next|reset|add <name>|remove <name>]"
            )

    # ---------------------------------------------------------------

    def _show(self, caller, room):
        """Display the current pose order queue."""
        from evennia import search_object
        order = room.db.pose_order or []

        if not order:
            self.msg("|x[ Pose order is empty. Use 'po join' to add yourself. ]|n")
            return

        sep = f"|w{'─' * 44}|n"
        lines = [f"\n{sep}", "|wPose Order|n", sep]

        for i, cid in enumerate(order):
            try:
                results = search_object(f"#{cid}")
                name = (results[0].db.rp_name or results[0].name) if results else f"#{cid}"
            except Exception:
                name = f"#{cid}"

            if i == 0:
                lines.append(f"  |w{i + 1}.|n |g{name}|n  |x(up)|n")
            else:
                lines.append(f"  |w{i + 1}.|n {name}")

        lines.append(sep)
        self.msg("\n".join(lines))

    def _join(self, caller, room, rest):
        """Add the caller to the end of the pose order queue."""
        order = room.db.pose_order or []
        if caller.id in order:
            self.msg("|xYou are already in the pose order queue.|n")
            return
        order.append(caller.id)
        room.db.pose_order = order
        name = _char_name(caller)
        pos = len(order)
        room.msg_contents(
            f"|x[ {name} joined pose order — position {pos}. ]|n"
        )

    def _leave(self, caller, room, rest):
        """Remove the caller from the pose order queue."""
        order = room.db.pose_order or []
        if caller.id not in order:
            self.msg("|xYou are not in the pose order queue.|n")
            return
        order.remove(caller.id)
        room.db.pose_order = order
        name = _char_name(caller)
        room.msg_contents(f"|x[ {name} left pose order. ]|n")

    def _skip(self, caller, room, rest):
        """Move the caller to the back of the queue."""
        order = room.db.pose_order or []
        if caller.id not in order:
            self.msg("|xYou are not in the pose order queue.|n")
            return
        order.remove(caller.id)
        order.append(caller.id)
        room.db.pose_order = order
        name = _char_name(caller)
        room.msg_contents(f"|x[ {name} skipped their turn. ]|n")
        _announce_up(room)

    def _next(self, caller, room, rest):
        """Advance the queue — move the current first person to the back."""
        order = room.db.pose_order or []
        if not order:
            self.msg("|xPose order is empty.|n")
            return
        if len(order) == 1:
            self.msg("|xOnly one person in queue — nothing to advance.|n")
            return
        # Move the front to the back
        first = order.pop(0)
        order.append(first)
        room.db.pose_order = order
        _announce_up(room)

    def _reset(self, caller, room, rest):
        """Clear the pose order queue entirely."""
        room.db.pose_order = []
        name = _char_name(caller)
        room.msg_contents(f"|x[ Pose order reset by {name}. ]|n")

    def _add(self, caller, room, rest):
        """Add another character to the queue by name."""
        if not rest:
            self.msg("Add whom? Usage: po add <name>")
            return
        target = _find_char_in_room(caller, rest)
        if not target:
            self.msg(f"Can't find '{rest}' in this room.")
            return
        order = room.db.pose_order or []
        if target.id in order:
            tname = _char_name(target)
            self.msg(f"|x{tname} is already in the pose order queue.|n")
            return
        order.append(target.id)
        room.db.pose_order = order
        tname = _char_name(target)
        pos = len(order)
        room.msg_contents(
            f"|x[ {tname} added to pose order at position {pos}. ]|n"
        )

    def _remove(self, caller, room, rest):
        """Remove another character from the queue by name."""
        if not rest:
            self.msg("Remove whom? Usage: po remove <name>")
            return
        target = _find_char_in_room(caller, rest)
        if not target:
            self.msg(f"Can't find '{rest}' in this room.")
            return
        order = room.db.pose_order or []
        if target.id not in order:
            tname = _char_name(target)
            self.msg(f"|x{tname} is not in the pose order queue.|n")
            return
        was_first = order[0] == target.id
        order.remove(target.id)
        room.db.pose_order = order
        tname = _char_name(target)
        room.msg_contents(f"|x[ {tname} removed from pose order. ]|n")
        if was_first and order:
            _announce_up(room)


def _announce_up(room):
    """
    Send a notification to the room saying who is now 'up' in pose order.
    """
    from evennia import search_object
    order = room.db.pose_order or []
    if not order:
        return
    try:
        results = search_object(f"#{order[0]}")
        if results:
            name = results[0].db.rp_name or results[0].name
            room.msg_contents(f"|x[ Pose order: |w{name}|n|x is up. ]|n")
    except Exception:
        pass


# -------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------

ALL_SCENE_CMDS = [
    CmdScene,
    CmdKnock,
    CmdPO,
]
