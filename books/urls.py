from django.urls import path  
from . import views

urlpatterns = [
path('', views.homepage_view, name='home'),
path('register/', views.register_view, name='register'),
path('rate/', views.add_rating_view, name='rate_book'),
path('rate/save/', views.save_rating_view, name='save_rating'),
path('my-books/', views.my_books_view, name='my_books'),
path('recommend/', views.recommendation_view, name='recommendations'),
path('api/search/', views.book_autocomplete, name='book_autocomplete'),
]