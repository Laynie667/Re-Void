"""
Cooking commands.

CmdCook  — prepare something from the kitchen's pantry list.
           Broadcasts a scent message after a short delay, then a "ready"
           message after a longer one.

Zone property used: zone["pantry"] — list of item name strings.
Builders populate this with:
  roomzone pantry <zone> + <item name>
"""

from evennia import Command
from evennia.utils.utils import delay


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fuzzy_pantry(room, query):
    """
    Search all zones in the room for a pantry item matching query.
    Returns (zone_name, canonical_item_name) or (None, None).
    """
    if not room:
        return None, None
    zones = room.db.zones or {}
    q = query.lower()
    for zname, zdata in zones.items():
        if not hasattr(zdata, "get"):
            continue
        for item in (zdata.get("pantry") or []):
            if q in item.lower() or item.lower().startswith(q):
                return zname, item
    return None, None


# Scent messages keyed by rough food category
_SCENTS = {
    "egg":     "The clean, simple smell of eggs cooking drifts from the kitchen.",
    "bacon":   "The smell of bacon hits the room like a declaration.",
    "bread":   "The unmistakable warmth of fresh bread begins to fill the cabin.",
    "cake":    "Something sweet is baking. The whole room notices.",
    "cookie":  "Butter and sugar. The kitchen is doing something right.",
    "biscuit": "The smell of baking dough reaches the rest of the room.",
    "pastry":  "Something buttery is in the oven. The room approves.",
    "soup":    "Something slow and savory begins scenting the air from the kitchen.",
    "stew":    "A deep, meaty smell starts its slow work on everyone in the room.",
    "pasta":   "Garlic and something simmering. The kitchen smells like effort.",
    "coffee":  "Fresh coffee fills the room with the specific authority of a morning decision.",
    "tea":     "The thin, clean smell of steeping tea drifts from the kitchen.",
    "oat":     "Porridge on the stove. Simple and honest.",
    "pancake": "Butter and batter. Breakfast smells arrive without apology.",
    "waffle":  "Butter and batter. Breakfast smells arrive without apology.",
    "rice":    "Something steaming and starchy joins the kitchen smells.",
    "roast":   "A slow, rich roast smell begins its long campaign on the room.",
    "fish":    "The kitchen has taken on that specific, assertive smell of fish cooking.",
    "default": "Something good is being made in the kitchen.",
}


def _scent_msg(item):
    item_l = item.lower()
    for key, msg in _SCENTS.items():
        if key in item_l:
            return msg
    return _SCENTS["default"]


def _is_baking(item, cmdstring):
    bake_words = ("bread", "cake", "cookie", "biscuit", "pastry", "waffle", "muffin", "tart", "pie")
    return "bake" in cmdstring.lower() or any(w in item.lower() for w in bake_words)


# ---------------------------------------------------------------------------
# CmdCook
# ---------------------------------------------------------------------------

class CmdCook(Command):
    """
    Cook or bake something from the kitchen pantry.

    Usage:
      cook                — list what's available in the kitchen
      cook <item>         — start cooking
      bake <item>         — same, with baking flavor

    Builders configure the kitchen pantry with:
      roomzone pantry <zone> + <item name>

    Cooking takes a little time — the room will smell it before it's done,
    and done before you know it.
    """

    key     = "cook"
    aliases = ["bake"]
    locks   = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        args = self.args.strip()

        # No args — list pantry
        if not args:
            zones = room.db.zones or {}
            items = []
            for zname, zdata in zones.items():
                if not hasattr(zdata, "get"):
                    continue
                for item in (zdata.get("pantry") or []):
                    items.append(item)
            if not items:
                caller.msg("|xThe kitchen pantry is empty right now.|n")
            else:
                lines = ["|wKitchen pantry:|n"]
                for item in items:
                    lines.append(f"  |x{item}|n")
                caller.msg("\n".join(lines))
            return

        zone_name, item = _fuzzy_pantry(room, args)
        if not item:
            caller.msg(
                f"|xThere's no '{args}' stocked in the kitchen.\n"
                "|xType |wcook|n with no arguments to see what's available.|n"
            )
            return

        c_name = caller.db.rp_name or caller.name
        baking = _is_baking(item, self.cmdstring)
        verb   = "baking" if baking else "cooking"
        scent  = _scent_msg(item)

        caller.msg(f"|yYou move into the kitchen and start {verb} {item}.|n")
        room.msg_contents(
            f"|x{c_name} moves into the kitchen and starts {verb}.|n",
            exclude=caller,
        )

        # Scent reaches the room after ~30s
        def _send_scent():
            if not caller.location or caller.location != room:
                return
            room.msg_contents(f"|x{scent}|n")

        # Dish ready after ~2 minutes
        def _ready():
            if not caller.location or caller.location != room:
                return
            room.msg_contents(
                f"|y{c_name}'s {item} is ready.|n"
            )

        delay(30,  _send_scent)
        delay(120, _ready)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_COOKING_CMDS = [CmdCook]
