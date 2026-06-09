"""
commands/builder_commands.py

Builder-level commands for room construction and world building.
Restricted to Builder permission and above.

These are intentionally pragmatic — enough to populate rooms and test
systems. The design will likely change significantly as the world-
building approach matures.

Commands:
    dig         — create a new room, optionally linked
    rlink       — create an exit between rooms
    runlink     — remove an exit
    rname       — rename the current room
    rdesc       — edit the base room description
    rtime       — set time-of-day description layers
    rweather    — set weather description layers
    rseason     — set season description layers
    rcrowd      — set population/crowd descriptions
    rmood       — set mood/atmosphere descriptions and active flag
    rambient    — manage the ambient message pool
    rtoggle     — set atmosphere toggle descriptions
    rentry      — set the arrival/entry description
    rexamine    — set the examine closely (deep look) layer
    rflags      — manage room boolean flags
    rtype       — set the room type tag
"""

import evennia
from evennia.commands.default.muxcommand import MuxCommand


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

BUILDER_LOCK = "cmd:perm(Builder)"


def _room(caller):
    """
    Return caller's current location if they have Builder permission.
    Messages and returns None on failure.
    """
    if not (caller.check_permstring("Builder") or caller.is_superuser):
        caller.msg("|xBuilder permission required.|n")
        return None
    loc = caller.location
    if not loc:
        caller.msg("|xYou must be inside a room to use this command.|n")
        return None
    return loc


def _open_editor(caller, room, display_name, getter, setter):
    """
    Open the universal text editor targeting a room field.

    Args:
        caller: Builder character.
        room: The room being edited.
        display_name (str): Human-readable field label.
        getter (callable): () -> str  — fetch current value.
        setter (callable): (str) -> None  — save new value.
    """
    from world.text_editor import _enter_editor, _PENDING_SETTERS

    current = getter() or ""
    initial = [l for l in current.split("\n") if l] if current else []

    def _room_setter(c, lines):
        setter("\n".join(lines))
        c.msg(f"|x[{display_name} saved for '{room.key}'.]|n")

    # Store directly in module-level dict — avoids pickle entirely.
    _PENDING_SETTERS[str(caller.dbref)] = _room_setter

    _enter_editor(
        caller,
        target_display=f"{room.key} — {display_name}",
        setter_key="_room_field",
        initial_lines=initial,
        extra=None,
    )


def _inline_or_editor(caller, room, raw_args, display_name,
                       getter, setter):
    """
    If raw_args contains '= text', set inline.
    Otherwise open the text editor.
    """
    if raw_args and "=" in raw_args:
        text = raw_args.split("=", 1)[1].strip()
        if not text:
            caller.msg(f"|xNo text provided after '='.|n")
            return
        setter(text)
        caller.msg(f"|x[{display_name} set for '{room.key}'.]|n")
    else:
        _open_editor(caller, room, display_name, getter, setter)


# -------------------------------------------------------------------
# CmdDig — create a new room
# -------------------------------------------------------------------

class CmdDig(MuxCommand):
    """
    Create a new room and optionally link it.

    Usage:
        dig <room name>
        dig <room name> = <exit>[/<return exit>]

    With no exit specified, creates the room unlinked.
    With exits, creates the named exits in both directions.

    Examples:
        dig The Velvet Room
        dig The Velvet Room = north/south
        dig The Velvet Room = north

    Use 'rlink' to link rooms after creation.
    """

    key = "dig"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("Usage: dig <room name> [= <exit>[/<return>]]")
            return

        if "=" in self.args:
            name_part, _, exit_part = self.args.partition("=")
            room_name = name_part.strip()
            exits_raw = exit_part.strip()
        else:
            room_name = self.args.strip()
            exits_raw = ""

        if not room_name:
            caller.msg("Please provide a room name.")
            return

        # Create the room
        new_room = evennia.create_object(
            "typeclasses.rooms.Room",
            key=room_name,
        )
        if not new_room:
            caller.msg("|rFailed to create room.|n")
            return

        caller.msg(
            f"|wRoom created:|n {room_name} "
            f"|x(#{new_room.id})|n"
        )

        # Create exits if specified
        if exits_raw and caller.location:
            parts = exits_raw.split("/")
            forward = parts[0].strip() if parts else ""
            back = parts[1].strip() if len(parts) > 1 else ""

            if forward:
                exit_obj = evennia.create_object(
                    "evennia.objects.objects.DefaultExit",
                    key=forward,
                    location=caller.location,
                    destination=new_room,
                )
                caller.msg(
                    f"|x  Exit '{forward}' created from "
                    f"'{caller.location.key}' → '{room_name}'.|n"
                )

            if back:
                exit_obj = evennia.create_object(
                    "evennia.objects.objects.DefaultExit",
                    key=back,
                    location=new_room,
                    destination=caller.location,
                )
                caller.msg(
                    f"|x  Exit '{back}' created from "
                    f"'{room_name}' → '{caller.location.key}'.|n"
                )

        caller.msg(
            f"|xType '|wrlink|x' to add exits later, "
            f"or 'teleport #{new_room.id}' to go there.|n"
        )


# -------------------------------------------------------------------
# CmdRLink — create an exit
# -------------------------------------------------------------------

class CmdRLink(MuxCommand):
    """
    Create an exit from the current room to another.

    Usage:
        rlink <direction> = <room name or #dbref>
        rlink/twoway <dir>/<return dir> = <room name or #dbref>

    Examples:
        rlink north = The Velvet Room
        rlink north = #42
        rlink/twoway north/south = #42

    See also: runlink, dig
    """

    key = "rlink"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if not self.args or "=" not in self.args:
            caller.msg("Usage: rlink <direction> = <room name or #dbref>")
            return

        dir_part, _, dest_part = self.args.partition("=")
        dir_part = dir_part.strip()
        dest_part = dest_part.strip()

        if not dir_part or not dest_part:
            caller.msg("Usage: rlink <direction> = <room name or #dbref>")
            return

        twoway = "twoway" in self.switches

        if twoway:
            dirs = dir_part.split("/")
            forward_dir = dirs[0].strip()
            back_dir = dirs[1].strip() if len(dirs) > 1 else ""
            if not back_dir:
                caller.msg(
                    "For /twoway, provide both directions: "
                    "rlink/twoway north/south = <room>"
                )
                return
        else:
            forward_dir = dir_part
            back_dir = ""

        # Find destination
        dest = caller.search(dest_part, global_search=True)
        if not dest:
            return  # search() already messages

        # Check it's a room
        from typeclasses.rooms import Room
        if not isinstance(dest, Room):
            caller.msg(f"|x'{dest.key}' is not a room.|n")
            return

        # Create forward exit
        evennia.create_object(
            "evennia.objects.objects.DefaultExit",
            key=forward_dir,
            location=here,
            destination=dest,
        )
        caller.msg(
            f"|x  Exit '{forward_dir}' created: "
            f"'{here.key}' → '{dest.key}'.|n"
        )

        # Create return exit
        if back_dir:
            evennia.create_object(
                "evennia.objects.objects.DefaultExit",
                key=back_dir,
                location=dest,
                destination=here,
            )
            caller.msg(
                f"|x  Exit '{back_dir}' created: "
                f"'{dest.key}' → '{here.key}'.|n"
            )


