from django.forms import ModelChoiceField, fields, forms
from django.template.defaultfilters import filesizeformat

from .models import DicomNode
from .widgets import DicomNodeSelect


class DicomNodeChoiceField(ModelChoiceField):
    """Field for selecting a DicomNode."""

    def __init__(self, source, node_type=None):
        if source:
            queryset = DicomNode.objects.filter(source_active=True)
        else:
            queryset = DicomNode.objects.filter(destination_active=True)

        if node_type and node_type in dict(DicomNode.NodeType.choices):
            queryset = queryset.filter(node_type=node_type)
        elif node_type is not None:
            raise AssertionError(f"Invalid node type: {node_type}")

        super().__init__(queryset=queryset, widget=DicomNodeSelect)


class RestrictedFileField(fields.FileField):
    """File field with restrictions.

    Same as FileField, but you can specify:
        * content_types - list containing allowed content_types.
          Example: ['application/pdf', 'image/jpeg']
            1MB - 1048576
            2.5MB - 2621440
            5MB - 5242880
            10MB - 10485760
            20MB - 20971520
            50MB - 52428800
            100MB - 104857600

    Adapted from https://stackoverflow.com/a/9016664/166229
    """

    def __init__(self, *args, **kwargs):
        self.max_upload_size = kwargs.pop("max_upload_size", 0)

        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        file = super().clean(data, initial=initial)

        if file.size > self.max_upload_size:
            raise forms.ValidationError(
                "File too large. Please keep filesize "
                f"under {filesizeformat(self.max_upload_size)}."
            )

        return file
