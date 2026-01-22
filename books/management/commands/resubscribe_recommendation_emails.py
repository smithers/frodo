from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from books.models import UserEmailPreferences


class Command(BaseCommand):
    help = 'Re-subscribe a user to recommendation emails'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to re-subscribe')

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" does not exist.'))
            return
        
        email_prefs, created = UserEmailPreferences.objects.get_or_create(user=user)
        
        if email_prefs.receive_recommendation_emails:
            self.stdout.write(self.style.WARNING(f'User "{username}" is already subscribed to recommendation emails.'))
        else:
            email_prefs.receive_recommendation_emails = True
            email_prefs.unsubscribed_at = None
            email_prefs.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully re-subscribed "{username}" to recommendation emails.'))
