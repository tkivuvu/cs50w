# f1/urls.py

from django.urls import path, include
from django.contrib.auth import views as auth_views
from .forms import LoginForm
from . import views

app_name = "f1"

urlpatterns = [

    # -------------------------------
    # Home
    # -------------------------------
    path("", views.index, name="index"),

    # -------------------------------
    # Schedule
    # -------------------------------
    path("schedule/", views.schedule, name="schedule"),
    path("schedule/<int:year>/", views.schedule_year, name="schedule_year"),
    path(
        "schedule/<int:year>/<int:rnd>/",
        views.schedule_sessions,
        name="schedule_sessions",
    ),
    path(
        "schedule/<int:year>/<int:rnd>/<str:kind>/",
        views.schedule_session_detail,
        name="schedule_session_detail",
    ),

    # -------------------------------
    # Results & Standings
    # -------------------------------
    path("results/find/", views.results_find, name="results_find"),
    path(
        "results/<int:year>/overview/",
        views.results_year_hub,
        name="results_year_hub",
    ),
    path("results/<int:year>/", views.results_season, name="results_season"),
    path(
        "results/<int:year>/driver-standings/",
        views.standings_drivers,
        name="standings_drivers",
    ),
    path(
        "results/<int:year>/constructor-standings/",
        views.standings_constructors,
        name="standings_constructors",
    ),

    # -------------------------------
    # Driver & Team Detail Pages
    # -------------------------------
    path("drivers/<slug:driver_id>/", views.driver_detail, name="driver_detail"),
    path("teams/<slug:constructor_id>/", views.constructor_detail, name="constructor_detail"),

    # -------------------------------
    # Favorites (Drivers & Teams)
    # -------------------------------
    path(
        "drivers/<slug:driver_id>/favorite/",
        views.favorite_driver_toggle,
        name="favorite_driver_toggle",
    ),
    path(
        "teams/<slug:constructor_id>/favorite/",
        views.favorite_constructor_toggle,
        name="favorite_constructor_toggle",
    ),

    # -------------------------------
    # User Account & Authentication
    # -------------------------------
    path("me/", views.my_hub, name="my_hub"),
    path("accounts/signup/", views.signup, name="signup"),

    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="f1/login.html",
            authentication_form=LoginForm,
        ),
        name="login",
    ),

    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(next_page="f1:index"),
        name="logout",
    ),

    # Built-in Django auth URLs (password reset, etc.)
    path("accounts/", include("django.contrib.auth.urls")),
]
