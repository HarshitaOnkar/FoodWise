from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login, logout as auth_logout

from .forms import RestaurantSignupForm, LeftoverRecordForm, DailyFoodRecordForm, FoodItemForm, DiscountedSaleForm, StorageRecordForm, DonationForm, ShareForm, WasteForm
from .models import Restaurant, LeftoverRecord, DailyFoodRecord

from django.contrib.auth.decorators import login_required

from django.db.models import Count, F, ExpressionWrapper, IntegerField, Sum
from django.utils import timezone

# Create your views here.


def home(request):
    return render(request, 'wastage/home.html')


def signup(request):
    if request.method == 'POST':
        form = RestaurantSignupForm(request.POST)

        if form.is_valid():
            user = form.save()

            Restaurant.objects.create(
                user=user,
                restaurant_name=form.cleaned_data['restaurant_name'],
                owner_name=form.cleaned_data['owner_name'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data['phone'],
                address=form.cleaned_data['address'],
                city=form.cleaned_data['city'],
            )

            return redirect('login')

    else:
        form = RestaurantSignupForm()

    return render(request, 'wastage/signup.html', {'form': form})


def login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect(request.GET.get('next', 'dashboard'))

    else:
        form = AuthenticationForm()

    return render(request, 'wastage/login.html', {'form': form})


def logout(request):
    auth_logout(request)
    return redirect('home')


@login_required
def dashboard(request):
    restaurant = request.user.restaurant
    surplus_count = LeftoverRecord.objects.filter(
        restaurant=restaurant).count()
    donation_count = LeftoverRecord.objects.filter(
        restaurant=restaurant, action='DONATED').count()
    recent_surplus = LeftoverRecord.objects.filter(
        restaurant=restaurant).select_related('food_item').order_by('-recorded_at')[:4]
    recent_donations = LeftoverRecord.objects.filter(restaurant=restaurant, action='DONATED').select_related(
        'food_item', 'donation_organization').order_by('-recorded_at')[:4]

    current_month = timezone.now().month
    current_year = timezone.now().year
    current_month_name = timezone.now().strftime('%b')
    donation_data = (
        LeftoverRecord.objects.filter(
            restaurant=restaurant,
            action='DONATED',
            recorded_at__year=current_year,
            recorded_at__month=current_month,
        )
        .values('recorded_at__day')
        .annotate(total=Count('id'))
        .order_by('recorded_at__day')
    )

    donation_counts = [0]*28
    for item in donation_data:
        day = item['recorded_at__day']
        if day <= 28:
            donation_counts[day-1] = item['total']

    max_donation = max(donation_counts) or 1
    donation_points = " ".join(
        f"{(index/27)*700},{200-(value/max_donation)*170}"
        for index, value in enumerate(donation_counts)
    )

    needy_people_helped = sum(
        donation.people_helped
        for donation in LeftoverRecord.objects.filter(
            restaurant=restaurant,
            action='DONATED',
            recorded_at__year=current_year,
            recorded_at__month=current_month,
        )
    )

    staff_people_helped = sum(
        record.people_helped
        for record in LeftoverRecord.objects.filter(
            restaurant=restaurant,
            action='STAFF',
            recorded_at__year=current_year,
            recorded_at__month=current_month,
        )
    )

    # =========================================================
    # REDUCE STATISTICS - UNIT AWARE
    # =========================================================
    surplus_data = (
        LeftoverRecord.objects
        .filter(restaurant=restaurant)
        .values('unit')
        .annotate(total=Sum('quantity'))
    )

    surplus_by_unit = {
        item['unit']: item['total']
        for item in surplus_data
    }

    rescued_data = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action__in=[
                'DISCOUNTED',
                'DONATED',
                'STORED',
                'STAFF'
            ]
        )
        .values('unit')
        .annotate(total=Sum('quantity'))
    )

    rescued_by_unit = {
        item['unit']: item['total']
        for item in rescued_data
    }

    wasted_data = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='WASTED'
        )
        .values('unit')
        .annotate(total=Sum('quantity'))
    )

    wasted_by_unit = {
        item['unit']: item['total']
        for item in wasted_data
    }

    # Calculate reduction percentage separately for each unit

    reduction_by_unit = {}
    for unit, surplus in surplus_by_unit.items():
        rescued = rescued_by_unit.get(unit, 0)
        reduction_by_unit[unit] = (
            (rescued / surplus) * 100
            if surplus > 0 else 0
        )

    return render(request, 'wastage/dashboard.html', {
        'restaurant': restaurant,
        'surplus_count': surplus_count,
        'donation_count': donation_count,
        'recent_surplus': recent_surplus,
        'recent_donations': recent_donations,
        'donation_data': donation_data,
        'current_month_name': current_month_name,
        'donation_counts': donation_counts,
        'donation_points': donation_points,
        'needy_people_helped': needy_people_helped,
        'staff_people_helped': staff_people_helped,
        'rescued_by_unit': rescued_by_unit,
        'surplus_by_unit': surplus_by_unit,
        'rescued_by_unit': rescued_by_unit,
        'wasted_by_unit': wasted_by_unit,
        'reduction_by_unit': reduction_by_unit,
    })


