from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Book, Author, UserBookRating

from .services import search_google_books

@login_required
def add_rating_view(request):
    results = []
    query = request.GET.get('q')
    
    if query:
        results = search_google_books(query)
        
    return render(request, 'add_rating.html', {'results': results, 'query': query})


@login_required
def save_rating_view(request):
    if request.method == "POST":
        raw_title = request.POST.get('title')
        raw_author = request.POST.get('author')
        isbn = request.POST.get('isbn')
        rating_value = int(request.POST.get('rating'))

        # --- STEP 1: NORMALIZE DATA ---
        # Python's .title() converts "THE OLD MAN" and "the old man" 
        # both to "The Old Man"
        clean_title = raw_title.strip().title() 
        clean_author_name = raw_author.strip().title()

        # --- STEP 2: HANDLE AUTHOR ---
        # We assume "Ernest Hemingway" is the same person regardless of case
        author, _ = Author.objects.get_or_create(
            name__iexact=clean_author_name,
            defaults={'name': clean_author_name}
        )

        # --- STEP 3: SMART BOOK LOOKUP (The Fix) ---
        
        # A. Try exact ISBN match first (Best case)
        book = Book.objects.filter(isbn=isbn).first()

        if not book:
            try:
                # Try to create it
                book = Book.objects.create(
                    title=clean_title, 
                    author=author, 
                    isbn=isbn
                )
            except IntegrityError:
                # If we hit here, it means another user created this exact Book
                # milliseconds ago. We catch the error and just fetch that book.
                book = Book.objects.get(title=clean_title, author=author)

        # --- STEP 4: SAVE RATING ---
        UserBookRating.objects.update_or_create(
            user=request.user,
            book=book,
            defaults={'rating': rating_value}
        )
        
        messages.success(request, f"Saved rating for {book.title}")
        return redirect('recommendations')
