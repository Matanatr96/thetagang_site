from datetime import datetime

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

import logging

logger = logging.getLogger(__name__)

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
    current_value = models.FloatField("Current Value of this Security", null=True, blank=True, default=0) # total. Updates only when we view in the view
    live_pl = models.FloatField("Live Profit/Loss on These Securities", null=True, blank=True, default=0) # in dollars

    def is_short(self):
        return self.num_open < 0
    
    def is_long(self):
        return self.num_open > 0
    
    def is_open(self):
        return self.num_open
    
    def update_live_pl(self, price, quantity):
        self.live_pl += -quantity * price
    
    def update_cost_basis(self, price, quantity):
        if self.num_open + quantity == 0:
            self.cost_basis = 0
            return 0
        self.cost_basis = ((self.cost_basis * self.num_open) + (price * quantity)) / (self.num_open + quantity)
        return self.cost_basis
    
    def update_num_open(self, quantity):
        self.num_open += quantity
        if self.num_open == 0:
            logger.info("This is a closing transaction")
    
    def update_cash_value(self, price, quantity):
        logger.info(f"updating cash value for {self}")
        deposit_cash = Cash.objects.get(description='m')
        deposit_cash.num_open += price * -quantity
        deposit_cash.save()

    class Meta:
        abstract = True

    def __str__(self):
        return(f"{self.num_open}: {self.ticker}")

class Share(Security):
    def set_current_value(self, live_price):
        self.current_value = self.num_open * live_price
        logger.debug(f"Updating Curr Value of Share: {self.num_open} {live_price} {self.current_value}")

    def transact(self, price, quantity):
        self.update_cost_basis(price, quantity)
        self.update_cash_value(price, quantity)
        self.update_live_pl(price, quantity)
        self.update_num_open(quantity)

    def calculate_pl(self):
        # Returns the PL of this option if we were to close it today 
        #  (along with historical gains)
        return self.live_pl + self.current_value
    
    # Get the live gain loss if we were to sell the share today (Don't include historical gains here)
    def get_live_gl(self):
        all_cost_basis = -self.num_open * self.cost_basis
        return all_cost_basis + self.current_value

    def __str__(self):
        return(f"{self.num_open}: {self.ticker}")

def validate_option_direction(value):
    if value not in ['p', 'c']:
        raise ValueError("Invalid option direction. Must be 'p' or 'c'.")
    

# TODO the closing contract price should be lower than the average open price currently. Then thats a win. Where do we track those wins? Who knows

class Option(Security):
    expiration_date = models.DateField('Expiry Date')
    strike_price = models.FloatField("Strike Price")
    direction = models.CharField(max_length=1, choices=[('p', 'PUT'), ('c', 'CALL')], validators=[validate_option_direction])
    def set_current_value(self, live_price):
        self.current_value = self.num_open * live_price * 100
        logger.debug(f"Updating Curr Value of Option: {self.num_open} {live_price} {self.current_value}")
    
    def calculate_pl(self):
        # Returns the PL of this option if we were to close it today 
        #  (along with historical gains)
        return (self.live_pl * 100) + self.current_value
    
    # Get the live gain loss if we were to sell the option today (Don't include historical gains here)
    def get_live_gl(self):
        all_cost_basis = -self.num_open * self.cost_basis * 100
        return all_cost_basis + self.current_value
    
    def transact(self, price, quantity):
        if self.num_open < 0 and quantity > 0 and self.direction == 'c':
            self.close_covered_call(price, quantity) # updates cost basis and live_pl as well
        else:
            self.update_cost_basis(price, quantity)
            self.update_cash_value(price*100, quantity)
            self.update_live_pl(price, quantity)
        
        self.update_num_open(quantity)

    # if we close a covered call, we want to reduce the cost basis of the stock instead of changing the total gains
    def close_covered_call(self, price, quantity):
        logger.info(f"Closing Covered Call {self}")
        overall_profit_from_this_trade = (self.cost_basis - price) * quantity * 100 #positive if its a profit, negative otherwise
        self.live_pl += (overall_profit_from_this_trade / 100)
        logger.info(f"Overall Profit from this Closure: {overall_profit_from_this_trade}")
        # apply this value to the current stock cost basis
        share = Share.objects.get(ticker=self.ticker)
        old_cost_basis = share.cost_basis
        share.cost_basis = old_cost_basis - (share.num_open / overall_profit_from_this_trade)
        share.save()
        logger.info(f'reducing cost basis by { overall_profit_from_this_trade / share.num_open}')
        logger.info(f'old cost basis {old_cost_basis} new cost basis {share.cost_basis}')

    def get_cash_set_aside(self):
        base_price = self.strike_price * 100 if self.is_short() else self.profit_loss
        return self.num_open * -base_price

    def __str__(self):
        return f"{self.ticker} {self.strike_price}{self.direction} {self.expiration_date}"

    def expires_today(self):
        return self.expiration_date.date() == datetime.now().date()
    
class Cash(models.Model):
    num_open = models.FloatField("Owned Cash", default=1)
    description = models.CharField(max_length=1, choices=[("d", "Deposit"), ("i", "Interest"), ('m', "Main")], default='d')
    
    def __str__(self):
        return(f"{self.num_open}: {self.description}")
    
class Transaction(models.Model):
    date = models.DateField()
    price = models.FloatField("What did this cost per security")
    quantity = models.IntegerField("How many shares/options were purchased or sold")
    value = models.FloatField("Total value of the transaction")

    # Fields for the generic foreign key
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    security = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        s_or_b = "Sell" if self.quantity < 1 else "Buy"
        return f"{s_or_b} {self.date}: {self.quantity} {self.security} @${self.price} | {self.value}"
    

class PortfolioTracker(models.Model):
    value = models.FloatField("What was the portfolio valued at?")
    date = models.DateField("When was this value accrued?")

    @classmethod
    def get_oldest_value(cls):
        if oldest_record := cls.objects.order_by('date').first():
             return oldest_record.value, oldest_record.date
        
        return None, None
    
    @classmethod
    def create_or_update_daily(cls, current_portfolio_value):
        today = timezone.now().date()
        obj, created = cls.objects.get_or_create(
            date=today,
            defaults={'value': current_portfolio_value}
        )
        
        if not created:
            # If the object already existed, update its value
            obj.value = current_portfolio_value
            obj.save()
        
        return obj, created
    
    def __str__(self):
        return f"{self.date}: {self.value}"