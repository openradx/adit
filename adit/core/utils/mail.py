from adit_radis_shared.common.utils.mail import send_mail_to_admins, send_mail_to_user
from django.template.loader import render_to_string


def send_job_finished_mail(job):
    subject = "Job finished"
    html_content = render_to_string(
        "core/mail/dicom_job_finished.html",
        {"job": job},
    )
    send_mail_to_user(job.owner, subject, html_content=html_content)


# TODO: This is not used anymore.
def send_job_failed_mail(job, celery_task_id):
    subject = "Job failed"
    html_content = render_to_string(
        "core/mail/dicom_job_failed.html",
        {"job": job, "celery_task_id": celery_task_id},
    )
    send_mail_to_admins(subject, html_content=html_content)
    send_mail_to_user(job.owner, subject, html_content=html_content)
