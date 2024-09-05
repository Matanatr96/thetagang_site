from django.db import models
from django.utils.translation import gettext_lazy

# Create your models here.
class Option(models.Model):
    class OptionDirection(models.TextChoices):
        PUT = 'p', gettext_lazy('PUT')
        CALL = 'c', gettext_lazy('CALL')

    ticker = models.CharField(max_length=5)
    expiration_date = models.DateField('Expiry Date')
    strike_price = models.FloatField("Strike Price")
    purchase_price = models.FloatField("Price Purchased")
    direction = models.CharField(choices=OptionDirection.choices, max_length=4)
    closed = models.BooleanField("Is the option closed")
    when_closed = models.DateField("When was this option closed")