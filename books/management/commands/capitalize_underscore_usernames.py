from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Capitalize first letter of animal, day, book character, and color in usernames ending with '_'"

    def capitalize_username_components(self, username):
        """Capitalize first letter of animal, day, book character, and color components"""
        
        # Remove trailing underscore for processing
        if not username.endswith('_'):
            return username
        
        base_username = username[:-1]  # Remove trailing '_'
        
        # Define categories (same as in update_underscore_usernames.py)
        animals = ['cat', 'dog', 'fox', 'owl', 'bee', 'bat', 'pig', 'cow', 'hen', 'ram', 'elk', 'jay']
        book_chars = ['harry', 'frodo', 'katniss', 'sherlock', 'holmes', 'gandalf', 'dumbledore', 'hermione', 'ron', 'bilbo']
        day_abbrevs = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        colors = ['red', 'blue', 'green', 'gold', 'pink', 'cyan', 'lime', 'navy', 'teal', 'gray']
        
        # Create a mapping of lowercase -> capitalized for items to capitalize
        capitalize_map = {}
        for category_list in [animals, book_chars, day_abbrevs, colors]:
            for item in category_list:
                capitalize_map[item.lower()] = item.capitalize()
        
        # Try to find and replace components
        result = base_username
        remaining_lower = base_username.lower()
        
        # Sort items by length (longest first) to match longer items first
        all_capitalize_items = animals + book_chars + day_abbrevs + colors
        sorted_items = sorted(all_capitalize_items, key=len, reverse=True)
        
        # Find all matches and their positions
        matches = []
        for item in sorted_items:
            item_lower = item.lower()
            # Find all occurrences
            start = 0
            while True:
                pos = remaining_lower.find(item_lower, start)
                if pos == -1:
                    break
                # Check if this is a valid match (word boundary)
                is_valid = True
                if pos > 0 and base_username[pos-1].isalnum():
                    is_valid = False
                if pos + len(item_lower) < len(base_username) and base_username[pos + len(item_lower)].isalnum():
                    is_valid = False
                
                if is_valid:
                    # Check if this position overlaps with an existing match
                    overlap = False
                    for existing_pos, existing_item, _ in matches:
                        if not (pos + len(item_lower) <= existing_pos or pos >= existing_pos + len(existing_item)):
                            overlap = True
                            break
                    if not overlap:
                        matches.append((pos, item, item_lower))
                start = pos + 1
        
        # Sort matches by position
        matches.sort(key=lambda x: x[0])
        
        # Build the result by replacing matches
        if matches:
            result_parts = []
            last_pos = 0
            
            for pos, original_item, item_lower in matches:
                # Add text before this match
                if pos > last_pos:
                    result_parts.append(base_username[last_pos:pos])
                
                # Add capitalized version
                result_parts.append(capitalize_map[item_lower])
                
                last_pos = pos + len(item_lower)
            
            # Add remaining text
            if last_pos < len(base_username):
                result_parts.append(base_username[last_pos:])
            
            result = ''.join(result_parts)
        
        # Add back trailing underscore
        return result + '_'

    def handle(self, *args, **options):
        # Find all users with usernames ending with '_'
        underscore_users = User.objects.filter(username__endswith='_').order_by('id')
        count = underscore_users.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING("No users found with usernames ending with '_'"))
            return
        
        self.stdout.write(
            self.style.WARNING(
                f"Found {count} user(s) with usernames ending with '_'. Capitalizing components..."
            )
        )
        
        updated_count = 0
        skipped_count = 0
        
        with transaction.atomic():
            for user in underscore_users:
                old_username = user.username
                new_username = self.capitalize_username_components(old_username)
                
                if new_username == old_username:
                    self.stdout.write(
                        self.style.WARNING(f"  {old_username} -> (no change)")
                    )
                    skipped_count += 1
                    continue
                
                # Check if new username already exists
                if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                    self.stdout.write(
                        self.style.ERROR(
                            f"  {old_username} -> (skipped: '{new_username}' already exists)"
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