# -------------------------------------------------------------------
# CmdRUnlink — remove an exit
# -------------------------------------------------------------------

class CmdRUnlink(MuxCommand):
    """
    Remove an exit from the current room.

    Usage:
        runlink <direction>

    Example:
        runlink north

    This only removes the exit you specify — it does not
    remove the matching return exit in the destination room.
    Use 'runlink' there separately if needed.

    See also: rlink
    """

    key = "runlink"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if not self.args:
            caller.msg("Usage: runlink <direction>")
            return

        direction = self.args.strip().lower()

        for exit_obj in here.exits:
            if exit_obj.key.lower() == direction:
                dest_name = exit_obj.destination.key
                exit_obj.delete()
                caller.msg(
                    f"|x  Exit '{direction}' to '{dest_name}' removed.|n"
                )
                return

        caller.msg(
            f"|xNo exit '{direction}' found in '{here.key}'.\n"
            f"Exits here: "
            f"{', '.join(e.key for e in here.exits) or 'none'}|n"
        )


# -------------------------------------------------------------------
# CmdRName — rename the current room
# -------------------------------------------------------------------

class CmdRName(MuxCommand):
    """
    Rename the current room.

    Usage:
        rname <new name>

    Example:
        rname The Amber Hall

    See also: rtype, rflags
    """

    key = "rname"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if not self.args:
            caller.msg(f"Current name: |w{here.key}|n")
            return

        old_name = here.key
        here.key = self.args.strip()
        caller.msg(
            f"|x  Room renamed: '{old_name}' → '{here.key}'.|n"
        )


# -------------------------------------------------------------------
# CmdRDesc — base room description (layer 1)
# -------------------------------------------------------------------

class CmdRDesc(MuxCommand):
    """
    Edit the base description of the current room (layer 1).

    This is the permanent, always-visible description. Time-of-day,
    weather, and other layers are added on top of this.

    Usage:
        rdesc               — open the text editor
        rdesc = <text>      — set a single-line description inline
        rdesc/show          — preview the current description
        rdesc/clear         — clear the description

    See also: rtime, rweather, rambient
    """

    key = "rdesc"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "show" in self.switches:
            desc = here.db.desc or ""
            sep = f"|w{'─' * 44}|n"
            caller.msg(
                f"\n{sep}\n"
                f"|wBase description — {here.key}|n\n"
                f"{sep}\n"
                f"{desc or '|x(empty)|n'}\n"
                f"{sep}"
            )
            return

        if "clear" in self.switches:
            here.db.desc = ""
            caller.msg(f"|x[Base description cleared for '{here.key}'.]|n")
            return

        _inline_or_editor(
            caller, here, self.args,
            display_name="Base description",
            getter=lambda: here.db.desc or "",
            setter=lambda t: setattr(here.db, "desc", t),
        )


# -------------------------------------------------------------------
# CmdRTime — time-of-day description layers (layer 2)
# -------------------------------------------------------------------

VALID_PERIODS = ["dawn", "morning", "afternoon", "dusk", "evening", "midnight"]


class CmdRTime(MuxCommand):
    """
    Set time-of-day description layers for the current room.

    Each period adds a line to the room desc when that time is active.

    Usage:
        rtime                       — show all periods
        rtime <period>              — open editor for that period
        rtime <period> = <text>     — set inline
        rtime/clear <period>        — clear a period
        rtime/enable                — enable time layer for this room
        rtime/disable               — disable time layer

    Valid periods:
        dawn  morning  afternoon  dusk  evening  midnight

    Example:
        rtime evening = The amber lamps have come on.
        rtime/enable
    """

    key = "rtime"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "enable" in self.switches:
            here.db.has_weather = here.db.has_weather  # no-op, just for clarity
            here.db.has_seasons = here.db.has_seasons
            # time is always potentially active; no flag — just write the descs
            caller.msg(
                f"|x[Time-of-day layers active for '{here.key}'.\n"
                f"  Write descriptions with 'rtime <period> = <text>'.]|n"
            )
            return

        if "disable" in self.switches:
            here.db.time_descs = {p: "" for p in VALID_PERIODS}
            caller.msg(
                f"|x[Time-of-day descriptions cleared for '{here.key}'.]|n"
            )
            return

        if "clear" in self.switches:
            period = self.args.strip().lower() if self.args else ""
            if period not in VALID_PERIODS:
                caller.msg(
                    f"|xUnknown period '{period}'.\n"
                    f"Valid: {', '.join(VALID_PERIODS)}|n"
                )
                return
            descs = here.db.time_descs or {}
            descs[period] = ""
            here.db.time_descs = descs
            caller.msg(f"|x[Time desc for '{period}' cleared.]|n")
            return

        if not self.args:
            # Show all periods
            descs = here.db.time_descs or {}
            sep = f"|w{'─' * 44}|n"
            lines = [f"\n{sep}", f"|wTime-of-day layers — {here.key}|n", sep]
            for p in VALID_PERIODS:
                text = descs.get(p, "") or "|x(empty)|n"
                lines.append(f"  |w{p:<12}|n {text}")
            lines.append(sep)
            caller.msg("\n".join(lines))
            return

        # Parse period from args
        args = self.args.strip()
        if "=" in args:
            period = args.split("=")[0].strip().lower()
            rest = args
        else:
            period = args.lower()
            rest = ""

        if period not in VALID_PERIODS:
            caller.msg(
                f"|xUnknown period '{period}'.\n"
                f"Valid: {', '.join(VALID_PERIODS)}|n"
            )
            return

        descs = here.db.time_descs or {}

        def getter():
            return (here.db.time_descs or {}).get(period, "")

        def setter(text):
            d = here.db.time_descs or {}
            d[period] = text
            here.db.time_descs = d

        _inline_or_editor(
            caller, here, rest,
            display_name=f"Time — {period}",
            getter=getter,
            setter=setter,
        )


