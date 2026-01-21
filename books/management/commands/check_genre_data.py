from django.core.management.base import BaseCommand
from books.models import Book


class Command(BaseCommand):
    help = 'Check how many books have genre data'

    def handle(self, *args, **options):
        total = Book.objects.count()
        with_genre = Book.objects.exclude(genre__isnull=True).exclude(genre='').count()
        
        # Also check genre distribution
        fiction_count = Book.objects.filter(genre='fiction').count()
        nonfiction_count = Book.objects.filter(genre='nonfiction').count()
        
        self.stdout.write(f'Total books: {total}')
        self.stdout.write(f'Books with genre data: {with_genre}')
        self.stdout.write(f'Books without genre: {total - with_genre}')
        self.stdout.write(f'  - Fiction: {fiction_count}')
        self.stdout.write(f'  - Non-fiction: {nonfiction_count}')
