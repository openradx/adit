import re


def extract_document_id(id: str) -> str:
    return id.split(":")[-1]


def sanitize_report_summary(text: str):
    text = re.sub(r"[\r\n]+", '<em class="break">...</em>', text)
    return text.strip()