# -------------------------------------------------------------------
# CmdRWeather — weather description layers (layer 3)
# -------------------------------------------------------------------

VALID_WEATHER = [
    "clear", "overcast", "rain", "heavy_rain",
    "fog", "storm", "snow",
]


class CmdRWeather(MuxCommand):
    """
    Set weather description layers for the current room.

    Only applies if the room has a weather window or is open-air.
    Enable with /enable before weather lines will appear.

    Usage:
        rweather                        — show all conditions
        rweather <condition>            — open editor
        rweather <condition> = <text>   — set inline
        rweather/clear <condition>      — clear a condition
        rweather/enable                 — mark room as weather-aware
        rweather/disable                — disable weather layer

    Valid conditions:
        clear  overcast  rain  heavy_rain  fog  storm  snow

    Example:
        rweather rain = Rain patters against the glass.
        rweather/enable
    """

    key = "rweather"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "enable" in self.switches:
            here.db.has_weather = True
            caller.msg(
                f"|x[Weather layer enabled for '{here.key}'.]|n"
            )
            return

        if "disable" in self.switches:
            here.db.has_weather = False
            caller.msg(
                f"|x[Weather layer disabled for '{here.key}'.]|n"
            )
            return

        if "clear" in self.switches:
            cond = self.args.strip().lower() if self.args else ""
            if cond not in VALID_WEATHER:
                caller.msg(
                    f"|xUnknown condition '{cond}'.\n"
                    f"Valid: {', '.join(VALID_WEATHER)}|n"
                )
                return
            descs = here.db.weather_descs or {}
            descs[cond] = ""
            here.db.weather_descs = descs
            caller.msg(f"|x[Weather desc for '{cond}' cleared.]|n")
            return

        if not self.args:
            descs = here.db.weather_descs or {}
            enabled = here.db.has_weather
            sep = f"|w{'─' * 44}|n"
            state = "|genabled|n" if enabled else "|xdisabled|n"
            lines = [
                f"\n{sep}",
                f"|wWeather layers — {here.key}|n  [{state}]",
                sep,
            ]
            for c in VALID_WEATHER:
                text = descs.get(c, "") or "|x(empty)|n"
                lines.append(f"  |w{c:<12}|n {text}")
            lines.append(sep)
            caller.msg("\n".join(lines))
            return

        args = self.args.strip()
        if "=" in args:
            cond = args.split("=")[0].strip().lower()
            rest = args
        else:
            cond = args.lower()
            rest = ""

        if cond not in VALID_WEATHER:
            caller.msg(
                f"|xUnknown condition '{cond}'.\n"
                f"Valid: {', '.join(VALID_WEATHER)}|n"
            )
            return

        def getter():
            return (here.db.weather_descs or {}).get(cond, "")

        def setter(text):
            d = here.db.weather_descs or {}
            d[cond] = text
            here.db.weather_descs = d

        _inline_or_editor(
            caller, here, rest,
            display_name=f"Weather — {cond}",
            getter=getter,
            setter=setter,
        )


# -------------------------------------------------------------------
# CmdRSeason — season description layers (layer 4)
# -------------------------------------------------------------------

VALID_SEASONS = ["spring", "summer", "autumn", "winter"]


class CmdRSeason(MuxCommand):
    """
    Set seasonal description layers for the current room.

    Usage:
        rseason                         — show all seasons
        rseason <season>                — open editor
        rseason <season> = <text>       — set inline
        rseason/clear <season>          — clear a season
        rseason/enable                  — enable season layer
        rseason/disable                 — disable season layer

    Valid seasons:  spring  summer  autumn  winter

    Example:
        rseason winter = Frost traces the inside of the glass.
    """

    key = "rseason"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "enable" in self.switches:
            here.db.has_seasons = True
            caller.msg(f"|x[Season layer enabled for '{here.key}'.]|n")
            return

        if "disable" in self.switches:
            here.db.has_seasons = False
            caller.msg(f"|x[Season layer disabled for '{here.key}'.]|n")
            return

        if "clear" in self.switches:
            s = self.args.strip().lower() if self.args else ""
            if s not in VALID_SEASONS:
                caller.msg(
                    f"|xUnknown season '{s}'.\n"
                    f"Valid: {', '.join(VALID_SEASONS)}|n"
                )
                return
            descs = here.db.season_descs or {}
            descs[s] = ""
            here.db.season_descs = descs
            caller.msg(f"|x[Season desc for '{s}' cleared.]|n")
            return

        if not self.args:
            descs = here.db.season_descs or {}
            enabled = here.db.has_seasons
            sep = f"|w{'─' * 44}|n"
            state = "|genabled|n" if enabled else "|xdisabled|n"
            lines = [
                f"\n{sep}",
                f"|wSeason layers — {here.key}|n  [{state}]",
                sep,
            ]
            for s in VALID_SEASONS:
                text = descs.get(s, "") or "|x(empty)|n"
                lines.append(f"  |w{s:<10}|n {text}")
            lines.append(sep)
            caller.msg("\n".join(lines))
            return

        args = self.args.strip()
        if "=" in args:
            season = args.split("=")[0].strip().lower()
            rest = args
        else:
            season = args.lower()
            rest = ""

        if season not in VALID_SEASONS:
            caller.msg(
                f"|xUnknown season '{season}'.\n"
                f"Valid: {', '.join(VALID_SEASONS)}|n"
            )
            return

        def getter():
            return (here.db.season_descs or {}).get(season, "")

        def setter(text):
            d = here.db.season_descs or {}
            d[season] = text
            here.db.season_descs = d

        _inline_or_editor(
            caller, here, rest,
            display_name=f"Season — {season}",
            getter=getter,
            setter=setter,
        )


# -------------------------------------------------------------------
# CmdRCrowd — population/crowd description layers (layer 7)
# -------------------------------------------------------------------

VALID_CROWD = ["empty", "quiet", "few", "busy", "crowded"]


