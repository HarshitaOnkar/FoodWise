from types import SimpleNamespace
from urllib import request

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash

from django.contrib.auth.models import User

from django.db import models

from .forms import (
    RestaurantSignupForm,
    LeftoverRecordForm,
    DailyFoodRecordForm,
    FoodItemForm,
    DiscountedSaleForm,
    StorageRecordForm,
    DonationForm,
    ShareForm,
    WasteForm,
    OrganizationSignupForm,
    OrganizationLoginForm,
    RestaurantProfileForm,
    OrganizationProfileForm,
)

from .models import (
    Restaurant,
    LeftoverRecord,
    DailyFoodRecord,
    FoodRescueOrganization,
    FoodRequest,
)

from django.contrib.auth.decorators import login_required

from django.db.models import (
    Count,
    F,
    ExpressionWrapper,
    IntegerField,
    Sum,
    Value,
    DecimalField,
    OuterRef,
    Subquery,
)

from django.db.models.functions import Coalesce

from django.utils import timezone


# =============================================================
# HOME
# =============================================================

def home(request):
    return render(
        request,
        'wastage/home.html'
    )


# =============================================================
# ORGANIZATION HOME
# =============================================================

def organization_home(request):
    return render(
        request,
        'wastage/organization_home.html'
    )


# =============================================================
# RESTAURANT SIGNUP
# =============================================================

def signup(request):

    if request.method == 'POST':

        form = RestaurantSignupForm(
            request.POST
        )

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

    return render(
        request,
        'wastage/signup.html',
        {
            'form': form,
        }
    )


# =============================================================
# ORGANIZATION SIGNUP
# =============================================================

