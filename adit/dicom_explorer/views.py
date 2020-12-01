from django.views.generic.edit import FormView
from django.core.exceptions import SuspiciousOperation
from .forms import DicomExplorerQueryForm


class DicomExplorerView(FormView):
    form_class = DicomExplorerQueryForm

    def get_template_names(self):
        if self.request.GET.get("query"):
            return ["dicom_explorer/dicom_explorer_result.html"]
        else:
            return ["dicom_explorer/dicom_explorer_form.html"]

    def get_form_kwargs(self):
        # Overridden because we use GET method for posting the query

        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        if self.request.GET.get("query"):
            kwargs.update({"data": self.request.GET})

        return kwargs

    def post(self, request, *args, **kwargs):
        raise SuspiciousOperation

    def get(self, request, *args, **kwargs):
        if not self.request.GET.get("query"):
            return super().get(request, *args, **kwargs)

        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)

        return self.form_invalid(form)

    def form_valid(self, form):
        return self.render_to_response(self.get_context_data(form=form))
