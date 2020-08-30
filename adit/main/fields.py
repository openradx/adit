from django.db import models


class SeparatedValuesField(models.TextField):
    """A serialized field that stores a list of strings.

    Inspired by https://stackoverflow.com/a/1113039/166229
    and https://github.com/ulule/django-separatedvaluesfield
    see also https://docs.djangoproject.com/en/3.1/howto/custom-model-fields/
    """

    def __init__(self, *args, **kwargs):
        self.token = kwargs.pop("token", ",")
        super(SeparatedValuesField, self).__init__(*args, **kwargs)

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