def organization_signup(request):

    if request.method == 'POST':

        form = OrganizationSignupForm(
            request.POST
        )

        if form.is_valid():

            user = form.save()

            FoodRescueOrganization.objects.create(
                user=user,
                organization_name=form.cleaned_data['organization_name'],
                organization_type=form.cleaned_data['organization_type'],
                contact_person=form.cleaned_data['contact_person'],
                owner_name=form.cleaned_data['owner_name'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data['phone'],
                address=form.cleaned_data['address'],
                city=form.cleaned_data['city'],
            )

            return redirect(
                'organization_login'
            )

    else:

        form = OrganizationSignupForm()

    return render(
        request,
        'wastage/organization_signup.html',
        {
            'form': form,
        }
    )


# =============================================================
# ORGANIZATION LOGIN
# =============================================================

def organization_login(request):

    if request.method == 'POST':

        form = OrganizationLoginForm(
            request.POST
        )

        if form.is_valid():

            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            try:

                user = User.objects.get(
                    username=username
                )

                # -------------------------------------------------
                # MAKE SURE THIS IS NOT A RESTAURANT ACCOUNT
                # -------------------------------------------------

                restaurant = Restaurant.objects.filter(
                    user=user
                ).first()

                if restaurant:

                    form.add_error(
                        None,
                        'This account is registered as a restaurant, not an organization.'
                    )

                else:

                    # -------------------------------------------------
                    # CHECK ORGANIZATION
                    # -------------------------------------------------

                    organization = (
                        FoodRescueOrganization.objects
                        .filter(user=user)
                        .first()
                    )

                    if (
                        organization
                        and user.check_password(password)
                    ):

                        auth_login(
                            request,
                            user
                        )

                        return redirect(
                            'organization_dashboard'
                        )

                    elif organization:

                        form.add_error(
                            None,
                            'Invalid username or password.'
                        )

                    else:

                        form.add_error(
                            None,
                            'This account is not registered as an organization.'
                        )

            except User.DoesNotExist:

                form.add_error(
                    None,
                    'Invalid username or password.'
                )

    else:

        form = OrganizationLoginForm()

    return render(
        request,
        'wastage/organization_login.html',
        {
            'form': form,
        }
    )


# =============================================================
# RESTAURANT LOGIN
# =============================================================

def login(request):

    if request.user.is_authenticated:

        restaurant = Restaurant.objects.filter(
            user=request.user
        ).first()

        if restaurant:

            return redirect(
                'dashboard'
            )

        organization = FoodRescueOrganization.objects.filter(
            user=request.user
        ).first()

        if organization:

            return redirect(
                'organization_dashboard'
            )

        auth_logout(request)

    if request.method == 'POST':

        form = AuthenticationForm(
            request,
            data=request.POST
        )

        if form.is_valid():

            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            try:

                user = User.objects.get(
                    username=username
                )

                if user.check_password(password):

                    restaurant = Restaurant.objects.filter(
                        user=user
                    ).first()

                    if restaurant:

                        auth_login(
                            request,
                            user
                        )

                        return redirect(
                            'dashboard'
                        )

                    else:

                        form.add_error(
                            None,
                            'This account is not registered as a restaurant.'
                        )

                else:

                    form.add_error(
                        None,
                        'Invalid username or password.'
                    )

            except User.DoesNotExist:

                form.add_error(
                    None,
                    'Invalid username or password.'
                )

    else:

        form = AuthenticationForm()

    return render(
        request,
        'wastage/login.html',
        {
            'form': form,
        }
    )


# =============================================================
# ORGANIZATION DASHBOARD
# =============================================================

@login_required
def organization_dashboard(request):

    organization = FoodRescueOrganization.objects.filter(
        user=request.user
    ).first()

    if not organization:
        return redirect('organization_login')

    # =========================================================
    # AVAILABLE SURPLUS FOOD
    #
    # Available surplus =
    #
    # (quantity_prepared - quantity_sold)
    #     - total quantity_used across ALL actions
    #
    # Example:
    #
    # Surplus = 20
    # Used = 2 + 8 + 2 + 2 + 2 = 16
    #
    # Available = 4
    # =========================================================

    available_food_list = (
        LeftoverRecord.objects
        .filter(
            action='DONATED'
        )
        .annotate(
            total_surplus=ExpressionWrapper(
                F('daily_record__quantity_prepared')
                - F('daily_record__quantity_sold'),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            ),
            total_used=Coalesce(
                Sum(
                    'daily_record__leftoverrecord__quantity_used'
                ),
                Value(0),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )
        .annotate(
            available_quantity=ExpressionWrapper(
                F('total_surplus') - F('total_used'),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )
        .filter(
            available_quantity__gt=0
        )
        .select_related(
            'food_item',
            'restaurant'
        )
        .order_by(
            '-recorded_at'
        )[:4]
    )

    # =========================================================
    # NUMBER OF AVAILABLE SURPLUS RECORDS
    # =========================================================

    available_food = (
        LeftoverRecord.objects
        .filter(
            action='DONATED'
        )
        .annotate(
            total_surplus=ExpressionWrapper(
                F('daily_record__quantity_prepared')
                - F('daily_record__quantity_sold'),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            ),
            total_used=Coalesce(
                Sum(
                    'daily_record__leftoverrecord__quantity_used'
                ),
                Value(0),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )
        .annotate(
            available_quantity=ExpressionWrapper(
                F('total_surplus') - F('total_used'),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )
        .filter(
            available_quantity__gt=0
        )
        .count()
    )

    # =========================================================
    # MY REQUESTS
    # =========================================================

    my_requests_list = (
        FoodRequest.objects
        .filter(
            organization=organization
        )
        .select_related(
            'leftover_record__food_item',
            'leftover_record__restaurant'
        )
        .order_by(
            '-requested_at'
        )
    )

    pending_requests_list = my_requests_list.filter(
        status='PENDING'
    )

    pending_requests = pending_requests_list.count()

    # =========================================================
    # APPROVED REQUESTS
    # =========================================================

    approved_requests = (
        FoodRequest.objects
        .filter(
            organization=organization,
            status='APPROVED'
        )
        .select_related(
            'leftover_record__food_item',
            'leftover_record__restaurant'
        )
        .order_by(
            '-requested_at'
        )
    )

    # =========================================================
    # DIRECT DONATIONS TO THIS ORGANIZATION
    # =========================================================

    direct_donations = (
        LeftoverRecord.objects
        .filter(
            donation_organization=organization,
            action='DONATED',
            quantity_used__gt=0
        )
        .select_related(
            'food_item',
            'restaurant'
        )
        .order_by(
            '-recorded_at'
        )
    )

    # =========================================================
    # TOTAL FOOD RECEIVED
    #
    # Approved requests + direct donations
    # =========================================================

    food_received_count = (
        approved_requests.count()
        + direct_donations.count()
    )

    # =========================================================
    # TOTAL PEOPLE HELPED
    # =========================================================

    direct_people_helped = (
        direct_donations.aggregate(
            total=Sum('people_helped')
        )['total'] or 0
    )

    approved_request_people_helped = (
        approved_requests
        .filter(
            leftover_record__donation_organization__isnull=True
        )
        .aggregate(
            total=Sum(
                'leftover_record__people_helped'
            )
        )['total'] or 0
    )

    people_helped = (
        direct_people_helped
        + approved_request_people_helped
    )

    # =========================================================
    # RECENT DONATIONS / FOOD RECEIVED
    #
    # IMPORTANT:
    #
    # A LeftoverRecord can contain:
    #
    #   2 direct donation
    #   +
    #   6 approved request
    #
    # quantity_used = 8
    #
    # But the dashboard must display:
    #
    #   2 Donated
    #   6 Received
    #
    # Therefore approved request quantities are removed from
    # quantity_used before displaying the direct donation.
    # =========================================================

    received_items = []

    # ---------------------------------------------------------
    # APPROVED REQUESTS
    # ---------------------------------------------------------

    for item in approved_requests:

        received_items.append({
            'food': item.leftover_record.food_item,
            'restaurant': item.leftover_record.restaurant,
            'quantity': item.quantity_requested,
            'unit': item.leftover_record.get_unit_display(),
            'date': item.requested_at,
            'type': 'REQUEST',
        })

    # ---------------------------------------------------------
    # DIRECT DONATIONS
    # ---------------------------------------------------------

    for item in direct_donations:

        approved_quantity = (
            FoodRequest.objects
            .filter(
                leftover_record=item,
                status='APPROVED'
            )
            .aggregate(
                total_quantity=Sum(
                    'quantity_requested'
                )
            )['total_quantity'] or 0
        )

        direct_donation_quantity = (
            item.quantity_used - approved_quantity
        )

        if direct_donation_quantity > 0:

            received_items.append({
                'food': item.food_item,
                'restaurant': item.restaurant,
                'quantity': direct_donation_quantity,
                'unit': item.get_unit_display(),
                'date': item.recorded_at,
                'type': 'DONATION',
            })

    # =========================================================
    # SORT RECENT ITEMS
    # =========================================================

    received_items.sort(
        key=lambda item: item['date'],
        reverse=True
    )

    # =========================================================
    # NOTIFICATIONS
    # =========================================================

    notifications_count = (
        FoodRequest.objects
        .filter(
            organization=organization
        )
        .count()
    )

    # =========================================================
    # RENDER
    # =========================================================

    return render(
        request,
        'wastage/organization_dashboard.html',
        {
            'organization': organization,

            'available_food': available_food,
            'available_food_list': available_food_list,

            'pending_requests': pending_requests,
            'pending_requests_list': pending_requests_list,
            'my_requests_list': my_requests_list,

            'food_received_count': food_received_count,
            'people_helped': people_helped,

            'received_items': received_items,

            'notifications_count': notifications_count,
        }
    )
    # =========================================================
    # NOTIFICATIONS
    # =========================================================

    notifications_count = (
        FoodRequest.objects
        .filter(
            organization=organization
        )
        .count()
    )

    return render(
        request,
        'wastage/organization_dashboard.html',
        {
            'organization': organization,

            'available_food': available_food,
            'available_food_list': available_food_list,

            'pending_requests': pending_requests,
            'pending_requests_list': pending_requests_list,
            'my_requests_list': my_requests_list,

            'food_received_count': food_received_count,
            'people_helped': people_helped,

            'received_items': received_items,

            'notifications_count': notifications_count,
        }
    )


# =============================================================
# ORGANIZATION MY REQUESTS
# =============================================================

@login_required
def my_requests(request):

    organization = FoodRescueOrganization.objects.filter(
        user=request.user
    ).first()

    if not organization:

        return redirect(
            'organization_login'
        )

    requests = (
        FoodRequest.objects
        .filter(
            organization=organization
        )
        .select_related(
            'leftover_record__food_item',
            'leftover_record__restaurant'
        )
        .order_by(
            '-requested_at'
        )
    )

    return render(
        request,
        'wastage/my_requests.html',
        {
            'organization': organization,
            'requests': requests,
        }
    )


# =============================================================
# ORGANIZATION FOOD RECEIVED
# =============================================================

@login_required
def food_received(request):

    organization = FoodRescueOrganization.objects.filter(
        user=request.user
    ).first()

    if not organization:

        return redirect(
            'organization_login'
        )

    # =========================================================
    # APPROVED REQUESTS
    # =========================================================

    approved_requests = (
        FoodRequest.objects
        .filter(
            organization=organization,
            status='APPROVED'
        )
        .select_related(
            'leftover_record__food_item',
            'leftover_record__restaurant'
        )
    )

    # =========================================================
    # DIRECT DONATIONS
    # =========================================================

    direct_donations = (
        LeftoverRecord.objects
        .filter(
            donation_organization=organization,
            action='DONATED',
            quantity_used__gt=0
        )
        .select_related(
            'food_item',
            'restaurant'
        )
        .order_by(
            '-recorded_at')
    )

    received_food = []

    # =========================================================
    # APPROVED REQUESTS
    # =========================================================

    for item in approved_requests:

        received_food.append(
            {
                'food': item.leftover_record.food_item,
                'restaurant': item.leftover_record.restaurant,
                'quantity': item.quantity_requested,
                'unit': item.leftover_record.get_unit_display(),
                'date': item.requested_at,
            }
        )

    # =========================================================
    # DIRECT DONATIONS
    # =========================================================

    for item in direct_donations:
        
        approved_quantity = (
            FoodRequest.objects
            .filter(
                leftover_record=item,
                status='APPROVED'
            )
            .aggregate(
                total_quantity=Sum('quantity_requested')
            )['total_quantity'] or 0
        )
        
        direct_donation_quantity = (item.quantity_used - approved_quantity)
        
        if direct_donation_quantity > 0:
            received_food.append(
                {
                    'food': item.food_item,
                    'restaurant': item.restaurant,
                    'quantity': direct_donation_quantity,
                    'unit': item.get_unit_display(),
                    'date': item.recorded_at,
                    'type': 'DONATION',
                }
            )

    received_food.sort(
        key=lambda item: item['date'],
        reverse=True
    )

    return render(
        request,
        'wastage/food_received.html',
        {
            'organization': organization,
            'received_food': received_food,
        }
    )


# =============================================================
# ORGANIZATION IMPACT
# =============================================================
@login_required
def organization_impact(request):

    organization = FoodRescueOrganization.objects.filter(
        user=request.user
    ).first()

    if not organization:
        return redirect('organization_login')

    # =========================================================
    # APPROVED REQUESTS
    # =========================================================

    approved_requests = (
        FoodRequest.objects
        .filter(
            organization=organization,
            status='APPROVED'
        )
        .select_related(
            'leftover_record__food_item',
            'leftover_record__restaurant'
        )
        .order_by('-requested_at')
    )

    # =========================================================
    # DIRECT DONATIONS
    # =========================================================

    direct_donations = (
        LeftoverRecord.objects
        .filter(
            donation_organization=organization,
            action='DONATED',
            quantity_used__gt=0
        )
        .select_related(
            'food_item',
            'restaurant'
        )
        .order_by('-recorded_at')
    )

    # =========================================================
    # ACTUAL DIRECT DONATION QUANTITIES
    #
    # A DONATED LeftoverRecord can contain both:
    #
    # Direct donation
    # +
    # Approved request
    #
    # Example:
    #
    # quantity_used = 8
    # approved request = 6
    #
    # Actual direct donation = 2
    # =========================================================

    direct_donation_data = []

    for item in direct_donations:

        approved_quantity = (
            FoodRequest.objects
            .filter(
                leftover_record=item,
                status='APPROVED'
            )
            .aggregate(
                total_quantity=Sum(
                    'quantity_requested'
                )
            )['total_quantity'] or 0
        )

        direct_donation_quantity = (
            item.quantity_used - approved_quantity
        )

        if direct_donation_quantity > 0:

            direct_donation_data.append({
                'item': item,
                'quantity': direct_donation_quantity,
            })

    # =========================================================
    # TOTAL FOOD RECEIVED
    #
    # One entry for each:
    # - Approved request
    # - Direct donation
    # =========================================================

    food_received_count = (
        approved_requests.count()
        + len(direct_donation_data)
    )

    # =========================================================
    # PEOPLE HELPED
    # =========================================================

    direct_people_helped = sum(
        item['item'].people_helped
        for item in direct_donation_data
    )

    approved_request_people_helped = (
        approved_requests
        .filter(
            leftover_record__donation_organization__isnull=True
        )
        .aggregate(
            total=Sum(
                'leftover_record__people_helped'
            )
        )['total'] or 0
    )

    people_helped = (
        direct_people_helped
        + approved_request_people_helped
    )

    # =========================================================
    # RESTAURANTS SUPPORTED
    #
    # Include restaurants from:
    # - approved requests
    # - direct donations
    # =========================================================

    restaurant_ids = set(
        approved_requests.values_list(
            'leftover_record__restaurant_id',
            flat=True
        )
    )

    restaurant_ids.update(
        item['item'].restaurant_id
        for item in direct_donation_data
    )

    restaurants_supported = len(
        restaurant_ids
    )

    # =========================================================
    # FOOD QUANTITY RECEIVED
    #
    # Include BOTH:
    #
    # Approved requests
    # +
    # Actual direct donations
    #
    # Example:
    #
    # 6 received
    # + 2 donated
    # = 8 pieces
    # =========================================================

    quantity_by_unit = {}

    # ---------------------------------------------------------
    # APPROVED REQUEST QUANTITIES
    # ---------------------------------------------------------

    for item in approved_requests:

        unit = item.leftover_record.unit

        quantity_by_unit[unit] = (
            quantity_by_unit.get(unit, 0)
            + item.quantity_requested
        )

    # ---------------------------------------------------------
    # DIRECT DONATION QUANTITIES
    # ---------------------------------------------------------

    for data in direct_donation_data:

        item = data['item']

        unit = item.unit

        quantity_by_unit[unit] = (
            quantity_by_unit.get(unit, 0)
            + data['quantity']
        )

    quantity_by_unit = [
        {
            'unit': unit,
            'total': total,
        }
        for unit, total in quantity_by_unit.items()
    ]

    quantity_by_unit.sort(
        key=lambda item: item['unit']
    )

    # =========================================================
    # RECENT FOOD RECEIVED
    #
    # Include BOTH:
    #
    # REQUEST:
    #     6 pieces → Received
    #
    # DONATION:
    #     2 pieces → Donated
    # =========================================================

    received_food = []

    # ---------------------------------------------------------
    # APPROVED REQUESTS
    # ---------------------------------------------------------

    for item in approved_requests:

        received_food.append({
            'food': item.leftover_record.food_item,
            'restaurant': item.leftover_record.restaurant,
            'quantity': item.quantity_requested,
            'unit': item.leftover_record.get_unit_display(),
            'date': item.requested_at,
            'type': 'REQUEST',
        })

    # ---------------------------------------------------------
    # DIRECT DONATIONS
    # ---------------------------------------------------------

    for data in direct_donation_data:

        item = data['item']

        received_food.append({
            'food': item.food_item,
            'restaurant': item.restaurant,
            'quantity': data['quantity'],
            'unit': item.get_unit_display(),
            'date': item.recorded_at,
            'type': 'DONATION',
        })

    # =========================================================
    # SORT RECENT FOOD
    # =========================================================

    received_food.sort(
        key=lambda item: item['date'],
        reverse=True
    )

    # =========================================================
    # RENDER
    # =========================================================

    return render(
        request,
        'wastage/organization_impact.html',
        {
            'organization': organization,

            'food_received_count':
                food_received_count,

            'people_helped':
                people_helped,

            'restaurants_supported':
                restaurants_supported,

            'quantity_by_unit':
                quantity_by_unit,

            'received_food':
                received_food,
        }
    )

# =============================================================
# ORGANIZATION PROFILE
# =============================================================


@login_required
def organization_profile(request):

    organization = FoodRescueOrganization.objects.filter(
        user=request.user
    ).first()

    if not organization:

        return redirect(
            'organization_login'
        )

    if request.method == 'POST':

        form = OrganizationProfileForm(
            request.POST,
            instance=organization
        )

        if form.is_valid():

            changed_fields = form.changed_data

            if changed_fields:

                organization = form.save(
                    commit=False
                )

                organization.save(
                    update_fields=changed_fields
                )

            return redirect(
                'organization_profile'
            )

    else:

        form = OrganizationProfileForm(
            instance=organization
        )

    return render(
        request,
        'wastage/organization_profile.html',
        {
            'organization': organization,
            'form': form,
        }
    )


# =============================================================
# ORGANIZATION NOTIFICATIONS
# =============================================================

@login_required
def organization_notifications(request):

    organization = FoodRescueOrganization.objects.filter(
        user=request.user
    ).first()

    if not organization:

        return redirect(
            'organization_login'
        )

    notifications = (
        FoodRequest.objects
        .filter(
            organization=organization
        )
        .select_related(
            'leftover_record__food_item',
            'leftover_record__restaurant'
        )
        .order_by(
            '-requested_at'
        )
    )

    return render(
        request,
        'wastage/organization_notifications.html',
        {
            'organization': organization,
            'notifications': notifications,
        }
    )


# =============================================================
# ORGANIZATION CHANGE PASSWORD
# =============================================================

@login_required
def organization_change_password(request):

    organization = FoodRescueOrganization.objects.filter(
        user=request.user
    ).first()

    if not organization:

        return redirect(
            'organization_login'
        )

    if request.method == 'POST':

        form = PasswordChangeForm(
            request.user,
            request.POST
        )

        if form.is_valid():

            user = form.save()

            update_session_auth_hash(
                request,
                user
            )

            return redirect(
                'organization_profile'
            )

    else:

        form = PasswordChangeForm(
            request.user
        )

    return render(
        request,
        'wastage/organization_change_password.html',
        {
            'organization': organization,
            'form': form,
        }
    )


# =============================================================
# BROWSE SURPLUS FOOD
#
# THIS PAGE SHOWS ONLY UNALLOCATED SURPLUS.
#
# Example:
#
# quantity = 10
# quantity_used = 6
#
# available_quantity = 4
# =============================================================

@login_required
def browse_surplus_food(request):

    organization = FoodRescueOrganization.objects.filter(
        user=request.user
    ).first()

    if not organization:
        return redirect(
            'organization_login'
        )

    # =========================================================
    # SELECT ONLY ONE DONATION RECORD PER DAILY FOOD RECORD
    #
    # This prevents the same food from appearing multiple times
    # when several LeftoverRecords belong to the same
    # DailyFoodRecord.
    # =========================================================

    latest_donation = (
        LeftoverRecord.objects
        .filter(
            daily_record=OuterRef('daily_record'),
            action='DONATED'
        )
        .order_by(
            '-recorded_at'
        )
        .values('id')[:1]
    )

    # =========================================================
    # AVAILABLE SURPLUS FOOD
    #
    # Available =
    #
    # quantity_prepared
    # - quantity_sold
    # - total quantity_used from ALL leftover records
    #
    # Example:
    #
    # Prepared = 100
    # Sold     = 30
    # Surplus  = 70
    # Used     = 67
    #
    # Available = 3
    # =========================================================

    available_food = (
        LeftoverRecord.objects

        # Only DONATED records can represent food available
        # for organizations.
        .filter(
            action='DONATED'
        )

        # Keep only ONE donation record for each
        # DailyFoodRecord.
        .filter(
            id=Subquery(
                latest_donation
            )
        )

        # =====================================================
        # ORIGINAL DAILY SURPLUS
        # =====================================================

        .annotate(
            total_surplus=ExpressionWrapper(
                F(
                    'daily_record__quantity_prepared'
                )
                -
                F(
                    'daily_record__quantity_sold'
                ),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )

        # =====================================================
        # TOTAL FOOD USED
        #
        # IMPORTANT:
        # This sums quantity_used from ALL LeftoverRecords
        # belonging to the same DailyFoodRecord.
        #
        # Therefore:
        #
        # DONATED
        # DISCOUNTED
        # STORED
        # STAFF
        # WASTED
        #
        # are all included.
        # =====================================================

        .annotate(
            total_used=Coalesce(
                Sum(
                    'daily_record__leftoverrecord__quantity_used'
                ),
                Value(0),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )

        # =====================================================
        # REMAINING AVAILABLE FOOD
        # =====================================================

        .annotate(
            available_quantity=ExpressionWrapper(
                F('total_surplus')
                -
                F('total_used'),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )

        # Only food that actually remains available.
        .filter(
            available_quantity__gt=0
        )

        .select_related(
            'food_item',
            'restaurant',
            'daily_record'
        )

        # IMPORTANT:
        # Sort using the actual food record date,
        # not the leftover creation date.
        .order_by(
            '-daily_record__date'
        )
    )

    return render(
        request,
        'wastage/browse_surplus_food.html',
        {
            'organization': organization,
            'available_food': available_food,
        }
    )
    
# =============================================================
# REQUEST FOOD
# =============================================================

@login_required
def request_food(request, leftover_id):

    organization = FoodRescueOrganization.objects.filter(
        user=request.user
    ).first()

    if not organization:

        return redirect(
            'organization_login'
        )

    leftover = get_object_or_404(
        LeftoverRecord,
        id=leftover_id,
        action='DONATED'
    )

    # =========================================================
    # ACTUAL CURRENT UNALLOCATED QUANTITY
    # =========================================================

    available_quantity = (
        leftover.quantity -
        leftover.quantity_used
    )

    # If nothing remains, do not allow a request.
    if available_quantity <= 0:

        return redirect(
            'browse_surplus_food'
        )

    if request.method == 'POST':

        quantity_requested = request.POST.get(
            'quantity_requested'
        )

        try:

            quantity_requested = float(
                quantity_requested
            )

            if quantity_requested <= 0:

                raise ValueError

            # -------------------------------------------------
            # CHECK CURRENT AVAILABLE QUANTITY
            # -------------------------------------------------

            if (
                quantity_requested >
                float(available_quantity)
            ):

                return render(
                    request,
                    'wastage/request_food.html',
                    {
                        'organization': organization,
                        'leftover': leftover,
                        'available_quantity': available_quantity,
                        'error':
                            'Requested quantity cannot be more than available quantity.'
                    }
                )

            # -------------------------------------------------
            # CREATE REQUEST
            #
            # IMPORTANT:
            # quantity_used is NOT changed here.
            #
            # It changes only after restaurant approval.
            # -------------------------------------------------

            FoodRequest.objects.create(
                organization=organization,
                leftover_record=leftover,
                quantity_requested=quantity_requested
            )

            return redirect(
                'organization_dashboard'
            )

        except (
            ValueError,
            TypeError
        ):

            return render(
                request,
                'wastage/request_food.html',
                {
                    'organization': organization,
                    'leftover': leftover,
                    'available_quantity': available_quantity,
                    'error':
                        'Please enter a valid quantity.'
                }
            )

    return render(
        request,
        'wastage/request_food.html',
        {
            'organization': organization,
            'leftover': leftover,
            'available_quantity': available_quantity,
        }
    )


# =============================================================
# RESTAURANT DASHBOARD
# =============================================================

@login_required
def dashboard(request):

    restaurant = request.user.restaurant

    now = timezone.now()

    current_month = now.month
    current_year = now.year
    current_month_name = now.strftime('%b')

    # =========================================================
    # MAIN DASHBOARD COUNTS
    # =========================================================

    surplus_count = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant
        )
        .count()
    )

    donation_count = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='DONATED'
        )
        .count()
    )

    # =========================================================
    # RECENT SURPLUS FOOD ACTIONS
    # =========================================================

    recent_surplus_records = list(
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant
        )
        .select_related(
            'food_item'
        )
        .order_by(
            '-recorded_at'
        )[:10]
    )

    # Approved organization food requests
    approved_requests = (
        FoodRequest.objects
        .filter(
            leftover_record__restaurant=restaurant,
            status='APPROVED'
        )
        .select_related(
            'leftover_record',
            'leftover_record__food_item'
        )
        .order_by(
            '-requested_at'
        )[:10]
    )

    # Convert approved requests into the same structure
    # used by the Recent Surplus Food Actions template.
    approved_request_items = []

    for food_request in approved_requests:
        approved_request_items.append(
            SimpleNamespace(
                food_item=food_request.leftover_record.food_item,

                action='DONATED',

                quantity=food_request.quantity_requested,

                quantity_used=food_request.quantity_requested,

                unit=food_request.leftover_record.unit,

                recorded_at=food_request.requested_at,

                get_unit_display=lambda unit=food_request.leftover_record.unit:
                    dict(LeftoverRecord.UNIT_CHOICES).get(
                        unit,
                        unit
                    )
            )
        )

    # Combine normal actions + approved organization donations
    recent_surplus = (
        recent_surplus_records +
        approved_request_items
    )

    # Most recent actions first
    recent_surplus.sort(
        key=lambda item: item.recorded_at,
        reverse=True
    )

    # Show only the latest 4
    recent_surplus = recent_surplus[:4]

    # =========================================================
    # RECENT DONATIONS
    # =========================================================

    recent_donations = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='DONATED'
        )
        .select_related(
            'food_item',
            'donation_organization'
        )
        .order_by(
           '-recorded_at'
        )[:4]
    )

    # =========================================================
    # DONATION GRAPH
    # =========================================================


    donation_data = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='DONATED',
            recorded_at__year=current_year,
            recorded_at__month=current_month
        )
        .values(
            'recorded_at__day'
        )
       .annotate(
           total=Count('id')
       )
       .order_by(
           'recorded_at__day'
       )
     )
    
    graph_days = 28

    donation_counts = [0] * graph_days

    for item in donation_data:

        day = item['recorded_at__day']

        if 1 <= day <= graph_days:

            donation_counts[day - 1] = (
                item['total']
            )

    highest_donation = (
        max(donation_counts)
        if donation_counts
        else 0
    )

    graph_y_max = max(
        5,
        ((highest_donation + 4) // 5) * 5
    )

    graph_y_labels = [
        graph_y_max,
        graph_y_max * 4 // 5,
        graph_y_max * 3 // 5,
        graph_y_max * 2 // 5,
        graph_y_max // 5,
        0
    ]

    graph_width = 700

    graph_top = 20
    graph_bottom = 155

    graph_height = (
        graph_bottom -
        graph_top
    )

    if graph_days > 1:

        donation_points = " ".join(

            f"{(index / (graph_days - 1)) * graph_width},"
            f"{graph_bottom - ((value / graph_y_max) * graph_height)}"

            for index, value in enumerate(
                donation_counts
            )
        )

    else:

        donation_points = (
            f"0,{graph_bottom}"
        )

    # =========================================================
    # CURRENT MONTH DONATION STATISTICS
    # =========================================================

    monthly_donations = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='DONATED',
            recorded_at__year=current_year,
            recorded_at__month=current_month
        )
    )

    monthly_donation_count = (
        monthly_donations.count()
    )

    monthly_people_helped = (
        monthly_donations
        .aggregate(
            total=Sum('people_helped')
        )['total'] or 0
    )

    monthly_staff_helped = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='STAFF',
            recorded_at__year=current_year,
            recorded_at__month=current_month
        )
        .aggregate(
            total=Sum('people_helped')
        )['total'] or 0
    )

    # =========================================================
    # PEOPLE HELPED
    # =========================================================

    needy_people_helped = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='DONATED'
        )
        .aggregate(
            total=Sum('people_helped')
        )['total'] or 0
    )

    staff_people_helped = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='STAFF'
        )
        .aggregate(
            total=Sum('people_helped')
        )['total'] or 0
    )

    # =========================================================
    # SURPLUS QUANTITY
    # =========================================================

    surplus_data = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant
        )
        .values(
            'unit'
        )
        .annotate(
            total=Sum('quantity')
        )
    )

    surplus_by_unit = {
        item['unit']: item['total']
        for item in surplus_data
    }

    # =========================================================
    # FOOD RESCUED
    # =========================================================

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
        .values(
            'unit'
        )
        .annotate(
            total=Sum('quantity_used')
        )
    )

    rescued_by_unit = {
        item['unit']: item['total']
        for item in rescued_data
    }

    # =========================================================
    # WASTED FOOD
    # =========================================================

    wasted_data = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='WASTED'
        )
        .values(
            'unit'
        )
        .annotate(
            total=Sum('quantity_used')
        )
    )

    wasted_by_unit = {
        item['unit']: item['total']
        for item in wasted_data
    }

    # =========================================================
    # WASTE REDUCTION
    # =========================================================

    reduction_by_unit = {}

    for unit, surplus in surplus_by_unit.items():

        rescued = rescued_by_unit.get(
            unit,
            0
        )

        reduction_by_unit[unit] = (
            (rescued / surplus) * 100
            if surplus > 0
            else 0
        )

    # =========================================================
    # NOTIFICATIONS
    # =========================================================

    notification_requests = (
        FoodRequest.objects
        .filter(
            leftover_record__restaurant=restaurant,
            status='PENDING'
        )
        .select_related(
            'organization',
            'leftover_record',
            'leftover_record__food_item'
        )
        .order_by(
            '-requested_at'
        )[:5]
    )

    notification_count = (
        FoodRequest.objects
        .filter(
            leftover_record__restaurant=restaurant,
            status='PENDING'
        )
        .count()
    )

    return render(
        request,
        'wastage/dashboard.html',
        {
            'restaurant': restaurant,

            'surplus_count': surplus_count,

            'donation_count': donation_count,

            'needy_people_helped': needy_people_helped,

            'rescued_by_unit': rescued_by_unit,

            'recent_surplus': recent_surplus,

            'recent_donations': recent_donations,

            'donation_data': donation_data,

            'current_month_name': current_month_name,

            'donation_counts': donation_counts,

            'donation_points': donation_points,

            'graph_y_max': graph_y_max,

            'graph_y_labels': graph_y_labels,

            'monthly_donation_count':
                monthly_donation_count,

            'monthly_people_helped':
                monthly_people_helped,

            'monthly_staff_helped':
                monthly_staff_helped,

            'staff_people_helped':
                staff_people_helped,

            'surplus_by_unit':
                surplus_by_unit,

            'wasted_by_unit':
                wasted_by_unit,

            'reduction_by_unit':
                reduction_by_unit,

            'notification_requests':
                notification_requests,

            'notification_count':
                notification_count,
        }
    )


