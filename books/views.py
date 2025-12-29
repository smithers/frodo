from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import IntegrityError
from .models import Book, Author, UserFavoriteBook
from django.http import JsonResponse
from .utils import get_book_recommendations, smart_title_case, generate_guest_username

from .services import search_books, get_book_details

def homepage_view(request):
    """Homepage view - accessible to all users, shows login form if not authenticated"""
    form = AuthenticationForm()
    # Remove Django's default autofocus to avoid auto-scrolling to login on mobile
    form.fields['username'].widget.attrs.pop('autofocus', None)
    
    if request.method == 'POST' and not request.user.is_authenticated:
        form = AuthenticationForm(request, data=request.POST)
        form.fields['username'].widget.attrs.pop('autofocus', None)
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

def add_favorite_view(request):
    results = []
    query = request.GET.get('q')
    
    if query:
        results = search_books(query)
        
    return render(request, 'add_favorite.html', {'results': results, 'query': query})

def book_autocomplete(request):
    query = request.GET.get('term', '') # jQuery UI uses 'term' to send what the user types
    
    if len(query) < 3:
        return JsonResponse([], safe=False)

    # Use the unified search function (database first, then Google API)
    results = search_books(query)
    
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

def save_favorite_view(request):
    if request.method == "POST":
        # Handle multiple books from add_favorite page
        titles = request.POST.getlist('title')
        authors = request.POST.getlist('author')
        isbns = request.POST.getlist('isbn')
        explanations = request.POST.getlist('explanation')
        source = request.POST.get('source', '')

        # If we got single values (from my_books page), convert to lists
        if not titles:
            raw_title = request.POST.get('title')
            raw_author = request.POST.get('author')
            isbn = request.POST.get('isbn', '')
            explanation = request.POST.get('explanation', '')
            
            if raw_title and raw_author:
                titles = [raw_title]
                authors = [raw_author]
                isbns = [isbn] if isbn else ['']
                explanations = [explanation] if explanation else ['']

        saved_count = 0

        # Ensure explanations list matches the length of other lists
        while len(explanations) < len(titles):
            explanations.append('')

        for raw_title, raw_author, isbn, explanation in zip(titles, authors, isbns, explanations):
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
            explanation_text = (explanation or "").strip()
            
            if request.user.is_authenticated:
                # Authenticated users: save to database
                favorite, created = UserFavoriteBook.objects.get_or_create(
                    user=request.user,
                    book=book,
                    defaults={'explanation': explanation_text}
                )
                # Update explanation if favorite already existed
                if not created and explanation_text:
                    favorite.explanation = explanation_text
                    favorite.save()
                if created:
                    saved_count += 1
            else:
                # Non-authenticated users: create or get guest user
                guest_user_id = request.session.get('guest_user_id')
                if guest_user_id:
                    try:
                        guest_user = User.objects.get(id=guest_user_id)
                    except User.DoesNotExist:
                        guest_user = None
                else:
                    guest_user = None
                
                if not guest_user:
                    # Create a new guest user with unique username
                    username = generate_guest_username()
                    guest_user = User.objects.create_user(
                        username=username,
                        password=User.objects.make_random_password(),
                        is_active=True
                    )
                    request.session['guest_user_id'] = guest_user.id
                
                # Save favorite to database using guest user
                favorite, created = UserFavoriteBook.objects.get_or_create(
                    user=guest_user,
                    book=book,
                    defaults={'explanation': explanation_text}
                )
                # Update explanation if favorite already existed
                if not created and explanation_text:
                    favorite.explanation = explanation_text
                    favorite.save()
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
                    if request.user.is_authenticated:
                        UserFavoriteBook.objects.filter(user=request.user, book=book).delete()
                        messages.success(request, f"Removed {book.title} from your favorites.")
                    else:
                        # Get guest user from session
                        guest_user_id = request.session.get('guest_user_id')
                        if guest_user_id:
                            try:
                                guest_user = User.objects.get(id=guest_user_id)
                                UserFavoriteBook.objects.filter(user=guest_user, book=book).delete()
                                messages.success(request, f"Removed {book.title} from your favorites.")
                            except User.DoesNotExist:
                                messages.warning(request, "Could not find your guest account.")
                        else:
                            messages.warning(request, "No favorites found to remove.")
    
    return redirect('my_books')

