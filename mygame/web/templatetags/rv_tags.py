"""
Re:Void custom template tags.
Load in templates with: {% load rv_tags %}
"""

import re
from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape, linebreaks

register = template.Library()

# Strip Evennia |X color/markup codes from a string.
# Handles: |r |g |b |y |m |c |w |x |n |R |G |B |Y |M |C |W |X
#          |/ (newline markup) |- (blank line) |_ (space) || (literal pipe)
#          |[X (background) |=a-z (greyscale) |000-|555 (xterm256)
_EVENNIA_MARKUP_RE = re.compile(
    r'\|\|'             # literal pipe (replace with | below)
    r'|\|[rgybmcwxnRGYBMCWXN]'    # basic colors
    r'|\|\[[rgybmcwxRGYBMCWX]\]?' # background colors
    r'|\|=[a-zA-Z]'    # greyscale
    r'|\|[0-5]{3}'     # xterm256
    r'|\|!'             # bright background prefix
    r'|\|h'             # bold prefix
    r'|\|u'             # underline prefix
    r'|\|i'             # italic prefix
    r'|\|s'             # strikethrough prefix
    r'|\|_'             # space
)


def _web_clean(text):
    """
    Convert Evennia in-game markup to clean text suitable for HTML rendering.

    - |- → paragraph break (blank line)
    - |/ → line break
    - || → literal |
    - All other |X codes → stripped
    """
    if not text:
        return ""
    # Handle structural markup first
    text = text.replace("|-", "\n\n")
    text = text.replace("|/", "\n")
    text = text.replace("||", "\x00PIPE\x00")  # protect literal pipes
    # Strip color/style codes
    text = _EVENNIA_MARKUP_RE.sub("", text)
    # Restore literal pipes
    text = text.replace("\x00PIPE\x00", "|")
    return text.strip()


@register.simple_tag
def render_zones(text, character):
    """
    Resolve {zone:X} tokens in text using the character's current zone
    states, then strip Evennia color markup and return safe HTML.

    Usage in template:
        {% load rv_tags %}
        {% render_zones object.db.physical_desc object as rendered_desc %}
        {{ rendered_desc }}
    """
    if not text or not character:
        return mark_safe("")
    try:
        from world.freeform_manager import render_zone_tokens
        resolved = render_zone_tokens(text, character)
    except Exception:
        resolved = text

    clean = _web_clean(resolved)
    # linebreaks converts \n\n → <p> blocks, \n → <br>
    return mark_safe(linebreaks(escape(clean)))


@register.simple_tag
def rv_connected_count():
    """Return the number of accounts currently connected."""
    try:
        from evennia import SESSION_HANDLER
        sessions = SESSION_HANDLER.get_sessions()
        unique = set()
        for sess in sessions:
            if sess.account:
                unique.add(sess.account.pk)
        return len(unique)
    except Exception:
        return 0


@register.simple_tag
def rv_active_scenes():
    """Return the number of rooms that currently contain at least one character."""
    try:
        from django.conf import settings
        from evennia.objects.models import ObjectDB

        char_path = settings.BASE_CHARACTER_TYPECLASS
        room_path = settings.BASE_ROOM_TYPECLASS

        # Location IDs of all placed characters
        occupied = (
            ObjectDB.objects
            .filter(db_typeclass_path=char_path)
            .exclude(db_location__isnull=True)
            .values_list("db_location_id", flat=True)
            .distinct()
        )
        # Count how many of those locations are rooms
        return ObjectDB.objects.filter(
            db_typeclass_path=room_path,
            pk__in=list(occupied)
        ).count()
    except Exception:
        return 0
