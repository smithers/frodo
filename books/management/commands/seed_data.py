import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from books.models import Author, Book, UserBookRating

class Command(BaseCommand):
    help = "Seeds the database with test data for recommendations"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Deleting old data...'))
        # Clear existing data to avoid duplicates
        UserBookRating.objects.all().delete()
        Book.objects.all().delete()
        Author.objects.all().delete()
        # We don't delete superusers, only the test users we are about to create
        User.objects.filter(username__startswith='testuser').delete()

        self.stdout.write(self.style.SUCCESS('Creating Authors and Books...'))

        # 1. Create Authors
        authors_list = ["J.K. Rowling", "Stephen King", "George Orwell", "J.R.R. Tolkien", "Agatha Christie"]
        authors = []
        for name in authors_list:
            author = Author.objects.create(name=name)
            authors.append(author)

        # 2. Create Books (4 books per author)
        books = []
        titles = [
            # Rowling
            ("Harry Potter 1", authors[0]), ("Harry Potter 2", authors[0]), ("Harry Potter 3", authors[0]), ("Casual Vacancy", authors[0]),
            # King
            ("It", authors[1]), ("The Shining", authors[1]), ("Carrie", authors[1]), ("Misery", authors[1]),
            # Orwell
            ("1984", authors[2]), ("Animal Farm", authors[2]), ("Homage to Catalonia", authors[2]), ("Road to Wigan Pier", authors[2]),
            # Tolkien
            ("The Hobbit", authors[3]), ("Fellowship of the Ring", authors[3]), ("Two Towers", authors[3]), ("Return of the King", authors[3]),
            # Christie
            ("Murder on the Orient Express", authors[4]), ("Death on the Nile", authors[4]), ("And Then There Were None", authors[4]), ("Halloween Party", authors[4]),
        ]

        for i, (title, author) in enumerate(titles):
            # Generate a fake ISBN based on loop index
            book = Book.objects.create(title=title, author=author, isbn=f"978-0-00-{i:06d}-1")
            books.append(book)

        self.stdout.write(self.style.SUCCESS(f'Created {len(books)} books.'))

        # 3. Create Users
        self.stdout.write(self.style.SUCCESS('Creating Users...'))
        test_users = []
        for i in range(1, 6): # Create 5 users
            username = f"testuser{i}"
            user = User.objects.create_user(username=username, password="password123")
            test_users.append(user)

        # 4. Create Ratings (Engineered for Similarity)
        
        # User 1 (The Target): Loves Fantasy (Rowling/Tolkien)
        # We give them 5 stars on specific books
        fantasy_books = books[0:3] + books[12:15] # HP and LOTR
        for book in fantasy_books:
            UserBookRating.objects.create(user=test_users[0], book=book, rating=5)

        # User 2 (The Match): Also loves Fantasy, plus one extra book
        # This user should be identified as "Similar" to User 1
        for book in fantasy_books:
            # They agree on the 5-star rating
            UserBookRating.objects.create(user=test_users[1], book=book, rating=5)
        
        # User 2 also likes "The Hobbit" (which User 1 hasn't read yet)
        # This should be the recommended book!
        the_hobbit = books[12] 
        # Actually, let's use a book User 1 hasn't rated yet for the recommendation
        # Let's say User 2 likes "The Shining" (King) as well
        the_shining = books[5]
        UserBookRating.objects.create(user=test_users[1], book=the_shining, rating=5)


        # User 3: Hates Fantasy (Ratings 1-2), Likes Horror
        # This user should NOT be similar to User 1
        for book in fantasy_books:
            UserBookRating.objects.create(user=test_users[2], book=book, rating=1)
        
        # Random ratings for others to fill the DB
        for user in test_users[3:]:
            # Pick 10 random books
            random_books = random.sample(books, 10)
            for book in random_books:
                rating = random.randint(1, 5)
                # Avoid crashing if we already rated it (though we cleaned DB first)
                if not UserBookRating.objects.filter(user=user, book=book).exists():
                    UserBookRating.objects.create(user=user, book=book, rating=rating)

        self.stdout.write(self.style.SUCCESS('Successfully seeded database!'))
        self.stdout.write(self.style.SUCCESS('User 1 (testuser1) loves Fantasy.'))
        self.stdout.write(self.style.SUCCESS('User 2 (testuser2) loves Fantasy + "The Shining".'))