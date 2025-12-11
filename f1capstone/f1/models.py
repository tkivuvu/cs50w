from django.conf import settings
from django.db import models

class FavoriteDriver(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorite_drivers")
    driver_id = models.SlugField(max_length=50)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "driver_id")

class FavoriteConstructor(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorite_teams")
    constructor_id = models.SlugField(max_length=50)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "constructor_id")
