import re
import random
from datetime import datetime

from django.contrib.auth.models import User

from .models import UserFavoriteBook, Book


def smart_title_case(text: str) -> str:
    """
    Title-case helper that avoids capital 'S' after apostrophes.
    Example: "ender's game" -> "Ender's Game" (not "Ender'S Game")
    Handles both regular apostrophes (') and curly apostrophes (')
    """
    if not text:
        return text
    titled = text.strip().title()
    # Replace capital S after any type of apostrophe with lowercase s
    # Handles regular apostrophe (') and curly apostrophes (' and ')
    # First handle curly apostrophes (U+2019, U+2018)
    titled = titled.replace(chr(8217) + "S", "'s")  # Right single quotation mark
    titled = titled.replace(chr(8216) + "S", "'s")  # Left single quotation mark
    # Then handle regular apostrophe
    return re.sub(r"'S\b", "'s", titled)


def get_book_recommendations(current_user):
    # 1. Find books I love (favorites)
    my_favorite_ids = set(
        UserFavoriteBook.objects.filter(
            user=current_user,
        ).values_list("book_id", flat=True)
    )

    if not my_favorite_ids:
        return []

    # 2. Find other users who also love at least one of those same books
    similar_users = (
        User.objects.filter(
            favorite_books__book_id__in=my_favorite_ids,
        )
        .exclude(id=current_user.id)
        .distinct()
    )

    # 3. For each recommended book, track which similar user(s) recommended it
    # and count the overlap in favorite books
    book_recommendations = {}  # book_id -> {book, similar_user, overlap_count}
    
    my_favorite_books = set(
        UserFavoriteBook.objects.filter(user=current_user).values_list("book_id", flat=True)
    )

    for user in similar_users:
        # Get all books this user loves
        their_favorite_book_ids = set(
            UserFavoriteBook.objects.filter(
                user=user
            ).values_list("book_id", flat=True)
        )
        
        # Find overlapping books: books BOTH users love
        overlapping_book_ids = my_favorite_books & their_favorite_book_ids
        overlap_count = len(overlapping_book_ids)
        
        # Get the actual Book objects for overlapping favorites
        overlapping_books = Book.objects.filter(id__in=overlapping_book_ids)
        overlapping_titles = [book.title for book in overlapping_books]
        
        # For each book they love that I haven't favorited, add it as a recommendation
        for book_id in their_favorite_book_ids:
            if book_id not in my_favorite_books:
                # If we haven't seen this book yet, or if this user has more overlap, use this user
                if book_id not in book_recommendations or overlap_count > book_recommendations[book_id]['overlap_count']:
                    book_recommendations[book_id] = {
                        'book_id': book_id,
                        'similar_user': user,
                        'overlap_count': overlap_count,
                        'overlapping_titles': overlapping_titles,
                    }

    # Convert to list of dictionaries with book objects
    result = []
    for rec_data in book_recommendations.values():
        book = Book.objects.get(id=rec_data['book_id'])
        result.append({
            'book': book,
            'similar_user': rec_data['similar_user'],
            'overlap_count': rec_data['overlap_count'],
            'overlapping_titles': rec_data['overlapping_titles'],
        })
    
    # Sort by overlap_count (descending) - users with more overlapping favorites first
    result.sort(key=lambda x: x['overlap_count'], reverse=True)
    
    return result


