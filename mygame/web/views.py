"""
Custom web views for Re:Void.

Uses Django's TemplateView directly rather than subclassing Evennia's IndexView,
so we're not tied to Evennia's internal module structure.

Evennia's context processors already inject: account, puppet, webclient_enabled,
register_enabled, rest_api_enabled into every template automatically.
We just add the homepage-specific stats and news posts here.
"""

from django.views.generic import TemplateView
from evennia.objects.models import ObjectDB
from django.conf import settings


class ReVoidIndexView(TemplateView):
    template_name = "website/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # --- Players currently online ---
        try:
            from evennia import SESSION_HANDLER
            sessions = SESSION_HANDLER.get_sessions()
            connected_accounts = set()
            for sess in sessions:
                if sess.account:
                    connected_accounts.add(sess.account.pk)
            context["num_accounts_connected"] = len(connected_accounts)
        except Exception:
            context["num_accounts_connected"] = 0

        # --- Total characters ---
        try:
            char_path = settings.BASE_CHARACTER_TYPECLASS
            context["num_characters"] = ObjectDB.objects.filter(
                db_typeclass_path=char_path
            ).count()
        except Exception:
            context["num_characters"] = 0

        # --- Total rooms ---
        try:
            room_path = settings.BASE_ROOM_TYPECLASS
            context["num_rooms"] = ObjectDB.objects.filter(
                db_typeclass_path=room_path
            ).count()
        except Exception:
            context["num_rooms"] = 0

        # --- News posts ---
        try:
            from web.news.models import NewsPost
            context["news_posts"] = NewsPost.objects.filter(published=True)[:6]
        except Exception:
            context["news_posts"] = []

        return context
