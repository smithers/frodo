from django.core.management.base import BaseCommand
from django.db.models import Count
from books.models import Book, UserFavoriteBook


class Command(BaseCommand):
    help = 'Display the top N most favorited books'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Number of books to display (default: 50)',
        )
        parser.add_argument(
            '--offset',
            type=int,
            default=0,
            help='Number of books to skip from the top (default: 0)',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        offset = options['offset']
        
        # Get books ordered by number of favorites
        top_books = (
            Book.objects
            .annotate(favorite_count=Count('favorited_by'))
            .filter(favorite_count__gt=0)
            .order_by('-favorite_count', 'title')
            .select_related('author')[offset:offset + limit]
        )
        
        if not top_books:
            self.stdout.write(self.style.WARNING('No favorited books found.'))
            return
        
        start_rank = offset + 1
        end_rank = offset + len(top_books)
        self.stdout.write(self.style.SUCCESS(f'\nMost Favorited Books (Rank {start_rank} to {end_rank}):\n'))
        self.stdout.write('-' * 100)
        self.stdout.write(f"{'Rank':<6} {'Favorites':<12} {'Title':<50} {'Author':<30}")
        self.stdout.write('-' * 100)
        
        for rank, book in enumerate(top_books, start_rank):
            favorite_count = book.favorite_count
            title = book.title[:47] + '...' if len(book.title) > 50 else book.title
            author = book.author.name[:27] + '...' if len(book.author.name) > 30 else book.author.name
            
            self.stdout.write(f"{rank:<6} {favorite_count:<12} {title:<50} {author:<30}")
        
        self.stdout.write('-' * 100)
        self.stdout.write(f'\nTotal books with favorites: {Book.objects.annotate(favorite_count=Count("favorited_by")).filter(favorite_count__gt=0).count()}')