def generate_guest_username():
    """
    Generate a unique username for guest users following the same rules as renamed users:
    - 5-10 character names ending with '_'
    - Random combinations from: animals, area codes, book characters, day abbreviations, colors, zip codes
    - Capitalize first letter of animals, book characters, days, and colors (even if embedded)
    - Ensure it's not all numbers
    """
    
    def generate_random_username():
        """Generate a random username from specified categories, 4-9 chars + '_' = 5-10 total"""
        
        # Define categories with short forms (same as update_underscore_usernames.py)
        animals = ['cat', 'dog', 'fox', 'owl', 'bee', 'bat', 'pig', 'cow', 'hen', 'ram', 'elk', 'jay']
        area_codes = ['212', '310', '415', '617', '718', '213', '312', '404', '305', '214']
        book_chars = ['harry', 'frodo', 'katniss', 'sherlock', 'holmes', 'gandalf', 'dumbledore', 'hermione', 'ron', 'bilbo']
        day_abbrevs = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        colors = ['red', 'blue', 'green', 'gold', 'pink', 'cyan', 'lime', 'navy', 'teal', 'gray']
        zip_codes = ['10001', '90210', '02134', '60601', '33139', '77002', '98101', '94102']
        
        all_categories = [
            animals,
            area_codes,
            book_chars,
            day_abbrevs,
            colors,
            zip_codes
        ]
        
        # Try to generate a username that's 4-9 characters (plus '_' = 5-10 total)
        max_attempts = 50
        for _ in range(max_attempts):
            # Randomly select 1-3 components
            num_components = random.randint(1, 3)
            selected = random.sample(all_categories, num_components)
            
            # Pick one item from each selected category
            components = [random.choice(cat) for cat in selected]
            
            # Combine them
            username = ''.join(components)
            
            # Ensure length is 4-9 characters (will add '_' at end)
            if 4 <= len(username) <= 9:
                # Add underscore at the end
                return username + '_'
        
        # Fallback: if we can't generate in range, use a simple pattern
        animal = random.choice(animals)
        day = random.choice(day_abbrevs)
        username = (animal + day)[:9]  # Ensure max 9 chars
        return username + '_'
    
    def capitalize_username_components(username):
        """Capitalize first letter of animal, day, book character, and color components"""
        
        # Remove trailing underscore for processing
        if not username.endswith('_'):
            return username
        
        base_username = username[:-1]  # Remove trailing '_'
        
        # Define categories (same as capitalize_underscore_usernames.py)
        animals = ['cat', 'dog', 'fox', 'owl', 'bee', 'bat', 'pig', 'cow', 'hen', 'ram', 'elk', 'jay']
        book_chars = ['harry', 'frodo', 'katniss', 'sherlock', 'holmes', 'gandalf', 'dumbledore', 'hermione', 'ron', 'bilbo']
        day_abbrevs = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        colors = ['red', 'blue', 'green', 'gold', 'pink', 'cyan', 'lime', 'navy', 'teal', 'gray']
        
        # Create a mapping of lowercase -> capitalized for items to capitalize
        capitalize_map = {}
        for category_list in [animals, book_chars, day_abbrevs, colors]:
            for item in category_list:
                capitalize_map[item.lower()] = item.capitalize()
        
        # Find and replace all occurrences of words to capitalize, even if embedded
        result = base_username
        remaining_lower = base_username.lower()
        
        # Sort items by length (longest first) to match longer items first
        all_capitalize_items = animals + book_chars + day_abbrevs + colors
        sorted_items = sorted(all_capitalize_items, key=len, reverse=True)
        
        # Find all matches and their positions (allow embedded matches)
        matches = []
        for item in sorted_items:
            item_lower = item.lower()
            # Find all occurrences (no word boundary checks)
            start = 0
            while True:
                pos = remaining_lower.find(item_lower, start)
                if pos == -1:
                    break
                
                # Check if this position overlaps with an existing match
                overlap = False
                for existing_pos, existing_item, _ in matches:
                    # Check if ranges overlap
                    if not (pos + len(item_lower) <= existing_pos or pos >= existing_pos + len(existing_item)):
                        overlap = True
                        break
                
                if not overlap:
                    matches.append((pos, item, item_lower))
                
                start = pos + 1
        
        # Sort matches by position (reverse order for safe replacement)
        matches.sort(key=lambda x: x[0], reverse=True)
        
        # Replace matches from end to beginning to preserve positions
        result_list = list(base_username)
        for pos, original_item, item_lower in matches:
            capitalized = capitalize_map[item_lower]
            # Replace the slice
            result_list[pos:pos + len(item_lower)] = list(capitalized)
        
        result = ''.join(result_list)
        
        # Add back trailing underscore
        return result + '_'
    
    def fix_all_number_username(username):
        """Add a letter component to usernames that are all numbers"""
        
        # Remove trailing underscore for processing
        if not username.endswith('_'):
            return username
        
        base_username = username[:-1]  # Remove trailing '_'
        
        # Check if the base username is all digits
        if base_username.isdigit():
            # Add a letter component
            animals = ['Cat', 'Dog', 'Fox', 'Owl', 'Bee', 'Bat', 'Pig', 'Cow', 'Hen', 'Ram', 'Elk', 'Jay']
            book_chars = ['Harry', 'Frodo', 'Katniss', 'Sherlock', 'Holmes', 'Gandalf', 'Hermione', 'Ron', 'Bilbo']
            day_abbrevs = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            colors = ['Red', 'Blue', 'Green', 'Gold', 'Pink', 'Cyan', 'Lime', 'Navy', 'Teal', 'Gray']
            
            all_components = animals + book_chars + day_abbrevs + colors
            letter_component = random.choice(all_components)
            # Combine: put letter before numbers for consistency
            new_base = letter_component + base_username
            return new_base + '_'
        
        # If it already has letters, return as-is
        return username
    
    # Generate username with uniqueness check
    max_attempts = 20
    for attempt in range(max_attempts):
        # Step 1: Generate random username
        candidate = generate_random_username()
        
        # Step 2: Capitalize components
        candidate = capitalize_username_components(candidate)
        
        # Step 3: Fix if all numbers
        candidate = fix_all_number_username(candidate)
        
        # Check if username already exists
        if not User.objects.filter(username=candidate).exists():
            return candidate
    
    # Fallback: if we can't generate a unique username, use timestamp-based
    import time
    timestamp_str = str(int(time.time()) % 10000000000)  # Last 10 digits
    # Ensure total length is 10 (max) including underscore
    if len(timestamp_str) > 9:
        timestamp_str = timestamp_str[:9]
    return timestamp_str + '_'