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
from investments.helpers import get_live_prices, update_prices, calculate_stats

import logging
import json

logger = logging.getLogger(__name__)

def index(request):
    live_prices = get_live_prices()  # live_option_prices, live_stock_prices
    update_prices(live_prices)
    stats = calculate_stats(live_prices)
    logger.debug(f"STATS: {stats['stats']}")

    all_active_options = Option.objects.exclude(num_open=0).order_by('expiration_date')
    all_active_shares = Share.objects.exclude(num_open=0)

    context = {
        'all_active_options': all_active_options,
        'all_active_shares': all_active_shares
    }

    context |= live_prices
    context |= stats

    logger.debug(f"FINAL CONTEXT :{context}")
    template = loader.get_template("index.html")
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
            logger.info("Updating Existing Security")
            security_type = data['security_type']
            existing_or_new = data['existing_or_new']
            quantity = float(data['quantity'])
            price = float(data['price'])
            date = parse_date(data['date'])

            if existing_or_new == 'existing':
                security_id = data['existing_security_id']
                if security_type == 'share':
                    security = Share.objects.get(id=security_id)
                    security.transact(price=price, quantity=quantity)
                    security.save()
                elif security_type == 'option':
                    security = Option.objects.get(id=security_id)
                    security.transact(price=price, quantity=quantity)
                    security.save()
                else: 
                    security = Cash.objects.create(
                        num_open=quantity,
                        description=data['description']
                    )
            else:  # New security
                logger.info("Creating New Security")
                ticker, _ = Ticker.objects.get_or_create(nasdaq_name=data['ticker'])
                
                if security_type == 'share':
                    security = Share.objects.create(
                        ticker=ticker,
                        num_open=quantity,
                        cost_basis=price,
                        live_pl=-quantity*price
                    )
                    security.update_cash_value(price=price, quantity=quantity)
                elif security_type == 'option':
                    security = Option.objects.create(
                        ticker=ticker,
                        num_open=quantity,
                        expiration_date=parse_date(data['expiration_date']),
                        strike_price=float(data['strike_price']),
                        direction=data['direction'],
                        cost_basis=price,
                        live_pl=-quantity*price
                    )
                    security.update_cash_value(quantity=quantity, price=price*100) # don't need to update cost basis nor num_open, just cash
                else:
                    security = Cash.objects.create(
                        num_open=quantity,
                        description=data['description']
                    )

            # Create new transaction
            Transaction.objects.create(
                date=date,
                price=price,
                quantity=quantity,
                security=security,
                value=price*quantity
            )
            logger.info("Created New Transaction")

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
    elif security_type == 'option':
        securities = Option.objects.exclude(num_open=0)
    else:
        securities = Cash.objects.all()
    
    securities_data = [
        {
            'id': security.id,
            'display_name': str(security)
        }
        for security in securities
    ]
    
    return JsonResponse(securities_data, safe=False)