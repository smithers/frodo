from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordResetForm
from .forms import UserRegistrationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.urls import reverse, reverse_lazy
from django.contrib.auth.forms import SetPasswordForm
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
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
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
            # Redirect to our custom completion page using absolute URL
            from django.urls import reverse
            return redirect(reverse('password_reset_complete'))
        # If form is invalid, we'll show errors below
    else:
        form = SetPasswordForm(user) if validlink and user else None
    
    # Build a simple HTML form directly (bypassing template to avoid any issues)
    from django.http import HttpResponse
    from django.middleware.csrf import get_token
    
    csrf_token = get_token(request)
    
    # Build error messages
    errors_html = ""
    if form and form.errors:
        errors_html = '<div style="color: #8b0000; padding: 15px; background: #ffffff; border-left: 4px solid #8b0000; margin-bottom: 25px;">'
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
                body {{ font-family: 'Lora', serif; background: #ffffff; padding: 40px 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 50px; border: 2px solid #1a1a1a; }}
                h1 {{ color: #1a1a1a; text-align: center; border-bottom: 4px solid #8b0000; padding-bottom: 20px; margin-bottom: 30px; }}
                label {{ display: block; margin-bottom: 8px; font-weight: 400; color: #1a1a1a; text-transform: uppercase; letter-spacing: 0.5px; font-size: 0.9em; }}
                input[type="password"] {{ width: 100%; padding: 12px 15px; border: 2px solid #1a1a1a; border-radius: 0; font-size: 1em; box-sizing: border-box; margin-bottom: 25px; }}
                input[type="password"]:focus {{ outline: none; border-color: #8b0000; border-width: 2px; }}
                button {{ width: 100%; background-color: #1a1a1a; color: #ffffff; padding: 15px; border: 2px solid #1a1a1a; font-size: 1em; font-weight: 400; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; }}
                button:hover {{ background-color: #8b0000; border-color: #8b0000; }}
                .error {{ color: #8b0000; font-size: 0.95em; margin-top: 8px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Enter New Password</h1>
                <p style="text-align: center; color: #1a1a1a; margin-bottom: 40px; font-style: italic;">Please enter your new password twice so we can verify you typed it correctly.</p>
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
                    <a href="/" style="color: #8b0000; font-weight: 600; text-decoration: none; border-bottom: 1px solid #8b0000;">Back to Login</a>
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
                h1 {{ color: #8b0000; }}
                .error {{ color: #8b0000; padding: 20px; background: #ffffff; border-left: 4px solid #8b0000; }}
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
    # Build HTML directly to avoid any template issues
    from django.http import HttpResponse
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Password Reset Complete - Great Minds Read Alike</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Lora', serif; background: #ffffff; padding: 40px 20px; }
            .container { max-width: 600px; margin: 0 auto; background: #ffffff; padding: 50px; border: 2px solid #1a1a1a; text-align: center; }
            h1 { color: #1a1a1a; border-bottom: 4px solid #8b0000; padding-bottom: 20px; margin-bottom: 30px; margin-top: 0; }
            p { color: #1a1a1a; margin-bottom: 20px; font-size: 1.1em; line-height: 1.8; }
            a { display: inline-block; background-color: #1a1a1a; color: #ffffff; padding: 15px 30px; border: 2px solid #1a1a1a; font-size: 1em; font-weight: 400; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; text-decoration: none; transition: all 0.3s ease; margin-top: 40px; }
            a:hover { background-color: #8b0000; border-color: #8b0000; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
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
