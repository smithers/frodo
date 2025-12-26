from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "List all users in the database, especially superusers"

    def handle(self, *args, **options):
        users = User.objects.all().order_by('username')
        superusers = User.objects.filter(is_superuser=True)
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Users in Database:'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        if users.count() == 0:
            self.stdout.write(self.style.WARNING('No users found in database.'))
            return
        
        self.stdout.write(f'\nTotal Users: {users.count()}')
        self.stdout.write(f'Superusers: {superusers.count()}\n')
        
        for user in users:
            status = 'SUPERUSER' if user.is_superuser else 'Regular'
            staff = 'Staff' if user.is_staff else 'Not Staff'
            self.stdout.write(f'  - {user.username} ({user.email}) - {status}, {staff}')
        
        self.stdout.write(self.style.SUCCESS('=' * 60))

