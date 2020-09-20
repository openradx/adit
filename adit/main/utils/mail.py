from django.core.mail import mail_admins, send_mail
from django.utils.html import strip_tags
from django.conf import settings


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
