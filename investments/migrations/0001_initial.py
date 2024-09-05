# Generated by Django 5.1.1 on 2024-09-05 04:03

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Option",
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
                ("ticker", models.CharField(max_length=5)),
                ("expiration_date", models.DateField(verbose_name="Expiry Date")),
                ("strike_price", models.FloatField(verbose_name="Strike Price")),
                ("purchase_price", models.FloatField(verbose_name="Price Purchased")),
                (
                    "direction",
                    models.CharField(
                        choices=[("p", "PUT"), ("c", "CALL")], max_length=4
                    ),
                ),
                ("closed", models.BooleanField(verbose_name="Is the option closed")),
                (
                    "when_closed",
                    models.DateField(verbose_name="When was this option closed"),
                ),
            ],
        ),
    ]
