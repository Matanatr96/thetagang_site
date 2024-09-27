from django.conf import settings
from django.core.cache import cache

from investments.models import Option, Share, Transaction, Ticker, Cash, PortfolioTracker
from investments.error_models import DataFetchError

import collections
import logging
import requests
import datetime

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------- #
#                             Main
# ----------------------------------------------------------------------- #
def get_live_prices():
    all_active_options = Option.objects.exclude(num_open=0).order_by('expiration_date')
    all_active_shares = Share.objects.exclude(num_open=0)

    live_option_prices = get_all_live_option_info(all_active_options=all_active_options)
    live_share_prices = get_all_live_share_info(all_active_shares)

    return {
        "live_option_prices": live_option_prices,
        "live_share_prices": live_share_prices,
    }

def update_prices(live_prices: dict[str, dict]):
    logger.debug(f"Live Prices: {live_prices}")
    update_options_with_live_price(live_prices["live_option_prices"])
    update_shares_with_live_price(live_prices["live_share_prices"])

def calculate_stats(live_prices):
    return calculate_portfolio_gains(live_prices)


# ----------------------------------------------------------------------- #
#                             Get Live Prices
# ----------------------------------------------------------------------- #
def get_all_live_share_info(all_active_shares: list[Share]):
    live_prices = {}
    api_key = settings.MARKET_DATA_API
    for share in all_active_shares:
        share_data = make_share_api_call(share.ticker, api_key)
        live_prices[share.id] = share_data

    return live_prices

def get_all_live_option_info(all_active_options: list[Option]):
    live_prices = {}
    api_key = settings.MARKET_DATA_API
    for option in all_active_options:
        option_data = make_option_api_call(option.ticker, option.expiration_date.isoformat(), option.direction, option.strike_price, api_key)
        live_prices[option.id] = option_data

    return live_prices

def make_share_api_call(ticker: str, api_key: str):
    cache_key = f"share_price_{ticker}"
    
    if (cached_data := cache.get(cache_key)) is not None:
        logger.info(f"Returned Cached Ticker Data for {ticker}")
        return cached_data
    
    url = f"https://api.marketdata.app/v1/stocks/quotes/{ticker}/"

    headers = {
        'Accept': 'application/json',
        'Authorization': f"Bearer {api_key}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code not in {200, 203}:
        raise DataFetchError(ticker, response.status_code, response.text)
    
    response = response.json()
    cache.set(key=cache_key, value=float(response['mid'][0]), timeout=1800)
    return float(response['mid'][0])


def make_option_api_call(ticker: str, expiration_timestamp: str, direction: str, strike_price: float, api_key: str):
    cache_key = f'option_price_{ticker}_{expiration_timestamp}_{direction}_{strike_price}'
    if (cached_data := cache.get(cache_key)) is not None:
        logger.info(f"Returning Cached Option Data for {ticker}")
        return cached_data

    side_name = 'put' if direction == 'p' else 'call'
    url = f"https://api.marketdata.app/v1/options/chain/{ticker}/?expiration={expiration_timestamp}&side={side_name}&strike={int(strike_price)}"

    headers = {
        'Accept': 'application/json',
        'Authorization': f"Bearer {api_key}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code not in {200, 203}:
        logger.error(DataFetchError(ticker, response.status_code, response.text))
        local_response = (0, 0, 0)
        cache.set(key=cache_key, value=local_response, timeout=1800)
        return local_response

    response = response.json()
    local_response = (response['underlyingPrice'][0], response['mid'][0], response['theta'][0])
    cache.set(key=cache_key, value=local_response, timeout=1800)
    return local_response

# ----------------------------------------------------------------------- #
#                             Update Prices
# ----------------------------------------------------------------------- #
def update_options_with_live_price(live_option_prices):
    all_active_options = Option.objects.exclude(num_open=0)

    for option in all_active_options:
        option.set_current_value(live_option_prices[option.id][1])
    
    Option.objects.bulk_update(all_active_options, ['current_value'])

def update_shares_with_live_price(live_share_prices):
    all_active_shares = Share.objects.exclude(num_open=0)

    for share in all_active_shares:
        share.set_current_value(live_share_prices[share.id])
    
    Share.objects.bulk_update(all_active_shares, ['current_value'])

# ----------------------------------------------------------------------- #
#                             Calculate Stats
# ----------------------------------------------------------------------- #
def calculate_portfolio_gains(live_prices):
    oldest_portfolio_value, _ = PortfolioTracker.get_oldest_value()
    live_option_prices, live_share_prices = live_prices["live_option_prices"], live_prices["live_share_prices"]
    
    all_cash = Cash.objects.all()
    main_val = Cash.objects.get(description='m').num_open
    deposits_val = sum(cash.num_open for cash in all_cash if cash.description=='d')
    current_portfolio_value = deposits_val + main_val

    gains_by_ticker, live_gls, current_theta, current_values = get_gains_by_ticker(live_option_prices)

    interest_gains = sum(cash.num_open for cash in all_cash if cash.description=='i')
    total_gain = sum(gains_by_ticker.values()) + interest_gains
    total_cash = deposits_val + interest_gains + main_val
    current_portfolio_value += current_values
    logger.debug("Current Portfolio Value: {current_portfolio_value}, Old Portfolio Value: {oldest_portfolio_value}")

    gain_comparison_num = oldest_portfolio_value + deposits_val
    pl_percentage = ((current_portfolio_value - gain_comparison_num) / gain_comparison_num) * 100 if oldest_portfolio_value else 0
    apy = ((current_theta * 100 * 365) / current_portfolio_value) * 100 if current_portfolio_value else 0 # % gains if I get this theta daily for the year

    # Create a new portfolio tracker if it
    PortfolioTracker.create_or_update_daily(current_portfolio_value=current_portfolio_value)
    
    return {
        'stats': {
            'current_cash': total_cash,
            'curr_portfolio_value': current_portfolio_value,
            'total_gain': total_gain,
            'pl_percentage': pl_percentage,
            'current_theta': current_theta * 100,
            'APY':  apy
        },
        'gains_by_ticker': gains_by_ticker,
        'share_live_gl': live_gls['share_live_gl'],
        'option_live_gl': live_gls['option_live_gl']
    }

def get_gains_by_ticker(live_option_prices):
    all_options = Option.objects.all()
    all_shares = Share.objects.all()

    all_gains = collections.defaultdict(float)
    option_live_gl = collections.defaultdict(float)
    share_live_gl = collections.defaultdict(float)
    curr_values = 0
    curr_theta = 0

    for option in all_options:
        live_pl = option.calculate_pl()
        logger.debug(f"{option.ticker.nasdaq_name} {live_pl}")
        all_gains[option.ticker.nasdaq_name] += live_pl
        curr_values += option.current_value
        if option.is_open():
            _, _, theta = live_option_prices.get(option.id)
            curr_theta += theta * option.num_open
            option_live_gl[option.id] = option.get_live_gl()

    for share in all_shares:
        all_gains[share.ticker.nasdaq_name] += share.calculate_pl()
        logger.debug(f"{share.ticker.nasdaq_name} {share.calculate_pl()}")
        curr_values += share.current_value
        if share.is_open():
            share_live_gl[share.id] = share.get_live_gl()

    live_gls = {
        'option_live_gl': dict(option_live_gl),
        'share_live_gl': dict(share_live_gl)
    }

    return dict(all_gains), live_gls, curr_theta, curr_values