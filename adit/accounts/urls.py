from django.contrib.auth import views as auth_views
from django.urls import path, include
from . import views

urlpatterns = [
    path('', include('registration.backends.admin_approval.urls')),
    path('<int:pk>/', views.UserProfileView.as_view(), name='user_profile')
]