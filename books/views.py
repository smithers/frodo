from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm
from .forms import UserRegistrationForm, FeedbackForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from django.urls import reverse, reverse_lazy
from django.contrib.auth.forms import SetPasswordForm
from .models import Book, Author, UserFavoriteBook, Feedback, ToBeReadBook, UserEmailPreferences
from django.http import JsonResponse
from .utils import get_book_recommendations, smart_title_case, generate_guest_username
from .services import search_books, get_book_details
from datetime import date, timedelta
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.db.models import Count, Max
import hashlib
import logging


def _send_new_recommendation_emails(request):
    """
    Send email notifications to users when another user (authenticated or guest) 
    adds favorites that overlap with their favorites and includes new books they don't have.
    """
    # Get the user who just added favorites (User B)
    if request.user.is_authenticated:
        user_b = request.user
    else:
        # Get guest user from session
        guest_user_id = request.session.get('guest_user_id')
        if not guest_user_id:
            return  # No user to check
        try:
            user_b = User.objects.get(id=guest_user_id)
        except User.DoesNotExist:
            return  # Guest user doesn't exist
    
    # Get all of User B's favorite book IDs
    user_b_favorite_book_ids = set(
        UserFavoriteBook.objects.filter(user=user_b).values_list("book_id", flat=True)
    )
    
    if not user_b_favorite_book_ids:
        return  # User B has no favorites
    
    # Find all other users (User A) who share at least one favorite with User B
    # and have an email address (authenticated users only)
    similar_users = (
        User.objects.filter(
            favorite_books__book_id__in=user_b_favorite_book_ids,
            email__isnull=False,
            email__gt='',  # Email is not empty
            is_active=True
        )
        .exclude(id=user_b.id)  # Exclude User B
        .distinct()
    )
    
    # Get site URL for email links
    site_url = getattr(settings, 'SITE_BASE_URL', '')
    if not site_url:
        # Try to build from request, otherwise use default Heroku domain
        try:
            site_url = request.build_absolute_uri('/').rstrip('/')
            # If site_url is malformed (e.g., just '/'), use default
            if not site_url or site_url.startswith('http:///') or site_url.startswith('https:///'):
                site_url = 'https://www.greatmindsreadalike.org'
        except:
            site_url = 'https://www.greatmindsreadalike.org'
    
    # Ensure site_url includes "www." if it's greatmindsreadalike.org
    if site_url and 'greatmindsreadalike.org' in site_url and 'www.' not in site_url:
        site_url = site_url.replace('https://greatmindsreadalike.org', 'https://www.greatmindsreadalike.org')
        site_url = site_url.replace('http://greatmindsreadalike.org', 'https://www.greatmindsreadalike.org')
    
    # Ensure site_url doesn't end with a slash (except for root)
    if site_url and site_url != '/' and site_url.endswith('/'):
        site_url = site_url.rstrip('/')
    
    # For each similar user (User A), check if they should receive a weekly email
    emails_sent = 0
    for user_a in similar_users:
        # Check if user has unsubscribed from recommendation emails
        email_prefs, _ = UserEmailPreferences.objects.get_or_create(user=user_a)
        if not email_prefs.receive_recommendation_emails:
            continue  # Skip this user, they've unsubscribed
        
        # Check if it's been at least 7 days since the last recommendation email
        now = timezone.now()
        if email_prefs.last_recommendation_email_sent:
            time_since_last_email = now - email_prefs.last_recommendation_email_sent
            if time_since_last_email < timedelta(days=7):
                continue  # Skip this user, it hasn't been a week yet
        
        # Get User A's favorite book IDs
        user_a_favorite_book_ids = set(
            UserFavoriteBook.objects.filter(user=user_a).values_list("book_id", flat=True)
        )
        
        # Calculate the date 7 days ago
        seven_days_ago = now - timedelta(days=7)
        
        # Find ALL users who share favorites with User A AND added those favorites in the past 7 days
        # This collects only recent recommendations
        recent_similar_users = (
            User.objects.filter(
                favorite_books__book_id__in=user_a_favorite_book_ids,
                favorite_books__created_at__gte=seven_days_ago
            )
            .exclude(id=user_a.id)
            .distinct()
        )
        
        # Collect all books from recent similar users that User A doesn't have
        # Only include books that were added as favorites in the past 7 days
        all_new_books = set()
        for similar_user in recent_similar_users:
            # Get books this user added as favorites in the past 7 days
            recent_favorites = UserFavoriteBook.objects.filter(
                user=similar_user,
                created_at__gte=seven_days_ago
            ).values_list("book_id", flat=True)
            
            similar_user_recent_favorite_book_ids = set(recent_favorites)
            new_books_from_user = similar_user_recent_favorite_book_ids - user_a_favorite_book_ids
            all_new_books.update(new_books_from_user)
        
        if all_new_books:
            # Get the Book objects
            new_books = Book.objects.filter(id__in=all_new_books).select_related('author')
            
            # Only send email if there are new books
            if new_books.exists():
                # Calculate total recommendations count (similar to recommendation_view logic)
                # Find all users who share favorites with User A
                all_similar_users = (
                    User.objects.filter(
                        favorite_books__book_id__in=user_a_favorite_book_ids,
                    )
                    .exclude(id=user_a.id)
                    .distinct()
                )
                
                # Count all unique recommended books (not just from past 7 days)
                all_recommended_book_ids = set()
                for similar_user in all_similar_users:
                    their_favorite_book_ids = set(
                        UserFavoriteBook.objects.filter(user=similar_user).values_list("book_id", flat=True)
                    )
                    # Books they love that User A doesn't have
                    recommended_from_user = their_favorite_book_ids - user_a_favorite_book_ids
                    all_recommended_book_ids.update(recommended_from_user)
                
                total_recommendations_count = len(all_recommended_book_ids)
                
                # Limit to 10 books for the email
                books_for_email = new_books[:10]
                additional_count = max(0, total_recommendations_count - 10)
                
                try:
                    subject = 'Your Weekly Book Recommendations!'
                    
                    # Generate unsubscribe token
                    token = default_token_generator.make_token(user_a)
                    uid = urlsafe_base64_encode(force_bytes(user_a.pk))
                    unsubscribe_path = reverse('unsubscribe_recommendations', kwargs={'uidb64': uid, 'token': token})
                    # Use site_url if available, otherwise build from request
                    if site_url:
                        unsubscribe_url = f"{site_url}{unsubscribe_path}"
                    else:
                        unsubscribe_url = request.build_absolute_uri(unsubscribe_path)
                    
                    # Create email content
                    html_message = render_to_string('registration/email_new_recommendations.html', {
                        'user': user_a,
                        'new_books': books_for_email,
                        'total_recommendations_count': total_recommendations_count,
                        'additional_count': additional_count,
                        'site_url': site_url,
                        'site_name': 'Great Minds Read Alike',
                        'unsubscribe_url': unsubscribe_url,
                    })
                    plain_message = f"Hi {user_a.username},\n\n"
                    plain_message += "Great news! Other readers who share some of your favorite books have added new favorites that you might love, too.\n\n"
                    plain_message += "Here are the books they added that you haven't listed as favorites yet:\n\n"
                    for book in books_for_email:
                        plain_message += f"- {book.title} by {book.author.name}\n"
                    if additional_count > 0:
                        plain_message += f"\nThere are {additional_count} more recommendations waiting for you on your recommendations page!\n"
                    plain_message += f"\nVisit {site_url}{reverse('recommendations')} to see more recommendations!\n\n"
                    plain_message += f"\nIf you no longer wish to receive these emails, you can unsubscribe here: {unsubscribe_url}\n\n"
                    plain_message += "Happy reading!\n— Great Minds Read Alike"
                    
                    from_email = settings.DEFAULT_FROM_EMAIL
                    send_mail(
                        subject,
                        plain_message,
                        from_email,
                        [user_a.email],
                        html_message=html_message,
                        fail_silently=True,  # Don't break the flow if email fails
                    )
                    
                    # Update the timestamp for when the email was sent
                    email_prefs.last_recommendation_email_sent = now
                    email_prefs.save()
                    
                    emails_sent += 1
                except Exception as e:
                    # Log error but don't break the flow
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error sending recommendation email to {user_a.email}: {str(e)}")
    
    return emails_sent

