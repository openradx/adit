from django.views.generic import TemplateView


class DicomExplorerView(TemplateView):
    template_name = "dicom_explorer/dicom_explorer.html"
