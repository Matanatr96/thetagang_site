from datetime import datetime

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


def validate_ticker_type(value):
    valid_options = ['sto', 'etf', 'mm', 'mf']
    if value not in valid_options:
        raise ValueError(f"Invalid ticker type, must be in {valid_options}")

# Create your models here.
class Ticker(models.Model):
    nasdaq_name = models.CharField("Nasdaq Ticker Name", max_length=5)
    name = models.CharField("Full Name of Stock", max_length=20, blank=True, null=True)
    type = models.CharField(max_length=3, choices=[
        ("sto", "Stock"),
        ("etf", "ETF"),
        ("mm", "Money Market"),
        ("mf", "Mutual Fund"),
    ], validators=[validate_ticker_type])

    def __str__(self):
        return(f"{self.nasdaq_name}")

class Security(models.Model):
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE)
    num_open = models.FloatField("Owned Securities", default=1)
    cost_basis = models.FloatField("Cost Basis Per Security", default=0) # per share/option
    current_value = models.FloatField("Current Value of this Security", null=True, blank=True, default=0) # total
    live_pl = models.FloatField("Live Profit/Loss on These Securities", null=True, blank=True, default=0) # in dollars

    def calculate_pl(self):
        # Returns the PL of this option if we were to close it today 
        #  (along with historical gains)
        print("option pl has been updated")
        return self.live_pl + self.current_value
    
    def update_pl(self):
        # only needs to happen when a transaction is made on this stock
        raise NotImplementedError

    class Meta:
        abstract = True

    def __str__(self):
        return(f"{self.num_open}: {self.ticker}")

class Share(Security):
    def set_current_value(self, live_price):
        self.current_value = self.num_open * live_price
        print("Share", self.num_open, live_price, self.current_value)

    def __str__(self):
        return(f"{self.num_open}: {self.ticker}")

def validate_option_direction(value):
    if value not in ['p', 'c']:
        raise ValueError("Invalid option direction. Must be 'p' or 'c'.")

class Option(Security):
    expiration_date = models.DateField('Expiry Date')
    strike_price = models.FloatField("Strike Price")
    direction = models.CharField(max_length=1, choices=[('p', 'PUT'), ('c', 'CALL')], validators=[validate_option_direction])
    def set_current_value(self, live_price):
        print(f'updating current value of {live_price}')
        self.current_value = self.num_open * live_price * 100
        print("Option", self.num_open, live_price, self.current_value)
    def is_short(self):
        return self.num_open < 0
    
    def is_long(self):
        return self.num_open > 0
    
    def is_open(self):
        return self.num_open
    
    def get_cash_set_aside(self):
        base_price = self.strike_price * 100 if self.is_short() else self.profit_loss
        return self.num_open * -base_price

    def __str__(self):
        return f"{self.ticker} {self.strike_price}{self.direction} {self.expiration_date}"

    def expires_today(self):
        return self.expiration_date.date() == datetime.now().date()
    
class Cash(models.Model):
    ticker = models.ForeignKey(Ticker, on_delete=models.CASCADE, default="FXAIX")
    num_open = models.FloatField("Owned Cash", default=1)
    description = models.CharField(max_length=1, choices=[("d", "Deposit"), ("i", "Interest")], default='d')

    def __str__(self):
        return(f"{self.num_open}: {self.ticker}")
    
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
    

class PortfolioTracker(models.Model):
    value = models.FloatField("What was the portfolio valued at?")
    date = models.DateField("When was this value accrued?")

    @classmethod
    def get_oldest_value(cls):
        if oldest_record := cls.objects.order_by('date').first():
             return oldest_record.value, oldest_record.date
        
        return None, None
    
    def __str__(self):
        return f"{self.date}: {self.value}"