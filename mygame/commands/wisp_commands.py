"""
commands/wisp_commands.py

Account-level commands for the wisp identity system.
These commands are available when the player is OOC (in wisp state)
and do not require an active character puppet.

Commands:
    mood        — set wisp mood
    wdesc       — set custom wisp description
    wcolor      — set custom wisp color
    wsize       — set wisp size
    wsignature  — set persistent signature element
    wsound      — set wisp sound description
    wambient    — manage personal ambient pool
    wpreview    — preview assembled wisp appearance
    haunt       — toggle haunting ambient
    reveal      — reveal wisp to specific player
    conceal     — conceal wisp from specific player
    wisp        — toggle wisp visibility preference
    score       — account overview
    ic          — enter a character
    ooc         — return to wisp state (from character)
    characters  — list account characters
"""

from evennia.commands.default.muxcommand import MuxCommand


# Valid moods with their color defaults
VALID_MOODS = [
    "uncertain", "curious", "melancholy", "bold",
    "playful", "serene", "intense", "tender",
    "anxious", "content", "restless", "reverent",
]

# Valid wisp sizes
VALID_SIZES = ["small", "medium", "large", "vast"]


class CmdMood(MuxCommand):
    """
    Set your wisp's current mood.

    The mood drives your wisp's color, description pool,
    ambient contribution, and say modifier.

    Usage:
        mood                    — see current mood
        mood <word>             — set mood
        mood/list               — see all valid moods

    Examples:
        mood curious
        mood melancholy
        mood playful

    Your mood is visible to others when they look at your wisp.
    It also carries forward when you log into a character.
    """
    key = "mood"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account

        if "list" in self.switches:
            mood_list = ", ".join(VALID_MOODS)
            self.msg(f"Available moods:\n  {mood_list}")
            return

        if not self.args:
            current = account.wisp_mood
            color = account.wisp_color_code
            color_desc = account.wisp_color_display
            self.msg(
                f"Current mood: {color}{current}|n\n"
                f"Current color: {color}{color_desc}|n\n"
                f"Type 'mood <word>' to change it."
            )
            return

        new_mood = self.args.strip().lower()

        if new_mood not in VALID_MOODS:
            mood_list = ", ".join(VALID_MOODS)
            self.msg(
                f"'{new_mood}' isn't a recognized mood.\n"
                f"Valid moods: {mood_list}\n"
                f"Or use 'wdesc' to write a fully custom description."
            )
            return

        account.db.wisp_mood = new_mood
        color = account.wisp_color_code
        color_desc = account.wisp_color_display

        if not account.db.wisp_color:
            self.msg(
                f"Mood set to {color}{new_mood}|n.\n"
                f"Your light shifts — {color}{color_desc}|n.\n"
                f"Type 'wpreview' to see your full appearance."
            )
        else:
            self.msg(
                f"Mood set to {color}{new_mood}|n.\n"
                f"Your custom color is unchanged.\n"
                f"Type 'wpreview' to see your full appearance."
            )


class CmdWDesc(MuxCommand):
    """
    Set your wisp's base description.

    By default your wisp uses a system-generated description
    based on your mood. Use this command to write your own.

    Usage:
        wdesc               — see current description
        wdesc <text>        — set custom description
        wdesc/clear         — return to system-generated description

    Example:
        wdesc Something bright and considerably larger than a wisp
        usually is — gold at the center, shifting at the edges
        toward orange and back.

    Your description is what others see when they look at your wisp.
    The mood tag and identity line are always appended by the system.
    """
    key = "wdesc"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account

        if "clear" in self.switches:
            account.db.wisp_desc = None
            self.msg(
                "Custom wisp description cleared.\n"
                "Your description will now be drawn from "
                "the system pool based on your mood."
            )
            return

        if not self.args:
            current = account.db.wisp_desc
            if current:
                self.msg(
                    f"Your current wisp description:\n\n"
                    f"{current}\n\n"
                    f"Use 'wdesc/clear' to return to "
                    f"system-generated description."
                )
            else:
                self.msg(
                    "You are using the system-generated description "
                    f"for mood: {account.wisp_mood}\n"
                    f"Use 'wdesc <text>' to write your own."
                )
            return

        new_desc = self.args.strip()

        if len(new_desc) < 10:
            self.msg(
                "Description is too short. "
                "Write something meaningful."
            )
            return

        if len(new_desc) > 2000:
            self.msg(
                f"Description is too long "
                f"({len(new_desc)} characters). "
                f"Keep it under 2000 characters."
            )
            return

        account.db.wisp_desc = new_desc
        self.msg(
            "Wisp description set.\n"
            "Type 'wpreview' to see your full assembled appearance."
        )


