"""
commands/proximity_commands.py

Proximity system for Re:Void.

A character's proximity state is a dict:
  char.db.proximity = {character_id: "near"/"with"}

You can be near/with multiple people simultaneously. Each entry is
independent — being "with" Alice does not affect your state with Bob.

Levels:
  (absent) / public  -- default; no special closeness
  near               -- close; unlocks intimate emotes
  with               -- side by side; unlocks mature and bdsm emotes

Proximity clears automatically on room change and on logout.

Commands:
  approach <name>     -- step closer to someone (absent->near->with)
  withdraw [name]     -- step back from someone, or from everyone
  beside <name>       -- go directly to "near" with someone
  prox                -- see your own proximity state
  prox/room           -- see all proximity pairs in the room
"""

from evennia.commands.default.muxcommand import MuxCommand
from evennia.objects.objects import DefaultCharacter
from typeclasses.characters import Character


def _name(char):
    """Return the character's display name."""
    return char.db.rp_name or char.name


def _get_level(char, target):
    """Return char's current proximity level toward target."""
    return (char.db.proximity or {}).get(target.id, "public")


def _set_level(char, target, level):
    """Set char's proximity toward target to level."""
    prox = char.db.proximity or {}
    prox[target.id] = level
    char.db.proximity = prox


def _set_level_mutual(char, target, level):
    """Set proximity both ways so both parties register the closeness."""
    _set_level(char, target, level)
    _set_level(target, char, level)


def _remove_mutual(char, target):
    """Remove proximity entry both ways."""
    _remove(char, target)
    _remove(target, char)


def _remove(char, target):
    """Remove char's proximity entry for target (back to public)."""
    prox = char.db.proximity or {}
    prox.pop(target.id, None)
    char.db.proximity = prox


# -------------------------------------------------------------------
# CmdApproach
# -------------------------------------------------------------------

class CmdApproach(MuxCommand):
    """
    Move closer to someone in the room.

    Each use steps one level closer toward that person:
      (none) --> near --> with

    You can be near or with multiple people at the same time.
    Approaching one person has no effect on your state with others.

    Usage:
      approach <name>

    Examples:
      approach Seraphine
      approach Seraphine    (again when already near -- moves to "with")

    See also: withdraw, beside, prox
    """

    key = "approach"
    aliases = ["app"]
    locks = "cmd:all()"
    help_category = "Proximity"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg("Approach whom? Usage: approach <name> [name ...]")
            return

        char_name = _name(char)
        # Support multiple names separated by commas or "and"
        raw = self.args.replace(" and ", ",").replace("  ", " ")
        names = [n.strip() for n in raw.split(",") if n.strip()]

        for name_str in names:
            results = char.search(name_str, location=char.location, quiet=True)
            if not results:
                self.msg(f"You don't see '{name_str}' here.")
                continue
            target = results[0] if isinstance(results, list) else results

            if target == char:
                self.msg("You can't approach yourself.")
                continue

            if not isinstance(target, DefaultCharacter):
                self.msg(f"You can only approach another person.")
                continue

            tname = _name(target)
            current = _get_level(char, target)

            if current == "with":
                self.msg(f"You're already as close as you can be to {tname}.")
                continue

            if current == "near":
                _set_level_mutual(char, target, "with")
                self.msg(f"You move to {tname}'s side.")
                target.msg(f"{char_name} moves to your side.")
                if char.location:
                    char.location.msg_contents(
                        f"{char_name} moves to {tname}'s side.",
                        exclude=[char, target],
                    )
            else:
                _set_level_mutual(char, target, "near")
                self.msg(f"You drift closer to {tname}.")
                target.msg(f"{char_name} drifts closer to you.")
                if char.location:
                    char.location.msg_contents(
                        f"{char_name} drifts closer to {tname}.",
                        exclude=[char, target],
                    )


# -------------------------------------------------------------------
# CmdWithdraw
# -------------------------------------------------------------------

