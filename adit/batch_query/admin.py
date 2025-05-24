from django.contrib import admin

from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .models import BatchQueryJob, BatchQueryResult, BatchQuerySettings, BatchQueryTask


class BatchQueryResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job_id",
        "query_id",
        "patient_id",
        "study_datetime",
        "modalities",
        "study_description",
        "series_description",
        "pseudonym",
    )


admin.site.register(BatchQueryJob, DicomJobAdmin)

admin.site.register(BatchQueryResult, BatchQueryResultAdmin)

admin.site.register(BatchQueryTask, DicomTaskAdmin)

admin.site.register(BatchQuerySettings, admin.ModelAdmin)
