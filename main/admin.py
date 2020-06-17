from django.contrib import admin
from .models import DicomServer, DicomPath, TransferJob

admin.site.site_header = 'ADIT administration'

class DicomServerAdmin(admin.ModelAdmin):
    list_display = ('node_id', 'node_name')
    exclude = ('node_type',)

class DicomPathAdmin(admin.ModelAdmin):
    list_display = ('node_id', 'node_name')
    exclude = ('node_type',)

class TransferJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'job_type', 'status', 'source',
        'destination', 'created_at', 'get_creator'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('created_by__username',)

    def get_creator(self, obj):
        return obj.created_by.username
    get_creator.short_description = 'Creator'
    get_creator.admin_order_field = 'created_by__username'

admin.site.register(DicomServer, DicomServerAdmin)
admin.site.register(DicomPath, DicomPathAdmin)
admin.site.register(TransferJob, TransferJobAdmin)