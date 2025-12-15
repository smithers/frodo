import csv

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from books.models import Author, Book, UserBookRating
from books.utils import smart_title_case


class Command(BaseCommand):
    help = "Import book ratings from a CSV file and seed the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help="Path to the CSV file with ratings",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        self.stdout.write(self.style.WARNING(f"Importing ratings from {csv_path}"))

        created_users = 0
        created_authors = 0
        created_books = 0
        created_ratings = 0
        updated_ratings = 0

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # Map original spreadsheet "user name" to an internal seed_user_N account
            seed_user_map = {}
            next_seed_index = 1

            def get_first(row, *keys):
                """Helper to read from any of a set of possible column names."""
                for key in keys:
                    if key in row and row[key] is not None:
                        return row[key]
                return ""

            for row in reader:
                # Skip completely blank lines or rows with no meaningful data
                if not row or all((value or "").strip() == "" for value in row.values()):
                    continue

                # Raw values from CSV (allow for different header labels and blanks)
                username = (get_first(row, "username", "User Name") or "").strip()
                raw_title = (get_first(row, "title", "Book Title") or "").strip()
                raw_author = (get_first(row, "author", "Book Author") or "").strip()
                rating_raw = (get_first(row, "rating", "User Rating") or "").strip()

                # If any of the critical fields are missing, skip this row
                if not username or not raw_title or not raw_author or not rating_raw:
                    continue

                isbn = (row.get("isbn") or "").strip() or None
                try:
                    rating_value = int(rating_raw)
                except ValueError:
                    # Skip rows where rating is not a valid integer
                    continue

                # Optional genre / sub-genre columns
                raw_genre = (get_first(row, "genre", "Genre") or "").strip()
                raw_sub_genre = (get_first(row, "sub_genre", "Sub-Genre") or "").strip()

                # --- USER ---
                # We do NOT want to use the real name from the spreadsheet as a username.
                # Instead, for each distinct spreadsheet user, assign a seed_user_N account.
                if username not in seed_user_map:
                    internal_username = f"seed_user_{next_seed_index}"
                    user, user_created = User.objects.get_or_create(
                        username=internal_username,
                        defaults={
                            "password": User.objects.make_random_password(),
                            "is_active": False,
                        },
                    )
                    if user_created:
                        created_users += 1
                    seed_user_map[username] = user
                    next_seed_index += 1
                else:
                    user = seed_user_map[username]

                # --- NORMALIZE TITLE & AUTHOR ---
                clean_title = smart_title_case(raw_title)
                clean_author_name = raw_author.title()

                # --- AUTHOR ---
                author, author_created = Author.objects.get_or_create(
                    name__iexact=clean_author_name,
                    defaults={"name": clean_author_name},
                )
                if author_created:
                    created_authors += 1

                # --- GENRE / SUB-GENRE ---
                # Map raw genre to Book.GENRE_* constants when possible.
                genre_value = Book.GENRE_FICTION  # default
                if raw_genre:
                    g = raw_genre.strip().lower()
                    if g in ("non-fiction", "nonfiction", "nf"):
                        genre_value = Book.GENRE_NONFICTION
                    elif g in ("fiction", "fic", "f"):
                        genre_value = Book.GENRE_FICTION

                clean_sub_genre = raw_sub_genre.title() if raw_sub_genre else None

                # --- BOOK (prefer ISBN when available) ---
                book = None
                if isbn:
                    book = Book.objects.filter(isbn=isbn).first()

                if not book:
                    book = Book.objects.filter(
                        title__iexact=clean_title,
                        author=author,
                    ).first()

                if not book:
                    try:
                        book = Book.objects.create(
                            title=clean_title,
                            author=author,
                            isbn=isbn,
                            genre=genre_value,
                            sub_genre=clean_sub_genre,
                        )
                        created_books += 1
                    except IntegrityError:
                        # Another process/row just created the same book: fetch it
                        book = Book.objects.get(title=clean_title, author=author)
                else:
                    # If the book already exists, optionally update its genre/sub-genre
                    updated = False
                    if raw_genre and book.genre != genre_value:
                        book.genre = genre_value
                        updated = True
                    if clean_sub_genre and book.sub_genre != clean_sub_genre:
                        book.sub_genre = clean_sub_genre
                        updated = True
                    if updated:
                        book.save()

                # --- RATING ---
                _, rating_created = UserBookRating.objects.update_or_create(
                    user=user,
                    book=book,
                    defaults={"rating": rating_value},
                )
                if rating_created:
                    created_ratings += 1
                else:
                    updated_ratings += 1

        self.stdout.write(self.style.SUCCESS(f"Users created:   {created_users}"))
        self.stdout.write(self.style.SUCCESS(f"Authors created: {created_authors}"))
        self.stdout.write(self.style.SUCCESS(f"Books created:   {created_books}"))
        self.stdout.write(self.style.SUCCESS(f"Ratings created: {created_ratings}"))
        self.stdout.write(self.style.SUCCESS(f"Ratings updated: {updated_ratings}"))


