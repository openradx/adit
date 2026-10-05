"""Decides which routing rules a closed batch matches and creates their deliveries."""

import logging
from datetime import date
from pathlib import Path

from django.db import IntegrityError, transaction
from django.db.models import CharField

from adit.core.utils.pseudonymizer import deterministic_pseudonym
from adit.core.utils.series_filters import select_study_series

from ..models import RouterBatch, RouterJob, RouterSender, RouterTask, RoutingRule
from . import spool
from .batches import BatchContents, read_batch

logger = logging.getLogger(__name__)

_patient_id_field = RouterTask._meta.get_field("patient_id")
assert isinstance(_patient_id_field, CharField)
assert _patient_id_field.max_length is not None
# Postgres raises DataError (not IntegrityError) for a value over the column's
# max_length, which would otherwise make every later cycle fail on this batch.
_MAX_PATIENT_ID_LENGTH: int = _patient_id_field.max_length


def decide_batch(spool_root: Path, batch: spool.BatchDir, today: date) -> list[RouterJob]:
    """Decide a closed batch and return the router jobs created for it.

    A batch that has no Patient ID, matches no enabled rule, or whose images were all
    sent before, is deleted. A batch that was decided before is left alone, and the
    unique constraints keep a concurrent second decision from creating anything.
    """
    if RouterBatch.objects.filter(batch_id=batch.batch_id).exists():
        return []

    sender = RouterSender.objects.select_related("server").filter(pk=batch.sender_id).first()
    if sender is None:
        logger.warning(
            "Deleting router batch %s: its sender %d no longer exists.",
            batch.batch_id,
            batch.sender_id,
        )
        spool.delete_batch(batch.path)
        return []

    contents = read_batch(spool_root, batch.path, today)
    if not contents.images:
        logger.warning("Deleting router batch %s: none of its files could be read.", batch.batch_id)
        spool.delete_batch(batch.path)
        return []

    if not contents.patient_id:
        logger.warning(
            "Deleting router batch %s of %s (study %s, %d images): it has no Patient ID.",
            batch.batch_id,
            sender.calling_ae_title,
            contents.study_instance_uid,
            len(contents.images),
        )
        spool.delete_batch(batch.path)
        return []

    if len(contents.patient_id) > _MAX_PATIENT_ID_LENGTH:
        logger.warning(
            "Deleting router batch %s of %s (study %s, %d images): its Patient ID is "
            "longer than %d characters.",
            batch.batch_id,
            sender.calling_ae_title,
            contents.study_instance_uid,
            len(contents.images),
            _MAX_PATIENT_ID_LENGTH,
        )
        spool.delete_batch(batch.path)
        return []

    matches = _match_rules(contents)
    if not matches:
        logger.info(
            "Deleting router batch %s of %s (study %s, %d images): no routing rule matches.",
            batch.batch_id,
            sender.calling_ae_title,
            contents.study_instance_uid,
            len(contents.images),
        )
        spool.delete_batch(batch.path)
        return []

    try:
        with transaction.atomic():
            router_batch = RouterBatch.objects.create(
                batch_id=batch.batch_id,
                sender=sender,
                study_instance_uid=contents.study_instance_uid,
                number_of_images=len(contents.images),
            )
            return [
                _create_job(router_batch, sender, contents, rule, series_uids)
                for rule, series_uids in matches
            ]
    except IntegrityError:
        logger.warning("Router batch %s was decided by another run; skipping it.", batch.batch_id)
        return []


def _match_rules(contents: BatchContents) -> list[tuple[RoutingRule, list[str]]]:
    """The enabled rules with images left to send, each with the series to send."""
    matches: list[tuple[RoutingRule, list[str]]] = []
    rules = RoutingRule.objects.filter(enabled=True).select_related("destination", "created_by")
    for rule in rules.order_by("pk"):
        selected = {
            s.series_instance_uid
            for s in select_study_series(contents.study, contents.series, rule.get_filters())
        }
        already_sent = RouterTask.already_sent(
            rule.pk, contents.study_instance_uid, rule.destination_id
        )
        series_left = sorted(
            {
                image.series_instance_uid
                for image in contents.images
                if image.series_instance_uid in selected
                and image.sop_instance_uid not in already_sent
            }
        )
        if series_left:
            matches.append((rule, series_left))
    return matches


def _create_job(
    router_batch: RouterBatch,
    sender: RouterSender,
    contents: BatchContents,
    rule: RoutingRule,
    series_uids: list[str],
) -> RouterJob:
    job = RouterJob.objects.create(
        rule=rule,
        batch=router_batch,
        owner=rule.created_by,
        status=RouterJob.Status.PENDING,
        send_finished_mail=False,
        trial_protocol_id=rule.trial_protocol_id,
        trial_protocol_name=rule.trial_protocol_name,
    )
    RouterTask.objects.create(
        job=job,
        source=sender.server,
        destination=rule.destination,
        patient_id=contents.patient_id,
        study_uid=contents.study_instance_uid,
        series_uids=series_uids,
        pseudonym=_pseudonym(rule, contents),
    )
    # Queued inside the transaction, so the queue rows appear only with the batch.
    job.queue_pending_tasks()
    return job


def _pseudonym(rule: RoutingRule, contents: BatchContents) -> str:
    if not rule.pseudonymize:
        return ""
    return deterministic_pseudonym(rule.pseudonym_salt, contents.patient_id)
