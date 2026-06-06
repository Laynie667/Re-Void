"""
commands/realm_commands.py

Staff tooling to designate which realm a room belongs to, and (only as an
override) which sub-faction owns a specific room. Phase 1 of the factions/realms
system — see world/FACTIONS_REALMS_DESIGN.md.
"""

from evennia.commands.default.muxcommand import MuxCommand

_LOCK = "cmd:perm(Builder)"


class CmdDesignate(MuxCommand):
    """
    Designate a room's realm affiliation and (override) faction ownership.

    Usage:
        designate                          — show this room's realm/faction
        designate realm <key>              — set this room's realm
        designate realm <key>/connected    — flood-fill the realm across connected exits
        designate faction <key>            — set a sub-faction override on THIS room
        designate faction none             — clear the override (revert to realm's owner)
        designate realms                   — list known realms
        designate factions                 — list known factions

    The realm carries its owning faction automatically; only set a faction override
    when a sub-faction holds this specific room. Flood-fill stamps every room reachable
    by exits (stopping at rooms already in a different realm, capped for safety).
    """

    key = "designate"
    aliases = ["realmstamp"]
    locks = _LOCK
    help_category = "Building"

    def func(self):
        from world.realms import (REALMS, FACTIONS, get_realm, get_faction,
                                   stamp_room, realm_name, faction_name)
        caller = self.caller
        room = caller.location
        args = (self.args or "").strip()

        if not args or args.lower() == "here":
            if not room:
                caller.msg("|xYou're nowhere.|n")
                return
            self._show(caller, room)
            return

        low = args.lower()
        if low == "realms":
            caller.msg("|wKnown realms:|n\n" + "\n".join(
                f"  |w{k}|n — {v['name']}  |x(faction: {v.get('faction')})|n"
                for k, v in REALMS.items()))
            return
        if low == "factions":
            caller.msg("|wKnown factions:|n\n" + "\n".join(
                f"  |w{k}|n — {v['name']}  |x({v.get('kind')}"
                f"{', sub of ' + v['parent'] if v.get('parent') else ''})|n"
                for k, v in FACTIONS.items()))
            return

        if not room:
            caller.msg("|xYou need to be in a room.|n")
            return

        parts = args.split()
        sub = parts[0].lower()
        rest = " ".join(parts[1:]).strip()

        if sub == "realm":
            connected = False
            key = rest
            if "/" in rest:
                key, sw = rest.split("/", 1)
                key = key.strip()
                connected = sw.strip().lower() in ("connected", "flood", "all")
            key = key.lower()
            if not get_realm(key):
                caller.msg(f"|xNo realm '{key}'. Try: designate realms|n")
                return
            if connected:
                n, capped = self._flood(room, key)
                note = "  |r(hit the flood cap — run again from an unstamped edge if needed)|n" if capped else ""
                caller.msg(f"|gStamped |w{n}|g connected room(s) into realm "
                           f"|w{realm_name(key)}|g.|n{note}")
            else:
                stamp_room(room, realm=key)
                caller.msg(f"|gThis room is now in realm |w{realm_name(key)}|g.|n")
            self._show(caller, room)
            return

        if sub == "faction":
            key = rest.lower()
            if key in ("none", "clear", ""):
                stamp_room(room, faction="")
                caller.msg("|gFaction override cleared — this room reverts to its realm's owner.|n")
            elif not get_faction(key):
                caller.msg(f"|xNo faction '{key}'. Try: designate factions|n")
                return
            else:
                stamp_room(room, faction=key)
                caller.msg(f"|gThis room's owner is now |w{faction_name(key)}|g (override).|n")
            self._show(caller, room)
            return

        caller.msg("|xUsage: designate realm <key>[/connected] | faction <key|none> "
                   "| realms | factions|n")

    def _show(self, caller, room):
        from world.realms import room_realm, room_faction, realm_name, faction_name
        rk, fk = room_realm(room), room_faction(room)
        override = getattr(room.db, "faction", None)
        src = "" if override else " — inherited from realm"
        caller.msg(
            f"|w{room.key}|n\n"
            f"  |xrealm:|n |w{realm_name(rk)}|n |x({rk})|n\n"
            f"  |xfaction:|n |w{faction_name(fk)}|n |x({fk}{src})|n"
        )

    def _flood(self, start, realm_key):
        """BFS over exits, stamping each reachable room into realm_key. Stops at rooms
        already explicitly in a DIFFERENT realm (boundaries) and at FLOOD_CAP. Returns
        (count, capped)."""
        from world.realms import stamp_room, FLOOD_CAP
        try:
            from typeclasses.rooms import Room
        except Exception:
            Room = None
        seen = set()
        queue = [start]
        count = 0
        capped = False
        while queue:
            rm = queue.pop()
            if rm.id in seen:
                continue
            seen.add(rm.id)
            existing = getattr(rm.db, "realm", None)
            # Don't cross an existing boundary (a room already set to another realm).
            if existing and existing != realm_key and rm is not start:
                continue
            stamp_room(rm, realm=realm_key)
            count += 1
            if count >= FLOOD_CAP:
                capped = True
                break
            for ex in rm.exits:
                dest = getattr(ex, "destination", None)
                if not dest or dest.id in seen:
                    continue
                if Room and not dest.is_typeclass(Room, exact=False):
                    continue
                queue.append(dest)
        return count, capped


