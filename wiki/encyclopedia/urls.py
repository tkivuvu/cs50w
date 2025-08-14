from django.urls import path

from . import views

app_name = "encyclopedia"

urlpatterns = [
    path("", views.index, name="index"),
    path("new/", views.new_page, name="new"),
    path("search/", views.search, name="search"),
    path("random/", views.random_page, name="random"),
    path("<str:title>/", views.entry, name="entry"),
    path("<str:title>/edit/", views.edit_page, name="edit"),
    
]
