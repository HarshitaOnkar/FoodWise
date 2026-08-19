"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from wastage import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('add_surplus/',views.add_surplus, name='add_surplus'),
    path('track-food/', views.track_food, name='track_food'),
    path('food-records/', views.food_records, name='food_records'),
    path('add-food-item/', views.add_food_item, name='add_food_item'),
    path('discounted-sale/', views.discounted_sale, name='discounted_sale'),
    path('storage-record/', views.storage_record, name='storage_record'),
    path('donation/<int:leftover_id>/', views.donation, name='donation'),
    path('share-food/', views.share_food, name='share_food'),
    path('waste-food/', views.waste_food, name='waste_food'),
]
