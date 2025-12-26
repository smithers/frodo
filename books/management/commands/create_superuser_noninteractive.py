from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = "Create a superuser non-interactively (for Railway/deployment use)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the superuser',
            default=os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin'),
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email for the superuser',
            default=os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com'),
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the superuser',
            default=os.environ.get('DJANGO_SUPERUSER_PASSWORD', ''),
        
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Use default values without prompting',
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        
        # Check if superuser already exists
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            if user.is_superuser:
                self.stdout.write(
                    self.style.WARNING(f'Superuser "{username}" already exists.')
                )
                return
            else:
                # User exists but is not a superuser, make them one
                user.is_superuser = True
                user.is_staff = True
                if password:
                    user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Existing user "{username}" has been promoted to superuser.')
                )
                return
        
        # If no password provided, generate a random one or use default
        if not password:
            if options['noinput']:
                # For non-interactive mode, use a default password
                password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'changeme123!')
                self.stdout.write(
                    self.style.WARNING('No password provided. Using default password. Please change it after first login!')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Password is required. Use --password or set DJANGO_SUPERUSER_PASSWORD environment variable.')
                )
                return
        
        # Create the superuser
        try:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created superuser "{username}"')
            )
            if password == 'changeme123!':
                self.stdout.write(
                    self.style.WARNING('IMPORTANT: Change the password after first login!')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {str(e)}')
            )

