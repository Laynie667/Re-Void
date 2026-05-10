"""
web/mail/forms.py

Forms for the website mailbox and staff contact page.
"""

from django import forms
from .models import OgramMessage


class ComposeForm(forms.Form):
    """Website compose form — send an Ogram to a character by name."""

    recipient = forms.CharField(
        max_length=80,
        label="To (character name)",
        widget=forms.TextInput(attrs={
            "placeholder": "Character name",
            "autocomplete": "off",
        }),
    )
    msg_type = forms.ChoiceField(
        choices=[
            ("message",   "Message"),
            ("emote",     "Emote / Pose"),
            ("affection", "Affection"),
            ("invite",    "Realm Invitation"),
        ],
        label="Type",
        initial="message",
    )
    affection_type = forms.ChoiceField(
        choices=[
            ("",            "— none —"),
            ("kiss",        "A soft kiss"),
            ("french_kiss", "A deep, passionate kiss"),
            ("hug",         "A warm hug"),
            ("grope",       "Wandering hands"),
        ],
        label="Affection type",
        required=False,
    )
    messenger_gender = forms.ChoiceField(
        choices=OgramMessage.GENDER_CHOICES,
        label="Messenger presentation",
        initial="neutral",
    )
    anonymous = forms.BooleanField(
        required=False,
        label="Send anonymously",
    )
    subject = forms.CharField(
        max_length=200,
        required=False,
        label="Subject (optional)",
        widget=forms.TextInput(attrs={"placeholder": "Optional subject"}),
    )
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 8,
            "placeholder": "Write your message here…",
        }),
        label="Message",
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        msg_type = cleaned.get("msg_type")
        body = cleaned.get("body", "").strip()
        affection_type = cleaned.get("affection_type", "")

        if msg_type == "affection" and not affection_type:
            self.add_error(
                "affection_type",
                "Please choose an affection type.",
            )

        if msg_type in ("message", "emote", "invite") and not body:
            self.add_error(
                "body",
                "Please write a message body.",
            )
        return cleaned


class StaffContactForm(forms.Form):
    """Staff contact form — submitted by players or visitors."""

    name = forms.CharField(
        max_length=80,
        label="Your name",
        widget=forms.TextInput(attrs={"placeholder": "Display name or character name"}),
    )
    email = forms.EmailField(
        required=False,
        label="Email (optional — for a reply)",
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}),
    )
    subject = forms.CharField(
        max_length=200,
        label="Subject",
        widget=forms.TextInput(attrs={"placeholder": "What's this about?"}),
    )
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 8,
            "placeholder": "Your message to staff…",
        }),
        label="Message",
    )