class CmdRCrowd(MuxCommand):
    """
    Set population/crowd description layers for the current room.

    These lines appear based on how many IC characters are present.
    The active level is determined automatically.

    Usage:
        rcrowd                          — show all levels
        rcrowd <level>                  — open editor
        rcrowd <level> = <text>         — set inline
        rcrowd/clear <level>            — clear a level

    Levels (auto-selected by population):
        empty    — no one here
        quiet    — 1–2 people
        few      — 3–4 people
        busy     — 5–8 people
        crowded  — 9+ people

    Example:
        rcrowd empty = The room is still, dust settling.
    """

    key = "rcrowd"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "clear" in self.switches:
            level = self.args.strip().lower() if self.args else ""
            if level not in VALID_CROWD:
                caller.msg(
                    f"|xUnknown level '{level}'.\n"
                    f"Valid: {', '.join(VALID_CROWD)}|n"
                )
                return
            descs = here.db.crowd_descs or {}
            descs[level] = ""
            here.db.crowd_descs = descs
            caller.msg(f"|x[Crowd desc for '{level}' cleared.]|n")
            return

        if not self.args:
            descs = here.db.crowd_descs or {}
            current = here.get_crowd_level() if hasattr(here, 'get_crowd_level') else "?"
            sep = f"|w{'─' * 44}|n"
            lines = [
                f"\n{sep}",
                f"|wCrowd layers — {here.key}|n  "
                f"|x(current: {current})|n",
                sep,
            ]
            for lv in VALID_CROWD:
                text = descs.get(lv, "") or "|x(empty)|n"
                marker = " |g←|n" if lv == current else ""
                lines.append(f"  |w{lv:<10}|n {text}{marker}")
            lines.append(sep)
            caller.msg("\n".join(lines))
            return

        args = self.args.strip()
        if "=" in args:
            level = args.split("=")[0].strip().lower()
            rest = args
        else:
            level = args.lower()
            rest = ""

        if level not in VALID_CROWD:
            caller.msg(
                f"|xUnknown level '{level}'.\n"
                f"Valid: {', '.join(VALID_CROWD)}|n"
            )
            return

        def getter():
            return (here.db.crowd_descs or {}).get(level, "")

        def setter(text):
            d = here.db.crowd_descs or {}
            d[level] = text
            here.db.crowd_descs = d

        _inline_or_editor(
            caller, here, rest,
            display_name=f"Crowd — {level}",
            getter=getter,
            setter=setter,
        )


# -------------------------------------------------------------------
# CmdRMood — mood/atmosphere flag and descriptions (layer 8)
# -------------------------------------------------------------------

class CmdRMood(MuxCommand):
    """
    Set the mood/atmosphere flag and descriptions for this room.

    A mood flag adds an atmospheric description line (layer 8) and
    can also affect which ambient lines fire. The flag is manually
    set and cleared — it doesn't change automatically.

    Usage:
        rmood                       — show current mood and all descs
        rmood/set <mood>            — set the active mood flag
        rmood/clear                 — remove the active mood flag
        rmood <mood>                — open editor for that mood desc
        rmood <mood> = <text>       — set inline
        rmood/cleardesc <mood>      — clear a mood description

    Example:
        rmood intimate = The room has a close, quiet quality.
        rmood/set intimate
    """

    key = "rmood"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "set" in self.switches:
            mood = self.args.strip().lower() if self.args else ""
            if not mood:
                caller.msg("Usage: rmood/set <mood>")
                return
            here.db.mood_flag = mood
            caller.msg(f"|x[Mood flag set to '{mood}' for '{here.key}'.]|n")
            return

        if "clear" in self.switches:
            here.db.mood_flag = None
            caller.msg(f"|x[Mood flag cleared for '{here.key}'.]|n")
            return

        if "cleardesc" in self.switches:
            mood = self.args.strip().lower() if self.args else ""
            if not mood:
                caller.msg("Usage: rmood/cleardesc <mood>")
                return
            descs = here.db.mood_descs or {}
            if mood in descs:
                del descs[mood]
                here.db.mood_descs = descs
            caller.msg(f"|x[Mood desc for '{mood}' cleared.]|n")
            return

        if not self.args:
            active = here.db.mood_flag or "|x(none)|n"
            descs = here.db.mood_descs or {}
            sep = f"|w{'─' * 44}|n"
            lines = [
                f"\n{sep}",
                f"|wMood flag — {here.key}|n  active: |w{active}|n",
                sep,
            ]
            if descs:
                for mood, text in descs.items():
                    marker = " |g←|n" if mood == here.db.mood_flag else ""
                    lines.append(f"  |w{mood}|n{marker}\n    {text or '|x(empty)|n'}")
            else:
                lines.append("  |x(no mood descs written)|n")
            lines.append(sep)
            caller.msg("\n".join(lines))
            return

        args = self.args.strip()
        if "=" in args:
            mood = args.split("=")[0].strip().lower()
            rest = args
        else:
            mood = args.lower()
            rest = ""

        if not mood:
            caller.msg("Usage: rmood <mood> [= <text>]")
            return

        def getter():
            return (here.db.mood_descs or {}).get(mood, "")

        def setter(text):
            d = here.db.mood_descs or {}
            d[mood] = text
            here.db.mood_descs = d

        _inline_or_editor(
            caller, here, rest,
            display_name=f"Mood desc — {mood}",
            getter=getter,
            setter=setter,
        )


# -------------------------------------------------------------------
# CmdRAmbient — ambient message pool manager (layers 11–13)
# -------------------------------------------------------------------

