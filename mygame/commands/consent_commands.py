"""
commands/consent_commands.py — the `log` command (behaviour log + lockout),
Layer 2 v2 of the authority stack. See world/consent.py.

    log                  — read your own behaviour log
    log <name>           — (owner) read someone you own
    log/lock <name>      — (owner) lock them out of their own log
    log/unlock <name>    — (owner) lift the lockout

A unit can read their own log unless a holder has locked them out. The OOC floor
(escape / force_clear) lifts every lockout, always.
"""

from evennia.commands.default.muxcommand import MuxCommand


class CmdLog(MuxCommand):
    """
    The behaviour log — what's been done to you, and by whom.

    Usage:
      log                 — your own log
      log <name>          — (owner only) read someone you own
      log/lock <name>     — (owner) lock them out of their own log
      log/unlock <name>   — (owner) lift that lockout

    It records consent locks, forced bonds, rule breaks, and the like. You can
    read your own unless a holder has locked you out of it — then you rely on
    them, or on your OOC floor (escape / force_clear), which lifts everything.
    """
    key            = "log"
    aliases        = ["behaviour", "record"]
    switch_options = ("lock", "unlock")
    locks          = "cmd:all()"
    help_category  = "Interaction"

    def func(self):
        caller = self.caller
        from world.consent import render_log, can_view_log, set_log_lockout, is_locked
        from world.relationships import tiers_of

        name = self.args.strip()

        # owner lock/unlock
        if self.switches:
            if not name:
                caller.msg("|xUsage: log/lock <name>  ·  log/unlock <name>|n")
                return
            target = caller.search(name, location=caller.location) or caller.search(name, global_search=True)
            if not target:
                return
            if "owner" not in tiers_of(caller, target):
                caller.msg(f"|xYou don't own {target.db.rp_name or target.key}.|n")
                return
            set_log_lockout(target, "lock" in self.switches, by=caller)
            tn = target.db.rp_name or target.key
            caller.msg(f"|g{tn} is {'locked out of' if 'lock' in self.switches else 'given back'} "
                       f"their behaviour log.|n")
            return

        # read
        target = caller
        if name:
            target = caller.search(name, location=caller.location) or caller.search(name, global_search=True)
            if not target:
                return
        if not can_view_log(caller, target):
            caller.msg("|rYou're locked out of your own log. A holder controls it now — or use your "
                       "OOC floor (|wescape|r / |wforce_clear|r), always free.|n")
            return
        caller.msg(render_log(target))


ALL_CONSENT_CMDS = [CmdLog]
