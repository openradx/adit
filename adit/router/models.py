from django.db import models

from adit.core.models import DicomAppSettings, DicomServer
from adit.core.validators import no_backslash_char_validator, no_control_chars_validator


class RouterSettings(DicomAppSettings):
    class Meta:
        verbose_name_plural = "Router settings"


class RouterSender(models.Model):
    server_id: int
    server = models.OneToOneField(
        DicomServer, on_delete=models.PROTECT, related_name="router_sender"
    )
    calling_ae_title = models.CharField(
        unique=True,
        max_length=16,
        blank=True,
        default="",
        validators=[no_backslash_char_validator, no_control_chars_validator],
        help_text="The AE title the server sends from. Leave empty to use its AE title.",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("calling_ae_title",)

    def __str__(self) -> str:
        return f"Router sender {self.calling_ae_title}"

    def save(self, *args, **kwargs) -> None:
        self.calling_ae_title = self.calling_ae_title.strip() or self.server.ae_title
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.server_id:
            self.calling_ae_title = self.calling_ae_title.strip() or self.server.ae_title
