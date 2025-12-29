from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import BooleanField, Case, Count, DateTimeField
from django.db.models import Exists, ExpressionWrapper, F, OuterRef, Value, When
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import PostForm
from .models import Follow, Like, Post, User

import json


_DEF_PAGE_SIZE = 10


def _with_like_flags(qs, user):
    qs = qs.annotate(likes_total=Count("likes"))
    if user.is_authenticated:
        qs = qs.annotate(
            liked_by_me=Exists(Like.objects.filter(user=user, post=OuterRef("pk")))
        )
    else:
        qs = qs.annotate(liked_by_me=Value(False, output_field=BooleanField()))

    edited_threshold = ExpressionWrapper(
        F("created_at") + Value(timedelta(seconds=1)),
        output_field=DateTimeField()
    )
    qs = qs.annotate(
        was_edited=Case(
            When(updated_at__gt=edited_threshold, then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        )
    )
    return qs


def _paginate(request, queryset, per_page=_DEF_PAGE_SIZE):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def index(request):
    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "You have to be signed in to make a post")
            return redirect("index")
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "Post sent!")
            return redirect("index")
    else:
        form = PostForm() if request.user.is_authenticated else None

    posts_qs = _with_like_flags(
        Post.objects.all(), request.user
    ).order_by("-created_at", "-id")
    page_obj = _paginate(request, posts_qs)

    return render(request, "network/index.html", {
        "form": form, "posts": page_obj.object_list, "page_obj": page_obj})



def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "network/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "network/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "network/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "network/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/register.html")


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)

    is_self = request.user.is_authenticated and request.user == profile_user
    if request.method == "POST" and request.user.is_authenticated and not is_self:
        rel, created = Follow.objects.get_or_create(
            follower=request.user,
            following=profile_user,
        )
        if not created:
            rel.delete()
        return redirect("profile", username=username)

    posts_qs = _with_like_flags(
        Post.objects.filter(
            author=profile_user), request.user).order_by("-created_at", "-id")
    page_obj = _paginate(request, posts_qs)

    follower_count = Follow.objects.filter(following=profile_user).count()
    following_count = Follow.objects.filter(follower=profile_user).count()

    is_following = False
    if request.user.is_authenticated and not is_self:
        is_following = Follow.objects.filter(
            follower=request.user, following=profile_user
        ).exists()

    return render(request, "network/profile.html", {
        "profile_user": profile_user,
        "posts": page_obj.object_list,
        "page_obj": page_obj,
        "follower_count": follower_count,
        "following_count": following_count,
        "is_self": is_self,
        "is_following": is_following,
    })


@login_required
def following(request):
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "Posted!")
            return redirect("following")
    else:
        form = PostForm()

    followed_ids = Follow.objects.filter(follower=request.user).values_list(
        "following_id", flat=True
    )

    posts_qs = _with_like_flags(
        Post.objects.filter(author_id__in=followed_ids), request.user
    ).order_by("-created_at", "-id")
    page_obj = _paginate(request, posts_qs)

    return render(
        request,
        "network/following.html",
        {"form": form, "posts": page_obj.object_list, "page_obj": page_obj}
    )



@login_required
@require_POST
def edit_post_api(request, post_id: int):
    post = get_object_or_404(Post, id=post_id)

    if post.author_id != request.user.id:
        return JsonResponse({"error": "Forbidden"}, status=403)

    content = None

    ctype = request.META.get("CONTENT_TYPE", "").lower()
    if "application/json" in ctype:
        try:
            raw = request.body.decode("utf-8") or "{}"
            data = json.loads(raw)
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        content = (data.get("content") or "").strip()
    else:
        content = (request.POST.get("content") or "").strip()

    if not content:
        return JsonResponse({"error": "Post cannot be empty."}, status=400)
    if len(content) > 500:
        return JsonResponse({"error": "Posts have a 500 character limit."}, status=400)

    post.content = content
    post.save()

    return JsonResponse({"id": post.id, "content": post.content}, status=200)


@login_required
@require_POST
def toggle_like_api(request, post_id: int):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if created:
        liked = True
    else:
        like.delete()
        liked = False

    likes = post.likes.count()
    return JsonResponse({"id": post.id, "liked": liked, "likes":likes}, status=200)
