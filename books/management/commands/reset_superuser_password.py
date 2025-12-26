from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = "Reset a superuser's password or create one if it doesn't exist"

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the superuser',
            default=os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin'),
        )
        parser.add_argument(
            '--password',
            type=str,
            help='New password for the superuser',
            default=os.environ.get('DJANGO_SUPERUSER_PASSWORD', ''),
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        
        if not password:
            self.stdout.write(
                self.style.ERROR('Password is required. Use --password or set DJANGO_SUPERUSER_PASSWORD environment variable.')
            )
            return
        
        # Check if user exists
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            # Update password and ensure superuser status
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Password updated for superuser "{username}"')
            )
        else:
            # Create new superuser
            email = os.environ.get('DJANGO_SUPERUSER_EMAIL', f'{username}@example.com')
            try:
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Created new superuser "{username}"')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating superuser: {str(e)}')
                )

