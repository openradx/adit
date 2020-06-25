from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class MyUserAdmin(UserAdmin):
    ordering = ('date_joined',)
    list_display = ('username', 'email', 'date_joined', 'first_name', 'last_name', 'is_staff')

admin.site.register(User, MyUserAdmin)