def _merge_guest_favorites(request, user):
    """
    Move favorites from a session-backed guest user into the authenticated user,
    then clean up the guest account.
    """
    guest_id = request.session.pop('guest_user_id', None)
    if not guest_id or guest_id == user.id:
        return

    try:
        guest_user = User.objects.get(id=guest_id)
    except User.DoesNotExist:
        return

    for fav in UserFavoriteBook.objects.filter(user=guest_user):
        UserFavoriteBook.objects.get_or_create(
            user=user,
            book=fav.book,
            defaults={'explanation': fav.explanation},
        )

    UserFavoriteBook.objects.filter(user=guest_user).delete()
    guest_user.delete()

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
            _merge_guest_favorites(request, request.user)
            messages.success(request, f"Welcome back, {request.user.username}!")
            return redirect('my_books')
    
    # Count unique users who have favorite books and total favorites
    unique_users_count = UserFavoriteBook.objects.values('user').distinct().count()
    favorites_count = UserFavoriteBook.objects.count()

    # Top 10 most favorited books (title, author, count)
    top_favorites = (
        UserFavoriteBook.objects.values('book__title', 'book__author__name')
        .annotate(count=Count('id'))
        .order_by('-count', 'book__title')[:10]
    )
    
    # 10 most recently favorited books (unique books, ordered by most recent favorite date)
    recent_favorites = (
        UserFavoriteBook.objects.values('book__title', 'book__author__name')
        .annotate(most_recent=Max('created_at'))
        .order_by('-most_recent')[:10]
    )
    
    return render(request, 'homepage.html', {
        'form': form,
        'unique_users_count': unique_users_count,
        'favorites_count': favorites_count,
        'top_favorites': top_favorites,
        'recent_favorites': recent_favorites,
    })


