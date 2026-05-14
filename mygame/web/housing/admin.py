from django.contrib import admin
from .models import HousingPlot


@admin.register(HousingPlot)
class HousingPlotAdmin(admin.ModelAdmin):
    list_display = (
        "character_id", "rooms_total", "rooms_used",
        "rooms_available_display", "created_at",
    )
    list_filter = ()
    search_fields = ("character_id",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Available")
    def rooms_available_display(self, obj):
        return obj.rooms_available