class CmdWColor(MuxCommand):
    """
    Set your wisp's color, overriding the mood default.

    Usage:
        wcolor                  — see current color
        wcolor <description>    — set custom color
        wcolor/clear            — return to mood-driven color
        wcolor/list             — see mood default colors

    Example:
        wcolor gold at the center, shifting at the edges
        toward orange and back, unable to commit to one temperature

    The color description appears in your wisp's look output
    and in the WHO list.
    """
    key = "wcolor"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account

        if "clear" in self.switches:
            account.db.wisp_color = None
            color = account.wisp_color_code
            self.msg(
                "Custom color cleared.\n"
                f"Your color will now follow your mood: "
                f"{color}{account.wisp_mood}|n → "
                f"{color}{account.wisp_color_display}|n"
            )
            return

        if "list" in self.switches:
            try:
                from world.pool_loader import load_pool
                pools = load_pool("wisp", "colors")
                mood_colors = pools.get("mood_colors", {})
                lines = ["|wMood default colors:|n\n"]
                for mood, data in mood_colors.items():
                    code = data.get("code", "|w")
                    base = data.get("base", "undefined")
                    lines.append(
                        f"  {code}{mood:<12}|n — {code}{base}|n"
                    )
                self.msg("\n".join(lines))
            except Exception:
                self.msg("Color list unavailable.")
            return

        if not self.args:
            custom = account.db.wisp_color
            color = account.wisp_color_code
            if custom:
                self.msg(
                    f"Your custom color: {color}{custom}|n"
                )
            else:
                self.msg(
                    f"Using mood default: "
                    f"{color}{account.wisp_color_display}|n\n"
                    f"Use 'wcolor <description>' to set a custom color."
                )
            return

        account.db.wisp_color = self.args.strip()
        self.msg(
            f"Wisp color set to: {self.args.strip()}\n"
            f"Type 'wpreview' to see your full appearance."
        )


class CmdWSize(MuxCommand):
    """
    Set your wisp's physical scale.

    Usage:
        wsize               — see current size
        wsize <size>        — set size

    Valid sizes:
        small   — close to the floor, concentrated light
        medium  — standard (default)
        large   — substantial, light reaching further than usual
        vast    — diffuse, spread through the upper air

    Example:
        wsize large
    """
    key = "wsize"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        color = account.wisp_color_code

        if not self.args:
            current = account.db.wisp_size or "medium"
            self.msg(f"Current wisp size: {color}{current}|n")
            return

        new_size = self.args.strip().lower()

        if new_size not in VALID_SIZES:
            self.msg(
                f"'{new_size}' is not a valid size.\n"
                f"Valid sizes: {', '.join(VALID_SIZES)}"
            )
            return

        account.db.wisp_size = new_size
        self.msg(f"Wisp size set to: {color}{new_size}|n")


class CmdWSignature(MuxCommand):
    """
    Set your wisp's persistent signature element.

    The signature is a detail that appears in your wisp's
    description regardless of mood or color changes.
    It's what makes your wisp recognizable as specifically yours.

    Usage:
        wsignature              — see current signature
        wsignature <text>       — set signature
        wsignature/clear        — remove signature

    Example:
        wsignature Always trailing a sound like a single piano
        key struck once, fading — regardless of what color
        or mood the rest of it is.
    """
    key = "wsignature"
    aliases = ["wsig"]
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        color = account.wisp_color_code

        if "clear" in self.switches:
            account.db.wisp_signature = None
            self.msg("Signature element cleared.")
            return

        if not self.args:
            current = account.db.wisp_signature
            if current:
                self.msg(
                    f"Your signature element:\n\n"
                    f"{color}{current}|n"
                )
            else:
                self.msg(
                    "No signature element set.\n"
                    "Use 'wsignature <text>' to set one."
                )
            return

        account.db.wisp_signature = self.args.strip()
        self.msg(
            "Signature element set.\n"
            "It will appear in your description regardless "
            "of mood changes."
        )


class CmdWAmbient(MuxCommand):
    """
    Manage your wisp's personal ambient contribution pool.

    These lines are added to the ambient pool of any room
    you're in as a wisp. They fire periodically alongside
    the room's own ambient messages.

    Usage:
        wambient                — list current ambient lines
        wambient add <line>     — add a line to your pool
        wambient remove <#>     — remove a line by number
        wambient clear          — clear all custom lines

    Example:
        wambient add The gold light drifts in a long,
        unhurried arc through the space.

    Use {name} as a placeholder for your account name.
    """
    key = "wambient"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        pool = account.db.wisp_ambient_pool or []
        color = account.wisp_color_code

        if "clear" in self.switches:
            account.db.wisp_ambient_pool = []
            self.msg("Personal ambient pool cleared.")
            return

        if "add" in self.switches or (
            self.args and not self.switches
        ):
            if not self.args:
                self.msg("Add what? Usage: wambient add <line>")
                return

            new_line = self.args.strip()
            if len(new_line) < 5:
                self.msg("Ambient line is too short.")
                return

            pool.append(new_line)
            account.db.wisp_ambient_pool = pool
            self.msg(
                f"Ambient line added (#{len(pool)}):\n"
                f"  {color}{new_line}|n"
            )
            return

        if "remove" in self.switches:
            if not self.args:
                self.msg(
                    "Remove which line? "
                    "Usage: wambient remove <number>"
                )
                return
            try:
                idx = int(self.args.strip()) - 1
                if idx < 0 or idx >= len(pool):
                    self.msg(
                        f"No line #{idx + 1}. "
                        f"You have {len(pool)} lines."
                    )
                    return
                removed = pool.pop(idx)
                account.db.wisp_ambient_pool = pool
                self.msg(f"Removed: {removed}")
            except ValueError:
                self.msg("Please provide a number.")
            return

        if not pool:
            self.msg(
                "Your personal ambient pool is empty.\n"
                "Use 'wambient add <line>' to add lines."
            )
            return

        lines = ["|wYour personal ambient pool:|n\n"]
        for i, line in enumerate(pool, 1):
            lines.append(f"  {i}. {color}{line}|n")
        self.msg("\n".join(lines))


