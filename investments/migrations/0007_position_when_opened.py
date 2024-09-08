# Generated by Django 5.1.1 on 2024-09-08 01:21

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("investments", "0006_alter_position_base_quantity"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="when_opened",
            field=models.DateField(
                blank=True, null=True, verbose_name="When was this option opened"
            ),
        ),
    ]
