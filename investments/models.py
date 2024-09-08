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
    

    def __str__(self):
        return f"{self.ticker} {self.strike_price}{self.direction} {self.expiration_date}"
    
    def expires_today(self):
        return self.expiration_date.date() == datetime.now().date()
    
class Position(models.Model):
    base_option = models.ForeignKey(Option, on_delete=models.CASCADE)
    base_quantity = models.IntegerField("How many base options were purchased", default=-1)
    # secondary_option = models.ForeignKey(Option, on_delete=models.CASCADE, null=True, blank=True)  # Unimplemented :)
    # secondary_quantity = models.IntegerField("How many secondary options were purchased")
    
    num_legs = models.IntegerField("How many legs does this position have?", default=1)
    purchase_price = models.FloatField("Avg Price Purchased", null=True, blank=True)
    closed_price = models.FloatField("Avg Price Purchased", null=True, blank=True)
    is_active = models.BooleanField("Is the option active", default=True)
    when_opened = models.DateField("When was this option opened")
    when_closed = models.DateField("When was this option closed", null=True, blank=True)
    profit = models.FloatField("When closed, what was the profit made on this position", null=True, blank=True)

    #TODO(anush) implement a feature to choose which option to close for how much of a profit, would need to make a Leg class in addition to this position class

    def get_profit(self) -> float:
        if self.profit:
            return self.profit
        
        if 

    def __str__(self) -> str:
        return f"{self.base_quantity}: {str(self.base_option)}"