# =============================================================
# ADD SURPLUS
# =============================================================

@login_required
def add_surplus(request):

    restaurant = request.user.restaurant

    if request.method == 'POST':

        form = LeftoverRecordForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():

            food_item = form.cleaned_data[
                'food_item'
            ]

            daily_record = form.cleaned_data[
                'daily_record'
            ]

            quantity = form.cleaned_data[
                'quantity'
            ]

            unit = form.cleaned_data[
                'unit'
            ]

            action = form.cleaned_data[
                'action'
            ]

            # =================================================
            # FOOD REMAINING AFTER SALES
            # =================================================

            remaining_food = (
                daily_record.quantity_prepared -
                daily_record.quantity_sold
            )

            # =================================================
            # SURPLUS ALREADY ALLOCATED / USED
            # =================================================

            used_quantity = (
                LeftoverRecord.objects
                .filter(
                    daily_record=daily_record
                )
                .aggregate(
                    total=Sum('quantity_used')
                )['total'] or 0
            )

            # =================================================
            # CURRENT UNALLOCATED SURPLUS
            # =================================================

            unallocated_quantity = (
                remaining_food -
                used_quantity
            )

            # =================================================
            # CHECK REQUESTED QUANTITY
            # =================================================

            if quantity > unallocated_quantity:

                form.add_error(
                    'quantity',
                    f'Only {unallocated_quantity} '
                    f'{unit} of surplus food is available.'
                )

            else:

                leftover = form.save(
                    commit=False
                )

                leftover.restaurant = restaurant

                # =================================================
                # IMPORTANT
                #
                # For DONATED food:
                #
                # quantity = TOTAL surplus pool
                # quantity_used = amount actually donated
                #
                # Example:
                #
                # Remaining surplus = 10 KG
                # User wants to donate = 6 KG
                #
                # Store:
                # quantity = 10
                # quantity_used = 0
                #
                # Donation view then changes:
                # quantity_used = 6
                #
                # Remaining = 10 - 6 = 4 KG
                # =================================================

                if action == 'DONATED':

                    leftover.quantity = (
                        unallocated_quantity
                    )

                else:

                    leftover.quantity = quantity

                # Nothing has been used yet.
                leftover.quantity_used = 0

                leftover.save()

                # =================================================
                # REDIRECT ACCORDING TO ACTION
                # =================================================

                if leftover.action == 'DISCOUNTED':

                    return redirect(
                        'discounted_sale'
                    )

                elif leftover.action == 'STORED':

                    return redirect(
                        'storage_record'
                    )

                elif leftover.action == 'DONATED':

                    return redirect(
                        'donation',
                        leftover_id=leftover.id
                    )

                elif leftover.action == 'STAFF':

                    return redirect(
                        'share_food'
                    )

                elif leftover.action == 'WASTED':

                    return redirect(
                        'waste_food'
                    )

                return redirect(
                    'dashboard'
                )

    else:

        form = LeftoverRecordForm(
            restaurant=restaurant
        )

    return render(
        request,
        'wastage/add_surplus.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )

# =============================================================
# TRACK FOOD
# =============================================================


@login_required
def track_food(request):

    restaurant = request.user.restaurant

    if request.method == 'POST':

        form = DailyFoodRecordForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():

            record = form.save(
                commit=False
            )

            record.restaurant = restaurant

            record.save()

            return redirect(
                'dashboard'
            )

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


# =============================================================
# FOOD RECORDS
# =============================================================

@login_required
def food_records(request):

    restaurant = request.user.restaurant

    records = (
        DailyFoodRecord.objects
        .filter(
            restaurant=restaurant
        )
        .select_related(
            'food_item'
        )
        .annotate(
            remaining=ExpressionWrapper(
                F('quantity_prepared') -
                F('quantity_sold'),
                output_field=IntegerField()
            ),

            surplus_used=Coalesce(
                Sum(
                    'leftoverrecord__quantity_used'
                ),
                Value(0),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )
        .annotate(
            unallocated_surplus=ExpressionWrapper(
                F('remaining') -
                F('surplus_used'),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )
        .order_by(
            '-date'
        )
    )

    return render(
        request,
        'wastage/food_records.html',
        {
            'restaurant': restaurant,
            'records': records,
        }
    )


# =============================================================
# ADD FOOD ITEM
# =============================================================

@login_required
def add_food_item(request):

    restaurant = request.user.restaurant

    if request.method == 'POST':

        form = FoodItemForm(
            request.POST
        )

        if form.is_valid():

            food_item = form.save(
                commit=False
            )

            food_item.restaurant = restaurant

            food_item.save()

            return redirect(
                'track_food'
            )

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


# =============================================================
# DISCOUNTED SALE
# =============================================================

@login_required
def discounted_sale(request):

    restaurant = request.user.restaurant

    if request.method == 'POST':

        form = DiscountedSaleForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():

            sale = form.save(
                commit=False
            )

            if (
                sale.leftover_record.restaurant
                != restaurant
            ):

                form.add_error(
                    'leftover_record',
                    'You can only sell your own restaurant food.'
                )

            else:

                sale.save()

                leftover = (
                    sale.leftover_record
                )

                leftover.quantity_used += (
                    sale.quantity_sold
                )

                leftover.save(
                    update_fields=[
                        'quantity_used'
                    ]
                )

                return redirect(
                    'dashboard'
                )

    else:

        form = DiscountedSaleForm(
            restaurant=restaurant
        )

    return render(
        request,
        'wastage/discounted_sale.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )


# =============================================================
# STORAGE RECORD
# =============================================================

@login_required
def storage_record(request):

    restaurant = request.user.restaurant

    if request.method == 'POST':

        form = StorageRecordForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():

            storage = form.save(
                commit=False
            )

            if (
                storage.leftover_record.restaurant
                != restaurant
            ):

                form.add_error(
                    'leftover_record',
                    'You can only store your own restaurant food.'
                )

            else:

                storage.save()

                leftover = (
                    storage.leftover_record
                )

                leftover.quantity_used += (
                    storage.quantity_stored
                )

                leftover.save(
                    update_fields=[
                        'quantity_used'
                    ]
                )

                return redirect(
                    'dashboard'
                )

    else:

        form = StorageRecordForm(
            restaurant=restaurant
        )

    return render(
        request,
        'wastage/storage_record.html',
        {
            'form': form,
            'restaurant': restaurant,
        }
    )


# =============================================================
# DONATION
#
# IMPORTANT:
#
# quantity = total surplus allocated to this donation record
#
# quantity_donated = amount actually donated now
#
# Example:
#
# quantity = 10
# quantity_used = 0
#
# donate 6
#
# quantity_used = 6
#
# remaining = 4
# =============================================================

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

            quantity_donated = (
                form.cleaned_data[
                    'quantity_donated'
                ]
            )

            donation_organization = (
                form.cleaned_data[
                    'donation_organization'
                ]
            )

            people_helped = (
                form.cleaned_data[
                    'people_helped'
                ]
            )

            # =================================================
            # CURRENT AVAILABLE QUANTITY
            # =================================================

            available_quantity = (
                leftover.quantity -
                leftover.quantity_used
            )

            # =================================================
            # FINAL SERVER-SIDE CHECK
            # =================================================

            if quantity_donated > available_quantity:

                form.add_error(
                    'quantity_donated',
                    f'Only {available_quantity} '
                    f'{leftover.get_unit_display()} '
                    f'is available for donation.'
                )

            else:

                leftover.donation_organization = (
                    donation_organization
                )

                leftover.people_helped = (
                    people_helped
                )

                # IMPORTANT:
                # Increment only by the quantity actually donated.
                leftover.quantity_used += (
                    quantity_donated
                )

                leftover.save(
                    update_fields=[
                        'donation_organization',
                        'people_helped',
                        'quantity_used',
                    ]
                )

                return redirect(
                    'dashboard'
                )

    else:

        form = DonationForm(
            restaurant=restaurant,
            leftover=leftover
        )

    available_quantity = (
        leftover.quantity -
        leftover.quantity_used
    )

    return render(
        request,
        'wastage/donation.html',
        {
            'form': form,
            'restaurant': restaurant,
            'leftover': leftover,
            'available_quantity': available_quantity,
        }
    )


# =============================================================
# SHARE FOOD WITH STAFF
# =============================================================

@login_required
def share_food(request):

    restaurant = request.user.restaurant

    if request.method == 'POST':

        form = ShareForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():

            leftover = form.cleaned_data[
                'leftover_record'
            ]

            leftover.people_helped = (
                form.cleaned_data[
                    'people_helped'
                ]
            )

            leftover.quantity_used = (
                leftover.quantity
            )

            leftover.save()

            return redirect(
                'dashboard'
            )

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


# =============================================================
# WASTE FOOD
# =============================================================

@login_required
def waste_food(request):

    restaurant = request.user.restaurant

    if request.method == 'POST':

        form = WasteForm(
            request.POST,
            restaurant=restaurant
        )

        if form.is_valid():

            leftover = form.cleaned_data[
                'leftover_record'
            ]

            leftover.waste_reason = (
                form.cleaned_data[
                    'waste_reason'
                ]
            )

            leftover.quantity_used = (
                leftover.quantity
            )

            leftover.save()

            return redirect(
                'dashboard'
            )

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


# =============================================================
# DONATIONS
# =============================================================

@login_required
def donations(request):

    restaurant = request.user.restaurant

    donations = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='DONATED'
        )
        .select_related(
            'food_item',
            'donation_organization'
        )
        .order_by(
            '-recorded_at'
        )
    )

    return render(
        request,
        'wastage/donations.html',
        {
            'restaurant': restaurant,
            'donations': donations,
        }
    )


# =============================================================
# RESTAURANT PROFILE
# =============================================================

@login_required
def profile(request):

    restaurant = request.user.restaurant

    return render(
        request,
        'wastage/profile.html',
        {
            'restaurant': restaurant,
        }
    )


# =============================================================
# RESTAURANT IMPACT
# =============================================================

@login_required
def impact(request):

    restaurant = request.user.restaurant


    # =====================================================
    # FOOD SURPLUS
    # Actual leftover = quantity prepared - quantity sold
    # =====================================================

    surplus_by_unit = {}

    daily_records = (
        DailyFoodRecord.objects
        .filter(
            restaurant=restaurant
        )
        .select_related('food_item')
    )

    for daily_record in daily_records:

        surplus = (
            daily_record.quantity_prepared
            - daily_record.quantity_sold
        )

        if surplus <= 0:
            continue

        # Get the unit used for this surplus food
        leftover = (
            LeftoverRecord.objects
            .filter(
                restaurant=restaurant,
                daily_record=daily_record
            )
            .order_by('recorded_at')
            .first()
        )

        if not leftover:
            continue

        unit = leftover.unit

        surplus_by_unit[unit] = (
            surplus_by_unit.get(unit, 0)
            + surplus
        )


    # =====================================================
    # FOOD RESCUED
    #
    # Only food actually handled through:
    # DISCOUNTED
    # DONATED
    # STORED
    # STAFF
    #
    # WASTED is deliberately excluded.
    # =====================================================

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
        .values(
            'unit'
        )
        .annotate(
            total=Sum('quantity_used')
        )
    )

    rescued_by_unit = {
        item['unit']: item['total']
        for item in rescued_data
    }


    # =====================================================
    # FOOD WASTED
    # =====================================================

    wasted_data = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant,
            action='WASTED'
        )
        .values(
            'unit'
        )
        .annotate(
            total=Sum('quantity')
        )
    )

    wasted_by_unit = {
        item['unit']: item['total']
        for item in wasted_data
    }


    # =====================================================
    # WASTE REDUCTION
    # Rescued / Surplus × 100
    # =====================================================

    reduction_by_unit = {}

    for unit, surplus in surplus_by_unit.items():

        rescued = rescued_by_unit.get(
            unit,
            0
        )

        reduction_by_unit[unit] = (
            (rescued / surplus) * 100
            if surplus > 0
            else 0
        )


    # =====================================================
    # PEOPLE HELPED
    # =====================================================

    needy_people_helped = sum(
        donation.people_helped
        for donation in (
            LeftoverRecord.objects
            .filter(
                restaurant=restaurant,
                action='DONATED'
            )
        )
    )


    # =====================================================
    # STAFF HELPED
    # =====================================================

    staff_people_helped = sum(
        staff.people_helped
        for staff in (
            LeftoverRecord.objects
            .filter(
                restaurant=restaurant,
                action='STAFF'
            )
        )
    )


    return render(
        request,
        'wastage/impact.html',
        {
            'restaurant': restaurant,
            'surplus_by_unit': surplus_by_unit,
            'rescued_by_unit': rescued_by_unit,
            'wasted_by_unit': wasted_by_unit,
            'reduction_by_unit': reduction_by_unit,
            'needy_people_helped': needy_people_helped,
            'staff_people_helped': staff_people_helped,
        }
    )


