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

Messengers are a set of tiefling triplets — Seraphine (feminine),
Calix (masculine), and Vesper (ambiguous/neutral) — each with distinct
character presence. If they become NPCs later, the names and quirks
are already established here.

Usage:
    ogram <character>
    og <character>
"""

import random

from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.evmenu import EvMenu


# ------------------------------------------------------------------ #
# Messenger triplets
# ------------------------------------------------------------------ #

# Seraphine — the feminine courier.
# Crimson-skinned tiefling woman. Small swept-back horns, a tail she
# uses expressively, and the particular poise of someone who has
# delivered very intimate secrets and found them entirely ordinary.
_SERAPHINE_ARRIVALS = [
    (
        "|wSeraphine|n arrives on quiet feet — a tiefling woman, crimson-skinned, "
        "her small swept-back horns catching the light as she tilts her head with "
        "the expression of someone who already knows exactly what she is carrying. "
        "Her tail sways once, languidly, as she steps forward."
    ),
    (
        "The scent of something faintly smoky and sweet arrives just before she does. "
        "|wSeraphine|n — crimson skin, swept-back horns, the unhurried posture of "
        "someone entirely at home in other people's private moments — produces a "
        "sealed Ogram and extends it without ceremony."
    ),
    (
        "|wSeraphine|n does not knock. She simply appears in the threshold, "
        "poised and crimson and faintly amused, her tail describing a slow arc "
        "behind her as she takes in the room. She has the look of a woman who "
        "has heard everything and found most of it charming."
    ),
    (
        "A tiefling woman with crimson skin and small, elegant horns steps lightly "
        "through the space as though she owns it. |wSeraphine|n. She says your name "
        "— or doesn't — and produces what she was sent to deliver."
    ),
]

# Calix — the masculine courier.
# Deep charcoal-skinned tiefling man. Ram horns, broad-shouldered,
# built like someone who could carry a sealed chest through a storm
# and arrive looking entirely unbothered. Few words. Absolute discretion.
_CALIX_ARRIVALS = [
    (
        "|wCalix|n fills the doorway for a moment before entering — a broad-shouldered "
        "tiefling man, charcoal-dark, ram horns angled with the patience of someone "
        "who has stood in worse weather. He sets what he carries before you with a "
        "single measured nod that implies he has heard everything and remembers "
        "none of it. Professionally."
    ),
    (
        "The footsteps, when they come, are heavier than you expected. |wCalix|n, "
        "a tiefling man with the deep charcoal complexion and ram's horns of someone "
        "who was clearly built for more demanding work than this, extends the Ogram "
        "without fanfare and waits."
    ),
    (
        "|wCalix|n enters with the quiet certainty of a man who has delivered "
        "far stranger things and asked no questions about any of them. "
        "Deep charcoal skin. Ram horns. An expression of complete professional "
        "indifference that is, in its own way, rather reassuring."
    ),
    (
        "A tiefling man with broad shoulders and the careful gravity of someone "
        "who moves through the world without breaking things places what he carries "
        "before you. |wCalix|n. He does not explain himself. He doesn't need to."
    ),
]

# Vesper — the ambiguous/neutral courier.
# Opalescent-skinned tiefling of undisclosed nature. Swept-back horns
# that seem to shift between sharp and something softer depending on
# the light. Eyes that change color — silver, then violet, then something
# without a name. Speaks rarely. Their body is elegant and deliberately
# unreadable. Their nature has never been explicitly stated and they
# seem to prefer it that way.
_VESPER_ARRIVALS = [
    (
        "|wVesper|n appears at the edge of your awareness before you quite register "
        "their arrival — a tiefling of opalescent skin and swept-back horns that "
        "seem to shift between sharp and something softer depending on the light. "
        "Their eyes, silver-violet and unsettled, hold yours for a moment longer "
        "than necessary before the Ogram is pressed precisely into your hands."
    ),
    (
        "The messenger who delivers this is called |wVesper|n. Their skin is "
        "opalescent, their horns elegant and ambiguous, and their expression is "
        "the particular kind of unreadable that takes years to cultivate. "
        "They say nothing. They don't need to. They simply extend what they carry "
        "and wait with the patience of something that has learned how."
    ),
    (
        "|wVesper|n materializes — there is genuinely no better word for the way "
        "they move — and presses a sealed Ogram into your hands with fingers "
        "that are cool and deliberate. The color of their eyes shifts as they "
        "watch you. They are gone before you've quite decided what to make of them."
    ),
    (
        "Something changes in the quality of the air before you see them. "
        "|wVesper|n, opalescent and unhurried, stands at a distance that is just "
        "slightly too close to be casual. Their horns catch light in ways that "
        "don't entirely make sense. They extend the Ogram. Their expression "
        "suggests they are thinking something very specific and will not be "
        "sharing it."
    ),
]

_MESSENGERS = {
    "feminine":  ("Seraphine", _SERAPHINE_ARRIVALS),
    "masculine": ("Calix",     _CALIX_ARRIVALS),
    "neutral":   ("Vesper",    _VESPER_ARRIVALS),
}


def _get_messenger(gender):
    """Return (name, arrival_line) for the given gender key."""
    name, arrivals = _MESSENGERS.get(gender, _MESSENGERS["neutral"])
    return name, random.choice(arrivals)


def _get_pronouns(recipient_object_id):
    """
    Look up a character's stored pronouns by ObjectDB pk.
    Returns a dict with subject/object/possessive/reflexive keys.
    Falls back to they/them if anything goes wrong.
    """
    defaults = {
        "subject":   "they",
        "object":    "them",
        "possessive": "their",
        "reflexive": "themselves",
    }
    try:
        from evennia.objects.models import ObjectDB
        char = ObjectDB.objects.get(pk=recipient_object_id)
        p = char.db.pronouns or {}
        return {
            "subject":    p.get("subject",        defaults["subject"]),
            "object":     p.get("object",         defaults["object"]),
            "possessive": p.get("possessive_adj", defaults["possessive"]),
            "reflexive":  p.get("reflexive",      defaults["reflexive"]),
        }
    except Exception:
        return defaults


# ------------------------------------------------------------------ #
# Affection delivery lines
# Each entry is a list of variants; one is chosen at random.
# Placeholders: {name} messenger name, {sender} sender display,
#   {obj} object pronoun, {poss} possessive adj, {subj} subject,
#   {refl} reflexive
# ------------------------------------------------------------------ #

_AFFECTION_LINES = {
    "kiss": [
        "{name} leans close — closer than strictly professional — and presses a "
        "soft, deliberate kiss to your lips. |xFrom {sender}.|n",

        "{name} cups your chin briefly, tilts your face, and presses a quiet "
        "kiss to your mouth — unhurried, certain. |xFrom {sender}.|n",

        "Without preamble, {name} leans in and leaves a soft kiss at the corner "
        "of your lips, then straightens as though nothing of note has occurred. "
        "|xFrom {sender}.|n",
    ],
    "french_kiss": [
        "{name} steps close — too close — and takes your face in both hands. "
        "The kiss that follows is deep and unhurried, and holds far longer than "
        "strictly necessary. You are left to collect yourself afterward. "
        "|xFrom {sender}, with intent.|n",

        "{name} draws you in without asking, one hand at your jaw, and kisses "
        "you slowly and thoroughly — the kind that carries a message of its own. "
        "|xFrom {sender}.|n",

        "There is very little warning before {name} pulls you forward by the "
        "collar of whatever you happen to be wearing and kisses you with the "
        "focused attention of someone who intends to be remembered. "
        "|xFrom {sender}.|n",
    ],
    "hug": [
        "{name} steps forward without ceremony and pulls you into a firm, "
        "warm embrace — the kind that holds rather than simply greets. "
        "|xFrom {sender}.|n",

        "Without explaining themselves, {name} wraps their arms around you "
        "and holds on for exactly as long as seems right. Then lets go. "
        "|xFrom {sender}.|n",

        "{name} opens both arms and simply waits. When you step in — or are "
        "gently drawn in — the hug is thorough and unambiguous. "
        "|xFrom {sender}.|n",
    ],
    "grope": [
        "{name} finds you with hands that are deliberate and entirely unhurried, "
        "learning the shape of you without apology — a study conducted on someone "
        "else's behalf. |xFrom {sender}.|n",

        "{name}'s hands settle at your waist first, then move with considered "
        "purpose — the kind of attention that knows exactly where it's going. "
        "|xFrom {sender}, who clearly wanted you to know you were being thought of.|n",

        "What {name} does next is thorough. Every place that catches breath gets "
        "a moment's attention, and then {name} steps back with the composure of "
        "someone who has done their job well. |xFrom {sender}.|n",
    ],
}


# ------------------------------------------------------------------ #
# EvMenu node functions
# All must be at module level so EvMenu can find them by name.
# ------------------------------------------------------------------ #

_SEP   = "|x" + "─" * 44 + "|n"
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
            "desc": "|wAffection|n — a kiss, embrace, or something more",
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
    """Step 1b — choose affection subtype."""
    draft = caller.db._ogram_draft or {}
    target = draft.get("target_name", "someone")

    text = (
        f"{_SEP}\n"
        f"{_TITLE}  |w→ {target}|n  |x[Affection]|n\n"
        f"{_SEP}\n\n"
        f"What are you sending?\n"
    )
    options = [
        {
            "key": ("1", "kiss"),
            "desc": "|wA soft kiss|n",
            "goto": (_set_affection, {"affection_type": "kiss"}),
        },
        {
            "key": ("2", "french", "french_kiss", "deep"),
            "desc": "|wA deep, passionate kiss|n",
            "goto": (_set_affection, {"affection_type": "french_kiss"}),
        },
        {
            "key": ("3", "hug", "embrace"),
            "desc": "|wA warm hug|n",
            "goto": (_set_affection, {"affection_type": "hug"}),
        },
        {
            "key": ("4", "grope", "hands"),
            "desc": "|wWandering hands|n",
            "goto": (_set_affection, {"affection_type": "grope"}),
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
            "desc": "|wSigned|n — the recipient will know it came from you",
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
    """Step 3 — choose messenger (courier)."""
    draft = caller.db._ogram_draft or {}
    target = draft.get("target_name", "someone")
    type_label = _type_label(draft.get("type", "message"))
    anon_label = "Anonymous" if draft.get("anonymous") else f"from {draft.get('sender_display', 'you')}"

    text = (
        f"{_SEP}\n"
        f"{_TITLE}  |w→ {target}|n  |x[{type_label} · {anon_label}]|n\n"
        f"{_SEP}\n\n"
        f"Who carries your Ogram?\n\n"
        f"  |w1.|n |wSeraphine|n  — crimson-skinned, swept-back horns. Warm, knowing, discreet.\n"
        f"  |w2.|n |wCalix|n      — charcoal-dark, ram horns. Few words. Absolute reliability.\n"
        f"  |w3.|n |wVesper|n     — opalescent, ambiguous. Eyes that change color. Speaks rarely.\n"
    )
    options = [
        {
            "key": ("1", "seraphine", "feminine", "female", "f"),
            "desc": "Seraphine",
            "goto": (_set_gender, {"gender": "feminine"}),
        },
        {
            "key": ("2", "calix", "masculine", "male", "m"),
            "desc": "Calix",
            "goto": (_set_gender, {"gender": "masculine"}),
        },
        {
            "key": ("3", "vesper", "neutral", "androgynous", "n"),
            "desc": "Vesper",
            "goto": (_set_gender, {"gender": "neutral"}),
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
    """Step 4 — compose body or confirm (for affections)."""
    draft = caller.db._ogram_draft or {}
    target = draft.get("target_name", "someone")
    type_label = _type_label(draft.get("type", "message"))
    anon_label = "Anonymous" if draft.get("anonymous") else f"from {draft.get('sender_display', 'you')}"
    messenger_name = {
        "feminine":  "Seraphine",
        "masculine": "Calix",
        "neutral":   "Vesper",
    }.get(draft.get("gender", "neutral"), "Vesper")

    text = (
        f"{_SEP}\n"
        f"{_TITLE}  |w→ {target}|n\n"
        f"{_SEP}\n"
        f"  Type:      {type_label}\n"
        f"  Sender:    {anon_label}\n"
        f"  Messenger: {messenger_name}\n"
        f"{_SEP}\n"
    )

    if draft.get("type") == "affection":
        aff_labels = {
            "kiss":        "a soft kiss",
            "french_kiss": "a deep, passionate kiss",
            "hug":         "a warm hug",
            "grope":       "wandering hands",
        }
        aff_display = aff_labels.get(draft.get("affection_type", "kiss"), "an affection")
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
# Goto callbacks — set state, return next node name
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
    Called when :done is pressed in the editor, or send-no-body chosen.
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

    messenger_name = {
        "feminine":  "Seraphine",
        "masculine": "Calix",
        "neutral":   "Vesper",
    }.get(draft.get("gender", "neutral"), "Vesper")

    msg = OgramMessage(
        sender_object_id     = caller.id,
        sender_name          = caller.db.rp_name or caller.key,
        sender_account_id    = caller.account.id if caller.account else None,
        anonymous            = draft.get("anonymous", False),
        recipient_object_id  = draft.get("target_id"),
        recipient_name       = target_name,
        recipient_account_id = draft.get("target_account_id"),
        msg_type             = draft.get("type", "message"),
        affection_type       = draft.get("affection_type", ""),
        messenger_gender     = draft.get("gender", "neutral"),
        subject              = draft.get("subject", ""),
        body                 = body.strip(),
    )
    msg.save()

    caller.db._ogram_draft = None

    caller.msg(
        f"\n|m✦ Ogram sealed.|n\n"
        f"|x{messenger_name} will carry it. "
        f"|w{target_name}|n|x will receive it upon their next login.|n"
    )

    _send_email_notification(msg)


def _send_email_notification(msg):
    """
    If the recipient account has email alerts enabled, send a brief notification.
    Silently skips on any error.
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
        email  = acct.email
        alerts = getattr(acct.db, "email_alerts", False)
        if not email or not alerts:
            return

        sender_display = "Anonymous" if msg.anonymous else (msg.sender_name or "Someone")
        send_mail(
            subject=f"[Re:Void] You have an Ogram from {sender_display}",
            message=(
                f"An Ogram has arrived for {msg.recipient_name}.\n\n"
                f"It will be waiting for you the next time you log in.\n\n— Re:Void"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@revoid.game"),
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        pass


def deliver_ograms(account):
    """
    Called from Account.at_post_login. Finds all undelivered Ograms for
    any character belonging to this account and delivers them.

    Args:
        account: The Evennia AccountDB instance logging in.
    """
    try:
        from web.mail.models import OgramMessage
        from django.utils import timezone
    except ImportError:
        return

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
    count = pending.count()
    lines = [
        f"\n{sep}",
        f"|m✦ {'An Ogram has' if count == 1 else f'{count} Ograms have'} arrived.|n",
        sep,
    ]

    for msg in pending:
        lines.append("")
        lines.append(_format_delivery(msg))

    lines.append("")
    lines.append("|x(Your full mailbox is available on the website.)|n")
    lines.append(sep)

    account.msg("\n".join(lines))
    pending.update(delivered_at=timezone.now())


def _format_delivery(msg):
    """
    Format a single OgramMessage for in-game delivery.
    Uses messenger triplet arrival lines and recipient pronouns.
    """
    name, arrival = _get_messenger(msg.messenger_gender)
    sender = "an anonymous sender" if msg.anonymous else (msg.sender_name or "an unknown sender")

    header = arrival

    if msg.msg_type == "message":
        action = f"|x{name} produces a sealed message and places it in your hands.|n"
        body   = f'\n\n|x"|n{msg.body}|x"|n' if msg.body else ""
        return f"{header}\n{action}{body}"

    elif msg.msg_type == "emote":
        action = f"|x{name}, acting on behalf of {sender}:|n"
        body   = f"\n{msg.body}" if msg.body else ""
        return f"{header}\n{action}{body}"

    elif msg.msg_type == "affection":
        variants = _AFFECTION_LINES.get(msg.affection_type, _AFFECTION_LINES["kiss"])
        action_template = random.choice(variants)
        action = action_template.format(name=name, sender=sender)
        note = f'\n\n|x"|n{msg.body}|x"|n' if msg.body else ""
        return f"{header}\n\n{action}{note}"

    elif msg.msg_type == "invite":
        action = f"|x{name} presents a formal invitation from {sender}:|n"
        body   = f"\n{msg.body}" if msg.body else ""
        return f"{header}\n{action}{body}"

    else:
        return f"{header}\n|xFrom {sender}:|n\n{msg.body}"


# ------------------------------------------------------------------ #
# The command
# ------------------------------------------------------------------ #

class CmdOgram(MuxCommand):
    """
    Send an offline message to another character.

    An Ogram is a sealed message delivered to the recipient the next time
    they log in. You may send a written message, an emote, an affection,
    or a formal realm invitation. Choose whether to sign it or remain
    anonymous, and select one of three couriers to carry it.

    The couriers are a set of tiefling triplets:
      Seraphine — feminine, crimson, warm and knowing
      Calix     — masculine, charcoal, few words, absolute discretion
      Vesper    — ambiguous, opalescent, eyes that change color

    Usage:
        ogram <character>
        og <character>
    """

    key      = "ogram"
    aliases  = ["og"]
    locks    = "cmd:all()"
    help_category = "Communication"

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("Usage: ogram <character name>")
            return

        target_name = self.args.strip()

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

        target_account = getattr(target, "account", None)

        caller.db._ogram_draft = {
            "target_id":          target.id,
            "target_name":        target.db.rp_name or target.key,
            "target_account_id":  target_account.id if target_account else None,
            "sender_display":     caller.db.rp_name or caller.key,
            "type":               None,
            "affection_type":     "",
            "anonymous":          False,
            "gender":             "neutral",
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
