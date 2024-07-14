from django.db import models
from django.contrib.auth.models import User

class PricingRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product_ids = models.TextField(blank=True, null=True)
    collection_ids = models.TextField(blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    special_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}"