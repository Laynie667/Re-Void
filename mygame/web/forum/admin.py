from django.contrib import admin

from .models import ForumCategory, ForumPost, ForumThread


@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    list_display  = ("order", "icon", "name", "slug", "staff_only_post")
    list_editable = ("order", "staff_only_post")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ForumThread)
class ForumThreadAdmin(admin.ModelAdmin):
    list_display  = ("title", "category", "author_name", "created_at", "pinned", "locked")
    list_editable = ("pinned", "locked")
    list_filter   = ("category", "pinned", "locked")
    search_fields = ("title", "author_name")


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display  = ("__str__", "created_at", "edited_at", "is_deleted")
    list_filter   = ("is_deleted",)
    search_fields = ("author_name", "body")
