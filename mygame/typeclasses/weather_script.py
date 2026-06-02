"""
typeclasses/weather_script.py

Compatibility shim.  All actual weather and time logic lives in:
  - world/weather.py   — WeatherScript + get_weather() / set_weather()
  - world/gametime.py  — get_time_period(), get_season(), get_time_display()

This module re-exports the canonical accessors so any code that imported
from here continues to work without changes.
"""

from world.gametime import get_time_period, get_season, get_time_display
from world.weather  import get_weather, set_weather, WEATHER_STATES


def get_time_of_day() -> str:
    """Return the current IC time period (dawn/morning/afternoon/dusk/evening/midnight)."""
    return get_time_period()


class WeatherTimeScript:
    """
    Thin compatibility wrapper.
    Prefer using world/weather.py and world/gametime.py directly.
    """

    @classmethod
    def get(cls):
        """Return the active WeatherScript instance, or None."""
        from evennia import search_script
        from world.weather import WEATHER_SCRIPT_KEY
        scripts = [
            s for s in (search_script(WEATHER_SCRIPT_KEY) or [])
            if s.key == WEATHER_SCRIPT_KEY
        ]
        return scripts[0] if scripts else None

    def get_summary(self) -> str:
        weather    = get_weather()
        time_period = get_time_period()
        return (
            f"|wWeather:|n {weather}\n"
            f"|wTime:|n    {time_period}"
        )

    def set_weather(self, state: str):
        set_weather(state, broadcast=True)

    def set_time(self, state: str):
        """IC time is driven by Evennia's gametime — cannot be set directly."""
        pass

    @property
    def weather(self) -> str:
        return get_weather()

    @property
    def time_of_day(self) -> str:
        return get_time_period()
