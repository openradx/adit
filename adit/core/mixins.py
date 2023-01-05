import re
from functools import reduce
from django.contrib.auth.mixins import AccessMixin
from django.forms.formsets import ORDERING_FIELD_NAME
from django_filters.views import FilterMixin
from adit.core.forms import PageSizeSelectForm


class OwnerRequiredMixin(AccessMixin):
    """
    Verify that the user is the owner of the object. By default
    also superusers and staff may access the object.
    Should be added to a view class after LoginRequiredMixin.
    """

    allow_superuser_access = True
    allow_staff_access = True
    owner_accessor = "owner"

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

        if check_owner and request.user != deepgetattr(self.object, self.owner_accessor):
            self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)


def deepgetattr(obj, attr):
    """Recurses through an attribute chain to get the ultimate value."""
    return reduce(getattr, attr.split("."), obj)


class RelatedFilterMixin(FilterMixin):
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


class PageSizeSelectMixin:
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


class InlineFormSetMixin:
    formset_class = None
    formset_prefix = None

    def add_formset_form(self, prefix):
        cp = self.request.POST.copy()
        cp[f"{prefix}-TOTAL_FORMS"] = int(cp[f"{prefix}-TOTAL_FORMS"]) + 1
        return cp

    def delete_formset_form(self, idx_to_delete, prefix):
        cp = self.request.POST.copy()
        cp[f"{prefix}-TOTAL_FORMS"] = int(cp[f"{prefix}-TOTAL_FORMS"]) - 1
        regex = prefix + r"-(\d+)-"
        filtered = {}
        for k, v in cp.items():
            match = re.findall(regex, k)
            if match:
                idx = int(match[0])
                if idx == idx_to_delete:
                    continue
                if idx > idx_to_delete:
                    k = re.sub(regex, f"{prefix}-{idx-1}-", k)
                filtered[k] = v
            else:
                filtered[k] = v
        return filtered

    def clear_errors(self, form_or_formset):
        # Hide all errors of a form or formset.
        # Found only this hacky way.
        # See https://stackoverflow.com/questions/64402527
        form_or_formset._errors = {}
        if hasattr(form_or_formset, "forms"):
            for form in form_or_formset.forms:
                self.clear_errors(form)

    def post(self, request, *args, **kwargs):
        self.object = None

        form = self.get_form()

        if request.POST.get("add_formset_form"):
            post_data = self.add_formset_form(self.formset_prefix)
            formset = self.formset_class(post_data)
            return self.render_changed_formset(form, formset)

        if request.POST.get("delete_formset_form"):
            idx_to_delete = int(request.POST.get("delete_formset_form"))
            post_data = self.delete_formset_form(idx_to_delete, self.formset_prefix)
            formset = self.formset_class(post_data)
            return self.render_changed_formset(form, formset)

        formset = self.formset_class(request.POST)
        if form.is_valid() and formset.is_valid():
            return self.form_and_formset_valid(form, formset)

        return self.form_or_formset_invalid(form, formset)

    def render_changed_formset(self, form, formset):
        self.clear_errors(form)
        self.clear_errors(formset)
        return self.form_or_formset_invalid(form, formset)

    def form_invalid(self, form):
        raise AttributeError(
            "A 'InlineFormSetCreateView' does not have a 'form_invalid' attribute. "
            "Use 'form_or_formset_invalid' instead."
        )

    def form_valid(self, form):
        raise AttributeError(
            "A 'InlineFormSetCreateView' does not have a 'form_valid' attribute. "
            "Use 'form_and_formset_valid' instead."
        )

    def form_or_formset_invalid(self, form, formset):
        return self.render_to_response(self.get_context_data(form=form, formset=formset))

    def form_and_formset_valid(self, form, formset):
        response = super().form_valid(form)
        formset.instance = self.object
        for idx, formset_form in enumerate(formset.ordered_forms):
            formset_form.instance.order = (
                formset_form.cleaned_data.get(ORDERING_FIELD_NAME) or idx + 1
            )
        formset.save()
        return response

    def get_context_data(self, **kwargs):
        if "formset" not in kwargs:
            kwargs["formset"] = self.formset_class()
        return super().get_context_data(**kwargs)
