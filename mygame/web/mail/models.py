"""
web/mail/models.py

Ogram messaging system for Re:Void.

An Ogram is an offline message — delivered to the recipient the next time
they log in. They can be plain messages, emotes/poses, affections, or
realm invitations. Each Ogram records who sent it, the messenger's
presentation, and whether it was sent anonymously.

Messages are also readable from the website mailbox.
"""

from django.db import models


class OgramMessage(models.Model):

    MSG_TYPE_CHOICES = [
        ("message",   "Message"),
        ("emote",     "Emote / Pose"),
        ("affection", "Affection"),
        ("invite",    "Realm Invitation"),
        ("staff",     "Staff Contact"),
    ]

    AFFECTION_CHOICES = [
        ("kiss",        "A soft kiss"),
        ("french_kiss", "A deep, passionate kiss"),
        ("hug",         "A warm hug"),
        ("grope",       "Wandering hands"),
    ]

    GENDER_CHOICES = [
        ("neutral",   "Neutral / Androgynous"),
        ("feminine",  "Feminine"),
        ("masculine", "Masculine"),
    ]

    # ------------------------------------------------------------------ #
    # Sender
    # ------------------------------------------------------------------ #
    # We store integer IDs rather than ForeignKeys to avoid cross-app
    # dependency issues with Evennia's ObjectDB / AccountDB models.
    sender_object_id  = models.IntegerField(null=True, blank=True)
    sender_name       = models.CharField(max_length=80, blank=True)
    sender_account_id = models.IntegerField(null=True, blank=True)
    # For staff-contact submissions from non-logged-in visitors:
    sender_email      = models.EmailField(blank=True)
    anonymous         = models.BooleanField(default=False)

    # ------------------------------------------------------------------ #
    # Recipient
    # ------------------------------------------------------------------ #
    recipient_object_id  = models.IntegerField(null=True, blank=True)
    recipient_name       = models.CharField(max_length=80, blank=True)
    recipient_account_id = models.IntegerField(null=True, blank=True)

    # ------------------------------------------------------------------ #
    # Message content
    # ------------------------------------------------------------------ #
    msg_type       = models.CharField(
        max_length=20, choices=MSG_TYPE_CHOICES, default="message"
    )
    affection_type = models.CharField(
        max_length=20, choices=AFFECTION_CHOICES, blank=True
    )
    messenger_gender = models.CharField(
        max_length=20, choices=GENDER_CHOICES, default="neutral"
    )
    subject = models.CharField(max_length=200, blank=True)
    body    = models.TextField(blank=True)

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #
    sent_at            = models.DateTimeField(auto_now_add=True)
    # Set when the in-game delivery fires on login
    delivered_at       = models.DateTimeField(null=True, blank=True)
    # Set when opened on the website
    read_at            = models.DateTimeField(null=True, blank=True)
    deleted_by_sender    = models.BooleanField(default=False)
    deleted_by_recipient = models.BooleanField(default=False)

    class Meta:
        app_label = "ogram"
        ordering = ["-sent_at"]
        verbose_name = "Ogram Message"
        verbose_name_plural = "Ogram Messages"

    def __str__(self):
        sender = "Anonymous" if self.anonymous else (self.sender_name or "Unknown")
        return f"{self.sent_at:%Y-%m-%d} — {sender} → {self.recipient_name} [{self.msg_type}]"

    @property
    def is_delivered(self):
        return self.delivered_at is not None

    @property
    def is_read(self):
        return self.read_at is not None

    @property
    def display_sender(self):
        """Name shown to the recipient (respects anonymous flag)."""
        if self.anonymous:
            return "Anonymous"
        return self.sender_name or "Unknown"

    @property
    def affection_label(self):
        labels = dict(self.AFFECTION_CHOICES)
        return labels.get(self.affection_type, "An affection")

    @property
    def messenger_name(self):
        return {
            "feminine":  "Seraphine",
            "masculine": "Calix",
            "neutral":   "Vesper",
        }.get(self.messenger_gender, "Vesper")

    @property
    def gender_label(self):
        labels = dict(self.GENDER_CHOICES)
        return labels.get(self.messenger_gender, "neutral")
