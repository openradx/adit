import threading
from datetime import timedelta
from pathlib import Path

import pytest
from adit_radis_shared.common.utils.testing_helpers import run_worker_once
from django.utils import timezone

from adit.core.utils.orthanc_utils import OrthancRestHandler
from adit.core.utils.pseudonymizer import deterministic_pseudonym
from adit.core.utils.testing_helpers import (
    free_port,
    setup_dimse_orthancs,
    wait_until_scp_accepts,
    wait_until_scp_idle,
)
from adit.router.factories import RoutingRuleFactory
from adit.router.models import RouterJob, RouterSender
from adit.router.utils import spool
from adit.router.utils.closer import run_spool_cycle
from adit.router.utils.intake import RouterStoreHandler, build_router_scp, load_intake_config

ROUTER_AE = "ROUTERE2E"


@pytest.mark.acceptance
@pytest.mark.order("last")
@pytest.mark.django_db(transaction=True)
def test_router_delivers_matching_studies_pseudonymized(tmp_path: Path, settings):
    orthanc1, orthanc2 = setup_dimse_orthancs()
    sender = RouterSender.objects.create(server=orthanc1)
    rule = RoutingRuleFactory.create(
        filters_json=[{"mode": "include", "modality": "CT"}],
        destination=orthanc2,
        trial_protocol_id="XNATPROJ",
    )
    settings.ROUTER_SPOOL_PATH = str(tmp_path)
    spool.ensure_spool_dirs(tmp_path)

    handler = RouterStoreHandler(tmp_path, min_free_bytes=0)
    handler.update_config(load_intake_config())
    port = free_port()
    scp = build_router_scp(tmp_path, handler, ae_title=ROUTER_AE, host="0.0.0.0", port=port)
    thread = threading.Thread(target=scp.start, daemon=True)
    thread.start()
    wait_until_scp_accepts(port, sender.calling_ae_title, ROUTER_AE)

    orthanc1_api = OrthancRestHandler(settings.ORTHANC1_HOST, settings.ORTHANC1_HTTP_PORT)
    orthanc2_api = OrthancRestHandler(settings.ORTHANC2_HOST, settings.ORTHANC2_HTTP_PORT)
    # The test runs in the web container. Orthanc resolves compose service names, but not
    # the containers' *.local hostnames.
    orthanc1_api.add_modality(ROUTER_AE, ROUTER_AE, "web", port)
    try:
        ct_study = orthanc1_api.find({"Level": "Study", "Query": {"PatientID": "1004"}})
        mr_study = orthanc1_api.find({"Level": "Study", "Query": {"PatientID": "1002"}})
        orthanc1_api.send_to_modality(ROUTER_AE, ct_study + mr_study)
    finally:
        orthanc1_api.remove_modality(ROUTER_AE)
        wait_until_scp_idle(scp)
        scp.stop()
        thread.join(timeout=5)

    run_spool_cycle(tmp_path, timezone.now() + timedelta(hours=2))

    job = RouterJob.objects.get()
    assert len(spool.list_batches(tmp_path)) == 1

    run_worker_once()

    pseudonym = deterministic_pseudonym(rule.pseudonym_salt, "1004")
    instances = orthanc2_api.find({"Level": "Instance", "Query": {"PatientID": pseudonym}})
    assert len(instances) == 10
    tags = orthanc2_api.instance_tags(instances[0])
    assert tags["PatientComments"].startswith(f"Project:XNATPROJ Subject:{pseudonym} ")
    assert orthanc2_api.find({"Level": "Study", "Query": {"PatientID": "1002"}}) == []
    job.refresh_from_db()
    assert job.status == RouterJob.Status.SUCCESS
