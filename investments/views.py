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
    all_active_options = Option.objects.exclude(num_open=0).order_by('expiration_date')
    total_num_open = all_active_options.aggregate(Sum('num_open'))['num_open__sum']

    live_prices = get_all_live_option_info(all_active_options)
    print("LIVE PRICES: ", live_prices)
    update_options_with_live_price(all_active_options, live_prices)
    stats = calculate_stats(all_active_options, live_prices)
    

    template = loader.get_template("index.html")
    context = {
        'all_active_options': all_active_options,
        'live_prices': live_prices,
        'total_num_open': total_num_open,
        'stats':stats
    }
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
    #return [0, 1, 2]
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
    #TODO(anush) make these all time stats, not just active ones
    money_invested = 0
    total_gain = 0
    current_theta = 0
    
    for option in all_active_options:
        money_invested += option.get_cash_set_aside()
        _, _, theta = live_prices.get(option.id)
        total_gain += option.live_pl
        current_theta += theta 

    pl_percentage = (total_gain / money_invested) * 100 if money_invested != 0 else 0
    
    return {
        'money_invested': money_invested,
        'total_gain': total_gain,
        'pl_percentage': pl_percentage,
        'current_theta': -current_theta * 100
    }

def update_options_with_live_price(all_active_options: list[Option], live_prices) -> list[Option]:
    for option, prices in zip(all_active_options, live_prices):
        option.set_current_value(live_prices[option.id][1])
    
    Option.objects.bulk_update(all_active_options, ['live_pl'])