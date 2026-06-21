"""
commands/rule_commands.py — the `rule` command (Layer 3 of the authority stack).
See world/rules.py.

    rule <who>                          — list someone's standing rules
    rule/add <who> = <name> [params]    — set a rule (needs rule.set authority)
    rule/remove <who> = <id>            — clear a rule (#id from the list)
    rule/list                           — show the rule catalogue

Setting a rule on someone requires authority over them: an owner, or yourself on
yourself (consent.may(you, them, "rule.set")). The OOC floor wipes all rules.
"""

from evennia.commands.default.muxcommand import MuxCommand


class CmdRule(MuxCommand):
    """
    Set, view, or clear standing rules on someone (or yourself).

    Usage:
      rule <who>                        — their standing rules
      rule/add <who> = <name> [params]  — impose a rule
      rule/remove <who> = <id>          — clear rule #id
      rule/list                         — the rule catalogue

    Rules (curated): present_on_enter, kneel_on_enter, no_leave, banned_words,
    honorific, ask_to_come, no_clothing, posture_hold, curfew.

    Params are key:value, e.g.
      rule/add Laynie = banned_words words:no,stop,please
      rule/add Laynie = curfew hours:22-6
      rule/add Laynie = honorific honorific:Mistress
      rule/add Laynie = posture_hold posture:kneeling

    Imposing a rule needs authority over the target (an owner, or yourself on
    yourself). Each rule's consequence is block / punish / notify; override the
    default with consequence:block|punish|notify. The OOC floor wipes all rules.
    """
    key            = "rule"
    aliases        = ["rules"]
    switch_options = ("add", "remove", "list", "clear")
    locks          = "cmd:all()"
    help_category  = "Interaction"

    def func(self):
        caller = self.caller
        from world import rules as R
        from world.consent import may

        if "list" in self.switches:
            lines = ["|wRULE CATALOGUE|n"]
            for name, meta in R.CATALOGUE.items():
                pr = f"  |x(param: {meta['param']})|n" if meta.get("param") else ""
                lines.append(f"  |w{name}|n → {meta['consequence']}  — {meta['desc']}{pr}")
            caller.msg("\n".join(lines))
            return

        name = (self.lhs or self.args or "").strip()
        if not name:
            caller.msg("|xRule on whom? See |whelp rule|x.|n")
            return
        target = caller.search(name, location=caller.location) or caller.search(name, global_search=True)
        if not target:
            return

        # view
        if not self.switches:
            caller.msg(R.render_rules(target))
            return

        # mutate — needs authority
        if not may(caller, target, "rule.set") and caller is not target:
            caller.msg(f"|xYou don't have the authority to set rules on "
                       f"{target.db.rp_name or target.key}. (They'd need to allow you "
                       f"'rule.set', or you own them.)|n")
            return

        if "remove" in self.switches or "clear" in self.switches:
            try:
                rid = int((self.rhs or "").strip().lstrip("#"))
            except ValueError:
                caller.msg("|xWhich rule #id? See |wrule <who>|x.|n")
                return
            ok = R.remove_rule(target, rid)
            caller.msg("|gRule cleared.|n" if ok else "|xNo rule with that id.|n")
            return

        if "add" in self.switches:
            spec = (self.rhs or "").strip()
            if not spec:
                caller.msg("|xName the rule: |wrule/add <who> = <name> [key:value ...]|x.|n")
                return
            parts = spec.split()
            rname = parts[0].lower()
            params, consequence, condition = {}, None, None
            for tok in parts[1:]:
                if ":" not in tok:
                    continue
                k, v = tok.split(":", 1)
                k = k.lower()
                if k == "consequence":
                    consequence = v.lower()
                elif k == "words":
                    params["words"] = [w.strip() for w in v.split(",") if w.strip()]
                elif k == "hours":
                    try:
                        a, b = v.split("-"); params["hours"] = (int(a), int(b))
                    except Exception:
                        pass
                else:
                    params[k] = v
            rule, err = R.add_rule(target, rname, caller, condition=condition,
                                   consequence=consequence, params=params)
            if err:
                caller.msg(f"|x{err}|n")
                return
            tn = target.db.rp_name or target.key
            caller.msg(f"|gRule set on {tn}: |w{rule['name']}|g → {rule['consequence']}.|n")
            if target is not caller:
                target.msg(f"|MA rule settles over you: |w{rule['name']}|M "
                           f"({R.CATALOGUE[rule['name']]['desc']}).|n")


class CmdHonorific(MuxCommand):
    """
    Set, view, or clear the honorific someone must address you by.

    A friendly front-end over the honorific standing-rule (see `rule`). The
    default consequence is a soft *notify* nudge — they're reminded, not
    punished; raise it with the full `rule` command if you want real bite.
    Setting one needs authority over the target: you own them, or they allowed
    you 'rule.set' (yourself on yourself always works).

    Usage:
      honorific <who> = <token>   — <who> should address holders as <token>
      honorific <who>             — show the honorific(s) owed by <who>
      honorific/clear <who>       — clear the honorific rule on <who>

    Example:
      honorific Laynie = Mistress
    """
    key            = "honorific"
    aliases        = ["address"]
    switch_options = ("clear", "remove")
    locks          = "cmd:all()"
    help_category  = "Interaction"

    def func(self):
        caller = self.caller
        from world import rules as R
        from world.consent import may

        name = (self.lhs or self.args or "").strip()
        if not name:
            caller.msg("|xHonorific on whom? |whonorific <who> = Mistress|x.|n")
            return
        target = (caller.search(name, location=caller.location)
                  or caller.search(name, global_search=True))
        if not target:
            return

        tn = target.db.rp_name or target.key
        existing = [r for r in (getattr(target.db, "rules", None) or [])
                    if r.get("name") == "honorific" and r.get("active", True)]

        # view
        if not self.switches and not self.rhs:
            if not existing:
                caller.msg(f"|x{tn} owes no honorific.|n")
            else:
                toks = ", ".join(r.get("params", {}).get("honorific", "?") for r in existing)
                caller.msg(f"|w{tn}|n is to address holders as: |w{toks}|n.")
            return

        # mutate — needs authority
        if not may(caller, target, "rule.set") and caller is not target:
            caller.msg(f"|xYou don't have the authority to set an honorific on {tn}. "
                       f"(They'd need to allow you 'rule.set', or you own them.)|n")
            return

        if "clear" in self.switches or "remove" in self.switches:
            removed = sum(1 for r in existing if R.remove_rule(target, r.get("id")))
            caller.msg("|gHonorific cleared.|n" if removed
                       else "|xNo honorific rule to clear.|n")
            return

        token = (self.rhs or "").strip()
        if not token:
            caller.msg("|xName the honorific: |whonorific <who> = Mistress|x.|n")
            return
        rule, err = R.add_rule(target, "honorific", caller, params={"honorific": token})
        if err:
            caller.msg(f"|x{err}|n")
            return
        caller.msg(f"|gFrom now on, {tn} should address holders as |w{token}|g "
                   f"(a soft nudge — raise it with |wrule|g for bite).|n")
        if target is not caller:
            target.msg(f"|MYou're to be addressed properly now — |w{token}|M, when it's owed.|n")


ALL_RULE_CMDS = [CmdRule, CmdHonorific]
