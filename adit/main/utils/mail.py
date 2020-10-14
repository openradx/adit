from django.conf import settings
from django.core.mail import mail_admins, send_mail
from django.utils.html import strip_tags
from django.template.loader import render_to_string


def send_mail_to_user(subject, html_content, user):
    subject = settings.EMAIL_SUBJECT_PREFIX + subject
    text_content = strip_tags(html_content)
    send_mail(
        subject,
        text_content,
        None,
        html_message=html_content,
        recipient_list=[user.email],
    )


def send_mail_to_admins(subject, html_content):
    text_content = strip_tags(html_content)
    mail_admins(subject, text_content, html_message=html_content)


def send_job_finished_mail(job):
    subject = f"{job.get_job_type_display()} finished"
    html_content = render_to_string(
        "main/mail/transfer_job_finished.html",
        {"BASE_URL": settings.BASE_URL, "job": job},
    )
    send_mail_to_user(subject, html_content, job.owner)


def send_job_failed_mail(job, celery_task_id):
    subject = f"{job.get_job_type_display()} failed"
    html_content = render_to_string(
        "main/mail/transfer_job_failed.html",
        {"BASE_URL": settings.BASE_URL, "job": job, "celery_task_id": celery_task_id},
    )
    send_mail_to_admins(subject, html_content)
    send_mail_to_user(subject, html_content, job.owner)