class CmdRAmbient(MuxCommand):
    """
    Manage the ambient message pool for the current room.

    Ambient lines fire periodically via the AmbientScript. They can
    be unconditional (base pool) or tied to toggle states, moods,
    or crowd levels.

    Usage:
        rambient                            — list base pool
        rambient add <text>                 — add to base pool
        rambient remove <#>                 — remove from base pool
        rambient/clear                      — clear base pool

        rambient/toggle <element>_<state> add <text>
        rambient/toggle <element>_<state> remove <#>
        rambient/toggle <element>_<state>   — list toggle pool

        rambient/mood <mood> add <text>
        rambient/mood <mood> remove <#>
        rambient/mood <mood>                — list mood pool

        rambient/crowd <level> add <text>
        rambient/crowd <level> remove <#>
        rambient/crowd <level>              — list crowd pool

        rambient/start                      — start ambient script
        rambient/stop                       — stop ambient script

    Example:
        rambient add The candle gutters in an unfelt draft.
        rambient/toggle lights_dim add The light shifts in the corner.
        rambient/start
    """

    key = "rambient"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "start" in self.switches:
            here.ensure_ambient_script()
            caller.msg(
                f"|x[Ambient script started for '{here.key}'.]|n"
            )
            return

        if "stop" in self.switches:
            scripts = here.scripts.get("ambient_script")
            if scripts:
                for s in scripts:
                    s.delete()
                caller.msg(
                    f"|x[Ambient script stopped for '{here.key}'.]|n"
                )
            else:
                caller.msg(
                    f"|x[No ambient script running on '{here.key}'.]|n"
                )
            return

        if "clear" in self.switches:
            here.db.ambient_msgs = []
            caller.msg(
                f"|x[Base ambient pool cleared for '{here.key}'.]|n"
            )
            return

        # --- Toggle pool ---
        if "toggle" in self.switches:
            self._handle_pool(
                caller, here, self.args,
                pool_attr="ambient_msgs_by_toggle",
                label="toggle",
            )
            return

        # --- Mood pool ---
        if "mood" in self.switches:
            self._handle_pool(
                caller, here, self.args,
                pool_attr="ambient_msgs_by_mood",
                label="mood",
            )
            return

        # --- Crowd pool ---
        if "crowd" in self.switches:
            self._handle_pool(
                caller, here, self.args,
                pool_attr="ambient_msgs_by_population",
                label="crowd",
            )
            return

        # --- Base pool ---
        pool = here.db.ambient_msgs or []
        args = self.args.strip() if self.args else ""

        if args.lower().startswith("add "):
            text = args[4:].strip()
            if not text:
                caller.msg("Add what?")
                return
            pool.append(text)
            here.db.ambient_msgs = pool
            caller.msg(f"|x[Ambient line #{len(pool)} added.]|n")
            return

        if args.lower().startswith("remove "):
            try:
                idx = int(args[7:].strip()) - 1
            except ValueError:
                caller.msg("Usage: rambient remove <number>")
                return
            if idx < 0 or idx >= len(pool):
                caller.msg(
                    f"|xNo line #{idx + 1}. "
                    f"Pool has {len(pool)} lines.|n"
                )
                return
            removed = pool.pop(idx)
            here.db.ambient_msgs = pool
            caller.msg(f"|x[Removed: {removed}]|n")
            return

        # Show base pool
        sep = f"|w{'─' * 44}|n"
        lines = [
            f"\n{sep}",
            f"|wBase ambient pool — {here.key}|n  "
            f"|x({len(pool)} lines)|n",
            sep,
        ]
        if pool:
            for i, line in enumerate(pool, 1):
                lines.append(f"  {i:>2}. {line}")
        else:
            lines.append("  |x(empty — use 'rambient add <text>')|n")
        lines.append(sep)
        caller.msg("\n".join(lines))

    def _handle_pool(self, caller, here, args, pool_attr, label):
        """Handle toggle/mood/crowd conditional pools."""
        args = (args or "").strip()

        if not args:
            # Show all keys in this pool
            pool_dict = getattr(here.db, pool_attr, {}) or {}
            sep = f"|w{'─' * 44}|n"
            lines = [f"\n{sep}", f"|w{label.capitalize()} pools — {here.key}|n", sep]
            if pool_dict:
                for key, msgs in pool_dict.items():
                    lines.append(f"  |w{key}|n ({len(msgs)} lines)")
            else:
                lines.append(f"  |x(empty)|n")
            lines.append(sep)
            caller.msg("\n".join(lines))
            return

        # Parse: "<key> add/remove <text/num>"
        parts = args.split(None, 2)
        key = parts[0] if parts else ""

        if len(parts) == 1:
            # Show pool for this key
            pool_dict = getattr(here.db, pool_attr, {}) or {}
            pool = pool_dict.get(key, [])
            sep = f"|w{'─' * 44}|n"
            lines = [f"\n{sep}", f"|w{label}: {key}|n  ({len(pool)} lines)", sep]
            for i, line in enumerate(pool, 1):
                lines.append(f"  {i:>2}. {line}")
            if not pool:
                lines.append("  |x(empty)|n")
            lines.append(sep)
            caller.msg("\n".join(lines))
            return

        action = parts[1].lower() if len(parts) > 1 else ""
        rest = parts[2] if len(parts) > 2 else ""

        pool_dict = getattr(here.db, pool_attr, {}) or {}
        pool = list(pool_dict.get(key, []))

        if action == "add":
            if not rest:
                caller.msg(f"Add what? Usage: rambient/{label} {key} add <text>")
                return
            pool.append(rest)
            pool_dict[key] = pool
            setattr(here.db, pool_attr, pool_dict)
            caller.msg(f"|x[Added to {label} '{key}': #{len(pool)}]|n")

        elif action == "remove":
            try:
                idx = int(rest) - 1
            except ValueError:
                caller.msg(f"Usage: rambient/{label} {key} remove <number>")
                return
            if idx < 0 or idx >= len(pool):
                caller.msg(
                    f"|xNo line #{idx + 1}. "
                    f"Pool '{key}' has {len(pool)} lines.|n"
                )
                return
            removed = pool.pop(idx)
            pool_dict[key] = pool
            setattr(here.db, pool_attr, pool_dict)
            caller.msg(f"|x[Removed from {label} '{key}': {removed}]|n")

        else:
            caller.msg(
                f"|xUnknown action '{action}'. "
                f"Use: add / remove|n"
            )


# -------------------------------------------------------------------
# CmdRToggle — atmosphere toggle descriptions (layer 5)
# -------------------------------------------------------------------

TOGGLE_STATES = {
    "lights":    ["bright", "dim", "dark"],
    "fireplace": ["unlit", "lit"],
    "curtains":  ["open", "drawn"],
    "music":     ["silent", "soft", "loud"],
}


