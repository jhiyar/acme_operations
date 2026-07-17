# Generated manually — drop issue models from core state (tables kept by issues app).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("issues", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="IssueUpdate"),
                migrations.DeleteModel(name="NextAction"),
                migrations.DeleteModel(name="Issue"),
                migrations.DeleteModel(name="Customer"),
            ],
            database_operations=[],
        ),
    ]
