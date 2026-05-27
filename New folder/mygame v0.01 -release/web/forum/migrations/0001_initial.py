from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ForumCategory",
            fields=[
                ("id",              models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name",            models.CharField(max_length=100)),
                ("slug",            models.SlugField(unique=True)),
                ("description",     models.CharField(blank=True, max_length=300)),
                ("icon",            models.CharField(default="✦", max_length=10)),
                ("staff_only_post", models.BooleanField(default=False, help_text="Only staff may create threads or reply in this category.")),
                ("order",           models.PositiveIntegerField(default=0)),
            ],
            options={"ordering": ["order"], "verbose_name": "category", "verbose_name_plural": "categories"},
        ),
        migrations.CreateModel(
            name="ForumThread",
            fields=[
                ("id",                models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title",             models.CharField(max_length=200)),
                ("author_account_id", models.IntegerField()),
                ("author_name",       models.CharField(max_length=80)),
                ("created_at",        models.DateTimeField(auto_now_add=True)),
                ("updated_at",        models.DateTimeField(auto_now=True)),
                ("pinned",            models.BooleanField(default=False)),
                ("locked",            models.BooleanField(default=False)),
                ("category",          models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="threads", to="forum.forumcategory")),
            ],
            options={"ordering": ["-pinned", "-updated_at"]},
        ),
        migrations.CreateModel(
            name="ForumPost",
            fields=[
                ("id",                models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("author_account_id", models.IntegerField()),
                ("author_name",       models.CharField(max_length=80)),
                ("body",              models.TextField()),
                ("created_at",        models.DateTimeField(auto_now_add=True)),
                ("edited_at",         models.DateTimeField(blank=True, null=True)),
                ("is_deleted",        models.BooleanField(default=False)),
                ("thread",            models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="posts", to="forum.forumthread")),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]
