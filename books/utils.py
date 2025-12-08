# books/utils.py
from django.contrib.auth.models import User
from .models import UserBookRating, Book

def get_book_recommendations(current_user):
    # 1. Find books I like (5 stars)
    my_5_star_ids = set(UserBookRating.objects.filter(
        user=current_user, 
        rating=5
    ).values_list('book_id', flat=True))

    if not my_5_star_ids:
        return []

    # 2. Find other users who liked at least one of those same books
    similar_users = User.objects.filter(
        ratings__book_id__in=my_5_star_ids, 
        ratings__rating=5
    ).exclude(id=current_user.id).distinct()

    suggested_books = set()

    # 3. Gather books from those similar users
    for user in similar_users:
        their_5_star_books = UserBookRating.objects.filter(
            user=user, 
            rating=5
        ).values_list('book_id', flat=True)
        
        # Add their books to our suggestion pile
        suggested_books.update(their_5_star_books)

    # 4. Filter out books I have already read
    books_i_read = UserBookRating.objects.filter(
        user=current_user
    ).values_list('book_id', flat=True)
    
    final_suggestions = suggested_books - set(books_i_read)

    # Return actual Book objects
    return Book.objects.filter(id__in=final_suggestions)