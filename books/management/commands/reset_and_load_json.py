import json
import os
import tempfile
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User
from books.models import Author, Book, UserFavoriteBook
from django.db import transaction


class Command(BaseCommand):
    help = "Delete all data except superusers, then load data from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to the JSON file to load',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        
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
            self.stdout.write(f'\nThen load data from: {json_file}')
            
            confirm = input('\nAre you sure you want to proceed? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Operation cancelled.'))
                return
        
        self.stdout.write(self.style.WARNING('Deleting data...'))
        
        # Delete in order to respect foreign key constraints
        with transaction.atomic():
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
        
        # Now load the JSON file, but filter out superusers to avoid conflicts
        self.stdout.write(self.style.WARNING(f'\nLoading data from {json_file}...'))
        
        try:
            # Get mapping of superuser usernames to their existing pks
            existing_superusers = {
                username: pk for username, pk in 
                User.objects.filter(is_superuser=True).values_list('username', 'pk')
            }
            existing_superuser_usernames = set(existing_superusers.keys())
            
            # Read the JSON file
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Build a mapping of JSON superuser pks to existing superuser pks
            # This is needed to update foreign key references in UserFavoriteBook
            superuser_pk_mapping = {}
            superuser_data = None  # Store superuser data from JSON if no superuser exists
            
            # Filter out superusers from the data and build the mapping
            filtered_data = []
            superusers_skipped = 0
            for item in data:
                # Handle superusers - skip them but record the pk mapping
                if item.get('model') == 'auth.user':
                    username = item.get('fields', {}).get('username', '')
                    is_superuser = item.get('fields', {}).get('is_superuser', False)
                    json_pk = item.get('pk')
                    
                    if is_superuser or username in existing_superuser_usernames:
                        # If superuser exists, map the JSON pk to the existing superuser pk
                        if username in existing_superusers:
                            existing_pk = existing_superusers[username]
                            if json_pk != existing_pk:
                                superuser_pk_mapping[json_pk] = existing_pk
                        else:
                            # No superuser exists - store the data to create it later
                            superuser_data = item
                        superusers_skipped += 1
                        continue
                
                filtered_data.append(item)
            
            # If no superuser exists but we have superuser data, create it
            if not existing_superusers and superuser_data:
                self.stdout.write(self.style.WARNING('No superuser found. Creating superuser from JSON data...'))
                user_fields = superuser_data.get('fields', {})
                User.objects.create_superuser(
                    username=user_fields.get('username', 'admin'),
                    email=user_fields.get('email', ''),
                    password='changeme123!'  # Set a default password - user should change it
                )
                new_superuser = User.objects.get(username=user_fields.get('username'))
                superuser_pk_mapping[superuser_data.get('pk')] = new_superuser.pk
                self.stdout.write(self.style.SUCCESS(f'Created superuser: {new_superuser.username} (pk={new_superuser.pk})'))
                self.stdout.write(self.style.WARNING('IMPORTANT: Change the superuser password after first login!'))
            
            # Collect all superuser pks from JSON for reference
            json_superuser_pks = set()
            for item in data:
                if item.get('model') == 'auth.user':
                    if item.get('fields', {}).get('is_superuser') or item.get('fields', {}).get('username') in existing_superuser_usernames:
                        json_superuser_pks.add(item.get('pk'))
            
            # Update foreign key references in UserFavoriteBook entries
            # If they reference a superuser pk from JSON, map it to the existing superuser pk
            # If no mapping exists (superuser doesn't exist and wasn't created), skip those entries
            favorites_skipped = 0
            final_filtered_data = []
            for item in filtered_data:
                if item.get('model') == 'books.userfavoritebook':
                    user_pk = item.get('fields', {}).get('user')
                    if user_pk in superuser_pk_mapping:
                        item['fields']['user'] = superuser_pk_mapping[user_pk]
                        final_filtered_data.append(item)
                    elif user_pk in json_superuser_pks:
                        # This references a superuser that we couldn't map - skip it
                        favorites_skipped += 1
                        continue
                    else:
                        final_filtered_data.append(item)
                else:
                    final_filtered_data.append(item)
            
            if favorites_skipped > 0:
                self.stdout.write(self.style.WARNING(f'Skipped {favorites_skipped} UserFavoriteBook entries that reference unmapped superusers.'))
            
            filtered_data = final_filtered_data
            
            if superusers_skipped > 0:
                self.stdout.write(self.style.WARNING(f'Skipped {superusers_skipped} superuser(s) from JSON file to avoid conflicts.'))
            
            # Create a temporary file with filtered data
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as temp_file:
                json.dump(filtered_data, temp_file, indent=2, ensure_ascii=False)
                temp_file_path = temp_file.name
            
            try:
                # Use Django's loaddata command with the filtered JSON
                call_command('loaddata', temp_file_path, verbosity=1)
                self.stdout.write(self.style.SUCCESS('\nData loaded successfully!'))
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nError loading data: {str(e)}'))
            raise

