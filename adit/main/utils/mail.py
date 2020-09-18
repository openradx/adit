from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.conf import settings


def send_mail(subject, html_content, to):
    subject = settings.EMAIL_SUBJECT_PREFIX + subject
    text_content = strip_tags(html_content)
    msg = EmailMultiAlternatives(subject, text_content, to=to)
    msg.attach_alternative(html_content, "text/html")
    msg.send()
