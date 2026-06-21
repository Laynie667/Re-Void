"""
commands/relationship_commands.py — the `relate` command (Layer 1 of the
authority stack). See world/relationships.py + CONSENT_RULES_CONTRACTS_DESIGN.md.

    relate                          — list your bonds + pending offers
    relate <who> = <bond>           — OFFER a bond (they must accept)
    relate/temp <who> = <bond> <dur>— offer a TEMP bond (e.g. 30m, 2h, 3d)
    relate/perm <who> = <bond>      — offer a permanent bond (the default)
    relate/accept <who>             — accept a pending offer
    relate/reject <who>             — refuse a pending offer
    relate/force <who> = <bond>     — OWNER imposes a family role or own/slave/pet
    relate/clear <who>              — dissolve the bond both ways

Bonds: a family role (mother father sire dam parent · daughter son get offspring
child · sister brother sibling), `lover`, or ownership (`own`/`slave`/`pet`).
Reciprocals are set automatically, gendered by the other person. lover and family
may coexist. Ownership offered here is CONSENSUAL (the target accepts); `relate/force`
is the owner-imposed path. The OOC floor reverts every forced/imposed bond.
"""

from evennia.commands.default.muxcommand import MuxCommand


def _parse_duration(text):
    """Parse a trailing duration token (30m / 2h / 3d / 90s) → seconds, or None.
    Returns (seconds_or_None, remainder_text)."""
    parts = (text or "").split()
    if not parts:
        return None, text
    tok = parts[-1].lower()
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if len(tok) >= 2 and tok[-1] in units and tok[:-1].isdigit():
        return int(tok[:-1]) * units[tok[-1]], " ".join(parts[:-1])
    return None, text


class CmdRelate(MuxCommand):
    """
    Set, accept, force, or dissolve a relationship with someone.

    Usage:
      relate                        — your bonds and any pending offers
      relate <who> = <role|lover>   — offer a bond (they must accept)
      relate/accept <who>           — accept their offer
      relate/reject <who>           — refuse their offer
      relate/force <who> = <role>   — (owner only) impose a family role
      relate/clear <who>            — dissolve the bond both ways

    Family roles: mother father sire dam parent / daughter son get offspring
    child / sister brother sibling. The reciprocal is set on the other person
    automatically, gendered by their pronouns. lover and family can stack.
    """
    key            = "relate"
    aliases        = ["relationship", "kin"]
    switch_options = ("accept", "reject", "force", "clear", "temp", "perm")
    locks          = "cmd:all()"
    help_category  = "Interaction"

    def func(self):
        caller = self.caller
        from world import relationships as rel

        # bare `relate` — list
        if not self.args and not self.switches:
            caller.msg(rel.describe(caller))
            return

        name = (self.lhs or self.args or "").strip()
        if not name:
            caller.msg("|xRelate to whom? See |whelp relate|x.|n")
            return
        target = caller.search(name, global_search=True)
        if not target:
            return
        if target is caller:
            caller.msg("|xYou can't form a bond with yourself.|n")
            return

        if "accept" in self.switches:
            rel.accept_relation(caller, target)
        elif "reject" in self.switches:
            rel.reject_relation(caller, target)
        elif "clear" in self.switches:
            rel.clear_relation(caller, target)
            caller.msg(f"|xBond with {target.db.rp_name or target.key} dissolved.|n")
        elif "force" in self.switches:
            role = (self.rhs or "").strip().lower()
            rel.force_relation(caller, target, role)
        else:
            # offer a bond (consensual) — own/slave/pet, lover, or a family role.
            # /temp <dur> makes it time-limited; /perm (or no switch) is permanent.
            import time
            spec = (self.rhs or "").strip().lower()
            expires_at = None
            if "temp" in self.switches:
                secs, spec = _parse_duration(spec)
                spec = spec.strip().lower()
                if not secs:
                    caller.msg("|xA temp bond needs a duration: "
                               "|wrelate/temp <who> = slave 2h|x (s/m/h/d).|n")
                    return
                expires_at = time.time() + secs
            if not spec:
                caller.msg("|xName the bond: |wrelate <who> = mother|x "
                           "(or lover, own, slave, pet, sister, son...).|n")
                return
            if spec in rel.OWNER_FLAVORS:
                rel.offer_relation(caller, target, owner=True,
                                   flavor=rel.OWNER_FLAVORS[spec], expires_at=expires_at)
            elif spec == "lover":
                rel.offer_relation(caller, target, lover=True, expires_at=expires_at)
            else:
                rel.offer_relation(caller, target, role=spec, expires_at=expires_at)


ALL_RELATIONSHIP_CMDS = [CmdRelate]
