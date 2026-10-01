import factory
from adit_radis_shared.common.factories import BaseDjangoModelFactory

from adit.core.factories import DicomServerFactory

from .models import RouterSender


class RouterSenderFactory(BaseDjangoModelFactory[RouterSender]):
    class Meta:
        model = RouterSender

    server = factory.SubFactory(DicomServerFactory)
    calling_ae_title = factory.Sequence(lambda n: f"SENDER{n}")
    enabled = True
