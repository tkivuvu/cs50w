from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("u/<str:username>/", views.profile, name="profile"),
    path("following/", views.following, name="following" ),
    path("api/posts/<int:post_id>/edit/", views.edit_post_api, name="edit_post_api"),
    path("api/posts/<int:post_id>/like/", views.toggle_like_api, name="toggle_like_api"),
]
