from django.contrib.auth import get_user_model
from main.models import DicomServer, DicomPath

try:
    User = get_user_model()
    User.objects.get(username='admin')
except User.DoesNotExist:
    User.objects.create_superuser('admin', 'kai.schlamp@med.uni-heidelberg.de', 'admin')


DicomServer.objects.get_or_create(
    node_id='id_ceres',
    defaults=dict(
        node_name='Ceres',
        ae_title='ae_ceres',
        ip='192.168.1.1',
        port=11112
    )
)
DicomServer.objects.get_or_create(
    node_id='id_eros',
    defaults=dict(
        node_name='Eros',
        ae_title='ae_eros',
        ip='192.168.1.2',
        port=11112
    )
)

DicomPath.objects.get_or_create(
    node_id='id_pallas',
    defaults=dict(
        node_name='Pallas',
        path='/workspace/test_dir'
    )
)
