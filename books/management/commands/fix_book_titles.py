from django.core.management.base import BaseCommand

from books.models import Book
from books.utils import smart_title_case


class Command(BaseCommand):
    help = "Normalize existing book titles so 's after apostrophes is not capitalized."

    def handle(self, *args, **options):
        updated = 0

        for book in Book.objects.all():
            fixed_title = smart_title_case(book.title)
            if fixed_title != book.title:
                book.title = fixed_title
                book.save(update_fields=["title"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Updated book titles: {updated}"))







