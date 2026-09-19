from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Restaurant, LeftoverRecord, DailyFoodRecord, FoodItem, DiscountedSale, StorageRecord, FoodRescueOrganization

from django.db.models import Sum, F


class RestaurantSignupForm(UserCreationForm):

    restaurant_name = forms.CharField(max_length=150)
    owner_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=15)
    address = forms.CharField(widget=forms.Textarea)
    city = forms.CharField(max_length=100)

    class Meta:
        model = User
        fields = [
            'username',
            'password1',
            'password2',
            'restaurant_name',
            'owner_name',
            'email',
            'phone',
            'address',
            'city',
        ]


class LeftoverRecordForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)

        if restaurant:
            self.fields['daily_record'].queryset = DailyFoodRecord.objects.filter(
                restaurant=restaurant)
            self.fields['food_item'].queryset = FoodItem.objects.filter(
                restaurant=restaurant)

    class Meta:
        model = LeftoverRecord
        fields = [
            'food_item',
            'daily_record',
            'quantity',
            'unit',
            'action',
        ]


class DailyFoodRecordForm(forms.ModelForm):

    class Meta:
        model = DailyFoodRecord
        fields = [
            'food_item',
            'date',
            'quantity_prepared',
            'quantity_sold',
        ]

        widgets = {
            'date': forms.DateInput(
                attrs={'type': 'date'}
            ),
            'quantity_prepared': forms.NumberInput(
                attrs={'min': 0}
            ),
            'quantity_sold': forms.NumberInput(
                attrs={'min': 0}
            ),
        }

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)

        if restaurant:
            self.fields['food_item'].queryset = FoodItem.objects.filter(
                restaurant=restaurant,
                is_active=True
            )

    def clean(self):
        cleaned_data = super().clean()
        prepared = cleaned_data.get('quantity_prepared')
        sold = cleaned_data.get('quantity_sold')
        if prepared is not None and sold is not None:
            if sold > prepared:
                raise forms.ValidationError(
                    "Quantity sold cannot be greater than quantity prepared."
                )
            return cleaned_data


class FoodItemForm(forms.ModelForm):

    class Meta:
        model = FoodItem
        fields = [
            'dish_name',
            'category',
            'average_cost',
            'selling_price',
            'can_be_stored',
        ]

        widgets = {
            'dish_name': forms.TextInput(
                attrs={'placeholder': 'Enter food item name'}
            ),
            'category': forms.TextInput(
                attrs={'placeholder': 'Enter food category'}
            ),
            'average_cost': forms.NumberInput(
                attrs={'min': 0, 'step': '0.01'}
            ),
            'selling_price': forms.NumberInput(
                attrs={'min': 0, 'step': '0.01'}
            ),
        }


class DiscountedSaleForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)

        if restaurant:
            self.fields['leftover_record'].queryset = (
                LeftoverRecord.objects.filter(
                    restaurant=restaurant,
                    action='DISCOUNTED'
                )
            )

    class Meta:
        model = DiscountedSale
        fields = [
            'leftover_record',
            'quantity_sold',
            'original_price',
            'discounted_price',
        ]

        widgets = {
            'quantity_sold': forms.NumberInput(
                attrs={'min': 1}
            ),
            'original_price': forms.NumberInput(
                attrs={'min': 0, 'step': '0.01'}
            ),
            'discounted_price': forms.NumberInput(
                attrs={'min': 0, 'step': '0.01'}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        leftover = cleaned_data.get('leftover_record')
        quantity_sold = cleaned_data.get('quantity_sold')

        if leftover and quantity_sold:
            
            already_sold = (
                DiscountedSale.objects
                .filter(leftover_record=leftover)
                .exclude(pk=self.instance.pk)
                .aggregate(total=Sum('quantity_sold'))
                ['total'] or 0
            )
                
            available_quantity = (
                leftover.quantity - leftover.quantity_used
            )
            if quantity_sold > available_quantity:
                raise forms.ValidationError(
                    f"Only {available_quantity} "
                    f"of this leftover food is still available for sale."
                )
        return cleaned_data


class StorageRecordForm(forms.ModelForm):

    storage_method = forms.ChoiceField(
        choices=[
            ('REFRIGERATION', 'Refrigeration'),
            ('FREEZING', 'Freezing'),
            ('DRY_STORAGE', 'Dry Storage'),
            ('AIRTIGHT_CONTAINER', 'Airtight Container'),
        ]
    )

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)

        if restaurant:
            self.fields['leftover_record'].queryset = (
                LeftoverRecord.objects.filter(
                    restaurant=restaurant,
                    action='STORED'
                )
            )

    class Meta:
        model = StorageRecord
        fields = [
            'leftover_record',
            'quantity_stored',
            'storage_method',
            'use_by_date',
        ]

        widgets = {
            'quantity_stored': forms.NumberInput(
                attrs={'min': 1}
            ),
            'use_by_date': forms.DateInput(
                attrs={'type': 'date'}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        leftover = cleaned_data.get('leftover_record')
        quantity_stored = cleaned_data.get('quantity_stored')

        if leftover and quantity_stored:

            already_stored = (
                StorageRecord.objects
                .filter(leftover_record=leftover)
                .exclude(pk=self.instance.pk)
                .aggregate(total=Sum('quantity_stored'))['total'] or 0
            )

            if already_stored + quantity_stored > leftover.quantity:
                raise forms.ValidationError(
                    f"Only {leftover.quantity - already_stored} "
                    f"of this leftover food is still available for storage."
                )

        return cleaned_data


class DonationForm(forms.Form):

    leftover_record = forms.ModelChoiceField(
        queryset=LeftoverRecord.objects.none(),
        empty_label='- Select an option -'
    )

    donation_organization = forms.ModelChoiceField(
        queryset=FoodRescueOrganization.objects.filter(
            is_active=True
        ),
        empty_label='- Select an organization -'
    )

    quantity_donated = forms.DecimalField(
        min_value=0.01,
        max_digits=8,
        decimal_places=2,
        label='Quantity to Donate'
    )

    people_helped = forms.IntegerField(
        min_value=0,
        initial=0
    )

    def __init__(self, *args, **kwargs):

        restaurant = kwargs.pop('restaurant', None)
        leftover = kwargs.pop('leftover', None)

        super().__init__(*args, **kwargs)

        if restaurant:

            self.fields['leftover_record'].queryset = (
                LeftoverRecord.objects.filter(
                    restaurant=restaurant,
                    action='DONATED',
                    quantity_used__lt=F('quantity')
                )
            )

        if leftover:

            self.fields['leftover_record'].queryset = (
                LeftoverRecord.objects.filter(
                    id=leftover.id
                )
            )

            self.fields['leftover_record'].initial = leftover

            available_quantity = (
                leftover.quantity - leftover.quantity_used
            )

            self.fields['quantity_donated'].widget.attrs.update({
                'max': str(available_quantity),
                'step': '0.01'
            })

    def clean(self):

        cleaned_data = super().clean()

        leftover = cleaned_data.get('leftover_record')
        quantity_donated = cleaned_data.get('quantity_donated')

        if leftover and quantity_donated is not None:

            available_quantity = (
                leftover.quantity - leftover.quantity_used
            )

            if quantity_donated > available_quantity:

                raise forms.ValidationError(
                    f'Only {available_quantity} '
                    f'{leftover.unit} of this food is still available '
                    f'for donation.'
                )

        return cleaned_data
    
class ShareForm(forms.Form):

    leftover_record = forms.ModelChoiceField(
        queryset=LeftoverRecord.objects.none(),
        empty_label='- Select an option -'
    )

    people_helped = forms.IntegerField(
        min_value=1,
        initial=1
    )

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)

        if restaurant:
            self.fields['leftover_record'].queryset = (
                LeftoverRecord.objects.filter(
                    restaurant=restaurant,
                    action='STAFF'
                )
            )


class WasteForm(forms.Form):

    leftover_record = forms.ModelChoiceField(
        queryset=LeftoverRecord.objects.none(),
        empty_label='- Select an option -'
    )

    waste_reason = forms.ChoiceField(
        choices=[
            ('', '- Select a reason -')
        ] + list(LeftoverRecord.WASTE_REASON_CHOICES)
    )

    def __init__(self, *args, **kwargs):
        restaurant = kwargs.pop('restaurant', None)
        super().__init__(*args, **kwargs)

        if restaurant:
            self.fields['leftover_record'].queryset = (
                LeftoverRecord.objects.filter(
                    restaurant=restaurant,
                    action='WASTED'
                )
            )


class OrganizationSignupForm(UserCreationForm):

    organization_name = forms.CharField(
        max_length=150,
        label='Organization Name'
    )

    organization_type = forms.ChoiceField(
        choices=FoodRescueOrganization.ORGANIZATION_TYPE_CHOICES,
        label='Organization Type'
    )

    owner_name = forms.CharField(
        max_length=100,
        label='Owner Name'
    )

    contact_person = forms.CharField(
        max_length=100,
        label='Contact Person'
    )

    email = forms.EmailField(
        label='Email'
    )

    phone = forms.CharField(
        max_length=15,
        label='Phone'
    )

    address = forms.CharField(
        widget=forms.Textarea,
        label='Address'
    )

    city = forms.CharField(
        max_length=100,
        label='City'
    )

    class Meta:
        model = User
        fields = [
            'username',
            'password1',
            'password2',
            'organization_name',
            'organization_type',
            'owner_name',
            'contact_person',
            'email',
            'phone',
            'address',
            'city',
        ]
        
class OrganizationLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your username',
            'autocomplete': 'username'
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password'
        })
    )
    
    
class RestaurantProfileForm(forms.ModelForm):

    class Meta:
        model = Restaurant

        fields = [
            'restaurant_name',
            'owner_name',
            'email',
            'phone',
            'address',
            'city',
        ]

        widgets = {
            'restaurant_name': forms.TextInput(
                attrs={
                    'placeholder': 'Enter restaurant name'
                }
            ),

            'owner_name': forms.TextInput(
                attrs={
                    'placeholder': 'Enter owner name'
                }
            ),

            'email': forms.EmailInput(
                attrs={
                    'placeholder': 'Enter email address'
                }
            ),

            'phone': forms.TextInput(
                attrs={
                    'placeholder': 'Enter phone number'
                }
            ),

            'address': forms.Textarea(
                attrs={
                    'placeholder': 'Enter restaurant address',
                    'rows': 3
                }
            ),

            'city': forms.TextInput(
                attrs={
                    'placeholder': 'Enter city'
                }
            ),
        }
        
        
class OrganizationProfileForm(forms.ModelForm):
    class Meta:
        model = FoodRescueOrganization
        fields = [
            'organization_name',
            'organization_type',
            'owner_name',
            'contact_person',
            'email',
            'phone',
            'address',
            'city',
        ]