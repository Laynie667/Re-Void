from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="OgramMessage",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("sender_object_id",    models.IntegerField(blank=True, null=True)),
                ("sender_name",         models.CharField(blank=True, max_length=80)),
                ("sender_account_id",   models.IntegerField(blank=True, null=True)),
                ("sender_email",        models.EmailField(blank=True)),
                ("anonymous",           models.BooleanField(default=False)),
                ("recipient_object_id", models.IntegerField(blank=True, null=True)),
                ("recipient_name",      models.CharField(blank=True, max_length=80)),
                ("recipient_account_id", models.IntegerField(blank=True, null=True)),
                ("msg_type", models.CharField(
                    choices=[
                        ("message",   "Message"),
                        ("emote",     "Emote / Pose"),
                        ("affection", "Affection"),
                        ("invite",    "Realm Invitation"),
                        ("staff",     "Staff Contact"),
                    ],
                    default="message",
                    max_length=20,
                )),
                ("affection_type", models.CharField(
                    blank=True,
                    choices=[
                        ("kiss",     "A gentle kiss"),
                        ("embrace",  "A warm embrace"),
                        ("intimate", "Something more intimate"),
                    ],
                    max_length=20,
                )),
                ("messenger_gender", models.CharField(
                    choices=[
                        ("neutral",   "Neutral / Androgynous"),
                        ("feminine",  "Feminine"),
                        ("masculine", "Masculine"),
                    ],
                    default="neutral",
                    max_length=20,
                )),
                ("subject",      models.CharField(blank=True, max_length=200)),
                ("body",         models.TextField(blank=True)),
                ("sent_at",      models.DateTimeField(auto_now_add=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("read_at",      models.DateTimeField(blank=True, null=True)),
                ("deleted_by_sender",    models.BooleanField(default=False)),
                ("deleted_by_recipient", models.BooleanField(default=False)),
            ],
            options={
                "app_label": "ogram",
                "ordering": ["-sent_at"],
                "verbose_name": "Ogram Message",
                "verbose_name_plural": "Ogram Messages",
            },
        ),
    ]
