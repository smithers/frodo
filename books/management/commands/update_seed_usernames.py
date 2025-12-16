import csv
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Replace usernames of seed users (starting with 'seed') with names from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help="Path to the CSV file with new usernames",
        )
        parser.add_argument(
            "--column",
            type=str,
            default="username",
            help="Column name in CSV containing the new usernames (default: 'username')",
        )
        parser.add_argument(
            "--old-column",
            type=str,
            default=None,
            help="Optional: Column name for old username if CSV has old,new format",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        column_name = options["column"]
        old_column = options["old_column"]

        # Check if file exists
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            return

        # Get all seed users ordered by ID to maintain consistent ordering
        seed_users = User.objects.filter(username__startswith="seed").order_by("id")
        seed_user_count = seed_users.count()

        if seed_user_count == 0:
            self.stdout.write(self.style.WARNING("No seed users found in database."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {seed_user_count} seed users. Reading new usernames from {csv_path}..."
            )
        )

        new_usernames = []
        username_mapping = {}

        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                # Try to detect if file has header by reading first line
                first_line = f.readline().strip()
                f.seek(0)  # Reset to beginning
                
                # Check if first line looks like a header (contains the column name or common header words)
                has_header = (
                    column_name.lower() in first_line.lower() or
                    first_line.lower() in ['username', 'name', 'user', 'user_name']
                )
                
                if has_header:
                    reader = csv.DictReader(f)
                    # Check if required column exists
                    if column_name not in reader.fieldnames:
                        # Try common variations
                        for common_name in ['username', 'name', 'user', 'user_name']:
                            if common_name in reader.fieldnames:
                                column_name = common_name
                                break
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Column '{column_name}' not found in CSV. Available columns: {', '.join(reader.fieldnames)}"
                                )
                            )
                            return

                    for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                        new_username = (row.get(column_name) or "").strip()

                        if not new_username:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Row {row_num}: Empty username, skipping..."
                                )
                            )
                            continue

                        if old_column:
                            # If old_column is specified, create a mapping
                            old_username = (row.get(old_column) or "").strip()
                            if old_username:
                                username_mapping[old_username] = new_username
                        else:
                            # Otherwise, just collect usernames in order
                            new_usernames.append(new_username)
                else:
                    # No header - read as simple list
                    reader = csv.reader(f)
                    for row_num, row in enumerate(reader, start=1):
                        if not row or len(row) == 0:
                            continue
                        # Take first column
                        new_username = (row[0] or "").strip()
                        
                        if not new_username:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Row {row_num}: Empty username, skipping..."
                                )
                            )
                            continue
                        
                        new_usernames.append(new_username)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error reading CSV file: {str(e)}")
            )
            return

        if old_column:
            # Use mapping approach
            updated_count = 0
            skipped_count = 0

            with transaction.atomic():
                for user in seed_users:
                    old_username = user.username
                    if old_username in username_mapping:
                        new_username = username_mapping[old_username]

                        # Check if new username already exists
                        if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Skipping {old_username}: username '{new_username}' already exists"
                                )
                            )
                            skipped_count += 1
                            continue

                        user.username = new_username
                        user.save()
                        updated_count += 1
                        self.stdout.write(
                            f"  {old_username} -> {new_username}"
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"No mapping found for {old_username}, skipping..."
                            )
                        )
                        skipped_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nUpdated {updated_count} usernames. Skipped {skipped_count}."
                )
            )

        else:
            # Use ordered list approach
            if len(new_usernames) < seed_user_count:
                self.stdout.write(
                    self.style.WARNING(
                        f"Warning: CSV has {len(new_usernames)} usernames but database has {seed_user_count} seed users."
                    )
                )
                response = input(
                    "Continue with partial update? (yes/no): "
                ).strip().lower()
                if response != "yes":
                    self.stdout.write(self.style.WARNING("Update cancelled."))
                    return

            updated_count = 0
            skipped_count = 0

            with transaction.atomic():
                for idx, user in enumerate(seed_users):
                    if idx >= len(new_usernames):
                        self.stdout.write(
                            self.style.WARNING(
                                f"No new username for {user.username}, skipping..."
                            )
                        )
                        skipped_count += 1
                        continue

                    old_username = user.username
                    new_username = new_usernames[idx]

                    # Check if new username already exists
                    if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping {old_username}: username '{new_username}' already exists"
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
                    f"\nUpdated {updated_count} usernames. Skipped {skipped_count}."
                )
            )

