import logging
import sys

from automation_server_client import (
    AutomationServer,
    Workqueue,
    Credential,
    WorkItemStatus,
)

from boss_client import client as boss_client
from oes_client import client as oes_client
from odk_tools.reporting import report
from odk_tools.tracking import Tracker

proces_navn = "Brugerluk ØS"


def populate_queue(workqueue: Workqueue, boss: boss_client.BossClient):
    logger = logging.getLogger(__name__)
    systems = boss.hent_systemer()
    boss_items = [
        item for item in systems["systems"] if item["systemName"] == "OS Indsigt"
    ]

    for item in boss_items:
        workqueue.add_item(item, item["initials"])


def process_workqueue(
    workqueue: Workqueue,
    boss: boss_client.BossClient,
    oes: oes_client.OESClient,
    tracker: Tracker,
):
    logger = logging.getLogger(__name__)

    for item in workqueue:
        with item:
            data = item.data  # Item data deserialized from json as dict

            try:
                oes.fremsoeg_bruger(data["initials"])
                oes.slet_bruger()
                boss.marker_bruger_som_slettet(data["id"])
                tracker.track_task(proces_navn)
            except ValueError as e:
                report(
                    "brugerluk_oes",
                    "Fejl",
                    {"Brugernavn": data["initials"], "Fejl": str(e)},
                )
                boss.marker_bruger_som_slettet(data["id"])
                tracker.track_partial_task(proces_navn)


if __name__ == "__main__":
    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    tracking_credential = Credential.get_credential("Odense SQL Server")
    boss_credential = Credential.get_credential("BOSS")
    robob_credential = Credential.get_credential("RoboB")

    boss = boss_client.BossClient(
        client_id=boss_credential.username,
        client_secret=boss_credential.password,
        api_url=boss_credential.data["api_url"],
        base_url=boss_credential.data["base_url"],
        login_url=boss_credential.data["login_url"],
    )

    oes = oes_client.OESClient(
        base_url=robob_credential.data["oes_url"],
        username=f"{robob_credential.username}@odense.dk",
        password=robob_credential.password,
        headless=True,
    )

    tracker = Tracker(
        username=tracking_credential.username, password=tracking_credential.password
    )

    # Queue management
    if "--queue" in sys.argv:
        workqueue.clear_workqueue(WorkItemStatus.NEW)
        populate_queue(workqueue, boss)
        exit(0)

    # Process workqueue
    process_workqueue(workqueue, boss, oes, tracker)
