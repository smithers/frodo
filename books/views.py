from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login
from django.db import IntegrityError
from .models import Book, Author, UserFavoriteBook
from django.http import JsonResponse
from .utils import get_book_recommendations, smart_title_case

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
def add_favorite_view(request):
    results = []
    query = request.GET.get('q')
    
    if query:
        results = search_google_books(query)
        
    return render(request, 'add_favorite.html', {'results': results, 'query': query})

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
def save_favorite_view(request):
    if request.method == "POST":
        # Handle multiple books from add_favorite page
        titles = request.POST.getlist('title')
        authors = request.POST.getlist('author')
        isbns = request.POST.getlist('isbn')
        source = request.POST.get('source', '')

        # If we got single values (from my_books page), convert to lists
        if not titles:
            raw_title = request.POST.get('title')
            raw_author = request.POST.get('author')
            isbn = request.POST.get('isbn', '')
            
            if raw_title and raw_author:
                titles = [raw_title]
                authors = [raw_author]
                isbns = [isbn] if isbn else ['']

        saved_count = 0

        for raw_title, raw_author, isbn in zip(titles, authors, isbns):
            raw_title = (raw_title or "").strip()
            raw_author = (raw_author or "").strip()
            isbn = (isbn or "").strip() or None

            if not raw_title or not raw_author:
                continue

            # --- STEP 1: NORMALIZE DATA ---
            clean_title = smart_title_case(raw_title)
            clean_author_name = raw_author.strip().title()

            # --- STEP 2: HANDLE AUTHOR ---
            author, _ = Author.objects.get_or_create(
                name__iexact=clean_author_name,
                defaults={'name': clean_author_name}
            )

            # --- STEP 3: SMART BOOK LOOKUP ---
            book = None
            if isbn:
                book = Book.objects.filter(isbn=isbn).first()

            if not book:
                book = Book.objects.filter(
                    title__iexact=clean_title,
                    author=author
                ).first()

            if not book:
                try:
                    book = Book.objects.create(
                        title=clean_title,
                        author=author,
                        isbn=isbn
                    )
                except IntegrityError:
                    book = Book.objects.get(title=clean_title, author=author)

            # --- STEP 4: SAVE FAVORITE ---
            favorite, created = UserFavoriteBook.objects.get_or_create(
                user=request.user,
                book=book
            )
            if created:
                saved_count += 1

        if saved_count:
            if saved_count == 1:
                messages.success(request, f"Added {Book.objects.filter(title__iexact=smart_title_case(titles[0].strip())).first().title if titles else 'book'} to your favorites!")
            else:
                messages.success(request, f"Added {saved_count} book(s) to your favorites!")
        else:
            messages.warning(request, "No valid books were submitted.")

        # If the update came from the My Books page, send the user back there
        if source == "my_books":
            return redirect('my_books')

        return redirect('recommendations')

@login_required
def remove_favorite_view(request):
    """Remove a book from favorites"""
    if request.method == "POST":
        raw_title = request.POST.get('title', '').strip()
        raw_author = request.POST.get('author', '').strip()
        
        if raw_title and raw_author:
            clean_title = smart_title_case(raw_title)
            clean_author_name = raw_author.strip().title()
            
            author = Author.objects.filter(name__iexact=clean_author_name).first()
            if author:
                book = Book.objects.filter(title__iexact=clean_title, author=author).first()
                if book:
                    UserFavoriteBook.objects.filter(user=request.user, book=book).delete()
                    messages.success(request, f"Removed {book.title} from your favorites.")
    
    return redirect('my_books')

@login_required
def recommendation_view(request):
    # Ask the brain for the list
    recommended_data = get_book_recommendations(request.user)
    
    # Diagnostic info to help debug empty recommendations
    user_favorites = UserFavoriteBook.objects.filter(user=request.user)
    
    if user_favorites.exists():
        my_favorite_book_ids = set(user_favorites.values_list('book_id', flat=True))
        from django.contrib.auth.models import User
        similar_users = User.objects.filter(
            favorite_books__book_id__in=my_favorite_book_ids
        ).exclude(id=request.user.id).distinct()
        
        diagnostic_info = {
            'total_favorites': user_favorites.count(),
            'similar_users_count': similar_users.count(),
            'recommendations_count': len(recommended_data),
        }
    else:
        diagnostic_info = {
            'total_favorites': 0,
            'similar_users_count': 0,
            'recommendations_count': 0,
            'message': 'You need to add at least one book you love to get recommendations!',
        }
    
    context = {
        'recommendations': recommended_data,
        'diagnostic': diagnostic_info,
    }
    return render(request, 'recommendations.html', context)

@login_required
def my_books_view(request):
    # Fetch user's favorite books ordered by newest first
    user_favorites = UserFavoriteBook.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'my_books.html', {'favorites': user_favorites})
