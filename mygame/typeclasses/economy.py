"""
typeclasses/economy.py

Shard economy utility functions for Re:Void.

All shard mutations go through these helpers so that:
  - The daily cap is always respected for passive income
  - Every movement is logged to ShardTransaction
  - Balance never goes below zero

Currency: Shards
Daily passive cap: 1,000 shards per 24 hours
"""

from datetime import date


DAILY_CAP       = 1000
DAILY_ALLOWANCE = 15


# ------------------------------------------------------------------ #
# Internal helpers
# ------------------------------------------------------------------ #

def _log(sender_id, recipient_id, amount, reason, note=""):
    """Write a ShardTransaction record. Silently skips on error."""
    try:
        from web.economy.models import ShardTransaction
        ShardTransaction.objects.create(
            sender_id    = sender_id,
            recipient_id = recipient_id,
            amount       = amount,
            reason       = reason,
            note         = note,
        )
    except Exception:
        pass


def _reset_daily_if_needed(character):
    """Reset the daily earned counter if the calendar day has changed."""
    today = str(date.today())
    if character.db.daily_shards_date != today:
        character.db.daily_shards_earned = 0
        character.db.daily_shards_date   = today


# ------------------------------------------------------------------ #
# Public API
# ------------------------------------------------------------------ #

def get_balance(character):
    """Return the character's current shard balance (never negative)."""
    bal = character.db.shards
    return int(bal) if bal is not None else 0


def add_shards(character, amount, reason="other", note=""):
    """
    Add shards unconditionally (staff grants, allowance delivery, etc.).
    Does NOT count toward the daily passive cap.
    Returns the new balance.
    """
    character.db.shards = get_balance(character) + amount
    _log(None, character.id, amount, reason, note)
    return character.db.shards


def add_passive_shards(character, amount, reason="passive"):
    """
    Add passive income shards, capped at DAILY_CAP per day.
    Returns the actual amount awarded (may be less than requested).
    """
    _reset_daily_if_needed(character)
    earned    = character.db.daily_shards_earned or 0
    remaining = DAILY_CAP - earned
    if remaining <= 0:
        return 0
    actual = min(amount, remaining)
    character.db.shards              = get_balance(character) + actual
    character.db.daily_shards_earned = earned + actual
    _log(None, character.id, actual, reason)
    return actual


def remove_shards(character, amount, reason="purchase", note=""):
    """
    Remove shards from a character's wallet.
    Returns True on success, False if the character can't afford it.
    """
    bal = get_balance(character)
    if bal < amount:
        return False
    character.db.shards = bal - amount
    _log(character.id, None, amount, reason, note)
    return True


def transfer_shards(sender, recipient, amount, reason="tip", note=""):
    """
    Transfer shards from sender to recipient.
    Returns (True, new_sender_balance) on success.
    Returns (False, error_string) on failure.
    """
    if amount <= 0:
        return False, "Amount must be greater than zero."
    bal = get_balance(sender)
    if bal < amount:
        return False, f"You only have {bal:,} shards."
    sender.db.shards    = bal - amount
    recipient.db.shards = get_balance(recipient) + amount
    _log(sender.id, recipient.id, amount, reason, note)
    return True, get_balance(sender)
