import re

from django.contrib.auth.models import User

from .models import UserFavoriteBook, Book


def smart_title_case(text: str) -> str:
    """
    Title-case helper that avoids capital 'S' after apostrophes.
    Example: "ender's game" -> "Ender's Game" (not "Ender'S Game")
    """
    if not text:
        return text
    titled = text.strip().title()
    # Replace capital S after apostrophe with lowercase s
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