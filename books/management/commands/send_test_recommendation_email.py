from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.utils import timezone
from django.urls import reverse
from books.models import Book, UserFavoriteBook, UserEmailPreferences
from datetime import timedelta


class Command(BaseCommand):
    help = 'Send a test recommendation email to a specific user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to send test email to')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" does not exist.'))
            return
        
        if not user.email:
            self.stdout.write(self.style.ERROR(f'User "{username}" does not have an email address.'))
            return
        
        self.stdout.write(f'Sending test recommendation email to {user.username} ({user.email})...')
        
        # Get User A's favorite book IDs
        user_a_favorite_book_ids = set(
            UserFavoriteBook.objects.filter(user=user).values_list("book_id", flat=True)
        )
        
        if not user_a_favorite_book_ids:
            self.stdout.write(self.style.WARNING(f'User "{username}" has no favorite books. Cannot generate recommendations.'))
            return
        
        # Calculate the date 7 days ago
        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)
        
        # Find ALL users who share favorites with User A AND added those favorites in the past 7 days
        recent_similar_users = (
            User.objects.filter(
                favorite_books__book_id__in=user_a_favorite_book_ids,
                favorite_books__created_at__gte=seven_days_ago
            )
            .exclude(id=user.id)
            .distinct()
        )
        
        # Collect all books from recent similar users that User A doesn't have
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
        
        if not all_new_books:
            # If no recent books, get all recommendations (for testing purposes)
            all_similar_users = (
                User.objects.filter(
                    favorite_books__book_id__in=user_a_favorite_book_ids,
                )
                .exclude(id=user.id)
                .distinct()
            )
            
            for similar_user in all_similar_users:
                their_favorite_book_ids = set(
                    UserFavoriteBook.objects.filter(user=similar_user).values_list("book_id", flat=True)
                )
                new_books_from_user = their_favorite_book_ids - user_a_favorite_book_ids
                all_new_books.update(new_books_from_user)
        
        if not all_new_books:
            self.stdout.write(self.style.WARNING(f'No recommendations found for user "{username}".'))
            return
        
        # Get the Book objects
        new_books = Book.objects.filter(id__in=all_new_books).select_related('author')
        
        # Calculate total recommendations count
        all_similar_users = (
            User.objects.filter(
                favorite_books__book_id__in=user_a_favorite_book_ids,
            )
            .exclude(id=user.id)
            .distinct()
        )
        
        # Count all unique recommended books
        all_recommended_book_ids = set()
        for similar_user in all_similar_users:
            their_favorite_book_ids = set(
                UserFavoriteBook.objects.filter(user=similar_user).values_list("book_id", flat=True)
            )
            recommended_from_user = their_favorite_book_ids - user_a_favorite_book_ids
            all_recommended_book_ids.update(recommended_from_user)
        
        total_recommendations_count = len(all_recommended_book_ids)
        
        # Limit to 10 books for the email
        books_for_email = new_books[:10]
        additional_count = max(0, total_recommendations_count - 10)
        
        # Get site URL
        site_url = getattr(settings, 'SITE_BASE_URL', '')
        if not site_url or site_url == '/' or site_url.startswith('http:///') or site_url.startswith('https:///'):
            site_url = 'https://greatmindsreadalike.org'
        # Ensure site_url doesn't end with a slash
        if site_url.endswith('/'):
            site_url = site_url.rstrip('/')
        
        # Generate unsubscribe token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        unsubscribe_url = f"{site_url}{reverse('unsubscribe_recommendations', kwargs={'uidb64': uid, 'token': token})}"
        
        # Create email content
        html_message = render_to_string('registration/email_new_recommendations.html', {
            'user': user,
            'new_books': books_for_email,
            'total_recommendations_count': total_recommendations_count,
            'additional_count': additional_count,
            'site_url': site_url,
            'site_name': 'Great Minds Read Alike',
            'unsubscribe_url': unsubscribe_url,
        })
        
        plain_message = f"Hi {user.username},\n\n"
        plain_message += "Great news! Other readers who share some of your favorite books have added new favorites that you might love, too.\n\n"
        plain_message += "Here are some recent recommendations from the past week:\n\n"
        for book in books_for_email:
            plain_message += f"- {book.title} by {book.author.name}\n"
        if additional_count > 0:
            plain_message += f"\nThere are {additional_count} more recommendation{'s' if additional_count != 1 else ''} waiting for you on your recommendations page!\n"
        plain_message += f"\nVisit {site_url}{reverse('recommendations')} to see more recommendations!\n\n"
        plain_message += f"\nIf you no longer wish to receive these emails, you can unsubscribe here: {unsubscribe_url}\n\n"
        plain_message += "Happy reading!\n— Great Minds Read Alike"
        
        try:
            from_email = settings.DEFAULT_FROM_EMAIL
            send_mail(
                'Your Weekly Book Recommendations!',
                plain_message,
                from_email,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully sent test email to {user.username} ({user.email})'))
            self.stdout.write(f'Email includes {len(books_for_email)} books and mentions {additional_count} additional recommendations.')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error sending email: {str(e)}'))
