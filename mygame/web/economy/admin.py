from django.contrib import admin
from .models import ShardTransaction


@admin.register(ShardTransaction)
class ShardTransactionAdmin(admin.ModelAdmin):
    list_display  = ("created_at", "sender_id", "recipient_id", "amount", "reason", "note")
    list_filter   = ("reason",)
    search_fields = ("sender_id", "recipient_id", "note")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
