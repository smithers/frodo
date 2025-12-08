from django.urls import path  
from . import views

urlpatterns = [
path('rate/', views.add_rating_view, name='rate_book'),
path('rate/save/', views.save_rating_view, name='save_rating'),
]