class CmdWPreview(MuxCommand):
    """
    Preview your wisp's assembled appearance.

    Shows exactly what others see when they look at your wisp,
    assembled from all your current settings.

    Usage:
        wpreview            — standard look preview
        wpreview/deep       — deep examine preview
        wpreview/presence   — room presence line preview
    """
    key = "wpreview"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        color = account.wisp_color_code
        sep = f"{color}{'━' * 40}|n"

        if "presence" in self.switches:
            line = account.get_wisp_presence_line()
            self.msg(f"Your room presence line:\n\n  {line}")
            return

        deep = "deep" in self.switches
        appearance = account.get_wisp_appearance(deep=deep)
        label = "deep examine" if deep else "standard look"

        self.msg(
            f"Your wisp appearance ({label}):\n"
            f"{sep}\n"
            f"{appearance}\n"
            f"{sep}\n"
            f"|xCommands: mood / wdesc / wcolor / wsize / "
            f"wsignature / wambient|n"
        )


class CmdHaunt(MuxCommand):
    """
    Toggle whether your wisp contributes haunting ambient
    lines to rooms you're in while invisible.

    When haunting is on, your personal ambient pool and
    mood-based ambient lines will occasionally fire in
    the room — visible to IC characters as atmospheric
    messages with no obvious source.

    Usage:
        haunt           — see current state
        haunt on        — enable haunting
        haunt off       — disable haunting

    Note: Haunting only works when you are invisible
    in the room (outside the Hub, and not revealed).
    In the Hub your wisp is always visible.
    """
    key = "haunt"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        current = account.db.wisp_haunt or False
        color = account.wisp_color_code

        if not self.args:
            state = "on" if current else "off"
            self.msg(f"Haunting is currently: {color}{state}|n")
            return

        arg = self.args.strip().lower()

        if arg == "on":
            account.db.wisp_haunt = True
            self.msg(
                f"Haunting {color}enabled|n.\n"
                "Your ambient lines will contribute to rooms "
                "while you are invisible.\n"
                "IC characters will see them as atmospheric "
                "messages with no obvious source."
            )
        elif arg == "off":
            account.db.wisp_haunt = False
            self.msg(
                "Haunting |wdisabled|n.\n"
                "You are completely undetectable "
                "in rooms where you are invisible."
            )
        else:
            self.msg("Usage: haunt on / haunt off")


class CmdReveal(MuxCommand):
    """
    Reveal your wisp to a specific player, or conceal it again.

    By default your wisp is invisible to IC characters
    outside the Hub. Use this command to make yourself
    visible to a specific person.

    Usage:
        reveal <name>       — reveal to this player's account
        reveal/all          — reveal to everyone in the room
        conceal <name>      — conceal from this player again
        conceal/all         — conceal from everyone

    The revealed player will see your wisp in the room
    listing regardless of their wisp preference setting.
    """
    key = "reveal"
    aliases = ["conceal"]
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        concealing = self.cmdstring == "conceal"

        if "all" in self.switches:
            if concealing:
                account.db.wisp_revealed_to = set()
                self.msg(
                    "Concealed from everyone.\n"
                    "Only players with 'wisp visible' set "
                    "can see you."
                )
            else:
                location = account.db.wisp_location
                if not location:
                    self.msg(
                        "You don't have a current location."
                    )
                    return

                revealed = account.db.wisp_revealed_to or set()
                count = 0
                for obj in location.contents:
                    if (hasattr(obj, 'account') and
                            obj.account and
                            obj.account != account):
                        revealed.add(obj.account.id)
                        obj.msg(
                            f"\n|xA wisp becomes visible — "
                            f"{account.get_wisp_presence_line()}|n"
                        )
                        count += 1
                account.db.wisp_revealed_to = revealed
                self.msg(
                    f"Revealed to {count} character(s) in "
                    f"{location.key}."
                )
            return

        if not self.args:
            action = "conceal" if concealing else "reveal"
            self.msg(f"Usage: {action} <player name>")
            return

        from evennia import search_account
        results = search_account(self.args.strip())

        if not results:
            self.msg(f"No account found: {self.args.strip()}")
            return

        target_account = results[0]

        if target_account == account:
            self.msg("You can't reveal yourself to yourself.")
            return

        if concealing:
            account.conceal_from(target_account)
            self.msg(
                f"Concealed from |w{target_account.name}|n.\n"
                f"They can no longer see your wisp unless "
                f"they have 'wisp visible' set."
            )
        else:
            account.reveal_to(target_account)
            self.msg(
                f"Revealed to |w{target_account.name}|n.\n"
                f"They can now see your wisp in any room."
            )
            sessions = target_account.sessions.get()
            if sessions:
                target_puppet = target_account.get_puppet(
                    sessions[0]
                )
                if target_puppet:
                    target_puppet.msg(
                        f"\n|xA wisp becomes visible nearby — "
                        f"{account.get_wisp_presence_line()}|n"
                    )


