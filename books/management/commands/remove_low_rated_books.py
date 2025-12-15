from django.core.management.base import BaseCommand
from books.models import Book, UserBookRating


class Command(BaseCommand):
    help = "Remove all books from the database that don't have any 4 or 5 star ratings"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Finding books with no 4 or 5 star ratings...'))
        
        all_books = Book.objects.all()
        books_to_delete = []
        
        for book in all_books:
            # Check if this book has any ratings of 4 or 5 stars
            high_ratings = UserBookRating.objects.filter(
                book=book,
                rating__in=[4, 5]
            ).exists()
            
            # If no high ratings, mark for deletion
            if not high_ratings:
                books_to_delete.append(book)
        
        if not books_to_delete:
            self.stdout.write(self.style.SUCCESS('No books to delete. All books have at least one 4 or 5 star rating.'))
            return
        
        self.stdout.write(self.style.WARNING(f'Found {len(books_to_delete)} books to delete.'))
        
        # Delete the books (ratings will be deleted via CASCADE)
        deleted_count = 0
        for book in books_to_delete:
            book.delete()
            deleted_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} book(s) that had no 4 or 5 star ratings.'))


