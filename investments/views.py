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
    print("STATS: ", stats['stats'])

    all_active_options = Option.objects.exclude(num_open=0).order_by('expiration_date')
    all_active_stocks = Share.objects.exclude(num_open=0)

    context = {
        'all_active_options': all_active_options,
    }

    context |= live_prices
    context |= stats

    print("FINAL CONTEXT ", context)
    # # Ensure gains_by_ticker is a dictionary
    # if not isinstance(gains_by_ticker, dict):
    #     print("Warning: gains_by_ticker is not a dictionary. Converting to dict.")
    #     gains_by_ticker = dict(gains_by_ticker) if hasattr(gains_by_ticker, '__iter__') else {"Error": float(gains_by_ticker)}

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