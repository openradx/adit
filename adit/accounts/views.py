from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin
from django.views.generic import DetailView
from django.views.generic.edit import CreateView

from adit.core.utils.permission_utils import is_staff_user

from .forms import RegistrationForm
from .models import User


class UserProfileView(LoginRequiredMixin, AccessMixin, DetailView):
    model = User
    template_name = "accounts/user_profile.html"

    def dispatch(self, request, *args, **kwargs):
        """Only staff and the user himself has access."""
        check_access = True
        if is_staff_user(self.request.user):
            check_access = False
        if check_access and request.user.pk != kwargs["pk"]:
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)


class RegistrationView(CreateView):
    model = User
    form_class = RegistrationForm
    template_name = "accounts/registration.html"

    def form_valid(self, form):
        form.instance.is_active = False
        return super().form_valid(form)
