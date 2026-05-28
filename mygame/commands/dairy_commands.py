"""
Dairy / fridge stock commands.

CmdSetDairy  — configure a character's production profile (fluid type, label desc)
CmdMilk      — collect from a character into a labeled jar; stores in room fridge stock
CmdFridge    — browse and take from the room's fridge stock

Room attribute:
  room.db.fridge_stock  = list of jar dicts:
    {"from": str, "fluid": str, "desc": str, "date": str}

Character attributes:
  char.db.dairy_fluid   = str   e.g. "milk", "cream", "honey", "seed", "slick"
  char.db.dairy_desc    = str   e.g. "warm and faintly sweet"
  char.db.dairy_on      = bool  whether this character is available to be milked
"""

from evennia import Command
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fridge_stock(room):
    """Return the room's fridge_stock list, initialising if absent."""
    if not getattr(room.db, "fridge_stock", None):
        room.db.fridge_stock = []
    return list(room.db.fridge_stock)


def _write_fridge(room, stock):
    """Full-list copy persistence for fridge stock."""
    room.db.fridge_stock = list(stock)


# ---------------------------------------------------------------------------
# CmdSetDairy
# ---------------------------------------------------------------------------

class CmdSetDairy(Command):
    """
    Configure your dairy production profile.

    Usage:
      setdairy                        — view your current profile
      setdairy fluid = <type>         — set what you produce
                                        e.g. milk, cream, honey, seed, slick, nectar
      setdairy desc = <description>   — label flavor text
                                        e.g. warm and faintly sweet, thick and rich
      setdairy on                     — make yourself available to be milked
      setdairy off                    — remove yourself from availability

    Examples:
      setdairy fluid = milk
      setdairy desc = warm, sweet, faintly herbal
      setdairy on
    """

    key   = "setdairy"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        caller = self.caller
        args   = self.args.strip()

        if not args:
            fluid  = getattr(caller.db, "dairy_fluid", None) or "|xnot set|n"
            desc   = getattr(caller.db, "dairy_desc",  None) or "|xnot set|n"
            on     = getattr(caller.db, "dairy_on",    False)
            status = "|won|n" if on else "|xoff|n"
            caller.msg(
                f"|wDairy profile:|n\n"
                f"  Fluid:       |w{fluid}|n\n"
                f"  Description: |x{desc}|n\n"
                f"  Available:   {status}"
            )
            return

        if args.lower() == "on":
            if not getattr(caller.db, "dairy_fluid", None):
                caller.msg(
                    "|xSet your fluid type first before enabling.\n"
                    "|xUsage: setdairy fluid = milk|n"
                )
                return
            caller.db.dairy_on = True
            fluid = caller.db.dairy_fluid
            caller.msg(f"|wYou are now available to be milked.|n |x({fluid})|n")
            return

        if args.lower() == "off":
            caller.db.dairy_on = False
            caller.msg("|xYou are no longer available to be milked.|n")
            return

        if "=" in args:
            key_part, _, val = args.partition("=")
            key_part = key_part.strip().lower()
            val      = val.strip()

            if not val:
                caller.msg("|xValue cannot be empty.|n")
                return

            if key_part == "fluid":
                caller.db.dairy_fluid = val
                caller.msg(f"|wFluid type set to:|n |y{val}|n")
            elif key_part == "desc":
                caller.db.dairy_desc = val
                caller.msg(f"|wLabel description set to:|n |x{val}|n")
            else:
                caller.msg(
                    f"|xUnknown field '{key_part}'.\n"
                    "|xUsage: setdairy fluid = <type> | setdairy desc = <text> | setdairy on/off|n"
                )
            return

        caller.msg(
            "|xUsage: setdairy fluid = <type> | setdairy desc = <text> | setdairy on/off|n"
        )


# ---------------------------------------------------------------------------
# CmdMilk
# ---------------------------------------------------------------------------

