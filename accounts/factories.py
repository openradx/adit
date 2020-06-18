import factory
from .models import User

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: "user_%d" % n)
    email = factory.Faker('email')
    password = factory.PostGenerationMethodCall('set_password', 'userpass')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')


class AdminUserFactory(UserFactory):
    is_superuser = True
    is_staff = True

class StaffUserFactory(UserFactory):
    is_staff = True