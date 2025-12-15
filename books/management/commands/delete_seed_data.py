from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from books.models import UserFavoriteBook


class Command(BaseCommand):
    help = "Delete all seed data (seed_user_* accounts and their favorite books)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Deleting seed data...'))
        
        # Find all seed users
        seed_users = User.objects.filter(username__startswith='seed_user_')
        seed_user_count = seed_users.count()
        
        if seed_user_count == 0:
            self.stdout.write(self.style.SUCCESS('No seed users found.'))
            return
        
        # Delete all favorites associated with seed users
        favorites_deleted = UserFavoriteBook.objects.filter(user__username__startswith='seed_user_').delete()[0]
        
        # Delete the seed users themselves
        users_deleted = seed_users.delete()[0]
        
        self.stdout.write(self.style.SUCCESS(f'Deleted {favorites_deleted} favorite book entries.'))
        self.stdout.write(self.style.SUCCESS(f'Deleted {users_deleted} seed user account(s).'))
        self.stdout.write(self.style.SUCCESS('Seed data deletion complete!'))


