"""
commands/ogram_commands.py

The Ogram system — offline messaging with IC flavor.

An Ogram displaces the sender into a brief wizard to choose:
  1. Message type  (message / emote / affection / realm invitation)
  2. Affection subtype  (if affection was chosen)
  3. Anonymity  (signed or anonymous)
  4. Messenger presentation  (the courier's gender)
  5. Body  (text editor for message/emote/invite; optional note for affection)

The finished Ogram is stored in the database and delivered the next time
the recipient logs in. It is also visible in the website mailbox.

Usage:
    ogram <character>
    og <character>
"""

from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.evmenu import EvMenu


# ------------------------------------------------------------------ #
# EvMenu node functions
# All must be at module level so EvMenu can find them by name.
# ------------------------------------------------------------------ #

_SEP = "|x" + "─" * 44 + "|n"
_TITLE = "|m✦ Ogram|n"


def node_type(caller, raw_string, **kwargs):
    """Step 1 — choose message type."""
    draft = caller.db._ogram_draft or {}
    target = draft.get("target_name", "someone")

    text = (
        f"{_SEP}\n"
        f"{_TITLE}  |w→ {target}|n\n"
        f"{_SEP}\n\n"
        f"What kind of Ogram are you sending?\n"
    )
    options = [
        {
            "key": ("1", "message", "msg"),
            "desc": "|wMessage|n — written words, delivered privately",
            "goto": (_set_type, {"msg_type": "message"}),
        },
        {
            "key": ("2", "emote", "pose"),
            "desc": "|wEmote / Pose|n — an action performed by your messenger",
            "goto": (_set_type, {"msg_type": "emote"}),
        },
        {
            "key": ("3", "affection", "aff"),
            "desc": "|wAffection|n — a kiss, embrace, or intimate gesture",
            "goto": (_set_type, {"msg_type": "affection"}),
        },
        {
            "key": ("4", "invite", "inv"),
            "desc": "|wRealm Invitation|n — a formal summons or title claim",
            "goto": (_set_type, {"msg_type": "invite"}),
        },
        {
            "key": ("q", "quit", "cancel"),
            "desc": "Cancel — discard this Ogram",
            "goto": _cancel,
        },
    ]
    return text, options


def node_affection(caller, raw_string, **kwargs):
    """Step 1b — choose affection subtype (only reached for affection type)."""
    draft = caller.db._ogram_draft or {}
    target = draft.get("target_name", "someone")

    text = (
        f"{_SEP}\n"
        f"{_TITLE}  |w→ {target}|n  |x[Affection]|n\n"
        f"{_SEP}\n\n"
        f"What kind of affection are you sending?\n"
    )
    options = [
        {
            "key": ("1", "kiss"),
            "desc": "|wA gentle kiss|n",
            "goto": (_set_affection, {"affection_type": "kiss"}),
        },
        {
            "key": ("2", "embrace", "hug"),
            "desc": "|wA warm embrace|n",
            "goto": (_set_affection, {"affection_type": "embrace"}),
        },
        {
            "key": ("3", "intimate"),
            "desc": "|wSomething more intimate|n",
            "goto": (_set_affection, {"affection_type": "intimate"}),
        },
        {
            "key": ("b", "back"),
            "desc": "Back",
            "goto": "node_type",
        },
        {
            "key": ("q", "quit", "cancel"),
            "desc": "Cancel",
            "goto": _cancel,
        },
    ]
    return text, options


def node_anon(caller, raw_string, **kwargs):
    """Step 2 — signed or anonymous."""
    draft = caller.db._ogram_draft or {}
    target = draft.get("target_name", "someone")
    type_label = _type_label(draft.get("type", "message"))

    text = (
        f"{_SEP}\n"
        f"{_TITLE}  |w→ {target}|n  |x[{type_label}]|n\n"
        f"{_SEP}\n\n"
        f"Should your identity be revealed?\n"
    )
    options = [
        {
            "key": ("1", "sign", "signed", "yes"),
            "desc": f"|wSigned|n — the recipient will know it came from you",
            "goto": (_set_anon, {"anonymous": False}),
        },
        {
            "key": ("2", "anon", "anonymous", "no"),
            "desc": "|wAnonymous|n — your name will not appear",
            "goto": (_set_anon, {"anonymous": True}),
        },
        {
            "key": ("b", "back"),
            "desc": "Back",
            "goto": "node_type",
        },
        {
            "key": ("q", "quit", "cancel"),
            "desc": "Cancel",
            "goto": _cancel,
        },
    ]
    return text, options


