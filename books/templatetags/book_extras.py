from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='to_stars')
def to_stars(value):
    try:
        value = int(value)
    except (ValueError, TypeError):
        value = 0
    
    # Logic: Draw filled stars + empty stars
    stars = '★' * value + '☆' * (5 - value)
    return mark_safe(f'<span class="star-rating">{stars}</span>')