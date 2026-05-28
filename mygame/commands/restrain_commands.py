"""
commands/restrain_commands.py

Commands for zone-level restraint mechanics.

    restrain <person> to <zone>   — secure a character to a restraint zone
    release <person>              — release a restrained character (restrainer / Builder)
    release                       — attempt to self-release (only if restrainer absent)

The zone must have a 'restrain' mechanic installed
(typeclasses.restrain_mechanic.RestrainMechanic).

The target must have 'restraint' in their consent_flags to be restrained.
"""

from evennia import Command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_restrain(room, zone_name, zone_data, restrain_copy):
    """Write updated restrain data back through a full dict copy for DB persistence."""
    zones = room.db.zones or {}
    mech  = dict((zone_data.get("mechanics") or {}))
    mech["restrain"] = restrain_copy
    zc = dict(zone_data) if hasattr(zone_data, "items") else {}
    zc["mechanics"] = mech
    zs = dict(zones)
    zs[zone_name] = zc
    room.db.zones = zs


def _fuzzy_restrain_zone(room, name):
    """
    Find a zone with a 'restrain' mechanic by fuzzy name.
    Returns (zone_name, zone_data, restrain_dict) or (None, None, None).
    """
    zones      = room.db.zones or {}
    name_clean = name.strip().lower()
    name_under = name_clean.replace(" ", "_")

    def _ok(zdata):
        if not hasattr(zdata, "get"):
            return False
        return bool((zdata.get("mechanics") or {}).get("restrain"))

    for candidate in (name_clean, name_under):
        if candidate in zones and _ok(zones[candidate]):
            zd = zones[candidate]
            return candidate, zd, zd["mechanics"]["restrain"]

    for zname, zdata in zones.items():
        if not _ok(zdata):
            continue
        if name_clean in zname or name_under in zname:
            return zname, zdata, zdata["mechanics"]["restrain"]

    return None, None, None


def _do_release(char, room=None, silent=False):
    """
    Release char from their zone restraint.
    Clears zone_restrained_at and removes from zone's restrained list.
    Returns True if released, False if char was not restrained.
    """
    val = getattr(char.db, "zone_restrained_at", None)
    if not val:
        return False

    char.db.zone_restrained_at = None
    char_id   = char.id
    char_name = char.db.rp_name or char.name

    try:
        from evennia import search_object
        rid, zone_name, _ = val
        if room is None:
            results = search_object(f"#{rid}")
            room    = results[0] if results else None
        if room:
            zones = room.db.zones or {}
            if zone_name in zones:
                zone = zones[zone_name]
                r    = (zone.get("mechanics") or {}).get("restrain")
                if r:
                    label      = r.get("label", zone_name)
                    restrained = [e for e in r.get("restrained", [])
                                  if e[0] != char_id]
                    rc = dict(r)
                    rc["restrained"] = restrained
                    _write_restrain(room, zone_name, zone, rc)
                    if not silent:
                        char.msg(f"|wYou are released from {label}.|n")
                        room.msg_contents(
                            f"|x{char_name} is released from {label}.|n",
                            exclude=char,
                        )
                    return True
    except Exception:
        pass

    if not silent:
        char.msg("|wYou pull free.|n")
    return True


# ---------------------------------------------------------------------------
# CmdRestrain
# ---------------------------------------------------------------------------

