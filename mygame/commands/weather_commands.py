"""
commands/weather_commands.py

Weather and time-of-day commands.

  weather         — show current weather and time of day (all players)
  weather/set     — force a specific weather state (Builder only)
  weather/time    — force a specific time state (Builder only)
  weather/next    — advance to next weather tick immediately (Builder only)

Valid weather states: clear, cloudy, light_rain, heavy_rain, storm, fog, snow
Valid time states:    dawn, morning, midday, afternoon, dusk, evening, night, deep_night
"""

from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand


class CmdWeather(MuxCommand):
    """
    Check the current weather and time of day.

    Usage:
      weather                  — show current conditions
      weather/set <state>      — force weather state (Builder)
      weather/time <state>     — force time-of-day state (Builder)
      weather/next             — advance weather tick now (Builder)

    Valid weather states:
      clear, cloudy, light_rain, heavy_rain, storm, fog, snow

    Valid time states:
      dawn, morning, midday, afternoon, dusk, evening, night, deep_night
    """

    key     = "weather"
    aliases = ["time"]
    locks   = "cmd:all()"
    help_category = "General"
    switch_options = ("set", "time", "next")

    def func(self):
        from typeclasses.weather_script import WeatherTimeScript
        wt = WeatherTimeScript.get()

        if "set" in self.switches:
            if not self.caller.permissions.check("Builder"):
                self.caller.msg("|xOnly builders can force weather states.|n")
                return
            state = self.args.strip().lower().replace(" ", "_")
            from typeclasses.weather_script import _TRANSITIONS
            if state not in _TRANSITIONS:
                self.caller.msg(
                    f"|xUnknown weather state '{state}'.\n"
                    f"Valid: {', '.join(_TRANSITIONS.keys())}|n"
                )
                return
            wt.set_weather(state)
            self.caller.msg(f"|wWeather set to:|n {state}")
            return

        if "time" in self.switches:
            if not self.caller.permissions.check("Builder"):
                self.caller.msg("|xOnly builders can force the time of day.|n")
                return
            state = self.args.strip().lower().replace(" ", "_")
            valid = ["dawn","morning","midday","afternoon","dusk",
                     "evening","night","deep_night"]
            if state not in valid:
                self.caller.msg(
                    f"|xUnknown time state '{state}'.\n"
                    f"Valid: {', '.join(valid)}|n"
                )
                return
            wt.set_time(state)
            self.caller.msg(f"|wTime set to:|n {state}")
            return

        if "next" in self.switches:
            if not self.caller.permissions.check("Builder"):
                self.caller.msg("|xOnly builders can advance the weather tick.|n")
                return
            wt.at_repeat()
            self.caller.msg(f"|wWeather tick advanced.|n\n{wt.get_summary()}")
            return

        # Default: show current conditions
        self.caller.msg(wt.get_summary())
