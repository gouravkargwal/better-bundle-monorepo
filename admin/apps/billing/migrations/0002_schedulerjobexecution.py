"""Generated migration for SchedulerJobExecution model"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Create scheduler_job_executions table for tracking cron job runs"""

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchedulerJobExecution",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        primary_key=True, serialize=False
                    ),
                ),
                (
                    "job_name",
                    models.CharField(db_index=True, max_length=100),
                ),
                (
                    "job_group",
                    models.CharField(
                        db_index=True, max_length=100, null=True, blank=True
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
                ("duration_ms", models.IntegerField(null=True, blank=True)),
                (
                    "status",
                    models.CharField(
                        db_index=True,
                        default="RUNNING",
                        max_length=20,
                    ),
                ),
                ("success", models.BooleanField(null=True)),
                ("result_summary", models.TextField(null=True, blank=True)),
                ("error_message", models.TextField(null=True, blank=True)),
                ("error_details", models.TextField(null=True, blank=True)),
                (
                    "triggered_by",
                    models.CharField(
                        default="scheduled", max_length=20
                    ),
                ),
                (
                    "attempt_number",
                    models.IntegerField(default=1),
                ),
                (
                    "items_processed",
                    models.IntegerField(null=True, blank=True),
                ),
                (
                    "metadata_json",
                    models.JSONField(null=True, blank=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "scheduler_job_executions",
                "ordering": ["-started_at"],
                "verbose_name": "Job Execution",
                "verbose_name_plural": "Job Executions",
            },
        ),
    ]
