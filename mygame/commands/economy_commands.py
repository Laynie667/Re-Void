"""
commands/economy_commands.py

Shard economy commands for Re:Void.

  wallet          — check your shard balance and recent transactions
  pay <who> = <n> — transfer shards to another character
  tip <who> = <n> — alias for pay, with warmer flavor
"""

from evennia.commands.default.muxcommand import MuxCommand


_SEP = "|x" + "─" * 44 + "|n"


class CmdWallet(MuxCommand):
    """
    Check your shard balance and recent transaction history.

    Usage:
        wallet
        shards
    """

    key           = "wallet"
    aliases       = ["shards"]
    locks         = "cmd:all()"
    help_category = "Economy"

    def func(self):
        from typeclasses.economy import get_balance
        from web.economy.models import ShardTransaction

        caller  = self.caller
        balance = get_balance(caller)

        lines = [
            f"\n{_SEP}",
            f"|m✦ Wallet  —  {caller.db.rp_name or caller.key}|n",
            _SEP,
        ]
        # Multi-currency: shards plus any realm-local currencies held (Phase 3).
        try:
            from world.wallet import wallet_lines
            lines.extend(wallet_lines(caller))
        except Exception:
            lines.append(f"  Balance:  |w{balance:,}|n shards")
        lines.append("")

        try:
            from django.db.models import Q
            recent = ShardTransaction.objects.filter(
                Q(sender_id=caller.id) | Q(recipient_id=caller.id)
            ).order_by("-created_at")[:8]

            if recent:
                lines.append("  |xRecent transactions:|n")
                for tx in recent:
                    when = tx.created_at.strftime("%m/%d %H:%M")
                    if tx.recipient_id == caller.id:
                        lines.append(
                            f"  |g+{tx.amount:>6,}|n  "
                            f"{tx.get_reason_display():<20}  |x{when}|n"
                        )
                    else:
                        lines.append(
                            f"  |r-{tx.amount:>6,}|n  "
                            f"{tx.get_reason_display():<20}  |x{when}|n"
                        )
            else:
                lines.append("  |xNo transactions yet.|n")
        except Exception:
            pass

        lines.append(_SEP)
        caller.msg("\n".join(lines))


class CmdPay(MuxCommand):
    """
    Transfer shards to another character.

    Both 'pay' and 'tip' do the same thing — 'tip' just feels warmer.

    Usage:
        pay <character> = <amount>
        tip <character> = <amount>

    Examples:
        pay Elara = 50
        tip Mira = 100
    """

    key           = "pay"
    aliases       = ["tip"]
    locks         = "cmd:all()"
    help_category = "Economy"

    def func(self):
        from typeclasses.economy import transfer_shards
        from evennia import search_object

        caller = self.caller

        if not self.args or "=" not in self.args:
            caller.msg("Usage: pay <character> = <amount>")
            return

        parts       = self.args.split("=", 1)
        target_name = parts[0].strip()
        amount_str  = parts[1].strip()

        try:
            amount = int(amount_str)
        except ValueError:
            caller.msg("|xAmount must be a whole number.|n")
            return

        if amount <= 0:
            caller.msg("|xAmount must be greater than zero.|n")
            return

        results = search_object(
            target_name,
            typeclass="typeclasses.characters.Character",
        )
        if not results:
            caller.msg(f"|xNo character found named '{target_name}'.|n")
            return
        if len(results) > 1:
            names = ", ".join(r.key for r in results)
            caller.msg(f"|xMultiple matches: {names}. Be more specific.|n")
            return

        target = results[0]
        if target == caller:
            caller.msg("|xYou can't pay yourself.|n")
            return

        is_tip = self.cmdstring.lower() == "tip"
        reason = "tip" if is_tip else "pay"
        note   = f"{caller.db.rp_name or caller.key} → {target.db.rp_name or target.key}"

        ok, result = transfer_shards(caller, target, amount, reason=reason, note=note)

        if not ok:
            caller.msg(f"|x{result}|n")
            return

        target_display = target.db.rp_name or target.key
        caller_display = caller.db.rp_name or caller.key

        if is_tip:
            caller.msg(
                f"|m✦|n You tip |w{target_display}|n |w{amount:,}|n shards. "
                f"|xBalance: {result:,}.|n"
            )
            target.msg(f"|m✦|n |w{caller_display}|n tips you |w{amount:,}|n shards.")
        else:
            caller.msg(
                f"|m✦|n You pay |w{target_display}|n |w{amount:,}|n shards. "
                f"|xBalance: {result:,}.|n"
            )
            target.msg(f"|m✦|n |w{caller_display}|n pays you |w{amount:,}|n shards.")


class CmdExchange(MuxCommand):
    """
    Exchange a realm's local currency into shards — where the realm allows it.

    Usage:
        exchange <amount> <currency>     — e.g. exchange 200 scrip

    Realm-local currencies are sovereign by default and do NOT convert; a realm
    only allows exchange if its governing faction has set a rate. Shards are the
    universal tender, so there's nothing to exchange them into.
    """

    key           = "exchange"
    aliases       = ["convert"]
    locks         = "cmd:all()"
    help_category = "Economy"

    def func(self):
        caller = self.caller
        room = caller.location
        parts = self.args.strip().split()
        if len(parts) < 2 or not parts[0].lstrip("-").isdigit():
            caller.msg("|xUsage: exchange <amount> <currency>  (e.g. exchange 200 scrip)|n")
            return
        amount = int(parts[0])
        currency = parts[1].lower()
        try:
            from world.wallet import exchange
            ok, msg = exchange(caller, room, currency, amount)
        except Exception as e:
            caller.msg(f"|rExchange unavailable: {e}|n")
            return
        caller.msg(("|g✨ " if ok else "|x") + msg + "|n")
