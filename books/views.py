from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login
from django.db import IntegrityError
from .models import Book, Author, UserBookRating
from django.http import JsonResponse
from .utils import get_book_recommendations

from .services import search_google_books

def homepage_view(request):
    """Homepage view - accessible to all users, shows login form if not authenticated"""
    form = AuthenticationForm()
    
    if request.method == 'POST' and not request.user.is_authenticated:
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, f"Welcome back, {request.user.username}!")
            return redirect('my_books')
    
    return render(request, 'homepage.html', {'form': form})

def register_view(request):
    """Registration view - allows new users to create accounts"""
    if request.user.is_authenticated:
        return redirect('my_books')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been created successfully.")
            return redirect('my_books')
    else:
        form = UserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})

@login_required
def add_rating_view(request):
    results = []
    query = request.GET.get('q')
    
    if query:
        results = search_google_books(query)
        
    return render(request, 'add_rating.html', {'results': results, 'query': query})

@login_required
def book_autocomplete(request):
    query = request.GET.get('term', '') # jQuery UI uses 'term' to send what the user types
    
    if len(query) < 3:
        return JsonResponse([], safe=False)

    # Use your existing service function!
    results = search_google_books(query)
    
    # Reformat data specifically for jQuery UI Autocomplete
    suggestions = []
    for book in results:
        suggestions.append({
            'label': f"{book['title']} ({book['author']})", # What the user sees in the dropdown
            'value': book['title'],      # What fills the box when they click
            'author': book['author'],    # Hidden data we need
            'isbn': book['isbn']         # Hidden data we need
        })
        
    return JsonResponse(suggestions, safe=False)

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


@login_required
def recommendation_view(request):
    # Ask the brain for the list
    recommended_books = get_book_recommendations(request.user)
    
    context = {
        'books': recommended_books,
    }
    return render(request, 'recommendations.html', context)

@login_required
def my_books_view(request):
    # Fetch user's ratings ordered by newest first
    user_ratings = UserBookRating.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'my_books.html', {'ratings': user_ratings})