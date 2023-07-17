from django.core.mail import mail_admins
from django.utils.html import strip_tags


def send_mail_to_admins(
    subject: str, text_content: str | None = None, html_content: str | None = None
):
    if text_content is None and html_content is None:
        raise Exception("Email must at have html_contant or text_content.")

    if text_content is None:
        assert html_content is not None
        text_content = strip_tags(html_content)

    # Emails for admins are automatically prefixed.
    mail_admins(subject, text_content, html_message=html_content)
