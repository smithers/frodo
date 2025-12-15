from django.contrib import admin
from .models import Author, Book, UserFavoriteBook

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'isbn')
    search_fields = ('title', 'isbn')

@admin.register(UserFavoriteBook)
class FavoriteBookAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'created_at')
    list_filter = ('created_at',)