class CmdRToggle(MuxCommand):
    """
    Set descriptions for atmosphere toggle states.

    Toggles are room-wide atmosphere elements (lights, fireplace,
    curtains, music) that players can change during a scene.
    Each state can have a description that appears in the room.

    Usage:
        rtoggle                             — show all toggles
        rtoggle <element> <state> = <text>  — set a state description
        rtoggle <element> <state>           — open editor
        rtoggle/clear <element> <state>     — clear a state desc
        rtoggle/set <element> <state>       — manually set current state

    Default elements and their states:
        lights:    bright / dim / dark
        fireplace: unlit / lit
        curtains:  open / drawn
        music:     silent / soft / loud

    Example:
        rtoggle lights dim = The room is lit only by candlelight.
        rtoggle fireplace lit = A fire burns in the hearth.
        rtoggle/set lights dim
    """

    key = "rtoggle"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "set" in self.switches:
            # Manually set the current toggle state
            parts = (self.args or "").strip().split(None, 1)
            if len(parts) < 2:
                caller.msg(
                    "Usage: rtoggle/set <element> <state>"
                )
                return
            element, state = parts[0].lower(), parts[1].lower()
            valid = TOGGLE_STATES.get(element, [])
            if not valid:
                caller.msg(
                    f"|xUnknown element '{element}'.\n"
                    f"Valid: {', '.join(TOGGLE_STATES)}|n"
                )
                return
            if state not in valid:
                caller.msg(
                    f"|xUnknown state '{state}' for '{element}'.\n"
                    f"Valid: {', '.join(valid)}|n"
                )
                return
            toggles = here.db.toggles or {}
            toggles[element] = state
            here.db.toggles = toggles
            caller.msg(
                f"|x[{element} set to '{state}' in '{here.key}'.]|n"
            )
            return

        if "clear" in self.switches:
            parts = (self.args or "").strip().split(None, 1)
            if len(parts) < 2:
                caller.msg(
                    "Usage: rtoggle/clear <element> <state>"
                )
                return
            element, state = parts[0].lower(), parts[1].lower()
            descs = here.db.toggle_descs or {}
            el_descs = descs.get(element, {})
            if state in el_descs:
                el_descs[state] = ""
                descs[element] = el_descs
                here.db.toggle_descs = descs
            caller.msg(
                f"|x[Toggle desc for '{element}/{state}' cleared.]|n"
            )
            return

        if not self.args:
            # Show all toggle states
            toggles = here.db.toggles or {}
            descs = here.db.toggle_descs or {}
            sep = f"|w{'─' * 44}|n"
            lines = [f"\n{sep}", f"|wToggle states — {here.key}|n", sep]
            for element, states in TOGGLE_STATES.items():
                current = toggles.get(element, states[0])
                lines.append(f"\n  |w{element}|n  (currently: |w{current}|n)")
                el_descs = descs.get(element, {})
                for state in states:
                    text = el_descs.get(state, "") or "|x(empty)|n"
                    marker = " |g←|n" if state == current else ""
                    lines.append(f"    {state:<10} {text}{marker}")
            lines.append(f"\n{sep}")
            caller.msg("\n".join(lines))
            return

        # Parse element and state from args
        parts = self.args.strip().split(None, 1)
        if not parts:
            caller.msg("Usage: rtoggle <element> <state> [= <text>]")
            return

        element = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        valid_states = TOGGLE_STATES.get(element, [])
        if not valid_states:
            caller.msg(
                f"|xUnknown element '{element}'.\n"
                f"Valid: {', '.join(TOGGLE_STATES)}|n"
            )
            return

        if not rest:
            # Show all states for this element
            descs = here.db.toggle_descs or {}
            current = (here.db.toggles or {}).get(element, valid_states[0])
            sep = f"|w{'─' * 44}|n"
            lines = [
                f"\n{sep}",
                f"|wToggle: {element} — {here.key}|n  (current: |w{current}|n)",
                sep,
            ]
            el_descs = descs.get(element, {})
            for state in valid_states:
                text = el_descs.get(state, "") or "|x(empty)|n"
                marker = " |g←|n" if state == current else ""
                lines.append(f"  |w{state:<10}|n {text}{marker}")
            lines.append(sep)
            caller.msg("\n".join(lines))
            return

        # Parse state from rest
        if "=" in rest:
            state = rest.split("=")[0].strip().lower()
            inline_rest = rest
        else:
            state = rest.split()[0].lower()
            inline_rest = ""

        if state not in valid_states:
            caller.msg(
                f"|xUnknown state '{state}' for '{element}'.\n"
                f"Valid: {', '.join(valid_states)}|n"
            )
            return

        def getter():
            return (here.db.toggle_descs or {}).get(
                element, {}
            ).get(state, "")

        def setter(text):
            d = here.db.toggle_descs or {}
            if element not in d:
                d[element] = {}
            d[element][state] = text
            here.db.toggle_descs = d

        _inline_or_editor(
            caller, here, inline_rest,
            display_name=f"Toggle — {element}/{state}",
            getter=getter,
            setter=setter,
        )


# -------------------------------------------------------------------
# CmdREntry — arrival/entry description (layer 17)
# -------------------------------------------------------------------

class CmdREntry(MuxCommand):
    """
    Set the arrival description for the current room.

    This text is shown to a character when they enter the room —
    in addition to (or instead of) the normal room look. Good for
    first impressions, smells, sounds that hit you on arrival.

    Usage:
        rentry              — open editor
        rentry = <text>     — set inline
        rentry/show         — preview current
        rentry/clear        — clear

    Example:
        rentry = The smell of cedar smoke hits you at the threshold.
    """

    key = "rentry"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "show" in self.switches:
            text = here.db.entry_desc or ""
            sep = f"|w{'─' * 44}|n"
            caller.msg(
                f"\n{sep}\n"
                f"|wEntry description — {here.key}|n\n"
                f"{sep}\n"
                f"{text or '|x(empty)|n'}\n"
                f"{sep}"
            )
            return

        if "clear" in self.switches:
            here.db.entry_desc = None
            caller.msg(
                f"|x[Entry description cleared for '{here.key}'.]|n"
            )
            return

        _inline_or_editor(
            caller, here, self.args,
            display_name="Entry description",
            getter=lambda: here.db.entry_desc or "",
            setter=lambda t: setattr(here.db, "entry_desc", t),
        )


# -------------------------------------------------------------------
# CmdRExamine — examine closely layer (layer 16)
# -------------------------------------------------------------------

class CmdRExamine(MuxCommand):
    """
    Set the examine-closely description for the current room.

    This text appears when a player uses 'look/deep' on the room —
    hidden details, architectural quirks, history, secrets.

    Usage:
        rexamine             — open editor
        rexamine = <text>    — set inline
        rexamine/show        — preview current
        rexamine/clear       — clear

    Example:
        rexamine = The plaster near the window has been patched
        many times — each patch a slightly different shade.
    """

    key = "rexamine"
    aliases = ["rexam"]
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if "show" in self.switches:
            text = here.db.examine_desc or ""
            sep = f"|w{'─' * 44}|n"
            caller.msg(
                f"\n{sep}\n"
                f"|wExamine layer — {here.key}|n\n"
                f"{sep}\n"
                f"{text or '|x(empty)|n'}\n"
                f"{sep}"
            )
            return

        if "clear" in self.switches:
            here.db.examine_desc = None
            caller.msg(
                f"|x[Examine layer cleared for '{here.key}'.]|n"
            )
            return

        _inline_or_editor(
            caller, here, self.args,
            display_name="Examine layer",
            getter=lambda: here.db.examine_desc or "",
            setter=lambda t: setattr(here.db, "examine_desc", t),
        )


# -------------------------------------------------------------------
# CmdRFlags — room boolean flags
# -------------------------------------------------------------------

