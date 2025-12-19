from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from books.models import UserFavoriteBook


class Command(BaseCommand):
    help = "Delete all users in the database except superusers"

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        # Count users to be deleted
        non_superusers = User.objects.filter(is_superuser=False)
        user_count = non_superusers.count()
        
        if user_count == 0:
            self.stdout.write(self.style.SUCCESS('No non-superuser users found. Nothing to delete.'))
            return
        
        # Count superusers for confirmation
        superuser_count = User.objects.filter(is_superuser=True).count()
        
        self.stdout.write(self.style.WARNING(f'Found {user_count} non-superuser user(s) to delete.'))
        self.stdout.write(self.style.SUCCESS(f'Found {superuser_count} superuser(s) that will be preserved.'))
        
        if not options['noinput']:
            confirm = input('Are you sure you want to delete all non-superuser users? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Deletion cancelled.'))
                return
        
        # Delete all favorites associated with non-superusers
        favorites_deleted = UserFavoriteBook.objects.filter(user__is_superuser=False).delete()[0]
        
        # Delete the non-superuser users themselves
        users_deleted = non_superusers.delete()[0]
        
        self.stdout.write(self.style.SUCCESS(f'Deleted {favorites_deleted} favorite book entries.'))
        self.stdout.write(self.style.SUCCESS(f'Deleted {users_deleted} user account(s).'))
        self.stdout.write(self.style.SUCCESS('Deletion complete!'))


