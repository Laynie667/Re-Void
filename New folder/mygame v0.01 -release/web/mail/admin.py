from django.contrib import admin
from .models import OgramMessage


@admin.register(OgramMessage)
class OgramMessageAdmin(admin.ModelAdmin):
    list_display  = (
        "sent_at", "sender_name", "recipient_name",
        "msg_type", "anonymous", "is_delivered", "is_read",
    )
    list_filter   = ("msg_type", "anonymous", "messenger_gender")
    search_fields = ("sender_name", "recipient_name", "body", "subject")
    readonly_fields = (
        "sent_at", "delivered_at", "read_at",
        "sender_object_id", "sender_account_id",
        "recipient_object_id", "recipient_account_id",
    )
    ordering = ("-sent_at",)
