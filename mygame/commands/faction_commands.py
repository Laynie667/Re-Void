"""
commands/faction_commands.py

The `faction` command suite (Phase 4b) — membership, ranks, residency, roster, and
info, all gated by the authority rules in world/factions.py.

Scope note: faction *definitions* (rank-ladder names, currency, relations) live in the
code registry (world/realms.FACTIONS) and are read-only at runtime here. Per-character
membership / rank / residency are persistent on the character and fully managed by these
commands. Owner-editable definitions + player-created factions need the persistent
faction store (next step) — this suite covers everything that rides on character state.
"""

from evennia.commands.default.muxcommand import MuxCommand


def _resolve_faction_key(caller, given):
    """A faction key from an explicit arg, else the caller's current room's faction."""
    from world.factions import _key
    if given:
        return _key(given)
    try:
        from world.realms import room_faction
        return room_faction(caller.location) if caller.location else None
    except Exception:
        return None


class CmdFaction(MuxCommand):
    """
    Factions — your standing, rank, and (with authority) managing members.

    Usage:
        faction                              — your factions, ranks, and residencies
        faction info [<key>]                 — a faction's public details
        faction roster <key>                 — list known members + ranks
        faction invite <player> [= <key>]    — grant membership (authority required)
        faction kick <player> [= <key>]      — remove membership (authority required)
        faction promote <player> [= <key>]   — raise a member one rank (authority required)
        faction demote <player> [= <key>]    — lower a member one rank (authority required)
        faction resident <player> = <realm>  — grant realm residency (authority required)
        faction evict <player> = <realm>     — remove realm residency (authority required)
        faction setrank <key> = A, B, C      — owner: name the rank ladder (low → high)

    Authority: you may move someone to any rank strictly below your own; a faction's
    owner (and a parent faction's owner, over an affiliated sub) may move across the
    whole ladder. Rep-driven factions (like the Facility) derive rank from standing —
    promote/demote there is automatic, not manual.
    """

    key = "faction"
    aliases = ["factions", "guild"]
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            return self._mine(caller)

        parts = args.split(None, 1)
        sub = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "info":
            return self._info(caller, rest)
        if sub == "roster":
            return self._roster(caller, rest)
        if sub in ("invite", "kick", "promote", "demote", "resident", "evict"):
            return self._manage(caller, sub, rest)
        if sub == "setrank":
            return self._setrank(caller, rest)
        if sub in ("befriend", "enemy", "subsidiary", "unrelate"):
            return self._relate(caller, sub, rest)

        caller.msg("|xUsage: faction [info|roster|invite|kick|promote|demote|resident|evict|"
                   "setrank|befriend|enemy|subsidiary|unrelate] …|n")

    def _relate(self, caller, sub, rest):
        """faction befriend|enemy|subsidiary|unrelate <other> [= <key>] — owner manages relations."""
        from world.factions import _key, is_owner
        from world.realms import get_faction, faction_name
        from world.realm_state import set_relation
        if "=" in rest:
            other_arg, key_arg = [p.strip() for p in rest.split("=", 1)]
        else:
            other_arg, key_arg = rest.strip(), ""
        k = _resolve_faction_key(caller, key_arg)
        other = _key(other_arg)
        if not get_faction(k) or not get_faction(other):
            caller.msg("|xUsage: faction befriend|enemy|subsidiary|unrelate <faction> = <yourfaction>|n")
            return
        if not (is_owner(caller, k) or caller.check_permstring("Builder")):
            caller.msg(f"|xOnly {faction_name(k)}'s owner may set its relations.|n")
            return
        kind = {"befriend": "friends", "enemy": "enemies", "subsidiary": "subsidiaries"}.get(sub)
        if sub == "unrelate":
            for kd in ("friends", "enemies", "subsidiaries"):
                set_relation(k, kd, other, add=False)
            caller.msg(f"|g{faction_name(k)} now regards {faction_name(other)} as neutral.|n")
            return
        set_relation(k, kind, other, add=True)
        caller.msg(f"|g{faction_name(k)} now regards {faction_name(other)} as "
                   f"{sub if sub != 'befriend' else 'a friend'}.|n")

    def _setrank(self, caller, rest):
        """faction setrank <key> = Name1, Name2, ... — owner sets the rank-name ladder."""
        from world.factions import _key, is_owner, ranks, advance_method
        from world.realms import get_faction, faction_name
        from world.realm_state import set_rank_names
        if "=" not in rest:
            caller.msg("|xUsage: faction setrank <key> = Rank1, Rank2, Rank3 "
                       "(low → high; 'default' to reset)|n")
            return
        key_arg, names_arg = [p.strip() for p in rest.split("=", 1)]
        k = _key(key_arg)
        if not get_faction(k):
            caller.msg(f"|xNo faction '{key_arg}'. Try: designate factions|n")
            return
        if not (is_owner(caller, k) or caller.check_permstring("Builder")):
            caller.msg(f"|xOnly {faction_name(k)}'s owner may rename its ranks.|n")
            return
        if names_arg.lower() in ("default", "reset", "none", ""):
            set_rank_names(k, None)
            caller.msg(f"|g{faction_name(k)} rank ladder reset to default.|n")
            return
        names = [n.strip() for n in names_arg.split(",") if n.strip()]
        if not names:
            caller.msg("|xGive at least one rank name.|n")
            return
        # Rep-driven ladders (e.g. the Facility) must keep their tier count so grade
        # thresholds still line up — renaming only, not resizing.
        base = list((get_faction(k) or {}).get("ranks", []))
        if advance_method(k) == "rep" and base and len(names) != len(base):
            caller.msg(f"|x{faction_name(k)} is rep-driven: give exactly {len(base)} names "
                       f"(rename only — resizing would break its grade thresholds).|n")
            return
        set_rank_names(k, names)
        caller.msg(f"|g{faction_name(k)} ranks set: |c{' → '.join(ranks(k)[i]['name'] for i in range(len(ranks(k))))}|g.|n")

    # ── read-only ────────────────────────────────────────────────────────────
    def _mine(self, caller):
        from world.factions import (rank_name, get_standing, is_member, _key)
        from world.realms import FACTIONS, faction_name
        mem = list(getattr(caller.db, "faction_member", None) or [])
        res = list(getattr(caller.db, "residency", None) or [])
        facs = dict(getattr(caller.db, "factions", None) or {})
        lines = ["|w" + "═" * 44 + "|n", "|wYOUR STANDING|n", "|w" + "═" * 44 + "|n"]
        if not facs and not mem and not res:
            lines.append("  |xNo faction ties or residencies yet.|n")
        for skey, rep in facs.items():
            k = _key(skey)
            nm = faction_name(k) if k else skey
            rk = rank_name(caller, k) if k else ""
            star = " |Y★member|n" if (k and is_member(caller, k)) else ""
            grade = f" — |Y{rk}|n" if rk else ""
            lines.append(f"  |c{nm}|n: {int(rep)}{grade}{star}")
        if res:
            lines.append("  |x── residencies ──|n")
            from world.realms import realm_name
            for rk in res:
                lines.append(f"  |grealm:|n {realm_name(rk)}")
        lines.append("|w" + "═" * 44 + "|n")
        caller.msg("\n".join(lines))

    def _info(self, caller, key_arg):
        from world.realms import get_faction, REALMS, realm_name
        from world.factions import _key, friends_of, enemies_of, subsidiaries_of, ranks
        k = _key(key_arg) or _resolve_faction_key(caller, None)
        f = get_faction(k)
        if not f:
            caller.msg("|xNo such faction. Try: designate factions|n")
            return
        col = f.get("colour", "|w")
        rks = ranks(k)
        ladder = " → ".join(r.get("name", "?") for r in rks) if rks else "(no ranks — neutral)"
        realm_here = next((rk for rk, rv in REALMS.items() if rv.get("faction") == k), None)
        lines = [
            f"{col}{f['name']}|n  |x({k} · {f.get('kind')}"
            f"{', sub of ' + f['parent'] if f.get('parent') else ''})|n",
            f"  |xowner:|n {f.get('owner') or '—'}   |xcurrency:|n {f.get('currency')}"
            f"   |xadvance:|n {f.get('advance')}",
            f"  |xrealm:|n {realm_name(realm_here) if realm_here else '—'}",
            f"  |xranks:|n {ladder}",
            f"  |xfriends:|n {', '.join(friends_of(k)) or '—'}",
            f"  |xenemies:|n {', '.join(enemies_of(k)) or '—'}",
            f"  |xsubsidiaries:|n {', '.join(subsidiaries_of(k)) or '—'}",
        ]
        if f.get("blurb"):
            lines.append(f"  |x{f['blurb']}|n")
        caller.msg("\n".join(lines))

    def _roster(self, caller, key_arg):
        from world.factions import _key, rank_name, get_rank_index
        from world.realms import faction_name
        k = _key(key_arg)
        if not k:
            caller.msg("|xUsage: faction roster <key>|n")
            return
        try:
            from typeclasses.characters import Character
            members = [o for o in Character.objects.all()
                       if k in (getattr(o.db, "faction_member", None) or [])]
        except Exception:
            members = []
        if not members:
            caller.msg(f"|x{faction_name(k)} has no recorded members.|n")
            return
        lines = [f"|w{faction_name(k)} — roster|n"]
        for m in sorted(members, key=lambda o: -get_rank_index(o, k)):
            lines.append(f"  |c{m.db.rp_name or m.key}|n — {rank_name(m, k) or 'member'}")
        caller.msg("\n".join(lines))

    # ── management (authority-gated) ──────────────────────────────────────────
    def _manage(self, caller, sub, rest):
        from world.factions import (_key, can_grant, is_owner, join_faction, leave_faction,
                                    set_rank, get_rank_index, ranks, advance_method,
                                    add_resident, remove_resident, is_member)
        from world.realms import get_realm, faction_name, realm_name

        # parse "<player> = <key/realm>"
        if "=" in rest:
            who, tail = [p.strip() for p in rest.split("=", 1)]
        else:
            who, tail = rest.strip(), ""
        if not who:
            caller.msg(f"|xUsage: faction {sub} <player> [= <key>]|n")
            return
        target = caller.search(who, global_search=True)
        if not target:
            return

        # Residency grants operate on a REALM, not a faction.
        if sub in ("resident", "evict"):
            realm = (tail or "").lower()
            if not get_realm(realm):
                caller.msg("|xUsage: faction resident <player> = <realm>|n")
                return
            # authority: owner of the realm's faction (or its parent)
            from world.realms import get_realm as _gr
            rfac = _gr(realm).get("faction")
            if not (is_owner(caller, rfac) or caller.check_permstring("Builder")):
                caller.msg(f"|xYou don't have the authority to grant residency in "
                           f"{realm_name(realm)}.|n")
                return
            if sub == "resident":
                add_resident(target, realm)
                try:
                    from world.realms import apply_realm_title
                    apply_realm_title(target, realm)
                except Exception:
                    pass
                caller.msg(f"|g{target.db.rp_name or target.key} is now a resident of "
                           f"{realm_name(realm)}.|n")
                target.msg(f"|gYou've been granted residency in {realm_name(realm)}.|n")
            else:
                remove_resident(target, realm)
                caller.msg(f"|g{target.db.rp_name or target.key} is no longer a resident of "
                           f"{realm_name(realm)}.|n")
            return

        k = _resolve_faction_key(caller, tail)
        if not k:
            caller.msg("|xWhich faction? Use '= <key>', or stand in its territory.|n")
            return

        if sub == "invite":
            if not can_grant(caller, k, 0):
                caller.msg(f"|xYou lack the authority to induct into {faction_name(k)}.|n")
                return
            join_faction(target, k, 0)
            caller.msg(f"|g{target.db.rp_name or target.key} is inducted into {faction_name(k)}.|n")
            target.msg(f"|gYou've been inducted into {faction_name(k)}.|n")
            return

        if sub == "kick":
            if not (is_owner(caller, k) or get_rank_index(caller, k) > get_rank_index(target, k)):
                caller.msg("|xYou can only remove members below your own rank.|n")
                return
            leave_faction(target, k)
            caller.msg(f"|g{target.db.rp_name or target.key} is removed from {faction_name(k)}.|n")
            target.msg(f"|rYou've been removed from {faction_name(k)}.|n")
            return

        # promote / demote
        if advance_method(k) == "rep":
            caller.msg(f"|x{faction_name(k)} ranks are driven by standing, not granted — "
                       f"rank rises with rep, not by hand.|n")
            return
        if not is_member(target, k):
            caller.msg(f"|x{target.db.rp_name or target.key} isn't a member of {faction_name(k)}.|n")
            return
        cur = get_rank_index(target, k)
        new = cur + 1 if sub == "promote" else cur - 1
        new = max(0, min(new, len(ranks(k)) - 1))
        if new == cur:
            caller.msg("|xNo room to move them that way.|n")
            return
        if not can_grant(caller, k, new):
            caller.msg("|xThat rank isn't below your own — you can't grant it.|n")
            return
        set_rank(target, k, new)
        from world.factions import rank_name
        caller.msg(f"|g{target.db.rp_name or target.key} is now {rank_name(target, k)} "
                   f"in {faction_name(k)}.|n")
        target.msg(f"|YYou are now {rank_name(target, k)} in {faction_name(k)}.|n")


ALL_FACTION_CMDS = [CmdFaction]