def node_gender(caller, raw_string, **kwargs):
    """Step 3 — messenger presentation (the courier who delivers)."""
    draft = caller.db._ogram_draft or {}
    target = draft.get("target_name", "someone")
    type_label = _type_label(draft.get("type", "message"))
    anon_label = "Anonymous" if draft.get("anonymous") else f"from {draft.get('sender_display', 'you')}"

    text = (
        f"{_SEP}\n"
        f"{_TITLE}  |w→ {target}|n  |x[{type_label} · {anon_label}]|n\n"
        f"{_SEP}\n\n"
        f"How does your messenger present themselves?\n"
    )
    options = [
        {
            "key": ("1", "neutral", "androgynous"),
            "desc": "|wNeutral / Androgynous|n",
            "goto": (_set_gender, {"gender": "neutral"}),
        },
        {
            "key": ("2", "feminine", "female", "f"),
            "desc": "|wFeminine|n",
            "goto": (_set_gender, {"gender": "feminine"}),
        },
        {
            "key": ("3", "masculine", "male", "m"),
            "desc": "|wMasculine|n",
            "goto": (_set_gender, {"gender": "masculine"}),
        },
        {
            "key": ("b", "back"),
            "desc": "Back",
            "goto": "node_anon",
        },
        {
            "key": ("q", "quit", "cancel"),
            "desc": "Cancel",
            "goto": _cancel,
        },
    ]
    return text, options


def node_compose(caller, raw_string, **kwargs):
    """Step 4 — compose body or confirm (for affections with no body needed)."""
    draft = caller.db._ogram_draft or {}
    target = draft.get("target_name", "someone")
    type_label = _type_label(draft.get("type", "message"))
    anon_label = "Anonymous" if draft.get("anonymous") else f"from {draft.get('sender_display', 'you')}"
    gender_label = draft.get("gender", "neutral").capitalize()

    text = (
        f"{_SEP}\n"
        f"{_TITLE}  |w→ {target}|n\n"
        f"{_SEP}\n"
        f"  Type:      {type_label}\n"
        f"  Sender:    {anon_label}\n"
        f"  Messenger: {gender_label}\n"
        f"{_SEP}\n"
    )

    if draft.get("type") == "affection":
        aff = draft.get("affection_type", "kiss")
        aff_labels = {
            "kiss": "a gentle kiss",
            "embrace": "a warm embrace",
            "intimate": "something more intimate",
        }
        aff_display = aff_labels.get(aff, "an affection")
        text += (
            f"\n  Affection: {aff_display}\n\n"
            f"You may add an optional accompanying note, or send as-is.\n"
        )
        options = [
            {
                "key": ("1", "compose", "note", "write"),
                "desc": "Add an accompanying note (opens editor)",
                "goto": _open_editor,
            },
            {
                "key": ("2", "send", "yes"),
                "desc": "Send as-is, no note",
                "goto": _send_no_body,
            },
            {
                "key": ("b", "back"),
                "desc": "Back",
                "goto": "node_gender",
            },
            {
                "key": ("q", "quit", "cancel"),
                "desc": "Cancel",
                "goto": _cancel,
            },
        ]
    else:
        text += "\nOpen the editor to write your message.\n"
        options = [
            {
                "key": ("1", "compose", "write", ""),
                "desc": "Open the editor to compose your Ogram",
                "goto": _open_editor,
            },
            {
                "key": ("b", "back"),
                "desc": "Back",
                "goto": "node_gender",
            },
            {
                "key": ("q", "quit", "cancel"),
                "desc": "Cancel",
                "goto": _cancel,
            },
        ]
    return text, options


# ------------------------------------------------------------------ #
# Goto callbacks — set state and return next node name
# ------------------------------------------------------------------ #

def _set_type(caller, raw_string, **kwargs):
    msg_type = kwargs.get("msg_type", "message")
    draft = caller.db._ogram_draft or {}
    draft["type"] = msg_type
    caller.db._ogram_draft = draft
    if msg_type == "affection":
        return "node_affection"
    return "node_anon"


def _set_affection(caller, raw_string, **kwargs):
    affection_type = kwargs.get("affection_type", "kiss")
    draft = caller.db._ogram_draft or {}
    draft["affection_type"] = affection_type
    caller.db._ogram_draft = draft
    return "node_anon"


