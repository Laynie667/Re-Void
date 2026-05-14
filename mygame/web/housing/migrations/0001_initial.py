from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="HousingPlot",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "character_id",
                    models.IntegerField(
                        db_index=True,
                        help_text="ObjectDB pk of the owning character.",
                        unique=True,
                    ),
                ),
                (
                    "rooms_total",
                    models.IntegerField(
                        default=1,
                        help_text="Total room slots purchased.",
                    ),
                ),
                (
                    "rooms_used",
                    models.IntegerField(
                        default=1,
                        help_text="Room slots consumed by created rooms.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["character_id"]},
        ),
    ]