class CmdWispPref(MuxCommand):
    """
    Set your preference for seeing other wisps.

    Usage:
        wisp                — see current preference
        wisp visible        — see all wisps in all rooms
        wisp hidden         — see wisps only in the Hub
                              (and those revealed to you)

    When set to visible, all wisps appear in room listings
    for you, marked with ~ to distinguish from IC characters.

    This is a personal setting — it doesn't affect what
    other players see.
    """
    key = "wisp"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        current = account.db.wisp_preference or "hidden"
        color = account.wisp_color_code

        if not self.args:
            self.msg(
                f"Wisp visibility preference: "
                f"{color}{current}|n\n"
                f"  |whidden|n  — wisps only visible in Hub "
                f"and those revealed to you\n"
                f"  |wvisible|n — all wisps visible everywhere"
            )
            return

        arg = self.args.strip().lower()

        if arg == "visible":
            account.db.wisp_preference = "visible"
            self.msg(
                "Wisp preference set to |wvisible|n.\n"
                "You will now see all wisps in all rooms,\n"
                "marked with ~ in room listings."
            )
        elif arg == "hidden":
            account.db.wisp_preference = "hidden"
            self.msg(
                "Wisp preference set to |whidden|n.\n"
                "Wisps only visible to you in the Hub\n"
                "or when specifically revealed to you."
            )
        else:
            self.msg("Usage: wisp visible / wisp hidden")


class CmdWispScore(MuxCommand):
    """
    View your account overview.

    Shows wisp identity, characters, consent flags,
    and account preferences.

    Usage:
        score
        sc
    """
    key = "score"
    aliases = ["sc"]
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        self.msg(self.account.get_account_score())


class CmdWispWho(MuxCommand):
    """
    See who is currently connected.

    Shows IC characters with their location and title,
    and OOC wisps with their account name and location.

    Usage:
        who             — full formatted who list
        qw              — quick compact who list
    """
    key = "who"
    aliases = ["qw"]
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        from evennia import SESSION_HANDLER

        sessions = SESSION_HANDLER.get_sessions()
        ic_entries = []
        ooc_entries = []

        for session in sessions:
            acct = session.get_account()
            if not acct:
                continue

            puppet = session.get_puppet()

            if puppet:
                name = (
                    puppet.db.rp_name
                    if hasattr(puppet.db, 'rp_name')
                    and puppet.db.rp_name
                    else puppet.key
                )

                title = ""
                if hasattr(puppet, 'get_full_title'):
                    title = puppet.get_full_title() or ""

                location = puppet.location
                if location:
                    hide = (
                        getattr(
                            location.db, 'hide_from_who', False
                        )
                        or getattr(
                            location.db, 'scene_locked', False
                        )
                    )
                    loc_display = (
                        "somewhere private" if hide
                        else location.key
                    )
                else:
                    loc_display = "unknown"

                ic_entries.append({
                    "name":     name,
                    "title":    title,
                    "location": loc_display,
                    "hidden":   loc_display == "somewhere private",
                })

            else:
                wisp_loc = acct.db.wisp_location
                loc_display = (
                    wisp_loc.key if wisp_loc
                    else "The Forming"
                )

                ooc_entries.append({
                    "account":  acct.name,
                    "location": loc_display,
                    "mood":     acct.wisp_mood,
                    "color":    acct.wisp_color_code,
                })

        if self.cmdstring == "qw":
            self.msg(
                self._format_quick(ic_entries, ooc_entries)
            )
        else:
            self.msg(
                self._format_full(ic_entries, ooc_entries)
            )

    def _format_full(self, ic, ooc):
        sep = "|w" + "━" * 44 + "|n"
        lines = [f"\n{sep}", ""]

        if ic:
            lines.append("|wIC — In Character|n\n")
            for entry in ic:
                title = entry["title"]
                name = entry["name"]
                loc = entry["location"]
                loc_str = f"[ {loc} ]"

                # Name line — right-pad to align location
                name_line = f"  |w{name}|n"
                pad = max(1, 34 - len(name))
                lines.append(
                    f"{name_line}{' ' * pad}{loc_str}"
                )

                # Title on its own line, indented, if present
                if title:
                    lines.append(f"  |x{title}|n")

                lines.append("")

        lines.append(sep)

        if ooc:
            lines.append("\n|wOOC — Wisp|n\n")
            for entry in ooc:
                acct = entry["account"]
                loc = entry["location"]
                mood = entry["mood"]
                color = entry["color"]
                pad = max(1, 30 - len(acct))
                lines.append(
                    f"  {color}{acct}|n{' ' * pad}"
                    f"|x{{OOC — {loc}}}|n  "
                    f"{color}{mood}|n"
                )
            lines.append("")

        lines.append(sep)
        total = len(ic) + len(ooc)
        lines.append(
            f"\n  {total} connected  |  "
            f"{len(ic)} IC  |  "
            f"{len(ooc)} OOC\n"
        )

        return "\n".join(lines)

    def _format_quick(self, ic, ooc):
        lines = []

        if ic:
            ic_parts = " · ".join(
                f"|w{e['name']}|n "
                f"[{'private' if e['hidden'] else e['location']}]"
                for e in ic
            )
            lines.append(f"IC:   {ic_parts}")

        if ooc:
            ooc_parts = " · ".join(
                f"{e['color']}{e['account']}|n "
                f"|x{{{e['location']}}}|n"
                for e in ooc
            )
            lines.append(f"OOC:  {ooc_parts}")

        if not lines:
            lines.append("Nobody is connected.")

        return "\n".join(lines)