# =============================================================
# HISTORY
# =============================================================

@login_required
def history(request):

    restaurant = request.user.restaurant

    records = (
        LeftoverRecord.objects
        .filter(
            restaurant=restaurant
        )
        .select_related(
            'food_item',
            'daily_record',
            'donation_organization'
        )
        .prefetch_related(
            'discountedsale_set',
            'storagerecord_set'
        )
        .order_by(
            '-recorded_at'
        )
    )

    approved_requests = (
        FoodRequest.objects
        .filter(
            leftover_record__restaurant=restaurant,
            status='APPROVED'
        )
        .select_related(
            'organization',
            'leftover_record',
            'leftover_record__food_item'
        )
        .order_by(
            '-requested_at'
        )
    )

    return render(
        request,
        'wastage/history.html',
        {
            'restaurant': restaurant,
            'records': records,
            'approved_requests': approved_requests,
        }
    )

# =============================================================
# RESTAURANT FOOD REQUESTS
# =============================================================
@login_required
def restaurant_food_requests(request):

    restaurant = Restaurant.objects.filter(
        user=request.user
    ).first()

    food_requests = (
        FoodRequest.objects
        .filter(
            leftover_record__restaurant=restaurant
        )
        .select_related(
            'organization',
            'leftover_record',
            'leftover_record__food_item',
            'leftover_record__daily_record'
        )
        .annotate(
            total_surplus=ExpressionWrapper(
                F('leftover_record__daily_record__quantity_prepared')
                - F('leftover_record__daily_record__quantity_sold'),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )
        .annotate(
            total_used=Coalesce(
                Sum(
                    'leftover_record__daily_record__leftoverrecord__quantity_used'
                ),
                Value(0),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )
        .annotate(
            available_food=ExpressionWrapper(
                F('total_surplus') - F('total_used'),
                output_field=DecimalField(
                    max_digits=8,
                    decimal_places=2
                )
            )
        )
        .order_by(
            '-requested_at'
        )
    )

    return render(
        request,
        'wastage/restaurant_food_requests.html',
        {
            'restaurant': restaurant,
            'food_requests': food_requests,
        }
    )

# =============================================================
# APPROVE FOOD REQUEST
#
# IMPORTANT:
# Use quantity_used directly.
#
# This prevents approving a request on food that was already
# directly donated.
# =============================================================

@login_required
def approve_food_request(request, request_id):

    restaurant = Restaurant.objects.filter(
        user=request.user
    ).first()

    food_request = get_object_or_404(
        FoodRequest,
        id=request_id,
        leftover_record__restaurant=restaurant
    )

    if request.method == 'POST':

        if food_request.status != 'PENDING':

            return redirect(
                'restaurant_food_requests'
            )

        leftover = (
            food_request.leftover_record
        )

        # =====================================================
        # ACTUAL CURRENT AVAILABLE QUANTITY
        # =====================================================

        available_quantity = (
            leftover.quantity -
            leftover.quantity_used
        )

        # =====================================================
        # CHECK REQUEST
        # =====================================================

        if (
            food_request.quantity_requested >
            available_quantity
        ):

            return redirect(
                'restaurant_food_requests'
            )

        # =====================================================
        # APPROVE
        # =====================================================

        food_request.status = 'APPROVED'

        food_request.save(
            update_fields=[
                'status'
            ]
        )

        # =====================================================
        # CONSUME REQUESTED QUANTITY
        # =====================================================

        leftover.quantity_used += (
            food_request.quantity_requested
        )

        leftover.save(
            update_fields=[
                'quantity_used'
            ]
        )

    return redirect(
        'restaurant_food_requests'
    )


# =============================================================
# REJECT FOOD REQUEST
# =============================================================

@login_required
def reject_food_request(request, request_id):

    restaurant = Restaurant.objects.filter(
        user=request.user
    ).first()

    food_request = get_object_or_404(
        FoodRequest,
        id=request_id,
        leftover_record__restaurant=restaurant
    )

    if request.method == 'POST':

        if food_request.status == 'PENDING':

            food_request.status = 'REJECTED'

            food_request.save(
                update_fields=[
                    'status'
                ]
            )

    return redirect(
        'restaurant_food_requests'
    )


# =============================================================
# RESTAURANT LOGOUT
# =============================================================

def logout(request):

    auth_logout(
        request
    )

    return redirect(
        'home'
    )


# =============================================================
# ORGANIZATION LOGOUT
# =============================================================

def organization_logout(request):

    auth_logout(
        request
    )

    return redirect(
        'organization_home'
    )


# =============================================================
# EDIT RESTAURANT PROFILE
# =============================================================

@login_required
def edit_profile(request):

    restaurant = request.user.restaurant

    if request.method == 'POST':

        form = RestaurantProfileForm(
            request.POST,
            instance=restaurant
        )

        if form.is_valid():

            form.save()

            return redirect(
                'profile'
            )

    else:

        form = RestaurantProfileForm(
            instance=restaurant
        )

    return render(
        request,
        'wastage/edit_profile.html',
        {
            'restaurant': restaurant,
            'form': form,
        }
    )


# =============================================================
# RESTAURANT CHANGE PASSWORD
# =============================================================

@login_required
def restaurant_change_password(request):

    restaurant = request.user.restaurant

    if request.method == 'POST':

        form = PasswordChangeForm(
            request.user,
            request.POST
        )

        if form.is_valid():

            user = form.save()

            update_session_auth_hash(
                request,
                user
            )

            return redirect(
                'profile'
            )

    else:

        form = PasswordChangeForm(
            request.user
        )

    return render(
        request,
        'wastage/restaurant_change_password.html',
        {
            'restaurant': restaurant,
            'form': form,
        }
    )
