"""
commands/inflate_commands.py

Inflation commands for Re:Void.

  inflate <target> [zone] [amount] [fluid]   — inflate a zone
  inflate/self [zone] [amount] [fluid]        — inflate your own zone
  inflate/drain <target> [zone]              — remove all volume
  inflate/check <target> [zone]              — show current level

Amount defaults to 50ml if not specified.
Fluid defaults to 'air'; any string is accepted (milk, semen, water, etc.).

Requires an InflationItem installed on the zone first.
"""

from evennia.commands.default.muxcommand import MuxCommand


class CmdInflate(MuxCommand):
    """
    Inflate or drain an inflation zone.

    Usage:
      inflate <target> [zone] [amount] [fluid]
      inflate/self [zone] [amount] [fluid]
      inflate/drain <target> [zone]
      inflate/check <target> [zone]

    Amount in ml (default 50). Fluid is 'air' by default.

    Requires the zone to have an InflationItem installed.
    Use: roomzone timedesc or zone desc with {inflation} token to show state.
    """

    key     = "inflate"
    locks   = "cmd:all()"
    help_category = "Interaction"
    switch_options = ("self", "drain", "check")

    def func(self):
        caller   = self.caller
        args     = self.args.strip()
        switches = self.switches
        room     = caller.location

        from typeclasses.inflation_item import (
            get_inflation_data, add_inflation_volume,
            drain_inflation, get_inflation_state
        )
        from typeclasses.production_item import format_volume

        # ── /self branch ─────────────────────────────────────────────
        if "self" in switches:
            target = caller
            rest   = args
        else:
            if not args:
                caller.msg(
                    "|xUsage: inflate <target> [zone] [amount] [fluid]\n"
                    "inflate/drain <target> [zone]\n"
                    "inflate/check <target> [zone]|n"
                )
                return
            parts  = args.split(None, 1)
            target = caller.search(parts[0], location=room)
            if not target:
                return
            rest = parts[1].strip() if len(parts) > 1 else ""

        target_name = target.db.rp_name or target.name
        caller_name = caller.db.rp_name or caller.name

        # Find inflation zone
        zones       = getattr(target.db, "zones", None) or {}
        zone_names  = [zn for zn, zd in zones.items()
                       if (zd.get("mechanics", {}) or {}).get("inflation")]

        if not zone_names:
            caller.msg(f"|x{target_name} has no inflation zones installed.|n")
            return

        # Parse zone / amount / fluid from rest
        zone_name  = None
        amount_ml  = 50.0
        fluid_type = "air"

        tokens = rest.split() if rest else []
        if tokens:
            # First token: zone name (try match) or amount
            first = tokens[0].lower().replace(" ", "_")
            matched_zone = next((zn for zn in zone_names
                                 if first in zn or zn.endswith(first)), None)
            if matched_zone:
                zone_name = matched_zone
                tokens = tokens[1:]
            # Remaining: amount, fluid
            for tok in tokens:
                try:
                    amount_ml = float(tok)
                except ValueError:
                    fluid_type = tok

        if not zone_name:
            if len(zone_names) == 1:
                zone_name = zone_names[0]
            else:
                lines = [f"|w{target_name}|n — inflation zones:"]
                for zn in zone_names:
                    inf = (zones[zn].get("mechanics", {}) or {}).get("inflation", {})
                    vol = inf.get("volume_ml", 0.0)
                    mx  = inf.get("max_volume_ml", 500.0)
                    state = get_inflation_state(vol, mx)
                    lines.append(f"  |w{zn.replace('_',' ')}|n — {state} ({format_volume(vol)}/{format_volume(mx)})")
                caller.msg("\n".join(lines))
                return

        zone_disp = zone_name.replace("_", " ")

        # /check
        if "check" in switches:
            inf = get_inflation_data(target, zone_name)
            if not inf:
                caller.msg(f"|x'{zone_name}' has no inflation mechanic.|n")
                return
            vol   = inf.get("volume_ml", 0.0)
            mx    = inf.get("max_volume_ml", 500.0)
            ft    = inf.get("fluid_type", "air")
            state = get_inflation_state(vol, mx)
            caller.msg(
                f"|w{target_name}'s {zone_disp}:|n "
                f"{state} — {format_volume(vol)} / {format_volume(mx)} ({ft})"
            )
            return

        # /drain
        if "drain" in switches:
            if drain_inflation(target, zone_name):
                room.msg_contents(
                    f"{caller_name} drains {target_name}'s {zone_disp}."
                )
            else:
                caller.msg(f"|xNo inflation mechanic on '{zone_name}'.|n")
            return

        # Default: inflate
        amount_ml = max(1.0, min(amount_ml, 2000.0))
        new_vol, state = add_inflation_volume(target, zone_name, amount_ml, fluid_type)

        if new_vol is None:
            caller.msg(f"|xNo inflation mechanic on '{zone_name}'.|n")
            return

        if caller == target:
            room.msg_contents(
                f"{caller_name} inflates their own {zone_disp} with {fluid_type}. "
                f"({state})"
            )
        else:
            room.msg_contents(
                f"{caller_name} inflates {target_name}'s {zone_disp} with "
                f"{fluid_type}. ({state})"
            )
