from django.contrib import admin
from .models import NewsPost


@admin.register(NewsPost)
class NewsPostAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "published")
    list_filter = ("published",)
    list_editable = ("published",)
    ordering = ("-date",)
    date_hierarchy = "date"
    search_fields = ("title", "body")
    fieldsets = (
        (None, {
            "fields": ("title", "date", "body", "published"),
        }),
    )