ROOM_FLAGS = {
    "wisp":       ("wisp_always_visible", "Wisps always visible"),
    "hub":        ("is_hub",              "Hub room"),
    "forming":    ("is_forming",          "Forming/tutorial room"),
    "weather":    ("has_weather",         "Weather layer active"),
    "seasons":    ("has_seasons",         "Season layer active"),
    "private":    ("is_private",          "Private room"),
    "hide":       ("hide_from_who",       "Hidden from who list"),
    "noteleport": ("allow_teleport_in",   "Teleport blocked"),
    # Note: noteleport inverts the flag — allow_teleport_in=False means blocked
}


class CmdRFlags(MuxCommand):
    """
    View and toggle boolean room flags.

    Usage:
        rflags              — show all flags and their state
        rflags <flag>       — toggle a flag on/off

    Available flags:
        wisp        — wisps always visible in this room
        hub         — treat as hub room
        forming     — treat as Forming/tutorial room
        weather     — enable weather layer
        seasons     — enable season layer
        private     — mark as private room
        hide        — hide from who list
        noteleport  — block teleport into this room

    Example:
        rflags wisp
        rflags hide
    """

    key = "rflags"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if not self.args:
            sep = f"|w{'─' * 44}|n"
            lines = [f"\n{sep}", f"|wRoom flags — {here.key}|n", sep]
            for flag_key, (attr, label) in ROOM_FLAGS.items():
                val = getattr(here.db, attr, False)
                # noteleport inverts
                if flag_key == "noteleport":
                    val = not val
                state = "|gon|n" if val else "|xoff|n"
                lines.append(f"  |w{flag_key:<14}|n {state}  |x{label}|n")
            lines.append(sep)
            caller.msg("\n".join(lines))
            return

        flag = self.args.strip().lower()
        if flag not in ROOM_FLAGS:
            caller.msg(
                f"|xUnknown flag '{flag}'.\n"
                f"Valid: {', '.join(ROOM_FLAGS)}|n"
            )
            return

        attr, label = ROOM_FLAGS[flag]

        if flag == "noteleport":
            # Inverted — toggling "noteleport" toggles allow_teleport_in
            current = getattr(here.db, attr, True)
            setattr(here.db, attr, not current)
            new_val = not current
            state = "blocked" if not new_val else "allowed"
            caller.msg(
                f"|x[Teleport into '{here.key}': {state}.]|n"
            )
        else:
            current = getattr(here.db, attr, False)
            setattr(here.db, attr, not current)
            state = "on" if not current else "off"
            caller.msg(
                f"|x[{label} → {state} for '{here.key}'.]|n"
            )


# -------------------------------------------------------------------
# CmdRType — room type tag
# -------------------------------------------------------------------

VALID_TYPES = [
    "general", "hub", "residential", "public",
    "wilderness", "transit", "private", "forming",
]


class CmdRType(MuxCommand):
    """
    Set the room type tag for the current room.

    The room type is used for categorization and may affect future
    systems (housing, navigation, etc.).

    Usage:
        rtype               — show current type
        rtype <type>        — set type

    Valid types:
        general  hub  residential  public
        wilderness  transit  private  forming

    Example:
        rtype residential
    """

    key = "rtype"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        here = _room(caller)
        if not here:
            return

        if not self.args:
            current = here.db.room_type or "general"
            caller.msg(
                f"Room type for '{here.key}': |w{current}|n\n"
                f"Valid: {', '.join(VALID_TYPES)}"
            )
            return

        new_type = self.args.strip().lower()
        if new_type not in VALID_TYPES:
            caller.msg(
                f"|xUnknown type '{new_type}'.\n"
                f"Valid: {', '.join(VALID_TYPES)}|n"
            )
            return

        here.db.room_type = new_type
        caller.msg(
            f"|x[Room type set to '{new_type}' for '{here.key}'.]|n"
        )


