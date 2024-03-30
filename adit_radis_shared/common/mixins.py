from typing import Any, Protocol

from django.core.exceptions import SuspiciousOperation
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.views.generic import TemplateView
from django_filters.filterset import FilterSet
from django_filters.views import FilterMixin

from .forms import PageSizeSelectForm
from .models import AppSettings
from .types import HtmxHttpRequest
from .utils.auth_utils import is_logged_in_user


class ViewProtocol(Protocol):
    request: HttpRequest

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        ...

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        ...

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ...


class LockedMixinProtocol(ViewProtocol, Protocol):
    settings_model: type[AppSettings]
    section_name: str


class LockedMixin:
    def dispatch(
        self: LockedMixinProtocol, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        settings = self.settings_model.get()
        assert settings

        if settings.locked and not (is_logged_in_user(request.user) and request.user.is_superuser):
            if request.method != "GET":
                raise SuspiciousOperation()

            return TemplateView.as_view(
                template_name="common/section_locked.html",
                extra_context={"section_name": self.section_name},
            )(request)

        return super().dispatch(request, *args, **kwargs)


class HtmxOnlyMixin:
    def dispatch(
        self: ViewProtocol, request: HtmxHttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        if not request.htmx:
            raise SuspiciousOperation()
        return super().dispatch(request, *args, **kwargs)


class RelatedFilterMixinProtocol(ViewProtocol, Protocol):
    filterset: FilterSet
    object_list: QuerySet

    def get_strict(self) -> bool:
        ...

    def get_filterset_class(self) -> type[FilterSet]:
        ...

    def get_filterset(self, filterset_class: type[FilterSet]) -> FilterSet:
        ...


class RelatedFilterMixin(FilterMixin):
    """A mixin that provides a way to show and handle a FilterSet in a request.

    The advantage is provided over FilterMixin is that it does use a special
    get_filter_queryset() method to get its data from and not get_queryset()
    like its parent so that it can be used in a DetailView to filter a related
    model field.
    django_tables2 automatically uses the set self.object_list attribute.
    It must be placed behind SingleTableMixin.
    """

    request: HttpRequest

    def get_filter_queryset(self):
        raise NotImplementedError("Must be implemented by the derived view.")

    def get_filterset_kwargs(self, _):
        kwargs = {
            "data": self.request.GET or None,
            "request": self.request,
            "queryset": self.get_filter_queryset(),
        }
        return kwargs

    def get_context_data(self: RelatedFilterMixinProtocol, **kwargs):
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


class PageSizeSelectMixinProtocol(ViewProtocol, Protocol):
    paginate_by: int
    page_sizes: list[int]


class PageSizeSelectMixin:
    """A mixin to show a page size selector."""

    def get(
        self: PageSizeSelectMixinProtocol, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        # Make the initial paginate_by attribute the default page size if set
        if not hasattr(self, "paginate_by") or self.paginate_by is None:
            self.paginate_by = 50

        try:
            per_page = int(request.GET.get("per_page", self.paginate_by))
        except ValueError:
            per_page = self.paginate_by

        per_page = min(per_page, 100)
        self.paginate_by = per_page  # used by MultipleObjectMixin and django-tables2

        return super().get(request, *args, **kwargs)

    def get_context_data(self: PageSizeSelectMixinProtocol, **kwargs):
        context = super().get_context_data(**kwargs)

        if not hasattr(self, "page_sizes") or self.page_sizes is None:
            self.page_sizes = [50, 100, 250, 500]
        context["page_size_select"] = PageSizeSelectForm(self.request.GET, self.page_sizes)

        return context
