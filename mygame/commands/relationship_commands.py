"""
commands/relationship_commands.py — the `relate` command (Layer 1 of the
authority stack). See world/relationships.py + CONSENT_RULES_CONTRACTS_DESIGN.md.

    relate                          — list your bonds + pending offers
    relate <who> = <role|lover>     — OFFER a mutual bond (they must accept)
    relate/accept <who>             — accept a pending offer
    relate/reject <who>             — refuse a pending offer
    relate/force <who> = <role>     — OWNER imposes a family role (no consent)
    relate/clear <who>              — dissolve the bond both ways

Family roles (core set): mother father sire dam parent · daughter son get
offspring child · sister brother sibling. Reciprocals are set automatically,
gendered by the other person. lover and family may coexist.
"""

from evennia.commands.default.muxcommand import MuxCommand


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
    switch_options = ("accept", "reject", "force", "clear")
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
            # offer a mutual bond
            spec = (self.rhs or "").strip().lower()
            if not spec:
                caller.msg("|xName the bond: |wrelate <who> = mother|x (or lover, sister, son...).|n")
                return
            if spec == "lover":
                rel.offer_relation(caller, target, lover=True)
            else:
                rel.offer_relation(caller, target, role=spec)


ALL_RELATIONSHIP_CMDS = [CmdRelate]
