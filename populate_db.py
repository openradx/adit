import factory
from accounts.factories import AdminUserFactory, UserFactory
from main.factories import DicomServerFactory, DicomPathFactory
from batch_transfer.factories import BatchTransferJobFactory

AdminUserFactory()

users = []
for i in range(10):
    user = UserFactory()
    users.append(user)
    
servers = []
for i in range(5):
    server = DicomServerFactory()
    servers.append(server)

paths = []
for i in range(3):
    path = DicomPathFactory()
    paths.append(path)

server_or_paths = servers + paths

batch_transfer_jobs = []
for i in range(150):
    job = BatchTransferJobFactory(
        source=factory.Faker('random_element', elements=servers),
        destination=factory.Faker('random_element', elements=server_or_paths),
        created_by=factory.Faker('random_element', elements=users)
    )