from django.urls import path
from . import views

app_name = 'coreseo'

urlpatterns = [
    path('sitemap.xml', views.sitemap_view, name='sitemap'),
    path('robots.txt', views.robots_view, name='robots'),
]