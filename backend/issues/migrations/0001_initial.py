# Generated manually — move Customer/Issue models from core without recreating tables.

from django.db import migrations, models
import django.db.models.deletion


def forwards_contenttypes(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model in ("customer", "issue", "issueupdate", "nextaction"):
        ContentType.objects.filter(app_label="core", model=model).update(
            app_label="issues"
        )


def backwards_contenttypes(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model in ("customer", "issue", "issueupdate", "nextaction"):
        ContentType.objects.filter(app_label="issues", model=model).update(
            app_label="core"
        )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Customer",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("name", models.CharField(max_length=255, unique=True)),
                        ("industry", models.CharField(blank=True, max_length=120)),
                        ("tier", models.CharField(default="standard", max_length=40)),
                        ("account_owner", models.CharField(blank=True, max_length=120)),
                        (
                            "contact_email",
                            models.EmailField(blank=True, max_length=254),
                        ),
                        ("notes", models.TextField(blank=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        "db_table": "core_customer",
                        "ordering": ["name"],
                    },
                ),
                migrations.CreateModel(
                    name="Issue",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("title", models.CharField(max_length=255)),
                        ("description", models.TextField(blank=True)),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("open", "Open"),
                                    ("in_progress", "In progress"),
                                    ("resolved", "Resolved"),
                                    ("closed", "Closed"),
                                ],
                                db_index=True,
                                default="open",
                                max_length=32,
                            ),
                        ),
                        (
                            "priority",
                            models.CharField(
                                choices=[
                                    ("low", "Low"),
                                    ("medium", "Medium"),
                                    ("high", "High"),
                                    ("critical", "Critical"),
                                ],
                                default="medium",
                                max_length=32,
                            ),
                        ),
                        (
                            "assigned_to",
                            models.CharField(db_index=True, max_length=120),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "customer",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="issues",
                                to="issues.customer",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "core_issue",
                        "ordering": ["-updated_at"],
                    },
                ),
                migrations.CreateModel(
                    name="NextAction",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("summary", models.TextField()),
                        ("recommended_by", models.CharField(max_length=120)),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("pending", "Pending"),
                                    ("done", "Done"),
                                    ("cancelled", "Cancelled"),
                                ],
                                default="pending",
                                max_length=32,
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "issue",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="next_actions",
                                to="issues.issue",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "core_nextaction",
                        "ordering": ["-created_at"],
                    },
                ),
                migrations.CreateModel(
                    name="IssueUpdate",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("author", models.CharField(max_length=120)),
                        ("body", models.TextField()),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "issue",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="updates",
                                to="issues.issue",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "core_issueupdate",
                        "ordering": ["created_at"],
                    },
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(forwards_contenttypes, backwards_contenttypes),
    ]