class CmdIC(MuxCommand):
    """
    Enter one of your characters from wisp state.

    Usage:
        ic              — enter your only/default character
        ic <name>       — enter a specific character

    If you have only one character, 'ic' alone works.
    If you have multiple, you must specify which one.
    """
    key = "ic"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        characters = account.characters.all()

        if not characters:
            self.msg(
                "You have no characters yet.\n"
                "Type '@charcreate <name>' to make one."
            )
            return

        if not self.args:
            if len(characters) == 1:
                target_char = characters[0]
            else:
                lines = [
                    "Which character? Use 'ic <name>':\n"
                ]
                for char in characters:
                    lines.append(f"  |w{char.key}|n")
                self.msg("\n".join(lines))
                return
        else:
            char_name = self.args.strip()
            matches = [
                c for c in characters
                if c.key.lower() == char_name.lower()
            ]
            if not matches:
                char_list = ", ".join(
                    c.key for c in characters
                )
                self.msg(
                    f"No character named '{char_name}'.\n"
                    f"Your characters: {char_list}"
                )
                return
            target_char = matches[0]

        session = self.session
        try:
            account.puppet_object(session, target_char)
            account.db.wisp_location = None
        except Exception as e:
            self.msg(
                f"Could not enter {target_char.key}: {e}"
            )


class CmdCharacters(MuxCommand):
    """
    List your characters.

    Usage:
        characters
        chars
    """
    key = "characters"
    aliases = ["chars"]
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        characters = account.characters.all()
        color = account.wisp_color_code

        if not characters:
            self.msg(
                "You have no characters yet.\n"
                "Type '@charcreate <name>' to make one."
            )
            return

        lines = ["|wYour characters:|n\n"]
        for i, char in enumerate(characters, 1):
            loc = char.location
            loc_name = loc.key if loc else "unknown"

            title = ""
            if hasattr(char, 'get_full_title'):
                title = char.get_full_title() or ""

            lines.append(f"  {i}. |w{char.key}|n")
            if title:
                lines.append(f"     |x{title}|n")
            lines.append(
                f"     Last location: {color}{loc_name}|n"
            )
            lines.append("")

        lines.append(
            "Type 'ic <name>' to enter a character.\n"
            "Type '@charcreate <name>' to create a new character."
        )

        self.msg("\n".join(lines))


class CmdOOC(MuxCommand):
    """
    Step out of your character and return to wisp state.

    Usage:
        ooc

    This returns you to your wisp identity. Your character
    remains where they are — they will be there when you
    return with 'ic <name>'.
    """
    key = "ooc"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        session = self.session

        puppet = account.get_puppet(session)
        if not puppet:
            self.msg("You are already in wisp state.")
            return

        char_location = puppet.location
        char_name = puppet.key

        account.unpuppet_object(session)
        account.db.wisp_location = char_location

        color = account.wisp_color_code
        mood = account.wisp_mood

        loc_name = char_location.key if char_location else "their last location"

        self.msg(
            f"\n|x{char_name} steps back — the edges of them soften,\n"
            f"the specific giving way to light.|n\n\n"
            f"{color}[ wisp: {account.name} | mood: {mood} ]|n\n"
            f"|x{char_name} remains in {loc_name}.|n\n"
            f"Type '|wic {char_name}|n' to return."
        )


# ===================================================================
# WISP COMMUNICATION — shared utilities
# ===================================================================

def _wisp_msg_room(account, room, visible_msg, invisible_msg,
                   exclude_self=True):
    """
    Send different messages to room occupants based on wisp visibility.

    Those who can see the wisp get visible_msg.
    Those who can't get invisible_msg (pass None to send nothing).

    Args:
        account: The wisp's Account object.
        room: The Room to broadcast to.
        visible_msg (str): Shown to observers who can see the wisp.
        invisible_msg (str|None): Shown to observers who can't.
        exclude_self (bool): Skip the wisp's own account if they have
                             a puppet in the room.
    """
    from world.wisp_visibility import WispVisibility
    for obj in room.contents:
        if not (hasattr(obj, 'has_account') and obj.has_account):
            continue
        if exclude_self:
            if hasattr(obj, 'account') and obj.account == account:
                continue
        if WispVisibility.wisp_visible_to(account, obj, room):
            obj.msg(visible_msg)
        else:
            if invisible_msg is not None:
                obj.msg(invisible_msg)


def _wisp_check_location(cmd):
    """
    Return (account, room) if the wisp has a valid location,
    or (None, None) after messaging the caller.
    """
    account = cmd.account
    room = account.db.wisp_location
    if not room:
        cmd.msg(
            "|xYou are not in a location. "
            "Use 'ic <name>' to enter a character, "
            "or move to a room first.|n"
        )
        return None, None
    return account, room


