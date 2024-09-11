from django import template

register = template.Library()

@register.filter
def get_option_item(dictionary, key):
    return dictionary.get(key, [None, None, None])

@register.filter
def type(value):
    return value.__class__.__name__