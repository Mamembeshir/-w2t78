import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawling", "0003_crawlsource_honor_local_crawl_delay"),
    ]

    operations = [
        migrations.CreateModel(
            name="CrawledProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("page_url", models.CharField(max_length=2000)),
                ("raw_payload", models.JSONField()),
                ("checksum", models.CharField(db_index=True, max_length=64)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="products",
                        to="crawling.crawlsource",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="products",
                        to="crawling.crawltask",
                    ),
                ),
            ],
            options={
                "db_table": "crawling_product",
                "indexes": [
                    models.Index(fields=["source", "-created_at"], name="crawling_pr_source_i_idx"),
                ],
            },
        ),
    ]
