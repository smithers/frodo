from django.urls import path, reverse_lazy
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
path('', views.homepage_view, name='home'),
path('how-it-works/', views.how_it_works_view, name='how_it_works'),
path('register/', views.register_view, name='register'),
# Redirect old rating URLs to new favorite URLs for backward compatibility
path('rate/', RedirectView.as_view(url='/add-favorite/', permanent=True)),
path('rate/save/', RedirectView.as_view(url='/add-favorite/save/', permanent=True)),
path('add-favorite/', views.add_favorite_view, name='add_favorite'),
path('add-favorite/save/', views.save_favorite_view, name='save_favorite'),
path('remove-favorite/', views.remove_favorite_view, name='remove_favorite'),
path('my-books/', views.my_books_view, name='my_books'),
path('tbr/', views.tbr_list_view, name='tbr_list'),
path('tbr/remove/', views.remove_tbr_view, name='remove_tbr'),
path('recommend/', views.recommendation_view, name='recommendations'),
path('terms-of-use/', views.terms_of_use_view, name='terms_of_use'),
path('privacy-policy/', views.privacy_policy_view, name='privacy_policy'),
path('api/search/', views.book_autocomplete, name='book_autocomplete'),
path('api/book-info/', views.book_info_view, name='book_info'),
path('feedback/submit/', views.feedback_submit, name='feedback_submit'),
    # Password reset URLs
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    # Custom password reset confirm view - completely custom function view
    # Put the /set-password/ pattern FIRST so it matches before any potential conflicts
    path('password-reset-confirm/<str:uidb64>/<str:token>/set-password/', views.password_reset_confirm_view, name='password_reset_confirm_set'),
    path('password-reset-confirm/<str:uidb64>/<str:token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('password-reset-complete/', views.password_reset_complete_view, name='password_reset_complete'),
# Username recovery URL
path('forgot-username/', views.forgot_username_view, name='forgot_username'),
# Unsubscribe from recommendation emails
path('unsubscribe/<str:uidb64>/<str:token>/', views.unsubscribe_recommendations_view, name='unsubscribe_recommendations'),
path('sitemap.xml', views.sitemap_view, name='sitemap'),
path('robots.txt', views.robots_txt, name='robots_txt'),
path('export/top-favorited-books-100-200.csv', views.export_top_favorited_csv_view, name='export_top_favorited_csv'),
]