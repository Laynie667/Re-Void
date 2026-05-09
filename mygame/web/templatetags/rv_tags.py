"""
Re:Void custom template tags.
Load in templates with: {% load rv_tags %}
"""

from django import template

register = template.Library()


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