class CmdWithdraw(MuxCommand):
    """
    Step back from someone you're near or with.

    With a name: steps back from that specific person only.
    Without a name: steps back from everyone at once.

    Each named use steps one level back:
      with --> near --> (gone)

    Usage:
      withdraw            -- step back from everyone
      withdraw <name>     -- step back from one person

    Examples:
      withdraw
      withdraw Seraphine

    See also: approach, beside, prox
    """

    key = "withdraw"
    aliases = ["wd"]
    locks = "cmd:all()"
    help_category = "Proximity"

    def func(self):
        char = self.caller
        proximity = char.db.proximity or {}

        # No args — withdraw from everyone
        if not self.args:
            if not proximity:
                self.msg(
                    "You're not particularly close to anyone right now."
                )
                return
            char_name = _name(char)
            # Notify everyone and clear
            from evennia import search_object
            for partner_id in list(proximity.keys()):
                try:
                    results = search_object(f"#{partner_id}")
                    if results:
                        results[0].msg(
                            f"{char_name} steps back from you."
                        )
                except Exception:
                    pass
            char.db.proximity = {}
            if char.location:
                char.location.msg_contents(
                    f"{char_name} steps back.",
                    exclude=char,
                )
            self.msg("You step back.")
            return

        # Named target — step back from that person only
        results = char.search(
            self.args.strip(),
            location=char.location,
            quiet=True,
        )
        if not results:
            self.msg(f"You don't see '{self.args.strip()}' here.")
            return
        target = results[0] if isinstance(results, list) else results

        if target == char:
            self.msg("You can't withdraw from yourself.")
            return

        char_name = _name(char)
        tname = _name(target)
        current = _get_level(char, target)

        if current == "public":
            self.msg(f"You're not particularly close to {tname}.")
            return

        if current == "with":
            # with -> near
            _set_level(char, target, "near")
            self.msg(f"You draw back slightly from {tname}.")
            target.msg(f"{char_name} draws back slightly.")
            if char.location:
                char.location.msg_contents(
                    f"{char_name} draws back slightly from {tname}.",
                    exclude=[char, target],
                )
        else:
            # near -> public
            _remove(char, target)
            self.msg(f"You step back from {tname}.")
            target.msg(f"{char_name} steps back from you.")
            if char.location:
                char.location.msg_contents(
                    f"{char_name} steps back from {tname}.",
                    exclude=[char, target],
                )


# -------------------------------------------------------------------
# CmdBeside
# -------------------------------------------------------------------

class CmdBeside(MuxCommand):
    """
    Move to stand near someone without going all the way to "with".

    Always lands at "near" regardless of where you started.
    Use 'approach' twice if you want to reach "with".

    Usage:
      beside <name>

    Examples:
      beside Seraphine

    See also: approach, withdraw, prox
    """

    key = "beside"
    aliases = ["near"]
    locks = "cmd:all()"
    help_category = "Proximity"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg("Stand beside whom? Usage: beside <name>")
            return

        char_name = _name(char)
        raw = self.args.replace(" and ", ",").replace("  ", " ")
        names = [n.strip() for n in raw.split(",") if n.strip()]

        for name_str in names:
            results = char.search(name_str, location=char.location, quiet=True)
            if not results:
                self.msg(f"You don't see '{name_str}' here.")
                continue
            target = results[0] if isinstance(results, list) else results

            if target == char:
                self.msg("You're already beside yourself.")
                continue

            if not isinstance(target, DefaultCharacter):
                self.msg("You can only stand beside another person.")
                continue

            tname = _name(target)
            current = _get_level(char, target)

            if current in ("near", "with"):
                self.msg(f"You're already near {tname}.")
                continue

            _set_level_mutual(char, target, "near")
            self.msg(f"You move to stand beside {tname}.")
            target.msg(f"{char_name} moves to stand beside you.")
            if char.location:
                char.location.msg_contents(
                    f"{char_name} moves to stand beside {tname}.",
                    exclude=[char, target],
                )


# -------------------------------------------------------------------
# CmdProx
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# CmdAside
# -------------------------------------------------------------------

