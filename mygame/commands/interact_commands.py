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

    # Pass 2: substring — "wolf" finds "center_wolf"
    for zone_name, zone_data in zones.items():
        if not hasattr(zone_data, "get"):
            continue
        details = zone_data.get("details") or {}
        for dkey, dtext in details.items():
            if name in dkey or name_under in dkey:
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

    # Substring fallback — "wolf" finds "center_wolf"
    for zone_name, zone_data in zones.items():
        if not hasattr(zone_data, "get"):
            continue
        handle_details = zone_data.get("handle_details") or {}
        for dkey, htext in handle_details.items():
            if name in dkey or name_under in dkey:
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

        # Fire any set_attr trigger attached to this detail
        # Builders add triggers via @py on the zone mechanics dict:
        #   zone['mechanics']['triggers'] = {
        #       'detail_key': {
        #           'type':       'set_attr',
        #           'attr':       'has_found_lab',   # attribute name
        #           'value':      1,
        #           'msg_caller': '|x...|n',          # shown to caller (optional)
        #           'msg_room':   '|x...|n',           # shown to room (optional)
        #           'once':       True,               # only fires once per character
        #       }
        #   }
        zones     = room.db.zones or {}
        zone_data = zones.get(zone_name) if zone_name else None
        if zone_data and hasattr(zone_data, "get"):
            triggers = (zone_data.get("mechanics") or {}).get("triggers") or {}
            trig = triggers.get(dkey)
            # reveal_item — handling this detail uncovers a stashed object (e.g. a
            # cursed piercing hidden under a chair), delivers it to the finder, and
            # — if it carries binding_effects — lets the curse bite on contact.
            if trig and trig.get("type") == "reveal_item":
                attr_name = trig.get("attr", f"found_{dkey}")
                already = caller.attributes.get(attr_name)
                if already and trig.get("once", True):
                    empty = trig.get("msg_empty",
                                     "|xThere's nothing else hidden there. Your fingers find "
                                     "only the cold underside of the seat.|n")
                    caller.msg(empty)
                else:
                    from evennia import search_object
                    obj = None
                    ref = trig.get("item_dbref")
                    if ref:
                        res = search_object(ref)
                        obj = res[0] if res else None
                    if obj:
                        try:
                            obj.move_to(caller, quiet=True, move_hooks=False)
                        except Exception:
                            obj.location = caller
                        caller.attributes.add(attr_name, True)
                        rmsg = trig.get("msg_room")
                        if rmsg:
                            room.msg_contents(rmsg.format(actor=char_name), exclude=caller)
                        # Let the cursed thing apply itself on contact.
                        if trig.get("apply_on_contact", True):
                            try:
                                from world.binding_effects import apply_effects
                                apply_effects(caller, obj)
                            except Exception:
                                pass
                    else:
                        caller.msg("|xYour fingers close on nothing — whatever was there is "
                                   "gone.|n")
                return
            if trig and trig.get("type") == "set_attr":
                attr_name = trig.get("attr")
                attr_val  = trig.get("value", 1)
                if attr_name:
                    already = caller.attributes.get(attr_name)
                    if not already or not trig.get("once", True):
                        caller.attributes.add(attr_name, attr_val)
                        trig_msg = trig.get("msg_caller", "")
                        if trig_msg:
                            caller.msg(trig_msg)
                        trig_room = trig.get("msg_room", "")
                        if trig_room:
                            room.msg_contents(trig_room, exclude=caller)

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

        study_details = list(zone_data.get("study_details") or [])
        inscriptions  = list(zone_data.get("inscriptions") or [])
        pool = study_details + inscriptions

        if not pool:
            caller.msg(
                f"|xYou study {zone_name} carefully but nothing new catches your attention.|n"
            ); return

        observation = random.choice(pool)
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
