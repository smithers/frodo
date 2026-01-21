import csv
from django.core.management.base import BaseCommand
from books.models import Book


class Command(BaseCommand):
    help = 'Export books table to CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='Output CSV filename (default: stdout)',
        )

    def handle(self, *args, **options):
        output_file = options['output']
        
        # Get all books with related author data
        books = Book.objects.select_related('author').order_by('id')
        
        # Define CSV columns
        fieldnames = [
            'id',
            'title',
            'author',
            'isbn',
            'genre',
            'sub_genre',
            'is_popular',
            'created_at',
        ]
        
        # Write to file or stdout
        if output_file:
            file_handle = open(output_file, 'w', newline='', encoding='utf-8')
        else:
            import sys
            file_handle = sys.stdout
        
        try:
            writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
            writer.writeheader()
            
            for book in books:
                writer.writerow({
                    'id': book.id,
                    'title': book.title,
                    'author': book.author.name,
                    'isbn': book.isbn or '',
                    'genre': book.genre,
                    'sub_genre': book.sub_genre or '',
                    'is_popular': book.is_popular,
                    'created_at': book.created_at.strftime('%Y-%m-%d %H:%M:%S') if book.created_at else '',
                })
        finally:
            if output_file:
                file_handle.close()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully exported {books.count()} books to {output_file}'
                    )
                )
            else:
                # When writing to stdout, write success message to stderr so it doesn't interfere with CSV
                import sys
                sys.stderr.write(f'\nSuccessfully exported {books.count()} books\n')
