r"""
Evennia settings file.

The available options are found in the default settings file found
here:

https://www.evennia.com/docs/latest/Setup/Settings-Default.html

Remember:

Don't copy more from the default file than you actually intend to
change; this will make sure that you don't overload upstream updates
unnecessarily.

When changing a setting requiring a file system path (like
path/to/actual/file.py), use GAME_DIR and EVENNIA_DIR to reference
your game folder and the Evennia library folders respectively. Python
paths (path.to.module) should be given relative to the game's root
folder (typeclasses.foo) whereas paths within the Evennia library
needs to be given explicitly (evennia.foo).

If you want to share your game dir, including its settings, you can
put secret game- or server-specific settings in secret_settings.py.

"""

# Use the defaults from Evennia unless explicitly overridden
from evennia.settings_default import *

INSTALLED_APPS += ["web.news.apps.NewsConfig"]

######################################################################
# Evennia base server config
######################################################################

SERVERNAME = "Re:Void"
GAME_SLOGAN = "Reshaping the Chaos of Nothingness, Creating from the essence of The Void."

######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")

######################################################################
# Character and account settings
######################################################################

MAX_NR_CHARACTERS = 5
MULTISESSION_MODE = 2

# New characters start in The Forming (Space 1: Before).
# After completing the tutorial they'll end up in the hub.
# On subsequent logins, characters return to wherever they last were.
START_LOCATION = "#3"
DEFAULT_HOME = "#3"

######################################################################
# Typeclass overrides
######################################################################

BASE_CHARACTER_TYPECLASS = "typeclasses.characters.Character"
BASE_ROOM_TYPECLASS = "typeclasses.rooms.Room"
BASE_EXIT_TYPECLASS = "typeclasses.exits.Exit"
BASE_OBJECT_TYPECLASS = "typeclasses.objects.Object"
BASE_ACCOUNT_TYPECLASS = "typeclasses.accounts.Account"
BASE_SCRIPT_TYPECLASS = "typeclasses.scripts.Script"
BASE_CHANNEL_TYPECLASS = "typeclasses.channels.Channel"

######################################################################
# Wisp and ambient settings
######################################################################

DEFAULT_WISP_MOOD = "uncertain"

# Ambient script interval in seconds
# Development: 20-30 seconds for testing
# Production: change to 240, 480
WISP_AMBIENT_INTERVAL_MIN = 600
WISP_AMBIENT_INTERVAL_MAX = 900

# Haunting wisp ambient interval
WISP_HAUNT_INTERVAL_MIN = 650
WISP_HAUNT_INTERVAL_MAX = 980

######################################################################
# YAML pool path
######################################################################

POOL_BASE_PATH = "world/data/pools"

######################################################################
# Game time settings
######################################################################

TIME_FACTOR = 2.0

TIME_PERIODS = {
    "dawn":      (5,  7),
    "morning":   (7,  12),
    "afternoon": (12, 17),
    "dusk":      (17, 19),
    "evening":   (19, 23),
    "midnight":  (23, 5),
}