def sitemap_view(request):
    """Simple XML sitemap for public pages."""
    base_urls = [
        reverse('home'),
        reverse('add_favorite'),
        reverse('my_books'),
        reverse('recommendations'),
        reverse('register'),
        reverse('terms_of_use'),
        reverse('privacy_policy'),
        reverse('login'),
    ]
    today = date.today().isoformat()

    site_base = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')

    entries = []
    for url in base_urls:
        loc = f"{site_base}{url}" if site_base else request.build_absolute_uri(url)
        entries.append(f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(entries)}
</urlset>
"""
    return HttpResponse(xml, content_type="application/xml")


def robots_txt(request):
    """Allow all crawlers."""
    lines = [
        "User-agent: *",
        "Disallow:",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def register_view(request):
    """Registration view - allows new users to create accounts"""
    if request.user.is_authenticated:
        return redirect('my_books')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            _merge_guest_favorites(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been created successfully.")
            return redirect('my_books')
    else:
        form = UserRegistrationForm()
    
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
            
            # Send email notifications to users who share favorites
            _send_new_recommendation_emails(request)
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


@require_POST
def feedback_submit(request):
    """Accept feedback submissions from the floating tab."""
    if not request.session.session_key:
        request.session.save()

    form = FeedbackForm(request.POST)
    if form.is_valid():
        feedback = form.save(commit=False)
        feedback.user = request.user if request.user.is_authenticated else None
        feedback.page_url = request.POST.get("page_url", request.META.get("HTTP_REFERER", ""))
        feedback.user_agent = request.META.get("HTTP_USER_AGENT", "")
        feedback.session_id = request.session.session_key or ""
        ip = request.META.get("REMOTE_ADDR", "")
        feedback.ip_hash = hashlib.sha256(ip.encode()).hexdigest() if ip else ""
        feedback.save()
        return JsonResponse({"ok": True})

    return JsonResponse({"ok": False, "errors": form.errors}, status=400)

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


@login_required
def tbr_list_view(request):
    """Display and manage the user's To Be Read (TBR) list."""
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        author_name = (request.POST.get("author") or "").strip()
        note = (request.POST.get("note") or "").strip()

        if not title or not author_name:
            messages.error(request, "Please provide both a title and an author.")
            return redirect("tbr_list")

        clean_title = smart_title_case(title)
        clean_author_name = author_name.strip().title()

        # Resolve or create author
        author = Author.objects.filter(name__iexact=clean_author_name).first()
        if not author:
            author = Author.objects.create(name=clean_author_name)

        # Resolve or create book
        book = Book.objects.filter(title__iexact=clean_title, author=author).first()
        if not book:
            book = Book.objects.create(title=clean_title, author=author)

        # Save to TBR list
        tbr_entry, created = ToBeReadBook.objects.get_or_create(
            user=request.user,
            book=book,
            defaults={"note": note},
        )

        if not created and note:
            tbr_entry.note = note
            tbr_entry.save()

        if created:
            messages.success(request, f"Added {book.title} to your TBR list.")
        else:
            messages.info(request, f"{book.title} is already on your TBR list.")

        return redirect("tbr_list")

    tbr_items = (
        ToBeReadBook.objects.filter(user=request.user)
        .select_related("book", "book__author")
        .order_by("-created_at")
    )
    return render(request, "tbr_list.html", {"tbr_items": tbr_items})


