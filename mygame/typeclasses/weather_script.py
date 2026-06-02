"""
typeclasses/weather_script.py

WeatherTimeScript — singleton persistent script that tracks weather state
and time of day for Re:Void.

Access:
    from typeclasses.weather_script import WeatherTimeScript
    wt = WeatherTimeScript.get()
    wt.weather    # e.g. "clear"
    wt.time_of_day  # e.g. "evening"
    wt.get_summary()  # human-readable combined description

Weather states: clear, cloudy, light_rain, heavy_rain, storm, fog, snow
Time states:    dawn, morning, midday, afternoon, dusk, evening, night, deep_night

Weather changes on a Markov chain every 30 minutes.
Time-of-day is derived from the real server clock each tick.

Outdoor rooms (db.is_outdoor = True) receive ambient messages from
world/weather_messages.yaml on the standard rambient timer.
"""

import random
import time
from evennia import DefaultScript


# ---------------------------------------------------------------------------
# Weather transition weights
# (current_state → {next_state: weight})
# ---------------------------------------------------------------------------

_TRANSITIONS = {
    "clear":       {"clear": 65, "cloudy": 20, "fog": 10, "snow": 5},
    "cloudy":      {"cloudy": 40, "clear": 25, "light_rain": 25, "fog": 10},
    "light_rain":  {"light_rain": 40, "cloudy": 25, "heavy_rain": 25, "clear": 10},
    "heavy_rain":  {"heavy_rain": 40, "storm": 30, "light_rain": 25, "cloudy": 5},
    "storm":       {"storm": 50, "heavy_rain": 30, "cloudy": 20},
    "fog":         {"fog": 55, "clear": 30, "cloudy": 15},
    "snow":        {"snow": 55, "clear": 30, "cloudy": 15},
}

_STARTING_WEATHER = "clear"


def _weighted_choice(weights: dict) -> str:
    """Pick a key from {key: weight} dict."""
    keys   = list(weights.keys())
    values = list(weights.values())
    total  = sum(values)
    r      = random.uniform(0, total)
    cumul  = 0
    for k, v in zip(keys, values):
        cumul += v
        if r <= cumul:
            return k
    return keys[-1]


def _time_of_day() -> str:
    """Return current time-of-day label based on server clock hour."""
    hour = int(time.strftime("%H"))
    if   0  <= hour < 5:  return "deep_night"
    elif 5  <= hour < 7:  return "dawn"
    elif 7  <= hour < 12: return "morning"
    elif 12 <= hour < 14: return "midday"
    elif 14 <= hour < 17: return "afternoon"
    elif 17 <= hour < 20: return "dusk"
    elif 20 <= hour < 22: return "evening"
    else:                 return "night"


# ---------------------------------------------------------------------------
# WeatherTimeScript
# ---------------------------------------------------------------------------

class WeatherTimeScript(DefaultScript):
    """Singleton weather + time-of-day tracker."""

    def at_script_creation(self):
        self.key        = "weather_time"
        self.persistent = True
        self.repeats    = 0
        self.interval   = 1800   # 30 minutes

        self.db.weather     = _STARTING_WEATHER
        self.db.time_of_day = _time_of_day()

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def get(cls):
        from evennia import search_script
        results = [s for s in (search_script("weather_time") or [])
                   if s.key == "weather_time"]
        if results:
            return results[0]
        from evennia.utils import create
        return create.create_script(cls, key="weather_time", persistent=True)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def weather(self) -> str:
        return self.db.weather or "clear"

    @property
    def time_of_day(self) -> str:
        return self.db.time_of_day or _time_of_day()

    # ------------------------------------------------------------------
    # Per-tick update
    # ------------------------------------------------------------------

    def at_repeat(self):
        # Advance weather via Markov chain
        current = self.db.weather or "clear"
        weights = _TRANSITIONS.get(current, _TRANSITIONS["clear"])
        self.db.weather = _weighted_choice(weights)

        # Update time from clock
        self.db.time_of_day = _time_of_day()

        # Fire outdoor ambient messages
        self._fire_outdoor_ambients()

    # ------------------------------------------------------------------
    # Outdoor ambient dispatch
    # ------------------------------------------------------------------

    def _fire_outdoor_ambients(self):
        """
        Send weather + time ambient messages to all outdoor rooms.
        Outdoor rooms must have db.is_outdoor = True.
        """
        try:
            import yaml, os, random as _r
            path = os.path.join(
                os.path.dirname(__file__), "..", "world", "weather_messages.yaml"
            )
            with open(os.path.normpath(path), "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception:
            return

        weather_pool = (
            data.get("outdoor_ambient", {}).get(self.db.weather, [])
        )
        time_pool = (
            data.get("time_ambient", {}).get(self.db.time_of_day, [])
        )

        from evennia.objects.models import ObjectDB
        for obj in ObjectDB.objects.filter(db_typeclass_path__contains="Room"):
            try:
                room = obj.typeclass
                if not getattr(room.db, "is_outdoor", False):
                    continue
                if not room.contents:
                    continue

                msgs = []
                if weather_pool and _r.random() < 0.60:
                    msgs.append(_r.choice(weather_pool))
                if time_pool and _r.random() < 0.40:
                    msgs.append(_r.choice(time_pool))

                for msg in msgs:
                    room.msg_contents(f"|x{msg}|n")

            except Exception:
                continue

    # ------------------------------------------------------------------
    # Summary for commands
    # ------------------------------------------------------------------

    def get_summary(self) -> str:
        try:
            import yaml, os
            path = os.path.join(
                os.path.dirname(__file__), "..", "world", "weather_messages.yaml"
            )
            with open(os.path.normpath(path), "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            w_desc = data.get("weather_desc", {}).get(self.db.weather, self.db.weather)
            t_desc = data.get("time_desc", {}).get(self.db.time_of_day, self.db.time_of_day)
        except Exception:
            w_desc = self.db.weather
            t_desc = self.db.time_of_day

        return f"|wWeather:|n {w_desc}\n|wTime:|n    {t_desc}"

    # ------------------------------------------------------------------
    # Staff: force a state
    # ------------------------------------------------------------------

    def set_weather(self, state: str):
        if state in _TRANSITIONS:
            self.db.weather = state

    def set_time(self, state: str):
        valid = ["dawn","morning","midday","afternoon","dusk","evening","night","deep_night"]
        if state in valid:
            self.db.time_of_day = state
