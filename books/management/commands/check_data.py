from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from books.models import Author, Book, UserFavoriteBook


class Command(BaseCommand):
    help = "Check data counts in the database"

    def handle(self, *args, **options):
        total_users = User.objects.count()
        superuser_count = User.objects.filter(is_superuser=True).count()
        non_superuser_count = total_users - superuser_count
        authors_count = Author.objects.count()
        books_count = Book.objects.count()
        favorites_count = UserFavoriteBook.objects.count()
        
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Database Statistics:'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f'Total Users: {total_users}')
        self.stdout.write(f'  - Superusers: {superuser_count}')
        self.stdout.write(f'  - Regular Users: {non_superuser_count}')
        self.stdout.write(f'Authors: {authors_count}')
        self.stdout.write(f'Books: {books_count}')
        self.stdout.write(f'UserFavoriteBooks: {favorites_count}')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        
        # Show a few sample users
        if non_superuser_count > 0:
            self.stdout.write('\nSample Users (first 5):')
            for user in User.objects.filter(is_superuser=False)[:5]:
                fav_count = UserFavoriteBook.objects.filter(user=user).count()
                self.stdout.write(f'  - {user.username} ({fav_count} favorites)')




