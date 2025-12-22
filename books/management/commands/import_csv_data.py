import csv

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from books.models import Author, Book, UserFavoriteBook
from books.utils import smart_title_case


class Command(BaseCommand):
    help = "Import books and user favorites from CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_path",
            type=str,
            help="Path to the CSV file",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        self.stdout.write(self.style.WARNING(f"Importing data from {csv_path}"))

        created_users = 0
        created_authors = 0
        created_books = 0
        created_favorites = 0
        skipped_rows = 0

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):  # Start at 2 because row 1 is header
                # Skip completely blank lines or rows with no meaningful data
                if not row or all((value or "").strip() == "" for value in row.values()):
                    skipped_rows += 1
                    continue

                # Extract values from CSV
                username = (row.get("User Name") or "").strip()
                raw_title = (row.get("Book Title") or "").strip()
                raw_author = (row.get("Book Author") or "").strip()
                raw_genre = (row.get("Genre") or "").strip()
                raw_sub_genre = (row.get("Sub-Genre") or "").strip()

                # Skip rows with missing critical fields
                if not username or not raw_title or not raw_author:
                    skipped_rows += 1
                    continue

                # --- USER ---
                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "password": User.objects.make_random_password(),
                        "is_active": True,
                    },
                )
                if user_created:
                    created_users += 1

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
                # Map raw genre to Book.GENRE_* constants
                genre_value = Book.GENRE_FICTION  # default
                if raw_genre:
                    g = raw_genre.strip().lower()
                    if g in ("non-fiction", "nonfiction", "nf", "non fiction"):
                        genre_value = Book.GENRE_NONFICTION
                    elif g in ("fiction", "fic", "f"):
                        genre_value = Book.GENRE_FICTION

                clean_sub_genre = raw_sub_genre.strip() if raw_sub_genre else None
                if clean_sub_genre:
                    clean_sub_genre = clean_sub_genre.title()

                # --- BOOK ---
                # Check if book already exists (by title and author)
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

                # --- FAVORITE ---
                favorite, favorite_created = UserFavoriteBook.objects.get_or_create(
                    user=user,
                    book=book,
                )
                if favorite_created:
                    created_favorites += 1

        self.stdout.write(self.style.SUCCESS(f"\nImport complete!"))
        self.stdout.write(self.style.SUCCESS(f"Users created:   {created_users}"))
        self.stdout.write(self.style.SUCCESS(f"Authors created: {created_authors}"))
        self.stdout.write(self.style.SUCCESS(f"Books created:   {created_books}"))
        self.stdout.write(self.style.SUCCESS(f"Favorites created: {created_favorites}"))
        if skipped_rows > 0:
            self.stdout.write(self.style.WARNING(f"Rows skipped: {skipped_rows}"))

