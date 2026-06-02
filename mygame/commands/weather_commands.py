"""
commands/weather_commands.py

Weather and time-of-day commands.

  weather         — show current weather and time of day (all players)
  weather/set     — force a specific weather state (Builder only)
  weather/next    — advance to next weather tick immediately (Builder only)

Uses the canonical systems:
  world/weather.py   — get_weather(), set_weather(), WEATHER_STATES
  world/gametime.py  — get_time_period(), get_time_display()

Valid weather states: clear, overcast, rain, heavy_rain, fog, storm, snow
"""

from evennia.commands.default.muxcommand import MuxCommand


class CmdWeather(MuxCommand):
    """
    Check the current weather and time of day.

    Usage:
      weather              — show current conditions
      weather/set <state>  — force weather state (Builder)
      weather/next         — advance weather tick now (Builder, for testing)

    Valid weather states:
      clear, overcast, rain, heavy_rain, fog, storm, snow
    """

    key     = "weather"
    locks   = "cmd:all()"
    help_category = "General"
    switch_options = ("set", "next")

    def func(self):
        from world.weather  import get_weather, set_weather, WEATHER_STATES
        from world.gametime import get_time_period, get_time_display

        if "set" in self.switches:
            if not self.caller.permissions.check("Builder"):
                self.caller.msg("|xOnly builders can force weather states.|n")
                return
            state = self.args.strip().lower()
            if state not in WEATHER_STATES:
                self.caller.msg(
                    f"|xUnknown weather state '{state}'.\n"
                    f"Valid: {', '.join(WEATHER_STATES)}|n"
                )
                return
            set_weather(state, broadcast=True)
            self.caller.msg(f"|wWeather set to:|n {state}")
            return

        if "next" in self.switches:
            if not self.caller.permissions.check("Builder"):
                self.caller.msg("|xOnly builders can advance the weather tick.|n")
                return
            from evennia import search_script
            from world.weather import WEATHER_SCRIPT_KEY
            scripts = search_script(WEATHER_SCRIPT_KEY)
            if scripts:
                scripts[0].at_repeat()
                self.caller.msg(
                    f"|wWeather tick advanced.|n\n"
                    f"|wWeather:|n {get_weather()}\n"
                    f"|wTime:|n    {get_time_display()}"
                )
            else:
                self.caller.msg("|xWeather script not found. Has it been started?|n")
            return

        # Default: show conditions
        weather     = get_weather()
        time_period = get_time_period()
        time_disp   = get_time_display()
        self.caller.msg(
            f"|wWeather:|n {weather}\n"
            f"|wTime:|n    {time_disp}"
        )