class CmdMaze(MuxCommand):
    """
    Build and configure a combination-lock ("Lost Woods") maze room.

    Usage:
        maze make [<name>]                    — turn a new room into a MazeRoom
                                                (or dig one with the given name)
        maze solution <name> = <dirs> > <dest> — add/replace a solution sequence
                                                (dirs space- or comma-separated;
                                                 dest = room dbref/#id, optional)
        maze reveal <name> = <prose>          — set the reveal line for a solution
        maze gate <name> = <type> [<min>]     — gate an exit on body state; type =
                                                conditioning|regression|devotion|
                                                standing|quota (quota needs no min;
                                                "none" clears the gate)
        maze decoy add = <line>               — add a decoy line (use {dir} token)
        maze decoy clear                      — wipe decoys back to defaults
        maze debt <0..1> [<species>]          — breeding-debt halls: chance a wrong
                                                turn breeds you (0 = off)
        maze mode classic|forgiving           — wrong move resets the combo, or not
        maze show                             — show this room's maze config

    The maze must be applied to a room with NO normal exits — directional moves
    ARE the puzzle. Stand in the room you want to configure.

    Example:
        maze make The Lost Hallway
        maze solution deeper = n n e w > #84
        maze reveal deeper = The corridor finally stops doubling back on itself.
        maze solution back = s s > #2
        maze mode classic
    """

    key = "maze"
    locks = BUILDER_LOCK
    help_category = "Builder"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg(self.get_help(caller, self.cmdset))
            return

        parts = args.split(None, 1)
        sub = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "make":
            self._make(caller, rest)
            return

        here = caller.location
        if not here or getattr(here.db, "room_type", None) != "maze":
            caller.msg("|rThis isn't a maze room. Use 'maze make' here first.|n")
            return

        if sub == "solution":
            self._solution(caller, here, rest)
        elif sub == "reveal":
            self._reveal(caller, here, rest)
        elif sub == "gate":
            self._gate(caller, here, rest)
        elif sub == "decoy":
            self._decoy(caller, here, rest)
        elif sub == "debt":
            self._debt(caller, here, rest)
        elif sub == "mode":
            self._mode(caller, here, rest)
        elif sub == "show":
            self._show(caller, here)
        else:
            caller.msg("Unknown subcommand. See 'help maze'.")

    def _make(self, caller, name):
        if name:
            room = evennia.create_object("typeclasses.maze_room.MazeRoom", key=name)
            caller.msg(f"|wMaze room created:|n {name} |x(#{room.id})|n  "
                       f"|x(use rlink to wire an entry exit into it)|n")
        else:
            here = caller.location
            if not here:
                caller.msg("|rYou are nowhere.|n")
                return
            here.swap_typeclass("typeclasses.maze_room.MazeRoom",
                                clean_attributes=False, run_start_hooks="all")
            caller.msg(f"|w'{here.key}' is now a maze room.|n |x(remove its normal "
                       f"exits — directions are the puzzle now.)|n")

    def _solution(self, caller, here, rest):
        if "=" not in rest:
            caller.msg("Usage: maze solution <name> = <dirs> [> <dest>]")
            return
        name, _, body = rest.partition("=")
        name = name.strip()
        dest = None
        if ">" in body:
            body, _, dest_part = body.partition(">")
            dest = caller.search(dest_part.strip(), global_search=True)
            if not dest:
                return
        dirs = [d for d in body.replace(",", " ").split() if d]
        if not name or not dirs:
            caller.msg("Need a solution name and at least one direction.")
            return
        ok = here.add_solution(name, dirs, dest=dest)
        if not ok:
            caller.msg("|rNo valid directions in that sequence.|n")
            return
        hint = here.solution_hint(name)
        dest_txt = f" → {dest.key}" if dest else " (no destination — prose-only)"
        caller.msg(f"|wSolution '{name}' set:|n {hint}{dest_txt}")

    def _reveal(self, caller, here, rest):
        if "=" not in rest:
            caller.msg("Usage: maze reveal <name> = <prose>")
            return
        name, _, prose = rest.partition("=")
        name = name.strip()
        sols = dict(here.db.maze_solutions or {})
        if name not in sols:
            caller.msg(f"|rNo solution '{name}'. Add it first with 'maze solution'.|n")
            return
        sols[name] = dict(sols[name]); sols[name]["reveal"] = prose.strip()
        here.db.maze_solutions = sols
        caller.msg(f"|wReveal line set for '{name}'.|n")

    def _gate(self, caller, here, rest):
        if "=" not in rest:
            caller.msg("Usage: maze gate <name> = <type> [<min>]   (type: conditioning|"
                       "regression|devotion|standing|quota|none)")
            return
        name, _, body = rest.partition("=")
        name = name.strip()
        toks = body.split()
        if not toks:
            caller.msg("Need a gate type.")
            return
        gtype = toks[0].lower()
        valid = ("conditioning", "regression", "devotion", "standing", "quota", "none")
        if gtype not in valid:
            caller.msg(f"Gate type must be one of: {', '.join(valid)}.")
            return
        if gtype == "none":
            gate = None
        elif gtype == "quota":
            gate = {"type": "quota"}
        else:
            try:
                gate = {"type": gtype, "min": float(toks[1])}
            except (IndexError, ValueError):
                caller.msg(f"'{gtype}' needs a minimum number, e.g. 'maze gate {name} = {gtype} 80'.")
                return
        if not here.set_gate(name, gate):
            caller.msg(f"|rNo solution '{name}'. Add it first with 'maze solution'.|n")
            return
        if gate is None:
            caller.msg(f"|wGate cleared on '{name}'.|n")
        elif gtype == "quota":
            caller.msg(f"|w'{name}' now opens only once her breeding quota is met.|n")
        else:
            caller.msg(f"|w'{name}' now opens only at {gtype} ≥ {gate['min']:.0f}.|n")

    def _debt(self, caller, here, rest):
        toks = rest.split()
        if not toks:
            caller.msg("Usage: maze debt <0..1> [<species>]   (0 = off)")
            return
        try:
            chance = max(0.0, min(1.0, float(toks[0])))
        except ValueError:
            caller.msg("Chance must be a number 0..1.")
            return
        here.db.maze_breeding_debt = chance
        if len(toks) > 1:
            here.db.maze_debt_species = toks[1].lower()
        if chance <= 0:
            caller.msg("|wBreeding-debt halls disabled.|n")
        else:
            caller.msg(f"|wBreeding-debt halls: {chance:.0%} chance per wrong turn, "
                       f"species '{here.db.maze_debt_species}'.|n")

    def _decoy(self, caller, here, rest):
        action = rest.split(None, 1)
        verb = action[0].lower() if action else ""
        if verb == "clear":
            from typeclasses.maze_room import _DEFAULT_DECOYS
            here.db.maze_decoys = list(_DEFAULT_DECOYS)
            caller.msg("|wDecoys reset to defaults.|n")
        elif verb == "add" and "=" in rest:
            line = rest.partition("=")[2].strip()
            if line:
                pool = list(here.db.maze_decoys or [])
                pool.append(line)
                here.db.maze_decoys = pool
                caller.msg(f"|wDecoy added.|n |x({len(pool)} total)|n")
        else:
            caller.msg("Usage: maze decoy add = <line>  |  maze decoy clear")

    def _mode(self, caller, here, rest):
        m = rest.strip().lower()
        if m not in ("classic", "forgiving"):
            caller.msg("Usage: maze mode classic|forgiving")
            return
        here.db.maze_reset_on_wrong = (m == "classic")
        caller.msg(f"|wMaze mode: {m}.|n |x(" +
                   ("wrong move resets the combo" if m == "classic"
                    else "sequence slides; trailing match wins") + ")|n")

    def _show(self, caller, here):
        lines = [f"|wMaze config for '{here.key}'|n  "
                 f"|x(mode: {'classic' if here.db.maze_reset_on_wrong else 'forgiving'})|n"]
        sols = here.db.maze_solutions or {}
        if not sols:
            lines.append("  |x(no solutions set)|n")
        for name, sol in sols.items():
            from world.maze import describe_solution
            dest = sol.get("dest_dbref") or "prose-only"
            lines.append(f"  |w{name}|n: {describe_solution(sol['sequence'])} → {dest}")
            gate = sol.get("gate")
            if gate:
                g = gate.get("type")
                gtxt = g if g == "quota" else f"{g} ≥ {gate.get('min', 0):.0f}"
                lines.append(f"      |Ggate: {gtxt}|n")
            if sol.get("reveal"):
                lines.append(f"      |x\"{sol['reveal']}\"|n")
        debt = float(here.db.maze_breeding_debt or 0)
        lines.append(f"  |xdecoys: {len(here.db.maze_decoys or [])} lines"
                     + (f" · breeding-debt {debt:.0%} ({here.db.maze_debt_species})" if debt > 0 else "")
                     + "|n")
        caller.msg("\n".join(lines))


# -------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------

ALL_BUILDER_CMDS = [
    CmdDig,
    CmdRLink,
    CmdRUnlink,
    CmdRName,
    CmdRDesc,
    CmdRTime,
    CmdRWeather,
    CmdRSeason,
    CmdRCrowd,
    CmdRMood,
    CmdRAmbient,
    CmdRToggle,
    CmdREntry,
    CmdRExamine,
    CmdRFlags,
    CmdRType,
    CmdMaze,
]
