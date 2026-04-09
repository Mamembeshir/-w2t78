"""
Add SystemSettings singleton for SMTP/SMS gateway configuration.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemSettings",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("smtp_host", models.CharField(blank=True, max_length=253)),
                ("smtp_port", models.PositiveSmallIntegerField(default=25)),
                ("smtp_use_tls", models.BooleanField(default=False)),
                ("sms_gateway_url", models.CharField(blank=True, max_length=500)),
            ],
            options={
                "db_table": "notifications_system_settings",
            },
        ),
    ]
