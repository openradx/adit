import django_filters
from adit_radis_shared.common.types import with_form_helper
from crispy_forms.bootstrap import FieldWithButtons
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Hidden, Layout, Submit
from django.http import HttpRequest, QueryDict

from adit.core.filters import DicomJobFilter, DicomTaskFilter

from .models import RouterJob, RouterTask

FILTER_FIELD_TEMPLATE = "common/_filter_set_field.html"


class RouterJobFilterFormHelper(FormHelper):
    """Renders the rule and the status filter side by side, styled like the other filters.

    SingleFilterFieldFormHelper only takes one field. Like it, this helper keeps the other
    query parameters, such as the page size, as hidden fields.
    """

    def __init__(self, params: QueryDict, **kwargs):
        super().__init__(**kwargs)
        self.form_method = "get"
        self.disable_csrf = True
        self.layout = Layout(
            Div(
                Field(
                    "rule", css_class="form-select form-select-sm", template=FILTER_FIELD_TEMPLATE
                ),
                FieldWithButtons(
                    Field("status", css_class="form-select form-select-sm"),
                    Submit("", "Filter", css_class="btn-secondary btn-sm"),
                    template=FILTER_FIELD_TEMPLATE,
                ),
                css_class="d-flex gap-3",
            ),
            Div(
                *(
                    Hidden(key, value)
                    for key, value in params.items()
                    if key not in ("rule", "status", "page")
                )
            ),
        )


class RouterJobFilter(django_filters.FilterSet):
    request: HttpRequest

    class Meta:
        model = RouterJob
        fields = ("rule", "status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        with_form_helper(self.form).helper = RouterJobFilterFormHelper(self.request.GET)


class RoutingRuleJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = RouterJob


class RouterTaskFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = RouterTask
