from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Author, Book, UserFavoriteBook, Feedback, ToBeReadBook, UserReadBook

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'genre', 'sub_genre', 'isbn', 'created_at')
    search_fields = ('title', 'isbn')
    list_filter = ('genre', 'sub_genre', 'created_at')

@admin.register(UserFavoriteBook)
class FavoriteBookAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'created_at')
    list_filter = ('created_at',)


@admin.register(ToBeReadBook)
class ToBeReadBookAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'created_at')
    list_filter = ('created_at',)


@admin.register(UserReadBook)
class UserReadBookAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'marked_at')
    list_filter = ('marked_at',)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'page_url', 'rating', 'contact_email')
    search_fields = ('message', 'contact_email', 'page_url')
    list_filter = ('rating', 'created_at')


# Show user creation date in the Users admin list
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')