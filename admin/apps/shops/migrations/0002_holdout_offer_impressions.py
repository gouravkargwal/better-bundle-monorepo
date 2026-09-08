"""
Migration to add holdout_disabled to shops and create offer_impressions table.
IMPORTANT: This matches the SQL migration run by the Python worker.
Django should NOT own these tables — they already exist.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shops", "0001_initial"),
    ]

    operations = [
        # Add holdout_disabled column to shops
        migrations.AddField(
            model_name="shop",
            name="holdout_disabled",
            field=models.BooleanField(default=False),
        ),
    ]
