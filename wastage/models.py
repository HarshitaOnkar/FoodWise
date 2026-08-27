from django.db import models
from django.contrib.auth.models import User
# Create your models here.


class Restaurant(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='restaurant')
    restaurant_name = models.CharField(max_length=150)
    owner_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    city = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.restaurant_name


class FoodItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    dish_name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    average_cost = models.DecimalField(max_digits=8, decimal_places=2)
    selling_price = models.DecimalField(max_digits=8, decimal_places=2)
    can_be_stored = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.dish_name


class DailyFoodRecord(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    date = models.DateField()
    quantity_prepared = models.PositiveIntegerField()
    quantity_sold = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.food_item.dish_name}-{self.date}"


class LeftoverRecord(models.Model):
    ACTION_CHOICES = [
        ('DISCOUNTED', 'Discounted & Sold'),
        ('DONATED', 'Donated'),
        ('STORED', 'Stored'),
        ('STAFF', 'Given to Staff'),
        ('WASTED', 'Wasted'),
    ]
    UNIT_CHOICES = [
        ('KG', 'Kilograms'),
        ('G', 'Grams'),
        ('L', 'Litres'),
        ('ML', 'Millilitres'),
        ('PCS', 'pieces'),
    ]
    WASTE_REASON_CHOICES = [
        ('OVERPRODUCTION', 'Overproduction'),
        ('LOW_DEMAND', 'Low Demand'),
        ('SPOILAGE', 'Spoilage'),
        ('PREPARATION_ERROR', 'Preparation Error'),
        ('CUSTOMER_LEFTOVER', 'Customer Leftover'),
        ('OTHER', 'Other'),
    ]
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    daily_record = models.ForeignKey(DailyFoodRecord, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    quantity_used = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES,default='KG')
    people_helped = models.PositiveIntegerField(default=0)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    waste_reason = models.CharField(max_length=30, choices=WASTE_REASON_CHOICES, blank=True)
    donation_organization = models.ForeignKey('FoodRescueOrganization', on_delete=models.SET_NULL, null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.food_item.dish_name} - {self.action}"
    
    @property
    def remaining_quantity(self):
        return self.quantity - self.quantity_used

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.db.models import Sum
        
        remaining_food = (
            self.daily_record.quantity_prepared
            - self.daily_record.quantity_sold
        )

        existing_used = (
            LeftoverRecord.objects
            .filter(daily_record=self.daily_record)
            .exclude(pk=self.pk)
            .aggregate(total=Sum('quantity_used'))['total'] or 0
        )
        
        if existing_used + self.quantity > remaining_food:
            raise ValidationError(
                f"Only {remaining_food - existing_used} "
                f"of this food is still available."
            )


class FoodRescueOrganization(models.Model):
    ORGANIZATION_TYPE_CHOICES = [
        ('NGO', 'NGO / Food Rescue Organization'),
        ('SHELTER', 'Shelter / Community Center'),
        ('ANIMAL', 'Animal Welfare Organization'),
    ]
    organization_name = models.CharField(max_length=150)
    organization_type = models.CharField(
        max_length=50, choices=ORGANIZATION_TYPE_CHOICES)
    contact_person = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    city = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.organization_name


class DiscountedSale(models.Model):
    leftover_record = models.ForeignKey(
        LeftoverRecord, on_delete=models.CASCADE)
    quantity_sold = models.PositiveIntegerField()
    original_price = models.DecimalField(max_digits=8, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=8, decimal_places=2)
    sold_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.leftover_record.food_item.dish_name} - Discounted Sale"


class StorageRecord(models.Model):
    leftover_record = models.ForeignKey(
        LeftoverRecord, on_delete=models.CASCADE)
    quantity_stored = models.PositiveIntegerField()
    storage_method = models.CharField(max_length=50)
    use_by_date = models.DateField()
    stored_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.leftover_record.food_item.dish_name} - Stored"
