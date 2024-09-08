from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from django.db.models import Sum
from django.conf import settings

from investments.models import Option

import datetime
import requests
import logging
import time
import json

logger = logging.getLogger(__name__)

def index(request):
    all_active_options = Option.objects.filter(is_active=True)
    total_purchase_price = all_active_options.aggregate(Sum('purchase_price'))['purchase_price__sum']
    live_prices = get_all_live_option_info(all_active_options)
    print("LIVE PRICES: ", live_prices)

    template = loader.get_template("index.html")
    context = {
        'all_active_options': all_active_options,
        'live_prices': live_prices,
        'total_purchase_price': total_purchase_price}
    return HttpResponse(template.render(context, request))

def detail(request, option_id):
    response = f"This is the detail page for option {option_id}"
    return HttpResponse(response)

# ----------- Helpers ---------------
def get_all_live_option_info(all_active_options: list[Option]) -> list[tuple]:
    live_prices = {}
    api_key = settings.MARKET_DATA_API
    for option in all_active_options:
        option_data = make_marketdata_api_call(option.ticker, option.expiration_date.isoformat(), option.direction, option.strike_price, api_key)
        live_prices[option.id] = option_data

    return live_prices

# Returns live price, underlying price and theta for now
def parse_marketdata_response(response: dict):
    return response['underlyingPrice'][0], response['mid'][0], response['theta'][0]

def make_marketdata_api_call(ticker: str, expiration_timestamp: str, direction: str, strike_price: float, api_key: str):
    return [0, 1, 2]
    print(ticker, expiration_timestamp, direction, strike_price, api_key)
    side_name = 'put' if direction == 'p' else 'call'
    url = f"https://api.marketdata.app/v1/options/chain/{ticker}/?expiration={expiration_timestamp}&side={side_name}&strike={int(strike_price)}"
    print("url", url)

    headers = {
        'Accept': 'application/json',
        'Authorization': f"Bearer {api_key}"
        }
    response = requests.get(url, headers=headers)
    if response.status_code not in {200, 203}:
        logger.error(response.text)
        logger.error(response.content)
        raise Exception(f"Error fetching data for {ticker}: {response.status_code}")

    print("ANUSH")
    print(response.json())
    return parse_marketdata_response(response.json())

def calculate_stats(all_active_options, live_prices):
    money_invested = sum(option.purchase_price for option in all_active_options) * 100
    
    total_gain = 0
    current_theta = 0
    
    for option in all_active_options:
        live_data = live_prices.get(option.id, (0, 0, 0))
        live_price = live_data[0]
        total_gain += live_price - option.purchase_price
        current_theta += live_data[2]  # Assuming theta is the third element
    
    pl_percentage = (total_gain / money_invested) * 100 if money_invested != 0 else 0
    
    return {
        'money_invested': money_invested,
        'total_gain': total_gain,
        'pl_percentage': pl_percentage,
        'current_theta': current_theta
    }