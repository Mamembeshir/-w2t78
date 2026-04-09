from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawling", "0002_phase6_waiting_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="crawlsource",
            name="honor_local_crawl_delay",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "When enabled, the worker respects crawl_delay_seconds from the "
                    "local ruleset between page requests (CLAUDE.md §9)."
                ),
            ),
        ),
    ]
