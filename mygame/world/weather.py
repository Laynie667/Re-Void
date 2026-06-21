"""
world/weather.py

Global weather state for ReVoid.

Weather is managed by a single persistent Script that
runs continuously and transitions weather states over time.
Weather affects rooms that have self.db.has_weather = True.
"""

import random
from evennia import DefaultScript
from evennia.utils import logger


# -------------------------------------------------------------------
# Weather state definitions
# -------------------------------------------------------------------

WEATHER_STATES = [
    "clear",
    "overcast",
    "rain",
    "heavy_rain",
    "fog",
    "storm",
    "snow",
]

# Valid transitions from each state
# Weather can't jump from clear to storm immediately
WEATHER_TRANSITIONS = {
    "clear":      ["clear", "clear", "overcast"],
    "overcast":   ["overcast", "clear", "rain", "fog"],
    "rain":       ["rain", "overcast", "heavy_rain"],
    "heavy_rain": ["heavy_rain", "rain", "storm"],
    "fog":        ["fog", "overcast", "clear"],
    "storm":      ["storm", "heavy_rain", "rain"],
    "snow":       ["snow", "overcast", "clear"],
}

# Weather descriptions broadcast when weather changes
WEATHER_CHANGE_MSGS = {
    "clear":      "The clouds begin to part. The air clears.",
    "overcast":   "Clouds gather overhead, dulling the light.",
    "rain":       "Rain begins — light at first, then settling in.",
    "heavy_rain": "The rain intensifies.",
    "fog":        "A fog rolls in, softening everything at a distance.",
    "storm":      "The storm arrives without much additional warning.",
    "snow":       "Snow begins to fall.",
}

# Global weather state storage key
WEATHER_SCRIPT_KEY = "global_weather_script"


def _seasonal_transitions(current, season):
    """Return the transition candidates for `current`, adjusted for season.

    Fixes the orphaned-snow bug: no base transition leads *into* `snow`, so it
    was unreachable and winter had to be faked. Snow is now **winter-only** —
    in winter cold/wet skies can turn to snow; out of season snow never appears
    (and any lingering snow thaws via its own transitions). Reuses the real
    `gametime` season rather than a parallel calendar.
    """
    base = list(WEATHER_TRANSITIONS.get(current, ["clear"]))
    if season == "winter":
        if current == "overcast":
            base += ["snow"]
        elif current == "fog":
            base += ["snow"]
        elif current in ("rain", "heavy_rain"):
            # Precipitation tends to fall as snow when it's cold enough.
            base += ["snow", "snow"]
    else:
        # Out of season: never transition into snow; existing snow thaws.
        base = [s for s in base if s != "snow"] or ["clear"]
    return base


# -------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------

def get_weather():
    """
    Get the current global weather state.

    Returns:
        str: Current weather state name, e.g. 'rain'
    """
    try:
        from evennia import search_script
        scripts = search_script(WEATHER_SCRIPT_KEY)
        if scripts:
            return scripts[0].db.current_weather or "clear"
    except Exception:
        pass
    return "clear"


def set_weather(new_state, broadcast=True):
    """
    Set the global weather state manually.
    Used by staff commands and the weather script.

    Args:
        new_state (str): Weather state to set.
        broadcast (bool): Whether to broadcast change to outdoor rooms.
    """
    if new_state not in WEATHER_STATES:
        return False

    try:
        from evennia import search_script
        scripts = search_script(WEATHER_SCRIPT_KEY)
        if scripts:
            scripts[0].db.current_weather = new_state
            if broadcast:
                scripts[0].broadcast_weather_change(new_state)
        return True
    except Exception as e:
        logger.log_err(f"Error setting weather: {e}")
        return False


# -------------------------------------------------------------------
# Weather Script
# -------------------------------------------------------------------

class WeatherScript(DefaultScript):
    """
    Global weather management script.
    Runs continuously, transitioning weather states over time.
    Broadcasts weather changes to all outdoor/windowed rooms.

    Start with:
        from world.weather import WeatherScript
        from evennia import create_script
        create_script(WeatherScript)
    """

    def at_script_creation(self):
        self.key = WEATHER_SCRIPT_KEY
        self.desc = "Global weather state manager"
        self.interval = 1800
        # Check/change weather every 30 minutes real time
        self.persistent = True
        self.repeats = 0
        # Run forever

        # Initial state
        self.db.current_weather = "clear"

    def at_repeat(self):
        """
        Called every interval seconds.
        Potentially transitions to a new weather state.
        """
        current = self.db.current_weather or "clear"
        season = "autumn"
        try:
            from world.gametime import get_season
            season = get_season()
        except Exception:
            pass
        transitions = _seasonal_transitions(current, season)
        new_weather = random.choice(transitions)

        if new_weather != current:
            self.db.current_weather = new_weather
            self.broadcast_weather_change(new_weather)

    def broadcast_weather_change(self, new_state):
        """
        Send weather change messages to all rooms with has_weather=True.

        Args:
            new_state (str): The new weather state.
        """
        msg = WEATHER_CHANGE_MSGS.get(new_state, "")
        if not msg:
            return

        try:
            from evennia import search_object
            from typeclasses.rooms import Room

            # Find all rooms with weather enabled
            rooms = [
                obj for obj in
                search_object(typeclass=Room)
                if obj.db.has_weather
            ]

            for room in rooms:
                if room.contents:
                    room.msg_contents(f"|x{msg}|n")

        except Exception as e:
            logger.log_err(f"Error broadcasting weather: {e}")

    def at_server_reload(self):
        """Preserve weather state across reloads."""
        pass