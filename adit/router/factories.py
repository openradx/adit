import uuid

import factory
from adit_radis_shared.accounts.factories import UserFactory
from adit_radis_shared.common.factories import BaseDjangoModelFactory
from pydicom.uid import generate_uid

from adit.core.factories import (
    AbstractTransferJobFactory,
    AbstractTransferTaskFactory,
    DicomServerFactory,
)

from .models import RouterBatch, RouterJob, RouterSender, RouterTask, RoutingRule


class RouterSenderFactory(BaseDjangoModelFactory[RouterSender]):
    class Meta:
        model = RouterSender

    server = factory.SubFactory(DicomServerFactory)
    calling_ae_title = factory.Sequence(lambda n: f"SENDER{n}")
    enabled = True


class RoutingRuleFactory(BaseDjangoModelFactory[RoutingRule]):
    class Meta:
        model = RoutingRule

    name = factory.Sequence(lambda n: f"Rule {n}")
    filters_json = factory.LazyFunction(lambda: [{"mode": "include", "modality": "CT"}])
    destination = factory.SubFactory(DicomServerFactory)
    created_by = factory.SubFactory(UserFactory)


class RouterBatchFactory(BaseDjangoModelFactory[RouterBatch]):
    class Meta:
        model = RouterBatch

    batch_id = factory.LazyFunction(uuid.uuid4)
    sender = factory.SubFactory(RouterSenderFactory)
    study_instance_uid = factory.LazyFunction(generate_uid)
    number_of_images = 1


class RouterJobFactory(AbstractTransferJobFactory[RouterJob]):
    class Meta:
        model = RouterJob

    status = RouterJob.Status.PENDING
    urgent = False
    rule = factory.SubFactory(RoutingRuleFactory)
    owner = factory.LazyAttribute(lambda job: job.rule.created_by)
    batch = factory.SubFactory(RouterBatchFactory)


class RouterTaskFactory(AbstractTransferTaskFactory[RouterTask]):
    class Meta:
        model = RouterTask

    job = factory.SubFactory(RouterJobFactory)
    status = RouterTask.Status.PENDING
    series_uids = factory.LazyFunction(list)
    pseudonym = ""
