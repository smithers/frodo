from django.contrib import admin
from .models import Author, Book, UserBookRating

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'isbn')
    search_fields = ('title', 'isbn')

@admin.register(UserBookRating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')