class CmdAside(MuxCommand):
    """
    Draw one or more people aside for a more private exchange.

    Jumps directly to "with" for all named people at once, no stepping
    required. Useful when you want a semi-private conversation in a busy
    space, or when closeness with multiple people at once is the point.

    Usage:
      aside <name>
      aside <name>, <name>
      aside <name> and <name>

    Examples:
      aside Seraphine
      aside Seraphine, Rook
      aside Seraphine and Rook

    See also: approach, withdraw, beside, prox
    """

    key = "aside"
    aliases = []
    locks = "cmd:all()"
    help_category = "Proximity"

    def func(self):
        char = self.caller

        if not self.args:
            self.msg("Draw whom aside? Usage: aside <name> [, <name> ...]")
            return

        char_name = _name(char)
        raw = self.args.replace(" and ", ",").replace("  ", " ")
        names = [n.strip() for n in raw.split(",") if n.strip()]

        drawn = []
        for name_str in names:
            results = char.search(name_str, location=char.location, quiet=True)
            if not results:
                self.msg(f"You don't see '{name_str}' here.")
                continue
            target = results[0] if isinstance(results, list) else results

            if target == char:
                self.msg("You can't draw yourself aside.")
                continue

            if not isinstance(target, DefaultCharacter):
                self.msg("You can only draw another person aside.")
                continue

            _set_level_mutual(char, target, "with")
            drawn.append(target)

        if not drawn:
            return

        drawn_names = [_name(t) for t in drawn]
        if len(drawn_names) == 1:
            name_list = drawn_names[0]
        elif len(drawn_names) == 2:
            name_list = f"{drawn_names[0]} and {drawn_names[1]}"
        else:
            name_list = ", ".join(drawn_names[:-1]) + f", and {drawn_names[-1]}"

        self.msg(f"You draw {name_list} aside into a quieter corner.")
        for target in drawn:
            target.msg(f"{char_name} draws you aside into a quieter corner.")
        if char.location:
            char.location.msg_contents(
                f"{char_name} draws {name_list} aside.",
                exclude=[char] + drawn,
            )


class CmdProx(MuxCommand):
    """
    Check your current proximity state, or see who is near/with whom
    in the room.

    Usage:
      prox              -- see your own state
      prox/room         -- see all proximity pairs in the room

    Proximity levels:
      near    -- close; unlocks intimate emotes
      with    -- side by side; unlocks mature and bdsm emotes

    See also: approach, withdraw, beside
    """

    key = "prox"
    aliases = ["proximity"]
    locks = "cmd:all()"
    help_category = "Proximity"

    def func(self):
        char = self.caller
        if "room" in self.switches or "all" in self.switches:
            self._show_room(char)
        else:
            self._show_self(char)

    def _show_self(self, char):
        proximity = char.db.proximity or {}
        if not proximity:
            self.msg(
                "You're not close to anyone in particular right now."
            )
            return

        from evennia import search_object
        lines = ["|wYour current proximity:|n"]
        for partner_id, level in proximity.items():
            try:
                results = search_object(f"#{partner_id}")
                pname = _name(results[0]) if results else f"#{partner_id}"
            except Exception:
                pname = f"#{partner_id}"
            level_note = {
                "near": "|x(intimate emotes unlocked)|n",
                "with": "|x(mature/bdsm emotes unlocked)|n",
            }.get(level, "")
            lines.append(f"  |w{level}|n {pname}  {level_note}")
        self.msg("\n".join(lines))

    def _show_room(self, char):
        if not char.location:
            self.msg("You're not in a room.")
            return

        chars = [
            obj for obj in char.location.contents
            if isinstance(obj, Character)
        ]

        from evennia import search_object
        lines = []
        seen_pairs = set()

        for c in chars:
            prox = c.db.proximity or {}
            for partner_id, level in prox.items():
                pair_key = tuple(sorted([c.id, partner_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                try:
                    results = search_object(f"#{partner_id}")
                    pname = _name(results[0]) if results else f"#{partner_id}"
                except Exception:
                    pname = f"#{partner_id}"
                cname = _name(c)
                lines.append(f"  {cname} is |w{level}|n {pname}.")

        if not lines:
            self.msg(
                "No one here is particularly close to anyone else."
            )
            return

        sep = f"|w{'─' * 40}|n"
        self.msg(
            f"\n{sep}\n"
            f"|wProximity in this room|n\n"
            f"{sep}\n"
            + "\n".join(lines)
            + f"\n{sep}"
        )