@login_required
def add_surplus(request):
    restaurant = request.user.restaurant

    if request.method == 'POST':
        form = LeftoverRecordForm(request.POST, restaurant=restaurant)

        if form.is_valid():
            leftover = form.save(commit=False)
            leftover.restaurant = restaurant
            leftover.save()

            if leftover.action == 'DISCOUNTED':
                return redirect('discounted_sale')

            elif leftover.action == 'STORED':
                return redirect('storage_record')

            elif leftover.action == 'DONATED':
                return redirect('donation', leftover_id=leftover.id)

            elif leftover.action == 'STAFF':
                return redirect('share_food')

            elif leftover.action == 'WASTED':
                return redirect('waste_food')

            return redirect('dashboard')

    else:
        form = LeftoverRecordForm(restaurant=restaurant)

    return render(
        request,
        'wastage/add_surplus.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )


@login_required
def track_food(request):
    restaurant = request.user.restaurant

    if request.method == 'POST':
        form = DailyFoodRecordForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():
            record = form.save(commit=False)
            record.restaurant = restaurant
            record.save()

            return redirect('dashboard')

    else:
        form = DailyFoodRecordForm(
            restaurant=restaurant
        )

    return render(
        request,
        'wastage/track_food.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )


@login_required
def food_records(request):
    restaurant = request.user.restaurant

    records = DailyFoodRecord.objects.filter(
        restaurant=restaurant
    ).select_related(
        'food_item'
    ).annotate(remaining=ExpressionWrapper(
        F('quantity_prepared')-F('quantity_sold'),
        output_field=IntegerField()
    )
    ).order_by('-date')

    return render(
        request,
        'wastage/food_records.html',
        {
            'restaurant': restaurant,
            'records': records,
        }
    )


@login_required
def add_food_item(request):
    restaurant = request.user.restaurant

    if request.method == 'POST':
        form = FoodItemForm(request.POST)

        if form.is_valid():
            food_item = form.save(commit=False)
            food_item.restaurant = restaurant
            food_item.save()

            return redirect('track_food')

    else:
        form = FoodItemForm()

    return render(
        request,
        'wastage/add_food_item.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )


@login_required
def discounted_sale(request):
    restaurant = request.user.restaurant

    if request.method == 'POST':
        form = DiscountedSaleForm(request.POST, restaurant=restaurant)

        if form.is_valid():
            sale = form.save(commit=False)

            if sale.leftover_record.restaurant != restaurant:
                form.add_error(
                    'leftover_record',
                    'You can only sell your own restaurant food.'
                )
            else:
                sale.save()
                return redirect('dashboard')

    else:
        form = DiscountedSaleForm(restaurant=restaurant)

    return render(
        request,
        'wastage/discounted_sale.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )


@login_required
def storage_record(request):
    restaurant = request.user.restaurant

    if request.method == 'POST':
        form = StorageRecordForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():
            storage = form.save(commit=False)

            if storage.leftover_record.restaurant != restaurant:
                form.add_error(
                    'leftover_record',
                    'You can only store your own restaurant food.'
                )
            else:
                storage.save()
                return redirect('dashboard')

    else:
        form = StorageRecordForm(restaurant=restaurant)

    return render(
        request,
        'wastage/storage_record.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )


@login_required
def donation(request, leftover_id):
    restaurant = request.user.restaurant

    leftover = get_object_or_404(
        LeftoverRecord,
        id=leftover_id,
        restaurant=restaurant,
        action='DONATED'
    )

    if request.method == 'POST':
        form = DonationForm(
            request.POST,
            restaurant=restaurant,
            leftover=leftover
        )

        if form.is_valid():
            leftover = form.cleaned_data['leftover_record']

            leftover.donation_organization = form.cleaned_data[
                'donation_organization'
            ]
            leftover.people_helped = form.cleaned_data[
                'people_helped'
            ]

            leftover.save()

            return redirect('dashboard')

    else:
        form = DonationForm(
            restaurant=restaurant,
            leftover=leftover
        )

    return render(
        request,
        'wastage/donation.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )


@login_required
def share_food(request):
    restaurant = request.user.restaurant

    if request.method == 'POST':
        form = ShareForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():
            leftover = form.cleaned_data['leftover_record']

            leftover.people_helped = form.cleaned_data[
                'people_helped'
            ]

            leftover.save()

            return redirect('dashboard')

    else:
        form = ShareForm(
            restaurant=restaurant
        )

    return render(
        request,
        'wastage/share_food.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )


@login_required
def waste_food(request):
    restaurant = request.user.restaurant

    if request.method == 'POST':
        form = WasteForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():
            leftover = form.cleaned_data['leftover_record']

            leftover.waste_reason = form.cleaned_data[
                'waste_reason'
            ]

            leftover.save()

            return redirect('dashboard')

    else:
        form = WasteForm(
            restaurant=restaurant
        )

    return render(
        request,
        'wastage/waste_food.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )
