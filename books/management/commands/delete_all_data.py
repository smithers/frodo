from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from books.models import Author, Book, UserFavoriteBook


class Command(BaseCommand):
    help = "Delete all data from Authors, Books, UserFavoriteBook, and Users (except superuser)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        # Count records to be deleted
        author_count = Author.objects.count()
        book_count = Book.objects.count()
        favorite_count = UserFavoriteBook.objects.count()
        user_count = User.objects.filter(is_superuser=False).count()
        
        superuser_count = User.objects.filter(is_superuser=True).count()
        
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('WARNING: This will delete ALL data from:'))
        self.stdout.write(self.style.WARNING(f'  - Authors: {author_count} records'))
        self.stdout.write(self.style.WARNING(f'  - Books: {book_count} records'))
        self.stdout.write(self.style.WARNING(f'  - UserFavoriteBook: {favorite_count} records'))
        self.stdout.write(self.style.WARNING(f'  - Users (non-superuser): {user_count} records'))
        self.stdout.write(self.style.SUCCESS(f'  - Superusers will be preserved: {superuser_count}'))
        self.stdout.write(self.style.WARNING('=' * 60))
        
        if not options['noinput']:
            confirm = input('Are you sure you want to delete ALL this data? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Deletion cancelled.'))
                return
        
        # Delete in order to respect foreign key constraints
        # UserFavoriteBook references both User and Book, so delete it first
        favorites_deleted = UserFavoriteBook.objects.all().delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Deleted {favorites_deleted} UserFavoriteBook records.'))
        
        # Books reference Authors, so delete Books before Authors
        books_deleted = Book.objects.all().delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Deleted {books_deleted} Book records.'))
        
        # Now delete Authors
        authors_deleted = Author.objects.all().delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Deleted {authors_deleted} Author records.'))
        
        # Finally delete non-superuser Users
        users_deleted = User.objects.filter(is_superuser=False).delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Deleted {users_deleted} User records (non-superuser).'))
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('All data deletion complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 60))