def _set_anon(caller, raw_string, **kwargs):
    anonymous = kwargs.get("anonymous", False)
    draft = caller.db._ogram_draft or {}
    draft["anonymous"] = anonymous
    caller.db._ogram_draft = draft
    return "node_gender"


def _set_gender(caller, raw_string, **kwargs):
    gender = kwargs.get("gender", "neutral")
    draft = caller.db._ogram_draft or {}
    draft["gender"] = gender
    caller.db._ogram_draft = draft
    return "node_compose"


def _open_editor(caller, raw_string, **kwargs):
    """Exit EvMenu and enter the text editor to compose the body."""
    from world.text_editor import _enter_editor, _PENDING_SETTERS

    draft = caller.db._ogram_draft or {}
    target_name = draft.get("target_name", "someone")

    def _ogram_setter(c, lines):
        _save_ogram(c, "\n".join(lines))

    _PENDING_SETTERS[str(caller.dbref)] = _ogram_setter
    _enter_editor(
        caller,
        target_display=f"Ogram → {target_name}",
        setter_key="_room_field",
        initial_lines=[],
    )
    return None  # exit EvMenu


def _send_no_body(caller, raw_string, **kwargs):
    """Send an affection Ogram with no written body."""
    _save_ogram(caller, "")
    return None  # exit EvMenu


def _cancel(caller, raw_string, **kwargs):
    caller.db._ogram_draft = None
    caller.msg("|x[Ogram cancelled.]|n")
    return None  # exit EvMenu


# ------------------------------------------------------------------ #
# Save and delivery helpers
# ------------------------------------------------------------------ #

def _type_label(msg_type):
    return {
        "message":   "Message",
        "emote":     "Emote",
        "affection": "Affection",
        "invite":    "Invitation",
        "staff":     "Staff",
    }.get(msg_type, msg_type.capitalize())


def _save_ogram(caller, body):
    """
    Create the OgramMessage record and confirm to the sender.
    Called when :done is pressed in the editor.
    """
    try:
        from web.mail.models import OgramMessage
    except ImportError:
        caller.msg("|rOgram system not available. Contact staff.|n")
        return

    draft = caller.db._ogram_draft or {}
    if not draft:
        caller.msg("|xNo Ogram draft found. Please start again with 'ogram <name>'.|n")
        return

    target_name = draft.get("target_name", "")
    if not target_name:
        caller.msg("|xOgram draft is missing a recipient. Please start again.|n")
        return

    msg = OgramMessage(
        sender_object_id    = caller.id,
        sender_name         = caller.db.rp_name or caller.key,
        sender_account_id   = caller.account.id if caller.account else None,
        anonymous           = draft.get("anonymous", False),
        recipient_object_id = draft.get("target_id"),
        recipient_name      = target_name,
        recipient_account_id = draft.get("target_account_id"),
        msg_type            = draft.get("type", "message"),
        affection_type      = draft.get("affection_type", ""),
        messenger_gender    = draft.get("gender", "neutral"),
        subject             = draft.get("subject", ""),
        body                = body.strip(),
    )
    msg.save()

    # Clear the draft
    caller.db._ogram_draft = None

    caller.msg(
        f"\n|m✦ Ogram sealed.|n\n"
        f"|xYour message to |w{target_name}|n|x will be delivered "
        f"upon their next login.|n"
    )

    # Optional: email notification
    _send_email_notification(msg)


def _send_email_notification(msg):
    """
    If the recipient account has an email address and email alerts enabled,
    send a notification. Silently skips if anything goes wrong.
    """
    try:
        from evennia.accounts.models import AccountDB
        from django.core.mail import send_mail
        from django.conf import settings

        if not msg.recipient_account_id:
            return

        acct = AccountDB.objects.filter(pk=msg.recipient_account_id).first()
        if not acct:
            return

        email = acct.email
        alerts = getattr(acct.db, "email_alerts", False)
        if not email or not alerts:
            return

        sender_display = "Anonymous" if msg.anonymous else (msg.sender_name or "Someone")
        subject = f"[Re:Void] You have an Ogram from {sender_display}"
        body = (
            f"An Ogram has arrived for {msg.recipient_name}.\n\n"
            f"It will be waiting for you the next time you log in.\n\n"
            f"— Re:Void"
        )
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@revoid.game")
        send_mail(subject, body, from_email, [email], fail_silently=True)
    except Exception:
        pass


