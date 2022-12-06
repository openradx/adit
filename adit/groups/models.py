from django.db import models
from django.contrib.auth.models import Group
# from core.models import DicomNode


class Access(models.Model):
    
    class AccessType(models.TextChoices):
        
        SOURCE = "src", "Source"
        DESTINATION = "dst", "Destination" 

    access_type = models.CharField(max_length=3, choices=AccessType.choices, editable=False)
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='GroupAccess',
                              null=True, blank=True, default=None, editable=False)
    node = models.ForeignKey("core.DicomNode", on_delete=models.CASCADE, editable=False)
    name = models.CharField(unique=False, max_length=128, null=True, blank=True, editable=False)
    
    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        access_type_dict = dict(self.AccessType.choices)
        
        if self.group is not None:
            self.name = f"{access_type_dict[self.access_type]}_{self.group}_{self.node}"
        else:
            self.name = f"{access_type_dict[self.access_type]}_{self.node}"
        super(Access, self).save(*args, **kwargs)