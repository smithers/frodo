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

    def handle(self, *args, **options):
        limit = options['limit']
        
        # Get books ordered by number of favorites
        top_books = (
            Book.objects
            .annotate(favorite_count=Count('favorited_by'))
            .filter(favorite_count__gt=0)
            .order_by('-favorite_count', 'title')
            .select_related('author')[:limit]
        )
        
        if not top_books:
            self.stdout.write(self.style.WARNING('No favorited books found.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\nTop {limit} Most Favorited Books:\n'))
        self.stdout.write('-' * 100)
        self.stdout.write(f"{'Rank':<6} {'Favorites':<12} {'Title':<50} {'Author':<30}")
        self.stdout.write('-' * 100)
        
        for rank, book in enumerate(top_books, 1):
            favorite_count = book.favorite_count
            title = book.title[:47] + '...' if len(book.title) > 50 else book.title
            author = book.author.name[:27] + '...' if len(book.author.name) > 30 else book.author.name
            
            self.stdout.write(f"{rank:<6} {favorite_count:<12} {title:<50} {author:<30}")
        
        self.stdout.write('-' * 100)
        self.stdout.write(f'\nTotal books with favorites: {Book.objects.annotate(favorite_count=Count("favorited_by")).filter(favorite_count__gt=0).count()}')
