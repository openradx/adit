from typing import Protocol, runtime_checkable


@runtime_checkable
class AnnotatedReport(Protocol):
    total: int


def extract_document_id(id: str) -> str:
    return id.split(":")[-1]
