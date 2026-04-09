from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_phase5_cycle_count_safety_stock"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="barcode",
            field=models.CharField(blank=True, db_index=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="item",
            name="rfid_tag",
            field=models.CharField(blank=True, db_index=True, default="", max_length=150),
        ),
    ]
