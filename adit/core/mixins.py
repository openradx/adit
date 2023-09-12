from functools import reduce
from typing import Any

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import SuspiciousOperation
from django.http import HttpRequest, HttpResponse
from django.views import View

# from django.forms.formsets import ORDERING_FIELD_NAME
from django.views.generic import DetailView, ListView, TemplateView
from django_filters.views import FilterMixin

from .forms import PageSizeSelectForm
from .models import AppSettings
from .types import AuthenticatedHttpRequest
from .utils.auth_utils import is_logged_in_user
from .utils.type_utils import with_type_hint


def deepgetattr(obj: object, attr: str):
    """Recurses through an attribute chain to get the ultimate value."""
    return reduce(getattr, attr.split("."), obj)


class LockedMixin(with_type_hint(View)):
    settings_model: type[AppSettings]
    section_name = "Section"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        settings = self.settings_model.get()
        assert settings

        if settings.locked and not (is_logged_in_user(request.user) and request.user.is_superuser):
            if request.method != "GET":
                raise SuspiciousOperation()

            return TemplateView.as_view(
                template_name="core/section_locked.html",
                extra_context={"section_name": self.section_name},
            )(request)

        return super().dispatch(request, *args, **kwargs)


class OwnerRequiredMixin(AccessMixin, with_type_hint(DetailView)):
    """
    Verify that the user is the owner of the object. By default
    also superusers and staff may access the object.
    Should be added to a view class after LoginRequiredMixin.
    """

    allow_superuser_access = True
    allow_staff_access = True
    owner_accessor = "owner"

    def dispatch(self, request: AuthenticatedHttpRequest, *args, **kwargs):
        obj = self.get_object()

        user = request.user
        if not user.is_authenticated:
            raise AssertionError("The user must be authenticated to check if he is the owner.")

        check_owner = True
        if (
            self.allow_superuser_access
            and user.is_superuser
            or self.allow_staff_access
            and user.is_staff
        ):
            check_owner = False

        if check_owner and user != deepgetattr(obj, self.owner_accessor):
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)


class RelatedFilterMixin(FilterMixin, with_type_hint(ListView)):
    """A mixin that provides a way to show and handle a FilterSet in a request.

    The advantage is provided over FilterMixin is that it does use a special
    get_filter_queryset() method to get its data from and not get_queryset()
    like its parent so that it can be used in a DetailView to filter a related
    model field.
    django_tables2 automatically uses the set self.object_list attribute.
    It must be placed behind SingleTableMixin.
    """

    def get_filter_queryset(self):
        raise NotImplementedError("Must be implemented by the derived view.")

    def get_filterset_kwargs(self, _):
        kwargs = {
            "data": self.request.GET or None,
            "request": self.request,
            "queryset": self.get_filter_queryset(),
        }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)

        if not self.filterset.is_bound or self.filterset.is_valid() or not self.get_strict():
            # object_list is consumed by SingleTableMixin of django_tables2
            self.object_list = self.filterset.qs
        else:
            self.object_list = self.filterset.queryset.none()

        context["filter"] = self.filterset
        context["object_list"] = self.object_list
        return context


class PageSizeSelectMixin(with_type_hint(ListView)):
    """A mixin to show a page size selector.

    Must be placed after the SingleTableMixin as it sets self.paginated_by
    which is used by this mixin for the page size.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            per_page = int(self.request.GET.get("per_page", 50))
        except ValueError:
            per_page = 50

        per_page = min(per_page, 1000)
        self.paginate_by = per_page  # Used by django_tables2

        context["page_size_select"] = PageSizeSelectForm(self.request.GET, [50, 100, 250, 500])
        return context
