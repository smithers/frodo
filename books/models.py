from django.db import models
from django.contrib.auth.models import User


class Author(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Book(models.Model):
    GENRE_FICTION = "fiction"
    GENRE_NONFICTION = "nonfiction"
    GENRE_CHOICES = [
        (GENRE_FICTION, "Fiction"),
        (GENRE_NONFICTION, "Non-fiction"),
    ]

    title = models.CharField(max_length=255)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    # High-level genre: fiction vs non-fiction
    genre = models.CharField(
        max_length=20,
        choices=GENRE_CHOICES,
        default=GENRE_FICTION,
    )

    # Optional, more specific category (e.g., "Fantasy", "Biography")
    sub_genre = models.CharField(max_length=100, null=True, blank=True)

    # We make ISBN nullable/blank because if we find a duplicate Title+Author,
    # we might choose to ignore the new ISBN, or we might insert a book manually without one.
    isbn = models.CharField(max_length=13, unique=True, null=True, blank=True)
    
    # Mark popular books for faster local database searches
    is_popular = models.BooleanField(default=False, db_index=True)

    # Track when the book entry was created
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        # This tells the DB: "You can have many books named 'It',
        # and many books by 'King', but only ONE 'It' by 'King'."
        unique_together = ("title", "author")
        indexes = [
            models.Index(fields=["is_popular", "title"]),  # For faster popular book searches
        ]

    def __str__(self):
        return self.title


class UserFavoriteBook(models.Model):
    """Tracks books that users love (no ratings, just favorites)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorite_books")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="favorited_by")
    explanation = models.TextField(max_length=500, blank=True, help_text="Why you love this book")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "book")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["book"]),
        ]

    def __str__(self):
        return f"{self.user.username} loves {self.book.title}"


class ToBeReadBook(models.Model):
    """Tracks books users plan to read next."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tbr_books")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="wanted_by")
    note = models.TextField(max_length=500, blank=True, help_text="Optional notes or why it's on your TBR")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "book")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["book"]),
        ]
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.user.username} wants to read {self.book.title}"


class Feedback(models.Model):
    """Stores reader feedback submitted from the site UI."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="feedback")
    page_url = models.URLField(max_length=500)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    message = models.TextField(blank=True)
    contact_email = models.EmailField(blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=64, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Feedback {self.id} ({self.rating})"


class UserEmailPreferences(models.Model):
    """Tracks user email preferences, including unsubscribe status for recommendation emails."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="email_preferences")
    receive_recommendation_emails = models.BooleanField(default=True, help_text="Whether to receive new book recommendation emails")
    unsubscribed_at = models.DateTimeField(null=True, blank=True, help_text="When the user unsubscribed from recommendation emails")
    last_recommendation_email_sent = models.DateTimeField(null=True, blank=True, help_text="When the last recommendation email was sent to this user")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Email Preferences"
        verbose_name_plural = "User Email Preferences"

    def __str__(self):
        status = "subscribed" if self.receive_recommendation_emails else "unsubscribed"
        return f"{self.user.username} - {status}"