from django.conf import settings
from django.core.mail import mail_admins, send_mail
from django.utils.html import strip_tags

from adit_radis_shared.accounts.models import User


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


def send_mail_to_user(
    user: User, subject: str, text_content: str | None = None, html_content: str | None = None
):
    if text_content is None and html_content is None:
        raise Exception("Email must at least have html_content or text_content.")

    subject = settings.EMAIL_SUBJECT_PREFIX + subject
    if text_content is None:
        assert html_content is not None
        text_content = strip_tags(html_content)

    send_mail(
        subject,
        text_content,
        None,
        html_message=html_content,
        recipient_list=[user.email],
    )