class CmdRestrain(Command):
    """
    Secure a character to a zone's restraint anchor point.

    Usage:
      restrain <person> to <zone>
      restrain <person> in <zone>

    The zone must have a restraint mechanic installed.
    The target must have restraint consent enabled in their settings.

    Example:
      restrain Auria to center
      restrain Laynie in cables
    """

    key   = "restrain"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        args = self.args.strip()
        if not args:
            caller.msg("|xUsage: |wrestrain <person> to <zone>|n")
            return

        zone_arg    = None
        target_name = args
        for sep in (" to ", " in "):
            if sep in args.lower():
                idx         = args.lower().index(sep)
                target_name = args[:idx].strip()
                zone_arg    = args[idx + len(sep):].strip()
                break

        if not zone_arg:
            caller.msg("|xUsage: |wrestrain <person> to <zone>|n")
            return

        # Locate target
        target = caller.search(target_name, location=room)
        if not target:
            return

        if target == caller:
            caller.msg("|xYou can't restrain yourself this way.|n")
            return

        # Consent / block check
        from typeclasses.characters import Character
        if isinstance(target, Character):
            block_list = target.db.block_list or set()
            if caller.id in block_list:
                caller.msg("|xYou can't interact with that person.|n")
                return
            consent_flags = target.db.consent_flags or {}
            if not consent_flags.get("restraint"):
                tgt_name = target.db.rp_name or target.name
                caller.msg(
                    f"|x{tgt_name} hasn't enabled restraint consent.|n"
                )
                return

        # Already restrained?
        if getattr(target.db, "zone_restrained_at", None):
            tgt_name = target.db.rp_name or target.name
            caller.msg(f"|x{tgt_name} is already restrained.|n")
            return

        # Find zone
        zone_name, zone_data, restrain = _fuzzy_restrain_zone(room, zone_arg)
        if zone_name is None:
            caller.msg(
                f"|xThere's no restraint point at '{zone_arg}' here.|n"
            )
            return

        restrained = list(restrain.get("restrained", []))
        capacity   = restrain.get("capacity", 1)
        label      = restrain.get("label", zone_name)

        if len(restrained) >= capacity:
            caller.msg(f"|x{label.capitalize()} is already at capacity.|n")
            return

        # Apply
        char_name = caller.db.rp_name or caller.name
        tgt_name  = target.db.rp_name or target.name

        restrained.append((target.id, tgt_name, caller.id))
        rc = dict(restrain)
        rc["restrained"] = restrained
        _write_restrain(room, zone_name, zone_data, rc)
        target.db.zone_restrained_at = (room.id, zone_name, caller.id)

        target.msg(f"|m{char_name} secures you to {label}.|n")
        caller.msg(f"|wYou secure {tgt_name} to {label}.|n")
        room.msg_contents(
            f"|x{char_name} secures {tgt_name} to {label}.|n",
            exclude=[caller, target],
        )


# ---------------------------------------------------------------------------
# CmdRelease
# ---------------------------------------------------------------------------

class CmdRelease(Command):
    """
    Release a restrained character from their restraint point.

    Usage:
      release <person>    — release someone else (must be their restrainer or a Builder)
      release             — attempt to free yourself (only works if restrainer is absent)

    Example:
      release Auria
      release
    """

    key   = "release"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        room   = caller.location
        args   = self.args.strip()

        # No args — try to self-release
        if not args:
            val = getattr(caller.db, "zone_restrained_at", None)
            if not val:
                caller.msg("|xYou aren't restrained.|n")
                return

            _, _, restrainer_id = val

            # Check if restrainer is still in the room
            if restrainer_id and room:
                for obj in room.contents:
                    if hasattr(obj, "id") and obj.id == restrainer_id:
                        if not caller.check_permstring("Builder"):
                            caller.msg(
                                "|xYou struggle, but the restraints hold.|n"
                            )
                            return
                        break

            _do_release(caller, room)
            return

        # Named target
        if not room:
            caller.msg("|xYou aren't anywhere.|n")
            return

        target = caller.search(args, location=room)
        if not target:
            return

        val = getattr(target.db, "zone_restrained_at", None)
        if not val:
            tgt_name = target.db.rp_name or target.name
            caller.msg(f"|x{tgt_name} isn't restrained.|n")
            return

        _, _, restrainer_id = val
        is_restrainer = (restrainer_id == caller.id)
        is_builder    = caller.check_permstring("Builder")

        if not (is_restrainer or is_builder):
            caller.msg("|xYou didn't secure them — you can't release them.|n")
            return

        _do_release(target, room)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

ALL_RESTRAIN_CMDS = [CmdRestrain, CmdRelease]
