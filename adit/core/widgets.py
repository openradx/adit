from django.forms.widgets import Select

from .models import DicomNode


class DicomNodeSelect(Select):
    """Widget for selecting a DicomNode."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if hasattr(value, "instance"):
            # Used to check if a an archive can be created in the selective transfer form
            dicom_node = value.instance
            if dicom_node.node_type == DicomNode.NodeType.SERVER:
                option["attrs"]["data-node_type"] = "server"
                option["attrs"]["data-node_id"] = dicom_node.id
            elif dicom_node.node_type == DicomNode.NodeType.FOLDER:
                option["attrs"]["data-node_type"] = "folder"
                option["attrs"]["data-node_id"] = dicom_node.id

        return option

