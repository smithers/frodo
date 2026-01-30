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

@register.filter(name='get_sub_genre_color')
def get_sub_genre_color(sub_genre):
    """Get a light, washed out color for a sub-genre pill button"""
    # Map each sub-genre to a specific light color
    sub_genre_colors = {
        'Mystery & Thriller': '#E3F2FD',  # light blue
        'Sci-Fi': '#E8F5E9',  # light green
        'Fantasy': '#F3E5F5',  # light purple
        'Historical Fiction': '#FFF9C4',  # light yellow
        'Horror': '#FFEBEE',  # light pink
        'General Fiction': '#E0F2F1',  # light teal
        'Classic': '#EFEBE9',  # light brown/stone
        'Literary Fiction': '#E0F2F1',  # same as General Fiction
        'Literary Fiction ': '#E0F2F1',  # same as General Fiction (trailing space)
        'Biography': '#FFF3E0',  # light orange
        'History': '#E1F5FE',  # light cyan
        'Science': '#F1F8E9',  # light lime
        'Philosophy & Religion': '#FCE4EC',  # light rose
        'Psychology & Self-Help': '#E8EAF6',  # light indigo
        'Business & Finance': '#FFF8E1',  # light amber
        'Politics': '#EDE7F6',  # light deep purple
        'Humor': '#E0F7FA',  # light aqua
        'True Crime': '#F9FBE7',  # light light green
        'Reference': '#FFFDE7',  # light light yellow
    }
    
    if sub_genre:
        return sub_genre_colors.get(sub_genre, '#E0E0E0')  # default light gray
    return '#E0E0E0'  # default light gray


@register.filter(name='sub_genre_display')
def sub_genre_display(sub_genre):
    """Display 'General Fiction' for 'Literary Fiction' (or with trailing space)."""
    if not sub_genre:
        return ''
    val = (sub_genre or '').strip()
    if val in ('Literary Fiction', 'Literary Fiction '):
        return 'General Fiction'
    return sub_genre