# ===================================================================
# WISP COMMUNICATION — context-aware base commands
#
# These use the same keys as the character commands (say, pose, emote,
# whisper, mutter, shout) so players don't need a separate vocabulary
# for wisp state. Evennia resolves the correct version automatically:
# AccountCmdSet fires these; CharacterCmdSet fires the IC versions.
# ===================================================================

class CmdWispSay(MuxCommand):
    """
    Speak from the light.

    Usage:
        say <text>
        " <text>

    When visible, speech is attributed to the light.
    When invisible, it arrives as a sourceless voice.

    To change your say verb (default: says), use 'wvoice'.

    See also: pose, emote, whisper, mutter, shout, wvoice
    """

    key = "say"
    aliases = ['"']
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account, room = _wisp_check_location(self)
        if not account:
            return

        if not self.args:
            self.msg('Say what? Usage: say <text>  or  " <text>')
            return

        text = self.args.strip()
        color = account.wisp_color_code
        mood = account.wisp_mood
        verb = account.db.wisp_say_verb or "says"
        name = account.wisp_display_name or f"a {mood} wisp"

        # Caller
        self.msg(f'{color}Your light {verb}s, "{text}"|n')

        # Room — split on visibility
        visible_msg = f'{color}The {mood} light {verb}s, "{text}"|n'
        invisible_msg = f'A voice from nowhere — "{text}"'
        _wisp_msg_room(account, room, visible_msg, invisible_msg)

        # Scene log
        room.append_scene_log(name, f'[wisp] {name} {verb}s, "{text}"')


class CmdWispPose(MuxCommand):
    """
    Pose as the light — light description auto-prepended.

    Usage:
        pose <text>
        : <text>

    'The <mood> light' is prepended automatically.

    Example:
        pose drifts toward the window.
        → The curious light drifts toward the window.

    When invisible, the pose appears as an atmospheric, sourceless
    impression in the room.

    See also: emote, say
    """

    key = "pose"
    aliases = [":"]
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account, room = _wisp_check_location(self)
        if not account:
            return

        if not self.args:
            self.msg("Pose what? Usage: pose <text>  or  : <text>")
            return

        text = self.args.strip()
        color = account.wisp_color_code
        mood = account.wisp_mood
        name = account.wisp_display_name or f"a {mood} wisp"

        light = f"{color}The {mood} light|n"

        # Caller
        self.msg(f"{light} {text}")

        # Room — split on visibility
        visible_msg = f"{light} {text}"
        invisible_msg = f"|x{text}|n"
        _wisp_msg_room(account, room, visible_msg, invisible_msg)

        # Scene log
        room.append_scene_log(name, f"[wisp] The {mood} light {text}")


class CmdWispEmote(MuxCommand):
    """
    Freeform pose from the light — no attribution prepended.

    Usage:
        emote <text>
        ; <text>
        @ <text>

    You write the full text. When visible, it appears in your mood
    color. When invisible, it arrives as an atmospheric aside —
    no source, no attribution.

    Example:
        emote Something cold moves through the room.

    See also: pose, say
    """

    key = "emote"
    aliases = [";", "@"]
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account, room = _wisp_check_location(self)
        if not account:
            return

        if not self.args:
            self.msg("Emote what? Usage: emote <text>  or  ; <text>")
            return

        text = self.args.strip()
        color = account.wisp_color_code
        mood = account.wisp_mood
        name = account.wisp_display_name or f"a {mood} wisp"

        # Caller
        self.msg(f"{color}{text}|n")

        # Room — visible gets mood color, invisible gets atmospheric dim
        visible_msg = f"{color}{text}|n"
        invisible_msg = f"|x{text}|n"
        _wisp_msg_room(account, room, visible_msg, invisible_msg)

        # Scene log
        room.append_scene_log(name, f"[wisp emote] {text}")


class CmdWispWhisper(MuxCommand):
    """
    Whisper from the light to a specific person.

    Usage:
        whisper <name> = <text>
        whisper/page <name> = <text>    — reach someone in another room

    The room sees the light lean close. Only the target hears the words.
    The target always receives it regardless of their wisp visibility
    setting.

    See also: say, mutter, aside
    """

    key = "whisper"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account, room = _wisp_check_location(self)
        if not account:
            return

        if "page" in self.switches:
            self._page(account)
            return

        if "=" not in (self.args or ""):
            self.msg("Usage: whisper <name> = <text>")
            return

        name_str, _, text = self.args.partition("=")
        name_str = name_str.strip()
        text = text.strip()

        if not name_str or not text:
            self.msg("Usage: whisper <name> = <text>")
            return

        from evennia import search_object
        results = search_object(
            name_str,
            typeclass="typeclasses.characters.Character",
            location=room,
        )
        if not results:
            self.msg(f"No one named '{name_str}' is here.")
            return

        target = results[0]
        color = account.wisp_color_code
        mood = account.wisp_mood
        wname = account.wisp_display_name or f"a {mood} wisp"
        tname = target.db.rp_name or target.key

        # Caller
        self.msg(
            f'{color}You whisper to |w{tname}|n{color}, "{text}"|n'
        )

        # Target — always hears, regardless of wisp visibility
        target.msg(
            f'{color}Something from the light whispers, "{text}"|n'
        )

        # Room sees the lean, split on visibility
        visible_room = (
            f"{color}The {mood} light leans close to "
            f"|w{tname}|n{color}.|n"
        )
        invisible_room = (
            f"|xSomething seems to brush close to |w{tname}|n|x.|n"
        )
        _wisp_msg_room(account, room, visible_room, invisible_room)

        # Scene log
        room.append_scene_log(
            wname, f'[wisp whisper -> {tname}] "{text}"'
        )

    def _page(self, account):
        """Cross-room direct whisper."""
        if "=" not in (self.args or ""):
            self.msg("Usage: whisper/page <name> = <text>")
            return

        name_str, _, text = self.args.partition("=")
        name_str = name_str.strip()
        text = text.strip()

        if not name_str or not text:
            self.msg("Usage: whisper/page <name> = <text>")
            return

        from evennia import search_object
        results = search_object(
            name_str,
            typeclass="typeclasses.characters.Character",
        )
        if not results:
            self.msg(f"No character named '{name_str}' found.")
            return

        target = results[0]
        color = account.wisp_color_code

        self.msg(
            f'{color}You page |w{target.db.rp_name or target.key}|n'
            f'{color}, "{text}"|n'
        )
        target.msg(
            f'|x[A wisp whispers from elsewhere — "{text}"]|n'
        )


