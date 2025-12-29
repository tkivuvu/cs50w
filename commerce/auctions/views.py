from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .forms import ListingForm, BidForm, CommentForm
from .models import Bid, Category, Listing, User



def index(request):
    listings = (
        Listing.objects
        .filter(is_active=True)
        .select_related("owner", "category")
        .prefetch_related("bids")
        .order_by("-created_at")
    )
    return render(request, "auctions/index.html", {"listings":listings})


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
            return render(request, "auctions/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "auctions/login.html")


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
            return render(request, "auctions/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "auctions/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "auctions/register.html")


@login_required
def create_listing(request):
    if request.method == "POST":
        form = ListingForm(request.POST)
        if form.is_valid():
            listing = form.save(owner=request.user)
            return redirect("listing_detail", listing_id=listing.id)
    else:
        form = ListingForm()
    return render(request, "auctions/create_listing.html", {"form": form})

def listing_detail(request, listing_id):
    listing = get_object_or_404(
        Listing.objects.select_related("owner", "category").prefetch_related(
            "bids", "comments"
        ), pk=listing_id
    )
    context = listing_cont(request, listing)
    return render(request, "auctions/listing_detail.html", context)


def listing_cont(request, listing, bid_form=None, comment_form=None):
    on_watchlist = False
    if request.user.is_authenticated:
        on_watchlist = request.user.watchlist.filter(pk=listing.pk).exists()

    return{
        "listing": listing,
        "on_watchlist": on_watchlist,
        "bid_form": bid_form or BidForm(),
        "comment_form": comment_form or CommentForm(),
        "current_price": listing.get_current_price(),
        "highest_bidder": listing.get_highest_bidder(),
        "total_bids": listing.get_total_bids(),
    }


@login_required
def toggle_watchlist(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)
    if request.method == "POST":
        if request.user.watchlist.filter(pk=listing.pk).exists():
            request.user.watchlist.remove(listing)
        else:
            request.user.watchlist.add(listing)
    return redirect("listing_detail", listing_id=listing.id)


@login_required
def place_bid(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)
    if request.method != "POST":
        return redirect("listing_detail", listing_id=listing.id)

    form = BidForm(request.POST)
    if not form.is_valid():
        context = listing_cont(request, listing, bid_form=form)
        return render(request, "auctions/listing_detail.html", context)

    if not listing.is_active:
        form.add_error(None, "This auction is closed.")
        context = listing_cont(request, listing, bid_form=form)
        return render(request, "auctions/listing_detail.html", context)

    amount = form.cleaned_data["amount"]

    current_price = listing.get_current_price()
    if amount < listing.starting_bid:
        form.add_error("amount", "Your bid must at least match the starting bid.")
    elif amount <= current_price:
        form.add_error("amount", "Your bid must exceed the current price.")

    if form.errors:
        context = listing_cont(request, listing, bid_form=form)
        return render(request, "auctions/listing_detail.html", context)

    Bid.objects.create(listing=listing, bidder=request.user, amount=amount)
    return redirect("listing_detail", listing_id=listing.id)


@login_required
def auction_close(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)
    if request.method == "POST" and listing.owner_id == request.user.id and listing.is_active:
        listing.is_active = False
        listing.save()
    return redirect("listing_detail", listing_id=listing.id)


@login_required
def add_comment(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)
    if request.method != "POST":
        return redirect("listing_detail", listing_id=listing.id)

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.listing = listing
        comment.author = request.user
        comment.save()
        return redirect("listing_detail", listing_id=listing.id)

    context = listing_cont(request, listing, comment_form=form)
    return render(request, "auctions/listing_detail.html", context)


@login_required
def watchlist(request):
    listings = (
        request.user.watchlist
        .select_related("owner", "category")
        .prefetch_related("bids")
        .order_by("-created_at")
    )
    return render(request, "auctions/watchlist.html", {"listings": listings})


def categories(request):
    cates = (
        Category.objects
        .annotate(active_count=Count(
            "listings", filter=Q(listings__is_active=True)))
        .order_by("name")
    )
    return render (request, "auctions/categories.html", {"categories": cates})


def category_detail(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    listings = (
        Listing.objects
        .filter(is_active=True, category=category)
        .select_related("owner", "category")
        .prefetch_related("bids")
        .order_by("-created_at")
    )
    return render(
        request,
        "auctions/category_detail.html",
        {"category": category, "listings": listings}
    )