@login_required
@require_POST
def remove_tbr_view(request):
    """Remove a book from the user's TBR list."""
    title = (request.POST.get("title") or "").strip()
    author_name = (request.POST.get("author") or "").strip()

    if title and author_name:
        clean_title = smart_title_case(title)
        clean_author_name = author_name.strip().title()

        author = Author.objects.filter(name__iexact=clean_author_name).first()
        if author:
            book = Book.objects.filter(title__iexact=clean_title, author=author).first()
            if book:
                deleted, _ = ToBeReadBook.objects.filter(user=request.user, book=book).delete()
                if deleted:
                    messages.success(request, f"Removed {book.title} from your TBR list.")
                else:
                    messages.warning(request, "That book was not found in your TBR list.")
                return redirect("tbr_list")

    messages.warning(request, "Could not find that book in your TBR list.")
    return redirect("tbr_list")

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

def forgot_username_view(request):
    """View to recover username by email"""
    if request.user.is_authenticated:
        return redirect('my_books')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'registration/forgot_username.html')
        
        # Find users with this email
        users = User.objects.filter(email=email, is_active=True)
        
        if users.exists():
            # Send email with username(s)
            usernames = [user.username for user in users]
            subject = 'Your Username Recovery'
            
            # Create email content
            html_message = render_to_string('registration/email_username_recovery.html', {
                'usernames': usernames,
                'site_name': 'Great Minds Read Alike',
            })
            plain_message = f"Your username(s): {', '.join(usernames)}"
            
            try:
                from_email = settings.DEFAULT_FROM_EMAIL
                send_mail(
                    subject,
                    plain_message,
                    from_email,
                    [email],
                    html_message=html_message,
                    fail_silently=False,
                )
                messages.success(request, 'An email with your username(s) has been sent to your email address.')
                return render(request, 'registration/forgot_username_done.html')
            except Exception as e:
                # Include the from email in error message for debugging
                messages.error(request, f'Error sending email from {settings.DEFAULT_FROM_EMAIL}: {str(e)}. Please check that this email address is verified in SendGrid.')
        else:
            # Don't reveal if email exists or not (security best practice)
            messages.success(request, 'If an account exists with that email, you will receive an email with your username(s).')
            return render(request, 'registration/forgot_username_done.html')
    
    return render(request, 'registration/forgot_username.html')

def password_reset_view(request):
    """Custom password reset view that shows success message on same page"""
    if request.user.is_authenticated:
        return redirect('my_books')
    
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            # Get all users with this email
            users = User.objects.filter(email__iexact=email, is_active=True)
            
            if users.exists():
                # Use Django's password reset email sending
                for user in users:
                    # Generate password reset token
                    token = default_token_generator.make_token(user)
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    
                    # Build reset URL
                    reset_url = request.build_absolute_uri(
                        reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                    )
                    
                    # Send email
                    subject = 'Password Reset Request'
                    html_message = render_to_string('registration/email_password_reset.html', {
                        'user': user,
                        'protocol': request.scheme,
                        'domain': request.get_host(),
                        'uid': uid,
                        'token': token,
                        'reset_url': reset_url,
                    })
                    plain_message = f"Please go to the following page and choose a new password:\n\n{reset_url}\n\nIf you didn't request this, please ignore this email."
                    
                    try:
                        from_email = settings.DEFAULT_FROM_EMAIL
                        send_mail(
                            subject,
                            plain_message,
                            from_email,
                            [email],
                            html_message=html_message,
                            fail_silently=False,
                        )
                    except Exception as e:
                        # Include the from email in error message for debugging
                        messages.error(request, f'Error sending email from {settings.DEFAULT_FROM_EMAIL}: {str(e)}. Please check that this email address is verified in SendGrid.')
                        return render(request, 'registration/password_reset.html', {'form': form})
            
            # Always show success message (security best practice - don't reveal if email exists)
            messages.success(request, 'If an account exists with that email address, you will receive password reset instructions shortly. Please check your email and spam folder.')
            # Re-render the form (now empty) with success message
            form = PasswordResetForm()
    else:
        form = PasswordResetForm()
    
    return render(request, 'registration/password_reset.html', {'form': form})

def password_reset_confirm_view(request, uidb64, token):
    """Custom password reset confirm view - completely custom, no Django admin redirects"""
    if request.user.is_authenticated:
        return redirect('my_books')
    
    # Decode user ID
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    # Validate token
    validlink = False
    if user is not None:
        if default_token_generator.check_token(user, token):
            validlink = True
    
    # Handle POST request
    if request.method == 'POST' and validlink and user:
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your password has been reset successfully. You can now log in with your new password.')
            return redirect('password_reset_complete')
        # If form is invalid, we'll show errors below
    else:
        form = SetPasswordForm(user) if validlink and user else None
    
    # Build HTML directly (this was working before)
    from django.http import HttpResponse
    from django.middleware.csrf import get_token
    
    csrf_token = get_token(request)
    
    # Build error messages
    errors_html = ""
    if form and form.errors:
        errors_html = '<div style="color: #cc785c; padding: 15px; background: #ffffff; border-left: 4px solid #cc785c; margin-bottom: 25px;">'
        for field, error_list in form.errors.items():
            for error in error_list:
                errors_html += f'<p style="margin: 5px 0;"><strong>{field}:</strong> {error}</p>'
        errors_html += '</div>'
    
    if validlink and form:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Enter New Password - Great Minds Read Alike</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: 'Lora', serif; background: #EBDBBC; padding: 40px 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 50px; border: 2px solid #40403E; }}
                h1 {{ color: #40403E; text-align: center; border-bottom: 4px solid #cc785c; padding-bottom: 20px; margin-bottom: 30px; }}
                label {{ display: block; margin-bottom: 8px; font-weight: 400; color: #40403E; text-transform: uppercase; letter-spacing: 0.5px; font-size: 0.9em; }}
                input[type="password"] {{ width: 100%; padding: 12px 15px; border: 2px solid #40403E; border-radius: 0; font-size: 1em; box-sizing: border-box; margin-bottom: 25px; }}
                input[type="password"]:focus {{ outline: none; border-color: #cc785c; border-width: 2px; }}
                button {{ width: 100%; background-color: #40403E; color: #ffffff; padding: 15px; border: 2px solid #40403E; font-size: 1em; font-weight: 400; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; }}
                button:hover {{ background-color: #cc785c; border-color: #cc785c; }}
                .error {{ color: #cc785c; font-size: 0.95em; margin-top: 8px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Enter New Password</h1>
                <p style="text-align: center; color: #40403E; margin-bottom: 40px; font-style: italic;">Please enter your new password twice so we can verify you typed it correctly.</p>
                {errors_html}
                <form method="post">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
                    <label for="id_new_password1">New Password:</label>
                    <input type="password" name="new_password1" id="id_new_password1" required>
                    <label for="id_new_password2">Confirm New Password:</label>
                    <input type="password" name="new_password2" id="id_new_password2" required>
                    <button type="submit">Change Password</button>
                </form>
                <p style="text-align: center; margin-top: 25px;">
                    <a href="/" style="color: #cc785c; font-weight: 600; text-decoration: none; border-bottom: 1px solid #cc785c;">Back to Login</a>
                </p>
            </div>
        </body>
        </html>
        """
    else:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Password Reset Invalid - Great Minds Read Alike</title>
            <style>
                body {{ font-family: Arial; padding: 50px; max-width: 600px; margin: 0 auto; }}
                h1 {{ color: #cc785c; }}
                .error {{ color: #cc785c; padding: 20px; background: #ffffff; border-left: 4px solid #cc785c; }}
            </style>
        </head>
        <body>
            <h1>Password Reset Invalid</h1>
            <div class="error">
                <p><strong>The password reset link was invalid, possibly because it has already been used.</strong></p>
                <p>Please request a new password reset.</p>
            </div>
            <p><a href="/password-reset/">Request New Reset Link</a></p>
        </body>
        </html>
        """
    
    response = HttpResponse(html, content_type="text/html")
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def password_reset_complete_view(request):
    """Custom password reset complete view"""
    # Build HTML directly (this was working before)
    from django.http import HttpResponse
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Password Reset Complete - Great Minds Read Alike</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Lora', serif; background: #EBDBBC; padding: 40px 20px; }
            .container { max-width: 600px; margin: 0 auto; background: #ffffff; padding: 50px; border: 2px solid #40403E; text-align: center; }
            h1 { color: #40403E; border-bottom: 4px solid #cc785c; padding-bottom: 20px; margin-bottom: 30px; margin-top: 0; }
            p { color: #40403E; margin-bottom: 20px; font-size: 1.1em; line-height: 1.8; }
            a { display: inline-block; background-color: #40403E; color: #ffffff; padding: 15px 30px; border: 2px solid #40403E; font-size: 1em; font-weight: 400; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; text-decoration: none; transition: all 0.3s ease; margin-top: 40px; }
            a:hover { background-color: #cc785c; border-color: #cc785c; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Password Reset Complete</h1>
            <p>Your password has been set. You may go ahead and log in now.</p>
            <a href="/">Log In</a>
        </div>
    </body>
    </html>
    """
    response = HttpResponse(html, content_type="text/html")
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def unsubscribe_recommendations_view(request, uidb64, token):
    """Handle unsubscribe from recommendation emails"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        # Token is valid, unsubscribe the user
        email_prefs, created = UserEmailPreferences.objects.get_or_create(user=user)
        email_prefs.receive_recommendation_emails = False
        email_prefs.unsubscribed_at = timezone.now()
        email_prefs.save()
        
        # Render success page
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Unsubscribed - Great Minds Read Alike</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: 'Lora', serif; background: #EBDBBC; padding: 40px 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 50px; border: 2px solid #40403E; text-align: center; }}
                h1 {{ color: #40403E; border-bottom: 4px solid #cc785c; padding-bottom: 20px; margin-bottom: 30px; margin-top: 0; }}
                p {{ color: #40403E; margin-bottom: 20px; font-size: 1.1em; line-height: 1.8; }}
                a {{ display: inline-block; background-color: #40403E; color: #ffffff; padding: 15px 30px; border: 2px solid #40403E; font-size: 1em; font-weight: 400; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; text-decoration: none; transition: all 0.3s ease; margin-top: 40px; }}
                a:hover {{ background-color: #cc785c; border-color: #cc785c; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Unsubscribed</h1>
                <p>You have been successfully unsubscribed from recommendation emails.</p>
                <p>You will no longer receive emails when other readers add new favorites that match your interests.</p>
                <a href="{reverse('home')}">Return to Home</a>
            </div>
        </body>
        </html>
        """
        response = HttpResponse(html, content_type="text/html")
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    else:
        # Invalid token
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Invalid Link - Great Minds Read Alike</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: 'Lora', serif; background: #EBDBBC; padding: 40px 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 50px; border: 2px solid #40403E; text-align: center; }}
                h1 {{ color: #40403E; border-bottom: 4px solid #cc785c; padding-bottom: 20px; margin-bottom: 30px; margin-top: 0; }}
                p {{ color: #40403E; margin-bottom: 20px; font-size: 1.1em; line-height: 1.8; }}
                a {{ display: inline-block; background-color: #40403E; color: #ffffff; padding: 15px 30px; border: 2px solid #40403E; font-size: 1em; font-weight: 400; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; text-decoration: none; transition: all 0.3s ease; margin-top: 40px; }}
                a:hover {{ background-color: #cc785c; border-color: #cc785c; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Invalid Link</h1>
                <p>This unsubscribe link is invalid or has expired.</p>
                <p>If you continue to receive emails, please contact support.</p>
                <a href="{reverse('home')}">Return to Home</a>
            </div>
        </body>
        </html>
        """
        response = HttpResponse(html, content_type="text/html")
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
