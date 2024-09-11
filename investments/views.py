from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.db.models import Sum
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.exceptions import ObjectDoesNotExist

from investments.models import Option, Share, Transaction, Ticker, Cash

import collections
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
    stats = calculate_stats(live_prices)
    gains_by_ticker = get_gains_by_ticker()

    # Ensure gains_by_ticker is a dictionary
    if not isinstance(gains_by_ticker, dict):
        print("Warning: gains_by_ticker is not a dictionary. Converting to dict.")
        gains_by_ticker = dict(gains_by_ticker) if hasattr(gains_by_ticker, '__iter__') else {"Error": float(gains_by_ticker)}

    template = loader.get_template("index.html")
    context = {
        'all_active_options': all_active_options,
        'live_prices': live_prices,
        'total_num_open': total_num_open,
        'stats':stats,
        'gains_by_ticker': gains_by_ticker,
    }
    return HttpResponse(template.render(context, request))

def detail(request, option_id):
    response = f"This is the detail page for option {option_id}"
    return HttpResponse(response)

@csrf_exempt
@require_http_methods(["POST"])
def create_transaction(request):
    data = json.loads(request.body)
    
    try:
        with transaction.atomic():
            security_type = data['security_type']
            existing_or_new = data['existing_or_new']
            quantity = int(data['quantity'])
            price = float(data['price'])
            date = parse_date(data['date'])

            if existing_or_new == 'existing':
                security_id = data['existing_security_id']
                if security_type == 'share':
                    security = Share.objects.get(id=security_id)
                else:
                    security = Option.objects.get(id=security_id)
                
                # Update existing security
                security.num_open += quantity
                if isinstance(security, Share):
                    security.average_price = ((security.average_price * security.num_open) + (price * quantity)) / (security.num_open + quantity)
                elif isinstance(security, Option):
                    security.cost_basis = ((security.cost_basis * security.num_open) + (price * quantity)) / (security.num_open + quantity)
                security.save()

            else:  # New security
                ticker, _ = Ticker.objects.get_or_create(nasdaq_name=data['ticker'])
                
                if security_type == 'share':
                    security = Share.objects.create(
                        ticker=ticker,
                        num_open=quantity,
                        average_price=price
                    )
                else:
                    security = Option.objects.create(
                        ticker=ticker,
                        num_open=quantity,
                        expiration_date=parse_date(data['expiration_date']),
                        strike_price=float(data['strike_price']),
                        direction=data['direction'],
                        cost_basis=price
                    )

            # Create new transaction
            Transaction.objects.create(
                date=date,
                price=price,
                quantity=quantity,
                security=security,
            )

        return JsonResponse({'status': 'success', 'message': 'Transaction created successfully'})
    except ObjectDoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Selected security does not exist'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_http_methods(["GET"])
def get_securities(request):
    security_type = request.GET.get('type', 'option')
    
    if security_type == 'share':
        securities = Share.objects.all()
    else:
        securities = Option.objects.filter(expiration_date__gte=timezone.now())
    
    securities_data = [
        {
            'id': security.id,
            'display_name': str(security)
        }
        for security in securities
    ]
    
    return JsonResponse(securities_data, safe=False)

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

def calculate_stats(live_prices):
    #TODO(anush) make these all time stats, not just active ones
    current_portfolio_value = 0
    total_gain = 0
    current_theta = 0

    all_cash = Cash.objects.all()
    current_portfolio_value += sum(cash.num_open for cash in all_cash)
    all_shares = Share.objects.exclude(num_open=0)
    # TODO(Add live share price api)
    #current_portfolio_value += sum(share.num_open * share.current_value for share in all_shares)
    all_options = Option.objects.all()

    for option in all_options:
        if option.is_open():
            print(option.id)
            _, _, theta = live_prices.get(option.id)
            current_theta += theta * option.num_open
            current_portfolio_value += option.current_value

        total_gain += option.live_pl

    pl_percentage = (total_gain / current_portfolio_value) * 100 if current_portfolio_value != 0 else 0
    
    return {
        'curr_portfolio_value': current_portfolio_value,
        'total_gain': total_gain,
        'pl_percentage': pl_percentage,
        'current_theta': -current_theta * 100
    }

def update_options_with_live_price(all_active_options: list[Option], live_prices) -> list[Option]:
    for option, prices in zip(all_active_options, live_prices):
        option.set_current_value(live_prices[option.id][1])
    
    Option.objects.bulk_update(all_active_options, ['current_value'])

def get_gains_by_ticker():
    all_options = Option.objects.all()
    all_shares = Share.objects.exclude()

    all_gains = collections.defaultdict(float)

    for option in all_options:
        all_gains[option.ticker.nasdaq_name] += option.live_pl

    for share in all_shares:
        all_gains[share.ticker.nasdaq_name] += share.live_pl

    return dict(all_gains)