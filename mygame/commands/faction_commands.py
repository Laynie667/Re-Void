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
        faction befriend|enemy|subsidiary <other> = <key>  — owner: set relations
        faction create <key> = <Name>        — found your own faction (you become owner)
        faction disband <key>                — owner: dissolve a player-made faction
        faction about <key>                  — a faction's public page (portrait/about/notes/gallery)
        faction invites / accept <#> / decline <#>  — answer invitations
        faction setportrait/setabout <key> = …      — owner: page portrait / description
        faction note|gallery <key> add|del <…>      — owner: public notes / gallery

    Invites are consent-based: an authorised member offers, the recipient accepts. This
    lets someone take realm residency WITHOUT joining a faction (residency ≠ membership).
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
        if sub == "invites":
            return self._invites(caller)
        if sub in ("accept", "decline"):
            return self._respond(caller, sub, rest)
        if sub == "about":
            return self._about(caller, rest)
        if sub in ("setportrait", "setabout", "note", "gallery"):
            return self._meta(caller, sub, rest)
        if sub == "create":
            return self._create(caller, rest)
        if sub == "disband":
            return self._disband(caller, rest)
        if sub == "setrank":
            return self._setrank(caller, rest)
        if sub in ("befriend", "enemy", "subsidiary", "unrelate"):
            return self._relate(caller, sub, rest)

        caller.msg("|xfaction [info|about|roster|invites|accept|decline|invite|kick|promote|"
                   "demote|resident|evict|setrank|befriend|enemy|subsidiary|unrelate|setportrait|"
                   "setabout|note|gallery|create|disband] …|n")

    # ── consent invites (residency / membership) ──────────────────────────────
    def _offer(self, caller, target, rec):
        """Record a pending invite on the recipient and notify them; they accept/decline."""
        pend = list(getattr(target.db, "faction_invites", None) or [])
        # de-dupe identical pending offers
        if any(p.get("kind") == rec["kind"] and p.get("key") == rec["key"] for p in pend):
            caller.msg(f"|x{target.db.rp_name or target.key} already has that invite pending.|n")
            return
        pend.append(rec)
        target.db.faction_invites = pend
        what = "membership in" if rec["kind"] == "membership" else "residency in"
        caller.msg(f"|gInvitation sent: {what} |w{rec['name']}|g → "
                   f"{target.db.rp_name or target.key}.|n")
        target.msg(f"|Y✦ {rec['from']} invites you to {what} |w{rec['name']}|Y. "
                   f"|x(faction invites · faction accept <#> · faction decline <#>)|n")
        # leave an offline notice too, if the ogram model is available
        try:
            from web.mail.models import OgramMessage
            OgramMessage(
                sender_object_id=caller.id, sender_name=rec["from"],
                recipient_object_id=target.id, recipient_name=target.db.rp_name or target.key,
                msg_type="invite",
                body=(f"An invitation to {what} {rec['name']}. "
                      f"Use 'faction invites' then 'faction accept <#>' in-world."),
            ).save()
        except Exception:
            pass

    def _invites(self, caller):
        pend = list(getattr(caller.db, "faction_invites", None) or [])
        if not pend:
            caller.msg("|xNo pending invites.|n")
            return
        lines = ["|wPending invites:|n"]
        for i, p in enumerate(pend, 1):
            what = "membership in" if p.get("kind") == "membership" else "residency in"
            lines.append(f"  |w{i}.|n {what} |c{p.get('name')}|n  |x(from {p.get('from')})|n")
        lines.append("|xfaction accept <#>  ·  faction decline <#>|n")
        caller.msg("\n".join(lines))

    def _respond(self, caller, sub, rest):
        from world.factions import join_faction, add_resident
        from world.realms import apply_realm_title
        pend = list(getattr(caller.db, "faction_invites", None) or [])
        if not pend:
            caller.msg("|xNo pending invites.|n")
            return
        try:
            idx = int(rest.strip()) - 1
        except ValueError:
            idx = 0 if len(pend) == 1 else -1
        if not (0 <= idx < len(pend)):
            caller.msg("|xWhich invite? See: faction invites|n")
            return
        rec = pend.pop(idx)
        caller.db.faction_invites = pend
        if sub == "decline":
            caller.msg(f"|xYou decline the invitation to {rec.get('name')}.|n")
            return
        if rec["kind"] == "membership":
            join_faction(caller, rec["key"], 0)
            caller.msg(f"|gYou accept — you're now a member of |w{rec['name']}|g.|n")
        else:
            add_resident(caller, rec["key"])
            try:
                apply_realm_title(caller, rec["key"])
            except Exception:
                pass
            caller.msg(f"|gYou accept — you're now a resident of |w{rec['name']}|g.|n")

    def _about(self, caller, key_arg):
        """Browsable faction page: portrait ref, about text, notes, gallery captions."""
        from world.factions import _key
        from world.realms import get_faction, faction_name
        from world.realm_state import get_faction_meta
        k = _key(key_arg) or _resolve_faction_key(caller, None)
        f = get_faction(k)
        if not f:
            caller.msg("|xNo such faction. Try: designate factions|n")
            return
        meta = get_faction_meta(k)
        col = f.get("colour", "|w")
        lines = [f"{col}{f['name']}|n  |x({k})|n"]
        if meta.get("portrait"):
            lines.append(f"  |xportrait:|n {meta['portrait']}")
        about = meta.get("about") or f.get("blurb") or "|x(no description set)|n"
        lines.append(f"  {about}")
        notes = meta.get("notes") or []
        if notes:
            lines.append("  |x── notes ──|n")
            for n in notes[-10:]:
                lines.append(f"  • {n}")
        gallery = meta.get("gallery") or []
        if gallery:
            lines.append(f"  |x── gallery ({len(gallery)}) ──|n")
            for g in gallery[-10:]:
                lines.append(f"  ◦ {g}")
        caller.msg("\n".join(lines))

    def _meta(self, caller, sub, rest):
        """Owner-editable faction metadata: setportrait, setabout, note add/del, gallery add/del."""
        from world.factions import _key, is_owner
        from world.realms import get_faction, faction_name
        from world.realm_state import (set_faction_meta, add_faction_list_item,
                                       remove_faction_list_item)
        if "=" in rest:
            key_arg, value = [p.strip() for p in rest.split("=", 1)]
        else:
            key_arg, value = rest.strip(), ""
        # for note/gallery the form is: faction note <key> add <text> / del <#>
        parts = key_arg.split(None, 1)
        k = _key(parts[0]) if parts else None
        if not get_faction(k):
            caller.msg(f"|xUsage: faction {sub} <key> = <value>  (or  faction note <key> add <text>)|n")
            return
        if not (is_owner(caller, k) or caller.check_permstring("Builder")):
            caller.msg(f"|xOnly {faction_name(k)}'s owner may edit its page.|n")
            return

        if sub == "setportrait":
            set_faction_meta(k, portrait=value or None)
            caller.msg(f"|g{faction_name(k)} portrait {'set' if value else 'cleared'}.|n")
            return
        if sub == "setabout":
            set_faction_meta(k, about=value or None)
            caller.msg(f"|g{faction_name(k)} description {'set' if value else 'cleared'}.|n")
            return
        # note / gallery: "<key> add <text>" or "<key> del <#>"
        op = (parts[1] if len(parts) > 1 else "").split(None, 1)
        action = op[0].lower() if op else ""
        payload = op[1].strip() if len(op) > 1 else ""
        field = "notes" if sub == "note" else "gallery"
        if action == "add" and payload:
            n = add_faction_list_item(k, field, payload)
            caller.msg(f"|g{faction_name(k)} {field}: added (#{n}).|n")
        elif action in ("del", "remove", "rm") and payload.isdigit():
            ok = remove_faction_list_item(k, field, int(payload) - 1)
            caller.msg(f"|g{field} #{payload} removed.|n" if ok else f"|xNo {field} #{payload}.|n")
        else:
            caller.msg(f"|xUsage: faction {sub} <key> add <text>   |   faction {sub} <key> del <#>|n")

    _CREATE_CAP = 3   # factions one player may own (anti-spam)

    def _create(self, caller, rest):
        """faction create <key> = <Display Name> — found a faction; you become its owner."""
        from world.realms import get_faction, all_factions
        from world.realm_state import create_faction, get_created_factions
        from world.factions import join_faction
        if "=" not in rest:
            caller.msg("|xUsage: faction create <key> = <Display Name>  "
                       "(key: one short word, letters/numbers)|n")
            return
        key_arg, name = [p.strip() for p in rest.split("=", 1)]
        key = key_arg.lower()
        if not key.isalnum() or len(key) < 2 or len(key) > 20:
            caller.msg("|xKey must be a single alphanumeric word, 2–20 chars.|n")
            return
        if get_faction(key):
            caller.msg(f"|xA faction keyed '{key}' already exists.|n")
            return
        if not name:
            caller.msg("|xGive it a display name.|n")
            return
        owned = sum(1 for v in get_created_factions().values() if v.get("owner_id") == caller.id)
        if owned >= self._CREATE_CAP and not caller.check_permstring("Builder"):
            caller.msg(f"|xYou already own {owned} factions (cap {self._CREATE_CAP}).|n")
            return
        create_faction(key, {
            "name": name, "kind": "guild", "parent": None, "colour": "|w",
            "invite_only": True, "currency": "shards",
            "owner": caller.db.rp_name or caller.key, "owner_id": caller.id,
            "advance": "granted", "standing_key": name,
            "ranks": [{"name": "Member", "rep": 0, "title": "Member"},
                      {"name": "Officer", "rep": 0, "title": "Officer"},
                      {"name": "Leader", "rep": 0, "title": "Leader"}],
            "relations": {"friends": [], "enemies": [], "subsidiaries": []},
            "blurb": "",
        })
        join_faction(caller, key, 2)   # owner seats at the top rank
        caller.msg(f"|g✦ You found |w{name}|g |x({key})|g and take its highest seat. "
                   f"Name its ranks with |wfaction setrank {key} = …|g.|n")

    def _disband(self, caller, rest):
        """faction disband <key> — the owner dissolves a player-created faction."""
        from world.realms import get_faction, faction_name, FACTIONS
        from world.realm_state import delete_created_faction
        from world.factions import _key, is_owner
        k = _key(rest.strip())
        if not get_faction(k):
            caller.msg("|xNo such faction.|n")
            return
        if k in FACTIONS:
            caller.msg("|xCore factions can't be disbanded.|n")
            return
        if not (is_owner(caller, k) or caller.check_permstring("Builder")):
            caller.msg("|xOnly the owner may disband it.|n")
            return
        nm = faction_name(k)
        delete_created_faction(k)
        caller.msg(f"|g{nm} is disbanded.|n")

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
                self._offer(caller, target, {"kind": "residency", "key": realm,
                                             "name": realm_name(realm),
                                             "from": caller.db.rp_name or caller.key})
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
            self._offer(caller, target, {"kind": "membership", "key": k,
                                         "name": faction_name(k),
                                         "from": caller.db.rp_name or caller.key})
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
