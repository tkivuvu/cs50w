from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models


class User(AbstractUser):
    watchlist = models.ManyToManyField(
        "Listing", blank=True, related_name="watchlisted_by"
    )

    def __str__(self):
        return self.username

class Category(models.Model):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.name

class Listing(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    image_url = models.URLField(blank=True)
    starting_bid = models.DecimalField(
        max_digits=10,
          decimal_places=2,
          validators=[MinValueValidator(0.01)])
    category = models.ForeignKey(
        Category,
          null=True, blank=True,
            on_delete=models.SET_NULL,
              related_name="listings"
    )
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="listings")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def get_current_price(self):
        top = self.bids.order_by("-amount").first()
        if top and top.amount is not None:
            return top.amount
        return self.starting_bid

    def get_highest_bidder(self):
        top = self.bids.order_by("-amount").select_related("bidder").first()
        return top.bidder if top else None

    def get_total_bids(self):
        return self.bids.count()

    def __str__(self):
        return f"{self.title} (#{self.pk})"


class Bid(models.Model):
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="bids")
    bidder = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bids")
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} on {self.listing} by {self.bidder}"

class Comment(models.Model):
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="comments")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"comment by {self.author} on {self.listing}"

