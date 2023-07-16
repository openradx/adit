from functools import reduce

from django.contrib.auth.mixins import AccessMixin
from django.views.generic import DetailView, ListView

from radis.core.forms import PageSizeSelectForm
from radis.core.utils.permission_utils import is_staff_user, is_superuser
from radis.core.utils.type_utils import with_type_hint


def deepgetattr(obj: object, attr: str):
    """Recurses through an attribute chain to get the ultimate value."""
    return reduce(getattr, attr.split("."), obj)


class OwnerRequiredMixin(AccessMixin, with_type_hint(DetailView)):
    """
    Verify that the user is the owner of the object. By default
    also superusers and staff may access the object.
    Should be added to a view class after LoginRequiredMixin.
    """

    allow_superuser_access = True
    allow_staff_access = True
    owner_accessor = "owner"

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()

        check_owner = True
        if (
            self.allow_superuser_access
            and is_superuser(request.user)
            or self.allow_staff_access
            and is_staff_user(request.user)
        ):
            check_owner = False

        if check_owner and request.user != deepgetattr(obj, self.owner_accessor):
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)


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
