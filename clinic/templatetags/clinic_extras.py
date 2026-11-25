from decimal import Decimal

from django import template
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma

register = template.Library()


@register.filter
def money(value):
    try:
        value = Decimal(value or 0).quantize(Decimal('0.01'))
    except Exception:
        return value
    symbol = getattr(settings, 'CURRENCY_SYMBOL', '')
    whole, frac = f'{value:.2f}'.split('.')
    return f'{symbol} {intcomma(int(whole))}.{frac}'


@register.simple_tag(takes_context=True)
def active(context, prefix):
    path = context['request'].path
    if prefix == '/':
        return 'active' if path == '/' else ''
    return 'active' if path.startswith(prefix) else ''
