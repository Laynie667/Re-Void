"""
Re:Void — website URL routing.

Pages that are not yet built resolve to the TBI (to-be-implemented) view.
Add proper views here as features are built out.
"""

from django.urls import path, include
from django.views.generic import TemplateView

from evennia.web.website.urls import urlpatterns as evennia_website_urlpatterns
from web.views import ReVoidIndexView
from web.mail.views import StaffContactView

# ---------------------------------------------------------------------------
# Placeholder view — shows the "coming soon" TBI page
# ---------------------------------------------------------------------------
tbi = TemplateView.as_view(template_name="website/tbi.html")

urlpatterns = [
    # ── Homepage ───────────────────────────────────────────────────────────
    path("", ReVoidIndexView.as_view(), name="index"),

    # ── Planned pages (TBI) ────────────────────────────────────────────────
    path("lore/",     tbi, name="lore"),
    path("factions/", tbi, name="factions"),
    path("forums/",   tbi, name="forums"),
    path("wiki/",     tbi, name="wiki"),
    path("guide/",    tbi, name="guide"),
    path("discord/",  tbi, name="discord"),

    # ── Ogram mailbox ──────────────────────────────────────────────────────
    path("mail/", include("web.mail.urls")),

    # ── Staff contact ──────────────────────────────────────────────────────
    path("contact/", StaffContactView.as_view(), name="contact"),
    path(
        "contact/thanks/",
        TemplateView.as_view(template_name="website/mail/contact_thanks.html"),
        name="contact-thanks",
    ),

    # ── Future real views go here ──────────────────────────────────────────
    # path("lore/", views.LoreView.as_view(), name="lore"),
]

# Evennia's default patterns (characters, registration, webclient, etc.)
urlpatterns = urlpatterns + evennia_website_urlpatterns
