import csv
import time
import requests
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import IntegrityError
from books.models import Book, Author
from books.utils import smart_title_case


class Command(BaseCommand):
    help = "Mark books as popular based on a CSV file or existing database"

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=str,
            help='Path to CSV file with popular books (columns: title, author, isbn)',
        )
        parser.add_argument(
            '--top-n',
            type=int,
            default=3000,
            help='Number of top books to mark as popular (by favorite count)',
        )
        parser.add_argument(
            '--fetch-from-api',
            action='store_true',
            help='Fetch popular books from Google Books API to reach target count',
        )

    def handle(self, *args, **options):
        if options['csv']:
            # Import from CSV
            self.import_from_csv(options['csv'])
        elif options['fetch_from_api']:
            # Fetch popular books from Google Books API
            self.fetch_popular_books_from_api(options['top_n'])
        else:
            # Mark top N books by favorite count
            self.mark_top_books(options['top_n'])

    def import_from_csv(self, csv_path):
        """Import popular books from CSV file"""
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            
            for row in reader:
                title = smart_title_case(row.get('title', '').strip())
                author_name = row.get('author', '').strip().title()
                isbn = row.get('isbn', '').strip() or None
                
                if not title or not author_name:
                    continue
                
                author, _ = Author.objects.get_or_create(
                    name__iexact=author_name,
                    defaults={'name': author_name}
                )
                
                book, created = Book.objects.get_or_create(
                    title__iexact=title,
                    author=author,
                    defaults={
                        'title': title,
                        'author': author,
                        'isbn': isbn,
                        'is_popular': True
                    }
                )
                
                if not created:
                    book.is_popular = True
                    if isbn and not book.isbn:
                        book.isbn = isbn
                    book.save()
                
                count += 1
                
        self.stdout.write(self.style.SUCCESS(f'Marked {count} books as popular'))

    def mark_top_books(self, top_n):
        """Mark top N books by favorite count as popular"""
        # First, unmark all books as not popular
        Book.objects.update(is_popular=False)
        
        # Get top books by number of favorites
        top_books = Book.objects.annotate(
            favorite_count=Count('favorited_by')
        ).order_by('-favorite_count')[:top_n]
        
        # Mark them as popular
        book_ids = [b.id for b in top_books]
        if book_ids:
            Book.objects.filter(id__in=book_ids).update(is_popular=True)
            self.stdout.write(self.style.SUCCESS(f'Marked {len(book_ids)} books as popular'))
        else:
            self.stdout.write(self.style.WARNING('No books found to mark as popular'))

    def fetch_popular_books_from_api(self, target_count):
        """Fetch popular books from Google Books API to reach target count"""
        # First, mark existing books with favorites as popular
        self.mark_top_books(target_count)
        
        # Count how many popular books we currently have
        current_count = Book.objects.filter(is_popular=True).count()
        self.stdout.write(f'Currently have {current_count} popular books')
        
        if current_count >= target_count:
            self.stdout.write(self.style.SUCCESS(f'Already have {current_count} popular books (target: {target_count})'))
            return
        
        needed = target_count - current_count
        self.stdout.write(f'Need to fetch {needed} more books from Google Books API')
        
        # Search queries for popular books - expanded list
        search_queries = [
            # General bestsellers
            'bestseller',
            'New York Times bestseller',
            'bestselling book',
            # Genres
            'popular fiction',
            'popular nonfiction',
            'science fiction',
            'fantasy',
            'mystery',
            'thriller',
            'romance',
            'historical fiction',
            'literary fiction',
            'biography',
            'memoir',
            'history',
            'science',
            'philosophy',
            # Awards and recognition
            'Pulitzer Prize',
            'Nobel Prize literature',
            'Booker Prize',
            'National Book Award',
            'Oprah Book Club',
            'Goodreads Choice',
            # Time periods and classics
            'classic literature',
            'modern classic',
            'contemporary fiction',
            '20th century literature',
            '21st century literature',
            # General terms
            'award winning',
            'best books',
            'must read',
            'top rated',
            'highly rated',
            'famous books',
            'popular book',
            # Specific authors (very popular ones)
            'Stephen King',
            'J.K. Rowling',
            'Dan Brown',
            'John Grisham',
            'James Patterson',
            'Nora Roberts',
            'Agatha Christie',
            'Jane Austen',
            'Charles Dickens',
            'Ernest Hemingway',
            'F. Scott Fitzgerald',
            'George Orwell',
            'J.R.R. Tolkien',
            'Harper Lee',
            'Margaret Atwood',
            'Toni Morrison',
            'Gabriel Garcia Marquez',
            'Maya Angelou',
            'Malcolm Gladwell',
            'Bill Bryson',
            'Brandon Sanderson',
            'Mistborn',
        ]
        
        session = requests.Session()
        added_count = 0
        seen_isbns = set(Book.objects.filter(is_popular=True).exclude(isbn__isnull=True).exclude(isbn='').values_list('isbn', flat=True))
        
        for query in search_queries:
            if added_count >= needed:
                break
                
            self.stdout.write(f'Searching for: {query}...')
            
            url = "https://www.googleapis.com/books/v1/volumes"
            params = {'q': query, 'maxResults': 40, 'orderBy': 'relevance'}  # Get more results per query
            
            try:
                response = session.get(url, params=params, timeout=10)
                if response.status_code != 200:
                    continue
                    
                data = response.json()
                items = data.get('items', [])
                
                for item in items:
                    if added_count >= needed:
                        break
                        
                    volume_info = item.get('volumeInfo', {})
                    
                    # Extract ISBN-13
                    identifiers = volume_info.get('industryIdentifiers', [])
                    isbn = next((i['identifier'] for i in identifiers if i['type'] == 'ISBN_13'), None)
                    
                    # Skip if no ISBN or already seen
                    if not isbn or isbn in seen_isbns:
                        continue
                    
                    # Get title and author
                    title = volume_info.get('title', '').strip()
                    authors = volume_info.get('authors', [])
                    
                    if not title or not authors:
                        continue
                    
                    author_name = authors[0].strip()
                    if not author_name:
                        continue
                    
                    # Normalize
                    clean_title = smart_title_case(title)
                    clean_author_name = author_name.title()
                    
                    # Get genre from categories if available
                    categories = volume_info.get('categories', [])
                    genre = Book.GENRE_FICTION  # default
                    if categories:
                        category_lower = categories[0].lower()
                        if any(term in category_lower for term in ['non-fiction', 'nonfiction', 'biography', 'history', 'science', 'business']):
                            genre = Book.GENRE_NONFICTION
                    
                    # Create or get author
                    try:
                        author = Author.objects.get(name__iexact=clean_author_name)
                    except Author.DoesNotExist:
                        author = Author.objects.create(name=clean_author_name)
                    
                    # Create or get book
                    try:
                        book = Book.objects.get(title__iexact=clean_title, author=author)
                        if not book.is_popular:
                            book.is_popular = True
                            if not book.isbn:
                                book.isbn = isbn
                            book.save()
                    except Book.DoesNotExist:
                        try:
                            book = Book.objects.create(
                                title=clean_title,
                                author=author,
                                isbn=isbn,
                                genre=genre,
                                is_popular=True
                            )
                        except IntegrityError:
                            # ISBN already exists, skip
                            continue
                    
                    seen_isbns.add(isbn)
                    added_count += 1
                    
                    if added_count % 10 == 0:
                        self.stdout.write(f'  Added {added_count} books so far...')
                
                # Rate limiting - be nice to the API
                time.sleep(0.3)
                
            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.WARNING(f'Error fetching {query}: {e}'))
                continue
        
        final_count = Book.objects.filter(is_popular=True).count()
        self.stdout.write(self.style.SUCCESS(f'Fetched {added_count} new books from API'))
        self.stdout.write(self.style.SUCCESS(f'Total popular books: {final_count}'))

