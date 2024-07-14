from django.contrib.auth.models import User
from django.db import models

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    base_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    def __str__(self):
        return self.user.username