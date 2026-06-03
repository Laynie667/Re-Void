"""
commands/vibrate_commands.py

Commands for controlling vibrating items.

  vibrate <target> [intensity]   — set vibration on target's vibrating item
  vibrate/stop <target>          — turn off vibration
  vibrate/pulse <target>         — one-shot burst message regardless of state

Requires a RemoteControlItem in your inventory paired to the target's
vibrating item, OR staff access.
"""

from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand


class CmdVibrate(MuxCommand):
    """
    Control a vibrating item worn by someone in your room.

    Usage:
      vibrate <target> [intensity]   — set intensity (low/medium/high/random)
      vibrate/stop <target>          — turn off
      vibrate/pulse <target>         — fire one burst message now

    Requires a remote control in your inventory paired to their device.

    Examples:
      vibrate Laynie medium
      vibrate/stop Laynie
      vibrate/pulse Laynie
    """

    key     = "vibrate"
    locks   = "cmd:all()"
    help_category = "Interaction"
    switch_options = ("stop", "pulse")

    def func(self):
        caller = self.caller
        args   = self.args.strip()
        room   = caller.location

        if not args:
            caller.msg("|xUsage: vibrate <target> [low/medium/high/random]|n")
            return

        parts     = args.split(None, 1)
        tgt_name  = parts[0]
        intensity = parts[1].strip().lower() if len(parts) > 1 else "medium"

        target = caller.search(tgt_name, location=room)
        if not target:
            return

        from typeclasses.vibration_item import VibratingPlugItem, RemoteControlItem

        # Find vibrating item on target
        vib_item = None
        for obj in target.contents:
            if isinstance(obj, VibratingPlugItem) and obj.db.is_inserted:
                vib_item = obj
                break

        if not vib_item:
            caller.msg(f"|x{target.db.rp_name or target.name} has no active vibrating device.|n")
            return

        # Check for paired remote in caller inventory (or staff bypass)
        has_remote = (
            caller.is_superuser or
            caller.check_permstring("Admin") or
            any(
                isinstance(obj, RemoteControlItem) and
                obj.db.paired_item == vib_item.dbref
                for obj in caller.contents
            )
        )
        if not has_remote:
            caller.msg("|xYou don't have a remote control paired to their device.|n")
            return

        target_name = target.db.rp_name or target.name
        caller_name = caller.db.rp_name or caller.name

        if "stop" in self.switches:
            vib_item.set_vibe("off")
            caller.msg(f"|wVibration stopped on {target_name}'s device.|n")
            target.msg(f"|xThe vibration stops.|n")
            return

        if "pulse" in self.switches:
            import random
            from typeclasses.vibration_item import _PRIVATE_MSGS, _ROOM_MSGS
            target.msg(random.choice(_PRIVATE_MSGS["high"]))
            if room:
                room_msgs = _ROOM_MSGS.get("high", [])
                if room_msgs and random.random() < 0.70:
                    room.msg_contents(
                        random.choice(room_msgs).format(name=target_name),
                        exclude=[caller, target],
                    )
            caller.msg(f"|w[Pulse sent to {target_name}]|n")
            try:
                from typeclasses.arousal_script import add_arousal
                add_arousal(target, 8.0)
            except Exception:
                pass
            return

        # Set intensity
        valid = ("low", "medium", "high", "random", "off")
        if intensity not in valid:
            caller.msg(f"|xIntensity must be: {', '.join(valid)}|n")
            return

        vib_item.set_vibe(intensity)
        caller.msg(f"|wVibration set to {intensity} on {target_name}'s device.|n")
        if intensity == "off":
            target.msg("|xThe vibration stops.|n")
        else:
            target.msg(f"|xThe vibration starts — {intensity}.|n")


ALL_VIBRATE_CMDS = [CmdVibrate]
