from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from books.models import Author, Book, UserFavoriteBook


class Command(BaseCommand):
    help = "Delete all data from books, users, authors, and userfavoritebook tables, except for superusers"

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        # Count items before deletion
        total_users = User.objects.count()
        superusers = User.objects.filter(is_superuser=True)
        superuser_count = superusers.count()
        non_superuser_count = total_users - superuser_count
        
        favorites_count = UserFavoriteBook.objects.count()
        books_count = Book.objects.count()
        authors_count = Author.objects.count()
        
        if not options['noinput']:
            self.stdout.write(self.style.WARNING('This will delete:'))
            self.stdout.write(f'  - {favorites_count} UserFavoriteBook entries')
            self.stdout.write(f'  - {books_count} Book entries')
            self.stdout.write(f'  - {authors_count} Author entries')
            self.stdout.write(f'  - {non_superuser_count} non-superuser User accounts')
            self.stdout.write(f'\n  (Preserving {superuser_count} superuser account(s))')
            
            confirm = input('\nAre you sure you want to proceed? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Operation cancelled.'))
                return
        
        self.stdout.write(self.style.WARNING('Deleting data...'))
        
        # Delete in order to respect foreign key constraints
        # 1. Delete all UserFavoriteBook entries (they reference User and Book)
        favorites_deleted = UserFavoriteBook.objects.all().delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Deleted {favorites_deleted} UserFavoriteBook entries.'))
        
        # 2. Delete all Books (they reference Author)
        books_deleted = Book.objects.all().delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Deleted {books_deleted} Book entries.'))
        
        # 3. Delete all Authors
        authors_deleted = Author.objects.all().delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Deleted {authors_deleted} Author entries.'))
        
        # 4. Delete all non-superuser Users
        non_superusers = User.objects.filter(is_superuser=False)
        users_deleted = non_superusers.delete()[0]
        self.stdout.write(self.style.SUCCESS(f'Deleted {users_deleted} non-superuser User accounts.'))
        
        self.stdout.write(self.style.SUCCESS(f'\nData deletion complete! {superuser_count} superuser account(s) preserved.'))

