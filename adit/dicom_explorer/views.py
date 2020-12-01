from django.views.generic.edit import FormView
from .forms import DicomExplorerQueryForm


class DicomExplorerView(FormView):
    template_name = "dicom_explorer/dicom_explorer.html"
    form_class = DicomExplorerQueryForm
    success_url = "dicom_explorer"

    def get_form_kwargs(self):
        # Overridden because we use GET method for posting the query

        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }

        if self.request.GET.get("query"):
            kwargs.update({"data": self.request.GET})

        return kwargs
