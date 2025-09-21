import pytest
from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from adit.core.factories import DicomServerFactory
from adit.core.models import DicomNodeGroupAccess
from adit.dicom_explorer.models import PermissionSupport


@pytest.mark.django_db
class TestDicomExplorer:
    def test_dicom_explorer_form_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        client.force_login(user)
        response = client.get("/dicom-explorer/")
        assert response.status_code == 200

    def test_dicom_explorer_form_view_with_server_redirect(self):
        client = Client()
        group = GroupFactory.create()
        user = UserFactory.create(is_active=True)
        user.groups.add(group)
        user.active_group = group
        user.save()
        client.force_login(user)
        server = DicomServerFactory.create()
        # Create access permission for user's group to access server as source
        DicomNodeGroupAccess.objects.create(dicom_node=server, group=group, source=True)
        response = client.get(f"/dicom-explorer/?server={server.pk}")
        assert response.status_code == 302  # Should redirect to server detail

    def test_dicom_explorer_server_query_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="query_dicom_server",
            content_type=ContentType.objects.get_for_model(PermissionSupport),
        )
        user.user_permissions.add(permission)
        client.force_login(user)
        response = client.get("/dicom-explorer/servers/")
        assert response.status_code == 200

    def test_dicom_explorer_server_detail_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="query_dicom_server",
            content_type=ContentType.objects.get_for_model(PermissionSupport),
        )
        user.user_permissions.add(permission)
        client.force_login(user)
        server = DicomServerFactory.create()
        response = client.get(f"/dicom-explorer/servers/{server.pk}/")
        assert response.status_code == 200

    def test_dicom_explorer_patient_query_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="query_dicom_server",
            content_type=ContentType.objects.get_for_model(PermissionSupport),
        )
        user.user_permissions.add(permission)
        client.force_login(user)
        server = DicomServerFactory.create()
        response = client.get(f"/dicom-explorer/servers/{server.pk}/patients/")
        assert response.status_code == 200

    def test_dicom_explorer_patient_detail_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="query_dicom_server",
            content_type=ContentType.objects.get_for_model(PermissionSupport),
        )
        user.user_permissions.add(permission)
        client.force_login(user)
        server = DicomServerFactory.create()
        patient_id = "PAT001"
        response = client.get(f"/dicom-explorer/servers/{server.pk}/patients/{patient_id}/")
        assert response.status_code == 200

    def test_dicom_explorer_study_query_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="query_dicom_server",
            content_type=ContentType.objects.get_for_model(PermissionSupport),
        )
        user.user_permissions.add(permission)
        client.force_login(user)
        server = DicomServerFactory.create()
        response = client.get(f"/dicom-explorer/servers/{server.pk}/studies/")
        assert response.status_code == 200

    def test_dicom_explorer_study_detail_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="query_dicom_server",
            content_type=ContentType.objects.get_for_model(PermissionSupport),
        )
        user.user_permissions.add(permission)
        client.force_login(user)
        server = DicomServerFactory.create()
        study_uid = "1.2.3.4.5.6.7.8.9"
        response = client.get(f"/dicom-explorer/servers/{server.pk}/studies/{study_uid}/")
        assert response.status_code == 200

    def test_dicom_explorer_series_query_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="query_dicom_server",
            content_type=ContentType.objects.get_for_model(PermissionSupport),
        )
        user.user_permissions.add(permission)
        client.force_login(user)
        server = DicomServerFactory.create()
        study_uid = "1.2.3.4.5.6.7.8.9"
        response = client.get(f"/dicom-explorer/servers/{server.pk}/studies/{study_uid}/series/")
        assert response.status_code == 200

    def test_dicom_explorer_series_detail_view(self):
        client = Client()
        user = UserFactory.create(is_active=True)
        permission = Permission.objects.get(
            codename="query_dicom_server",
            content_type=ContentType.objects.get_for_model(PermissionSupport),
        )
        user.user_permissions.add(permission)
        client.force_login(user)
        server = DicomServerFactory.create()
        study_uid = "1.2.3.4.5.6.7.8.9"
        series_uid = "1.2.3.4.5.6.7.8.9.10"
        url = f"/dicom-explorer/servers/{server.pk}/studies/{study_uid}/series/{series_uid}/"
        response = client.get(url)
        assert response.status_code == 200
