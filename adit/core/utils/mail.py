from django.conf import settings
from django.core.mail import mail_admins, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from adit.shared.accounts.models import User


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
        raise Exception("Email must at have html_contant or text_content.")

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


def send_job_finished_mail(job):
    subject = "Job finished"
    html_content = render_to_string(
        "core/mail/dicom_job_finished.html",
        {"base_url": settings.BASE_URL, "job": job},
    )
    send_mail_to_user(job.owner, subject, html_content=html_content)


# TODO: This is not used anymore.
def send_job_failed_mail(job, celery_task_id):
    subject = "Job failed"
    html_content = render_to_string(
        "core/mail/dicom_job_failed.html",
        {"base_url": settings.BASE_URL, "job": job, "celery_task_id": celery_task_id},
    )
    send_mail_to_admins(subject, html_content=html_content)
    send_mail_to_user(job.owner, subject, html_content=html_content)
