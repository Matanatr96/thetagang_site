from datetime import datetime

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# Create your models here.
class Ticker(models.Model):
    nasdaq_name = models.CharField("Nasdaq Ticker Name", max_length=5)
    name = models.CharField("Full Name of Stock", max_length=20, blank=True, null=True)

    def __str__(self):
        return(f"{self.nasdaq_name}")

class Security(models.Model):
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    num_open = models.FloatField("Owned Securities", default=1) # same thing as is_active

    class Meta:
        abstract = True

    def __str__(self):
        return(f"{self.num_open}: {self.ticker}")

class Share(Security):
    average_price = models.FloatField("Average Price of Purchase")

    def buy_shares(self, quantity: int, price: float):
        new_total_open = self.num_open + quantity
        old_cost_basis = self.num_open * self.average_price
        new_cost_basis = quantity * price
        new_average_price = (old_cost_basis + new_cost_basis) / new_total_open

        self.num_open = new_total_open
        self.average_price = new_average_price
        return new_total_open, new_average_price
    
    def __str__(self):
        return(f"{self.num_open}: {self.ticker}")

def validate_option_direction(value):
    if value not in ['p', 'c']:
        raise ValueError("Invalid option direction. Must be 'p' or 'c'.")

class Option(Security):
    expiration_date = models.DateField('Expiry Date')
    strike_price = models.FloatField("Strike Price")
    direction = models.CharField(max_length=1, choices=[('p', 'PUT'), ('c', 'CALL')], validators=[validate_option_direction])
    cost_basis = models.FloatField("Cost Basis of this option", default=0)
    current_value = models.FloatField("Current Value of this option", null=True, blank=True)
    live_pl = models.FloatField("Live Profit/Loss on this option", null=True, blank=True)
    
    def set_current_value(self, live_price):
        self.current_value = self.num_open * live_price
        self.update_pl()

    def update_pl(self):
        self.live_pl = (self.cost_basis + self.current_value) * 100
    
    def is_short(self):
        return self.num_open < 0
    
    def is_long(self):
        return self.num_open > 0
    
    def get_cash_set_aside(self):
        base_price = self.strike_price * 100 if self.is_short() else self.profit_loss
        return self.num_open * -base_price

    def __str__(self):
        return f"{self.ticker} {self.strike_price}{self.direction} {self.expiration_date}"

    def expires_today(self):
        return self.expiration_date.date() == datetime.now().date()
    
class Cash(Security):
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE, default="FXAIX")
    
class Transaction(models.Model):
    date = models.DateField()
    price = models.FloatField("What did this cost per security")
    quantity = models.IntegerField("How many shares/options were purchased or sold")

    # Fields for the generic foreign key
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    security = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f"{self.date}: {self.quantity} {self.security}"