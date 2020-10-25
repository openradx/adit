from django.contrib.auth.mixins import AccessMixin
from django_filters.views import FilterMixin
from adit.main.forms import PageSizeSelectForm


class OwnerRequiredMixin(AccessMixin):
    """
    Verify that the user is the owner of the object. By default
    also superusers and staff may access the object.
    Should be added to a view class after LoginRequiredMixin.
    """

    allow_superuser_access = True
    allow_staff_access = True
    owner_accessor = "user"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        check_owner = True
        if (
            self.allow_superuser_access
            and request.user.is_superuser
            or self.allow_staff_access
            and request.user.is_staff
        ):
            check_owner = False

        if check_owner and request.user != getattr(self.object, self.owner_accessor):
            self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)


class RelatedFilterMixin(FilterMixin):
    """A mixin that provides a way to show and handle a FilterSet in a request.

    The advantage is provided over FilterMixin is that it does use a special
    get_filter_queryset() method to get its data from and not get_queryset()
    like its parent so that it can be used a DetailView to filter a related
    field in table.
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

        if (
            not self.filterset.is_bound
            or self.filterset.is_valid()
            or not self.get_strict()
        ):
            self.object_list = self.filterset.qs
        else:
            self.object_list = self.filterset.queryset.none()

        context["filter"] = self.filterset
        context["object_list"] = self.object_list
        return context


class PageSizeSelectMixin:  # pylint: disable=too-few-public-methods
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
        if per_page > 1000:
            per_page = 1000
        self.paginate_by = per_page  # Used by django_tables2

        context["page_size_select"] = PageSizeSelectForm(
            self.request.GET, [50, 100, 250, 500]
        )
        return context
