from django.contrib.auth import views as auth_views
from django.urls import path
from .views import LoginViewWithSuccessMsg

urlpatterns = [
    path('login/', LoginViewWithSuccessMsg.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        template_name='accounts/logged_out.html'
    ), name='logout'),
]