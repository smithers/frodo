import csv
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from books.models import Author, Book, UserFavoriteBook
from books.utils import smart_title_case


class Command(BaseCommand):
    help = "Import books from CSV file with columns: User Name, Book Title, Book Author, Genre, Subgenre"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            nargs="?",
            default=None,
            help="Path to the CSV file (default: looks for CSV files in project root)",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        
        # If no path provided, look for CSV files in the project root
        if not csv_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            csv_files = [f for f in os.listdir(base_dir) if f.endswith('.csv') and f != 'new_usernames.csv']
            if not csv_files:
                self.stdout.write(self.style.ERROR('No CSV file found. Please specify the path to the CSV file.'))
                return
            if len(csv_files) > 1:
                self.stdout.write(self.style.WARNING(f'Multiple CSV files found: {csv_files}'))
                self.stdout.write(self.style.WARNING('Using the first one. Specify the path explicitly to use a different file.'))
            csv_path = os.path.join(base_dir, csv_files[0])
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'CSV file not found: {csv_path}'))
            return
        
        self.stdout.write(self.style.WARNING(f"Importing books from {csv_path}"))

        created_users = 0
        created_authors = 0
        created_books = 0
        created_favorites = 0
        skipped_rows = 0

        def get_first(row, *keys):
            """Helper to read from any of a set of possible column names."""
            for key in keys:
                if key in row and row[key] is not None:
                    return row[key]
                # Also try case-insensitive match
                for k in row.keys():
                    if k.lower() == key.lower():
                        return row[k]
            return ""

        with open(csv_path, newline="", encoding="utf-8") as f:
            # Try to detect if there's a header row
            sample = f.read(1024)
            f.seek(0)
            has_header = csv.Sniffer().has_header(sample)
            
            reader = csv.DictReader(f) if has_header else None
            
            if not reader:
                # No header row, read as list and create header
                f.seek(0)
                reader = csv.reader(f)
                # Read first row to determine structure
                first_row = next(reader, None)
                if not first_row or len(first_row) < 3:
                    self.stdout.write(self.style.ERROR('CSV file must have at least 3 columns: User Name, Book Title, Book Author'))
                    return
                
                # Create a reader that maps columns by position
                fieldnames = ['User Name', 'Book Title', 'Book Author', 'Genre', 'Subgenre']
                reader = csv.DictReader(f, fieldnames=fieldnames)
                # Skip the first row if it was data
                if first_row:
                    # Reconstruct the row as a dict
                    row_dict = {}
                    for i, value in enumerate(first_row):
                        if i < len(fieldnames):
                            row_dict[fieldnames[i]] = value
                    # Process this first row
                    with transaction.atomic():
                        result = self._process_row(row_dict, get_first)
                        if result:
                            created_users += result.get('users', 0)
                            created_authors += result.get('authors', 0)
                            created_books += result.get('books', 0)
                            created_favorites += result.get('favorites', 0)
                        else:
                            skipped_rows += 1

            for row in reader:
                # Skip completely blank lines
                if not row or all((str(value) or "").strip() == "" for value in row.values()):
                    continue

                with transaction.atomic():
                    result = self._process_row(row, get_first)
                    if result:
                        created_users += result.get('users', 0)
                        created_authors += result.get('authors', 0)
                        created_books += result.get('books', 0)
                        created_favorites += result.get('favorites', 0)
                    else:
                        skipped_rows += 1

        self.stdout.write(self.style.SUCCESS(f"\nImport complete!"))
        self.stdout.write(self.style.SUCCESS(f"Users created:   {created_users}"))
        self.stdout.write(self.style.SUCCESS(f"Authors created: {created_authors}"))
        self.stdout.write(self.style.SUCCESS(f"Books created:   {created_books}"))
        self.stdout.write(self.style.SUCCESS(f"Favorites created: {created_favorites}"))
        if skipped_rows > 0:
            self.stdout.write(self.style.WARNING(f"Rows skipped:    {skipped_rows}"))

    def _process_row(self, row, get_first):
        """Process a single CSV row and return counts of created objects."""
        # Get values from CSV (handle various column name variations)
        username = (get_first(row, "User Name", "username", "user") or "").strip()
        raw_title = (get_first(row, "Book Title", "title", "book title") or "").strip()
        raw_author = (get_first(row, "Book Author", "author", "book author") or "").strip()
        raw_genre = (get_first(row, "Genre", "genre") or "").strip()
        raw_subgenre = (get_first(row, "Subgenre", "subgenre", "Sub-Genre", "sub-genre") or "").strip()

        # Validate required fields
        if not username or not raw_title or not raw_author:
            return None

        counts = {'users': 0, 'authors': 0, 'books': 0, 'favorites': 0}

        # --- USER ---
        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={
                "password": User.objects.make_random_password(),
                "is_active": True,
            },
        )
        if user_created:
            counts['users'] = 1

        # --- NORMALIZE TITLE & AUTHOR ---
        clean_title = smart_title_case(raw_title)
        clean_author_name = raw_author.title()

        # --- AUTHOR ---
        author, author_created = Author.objects.get_or_create(
            name__iexact=clean_author_name,
            defaults={"name": clean_author_name},
        )
        if author_created:
            counts['authors'] = 1

        # --- GENRE / SUB-GENRE ---
        # Map raw genre to Book.GENRE_* constants
        genre_value = Book.GENRE_FICTION  # default
        if raw_genre:
            g = raw_genre.strip().lower()
            if g in ("non-fiction", "nonfiction", "nf", "non fiction"):
                genre_value = Book.GENRE_NONFICTION
            elif g in ("fiction", "fic", "f"):
                genre_value = Book.GENRE_FICTION

        clean_sub_genre = raw_subgenre.title() if raw_subgenre else None

        # --- BOOK ---
        book = Book.objects.filter(
            title__iexact=clean_title,
            author=author,
        ).first()

        if not book:
            try:
                book = Book.objects.create(
                    title=clean_title,
                    author=author,
                    genre=genre_value,
                    sub_genre=clean_sub_genre,
                )
                counts['books'] = 1
            except IntegrityError:
                # Another process/row just created the same book: fetch it
                book = Book.objects.get(title=clean_title, author=author)
        else:
            # Update genre/subgenre if provided and different
            updated = False
            if raw_genre and book.genre != genre_value:
                book.genre = genre_value
                updated = True
            if clean_sub_genre and book.sub_genre != clean_sub_genre:
                book.sub_genre = clean_sub_genre
                updated = True
            if updated:
                book.save()

        # --- FAVORITE ---
        favorite, favorite_created = UserFavoriteBook.objects.get_or_create(
            user=user,
            book=book,
        )
        if favorite_created:
            counts['favorites'] = 1

        return counts


