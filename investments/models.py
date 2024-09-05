from datetime import datetime

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy

# Create your models here.
class Option(models.Model):
    class OptionDirection(models.TextChoices):
        PUT = 'p', gettext_lazy('PUT')
        CALL = 'c', gettext_lazy('CALL')

    ticker = models.CharField(max_length=5)
    expiration_date = models.DateField('Expiry Date')
    strike_price = models.FloatField("Strike Price")
    direction = models.CharField(choices=OptionDirection.choices, max_length=4)
    purchase_price = models.FloatField("Price Purchased", null=True, blank=True)
    closed = models.BooleanField("Is the option closed", null=True, blank=True)
    when_closed = models.DateField("When was this option closed", null=True, blank=True)

    def __str__(self):
        return f"{self.ticker} {self.strike_price}{self.direction}"
    
    def expires_today(self):
        return self.expiration_date.date() == datetime.today().date()