"""
web/economy/models.py

Transaction log for the Re:Void shard economy.
Every shard movement — passive income, allowances, tips, purchases — is
recorded here for admin visibility and debugging.
"""

from django.db import models


REASON_CHOICES = [
    ("passive",         "Passive income"),
    ("active_rp",       "Active RP income"),
    ("daily_allowance", "Daily allowance"),
    ("tip",             "Player tip"),
    ("pay",             "Player payment"),
    ("purchase",        "Shop purchase"),
    ("staff_grant",     "Staff grant"),
    ("staff_deduct",    "Staff deduction"),
    ("other",           "Other"),
]


class ShardTransaction(models.Model):
    """
    Records a single shard movement.
    sender_id / recipient_id are ObjectDB PKs (characters).
    Either may be None for system-generated income or purchases.
    """
    sender_id    = models.IntegerField(null=True, blank=True, db_index=True)
    recipient_id = models.IntegerField(null=True, blank=True, db_index=True)
    amount       = models.IntegerField()
    reason       = models.CharField(max_length=32, choices=REASON_CHOICES, default="other")
    note         = models.CharField(max_length=200, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        s = f"#{self.sender_id}" if self.sender_id else "System"
        r = f"#{self.recipient_id}" if self.recipient_id else "System"
        return f"{s} → {r}: {self.amount} shards ({self.reason})"
