from django.contrib.auth import get_user_model
from django.db import IntegrityError
from main.models import DicomServer, DicomPath
from batch_transfer.models import BatchTransferJob
from main.models import TransferJob

superuser = None
User = get_user_model()
try:
    superuser = User.objects.get(username='admin')
except User.DoesNotExist:
    superuser = User.objects.create_superuser('admin', 'kai.schlamp@med.uni-heidelberg.de', 'admin')

def get_or_create_user(username, email, password, *args, **kwargs):
    global User, IntegrityError
    try:
        return (User.objects.create_user(username, email, password), True)
    except IntegrityError:
        return (User.objects.get(username=username, email=email), False)

normal_users = []
for i in range(10):
    username = 'user' + str(i)
    email = username + '@foo.com'
    password = username
    normal_user, _ = get_or_create_user(username, email, password)
    normal_users.append(normal_user)

ceres_server, _ = DicomServer.objects.get_or_create(
    node_id='id_ceres',
    defaults=dict(
        node_name='Ceres',
        ae_title='ae_ceres',
        ip='192.168.1.1',
        port=11112
    )
)

eros_server, _ = DicomServer.objects.get_or_create(
    node_id='id_eros',
    defaults=dict(
        node_name='Eros',
        ae_title='ae_eros',
        ip='192.168.1.2',
        port=11112
    )
)

pallas_path, _ = DicomPath.objects.get_or_create(
    node_id='id_pallas',
    defaults=dict(
        node_name='Pallas',
        path='/workspace/test_dir'
    )
)

batch_transfer_jobs = []
for i in range(10):
    project_name = 'Project ' + str(i)
    project_description = project_name + ' description'
    batch_transfer_jobs.append(
        BatchTransferJob.objects.create(
            source=ceres_server,
            destination=eros_server,
            project_name=project_name,
            project_description=project_description,
            created_by=normal_users[3]
        )
    )
