"""
Export the 100-200 most favorited books to CSV.
Usage:
  python manage.py export_top_favorited_csv
  python manage.py export_top_favorited_csv --offset=99 --limit=101 --output=top_100_200.csv

On Heroku (save to file on your machine):
  heroku run "python manage.py export_top_favorited_csv --offset=99 --limit=101" --app great-minds > top_100_200.csv
"""
import csv
import sys
from django.core.management.base import BaseCommand
from django.db.models import Count
from books.models import Book


class Command(BaseCommand):
    help = 'Export top favorited books (default: ranks 100-200) to CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--offset',
            type=int,
            default=99,
            help='Rank to start from (1-based). Default 99 = start at rank 100.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=101,
            help='Number of books to export. Default 101 = ranks 100-200.',
        )
        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='Output CSV filename (default: stdout)',
        )

    def handle(self, *args, **options):
        offset = options['offset']
        limit = options['limit']
        output_file = options['output']

        top_books = (
            Book.objects
            .annotate(favorite_count=Count('favorited_by'))
            .filter(favorite_count__gt=0)
            .order_by('-favorite_count', 'title')
            .select_related('author')[offset:offset + limit]
        )

        books_list = list(top_books)
        if not books_list:
            self.stdout.write(self.style.WARNING('No books found in that range.'))
            return

        fieldnames = ['rank', 'favorite_count', 'title', 'author', 'isbn', 'genre', 'sub_genre']
        if output_file:
            f = open(output_file, 'w', newline='', encoding='utf-8')
        else:
            f = sys.stdout

        try:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for i, book in enumerate(books_list, start=offset + 1):
                writer.writerow({
                    'rank': i,
                    'favorite_count': book.favorite_count,
                    'title': book.title,
                    'author': book.author.name,
                    'isbn': book.isbn or '',
                    'genre': book.genre or '',
                    'sub_genre': book.sub_genre or '',
                })
        finally:
            if output_file:
                f.close()
                self.stdout.write(self.style.SUCCESS(f'Exported {len(books_list)} books to {output_file}'))
            else:
                sys.stderr.write(f'\nExported {len(books_list)} books (ranks {offset + 1}-{offset + len(books_list)})\n')