class CmdWispMutter(MuxCommand):
    """
    Mutter from the light — audible but hard to make out.

    Usage:
        mutter <text>

    The room hears fragments. The full text is lost in the light.
    Invisible: a shapeless murmur with no source.

    See also: say, whisper
    """

    key = "mutter"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account, room = _wisp_check_location(self)
        if not account:
            return

        if not self.args:
            self.msg("Mutter what?")
            return

        text = self.args.strip()
        color = account.wisp_color_code
        mood = account.wisp_mood
        name = account.wisp_display_name or f"a {mood} wisp"

        # Fragment — first third of words + last word
        words = text.split()
        if len(words) <= 2:
            fragment = words[0] if words else "..."
        else:
            cutoff = max(1, len(words) // 3)
            fragment = " ".join(words[:cutoff])
            if words[-1] != words[cutoff - 1]:
                fragment += f" ... {words[-1]}"

        # Caller sees full text
        self.msg(f'{color}Your light mutters, "{text}"|n')

        # Room — visible gets fragment, invisible gets even less
        visible_msg = (
            f"{color}Something from the {mood} light mutters — "
            f'"|x{fragment}...|n{color}"|n'
        )
        invisible_msg = "|xA murmur from nowhere — indistinct.|n"
        _wisp_msg_room(account, room, visible_msg, invisible_msg)

        # Scene log
        room.append_scene_log(name, f'[wisp mutter] "{text}"')


class CmdWispShout(MuxCommand):
    """
    Shout from the light — voice carries to adjacent rooms.

    Usage:
        shout <text>

    Everyone in this room and adjacent rooms hears it.
    Adjacent rooms hear a distant, sourceless voice.

    See also: say, mutter
    """

    key = "shout"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account, room = _wisp_check_location(self)
        if not account:
            return

        if not self.args:
            self.msg("Shout what?")
            return

        text = self.args.strip()
        color = account.wisp_color_code
        mood = account.wisp_mood
        name = account.wisp_display_name or f"a {mood} wisp"

        # Caller
        self.msg(f'{color}Your light calls out, "{text}"|n')

        # This room — split on visibility
        visible_msg = f'{color}The {mood} light calls out, "{text}"|n'
        invisible_msg = f'A voice from the light shouts, "{text}"'
        _wisp_msg_room(account, room, visible_msg, invisible_msg)

        # Adjacent rooms — distant, sourceless
        for exit_obj in room.exits:
            dest = exit_obj.destination
            if dest and dest != room:
                dest.msg_contents(
                    f'|xA voice carries from nearby — "{text}"|n'
                )

        # Scene log
        room.append_scene_log(name, f'[wisp shout] "{text}"')


class CmdWVoice(MuxCommand):
    """
    Set your wisp's speech verb.

    The voice verb replaces 'says' in all wisp speech output.

    Usage:
        wvoice                  — see current verb
        wvoice <verb>           — set (e.g. hums, sighs, breathes)
        wvoice/clear            — reset to default (says)

    Example:
        wvoice hums
        → The curious light hums, "Follow me."

    See also: say, mood
    """

    key = "wvoice"
    aliases = ["wsayverb"]  # backwards compat alias
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        color = account.wisp_color_code

        if "clear" in self.switches:
            account.db.wisp_say_verb = None
            self.msg("|xWisp voice reset to default (says).|n")
            return

        if not self.args:
            current = account.db.wisp_say_verb or "says (default)"
            self.msg(f"Current wisp voice: {color}{current}|n")
            return

        verb = self.args.strip().lower()
        account.db.wisp_say_verb = verb
        self.msg(
            f"Wisp voice set to: {color}{verb}|n\n"
            f"|xOutput: The {account.wisp_mood} light "
            f'{verb}s, "..."|n'
        )


# ===================================================================
# CmdWLog — personal scene logging for wisps
# ===================================================================

class CmdWLog(MuxCommand):
    """
    Toggle personal scene logging for your wisp.

    When on, everything you see in the current room is
    saved to your personal log. Use 'wlog save' to retrieve it.

    Usage:
        wlog on     — start logging
        wlog off    — stop logging
        wlog save   — display current log
        wlog clear  — clear log

    See also: scene log
    """

    key = "wlog"
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        args = self.args.strip().lower() if self.args else ""

        if args == "on":
            account.db.wisp_log_active = True
            account.db.wisp_log = account.db.wisp_log or []
            self.msg("|x[Wisp log started.]|n")

        elif args == "off":
            account.db.wisp_log_active = False
            self.msg("|x[Wisp log paused.]|n")

        elif args == "save":
            log = account.db.wisp_log or []
            if not log:
                self.msg("|xYour wisp log is empty.|n")
                return
            sep = f"|w{'─' * 44}|n"
            lines = [f"\n{sep}", "|wWisp Scene Log|n", sep]
            for entry in log:
                lines.append(f"  {entry}")
            lines.append(sep)
            self.msg("\n".join(lines))

        elif args == "clear":
            account.db.wisp_log = []
            self.msg("|x[Wisp log cleared.]|n")

        else:
            active = account.db.wisp_log_active or False
            count = len(account.db.wisp_log or [])
            status = "|gon|n" if active else "off"
            self.msg(
                f"Wisp log: {status} | {count} entries\n"
                f"  wlog on / off / save / clear"
            )


# ===================================================================
# CmdWispLook — wisp room viewing
# ===================================================================

class CmdWispLook(MuxCommand):
    """
    Look at your surroundings as a wisp.

    Usage:
        look
        l
        look <target>   — examine something in the room

    You see the room's description, any IC characters present,
    and available exits. When you're IC (puppeting a character),
    your character's look command takes over automatically.

    See also: go, north, south, east, west
    """

    key = "look"
    aliases = ["l"]
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        session = self.session

        # When IC, the character's look command takes priority.
        # This command steps aside to avoid conflict.
        if account.get_puppet(session):
            return

        account, room = _wisp_check_location(self)
        if not account:
            return

        # Look at a specific target in the room
        if self.args:
            target_name = self.args.strip()
            from evennia import search_object
            results = [obj for obj in search_object(target_name)
                       if obj.location == room]
            if results:
                obj = results[0]
                if hasattr(obj, 'return_appearance'):
                    self.msg(obj.return_appearance(account))
                elif hasattr(obj, 'get_wisp_appearance'):
                    self.msg(
                        obj.get_wisp_appearance(looker=account)
                    )
                else:
                    self.msg(f"You see: |w{obj.key}|n")
            else:
                self.msg(
                    f"|xNothing named '{target_name}' here.|n"
                )
            return

        # Look at the current room
        self.msg(account._build_wisp_room_view(room))


# ===================================================================
# CmdWispMove — wisp navigation through exits
# ===================================================================

class CmdWispMove(MuxCommand):
    """
    Move your wisp through an exit.

    Usage:
        north / n           south / s
        east / e            west / w
        up / u              down / d
        northeast / ne      northwest / nw
        southeast / se      southwest / sw
        out / in
        go <exit name>      — move through any named exit

    Wisps drift as light — moving through a door is simply
    sliding from one side to the other.

    When IC (puppeting a character), your character moves
    normally and this command steps aside.

    See also: look
    """

    key = "go"
    aliases = [
        "north", "n", "south", "s",
        "east", "e", "west", "w",
        "up", "u", "down", "d",
        "northeast", "ne", "northwest", "nw",
        "southeast", "se", "southwest", "sw",
        "out", "in",
    ]
    locks = "cmd:all()"
    help_category = "Wisp"

    def func(self):
        account = self.account
        session = self.session

        # When IC, character movement handles this.
        if account.get_puppet(session):
            return

        account, room = _wisp_check_location(self)
        if not account:
            return

        # Determine which exit to search for
        if self.cmdstring == "go":
            if not self.args:
                self.msg("Go where? Usage: go <exit name>")
                return
            exit_name = self.args.strip().lower()
        else:
            exit_name = self.cmdstring.lower()

        # Find the exit in the current room
        exit_obj = None
        for ex in room.exits:
            if ex.key.lower() == exit_name:
                exit_obj = ex
                break
            try:
                if exit_name in [a.lower() for a in ex.aliases.all()]:
                    exit_obj = ex
                    break
            except Exception:
                pass

        if not exit_obj:
            self.msg(f"|xNo exit '{exit_name}' from here.|n")
            return

        destination = exit_obj.destination
        if not destination:
            self.msg("|xThat exit leads nowhere.|n")
            return

        color = account.wisp_color_code
        mood = account.wisp_mood

        # Departure message to origin room (only to those who see the wisp)
        leave_msg = (
            f"|x{color}The {mood} light drifts {exit_obj.key}ward "
            f"and fades.|n"
        )
        _wisp_msg_room(account, room, leave_msg, None)

        # Move the wisp
        account.db.wisp_location = destination

        # Arrival message to destination room
        arrive_msg = f"|x{color}A {mood} light drifts in.|n"
        _wisp_msg_room(account, destination, arrive_msg, None)

        # Show the new room to the wisp
        self.msg(account._build_wisp_room_view(destination))