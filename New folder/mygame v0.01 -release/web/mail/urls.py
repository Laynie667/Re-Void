"""
web/mail/urls.py — Ogram mailbox URL patterns.
"""

from django.urls import path
from django.views.generic import TemplateView

from .views import (
    InboxView,
    OutboxView,
    MessageDetailView,
    DeleteMessageView,
    ComposeView,
    StaffContactView,
)

urlpatterns = [
    path("inbox/",              InboxView.as_view(),         name="mail-inbox"),
    path("outbox/",             OutboxView.as_view(),        name="mail-outbox"),
    path("compose/",            ComposeView.as_view(),       name="mail-compose"),
    path("<int:pk>/",           MessageDetailView.as_view(), name="mail-detail"),
    path("<int:pk>/delete/",    DeleteMessageView.as_view(), name="mail-delete"),
]
