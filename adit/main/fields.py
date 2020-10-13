from django.db import models
from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor


class SeparatedValuesField(models.TextField):
    """A serialized field that stores a list of strings.

    Inspired by https://stackoverflow.com/a/1113039/166229
    and https://github.com/ulule/django-separatedvaluesfield
    see also https://docs.djangoproject.com/en/3.1/howto/custom-model-fields/
    """

    def __init__(self, *args, **kwargs):
        self.token = kwargs.pop("token", ",")
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if not value:
            return None

        if isinstance(value, list):
            return value

        return value.split(self.token)

    def get_prep_value(self, value):
        if not value:
            return None

        assert isinstance(value, (list, tuple))
        return self.token.join(["%s" % s for s in value])

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return self.get_prep_value(value)


# Make related fields work with InheritanceManager of django-model-utils.
# This unfortunately does not work for prefetching related fields with
# select_related (but does work for prefetch_related).
# Solution from https://github.com/jazzband/django-model-utils/issues/11
class InheritanceForwardManyToOneDescriptor(ForwardManyToOneDescriptor):
    def get_queryset(self, **hints):
        return self.field.remote_field.model.objects.db_manager(
            hints=hints
        ).select_subclasses()


class InheritanceForeignKey(models.ForeignKey):
    forward_related_accessor_class = InheritanceForwardManyToOneDescriptor
