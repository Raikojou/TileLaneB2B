from django.contrib import admin
from .models import PricingRule

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ('user', 'discount_percentage', 'special_price')
    search_fields = ('user__username', 'product_id')