class CmdMilk(Command):
    """
    Milk a character, collecting their output into a labeled jar for the fridge.

    Usage:
      milk <character>
      milk me

    The target must have dairy availability on (setdairy on) and must have
    granted milking consent (consent allow milking).

    Self-milking is allowed and requires no consent check.

    The jar is labeled with the character's name, fluid type, description,
    and the current date. It is stored in room.db.fridge_stock until taken.

    See also: fridge, setdairy
    """

    key   = "milk"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        arg = self.args.strip()
        if not arg:
            caller.msg("|xMilk whom? Usage: milk <character> | milk me|n")
            return

        # Self-milking
        self_milk = arg.lower() in ("me", "myself", "self")
        if self_milk:
            target = caller
        else:
            target = caller.search(arg, location=room)
            if not target:
                return

        # Check dairy availability
        if not getattr(target.db, "dairy_on", False):
            t_name = target.db.rp_name or target.name
            if target == caller:
                caller.msg(
                    "|xYou aren't set as available for milking. "
                    "Use |wsetdairy fluid = <type>|n then |wsetdairy on|x to enable.|n"
                )
            else:
                caller.msg(
                    f"|x{t_name} isn't available for milking right now.|n"
                )
            return

        # Consent check (non-self only)
        if target != caller:
            t_name = target.db.rp_name or target.name
            c_name = caller.db.rp_name or caller.name

            block_list = list(getattr(target.db, "block_list", None) or [])
            if caller.id in block_list:
                caller.msg(f"|xYou cannot do that with {t_name}.|n")
                return

            consent_flags = dict(getattr(target.db, "consent_flags", None) or {})
            if not consent_flags.get("milking", False):
                caller.msg(
                    f"|x{t_name} hasn't granted milking consent. "
                    f"They can use '|wconsent allow milking|x' to enable it.|n"
                )
                return

        # Gather dairy profile
        fluid    = getattr(target.db, "dairy_fluid", None) or "milk"
        desc     = getattr(target.db, "dairy_desc",  None) or "warm"
        t_name   = target.db.rp_name or target.name
        c_name   = caller.db.rp_name or caller.name
        date_str = datetime.now().strftime("%b %d")

        # Add jar to fridge stock
        stock = _fridge_stock(room)
        jar = {
            "from":  t_name,
            "fluid": fluid,
            "desc":  desc,
            "date":  date_str,
        }
        stock.append(jar)
        _write_fridge(room, stock)

        label = f"{t_name}'s {fluid} — {desc} — {date_str}"

        if target == caller:
            caller.msg(
                f"|yYou collect your own {fluid}|n into a small jar, "
                f"seal it, and set it in the fridge.\n"
                f"|x(Label: {label})|n"
            )
            room.msg_contents(
                f"|x{c_name} adds something to the fridge. "
                f"A labeled jar joins the shelf.|n",
                exclude=caller,
            )
        else:
            caller.msg(
                f"|yYou collect {t_name}'s {fluid}|n into a small jar "
                f"and seal it carefully.\n"
                f"|x(Label: {label})|n"
            )
            target.msg(
                f"|y{c_name}|n collects your {fluid} into a jar and "
                f"|xseals it for the fridge.|n"
            )
            room.msg_contents(
                f"|y{c_name}|n tends to |w{t_name}|n quietly. "
                f"|xA labeled jar is added to the fridge shelf.|n",
                exclude=[caller, target],
            )


# ---------------------------------------------------------------------------
# CmdFridge
# ---------------------------------------------------------------------------

class CmdFridge(Command):
    """
    Browse or take from the room's fridge stock.

    Usage:
      fridge              — list all jars on the dairy shelf
      fridge take <n>     — take jar number <n>

    Jars are labeled with the producer's name, fluid type, description,
    and the date they were collected.

    See also: milk, setdairy
    """

    key   = "fridge"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        stock = _fridge_stock(room)
        args  = self.args.strip().lower()

        # List
        if not args or args == "list":
            if not stock:
                caller.msg("|xThe dairy shelf in the fridge is empty.|n")
                return
            lines = ["|wDairy shelf:|n"]
            for i, jar in enumerate(stock, 1):
                lines.append(
                    f"  |w{i}.|n |y{jar['from']}'s {jar['fluid']}|n "
                    f"|x— {jar['desc']} — {jar['date']}|n"
                )
            caller.msg("\n".join(lines))
            return

        # Take
        if args.startswith("take"):
            rest = args[4:].strip()
            if not rest.isdigit():
                caller.msg("|xUsage: fridge take <number>|n")
                return
            n = int(rest)
            if n < 1 or n > len(stock):
                caller.msg(
                    f"|xNo jar #{n}. "
                    f"There {'is' if len(stock) == 1 else 'are'} "
                    f"{len(stock)} jar(s) on the shelf.|n"
                )
                return
            jar    = stock.pop(n - 1)
            _write_fridge(room, stock)
            c_name = caller.db.rp_name or caller.name
            caller.msg(
                f"|yYou take the jar of {jar['from']}'s {jar['fluid']}|n "
                f"|x({jar['desc']}, {jar['date']}).|n"
            )
            room.msg_contents(
                f"|x{c_name} takes something from the dairy shelf.|n",
                exclude=caller,
            )
            return

        caller.msg("|xUsage: fridge | fridge take <number>|n")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_DAIRY_CMDS = [CmdSetDairy, CmdMilk, CmdFridge]
