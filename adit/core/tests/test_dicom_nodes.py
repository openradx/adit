import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from django.db import IntegrityError

from adit.core.factories import DicomFolderFactory, DicomServerFactory
from adit.core.models import DicomNode, DicomNodeGroupAccess


class TestDicomNode:
    @pytest.mark.django_db
    def test_dicom_server_creation(self):
        server = DicomServerFactory.create(name="Test Server")

        assert server.node_type == DicomNode.NodeType.SERVER
        assert server.name == "Test Server"
        assert isinstance(server, DicomNode)

    @pytest.mark.django_db
    def test_dicom_folder_creation(self):
        folder = DicomFolderFactory.create(name="Test Folder", path="/test/path")

        assert folder.node_type == DicomNode.NodeType.FOLDER
        assert folder.name == "Test Folder"
        assert folder.path == "/test/path"
        assert isinstance(folder, DicomNode)

    @pytest.mark.django_db
    def test_dicom_server_string_representation(self):
        server = DicomServerFactory.create(name="MyServer")
        expected = "DICOM Server MyServer"
        assert str(server) == expected

    @pytest.mark.django_db
    def test_dicom_folder_string_representation(self):
        folder = DicomFolderFactory.create(name="MyFolder")
        expected = "DICOM Folder MyFolder"
        assert str(folder) == expected

    @pytest.mark.django_db
    def test_dicom_node_repr(self):
        server = DicomServerFactory.create(name="TestServer")
        expected = f"DICOM Server TestServer [{server.pk}]"
        assert repr(server) == expected

    @pytest.mark.django_db
    def test_dicom_node_name_uniqueness(self):
        DicomServerFactory.create(name="UniqueServer")

        with pytest.raises(IntegrityError):
            DicomFolderFactory.create(name="UniqueServer")

    @pytest.mark.django_db
    def test_dicom_server_ae_title_uniqueness(self):
        DicomServerFactory.create(ae_title="UNIQUE_AE")

        with pytest.raises(IntegrityError):
            DicomServerFactory.create(ae_title="UNIQUE_AE")

    @pytest.mark.django_db
    def test_dicom_server_port_validation(self):
        """Test DicomServer port validation."""
        server = DicomServerFactory.create(port=1024)
        assert server.port == 1024

        server = DicomServerFactory.create(port=65535)
        assert server.port == 65535

    @pytest.mark.django_db
    def test_dicom_node_ordering(self):
        DicomNode.objects.all().delete()

        DicomServerFactory.create(name="B_Server")
        DicomServerFactory.create(name="A_Server")
        DicomServerFactory.create(name="C_Server")

        nodes = list(DicomNode.objects.all())
        node_names = [node.name for node in nodes]
        expected_names = ["A_Server", "B_Server", "C_Server"]
        assert node_names == expected_names

    @pytest.mark.django_db
    def test_is_accessible_by_user_with_access(self):
        user = UserFactory.create()
        group = GroupFactory.create()
        user.groups.add(group)
        user.active_group = group
        user.save()

        server = DicomServerFactory.create()
        DicomNodeGroupAccess.objects.create(dicom_node=server, group=group, source=True)

        assert server.is_accessible_by_user(user, "source")
        assert not server.is_accessible_by_user(user, "destination")

    @pytest.mark.django_db
    def test_is_accessible_by_user_without_access(self):
        user = UserFactory.create()
        group = GroupFactory.create()
        user.groups.add(group)
        user.active_group = group
        user.save()

        server = DicomServerFactory.create()

        assert not server.is_accessible_by_user(user, "source")
        assert not server.is_accessible_by_user(user, "destination")


class TestDicomNodeManager:
    @pytest.mark.django_db
    def test_accessible_by_user_source_access(self):
        user = UserFactory.create()
        group = GroupFactory.create()
        user.groups.add(group)
        user.active_group = group
        user.save()

        server_source = DicomServerFactory.create(name="SourceServer")
        server_dest = DicomServerFactory.create(name="DestServer")
        server_no_access = DicomServerFactory.create(name="NoAccessServer")

        DicomNodeGroupAccess.objects.create(
            dicom_node=server_source, group=group, source=True, destination=False
        )
        DicomNodeGroupAccess.objects.create(
            dicom_node=server_dest, group=group, source=False, destination=True
        )

        accessible_sources = DicomNode.objects.accessible_by_user(user, "source")

        assert accessible_sources.filter(pk=server_source.pk).exists()
        assert not accessible_sources.filter(pk=server_dest.pk).exists()
        assert not accessible_sources.filter(pk=server_no_access.pk).exists()

    @pytest.mark.django_db
    def test_accessible_by_user_destination_access(self):
        user = UserFactory.create()
        group = GroupFactory.create()
        user.groups.add(group)
        user.active_group = group
        user.save()

        server_dest = DicomServerFactory.create(name="DestServer")
        DicomNodeGroupAccess.objects.create(dicom_node=server_dest, group=group, destination=True)

        accessible_destinations = DicomNode.objects.accessible_by_user(user, "destination")

        assert accessible_destinations.filter(pk=server_dest.pk).exists()

    @pytest.mark.django_db
    def test_accessible_by_user_all_groups(self):
        user = UserFactory.create()
        group1 = GroupFactory.create()
        group2 = GroupFactory.create()
        user.groups.add(group1, group2)
        user.active_group = group1
        user.save()

        server1 = DicomServerFactory.create(name="Server1")
        server2 = DicomServerFactory.create(name="Server2")

        DicomNodeGroupAccess.objects.create(dicom_node=server1, group=group1, source=True)
        DicomNodeGroupAccess.objects.create(dicom_node=server2, group=group2, source=True)

        # Test with active group only
        accessible_active = DicomNode.objects.accessible_by_user(user, "source", all_groups=False)
        assert accessible_active.filter(pk=server1.pk).exists()
        assert not accessible_active.filter(pk=server2.pk).exists()

        # Test with all groups
        accessible_all = DicomNode.objects.accessible_by_user(user, "source", all_groups=True)
        assert accessible_all.filter(pk=server1.pk).exists()
        assert accessible_all.filter(pk=server2.pk).exists()

    @pytest.mark.django_db
    def test_accessible_by_user_invalid_access_type(self):
        user = UserFactory.create()

        with pytest.raises(AssertionError, match="Invalid node type: invalid"):
            DicomNode.objects.accessible_by_user(user, "invalid")  # type: ignore

    @pytest.mark.django_db
    def test_accessible_by_user_duplicate_results_filtered(self):
        user = UserFactory.create()
        group1 = GroupFactory.create()
        group2 = GroupFactory.create()
        user.groups.add(group1, group2)
        user.active_group = group1
        user.save()

        server = DicomServerFactory.create()

        DicomNodeGroupAccess.objects.create(dicom_node=server, group=group1, source=True)
        DicomNodeGroupAccess.objects.create(dicom_node=server, group=group2, source=True)

        accessible = DicomNode.objects.accessible_by_user(user, "source", all_groups=True)

        # Should only appear once despite multiple access grants
        assert accessible.count() == 1
        assert accessible.filter(pk=server.pk).exists()


