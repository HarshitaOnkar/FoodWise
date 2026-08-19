from django.contrib import admin

# Register your models here.
from .models import (
    Restaurant,
    FoodItem,
    DailyFoodRecord,
    LeftoverRecord,
    FoodRescueOrganization,
    DiscountedSale,
    StorageRecord,
)
admin.site.register(Restaurant)
admin.site.register(FoodItem)
admin.site.register(DailyFoodRecord)
admin.site.register(LeftoverRecord)
admin.site.register(FoodRescueOrganization)
admin.site.register(DiscountedSale)
admin.site.register(StorageRecord)