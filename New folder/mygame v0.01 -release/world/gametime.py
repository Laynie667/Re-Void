"""
world/gametime.py

Tracks in-game time and provides helper functions for
querying the current time period and season.

Uses Evennia's built-in gametime system as the source,
configured by TIME_FACTOR in settings.py.
"""

from evennia.utils import gametime
from django.conf import settings


# -------------------------------------------------------------------
# Time period configuration
# -------------------------------------------------------------------

TIME_PERIODS = getattr(settings, 'TIME_PERIODS', {
    "dawn":      (5,  7),
    "morning":   (7,  12),
    "afternoon": (12, 17),
    "dusk":      (17, 19),
    "evening":   (19, 23),
    "midnight":  (23, 5),
})

# Season configuration
# Each season covers 3 IC months
SEASONS = {
    "spring": (3,  5),
    "summer": (6,  8),
    "autumn": (9,  11),
    "winter": (12, 2),
}

# IC calendar — 12 months, 30 days each
# Total IC year = 360 days
DAYS_PER_MONTH = 30
MONTHS_PER_YEAR = 12
HOURS_PER_DAY = 24
SECONDS_PER_IC_DAY = HOURS_PER_DAY * 60 * 60


# -------------------------------------------------------------------
# Core time functions
# -------------------------------------------------------------------

def get_ic_time():
    """
    Get the current IC time as a dict.

    Returns:
        dict: {
            seconds, minutes, hours, days,
            month, year, weekday
        }
    """
    # Evennia's gametime returns seconds since game epoch
    # adjusted by TIME_FACTOR
    total_seconds = gametime.gametime(absolute=False)

    seconds = int(total_seconds % 60)
    minutes = int((total_seconds // 60) % 60)
    hours   = int((total_seconds // 3600) % 24)
    days    = int(total_seconds // 86400)

    # Calculate month and year from days
    month   = (days % (DAYS_PER_MONTH * MONTHS_PER_YEAR)) \
              // DAYS_PER_MONTH + 1
    year    = days // (DAYS_PER_MONTH * MONTHS_PER_YEAR) + 1
    day_of_month = (days % DAYS_PER_MONTH) + 1

    return {
        "seconds":     seconds,
        "minutes":     minutes,
        "hours":       hours,
        "days":        days,
        "day_of_month": day_of_month,
        "month":       month,
        "year":        year,
    }


def get_time_period():
    """
    Get the current IC time period name.

    Returns:
        str: One of dawn/morning/afternoon/dusk/evening/midnight
    """
    try:
        ic = get_ic_time()
        hour = ic["hours"]

        for period, (start, end) in TIME_PERIODS.items():
            if start < end:
                # Normal range e.g. 7-12
                if start <= hour < end:
                    return period
            else:
                # Wraps midnight e.g. 23-5
                if hour >= start or hour < end:
                    return period

        return "evening"
        # Fallback

    except Exception:
        return "evening"


def get_season():
    """
    Get the current IC season.

    Returns:
        str: One of spring/summer/autumn/winter
    """
    try:
        ic = get_ic_time()
        month = ic["month"]

        for season, (start, end) in SEASONS.items():
            if start <= end:
                if start <= month <= end:
                    return season
            else:
                # Wraps year e.g. winter (12-2)
                if month >= start or month <= end:
                    return season

        return "autumn"
        # Fallback

    except Exception:
        return "autumn"


def get_time_display():
    """
    Get a formatted IC time string for display.

    Returns:
        str: e.g. "evening — the 14th day of month 3, year 2"
    """
    try:
        ic = get_ic_time()
        period = get_time_period()
        season = get_season()

        # Ordinal suffix
        day = ic["day_of_month"]
        if 10 <= day % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

        return (
            f"{period} — "
            f"the {day}{suffix} day of month {ic['month']}, "
            f"year {ic['year']} "
            f"({season})"
        )

    except Exception:
        return "evening"


def get_clock_display():
    """
    Get a simple IC clock display.

    Returns:
        str: e.g. "21:34"
    """
    try:
        ic = get_ic_time()
        return f"{ic['hours']:02d}:{ic['minutes']:02d}"
    except Exception:
        return "00:00"