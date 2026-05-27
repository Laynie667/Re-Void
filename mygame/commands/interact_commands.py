"""
commands/interact_commands.py

Interaction commands for zone details:

    handle <detail>     — intimate interaction with a detail (emote sequence)
    study <zone>        — glean a random observation from a zone's study list

Setting up handle text (Builder):
    roomzone handle <zone>/<detail> = <text>    — set intimate handle response

Setting up study details (Builder):
    roomzone study <zone> + <text>              — add a study observation
    roomzone study/rm <zone> <index>            — remove by index
    roomzone study/list <zone>                  — list all

The 'handle' command reads zone detail's "handle_text" field.
The 'study' command reads from zone's "study_details" list (random pick).
"""

import random
from evennia import Command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_detail_in_zones(room, detail_name):
    """
    Search all zones for a detail matching detail_name.
    Returns (zone_name, detail_key, detail_text) or (None, None, None).
    Tries exact match then prefix match.
    """
    zones = room.db.zones or {}
    name = detail_name.strip().lower()
    name_under = name.replace(" ", "_")

    # Pass 1: exact
    for zone_name, zone_data in zones.items():
        if not hasattr(zone_data, "get"):
            continue
        details = zone_data.get("details") or {}
        for dkey in (name, name_under):
            if dkey in details:
                return zone_name, dkey, details[dkey]

    # Pass 2: prefix
    for zone_name, zone_data in zones.items():
        if not hasattr(zone_data, "get"):
            continue
        details = zone_data.get("details") or {}
        for dkey, dtext in details.items():
            if dkey.startswith(name) or dkey.startswith(name_under):
                return zone_name, dkey, dtext

    return None, None, None


def _get_handle_text(room, detail_name):
    """
    Return (zone_name, detail_key, handle_text) for a detail's handle_text field,
    or (None, None, None) if not found or not set.
    """
    zones = room.db.zones or {}
    name = detail_name.strip().lower()
    name_under = name.replace(" ", "_")

    for zone_name, zone_data in zones.items():
        if not hasattr(zone_data, "get"):
            continue
        handle_details = zone_data.get("handle_details") or {}
        for dkey in (name, name_under):
            if dkey in handle_details:
                return zone_name, dkey, handle_details[dkey]

    # Prefix fallback
    for zone_name, zone_data in zones.items():
        if not hasattr(zone_data, "get"):
            continue
        handle_details = zone_data.get("handle_details") or {}
        for dkey, htext in handle_details.items():
            if dkey.startswith(name) or dkey.startswith(name_under):
                return zone_name, dkey, htext

    return None, None, None


# ---------------------------------------------------------------------------
# CmdHandle
# ---------------------------------------------------------------------------

class CmdHandle(Command):
    """
    Interact intimately with an object described as a zone detail.

    Usage:
      handle <detail>

    Plays a private emote sequence. What others see is a brief, tasteful version.
    The detail must have handle text set by a Builder with:
      roomzone handle <zone>/<detail> = <text>

    Example:
      handle center_wolf
      handle figurine
    """

    key = "handle"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("|xYou aren't in a room.|n"); return

        target = self.args.strip()
        if not target:
            caller.msg("|xHandle what? Usage: |whandle <detail>|n"); return

        zone_name, dkey, handle_text = _get_handle_text(room, target)

        if handle_text is None:
            # Check if the detail exists at all, to give a better error
            zn, dk, _ = _find_detail_in_zones(room, target)
            if zn:
                caller.msg(
                    f"|xYou examine {dk} but find nothing compelling enough "
                    f"to act on. (No handle text set.)|n"
                )
            else:
                caller.msg(f"|xYou don't see '{target}' here.|n")
            return

        char_name = caller.db.rp_name or caller.name

        # Show the full intimate sequence to the caller only
        caller.msg(handle_text)

        # Show a brief, discreet version to the room
        room.msg_contents(
            f"|x{char_name} pauses at something on display, "
            f"reaches out — and then thinks better of it, withdrawing "
            f"their hand with the careful composure of someone who was "
            f"absolutely not just doing what it looked like.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# CmdStudy
# ---------------------------------------------------------------------------

class CmdStudy(Command):
    """
    Study a zone carefully and glean a random observation.

    Usage:
      study <zone>

    Each time you study, you may notice something different. Details are
    set by Builders with:
      roomzone study <zone> + <observation text>

    Example:
      study portrait
      study west
    """

    key = "study"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("|xYou aren't in a room.|n"); return

        target = self.args.strip().lower()
        if not target:
            caller.msg("|xStudy what? Usage: |wstudy <zone>|n"); return

        zones = room.db.zones or {}
        target_under = target.replace(" ", "_")

        # Find zone
        zone_name = None
        zone_data = None
        for candidate in (target, target_under):
            if candidate in zones:
                zone_name = candidate
                zone_data = zones[candidate]
                break

        if zone_name is None:
            # Prefix fallback
            for zname, zdata in zones.items():
                if zname.startswith(target) or zname.startswith(target_under):
                    zone_name = zname
                    zone_data = zdata
                    break

        if zone_name is None or not hasattr(zone_data, "get"):
            caller.msg(f"|xYou don't see '{target}' here to study.|n"); return

        study_details = zone_data.get("study_details") or []
        if not study_details:
            caller.msg(
                f"|xYou study {zone_name} carefully but nothing new catches your attention.|n"
            ); return

        observation = random.choice(study_details)
        caller.msg(observation)

        char_name = caller.db.rp_name or caller.name
        room.msg_contents(
            f"|x{char_name} pauses, studying {zone_name} with quiet attention.|n",
            exclude=caller,
        )


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_INTERACT_CMDS = [CmdHandle, CmdStudy]