def recommendation_view(request):
    # Get favorite book IDs (from database or guest user)
    if request.user.is_authenticated:
        my_favorite_book_ids = set(
            UserFavoriteBook.objects.filter(user=request.user).values_list("book_id", flat=True)
        )
    else:
        # Get from guest user in session
        guest_user_id = request.session.get('guest_user_id')
        if guest_user_id:
            try:
                guest_user = User.objects.get(id=guest_user_id)
                my_favorite_book_ids = set(
                    UserFavoriteBook.objects.filter(user=guest_user).values_list("book_id", flat=True)
                )
            except User.DoesNotExist:
                my_favorite_book_ids = set()
        else:
            my_favorite_book_ids = set()
    
    if not my_favorite_book_ids:
        context = {
            'grouped_recommendations': [],
            'diagnostic': {
                'total_favorites': 0,
                'similar_users_count': 0,
                'recommendations_count': 0,
                'message': 'You need to add at least one book you love to get recommendations!',
            },
            'show_account_prompt': False,
        }
        return render(request, 'recommendations.html', context)
    
    # Find other users who also love at least one of those same books
    similar_users = (
        User.objects.filter(
            favorite_books__book_id__in=my_favorite_book_ids,
        )
    )
    if request.user.is_authenticated:
        similar_users = similar_users.exclude(id=request.user.id)
    similar_users = similar_users.distinct()
    
    # For each recommended book, track which similar user(s) recommended it
    # and count the overlap in favorite books
    book_recommendations = {}  # book_id -> {book, similar_user, overlap_count}
    
    for user in similar_users:
        # Get all books this user loves
        their_favorite_book_ids = set(
            UserFavoriteBook.objects.filter(user=user).values_list("book_id", flat=True)
        )
        
        # Find overlapping books: books BOTH users love
        overlapping_book_ids = my_favorite_book_ids & their_favorite_book_ids
        overlap_count = len(overlapping_book_ids)
        
        # Get the actual Book objects for overlapping favorites
        overlapping_books = Book.objects.filter(id__in=overlapping_book_ids)
        overlapping_titles = [book.title for book in overlapping_books]
        
        # For each book they love that I haven't favorited, add it as a recommendation
        for book_id in their_favorite_book_ids:
            if book_id not in my_favorite_book_ids:
                # If we haven't seen this book yet, or if this user has more overlap, use this user
                if book_id not in book_recommendations or overlap_count > book_recommendations[book_id]['overlap_count']:
                    book_recommendations[book_id] = {
                        'book_id': book_id,
                        'similar_user': user,
                        'overlap_count': overlap_count,
                        'overlapping_titles': overlapping_titles,
                    }
    
    # Convert to list of dictionaries with book objects
    recommended_data = []
    for rec_data in book_recommendations.values():
        book = Book.objects.get(id=rec_data['book_id'])
        recommended_data.append({
            'book': book,
            'similar_user': rec_data['similar_user'],
            'overlap_count': rec_data['overlap_count'],
            'overlapping_titles': rec_data['overlapping_titles'],
        })
    
    # Sort by overlap_count (descending) - users with more overlapping favorites first
    recommended_data.sort(key=lambda x: x['overlap_count'], reverse=True)
    
    # Group recommendations by similar_user
    grouped_recommendations = {}
    for rec in recommended_data:
        user_id = rec['similar_user'].id
        if user_id not in grouped_recommendations:
            grouped_recommendations[user_id] = {
                'similar_user': rec['similar_user'],
                'overlap_count': rec['overlap_count'],
                'overlapping_titles': rec['overlapping_titles'],
                'recommended_books': []
            }
        # Get the explanation from the similar user's favorite record
        favorite = UserFavoriteBook.objects.filter(
            user=rec['similar_user'],
            book=rec['book']
        ).first()
        explanation = favorite.explanation if favorite else ''
        
        grouped_recommendations[user_id]['recommended_books'].append({
            'book': rec['book'],
            'explanation': explanation
        })
    
    # Convert to list and sort by overlap_count (descending)
    grouped_list = list(grouped_recommendations.values())
    grouped_list.sort(key=lambda x: x['overlap_count'], reverse=True)
    
    # Diagnostic info
    total_favorites = len(my_favorite_book_ids)
    diagnostic_info = {
        'total_favorites': total_favorites,
        'similar_users_count': similar_users.count(),
        'recommendations_count': len(recommended_data),
    }
    
    # Check if user is not authenticated but has favorite books
    show_account_prompt = not request.user.is_authenticated and total_favorites > 0
    
    # Check if there are similar users but no recommendations
    show_no_new_books_message = diagnostic_info['similar_users_count'] > 0 and len(recommended_data) == 0
    
    context = {
        'grouped_recommendations': grouped_list,
        'diagnostic': diagnostic_info,
        'show_account_prompt': show_account_prompt,
        'show_no_new_books_message': show_no_new_books_message,
    }
    return render(request, 'recommendations.html', context)

def terms_of_use_view(request):
    """Terms of Use page"""
    return render(request, 'terms_of_use.html')

def privacy_policy_view(request):
    """Privacy Policy page"""
    return render(request, 'privacy_policy.html')

def my_books_view(request):
    if request.user.is_authenticated:
        # Fetch user's favorite books ordered by newest first
        user_favorites = UserFavoriteBook.objects.filter(user=request.user).order_by('-created_at')
        return render(request, 'my_books.html', {'favorites': user_favorites})
    else:
        # For non-authenticated users, get books from guest user
        guest_user_id = request.session.get('guest_user_id')
        if guest_user_id:
            try:
                guest_user = User.objects.get(id=guest_user_id)
                user_favorites = UserFavoriteBook.objects.filter(user=guest_user).order_by('-created_at')
                return render(request, 'my_books.html', {'favorites': user_favorites})
            except User.DoesNotExist:
                # Guest user doesn't exist, return empty list
                return render(request, 'my_books.html', {'favorites': []})
        else:
            # No guest user yet, return empty list
            return render(request, 'my_books.html', {'favorites': []})

def book_info_view(request):
    """API endpoint to get book information from Google Books"""
    title = request.GET.get('title', '').strip()
    author = request.GET.get('author', '').strip()
    
    if not title or not author:
        return JsonResponse({'error': 'Title and author are required'}, status=400)
    
    book_details = get_book_details(title, author)
    
    if book_details:
        return JsonResponse(book_details)
    else:
        return JsonResponse({'error': 'Book information not found'}, status=404)
