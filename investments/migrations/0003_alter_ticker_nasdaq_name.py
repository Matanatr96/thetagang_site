# Generated by Django 5.1.1 on 2024-09-08 07:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("investments", "0002_option_live_pl_alter_option_num_open_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ticker",
            name="nasdaq_name",
            field=models.CharField(max_length=5, verbose_name="Nasdaq Ticker Name"),
        ),
    ]
