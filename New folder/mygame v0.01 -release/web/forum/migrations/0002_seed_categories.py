"""
Data migration — seeds the initial forum categories.
"""

from django.db import migrations

CATEGORIES = [
    {
        "name":            "Announcements",
        "slug":            "announcements",
        "description":     "Official news, updates, and events from staff. Read-only for players.",
        "icon":            "✦",
        "staff_only_post": True,
        "order":           0,
    },
    {
        "name":            "General OOC",
        "slug":            "general",
        "description":     "Out-of-character chat, introductions, and general discussion.",
        "icon":            "◈",
        "staff_only_post": False,
        "order":           1,
    },
    {
        "name":            "Lore & Worldbuilding",
        "slug":            "lore",
        "description":     "Discuss the world, factions, history, and lore of Re:Void.",
        "icon":            "◇",
        "staff_only_post": False,
        "order":           2,
    },
    {
        "name":            "Character Boards",
        "slug":            "characters",
        "description":     "IC journals, character stories, and personal development threads.",
        "icon":            "✧",
        "staff_only_post": False,
        "order":           3,
    },
    {
        "name":            "Bug Reports & Requests",
        "slug":            "bugs",
        "description":     "Found something broken? Have a feature request? Post it here.",
        "icon":            "⚙",
        "staff_only_post": False,
        "order":           4,
    },
]


def seed_categories(apps, schema_editor):
    ForumCategory = apps.get_model("forum", "ForumCategory")
    for cat in CATEGORIES:
        ForumCategory.objects.get_or_create(slug=cat["slug"], defaults=cat)


def unseed_categories(apps, schema_editor):
    ForumCategory = apps.get_model("forum", "ForumCategory")
    slugs = [c["slug"] for c in CATEGORIES]
    ForumCategory.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("forum", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
