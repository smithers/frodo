import random
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Update usernames starting with '_' to random 5-10 character names ending with '_'"

    def generate_random_username(self):
        """Generate a random username from specified categories, 4-9 chars + '_' = 5-10 total"""
        
        # Define categories with short forms
        animals = ['cat', 'dog', 'fox', 'owl', 'bee', 'bat', 'pig', 'cow', 'hen', 'ram', 'elk', 'jay']
        area_codes = ['212', '310', '415', '617', '718', '213', '312', '404', '305', '214']
        book_chars = ['harry', 'frodo', 'katniss', 'sherlock', 'holmes', 'gandalf', 'dumbledore', 'hermione', 'ron', 'bilbo']
        day_abbrevs = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        colors = ['red', 'blue', 'green', 'gold', 'pink', 'cyan', 'lime', 'navy', 'teal', 'gray']
        zip_codes = ['10001', '90210', '02134', '60601', '33139', '77002', '98101', '94102']
        
        all_categories = [
            animals,
            area_codes,
            book_chars,
            day_abbrevs,
            colors,
            zip_codes
        ]
        
        # Try to generate a username that's 4-9 characters (plus '_' = 5-10 total)
        max_attempts = 50
        for _ in range(max_attempts):
            # Randomly select 1-3 components
            num_components = random.randint(1, 3)
            selected = random.sample(all_categories, num_components)
            
            # Pick one item from each selected category
            components = [random.choice(cat) for cat in selected]
            
            # Combine them
            username = ''.join(components)
            
            # Ensure length is 4-9 characters (will add '_' at end)
            if 4 <= len(username) <= 9:
                # Add underscore at the end
                return username + '_'
        
        # Fallback: if we can't generate in range, use a simple pattern
        animal = random.choice(animals)
        day = random.choice(day_abbrevs)
        username = (animal + day)[:9]  # Ensure max 9 chars
        return username + '_'

    def handle(self, *args, **options):
        # Find all users with usernames starting with underscore character '_'
        # Note: '_' is the underscore character, not an empty string
        underscore_users = User.objects.filter(username__startswith='_').order_by('id')
        count = underscore_users.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING("No users found with usernames starting with '_'"))
            return
        
        self.stdout.write(
            self.style.WARNING(
                f"Found {count} user(s) with usernames starting with '_'. Generating new usernames..."
            )
        )
        
        updated_count = 0
        skipped_count = 0
        
        with transaction.atomic():
            for user in underscore_users:
                old_username = user.username
                max_attempts = 20
                new_username = None
                
                # Try to generate a unique username
                for attempt in range(max_attempts):
                    candidate = self.generate_random_username()
                    
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
