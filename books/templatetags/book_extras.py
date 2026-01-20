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

@register.filter(name='get_pill_color')
def get_pill_color(value):
    """Get a light, washed out color for a pill button based on the input value (book title or index)"""
    colors = [
        '#E3F2FD',  # light blue
        '#E8F5E9',  # light green
        '#FFF9C4',  # light yellow
        '#F3E5F5',  # light purple
        '#FFEBEE',  # light pink
        '#E0F2F1',  # light teal
        '#FFF3E0',  # light orange
        '#E1F5FE',  # light cyan
        '#F1F8E9',  # light lime
        '#FCE4EC',  # light rose
        '#E8EAF6',  # light indigo
        '#FFF8E1',  # light amber
        '#EDE7F6',  # light deep purple
        '#E0F7FA',  # light aqua
        '#F9FBE7',  # light light green
        '#FFFDE7',  # light light yellow
    ]
    
    # If value is a string (book title), hash it to get a consistent color
    if isinstance(value, str):
        # Simple hash function to convert string to index
        hash_value = sum(ord(c) for c in value)
        idx = hash_value % len(colors)
        return colors[idx]
    
    # If value is a number (index), use it directly
    try:
        idx = int(value) % len(colors)
        return colors[idx]
    except (ValueError, TypeError):
        return colors[0]