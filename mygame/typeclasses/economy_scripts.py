"""
typeclasses/economy_scripts.py

Global economy scripts for Re:Void.

PassiveIncomeScript   — awards shards to all logged-in characters every 10 min
DailyAllowanceScript  — sends The Witch's daily allowance O'gram once per day
                        per account (checks hourly, acts only when due)
"""

import random
from evennia import DefaultScript


# ------------------------------------------------------------------ #
# Passive income
# ------------------------------------------------------------------ #

class PassiveIncomeScript(DefaultScript):
    """
    Runs every 10 minutes. For every character currently puppeted by
    a connected session:

      - In a room with other connected players → 5–20 shards (active RP rate)
      - Alone                                  → 1–7  shards (passive rate)

    Both rates count toward the 1,000-shard daily cap.
    """

    def at_script_creation(self):
        self.key        = "passive_income_script"
        self.desc       = "Awards passive shard income to logged-in characters."
        self.interval   = 600   # 10 minutes
        self.persistent = True

    def at_repeat(self):
        from evennia.accounts.models import AccountDB
        from typeclasses.economy import add_passive_shards

        for account in AccountDB.objects.filter(db_is_connected=True):
            try:
                for session in account.sessions.all():
                    puppet = session.get_puppet()
                    if not puppet:
                        continue
                    try:
                        room = puppet.location
                        if not room:
                            continue

                        # Count other actively-connected characters in same room
                        others = [
                            obj for obj in room.contents
                            if obj != puppet
                            and hasattr(obj, "sessions")
                            and obj.sessions.count() > 0
                        ]

                        if others:
                            amount = random.randint(5, 20)
                            reason = "active_rp"
                        else:
                            amount = random.randint(1, 7)
                            reason = "passive"

                        add_passive_shards(puppet, amount, reason)

                    except Exception:
                        pass
            except Exception:
                pass


# ------------------------------------------------------------------ #
# Daily allowance
# ------------------------------------------------------------------ #

_WITCH_BODIES = [
    "Your daily allowance, love. Fifteen shards — spend them on something that makes you smile.\n\n— Witch ✦",
    "Here. You showed up today, and that's worth something.\n\n(15 shards, as always.)\n\n— Witch ✦",
    "Don't let the Void have everything. Fifteen shards. Spend them well.\n\n— Witch ✦",
    "Still here. Good. Fifteen shards for your trouble.\n\n— Witch ✦",
    "A little something to keep the emptiness from feeling quite so empty.\n\n— Witch ✦",
    "Fifteen shards, delivered as promised. Don't spend them all in one place.\n\n(I know you will.)\n\n— Witch ✦",
]


class DailyAllowanceScript(DefaultScript):
    """
    Runs every hour. For each account that hasn't received their allowance
    today, creates an allowance O'gram from Witch addressed to the account's
    first character. Shards are deposited when the O'gram is delivered on login.
    """

    def at_script_creation(self):
        self.key        = "daily_allowance_script"
        self.desc       = "Sends The Witch's daily allowance O'gram to each account."
        self.interval   = 3600  # check every hour
        self.persistent = True

    def at_repeat(self):
        from datetime import date
        from evennia.accounts.models import AccountDB
        from web.mail.models import OgramMessage

        today   = str(date.today())
        genders = ["feminine", "masculine", "neutral"]

        for account in AccountDB.objects.all():
            try:
                if account.db.last_allowance_date == today:
                    continue

                chars = list(account.characters.all())
                if not chars:
                    continue

                char           = chars[0]
                recipient_name = char.db.rp_name or char.key
                gender         = random.choice(genders)

                OgramMessage.objects.create(
                    sender_name          = "Witch",
                    sender_account_id    = None,
                    anonymous            = False,
                    recipient_object_id  = char.id,
                    recipient_name       = recipient_name,
                    recipient_account_id = account.id,
                    msg_type             = "allowance",
                    messenger_gender     = gender,
                    subject              = "Your Daily Allowance",
                    body                 = random.choice(_WITCH_BODIES),
                )

                account.db.last_allowance_date = today

            except Exception:
                pass
