from typing import Callable, Literal

from radis.reports.models import Report

ReportEventType = Literal["created", "updated", "deleted"]
ReportEventHandler = Callable[[ReportEventType, Report], None]

report_event_handlers: list[ReportEventHandler] = []


def register_report_handler(handler: ReportEventHandler) -> None:
    report_event_handlers.append(handler)
