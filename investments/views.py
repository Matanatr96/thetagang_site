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