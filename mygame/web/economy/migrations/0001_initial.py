from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ShardTransaction",
            fields=[
                ("id",           models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sender_id",    models.IntegerField(blank=True, db_index=True, null=True)),
                ("recipient_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("amount",       models.IntegerField()),
                ("reason",       models.CharField(
                    choices=[
                        ("passive",         "Passive income"),
                        ("active_rp",       "Active RP income"),
                        ("daily_allowance", "Daily allowance"),
                        ("tip",             "Player tip"),
                        ("pay",             "Player payment"),
                        ("purchase",        "Shop purchase"),
                        ("staff_grant",     "Staff grant"),
                        ("staff_deduct",    "Staff deduction"),
                        ("other",           "Other"),
                    ],
                    default="other",
                    max_length=32,
                )),
                ("note",         models.CharField(blank=True, max_length=200)),
                ("created_at",   models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
