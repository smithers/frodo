from django.core.management.base import BaseCommand
from books.services import search_books, search_database_books, search_google_books
from django.core.cache import cache


class Command(BaseCommand):
    help = "Test book search functionality to debug autocomplete issues"

    def add_arguments(self, parser):
        parser.add_argument(
            'query',
            type=str,
            help='Search query to test',
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear cache before testing',
        )

    def handle(self, *args, **options):
        query = options['query']
        
        if options['clear_cache']:
            cache.clear()
            self.stdout.write(self.style.SUCCESS('Cache cleared!'))
        
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(f"Testing search for: '{query}'")
        self.stdout.write(f"{'='*70}\n")
        
        # Test database search
        self.stdout.write("1. DATABASE SEARCH (popular books):")
        self.stdout.write("-" * 70)
        db_results = search_database_books(query)
        self.stdout.write(f"   Found {len(db_results)} results")
        if db_results:
            for i, book in enumerate(db_results, 1):
                self.stdout.write(f"   {i}. {book['title']} by {book['author']} (ISBN: {book['isbn']})")
        else:
            self.stdout.write("   No results")
        
        # Test Google Books API directly
        self.stdout.write("\n2. GOOGLE BOOKS API SEARCH:")
        self.stdout.write("-" * 70)
        google_results = search_google_books(query)
        self.stdout.write(f"   Found {len(google_results)} results")
        if google_results:
            for i, book in enumerate(google_results, 1):
                self.stdout.write(f"   {i}. {book['title']} by {book['author']} (ISBN: {book['isbn'] or 'none'})")
        else:
            self.stdout.write("   No results")
        
        # Test unified search
        self.stdout.write("\n3. UNIFIED SEARCH (database + Google):")
        self.stdout.write("-" * 70)
        all_results = search_books(query)
        self.stdout.write(f"   Found {len(all_results)} total results")
        if all_results:
            for i, book in enumerate(all_results, 1):
                self.stdout.write(f"   {i}. {book['title']} by {book['author']} (ISBN: {book['isbn'] or 'none'})")
        else:
            self.stdout.write("   No results")
        
        self.stdout.write(f"\n{'='*70}\n")
        
        if not all_results:
            self.stdout.write(self.style.WARNING(f"⚠️  WARNING: No results found for '{query}'!"))
        else:
            self.stdout.write(self.style.SUCCESS("✓ Search completed successfully"))
