"""
Re:Void custom template tags.
Load in templates with: {% load rv_tags %}
"""

import re
from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()

# Evennia |X color/style codes — compiled once at module load.
# Handles basic colors, backgrounds, greyscale, xterm256, and style codes.
_EVENNIA_MARKUP_RE = re.compile(
    r'\|[rgybmcwxnRGYBMCWXN]'   # basic colors + reset
    r'|\|\[[rgybmcwxRGYBMCWX]\]?'  # background colors
    r'|\|=[a-zA-Z]'              # greyscale
    r'|\|[0-5][0-5][0-5]'       # xterm256 (three digits 0-5)
    r'|\|[!huis_]'               # style codes + space
)


def _web_clean(text):
    """
    Convert Evennia in-game markup to plain text for HTML rendering.

      |-   → paragraph break (double newline)
      |/   → line break (single newline)
      ||   → literal pipe character
      |X   → stripped (color/style codes)
    """
    if not text:
        return ""
    text = str(text)
    # Structural markup first
    text = text.replace("|-", "\n\n")
    text = text.replace("|/", "\n")
    # Protect literal pipes before stripping other codes
    text = text.replace("||", "\x00PIPE\x00")
    # Strip color/style codes
    text = _EVENNIA_MARKUP_RE.sub("", text)
    # Restore literal pipes
    text = text.replace("\x00PIPE\x00", "|")
    return text.strip()


def _to_html(clean_text):
    """
    Convert plain text (with real newlines) to safe HTML.
    Double newlines → <p> paragraphs, single newlines → <br>.
    """
    escaped = escape(clean_text)
    paragraphs = re.split(r'\n{2,}', escaped)
    html_paras = []
    for para in paragraphs:
        para = para.replace('\n', '<br>')
        if para.strip():
            html_paras.append(f'<p>{para}</p>')
    return '\n'.join(html_paras)


@register.simple_tag
def render_zones(text, character):
    """
    Resolve {zone:X} tokens in text using the character's current zone
    states, strip Evennia color markup, and return safe HTML.

    Usage in template:
        {% load rv_tags %}
        {% render_zones object.db.physical_desc object as rendered_desc %}
        {{ rendered_desc }}
    """
    if not text or not character:
        return mark_safe("")

    # Resolve zone tokens
    try:
        from world.freeform_manager import render_zone_tokens
        resolved = render_zone_tokens(text, character)
    except Exception:
        resolved = text

    # Clean markup and convert to HTML
    try:
        clean = _web_clean(resolved)
        html = _to_html(clean)
        return mark_safe(html)
    except Exception:
        # Last resort: just escape and return raw
        return mark_safe(f"<p>{escape(str(resolved))}</p>")


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