class CmdRealmHere(MuxCommand):
    """
    Show the realm and faction of your current room (read-only, any player).

    Usage:
        realmhere
    """

    key = "realmhere"
    aliases = ["whererealm"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.realms import (room_realm, room_faction, realm_name, faction_name,
                                   get_realm)
        room = self.caller.location
        if not room:
            self.caller.msg("|xYou're nowhere.|n")
            return
        rk, fk = room_realm(room), room_faction(room)
        r = get_realm(rk)
        blurb = f"\n  |x{r['blurb']}|n" if r and r.get("blurb") else ""
        self.caller.msg(
            f"|wYou are in |w{realm_name(rk)}|n, held by |w{faction_name(fk)}|n.|n{blurb}"
        )


class CmdRealmOwner(MuxCommand):
    """
    View or reassign which faction OWNS a realm — control shifts over time.

    Usage:
        realmowner                          — list realms and their current owners
        realmowner <realm> = <faction>      — reassign the realm's owning faction
        realmowner <realm> = default        — revert to the seeded default

    The change is persistent (survives reload). Every room in the realm that hasn't a
    sub-faction override immediately reports the new owner.
    """

    key = "realmowner"
    aliases = ["realmown"]
    locks = _LOCK
    help_category = "Building"

    def func(self):
        from world.realms import REALMS, get_realm, get_faction, realm_owner, faction_name
        from world.realm_state import set_realm_owner, get_realm_owner_override
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            lines = ["|wRealm ownership:|n"]
            for rk, rv in REALMS.items():
                cur = realm_owner(rk)
                ov = get_realm_owner_override(rk)
                tag = " |Y(reassigned)|n" if ov else ""
                lines.append(f"  |w{rv['name']}|n |x({rk})|n → |c{faction_name(cur)}|n{tag}")
            caller.msg("\n".join(lines))
            return

        if "=" not in args:
            caller.msg("|xUsage: realmowner <realm> = <faction|default>|n")
            return
        realm_arg, fac_arg = [p.strip() for p in args.split("=", 1)]
        rk = (realm_arg or "").lower()
        if not get_realm(rk):
            caller.msg(f"|xNo realm '{realm_arg}'. Try: designate realms|n")
            return
        if fac_arg.lower() in ("default", "none", "revert", ""):
            set_realm_owner(rk, None)
            caller.msg(f"|g{REALMS[rk]['name']} reverted to its default owner: "
                       f"|c{faction_name(realm_owner(rk))}|g.|n")
            return
        if not get_faction(fac_arg):
            caller.msg(f"|xNo faction '{fac_arg}'. Try: designate factions|n")
            return
        set_realm_owner(rk, fac_arg.lower())
        caller.msg(f"|g{REALMS[rk]['name']} is now owned by |c{faction_name(fac_arg)}|g. "
                   f"|x(persistent)|n")


class CmdRealmCurrency(MuxCommand):
    """
    Set a realm's currency policy — the governing faction's call.

    Usage:
        realmcurrency <realm>                       — show the realm's currency config
        realmcurrency <realm> name = <text>         — name the realm's local currency
        realmcurrency <realm> shards = on|off       — accept outside shards, or not
        realmcurrency <realm> rate = <number>       — shards per 1 local unit (0 = no exchange)

    Local currency is sovereign by default (no exchange). Persistent. Allowed to the
    realm's owning-faction owner (or a Builder).
    """

    key = "realmcurrency"
    aliases = ["realmcur"]
    locks = _LOCK
    help_category = "Building"

    def func(self):
        from world.realms import get_realm, realm_config, realm_owner, realm_name
        from world.realm_state import set_realm_currency
        from world.factions import is_owner
        caller = self.caller
        args = (self.args or "").strip()
        parts = args.split(None, 1)
        if not parts:
            caller.msg("|xUsage: realmcurrency <realm> [name=.. | shards=on/off | rate=N]|n")
            return
        rk = parts[0].lower()
        if not get_realm(rk):
            caller.msg(f"|xNo realm '{parts[0]}'. Try: designate realms|n")
            return
        cfg = realm_config(rk)
        if len(parts) == 1 or "=" not in parts[1]:
            caller.msg(f"|w{realm_name(rk)} currency|n\n"
                       f"  |xlocal:|n {cfg.get('currency_name') or cfg.get('local_currency') or '—'}"
                       f"   |xaccepts shards:|n {cfg.get('accepts_shards', True)}"
                       f"   |xexchange rate:|n {cfg.get('exchange_rate', 0)}")
            return
        # authority: the realm's owning faction's owner (or a builder)
        if not (is_owner(caller, realm_owner(rk)) or caller.check_permstring("Builder")):
            caller.msg(f"|xOnly {realm_name(rk)}'s owning faction may set its currency.|n")
            return
        field, value = [p.strip() for p in parts[1].split("=", 1)]
        field = field.lower()
        if field == "name":
            set_realm_currency(rk, currency_name=value or None)
            caller.msg(f"|g{realm_name(rk)}'s local currency is now '|w{value}|g'.|n")
        elif field == "shards":
            on = value.lower() in ("on", "yes", "true", "1", "accept")
            set_realm_currency(rk, accepts_shards=on)
            caller.msg(f"|g{realm_name(rk)} {'accepts' if on else 'refuses'} outside shards.|n")
        elif field == "rate":
            try:
                rate = float(value)
            except ValueError:
                caller.msg("|xRate must be a number (0 = no exchange).|n")
                return
            set_realm_currency(rk, exchange_rate=rate)
            caller.msg(f"|g{realm_name(rk)} exchange rate set: |w{rate}|g shards per local unit"
                       f"{' (no exchange)' if rate == 0 else ''}.|n")
        else:
            caller.msg("|xField must be name, shards, or rate.|n")


ALL_REALM_CMDS = [CmdDesignate, CmdRealmHere, CmdRealmOwner, CmdRealmCurrency]
