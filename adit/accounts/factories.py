import factory
from .models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: "user_%d" % n)
    email = factory.Faker("email")
    password = factory.PostGenerationMethodCall("set_password", "userpass")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    phone_number = factory.Faker("phone_number")
    department = factory.Faker("company")


class AdminUserFactory(UserFactory):
    username = "admin"
    email = "admin@adit.test"
    password = factory.PostGenerationMethodCall("set_password", "admin")
    is_superuser = True
    is_staff = True