def deliver_ograms(account):
    """
    Called from Account.at_post_login. Finds all undelivered Ograms for
    any character belonging to this account and delivers them with
    formatted output. Marks each as delivered.

    Args:
        account: The Evennia AccountDB instance logging in.
    """
    try:
        from web.mail.models import OgramMessage
        from django.utils import timezone
    except ImportError:
        return

    # Get all character IDs for this account
    try:
        char_ids = [c.id for c in account.characters.all()]
    except Exception:
        return

    if not char_ids:
        return

    pending = OgramMessage.objects.filter(
        recipient_object_id__in=char_ids,
        delivered_at__isnull=True,
        deleted_by_recipient=False,
    ).order_by("sent_at")

    if not pending.exists():
        return

    sep = "|m" + "─" * 44 + "|n"
    lines = [f"\n{sep}", f"|m✦ You have {pending.count()} Ogram(s) waiting.|n", sep]

    for msg in pending:
        lines.append("")
        lines.append(_format_delivery(msg))

    lines.append("")
    lines.append(f"|x(View your mailbox at the website for full details.)|n")
    lines.append(sep)

    account.msg("\n".join(lines))

    # Mark all as delivered
    pending.update(delivered_at=timezone.now())


def _format_delivery(msg):
    """
    Format a single OgramMessage for in-game delivery display.
    """
    sender = "An anonymous sender" if msg.anonymous else (msg.sender_name or "An unknown sender")
    gender_article = {
        "neutral":   "A messenger",
        "feminine":  "A feminine messenger",
        "masculine": "A masculine messenger",
    }.get(msg.messenger_gender, "A messenger")

    if msg.msg_type == "message":
        header = f"|m{gender_article} delivers a sealed message from {sender}.|n"
        body   = f'\n|x"{msg.body}"|n' if msg.body else ""
        return f"{header}{body}"

    elif msg.msg_type == "emote":
        header = f"|m{gender_article} arrives on behalf of {sender}:|n"
        body   = f"\n{msg.body}" if msg.body else ""
        return f"{header}{body}"

    elif msg.msg_type == "affection":
        aff_labels = {
            "kiss":     "leaves a gentle kiss",
            "embrace":  "offers a warm embrace",
            "intimate": "delivers something more intimate",
        }
        aff_display = aff_labels.get(msg.affection_type, "delivers an affection")
        header = f"|m{gender_article} {aff_display} — a gift from {sender}.|n"
        note   = f'\n|x"{msg.body}"|n' if msg.body else ""
        return f"{header}{note}"

    elif msg.msg_type == "invite":
        header = f"|m{gender_article} presents a formal invitation from {sender}:|n"
        body   = f"\n{msg.body}" if msg.body else ""
        return f"{header}{body}"

    else:
        return f"|mAn Ogram from {sender}:|n\n{msg.body}"


# ------------------------------------------------------------------ #
# The command
# ------------------------------------------------------------------ #

class CmdOgram(MuxCommand):
    """
    Send an offline message to another character.

    An Ogram is a sealed message delivered to the recipient the next time
    they log in. You may send a written message, an emote, an affection,
    or a formal realm invitation. Choose whether to sign it or remain
    anonymous, and select the presentation of the messenger who carries it.

    Usage:
        ogram <character>
        og <character>

    The Ogram wizard will guide you through the rest.
    Sent Ograms are also visible in the website mailbox.
    """

    key  = "ogram"
    aliases = ["og"]
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("Usage: ogram <character name>")
            return

        target_name = self.args.strip()

        # Find the target character
        from evennia import search_object
        results = search_object(
            target_name,
            typeclass="typeclasses.characters.Character",
        )
        if not results:
            caller.msg(f"|xNo character found named '{target_name}'.|n")
            return
        if len(results) > 1:
            names = ", ".join(r.key for r in results)
            caller.msg(f"|xMultiple characters found: {names}. Be more specific.|n")
            return

        target = results[0]
        if target == caller:
            caller.msg("|xYou can't send an Ogram to yourself.|n")
            return

        # Get target's account for notification and mailbox linking
        target_account = getattr(target, "account", None)

        # Set up the draft
        caller.db._ogram_draft = {
            "target_id":         target.id,
            "target_name":       target.db.rp_name or target.key,
            "target_account_id": target_account.id if target_account else None,
            "sender_display":    caller.db.rp_name or caller.key,
            "type":              None,
            "affection_type":    "",
            "anonymous":         False,
            "gender":            "neutral",
        }

        EvMenu(
            caller,
            "commands.ogram_commands",
            startnode="node_type",
            cmd_on_exit=None,
            auto_quit=False,
            auto_look=False,
            auto_help=False,
        )
