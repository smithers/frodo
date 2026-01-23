from django.core.management.base import BaseCommand
from django.db.models import Q
from books.models import Book


class Command(BaseCommand):
    help = "Replace sub-genre 'Literary Fiction' (with or without trailing space) with 'General Fiction'"

    def handle(self, *args, **options):
        # Find books with "Literary Fiction" (with or without trailing space, case-insensitive)
        # Check for exact matches and case-insensitive matches
        books = Book.objects.filter(
            Q(sub_genre="Literary Fiction ") | 
            Q(sub_genre="Literary Fiction") |
            Q(sub_genre__iexact="Literary Fiction")
        ).distinct()
        
        count = books.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING("No books found with sub_genre 'Literary Fiction' (any variation)"))
            return
        
        # Update to "General Fiction"
        updated = books.update(sub_genre=Book.SUB_GENRE_GENERAL_FICTION)
        
        self.stdout.write(self.style.SUCCESS(f"Updated {updated} book(s) from 'Literary Fiction' to 'General Fiction'"))
