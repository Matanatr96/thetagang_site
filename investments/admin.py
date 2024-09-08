from django.contrib import admin

from .models import Option, Ticker, Transaction, Share, Security

admin.site.register(Option)
admin.site.register(Ticker)
admin.site.register(Transaction)
admin.site.register(Share)