class TestDicomNodeGroupAccess:
    @pytest.mark.django_db
    def test_dicom_node_group_access_creation(self):
        """Test creating DicomNodeGroupAccess relationship."""
        node = DicomServerFactory.create()
        group = GroupFactory.create()

        access = DicomNodeGroupAccess.objects.create(
            dicom_node=node, group=group, source=True, destination=False
        )

        assert access.dicom_node == node
        assert access.group == group
        assert access.source is True
        assert access.destination is False

    @pytest.mark.django_db
    def test_dicom_node_group_access_unique_constraint(self):
        node = DicomServerFactory.create()
        group = GroupFactory.create()

        DicomNodeGroupAccess.objects.create(dicom_node=node, group=group, source=True)

        # Trying to create another access for same node/group should fail
        with pytest.raises(IntegrityError):
            DicomNodeGroupAccess.objects.create(dicom_node=node, group=group, destination=True)

    @pytest.mark.django_db
    def test_dicom_node_group_access_defaults(self):
        node = DicomServerFactory.create()
        group = GroupFactory.create()

        access = DicomNodeGroupAccess.objects.create(dicom_node=node, group=group)

        assert access.source is False
        assert access.destination is False

    @pytest.mark.django_db
    def test_dicom_node_group_access_string_representation(self):
        """Test DicomNodeGroupAccess string representation."""
        node = DicomServerFactory.create()
        group = GroupFactory.create()

        access = DicomNodeGroupAccess.objects.create(dicom_node=node, group=group)

        expected = f"DicomNodeGroupAccess [{access.pk}]"
        assert str(access) == expected

    @pytest.mark.django_db
    def test_cascade_delete_node(self):
        node = DicomServerFactory.create()
        group = GroupFactory.create()

        access = DicomNodeGroupAccess.objects.create(dicom_node=node, group=group, source=True)
        access_pk = access.pk

        node.delete()

        # Access should be deleted as well
        assert not DicomNodeGroupAccess.objects.filter(pk=access_pk).exists()

    @pytest.mark.django_db
    def test_cascade_delete_group(self):
        node = DicomServerFactory.create()
        group = GroupFactory.create()

        access = DicomNodeGroupAccess.objects.create(dicom_node=node, group=group, source=True)
        access_pk = access.pk

        group.delete()

        # Access should be deleted as well
        assert not DicomNodeGroupAccess.objects.filter(pk=access_pk).exists()


class TestDicomServer:
    @pytest.mark.django_db
    def test_dicom_server_default_support_flags(self):
        server = DicomServerFactory.create()

        assert server.patient_root_find_support is True
        assert server.patient_root_get_support is True
        assert server.patient_root_move_support is True
        assert server.study_root_find_support is True
        assert server.study_root_get_support is True
        assert server.study_root_move_support is True
        assert server.store_scp_support is True

        assert server.dicomweb_qido_support is False
        assert server.dicomweb_wado_support is False
        assert server.dicomweb_stow_support is False

    @pytest.mark.django_db
    def test_dicom_server_dicomweb_fields(self):
        server = DicomServerFactory.create(
            dicomweb_root_url="http://example.com/dicomweb",
            dicomweb_qido_prefix="/qido-rs",
            dicomweb_wado_prefix="/wado-rs",
            dicomweb_stow_prefix="/stow-rs",
            dicomweb_authorization_header="CCI Bonn token123",
        )

        assert server.dicomweb_root_url == "http://example.com/dicomweb"
        assert server.dicomweb_qido_prefix == "/qido-rs"
        assert server.dicomweb_wado_prefix == "/wado-rs"
        assert server.dicomweb_stow_prefix == "/stow-rs"
        assert server.dicomweb_authorization_header == "CCI Bonn token123"


class TestDicomFolder:
    @pytest.mark.django_db
    def test_dicom_folder_quota_fields(self):
        folder = DicomFolderFactory.create(
            path="/test/path",
            quota=1000,
            warn_size=800,
        )

        assert folder.path == "/test/path"
        assert folder.quota == 1000
        assert folder.warn_size == 800

    @pytest.mark.django_db
    def test_dicom_folder_nullable_fields(self):
        folder = DicomFolderFactory.create(quota=None, warn_size=None)

        assert folder.quota is None
        assert folder.warn_size is None
