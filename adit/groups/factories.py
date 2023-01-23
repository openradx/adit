# import factory
# from faker import Faker
# from django.contrib.auth.models import Group
# from adit.groups.models import Access
# fake = Faker()


# class AccessFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = Access
        
#     access_type = 'src'
#     group = None
#     node = None
    

# class GroupFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = Group
#         django_get_or_create = ("name",)

#     name = factory.Sequence(lambda n: f"group_{n}")