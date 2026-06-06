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
# CmdFridge
# ---------------------------------------------------------------------------
# NOTE: CmdMilk was removed from this file. The modern milking machine
# system lives in commands/body_mod_commands.py (CmdMilk using
# MilkingSessionScript + GlobalFluidBank + FluidFridge).
# ---------------------------------------------------------------------------

def _fridge_bottles(room):
    """Return FluidBottle objects stocked in this room's fridge."""
    from typeclasses.fluid_bottle import FluidBottle
    return [
        obj for obj in room.contents
        if isinstance(obj, FluidBottle) and getattr(obj.db, "in_fridge", False)
    ]


class CmdFridge(Command):
    """
    Browse, take from, stock, or drink from the room's fridge.

    Usage:
      fridge                  — list everything on the shelf
      fridge take <n>         — take item number <n> from the shelf
      fridge drink <n>        — take a sip from bottle number <n> in place
      fridge store <bottle>   — put a FluidBottle from your inventory into the fridge
      fridge drain <n>        — drain an entire bottle (consume fully)

    The shelf shows both old-style jars (collected via legacy 'milk' command)
    and new FluidBottle objects (produced by the milking machine).

    New-style bottles can be taken as physical objects, sipped in place,
    or drained entirely. Old-style jars are removed from the list when taken.

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

        args = self.args.strip()

        # -- Store a bottle --
        if args.lower().startswith("store"):
            self._do_store(caller, room, args[5:].strip())
            return

        # Build unified shelf: legacy dicts first, then FluidBottle objects
        stock   = _fridge_stock(room)      # list of dicts
        bottles = _fridge_bottles(room)    # FluidBottle objects

        total = len(stock) + len(bottles)

        # -- List --
        if not args or args.lower() == "list":
            if total == 0:
                caller.msg("|xThe dairy shelf in the fridge is empty.|n")
                return
            lines = ["|wDairy shelf:|n"]
            idx = 1
            for jar in stock:
                lines.append(
                    f"  |w{idx}.|n |y{jar['from']}'s {jar['fluid']}|n "
                    f"|x— {jar.get('desc', '')} — {jar.get('date', '')}|n"
                )
                idx += 1
            for bottle in bottles:
                from typeclasses.production_item import format_volume
                vol   = format_volume(bottle.db.volume_ml or 0)
                flav  = f", {bottle.db.fluid_flavor}" if bottle.db.fluid_flavor else ""
                lines.append(
                    f"  |w{idx}.|n |y{bottle.db.producer_name}'s "
                    f"{bottle.db.fluid_type}{flav}|n |x({vol})|n"
                )
                idx += 1
            caller.msg("\n".join(lines))
            return

        # -- Take --
        if args.lower().startswith("take"):
            n_str = args[4:].strip()
            self._do_take(caller, room, n_str, stock, bottles, drain=False)
            return

        # -- Drink (sip in place) --
        if args.lower().startswith("drink"):
            n_str = args[5:].strip()
            self._do_drink(caller, room, n_str, stock, bottles)
            return

        # -- Drain --
        if args.lower().startswith("drain"):
            n_str = args[5:].strip()
            self._do_take(caller, room, n_str, stock, bottles, drain=True)
            return

        caller.msg(
            "|xUsage: fridge | fridge take <n> | fridge drink <n> | "
            "fridge store <bottle> | fridge drain <n>|n"
        )

    def _resolve_n(self, n_str, stock, bottles):
        """
        Parse the shelf number and return (jar_or_bottle, is_bottle, index_in_list).
        Returns (None, False, -1) on error.
        """
        if not n_str.isdigit():
            return None, False, -1
        n = int(n_str)
        total = len(stock) + len(bottles)
        if n < 1 or n > total:
            return None, False, -1
        if n <= len(stock):
            return stock[n - 1], False, n - 1
        else:
            bottle_idx = n - len(stock) - 1
            return bottles[bottle_idx], True, bottle_idx

    def _do_take(self, caller, room, n_str, stock, bottles, drain=False):
        item, is_bottle, idx = self._resolve_n(n_str, stock, bottles)
        if item is None:
            caller.msg(f"|xNo item #{n_str} on the shelf.|n")
            return
        c_name = caller.db.rp_name or caller.name

        if not is_bottle:
            jar = item
            stock.pop(idx)
            _write_fridge(room, stock)
            caller.msg(
                f"|yYou take the jar of {jar['from']}'s {jar['fluid']}|n "
                f"|x({jar.get('desc','')}, {jar.get('date','')}).|n"
            )
            room.msg_contents(
                f"|x{c_name} takes something from the dairy shelf.|n",
                exclude=caller,
            )
        else:
            bottle = item
            if drain:
                msg = bottle.do_drink(caller, drain=True)
                caller.msg(msg)
                if bottle.db.is_empty:
                    bottle.delete()
                else:
                    bottle.db.in_fridge = False
                    bottle.location = caller
            else:
                bottle.db.in_fridge = False
                bottle.location = caller
                from typeclasses.production_item import format_volume
                vol = format_volume(bottle.db.volume_ml or 0)
                caller.msg(
                    f"|yYou take the bottle of "
                    f"{bottle.db.producer_name}'s {bottle.db.fluid_type}|n "
                    f"|x({vol}).|n"
                )
            room.msg_contents(
                f"|x{c_name} takes something from the dairy shelf.|n",
                exclude=caller,
            )

    def _do_drink(self, caller, room, n_str, stock, bottles):
        item, is_bottle, idx = self._resolve_n(n_str, stock, bottles)
        if item is None:
            caller.msg(f"|xNo item #{n_str} on the shelf.|n")
            return
        c_name = caller.db.rp_name or caller.name

        if not is_bottle:
            # Legacy jar — no partial drinking; just describes it
            jar = item
            caller.msg(
                f"You taste a bit from the jar — "
                f"{jar['from']}'s {jar['fluid']}, {jar.get('desc','')}."
            )
        else:
            bottle = item
            msg = bottle.do_drink(caller)
            caller.msg(msg)
            if bottle.db.is_empty:
                bottle.delete()
            room.msg_contents(
                f"|x{c_name} samples something from the dairy shelf.|n",
                exclude=caller,
            )

    def _do_store(self, caller, room, bottle_name):
        from typeclasses.fluid_bottle import FluidBottle
        target = None
        for obj in caller.contents:
            if isinstance(obj, FluidBottle):
                if not bottle_name or bottle_name.lower() in obj.key.lower():
                    target = obj
                    break
        if not target:
            caller.msg(
                "|xYou don't have a fluid bottle"
                + (f" matching '{bottle_name}'" if bottle_name else "")
                + " to store.|n"
            )
            return
        target.db.in_fridge = True
        target.location = room
        c_name = caller.db.rp_name or caller.name
        from typeclasses.production_item import format_volume
        vol = format_volume(target.db.volume_ml or 0)
        caller.msg(
            f"|yYou place the bottle of "
            f"{target.db.producer_name}'s {target.db.fluid_type}|n "
            f"|x({vol}) on the dairy shelf.|n"
        )
        room.msg_contents(
            f"|x{c_name} adds something to the dairy shelf.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class CmdFluids(Command):
    """
    Check your fluid bank — lifetime produced and how much is pending a bottle.

    Usage:
        fluids

    The bank accumulates what you produce and mints a 591ml (20 fl oz) bottle each
    time the pending buffer fills; bottles route to the fridge in the room they were
    produced in (or any fridge). This shows how close the next bottle is.
    """

    key           = "fluids"
    aliases       = ["fluidbalance", "fluidbank"]
    locks         = "cmd:all()"
    help_category = "Economy"

    def func(self):
        try:
            from typeclasses.fluid_bank import GlobalFluidBank
            self.caller.msg(GlobalFluidBank.get().get_deposit_summary(self.caller))
        except Exception as e:
            self.caller.msg(f"|xNo fluid bank available: {e}|n")


ALL_DAIRY_CMDS = [CmdSetDairy, CmdFridge, CmdFluids]
