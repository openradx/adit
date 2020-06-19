from django.contrib import admin
from .models import BatchTransferJob

class BatchTransferJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'project_name', 'source', 'destination',
        'status', 'created_at', 'get_creator'
    )
    list_filter = ('status', 'created_at', 'created_by')
    search_fields = ('project_name', 'created_by__username')

    def get_creator(self, obj):
        return obj.created_by.username
    get_creator.short_description = 'Creator'
    get_creator.admin_order_field = 'created_by__username'

admin.site.register(BatchTransferJob, BatchTransferJobAdmin)