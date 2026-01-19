import random
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Fix usernames ending with '_' that are all numbers by adding letter components"

    def generate_letter_component(self):
        """Generate a random letter component from categories"""
        animals = ['Cat', 'Dog', 'Fox', 'Owl', 'Bee', 'Bat', 'Pig', 'Cow', 'Hen', 'Ram', 'Elk', 'Jay']
        book_chars = ['Harry', 'Frodo', 'Katniss', 'Sherlock', 'Holmes', 'Gandalf', 'Hermione', 'Ron', 'Bilbo']
        day_abbrevs = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        colors = ['Red', 'Blue', 'Green', 'Gold', 'Pink', 'Cyan', 'Lime', 'Navy', 'Teal', 'Gray']
        
        all_components = animals + book_chars + day_abbrevs + colors
        return random.choice(all_components)

    def fix_all_number_username(self, username):
        """Add a letter component to usernames that are all numbers"""
        
        # Remove trailing underscore for processing
        if not username.endswith('_'):
            return username
        
        base_username = username[:-1]  # Remove trailing '_'
        
        # Check if the base username is all digits
        if base_username.isdigit():
            # Add a letter component
            letter_component = self.generate_letter_component()
            # Combine: could put letter before or after numbers, let's put it before for consistency
            new_base = letter_component + base_username
            return new_base + '_'
        
        # If it already has letters, return as-is
        return username

    def handle(self, *args, **options):
        # Find all users with usernames ending with '_'
        underscore_users = User.objects.filter(username__endswith='_').order_by('id')
        count = underscore_users.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING("No users found with usernames ending with '_'"))
            return
        
        # Filter to only those that are all numbers
        all_number_users = []
        for user in underscore_users:
            base = user.username[:-1] if user.username.endswith('_') else user.username
            if base.isdigit():
                all_number_users.append(user)
        
        if len(all_number_users) == 0:
            self.stdout.write(self.style.SUCCESS("No usernames found that are all numbers. All good!"))
            return
        
        self.stdout.write(
            self.style.WARNING(
                f"Found {len(all_number_users)} username(s) that are all numbers. Adding letter components..."
            )
        )
        
        updated_count = 0
        skipped_count = 0
        
        with transaction.atomic():
            for user in all_number_users:
                old_username = user.username
                max_attempts = 20
                new_username = None
                
                # Try to generate a unique username
                for attempt in range(max_attempts):
                    candidate = self.fix_all_number_username(old_username)
                    
                    # Check if username already exists
                    if not User.objects.filter(username=candidate).exclude(id=user.id).exists():
                        new_username = candidate
                        break
                
                if not new_username:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Could not generate unique username for {old_username} after {max_attempts} attempts. Skipping..."
                        )
                    )
                    skipped_count += 1
                    continue
                
                user.username = new_username
                user.save()
                updated_count += 1
                self.stdout.write(f"  {old_username} -> {new_username}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nUpdated {updated_count} username(s). Skipped {skipped_count}."
            )
        )
